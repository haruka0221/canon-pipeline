from pathlib import Path
import json
import pandas as pd

ROOT = Path("derived/benchmark/judgments")
INPUT = ROOT / "input" / "wikidata_judge_input_130.csv"

FILES = {
    "claude": ROOT / "raw" / "claude_sonnet5_high_2026-09-11.csv",
    "gemini": ROOT / "raw" / "gemini_3.1_pro_2026-09-11.csv",
}

EXPECTED_COLUMNS = [
    "target_id",
    "title",
    "decision",
    "selected_qid",
    "alternative_qids",
    "confidence",
    "issue_codes",
    "reason",
]

ALLOWED_DECISIONS = {"MATCH", "NO_MATCH", "AMBIGUOUS"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_ISSUES = {
    "duplicate_work_items",
    "edition_or_translation",
    "edition_without_work_item",
    "adaptation",
    "author_ambiguity",
    "missing_metadata",
    "title_variant",
    "wrong_work",
}


def split_semicolon(value):
    if pd.isna(value) or not str(value).strip():
        return []
    return [x.strip() for x in str(value).split(";") if x.strip()]


inp = pd.read_csv(INPUT, dtype=str).fillna("")

candidate_sets = {}
input_titles = {}

for _, row in inp.iterrows():
    tid = row["target_id"]
    input_titles[tid] = row["title"]
    candidates = json.loads(row["candidates_json"])
    candidate_sets[tid] = {c["qid"] for c in candidates}

print(f"INPUT: {len(inp)} rows, {inp['target_id'].nunique()} unique target_ids")
print()

for model, path in FILES.items():
    print("=" * 70)
    print(model.upper(), path)
    print("=" * 70)

    df = pd.read_csv(path, dtype=str).fillna("")
    errors = []

    print("rows:", len(df))
    print("unique target_ids:", df["target_id"].nunique() if "target_id" in df else "N/A")
    print("columns:", df.columns.tolist())

    if df.columns.tolist() != EXPECTED_COLUMNS:
        errors.append(
            f"Column mismatch:\n expected={EXPECTED_COLUMNS}\n actual={df.columns.tolist()}"
        )

    if len(df) != len(inp):
        errors.append(f"Expected {len(inp)} rows, found {len(df)}")

    if "target_id" in df:
        dupes = df[df["target_id"].duplicated(keep=False)]["target_id"].tolist()
        if dupes:
            errors.append(f"Duplicate target_ids: {sorted(set(dupes))}")

        missing = set(inp["target_id"]) - set(df["target_id"])
        extra = set(df["target_id"]) - set(inp["target_id"])
        if missing:
            errors.append(f"Missing target_ids: {sorted(missing)}")
        if extra:
            errors.append(f"Unexpected target_ids: {sorted(extra)}")

    for i, row in df.iterrows():
        tid = row.get("target_id", "")
        if tid not in candidate_sets:
            continue

        title = row.get("title", "")
        if title != input_titles[tid]:
            errors.append(
                f"{tid}: title changed: {title!r} != {input_titles[tid]!r}"
            )

        decision = row.get("decision", "")
        confidence = row.get("confidence", "")
        selected = row.get("selected_qid", "").strip()
        alternatives = split_semicolon(row.get("alternative_qids", ""))
        issues = split_semicolon(row.get("issue_codes", ""))

        if decision not in ALLOWED_DECISIONS:
            errors.append(f"{tid}: invalid decision {decision!r}")

        if confidence not in ALLOWED_CONFIDENCE:
            errors.append(f"{tid}: invalid confidence {confidence!r}")

        bad_issues = [x for x in issues if x not in ALLOWED_ISSUES]
        if bad_issues:
            errors.append(f"{tid}: invalid issue_codes {bad_issues}")

        candidates = candidate_sets[tid]

        if selected and selected not in candidates:
            errors.append(
                f"{tid}: selected_qid {selected} is not in supplied candidates"
            )

        for qid in alternatives:
            if qid not in candidates:
                errors.append(
                    f"{tid}: alternative_qid {qid} is not in supplied candidates"
                )

        if decision == "MATCH" and not selected:
            errors.append(f"{tid}: MATCH but selected_qid is blank")

        if decision == "NO_MATCH" and selected:
            errors.append(
                f"{tid}: NO_MATCH but selected_qid={selected}"
            )

    if "decision" in df:
        print("\ndecisions:")
        print(df["decision"].value_counts(dropna=False).to_string())

    if "confidence" in df:
        print("\nconfidence:")
        print(df["confidence"].value_counts(dropna=False).to_string())

    print()
    if errors:
        print(f"VALIDATION FAILED: {len(errors)} issue(s)")
        for e in errors[:50]:
            print(" -", e)
        if len(errors) > 50:
            print(f" ... and {len(errors) - 50} more")
    else:
        print("VALIDATION PASSED")

    print()
