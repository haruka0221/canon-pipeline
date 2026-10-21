#!/usr/bin/env python3
"""Compare the already-entered 40 researcher labels to the sealed Luna key.

Development diagnostics only: the 40 were deliberately sampled using model
judgments and are not an independent precision estimator. Does not touch 600
blind holdout, previous predictions, integrated v2, or original human TSV.

From the canon-pipeline-openalex-a2val repository root:
    python -B scripts/compare_openalex_development_40_human_vs_luna_v0_1.py
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import sys

import pandas as pd

ROOT = Path.cwd()
BASE = ROOT / "derived/openalex_production/retrieval_r2a1_development_160_review_v0_1"
REVIEW = BASE / "researcher_review_v0_1/development_40_blind_review_v0_1_judged.tsv"
ORIGINAL = BASE / "development_40_blind_review_v0_1.tsv"
KEY = BASE / "development_40_model_key_DO_NOT_OPEN_BEFORE_BLIND_REVIEW_v0_1.tsv"
OUT = BASE / "researcher_review_v0_1/development_40_luna_comparison_v0_1"
LABELS = ("VALID_TARGET_REFERENCE", "INVALID_TARGET_REFERENCE", "UNCERTAIN")
CANON = {
    "VALID": LABELS[0],
    "VALID_TARGET_REFERENCE": LABELS[0],
    "INVALID": LABELS[1],
    "INVALID_TARGET_REFERENCE": LABELS[1],
    "UNCERTAIN": LABELS[2],
    "UNSURE": LABELS[2],
    "保留": LABELS[2],
    "不明": LABELS[2],
}
KEYCOLS = ("review_case_id", "baseline_candidate_id", "project_work_id", "openalex_work_id")


def read_tsv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Missing: {path}")
    return pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False,
                       encoding="utf-8-sig")


def digest(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def ensure_identical_keys(a: pd.DataFrame, b: pd.DataFrame, name: str) -> None:
    for col in KEYCOLS:
        if col not in a or col not in b:
            raise ValueError(f"{name}: missing key column {col}")
    if len(a) != 40 or len(b) != 40:
        raise ValueError(f"{name}: expected 40 rows, found {len(a)} and {len(b)}")
    for df in (a, b):
        if df[list(KEYCOLS)].duplicated().any() or df[list(KEYCOLS)].eq("").any().any():
            raise ValueError(f"{name}: duplicate or empty key")
    aa = a[list(KEYCOLS)].sort_values("baseline_candidate_id").reset_index(drop=True)
    bb = b[list(KEYCOLS)].sort_values("baseline_candidate_id").reset_index(drop=True)
    if not aa.equals(bb):
        raise ValueError(f"{name}: identifiers do not match frozen review packet")


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"Refusing to overwrite prior comparison: {OUT}")

    review = read_tsv(REVIEW)
    original = read_tsv(ORIGINAL)
    ensure_identical_keys(review, original, "Judged vs original blind sheet")
    for col in ("target_title", "target_author", "openalex_title", "openalex_abstract"):
        if col not in review or col not in original:
            raise ValueError(f"Missing original evidence field {col}")
        aligned = review.set_index("baseline_candidate_id").loc[original.baseline_candidate_id]
        if not aligned[col].reset_index(drop=True).equals(original[col].reset_index(drop=True)):
            raise ValueError(f"The source evidence field {col} differs from the original blind sheet."
                             " Check Excel TSV import/export; do not silently compare altered evidence.")

    label_col = "reviewer_target_attribution_judgment"
    if label_col not in review:
        raise ValueError(f"Missing reviewer judgment column: {label_col}")
    labels = review[label_col].str.strip().str.upper().map(CANON)
    incomplete = labels.isna()
    if incomplete.any():
        print("STOP BEFORE OPENING MODEL KEY: incomplete/unrecognized human judgments:")
        for _, r in review.loc[incomplete, ["review_case_id", "baseline_candidate_id", label_col]].iterrows():
            print(" ", r.review_case_id, r.baseline_candidate_id, repr(r[label_col]))
        print("Please complete or correct these rows in your judged TSV. No files were written.")
        sys.exit(2)

    # Unblind only after validating that all 40 judgments are in place.
    key = read_tsv(KEY)
    ensure_identical_keys(review, key, "Judged sheet vs frozen model key")
    if "judgment" not in key or not key.judgment.isin(LABELS).all():
        raise ValueError("Malformed Luna key judgments")
    if "model" in key and set(key.model) != {"gpt-6-luna"}:
        raise ValueError("Unexpected model in key")

    kept = ["review_case_id", "baseline_candidate_id", "project_work_id", "openalex_work_id",
            "target_title", "target_author", "openalex_title", label_col,
            "reviewer_reason_code", "reviewer_evidence_note", "reviewer_identity_context_status",
            "reviewer_external_sources", "reviewer_name", "review_date"]
    kept = [c for c in kept if c in review]
    compare = review[kept].copy()
    compare["human_normalized"] = labels.to_list()
    key_use = key.drop(columns=[c for c in KEYCOLS if c != "baseline_candidate_id"])
    compare = compare.merge(key_use, on="baseline_candidate_id", how="left", validate="one_to_one")
    if len(compare) != 40 or compare.judgment.isna().any():
        raise ValueError("40-row merge failed")
    compare["exact_agreement"] = compare.human_normalized.eq(compare.judgment)
    compare["disagreement_type"] = "AGREE"
    compare.loc[~compare.exact_agreement, "disagreement_type"] = "OTHER_DISAGREEMENT"
    compare.loc[compare.human_normalized.eq(LABELS[0]) & compare.judgment.eq(LABELS[1]),
                "disagreement_type"] = "HUMAN_VALID__LUNA_INVALID"
    compare.loc[compare.human_normalized.eq(LABELS[1]) & compare.judgment.eq(LABELS[0]),
                "disagreement_type"] = "HUMAN_INVALID__LUNA_VALID"
    compare.loc[compare.human_normalized.eq(LABELS[2]) & ~compare.judgment.eq(LABELS[2]),
                "disagreement_type"] = "HUMAN_UNCERTAIN__LUNA_DECISIVE"
    compare.loc[~compare.human_normalized.eq(LABELS[2]) & compare.judgment.eq(LABELS[2]),
                "disagreement_type"] = "HUMAN_DECISIVE__LUNA_UNCERTAIN"

    table = pd.crosstab(compare.human_normalized, compare.judgment).reindex(
        index=LABELS, columns=LABELS, fill_value=0
    )
    summary = {
        "release": "r2a1-development-40-human-vs-luna-v0_1",
        "status": "DEVELOPMENT_DIAGNOSTIC_NOT_PRECISION_ESTIMATE",
        "reviewed_n": 40,
        "human_counts": dict(Counter(compare.human_normalized)),
        "luna_counts": dict(Counter(compare.judgment)),
        "exact_agreement": int(compare.exact_agreement.sum()),
        "disagreements": int((~compare.exact_agreement).sum()),
        "human_valid_luna_invalid": int((compare.disagreement_type == "HUMAN_VALID__LUNA_INVALID").sum()),
        "human_invalid_luna_valid": int((compare.disagreement_type == "HUMAN_INVALID__LUNA_VALID").sum()),
        "human_uncertain_luna_decisive": int((compare.disagreement_type == "HUMAN_UNCERTAIN__LUNA_DECISIVE").sum()),
        "human_decisive_luna_uncertain": int((compare.disagreement_type == "HUMAN_DECISIVE__LUNA_UNCERTAIN").sum()),
        "confusion_table_human_rows_luna_columns": table.to_dict(orient="index"),
        "review_selection": "MODEL_STRATIFIED_DIAGNOSTIC_NOT_ESTIMATOR",
        "independence_note": "Diagnostic 40 were chosen using Luna labels; some earlier Luna and AI reviews were seen in chat; not a blind independent gold-standard evaluation.",
        "holdout_600_accessed": False,
        "any_api_calls": False,
        "source_hashes": {str(p.relative_to(ROOT)): digest(p) for p in (REVIEW, ORIGINAL, KEY)},
    }
    OUT.mkdir(parents=True, exist_ok=False)
    compare.to_csv(OUT / "development_40_researcher_luna_paired_v0_1.tsv",
                   sep="\t", index=False, lineterminator="\n")
    (OUT / "development_40_comparison_summary_v0_1.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8"
    )
    print("=== DEVELOPMENT 40: RESEARCHER × LUNA DIAGNOSTIC ===")
    print("Human:", summary["human_counts"])
    print("Luna:", summary["luna_counts"])
    print("Exact agreement:", summary["exact_agreement"], "/ 40")
    print("Human VALID / Luna INVALID:", summary["human_valid_luna_invalid"])
    print("Human INVALID / Luna VALID:", summary["human_invalid_luna_valid"])
    print("Human UNCERTAIN / Luna decisive:", summary["human_uncertain_luna_decisive"])
    print("Human decisive / Luna UNCERTAIN:", summary["human_decisive_luna_uncertain"])
    print("\n=== CONFUSION MATRIX (human rows / Luna columns) ===")
    print(table.to_string())
    print("\n=== NONAGREEMENT CASES ===")
    for r in compare.loc[~compare.exact_agreement].itertuples(index=False):
        print(f"{r.review_case_id} | {r.project_work_id} | {r.target_title[:60]} | "
              f"HUMAN={r.human_normalized} | LUNA={r.judgment} | {r.disagreement_type}")
    print("\nOutput:", OUT)
    print("NO API; old judgments, integrated v2, and holdout 600 untouched.")
    print("Diagnostic only; do NOT extrapolate rates to ~22万 candidates.")


if __name__ == "__main__":
    main()
