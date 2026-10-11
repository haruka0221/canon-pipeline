#!/usr/bin/env python3

from pathlib import Path
from collections import Counter
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

HUMAN_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_human_audit_adjudication_v1"
)

HUMAN = (
    HUMAN_DIR
    / "openlibrary_r2a1_split_edition_human_audit_adjudication_v1.tsv"
)

HUMAN_MANIFEST = (
    HUMAN_DIR
    / "openlibrary_r2a1_split_edition_human_audit_adjudication_v1_manifest.json"
)

LLM_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_routing_llm_v1"
)

LLM = (
    LLM_DIR
    / "openlibrary_r2a1_split_edition_routing_llm_v1.tsv"
)

LLM_MANIFEST = (
    LLM_DIR
    / "openlibrary_r2a1_split_edition_routing_llm_v1_manifest.json"
)

REVIEW_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_human_audit_v1"
)

REVIEW_MANIFEST = (
    REVIEW_DIR
    / "openlibrary_r2a1_split_edition_human_audit_v1_manifest.json"
)

OUT_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_human_llm_comparison_v1"
)

OUT_TSV = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_human_llm_comparison_v1.tsv"
)

OUT_DISAGREEMENTS = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_human_llm_disagreements_v1.tsv"
)

OUT_SUMMARY = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_human_llm_comparison_v1_summary.json"
)

OUT_AUDIT = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_human_llm_comparison_v1_audit.json"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_human_llm_comparison_v1_manifest.json"
)


RELEASE = (
    "openlibrary-r2a1-split-edition-human-llm-comparison-v1"
)

CREATED_AT = "2026-10-11"

RAW_LLM_FREEZE_COMMIT = (
    "9d4a2d0ce50cc5335e06672732aa060d3a3be124"
)

REVIEW_SELECTION_FREEZE_COMMIT = (
    "32d95c3de27eabee635cb54e930f7c791a6822b3"
)

HUMAN_FREEZE_COMMIT = (
    "655d2e521487d4cf8e34c435ac419a86a9a353be"
)

EXPECTED_HUMAN_ROWS = 118
EXPECTED_LLM_ROWS = 508
EXPECTED_PROJECTS = 17

EXPECTED_STAGE_COUNTS = {
    "mandatory_non_high": 57,
    "mandatory_sensitive_assignment": 28,
    "high_primary_successor_sample": 3,
    "high_assign_sample": 17,
    "high_hold_sample": 13,
}

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


