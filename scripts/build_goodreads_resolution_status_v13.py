from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

V12 = ROOT / "derived/goodreads_resolution_status_v12.tsv"
EVIDENCE = ROOT / "derived/goodreads_wikidata_dual_name_identity_evidence_v1.tsv"

OUT = ROOT / "derived/goodreads_resolution_status_v13.tsv"


v12 = pd.read_csv(
    V12,
    sep="\t",
    dtype=str,
).fillna("")

ev = pd.read_csv(
    EVIDENCE,
    sep="\t",
    dtype=str,
).fillna("")


# ------------------------------------------------------------
# 1. Input integrity
# ------------------------------------------------------------

assert len(v12) == 34789
assert v12["work_key"].is_unique

assert len(ev) == 4
assert ev["ol_work_key"].is_unique

assert (
    ev["promotion_eligible"]
    == "1"
).all()

assert (
    ev["proposed_resolution_status"]
    == "AUTO_MATCH_WIKIDATA_DUAL_NAME_IDENTITY"
).all()


out = v12.copy().set_index("work_key")


# ------------------------------------------------------------
# 2. Apply four source-supported positive identity matches
# ------------------------------------------------------------

for r in ev.itertuples(index=False):

    wk = r.ol_work_key

    assert (
        out.at[wk, "goodreads_resolution_status"]
        == "NO_AUTHOR_SUPPORT"
    )

    assert (
        out.at[wk, "goodreads_candidate_count"]
        == "1"
    )

    out.at[
        wk,
        "goodreads_resolution_status",
    ] = "AUTO_MATCH_WIKIDATA_DUAL_NAME_IDENTITY"

    out.at[
        wk,
        "selected_goodreads_work_id",
    ] = r.goodreads_work_id

    out.at[
        wk,
        "selected_title_match_type",
    ] = r.title_match_type

    out.at[
        wk,
        "selected_author_match_quality",
    ] = "IDENTITY_WIKIDATA_DUAL_NAME"

    out.at[
        wk,
        "selected_goodreads_author",
    ] = r.gr_person_name

    out.at[
        wk,
        "selected_gr_original_title",
    ] = r.gr_original_title

    out.at[
        wk,
        "selected_gr_original_publication_year",
    ] = r.gr_original_publication_year

    out.at[
        wk,
        "review_needed",
    ] = "0"


# ------------------------------------------------------------
# 3. Write v13
# ------------------------------------------------------------

out = out.reset_index()

out.to_csv(
    OUT,
    sep="\t",
    index=False,
)


print("=== V13 RESOLUTION STATUS ===")
print(
    out["goodreads_resolution_status"]
    .value_counts()
    .to_string()
)

print("\ntotal:", len(out))


# ------------------------------------------------------------
# 4. V12 -> V13 changes
# ------------------------------------------------------------

cmp = v12.merge(
    out,
    on="work_key",
    suffixes=("_v12", "_v13"),
    validate="one_to_one",
)

changed = cmp[
    cmp["goodreads_resolution_status_v12"]
    != cmp["goodreads_resolution_status_v13"]
].copy()

print("\n=== V12 -> V13 CHANGES ===")
print("changed rows:", len(changed))

print(
    changed[
        [
            "work_key",
            "title_v13",
            "author_name_v13",
            "goodreads_resolution_status_v12",
            "goodreads_resolution_status_v13",
            "selected_goodreads_work_id_v13",
            "selected_goodreads_author_v13",
            "selected_author_match_quality_v13",
            "review_needed_v13",
        ]
    ]
    .sort_values("work_key")
    .to_string(index=False)
)


# ------------------------------------------------------------
# 5. Integrity checks
# ------------------------------------------------------------

assert len(out) == 34789
assert out["work_key"].is_unique
assert len(changed) == 4

assert (
    out["goodreads_resolution_status"]
    == "NO_AUTHOR_SUPPORT"
).sum() == 3506

assert (
    out["goodreads_resolution_status"]
    == "AUTO_MATCH_WIKIDATA_DUAL_NAME_IDENTITY"
).sum() == 4

expected = {
    "/works/OL11888695W",
    "/works/OL12107549W",
    "/works/OL5408075W",
    "/works/OL6327626W",
}

assert set(changed["work_key"]) == expected

assert (
    changed["goodreads_resolution_status_v13"]
    == "AUTO_MATCH_WIKIDATA_DUAL_NAME_IDENTITY"
).all()

assert (
    changed["review_needed_v13"]
    == "0"
).all()


print("\noutput:", OUT)
