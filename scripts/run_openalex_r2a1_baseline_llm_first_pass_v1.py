#!/usr/bin/env python3

from __future__ import annotations

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from pathlib import Path

import hashlib
import json
import os
import time

import pandas as pd
from openai import OpenAI


ROOT = Path(__file__).resolve().parents[1]

INPUT_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_r2a1_baseline_validation_review_input_v1"
)

INPUT = (
    INPUT_DIR
    / "openalex_r2a1_baseline_validation_blind_v1.tsv"
)

INPUT_MANIFEST = (
    INPUT_DIR
    / "openalex_r2a1_baseline_validation_review_input_v1_manifest.json"
)

PROMPT = (
    ROOT
    / "docs"
    / "OPENALEX_R2A1_BASELINE_LLM_FIRST_PASS_PROMPT_V1.md"
)

OUT_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_r2a1_baseline_validation_llm_first_pass_v1"
)

PARTIAL = (
    OUT_DIR
    / "openalex_r2a1_baseline_validation_llm_first_pass_v1.partial.tsv"
)

RUN_CONFIG = (
    OUT_DIR
    / "openalex_r2a1_baseline_validation_llm_first_pass_v1_run_config.json"
)

OUT_TSV = (
    OUT_DIR
    / "openalex_r2a1_baseline_validation_llm_first_pass_v1.tsv"
)

OUT_SUMMARY = (
    OUT_DIR
    / "openalex_r2a1_baseline_validation_llm_first_pass_summary_v1.json"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openalex_r2a1_baseline_validation_llm_first_pass_v1_manifest.json"
)


RELEASE = (
    "openalex-r2a1-baseline-validation-"
    "llm-first-pass-v1"
)

PROMPT_VERSION = (
    "openalex-r2a1-baseline-"
    "llm-first-pass-prompt-v1"
)

CREATED_AT = "2026-10-11"

MODEL = "gpt-6.1-sol"

EXPECTED_ROWS = 1147

MAX_WORKERS = int(
    os.environ.get(
        "OPENAI_MAX_WORKERS",
        "6",
    )
)

MAX_ATTEMPTS = 5

ORDER_SALT = (
    "openalex-r2a1-baseline-"
    "llm-first-pass-v1"
)


VALID_REASONS = {
    "VALID_TARGET_REFERENCE": {
        "DIRECT_TARGET_REFERENCE",
        "VALID_TITLE_VARIANT",
        "VALID_CONTEXTUAL_REFERENCE",
    },

    "INVALID_TARGET_REFERENCE": {
        "TITLE_COLLISION_DIFFERENT_WORK",
        "GENERIC_OR_LEXICAL_TITLE_USE",
        "AUTHOR_COLLISION_DIFFERENT_PERSON",
        "TITLE_AUTHOR_UNLINKED_COOCCURRENCE",
        "WRONG_WORK_SAME_AUTHOR",
        "ALIAS_NOT_TARGET_EQUIVALENT",
        "METADATA_TEXT_ARTIFACT",
        "OTHER",
    },

    "UNCERTAIN": {
        "INSUFFICIENT_CONTEXT",
        "AMBIGUOUS_TARGET_REFERENCE",
    },
}

VALID_CONFIDENCE = {
    "HIGH",
    "MEDIUM",
    "LOW",
}


