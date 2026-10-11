#!/usr/bin/env python3

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import hashlib
import json
import os
import time

import pandas as pd
from openai import OpenAI


ROOT = Path(__file__).resolve().parents[1]

SOURCE_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_diagnostic_v1"
)

SUMMARY = (
    SOURCE_DIR
    / "openlibrary_r2a1_target_identity_current_api_summary_v1.tsv"
)

EDITIONS = (
    SOURCE_DIR
    / "openlibrary_r2a1_target_identity_current_api_editions_v1.tsv"
)

SOURCE_MANIFEST = (
    SOURCE_DIR
    / "openlibrary_r2a1_target_identity_diagnostic_v1_manifest.json"
)

PROMPT = (
    ROOT
    / "docs"
    / "OPENLIBRARY_R2A1_TARGET_IDENTITY_LLM_PROMPT_V1.md"
)

OUT_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_llm_v1"
)

PARTIAL = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_llm_v1.partial.tsv"
)

OUT_TSV = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_llm_v1.tsv"
)

OUT_SUMMARY = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_llm_v1_summary.json"
)

OUT_AUDIT = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_llm_v1_audit.json"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_llm_v1_manifest.json"
)

RUN_CONFIG = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_llm_v1_run_config.json"
)


RELEASE = "openlibrary-r2a1-target-identity-llm-v1"
PROMPT_VERSION = "openlibrary-r2a1-target-identity-llm-prompt-v1"
CREATED_AT = "2026-10-11"

MODEL = "gpt-6.1-sol"

EXPECTED_WORKS = 48
EXPECTED_EDITION_ROWS = 650

MAX_WORKERS = int(
    os.environ.get(
        "OPENAI_MAX_WORKERS",
        "6",
    )
)

MAX_ATTEMPTS = 5

ORDER_SALT = (
    "openlibrary-r2a1-target-"
    "identity-llm-v1"
)


ENTITY_STATUS = {
    "COHERENT_SINGLE_WORK",
    "COHERENT_COLLECTION",
    "HETEROGENEOUS_CLUSTER",
    "NONWORK_OR_HEADING_ARTIFACT",
    "UNCERTAIN",
}

CONTENT_TYPE = {
    "SPECIFIC_FICTION_WORK",
    "FICTION_COLLECTION_OR_ANTHOLOGY",
    "BROAD_AUTHOR_OEUVRE_OR_MIXED_COLLECTION",
    "NONFICTION_OR_OTHER_LITERARY_FORM",
    "MIXED_OR_UNCLEAR",
}

DATE_STATUS = {
    "LIKELY_ORIGINAL_1880_1950",
    "LIKELY_ORIGINAL_OUTSIDE_1880_1950",
    "INSUFFICIENT_DATE_EVIDENCE",
}

CONFIDENCE = {
    "HIGH",
    "MEDIUM",
    "LOW",
}


OUTPUT_FIELDS = [
    "project_work_id",
    "current_ol_work_id",
    "r2_target_title",
    "r2_target_author",
    "frozen_first_publish_year",
    "current_work_title",

    "llm_entity_status",
    "llm_content_type",
    "llm_date_window_assessment",
    "llm_confidence",
    "llm_note",

    "llm_model_requested",
    "llm_model_returned",
    "llm_response_id",
    "llm_input_tokens",
    "llm_output_tokens",
    "llm_prompt_version",
]


