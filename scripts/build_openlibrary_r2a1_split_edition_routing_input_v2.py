#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

V1_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_routing_input_v1"
)

V1_EDITIONS = (
    V1_DIR
    / "openlibrary_r2a1_split_edition_routing_input_v1.tsv"
)

V1_PROJECTS = (
    V1_DIR
    / "openlibrary_r2a1_split_edition_routing_projects_v1.tsv"
)

REGISTRY_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_component_registry_v2"
)

REGISTRY = (
    REGISTRY_DIR
    / "openlibrary_r2a1_split_component_registry_v2.tsv"
)

AFFECTED_PROJECTS = (
    REGISTRY_DIR
    / "openlibrary_r2a1_split_component_registry_v2_affected_projects.tsv"
)

REGISTRY_MANIFEST = (
    REGISTRY_DIR
    / "openlibrary_r2a1_split_component_registry_v2_manifest.json"
)

OUT_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_routing_input_v2"
)

OUT_EDITIONS = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_input_v2.tsv"
)

OUT_PROJECTS = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_projects_v2.tsv"
)

OUT_COMPONENTS = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_components_v2.tsv"
)

OUT_AUDIT = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_input_v2_audit.json"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_input_v2_manifest.json"
)


RELEASE = (
    "openlibrary-r2a1-split-edition-routing-input-v2"
)

CREATED_AT = "2026-10-11"

REGISTRY_V2_FREEZE_COMMIT = (
    "bbb190bd6f47eda96981a4434da00935bf2a818f"
)

EXPECTED_PROJECTS = 6
EXPECTED_EDITIONS = 191
EXPECTED_COMPONENTS = 39

EXPECTED_EDITION_COUNTS = {
    "W000014024": 31,
    "W000030498": 42,
    "W000003023": 6,
    "W000005682": 22,
    "W000021761": 47,
    "W000005423": 43,
}

EXPECTED_COMPONENT_COUNTS = {
    "W000014024": 9,
    "W000030498": 7,
    "W000003023": 4,
    "W000005682": 5,
    "W000021761": 7,
    "W000005423": 7,
}


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


