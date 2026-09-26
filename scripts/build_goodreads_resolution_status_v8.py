from pathlib import Path

import pandas as pd

V7 = Path(
    "derived/goodreads_resolution_status_v7.tsv"
)

PROMO = Path(
    "derived/goodreads_identity_promotions_wikidata_p50_transliteration_v1.tsv"
)

OUT = Path(
    "derived/goodreads_resolution_status_v8.tsv"
)

v7 = pd.read_csv(
    V7,
    sep="\t",
    dtype=str,
).fillna("")

p = pd.read_csv(
    PROMO,
    sep="\t",
    dtype=str,
).fillna("")

# ------------------------------------------------------------
# 1. Input integrity
# ------------------------------------------------------------

assert len(v7) == 34789
assert v7["work_key"].is_unique

assert len(p) == 1
assert p["ol_work_key"].is_unique

assert (
    p.iloc[0]["proposed_resolution_status"]
    == "AUTO_MATCH_WIKIDATA_P50_TRANSLITERATION"
)

out = v7.copy()
out_i = out.set_index("work_key")

wk = p.iloc[0]["ol_work_key"]

assert wk in out_i.index

assert (
    out_i.at[
        wk,
        "goodreads_resolution_status",
    ]
    == "NO_AUTHOR_SUPPORT"
)

assert (
    out_i.at[
        wk,
        "goodreads_candidate_count",
    ]
    == "1"
)


# ------------------------------------------------------------
# 2. Promote reviewed transliteration-supported identity
# ------------------------------------------------------------

r = p.iloc[0]

out_i.at[
    wk,
    "goodreads_resolution_status",
] = "AUTO_MATCH_WIKIDATA_P50_TRANSLITERATION"

out_i.at[
    wk,
    "selected_goodreads_work_id",
] = r["goodreads_work_id"]

out_i.at[
    wk,
    "selected_title_match_type",
] = r["title_match_type"]

out_i.at[
    wk,
    "selected_author_match_quality",
] = "IDENTITY_WIKIDATA_P50_TRANSLITERATION"

out_i.at[
    wk,
    "selected_goodreads_author",
] = r["resolved_gr_name"]

out_i.at[
    wk,
    "selected_gr_original_title",
] = r["gr_original_title"]

out_i.at[
    wk,
    "selected_gr_original_publication_year",
] = r["gr_original_publication_year"]

out_i.at[
    wk,
    "review_needed",
] = "0"


# ------------------------------------------------------------
# 3. Write v8
# ------------------------------------------------------------

out = out_i.reset_index()

out.to_csv(
    OUT,
    sep="\t",
    index=False,
)

print("=== V8 RESOLUTION STATUS ===")
print(
    out["goodreads_resolution_status"]
    .value_counts()
    .to_string()
)

print("\ntotal:", len(out))

print("\n=== V7 -> V8 CHANGES ===")

cmp = v7.merge(
    out,
    on="work_key",
    suffixes=("_v7", "_v8"),
    validate="one_to_one",
)

changed = cmp[
    cmp["goodreads_resolution_status_v7"]
    != cmp["goodreads_resolution_status_v8"]
].copy()

print("changed rows:", len(changed))

print(
    changed[
        [
            "work_key",
            "title_v8",
            "author_name_v8",
            "goodreads_resolution_status_v7",
            "goodreads_resolution_status_v8",
            "selected_goodreads_work_id_v8",
            "selected_author_match_quality_v8",
            "review_needed_v8",
        ]
    ].to_string(index=False)
)


# ------------------------------------------------------------
# 4. Integrity checks
# ------------------------------------------------------------

assert len(out) == 34789
assert out["work_key"].is_unique

assert len(changed) == 1

assert (
    changed.iloc[0]["work_key"]
    == "/works/OL313923W"
)

assert (
    changed.iloc[0]["goodreads_resolution_status_v8"]
    == "AUTO_MATCH_WIKIDATA_P50_TRANSLITERATION"
)

assert (
    changed.iloc[0]["selected_goodreads_work_id_v8"]
    == "1257386"
)

assert (
    changed.iloc[0]["selected_author_match_quality_v8"]
    == "IDENTITY_WIKIDATA_P50_TRANSLITERATION"
)

assert (
    changed.iloc[0]["review_needed_v8"]
    == "0"
)

assert (
    out["goodreads_resolution_status"]
    == "NO_AUTHOR_SUPPORT"
).sum() == 3529

assert (
    out["goodreads_resolution_status"]
    == "AUTO_MATCH_WIKIDATA_P50"
).sum() == 7

assert (
    out["goodreads_resolution_status"]
    == "AUTO_MATCH_WIKIDATA_P50_TRANSLITERATION"
).sum() == 1

assert (
    out["goodreads_resolution_status"]
    == "REVIEW_WIKIDATA_P50_ALIAS"
).sum() == 1

print("\noutput:", OUT)
