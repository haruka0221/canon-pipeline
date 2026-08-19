#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import csv
import json
import re
import time
import unicodedata

from openai import OpenAI


ROOT = Path(__file__).resolve().parents[1]

INPUT = ROOT / "derived" / "openalex_candidates_dump.tsv"

OUTPUT = ROOT / "derived" / "openalex_visibility_judgments_v4_full6007.tsv"

SUMMARY = ROOT / "derived" / "openalex_visibility_summary_v4_full6007.tsv"

MODEL = "gpt-5-mini"
PROMPT_VERSION = "literary_visibility_v4_final_20260818"
MAX_WORKERS = 4

TARGET_WORKS = None

VALID_LABELS = {
    "include_substantive",
    "include_mention",
    "exclude_non_scholarly",
    "exclude_unrelated",
    "unclear",
}


SYSTEM_PROMPT = """
You are classifying OpenAlex candidate records for a dataset measuring
the scholarly visibility of literary works.

Use only the supplied OpenAlex record title, record type, topic, and
abstract. Do not infer what the full text contains.

The classification must be performed in the following order.

STEP 1: DOCUMENT-SCOPE CHECK

First determine whether the record is an eligible scholarly secondary
contribution under this study's operational definition.

Classify as exclude_non_scholarly when the record is primarily any of
the following:

- the primary literary text itself;
- an electronic-text or ebook record of the primary work;
- a critical or annotated edition whose primary function is to present
  or edit the literary text;
- a book review or review notice;
- a bibliography or descriptive bibliography;
- a catalogue or collection catalogue;
- an anthology whose primary function is to reproduce literary texts;
- a preface, front matter, or similar paratext rather than an
  independent research contribution;
- a documentary compilation or reprint collection;
- a books-received or new-books notice;
- a reference entry;
- a PDF/download page, commercial listing, study guide, summary page,
  spam, scraped text, or malformed metadata.

Apply exclude_non_scholarly even when such a record mentions,
summarizes, reproduces, or reports criticism of the target work.

Do not infer that an item is an independent scholarly contribution
merely because it has an academic publisher, editor, commentary,
introduction, or scholarly apparatus.

Only records that pass this document-scope check should proceed to the
next steps.

STEP 2: TARGET-WORK RELEVANCE

Determine whether the record is genuinely connected to the target
literary work.

Classify as exclude_unrelated when the apparent match results from an
ordinary phrase, surname collision, person/work confusion, another work
with a similar title, or an otherwise unrelated subject.

If the supplied metadata is insufficient or contradictory, classify as
unclear rather than guessing.

STEP 3: SUBSTANTIVE ANALYSIS VS SCHOLARLY MENTION

For an eligible scholarly secondary contribution genuinely connected
to the target work:

include_substantive

Use when the supplied title or abstract makes a substantive analytical,
interpretive, comparative, historical, reception-oriented, adaptation-
oriented, or otherwise meaningful claim about the target work.

The work does not need to be the sole or primary subject. Broader
author studies, thematic studies, genre studies, comparative studies,
and studies of multiple works qualify when the supplied metadata shows
meaningful analysis of the target work itself.

include_mention

Use when the target work functions as a genuine scholarly comparison,
quotation, example, reference point, bibliographic reference, or brief
contextual mention, but the supplied title and abstract do not show
substantive analysis of the work itself.

Do not promote a brief mention to include_substantive merely because
the surrounding article is scholarly or discusses the same author.

unclear

Use when the supplied metadata is too incomplete, contradictory, or
ambiguous to decide among the categories above.

An unusual or incorrect OpenAlex topic is not by itself a reason to
exclude a record. Give greater weight to the record title, record type,
and abstract.

Assign exactly one of these labels:

include_substantive
include_mention
exclude_non_scholarly
exclude_unrelated
unclear

Return a concise reason and concise evidence based only on the supplied
metadata.
""".strip()


