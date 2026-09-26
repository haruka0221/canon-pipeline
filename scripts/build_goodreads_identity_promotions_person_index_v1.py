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
    / "derived/goodreads_identity_promotions_person_index_v1.tsv"
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
# 1. Positive SAME_P50 case from full-dump person index
# ------------------------------------------------------------

x = ev[
    ev["person_resolution_status"].eq("SAME_P50")
].copy()

assert len(x) == 1

r = x.iloc[0]

assert (
    r["ol_work_key"]
    == "/works/OL2343325W"
)

assert (
    r["shared_p50_qids"]
    == "Q1700099"
)

assert (
    r["resolved_gr_person_qids"]
    == "Q1700099"
)

assert (
    r["crosswalk_confidence"]
    == "high"
)


# ------------------------------------------------------------
# 2. Verify current Goodreads state
# ------------------------------------------------------------

cur = v10[
    v10["work_key"].eq(
        r["ol_work_key"]
    )
].copy()

assert len(cur) == 1

cur = cur.iloc[0]

assert (
    cur["goodreads_resolution_status"]
    == "NO_AUTHOR_SUPPORT"
)

assert (
    cur["goodreads_candidate_count"]
    == "1"
)


# ------------------------------------------------------------
# 3. Attach singleton candidate metadata
# ------------------------------------------------------------

m = meta[
    meta["work_key"].eq(
        r["ol_work_key"]
    )
].copy()

assert len(m) == 1

m = m.iloc[0]

assert (
    m["goodreads_work_id"]
    == r["goodreads_work_id"]
)

assert m["title_match_type"] in {
    "WORK_FULL",
    "BOOK_FULL",
}


# ------------------------------------------------------------
# 4. Promotion layer
# ------------------------------------------------------------

out = pd.DataFrame([
    {
        "ol_work_key":
            r["ol_work_key"],

        "ol_title":
            r["ol_title"],

        "ol_author_name":
            r["ol_author_name"],

        "goodreads_work_id":
            r["goodreads_work_id"],

        "title_match_type":
            r["title_match_type"],

        "resolved_gr_name":
            "John Fox Jr.",

        "gr_original_title":
            m["gr_original_title"],

        "gr_original_publication_year":
            m["gr_original_publication_year"],

        "wikidata_work_qid":
            r["wikidata_work_qid"],

        "matched_person_qid":
            r["shared_p50_qids"],

        "wikidata_p50_people":
            r["wikidata_p50_people"],

        "person_index_evidence":
            r["person_index_evidence"],

        "crosswalk_decision":
            r["crosswalk_decision"],

        "crosswalk_confidence":
            r["crosswalk_confidence"],

        "promotion_eligible":
            "1",

        "proposed_resolution_status":
            "AUTO_MATCH_WIKIDATA_P50_PERSON_INDEX",
    }
])

out.to_csv(
    OUT,
    sep="\t",
    index=False,
)


print("rows:", len(out))

print("\n=== PERSON-INDEX PROMOTION ===")
print(
    out.to_string(index=False)
)

assert len(out) == 1

assert (
    out.iloc[0]["proposed_resolution_status"]
    == "AUTO_MATCH_WIKIDATA_P50_PERSON_INDEX"
)

print("\noutput:", OUT)
