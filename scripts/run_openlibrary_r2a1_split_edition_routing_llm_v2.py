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
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_routing_input_v2"
)

ROUTING_INPUT = (
    INPUT_DIR
    / "openlibrary_r2a1_split_edition_routing_input_v2.tsv"
)

PROJECT_INPUT = (
    INPUT_DIR
    / "openlibrary_r2a1_split_edition_routing_projects_v2.tsv"
)

INPUT_AUDIT = (
    INPUT_DIR
    / "openlibrary_r2a1_split_edition_routing_input_v2_audit.json"
)

COMPONENT_DIR = INPUT_DIR

COMPONENTS = (
    COMPONENT_DIR
    / "openlibrary_r2a1_split_edition_routing_components_v2.tsv"
)

COMPONENT_MANIFEST = (
    COMPONENT_DIR
    / "openlibrary_r2a1_split_edition_routing_input_v2_manifest.json"
)

PROMPT = (
    ROOT
    / "docs"
    / "OPENLIBRARY_R2A1_SPLIT_EDITION_ROUTING_LLM_PROMPT_V2.md"
)

OUT_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_routing_llm_v2"
)

PARTIAL_ROUTING = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_llm_v2.partial.tsv"
)

PARTIAL_RESPONSES = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_llm_v2_responses.partial.tsv"
)

OUT_TSV = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_llm_v2.tsv"
)

OUT_RESPONSES = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_llm_v2_responses.tsv"
)

OUT_SUMMARY = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_llm_v2_summary.json"
)

OUT_AUDIT = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_llm_v2_audit.json"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_llm_v2_manifest.json"
)

RUN_CONFIG = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_llm_v2_run_config.json"
)


RELEASE = (
    "openlibrary-r2a1-split-edition-routing-llm-v2"
)

PROMPT_VERSION = (
    "openlibrary-r2a1-split-edition-routing-llm-prompt-v2"
)

CREATED_AT = "2026-10-11"

INPUT_FREEZE_COMMIT = (
    "107b65881276075b2e8f5ef4467d547f9ac07265"
)

REGISTRY_V2_FREEZE_COMMIT = (
    "bbb190bd6f47eda96981a4434da00935bf2a818f"
)

MODEL = "gpt-6.1-sol"

EXPECTED_PROJECTS = 6
EXPECTED_EDITIONS = 191
EXPECTED_COMPONENTS = 39

MAX_WORKERS = int(
    os.environ.get(
        "OPENAI_MAX_WORKERS",
        "4",
    )
)

MAX_ATTEMPTS = 5

ORDER_SALT = (
    "openlibrary-r2a1-split-edition-routing-llm-v2"
)

ROUTING_DECISIONS = {
    "ASSIGN_COMPONENT",
    "HOLD_UNRESOLVED",
}

CONFIDENCE = {
    "HIGH",
    "MEDIUM",
    "LOW",
}


ROUTING_FIELDS = [
    "remediation_priority_rank",
    "project_work_id",
    "current_ol_work_id",

    "edition_key",
    "edition_title",
    "edition_subtitle",
    "publish_date",
    "publishers",
    "edition_author_keys",
    "number_of_pages",

    "routing_decision",
    "component_id",
    "component_label",
    "human_role_hint",

    "llm_confidence",
    "llm_note",

    "llm_model_requested",
    "llm_model_returned",
    "llm_response_id",
    "llm_prompt_version",
]


RESPONSE_FIELDS = [
    "remediation_priority_rank",
    "project_work_id",
    "current_ol_work_id",
    "edition_rows",
    "component_count",

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
    project_work_id: str,
) -> str:

    return hashlib.sha256(
        (
            ORDER_SALT
            + "\0"
            + project_work_id
        ).encode("utf-8")
    ).hexdigest()


def clean(v) -> str:
    if pd.isna(v):
        return ""

    return str(v).strip()


