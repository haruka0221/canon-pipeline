"""
build_goodreads_candidates_v3.py
================================
Open Library 母集団と Goodreads の title evidence から、
identity resolution 用 candidate pair table を作る。

1行 = 1 OL work × 1 Goodreads work candidate

title evidence:
  WORK_FULL : Goodreads work.original_title と OL title が full exact
  WORK_BASE : subtitle 等を落とした base title が exact
  BOOK_FULL : Goodreads book/edition title と OL title が full exact
  BOOK_BASE : subtitle 等を落とした base title が exact

注意:
  - ここでは match を確定しない
  - author / year / contributor role / ratings で候補を選ばない
  - ratings は identity resolution に使わない
"""

import csv
import gzip
import json
import re
import unicodedata
from collections import defaultdict, Counter

UCSD_DIR = "/mnt/d/goodreads"

OL_PATH = "derived/ol_dump_population_with_scope.tsv"
GR_WORK_PATH = "derived/goodreads_works_index_v3.tsv"
OUT_PATH = "derived/goodreads_candidates_v3.tsv"


def norm_title(t, drop_subtitle=False):
    if not t:
        return ""

    t = str(t)

    if drop_subtitle:
        t = t.split(":", 1)[0].split(";", 1)[0]

    t = t.casefold()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    return t


# ------------------------------------------------------------
# Step 1: OL population
# ------------------------------------------------------------

print("Step 1: OL母集団読み込み中...")

ol_rows = []
ol_full_to_idx = defaultdict(list)
ol_base_to_idx = defaultdict(list)

with open(OL_PATH, encoding="utf-8") as f:
    for row in csv.DictReader(f, delimiter="\t"):
        # Keep all frozen source-population rows, including out_lang.
        # scope_flag is retained for downstream cohort decisions.
        full = norm_title(row.get("title", ""), False)
        base = norm_title(row.get("title", ""), True)

        idx = len(ol_rows)

        ol_rows.append({
            "work_key": row.get("work_key", ""),
            "title": row.get("title", ""),
            "author_name": row.get("author_name", ""),
            "first_publish_year": row.get("first_publish_year", ""),
            "canonical": row.get("canonical", "0"),
            "full": full,
            "base": base,
        })

        if full:
            ol_full_to_idx[full].append(idx)
        if base:
            ol_base_to_idx[base].append(idx)

print(f"  → {len(ol_rows):,} OL works")


# ------------------------------------------------------------
# Step 2: Goodreads work-level evidence
# ------------------------------------------------------------

print("Step 2: Goodreads work title evidence 読み込み中...")

gr_meta = {}

# pair key = (OL row index, Goodreads work id)
evidence = defaultdict(lambda: {
    "types": set(),
    "book_ids": set(),
    "book_titles": set(),
})

with open(GR_WORK_PATH, encoding="utf-8") as f:
    for row in csv.DictReader(f, delimiter="\t"):
        wid = row["goodreads_work_id"]

        gr_meta[wid] = {
            "title": row.get("title", ""),
            "year": row.get("original_publication_year", ""),
            "ratings_count": row.get("ratings_count", ""),
            "text_reviews_count": row.get("text_reviews_count", ""),
        }

        full = row.get("title_full_norm", "")
        base = row.get("title_base_norm", "")

        if full and full in ol_full_to_idx:
            for idx in ol_full_to_idx[full]:
                evidence[(idx, wid)]["types"].add("WORK_FULL")

        if base and base in ol_base_to_idx:
            for idx in ol_base_to_idx[base]:
                evidence[(idx, wid)]["types"].add("WORK_BASE")

print(f"  → work-level candidate pairs: {len(evidence):,}")


# ------------------------------------------------------------
# Step 3: Goodreads book/edition title evidence
# ------------------------------------------------------------

print("Step 3: Goodreads book title evidence 走査中...")

n = 0
book_hits = 0

