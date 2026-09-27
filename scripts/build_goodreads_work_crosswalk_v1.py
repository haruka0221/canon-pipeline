from pathlib import Path
import json

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

SRC = ROOT / "derived/goodreads_resolution_status_v13.tsv"

OUT_DIR = ROOT / "derived/crosswalks"
OUT_TSV = OUT_DIR / "goodreads_work_crosswalk_v1.tsv"
OUT_PARQUET = OUT_DIR / "goodreads_work_crosswalk_v1.parquet"
OUT_SUMMARY = OUT_DIR / "goodreads_work_crosswalk_v1_summary.json"


MATCH_STATUSES = {
    "AUTO_MATCH_HIGH",
    "AUTO_MATCH_IDENTITY_EVIDENCE",
    "AUTO_MATCH_WIKIDATA_P50",
    "AUTO_MATCH_WIKIDATA_P50_AUTHOR_ROLE",
    "AUTO_MATCH_WIKIDATA_P50_TRANSLITERATION",
    "AUTO_MATCH_WIKIDATA_P50_PERSON_INDEX",
    "AUTO_MATCH_WIKIDATA_P50_TARGETED_PERSON",
    "AUTO_MATCH_WIKIDATA_DUAL_NAME_IDENTITY",
}

NO_MATCH_STATUSES = {
    "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT",
    "NO_MATCH_WIKIDATA_WORK_IDENTITY_CONFLICT",
}

NO_CANDIDATE_STATUSES = {
    "NO_TITLE_CANDIDATE",
}

AMBIGUOUS_STATUSES = {
    "NO_AUTHOR_SUPPORT",
    "REVIEW_BASE",
    "STRONG_PRIMARY_MULTIPLE",
    "REVIEW_SURNAME_ONLY",
    "NONPRIMARY_ROLE_SUPPORT",
    "OL_AUTHOR_MISSING",
    "SURNAME_ONLY_REMAINDER",
    "REVIEW_GENERIC_AUTHOR_IDENTITY",
    "REVIEW_WIKIDATA_P50_ALIAS",
}


df = pd.read_csv(
    SRC,
    sep="\t",
    dtype=str,
).fillna("")

assert len(df) == 34789
assert df["work_key"].is_unique


# ------------------------------------------------------------
# 1. Make sure every v13 status is explicitly accounted for
# ------------------------------------------------------------

known = (
    MATCH_STATUSES
    | NO_MATCH_STATUSES
    | NO_CANDIDATE_STATUSES
    | AMBIGUOUS_STATUSES
)

observed = set(df["goodreads_resolution_status"])

assert observed == known, {
    "unexpected": sorted(observed - known),
    "missing": sorted(known - observed),
}


# ------------------------------------------------------------
# 2. Map detailed v13 statuses to stable crosswalk semantics
# ------------------------------------------------------------

def decision(status):
    if status in MATCH_STATUSES:
        return "MATCH"
    if status in NO_MATCH_STATUSES:
        return "NO_MATCH"
    if status in NO_CANDIDATE_STATUSES:
        return "NO_CANDIDATE"
    if status in AMBIGUOUS_STATUSES:
        return "AMBIGUOUS"
    raise ValueError(status)


def processing_status(status):
    if status in MATCH_STATUSES:
        return "processed_match"
    if status in NO_MATCH_STATUSES:
        return "processed_no_match"
    if status in NO_CANDIDATE_STATUSES:
        return "processed_no_match"
    if status in AMBIGUOUS_STATUSES:
        return "ambiguous"
    raise ValueError(status)


out = pd.DataFrame()

# Reserved for the future project-defined conceptual work identity.
# Deliberately blank in v1.
out["work_id"] = ""

out["source_record_id"] = (
    "OL:"
    + df["work_key"].str.replace(
        "/works/",
        "",
        regex=False,
    )
)

out["source_name"] = "openlibrary"

out["ol_work_key"] = df["work_key"]

out["ol_work_id"] = (
    df["work_key"]
    .str.replace(
        "/works/",
        "",
        regex=False,
    )
)

