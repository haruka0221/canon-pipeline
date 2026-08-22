import argparse
import json
import os
import random
import time
from pathlib import Path

import pandas as pd
from openai import OpenAI


# ============================================================
# Configuration
# ============================================================

SRC = Path("derived/internetarchive_candidates_90works_v2.tsv")
OUT = Path("derived/internetarchive_candidates_90works_llm_v1.tsv")

MODEL = "gpt-5-mini"

# Current GPT-5 mini standard API prices, USD / 1M tokens.
# Used only for approximate runtime reporting.
INPUT_PRICE_PER_M = 0.25
OUTPUT_PRICE_PER_M = 2.00

MAX_RETRIES = 6

LABELS = [
    "primary_text",
    "scholarly_metatext",
    "pedagogical_metatext",
    "adaptation_derivative",
    "unrelated",
    "unclear",
]


SYSTEM_PROMPT = """
You are classifying Internet Archive metadata for a literary-history
research project.

For each record, determine its relationship to the specified TARGET WORK
and TARGET AUTHOR.

Use exactly one of these labels:

1. primary_text
The item contains the target literary work itself, either standalone or
in a collection/combined volume. Ordinary editions, reprints, and
translations of the target work count as primary_text.

2. scholarly_metatext
The item substantially studies, interprets, criticizes, or provides
scholarly discussion of the target work. Examples include monographs,
critical editions primarily functioning as criticism, essays,
dissertations, theses, and scholarly essay collections.

3. pedagogical_metatext
The item is substantially designed for teaching or studying the target
work rather than simply reproducing it. Examples include study guides,
teaching guides, classroom materials, and pedagogical commentary.

4. adaptation_derivative
The item substantially rewrites, abridges, simplifies, adapts,
dramatizes, or otherwise derives from the target work rather than
presenting the work itself. Graded readers and substantial literary
rewritings belong here.

5. unrelated
The item is not substantively about or an edition/adaptation of the
target work. Mere title overlap, phrase reuse, character-name reuse, or
an unrelated work by another author is not enough.

6. unclear
The available metadata is genuinely insufficient to determine the
relationship reliably. Do not use unclear merely because some metadata
fields are missing; use it only when the substantive relationship cannot
reasonably be determined.

Important distinctions:

- A combined volume containing the complete target work is primary_text.
- A translation of the target literary work is primary_text unless the
  metadata indicates substantial simplification/adaptation.
- A graded/simplified reader is adaptation_derivative.
- A book about the target work is scholarly_metatext or
  pedagogical_metatext depending on its primary function.
- A film, children's story, or other work merely using a famous
  character/name is not automatically an adaptation.
- Judge only from the supplied metadata. Do not invent missing facts.

Also return:

subtype:
A short descriptive subtype such as standalone, collected_or_combined,
translation, critical_edition, monograph, essay_collection, dissertation,
study_guide, graded_reader, adaptation, or other.

contains_primary_text:
"yes", "no", or "unclear".

is_about_target_work:
"yes", "no", or "unclear".

confidence:
"high", "medium", or "low".

note:
A concise explanation of the decisive metadata evidence. Keep it short.

Return JSON only with these keys:
label
subtype
contains_primary_text
is_about_target_work
confidence
note
""".strip()


# ============================================================
# Helpers
# ============================================================

def val(x, max_chars=None):
    if pd.isna(x):
        return ""

    s = str(x).strip()

    if max_chars and len(s) > max_chars:
        s = s[:max_chars] + " [TRUNCATED]"

    return s


def build_input(row):
    # Prevent exceptionally long IA descriptions/subjects from
    # dominating token use while preserving useful metadata.
    fields = {
        "TARGET WORK": val(row.get("selection_title")),
        "TARGET AUTHOR": val(row.get("selection_author")),
        "TARGET YEAR": val(row.get("selection_year")),
        "IA TITLE": val(row.get("ia_title"), 1500),
        "IA CREATOR": val(row.get("ia_creator"), 1000),
        "IA DATE": val(row.get("ia_date")),
        "IA YEAR": val(row.get("ia_year")),
        "IA PUBLISHER": val(row.get("ia_publisher"), 1000),
        "IA SUBJECT": val(row.get("ia_subject"), 3000),
        "IA DESCRIPTION": val(row.get("ia_description"), 4000),
        "IA COLLECTION": val(row.get("ia_collection"), 2000),
        "IA LANGUAGE": val(row.get("ia_language"), 500),
        "RETRIEVAL SOURCE": val(row.get("retrieval_source")),
        "AUTHOR METADATA EVIDENCE": val(
            row.get("author_metadata_evidence")
        ),
        "FOUND IN PRIMARY QUERY": val(
            row.get("found_in_primary_query")
        ),
    }

    return "\n".join(
        f"{k}: {v}"
        for k, v in fields.items()
    )


