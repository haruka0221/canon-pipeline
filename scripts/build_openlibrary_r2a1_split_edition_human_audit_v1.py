#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

LLM_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_routing_llm_v1"
)

LLM_ROUTING = (
    LLM_DIR
    / "openlibrary_r2a1_split_edition_routing_llm_v1.tsv"
)

INPUT_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_routing_input_v1"
)

ROUTING_INPUT = (
    INPUT_DIR
    / "openlibrary_r2a1_split_edition_routing_input_v1.tsv"
)

PROJECT_INPUT = (
    INPUT_DIR
    / "openlibrary_r2a1_split_edition_routing_projects_v1.tsv"
)

COMPONENTS = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_component_registry_v1"
    / "openlibrary_r2a1_split_component_registry_v1.tsv"
)

OUT_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_human_audit_v1"
)

OUT_CASES = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_human_audit_cases_v1.tsv"
)

OUT_COMPONENTS = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_human_audit_components_v1.tsv"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_human_audit_v1_manifest.json"
)


CREATED_AT = "2026-10-11"

LLM_FREEZE_COMMIT = (
    "9d4a2d0ce50cc5335e06672732aa060d3a3be124"
)

EXPECTED_ROWS = 508
EXPECTED_PROJECTS = 17
EXPECTED_NON_HIGH = 57
EXPECTED_SENSITIVE_ASSIGNED = 28

SALT = (
    "openlibrary-r2a1-split-edition-human-audit-v1"
)


def sha256_file(path):
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


def stable_hash(
    project_work_id,
    stratum,
    edition_key,
):
    return hashlib.sha256(
        (
            SALT
            + "\0"
            + project_work_id
            + "\0"
            + stratum
            + "\0"
            + edition_key
        ).encode("utf-8")
    ).hexdigest()


def choose_one(
    df,
    project_work_id,
    stratum,
):
    if df.empty:
        return None

    z = df.copy()

    z["_selection_hash"] = z[
        "edition_key"
    ].map(
        lambda x:
            stable_hash(
                project_work_id,
                stratum,
                x,
            )
    )

    z = z.sort_values(
        [
            "_selection_hash",
            "edition_key",
        ],
        kind="stable",
    )

    return z.iloc[0][
        "edition_key"
    ]


