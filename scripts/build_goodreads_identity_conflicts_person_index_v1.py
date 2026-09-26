from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

EVIDENCE = (
    ROOT
    / "derived/goodreads_wikidata_person_index_evidence_v1.tsv"
)

META = (
    ROOT
    / "derived/goodreads_no_author_singleton_full_v10.tsv"
)

V10 = (
    ROOT
    / "derived/goodreads_resolution_status_v10.tsv"
)

OUT = (
    ROOT
    / "derived/goodreads_identity_conflicts_person_index_v1.tsv"
)


ev = pd.read_csv(
    EVIDENCE,
    sep="\t",
    dtype=str,
).fillna("")

meta = pd.read_csv(
    META,
    sep="\t",
    dtype=str,
).fillna("")

v10 = pd.read_csv(
    V10,
    sep="\t",
    dtype=str,
).fillna("")


# ------------------------------------------------------------
# 1. Negative UNIQUE_OTHER cases
# ------------------------------------------------------------

x = ev[
    ev["person_resolution_status"].eq("UNIQUE_OTHER")
].copy()

assert len(x) == 3
assert x["ol_work_key"].is_unique

expected = {
    "/works/OL1002110W": "Q559750",
    "/works/OL1161367W": "Q733850",
    "/works/OL5185419W": "Q5539373",
}

assert dict(
    zip(
        x["ol_work_key"],
        x["resolved_gr_person_qids"],
    )
) == expected

assert (
    x["crosswalk_decision"]
    == "MATCH"
).all()

assert (
    x["crosswalk_confidence"]
    == "high"
).all()

assert (
    x["shared_p50_qids"]
    == ""
).all()


# ------------------------------------------------------------
# 2. Verify current v10 state
# ------------------------------------------------------------

v10_check = v10[
    [
        "work_key",
        "goodreads_resolution_status",
        "goodreads_candidate_count",
    ]
].rename(
    columns={
        "goodreads_resolution_status":
            "v10_resolution_status",
        "goodreads_candidate_count":
            "v10_candidate_count",
    }
)

x = x.merge(
    v10_check,
    left_on="ol_work_key",
    right_on="work_key",
    how="left",
    validate="one_to_one",
)

assert (
    x["v10_resolution_status"]
    == "NO_AUTHOR_SUPPORT"
).all()

assert (
    x["v10_candidate_count"]
    == "1"
).all()


# ------------------------------------------------------------
# 3. Attach Goodreads candidate metadata
# ------------------------------------------------------------

meta_keep = meta[
    [
        "work_key",
        "goodreads_work_id",
        "title_match_type",
        "gr_original_title",
        "gr_original_publication_year",
        "goodreads_contributors",
        "source_batch",
    ]
].rename(
    columns={
        "goodreads_work_id":
            "meta_goodreads_work_id",
        "title_match_type":
            "meta_title_match_type",
    }
)

x = x.merge(
    meta_keep,
    left_on="ol_work_key",
    right_on="work_key",
    how="left",
    validate="one_to_one",
    suffixes=("", "_meta"),
)

assert (
    x["goodreads_work_id"]
    == x["meta_goodreads_work_id"]
).all()

assert (
    x["title_match_type"]
    == x["meta_title_match_type"]
).all()

assert x["title_match_type"].isin(
    ["WORK_FULL", "BOOK_FULL"]
).all()


# ------------------------------------------------------------
# 4. Negative identity evidence layer
# ------------------------------------------------------------

out = pd.DataFrame({
    "ol_work_key":
        x["ol_work_key"],

    "ol_title":
        x["ol_title"],

    "ol_author_name":
        x["ol_author_name"],

    "goodreads_work_id":
        x["goodreads_work_id"],

    "title_match_type":
        x["title_match_type"],

    "gr_original_title":
        x["gr_original_title"],

    "gr_original_publication_year":
        x["gr_original_publication_year"],

    "goodreads_contributors":
        x["goodreads_contributors"],

    "gr_primary_contributors":
        x["gr_primary_contributors"],

    "wikidata_work_qid":
        x["wikidata_work_qid"],

    "wikidata_p50_people":
        x["wikidata_p50_people"],

    "resolved_gr_person_qids":
        x["resolved_gr_person_qids"],

    "person_index_evidence":
        x["person_index_evidence"],

    "crosswalk_decision":
        x["crosswalk_decision"],

    "crosswalk_confidence":
        x["crosswalk_confidence"],

    "conflict_type":
        "OL_P50_VS_GR_UNIQUE_OTHER_PERSON",

    "identity_evidence_source":
        "WIKIDATA_FULL_DUMP_PERSON_INDEX",

    "proposed_resolution_status":
        "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT",
})

out = out.sort_values(
    "ol_work_key"
)

out.to_csv(
    OUT,
    sep="\t",
    index=False,
)


print("rows:", len(out))

print("\n=== PERSON-INDEX IDENTITY CONFLICTS ===")
print(
    out[
        [
            "ol_work_key",
            "ol_title",
            "ol_author_name",
            "wikidata_p50_people",
            "gr_primary_contributors",
            "resolved_gr_person_qids",
            "proposed_resolution_status",
        ]
    ].to_string(index=False)
)

assert len(out) == 3

assert (
    out["proposed_resolution_status"]
    == "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT"
).all()

print("\noutput:", OUT)
