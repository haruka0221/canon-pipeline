from pathlib import Path
import pandas as pd

V4 = Path("derived/goodreads_resolution_status_v4.tsv")
PROMO = Path("derived/goodreads_identity_promotions_outlang28_v1.tsv")
TRANSFER = Path("derived/goodreads_outlang_singleton_full28_v1.tsv")
OUT = Path("derived/goodreads_resolution_status_v5.tsv")

v4 = pd.read_csv(V4, sep="\t", dtype=str).fillna("")
p = pd.read_csv(PROMO, sep="\t", dtype=str).fillna("")
tr = pd.read_csv(TRANSFER, sep="\t", dtype=str).fillna("")

assert len(v4) == 34789
assert v4["work_key"].is_unique
assert len(p) == 12
assert p["ol_work_key"].is_unique

# Add Goodreads title/year metadata from the compact 28-case transfer.
p = p.merge(
    tr[
        [
            "work_key",
            "goodreads_work_id",
            "gr_original_title",
            "gr_original_publication_year",
        ]
    ],
    left_on="ol_work_key",
    right_on="work_key",
    how="left",
    suffixes=("", "_transfer"),
    validate="one_to_one",
)

assert (
    p["goodreads_work_id"]
    == p["goodreads_work_id_transfer"]
).all()

assert (
    p["proposed_resolution_status"]
    == "AUTO_MATCH_IDENTITY_EVIDENCE"
).all()

out = v4.copy()
out_i = out.set_index("work_key")

assert set(p["ol_work_key"]).issubset(set(out_i.index))

# All 12 supplemental cases must still be unresolved in v4.
assert (
    out_i.loc[
        p["ol_work_key"],
        "goodreads_resolution_status",
    ]
    == "NO_AUTHOR_SUPPORT"
).all()


def quality(status):
    return {
        "SAME_PERSON_OL_DIRECT": "IDENTITY_OL_DIRECT",
        "SAME_PERSON_OL_ALIAS": "IDENTITY_OL_ALIAS",
        "SAME_PERSON_OL_GIVEN_COMPATIBLE":
            "IDENTITY_OL_GIVEN_COMPATIBLE",
    }[status]


# Promote the 12 additional source-supported identity matches.
for r in p.itertuples(index=False):
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

out = out_i.reset_index()
out.to_csv(OUT, sep="\t", index=False)

print("=== V5 RESOLUTION STATUS ===")
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

print("\n=== V4 -> V5 CHANGES ===")
cmp = v4.merge(
    out,
    on="work_key",
    suffixes=("_v4", "_v5"),
    validate="one_to_one",
)

changed = cmp[
    cmp["goodreads_resolution_status_v4"]
    != cmp["goodreads_resolution_status_v5"]
]

print("changed rows:", len(changed))

print(
    changed[
        [
            "work_key",
            "title_v5",
            "author_name_v5",
            "goodreads_resolution_status_v4",
            "goodreads_resolution_status_v5",
            "selected_author_match_quality_v5",
        ]
    ].to_string(index=False)
)

# Integrity checks.
assert len(out) == 34789
assert out["work_key"].is_unique

assert (
    out["goodreads_resolution_status"]
    == "AUTO_MATCH_IDENTITY_EVIDENCE"
).sum() == 199

assert (
    out["goodreads_resolution_status"]
    == "REVIEW_GENERIC_AUTHOR_IDENTITY"
).sum() == 1

assert (
    out["goodreads_resolution_status"]
    == "NO_AUTHOR_SUPPORT"
).sum() == 3547

assert len(changed) == 12

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
