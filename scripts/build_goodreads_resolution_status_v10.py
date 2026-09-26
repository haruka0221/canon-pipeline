from pathlib import Path

import pandas as pd


V9 = Path(
    "derived/goodreads_resolution_status_v9.tsv"
)

IDENTITY_CONFLICT = Path(
    "derived/goodreads_identity_conflicts_wikidata_p50_v2.tsv"
)

AUTHOR_ROLE = Path(
    "derived/goodreads_identity_promotions_author_role_v1.tsv"
)

WORK_CONFLICT = Path(
    "derived/goodreads_work_identity_conflicts_v1.tsv"
)

OUT = Path(
    "derived/goodreads_resolution_status_v10.tsv"
)


v9 = pd.read_csv(
    V9,
    sep="\t",
    dtype=str,
).fillna("")

ic = pd.read_csv(
    IDENTITY_CONFLICT,
    sep="\t",
    dtype=str,
).fillna("")

ar = pd.read_csv(
    AUTHOR_ROLE,
    sep="\t",
    dtype=str,
).fillna("")

wc = pd.read_csv(
    WORK_CONFLICT,
    sep="\t",
    dtype=str,
).fillna("")


# ------------------------------------------------------------
# 1. Input integrity
# ------------------------------------------------------------

assert len(v9) == 34789
assert v9["work_key"].is_unique

assert len(ic) == 8
assert ic["ol_work_key"].is_unique

assert len(ar) == 1
assert ar["ol_work_key"].is_unique

assert len(wc) == 1
assert wc["ol_work_key"].is_unique

assert (
    ic["proposed_resolution_status"]
    == "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT"
).all()

assert (
    ar["proposed_resolution_status"]
    == "AUTO_MATCH_WIKIDATA_P50_AUTHOR_ROLE"
).all()

assert (
    wc["proposed_resolution_status"]
    == "NO_MATCH_WIKIDATA_WORK_IDENTITY_CONFLICT"
).all()

assert set(ar["ol_work_key"]).isdisjoint(
    set(ic["ol_work_key"])
)

assert set(wc["ol_work_key"]).isdisjoint(
    set(ic["ol_work_key"])
)

assert set(ar["ol_work_key"]).isdisjoint(
    set(wc["ol_work_key"])
)


out = v9.copy()
out_i = out.set_index("work_key")


# ------------------------------------------------------------
# 2. Apply P50 negative identity conflicts
#
# Seven were already applied in v9.
# One new case ("I know a secret") is promoted to NO_MATCH.
# ------------------------------------------------------------

new_identity_conflicts = 0

for r in ic.itertuples(index=False):

    wk = r.ol_work_key

    assert wk in out_i.index

    current = out_i.at[
        wk,
        "goodreads_resolution_status",
    ]

    if current == "NO_AUTHOR_SUPPORT":

        new_identity_conflicts += 1

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

    else:
        assert (
            current
            == "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT"
        )

assert new_identity_conflicts == 1


# ------------------------------------------------------------
# 3. Apply source-supported author-role promotion
# ------------------------------------------------------------

r = ar.iloc[0]
wk = r["ol_work_key"]

assert wk == "/works/OL14942914W"

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
] = "AUTO_MATCH_WIKIDATA_P50_AUTHOR_ROLE"

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
] = "IDENTITY_WIKIDATA_P50_AUTHOR_ROLE"

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
# 4. Apply same-title different-work NO_MATCH
# ------------------------------------------------------------

r = wc.iloc[0]
wk = r["ol_work_key"]

assert wk == "/works/OL69043W"

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
] = "NO_MATCH_WIKIDATA_WORK_IDENTITY_CONFLICT"

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
# 5. Write v10
# ------------------------------------------------------------

out = out_i.reset_index()

out.to_csv(
    OUT,
    sep="\t",
    index=False,
)


print("=== V10 RESOLUTION STATUS ===")
print(
    out["goodreads_resolution_status"]
    .value_counts()
    .to_string()
)

print("\ntotal:", len(out))


# ------------------------------------------------------------
# 6. V9 -> V10 changes
# ------------------------------------------------------------

cmp = v9.merge(
    out,
    on="work_key",
    suffixes=("_v9", "_v10"),
    validate="one_to_one",
)

changed = cmp[
    cmp["goodreads_resolution_status_v9"]
    != cmp["goodreads_resolution_status_v10"]
].copy()

print("\n=== V9 -> V10 CHANGES ===")
print("changed rows:", len(changed))

print(
    changed[
        [
            "work_key",
            "title_v10",
            "author_name_v10",
            "goodreads_resolution_status_v9",
            "goodreads_resolution_status_v10",
            "selected_goodreads_work_id_v10",
            "selected_author_match_quality_v10",
            "review_needed_v10",
        ]
    ]
    .sort_values("work_key")
    .to_string(index=False)
)


# ------------------------------------------------------------
# 7. Integrity checks
# ------------------------------------------------------------

assert len(out) == 34789
assert out["work_key"].is_unique

assert len(changed) == 3

changed_status = dict(
    zip(
        changed["work_key"],
        changed["goodreads_resolution_status_v10"],
    )
)

assert changed_status == {
    "/works/OL14942914W":
        "AUTO_MATCH_WIKIDATA_P50_AUTHOR_ROLE",

    "/works/OL619322W":
        "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT",

    "/works/OL69043W":
        "NO_MATCH_WIKIDATA_WORK_IDENTITY_CONFLICT",
}

assert (
    out["goodreads_resolution_status"]
    == "NO_AUTHOR_SUPPORT"
).sum() == 3519

assert (
    out["goodreads_resolution_status"]
    == "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT"
).sum() == 8

assert (
    out["goodreads_resolution_status"]
    == "AUTO_MATCH_WIKIDATA_P50_AUTHOR_ROLE"
).sum() == 1

assert (
    out["goodreads_resolution_status"]
    == "NO_MATCH_WIKIDATA_WORK_IDENTITY_CONFLICT"
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
    == "REVIEW_WIKIDATA_P50_ALIAS"
).sum() == 1


# Through Russia must be a selected positive match.
tr = out[
    out["work_key"].eq("/works/OL14942914W")
].iloc[0]

assert tr["selected_goodreads_work_id"] == "2078313"
assert (
    tr["selected_author_match_quality"]
    == "IDENTITY_WIKIDATA_P50_AUTHOR_ROLE"
)
assert tr["selected_goodreads_author"] == "Maxim Gorky"
assert tr["review_needed"] == "0"


# Both new negative resolutions must remain unselected.
for wk in [
    "/works/OL619322W",
    "/works/OL69043W",
]:
    r = out[
        out["work_key"].eq(wk)
    ].iloc[0]

    assert r["selected_goodreads_work_id"] == ""
    assert r["selected_author_match_quality"] == ""
    assert r["review_needed"] == "0"


print("\noutput:", OUT)
