from pathlib import Path

import pandas as pd


V10 = Path(
    "derived/goodreads_resolution_status_v10.tsv"
)

PROMO = Path(
    "derived/goodreads_identity_promotions_person_index_v1.tsv"
)

CONFLICT = Path(
    "derived/goodreads_identity_conflicts_person_index_v1.tsv"
)

OUT = Path(
    "derived/goodreads_resolution_status_v11.tsv"
)


v10 = pd.read_csv(
    V10,
    sep="\t",
    dtype=str,
).fillna("")

p = pd.read_csv(
    PROMO,
    sep="\t",
    dtype=str,
).fillna("")

c = pd.read_csv(
    CONFLICT,
    sep="\t",
    dtype=str,
).fillna("")


# ------------------------------------------------------------
# 1. Input integrity
# ------------------------------------------------------------

assert len(v10) == 34789
assert v10["work_key"].is_unique

assert len(p) == 1
assert p["ol_work_key"].is_unique

assert len(c) == 3
assert c["ol_work_key"].is_unique

assert (
    p["proposed_resolution_status"]
    == "AUTO_MATCH_WIKIDATA_P50_PERSON_INDEX"
).all()

assert (
    c["proposed_resolution_status"]
    == "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT"
).all()

assert set(p["ol_work_key"]).isdisjoint(
    set(c["ol_work_key"])
)

out = v10.copy()
out_i = out.set_index("work_key")


# ------------------------------------------------------------
# 2. Apply positive person-index promotion
# ------------------------------------------------------------

r = p.iloc[0]
wk = r["ol_work_key"]

assert wk == "/works/OL2343325W"

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

out_i.at[
    wk,
    "goodreads_resolution_status",
] = "AUTO_MATCH_WIKIDATA_P50_PERSON_INDEX"

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
] = "IDENTITY_WIKIDATA_P50_PERSON_INDEX"

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
# 3. Apply negative person-index identity conflicts
# ------------------------------------------------------------

for r in c.itertuples(index=False):

    wk = r.ol_work_key

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

    out_i.at[
        wk,
        "goodreads_resolution_status",
    ] = "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT"

    out_i.at[
        wk,
        "selected_goodreads_work_id",
    ] = ""

    out_i.at[
        wk,
        "selected_title_match_type",
    ] = ""

    out_i.at[
        wk,
        "selected_author_match_quality",
    ] = ""

    out_i.at[
        wk,
        "selected_goodreads_author",
    ] = ""

    out_i.at[
        wk,
        "selected_gr_original_title",
    ] = ""

    out_i.at[
        wk,
        "selected_gr_original_publication_year",
    ] = ""

    out_i.at[
        wk,
        "review_needed",
    ] = "0"


# ------------------------------------------------------------
# 4. Write v11
# ------------------------------------------------------------

out = out_i.reset_index()

out.to_csv(
    OUT,
    sep="\t",
    index=False,
)


print("=== V11 RESOLUTION STATUS ===")
print(
    out["goodreads_resolution_status"]
    .value_counts()
    .to_string()
)

print("\ntotal:", len(out))


# ------------------------------------------------------------
# 5. V10 -> V11 changes
# ------------------------------------------------------------

cmp = v10.merge(
    out,
    on="work_key",
    suffixes=("_v10", "_v11"),
    validate="one_to_one",
)

changed = cmp[
    cmp["goodreads_resolution_status_v10"]
    != cmp["goodreads_resolution_status_v11"]
].copy()

print("\n=== V10 -> V11 CHANGES ===")
print("changed rows:", len(changed))

print(
    changed[
        [
            "work_key",
            "title_v11",
            "author_name_v11",
            "goodreads_resolution_status_v10",
            "goodreads_resolution_status_v11",
            "selected_goodreads_work_id_v11",
            "selected_author_match_quality_v11",
            "review_needed_v11",
        ]
    ]
    .sort_values("work_key")
    .to_string(index=False)
)


# ------------------------------------------------------------
# 6. Integrity checks
# ------------------------------------------------------------

assert len(out) == 34789
assert out["work_key"].is_unique

assert len(changed) == 4

changed_status = dict(
    zip(
        changed["work_key"],
        changed["goodreads_resolution_status_v11"],
    )
)

assert changed_status == {
    "/works/OL1002110W":
        "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT",

    "/works/OL1161367W":
        "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT",

    "/works/OL2343325W":
        "AUTO_MATCH_WIKIDATA_P50_PERSON_INDEX",

    "/works/OL5185419W":
        "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT",
}

assert (
    out["goodreads_resolution_status"]
    == "NO_AUTHOR_SUPPORT"
).sum() == 3515

assert (
    out["goodreads_resolution_status"]
    == "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT"
).sum() == 11

assert (
    out["goodreads_resolution_status"]
    == "AUTO_MATCH_WIKIDATA_P50_PERSON_INDEX"
).sum() == 1

assert (
    out["goodreads_resolution_status"]
    == "AUTO_MATCH_WIKIDATA_P50_AUTHOR_ROLE"
).sum() == 1

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
    == "NO_MATCH_WIKIDATA_WORK_IDENTITY_CONFLICT"
).sum() == 1


# Positive case must be selected.
pos = out[
    out["work_key"].eq("/works/OL2343325W")
].iloc[0]

assert pos["selected_goodreads_work_id"] == "2517834"

assert (
    pos["selected_author_match_quality"]
    == "IDENTITY_WIKIDATA_P50_PERSON_INDEX"
)

assert pos["selected_goodreads_author"] == "John Fox Jr."
assert pos["review_needed"] == "0"


# Negative cases must remain unselected.
for wk in [
    "/works/OL1002110W",
    "/works/OL1161367W",
    "/works/OL5185419W",
]:
    r = out[
        out["work_key"].eq(wk)
    ].iloc[0]

    assert r["selected_goodreads_work_id"] == ""
    assert r["selected_author_match_quality"] == ""
    assert r["review_needed"] == "0"


print("\noutput:", OUT)
