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

REGISTRY_CHANGES = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_component_registry_v2"
    / "openlibrary_r2a1_split_component_registry_v2_changes.tsv"
)

OUT_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_routing_v1_v2_comparison_v1"
)

OUT_ALL = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_v1_v2_comparison_v1.tsv"
)

OUT_CHANGED = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_v1_v2_changed_v1.tsv"
)

OUT_REGISTRY = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_registry_issue_resolution_v1.tsv"
)

OUT_HUMAN = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_human_v2_comparison_v1.tsv"
)

OUT_SUMMARY = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_v1_v2_comparison_v1_summary.json"
)

OUT_AUDIT = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_v1_v2_comparison_v1_audit.json"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_v1_v2_comparison_v1_manifest.json"
)


RELEASE = (
    "openlibrary-r2a1-split-edition-routing-v1-v2-comparison-v1"
)

CREATED_AT = "2026-10-11"

V1_FREEZE_COMMIT = (
    "9d4a2d0ce50cc5335e06672732aa060d3a3be124"
)

HUMAN_FREEZE_COMMIT = (
    "655d2e521487d4cf8e34c435ac419a86a9a353be"
)

REGISTRY_V2_FREEZE_COMMIT = (
    "bbb190bd6f47eda96981a4434da00935bf2a818f"
)

V2_INPUT_FREEZE_COMMIT = (
    "107b65881276075b2e8f5ef4467d547f9ac07265"
)

V2_METHODOLOGY_FIX_COMMIT = (
    "df1cba79811d89d618c603fcceeebcbdbebabc03"
)

V2_ROUTING_FREEZE_COMMIT = (
    "de464605eaf4281ab60a1f51706ab5c7245090ac"
)

EXPECTED_V1_ROWS = 508
EXPECTED_V2_ROWS = 191
EXPECTED_AFFECTED_PROJECTS = 6
EXPECTED_HUMAN_ROWS_IN_AFFECTED_PROJECTS = 44
EXPECTED_REGISTRY_ISSUES = 6


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
    tmp = path.with_name(path.name + ".tmp")

    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    os.replace(tmp, path)


