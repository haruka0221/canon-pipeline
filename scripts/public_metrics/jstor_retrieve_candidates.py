#!/usr/bin/env python3

"""
Retrieve candidate JSTOR research articles for literary works.

A candidate is retained when:

1. content_type == "article"
2. content_subtype == "research-article"
3. "Language & Literature" is among discipline_names
4. the normalized literary-work title appears as a whole-word phrase
   in the normalized article title

The output is a candidate-level TSV intended for subsequent relevance
classification.

These candidates are title-based matches, not final counts of scholarship.
"""

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path


NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]")
SPACE_RE = re.compile(r"\s+")


def normalize_title(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(
        char for char in value
        if not unicodedata.combining(char)
    )
    value = value.lower()
    value = NON_ALNUM_RE.sub(" ", value)
    return SPACE_RE.sub(" ", value).strip()


def detect_delimiter(path):
    return "," if Path(path).suffix.lower() == ".csv" else "\t"


def load_works(
    path,
    key_column,
    title_column,
    author_column,
):
    delimiter = detect_delimiter(path)

    works = []
    first_token_index = defaultdict(list)

    with open(
        path,
        encoding="utf-8-sig",
        newline="",
    ) as f:
        reader = csv.DictReader(
            f,
            delimiter=delimiter,
        )

        required = {
            key_column,
            title_column,
            author_column,
        }

        missing = required - set(reader.fieldnames or [])

        if missing:
            raise ValueError(
                f"Missing columns: {sorted(missing)}"
            )

        for row in reader:
            work_key = (
                row.get(key_column) or ""
            ).strip()

            work_title = (
                row.get(title_column) or ""
            ).strip()

            work_author = (
                row.get(author_column) or ""
            ).strip()

            normalized = normalize_title(
                work_title
            )

            if not work_key or not normalized:
                continue

            work = {
                "work_key": work_key,
                "work_title": work_title,
                "work_author": work_author,
                "normalized_title": normalized,
            }

            idx = len(works)
            works.append(work)

            first_token = normalized.split()[0]

            first_token_index[
                first_token
            ].append(idx)

    return works, first_token_index


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--jstor",
        required=True,
        help="JSTOR metadata JSONL snapshot",
    )

    parser.add_argument(
        "--works",
        required=True,
        help="CSV/TSV containing literary works",
    )

    parser.add_argument(
        "--key-column",
        default="work_key",
    )

    parser.add_argument(
        "--title-column",
        default="title",
    )

    parser.add_argument(
        "--author-column",
        default="author",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output candidate TSV",
    )

    args = parser.parse_args()

    works, first_token_index = load_works(
        args.works,
        args.key_column,
        args.title_column,
        args.author_column,
    )

    print(
        f"Works loaded: {len(works):,}",
        flush=True,
    )

    rows = []

    with open(
        args.jstor,
        encoding="utf-8",
    ) as f:
        for n, line in enumerate(f, 1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if record.get(
                "content_type"
            ) != "article":
                continue

            if record.get(
                "content_subtype"
            ) != "research-article":
                continue

            disciplines = (
                record.get("discipline_names")
                or []
            )

            if (
                "Language & Literature"
                not in disciplines
            ):
                continue

            raw_article_title = (
                record.get("title") or ""
            )

            article_title = normalize_title(
                raw_article_title
            )

            if not article_title:
                continue

            possible = set()

            for token in set(
                article_title.split()
            ):
                possible.update(
                    first_token_index.get(
                        token,
                        [],
                    )
                )

            padded = f" {article_title} "

            for idx in possible:
                work = works[idx]

                phrase = (
                    f" {work['normalized_title']} "
                )

                if phrase not in padded:
                    continue

                rows.append({
                    "work_key":
                        work["work_key"],
                    "work_title":
                        work["work_title"],
                    "work_author":
                        work["work_author"],
                    "jstor_item_id":
                        record.get(
                            "item_id",
                            "",
                        ),
                    "jstor_doi":
                        record.get("doi")
                        or record.get(
                            "ithaka_doi",
                            "",
                        ),
                    "article_title":
                        raw_article_title,
                    "published_date":
                        record.get(
                            "published_date",
                            "",
                        ),
                })

            if n % 1_000_000 == 0:
                print(
                    f"{n:,} JSTOR records processed",
                    flush=True,
                )

    fields = [
        "work_key",
        "work_title",
        "work_author",
        "jstor_item_id",
        "jstor_doi",
        "article_title",
        "published_date",
    ]

    Path(args.output).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        args.output,
        "w",
        encoding="utf-8",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields,
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(rows)

    print()
    print(f"Candidate rows: {len(rows):,}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
