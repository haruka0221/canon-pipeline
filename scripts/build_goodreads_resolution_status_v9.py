from pathlib import Path

import pandas as pd

V8 = Path(
    "derived/goodreads_resolution_status_v8.tsv"
)

CONFLICT = Path(
    "derived/goodreads_identity_conflicts_wikidata_p50_v1.tsv"
)

OUT = Path(
    "derived/goodreads_resolution_status_v9.tsv"
)

v8 = pd.read_csv(
    V8,
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

assert len(v8) == 34789
assert v8["work_key"].is_unique

assert len(c) == 7
assert c["ol_work_key"].is_unique

assert (
    c["proposed_resolution_status"]
    == "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT"
).all()

out = v8.copy()
out_i = out.set_index("work_key")

assert set(c["ol_work_key"]).issubset(set(out_i.index))

# All seven must still be unresolved in v8.
assert (
    out_i.loc[
        c["ol_work_key"],
        "goodreads_resolution_status",
    ]
    == "NO_AUTHOR_SUPPORT"
).all()

assert (
    out_i.loc[
        c["ol_work_key"],
        "goodreads_candidate_count",
    ]
    == "1"
).all()

# No Goodreads work should already be selected.
assert (
    out_i.loc[
        c["ol_work_key"],
        "selected_goodreads_work_id",
    ]
    == ""
).all()


# ------------------------------------------------------------
# 2. Apply source-supported negative identity evidence
# ------------------------------------------------------------

for r in c.itertuples(index=False):

    wk = r.ol_work_key

    out_i.at[
        wk,
        "goodreads_resolution_status",
    ] = "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT"

    # Candidate is explicitly rejected, not selected.
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
# 3. Write v9
# ------------------------------------------------------------

out = out_i.reset_index()

out.to_csv(
    OUT,
    sep="\t",
    index=False,
)

print("=== V9 RESOLUTION STATUS ===")
print(
    out["goodreads_resolution_status"]
    .value_counts()
    .to_string()
)

print("\ntotal:", len(out))

print("\n=== V8 -> V9 CHANGES ===")

cmp = v8.merge(
    out,
    on="work_key",
    suffixes=("_v8", "_v9"),
    validate="one_to_one",
)

changed = cmp[
    cmp["goodreads_resolution_status_v8"]
    != cmp["goodreads_resolution_status_v9"]
].copy()

print("changed rows:", len(changed))

print(
    changed[
        [
            "work_key",
            "title_v9",
            "author_name_v9",
            "goodreads_resolution_status_v8",
            "goodreads_resolution_status_v9",
            "selected_goodreads_work_id_v9",
            "review_needed_v9",
        ]
    ].to_string(index=False)
)


# ------------------------------------------------------------
# 4. Integrity checks
# ------------------------------------------------------------

assert len(out) == 34789
assert out["work_key"].is_unique

assert len(changed) == 7

assert (
    changed["goodreads_resolution_status_v9"]
    == "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT"
).all()

assert (
    changed["selected_goodreads_work_id_v9"]
    == ""
).all()

assert (
    changed["review_needed_v9"]
    == "0"
).all()

assert (
    out["goodreads_resolution_status"]
    == "NO_AUTHOR_SUPPORT"
).sum() == 3522

assert (
    out["goodreads_resolution_status"]
    == "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT"
).sum() == 7

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
