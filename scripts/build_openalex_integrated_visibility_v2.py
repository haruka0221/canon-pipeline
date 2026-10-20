#!/usr/bin/env python3
"""Produce a separate, provenance-preserving OpenAlex integrated v2 release.

Run from a checkout of canon-pipeline after placing this file under scripts/.
Read-only with respect to all existing releases, frozen evaluations and identity
layers. Creates two NEW output directories only. Fails closed on QC mismatch.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

import pandas as pd
import pyarrow.dataset as ds

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[1] if SCRIPT.parent.name == "scripts" else Path.cwd()
if not (ROOT / "derived/openalex_production/integrated_work_visibility_v1").is_dir():
    raise SystemExit("Run this script from the canon-pipeline repository root, "
                     "or install it in the repository scripts/ directory")
OA = ROOT / "derived/openalex_production"
ID = ROOT / "derived/identity"
SCAN = Path(
    "/media/hdd1/user/tsutsui/openalex/scans/"
    "full_r23_v1/full_2040files_4a275210"
)
V1 = OA / "integrated_work_visibility_v1"
REVIEW_DIR = OA / "cross_route_intersection_review_v1"
V2 = OA / "integrated_work_visibility_v2"
WID = "W000031714"
DATE = "2026-10-20"
ROUTE = "CROSS_ROUTE_INTERSECTION"
PROVENANCE = "RESEARCHER_CHAT_CONFIRMATION_OF_MODEL_PROPOSAL"

# Fixed seven-pair residual, established by an independent read-only full-scan QC.
# These labels were explicitly ratified by the researcher in conversation on DATE;
# they are not from a blind human audit or from an existing held-out sample.
REASONS = {
    "W2525806193": "Abstract identifies Bagnold, the novel, its protagonist and historical setting.",
    "W2891432466": "Abstract explicitly names the novel in a comparative study.",
    "W2897419525": "Dissertation abstract names the novel among the works examined.",
    "W3197758999": "Book-chapter title and abstract explicitly name and discuss the novel.",
    "W4233594726": "Book-chapter abstract explicitly discusses the novel.",
    "W642125752": "Book metadata includes a contents entry identifying a section on the novel.",
    "W7056596198": "Article title explicitly identifies the author and the novel; abstract absent.",
}
OAS = sorted(REASONS)
QUERY_IDS = ("OAQ000099741", "OAQ000099742", "OAQ000099743")
QUERY_EXPECTED = {
    "OAQ000099741": ("R2", "OAA000001746", "OL1165901W", "Bagnold, Enid."),
    "OAQ000099742": ("R3", "OAA000001746", "OL1165901W", "Bagnold, Enid."),
    "OAQ000099743": ("R3", "OAA000008183", "OL17662276W", "Enid Bagnold"),
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def read_tsv(p: Path) -> pd.DataFrame:
    return pd.read_csv(p, sep="\t", dtype=str, keep_default_na=False)


def write_json(p: Path, data: dict) -> None:
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fail(message: str) -> None:
    raise RuntimeError("QC FAILED: " + message)


def check_v1() -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    v1_manifest = json.loads((V1 / "integrated_visibility_manifest_v1.json").read_text())
    for file_name, digest in v1_manifest["outputs"].items():
        p = V1 / file_name
        if sha256(p) != digest:
            fail(f"V1 frozen output hash mismatch: {p}")
    summary = json.loads((V1 / "integrated_visibility_summary_v1.json").read_text())
    pair = pd.read_parquet(V1 / "integrated_candidate_dispositions_v1.parquet")
    by_w = pd.read_parquet(V1 / "openalex_visibility_by_project_work_v1.parquet")
    if len(pair) != 291852 or len(by_w) != 32066:
        fail("v1 pair / work row counts differ from the frozen release")
    if len(pair.columns) != 9 or set(pair.columns) != {
        "project_work_id", "openalex_work_id", "route", "source_candidate_id",
        "disposition", "judgment", "judgment_provenance", "identity_gate",
        "operational_include",
    }:
        fail(f"unexpected v1 pair schema: {list(pair.columns)}")
    keys = ["project_work_id", "openalex_work_id"]
    if pair.duplicated(keys).any():
        fail("v1 pair keys are not unique")
    if int(pair["operational_include"].sum()) != 226214:
        fail("v1 included-count mismatch")
    if summary["total_candidate_pairs"] != 291852 or summary["operationally_included_pairs"] != 226214:
        fail("v1 frozen summary mismatch")
    return pair, by_w, summary, v1_manifest


def check_identity() -> tuple[pd.DataFrame, set[str]]:
    works_path = ID / "project_works_v7.tsv"
    susp_path = ID / "project_work_identity_suspensions_v1.tsv"
    v1_manifest = json.loads((V1 / "integrated_visibility_manifest_v1.json").read_text())
    for p in [works_path, susp_path]:
        k = str(p.relative_to(ROOT))
        if sha256(p) != v1_manifest["inputs"][k]:
            fail(f"frozen identity input changed: {k}")
    works = read_tsv(works_path)
    susp = read_tsv(susp_path)
    if len(works) != 32089 or len(susp) != 17:
        fail("identity source row counts changed")
    target = works[works["project_work_id"].eq(WID)]
    if len(target) != 1 or target.iloc[0]["status"] != "active":
        fail("target is not one active Project W")
    if target.iloc[0]["origin_unit_anchor_entity_id"] != "E000001746":
        fail("target anchor changed")
    affected = set(susp["project_work_id"])
    if WID in affected:
        fail("target is legacy suspended")
    return works, affected


def query_and_evidence() -> tuple[pd.DataFrame, pd.DataFrame]:
    qr_path = OA / "registry_v4/openalex_queries_v4.tsv"
    registry = read_tsv(qr_path)
    q = registry[registry["query_id"].isin(QUERY_IDS)].copy()
    if len(q) != 3 or set(q["query_id"]) != set(QUERY_IDS):
        fail("three logical queries missing or duplicated")
    for r in q.to_dict("records"):
        route, alias, source, author = QUERY_EXPECTED[r["query_id"]]
        if (r["project_work_id"], r["query_route"], r["alias_id"],
            r["alias_source_record_id"], r["query_author"]) != (WID, route, alias, source, author):
            fail("frozen query registry differs: " + r["query_id"])
        if r["query_title"].strip().casefold() != "the happy foreigner":
            fail("target query title changed")
    ev_path = SCAN / "openalex_retrieval_full_r23_hit_evidence_v1.parquet"
    dataset = ds.dataset(str(ev_path), format="parquet")
    columns = ["project_work_id", "openalex_work_id", "target_lane", "query_route",
               "author_a1_hit", "author_a2_hit", "query_id", "execution_id",
               "alias_id", "alias_project_source_entity_id"]
    if not set(columns) <= set(dataset.schema.names):
        fail("hit-evidence schema mismatch")
    filt = ((ds.field("project_work_id") == WID) &
            ds.field("openalex_work_id").isin(OAS) &
            (ds.field("target_lane") == "resolved_w"))
    ev = dataset.to_table(columns=columns, filter=filt).to_pandas()
    if len(ev) != 21 or ev.duplicated(["openalex_work_id", "query_id"]).any():
        fail("expected exactly three distinct query hits per each of seven OA works")
    for oa in OAS:
        z = ev[ev["openalex_work_id"].eq(oa)]
        if set(z["query_id"]) != set(QUERY_IDS):
            fail(f"query evidence different for {oa}")
        for r in z.to_dict("records"):
            route, alias, _, _ = QUERY_EXPECTED[r["query_id"]]
            if r["query_route"] != route or r["alias_id"] != alias:
                fail(f"route or alias inconsistent for {oa}")
            expected = {
                "OAQ000099741": (False, True),
                "OAQ000099742": (False, True),
                "OAQ000099743": (True, True),
            }[r["query_id"]]
            if (bool(r["author_a1_hit"]), bool(r["author_a2_hit"])) != expected:
                fail(f"frozen author-hit evidence inconsistent for {oa}")
    ev = ev.sort_values(["openalex_work_id", "query_id"]).reset_index(drop=True)
    return q.sort_values("query_id").reset_index(drop=True), ev


def oa_metadata() -> pd.DataFrame:
    p = SCAN / "openalex_retrieval_full_r23_oa_records_v1.parquet"
    dataset = ds.dataset(str(p), format="parquet")
    needed = ["openalex_work_id", "display_name", "abstract", "abstract_present",
              "publication_year", "type", "doi", "is_retracted"]
    if not set(needed) <= set(dataset.schema.names):
        fail("OpenAlex metadata schema differs")
    m = dataset.to_table(
        columns=needed, filter=ds.field("openalex_work_id").isin(OAS)
    ).to_pandas()
    if len(m) != 7 or m["openalex_work_id"].duplicated().any() or set(m["openalex_work_id"]) != set(OAS):
        fail("could not retrieve exactly seven frozen OA metadata records")
    for r in m.to_dict("records"):
        text = (str(r["display_name"] or "") + "\n" + str(r["abstract"] or "")).casefold()
        if "the happy foreigner" not in text:
            fail("no explicit title reference: " + r["openalex_work_id"])
    return m.sort_values("openalex_work_id").reset_index(drop=True)


def build_review(meta: pd.DataFrame, query: pd.DataFrame, ev: pd.DataFrame, out: Path) -> Path:
    rows = []
    for oa in OAS:
        r = meta[meta["openalex_work_id"].eq(oa)].iloc[0]
        rows.append({
            "review_case_id": f"CRI_V1_{len(rows)+1:04d}",
            "project_work_id": WID,
            "openalex_work_id": oa,
            "judgment": "VALID_TARGET_REFERENCE",
            "reason_code": "DIRECT_TARGET_REFERENCE",
            "judgment_provenance": PROVENANCE,
            "researcher_confirmation_date": DATE,
            "review_method": "RESEARCHER_CONFIRMED_ASSISTANT_PRESENTED_SNAPSHOT_EVIDENCE_IN_CHAT",
            "review_note": REASONS[oa],
            "oa_display_name": r["display_name"],
            "oa_abstract": r["abstract"] if isinstance(r["abstract"], str) else "",
            "oa_publication_year": r["publication_year"],
            "oa_type": r["type"],
            "oa_doi": r["doi"] if isinstance(r["doi"], str) else "",
            "supporting_query_ids": ";".join(QUERY_IDS),
            "possible_content_duplicate_with": (
                "W4233594726" if oa == "W2525806193" else
                "W2525806193" if oa == "W4233594726" else ""
            ),
        })
    review = pd.DataFrame(rows)
    review_path = out / "cross_route_intersection_review_v1.tsv"
    review.to_csv(review_path, sep="\t", index=False, lineterminator="\n")
    q_path = out / "cross_route_intersection_queries_v1.tsv"
    query.to_csv(q_path, sep="\t", index=False, lineterminator="\n")
    ev_path = out / "cross_route_intersection_hit_evidence_v1.tsv"
    ev.to_csv(ev_path, sep="\t", index=False, lineterminator="\n")
    note = """# OpenAlex cross-route intersection review v1

