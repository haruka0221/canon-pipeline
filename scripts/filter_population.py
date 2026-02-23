#!/usr/bin/env python3
"""
Filter Open Library works TSV by subject_keys.

Rule:
- If any EXCLUDE subject is present AND no STRONG_FICTION subject is present -> remove.
- Otherwise keep.

Inputs/Outputs (default):
- Input : derived/ol_works_population_unique_clean.tsv
- Kept  : derived/ol_works_filtered.tsv
- Removed: derived/ol_works_filtered_removed.tsv

This script is intended to replace earlier one-off python -c filtering for reproducibility.
"""
from __future__ import annotations
import argparse
import csv
from pathlib import Path
from typing import List, Set, Tuple

EXCLUDE: Set[str] = {
    "plays",
    "dramatic_works",
    "scripts",
    "poetry",
    "poems",
    "ballads",
    "stories_in_rhyme",
    "nonsense_verses",
    "verse",
    "picture_books",
    "literary_criticism",
    "nonfiction",
    "biography__autobiography",
}

STRONG_FICTION: Set[str] = {
    "novel",
    "novels",
    "short_stories",
    "literary_fiction",
    "fiction_general",
    "english_fiction",
    "american_fiction",
}

# These should NOT be used for exclusion (documented to avoid false removals)
DO_NOT_EXCLUDE: Set[str] = {"drama", "history_and_criticism", "fiction"}


def parse_subject_keys(raw: str) -> Set[str]:
    """
    subject_keys column is assumed to be a delimiter-separated string.
    We handle common delimiters: '|', ';', ',', whitespace.
    """
    if raw is None:
        return set()
    s = raw.strip()
    if not s:
        return set()

    # Try the most likely delimiters first
    if "|" in s:
        parts = [p.strip() for p in s.split("|")]
    elif ";" in s:
        parts = [p.strip() for p in s.split(";")]
    elif "," in s:
        parts = [p.strip() for p in s.split(",")]
    else:
        # fallback: split on whitespace
        parts = s.split()

    # normalize: lower, keep as-is keys
    return {p.strip().lower() for p in parts if p.strip()}


def should_remove(subjects: Set[str]) -> Tuple[bool, List[str]]:
    """
    Returns (remove?, reasons).
    reasons are exclude keys that triggered removal.
    """
    # Safety: never remove based solely on DO_NOT_EXCLUDE
    # (not used directly, but kept as explicit guard)
    _ = DO_NOT_EXCLUDE

    has_strong = any(k in subjects for k in STRONG_FICTION)
    hits = [k for k in EXCLUDE if k in subjects]

    if hits and (not has_strong):
        return True, sorted(hits)
    return False, []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="derived/ol_works_population_unique_clean.tsv")
    ap.add_argument("--kept", default="derived/ol_works_filtered.tsv")
    ap.add_argument("--removed", default="derived/ol_works_filtered_removed.tsv")
    ap.add_argument("--subject-col", default="subject_keys")
    args = ap.parse_args()

    in_path = Path(args.input)
    kept_path = Path(args.kept)
    rem_path = Path(args.removed)

    if not in_path.exists():
        raise FileNotFoundError(f"Input not found: {in_path}")

    kept_path.parent.mkdir(parents=True, exist_ok=True)
    rem_path.parent.mkdir(parents=True, exist_ok=True)

    kept_rows = 0
    removed_rows = 0

    with in_path.open("r", encoding="utf-8", newline="") as f_in, \
         kept_path.open("w", encoding="utf-8", newline="") as f_kept, \
         rem_path.open("w", encoding="utf-8", newline="") as f_rem:

        reader = csv.DictReader(f_in, delimiter="\t")
        if args.subject_col not in reader.fieldnames:
            raise KeyError(f"Column '{args.subject_col}' not found. Available: {reader.fieldnames}")

        kept_fieldnames = list(reader.fieldnames)
        rem_fieldnames = list(reader.fieldnames) + ["remove_reasons"]

        w_kept = csv.DictWriter(f_kept, fieldnames=kept_fieldnames, delimiter="\t")
        w_rem = csv.DictWriter(f_rem, fieldnames=rem_fieldnames, delimiter="\t")

        w_kept.writeheader()
        w_rem.writeheader()

        for row in reader:
            subjects = parse_subject_keys(row.get(args.subject_col, ""))
            remove, reasons = should_remove(subjects)
            if remove:
                row2 = dict(row)
                row2["remove_reasons"] = "|".join(reasons)
                w_rem.writerow(row2)
                removed_rows += 1
            else:
                w_kept.writerow(row)
                kept_rows += 1

    total = kept_rows + removed_rows
    print(f"input: {in_path}  rows={total}")
    print(f"kept: {kept_path}  rows={kept_rows}")
    print(f"removed: {rem_path}  rows={removed_rows}")
    if total:
        print(f"removed_ratio: {removed_rows/total:.4f}")


if __name__ == "__main__":
    main()
