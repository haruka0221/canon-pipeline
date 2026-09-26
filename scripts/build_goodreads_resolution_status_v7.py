from pathlib import Path

import pandas as pd

V6 = Path(
    "derived/goodreads_resolution_status_v6.tsv"
)

PROMO = Path(
    "derived/goodreads_identity_promotions_wikidata_p50_v1.tsv"
)

OUT = Path(
    "derived/goodreads_resolution_status_v7.tsv"
)

v6 = pd.read_csv(
    V6,
    sep="\t",
    dtype=str,
).fillna("")

p = pd.read_csv(
    PROMO,
    sep="\t",
    dtype=str,
).fillna("")

# ------------------------------------------------------------
# 1. Integrity of inputs
# ------------------------------------------------------------

assert len(v6) == 34789
assert v6["work_key"].is_unique

assert len(p) == 8
assert p["ol_work_key"].is_unique

assert (
    p["proposed_resolution_status"]
    == "AUTO_MATCH_WIKIDATA_P50"
).sum() == 7

assert (
    p["proposed_resolution_status"]
    == "REVIEW_WIKIDATA_P50_ALIAS"
).sum() == 1

out = v6.copy()
out_i = out.set_index("work_key")

assert set(
    p["ol_work_key"]
).issubset(set(out_i.index))

# All 8 must still be unresolved in v6.
assert (
    out_i.loc[
        p["ol_work_key"],
        "goodreads_resolution_status",
    ]
    == "NO_AUTHOR_SUPPORT"
).all()

assert (
    out_i.loc[
        p["ol_work_key"],
        "goodreads_candidate_count",
    ]
    == "1"
).all()


# ------------------------------------------------------------
# 2. AUTO: Wikidata Work -> P50 identity evidence
# ------------------------------------------------------------

auto = p[
    p["proposed_resolution_status"]
    == "AUTO_MATCH_WIKIDATA_P50"
].copy()

review = p[
    p["proposed_resolution_status"]
    == "REVIEW_WIKIDATA_P50_ALIAS"
].copy()

assert len(auto) == 7
assert len(review) == 1

for r in auto.itertuples(index=False):

    wk = r.ol_work_key

    out_i.at[
        wk,
        "goodreads_resolution_status",
    ] = "AUTO_MATCH_WIKIDATA_P50"

    out_i.at[
        wk,
        "selected_goodreads_work_id",
    ] = r.goodreads_work_id

    out_i.at[
        wk,
        "selected_title_match_type",
    ] = r.title_match_type

    out_i.at[
        wk,
        "selected_author_match_quality",
    ] = "IDENTITY_WIKIDATA_WORK_P50"

    out_i.at[
        wk,
        "selected_goodreads_author",
    ] = r.resolved_gr_name

    out_i.at[
        wk,
        "selected_gr_original_title",
    ] = r.gr_original_title

    out_i.at[
        wk,
        "selected_gr_original_publication_year",
    ] = r.gr_original_publication_year

    out_i.at[
        wk,
        "review_needed",
    ] = "0"


# ------------------------------------------------------------
# 3. REVIEW: collision-prone P50 alias
#
# Do not select the Goodreads work yet.
# ------------------------------------------------------------

for r in review.itertuples(index=False):

    wk = r.ol_work_key

    out_i.at[
        wk,
        "goodreads_resolution_status",
    ] = "REVIEW_WIKIDATA_P50_ALIAS"

    out_i.at[
        wk,
        "review_needed",
    ] = "1"


# ------------------------------------------------------------
# 4. Write v7
# ------------------------------------------------------------

out = out_i.reset_index()

out.to_csv(
    OUT,
    sep="\t",
    index=False,
)

print("=== V7 RESOLUTION STATUS ===")
print(
    out["goodreads_resolution_status"]
    .value_counts()
    .to_string()
)

print("\ntotal:", len(out))

print("\n=== V6 -> V7 CHANGES ===")

cmp = v6.merge(
    out,
    on="work_key",
    suffixes=("_v6", "_v7"),
    validate="one_to_one",
)

changed = cmp[
    cmp["goodreads_resolution_status_v6"]
    != cmp["goodreads_resolution_status_v7"]
].copy()

print("changed rows:", len(changed))

print(
    changed[
        [
            "work_key",
            "title_v7",
            "author_name_v7",
            "goodreads_resolution_status_v6",
            "goodreads_resolution_status_v7",
            "selected_goodreads_work_id_v7",
            "selected_author_match_quality_v7",
            "review_needed_v7",
        ]
    ].to_string(index=False)
)


# ------------------------------------------------------------
# 5. Integrity checks
# ------------------------------------------------------------

assert len(out) == 34789
assert out["work_key"].is_unique

assert (
    out["goodreads_resolution_status"]
    == "NO_AUTHOR_SUPPORT"
).sum() == 3530

assert (
    out["goodreads_resolution_status"]
    == "AUTO_MATCH_WIKIDATA_P50"
).sum() == 7

assert (
    out["goodreads_resolution_status"]
    == "REVIEW_WIKIDATA_P50_ALIAS"
).sum() == 1

assert (
    out["goodreads_resolution_status"]
    == "AUTO_MATCH_IDENTITY_EVIDENCE"
).sum() == 208

assert len(changed) == 8

auto_changed = changed[
    changed["goodreads_resolution_status_v7"]
    == "AUTO_MATCH_WIKIDATA_P50"
]

assert len(auto_changed) == 7

assert (
    auto_changed[
        "selected_author_match_quality_v7"
    ]
    == "IDENTITY_WIKIDATA_WORK_P50"
).all()

assert (
    auto_changed[
        "selected_goodreads_work_id_v7"
    ].ne("")
).all()

review_changed = changed[
    changed["goodreads_resolution_status_v7"]
    == "REVIEW_WIKIDATA_P50_ALIAS"
]

assert len(review_changed) == 1

assert (
    review_changed[
        "selected_goodreads_work_id_v7"
    ]
    == ""
).all()

assert (
    review_changed[
        "review_needed_v7"
    ]
    == "1"
).all()

print("\noutput:", OUT)