def main():

    for p in [
        V1_EDITIONS,
        V1_PROJECTS,
        REGISTRY,
        AFFECTED_PROJECTS,
        REGISTRY_MANIFEST,
    ]:
        if not p.exists():
            raise FileNotFoundError(p)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory already exists: {OUT_DIR}"
        )

    editions = pd.read_csv(
        V1_EDITIONS,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    projects = pd.read_csv(
        V1_PROJECTS,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    registry = pd.read_csv(
        REGISTRY,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    affected = pd.read_csv(
        AFFECTED_PROJECTS,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    registry_manifest = json.loads(
        REGISTRY_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    assert (
        registry_manifest["status"]
        == "human_defined_routing_component_registry"
    )

    assert (
        registry_manifest["release"]
        == "openlibrary-r2a1-split-component-registry-v2"
    )

    affected_ids = set(
        affected["project_work_id"]
    )

    assert len(
        affected_ids
    ) == EXPECTED_PROJECTS

    assert affected_ids == set(
        EXPECTED_EDITION_COUNTS
    )

    # --------------------------------------------------------
    # Exact six-project rerouting subset.
    # --------------------------------------------------------

    out_editions = editions.loc[
        editions[
            "project_work_id"
        ].isin(
            affected_ids
        )
    ].copy()

    out_projects = projects.loc[
        projects[
            "project_work_id"
        ].isin(
            affected_ids
        )
    ].copy()

    out_components = registry.loc[
        registry[
            "project_work_id"
        ].isin(
            affected_ids
        )
    ].copy()

    # --------------------------------------------------------
    # QC.
    # --------------------------------------------------------

    assert len(
        out_editions
    ) == EXPECTED_EDITIONS

    assert out_editions[
        "edition_key"
    ].is_unique

    assert (
        out_editions[
            "project_work_id"
        ].nunique()
        == EXPECTED_PROJECTS
    )

    assert len(
        out_projects
    ) == EXPECTED_PROJECTS

    assert out_projects[
        "project_work_id"
    ].is_unique

    assert len(
        out_components
    ) == EXPECTED_COMPONENTS

    assert out_components[
        "component_id"
    ].is_unique

    edition_counts = {
        str(k): int(v)
        for k, v
        in out_editions[
            "project_work_id"
        ]
        .value_counts()
        .sort_index()
        .items()
    }

    component_counts = {
        str(k): int(v)
        for k, v
        in out_components[
            "project_work_id"
        ]
        .value_counts()
        .sort_index()
        .items()
    }

    assert (
        edition_counts
        == dict(
            sorted(
                EXPECTED_EDITION_COUNTS.items()
            )
        )
    )

    assert (
        component_counts
        == dict(
            sorted(
                EXPECTED_COMPONENT_COUNTS.items()
            )
        )
    )

    project_declared_counts = {
        row.project_work_id:
            int(
                row.edition_rows
            )
        for row in out_projects.itertuples(
            index=False
        )
    }

    assert (
        project_declared_counts
        == EXPECTED_EDITION_COUNTS
    )

    affected_declared_counts = {
        row.project_work_id:
            int(
                row.edition_rows_to_reroute
            )
        for row in affected.itertuples(
            index=False
        )
    }

    assert (
        affected_declared_counts
        == EXPECTED_EDITION_COUNTS
    )

    # No LLM-output or human-row-adjudication fields should
    # enter the rerouting evidence packet.
    forbidden_columns = {
        "routing_decision",
        "component_id",
        "component_label",
        "human_role_hint",
        "llm_confidence",
        "llm_note",
        "llm_response_id",
        "human_routing_decision",
        "human_component_id",
        "human_confidence",
        "human_note",
    }

    assert not (
        forbidden_columns
        & set(
            out_editions.columns
        )
    )

    # Stable ordering.
    out_editions[
        "_rank"
    ] = pd.to_numeric(
        out_editions[
            "remediation_priority_rank"
        ]
    )

    out_editions = (
        out_editions.sort_values(
            [
                "_rank",
                "project_work_id",
                "publish_date",
                "edition_key",
            ],
            kind="stable",
        )
        .drop(
            columns="_rank"
        )
        .reset_index(
            drop=True
        )
    )

    out_projects[
        "_rank"
    ] = pd.to_numeric(
        out_projects[
            "remediation_priority_rank"
        ]
    )

    out_projects = (
        out_projects.sort_values(
            [
                "_rank",
                "project_work_id",
            ],
            kind="stable",
        )
        .drop(
            columns="_rank"
        )
        .reset_index(
            drop=True
        )
    )

    out_components[
        "_rank"
    ] = pd.to_numeric(
        out_components[
            "remediation_priority_rank"
        ]
    )

    out_components[
        "_local"
    ] = (
        out_components[
            "component_local_id"
        ]
        .str.replace(
            "C",
            "",
            regex=False,
        )
        .astype(int)
    )

    out_components = (
        out_components.sort_values(
            [
                "_rank",
                "project_work_id",
                "_local",
            ],
            kind="stable",
        )
        .drop(
            columns=[
                "_rank",
                "_local",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    OUT_DIR.mkdir(
        parents=True,
    )

    atomic_tsv(
        out_editions,
        OUT_EDITIONS,
    )

    atomic_tsv(
        out_projects,
        OUT_PROJECTS,
    )

    atomic_tsv(
        out_components,
        OUT_COMPONENTS,
    )

    audit = {
        "release":
            RELEASE,

        "audit_status":
            "PASSED",

        "project_works":
            len(
                out_projects
            ),

        "edition_rows":
            len(
                out_editions
            ),

        "unique_edition_keys":
            out_editions[
                "edition_key"
            ].nunique(),

        "component_rows":
            len(
                out_components
            ),

        "edition_rows_by_project":
            edition_counts,

        "component_rows_by_project":
            component_counts,

        "affected_project_set_exact":
            True,

        "contains_prior_llm_answers":
            False,

        "contains_row_level_human_adjudication":
            False,
    }

    atomic_json(
        audit,
        OUT_AUDIT,
    )

    manifest = {
        "release":
            RELEASE,

        "status":
            "llm_rerouting_input",

        "created_at":
            CREATED_AT,

        "registry_v2_freeze_commit":
            REGISTRY_V2_FREEZE_COMMIT,

        "semantics": [
            (
                "This artifact contains only the six "
                "project works whose fixed component "
                "registry changed in registry v2."
            ),
            (
                "All 191 Editions belonging to those six "
                "predecessor project works are rerouted "
                "in full; individual issue rows are not "
                "patched in isolation."
            ),
            (
                "The 317 Editions belonging to the other "
                "eleven split project works are absent "
                "because their component ontology did "
                "not change."
            ),
            (
                "The original frozen human resolution "
                "plan and note are retained as historical "
                "project context. The fixed registry v2 "
                "will be authoritative where that older "
                "plan omits a newly added or revised "
                "component."
            ),
            (
                "No frozen v1 LLM routing answer is "
                "included in the rerouting input."
            ),
            (
                "No row-level human audit decision is "
                "included in the rerouting input."
            ),
            (
                "Registry v2 itself is human-remediated "
                "and therefore this rerun is remediation, "
                "not an independent validation experiment."
            ),
            (
                "No project-work IDs, source-entity IDs, "
                "lineage, or scope decisions are created "
                "by this input artifact."
            ),
        ],

        "inputs": {
            str(
                V1_EDITIONS.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    V1_EDITIONS
                ),

            str(
                V1_PROJECTS.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    V1_PROJECTS
                ),

            str(
                REGISTRY.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    REGISTRY
                ),

            str(
                AFFECTED_PROJECTS.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    AFFECTED_PROJECTS
                ),

            str(
                REGISTRY_MANIFEST.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    REGISTRY_MANIFEST
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
            OUT_EDITIONS.name:
                sha256_file(
                    OUT_EDITIONS
                ),

            OUT_PROJECTS.name:
                sha256_file(
                    OUT_PROJECTS
                ),

            OUT_COMPONENTS.name:
                sha256_file(
                    OUT_COMPONENTS
                ),

            OUT_AUDIT.name:
                sha256_file(
                    OUT_AUDIT
                ),
        },
    }

    atomic_json(
        manifest,
        OUT_MANIFEST,
    )

    print(
        "=== SPLIT EDITION REROUTING INPUT V2 ==="
    )

    print(
        "project works:",
        len(
            out_projects
        ),
    )

    print(
        "edition rows:",
        len(
            out_editions
        ),
    )

    print(
        "component rows:",
        len(
            out_components
        ),
    )

    print()
    print(
        "=== EDITIONS BY PROJECT ==="
    )

    print(
        out_editions.groupby(
            [
                "remediation_priority_rank",
                "project_work_id",
                "r2_target_title",
            ]
        )
        .size()
        .rename(
            "edition_rows"
        )
        .reset_index()
        .assign(
            remediation_priority_rank=lambda x:
                pd.to_numeric(
                    x[
                        "remediation_priority_rank"
                    ]
                )
        )
        .sort_values(
            "remediation_priority_rank"
        )
        .to_string(
            index=False
        )
    )

    print()
    print(
        "=== COMPONENTS BY PROJECT ==="
    )

    print(
        out_components.groupby(
            [
                "remediation_priority_rank",
                "project_work_id",
                "r2_target_title",
            ]
        )
        .size()
        .rename(
            "component_rows"
        )
        .reset_index()
        .assign(
            remediation_priority_rank=lambda x:
                pd.to_numeric(
                    x[
                        "remediation_priority_rank"
                    ]
                )
        )
        .sort_values(
            "remediation_priority_rank"
        )
        .to_string(
            index=False
        )
    )

    print()
    print(
        "prior LLM answers included:",
        False,
    )

    print(
        "row-level human decisions included:",
        False,
    )

    print()
    print(
        "QC STATUS: PASSED"
    )


if __name__ == "__main__":
    main()