def reconstruct_selection_stages(
    llm,
):
    selected = set()
    stage = {}

    def add_keys(keys, label):
        for key in keys:
            if key not in selected:
                selected.add(key)
                stage[key] = label

    # Stage 1: all LOW + MEDIUM.
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

    add_keys(
        non_high[
            "edition_key"
        ].tolist(),
        "mandatory_non_high",
    )

    # Stage 2: all DETACH / EXCLUDE_APPARATUS
    # assignments not already selected.
    sensitive = llm.loc[
        (
            llm[
                "routing_decision"
            ].eq(
                "ASSIGN_COMPONENT"
            )
        )
        &
        (
            llm[
                "human_role_hint"
            ].isin(
                [
                    "DETACH",
                    "EXCLUDE_APPARATUS",
                ]
            )
        )
    ].copy()

    add_keys(
        sensitive[
            "edition_key"
        ].tolist(),
        "mandatory_sensitive_assignment",
    )

    # Stage 3: one remaining HIGH PRIMARY_SUCCESSOR_HINT
    # assignment per relevant project.
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
            (
                llm[
                    "project_work_id"
                ].eq(pid)
            )
            &
            (
                llm[
                    "routing_decision"
                ].eq(
                    "ASSIGN_COMPONENT"
                )
            )
            &
            (
                llm[
                    "human_role_hint"
                ].eq(
                    "PRIMARY_SUCCESSOR_HINT"
                )
            )
            &
            (
                llm[
                    "llm_confidence"
                ].eq(
                    "HIGH"
                )
            )
            &
            (
                ~llm[
                    "edition_key"
                ].isin(
                    selected
                )
            )
        ].copy()

        key = choose_one(
            z,
            pid,
            "high_primary_successor",
        )

        if key is not None:
            add_keys(
                [key],
                "high_primary_successor_sample",
            )

    # Stage 4: one remaining HIGH assignment
    # per project.
    for pid in sorted(
        set(
            llm[
                "project_work_id"
            ]
        )
    ):

        z = llm.loc[
            (
                llm[
                    "project_work_id"
                ].eq(pid)
            )
            &
            (
                llm[
                    "routing_decision"
                ].eq(
                    "ASSIGN_COMPONENT"
                )
            )
            &
            (
                llm[
                    "llm_confidence"
                ].eq(
                    "HIGH"
                )
            )
            &
            (
                ~llm[
                    "edition_key"
                ].isin(
                    selected
                )
            )
        ].copy()

        key = choose_one(
            z,
            pid,
            "high_assign",
        )

        if key is not None:
            add_keys(
                [key],
                "high_assign_sample",
            )

    # Stage 5: one remaining HIGH HOLD
    # per project.
    for pid in sorted(
        set(
            llm[
                "project_work_id"
            ]
        )
    ):

        z = llm.loc[
            (
                llm[
                    "project_work_id"
                ].eq(pid)
            )
            &
            (
                llm[
                    "routing_decision"
                ].eq(
                    "HOLD_UNRESOLVED"
                )
            )
            &
            (
                llm[
                    "llm_confidence"
                ].eq(
                    "HIGH"
                )
            )
            &
            (
                ~llm[
                    "edition_key"
                ].isin(
                    selected
                )
            )
        ].copy()

        key = choose_one(
            z,
            pid,
            "high_hold",
        )

        if key is not None:
            add_keys(
                [key],
                "high_hold_sample",
            )

    return (
        selected,
        stage,
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


def summarize_subset(df):
    registry = int(
        df[
            "comparison_status"
        ].eq(
            "REGISTRY_ISSUE"
        ).sum()
    )

    comparable = df.loc[
        ~df[
            "comparison_status"
        ].eq(
            "REGISTRY_ISSUE"
        )
    ].copy()

    exact = int(
        comparable[
            "comparison_status"
        ].eq(
            "EXACT_AGREEMENT"
        ).sum()
    )

    decision_disagreement = int(
        comparable[
            "comparison_status"
        ].eq(
            "DECISION_DISAGREEMENT"
        ).sum()
    )

    component_disagreement = int(
        comparable[
            "comparison_status"
        ].eq(
            "COMPONENT_DISAGREEMENT"
        ).sum()
    )

    both_assign = comparable.loc[
        (
            comparable[
                "human_routing_decision"
            ].eq(
                "ASSIGN_COMPONENT"
            )
        )
        &
        (
            comparable[
                "llm_routing_decision"
            ].eq(
                "ASSIGN_COMPONENT"
            )
        )
    ].copy()

    component_exact = int(
        (
            both_assign[
                "human_component_id"
            ]
            ==
            both_assign[
                "llm_component_id"
            ]
        ).sum()
    )

    return {
        "rows":
            int(
                len(df)
            ),

        "registry_issues":
            registry,

        "comparable_rows":
            int(
                len(
                    comparable
                )
            ),

        "exact_route_agreements":
            exact,

        "decision_disagreements":
            decision_disagreement,

        "component_disagreements":
            component_disagreement,

        "descriptive_exact_route_agreement_rate":
            (
                exact
                / len(comparable)
                if len(comparable)
                else None
            ),

        "both_assign_rows":
            int(
                len(
                    both_assign
                )
            ),

        "both_assign_component_exact":
            component_exact,

        "descriptive_component_exact_rate_among_both_assign":
            (
                component_exact
                / len(both_assign)
                if len(both_assign)
                else None
            ),

        "human_decision_counts":
            count_dict(
                df[
                    "human_routing_decision"
                ]
            ),

        "llm_decision_counts":
            count_dict(
                df[
                    "llm_routing_decision"
                ]
            ),

        "comparison_status_counts":
            count_dict(
                df[
                    "comparison_status"
                ]
            ),
    }


def main():

    required = [
        HUMAN,
        HUMAN_MANIFEST,
        LLM,
        LLM_MANIFEST,
        REVIEW_MANIFEST,
    ]

    for p in required:
        if not p.exists():
            raise FileNotFoundError(p)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory already exists: {OUT_DIR}"
        )

    human = pd.read_csv(
        HUMAN,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    llm = pd.read_csv(
        LLM,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    assert len(
        human
    ) == EXPECTED_HUMAN_ROWS

    assert len(
        llm
    ) == EXPECTED_LLM_ROWS

    assert human[
        "audit_case_id"
    ].is_unique

    assert human[
        "edition_key"
    ].is_unique

    assert llm[
        "edition_key"
    ].is_unique

    assert (
        human[
            "project_work_id"
        ].nunique()
        == EXPECTED_PROJECTS
    )

    human_manifest = json.loads(
        HUMAN_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    review_manifest = json.loads(
        REVIEW_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    llm_manifest = json.loads(
        LLM_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    assert (
        human_manifest[
            "status"
        ]
        == "frozen_human_only_adjudication"
    )

    assert (
        human_manifest[
            "review_selection_freeze_commit"
        ]
        == REVIEW_SELECTION_FREEZE_COMMIT
    )

    assert (
        human_manifest[
            "raw_llm_freeze_commit"
        ]
        == RAW_LLM_FREEZE_COMMIT
    )

    assert (
        review_manifest[
            "llm_freeze_commit"
        ]
        == RAW_LLM_FREEZE_COMMIT
    )

    assert (
        llm_manifest[
            "input_freeze_commit"
        ]
        == "83cfef1121a61de39b52cf5c91e7c0dd4ad4e7f0"
    )

    # --------------------------------------------------------
    # Reconstruct exact audit-selection stages.
    # --------------------------------------------------------

    selected, stage_map = (
        reconstruct_selection_stages(
            llm
        )
    )

    assert len(
        selected
    ) == EXPECTED_HUMAN_ROWS

    assert selected == set(
        human[
            "edition_key"
        ]
    )

    reconstructed_stage_counts = {
        stage:
            sum(
                1
                for x
                in stage_map.values()
                if x == stage
            )
        for stage
        in EXPECTED_STAGE_COUNTS
    }

    assert (
        reconstructed_stage_counts
        == EXPECTED_STAGE_COUNTS
    )

    assert (
        review_manifest[
            "counts"
        ][
            "selection_stage_new_rows"
        ]
        == EXPECTED_STAGE_COUNTS
    )

    # --------------------------------------------------------
    # Join frozen human-only results to frozen LLM results.
    # --------------------------------------------------------

    llm_selected = llm.loc[
        llm[
            "edition_key"
        ].isin(
            selected
        ),
        [
            "edition_key",
            "project_work_id",
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
        ],
    ].copy()

    llm_selected = (
        llm_selected.rename(
            columns={
                "project_work_id":
                    "llm_project_work_id",

                "routing_decision":
                    "llm_routing_decision",

                "component_id":
                    "llm_component_id",

                "component_label":
                    "llm_component_label",

                "human_role_hint":
                    "llm_component_role_hint",
            }
        )
    )

    out = human.merge(
        llm_selected,
        on="edition_key",
        how="left",
        validate="one_to_one",
    )

    assert len(
        out
    ) == EXPECTED_HUMAN_ROWS

    assert out[
        "llm_routing_decision"
    ].ne(
        ""
    ).all()

    assert (
        out[
            "project_work_id"
        ]
        ==
        out[
            "llm_project_work_id"
        ]
    ).all()

    out[
        "selection_stage"
    ] = out[
        "edition_key"
    ].map(
        stage_map
    )

    assert out[
        "selection_stage"
    ].notna().all()

    out[
        "selection_group"
    ] = out[
        "selection_stage"
    ].map(
        lambda x:
            (
                "targeted_operational_review"
                if x.startswith(
                    "mandatory_"
                )
                else
                "high_confidence_validation_sample"
            )
    )

    # --------------------------------------------------------
    # Human vs LLM comparison.
    # --------------------------------------------------------

    comparison_status = []
    decision_agreement = []
    component_agreement = []
    exact_route_agreement = []

    for r in out.itertuples(
        index=False
    ):

        if (
            r.human_routing_decision
            == "REGISTRY_ISSUE"
        ):
            comparison_status.append(
                "REGISTRY_ISSUE"
            )

            decision_agreement.append(
                ""
            )

            component_agreement.append(
                ""
            )

            exact_route_agreement.append(
                ""
            )

            continue

        same_decision = (
            r.human_routing_decision
            == r.llm_routing_decision
        )

        decision_agreement.append(
            "TRUE"
            if same_decision
            else "FALSE"
        )

        if not same_decision:

            comparison_status.append(
                "DECISION_DISAGREEMENT"
            )

            component_agreement.append(
                ""
            )

            exact_route_agreement.append(
                "FALSE"
            )

            continue

        if (
            r.human_routing_decision
            == "ASSIGN_COMPONENT"
        ):

            same_component = (
                r.human_component_id
                == r.llm_component_id
            )

            component_agreement.append(
                "TRUE"
                if same_component
                else "FALSE"
            )

            if same_component:

                comparison_status.append(
                    "EXACT_AGREEMENT"
                )

                exact_route_agreement.append(
                    "TRUE"
                )

            else:

                comparison_status.append(
                    "COMPONENT_DISAGREEMENT"
                )

                exact_route_agreement.append(
                    "FALSE"
                )

        else:
            # Both HOLD_UNRESOLVED.
            component_agreement.append(
                ""
            )

            comparison_status.append(
                "EXACT_AGREEMENT"
            )

            exact_route_agreement.append(
                "TRUE"
            )

    out[
        "decision_agreement"
    ] = decision_agreement

    out[
        "component_agreement"
    ] = component_agreement

    out[
        "exact_route_agreement"
    ] = exact_route_agreement

    out[
        "comparison_status"
    ] = comparison_status

    # Reorder the most important comparison fields toward
    # the front without discarding provenance columns.
    front = [
        "audit_case_id",
        "selection_stage",
        "selection_group",
        "remediation_priority_rank",
        "project_work_id",
        "r2_target_title",
        "r2_target_author",
        "current_ol_work_id",
        "edition_key",
        "edition_title",
        "edition_subtitle",
        "publish_date",
        "publishers",
        "number_of_pages",

        "human_routing_decision",
        "human_component_id",
        "human_component_label",
        "human_component_role_hint",
        "human_confidence",
        "human_note",

        "llm_routing_decision",
        "llm_component_id",
        "llm_component_label",
        "llm_component_role_hint",
        "llm_confidence",
        "llm_note",

        "decision_agreement",
        "component_agreement",
        "exact_route_agreement",
        "comparison_status",
    ]

    remainder = [
        c
        for c in out.columns
        if c not in front
    ]

    out = out[
        front + remainder
    ].copy()

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
            "audit_case_id",
        ],
        kind="stable",
    ).reset_index(
        drop=True
    )

    disagreements = out.loc[
        ~out[
            "comparison_status"
        ].eq(
            "EXACT_AGREEMENT"
        )
    ].copy()

    OUT_DIR.mkdir(
        parents=True,
    )

    atomic_tsv(
        out,
        OUT_TSV,
    )

    atomic_tsv(
        disagreements,
        OUT_DISAGREEMENTS,
    )

    # --------------------------------------------------------
    # Summary: descriptive agreement only.
    # This audit sample is intentionally enriched for
    # uncertain and policy-sensitive cases.
    # --------------------------------------------------------

    overall = summarize_subset(
        out
    )

    by_selection_group = {}

    for group, g in out.groupby(
        "selection_group",
        sort=True,
    ):
        by_selection_group[
            str(group)
        ] = summarize_subset(
            g
        )

    by_selection_stage = {}

    for stage, g in out.groupby(
        "selection_stage",
        sort=True,
    ):
        by_selection_stage[
            str(stage)
        ] = summarize_subset(
            g
        )

    by_llm_confidence = {}

    for conf, g in out.groupby(
        "llm_confidence",
        sort=True,
    ):
        by_llm_confidence[
            str(conf)
        ] = summarize_subset(
            g
        )

    by_project = {}

    for pid, g in out.groupby(
        "project_work_id",
        sort=True,
    ):
        by_project[
            str(pid)
        ] = summarize_subset(
            g
        )

    decision_crosstab = (
        pd.crosstab(
            out[
                "human_routing_decision"
            ],
            out[
                "llm_routing_decision"
            ],
            dropna=False,
        )
    )

    decision_matrix = {
        str(human_decision): {
            str(llm_decision):
                int(
                    decision_crosstab.loc[
                        human_decision,
                        llm_decision,
                    ]
                )
            for llm_decision
            in decision_crosstab.columns
        }
        for human_decision
        in decision_crosstab.index
    }

    summary = {
        "release":
            RELEASE,

        "status":
            "descriptive_unblinded_comparison",

        "created_at":
            CREATED_AT,

        "interpretation_warning": (
            "The 118-row human audit set is not a simple "
            "random sample of all 508 Editions. It "
            "deliberately oversamples LOW/MEDIUM LLM "
            "confidence and policy-sensitive assignments. "
            "Agreement rates below are descriptive for "
            "the selected audit strata and must not be "
            "reported as population accuracy."
        ),

        "overall":
            overall,

        "decision_crosstab_human_by_llm":
            decision_matrix,

        "by_selection_group":
            by_selection_group,

        "by_selection_stage":
            by_selection_stage,

        "by_llm_confidence":
            by_llm_confidence,

        "by_project":
            by_project,
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

        "human_rows":
            len(
                human
            ),

        "llm_rows":
            len(
                llm
            ),

        "comparison_rows":
            len(
                out
            ),

        "unique_audit_case_ids":
            out[
                "audit_case_id"
            ].nunique(),

        "unique_edition_keys":
            out[
                "edition_key"
            ].nunique(),

        "project_works":
            out[
                "project_work_id"
            ].nunique(),

        "exact_human_llm_join":
            True,

        "project_work_ids_match":
            True,

        "selection_set_exactly_reconstructed":
            True,

        "selection_stage_counts":
            reconstructed_stage_counts,

        "selection_stage_counts_match_frozen_manifest":
            True,

        "comparison_status_counts":
            count_dict(
                out[
                    "comparison_status"
                ]
            ),

        "disagreement_rows_including_registry_issues":
            len(
                disagreements
            ),

        "human_frozen_before_unblinding":
            True,

        "population_accuracy_claim_permitted":
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
            "descriptive_unblinded_comparison",

        "created_at":
            CREATED_AT,

        "raw_llm_freeze_commit":
            RAW_LLM_FREEZE_COMMIT,

        "review_selection_freeze_commit":
            REVIEW_SELECTION_FREEZE_COMMIT,

        "human_freeze_commit":
            HUMAN_FREEZE_COMMIT,

        "semantics": [
            (
                "Human decisions were frozen before this "
                "row-level unblinding comparison."
            ),
            (
                "REGISTRY_ISSUE rows are not counted as "
                "route agreements or disagreements because "
                "the human reviewer judged the fixed "
                "component ontology itself inadequate."
            ),
            (
                "For ASSIGN_COMPONENT rows, exact route "
                "agreement requires the same component_id."
            ),
            (
                "Two HOLD_UNRESOLVED decisions count as "
                "exact route agreement."
            ),
            (
                "The audit set deliberately oversamples "
                "non-HIGH LLM decisions and sensitive "
                "component assignments."
            ),
            (
                "Reported agreement is descriptive of "
                "selected audit strata and is not an "
                "estimate of accuracy across all 508 "
                "Edition rows."
            ),
            (
                "This comparison does not mutate either "
                "the frozen LLM routing or the frozen "
                "human adjudication."
            ),
        ],

        "inputs": {
            str(
                HUMAN.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    HUMAN
                ),

            str(
                HUMAN_MANIFEST.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    HUMAN_MANIFEST
                ),

            str(
                LLM.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    LLM
                ),

            str(
                LLM_MANIFEST.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    LLM_MANIFEST
                ),

            str(
                REVIEW_MANIFEST.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    REVIEW_MANIFEST
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

            OUT_DISAGREEMENTS.name:
                sha256_file(
                    OUT_DISAGREEMENTS
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
        "=== HUMAN–LLM UNBLINDING COMPARISON V1 ==="
    )

    print(
        "rows:",
        len(
            out
        ),
    )

    print(
        "project works:",
        out[
            "project_work_id"
        ].nunique(),
    )

    print()
    print(
        "=== SELECTION STAGES ==="
    )

    print(
        out[
            "selection_stage"
        ]
        .value_counts()
        .reindex(
            list(
                EXPECTED_STAGE_COUNTS.keys()
            )
        )
        .to_string()
    )

    print()
    print(
        "=== COMPARISON STATUS ==="
    )

    print(
        out[
            "comparison_status"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print()
    print(
        "=== HUMAN x LLM DECISION ==="
    )

    print(
        pd.crosstab(
            out[
                "human_routing_decision"
            ],
            out[
                "llm_routing_decision"
            ],
        ).to_string()
    )

    print()
    print(
        "=== OVERALL DESCRIPTIVE AGREEMENT ==="
    )

    print(
        "comparable rows:",
        overall[
            "comparable_rows"
        ],
    )

    print(
        "exact route agreements:",
        overall[
            "exact_route_agreements"
        ],
    )

    if (
        overall[
            "descriptive_exact_route_agreement_rate"
        ]
        is not None
    ):
        print(
            "descriptive exact-route agreement:",
            f"{100 * overall['descriptive_exact_route_agreement_rate']:.3f}%",
        )

    print(
        "both ASSIGN:",
        overall[
            "both_assign_rows"
        ],
    )

    print(
        "exact component matches among both ASSIGN:",
        overall[
            "both_assign_component_exact"
        ],
    )

    if (
        overall[
            "descriptive_component_exact_rate_among_both_assign"
        ]
        is not None
    ):
        print(
            "descriptive component agreement among both ASSIGN:",
            f"{100 * overall['descriptive_component_exact_rate_among_both_assign']:.3f}%",
        )

    print()
    print(
        "=== BY SELECTION GROUP ==="
    )

    for group in sorted(
        by_selection_group
    ):
        x = (
            by_selection_group[
                group
            ]
        )

        rate = (
            x[
                "descriptive_exact_route_agreement_rate"
            ]
        )

        rate_text = (
            "NA"
            if rate is None
            else f"{100 * rate:.3f}%"
        )

        print(
            group,
            "rows=",
            x["rows"],
            "registry=",
            x["registry_issues"],
            "comparable=",
            x["comparable_rows"],
            "exact=",
            x["exact_route_agreements"],
            "rate=",
            rate_text,
        )

    print()
    print(
        "=== BY LLM CONFIDENCE ==="
    )

    for conf in [
        "HIGH",
        "MEDIUM",
        "LOW",
    ]:
        if conf not in (
            by_llm_confidence
        ):
            continue

        x = (
            by_llm_confidence[
                conf
            ]
        )

        rate = (
            x[
                "descriptive_exact_route_agreement_rate"
            ]
        )

        rate_text = (
            "NA"
            if rate is None
            else f"{100 * rate:.3f}%"
        )

        print(
            conf,
            "rows=",
            x["rows"],
            "registry=",
            x["registry_issues"],
            "comparable=",
            x["comparable_rows"],
            "exact=",
            x["exact_route_agreements"],
            "rate=",
            rate_text,
        )

    print()
    print(
        "=== NON-EXACT CASES BY PROJECT ==="
    )

    if len(
        disagreements
    ):
        print(
            disagreements.groupby(
                [
                    "project_work_id",
                    "r2_target_title",
                    "comparison_status",
                ]
            )
            .size()
            .rename(
                "rows"
            )
            .reset_index()
            .to_string(
                index=False
            )
        )
    else:
        print("[none]")

    print()
    print(
        "IMPORTANT: agreement rates are descriptive "
        "for the selected audit strata, not population "
        "accuracy across all 508 Editions."
    )

    print()
    print(
        "QC STATUS: PASSED"
    )


if __name__ == "__main__":
    main()