out["source_title"] = df["title"]
out["source_author_name"] = df["author_name"]
out["source_author_keys"] = df["author_keys"]
out["source_first_publish_year"] = df["first_publish_year"]
out["scope_flag"] = df["scope_flag"]

out["crosswalk_decision"] = (
    df["goodreads_resolution_status"]
    .map(decision)
)

out["processing_status"] = (
    df["goodreads_resolution_status"]
    .map(processing_status)
)

# Preserve exact historical v13 category losslessly.
out["resolution_status_detail"] = (
    df["goodreads_resolution_status"]
)

out["goodreads_candidate_count"] = (
    df["goodreads_candidate_count"]
)

out["goodreads_strongest_title_evidence"] = (
    df["goodreads_strongest_title_evidence"]
)

# Preserve the v13 selected candidate losslessly.
# For accepted MATCH rows this is the resolved Goodreads work.
# For REVIEW_BASE / REVIEW_SURNAME_ONLY it is only a provisional
# candidate and must not be mistaken for an accepted match.
out["candidate_goodreads_work_id"] = (
    df["selected_goodreads_work_id"]
)

out["candidate_title_match_type"] = (
    df["selected_title_match_type"]
)

out["candidate_author_match_quality"] = (
    df["selected_author_match_quality"]
)

out["candidate_goodreads_author"] = (
    df["selected_goodreads_author"]
)

out["candidate_goodreads_original_title"] = (
    df["selected_gr_original_title"]
)

out["candidate_goodreads_original_publication_year"] = (
    df["selected_gr_original_publication_year"]
)


# Accepted-match fields are populated only for crosswalk_decision=MATCH.
is_match = out["crosswalk_decision"].eq("MATCH")

out["goodreads_work_id"] = (
    df["selected_goodreads_work_id"].where(is_match, "")
)

out["title_match_type"] = (
    df["selected_title_match_type"].where(is_match, "")
)

out["author_match_quality"] = (
    df["selected_author_match_quality"].where(is_match, "")
)

out["goodreads_author"] = (
    df["selected_goodreads_author"].where(is_match, "")
)

out["goodreads_original_title"] = (
    df["selected_gr_original_title"].where(is_match, "")
)

out["goodreads_original_publication_year"] = (
    df["selected_gr_original_publication_year"].where(is_match, "")
)

out["review_needed"] = df["review_needed"]

out["baseline_resolution_version"] = "v13"

out["baseline_source_file"] = (
    "derived/goodreads_resolution_status_v13.tsv"
)


# ------------------------------------------------------------
# 3. Integrity checks
# ------------------------------------------------------------

assert len(out) == 34789
assert out["source_record_id"].is_unique
assert out["ol_work_key"].is_unique

counts = (
    out["crosswalk_decision"]
    .value_counts()
    .to_dict()
)

assert counts == {
    "NO_CANDIDATE": 22465,
    "MATCH": 7624,
    "AMBIGUOUS": 4685,
    "NO_MATCH": 15,
}

status_counts = (
    out["processing_status"]
    .value_counts()
    .to_dict()
)

assert status_counts == {
    "processed_no_match": 22480,
    "processed_match": 7624,
    "ambiguous": 4685,
}

# Accepted matches must have a selected Goodreads Work ID.
assert (
    out.loc[
        out["crosswalk_decision"].eq("MATCH"),
        "goodreads_work_id",
    ]
    .ne("")
    .all()
)

# Non-matches / unresolved records must not masquerade as
# accepted matches.
assert (
    out.loc[
        ~out["crosswalk_decision"].eq("MATCH"),
        "goodreads_work_id",
    ]
    .eq("")
    .all()
)

# v13 also preserves 592 provisional review candidates.
provisional = out[
    ~out["crosswalk_decision"].eq("MATCH")
    & out["candidate_goodreads_work_id"].ne("")
]

assert len(provisional) == 592

assert set(
    provisional["resolution_status_detail"]
) == {
    "REVIEW_BASE",
    "REVIEW_SURNAME_ONLY",
}

# Accepted matches + provisional review candidates.
assert (
    out["candidate_goodreads_work_id"]
    .ne("")
    .sum()
) == 8216


