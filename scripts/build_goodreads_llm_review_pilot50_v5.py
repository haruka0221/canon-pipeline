#!/usr/bin/env python3

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PILOT = ROOT / "derived/goodreads_llm_review_pilot50_v3.tsv"
EV = ROOT / "derived/goodreads_contributor_evidence_v3.tsv"
OUT = ROOT / "derived/goodreads_llm_review_pilot50_v5.tsv"

# ------------------------------------------------------------
# Load pilot rows
# ------------------------------------------------------------

rows = []

with PILOT.open(encoding="utf-8") as f:
    rows = list(csv.DictReader(f, delimiter="\t"))

pilot_gr_ids = {
    r["goodreads_work_id"]
    for r in rows
}

# ------------------------------------------------------------
# Role-aware contributor evidence
# ------------------------------------------------------------

evidence = defaultdict(lambda: defaultdict(set))

with EV.open(encoding="utf-8") as f:
    for r in csv.DictReader(f, delimiter="\t"):

        gid = r["goodreads_work_id"]

        if gid not in pilot_gr_ids:
            continue

        name = (r.get("author_name") or "").strip()
        role = (r.get("role_raw") or "").casefold().strip()

        if not name:
            continue

        if (
            role == ""
            or role == "author"
            or role.startswith("original author")
        ):
            cls = "PRIMARY"

        elif "pseud" in role or "pen name" in role:
            cls = "PSEUDONYM"

        elif "editor" in role:
            cls = "EDITOR"

        elif "translat" in role:
            cls = "TRANSLATOR"

        elif "adapt" in role or "retell" in role:
            cls = "ADAPTER_RETELLER"

        else:
            cls = "OTHER"

        evidence[gid][cls].add(name)


def joined(names):
    return " | ".join(sorted(names))


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

    "gr_primary_contributors",
    "gr_pseudonym_contributors",
    "gr_editors",
    "gr_translators",
    "gr_adapters_retellers",
    "gr_other_contributors",

    "review_decision",
    "review_confidence",
    "review_reason",
]

out_rows = []

for r in rows:
    gid = r["goodreads_work_id"]
    ev = evidence[gid]

    out_rows.append({
        "ol_work_key": r["ol_work_key"],
        "ol_title": r["ol_title"],
        "ol_author_name": r["ol_author_name"],
        "ol_first_publish_year": r["ol_first_publish_year"],

        "goodreads_work_id": gid,
        "title_match_type": r["title_match_type"],
        "gr_original_title": r["gr_original_title"],
        "gr_original_publication_year":
            r["gr_original_publication_year"],
        "matched_book_titles":
            r["matched_book_titles"],

        "gr_primary_contributors":
            joined(ev["PRIMARY"]),
        "gr_pseudonym_contributors":
            joined(ev["PSEUDONYM"]),
        "gr_editors":
            joined(ev["EDITOR"]),
        "gr_translators":
            joined(ev["TRANSLATOR"]),
        "gr_adapters_retellers":
            joined(ev["ADAPTER_RETELLER"]),
        "gr_other_contributors":
            joined(ev["OTHER"]),

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
    writer.writerows(out_rows)


print("rows:", len(out_rows))
print("output:", OUT)

print("\n=== FIRST 10 ===")

for r in out_rows[:10]:
    print(
        f"{r['ol_title']} | "
        f"OL={r['ol_author_name']} | "
        f"PRIMARY={r['gr_primary_contributors']} | "
        f"PSEUDONYM={r['gr_pseudonym_contributors']} | "
        f"TRANSLATOR={r['gr_translators']} | "
        f"ADAPTER={r['gr_adapters_retellers']}"
    )
