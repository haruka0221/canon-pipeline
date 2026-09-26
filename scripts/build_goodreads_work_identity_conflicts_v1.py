from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

V9 = ROOT / "derived/goodreads_resolution_status_v9.tsv"

META = (
    ROOT
    / "derived/goodreads_no_author_singleton_full_v9.tsv"
)

CW = (
    ROOT
    / "derived/crosswalks/work_to_wikidata_v2.parquet"
)

CORR = (
    ROOT
    / "derived/crosswalks/work_to_wikidata_corrections_v1.tsv"
)

OUT = (
    ROOT
    / "derived/goodreads_work_identity_conflicts_v1.tsv"
)


v9 = pd.read_csv(
    V9,
    sep="\t",
    dtype=str,
).fillna("")

meta = pd.read_csv(
    META,
    sep="\t",
    dtype=str,
).fillna("")

cw = pd.read_parquet(
    CW,
).fillna("")

corr = pd.read_csv(
    CORR,
    sep="\t",
    dtype=str,
    keep_default_na=False,
)


WORK_KEY = "/works/OL69043W"
OL_WORK_ID = "OL69043W"
DISTINCT_WORK_ID = "OL85885W"
WD_QID = "Q301517"


# ------------------------------------------------------------
# 1. Verify source-supported crosswalk correction
# ------------------------------------------------------------

c = corr[
    corr["ol_work_id"].eq(OL_WORK_ID)
].copy()

assert len(c) == 1

c = c.iloc[0]

assert c["original_decision"] == "MATCH"
assert c["original_wikidata_qid"] == WD_QID
assert c["corrected_decision"] == "NO_MATCH"
assert c["corrected_wikidata_qid"] == ""
assert c["correction_type"] == "SAME_TITLE_DIFFERENT_WORK"
assert c["evidence_status"] == "SOURCE_SUPPORTED"


# ------------------------------------------------------------
# 2. Verify corrected crosswalk
# ------------------------------------------------------------

z = cw[
    cw["ol_work_id"].eq(OL_WORK_ID)
].copy()

assert len(z) == 1

z = z.iloc[0]

assert z["decision"] == "NO_MATCH"
assert z["wikidata_qid"] == ""
assert bool(z["correction_applied"])
assert z["original_wikidata_qid"] == WD_QID
assert z["correction_type"] == "SAME_TITLE_DIFFERENT_WORK"


# The actual Bram Stoker OL Work remains mapped to Q301517.
distinct = cw[
    cw["ol_work_id"].eq(DISTINCT_WORK_ID)
].copy()

assert len(distinct) == 1

distinct = distinct.iloc[0]

assert distinct["decision"] == "MATCH"
assert distinct["wikidata_qid"] == WD_QID


# ------------------------------------------------------------
# 3. Verify current Goodreads state
# ------------------------------------------------------------

cur = v9[
    v9["work_key"].eq(WORK_KEY)
].copy()

assert len(cur) == 1

cur = cur.iloc[0]

assert cur["goodreads_resolution_status"] == "NO_AUTHOR_SUPPORT"
assert cur["goodreads_candidate_count"] == "1"


# ------------------------------------------------------------
# 4. Goodreads singleton candidate metadata
# ------------------------------------------------------------

m = meta[
    meta["work_key"].eq(WORK_KEY)
].copy()

assert len(m) == 1

m = m.iloc[0]

assert m["goodreads_work_id"] == "768567"
assert m["title_match_type"] == "WORK_FULL"
assert m["gr_original_title"] == "Under the Sunset"
assert m["gr_original_publication_year"] == "1881"
assert "Bram Stoker" in m["goodreads_contributors"]


# ------------------------------------------------------------
# 5. Work-identity conflict evidence
# ------------------------------------------------------------

out = pd.DataFrame([
    {
        "ol_work_key":
            WORK_KEY,

        "ol_title":
            m["ol_title"],

        "ol_author_name":
            m["ol_author_name"],

        "goodreads_work_id":
            m["goodreads_work_id"],

        "title_match_type":
            m["title_match_type"],

        "gr_original_title":
            m["gr_original_title"],

        "gr_original_publication_year":
            m["gr_original_publication_year"],

        "goodreads_contributors":
            m["goodreads_contributors"],

        "rejected_wikidata_qid":
            WD_QID,

        "distinct_ol_work_id":
            DISTINCT_WORK_ID,

        "crosswalk_correction_type":
            c["correction_type"],

        "evidence_status":
            c["evidence_status"],

        "conflict_type":
            "SAME_TITLE_DIFFERENT_WORK",

        "proposed_resolution_status":
            "NO_MATCH_WIKIDATA_WORK_IDENTITY_CONFLICT",
    }
])

out.to_csv(
    OUT,
    sep="\t",
    index=False,
)


print("rows:", len(out))

print("\n=== WORK IDENTITY CONFLICT ===")
print(
    out.to_string(index=False)
)

assert len(out) == 1

assert (
    out.iloc[0]["proposed_resolution_status"]
    == "NO_MATCH_WIKIDATA_WORK_IDENTITY_CONFLICT"
)

print("\noutput:", OUT)
