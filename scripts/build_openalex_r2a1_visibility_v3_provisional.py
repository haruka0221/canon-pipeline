#!/usr/bin/env python3
"""Build a non-destructive PROVISIONAL OpenAlex v3 with R2+A1 model attribution.

No OpenAI calls, no retrieval, no human-gold/holdout modification.
The v2 operational flag is preserved; a separate v3 flag excludes model
INVALID and UNCERTAIN. Remaining non-model v2 includes are not validated.
Run from the canon-pipeline checkout with pandas and pyarrow installed.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import tempfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OA = ROOT / "derived/openalex_production"
SOURCE = OA / "retrieval_r2a1_production_identity_aware_v0_1"
V2 = OA / "integrated_work_visibility_v2"
OUT = OA / "integrated_work_visibility_v3_r2a1_model_provisional"
N = 223115
VALID = "VALID_TARGET_REFERENCE"
INVALID = "INVALID_TARGET_REFERENCE"
UNCERTAIN = "UNCERTAIN"
LABELS = {VALID, INVALID, UNCERTAIN}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def die(msg: str):
    raise RuntimeError("QC FAILED: " + msg)


def main():
    if OUT.exists():
        die(f"Output already exists; no overwrite: {OUT}")
    pairfile = V2 / "integrated_candidate_dispositions_v2.parquet"
    workfile = V2 / "openalex_visibility_by_project_work_v2.parquet"
    manifestfile = V2 / "integrated_visibility_manifest_v2.json"
    for p in (pairfile, workfile, manifestfile):
        if not p.is_file():
            die(f"Missing frozen v2 input: {p}")

    old_manifest = json.loads(manifestfile.read_text(encoding="utf-8"))
    for p in (pairfile, workfile):
        expected = old_manifest.get("output_sha256", {}).get(p.name)
        if not expected or sha(p) != expected:
            die(f"Frozen v2 output SHA mismatch: {p}")

    rows = []
    input_hashes = {}
    seen_cid = set()
    seen_ord = set()
    counts = Counter()
    for batch in range(224):
        p = (SOURCE / "batch_0000_model_results_v0_1.jsonl" if batch == 0
             else SOURCE / f"batch_{batch:04d}_continuation_v0_1/model_results.jsonl")
        if not p.is_file():
            die(f"Missing model result file: {p}")
        input_hashes[str(p.relative_to(ROOT))] = sha(p)
        this_count = 0
        with p.open(encoding="utf-8") as f:
            for line in f:
                x = json.loads(line)
                cid = x["baseline_candidate_id"]
                ord_ = int(x["production_queue_ordinal"])
                if cid in seen_cid or ord_ in seen_ord:
                    die(f"Duplicate candidate ID/ordinal: {cid} / {ord_}")
                if x["judgment"] not in LABELS:
                    die(f"Invalid model judgment: {cid}")
                seen_cid.add(cid)
                seen_ord.add(ord_)
                counts[x["judgment"]] += 1
                rows.append({
                    "baseline_candidate_id": cid,
                    "project_work_id": x["project_work_id"],
                    "openalex_work_id": x["openalex_work_id"],
                    "r2a1_model_judgment": x["judgment"],
                    "r2a1_model_reason": x["reason_code"],
                    "r2a1_model_confidence": x["confidence"],
                    "r2a1_model_context_adequacy": x["identity_context_adequacy"],
                })
                this_count += 1
        if this_count != (115 if batch == 223 else 1000):
            die(f"Unexpected batch size {batch}: {this_count}")
    if len(rows) != N or seen_ord != set(range(N)):
        die("Production IDs/ordinals incomplete")

    labels = pd.DataFrame(rows)
    pairs = pd.read_parquet(pairfile)
    works = pd.read_parquet(workfile)
    keys = ["project_work_id", "openalex_work_id"]
    if len(pairs) != 291859 or pairs.duplicated(keys).any():
        die("Frozen v2 pair dimensions/identities unexpected")
    if len(works) != 32066 or works["project_work_id"].duplicated().any():
        die("Frozen v2 work dimensions unexpected")
    if int(pairs["operational_include"].sum()) != 226221:
        die("Frozen v2 operational count changed")

    match = pairs["source_candidate_id"].isin(seen_cid)
    if match.sum() != N:
        die(f"Only {match.sum()} of {N} production IDs occur in v2")
    if not pairs.loc[match, "route"].eq("R2_A1_BASELINE").all():
        die("Production IDs map outside R2+A1")
    if not pairs.loc[match, "disposition"].eq("INCLUDE_BASELINE_UNADJUDICATED").all():
        die("Production IDs overlap previously adjudicated records")
    if not pairs.loc[match, "operational_include"].all():
        die("Production records are unexpectedly excluded in v2")

    compare = pairs.loc[match, [
        "source_candidate_id", "project_work_id", "openalex_work_id"
    ]].merge(labels[[
        "baseline_candidate_id", "project_work_id", "openalex_work_id"
    ]], left_on="source_candidate_id", right_on="baseline_candidate_id",
       validate="one_to_one", suffixes=("_v2", "_model"))
    if len(compare) != N:
        die("Model/pair merge incomplete")
    for key in keys:
        if not compare[f"{key}_v2"].eq(compare[f"{key}_model"]).all():
            die(f"Model/pair work identity mismatch: {key}")

    by_id = labels.set_index("baseline_candidate_id")
    for column in [
        "r2a1_model_judgment", "r2a1_model_reason",
        "r2a1_model_confidence", "r2a1_model_context_adequacy"
    ]:
        pairs[column] = pairs["source_candidate_id"].map(by_id[column])

    pairs["v3_provisional_include"] = pairs["operational_include"].astype(bool)
    pairs.loc[match & pairs["r2a1_model_judgment"].ne(VALID),
              "v3_provisional_include"] = False
    pairs["v3_attribution_basis"] = "UNCHANGED_V2_UNREVIEWED_OR_PREVIOUS_DISPOSITION"
    pairs.loc[match & pairs["r2a1_model_judgment"].eq(VALID),
              "v3_attribution_basis"] = "R2A1_MODEL_VALID_PROVISIONAL"
    pairs.loc[match & pairs["r2a1_model_judgment"].eq(INVALID),
              "v3_attribution_basis"] = "R2A1_MODEL_INVALID_EXCLUDED"
    pairs.loc[match & pairs["r2a1_model_judgment"].eq(UNCERTAIN),
              "v3_attribution_basis"] = "R2A1_MODEL_UNCERTAIN_HELD"

    expected_included = 226221 - counts[INVALID] - counts[UNCERTAIN]
    if int(pairs["v3_provisional_include"].sum()) != expected_included:
        die("Provisional v3 total arithmetic mismatch")
    if int(pairs["v3_provisional_include"].sum()) != 173897:
        die("Unexpected v3 provisional total: inspect before release")

    included = pairs.loc[pairs["v3_provisional_include"]]
    grouped = included.groupby("project_work_id").size().rename(
        "v3_provisional_operational_pairs")
    model_counts = pd.crosstab(
        pairs.loc[match, "project_work_id"],
        pairs.loc[match, "r2a1_model_judgment"]
    )
    model_counts = model_counts.reindex(
        columns=[VALID, INVALID, UNCERTAIN], fill_value=0
    ).rename(columns={
        VALID: "r2a1_model_valid_pairs",
        INVALID: "r2a1_model_invalid_pairs",
        UNCERTAIN: "r2a1_model_uncertain_pairs",
    })
    leftover = included.loc[
        included["r2a1_model_judgment"].isna()
    ].groupby("project_work_id").size().rename(
        "v3_included_without_new_model_judgment")

    output_works = works.join(grouped, on="project_work_id")
    output_works = output_works.join(model_counts, on="project_work_id")
    output_works = output_works.join(leftover, on="project_work_id")
    newcols = [
        "v3_provisional_operational_pairs",
        "r2a1_model_valid_pairs", "r2a1_model_invalid_pairs",
        "r2a1_model_uncertain_pairs",
        "v3_included_without_new_model_judgment"
    ]
    output_works[newcols] = output_works[newcols].fillna(0).astype("Int64")
    hold = output_works["measurement_status"].eq(
        "HOLD_PRIMARY_SUCCESSOR_NOT_RERETRIEVED")
    if hold.sum() != 1:
        die("Expected one specifically unremeasured Alcott work")
    output_works.loc[hold, [
        "v3_provisional_operational_pairs",
        "v3_included_without_new_model_judgment"
    ]] = pd.NA
    if int(output_works["v3_provisional_operational_pairs"].sum()) != expected_included:
        die("Work-level counts do not sum to pair-level counts")

    multi_oa = included.groupby("openalex_work_id")["project_work_id"].nunique()
    multi_oa = multi_oa[multi_oa > 1]
    summary = {
        "release": "openalex-integrated-work-visibility-v3-r2a1-model-provisional",
        "status": "PROVISIONAL_ATTRIBUTION_NOT_SCHOLARLY_VISIBILITY",
        "unit": "unique Project W x OpenAlex Work pair",
        "production_model_pairs": N,
        "model_judgments": dict(counts),
        "frozen_v2_operational_pairs": 226221,
        "v3_provisional_operational_pairs": expected_included,
        "removed_model_invalid": counts[INVALID],
        "held_model_uncertain": counts[UNCERTAIN],
        "included_pairs_without_new_production_model_judgment":
            int(included["r2a1_model_judgment"].isna().sum()),
        "v3_works_with_positive_candidates":
            int(output_works["v3_provisional_operational_pairs"].fillna(0).gt(0).sum()),
        "distinct_openalex_ids_linked_to_multiple_project_works":
            int(len(multi_oa)),
        "notes": [
            "v2 files and original dispositions are unchanged.",
            "Model VALID is provisional attribution, not human gold or a scholarly-scope decision.",
            "Residual v2 operational includes may be human-reviewed, policy-accepted, or unreviewed; distinguish by original disposition and provenance.",
            "The independent 600-case sealed holdout is not read or imported.",
            "No document-type filtering, bibliographic scope filtering, or same-content OA deduplication.",
            "Zero means zero in this retrieval/aggregation, not proven absence of scholarship.",
            "Preserve the one held unremeasured W as NA."
        ],
        "created_at_utc": datetime.now(timezone.utc).isoformat()
    }

    with tempfile.TemporaryDirectory(prefix=".v3_r2a1_stage_", dir=OA) as temp:
        stage = Path(temp)
        pp = stage / "integrated_candidate_dispositions_v3_provisional.parquet"
        wp = stage / "openalex_visibility_by_project_work_v3_provisional.parquet"
        wt = stage / "openalex_visibility_by_project_work_v3_provisional.tsv"
        sp = stage / "summary_v3_provisional.json"
        mp = stage / "manifest_v3_provisional.json"
        pairs.to_parquet(pp, index=False)
        output_works.to_parquet(wp, index=False)
        output_works.to_csv(wt, sep="\t", index=False)
        sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2)
                      + "\n", encoding="utf-8")
        manifest = {
            "v2_input_sha256": {
                str(p.relative_to(ROOT)): sha(p)
                for p in [pairfile, workfile, manifestfile]
            },
            "r2a1_result_sha256": input_hashes,
            "builder_sha256": sha(Path(__file__)),
            "outputs_sha256": {p.name: sha(p) for p in [pp, wp, wt, sp]},
            "no_existing_release_modified": True,
        }
        mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)
                      + "\n", encoding="utf-8")
        if OUT.exists():
            die("Output appeared concurrently")
        stage.rename(OUT)

    print("QC: PASSED; NO API CALLS; v2 and holdout unchanged")
    print("Model VALID/INVALID/UNCERTAIN:", counts[VALID], counts[INVALID], counts[UNCERTAIN])
    print("v2 operational -> v3 provisional:", 226221, "->", expected_included)
    print("Residual included without new production model judgment:",
          summary["included_pairs_without_new_production_model_judgment"])
    print("Works with positive v3 provisional candidates:",
          summary["v3_works_with_positive_candidates"])
    print("OpenAlex IDs linked to multiple W:", len(multi_oa))
    print("Output:", OUT)
    print("Top 20 provisional W:")
    print(output_works.nlargest(20, "v3_provisional_operational_pairs")[
        ["project_work_id", "v3_provisional_operational_pairs",
         "r2a1_model_valid_pairs", "v3_included_without_new_model_judgment"]
    ].to_string(index=False))


if __name__ == "__main__":
    main()