- Status: researcher-confirmed, model-assisted source review; 2026-10-20.
- Unit: distinct Project W x OpenAlex Work, W000031714 / The Happy Foreigner.
- All seven: VALID_TARGET_REFERENCE / DIRECT_TARGET_REFERENCE.
- Provenance: ChatGPT proposed labels from the frozen OpenAlex titles and
  abstracts/contents; the researcher explicitly reviewed and ratified those
  labels in the 2026-10-20 conversation. This is NOT an independent blind human
  audit, and is not part of the frozen calibration, held-out or baseline sample.
- Query intersection: (R2+A2 intersection R3+A1) minus R2+A1, with confirmed
  three-query evidence for each candidate and no overlap with integrated v1.
- W2525806193 (2016 article) and W4233594726 (2019 book chapter) may contain
  the same scholarly content; this is a separate future deduplication QC,
  NOT a basis to discard either unique OpenAlex ID from this release.
- No changes were made to Work/Edition identity, OL audits, baseline decisions,
  frozen marginal decisions, LLM/held-out labels, or OpenAlex retrieval policy.
"""
    note_path = out / "README.md"
    note_path.write_text(note, encoding="utf-8")
    manifest_path = out / "cross_route_intersection_review_manifest_v1.json"
    inputs = [
        OA / "registry_v4/openalex_queries_v4.tsv",
        V1 / "integrated_visibility_manifest_v1.json",
        SCAN / "openalex_retrieval_full_r23_scan_v1_manifest.json",
    ]
    write_json(manifest_path, {
        "release": "openalex-cross-route-intersection-review-v1",
        "reviewed_date": DATE,
        "status": "RESEARCHER_CONFIRMED_MODEL_ASSISTED",
        "cases": 7,
        "evidence_rows": 21,
        "inputs_sha256": {str(p): sha256(p) for p in inputs},
        "scan_artifacts": {
            "hit_evidence": str(SCAN / "openalex_retrieval_full_r23_hit_evidence_v1.parquet"),
            "oa_records": str(SCAN / "openalex_retrieval_full_r23_oa_records_v1.parquet"),
        },
        "outputs_sha256": {p.name: sha256(p) for p in [review_path, q_path, ev_path, note_path]},
    })
    return review_path


def build_v2(v1_pairs: pd.DataFrame, old_by_w: pd.DataFrame, old_summary: dict,
             affected: set[str], review_path: Path, review_out: Path, out: Path) -> dict:
    keys = ["project_work_id", "openalex_work_id"]
    review = read_tsv(review_path)
    if len(review) != 7 or (set(review["openalex_work_id"]) != set(OAS)):
        fail("review table changed unexpectedly")
    if not review["judgment"].eq("VALID_TARGET_REFERENCE").all():
        fail("not all researcher-confirmed judgments are valid")
    if not review["reason_code"].eq("DIRECT_TARGET_REFERENCE").all():
        fail("reason code differs")
    add = pd.DataFrame({
        "project_work_id": review["project_work_id"],
        "openalex_work_id": review["openalex_work_id"],
        "route": ROUTE,
        "source_candidate_id": review["review_case_id"],
        "disposition": "INCLUDE_FINAL_VALID",
        "judgment": review["judgment"],
        "judgment_provenance": review["judgment_provenance"],
        "identity_gate": "ELIGIBLE_FOR_R2A1_ADJUDICATION",
        "operational_include": True,
    })
    if set(add["project_work_id"]) != {WID} or WID in affected:
        fail("cross-route identity not eligible")
    if set(map(tuple, add[keys].itertuples(index=False, name=None))) & set(
        v1_pairs[keys].itertuples(index=False, name=None)
    ):
        fail("new pairs overlap frozen v1")
    add = add[v1_pairs.columns]
    combined = pd.concat([v1_pairs, add], ignore_index=True)
    if len(combined) != 291859 or combined.duplicated(keys).any():
        fail("v2 pair-set cardinality or key uniqueness failed")
    if not combined.iloc[:len(v1_pairs)].reset_index(drop=True).equals(v1_pairs.reset_index(drop=True)):
        fail("v1 rows changed during append")
    if int(combined["operational_include"].sum()) != 226221:
        fail("v2 included count mismatch")
    if not combined.loc[combined["operational_include"], "project_work_id"].isin(affected).sum() == 0:
        fail("legacy identity suspension violated")
    previous_cols = old_by_w.columns.tolist()
    by_w = old_by_w.copy()
    if "cross_route_operational_pairs" in by_w.columns:
        fail("cross-route work column already exists in v1")
    at = by_w.columns.get_loc("total_operational_pairs")
    by_w.insert(at, "cross_route_operational_pairs", pd.Series(0, index=by_w.index, dtype="Int64"))
    target = by_w["project_work_id"].eq(WID)
    if target.sum() != 1 or int(by_w.loc[target, "total_operational_pairs"].iloc[0]) != 1:
        fail("frozen target W had unexpected baseline count")
    by_w.loc[target, "cross_route_operational_pairs"] = 7
    by_w.loc[target, "total_operational_pairs"] = 8
    alcott = by_w["project_work_id"].eq("W000014515")
    if alcott.sum() != 1 or by_w.loc[alcott, "measurement_status"].iloc[0] != "HOLD_PRIMARY_SUCCESSOR_NOT_RERETRIEVED":
        fail("Alcott successor status changed")
    by_w.loc[alcott, "cross_route_operational_pairs"] = pd.NA
    if not by_w.loc[alcott, "total_operational_pairs"].isna().all():
        fail("Alcott successor became zero or nonnull")
    if (int(by_w["total_operational_pairs"].sum()) != 226221 or
        int(by_w["total_operational_pairs"].fillna(0).gt(0).sum()) != 7077):
        fail("work-level v2 aggregation invariant failed")
    # Check all original v1 work-level columns, except the target total, unchanged.
    before = old_by_w.loc[~target, previous_cols].reset_index(drop=True)
    after = by_w.loc[~target, previous_cols].reset_index(drop=True)
    pd.testing.assert_frame_equal(before, after)
    pair_path = out / "integrated_candidate_dispositions_v2.parquet"
    work_tsv = out / "openalex_visibility_by_project_work_v2.tsv"
    work_pq = out / "openalex_visibility_by_project_work_v2.parquet"
    summary_path = out / "integrated_visibility_summary_v2.json"
    manifest_path = out / "integrated_visibility_manifest_v2.json"
    combined.to_parquet(pair_path, index=False)
    by_w.to_csv(work_tsv, sep="\t", index=False, lineterminator="\n")
    by_w.to_parquet(work_pq, index=False)
    route_counts = {
        k: int(v) for k, v in combined.loc[combined["operational_include"], "route"].value_counts().items()
    }
    if route_counts.get(ROUTE) != 7:
        fail("new route count mismatch")
    summary = dict(old_summary)
    summary.update({
        "release": "openalex-integrated-work-visibility-v2",
        "total_candidate_pairs": 291859,
        "operationally_included_pairs": 226221,
        "included_by_route": route_counts,
        "cross_route_intersection_review": "cross_route_intersection_review_v1",
        "cross_route_researcher_confirmed_pairs": 7,
        "cross_route_review_provenance": PROVENANCE,
        "v1_candidate_pairs_preserved": 291852,
    })
    summary["semantics"] = dict(old_summary["semantics"])
    summary["semantics"]["cross_route_intersection"] = (
        "Seven residual (R2+A2 intersect R3+A1) minus R2+A1 pairs; "
        "individually confirmed by researcher after viewing model-presented "
        "frozen OpenAlex evidence in chat; NOT blind independent adjudication."
    )
    summary["semantics"]["duplicates"] = (
        "Unique OpenAlex Work IDs; possible same-content works are NOT deduplicated."
    )
    write_json(summary_path, summary)
    inputs = [
        V1 / "integrated_candidate_dispositions_v1.parquet",
        V1 / "openalex_visibility_by_project_work_v1.parquet",
        V1 / "integrated_visibility_manifest_v1.json",
        review_path,
        review_out / "cross_route_intersection_review_manifest_v1.json",
    ]
    write_json(manifest_path, {
        "release": summary["release"],
        "base_release": "openalex-integrated-work-visibility-v1",
        "input_sha256": {str(p): sha256(p) for p in inputs},
        "output_sha256": {p.name: sha256(p) for p in [pair_path, work_tsv, work_pq, summary_path]},
        "invariants": {
            "raw_pairs": 291859,
            "operational_included": 226221,
            "cross_route_included": 7,
            "active_works": 32066,
            "works_with_operational_candidates": 7077,
            "source_light_unremeasured_works": 1,
            "held_legacy_pairs": 65546,
        },
    })
    return summary


def main() -> None:
    if REVIEW_DIR.exists() or V2.exists():
        fail("output directory already exists: no overwriting allowed")
    v1_pairs, v1_by_w, v1_summary, _ = check_v1()
    _, affected = check_identity()
    query, evidence = query_and_evidence()
    records = oa_metadata()
    if len(OAS) != len(set(OAS)) or len(OAS) != 7:
        fail("case IDs not unique")
    # Stage both releases outside final names, so validation failures never
    # partially create a released output directory.
    with tempfile.TemporaryDirectory(prefix=".openalex_v2_staging_", dir=OA) as temp:
        stage = Path(temp)
        review_stage = stage / REVIEW_DIR.name
        v2_stage = stage / V2.name
        review_stage.mkdir()
        v2_stage.mkdir()
        review_path = build_review(records, query, evidence, review_stage)
        summary = build_v2(v1_pairs, v1_by_w, v1_summary, affected,
                           review_path, review_stage, v2_stage)
        # Normalize path keys inside v2 manifest: temporary staging paths should
        # not appear in provenance records of the published release.
        v2_manifest_path = v2_stage / "integrated_visibility_manifest_v2.json"
        v2_manifest = json.loads(v2_manifest_path.read_text())
        changes = {}
        for k, v in v2_manifest["input_sha256"].items():
            if k.startswith(str(review_stage)):
                changes[str(REVIEW_DIR / Path(k).name)] = v
            else:
                changes[k] = v
        v2_manifest["input_sha256"] = changes
        write_json(v2_manifest_path, v2_manifest)
        REVIEW_DIR.parent.mkdir(parents=True, exist_ok=True)
        if REVIEW_DIR.exists() or V2.exists():
            fail("output directories appeared while building")
        review_stage.rename(REVIEW_DIR)
        v2_stage.rename(V2)
    print("=== OPENALEX CROSS-ROUTE REVIEW + INTEGRATED V2 ===")
    print("Researcher-confirmed cases: 7 (2026-10-20; model-assisted chat review)")
    print("Frozen v1 raw / operational: 291852 / 226214")
    print("New v2 raw / operational:", summary["total_candidate_pairs"],
          "/", summary["operationally_included_pairs"])
    print("Target W operational pairs: 1 -> 8")
    print("Works with operational candidates: 7077 (unchanged)")
    print("Legacy held: 65546; Alcott unremeasured: NA (unchanged)")
    print("Review output:", REVIEW_DIR)
    print("V2 output:", V2)
    print("QC: PASSED")


if __name__ == "__main__":
    main()
