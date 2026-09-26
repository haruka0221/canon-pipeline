from pathlib import Path
import re

import pandas as pd

TRIAGE = Path(
    "derived/goodreads_no_author_singleton_full_v6_temporal_triage.tsv"
)
GP = Path(
    "derived/goodreads_wikidata_gr_person_evidence_v1.tsv"
)
CW = Path(
    "derived/crosswalks/work_to_wikidata.parquet"
)
V6 = Path(
    "derived/goodreads_resolution_status_v6.tsv"
)

OUT = Path(
    "derived/goodreads_identity_promotions_wikidata_p50_v1.tsv"
)

# ------------------------------------------------------------
# 1. Current unresolved, temporally plausible old-batch cases
# ------------------------------------------------------------

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

v6 = pd.read_csv(
    V6,
    sep="\t",
    dtype=str,
).fillna("")

target = t[
    t["temporal_triage"].eq(
        "TEMPORALLY_PLAUSIBLE_UNRESOLVED"
    )
    & t["source_batch"].eq("old_1122")
].copy()

assert len(target) == 254


# ------------------------------------------------------------
# 2. Wikidata Work -> P50 evidence
# ------------------------------------------------------------

x = target.merge(
    gp,
    left_on="work_key",
    right_on="ol_work_key",
    how="left",
    suffixes=("", "_gp"),
).fillna("")


def qset(v):
    return {
        z.strip()
        for z in str(v).split("|")
        if z.strip()
    }


x["ol_gr_same_p50"] = x.apply(
    lambda r: "|".join(
        sorted(
            qset(r["ol_matching_p50_qids"])
            & qset(r["gr_person_candidate_qids"])
        )
    ),
    axis=1,
)

x = x[
    x["shared_p50_qids"].ne("")
    | x["ol_gr_same_p50"].ne("")
].copy()

assert len(x) == 8


def choose_person_qid(r):
    shared = sorted(qset(r["shared_p50_qids"]))

    if shared:
        assert len(shared) == 1
        return shared[0]

    shared = sorted(qset(r["ol_gr_same_p50"]))

    assert len(shared) == 1
    return shared[0]


x["matched_person_qid"] = x.apply(
    choose_person_qid,
    axis=1,
)


# ------------------------------------------------------------
# 3. Verify OL -> Wikidata Work crosswalk
# ------------------------------------------------------------

x["ol_work_id"] = (
    x["work_key"]
    .str.replace(r"^/works/", "", regex=True)
)

cw_keep = cw[
    [
        "ol_work_id",
        "wikidata_qid",
        "decision",
        "confidence",
    ]
].copy()

assert cw_keep["ol_work_id"].is_unique

x = x.merge(
    cw_keep,
    on="ol_work_id",
    how="left",
    validate="one_to_one",
)

assert (
    x["wikidata_qid"]
    == x["wikidata_work_qid"]
).all()

assert (
    x["decision"] == "MATCH"
).all()

assert (
    x["confidence"] == "high"
).all()


# ------------------------------------------------------------
# 4. Verify current Goodreads resolution state
# ------------------------------------------------------------

x = x.merge(
    v6[
        [
            "work_key",
            "goodreads_resolution_status",
            "goodreads_candidate_count",
        ]
    ],
    on="work_key",
    how="left",
    validate="one_to_one",
    suffixes=("", "_v6"),
)

assert (
    x["goodreads_resolution_status"]
    == "NO_AUTHOR_SUPPORT"
).all()

assert (
    x["goodreads_candidate_count"]
    == "1"
).all()

assert x["title_match_type"].isin(
    ["WORK_FULL", "BOOK_FULL"]
).all()


# ------------------------------------------------------------
# 5. Goodreads primary contributor display name
# ------------------------------------------------------------

def primary_gr_name(s):
    fallback = ""

    for raw in str(s).split("|"):
        raw = raw.strip()

        if not raw:
            continue

        m = re.match(
            r"^(.*?)\s*\[([^\]]*)\]\s*$",
            raw,
        )

        if m:
            name = m.group(1).strip()
            role = m.group(2).strip()
        else:
            name = raw
            role = ""

        if not fallback:
            fallback = name

        if role in {
            "",
            "<EMPTY>",
            "Author",
            "Original Author",
        }:
            return name

    return fallback


