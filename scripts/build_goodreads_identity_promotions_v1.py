from pathlib import Path
import re
import unicodedata
import pandas as pd

COMB = Path("derived/goodreads_author_identity_combined_v1.tsv")
BATCH = Path("derived/goodreads_llm_review_batch1_v3.tsv")
RES = Path("derived/goodreads_resolution_status_v3.tsv")
OUT = Path("derived/goodreads_identity_promotions_v1.tsv")

c = pd.read_csv(COMB, sep="\t", dtype=str).fillna("")
b = pd.read_csv(BATCH, sep="\t", dtype=str).fillna("")
r = pd.read_csv(RES, sep="\t", dtype=str).fillna("")

pos = c[
    c["combined_identity_status"].str.startswith("SAME_PERSON_")
].copy()

x = pos.merge(
    b,
    on="ol_work_key",
    how="left",
    suffixes=("_identity", "_batch"),
    validate="one_to_one",
)

x = x.merge(
    r[
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

def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.casefold()
    s = re.sub(r"[^\w]+", " ", s)
    return " ".join(s.split())

generic = {
    "anonymous",
    "anonyma",
    "anon",
    "unknown",
    "various",
    "various authors",
}

x["generic_author_identity"] = (
    x["resolved_gr_name"].map(norm).isin(generic)
    | x["resolved_ol_name"].map(norm).isin(generic)
)

x["goodreads_id_consistent"] = (
    x["goodreads_work_id_identity"]
    == x["goodreads_work_id_batch"]
)

x["promotion_eligible"] = (
    x["goodreads_resolution_status"].eq("NO_AUTHOR_SUPPORT")
    & x["goodreads_candidate_count"].eq("1")
    & x["goodreads_id_consistent"]
    & x["title_match_type"].isin(["WORK_FULL", "BOOK_FULL"])
    & ~x["generic_author_identity"]
)

x["proposed_resolution_status"] = "REVIEW_IDENTITY_EVIDENCE"
x.loc[
    x["promotion_eligible"],
    "proposed_resolution_status",
] = "AUTO_MATCH_IDENTITY_EVIDENCE"

x.loc[
    x["generic_author_identity"],
    "proposed_resolution_status",
] = "REVIEW_GENERIC_AUTHOR_IDENTITY"

out = pd.DataFrame({
    "ol_work_key": x["ol_work_key"],
    "ol_title": x["ol_title_identity"],
    "ol_author_name": x["ol_author_name_identity"],
    "goodreads_work_id": x["goodreads_work_id_identity"],
    "title_match_type": x["title_match_type"],
    "combined_identity_status": x["combined_identity_status"],
    "resolved_gr_name": x["resolved_gr_name"],
    "resolved_ol_name": x["resolved_ol_name"],
    "resolved_person_qid": x["resolved_person_qid"],
    "cross_source_corroborated": x["cross_source_corroborated"],
    "newly_resolved_by_wikidata": x["newly_resolved_by_wikidata"],
    "goodreads_candidate_count": x["goodreads_candidate_count"],
    "goodreads_id_consistent": x["goodreads_id_consistent"],
    "generic_author_identity": x["generic_author_identity"],
    "promotion_eligible": x["promotion_eligible"],
    "proposed_resolution_status": x["proposed_resolution_status"],
})

out.to_csv(OUT, sep="\t", index=False)

print("=== IDENTITY PROMOTIONS ===")
print(out["proposed_resolution_status"].value_counts().to_string())

print("\n=== BY IDENTITY SOURCE ===")
print(
    pd.crosstab(
        out["combined_identity_status"],
        out["proposed_resolution_status"],
    ).to_string()
)

print("\n=== TITLE EVIDENCE ===")
print(
    pd.crosstab(
        out["title_match_type"],
        out["proposed_resolution_status"],
    ).to_string()
)

print("\n=== NON-AUTO CASES ===")
print(
    out[
        out["proposed_resolution_status"]
        != "AUTO_MATCH_IDENTITY_EVIDENCE"
    ].to_string(index=False)
)

assert len(out) == 188
assert (out["proposed_resolution_status"] == "AUTO_MATCH_IDENTITY_EVIDENCE").sum() == 187
assert (out["proposed_resolution_status"] == "REVIEW_GENERIC_AUTHOR_IDENTITY").sum() == 1
assert out["goodreads_id_consistent"].all()

print("\noutput:", OUT)