def main():

    for p in [
        LLM_ROUTING,
        ROUTING_INPUT,
        PROJECT_INPUT,
        COMPONENTS,
    ]:
        if not p.exists():
            raise FileNotFoundError(p)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory already exists: {OUT_DIR}"
        )

    llm = pd.read_csv(
        LLM_ROUTING,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    src = pd.read_csv(
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

    assert len(llm) == EXPECTED_ROWS
    assert len(src) == EXPECTED_ROWS

    assert llm["edition_key"].is_unique
    assert src["edition_key"].is_unique

    assert set(
        llm["edition_key"]
    ) == set(
        src["edition_key"]
    )

    assert (
        llm["project_work_id"].nunique()
        == EXPECTED_PROJECTS
    )

    assert (
        projects["project_work_id"].nunique()
        == EXPECTED_PROJECTS
    )

    # --------------------------------------------------------
    # Selection.
    #
    # Selection criteria are computed from frozen LLM output,
    # but the resulting human-review cases do NOT expose
    # LLM decision/confidence/note fields.
    # --------------------------------------------------------

    selected = set()

    selection_counts = {
        "mandatory_non_high":
            0,

        "mandatory_sensitive_assignment":
            0,

        "high_primary_successor_sample":
            0,

        "high_assign_sample":
            0,

        "high_hold_sample":
            0,
    }

    # 1. All LOW + MEDIUM.
    non_high = llm.loc[
        llm[
            "llm_confidence"
        ].isin(
            [
                "LOW",
                "MEDIUM",
            ]
        )
    ].copy()

    assert len(
        non_high
    ) == EXPECTED_NON_HIGH

    before = len(selected)

    selected.update(
        non_high[
            "edition_key"
        ]
    )

    selection_counts[
        "mandatory_non_high"
    ] = (
        len(selected)
        - before
    )

    # 2. All policy-sensitive assignments:
    # DETACH or EXCLUDE_APPARATUS.
    sensitive = llm.loc[
        llm[
            "routing_decision"
        ].eq(
            "ASSIGN_COMPONENT"
        )
        &
        llm[
            "human_role_hint"
        ].isin(
            [
                "DETACH",
                "EXCLUDE_APPARATUS",
            ]
        )
    ].copy()

    assert len(
        sensitive
    ) == EXPECTED_SENSITIVE_ASSIGNED

    before = len(selected)

    selected.update(
        sensitive[
            "edition_key"
        ]
    )

    selection_counts[
        "mandatory_sensitive_assignment"
    ] = (
        len(selected)
        - before
    )

    # 3. For every project containing a
    # PRIMARY_SUCCESSOR_HINT, select one HIGH-confidence
    # assignment to that role if not already represented.
    primary_projects = sorted(
        set(
            llm.loc[
                llm[
                    "human_role_hint"
                ].eq(
                    "PRIMARY_SUCCESSOR_HINT"
                ),
                "project_work_id",
            ]
        )
    )

    for pid in primary_projects:

        z = llm.loc[
            llm[
                "project_work_id"
            ].eq(pid)
            &
            llm[
                "routing_decision"
            ].eq(
                "ASSIGN_COMPONENT"
            )
            &
            llm[
                "human_role_hint"
            ].eq(
                "PRIMARY_SUCCESSOR_HINT"
            )
            &
            llm[
                "llm_confidence"
            ].eq(
                "HIGH"
            )
            &
            ~llm[
                "edition_key"
            ].isin(
                selected
            )
        ].copy()

        key = choose_one(
            z,
            pid,
            "high_primary_successor",
        )

        if key is not None:
            selected.add(key)

            selection_counts[
                "high_primary_successor_sample"
            ] += 1

    # 4. One remaining HIGH-confidence ordinary assignment
    # per project where available.
    for pid in sorted(
        set(
            llm[
                "project_work_id"
            ]
        )
    ):

        z = llm.loc[
            llm[
                "project_work_id"
            ].eq(pid)
            &
            llm[
                "routing_decision"
            ].eq(
                "ASSIGN_COMPONENT"
            )
            &
            llm[
                "llm_confidence"
            ].eq(
                "HIGH"
            )
            &
            ~llm[
                "edition_key"
            ].isin(
                selected
            )
        ].copy()

        key = choose_one(
            z,
            pid,
            "high_assign",
        )

        if key is not None:
            selected.add(key)

            selection_counts[
                "high_assign_sample"
            ] += 1

    # 5. One remaining HIGH-confidence HOLD per project
    # where available.
    for pid in sorted(
        set(
            llm[
                "project_work_id"
            ]
        )
    ):

        z = llm.loc[
            llm[
                "project_work_id"
            ].eq(pid)
            &
            llm[
                "routing_decision"
            ].eq(
                "HOLD_UNRESOLVED"
            )
            &
            llm[
                "llm_confidence"
            ].eq(
                "HIGH"
            )
            &
            ~llm[
                "edition_key"
            ].isin(
                selected
            )
        ].copy()

        key = choose_one(
            z,
            pid,
            "high_hold",
        )

        if key is not None:
            selected.add(key)

            selection_counts[
                "high_hold_sample"
            ] += 1

    assert selected

    # --------------------------------------------------------
    # Visible human-review packet.
    #
    # Crucially, source rows come from pre-LLM routing input,
    # not from the LLM output table.
    # --------------------------------------------------------

    review = src.loc[
        src[
            "edition_key"
        ].isin(
            selected
        )
    ].copy()

    review[
        "remediation_priority_rank"
    ] = pd.to_numeric(
        review[
            "remediation_priority_rank"
        ]
    )

    review = review.sort_values(
        [
            "remediation_priority_rank",
            "project_work_id",
            "publish_date",
            "edition_key",
        ],
        kind="stable",
    ).reset_index(
        drop=True
    )

    assert set(
        review[
            "edition_key"
        ]
    ) == selected

    # No LLM-result fields are permitted in the review table.
    forbidden = {
        "routing_decision",
        "component_id",
        "component_label",
        "human_role_hint",
        "llm_confidence",
        "llm_note",
        "llm_response_id",
    }

    assert not (
        forbidden
        & set(
            review.columns
        )
    )

    review.insert(
        0,
        "audit_case_id",
        [
            f"SERH{n:04d}"
            for n
            in range(
                1,
                len(review) + 1,
            )
        ],
    )

    # Human-entered fields.
    review[
        "human_routing_decision"
    ] = ""

    review[
        "human_component_id"
    ] = ""

    review[
        "human_confidence"
    ] = ""

    review[
        "human_note"
    ] = ""

    # Keep all fixed component definitions for every selected
    # predecessor project work.
    selected_projects = set(
        review[
            "project_work_id"
        ]
    )

    review_components = (
        components.loc[
            components[
                "project_work_id"
            ].isin(
                selected_projects
            )
        ]
        .sort_values(
            [
                "remediation_priority_rank",
                "project_work_id",
                "component_local_id",
            ],
            kind="stable",
        )
        .reset_index(
            drop=True
        )
    )

    # Every selected project must have its component registry.
    assert set(
        review[
            "project_work_id"
        ]
    ) == set(
        review_components[
            "project_work_id"
        ]
    )

    # All 17 projects should be represented by the audit.
    assert (
        review[
            "project_work_id"
        ].nunique()
        == EXPECTED_PROJECTS
    )

    OUT_DIR.mkdir(
        parents=True,
    )

    atomic_tsv(
        review,
        OUT_CASES,
    )

    atomic_tsv(
        review_components,
        OUT_COMPONENTS,
    )

    manifest = {
        "release":
            "openlibrary-r2a1-split-edition-human-audit-v1",

        "created_at":
            CREATED_AT,

        "llm_freeze_commit":
            LLM_FREEZE_COMMIT,

        "status":
            "human_review_packet_unadjudicated",

        "counts": {
            "review_cases":
                len(review),

            "review_project_works":
                int(
                    review[
                        "project_work_id"
                    ].nunique()
                ),

            "component_reference_rows":
                len(
                    review_components
                ),

            "selection_stage_new_rows":
                selection_counts,

            "frozen_llm_non_high_rows":
                len(
                    non_high
                ),

            "frozen_llm_sensitive_assignment_rows":
                len(
                    sensitive
                ),
        },

        "selection_policy": [
            (
                "Include every frozen LLM row with LOW or "
                "MEDIUM confidence."
            ),
            (
                "Include every ASSIGN_COMPONENT row routed "
                "to a human-defined DETACH or "
                "EXCLUDE_APPARATUS component."
            ),
            (
                "For project works with a "
                "PRIMARY_SUCCESSOR_HINT component, add one "
                "deterministically selected remaining "
                "HIGH-confidence assignment when available."
            ),
            (
                "For each predecessor project work, add one "
                "deterministically selected remaining "
                "HIGH-confidence assignment when available."
            ),
            (
                "For each predecessor project work, add one "
                "deterministically selected remaining "
                "HIGH-confidence HOLD_UNRESOLVED row when "
                "available."
            ),
        ],

        "blinding": [
            (
                "Human review cases are populated from the "
                "pre-LLM routing input rather than from the "
                "LLM output artifact."
            ),
            (
                "Row-level LLM routing decision, component, "
                "confidence, note, and response identifier "
                "are withheld from the human review table."
            ),
            (
                "This is not a fully independent blinded "
                "validation because the reviewer has prior "
                "knowledge of the project and aggregate LLM "
                "results."
            ),
        ],

        "human_decision_contract": {
            "human_routing_decision": [
                "ASSIGN_COMPONENT",
                "HOLD_UNRESOLVED",
                "REGISTRY_ISSUE",
            ],

            "human_component_id":
                (
                    "Required only for ASSIGN_COMPONENT; "
                    "must be a component_id belonging to "
                    "the same predecessor project work."
                ),

            "human_confidence": [
                "HIGH",
                "MEDIUM",
                "LOW",
            ],

            "human_note":
                (
                    "Concise evidence basis; required for "
                    "REGISTRY_ISSUE and recommended for "
                    "other decisions."
                ),
        },

        "semantics": [
            (
                "The packet combines targeted operational "
                "review with a small deterministic "
                "validation sample."
            ),
            (
                "The selected rows must not be treated as "
                "a simple random sample of all 508 Editions."
            ),
            (
                "Human review does not mutate the frozen "
                "raw LLM routing artifact."
            ),
            (
                "REGISTRY_ISSUE allows the reviewer to flag "
                "a problem with the fixed component "
                "ontology rather than forcing an invalid "
                "assignment."
            ),
        ],

        "inputs": {
            str(
                LLM_ROUTING.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    LLM_ROUTING
                ),

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
                COMPONENTS.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    COMPONENTS
                ),
        },

        "outputs": {
            OUT_CASES.name:
                sha256_file(
                    OUT_CASES
                ),

            OUT_COMPONENTS.name:
                sha256_file(
                    OUT_COMPONENTS
                ),
        },
    }

    atomic_json(
        manifest,
        OUT_MANIFEST,
    )

    print(
        "=== SPLIT EDITION HUMAN AUDIT V1 ==="
    )

    print(
        "review cases:",
        len(review),
    )

    print(
        "project works:",
        review[
            "project_work_id"
        ].nunique(),
    )

    print(
        "component reference rows:",
        len(
            review_components
        ),
    )

    print()
    print(
        "=== NEW ROWS BY SELECTION STAGE ==="
    )

    for k, v in (
        selection_counts.items()
    ):
        print(
            f"{k}: {v}"
        )

    print()
    print(
        "=== REVIEW CASES BY PROJECT ==="
    )

    print(
        review.groupby(
            [
                "remediation_priority_rank",
                "project_work_id",
                "r2_target_title",
            ]
        )
        .size()
        .rename(
            "review_cases"
        )
        .reset_index()
        .sort_values(
            "remediation_priority_rank"
        )
        .to_string(
            index=False
        )
    )

    print()
    print(
        "LLM row-level answers withheld:",
        True,
    )

    print()
    print(
        "QC STATUS: PASSED"
    )


if __name__ == "__main__":
    main()
