#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

V1 = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_routing_llm_v1"
    / "openlibrary_r2a1_split_edition_routing_llm_v1.tsv"
)

V2 = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_routing_llm_v2"
    / "openlibrary_r2a1_split_edition_routing_llm_v2.tsv"
)

HUMAN = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_human_audit_adjudication_v1"
    / "openlibrary_r2a1_split_edition_human_audit_adjudication_v1.tsv"
)

REGISTRY = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_component_registry_v2"
    / "openlibrary_r2a1_split_component_registry_v2.tsv"
)

REGISTRY_CHANGES = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_component_registry_v2"
    / "openlibrary_r2a1_split_component_registry_v2_changes.tsv"
)

OUT_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_routing_final_v1"
)

OUT_TSV = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_final_v1.tsv"
)

OUT_HUMAN_LEDGER = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_final_v1_human_authority.tsv"
)

OUT_SUMMARY = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_final_v1_summary.json"
)

OUT_AUDIT = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_final_v1_audit.json"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_final_v1_manifest.json"
)


RELEASE = (
    "openlibrary-r2a1-split-edition-routing-final-v1"
)

CREATED_AT = "2026-10-11"

V1_LLM_FREEZE_COMMIT = (
    "9d4a2d0ce50cc5335e06672732aa060d3a3be124"
)

HUMAN_FREEZE_COMMIT = (
    "655d2e521487d4cf8e34c435ac419a86a9a353be"
)

REGISTRY_V2_FREEZE_COMMIT = (
    "bbb190bd6f47eda96981a4434da00935bf2a818f"
)

V2_LLM_FREEZE_COMMIT = (
    "de464605eaf4281ab60a1f51706ab5c7245090ac"
)

V1_V2_COMPARISON_FREEZE_COMMIT = (
    "497bb5bbc80c7ba0063b9e3eda3fdc1d2dd4c62a"
)


EXPECTED_ROWS = 508
EXPECTED_PROJECTS = 17

EXPECTED_V2_ROWS = 191
EXPECTED_V1_BASE_ROWS = 317

EXPECTED_HUMAN_ROWS = 118
EXPECTED_HUMAN_DIRECT = 112
EXPECTED_REGISTRY_REMEDIATION = 6
EXPECTED_LLM_ONLY = 390

EXPECTED_FINAL_DECISIONS = {
    "ASSIGN_COMPONENT": 404,
    "HOLD_UNRESOLVED": 104,
}

EXPECTED_PROVENANCE = {
    "human_direct_adjudication": 112,
    "human_registry_remediation_v2": 6,
    "llm_v1_unreviewed": 243,
    "llm_v2_unreviewed": 147,
}

EXPECTED_HUMAN_EFFECT = {
    "HUMAN_CONFIRMS_BASE": 95,
    "HUMAN_OVERRIDES_BASE": 17,
    "REGISTRY_REMEDIATION_CONFIRMED_BY_V2": 6,
}

