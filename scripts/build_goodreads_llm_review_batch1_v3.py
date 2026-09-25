import csv
from collections import defaultdict
from pathlib import Path

STATUS = Path("derived/goodreads_resolution_status_v3.tsv")
CAND = Path("derived/goodreads_candidates_v3.tsv")
EV = Path("derived/goodreads_contributor_evidence_v3.tsv")
OUT = Path("derived/goodreads_llm_review_batch1_v3.tsv")

# ------------------------------------------------------------
# 1. Select batch:
# NO_AUTHOR_SUPPORT + exactly 1 candidate + FULL title
# ------------------------------------------------------------

targets = {}

with STATUS.open(encoding="utf-8") as f:
    for r in csv.DictReader(f, delimiter="\t"):
        if (
            r["goodreads_resolution_status"] == "NO_AUTHOR_SUPPORT"
            and int(r["goodreads_candidate_count"]) == 1
            and r["goodreads_strongest_title_evidence"]
                in {"WORK_FULL", "BOOK_FULL"}
        ):
            targets[r["work_key"]] = r

print("target OL works:", len(targets))

# ------------------------------------------------------------
# 2. Candidate row
# ------------------------------------------------------------

cand = {}

with CAND.open(encoding="utf-8") as f:
    for r in csv.DictReader(f, delimiter="\t"):
        if r["ol_work_key"] in targets:
            cand[r["ol_work_key"]] = r

assert len(cand) == len(targets)

# ------------------------------------------------------------
# 3. Contributor evidence, deduplicated
# ------------------------------------------------------------

contributors = defaultdict(set)

with EV.open(encoding="utf-8") as f:
    for r in csv.DictReader(f, delimiter="\t"):
        gid = r["goodreads_work_id"]
        name = (r.get("author_name") or "").strip()
        role = (r.get("role_raw") or "").strip()

        if name:
            contributors[gid].add(
                (name, role or "<EMPTY>")
            )

# ------------------------------------------------------------
# 4. Review table
# ------------------------------------------------------------

fieldnames = [
    "ol_work_key",
    "ol_title",
    "ol_author_name",
    "ol_first_publish_year",

    "goodreads_work_id",
    "title_match_type",
    "gr_original_title",
    "gr_original_publication_year",

    "matched_book_titles",
    "goodreads_contributors",

    "review_decision",
    "review_confidence",
    "review_reason",
]

rows = []

for wk in sorted(targets):
    r = cand[wk]
    gid = r["goodreads_work_id"]

    people = sorted(contributors.get(gid, set()))
    people_text = " | ".join(
        f"{name} [{role}]"
        for name, role in people
    )

    rows.append({
        "ol_work_key": wk,
        "ol_title": r.get("ol_title", ""),
        "ol_author_name": r.get("ol_author_name", ""),
        "ol_first_publish_year":
            r.get("ol_first_publish_year", ""),

        "goodreads_work_id": gid,
        "title_match_type":
            r.get("title_match_type", ""),
        "gr_original_title":
            r.get("gr_original_title", ""),
        "gr_original_publication_year":
            r.get("gr_original_publication_year", ""),

        "matched_book_titles":
            r.get("matched_book_titles", ""),
        "goodreads_contributors": people_text,

        "review_decision": "",
        "review_confidence": "",
        "review_reason": "",
    })

with OUT.open(
    "w",
    newline="",
    encoding="utf-8",
) as f:
    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames,
        delimiter="\t",
    )
    writer.writeheader()
    writer.writerows(rows)

print("rows:", len(rows))
print("output:", OUT)
