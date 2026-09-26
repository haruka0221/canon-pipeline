from pathlib import Path
import pandas as pd

EV = Path("derived/goodreads_ol_author_identity_outlang28_v1.tsv")
TR = Path("derived/goodreads_outlang_singleton_full28_v1.tsv")
RES = Path("derived/goodreads_resolution_status_v4.tsv")
OUT = Path("derived/goodreads_identity_promotions_outlang28_v1.tsv")

ev = pd.read_csv(EV, sep="\t", dtype=str).fillna("")
tr = pd.read_csv(TR, sep="\t", dtype=str).fillna("")
res = pd.read_csv(RES, sep="\t", dtype=str).fillna("")

positive_statuses = {
    "DIRECT_NAME_MATCH",
    "OL_ALIAS_MATCH",
    "GIVEN_NAME_COMPATIBLE",
}

x = ev[
    ev["identity_status"].isin(positive_statuses)
].copy()

x = x.merge(
    tr[
        [
            "work_key",
            "goodreads_work_id",
            "title_match_type",
        ]
    ],
    left_on="ol_work_key",
    right_on="work_key",
    how="left",
    validate="one_to_one",
    suffixes=("_evidence", "_transfer"),
)

assert (
    x["goodreads_work_id_evidence"]
    == x["goodreads_work_id_transfer"]
).all()

x["goodreads_work_id"] = x["goodreads_work_id_evidence"]

x = x.merge(
    res[
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
    suffixes=("", "_resolution"),
)

status_map = {
    "DIRECT_NAME_MATCH": "SAME_PERSON_OL_DIRECT",
    "OL_ALIAS_MATCH": "SAME_PERSON_OL_ALIAS",
    "GIVEN_NAME_COMPATIBLE": "SAME_PERSON_OL_GIVEN_COMPATIBLE",
}

x["promotion_eligible"] = (
    x["goodreads_resolution_status"].eq("NO_AUTHOR_SUPPORT")
    & x["goodreads_candidate_count"].eq("1")
    & x["title_match_type"].isin(["WORK_FULL", "BOOK_FULL"])
)

assert len(x) == 12
assert x["promotion_eligible"].all()

out = pd.DataFrame({
    "ol_work_key": x["ol_work_key"],
    "ol_title": x["ol_title"],
    "ol_author_name": x["ol_author_name"],
    "goodreads_work_id": x["goodreads_work_id"],
    "title_match_type": x["title_match_type"],
    "combined_identity_status": x["identity_status"].map(status_map),
    "resolved_gr_name": x["matched_gr_name"],
    "resolved_ol_name": x["matched_ol_name_raw"],
    "resolved_person_qid": "",
    "cross_source_corroborated": "0",
    "newly_resolved_by_wikidata": "0",
    "goodreads_candidate_count": x["goodreads_candidate_count"],
    "goodreads_id_consistent": "1",
    "generic_author_identity": "0",
    "promotion_eligible": "1",
    "proposed_resolution_status": "AUTO_MATCH_IDENTITY_EVIDENCE",
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

print("\noutput:", OUT)