EXPECTED_ROLE_COUNTS = {
    "DETACH": 28,
    "EXCLUDE_APPARATUS": 5,
    "PRIMARY_SUCCESSOR_HINT": 74,
    "SUCCESSOR": 297,
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


def count_dict(series):
    return {
        str(k): int(v)
        for k, v
        in series.value_counts(
            dropna=False
        )
        .sort_index()
        .items()
    }


def main():

    for p in [
        V1,
        V2,
        HUMAN,
        REGISTRY,
        REGISTRY_CHANGES,
    ]:
        if not p.exists():
            raise FileNotFoundError(p)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory already exists: {OUT_DIR}"
        )

    v1 = pd.read_csv(
        V1,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    v2 = pd.read_csv(
        V2,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    human = pd.read_csv(
        HUMAN,
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

    changes = pd.read_csv(
        REGISTRY_CHANGES,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    # --------------------------------------------------------
    # Structural checks.
    # --------------------------------------------------------

    assert len(v1) == EXPECTED_ROWS
    assert len(v2) == EXPECTED_V2_ROWS
    assert len(human) == EXPECTED_HUMAN_ROWS

    assert v1["edition_key"].is_unique
    assert v2["edition_key"].is_unique
    assert human["edition_key"].is_unique
    assert registry["component_id"].is_unique

    assert (
        v1["project_work_id"].nunique()
        == EXPECTED_PROJECTS
    )

    assert set(
        v2["edition_key"]
    ).issubset(
        set(v1["edition_key"])
    )

    affected_projects = set(
        v2["project_work_id"]
    )

    assert len(
        affected_projects
    ) == 6

    assert len(
        v1.loc[
            v1["project_work_id"].isin(
                affected_projects
            )
        ]
    ) == EXPECTED_V2_ROWS

    # --------------------------------------------------------
    # Maps.
    # --------------------------------------------------------

    v2_map = {
        r["edition_key"]: r
        for r in v2.to_dict(
            orient="records"
        )
    }

    human_map = {
        r["edition_key"]: r
        for r in human.to_dict(
            orient="records"
        )
    }

    component_map = {
        r["component_id"]: r
        for r in registry.to_dict(
            orient="records"
        )
    }

    project_meta = {}

    for r in registry.to_dict(
        orient="records"
    ):
        pid = r["project_work_id"]

        project_meta.setdefault(
            pid,
            {
                "r2_target_title":
                    r["r2_target_title"],

                "r2_target_author":
                    r["r2_target_author"],
            },
        )

    added = changes.loc[
        changes[
            "change_type"
        ].eq(
            "ADD_COMPONENT"
        )
    ].copy()

    assert len(added) == 6
    assert added["basis_case_id"].is_unique

    added_by_case = dict(
        zip(
            added["basis_case_id"],
            added["component_id"],
        )
    )

    # --------------------------------------------------------
    # Compose final 508-row operational routing.
    # --------------------------------------------------------

    rows = []

    for r1 in v1.to_dict(
        orient="records"
    ):

        edition_key = r1["edition_key"]

        if edition_key in v2_map:
            base = v2_map[edition_key]
            base_version = "v2"
        else:
            base = r1
            base_version = "v1"

        h = human_map.get(
            edition_key
        )

        human_case_id = ""
        human_decision = ""
        human_component_id = ""
        human_confidence = ""
        human_note = ""
        human_effect = ""

        if h is None:

            final_decision = (
                base["routing_decision"]
            )

            final_component_id = (
                base["component_id"]
            )

            if base_version == "v2":
                final_provenance = (
                    "llm_v2_unreviewed"
                )
            else:
                final_provenance = (
                    "llm_v1_unreviewed"
                )

        else:

            human_case_id = (
                h["audit_case_id"]
            )

            human_decision = (
                h["human_routing_decision"]
            )

            human_component_id = (
                h["human_component_id"]
            )

            human_confidence = (
                h["human_confidence"]
            )

            human_note = (
                h["human_note"]
            )

            if human_decision in {
                "ASSIGN_COMPONENT",
                "HOLD_UNRESOLVED",
            }:

                final_decision = (
                    human_decision
                )

                final_component_id = (
                    human_component_id
                )

                final_provenance = (
                    "human_direct_adjudication"
                )

                same = (
                    final_decision
                    == base["routing_decision"]
                    and
                    final_component_id
                    == base["component_id"]
                )

                human_effect = (
                    "HUMAN_CONFIRMS_BASE"
                    if same
                    else
                    "HUMAN_OVERRIDES_BASE"
                )

            elif (
                human_decision
                == "REGISTRY_ISSUE"
            ):

                assert (
                    human_case_id
                    in added_by_case
                )

                expected_component = (
                    added_by_case[
                        human_case_id
                    ]
                )

                # Registry remediation was applied only to
                # affected projects rerun under v2.
                assert base_version == "v2"

                # The fresh v2 model independently routed
                # the Edition to the human-added component.
                assert (
                    base["routing_decision"]
                    == "ASSIGN_COMPONENT"
                )

                assert (
                    base["component_id"]
                    == expected_component
                )

                final_decision = (
                    "ASSIGN_COMPONENT"
                )

                final_component_id = (
                    expected_component
                )

                final_provenance = (
                    "human_registry_remediation_v2"
                )

                human_effect = (
                    "REGISTRY_REMEDIATION_CONFIRMED_BY_V2"
                )

            else:
                raise AssertionError(
                    human_decision
                )

        # ----------------------------------------------------
        # Canonical component metadata always comes from
        # frozen component registry v2.
        # ----------------------------------------------------

        if (
            final_decision
            == "ASSIGN_COMPONENT"
        ):

            assert final_component_id

            assert (
                final_component_id
                in component_map
            )

            cm = component_map[
                final_component_id
            ]

            assert (
                cm["project_work_id"]
                == r1["project_work_id"]
            )

            final_component_label = (
                cm["component_label"]
            )

            final_component_role_hint = (
                cm["human_role_hint"]
            )

        elif (
            final_decision
            == "HOLD_UNRESOLVED"
        ):

            assert (
                final_component_id
                == ""
            )

            final_component_label = ""
            final_component_role_hint = ""

        else:
            raise AssertionError(
                final_decision
            )

        pm = project_meta[
            r1["project_work_id"]
        ]

        rows.append({
            "remediation_priority_rank":
                r1[
                    "remediation_priority_rank"
                ],

            "project_work_id":
                r1[
                    "project_work_id"
                ],

            "r2_target_title":
                pm[
                    "r2_target_title"
                ],

            "r2_target_author":
                pm[
                    "r2_target_author"
                ],

            "current_ol_work_id":
                r1[
                    "current_ol_work_id"
                ],

            "edition_key":
                edition_key,

            "edition_title":
                r1[
                    "edition_title"
                ],

            "edition_subtitle":
                r1[
                    "edition_subtitle"
                ],

            "publish_date":
                r1[
                    "publish_date"
                ],

            "publishers":
                r1[
                    "publishers"
                ],

            "edition_author_keys":
                r1[
                    "edition_author_keys"
                ],

            "number_of_pages":
                r1[
                    "number_of_pages"
                ],

            "base_routing_version":
                base_version,

            "base_routing_decision":
                base[
                    "routing_decision"
                ],

            "base_component_id":
                base[
                    "component_id"
                ],

            "base_component_label":
                base[
                    "component_label"
                ],

            "base_component_role_hint":
                base[
                    "human_role_hint"
                ],

            "base_llm_confidence":
                base[
                    "llm_confidence"
                ],

            "base_llm_note":
                base[
                    "llm_note"
                ],

            "base_llm_response_id":
                base[
                    "llm_response_id"
                ],

            "base_llm_prompt_version":
                base[
                    "llm_prompt_version"
                ],

            "human_audit_case_id":
                human_case_id,

            "human_routing_decision":
                human_decision,

            "human_component_id":
                human_component_id,

            "human_confidence":
                human_confidence,

            "human_note":
                human_note,

            "human_authority_effect":
                human_effect,

            "final_routing_decision":
                final_decision,

            "final_component_id":
                final_component_id,

            "final_component_label":
                final_component_label,

            "final_component_role_hint":
                final_component_role_hint,

            "final_component_registry_version":
                "v2",

            "final_provenance":
                final_provenance,
        })

    out = pd.DataFrame(rows)

    # --------------------------------------------------------
    # Final exact QC.
    # --------------------------------------------------------

    assert len(out) == EXPECTED_ROWS

    assert out["edition_key"].is_unique

    assert set(
        out["edition_key"]
    ) == set(
        v1["edition_key"]
    )

    assert (
        out["project_work_id"].nunique()
        == EXPECTED_PROJECTS
    )

    assert (
        count_dict(
            out[
                "base_routing_version"
            ]
        )
        == {
            "v1": EXPECTED_V1_BASE_ROWS,
            "v2": EXPECTED_V2_ROWS,
        }
    )

    assert (
        count_dict(
            out[
                "final_routing_decision"
            ]
        )
        == EXPECTED_FINAL_DECISIONS
    )

    assert (
        count_dict(
            out[
                "final_provenance"
            ]
        )
        == EXPECTED_PROVENANCE
    )

    human_rows = out.loc[
        out[
            "human_audit_case_id"
        ].ne("")
    ].copy()

    assert len(
        human_rows
    ) == EXPECTED_HUMAN_ROWS

    assert (
        human_rows[
            "human_audit_case_id"
        ].is_unique
    )

    assert (
        count_dict(
            human_rows[
                "human_authority_effect"
            ]
        )
        == EXPECTED_HUMAN_EFFECT
    )

    assert int(
        out[
            "final_provenance"
        ].isin(
            [
                "llm_v1_unreviewed",
                "llm_v2_unreviewed",
            ]
        ).sum()
    ) == EXPECTED_LLM_ONLY

    assigned = out.loc[
        out[
            "final_routing_decision"
        ].eq(
            "ASSIGN_COMPONENT"
        )
    ].copy()

    assert (
        count_dict(
            assigned[
                "final_component_role_hint"
            ]
        )
        == EXPECTED_ROLE_COUNTS
    )

    holds = out.loc[
        out[
            "final_routing_decision"
        ].eq(
            "HOLD_UNRESOLVED"
        )
    ].copy()

    assert holds[
        "final_component_id"
    ].eq("").all()

    assert holds[
        "final_component_label"
    ].eq("").all()

    assert holds[
        "final_component_role_hint"
    ].eq("").all()

    # Original edition metadata remains identical to v1.
    metadata_cols = [
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
        out[
            metadata_cols
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
        v1[
            metadata_cols
        ]
        .sort_values(
            "edition_key"
        )
        .reset_index(
            drop=True
        )
        .astype(str)
    )

    assert left.equals(right)

    # --------------------------------------------------------
    # Stable order and human-authority ledger.
    # --------------------------------------------------------

    out[
        "remediation_priority_rank"
    ] = pd.to_numeric(
        out[
            "remediation_priority_rank"
        ]
    )

    out = out.sort_values(
        [
            "remediation_priority_rank",
            "project_work_id",
            "edition_key",
        ],
        kind="stable",
    ).reset_index(
        drop=True
    )

    human_rows = out.loc[
        out[
            "human_audit_case_id"
        ].ne("")
    ].copy()

    # --------------------------------------------------------
    # Summaries.
    # --------------------------------------------------------

    project_summaries = []

    for pid, g in out.groupby(
        "project_work_id",
        sort=False,
    ):

        project_summaries.append({
            "project_work_id":
                pid,

            "edition_rows":
                int(len(g)),

            "assign_component":
                int(
                    g[
                        "final_routing_decision"
                    ].eq(
                        "ASSIGN_COMPONENT"
                    ).sum()
                ),

            "hold_unresolved":
                int(
                    g[
                        "final_routing_decision"
                    ].eq(
                        "HOLD_UNRESOLVED"
                    ).sum()
                ),

            "human_authoritative_rows":
                int(
                    g[
                        "human_audit_case_id"
                    ].ne("").sum()
                ),

            "llm_only_rows":
                int(
                    g[
                        "final_provenance"
                    ].isin(
                        [
                            "llm_v1_unreviewed",
                            "llm_v2_unreviewed",
                        ]
                    ).sum()
                ),
        })

    summary = {
        "release":
            RELEASE,

        "status":
            "operational_final_edition_routing",

        "created_at":
            CREATED_AT,

        "edition_rows":
            len(out),

        "project_works":
            out[
                "project_work_id"
            ].nunique(),

        "base_routing_version_counts":
            count_dict(
                out[
                    "base_routing_version"
                ]
            ),

        "final_routing_decision_counts":
            count_dict(
                out[
                    "final_routing_decision"
                ]
            ),

        "final_provenance_counts":
            count_dict(
                out[
                    "final_provenance"
                ]
            ),

        "human_authority_effect_counts":
            count_dict(
                human_rows[
                    "human_authority_effect"
                ]
            ),

        "assigned_component_role_hint_counts":
            count_dict(
                assigned[
                    "final_component_role_hint"
                ]
            ),

        "human_authoritative_rows":
            len(human_rows),

        "llm_only_rows":
            int(
                out[
                    "final_provenance"
                ].isin(
                    [
                        "llm_v1_unreviewed",
                        "llm_v2_unreviewed",
                    ]
                ).sum()
            ),

        "project_summaries":
            project_summaries,
    }

    audit = {
        "release":
            RELEASE,

        "audit_status":
            "PASSED",

        "rows":
            len(out),

        "unique_edition_keys":
            out[
                "edition_key"
            ].nunique(),

        "project_works":
            out[
                "project_work_id"
            ].nunique(),

        "base_v1_rows":
            int(
                out[
                    "base_routing_version"
                ].eq("v1").sum()
            ),

        "base_v2_rows":
            int(
                out[
                    "base_routing_version"
                ].eq("v2").sum()
            ),

        "human_direct_rows":
            int(
                out[
                    "final_provenance"
                ].eq(
                    "human_direct_adjudication"
                ).sum()
            ),

        "human_registry_remediation_rows":
            int(
                out[
                    "final_provenance"
                ].eq(
                    "human_registry_remediation_v2"
                ).sum()
            ),

        "llm_only_rows":
            int(
                out[
                    "final_provenance"
                ].isin(
                    [
                        "llm_v1_unreviewed",
                        "llm_v2_unreviewed",
                    ]
                ).sum()
            ),

        "all_final_components_valid_in_registry_v2":
            True,

        "all_final_components_belong_to_same_project":
            True,

        "all_holds_have_blank_component":
            True,

        "original_edition_metadata_unchanged":
            True,

        "human_authority_applied_to_all_118_reviewed_rows":
            True,

        "registry_issues_resolved_through_registry_v2":
            True,

        "final_routing_decision_counts":
            count_dict(
                out[
                    "final_routing_decision"
                ]
            ),

        "final_provenance_counts":
            count_dict(
                out[
                    "final_provenance"
                ]
            ),
    }

    OUT_DIR.mkdir(
        parents=True,
    )

    atomic_tsv(
        out,
        OUT_TSV,
    )

    atomic_tsv(
        human_rows,
        OUT_HUMAN_LEDGER,
    )

    atomic_json(
        summary,
        OUT_SUMMARY,
    )

    atomic_json(
        audit,
        OUT_AUDIT,
    )

    manifest = {
        "release":
            RELEASE,

        "status":
            "operational_final_edition_routing",

        "created_at":
            CREATED_AT,

        "v1_llm_freeze_commit":
            V1_LLM_FREEZE_COMMIT,

        "human_freeze_commit":
            HUMAN_FREEZE_COMMIT,

        "registry_v2_freeze_commit":
            REGISTRY_V2_FREEZE_COMMIT,

        "v2_llm_freeze_commit":
            V2_LLM_FREEZE_COMMIT,

        "v1_v2_comparison_freeze_commit":
            V1_V2_COMPARISON_FREEZE_COMMIT,

        "semantics": [
            (
                "This is the final operational Edition-"
                "routing release for the 508 Editions "
                "inside the 17 human-SPLIT predecessor "
                "project works."
            ),
            (
                "The six registry-remediated predecessor "
                "projects use frozen LLM routing v2 as "
                "their base; the other eleven projects "
                "retain frozen LLM routing v1 as base."
            ),
            (
                "All 118 human-reviewed Edition rows are "
                "human-authoritative in the final release."
            ),
            (
                "For 112 rows with direct human ASSIGN or "
                "HOLD decisions, the human decision "
                "overrides or confirms the LLM base."
            ),
            (
                "For the six former REGISTRY_ISSUE rows, "
                "the final component is the human-added "
                "registry-v2 component; the fresh v2 LLM "
                "routing independently agreed with all six."
            ),
            (
                "The remaining 390 unreviewed rows retain "
                "their frozen operational LLM routing."
            ),
            (
                "HOLD_UNRESOLVED is preserved as explicit "
                "uncertainty and is not treated as failure."
            ),
            (
                "A routing component is an Edition-routing "
                "ontology label, not a project_work_id or "
                "source_entity_id."
            ),
            (
                "DETACH and EXCLUDE_APPARATUS are component "
                "role hints and do not themselves constitute "
                "corpus-scope decisions."
            ),
            (
                "This release does not create successor "
                "project works, source entities, lineage "
                "edges, or scope decisions."
            ),
        ],

        "inputs": {
            str(
                V1.relative_to(ROOT)
            ):
                sha256_file(V1),

            str(
                V2.relative_to(ROOT)
            ):
                sha256_file(V2),

            str(
                HUMAN.relative_to(ROOT)
            ):
                sha256_file(HUMAN),

            str(
                REGISTRY.relative_to(ROOT)
            ):
                sha256_file(REGISTRY),

            str(
                REGISTRY_CHANGES.relative_to(ROOT)
            ):
                sha256_file(
                    REGISTRY_CHANGES
                ),

            str(
                Path(__file__).relative_to(ROOT)
            ):
                sha256_file(
                    Path(__file__)
                ),
        },

        "outputs": {
            OUT_TSV.name:
                sha256_file(OUT_TSV),

            OUT_HUMAN_LEDGER.name:
                sha256_file(
                    OUT_HUMAN_LEDGER
                ),

            OUT_SUMMARY.name:
                sha256_file(
                    OUT_SUMMARY
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

    # --------------------------------------------------------
    # Console report.
    # --------------------------------------------------------

    print(
        "=== FINAL OPERATIONAL SPLIT-EDITION ROUTING V1 ==="
    )

    print(
        "edition rows:",
        len(out),
    )

    print(
        "project works:",
        out[
            "project_work_id"
        ].nunique(),
    )

    print()
    print(
        "=== BASE ROUTING VERSION ==="
    )

    print(
        out[
            "base_routing_version"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print()
    print(
        "=== FINAL ROUTING DECISIONS ==="
    )

    print(
        out[
            "final_routing_decision"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print()
    print(
        "=== FINAL PROVENANCE ==="
    )

    print(
        out[
            "final_provenance"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print()
    print(
        "=== HUMAN AUTHORITY EFFECT ==="
    )

    print(
        human_rows[
            "human_authority_effect"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print()
    print(
        "=== ASSIGNED COMPONENT ROLE HINTS ==="
    )

    print(
        assigned[
            "final_component_role_hint"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print()
    print(
        "=== PER PROJECT ==="
    )

    print(
        pd.DataFrame(
            project_summaries
        ).to_string(
            index=False
        )
    )

    print()
    print(
        "QC STATUS: PASSED"
    )


if __name__ == "__main__":
    main()