def atomic_json(obj, path):
    tmp = path.with_name(path.name + ".tmp")

    tmp.write_text(
        json.dumps(
            obj,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    os.replace(tmp, path)


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

    changes = pd.read_csv(
        REGISTRY_CHANGES,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    assert len(v1) == EXPECTED_V1_ROWS
    assert len(v2) == EXPECTED_V2_ROWS

    assert v1["edition_key"].is_unique
    assert v2["edition_key"].is_unique
    assert human["edition_key"].is_unique

    affected_projects = set(
        v2["project_work_id"]
    )

    assert (
        len(affected_projects)
        == EXPECTED_AFFECTED_PROJECTS
    )

    v1_sub = v1.loc[
        v1[
            "project_work_id"
        ].isin(
            affected_projects
        )
    ].copy()

    assert len(v1_sub) == EXPECTED_V2_ROWS

    assert set(
        v1_sub["edition_key"]
    ) == set(
        v2["edition_key"]
    )

    # --------------------------------------------------------
    # Exact v1-v2 join.
    # --------------------------------------------------------

    base_cols = [
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
    ]

    for col in [
        c
        for c in base_cols
        if c != "edition_key"
    ]:
        a = (
            v1_sub[
                ["edition_key", col]
            ]
            .set_index("edition_key")[col]
            .sort_index()
        )

        b = (
            v2[
                ["edition_key", col]
            ]
            .set_index("edition_key")[col]
            .sort_index()
        )

        assert a.equals(b), col

    v1_route = v1_sub[
        [
            "edition_key",
            "routing_decision",
            "component_id",
            "component_label",
            "human_role_hint",
            "llm_confidence",
            "llm_note",
            "llm_response_id",
            "llm_prompt_version",
        ]
    ].rename(
        columns={
            "routing_decision":
                "v1_routing_decision",
            "component_id":
                "v1_component_id",
            "component_label":
                "v1_component_label",
            "human_role_hint":
                "v1_component_role_hint",
            "llm_confidence":
                "v1_llm_confidence",
            "llm_note":
                "v1_llm_note",
            "llm_response_id":
                "v1_llm_response_id",
            "llm_prompt_version":
                "v1_llm_prompt_version",
        }
    )

    v2_route = v2[
        base_cols
        + [
            "routing_decision",
            "component_id",
            "component_label",
            "human_role_hint",
            "llm_confidence",
            "llm_note",
            "llm_response_id",
            "llm_prompt_version",
        ]
    ].rename(
        columns={
            "routing_decision":
                "v2_routing_decision",
            "component_id":
                "v2_component_id",
            "component_label":
                "v2_component_label",
            "human_role_hint":
                "v2_component_role_hint",
            "llm_confidence":
                "v2_llm_confidence",
            "llm_note":
                "v2_llm_note",
            "llm_response_id":
                "v2_llm_response_id",
            "llm_prompt_version":
                "v2_llm_prompt_version",
        }
    )

    out = v2_route.merge(
        v1_route,
        on="edition_key",
        how="left",
        validate="one_to_one",
    )

    assert len(out) == EXPECTED_V2_ROWS

    # --------------------------------------------------------
    # Change classification.
    # --------------------------------------------------------

    change_status = []

    for r in out.itertuples(index=False):

        if (
            r.v1_routing_decision
            == r.v2_routing_decision
            and
            r.v1_component_id
            == r.v2_component_id
        ):
            status = "UNCHANGED"

        elif (
            r.v1_routing_decision
            == "HOLD_UNRESOLVED"
            and
            r.v2_routing_decision
            == "ASSIGN_COMPONENT"
        ):
            status = "HOLD_TO_ASSIGN"

        elif (
            r.v1_routing_decision
            == "ASSIGN_COMPONENT"
            and
            r.v2_routing_decision
            == "HOLD_UNRESOLVED"
        ):
            status = "ASSIGN_TO_HOLD"

        elif (
            r.v1_routing_decision
            == "ASSIGN_COMPONENT"
            and
            r.v2_routing_decision
            == "ASSIGN_COMPONENT"
            and
            r.v1_component_id
            != r.v2_component_id
        ):
            status = "ASSIGN_COMPONENT_CHANGED"

        else:
            status = "OTHER_CHANGE"

        change_status.append(status)

    out["v1_v2_change_status"] = change_status

    # --------------------------------------------------------
    # New v2 components.
    # --------------------------------------------------------

    added_components = set(
        changes.loc[
            changes[
                "change_type"
            ].eq(
                "ADD_COMPONENT"
            ),
            "component_id",
        ]
    )

    assert len(added_components) == 6

    out[
        "v2_uses_new_component"
    ] = out[
        "v2_component_id"
    ].isin(
        added_components
    )

    # --------------------------------------------------------
    # Join human review where available.
    # --------------------------------------------------------

    human_cols = human[
        [
            "audit_case_id",
            "edition_key",
            "human_routing_decision",
            "human_component_id",
            "human_component_label",
            "human_component_role_hint",
            "human_confidence",
            "human_note",
        ]
    ].copy()

    out = out.merge(
        human_cols,
        on="edition_key",
        how="left",
        validate="one_to_one",
    )

    for col in [
        "audit_case_id",
        "human_routing_decision",
        "human_component_id",
        "human_component_label",
        "human_component_role_hint",
        "human_confidence",
        "human_note",
    ]:
        out[col] = out[col].fillna("")

    reviewed = out.loc[
        out[
            "audit_case_id"
        ].ne("")
    ].copy()

    assert (
        len(reviewed)
        == EXPECTED_HUMAN_ROWS_IN_AFFECTED_PROJECTS
    )

    human_v2_status = []

    for r in reviewed.itertuples(
        index=False
    ):

        if (
            r.human_routing_decision
            == "REGISTRY_ISSUE"
        ):
            status = "REGISTRY_ISSUE"

        elif (
            r.human_routing_decision
            != r.v2_routing_decision
        ):
            status = "DECISION_DISAGREEMENT"

        elif (
            r.human_routing_decision
            == "ASSIGN_COMPONENT"
            and
            r.human_component_id
            != r.v2_component_id
        ):
            status = "COMPONENT_DISAGREEMENT"

        else:
            status = "EXACT_AGREEMENT"

        human_v2_status.append(status)

    reviewed[
        "human_v2_comparison_status"
    ] = human_v2_status

    status_map = dict(
        zip(
            reviewed["edition_key"],
            reviewed[
                "human_v2_comparison_status"
            ],
        )
    )

    out[
        "human_v2_comparison_status"
    ] = out[
        "edition_key"
    ].map(
        status_map
    ).fillna("")

    # --------------------------------------------------------
    # Resolve six registry-issue cases against the v2 registry.
    #
    # Each REGISTRY_ISSUE has exactly one newly added component
    # whose basis_case_id is that human audit case.
    # --------------------------------------------------------

    issue_human = human.loc[
        human[
            "human_routing_decision"
        ].eq(
            "REGISTRY_ISSUE"
        )
        &
        human[
            "project_work_id"
        ].isin(
            affected_projects
        )
    ].copy()

    assert (
        len(issue_human)
        == EXPECTED_REGISTRY_ISSUES
    )

    added_by_case = changes.loc[
        changes[
            "change_type"
        ].eq(
            "ADD_COMPONENT"
        )
        &
        changes[
            "basis_case_id"
        ].ne("")
    ][
        [
            "basis_case_id",
            "component_id",
        ]
    ].copy()

    assert added_by_case[
        "basis_case_id"
    ].is_unique

    issue = issue_human.merge(
        added_by_case,
        left_on="audit_case_id",
        right_on="basis_case_id",
        how="left",
        validate="one_to_one",
    ).rename(
        columns={
            "component_id":
                "expected_v2_component_id",
        }
    )

    issue = issue.merge(
        v2[
            [
                "edition_key",
                "routing_decision",
                "component_id",
                "component_label",
                "llm_confidence",
                "llm_note",
            ]
        ].rename(
            columns={
                "routing_decision":
                    "v2_routing_decision",
                "component_id":
                    "v2_component_id",
                "component_label":
                    "v2_component_label",
                "llm_confidence":
                    "v2_llm_confidence",
                "llm_note":
                    "v2_llm_note",
            }
        ),
        on="edition_key",
        how="left",
        validate="one_to_one",
    )

    issue[
        "registry_issue_resolution_status"
    ] = issue.apply(
        lambda r:
            (
                "RESOLVED_AS_EXPECTED"
                if (
                    r[
                        "v2_routing_decision"
                    ]
                    == "ASSIGN_COMPONENT"
                    and
                    r[
                        "v2_component_id"
                    ]
                    == r[
                        "expected_v2_component_id"
                    ]
                )
                else
                "NOT_RESOLVED_AS_EXPECTED"
            ),
        axis=1,
    )

    # --------------------------------------------------------
    # Stable ordering.
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

    changed = out.loc[
        ~out[
            "v1_v2_change_status"
        ].eq(
            "UNCHANGED"
        )
    ].copy()

    reviewed = reviewed.sort_values(
        [
            "remediation_priority_rank",
            "project_work_id",
            "edition_key",
        ],
        kind="stable",
    ).reset_index(
        drop=True
    )

    issue = issue.sort_values(
        [
            "remediation_priority_rank",
            "project_work_id",
            "edition_key",
        ],
        kind="stable",
    ).reset_index(
        drop=True
    )

    # --------------------------------------------------------
    # Summary.
    # --------------------------------------------------------

    per_project = []

    for pid, g in out.groupby(
        "project_work_id",
        sort=False,
    ):
        per_project.append({
            "project_work_id":
                pid,

            "edition_rows":
                int(len(g)),

            "unchanged":
                int(
                    g[
                        "v1_v2_change_status"
                    ].eq(
                        "UNCHANGED"
                    ).sum()
                ),

            "hold_to_assign":
                int(
                    g[
                        "v1_v2_change_status"
                    ].eq(
                        "HOLD_TO_ASSIGN"
                    ).sum()
                ),

            "assign_to_hold":
                int(
                    g[
                        "v1_v2_change_status"
                    ].eq(
                        "ASSIGN_TO_HOLD"
                    ).sum()
                ),

            "assign_component_changed":
                int(
                    g[
                        "v1_v2_change_status"
                    ].eq(
                        "ASSIGN_COMPONENT_CHANGED"
                    ).sum()
                ),

            "new_component_assignments":
                int(
                    g[
                        "v2_uses_new_component"
                    ].sum()
                ),
        })

    new_component_counts = (
        out.loc[
            out[
                "v2_uses_new_component"
            ]
        ][
            "v2_component_id"
        ]
        .value_counts()
        .sort_index()
    )

    summary = {
        "release":
            RELEASE,

        "status":
            "descriptive_v1_v2_rerouting_comparison",

        "created_at":
            CREATED_AT,

        "edition_rows":
            len(out),

        "project_works":
            out[
                "project_work_id"
            ].nunique(),

        "v1_v2_change_counts":
            count_dict(
                out[
                    "v1_v2_change_status"
                ]
            ),

        "new_component_assignment_counts":
            {
                str(k): int(v)
                for k, v
                in new_component_counts.items()
            },

        "human_reviewed_rows_in_affected_projects":
            len(reviewed),

        "human_v2_comparison_counts":
            count_dict(
                reviewed[
                    "human_v2_comparison_status"
                ]
            ),

        "registry_issue_resolution_counts":
            count_dict(
                issue[
                    "registry_issue_resolution_status"
                ]
            ),

        "project_summaries":
            per_project,

        "interpretation": [
            (
                "v1-v2 differences describe the effect of "
                "human-remediated component-registry v2 "
                "plus a fresh LLM rerun; they are not an "
                "independent estimate of model accuracy."
            ),
            (
                "The six registry-issue cases are checked "
                "against the newly added component whose "
                "basis_case_id is that human review case."
            ),
            (
                "Human audit decisions remain frozen and "
                "are not overwritten by v2 LLM routing."
            ),
        ],
    }

    audit = {
        "release":
            RELEASE,

        "audit_status":
            "PASSED",

        "v1_rows":
            len(v1),

        "v2_rows":
            len(v2),

        "affected_v1_rows":
            len(v1_sub),

        "comparison_rows":
            len(out),

        "exact_edition_set_match":
            True,

        "original_metadata_unchanged":
            True,

        "affected_project_works":
            len(
                affected_projects
            ),

        "human_reviewed_rows":
            len(reviewed),

        "registry_issue_rows":
            len(issue),

        "registry_issue_cases_all_have_added_component":
            bool(
                issue[
                    "expected_v2_component_id"
                ].ne("").all()
            ),

        "registry_issue_resolution_status_counts":
            count_dict(
                issue[
                    "registry_issue_resolution_status"
                ]
            ),

        "change_status_counts":
            count_dict(
                out[
                    "v1_v2_change_status"
                ]
            ),
    }

    OUT_DIR.mkdir(
        parents=True,
    )

    atomic_tsv(
        out,
        OUT_ALL,
    )

    atomic_tsv(
        changed,
        OUT_CHANGED,
    )

    atomic_tsv(
        issue,
        OUT_REGISTRY,
    )

    atomic_tsv(
        reviewed,
        OUT_HUMAN,
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
            "descriptive_v1_v2_rerouting_comparison",

        "created_at":
            CREATED_AT,

        "v1_freeze_commit":
            V1_FREEZE_COMMIT,

        "human_freeze_commit":
            HUMAN_FREEZE_COMMIT,

        "registry_v2_freeze_commit":
            REGISTRY_V2_FREEZE_COMMIT,

        "v2_input_freeze_commit":
            V2_INPUT_FREEZE_COMMIT,

        "v2_methodology_fix_commit":
            V2_METHODOLOGY_FIX_COMMIT,

        "v2_routing_freeze_commit":
            V2_ROUTING_FREEZE_COMMIT,

        "semantics": [
            (
                "This artifact compares the frozen v1 "
                "and v2 LLM routing only for the six "
                "registry-remediated predecessor projects."
            ),
            (
                "The other eleven split projects and "
                "their 317 Editions are outside this "
                "comparison because their registry did "
                "not change and they were not rerun."
            ),
            (
                "No routing, human adjudication, "
                "component registry, project-work "
                "identity, lineage, or scope decision is "
                "mutated by this comparison."
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
            OUT_ALL.name:
                sha256_file(OUT_ALL),

            OUT_CHANGED.name:
                sha256_file(OUT_CHANGED),

            OUT_REGISTRY.name:
                sha256_file(OUT_REGISTRY),

            OUT_HUMAN.name:
                sha256_file(OUT_HUMAN),

            OUT_SUMMARY.name:
                sha256_file(OUT_SUMMARY),

            OUT_AUDIT.name:
                sha256_file(OUT_AUDIT),
        },
    }

    atomic_json(
        manifest,
        OUT_MANIFEST,
    )

    # --------------------------------------------------------
    # Console.
    # --------------------------------------------------------

    print(
        "=== V1 -> V2 ROUTING COMPARISON ==="
    )

    print(
        "comparison rows:",
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
        "=== CHANGE STATUS ==="
    )

    print(
        out[
            "v1_v2_change_status"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print()
    print(
        "=== NEW COMPONENT ASSIGNMENTS ==="
    )

    print(
        new_component_counts.to_string()
    )

    print()
    print(
        "=== REGISTRY ISSUE RESOLUTION ==="
    )

    print(
        issue[
            [
                "audit_case_id",
                "project_work_id",
                "edition_key",
                "expected_v2_component_id",
                "v2_component_id",
                "v2_llm_confidence",
                "registry_issue_resolution_status",
            ]
        ].to_string(
            index=False
        )
    )

    print()
    print(
        "=== HUMAN REVIEWED ROWS IN 6 PROJECTS ==="
    )

    print(
        reviewed[
            "human_v2_comparison_status"
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
            per_project
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
