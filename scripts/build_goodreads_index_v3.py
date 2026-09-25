"""
build_goodreads_index_v3.py
===========================
UCSD Goodreads の work-level metadata だけから
照合用 work index を構築する。

重要:
  - goodreads_books.json.gz はここでは読まない
  - best_book_id に依存して著者・genreを決めない
  - 著者 / editor / translator 等の contributor evidence は
    matching 時に candidate works について別途回収する
  - ratings は保存するが identity resolution には使用しない

出力:
  derived/goodreads_works_index_v3.tsv
"""

import csv
import gzip
import json
import re
import unicodedata

UCSD_DIR = "/mnt/d/goodreads"
OUT_PATH = "derived/goodreads_works_index_v3.tsv"


def normalize_title(t, drop_subtitle=False):
    """
    case / Unicode / punctuation を正規化する。
    article (the/a/an) は削除しない。
    """
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


def parse_rating_dist(dist_str):
    result = {
        "ratings_5": "",
        "ratings_4": "",
        "ratings_3": "",
        "ratings_2": "",
        "ratings_1": "",
    }

    if not dist_str:
        return result

    for part in dist_str.split("|"):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        if k in {"1", "2", "3", "4", "5"}:
            result[f"ratings_{k}"] = v

    return result


fieldnames = [
    "goodreads_work_id",
    "title",
    "title_full_norm",
    "title_base_norm",
    "original_publication_year",
    "books_count",
    "best_book_id",
    "ratings_count",
    "text_reviews_count",
    "ratings_5",
    "ratings_4",
    "ratings_3",
    "ratings_2",
    "ratings_1",
    "rating_dist",
]


print("Goodreads work index v3 構築中...")

n = 0
n_title = 0

with gzip.open(
    f"{UCSD_DIR}/goodreads_book_works.json.gz", "rt"
) as fin, open(
    OUT_PATH, "w", newline="", encoding="utf-8"
) as fout:

    writer = csv.DictWriter(
        fout,
        fieldnames=fieldnames,
        delimiter="\t",
    )
    writer.writeheader()

    for line in fin:
        d = json.loads(line)

        wid = str(d.get("work_id", "") or "")
        if not wid:
            continue

        title = d.get("original_title", "") or ""
        rd = d.get("rating_dist", "") or ""
        stars = parse_rating_dist(rd)

        row = {
            "goodreads_work_id": wid,
            "title": title,
            "title_full_norm": normalize_title(
                title,
                drop_subtitle=False,
            ),
            "title_base_norm": normalize_title(
                title,
                drop_subtitle=True,
            ),
            "original_publication_year":
                d.get("original_publication_year", ""),
            "books_count":
                d.get("books_count", ""),
            "best_book_id":
                d.get("best_book_id", ""),
            "ratings_count":
                d.get("ratings_count", "0"),
            "text_reviews_count":
                d.get("text_reviews_count", "0"),
            "rating_dist": rd,
            **stars,
        }

        writer.writerow(row)

        n += 1
        if title:
            n_title += 1

        if n % 250000 == 0:
            print(f"  {n:,} works...")

print()
print("=== 完了 ===")
print(f"works: {n:,}")
print(f"works with original_title: {n_title:,}")
print(f"output: {OUT_PATH}")