OUTPUT_FIELDS = [
    "baseline_candidate_id",
    "project_work_id",
    "target_title",
    "target_author",
    "openalex_work_id",
    "openalex_display_name",
    "openalex_abstract",
    "publication_year",
    "publication_date",
    "doi",

    "llm_first_pass_judgment",
    "llm_first_pass_reason_code",
    "llm_first_pass_confidence",
    "llm_first_pass_note",

    "llm_model_requested",
    "llm_model_returned",
    "llm_response_id",
    "llm_input_tokens",
    "llm_output_tokens",
    "llm_prompt_version",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def atomic_tsv(
    df: pd.DataFrame,
    path: Path,
) -> None:

    tmp = path.with_name(
        path.name + ".tmp"
    )

    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    os.replace(
        tmp,
        path,
    )


def atomic_json(
    obj,
    path: Path,
) -> None:

    tmp = path.with_name(
        path.name + ".tmp"
    )

    tmp.write_text(
        json.dumps(
            obj,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    os.replace(
        tmp,
        path,
    )


def stable_key(
    candidate_id: str,
) -> str:

    return hashlib.sha256(
        (
            ORDER_SALT
            + "\0"
            + candidate_id
        ).encode("utf-8")
    ).hexdigest()


def clean(value) -> str:
    if pd.isna(value):
        return ""

    return str(value)


def make_input(
    prompt_text: str,
    row: dict[str, str],
) -> str:

    abstract = (
        row.get(
            "openalex_abstract",
            "",
        ).strip()
    )

    if not abstract:
        abstract = "[No abstract available]"

    return f"""
{prompt_text}

CANDIDATE TO ADJUDICATE

baseline_candidate_id:
{row["baseline_candidate_id"]}

TARGET LITERARY WORK

Target title:
{row["target_title"]}

Target author:
{row["target_author"]}

OPENALEX RECORD

OpenAlex Work ID:
{row["openalex_work_id"]}

Record title:
{row["openalex_display_name"]}

Abstract:
{abstract}

Publication year:
{row["publication_year"]}

Publication date:
{row["publication_date"]}

DOI:
{row["doi"]}
""".strip()


SCHEMA = {
    "type": "object",

    "properties": {
        "baseline_candidate_id": {
            "type": "string",
        },

        "llm_first_pass_judgment": {
            "type": "string",
            "enum": [
                "VALID_TARGET_REFERENCE",
                "INVALID_TARGET_REFERENCE",
                "UNCERTAIN",
            ],
        },

        "llm_first_pass_reason_code": {
            "type": "string",
            "enum": sorted(
                set().union(
                    *VALID_REASONS.values()
                )
            ),
        },

        "llm_first_pass_confidence": {
            "type": "string",
            "enum": sorted(
                VALID_CONFIDENCE
            ),
        },

        "llm_first_pass_note": {
            "type": "string",
        },
    },

    "required": [
        "baseline_candidate_id",
        "llm_first_pass_judgment",
        "llm_first_pass_reason_code",
        "llm_first_pass_confidence",
        "llm_first_pass_note",
    ],

    "additionalProperties": False,
}


def validate_result(
    candidate_id: str,
    obj: dict,
) -> None:

    if (
        obj.get(
            "baseline_candidate_id"
        )
        != candidate_id
    ):
        raise ValueError(
            "Candidate ID echo mismatch: "
            f"{candidate_id} != "
            f"{obj.get('baseline_candidate_id')}"
        )

    judgment = obj.get(
        "llm_first_pass_judgment"
    )

    reason = obj.get(
        "llm_first_pass_reason_code"
    )

    confidence = obj.get(
        "llm_first_pass_confidence"
    )

    note = str(
        obj.get(
            "llm_first_pass_note",
            "",
        )
    ).strip()

    if judgment not in VALID_REASONS:
        raise ValueError(
            f"Invalid judgment: {judgment}"
        )

    if (
        reason
        not in VALID_REASONS[
            judgment
        ]
    ):
        raise ValueError(
            "Reason/judgment mismatch: "
            f"{judgment} / {reason}"
        )

    if (
        confidence
        not in VALID_CONFIDENCE
    ):
        raise ValueError(
            f"Invalid confidence: {confidence}"
        )

    if not note:
        raise ValueError(
            "Blank llm_first_pass_note"
        )


def call_one(
    client: OpenAI,
    prompt_text: str,
    row: dict[str, str],
) -> dict[str, str]:

    candidate_id = row[
        "baseline_candidate_id"
    ]

    last_error = None

    for attempt in range(
        1,
        MAX_ATTEMPTS + 1,
    ):
        try:

            response = (
                client.responses.create(
                    model=MODEL,

                    input=make_input(
                        prompt_text,
                        row,
                    ),

                    text={
                        "format": {
                            "type":
                                "json_schema",

                            "name":
                                "openalex_r2a1_"
                                "baseline_target_"
                                "attribution_v1",

                            "strict":
                                True,

                            "schema":
                                SCHEMA,
                        }
                    },
                )
            )

            obj = json.loads(
                response.output_text
            )

            validate_result(
                candidate_id,
                obj,
            )

            usage = getattr(
                response,
                "usage",
                None,
            )

            input_tokens = ""
            output_tokens = ""

            if usage is not None:
                input_tokens = str(
                    getattr(
                        usage,
                        "input_tokens",
                        "",
                    )
                    or ""
                )

                output_tokens = str(
                    getattr(
                        usage,
                        "output_tokens",
                        "",
                    )
                    or ""
                )

            return {
                **{
                    c: row.get(c, "")
                    for c in [
                        "baseline_candidate_id",
                        "project_work_id",
                        "target_title",
                        "target_author",
                        "openalex_work_id",
                        "openalex_display_name",
                        "openalex_abstract",
                        "publication_year",
                        "publication_date",
                        "doi",
                    ]
                },

                "llm_first_pass_judgment":
                    obj[
                        "llm_first_pass_judgment"
                    ],

                "llm_first_pass_reason_code":
                    obj[
                        "llm_first_pass_reason_code"
                    ],

                "llm_first_pass_confidence":
                    obj[
                        "llm_first_pass_confidence"
                    ],

                "llm_first_pass_note":
                    obj[
                        "llm_first_pass_note"
                    ].strip(),

                "llm_model_requested":
                    MODEL,

                "llm_model_returned":
                    str(
                        getattr(
                            response,
                            "model",
                            "",
                        )
                        or ""
                    ),

                "llm_response_id":
                    str(
                        getattr(
                            response,
                            "id",
                            "",
                        )
                        or ""
                    ),

                "llm_input_tokens":
                    input_tokens,

                "llm_output_tokens":
                    output_tokens,

                "llm_prompt_version":
                    PROMPT_VERSION,
            }

        except Exception as exc:
            last_error = exc

            if attempt < MAX_ATTEMPTS:
                time.sleep(
                    min(
                        2 ** attempt,
                        20,
                    )
                )

    raise RuntimeError(
        f"{candidate_id}: "
        f"{type(last_error).__name__}: "
        f"{last_error}"
    )


def load_partial(
    source_ids: set[str],
) -> pd.DataFrame:

    if not PARTIAL.exists():
        return pd.DataFrame(
            columns=OUTPUT_FIELDS
        )

    p = pd.read_csv(
        PARTIAL,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    assert set(
        OUTPUT_FIELDS
    ) == set(
        p.columns
    )

    p = p[
        OUTPUT_FIELDS
    ]

    assert p[
        "baseline_candidate_id"
    ].is_unique

    assert set(
        p[
            "baseline_candidate_id"
        ]
    ) <= source_ids

    assert p[
        "llm_model_requested"
    ].eq(MODEL).all()

    assert p[
        "llm_prompt_version"
    ].eq(
        PROMPT_VERSION
    ).all()

    return p


def checkpoint(
    rows: list[dict[str, str]],
) -> None:

    p = pd.DataFrame(
        rows,
        columns=OUTPUT_FIELDS,
    )

    p = (
        p.sort_values(
            "baseline_candidate_id",
            kind="stable",
        )
        .reset_index(drop=True)
    )

    assert p[
        "baseline_candidate_id"
    ].is_unique

    atomic_tsv(
        p,
        PARTIAL,
    )


def main():

    for path in [
        INPUT,
        INPUT_MANIFEST,
        PROMPT,
    ]:
        if not path.exists():
            raise FileNotFoundError(path)

    if OUT_TSV.exists():
        raise RuntimeError(
            f"Final output already exists: "
            f"{OUT_TSV}"
        )

    src = pd.read_csv(
        INPUT,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    assert len(src) == EXPECTED_ROWS

    assert src[
        "baseline_candidate_id"
    ].is_unique

    for c in [
        "human_judgment",
        "human_reason_code",
        "human_notes",
    ]:
        assert src[c].eq("").all()

    prompt_text = (
        PROMPT.read_text(
            encoding="utf-8"
        ).strip()
    )

    input_sha = sha256_file(
        INPUT
    )

    input_manifest_sha = sha256_file(
        INPUT_MANIFEST
    )

    prompt_sha = sha256_file(
        PROMPT
    )

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    config = {
        "release":
            RELEASE,

        "created_at":
            CREATED_AT,

        "model":
            MODEL,

        "prompt_version":
            PROMPT_VERSION,

        "input": {
            "path":
                str(
                    INPUT.relative_to(
                        ROOT
                    )
                ),
            "sha256":
                input_sha,
        },

        "input_manifest": {
            "path":
                str(
                    INPUT_MANIFEST.relative_to(
                        ROOT
                    )
                ),
            "sha256":
                input_manifest_sha,
        },

        "prompt": {
            "path":
                str(
                    PROMPT.relative_to(
                        ROOT
                    )
                ),
            "sha256":
                prompt_sha,
        },

        "ordering": {
            "method":
                (
                    "SHA256("
                    "salt + NUL + "
                    "baseline_candidate_id)"
                ),

            "salt":
                ORDER_SALT,
        },

        "max_workers":
            MAX_WORKERS,

        "max_attempts_per_candidate":
            MAX_ATTEMPTS,
    }

    if RUN_CONFIG.exists():

        existing = json.loads(
            RUN_CONFIG.read_text(
                encoding="utf-8"
            )
        )

        # Worker count may differ on resume without
        # changing adjudication semantics.
        existing_cmp = dict(existing)
        current_cmp = dict(config)

        existing_cmp.pop(
            "max_workers",
            None,
        )

        current_cmp.pop(
            "max_workers",
            None,
        )

        assert (
            existing_cmp
            == current_cmp
        ), (
            "Run configuration differs from "
            "existing partial-run configuration"
        )

    else:
        atomic_json(
            config,
            RUN_CONFIG,
        )

    source_ids = set(
        src[
            "baseline_candidate_id"
        ]
    )

    partial = load_partial(
        source_ids
    )

    done_ids = set(
        partial[
            "baseline_candidate_id"
        ]
    )

    result_rows = (
        partial[
            OUTPUT_FIELDS
        ]
        .to_dict(
            orient="records"
        )
    )

    remaining = (
        src.loc[
            ~src[
                "baseline_candidate_id"
            ].isin(
                done_ids
            )
        ]
        .copy()
    )

    remaining[
        "_stable_order"
    ] = remaining[
        "baseline_candidate_id"
    ].map(
        stable_key
    )

    remaining = (
        remaining.sort_values(
            [
                "_stable_order",
                "baseline_candidate_id",
            ],
            kind="stable",
        )
        .drop(
            columns=[
                "_stable_order"
            ]
        )
        .reset_index(drop=True)
    )

    print(
        "=== R2+A1 BASELINE "
        "LLM FIRST PASS V1 ==="
    )

    print(
        "model:",
        MODEL,
    )

    print(
        "source rows:",
        len(src),
    )

    print(
        "already completed:",
        len(done_ids),
    )

    print(
        "remaining:",
        len(remaining),
    )

    print(
        "max workers:",
        MAX_WORKERS,
    )

    if len(remaining):

        client = OpenAI()

        failures = []

        with ThreadPoolExecutor(
            max_workers=MAX_WORKERS
        ) as executor:

            futures = {
                executor.submit(
                    call_one,
                    client,
                    prompt_text,
                    {
                        k: clean(v)
                        for k, v
                        in row._asdict().items()
                    },
                ):
                row.baseline_candidate_id

                for row
                in remaining.itertuples(
                    index=False
                )
            }

            for i, future in enumerate(
                as_completed(futures),
                start=1,
            ):

                cid = futures[
                    future
                ]

                try:
                    result = (
                        future.result()
                    )

                    result_rows.append(
                        result
                    )

                    checkpoint(
                        result_rows
                    )

                except Exception as exc:
                    failures.append(
                        (
                            cid,
                            str(exc),
                        )
                    )

                if (
                    i % 25 == 0
                    or i == len(futures)
                ):
                    print(
                        "completed this run:",
                        i,
                        "/",
                        len(futures),
                        "| total saved:",
                        len(result_rows),
                        "| failures:",
                        len(failures),
                        flush=True,
                    )

        if failures:
            print()
            print(
                "FAILED CANDIDATES:"
            )

            for cid, message in failures:
                print(
                    cid,
                    message,
                    sep="\t",
                )

            raise RuntimeError(
                "One or more candidates failed. "
                "Partial successful results were "
                "saved; rerun the same command "
                "to resume."
            )

    final = pd.DataFrame(
        result_rows,
        columns=OUTPUT_FIELDS,
    )

    final = (
        final.sort_values(
            "baseline_candidate_id",
            kind="stable",
        )
        .reset_index(drop=True)
    )

    assert len(final) == EXPECTED_ROWS

    assert final[
        "baseline_candidate_id"
    ].is_unique

    assert set(
        final[
            "baseline_candidate_id"
        ]
    ) == source_ids

    for row in final.itertuples(
        index=False
    ):
        validate_result(
            row.baseline_candidate_id,
            {
                "baseline_candidate_id":
                    row.baseline_candidate_id,

                "llm_first_pass_judgment":
                    row.llm_first_pass_judgment,

                "llm_first_pass_reason_code":
                    row.llm_first_pass_reason_code,

                "llm_first_pass_confidence":
                    row.llm_first_pass_confidence,

                "llm_first_pass_note":
                    row.llm_first_pass_note,
            },
        )

    atomic_tsv(
        final,
        OUT_TSV,
    )

    judgment_counts = {
        str(k): int(v)
        for k, v
        in final[
            "llm_first_pass_judgment"
        ]
        .value_counts()
        .sort_index()
        .items()
    }

    reason_counts = {
        str(k): int(v)
        for k, v
        in final[
            "llm_first_pass_reason_code"
        ]
        .value_counts()
        .sort_index()
        .items()
    }

    confidence_counts = {
        str(k): int(v)
        for k, v
        in final[
            "llm_first_pass_confidence"
        ]
        .value_counts()
        .sort_index()
        .items()
    }

    input_token_total = int(
        pd.to_numeric(
            final[
                "llm_input_tokens"
            ],
            errors="coerce",
        )
        .fillna(0)
        .sum()
    )

    output_token_total = int(
        pd.to_numeric(
            final[
                "llm_output_tokens"
            ],
            errors="coerce",
        )
        .fillna(0)
        .sum()
    )

    summary = {
        "release":
            RELEASE,

        "created_at":
            CREATED_AT,

        "status":
            "provisional_blind_llm_first_pass",

        "candidate_rows":
            len(final),

        "model_requested":
            MODEL,

        "prompt_version":
            PROMPT_VERSION,

        "judgment_counts":
            judgment_counts,

        "reason_code_counts":
            reason_counts,

        "confidence_counts":
            confidence_counts,

        "usage": {
            "input_tokens":
                input_token_total,

            "output_tokens":
                output_token_total,
        },

        "interpretation": [
            (
                "These are provisional LLM "
                "first-pass judgments, not "
                "authoritative human judgments."
            ),

            (
                "The LLM received no primary/"
                "secondary sample membership, "
                "retrieval-risk features, work "
                "candidate volume, or query "
                "provenance."
            ),

            (
                "The adjudication target is "
                "target attribution only; "
                "document scope and mention "
                "strength remain separate."
            ),

            (
                "The primary 800-pair sample "
                "must use human adjudication, "
                "not these LLM labels, for the "
                "final baseline precision result."
            ),
        ],
    }

    atomic_json(
        summary,
        OUT_SUMMARY,
    )

    manifest = {
        "release":
            RELEASE,

        "created_at":
            CREATED_AT,

        "model_requested":
            MODEL,

        "prompt_version":
            PROMPT_VERSION,

        "sources": {
            str(
                INPUT.relative_to(ROOT)
            ):
                input_sha,

            str(
                INPUT_MANIFEST.relative_to(
                    ROOT
                )
            ):
                input_manifest_sha,

            str(
                PROMPT.relative_to(ROOT)
            ):
                prompt_sha,
        },

        "outputs": {
            str(
                OUT_TSV.relative_to(ROOT)
            ):
                sha256_file(
                    OUT_TSV
                ),

            str(
                OUT_SUMMARY.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    OUT_SUMMARY
                ),
        },

        "blinding": {
            "sample_membership_used":
                False,

            "retrieval_risk_features_used":
                False,

            "candidate_volume_used":
                False,

            "query_provenance_used":
                False,

            "external_web_used":
                False,
        },
    }

    atomic_json(
        manifest,
        OUT_MANIFEST,
    )

    # Partial checkpoint has served its purpose.
    if PARTIAL.exists():
        PARTIAL.unlink()

    print()
    print(
        "=== COMPLETE ==="
    )

    print(
        "rows:",
        len(final),
    )

    print()
    print(
        "JUDGMENTS"
    )

    print(
        final[
            "llm_first_pass_judgment"
        ]
        .value_counts()
        .to_string()
    )

    print()
    print(
        "CONFIDENCE"
    )

    print(
        final[
            "llm_first_pass_confidence"
        ]
        .value_counts()
        .to_string()
    )

    print()
    print(
        "input tokens:",
        input_token_total,
    )

    print(
        "output tokens:",
        output_token_total,
    )

    print()
    print(
        "output:",
        OUT_DIR,
    )


if __name__ == "__main__":
    main()
