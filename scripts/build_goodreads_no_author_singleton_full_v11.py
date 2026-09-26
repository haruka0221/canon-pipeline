#!/usr/bin/env python3

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

V11 = ROOT / "derived/goodreads_resolution_status_v11.tsv"
OLD = ROOT / "derived/goodreads_llm_review_batch1_v3.tsv"
OUTLANG = ROOT / "derived/goodreads_outlang_singleton_full28_v1.tsv"

OUT = ROOT / "derived/goodreads_no_author_singleton_full_v11.tsv"
OUT_TRIAGE = (
    ROOT
    / "derived/goodreads_no_author_singleton_full_v11_temporal_triage.tsv"
)

v11 = pd.read_csv(V11, sep="\t", dtype=str).fillna("")
old = pd.read_csv(OLD, sep="\t", dtype=str).fillna("")
new = pd.read_csv(OUTLANG, sep="\t", dtype=str).fillna("")

old2 = pd.DataFrame({
    "work_key": old["ol_work_key"],
    "ol_title": old["ol_title"],
    "ol_author_name": old["ol_author_name"],
    "ol_first_publish_year": old["ol_first_publish_year"],
    "goodreads_work_id": old["goodreads_work_id"],
    "title_match_type": old["title_match_type"],
    "gr_original_title": old["gr_original_title"],
    "gr_original_publication_year":
        old["gr_original_publication_year"],
    "matched_book_titles": old["matched_book_titles"],
    "goodreads_contributors": old["goodreads_contributors"],
    "source_batch": "old_1122",
})

new2 = pd.DataFrame({
    "work_key": new["work_key"],
    "ol_title": new["title"],
    "ol_author_name": new["author_name"],
    "ol_first_publish_year": new["first_publish_year"],
    "goodreads_work_id": new["goodreads_work_id"],
    "title_match_type": new["title_match_type"],
    "gr_original_title": new["gr_original_title"],
    "gr_original_publication_year":
        new["gr_original_publication_year"],
    "matched_book_titles": new["matched_book_titles"],
    "goodreads_contributors": new["goodreads_contributors"],
    "source_batch": "outlang_28",
})

detail = pd.concat(
    [old2, new2],
    ignore_index=True,
)

assert detail["work_key"].is_unique

target = v11[
    v11["goodreads_resolution_status"].eq("NO_AUTHOR_SUPPORT")
    & v11["goodreads_candidate_count"].eq("1")
].copy()

x = target.merge(
    detail,
    on="work_key",
    how="inner",
    validate="one_to_one",
)

x = x[
    x["title_match_type"].isin(
        ["WORK_FULL", "BOOK_FULL"]
    )
].copy()

x.to_csv(OUT, sep="\t", index=False)


def year_num(s):
    try:
        y = int(float(s))
        if 1000 <= y <= 2100:
            return y
    except Exception:
        pass
    return None


x["ol_year_num"] = x["ol_first_publish_year"].map(year_num)
x["gr_year_num"] = x["gr_original_publication_year"].map(year_num)

x["signed_year_diff"] = x.apply(
    lambda r: (
        r["gr_year_num"] - r["ol_year_num"]
        if r["ol_year_num"] is not None
        and r["gr_year_num"] is not None
        else None
    ),
    axis=1,
)


def triage(d):
    if pd.isna(d):
        return "YEAR_MISSING"

    d = int(d)

    if d >= 51:
        return "TEMPORAL_CONFLICT_GR_MUCH_NEWER"

    if d <= -51:
        return "POSSIBLE_OLDER_WORK_MANIFESTATION"

    return "TEMPORALLY_PLAUSIBLE_UNRESOLVED"


x["temporal_triage"] = x["signed_year_diff"].map(triage)

x.to_csv(
    OUT_TRIAGE,
    sep="\t",
    index=False,
)

print("rows:", len(x))

print("\n=== SOURCE BATCH ===")
print(
    x["source_batch"]
    .value_counts()
    .to_string()
)

print("\n=== TEMPORAL TRIAGE ===")
print(
    x["temporal_triage"]
    .value_counts()
    .to_string()
)

print("\n=== TITLE TYPE x TRIAGE ===")
print(
    pd.crosstab(
        x["title_match_type"],
        x["temporal_triage"],
    ).to_string()
)

assert x["work_key"].is_unique

assert len(x) == 918
assert (x["source_batch"] == "old_1122").sum() == 902
assert (x["source_batch"] == "outlang_28").sum() == 16

assert (
    x["temporal_triage"]
    == "TEMPORAL_CONFLICT_GR_MUCH_NEWER"
).sum() == 584

assert (
    x["temporal_triage"]
    == "TEMPORALLY_PLAUSIBLE_UNRESOLVED"
).sum() == 236

assert (
    x["temporal_triage"]
    == "YEAR_MISSING"
).sum() == 73

assert (
    x["temporal_triage"]
    == "POSSIBLE_OLDER_WORK_MANIFESTATION"
).sum() == 25

print("\noutput:", OUT)
print("triage:", OUT_TRIAGE)