def make_schema(
    project_work_id: str,
    edition_keys: list[str],
    component_ids: list[str],
) -> dict:

    return {
        "type": "object",

        "properties": {
            "project_work_id": {
                "type": "string",
                "enum": [
                    project_work_id
                ],
            },

            "routes": {
                "type": "array",

                "minItems":
                    len(edition_keys),

                "maxItems":
                    len(edition_keys),

                "items": {
                    "type": "object",

                    "properties": {
                        "edition_key": {
                            "type": "string",
                            "enum":
                                sorted(
                                    edition_keys
                                ),
                        },

                        "routing_decision": {
                            "type": "string",
                            "enum":
                                sorted(
                                    ROUTING_DECISIONS
                                ),
                        },

                        "component_id": {
                            "type": "string",
                            "enum":
                                [
                                    ""
                                ]
                                + sorted(
                                    component_ids
                                ),
                        },

                        "llm_confidence": {
                            "type": "string",
                            "enum":
                                sorted(
                                    CONFIDENCE
                                ),
                        },

                        "llm_note": {
                            "type": "string",
                        },
                    },

                    "required": [
                        "edition_key",
                        "routing_decision",
                        "component_id",
                        "llm_confidence",
                        "llm_note",
                    ],

                    "additionalProperties":
                        False,
                },
            },
        },

        "required": [
            "project_work_id",
            "routes",
        ],

        "additionalProperties":
            False,
    }


def component_payload(
    components: pd.DataFrame,
) -> list[dict]:

    rows = []

    for r in components.itertuples(
        index=False
    ):
        rows.append({
            "component_id":
                clean(
                    r.component_id
                ),

            "component_label":
                clean(
                    r.component_label
                ),

            "human_role_hint":
                clean(
                    r.human_role_hint
                ),

            "component_definition":
                clean(
                    r.component_definition
                ),
        })

    return rows


def edition_payload(
    editions: pd.DataFrame,
) -> list[dict]:

    fields = [
        "edition_key",
        "edition_title",
        "edition_subtitle",
        "publish_date",
        "publishers",
        "edition_author_keys",
        "number_of_pages",
    ]

    rows = []

    for r in editions[
        fields
    ].to_dict(
        orient="records"
    ):
        rows.append(
            {
                k: clean(v)
                for k, v
                in r.items()
            }
        )

    return rows