def parse_json_response(text):
    text = text.strip()

    # Defensive handling in case fenced JSON is returned.
    if text.startswith("```"):
        text = text.strip("`").strip()

        if text.lower().startswith("json"):
            text = text[4:].strip()

    obj = json.loads(text)

    required = [
        "label",
        "subtype",
        "contains_primary_text",
        "is_about_target_work",
        "confidence",
        "note",
    ]

    for k in required:
        if k not in obj:
            raise ValueError(f"Missing JSON key: {k}")

    if obj["label"] not in LABELS:
        raise ValueError(
            f"Invalid label: {obj['label']}"
        )

    if obj["contains_primary_text"] not in [
        "yes", "no", "unclear"
    ]:
        raise ValueError(
            "Invalid contains_primary_text"
        )

    if obj["is_about_target_work"] not in [
        "yes", "no", "unclear"
    ]:
        raise ValueError(
            "Invalid is_about_target_work"
        )

    if obj["confidence"] not in [
        "high", "medium", "low"
    ]:
        raise ValueError(
            f"Invalid confidence: {obj['confidence']}"
        )

    return obj


def classify(client, row):

    user_input = build_input(row)

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            response = client.responses.create(
                model=MODEL,
                instructions=SYSTEM_PROMPT,
                input=user_input,
            )

            obj = parse_json_response(
                response.output_text
            )

            usage = getattr(response, "usage", None)

            input_tokens = (
                getattr(usage, "input_tokens", 0)
                if usage else 0
            )

            output_tokens = (
                getattr(usage, "output_tokens", 0)
                if usage else 0
            )

            return obj, input_tokens, output_tokens

        except Exception as e:
            last_error = e

            if attempt == MAX_RETRIES:
                break

            wait = min(
                60,
                2 ** (attempt - 1)
                + random.random()
            )

            print(
                f"\n  ERROR attempt "
                f"{attempt}/{MAX_RETRIES}: {e}"
            )
            print(
                f"  retrying after {wait:.1f}s"
            )

            time.sleep(wait)

    raise RuntimeError(
        f"Classification failed after "
        f"{MAX_RETRIES} attempts: {last_error}"
    )


def save(df):
    df.to_csv(
        OUT,
        sep="\t",
        index=False
    )


# ============================================================
# Arguments
# ============================================================

parser = argparse.ArgumentParser()

parser.add_argument(
    "--limit",
    type=int,
    default=None,
    help=(
        "Maximum number of NEW records to classify "
        "during this run. Omit for all remaining."
    ),
)

parser.add_argument(
    "--report-every",
    type=int,
    default=100,
)

args = parser.parse_args()


# ============================================================
# Setup
# ============================================================

if not os.environ.get("OPENAI_API_KEY"):
    raise RuntimeError(
        "OPENAI_API_KEY is not set."
    )

client = OpenAI()

df = pd.read_csv(
    SRC,
    sep="\t",
    dtype=str,
    keep_default_na=False,
)

print("Source rows:", len(df))

if df.duplicated(
    ["openlibrary_work_key", "ia_identifier"]
).any():
    raise RuntimeError(
        "Duplicate work+identifier pairs in source."
    )


# ============================================================
# Resume previous classifications
# ============================================================

output_cols = [
    "llm_label",
    "llm_subtype",
    "contains_primary_text",
    "is_about_target_work",
    "llm_confidence",
    "llm_note",
    "llm_model",
    "llm_input_tokens",
    "llm_output_tokens",
]

for c in output_cols:
    if c not in df.columns:
        df[c] = ""