# ------------------------------------------------------------
# 4. Write dual release format
# ------------------------------------------------------------

OUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

out.to_csv(
    OUT_TSV,
    sep="\t",
    index=False,
)

out.to_parquet(
    OUT_PARQUET,
    index=False,
)


# Verify TSV and Parquet represent the same rows/keys.
tsv_check = pd.read_csv(
    OUT_TSV,
    sep="\t",
    dtype=str,
).fillna("")

pq_check = pd.read_parquet(
    OUT_PARQUET,
).fillna("")

assert len(tsv_check) == len(pq_check) == 34789

assert (
    tsv_check["source_record_id"].tolist()
    == pq_check["source_record_id"].astype(str).tolist()
)

assert (
    tsv_check["crosswalk_decision"].tolist()
    == pq_check["crosswalk_decision"].astype(str).tolist()
)


summary = {
    "crosswalk_version": "v1",
    "baseline_resolution_version": "v13",
    "row_count": int(len(out)),
    "crosswalk_decision_counts": {
        k: int(v)
        for k, v in (
            out["crosswalk_decision"]
            .value_counts()
            .to_dict()
            .items()
        )
    },
    "processing_status_counts": {
        k: int(v)
        for k, v in (
            out["processing_status"]
            .value_counts()
            .to_dict()
            .items()
        )
    },
    "match_count": int(
        out["crosswalk_decision"]
        .eq("MATCH")
        .sum()
    ),
    "accepted_goodreads_work_ids": int(
        out["goodreads_work_id"]
        .ne("")
        .sum()
    ),
    "candidate_goodreads_work_ids": int(
        out["candidate_goodreads_work_id"]
        .ne("")
        .sum()
    ),
    "provisional_review_candidates": int(
        (
            ~out["crosswalk_decision"].eq("MATCH")
            & out["candidate_goodreads_work_id"].ne("")
        ).sum()
    ),
    "decision_semantics": {
        "MATCH": (
            "accepted Goodreads work identity in crosswalk v1"
        ),
        "NO_MATCH": (
            "candidate identity was evaluated and rejected; "
            "this is an identity decision, not a statement "
            "about Goodreads coverage"
        ),
        "NO_CANDIDATE": (
            "the current candidate-generation/resolution pipeline "
            "produced no candidate for acceptance; this does not "
            "establish that no corresponding Goodreads work exists"
        ),
        "AMBIGUOUS": (
            "identity remains unresolved and no Goodreads work "
            "identity has been accepted"
        ),
    },
    "processing_status_semantics": {
        "processed_match": (
            "processing completed with an accepted match"
        ),
        "processed_no_match": (
            "processing completed without an accepted match; "
            "consult crosswalk_decision to distinguish NO_MATCH "
            "from NO_CANDIDATE"
        ),
        "ambiguous": (
            "processing completed but identity remains unresolved"
        ),
    },
    "candidate_field_policy": (
        "candidate_* fields preserve candidate evidence and do not "
        "by themselves represent an accepted Goodreads identity"
    ),
    "reserved_work_id_policy": (
        "work_id is intentionally blank in v1; "
        "project-defined conceptual work identity "
        "will be assigned in a later identity layer"
    ),
}

OUT_SUMMARY.write_text(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2,
    )
    + "\n"
)


print("=== GOODREADS WORK CROSSWALK V1 ===")
print("rows:", len(out))

print("\n=== DECISION ===")
print(
    out["crosswalk_decision"]
    .value_counts()
    .to_string()
)

print("\n=== PROCESSING STATUS ===")
print(
    out["processing_status"]
    .value_counts()
    .to_string()
)

print("\naccepted Goodreads work IDs:",
      out["goodreads_work_id"].ne("").sum())

print("candidate Goodreads work IDs:",
      out["candidate_goodreads_work_id"].ne("").sum())

print("provisional review candidates:",
      (
          ~out["crosswalk_decision"].eq("MATCH")
          & out["candidate_goodreads_work_id"].ne("")
      ).sum())

print("\nTSV:", OUT_TSV)
print("Parquet:", OUT_PARQUET)
print("Summary:", OUT_SUMMARY)
