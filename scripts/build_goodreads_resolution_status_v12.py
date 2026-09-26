from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

V11 = ROOT / "derived/goodreads_resolution_status_v11.tsv"
EVIDENCE = ROOT / "derived/goodreads_wikidata_targeted_person_evidence_v1.tsv"
TRIAGE = ROOT / "derived/goodreads_no_author_singleton_full_v11_temporal_triage.tsv"

OUT = ROOT / "derived/goodreads_resolution_status_v12.tsv"


v11 = pd.read_csv(
    V11,
    sep="\t",
    dtype=str,
).fillna("")

ev = pd.read_csv(
    EVIDENCE,
    sep="\t",
    dtype=str,
).fillna("")

triage = pd.read_csv(
    TRIAGE,
    sep="\t",
    dtype=str,
).fillna("")


# ------------------------------------------------------------
# 1. Input integrity
# ------------------------------------------------------------

assert len(v11) == 34789
assert v11["work_key"].is_unique

assert len(ev) == 5
assert ev["ol_work_key"].is_unique

assert (
    ev["relation_to_p50"]
    == "SAME_P50"
).sum() == 2

assert (
    ev["relation_to_p50"]
    == "UNIQUE_OTHER"
).sum() == 3

assert (
    ev["crosswalk_decision"]
    == "MATCH"
).all()

assert (
    ev["crosswalk_confidence"]
    == "high"
).all()


# Attach original Goodreads metadata from v11 residual.
meta = triage[
    [
        "work_key",
        "goodreads_work_id",
        "title_match_type",
        "gr_original_title",
        "gr_original_publication_year",
    ]
].copy()

ev = ev.merge(
    meta,
    left_on="ol_work_key",
    right_on="work_key",
    how="left",
    validate="one_to_one",
)

assert (
    ev["goodreads_work_id_x"]
    == ev["goodreads_work_id_y"]
).all()

ev["goodreads_work_id"] = ev["goodreads_work_id_x"]
ev["title_match_type"] = ev["title_match_type_y"]

out = v11.copy().set_index("work_key")


# ------------------------------------------------------------
# 2. Apply positive SAME_P50 cases
# ------------------------------------------------------------

pos = ev[
    ev["relation_to_p50"].eq("SAME_P50")
].copy()

for r in pos.itertuples(index=False):

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
    ] = "AUTO_MATCH_WIKIDATA_P50_TARGETED_PERSON"

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
    ] = "IDENTITY_WIKIDATA_P50_TARGETED_PERSON"

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
# 3. Apply negative UNIQUE_OTHER cases
# ------------------------------------------------------------

neg = ev[
    ev["relation_to_p50"].eq("UNIQUE_OTHER")
].copy()

for r in neg.itertuples(index=False):

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
    ] = "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT"

    for col in [
        "selected_goodreads_work_id",
        "selected_title_match_type",
        "selected_author_match_quality",
        "selected_goodreads_author",
        "selected_gr_original_title",
        "selected_gr_original_publication_year",
    ]:
        out.at[wk, col] = ""

    out.at[
        wk,
        "review_needed",
    ] = "0"


# ------------------------------------------------------------
# 4. Write v12
# ------------------------------------------------------------

out = out.reset_index()

out.to_csv(
    OUT,
    sep="\t",
    index=False,
)


print("=== V12 RESOLUTION STATUS ===")
print(
    out["goodreads_resolution_status"]
    .value_counts()
    .to_string()
)

print("\ntotal:", len(out))


# ------------------------------------------------------------
# 5. V11 -> V12 changes
# ------------------------------------------------------------

cmp = v11.merge(
    out,
    on="work_key",
    suffixes=("_v11", "_v12"),
    validate="one_to_one",
)

changed = cmp[
    cmp["goodreads_resolution_status_v11"]
    != cmp["goodreads_resolution_status_v12"]
].copy()

print("\n=== V11 -> V12 CHANGES ===")
print("changed rows:", len(changed))

print(
    changed[
        [
            "work_key",
            "title_v12",
            "author_name_v12",
            "goodreads_resolution_status_v11",
            "goodreads_resolution_status_v12",
            "selected_goodreads_work_id_v12",
            "selected_goodreads_author_v12",
            "review_needed_v12",
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

assert len(changed) == 5

assert (
    out["goodreads_resolution_status"]
    == "NO_AUTHOR_SUPPORT"
).sum() == 3510

assert (
    out["goodreads_resolution_status"]
    == "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT"
).sum() == 14

assert (
    out["goodreads_resolution_status"]
    == "AUTO_MATCH_WIKIDATA_P50_TARGETED_PERSON"
).sum() == 2

expected = {
    "/works/OL15866097W":
        "AUTO_MATCH_WIKIDATA_P50_TARGETED_PERSON",
    "/works/OL2571823W":
        "AUTO_MATCH_WIKIDATA_P50_TARGETED_PERSON",
    "/works/OL19601011W":
        "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT",
    "/works/OL2939747W":
        "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT",
    "/works/OL7425541W":
        "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT",
}

assert dict(
    zip(
        changed["work_key"],
        changed["goodreads_resolution_status_v12"],
    )
) == expected


print("\noutput:", OUT)
