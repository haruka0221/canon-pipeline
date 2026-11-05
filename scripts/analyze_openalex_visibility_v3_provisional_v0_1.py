#!/usr/bin/env python3
"""Read-only diagnostic analysis of provisional OpenAlex v3.

Reads frozen v3 outputs and Project Works v7 identity. Creates only a separate,
versioned analysis directory; no LLM/API calls or modifications of input data.
Cross-W OpenAlex reuse is a QC SIGNAL, not automatically a false attribution.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OA = ROOT / "derived/openalex_production"
V3 = OA / "integrated_work_visibility_v3_r2a1_model_provisional"
PAIRS = V3 / "integrated_candidate_dispositions_v3_provisional.parquet"
WORK_COUNTS = V3 / "openalex_visibility_by_project_work_v3_provisional.parquet"
IDENTITY = ROOT / "derived/identity/project_works_v7.tsv"
OUT = OA / "analysis_v3_provisional_diagnostics_v0_1"
TOP_KEYS = ["W000030950", "W000017666", "W000016985"]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for part in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def field(cols, preferred, keyword):
    for x in preferred:
        if x in cols:
            return x
    matches = [x for x in cols
               if keyword in x.casefold() and not any(
                   bad in x.casefold() for bad in ("normalized", "sort", "alias",
                                                  "variant", "id", "search"))]
    return matches[0] if matches else None


def fail(reason: str):
    raise RuntimeError("QC FAILED: " + reason)


def main() -> None:
    if OUT.exists():
        fail(f"analysis output already exists; never overwrite: {OUT}")
    for path in [PAIRS, WORK_COUNTS, IDENTITY]:
        if not path.is_file():
            fail(f"Input missing: {path}")

    p = pd.read_parquet(PAIRS)
    w = pd.read_parquet(WORK_COUNTS)
    keys = ["project_work_id", "openalex_work_id"]
    if len(p) != 291859 or p.duplicated(keys).any():
        fail("Unexpected v3 pair count or duplicate pairs")
    if len(w) != 32066 or w.project_work_id.duplicated().any():
        fail("Unexpected v3 W count or duplicate W")
    inc = p.loc[p.v3_provisional_include.eq(True), keys].copy()
    if len(inc) != 173897:
        fail("Provisional included pair count changed")
    if int(w.v3_provisional_operational_pairs.sum()) != 173897:
        fail("W counts do not sum to pair counts")

    meta = pd.read_csv(IDENTITY, sep="\t", dtype=str, keep_default_na=False)
    if "project_work_id" not in meta or meta.project_work_id.duplicated().any():
        fail("Project Works source lacks unique project_work_id")
    title_col = field(meta.columns, [
        "canonical_title", "representative_title", "work_title", "display_title",
        "preferred_title", "title", "target_title", "original_title"
    ], "title")
    author_col = field(meta.columns, [
        "canonical_author", "representative_author", "author_name",
        "display_author", "work_author", "author", "target_author"
    ], "author")
    metadata = meta[["project_work_id"]].copy()
    metadata["work_title_from_v7"] = meta[title_col] if title_col else ""
    metadata["work_author_from_v7"] = meta[author_col] if author_col else ""
    overview = w.merge(metadata, on="project_work_id", how="left", validate="one_to_one")
    overview["rank_v3"] = overview.v3_provisional_operational_pairs.rank(
        ascending=False, method="min", na_option="bottom")
    overview["rank_v2"] = overview.total_operational_pairs.rank(
        ascending=False, method="min", na_option="bottom")
    overview["v2_minus_v3_pairs"] = (
        overview.total_operational_pairs - overview.v3_provisional_operational_pairs)
    overview = overview.sort_values(
        ["v3_provisional_operational_pairs", "project_work_id"],
        ascending=[False, True], na_position="last")

    # An OpenAlex record may validly discuss multiple works. Preserve and
    # quantify cross-W reuse rather than deduplicating globally.
    oa_mult = inc.groupby("openalex_work_id").project_work_id.nunique()
    shared_ids = set(oa_mult.index[oa_mult.gt(1)])
    if len(shared_ids) != 24001:
        fail(f"Expected 24,001 shared OpenAlex IDs; found {len(shared_ids)}")
    shared_pairs = inc.openalex_work_id.isin(shared_ids).sum()
    reuse_hist = {
        str(int(n)): int(v) for n, v in
        oa_mult.value_counts().sort_index().items()
    }
    shared = inc.loc[inc.openalex_work_id.isin(shared_ids)].copy()
    grouped = shared.groupby("openalex_work_id").agg(
        linked_project_w_count=("project_work_id", "nunique"),
        linked_project_w_ids=("project_work_id", lambda x: ";".join(sorted(set(x))))
    ).reset_index().sort_values(
        ["linked_project_w_count", "openalex_work_id"], ascending=[False, True])

    associations = {
        key: set(inc.loc[inc.project_work_id.eq(key), "openalex_work_id"])
        for key in TOP_KEYS
    }
    overlaps = []
    for i, a in enumerate(TOP_KEYS):
        for b in TOP_KEYS[i + 1:]:
            intersect = associations[a] & associations[b]
            union = associations[a] | associations[b]
            overlaps.append({
                "project_w_a": a,
                "project_w_b": b,
                "a_pairs": len(associations[a]),
                "b_pairs": len(associations[b]),
                "shared_openalex_ids": len(intersect),
                "jaccard": round(len(intersect) / len(union), 6) if union else None,
                "shared_openalex_sample_10": ";".join(sorted(intersect)[:10]),
            })

    positive = overview.loc[overview.v3_provisional_operational_pairs.gt(0)]
    summary = {
        "status": "READ_ONLY_DIAGNOSTIC_NOT_SCHOLARLY_VISIBILITY",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "v3_included_pairs": int(len(inc)),
        "v3_works": int(len(overview)),
        "positive_candidate_works": int(len(positive)),
        "unique_openalex_ids_included": int(len(oa_mult)),
        "openalex_ids_linked_to_multiple_w": int(len(shared_ids)),
        "included_pairs_on_shared_openalex_ids": int(shared_pairs),
        "shared_pair_fraction": round(float(shared_pairs / len(inc)), 6),
        "openalex_id_w_count_distribution": reuse_hist,
        "top_10_w_share_of_pair_counts": round(
            float(positive.v3_provisional_operational_pairs.head(10).sum() / len(inc)), 6),
        "top_100_w_share_of_pair_counts": round(
            float(positive.v3_provisional_operational_pairs.head(100).sum() / len(inc)), 6),
        "median_pairs_among_positive_w": float(
            positive.v3_provisional_operational_pairs.median()),
        "top_three_w_pairwise_overlap": overlaps,
        "identity_title_column_used": title_col,
        "identity_author_column_used": author_col,
        "interpretation_warning": (
            "Counts are work-document candidate pairs, not verified scholarly citations. "
            "Shared OpenAlex IDs may be appropriate multi-work references. "
            "Work scope and OpenAlex document suitability are not screened."
        ),
    }

    with tempfile.TemporaryDirectory(prefix=".oa_v3_diag_", dir=OA) as tmp:
        stage = Path(tmp)
        op = stage / "all_project_w_v3_provisional_ranking.tsv"
        tp = stage / "top100_project_w_v3_provisional.tsv"
        sh = stage / "shared_openalex_ids_v3_provisional.tsv"
        ov = stage / "top3_w_pairwise_overlap.tsv"
        summary_path = stage / "analysis_summary.json"
        manifest_path = stage / "analysis_manifest.json"
        overview.to_csv(op, sep="\t", index=False)
        overview.head(100).to_csv(tp, sep="\t", index=False)
        grouped.to_csv(sh, sep="\t", index=False)
        pd.DataFrame(overlaps).to_csv(ov, sep="\t", index=False)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        manifest = {
            "source_sha256": {
                str(q.relative_to(ROOT)): sha(q) for q in [PAIRS, WORK_COUNTS, IDENTITY]
            },
            "outputs_sha256": {
                x.name: sha(x) for x in [op, tp, sh, ov, summary_path]
            },
            "script_sha256": sha(Path(__file__)),
            "no_input_modification": True,
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        if OUT.exists():
            fail("Analysis output directory appeared concurrently")
        stage.rename(OUT)

    print("DIAGNOSTIC QC: PASSED; API CALLS: 0")
    print(f"Included work-document pairs: {len(inc):,}")
    print(f"Distinct OpenAlex IDs: {len(oa_mult):,}")
    print(f"OpenAlex IDs associated with multiple W: {len(shared_ids):,}")
    print(f"Candidate pairs belonging to shared OpenAlex IDs: {shared_pairs:,} ({shared_pairs/len(inc):.1%})")
    print(f"Positive W: {len(positive):,}; top 10 share: {summary['top_10_w_share_of_pair_counts']:.1%}; top 100 share: {summary['top_100_w_share_of_pair_counts']:.1%}")
    print(f"Identity display columns: title={title_col}, author={author_col}")
    cols = ["project_work_id", "work_title_from_v7", "work_author_from_v7",
            "total_operational_pairs", "v3_provisional_operational_pairs",
            "r2a1_model_valid_pairs", "v3_included_without_new_model_judgment",
            "v2_minus_v3_pairs"]
    print("\nTOP 20 PROJECT WORKS:")
    print(overview[cols].head(20).to_string(index=False))
    print("\nTOP-THREE W PAIRWISE OVERLAP:")
    print(pd.DataFrame(overlaps)[["project_w_a", "project_w_b",
                                  "shared_openalex_ids", "jaccard"]].to_string(index=False))
    print("\nAnalysis directory:", OUT)


if __name__ == "__main__":
    main()