def make_input(
    prompt_text: str,
    project_row: dict,
    components: pd.DataFrame,
    editions: pd.DataFrame,
) -> str:

    project_context = {
        "project_work_id":
            project_row[
                "project_work_id"
            ],

        "current_ol_work_id":
            project_row[
                "current_ol_work_id"
            ],

        "r2_target_title":
            project_row[
                "r2_target_title"
            ],

        "r2_target_author":
            project_row[
                "r2_target_author"
            ],

        "human_resolution_plan":
            project_row[
                "resolution_plan"
            ],

        "human_resolution_note":
            project_row[
                "resolution_note"
            ],
    }

    return (
        prompt_text
        + "\n\n"
        + "PROJECT CONTEXT\n\n"
        + json.dumps(
            project_context,
            ensure_ascii=False,
            indent=2,
        )
        + "\n\n"
        + "FIXED COMPONENT REGISTRY\n\n"
        + json.dumps(
            component_payload(
                components
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n\n"
        + "EDITION RECORDS TO ROUTE\n\n"
        + json.dumps(
            edition_payload(
                editions
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


def validate_response(
    project_work_id: str,
    editions: pd.DataFrame,
    components: pd.DataFrame,
    obj: dict,
) -> list[dict]:

    if (
        obj.get(
            "project_work_id"
        )
        != project_work_id
    ):
        raise ValueError(
            "project_work_id echo mismatch"
        )

    routes = obj.get(
        "routes"
    )

    if not isinstance(
        routes,
        list,
    ):
        raise ValueError(
            "routes is not a list"
        )

    expected_keys = set(
        editions[
            "edition_key"
        ]
    )

    observed_keys = [
        clean(
            r.get(
                "edition_key"
            )
        )
        for r in routes
    ]

    if len(
        observed_keys
    ) != len(
        expected_keys
    ):
        raise ValueError(
            "route row count mismatch"
        )

    if len(
        set(
            observed_keys
        )
    ) != len(
        observed_keys
    ):
        raise ValueError(
            "duplicate edition_key in response"
        )

    if set(
        observed_keys
    ) != expected_keys:
        raise ValueError(
            "edition_key set mismatch"
        )

    valid_components = set(
        components[
            "component_id"
        ]
    )

    normalized = []

    for r in routes:

        edition_key = clean(
            r.get(
                "edition_key"
            )
        )

        decision = clean(
            r.get(
                "routing_decision"
            )
        )

        component_id = clean(
            r.get(
                "component_id"
            )
        )

        confidence = clean(
            r.get(
                "llm_confidence"
            )
        )

        note = clean(
            r.get(
                "llm_note"
            )
        )

        if (
            decision
            not in ROUTING_DECISIONS
        ):
            raise ValueError(
                "invalid routing_decision: "
                f"{decision}"
            )

        if (
            confidence
            not in CONFIDENCE
        ):
            raise ValueError(
                "invalid llm_confidence"
            )

        if not note:
            raise ValueError(
                "blank llm_note"
            )

        if (
            decision
            == "ASSIGN_COMPONENT"
        ):
            if (
                component_id
                not in valid_components
            ):
                raise ValueError(
                    "assigned component not "
                    "valid for project: "
                    f"{component_id}"
                )

        elif (
            decision
            == "HOLD_UNRESOLVED"
        ):
            if component_id:
                raise ValueError(
                    "HOLD_UNRESOLVED must "
                    "have blank component_id"
                )

        normalized.append({
            "edition_key":
                edition_key,

            "routing_decision":
                decision,

            "component_id":
                component_id,

            "llm_confidence":
                confidence,

            "llm_note":
                note,
        })

    return normalized


def call_one(
    client: OpenAI,
    prompt_text: str,
    project_row: dict,
    components: pd.DataFrame,
    editions: pd.DataFrame,
):

    project_work_id = project_row[
        "project_work_id"
    ]

    edition_keys = (
        editions[
            "edition_key"
        ]
        .tolist()
    )

    component_ids = (
        components[
            "component_id"
        ]
        .tolist()
    )

    schema = make_schema(
        project_work_id,
        edition_keys,
        component_ids,
    )

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
                        project_row,
                        components,
                        editions,
                    ),

                    text={
                        "format": {
                            "type":
                                "json_schema",

                            "name":
                                "openlibrary_"
                                "split_edition_"
                                "routing_v2",

                            "strict":
                                True,

                            "schema":
                                schema,
                        }
                    },
                )
            )

            obj = json.loads(
                response.output_text
            )

            routes = (
                validate_response(
                    project_work_id,
                    editions,
                    components,
                    obj,
                )
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

            model_returned = str(
                getattr(
                    response,
                    "model",
                    "",
                )
                or ""
            )

            response_id = str(
                getattr(
                    response,
                    "id",
                    "",
                )
                or ""
            )

            component_meta = (
                components
                .set_index(
                    "component_id"
                )
                [
                    [
                        "component_label",
                        "human_role_hint",
                    ]
                ]
                .to_dict(
                    orient="index"
                )
            )

            edition_meta = (
                editions
                .set_index(
                    "edition_key"
                )
                .to_dict(
                    orient="index"
                )
            )

            routing_rows = []

            for route in routes:

                edition_key = route[
                    "edition_key"
                ]

                em = edition_meta[
                    edition_key
                ]

                component_id = route[
                    "component_id"
                ]

                cm = (
                    component_meta.get(
                        component_id,
                        {},
                    )
                )

                routing_rows.append({
                    "remediation_priority_rank":
                        project_row[
                            "remediation_priority_rank"
                        ],

                    "project_work_id":
                        project_work_id,

                    "current_ol_work_id":
                        project_row[
                            "current_ol_work_id"
                        ],

                    "edition_key":
                        edition_key,

                    "edition_title":
                        clean(
                            em.get(
                                "edition_title"
                            )
                        ),

                    "edition_subtitle":
                        clean(
                            em.get(
                                "edition_subtitle"
                            )
                        ),

                    "publish_date":
                        clean(
                            em.get(
                                "publish_date"
                            )
                        ),

                    "publishers":
                        clean(
                            em.get(
                                "publishers"
                            )
                        ),

                    "edition_author_keys":
                        clean(
                            em.get(
                                "edition_author_keys"
                            )
                        ),

                    "number_of_pages":
                        clean(
                            em.get(
                                "number_of_pages"
                            )
                        ),

                    "routing_decision":
                        route[
                            "routing_decision"
                        ],

                    "component_id":
                        component_id,

                    "component_label":
                        clean(
                            cm.get(
                                "component_label"
                            )
                        ),

                    "human_role_hint":
                        clean(
                            cm.get(
                                "human_role_hint"
                            )
                        ),

                    "llm_confidence":
                        route[
                            "llm_confidence"
                        ],

                    "llm_note":
                        route[
                            "llm_note"
                        ],

                    "llm_model_requested":
                        MODEL,

                    "llm_model_returned":
                        model_returned,

                    "llm_response_id":
                        response_id,

                    "llm_prompt_version":
                        PROMPT_VERSION,
                })

            response_row = {
                "remediation_priority_rank":
                    project_row[
                        "remediation_priority_rank"
                    ],

                "project_work_id":
                    project_work_id,

                "current_ol_work_id":
                    project_row[
                        "current_ol_work_id"
                    ],

                "edition_rows":
                    str(
                        len(
                            editions
                        )
                    ),

                "component_count":
                    str(
                        len(
                            components
                        )
                    ),

                "llm_model_requested":
                    MODEL,

                "llm_model_returned":
                    model_returned,

                "llm_response_id":
                    response_id,

                "llm_input_tokens":
                    input_tokens,

                "llm_output_tokens":
                    output_tokens,

                "llm_prompt_version":
                    PROMPT_VERSION,
            }

            return (
                routing_rows,
                response_row,
            )

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
        f"{project_work_id}: "
        f"{type(last_error).__name__}: "
        f"{last_error}"
    )


def checkpoint(
    routing_rows,
    response_rows,
):

    if routing_rows:

        routing = pd.DataFrame(
            routing_rows,
            columns=ROUTING_FIELDS,
        )

        routing[
            "remediation_priority_rank"
        ] = pd.to_numeric(
            routing[
                "remediation_priority_rank"
            ]
        )

        routing = routing.sort_values(
            [
                "remediation_priority_rank",
                "project_work_id",
                "edition_key",
            ],
            kind="stable",
        ).reset_index(
            drop=True
        )

        atomic_tsv(
            routing,
            PARTIAL_ROUTING,
        )

    if response_rows:

        responses = pd.DataFrame(
            response_rows,
            columns=RESPONSE_FIELDS,
        )

        responses[
            "remediation_priority_rank"
        ] = pd.to_numeric(
            responses[
                "remediation_priority_rank"
            ]
        )

        responses = responses.sort_values(
            [
                "remediation_priority_rank",
                "project_work_id",
            ],
            kind="stable",
        ).reset_index(
            drop=True
        )

        atomic_tsv(
            responses,
            PARTIAL_RESPONSES,
        )


def main():

    required = [
        ROUTING_INPUT,
        PROJECT_INPUT,
        INPUT_AUDIT,
        COMPONENTS,
        COMPONENT_MANIFEST,
        PROMPT,
    ]

    for p in required:
        if not p.exists():
            raise FileNotFoundError(p)

    if (
        OUT_TSV.exists()
        or OUT_RESPONSES.exists()
    ):
        raise RuntimeError(
            "Final output already exists"
        )

    routing_input = pd.read_csv(
        ROUTING_INPUT,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    projects = pd.read_csv(
        PROJECT_INPUT,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    components = pd.read_csv(
        COMPONENTS,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    assert len(
        routing_input
    ) == EXPECTED_EDITIONS

    assert routing_input[
        "edition_key"
    ].is_unique

    assert len(
        projects
    ) == EXPECTED_PROJECTS

    assert projects[
        "project_work_id"
    ].is_unique

    assert len(
        components
    ) == EXPECTED_COMPONENTS

    assert components[
        "component_id"
    ].is_unique

    assert (
        routing_input[
            "project_work_id"
        ].nunique()
        == EXPECTED_PROJECTS
    )

    assert (
        components[
            "project_work_id"
        ].nunique()
        == EXPECTED_PROJECTS
    )

    project_ids = set(
        projects[
            "project_work_id"
        ]
    )

    assert set(
        routing_input[
            "project_work_id"
        ]
    ) == project_ids

    assert set(
        components[
            "project_work_id"
        ]
    ) == project_ids

    input_audit = json.loads(
        INPUT_AUDIT.read_text(
            encoding="utf-8"
        )
    )

    assert (
        input_audit[
            "status"
        ]
        == "PASSED"
    )

    component_manifest = json.loads(
        COMPONENT_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    assert (
        component_manifest[
            "release"
        ]
        == "openlibrary-r2a1-split-edition-routing-input-v2"
    )

    assert (
        component_manifest[
            "status"
        ]
        == "llm_rerouting_input"
    )

    assert (
        component_manifest[
            "registry_v2_freeze_commit"
        ]
        == REGISTRY_V2_FREEZE_COMMIT
    )

    prompt_text = PROMPT.read_text(
        encoding="utf-8"
    ).strip()

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_config = {
        "release":
            RELEASE,

        "created_at":
            CREATED_AT,

        "input_freeze_commit":
            INPUT_FREEZE_COMMIT,

        "registry_v2_freeze_commit":
            REGISTRY_V2_FREEZE_COMMIT,

        "model_requested":
            MODEL,

        "max_workers":
            MAX_WORKERS,

        "max_attempts":
            MAX_ATTEMPTS,

        "call_unit":
            "one API call per predecessor project work",

        "expected_project_works":
            EXPECTED_PROJECTS,

        "expected_edition_rows":
            EXPECTED_EDITIONS,

        "expected_components":
            EXPECTED_COMPONENTS,

        "prompt_version":
            PROMPT_VERSION,

        "prompt_sha256":
            sha256_file(
                PROMPT
            ),

        "runner_sha256":
            sha256_file(
                Path(__file__)
            ),

        "routing_input_sha256":
            sha256_file(
                ROUTING_INPUT
            ),

        "project_input_sha256":
            sha256_file(
                PROJECT_INPUT
            ),

        "component_registry_sha256":
            sha256_file(
                COMPONENTS
            ),
    }

    atomic_json(
        run_config,
        RUN_CONFIG,
    )

    completed_routing = []
    completed_responses = []

    if PARTIAL_ROUTING.exists():

        partial = pd.read_csv(
            PARTIAL_ROUTING,
            sep="\t",
            dtype=str,
            keep_default_na=False,
        )

        assert list(
            partial.columns
        ) == ROUTING_FIELDS

        completed_routing = (
            partial.to_dict(
                orient="records"
            )
        )

    if PARTIAL_RESPONSES.exists():

        partial_resp = pd.read_csv(
            PARTIAL_RESPONSES,
            sep="\t",
            dtype=str,
            keep_default_na=False,
        )

        assert list(
            partial_resp.columns
        ) == RESPONSE_FIELDS

        assert partial_resp[
            "project_work_id"
        ].is_unique

        completed_responses = (
            partial_resp.to_dict(
                orient="records"
            )
        )

    done_projects = {
        r[
            "project_work_id"
        ]
        for r
        in completed_responses
    }

    if completed_routing:

        routing_done_projects = {
            r[
                "project_work_id"
            ]
            for r
            in completed_routing
        }

        assert (
            routing_done_projects
            == done_projects
        )

        for pid in done_projects:

            expected_n = int(
                projects.loc[
                    projects[
                        "project_work_id"
                    ].eq(pid),
                    "edition_rows",
                ].iloc[0]
            )

            observed_n = sum(
                1
                for r
                in completed_routing
                if r[
                    "project_work_id"
                ] == pid
            )

            assert (
                observed_n
                == expected_n
            )

    remaining = projects.loc[
        ~projects[
            "project_work_id"
        ].isin(
            done_projects
        )
    ].copy()

    remaining["_order"] = (
        remaining[
            "project_work_id"
        ].map(
            stable_key
        )
    )

    remaining = (
        remaining.sort_values(
            [
                "_order",
                "project_work_id",
            ],
            kind="stable",
        )
        .drop(
            columns="_order"
        )
    )

    print(
        "=== OL SPLIT EDITION ROUTING LLM V2 ==="
    )

    print(
        "model:",
        MODEL,
    )

    print(
        "project works:",
        len(
            projects
        ),
    )

    print(
        "edition rows:",
        len(
            routing_input
        ),
    )

    print(
        "components:",
        len(
            components
        ),
    )

    print(
        "already completed projects:",
        len(
            done_projects
        ),
    )

    print(
        "remaining projects:",
        len(
            remaining
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

            pid = row[
                "project_work_id"
            ]

            ed = routing_input.loc[
                routing_input[
                    "project_work_id"
                ].eq(pid)
            ].copy()

            cp = components.loc[
                components[
                    "project_work_id"
                ].eq(pid)
            ].copy()

            assert len(ed) == int(
                row[
                    "edition_rows"
                ]
            )

            assert not cp.empty

            future = executor.submit(
                call_one,
                client,
                prompt_text,
                row,
                cp,
                ed,
            )

            futures[
                future
            ] = pid

        for i, future in enumerate(
            as_completed(
                futures
            ),
            start=1,
        ):

            pid = futures[
                future
            ]

            try:

                routes, response_row = (
                    future.result()
                )

                completed_routing.extend(
                    routes
                )

                completed_responses.append(
                    response_row
                )

                checkpoint(
                    completed_routing,
                    completed_responses,
                )

            except Exception as exc:

                failures.append(
                    (
                        pid,
                        str(exc),
                    )
                )

            if (
                i % 5 == 0
                or i == len(
                    futures
                )
            ):
                print(
                    "completed this run:",
                    i,
                    "/",
                    len(
                        futures
                    ),
                    "| total projects saved:",
                    len(
                        completed_responses
                    ),
                    "| failures:",
                    len(
                        failures
                    ),
                    flush=True,
                )

    if failures:

        print()
        print("FAILED:")

        for pid, message in failures:
            print(
                pid,
                message,
                sep="\t",
            )

        raise RuntimeError(
            "Some projects failed; "
            "partial results saved."
        )

    routing = pd.DataFrame(
        completed_routing,
        columns=ROUTING_FIELDS,
    )

    responses = pd.DataFrame(
        completed_responses,
        columns=RESPONSE_FIELDS,
    )

    routing[
        "remediation_priority_rank"
    ] = pd.to_numeric(
        routing[
            "remediation_priority_rank"
        ]
    )

    responses[
        "remediation_priority_rank"
    ] = pd.to_numeric(
        responses[
            "remediation_priority_rank"
        ]
    )

    routing = routing.sort_values(
        [
            "remediation_priority_rank",
            "project_work_id",
            "edition_key",
        ],
        kind="stable",
    ).reset_index(
        drop=True
    )

    responses = responses.sort_values(
        [
            "remediation_priority_rank",
            "project_work_id",
        ],
        kind="stable",
    ).reset_index(
        drop=True
    )

    # --------------------------------------------------------
    # Final exact-set validation
    # --------------------------------------------------------

    assert len(
        routing
    ) == EXPECTED_EDITIONS

    assert routing[
        "edition_key"
    ].is_unique

    assert set(
        routing[
            "edition_key"
        ]
    ) == set(
        routing_input[
            "edition_key"
        ]
    )

    assert (
        routing[
            "project_work_id"
        ].nunique()
        == EXPECTED_PROJECTS
    )

    assert len(
        responses
    ) == EXPECTED_PROJECTS

    assert responses[
        "project_work_id"
    ].is_unique

    assert set(
        responses[
            "project_work_id"
        ]
    ) == project_ids

    valid_component_map = (
        components
        .set_index(
            "component_id"
        )[
            "project_work_id"
        ]
        .to_dict()
    )

    for r in routing.itertuples(
        index=False
    ):

        if (
            r.routing_decision
            == "ASSIGN_COMPONENT"
        ):
            assert r.component_id

            assert (
                valid_component_map[
                    r.component_id
                ]
                == r.project_work_id
            )

            assert r.component_label
            assert r.human_role_hint

        elif (
            r.routing_decision
            == "HOLD_UNRESOLVED"
        ):
            assert (
                r.component_id
                == ""
            )

            assert (
                r.component_label
                == ""
            )

            assert (
                r.human_role_hint
                == ""
            )

        else:
            raise AssertionError(
                r.routing_decision
            )

        assert (
            r.llm_confidence
            in CONFIDENCE
        )

        assert r.llm_note

    # Original Edition metadata must be unchanged.
    compare_cols = [
        "project_work_id",
        "current_ol_work_id",
        "edition_key",
        "edition_title",
        "edition_subtitle",
        "publish_date",
        "publishers",
        "edition_author_keys",
        "number_of_pages",
    ]

    left = (
        routing[
            compare_cols
        ]
        .sort_values(
            "edition_key"
        )
        .reset_index(
            drop=True
        )
        .astype(str)
    )

    right = (
        routing_input[
            compare_cols
        ]
        .sort_values(
            "edition_key"
        )
        .reset_index(
            drop=True
        )
        .astype(str)
    )

    assert left.equals(
        right
    )

    atomic_tsv(
        routing,
        OUT_TSV,
    )

    atomic_tsv(
        responses,
        OUT_RESPONSES,
    )

    if PARTIAL_ROUTING.exists():
        PARTIAL_ROUTING.unlink()

    if PARTIAL_RESPONSES.exists():
        PARTIAL_RESPONSES.unlink()

    decision_counts = {
        str(k): int(v)
        for k, v
        in routing[
            "routing_decision"
        ]
        .value_counts()
        .sort_index()
        .items()
    }

    confidence_counts = {
        str(k): int(v)
        for k, v
        in routing[
            "llm_confidence"
        ]
        .value_counts()
        .sort_index()
        .items()
    }

    assigned = routing.loc[
        routing[
            "routing_decision"
        ].eq(
            "ASSIGN_COMPONENT"
        )
    ].copy()

    role_counts = {
        str(k): int(v)
        for k, v
        in assigned[
            "human_role_hint"
        ]
        .value_counts()
        .sort_index()
        .items()
    }

    per_project = []

    for pid, g in routing.groupby(
        "project_work_id",
        sort=False,
    ):

        per_project.append({
            "project_work_id":
                pid,

            "edition_rows":
                len(g),

            "assigned":
                int(
                    g[
                        "routing_decision"
                    ].eq(
                        "ASSIGN_COMPONENT"
                    ).sum()
                ),

            "hold_unresolved":
                int(
                    g[
                        "routing_decision"
                    ].eq(
                        "HOLD_UNRESOLVED"
                    ).sum()
                ),

            "low_confidence":
                int(
                    g[
                        "llm_confidence"
                    ].eq(
                        "LOW"
                    ).sum()
                ),
        })

    input_tokens = (
        pd.to_numeric(
            responses[
                "llm_input_tokens"
            ],
            errors="coerce",
        )
        .fillna(0)
        .sum()
    )

    output_tokens = (
        pd.to_numeric(
            responses[
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

        "status":
            "provisional_llm_edition_routing",

        "created_at":
            CREATED_AT,

        "model_requested":
            MODEL,

        "project_works":
            EXPECTED_PROJECTS,

        "edition_rows":
            EXPECTED_EDITIONS,

        "component_registry_rows":
            EXPECTED_COMPONENTS,

        "routing_decision_counts":
            decision_counts,

        "confidence_counts":
            confidence_counts,

        "assigned_component_role_hint_counts":
            role_counts,

        "project_summaries":
            per_project,

        "usage": {
            "input_tokens":
                int(
                    input_tokens
                ),

            "output_tokens":
                int(
                    output_tokens
                ),
        },
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

        "rows":
            len(
                routing
            ),

        "unique_edition_keys":
            routing[
                "edition_key"
            ].nunique(),

        "project_works":
            routing[
                "project_work_id"
            ].nunique(),

        "project_response_rows":
            len(
                responses
            ),

        "exact_edition_key_set_match":
            True,

        "no_duplicate_edition_keys":
            True,

        "original_edition_metadata_unchanged":
            True,

        "all_assigned_components_valid_for_project":
            True,

        "all_holds_have_blank_component":
            True,

        "all_notes_nonblank":
            True,

        "routing_decision_counts":
            decision_counts,

        "confidence_counts":
            confidence_counts,

        "assigned_component_role_hint_counts":
            role_counts,

        "project_summaries":
            per_project,
    }

    atomic_json(
        audit,
        OUT_AUDIT,
    )

    manifest = {
        "release":
            RELEASE,

        "status":
            "provisional_llm_edition_routing",

        "created_at":
            CREATED_AT,

        "input_freeze_commit":
            INPUT_FREEZE_COMMIT,

        "registry_v2_freeze_commit":
            REGISTRY_V2_FREEZE_COMMIT,

        "semantics": [
            (
                "This v2 run reroutes all 191 Editions "
                "belonging to the six predecessor project "
                "works whose component registry changed "
                "after human audit."
            ),
            (
                "The frozen project-level human "
                "resolution_plan and resolution_note "
                "predate registry v2 and are historical "
                "context. Where they omit or conflict "
                "with a registry-v2 component, the fixed "
                "registry v2 is authoritative."
            ),
            (
                "No previous row-level LLM routing answer "
                "or human audit decision is supplied to "
                "the model."
            ),
            (
                "One LLM call is made per predecessor "
                "project work, with all of that Work's "
                "Edition records visible together."
            ),
            (
                "The LLM may assign an Edition only to "
                "a human-defined fixed component for the "
                "same predecessor project work, or return "
                "HOLD_UNRESOLVED."
            ),
            (
                "The LLM may not create, merge, or split "
                "component boundaries."
            ),
            (
                "An omnibus or anthology is routed as one "
                "Edition-level publication and is not "
                "decomposed into constituent literary works."
            ),
            (
                "DETACH, EXCLUDE_APPARATUS, and "
                "PRIMARY_SUCCESSOR_HINT are human component "
                "metadata, not LLM routing decisions."
            ),
            (
                "This release does not create source "
                "entities, project works, lineage edges, "
                "or corpus-scope decisions."
            ),
        ],

        "inputs": {
            str(
                ROUTING_INPUT.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    ROUTING_INPUT
                ),

            str(
                PROJECT_INPUT.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    PROJECT_INPUT
                ),

            str(
                INPUT_AUDIT.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    INPUT_AUDIT
                ),

            str(
                COMPONENTS.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    COMPONENTS
                ),

            str(
                COMPONENT_MANIFEST.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    COMPONENT_MANIFEST
                ),

            str(
                PROMPT.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    PROMPT
                ),

            str(
                Path(__file__).relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    Path(__file__)
                ),
        },

        "outputs": {
            OUT_TSV.name:
                sha256_file(
                    OUT_TSV
                ),

            OUT_RESPONSES.name:
                sha256_file(
                    OUT_RESPONSES
                ),

            OUT_SUMMARY.name:
                sha256_file(
                    OUT_SUMMARY
                ),

            OUT_AUDIT.name:
                sha256_file(
                    OUT_AUDIT
                ),

            RUN_CONFIG.name:
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
        "=== FINAL ROUTING SUMMARY ==="
    )

    print(
        "edition rows:",
        len(
            routing
        ),
    )

    print(
        "project works:",
        routing[
            "project_work_id"
        ].nunique(),
    )

    print()
    print(
        "=== ROUTING DECISIONS ==="
    )

    print(
        routing[
            "routing_decision"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print()
    print(
        "=== CONFIDENCE ==="
    )

    print(
        routing[
            "llm_confidence"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print()
    print(
        "=== ASSIGNED HUMAN ROLE HINTS ==="
    )

    if len(
        assigned
    ):
        print(
            assigned[
                "human_role_hint"
            ]
            .value_counts()
            .sort_index()
            .to_string()
        )
    else:
        print(
            "[none]"
        )

    print()
    print(
        "=== PER PROJECT ==="
    )

    print(
        pd.DataFrame(
            per_project
        ).to_string(
            index=False
        )
    )

    print()
    print(
        "input tokens:",
        int(
            input_tokens
        ),
    )

    print(
        "output tokens:",
        int(
            output_tokens
        ),
    )

    print()
    print(
        "QC STATUS: PASSED"
    )


if __name__ == "__main__":
    main()