with gzip.open(
    f"{UCSD_DIR}/goodreads_books.json.gz",
    "rt"
) as f:

    for line in f:
        d = json.loads(line)

        bid = str(d.get("book_id", "") or "")
        wid = str(d.get("work_id", "") or "")
        title = d.get("title", "") or ""

        if not wid or not title:
            continue

        full = norm_title(title, False)
        base = norm_title(title, True)

        hit_pairs = set()

        if full and full in ol_full_to_idx:
            for idx in ol_full_to_idx[full]:
                key = (idx, wid)
                evidence[key]["types"].add("BOOK_FULL")
                hit_pairs.add(key)

        if base and base in ol_base_to_idx:
            for idx in ol_base_to_idx[base]:
                key = (idx, wid)
                evidence[key]["types"].add("BOOK_BASE")
                hit_pairs.add(key)

        if hit_pairs:
            book_hits += 1
            for key in hit_pairs:
                if bid:
                    evidence[key]["book_ids"].add(bid)
                evidence[key]["book_titles"].add(title)

        n += 1

        if n % 500000 == 0:
            print(f"  {n:,} books scanned...")

print(f"  → books with OL-title evidence: {book_hits:,}")
print(f"  → total candidate pairs: {len(evidence):,}")


# ------------------------------------------------------------
# Step 4: output
# ------------------------------------------------------------

print("Step 4: candidate table 出力中...")

strength = {
    "WORK_FULL": 1,
    "BOOK_FULL": 2,
    "WORK_BASE": 3,
    "BOOK_BASE": 4,
}

fieldnames = [
    "ol_work_key",
    "ol_title",
    "ol_author_name",
    "ol_first_publish_year",
    "canonical",
    "goodreads_work_id",
    "gr_original_title",
    "gr_original_publication_year",
    "title_match_type",
    "title_match_types",
    "matched_book_ids",
    "matched_book_titles",
    "ratings_count",
    "text_reviews_count",
]

candidate_count_by_ol = Counter()

with open(
    OUT_PATH,
    "w",
    newline="",
    encoding="utf-8"
) as fout:

    writer = csv.DictWriter(
        fout,
        fieldnames=fieldnames,
        delimiter="\t",
    )
    writer.writeheader()

    for (idx, wid), ev in sorted(
        evidence.items(),
        key=lambda x: (x[0][0], int(x[0][1]))
    ):
        ol = ol_rows[idx]
        gr = gr_meta.get(wid, {})

        types = sorted(
            ev["types"],
            key=lambda x: strength[x]
        )

        strongest = types[0]

        writer.writerow({
            "ol_work_key": ol["work_key"],
            "ol_title": ol["title"],
            "ol_author_name": ol["author_name"],
            "ol_first_publish_year": ol["first_publish_year"],
            "canonical": ol["canonical"],
            "goodreads_work_id": wid,
            "gr_original_title": gr.get("title", ""),
            "gr_original_publication_year": gr.get("year", ""),
            "title_match_type": strongest,
            "title_match_types": "|".join(types),
            "matched_book_ids": json.dumps(
                sorted(ev["book_ids"], key=lambda x: int(x)),
                ensure_ascii=False
            ),
            "matched_book_titles": json.dumps(
                sorted(ev["book_titles"]),
                ensure_ascii=False
            ),
            "ratings_count": gr.get("ratings_count", ""),
            "text_reviews_count": gr.get("text_reviews_count", ""),
        })

        candidate_count_by_ol[idx] += 1


# ------------------------------------------------------------
# Summary
# ------------------------------------------------------------

covered = len(candidate_count_by_ol)

print()
print("=== 完了 ===")
print(f"candidate pairs: {len(evidence):,}")
print(f"OL works with >=1 candidate: {covered:,}")
print(f"OL works with no candidate: {len(ol_rows) - covered:,}")
print(f"output: {OUT_PATH}")

print()
print("=== candidates per OL work ===")

dist = Counter(candidate_count_by_ol.values())

for n in sorted(dist):
    if n <= 10:
        print(f"{n} candidate(s): {dist[n]:,}")

print(
    ">10 candidates:",
    sum(c for n, c in dist.items() if n > 10)
)
