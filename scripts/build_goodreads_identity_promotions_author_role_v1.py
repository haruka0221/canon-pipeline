from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

V9 = ROOT / "derived/goodreads_resolution_status_v9.tsv"

META = (
    ROOT
    / "derived/goodreads_no_author_singleton_full_v9.tsv"
)

GP = (
    ROOT
    / "derived/goodreads_wikidata_gr_person_evidence_v2.tsv"
)

CW = (
    ROOT
    / "derived/crosswalks/work_to_wikidata_v2.parquet"
)

ROLE = (
    ROOT
    / "derived/goodreads_author_role_evidence_v1.tsv"
)

OUT = (
    ROOT
    / "derived/goodreads_identity_promotions_author_role_v1.tsv"
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

gp = pd.read_csv(
    GP,
    sep="\t",
    dtype=str,
).fillna("")

cw = pd.read_parquet(
    CW,
).fillna("")

role = pd.read_csv(
    ROLE,
    sep="\t",
    dtype=str,
).fillna("")


# ------------------------------------------------------------
# 1. Source-supported author-role evidence
# ------------------------------------------------------------

assert len(role) == 1
assert role["ol_work_key"].is_unique

r = role.iloc[0]

assert r["ol_work_key"] == "/works/OL14942914W"
assert r["goodreads_work_id"] == "2078313"
assert r["wikidata_work_qid"] == "Q13181913"
assert r["conceptual_author_qid"] == "Q12706"
assert r["conceptual_author_name"] == "Maxim Gorky"
assert r["ol_attributed_name"] == "C. J. Hogarth"
assert r["verified_role"] == "translator"
assert (
    r["evidence_status"]
    == "SOURCE_SUPPORTED_AUTHOR_ROLE_CONFLICT"
)


# ------------------------------------------------------------
# 2. Verify current Goodreads state
# ------------------------------------------------------------

cur = v9[
    v9["work_key"].eq(r["ol_work_key"])
].copy()

assert len(cur) == 1

assert (
    cur.iloc[0]["goodreads_resolution_status"]
    == "NO_AUTHOR_SUPPORT"
)

assert (
    cur.iloc[0]["goodreads_candidate_count"]
    == "1"
)


# ------------------------------------------------------------
# 3. Goodreads singleton candidate metadata
# ------------------------------------------------------------

m = meta[
    meta["work_key"].eq(r["ol_work_key"])
].copy()

assert len(m) == 1

m = m.iloc[0]

assert m["goodreads_work_id"] == r["goodreads_work_id"]
assert m["title_match_type"] in {
    "WORK_FULL",
    "BOOK_FULL",
}


# ------------------------------------------------------------
# 4. Verify Wikidata Work -> P50 evidence
# ------------------------------------------------------------

g = gp[
    gp["ol_work_key"].eq(r["ol_work_key"])
].copy()

assert len(g) == 1

g = g.iloc[0]

assert (
    g["wikidata_work_qid"]
    == r["wikidata_work_qid"]
)

assert (
    g["work_author_evidence_status"]
    == "P50_SUPPORTS_GR_ONLY"
)

gr_p50 = {
    z.strip()
    for z in g["gr_matching_p50_qids"].split("|")
    if z.strip()
}

assert r["conceptual_author_qid"] in gr_p50


# ------------------------------------------------------------
# 5. Verify corrected OL -> Wikidata Work crosswalk
# ------------------------------------------------------------

ol_work_id = r["ol_work_key"].replace(
    "/works/",
    "",
)

c = cw[
    cw["ol_work_id"].eq(ol_work_id)
].copy()

assert len(c) == 1

c = c.iloc[0]

assert c["decision"] == "MATCH"
assert c["wikidata_qid"] == r["wikidata_work_qid"]
assert c["confidence"] == "high"
assert not bool(c["correction_applied"])


# ------------------------------------------------------------
# 6. Promotion layer
# ------------------------------------------------------------

out = pd.DataFrame([
    {
        "ol_work_key":
            r["ol_work_key"],

        "ol_title":
            m["ol_title"],

        "ol_author_name":
            m["ol_author_name"],

        "goodreads_work_id":
            m["goodreads_work_id"],

        "title_match_type":
            m["title_match_type"],

        "resolved_gr_name":
            r["conceptual_author_name"],

        "gr_original_title":
            m["gr_original_title"],

        "gr_original_publication_year":
            m["gr_original_publication_year"],

        "wikidata_work_qid":
            r["wikidata_work_qid"],

        "matched_person_qid":
            r["conceptual_author_qid"],

        "verified_ol_role":
            r["verified_role"],

        "author_role_evidence_status":
            r["evidence_status"],

        "crosswalk_decision":
            c["decision"],

        "crosswalk_confidence":
            c["confidence"],

        "promotion_eligible":
            "1",

        "proposed_resolution_status":
            "AUTO_MATCH_WIKIDATA_P50_AUTHOR_ROLE",
    }
])

out.to_csv(
    OUT,
    sep="\t",
    index=False,
)

print("rows:", len(out))

print("\n=== AUTHOR-ROLE PROMOTION ===")
print(
    out.to_string(index=False)
)

assert len(out) == 1

assert (
    out.iloc[0]["proposed_resolution_status"]
    == "AUTO_MATCH_WIKIDATA_P50_AUTHOR_ROLE"
)

print("\noutput:", OUT)