SCHEMA = {
    "type": "object",
    "properties": {
        "current_ol_work_id": {
            "type": "string",
        },
        "llm_entity_status": {
            "type": "string",
            "enum": sorted(ENTITY_STATUS),
        },
        "llm_content_type": {
            "type": "string",
            "enum": sorted(CONTENT_TYPE),
        },
        "llm_date_window_assessment": {
            "type": "string",
            "enum": sorted(DATE_STATUS),
        },
        "llm_confidence": {
            "type": "string",
            "enum": sorted(CONFIDENCE),
        },
        "llm_note": {
            "type": "string",
        },
    },
    "required": [
        "current_ol_work_id",
        "llm_entity_status",
        "llm_content_type",
        "llm_date_window_assessment",
        "llm_confidence",
        "llm_note",
    ],
    "additionalProperties": False,
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def atomic_tsv(df, path):
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


def atomic_json(obj, path):
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


def stable_key(ol_work_id):
    return hashlib.sha256(
        (
            ORDER_SALT
            + "\0"
            + str(ol_work_id)
        ).encode("utf-8")
    ).hexdigest()


def clean(v):
    if pd.isna(v):
        return ""

    return str(v).strip()


def edition_evidence(
    editions: pd.DataFrame,
) -> str:

    if len(editions) == 0:
        return "[No edition rows available]"

    rows = []

    for i, r in enumerate(
        editions.itertuples(
            index=False
        ),
        start=1,
    ):
        rows.append(
            "\n".join(
                [
                    f"Edition {i}:",
                    f"  title: {clean(r.edition_title)}",
                    f"  subtitle: {clean(r.edition_subtitle)}",
                    f"  publish_date: {clean(r.publish_date)}",
                    f"  publishers: {clean(r.publishers)}",
                ]
            )
        )

    return "\n\n".join(rows)


def make_input(
    prompt_text,
    row,
    work_editions,
):
    return f"""
{prompt_text}

RECORD TO ADJUDICATE

Open Library Work ID:
{row["current_ol_work_id"]}

FROZEN TARGET CONTEXT

Target title:
{row["r2_target_title"]}

Target author:
{row["r2_target_author"]}

Frozen Open Library title:
{row["title"]}

Frozen first_publish_year:
{row["first_publish_year"]}

CURRENT OPEN LIBRARY WORK METADATA

Current Work title:
{row["current_work_title"]}

Current Work first_publish_date:
{row["current_work_first_publish_date"]}

Description:
{row["current_work_description"] or "[No description available]"}

Subjects:
{row["current_work_subjects"] or "[No subjects available]"}

Reported edition count:
{row["edition_total_reported"]}

Fetched edition rows:
{row["edition_rows_fetched"]}

EDITION EVIDENCE

{edition_evidence(work_editions)}
""".strip()


def validate_result(
    oid,
    obj,
):
    if obj.get(
        "current_ol_work_id"
    ) != oid:
        raise ValueError(
            "OL Work ID echo mismatch: "
            f"{oid} != "
            f"{obj.get('current_ol_work_id')}"
        )

    if (
        obj.get("llm_entity_status")
        not in ENTITY_STATUS
    ):
        raise ValueError(
            "Invalid entity status"
        )

    if (
        obj.get("llm_content_type")
        not in CONTENT_TYPE
    ):
        raise ValueError(
            "Invalid content type"
        )

    if (
        obj.get(
            "llm_date_window_assessment"
        )
        not in DATE_STATUS
    ):
        raise ValueError(
            "Invalid date assessment"
        )

    if (
        obj.get("llm_confidence")
        not in CONFIDENCE
    ):
        raise ValueError(
            "Invalid confidence"
        )

    if not str(
        obj.get(
            "llm_note",
            "",
        )
    ).strip():
        raise ValueError(
            "Blank LLM note"
        )


def call_one(
    client,
    prompt_text,
    row,
    work_editions,
):
    oid = row[
        "current_ol_work_id"
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
                        work_editions,
                    ),
                    text={
                        "format": {
                            "type":
                                "json_schema",
                            "name":
                                "openlibrary_"
                                "target_identity_v1",
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
                oid,
                obj,
            )

            usage = getattr(
                response,
                "usage",
                None,
            )

            in_tok = ""
            out_tok = ""

            if usage is not None:
                in_tok = str(
                    getattr(
                        usage,
                        "input_tokens",
                        "",
                    )
                    or ""
                )

                out_tok = str(
                    getattr(
                        usage,
                        "output_tokens",
                        "",
                    )
                    or ""
                )

            return {
                "project_work_id":
                    row["project_work_id"],

                "current_ol_work_id":
                    oid,

                "r2_target_title":
                    row["r2_target_title"],

                "r2_target_author":
                    row["r2_target_author"],

                "frozen_first_publish_year":
                    row["first_publish_year"],

                "current_work_title":
                    row["current_work_title"],

                "llm_entity_status":
                    obj["llm_entity_status"],

                "llm_content_type":
                    obj["llm_content_type"],

                "llm_date_window_assessment":
                    obj[
                        "llm_date_window_assessment"
                    ],

                "llm_confidence":
                    obj["llm_confidence"],

                "llm_note":
                    obj["llm_note"].strip(),

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
                    in_tok,

                "llm_output_tokens":
                    out_tok,

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
        f"{oid}: "
        f"{type(last_error).__name__}: "
        f"{last_error}"
    )


def checkpoint(rows):
    df = pd.DataFrame(
        rows,
        columns=OUTPUT_FIELDS,
    )

    df = (
        df.sort_values(
            "current_ol_work_id",
            kind="stable",
        )
        .reset_index(drop=True)
    )

    assert df[
        "current_ol_work_id"
    ].is_unique

    atomic_tsv(
        df,
        PARTIAL,
    )


def main():
    for p in [
        SUMMARY,
        EDITIONS,
        SOURCE_MANIFEST,
        PROMPT,
    ]:
        if not p.exists():
            raise FileNotFoundError(p)

    if OUT_TSV.exists():
        raise RuntimeError(
            f"Final output already exists: "
            f"{OUT_TSV}"
        )

    src = pd.read_csv(
        SUMMARY,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    editions = pd.read_csv(
        EDITIONS,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    assert len(src) == EXPECTED_WORKS
    assert len(editions) == EXPECTED_EDITION_ROWS

    assert src[
        "current_ol_work_id"
    ].is_unique

    assert src[
        "api_status"
    ].eq("OK").all()

    # Risk/impact fields exist in the frozen diagnostic
    # source but are deliberately NOT passed to the LLM.
    forbidden_for_llm = {
        "pair_count",
        "pairset_sha256",
        "diagnostic_type",
        "exact_pairset_duplicate_group",
        "has_exact_pairset_duplicate",
    }

    prompt_text = PROMPT.read_text(
        encoding="utf-8"
    ).strip()

    source_manifest = json.loads(
        SOURCE_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    assert (
        source_manifest["release"]
        == "openlibrary-r2a1-target-identity-diagnostic-v1"
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

        "source_summary_sha256":
            sha256_file(SUMMARY),

        "source_editions_sha256":
            sha256_file(EDITIONS),

        "source_manifest_sha256":
            sha256_file(SOURCE_MANIFEST),

        "prompt_sha256":
            sha256_file(PROMPT),

        "expected_openlibrary_works":
            EXPECTED_WORKS,

        "expected_edition_rows":
            EXPECTED_EDITION_ROWS,

        "risk_fields_withheld_from_llm":
            sorted(
                forbidden_for_llm
            ),

        "max_workers":
            MAX_WORKERS,
    }

    if RUN_CONFIG.exists():
        old = json.loads(
            RUN_CONFIG.read_text(
                encoding="utf-8"
            )
        )

        old_cmp = dict(old)
        new_cmp = dict(config)

        old_cmp.pop(
            "max_workers",
            None,
        )
        new_cmp.pop(
            "max_workers",
            None,
        )

        assert old_cmp == new_cmp

    else:
        atomic_json(
            config,
            RUN_CONFIG,
        )

    source_ids = set(
        src["current_ol_work_id"]
    )

    completed = []

    if PARTIAL.exists():
        partial = pd.read_csv(
            PARTIAL,
            sep="\t",
            dtype=str,
            keep_default_na=False,
        )

        assert set(
            partial.columns
        ) == set(
            OUTPUT_FIELDS
        )

        partial = partial[
            OUTPUT_FIELDS
        ]

        assert partial[
            "current_ol_work_id"
        ].is_unique

        assert set(
            partial[
                "current_ol_work_id"
            ]
        ) <= source_ids

        completed = (
            partial.to_dict(
                orient="records"
            )
        )

    done = {
        r["current_ol_work_id"]
        for r in completed
    }

    remaining = src.loc[
        ~src[
            "current_ol_work_id"
        ].isin(done)
    ].copy()

    remaining["_order"] = (
        remaining[
            "current_ol_work_id"
        ].map(stable_key)
    )

    remaining = (
        remaining.sort_values(
            [
                "_order",
                "current_ol_work_id",
            ],
            kind="stable",
        )
        .drop(
            columns="_order"
        )
    )

    print(
        "=== OL TARGET IDENTITY "
        "LLM V1 ==="
    )
    print("model:", MODEL)
    print("source works:", len(src))
    print("edition rows:", len(editions))
    print("already completed:", len(done))
    print("remaining:", len(remaining))
    print(
        "risk/impact fields withheld:",
        sorted(
            forbidden_for_llm
        ),
    )

    client = OpenAI()

    failures = []

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = {}

        for row in remaining.to_dict(
            orient="records"
        ):
            oid = row[
                "current_ol_work_id"
            ]

            ed = editions.loc[
                editions[
                    "current_ol_work_id"
                ].eq(oid)
            ].copy()

            future = executor.submit(
                call_one,
                client,
                prompt_text,
                row,
                ed,
            )

            futures[future] = oid

        for i, future in enumerate(
            as_completed(futures),
            start=1,
        ):
            oid = futures[future]

            try:
                completed.append(
                    future.result()
                )

                checkpoint(
                    completed
                )

            except Exception as exc:
                failures.append(
                    (
                        oid,
                        str(exc),
                    )
                )

            if (
                i % 10 == 0
                or i == len(futures)
            ):
                print(
                    "completed this run:",
                    i,
                    "/",
                    len(futures),
                    "| total saved:",
                    len(completed),
                    "| failures:",
                    len(failures),
                    flush=True,
                )

    if failures:
        print(
            "\nFAILED:"
        )

        for oid, message in failures:
            print(
                oid,
                message,
                sep="\t",
            )

        raise RuntimeError(
            "Some candidates failed; "
            "partial results saved."
        )

    final = pd.DataFrame(
        completed,
        columns=OUTPUT_FIELDS,
    )

    final = (
        final.sort_values(
            "current_ol_work_id",
            kind="stable",
        )
        .reset_index(drop=True)
    )

    assert len(final) == EXPECTED_WORKS
    assert final[
        "current_ol_work_id"
    ].is_unique
    assert set(
        final[
            "current_ol_work_id"
        ]
    ) == source_ids

    for r in final.itertuples(
        index=False
    ):
        validate_result(
            r.current_ol_work_id,
            {
                "current_ol_work_id":
                    r.current_ol_work_id,
                "llm_entity_status":
                    r.llm_entity_status,
                "llm_content_type":
                    r.llm_content_type,
                "llm_date_window_assessment":
                    r.llm_date_window_assessment,
                "llm_confidence":
                    r.llm_confidence,
                "llm_note":
                    r.llm_note,
            },
        )

    atomic_tsv(
        final,
        OUT_TSV,
    )

    if PARTIAL.exists():
        PARTIAL.unlink()

    summary = {
        "release":
            RELEASE,

        "status":
            "provisional_llm_identity_scope_adjudication",

        "created_at":
            CREATED_AT,

        "model_requested":
            MODEL,

        "rows":
            len(final),

        "project_works":
            int(
                final[
                    "project_work_id"
                ].nunique()
            ),

        "entity_status_counts":
            {
                str(k): int(v)
                for k, v
                in final[
                    "llm_entity_status"
                ]
                .value_counts()
                .sort_index()
                .items()
            },

        "content_type_counts":
            {
                str(k): int(v)
                for k, v
                in final[
                    "llm_content_type"
                ]
                .value_counts()
                .sort_index()
                .items()
            },

        "date_window_counts":
            {
                str(k): int(v)
                for k, v
                in final[
                    "llm_date_window_assessment"
                ]
                .value_counts()
                .sort_index()
                .items()
            },

        "confidence_counts":
            {
                str(k): int(v)
                for k, v
                in final[
                    "llm_confidence"
                ]
                .value_counts()
                .sort_index()
                .items()
            },

        "usage": {
            "input_tokens":
                int(
                    pd.to_numeric(
                        final[
                            "llm_input_tokens"
                        ],
                        errors="coerce",
                    )
                    .fillna(0)
                    .sum()
                ),

            "output_tokens":
                int(
                    pd.to_numeric(
                        final[
                            "llm_output_tokens"
                        ],
                        errors="coerce",
                    )
                    .fillna(0)
                    .sum()
                ),
        },

        "interpretation": [
            (
                "These are provisional LLM judgments "
                "over a selected high-impact identity/scope "
                "risk set, not a population-wide estimate."
            ),
            (
                "Risk and OpenAlex impact fields were "
                "withheld from the LLM."
            ),
            (
                "Identity coherence, corpus content type, "
                "and original-date assessment are separate "
                "judgment axes."
            ),
            (
                "No production inclusion/exclusion policy "
                "is established by this release."
            ),
        ],
    }

    atomic_json(
        summary,
        OUT_SUMMARY,
    )

    audit = {
        "release":
            RELEASE,

        "audit_status":
            "PASSED",

        "checks": {
            "rows":
                len(final),

            "expected_rows":
                EXPECTED_WORKS,

            "unique_openlibrary_work_ids":
                int(
                    final[
                        "current_ol_work_id"
                    ].nunique()
                ),

            "source_membership_exact":
                (
                    set(
                        final[
                            "current_ol_work_id"
                        ]
                    )
                    == source_ids
                ),

            "risk_fields_not_in_output":
                not bool(
                    forbidden_for_llm
                    & set(
                        final.columns
                    )
                ),

            "all_notes_nonblank":
                bool(
                    final[
                        "llm_note"
                    ]
                    .astype(str)
                    .str.strip()
                    .ne("")
                    .all()
                ),
        },
    }

    atomic_json(
        audit,
        OUT_AUDIT,
    )

    manifest = {
        "release":
            RELEASE,

        "created_at":
            CREATED_AT,

        "inputs": {
            str(
                SUMMARY.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    SUMMARY
                ),

            str(
                EDITIONS.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    EDITIONS
                ),

            str(
                SOURCE_MANIFEST.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    SOURCE_MANIFEST
                ),

            str(
                PROMPT.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    PROMPT
                ),
        },

        "outputs": {
            str(
                OUT_TSV.relative_to(
                    ROOT
                )
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

            str(
                OUT_AUDIT.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    OUT_AUDIT
                ),

            str(
                RUN_CONFIG.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    RUN_CONFIG
                ),
        },
    }

    atomic_json(
        manifest,
        OUT_MANIFEST,
    )

    print()
    print(
        "=== FINAL SUMMARY ==="
    )
    print(
        "entity status:"
    )
    print(
        final[
            "llm_entity_status"
        ]
        .value_counts()
        .to_string()
    )

    print(
        "\ncontent type:"
    )
    print(
        final[
            "llm_content_type"
        ]
        .value_counts()
        .to_string()
    )

    print(
        "\ndate window:"
    )
    print(
        final[
            "llm_date_window_assessment"
        ]
        .value_counts()
        .to_string()
    )

    print(
        "\nconfidence:"
    )
    print(
        final[
            "llm_confidence"
        ]
        .value_counts()
        .to_string()
    )

    print(
        "\ninput tokens:",
        summary[
            "usage"
        ][
            "input_tokens"
        ],
    )

    print(
        "output tokens:",
        summary[
            "usage"
        ][
            "output_tokens"
        ],
    )

    print(
        "QC STATUS: PASSED"
    )


if __name__ == "__main__":
    main()