OUTPUT_FIELDS = [
    "work_key",
    "title",
    "author_name",
    "canonical",
    "test_reason",
    "total_candidates",
    "sampled_n",
    "oa_id",
    "oa_title",
    "oa_abstract",
    "oa_year",
    "oa_type",
    "oa_lang",
    "oa_lit",
    "oa_topic",
    "visibility_label",
    "broad_visibility_include",
    "reason",
    "evidence",
    "model",
    "prompt_version",
]


def normalize(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(
        encoding="utf-8-sig",
        newline="",
    ) as file:
        return list(csv.DictReader(file, delimiter="\t"))


def write_tsv(
    path: Path,
    rows: list[dict[str, object]],
    fields: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            delimiter="\t",
            lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def result_key(row: dict[str, str]) -> tuple[str, str]:
    return (
        row.get("work_key", "").strip(),
        row.get("oa_id", "").strip(),
    )


def make_prompt(row: dict[str, str]) -> str:
    abstract = row.get("oa_abstract", "").strip()

    return f"""
{SYSTEM_PROMPT}

TARGET LITERARY WORK

Title: {row.get("title", "")}
Author: {row.get("author_name", "")}

OPENALEX CANDIDATE RECORD

Record title:
{row.get("oa_title", "")}

Record type:
{row.get("oa_type", "")}

OpenAlex topic:
{row.get("oa_topic", "")}

Abstract:
{abstract if abstract else "[No abstract available]"}
""".strip()


def base_result(row: dict[str, str]) -> dict[str, str]:
    return {
        "work_key": row.get("work_key", ""),
        "title": row.get("title", ""),
        "author_name": row.get("author_name", ""),
        "canonical": row.get("canonical", ""),
        "test_reason": row.get("test_reason", ""),
        "total_candidates": row.get("total_candidates", ""),
        "sampled_n": row.get("sampled_n", ""),
        "oa_id": row.get("oa_id", ""),
        "oa_title": row.get("oa_title", ""),
        "oa_abstract": row.get("oa_abstract", ""),
        "oa_year": row.get("oa_year", ""),
        "oa_type": row.get("oa_type", ""),
        "oa_lang": row.get("oa_lang", ""),
        "oa_lit": row.get("oa_lit", ""),
        "oa_topic": row.get("oa_topic", ""),
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
    }


def judge(
    client: OpenAI,
    row: dict[str, str],
) -> dict[str, str]:

    last_error = ""

    for attempt in range(5):
        try:
            response = client.responses.create(
                model=MODEL,
                input=make_prompt(row),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "literary_visibility_v3",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "visibility_label": {
                                    "type": "string",
                                    "enum": [
                                        "include_substantive",
                                        "include_mention",
                                        "exclude_non_scholarly",
                                        "exclude_unrelated",
                                        "unclear",
                                    ],
                                },
                                "reason": {
                                    "type": "string",
                                },
                                "evidence": {
                                    "type": "string",
                                },
                            },
                            "required": [
                                "visibility_label",
                                "reason",
                                "evidence",
                            ],
                            "additionalProperties": False,
                        },
                    }
                },
            )

            data = json.loads(response.output_text)
            label = data["visibility_label"]

            result = base_result(row)
            result.update({
                "visibility_label": label,
                "broad_visibility_include":
                    "1"
                    if label in {
                        "include_substantive",
                        "include_mention",
                    }
                    else "0",
                "reason": data["reason"].strip(),
                "evidence": data["evidence"].strip(),
            })
            return result

        except Exception as exc:
            last_error = str(exc)
            time.sleep(2 ** attempt)

    result = base_result(row)
    result.update({
        "visibility_label": "error",
        "broad_visibility_include": "",
        "reason": last_error[:500],
        "evidence": "",
    })
    return result


def load_completed() -> dict[
    tuple[str, str],
    dict[str, str],
]:
    if not OUTPUT.exists():
        return {}

    completed = {}

    for row in read_tsv(OUTPUT):
        if (
            row.get("prompt_version") == PROMPT_VERSION
            and row.get("visibility_label") in VALID_LABELS
        ):
            completed[result_key(row)] = row

    return completed


