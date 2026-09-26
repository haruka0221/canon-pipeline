from pathlib import Path
import pandas as pd

V3 = Path("derived/goodreads_resolution_status_v3.tsv")
PROMO = Path("derived/goodreads_identity_promotions_v1.tsv")
BATCH = Path("derived/goodreads_llm_review_batch1_v3.tsv")
OUT = Path("derived/goodreads_resolution_status_v4.tsv")

v3 = pd.read_csv(V3, sep="\t", dtype=str).fillna("")
p = pd.read_csv(PROMO, sep="\t", dtype=str).fillna("")
b = pd.read_csv(BATCH, sep="\t", dtype=str).fillna("")

assert len(v3) == 34789
assert v3["work_key"].is_unique
assert len(p) == 188
assert p["ol_work_key"].is_unique

# Add Goodreads title/year metadata from the original 1,122-case batch.
p = p.merge(
    b[
        [
            "ol_work_key",
            "goodreads_work_id",
            "gr_original_title",
            "gr_original_publication_year",
        ]
    ],
    on="ol_work_key",
    how="left",
    suffixes=("", "_batch"),
    validate="one_to_one",
)

assert (
    p["goodreads_work_id"]
    == p["goodreads_work_id_batch"]
).all()

out = v3.copy()
out_i = out.set_index("work_key")

# All 188 cases must still be unresolved in v3.
assert set(p["ol_work_key"]).issubset(set(out_i.index))
assert (
    out_i.loc[
        p["ol_work_key"],
        "goodreads_resolution_status",
    ]
    == "NO_AUTHOR_SUPPORT"
).all()

auto = p[
    p["proposed_resolution_status"]
    == "AUTO_MATCH_IDENTITY_EVIDENCE"
].copy()

review = p[
    p["proposed_resolution_status"]
    == "REVIEW_GENERIC_AUTHOR_IDENTITY"
].copy()

assert len(auto) == 187
assert len(review) == 1

def quality(status):
    return {
        "SAME_PERSON_OL_DIRECT": "IDENTITY_OL_DIRECT",
        "SAME_PERSON_OL_ALIAS": "IDENTITY_OL_ALIAS",
        "SAME_PERSON_WIKIDATA": "IDENTITY_WIKIDATA",
    }[status]

# Promote 187 source-supported identity matches.
for r in auto.itertuples(index=False):
    wk = r.ol_work_key

    out_i.at[wk, "goodreads_resolution_status"] = (
        "AUTO_MATCH_IDENTITY_EVIDENCE"
    )
    out_i.at[wk, "selected_goodreads_work_id"] = (
        r.goodreads_work_id
    )
    out_i.at[wk, "selected_title_match_type"] = (
        r.title_match_type
    )
    out_i.at[wk, "selected_author_match_quality"] = (
        quality(r.combined_identity_status)
    )
    out_i.at[wk, "selected_goodreads_author"] = (
        r.resolved_gr_name
    )
    out_i.at[wk, "selected_gr_original_title"] = (
        r.gr_original_title
    )
    out_i.at[wk, "selected_gr_original_publication_year"] = (
        r.gr_original_publication_year
    )
    out_i.at[wk, "review_needed"] = "0"

# Keep generic/non-discriminating identity evidence unresolved.
for r in review.itertuples(index=False):
    wk = r.ol_work_key
    out_i.at[wk, "goodreads_resolution_status"] = (
        "REVIEW_GENERIC_AUTHOR_IDENTITY"
    )
    out_i.at[wk, "review_needed"] = "1"

out = out_i.reset_index()
out.to_csv(OUT, sep="\t", index=False)

print("=== V4 RESOLUTION STATUS ===")
print(
    out["goodreads_resolution_status"]
    .value_counts()
    .to_string()
)

print("\ntotal:", len(out))

print("\n=== IDENTITY AUTO MATCHES BY QUALITY ===")
x = out[
    out["goodreads_resolution_status"]
    == "AUTO_MATCH_IDENTITY_EVIDENCE"
]
print(
    x["selected_author_match_quality"]
    .value_counts()
    .to_string()
)

print("\n=== REVIEW GENERIC AUTHOR ===")
print(
    out[
        out["goodreads_resolution_status"]
        == "REVIEW_GENERIC_AUTHOR_IDENTITY"
    ][
        [
            "work_key",
            "title",
            "author_name",
            "goodreads_candidate_count",
            "selected_goodreads_work_id",
            "review_needed",
        ]
    ].to_string(index=False)
)

# Integrity checks.
assert len(out) == 34789
assert out["work_key"].is_unique

assert (
    out["goodreads_resolution_status"]
    == "AUTO_MATCH_IDENTITY_EVIDENCE"
).sum() == 187

assert (
    out["goodreads_resolution_status"]
    == "REVIEW_GENERIC_AUTHOR_IDENTITY"
).sum() == 1

assert (
    out["goodreads_resolution_status"]
    == "NO_AUTHOR_SUPPORT"
).sum() == 3559

assert (
    x["selected_goodreads_work_id"].ne("").all()
)
assert (
    x["selected_title_match_type"]
    .isin(["WORK_FULL", "BOOK_FULL"])
    .all()
)
assert (
    x["review_needed"] == "0"
).all()

print("\noutput:", OUT)