x["resolved_gr_name"] = (
    x["goodreads_contributors"]
    .map(primary_gr_name)
)

assert x["resolved_gr_name"].ne("").all()


# ------------------------------------------------------------
# 6. Conservative promotion policy
#
# Seven cases are source-supported auto matches.
#
# Brigands of the moon is held for review:
# Wikidata P50 identifies Ray Cummings, and the same
# person record contains "John Campbell" as an alias,
# but that alias is not explicitly represented in P742
# and is collision-prone.
# ------------------------------------------------------------

REVIEW_WORK = "/works/OL37021076W"

assert REVIEW_WORK in set(x["work_key"])

x["proposed_resolution_status"] = (
    "AUTO_MATCH_WIKIDATA_P50"
)

x.loc[
    x["work_key"].eq(REVIEW_WORK),
    "proposed_resolution_status",
] = "REVIEW_WIKIDATA_P50_ALIAS"

x["combined_identity_status"] = (
    "SAME_PERSON_WIKIDATA_WORK_P50"
)

x.loc[
    x["work_key"].eq(REVIEW_WORK),
    "combined_identity_status",
] = "WIKIDATA_WORK_P50_ALIAS_REVIEW"

x["promotion_eligible"] = x[
    "proposed_resolution_status"
].eq("AUTO_MATCH_WIKIDATA_P50").map(
    {True: "1", False: "0"}
)

x["review_reason"] = ""

x.loc[
    x["work_key"].eq(REVIEW_WORK),
    "review_reason",
] = (
    "P50 person contains OL name John Campbell as alias, "
    "but alias is not explicitly P742 pseudonym; "
    "manual review retained"
)


# ------------------------------------------------------------
# 7. Output promotion layer
# ------------------------------------------------------------

out = pd.DataFrame({
    "ol_work_key":
        x["work_key"],

    "ol_title":
        x["ol_title"],

    "ol_author_name":
        x["ol_author_name"],

    "goodreads_work_id":
        x["goodreads_work_id"],

    "title_match_type":
        x["title_match_type"],

    "combined_identity_status":
        x["combined_identity_status"],

    "matched_person_qid":
        x["matched_person_qid"],

    "wikidata_work_qid":
        x["wikidata_work_qid"],

    "wikidata_p50_people":
        x["wikidata_p50_people"],

    "resolved_gr_name":
        x["resolved_gr_name"],

    "gr_original_title":
        x["gr_original_title"],

    "gr_original_publication_year":
        x["gr_original_publication_year"],

    "goodreads_candidate_count":
        x["goodreads_candidate_count"],

    "crosswalk_decision":
        x["decision"],

    "crosswalk_confidence":
        x["confidence"],

    "promotion_eligible":
        x["promotion_eligible"],

    "proposed_resolution_status":
        x["proposed_resolution_status"],

    "review_reason":
        x["review_reason"],
})

out = out.sort_values(
    ["proposed_resolution_status", "ol_work_key"]
)

out.to_csv(
    OUT,
    sep="\t",
    index=False,
)

print("rows:", len(out))

print("\n=== PROPOSED STATUS ===")
print(
    out["proposed_resolution_status"]
    .value_counts()
    .to_string()
)

print("\n=== AUTO 7 ===")
print(
    out[
        out["proposed_resolution_status"]
        == "AUTO_MATCH_WIKIDATA_P50"
    ][
        [
            "ol_work_key",
            "ol_title",
            "ol_author_name",
            "resolved_gr_name",
            "matched_person_qid",
        ]
    ].to_string(index=False)
)

print("\n=== REVIEW 1 ===")
print(
    out[
        out["proposed_resolution_status"]
        == "REVIEW_WIKIDATA_P50_ALIAS"
    ][
        [
            "ol_work_key",
            "ol_title",
            "ol_author_name",
            "resolved_gr_name",
            "matched_person_qid",
            "review_reason",
        ]
    ].to_string(index=False)
)

assert len(out) == 8
assert (
    out["proposed_resolution_status"]
    == "AUTO_MATCH_WIKIDATA_P50"
).sum() == 7
assert (
    out["proposed_resolution_status"]
    == "REVIEW_WIKIDATA_P50_ALIAS"
).sum() == 1

print("\noutput:", OUT)