def save_results(
    rows: list[dict[str, str]],
) -> None:
    rows.sort(
        key=lambda row: (
            normalize(row.get("title")),
            row.get("oa_id", ""),
        )
    )
    write_tsv(OUTPUT, rows, OUTPUT_FIELDS)


def build_summary(
    results: list[dict[str, str]],
) -> list[dict[str, object]]:

    grouped = defaultdict(list)

    for row in results:
        grouped[row["work_key"]].append(row)

    output = []

    for work_key, rows in grouped.items():
        first = rows[0]
        counts = Counter(
            row["visibility_label"]
            for row in rows
        )

        included = (
            counts["include_substantive"]
            + counts["include_mention"]
        )

        decided = (
            included
            + counts["exclude_non_scholarly"]
            + counts["exclude_unrelated"]
        )

        output.append({
            "work_key": work_key,
            "work_title": first["title"],
            "work_author": first["author_name"],
            "total_candidates": first["total_candidates"],
            "sampling_method": "uniform_reservoir_sampling",
            "sampling_seed": "20260713",
            "sampled_n": len(rows),
            "include_substantive_n":
                counts["include_substantive"],
            "include_mention_n":
                counts["include_mention"],
            "broad_visibility_include_n":
                included,
            "exclude_non_scholarly_n":
                counts["exclude_non_scholarly"],
            "exclude_unrelated_n":
                counts["exclude_unrelated"],
            "unclear_n":
                counts["unclear"],
            "error_n":
                counts["error"],
            "broad_visibility_rate_among_decided":
                f"{included / decided:.3f}"
                if decided else "",
            "model": MODEL,
            "prompt_version": PROMPT_VERSION,
        })

    output.sort(
        key=lambda row:
        normalize(str(row["work_title"]))
    )

    return output


def main() -> None:
    if not INPUT.exists():
        raise FileNotFoundError(INPUT)

    source_rows = read_tsv(INPUT)

    completed = load_completed()

    pending = [
        row for row in source_rows
        if result_key(row) not in completed
    ]

    print(f"Target candidate rows: {len(source_rows)}")
    print(f"Already completed: {len(completed)}")
    print(f"Pending: {len(pending)}")
    print(f"Model: {MODEL}")
    print(f"Prompt version: {PROMPT_VERSION}")

    client = OpenAI(
        timeout=60.0,
        max_retries=0,
    )

    results = list(completed.values())

    if pending:
        with ThreadPoolExecutor(
            max_workers=MAX_WORKERS,
        ) as executor:

            futures = {
                executor.submit(
                    judge,
                    client,
                    row,
                ): row
                for row in pending
            }

            for number, future in enumerate(
                as_completed(futures),
                start=1,
            ):
                result = future.result()
                results.append(result)

                print(
                    f"[{number}/{len(pending)}] "
                    f"{result['title']} | "
                    f"{result['oa_id']} | "
                    f"{result['visibility_label']}"
                )

                save_results(results)

    save_results(results)

    summary_rows = build_summary(results)

    summary_fields = [
        "work_key",
        "work_title",
        "work_author",
        "total_candidates",
        "sampling_method",
        "sampling_seed",
        "sampled_n",
        "include_substantive_n",
        "include_mention_n",
        "broad_visibility_include_n",
        "exclude_non_scholarly_n",
        "exclude_unrelated_n",
        "unclear_n",
        "error_n",
        "broad_visibility_rate_among_decided",
        "model",
        "prompt_version",
    ]

    write_tsv(
        SUMMARY,
        summary_rows,
        summary_fields,
    )

    print()
    print(f"Created: {OUTPUT}")
    print(f"Created: {SUMMARY}")
    print()

    for row in summary_rows:
        print(
            f"{row['work_title']}: "
            f"substantive={row['include_substantive_n']}, "
            f"mention={row['include_mention_n']}, "
            f"non_scholarly={row['exclude_non_scholarly_n']}, "
            f"unrelated={row['exclude_unrelated_n']}, "
            f"unclear={row['unclear_n']}"
        )


if __name__ == "__main__":
    main()
