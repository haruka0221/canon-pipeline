from pathlib import Path

import pandas as pd

V7 = Path(
    "derived/goodreads_resolution_status_v7.tsv"
)

TRIAGE = Path(
    "derived/goodreads_no_author_singleton_full_v7_temporal_triage.tsv"
)

GP = Path(
    "derived/goodreads_wikidata_gr_person_evidence_v1.tsv"
)

CW = Path(
    "derived/crosswalks/work_to_wikidata.parquet"
)

OUT = Path(
    "derived/goodreads_identity_promotions_wikidata_p50_transliteration_v1.tsv"
)

WORK_KEY = "/works/OL313923W"
PERSON_QID = "Q404622"

OL_EVIDENCE_NAME = "Saratchandra Chattopadhyaya"
WIKIDATA_NAME = "Sarat Chandra Chattopadhyay"
NAME_SIMILARITY = "0.980392"

v7 = pd.read_csv(
    V7,
    sep="\t",
    dtype=str,
).fillna("")

t = pd.read_csv(
    TRIAGE,
    sep="\t",
    dtype=str,
).fillna("")

gp = pd.read_csv(
    GP,
    sep="\t",
    dtype=str,
).fillna("")

cw = pd.read_parquet(CW).fillna("")


# ------------------------------------------------------------
# 1. Current unresolved Goodreads state
# ------------------------------------------------------------

r = v7[
    v7["work_key"].eq(WORK_KEY)
].copy()

assert len(r) == 1

assert (
    r.iloc[0]["goodreads_resolution_status"]
    == "NO_AUTHOR_SUPPORT"
)

assert (
    r.iloc[0]["goodreads_candidate_count"]
    == "1"
)

assert (
    r.iloc[0]["goodreads_strongest_title_evidence"]
    == "BOOK_FULL"
)


# ------------------------------------------------------------
# 2. Candidate detail
# ------------------------------------------------------------

c = t[
    t["work_key"].eq(WORK_KEY)
].copy()

assert len(c) == 1

assert (
    c.iloc[0]["temporal_triage"]
    == "TEMPORALLY_PLAUSIBLE_UNRESOLVED"
)

assert (
    c.iloc[0]["title_match_type"]
    == "BOOK_FULL"
)

assert (
    c.iloc[0]["goodreads_contributors"]
    == "Sarat Chandra Chattopadhyay [<EMPTY>]"
)


# ------------------------------------------------------------
# 3. Wikidata Work -> P50 evidence
# ------------------------------------------------------------

g = gp[
    gp["ol_work_key"].eq(WORK_KEY)
].copy()

assert len(g) == 1

assert (
    g.iloc[0]["work_author_evidence_status"]
    == "P50_SUPPORTS_GR_ONLY"
)

assert PERSON_QID in {
    z for z in
    g.iloc[0]["wikidata_p50_qids"].split("|")
    if z
}

wikidata_work_qid = g.iloc[0]["wikidata_work_qid"]


# ------------------------------------------------------------
# 4. Verify high-confidence OL -> Wikidata Work crosswalk
# ------------------------------------------------------------

ol_work_id = WORK_KEY.replace("/works/", "")

w = cw[
    cw["ol_work_id"].eq(ol_work_id)
].copy()

assert len(w) == 1

assert (
    w.iloc[0]["wikidata_qid"]
    == wikidata_work_qid
)

assert (
    w.iloc[0]["decision"]
    == "MATCH"
)

assert (
    w.iloc[0]["confidence"]
    == "high"
)


# ------------------------------------------------------------
# 5. Explicit, reviewed transliteration evidence
#
# Do not generalize the 0.98 similarity threshold here.
# This layer records the individually inspected source chain:
#
# OL alternate name:
#   Saratchandra Chattopadhyaya
#
# Wikidata P50 person / Goodreads primary contributor:
#   Sarat Chandra Chattopadhyay
# ------------------------------------------------------------

out = pd.DataFrame([{
    "ol_work_key":
        WORK_KEY,

    "ol_title":
        c.iloc[0]["ol_title"],

    "ol_author_name":
        c.iloc[0]["ol_author_name"],

    "goodreads_work_id":
        c.iloc[0]["goodreads_work_id"],

    "title_match_type":
        c.iloc[0]["title_match_type"],

    "combined_identity_status":
        "SAME_PERSON_WIKIDATA_P50_TRANSLITERATION",

    "matched_person_qid":
        PERSON_QID,

    "wikidata_work_qid":
        wikidata_work_qid,

    "ol_evidence_name":
        OL_EVIDENCE_NAME,

    "wikidata_person_name":
        WIKIDATA_NAME,

    "resolved_gr_name":
        WIKIDATA_NAME,

    "name_similarity":
        NAME_SIMILARITY,

    "gr_original_title":
        c.iloc[0]["gr_original_title"],

    "gr_original_publication_year":
        c.iloc[0]["gr_original_publication_year"],

    "goodreads_candidate_count":
        "1",

    "crosswalk_decision":
        w.iloc[0]["decision"],

    "crosswalk_confidence":
        w.iloc[0]["confidence"],

    "promotion_eligible":
        "1",

    "proposed_resolution_status":
        "AUTO_MATCH_WIKIDATA_P50_TRANSLITERATION",
}])

out.to_csv(
    OUT,
    sep="\t",
    index=False,
)

print(out.to_string(index=False))

assert len(out) == 1
assert (
    out.iloc[0]["proposed_resolution_status"]
    == "AUTO_MATCH_WIKIDATA_P50_TRANSLITERATION"
)

print("\noutput:", OUT)
