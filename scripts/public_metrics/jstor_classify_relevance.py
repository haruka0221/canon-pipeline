#!/usr/bin/env python3

"""
Classify candidate JSTOR article-title matches as relevant, unrelated,
or unclear.

Input is a candidate TSV produced by jstor_retrieve_candidates.py.

The classifier uses only the target work title, target author, and JSTOR
article title. It does not use abstracts or full text.

Requires OPENAI_API_KEY.
"""


import argparse
import json
import os
import time
from pathlib import Path

import pandas as pd
from openai import OpenAI


MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
PROMPT_VERSION = "jstor_title_relevance_20260808"

SYSTEM_PROMPT = """
You are classifying candidate matches between a literary work and a JSTOR
research-article title.

For each candidate, decide whether the article title refers to the TARGET
LITERARY WORK.

Labels:

relevant
- The article title clearly refers to, discusses, compares, adapts, teaches,
  interprets, or otherwise concerns the target literary work.
- Comparative articles are relevant if the target work is genuinely one of
  the works discussed.

unrelated
- The matched words refer to something else: an ordinary phrase, another
  person, another work, another cultural object, or a different meaning.
- The literary-work title merely occurs accidentally inside another phrase.

unclear
- The article title alone does not provide enough evidence to decide.
- Do not guess when a short or ambiguous title could plausibly refer either
  to the target work or to something else.

Important:
- Use the target work title and author to identify the intended literary work.
- Judge from the article title only. Do not invent unavailable abstract or
  full-text context.
- Well-established literary knowledge may be used when the article title
  clearly identifies characters, authors, or contexts associated with the
  target work.
- For highly ambiguous titles such as Ulysses, Orlando, Kim, or The Job,
  require contextual evidence before choosing relevant.
- If the article title is too short or ambiguous to distinguish referents,
  choose unclear rather than guessing.

Additional decision rules:

- A mere allusion, metaphor, comparison, nickname, cultural reference,
  or reuse of the same words does NOT make a candidate relevant.
  The target literary work itself must be an object of discussion.

- References to a character or cultural figure derived from a work
  should be labeled unrelated unless the article title also indicates
  discussion of the literary work itself.

- For short or ambiguous titles, an exact title match by itself is not
  sufficient evidence. If the article title provides no author,
  character, quotation, translation, adaptation, or other contextual
  evidence identifying the target work, choose unclear.

- Do not infer that a generic phrase refers to the target work merely
  because it matches the work title.

Examples:

Target: The Job / Sinclair Lewis
Article: The Job
Label: unclear

Target: The Job / Sinclair Lewis
Article: The Job of Work
Label: unrelated

Target: Dracula / Bram Stoker
Article: Phoenix Rising: Like Dracula from the Grave
Label: unrelated

Target: Dracula / Bram Stoker
Article: The Narrative Method of Dracula
Label: relevant

Target: Peter Pan / J. M. Barrie
Article: The Peter Pan of American Literature
Label: unrelated

Return one result for every candidate_id supplied.
""".strip()


SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidate_id": {
                        "type": "string"
                    },
                    "label": {
                        "type": "string",
                        "enum": [
                            "relevant",
                            "unrelated",
                            "unclear",
                        ],
                    },
                    "confidence": {
                        "type": "string",
                        "enum": [
                            "high",
                            "medium",
                            "low",
                        ],
                    },
                    "note": {
                        "type": "string"
                    },
                },
                "required": [
                    "candidate_id",
                    "label",
                    "confidence",
                    "note",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}


def read_table(path):
    path = Path(path)
    sep = "," if path.suffix.lower() == ".csv" else "\t"
    return pd.read_csv(
        path,
        sep=sep,
        dtype=str,
    ).fillna("")


def make_candidate_id(row):
    review_id = str(row.get("review_id", "")).strip()

    if review_id:
        return review_id

    work_key = str(row.get("work_key", "")).strip()
    item_id = str(row.get("jstor_item_id", "")).strip()

    if not work_key or not item_id:
        raise ValueError(
            "Need either review_id or both work_key and jstor_item_id."
        )

    return f"{work_key}::{item_id}"


