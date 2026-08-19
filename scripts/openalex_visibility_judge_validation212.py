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

OUTPUT = (
    ROOT
    / "derived"
    / "openalex_visibility_judgments_validation212.tsv"
)

SUMMARY = (
    ROOT
    / "derived"
    / "openalex_visibility_summary_validation212.tsv"
)

MODEL = "gpt-5-mini"
PROMPT_VERSION = "literary_visibility_validation212_20260818"
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

First determine whether the record represents a genuine scholarly
secondary source.

Then determine how the target literary work is involved.

Assign exactly one label.

include_substantive

Use when a genuine scholarly secondary source interprets, analyses,
compares, historically positions, discusses the reception or
adaptation of, or otherwise makes a substantive claim about the target
work.

The target work does not need to be the sole or primary subject.

Broader author studies, thematic studies, genre studies, comparative
studies, and studies of multiple works should be included when the
title or abstract makes a meaningful claim about the target work.

include_mention

Use when a genuine scholarly secondary source uses the target work as
a real comparison, quotation, example, or reference, but the supplied
title and abstract do not show substantive analysis of the work itself.

This still counts as broad scholarly visibility.

exclude_non_scholarly

Use when the record is connected to the target work but is not a
scholarly secondary source.

Examples include:
- the literary text itself;
- an electronic-text or ebook record;
- a PDF or download page;
- a commercial book listing;
- a catalogue-only record;
- a study-guide or summary page without original scholarship;
- spam, scraped text, or malformed download metadata.

Do not classify a primary text or download page as include_mention
merely because it reproduces passages from the literary work.

exclude_unrelated

Use when the record is not genuinely connected to the target literary
work.

Examples include:
- an ordinary phrase that happens to match the work title;
- a surname collision;
- an unrelated scientific, legal, or professional article;
- another work with a similar title.

unclear

Use when the supplied metadata is too incomplete, contradictory, or
ambiguous to determine the correct label.

An unusual or incorrect OpenAlex topic is not by itself a reason to
exclude a record. Give greater weight to the record title and abstract.

Calibration examples:

1. "Holroyd's Man" is include_substantive for Heart of Darkness when
the abstract discusses critical debates about the novel, imperialism,
fiction-making, and cultural value, even though the study has a wider
Conrad context and the OpenAlex topic is misleading.

2. A study of astronomical symbolism in the "Ithaca" episode is
include_substantive for Ulysses, even when Ulysses is absent from the
record title but clearly discussed in the abstract.

3. An academic article that briefly compares The Da Vinci Code's
twenty-four-hour structure with Ulysses is include_mention.

4. A scholarly study of Malcolm Lowry that lists Heart of Darkness as
an example of inner-frame storytelling, without further analysis of
the novel, is include_mention.

5. A page titled "ulysses text pdf" containing download instructions
and reproduced novel text is exclude_non_scholarly.

6. "The Great Gatsby [Electronic text] / by F. Scott Fitzgerald" is
exclude_non_scholarly when it represents the primary literary text
rather than secondary scholarship.

7. A chemistry article containing "does the job" and "Lewis acid" is
exclude_unrelated for Sinclair Lewis's novel The Job.

8. A record whose title promises Heart of Darkness criticism but whose
abstract is unrelated medical content is unclear because the metadata
is contradictory.

Return a concise reason and concise evidence from the supplied
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
