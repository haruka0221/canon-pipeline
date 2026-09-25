"""
build_goodreads_contributor_evidence_v3.py
==========================================
Goodreads candidate works について、
book-level の contributor / role evidence を保存する。

1行 = 1 Goodreads book × 1 contributor relation

ここでは role の意味を決めない。
raw role を保持し、軽い文字列正規化だけした role_norm も保存する。

出力:
  derived/goodreads_contributor_evidence_v3.tsv
"""

import csv
import gzip
import json
import re

UCSD_DIR = "/mnt/d/goodreads"
CANDIDATE_PATH = "derived/goodreads_candidates_v3.tsv"
OUT_PATH = "derived/goodreads_contributor_evidence_v3.tsv"


def norm_role(role):
    role = (role or "").strip().casefold()
    role = re.sub(r"\s+", " ", role)
    return role


# ------------------------------------------------------------
# Step 1: candidate Goodreads work IDs
# ------------------------------------------------------------

print("Step 1: candidate Goodreads works 読み込み中...")

target_works = set()

with open(CANDIDATE_PATH, encoding="utf-8") as f:
    for row in csv.DictReader(f, delimiter="\t"):
        wid = row.get("goodreads_work_id", "")
        if wid:
            target_works.add(wid)

print(f"  → {len(target_works):,} Goodreads works")


# ------------------------------------------------------------
# Step 2: author_id -> author name
# ------------------------------------------------------------

print("Step 2: Goodreads author metadata 読み込み中...")

author_names = {}

with gzip.open(
    f"{UCSD_DIR}/goodreads_book_authors.json.gz",
    "rt"
) as f:
    for line in f:
        d = json.loads(line)
        aid = str(d.get("author_id", "") or "")
        name = d.get("name", "") or ""

        if aid:
            author_names[aid] = name

print(f"  → {len(author_names):,} authors")


# ------------------------------------------------------------
# Step 3: scan books and write contributor evidence
# ------------------------------------------------------------

print("Step 3: candidate works の books / contributors 走査中...")

fieldnames = [
    "goodreads_work_id",
    "book_id",
    "book_title",
    "language_code",
    "publication_year",
    "isbn13",
    "author_id",
    "author_name",
    "role_raw",
    "role_norm",
]

n_books = 0
n_target_books = 0
n_relations = 0
works_seen = set()

with gzip.open(
    f"{UCSD_DIR}/goodreads_books.json.gz",
    "rt"
) as fin, open(
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

    for line in fin:
        d = json.loads(line)

        n_books += 1

        wid = str(d.get("work_id", "") or "")
        if wid not in target_works:
            if n_books % 500000 == 0:
                print(f"  {n_books:,} books scanned...")
            continue

        n_target_books += 1
        works_seen.add(wid)

        bid = str(d.get("book_id", "") or "")
        title = d.get("title", "") or ""
        language = d.get("language_code", "") or ""
        pub_year = d.get("publication_year", "") or ""
        isbn13 = d.get("isbn13", "") or ""

        for a in d.get("authors", []):
            aid = str(a.get("author_id", "") or "")
            role_raw = (a.get("role") or "").strip()

            writer.writerow({
                "goodreads_work_id": wid,
                "book_id": bid,
                "book_title": title,
                "language_code": language,
                "publication_year": pub_year,
                "isbn13": isbn13,
                "author_id": aid,
                "author_name": author_names.get(aid, ""),
                "role_raw": role_raw,
                "role_norm": norm_role(role_raw),
            })

            n_relations += 1

        if n_books % 500000 == 0:
            print(f"  {n_books:,} books scanned...")


# ------------------------------------------------------------
# Summary
# ------------------------------------------------------------

print()
print("=== 完了 ===")
print(f"all books scanned: {n_books:,}")
print(f"candidate-work books: {n_target_books:,}")
print(f"candidate works found in books dump: {len(works_seen):,}")
print(f"candidate works missing from books dump: {len(target_works - works_seen):,}")
print(f"contributor relations: {n_relations:,}")
print(f"output: {OUT_PATH}")
