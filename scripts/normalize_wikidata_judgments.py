from pathlib import Path
import shutil
import pandas as pd

ROOT = Path("derived/benchmark/judgments")
RAW = ROOT / "raw"
OUT = ROOT / "normalized"
OUT.mkdir(parents=True, exist_ok=True)

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

def split_semicolon(x):
    if pd.isna(x) or not str(x).strip():
        return []
    return [v.strip() for v in str(x).split(";") if v.strip()]

# Claude: already schema-valid, preserve exactly
shutil.copy2(
    RAW / "claude_sonnet5_high_2026-09-11.csv",
    OUT / "claude_sonnet5_high_2026-09-11.csv",
)

# Gemini: fix the systematic NO_MATCH field shift only
src = RAW / "gemini_3.1_pro_2026-09-11.csv"
dst = OUT / "gemini_3.1_pro_2026-09-11.csv"

df = pd.read_csv(src, dtype=str).fillna("")

fixed = 0

for i, row in df.iterrows():
    if row["decision"] != "NO_MATCH":
        continue

    misplaced_issues = split_semicolon(row["alternative_qids"])
    misplaced_reason = row["issue_codes"].strip()

    # Only repair the known Gemini formatting pattern:
    # alternative_qids contains valid issue codes,
    # issue_codes contains prose,
    # reason is blank.
    if (
        misplaced_issues
        and all(x in ALLOWED_ISSUES for x in misplaced_issues)
        and misplaced_reason
        and row["reason"].strip() == ""
    ):
        df.at[i, "alternative_qids"] = ""
        df.at[i, "issue_codes"] = ";".join(misplaced_issues)
        df.at[i, "reason"] = misplaced_reason
        fixed += 1

df.to_csv(dst, index=False)

print(f"Claude normalized: unchanged copy")
print(f"Gemini normalized: repaired {fixed} rows")
print(f"Saved: {dst}")
