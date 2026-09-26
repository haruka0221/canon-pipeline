from pathlib import Path

import pandas as pd

V1 = Path("derived/goodreads_ol_author_identity_evidence_v1.tsv")
V2 = Path("derived/goodreads_ol_author_identity_evidence_v2.tsv")
BATCH = Path("derived/goodreads_llm_review_batch1_v3.tsv")
V5 = Path("derived/goodreads_resolution_status_v5.tsv")
OUT = Path("derived/goodreads_identity_promotions_redirect_v1.tsv")

v1 = pd.read_csv(V1, sep="\t", dtype=str).fillna("")
v2 = pd.read_csv(V2, sep="\t", dtype=str).fillna("")
b = pd.read_csv(BATCH, sep="\t", dtype=str).fillna("")
v5 = pd.read_csv(V5, sep="\t", dtype=str).fillna("")

cmp = v1[
    ["ol_work_key", "identity_status"]
].merge(
    v2[
        [
            "ol_work_key",
            "identity_status",
            "matched_gr_name",
            "matched_ol_name_raw",
            "redirect_applied",
        ]
    ],
    on="ol_work_key",
    suffixes=("_v1", "_v2"),
    validate="one_to_one",
)

x = cmp[
    (cmp["identity_status_v1"] != cmp["identity_status_v2"])
    & cmp["identity_status_v2"].isin(
        ["DIRECT_NAME_MATCH", "OL_ALIAS_MATCH"]
    )
].copy()

x = x.merge(
    b[
        [
            "ol_work_key",
            "ol_title",
            "ol_author_name",
            "goodreads_work_id",
            "title_match_type",
            "gr_original_title",
            "gr_original_publication_year",
        ]
    ],
    on="ol_work_key",
    how="left",
    validate="one_to_one",
)

x = x.merge(
    v5[
        [
            "work_key",
            "goodreads_resolution_status",
            "goodreads_candidate_count",
        ]
    ],
    left_on="ol_work_key",
    right_on="work_key",
    how="left",
    validate="one_to_one",
)

x["promotion_eligible"] = (
    x["goodreads_resolution_status"].eq("NO_AUTHOR_SUPPORT")
    & x["goodreads_candidate_count"].eq("1")
    & x["title_match_type"].isin(["WORK_FULL", "BOOK_FULL"])
    & x["redirect_applied"].eq("1")
)

assert len(x) == 9
assert x["promotion_eligible"].all()

status_map = {
    "DIRECT_NAME_MATCH": "SAME_PERSON_OL_REDIRECT_DIRECT",
    "OL_ALIAS_MATCH": "SAME_PERSON_OL_REDIRECT_ALIAS",
}

out = pd.DataFrame({
    "ol_work_key": x["ol_work_key"],
    "ol_title": x["ol_title"],
    "ol_author_name": x["ol_author_name"],
    "goodreads_work_id": x["goodreads_work_id"],
    "title_match_type": x["title_match_type"],
    "combined_identity_status":
        x["identity_status_v2"].map(status_map),
    "resolved_gr_name": x["matched_gr_name"],
    "resolved_ol_name": x["matched_ol_name_raw"],
    "gr_original_title": x["gr_original_title"],
    "gr_original_publication_year":
        x["gr_original_publication_year"],
    "goodreads_candidate_count":
        x["goodreads_candidate_count"],
    "redirect_applied": x["redirect_applied"],
    "promotion_eligible": "1",
    "proposed_resolution_status":
        "AUTO_MATCH_IDENTITY_EVIDENCE",
})

out.to_csv(OUT, sep="\t", index=False)

print("rows:", len(out))

print("\n=== IDENTITY SOURCE ===")
print(
    out["combined_identity_status"]
    .value_counts()
    .to_string()
)

print("\n=== TITLE TYPE ===")
print(
    out["title_match_type"]
    .value_counts()
    .to_string()
)

print("\n=== PROMOTION STATUS ===")
print(
    out["proposed_resolution_status"]
    .value_counts()
    .to_string()
)

assert len(out) == 9
assert (
    out["proposed_resolution_status"]
    == "AUTO_MATCH_IDENTITY_EVIDENCE"
).all()

print("\noutput:", OUT)