if OUT.exists():

    old = pd.read_csv(
        OUT,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    old_key = {
        (
            r["openlibrary_work_key"],
            r["ia_identifier"],
        ): r
        for _, r in old.iterrows()
        if r.get("llm_label", "")
    }

    for i, row in df.iterrows():

        key = (
            row["openlibrary_work_key"],
            row["ia_identifier"],
        )

        if key not in old_key:
            continue

        r = old_key[key]

        for c in output_cols:
            if c in r:
                df.at[i, c] = r[c]


already = (
    df["llm_label"]
    .astype(str)
    .str.strip()
    .ne("")
)

print("Already classified:", already.sum())
print("Remaining:", (~already).sum())


# ============================================================
# Classification
# ============================================================

run_count = 0
run_input_tokens = 0
run_output_tokens = 0

total = len(df)

remaining_at_start = int((~already).sum())

for idx, row in df.iterrows():

    if val(row["llm_label"]):
        continue

    if (
        args.limit is not None
        and run_count >= args.limit
    ):
        break

    print(
        f"[{idx+1}/{total}] "
        f"{row['selection_title']} | "
        f"{row['ia_title'][:80]}"
    )

    obj, input_tokens, output_tokens = classify(
        client,
        row
    )

    df.at[idx, "llm_label"] = obj["label"]
    df.at[idx, "llm_subtype"] = obj["subtype"]
    df.at[idx, "contains_primary_text"] = (
        obj["contains_primary_text"]
    )
    df.at[idx, "is_about_target_work"] = (
        obj["is_about_target_work"]
    )
    df.at[idx, "llm_confidence"] = (
        obj["confidence"]
    )
    df.at[idx, "llm_note"] = obj["note"]
    df.at[idx, "llm_model"] = MODEL
    df.at[idx, "llm_input_tokens"] = str(
        input_tokens
    )
    df.at[idx, "llm_output_tokens"] = str(
        output_tokens
    )

    run_count += 1
    run_input_tokens += input_tokens
    run_output_tokens += output_tokens

    # Save every record: safest possible resume behavior.
    save(df)

    if (
        run_count % args.report_every == 0
        or run_count == 1
    ):

        cost = (
            run_input_tokens
            / 1_000_000
            * INPUT_PRICE_PER_M
            +
            run_output_tokens
            / 1_000_000
            * OUTPUT_PRICE_PER_M
        )

        avg_cost = (
            cost / run_count
            if run_count else 0
        )

        projected_remaining_cost = (
            avg_cost * remaining_at_start
        )

        print("\n" + "-" * 72)
        print(
            f"Processed this run: {run_count}"
        )
        print(
            f"Input tokens: {run_input_tokens:,}"
        )
        print(
            f"Output tokens: {run_output_tokens:,}"
        )
        print(
            f"Estimated run cost: "
            f"${cost:.4f}"
        )
        print(
            f"Projected cost for "
            f"{remaining_at_start:,} records "
            f"at current average: "
            f"${projected_remaining_cost:.2f}"
        )
        print("-" * 72 + "\n")


# ============================================================
# Final report
# ============================================================

save(df)

done = (
    df["llm_label"]
    .astype(str)
    .str.strip()
    .ne("")
)

print("\n" + "=" * 80)
print("Created/updated:", OUT)

print(
    "Classified:",
    done.sum(),
    "/",
    len(df)
)

print(
    "Remaining:",
    (~done).sum()
)

print("\nLABELS SO FAR:")
print(
    df.loc[done, "llm_label"]
    .value_counts()
    .to_string()
)

if run_count:

    cost = (
        run_input_tokens
        / 1_000_000
        * INPUT_PRICE_PER_M
        +
        run_output_tokens
        / 1_000_000
        * OUTPUT_PRICE_PER_M
    )

    print("\nTHIS RUN:")
    print("Records:", run_count)
    print(
        "Input tokens:",
        f"{run_input_tokens:,}"
    )
    print(
        "Output tokens:",
        f"{run_output_tokens:,}"
    )
    print(
        "Estimated cost:",
        f"${cost:.4f}"
    )

print("\nIA LLM CLASSIFICATION V1 OK")