def build_batch_prompt(batch):
    candidates = []

    for _, row in batch.iterrows():
        candidates.append({
            "candidate_id": row["candidate_id"],
            "target_work_title": row["work_title"],
            "target_work_author": row["work_author"],
            "article_title": row["article_title"],
        })

    return (
        "Classify the following candidates.\n\n"
        + json.dumps(
            candidates,
            ensure_ascii=False,
            indent=2,
        )
    )


def classify_batch(client, batch, max_retries=3):
    expected = set(batch["candidate_id"])

    for attempt in range(1, max_retries + 1):
        try:
            response = client.responses.create(
                model=MODEL,
                instructions=SYSTEM_PROMPT,
                input=build_batch_prompt(batch),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "jstor_title_relevance",
                        "schema": SCHEMA,
                        "strict": True,
                    }
                },
            )

            data = json.loads(response.output_text)
            results = data["results"]

            returned = {
                r["candidate_id"]
                for r in results
            }

            if returned != expected:
                missing = expected - returned
                extra = returned - expected

                raise ValueError(
                    f"ID mismatch. "
                    f"missing={missing}, extra={extra}"
                )

            if len(results) != len(returned):
                raise ValueError(
                    "Duplicate candidate_id in model output."
                )

            return {
                r["candidate_id"]: r
                for r in results
            }

        except Exception as exc:
            print(
                f"Batch attempt {attempt}/{max_retries} failed: "
                f"{exc}",
                flush=True,
            )

            if attempt == max_retries:
                raise

            time.sleep(2 * attempt)


def save(df, path):
    Path(path).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        path,
        sep="\t",
        index=False,
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
    )
    parser.add_argument(
        "--output",
        required=True,
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional test limit.",
    )

    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is not set."
        )

    input_df = read_table(args.input)

    required = {
        "work_title",
        "work_author",
        "article_title",
    }

    missing = required - set(input_df.columns)

    if missing:
        raise SystemExit(
            f"Missing required columns: {sorted(missing)}"
        )

    input_df["candidate_id"] = input_df.apply(
        make_candidate_id,
        axis=1,
    )

    if input_df["candidate_id"].duplicated().any():
        dupes = input_df.loc[
            input_df["candidate_id"].duplicated(),
            "candidate_id",
        ].tolist()

        raise SystemExit(
            f"Duplicate candidate IDs: {dupes[:10]}"
        )

    output_path = Path(args.output)

    if output_path.exists():
        df = pd.read_csv(
            output_path,
            sep="\t",
            dtype=str,
        ).fillna("")

        print(
            f"Resuming existing output: {output_path}",
            flush=True,
        )

        input_ids = set(input_df["candidate_id"])
        output_ids = set(df["candidate_id"])

        if input_ids != output_ids:
            raise SystemExit(
                "Existing output does not match input candidate IDs."
            )

    else:
        df = input_df.copy()

        df["llm_label"] = ""
        df["llm_confidence"] = ""
        df["llm_note"] = ""
        df["llm_model"] = ""
        df["llm_prompt_version"] = ""

        save(df, output_path)

    pending = df.index[
        df["llm_label"].str.strip() == ""
    ].tolist()

    if args.limit is not None:
        pending = pending[:args.limit]

    print(f"Model: {MODEL}")
    print(f"Prompt: {PROMPT_VERSION}")
    print(f"Rows total: {len(df):,}")
    print(f"Rows pending this run: {len(pending):,}")
    print()

    if not pending:
        print("Nothing to classify.")
        return

    client = OpenAI()

    completed = 0

    for start in range(
        0,
        len(pending),
        args.batch_size,
    ):
        idxs = pending[
            start:start + args.batch_size
        ]

        batch = df.loc[idxs]

        results = classify_batch(
            client,
            batch,
        )

        for idx in idxs:
            candidate_id = df.at[
                idx,
                "candidate_id",
            ]

            result = results[candidate_id]

            df.at[idx, "llm_label"] = (
                result["label"]
            )
            df.at[idx, "llm_confidence"] = (
                result["confidence"]
            )
            df.at[idx, "llm_note"] = (
                result["note"]
            )
            df.at[idx, "llm_model"] = MODEL
            df.at[
                idx,
                "llm_prompt_version",
            ] = PROMPT_VERSION

        save(df, output_path)

        completed += len(idxs)

        print(
            f"Completed this run: "
            f"{completed:,}/{len(pending):,}",
            flush=True,
        )

    print()
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
