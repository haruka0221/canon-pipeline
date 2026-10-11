#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

RISK = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_diagnostic_v1"
    / "openlibrary_r2a1_target_identity_risk_packet_v1.tsv"
)

LLM = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_llm_v1"
    / "openlibrary_r2a1_target_identity_llm_v1.tsv"
)

HUMAN = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_human_adjudication_v1"
    / "openlibrary_r2a1_target_identity_human_adjudication_v1.tsv"
)

OUT_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_pair_impact_v1"
)

SOURCE_OUT = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_pair_impact_source_record_v1.tsv"
)

PROJECT_OUT = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_pair_impact_project_v1.tsv"
)

REVIEWED_DISAGREE_OUT = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_pair_impact_reviewed_entity_disagreements_v1.tsv"
)

SUMMARY = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_pair_impact_v1_summary.json"
)

MANIFEST = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_pair_impact_v1_manifest.json"
)


RELEASE = (
    "openlibrary-r2a1-target-identity-pair-impact-v1"
)

BASELINE_R2A1_PAIRS = 290_480
EXPECTED_SOURCE_RECORDS = 48
EXPECTED_PROJECT_WORKS = 47
EXPECTED_RISK_PAIR_MASS = 102_128

PROJECT_STATUS_ORDER = [
    "COHERENT_SINGLE_WORK",
    "COHERENT_COLLECTION",
    "HETEROGENEOUS_CLUSTER",
    "NONWORK_OR_HEADING_ARTIFACT",
    "UNCERTAIN",
    "MULTI_RECORD_CONFLICT",
]

EXPECTED_STATUS = {
    "COHERENT_SINGLE_WORK": {
        "works": 5,
        "pairs": 605,
    },
    "COHERENT_COLLECTION": {
        "works": 19,
        "pairs": 28_984,
    },
    "HETEROGENEOUS_CLUSTER": {
        "works": 19,
        "pairs": 67_244,
    },
    "NONWORK_OR_HEADING_ARTIFACT": {
        "works": 0,
        "pairs": 0,
    },
    "UNCERTAIN": {
        "works": 3,
        "pairs": 3_410,
    },
    "MULTI_RECORD_CONFLICT": {
        "works": 1,
        "pairs": 1_885,
    },
}

EXPECTED_HUMAN_REVIEWED_PROJECT_PAIR_MASS = 29_528
EXPECTED_REVIEWED_ENTITY_DISAGREEMENT_PAIR_MASS = 731


def sha256_file(path):
    h = hashlib.sha256()

    with Path(path).open("rb") as f:
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


def joined_values(series):
    vals = sorted(
        {
            str(x)
            for x in series
            if str(x) != ""
        }
    )

    return " || ".join(vals)


def main():

    for p in [
        RISK,
        LLM,
        HUMAN,
    ]:
        if not p.exists():
            raise FileNotFoundError(p)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory exists: {OUT_DIR}"
        )

    risk = pd.read_csv(
        RISK,
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

    human = pd.read_csv(
        HUMAN,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    if len(risk) != EXPECTED_SOURCE_RECORDS:
        raise RuntimeError(
            f"Expected {EXPECTED_SOURCE_RECORDS} risk rows; "
            f"found {len(risk)}"
        )

    if len(llm) != EXPECTED_SOURCE_RECORDS:
        raise RuntimeError(
            f"Expected {EXPECTED_SOURCE_RECORDS} LLM rows; "
            f"found {len(llm)}"
        )

    if not llm[
        "current_ol_work_id"
    ].is_unique:
        raise RuntimeError(
            "LLM current_ol_work_id is not unique"
        )

    if not human[
        "current_ol_work_id"
    ].is_unique:
        raise RuntimeError(
            "Human current_ol_work_id is not unique"
        )

    risk[
        "pair_count"
    ] = pd.to_numeric(
        risk[
            "pair_count"
        ],
        errors="raise",
    )

    # --------------------------------------------------
    # Source-record level: 48 OL records.
    # --------------------------------------------------

    source = (
        risk.merge(
            llm[
                [
                    "project_work_id",
                    "current_ol_work_id",
                    "r2_target_title",
                    "r2_target_author",
                    "llm_entity_status",
                    "llm_content_type",
                    "llm_date_window_assessment",
                    "llm_confidence",
                    "llm_note",
                ]
            ],
            on=[
                "project_work_id",
                "current_ol_work_id",
                "r2_target_title",
                "r2_target_author",
            ],
            how="left",
            validate="one_to_one",
        )
        .merge(
            human[
                [
                    "current_ol_work_id",
                    "human_entity_status",
                    "human_content_type",
                    "human_date_window_assessment",
                    "human_confidence",
                    "human_note",
                ]
            ],
            on="current_ol_work_id",
            how="left",
            validate="one_to_one",
        )
    )

    human_cols = [
        "human_entity_status",
        "human_content_type",
        "human_date_window_assessment",
        "human_confidence",
        "human_note",
    ]

    for c in human_cols:
        source[c] = (
            source[c]
            .fillna("")
        )

    source[
        "human_reviewed"
    ] = source[
        "human_entity_status"
    ].ne("")

    source[
        "entity_exact_match_if_reviewed"
    ] = ""

    m = source[
        "human_reviewed"
    ]

    source.loc[
        m,
        "entity_exact_match_if_reviewed",
    ] = (
        source.loc[
            m,
            "llm_entity_status",
        ]
        .eq(
            source.loc[
                m,
                "human_entity_status",
            ]
        )
        .map(
            {
                True: "TRUE",
                False: "FALSE",
            }
        )
    )

    if source[
        "llm_entity_status"
    ].eq("").any():
        raise RuntimeError(
            "Missing LLM entity status after merge"
        )

    # --------------------------------------------------
    # Collapse 48 OL source records to 47 project works.
    #
    # pair_count belongs to project_work_id × OA Work
    # retrieval mass. It is therefore counted ONCE per
    # project_work_id, even where multiple OL records
    # resolve to one project work.
    # --------------------------------------------------

    project_rows = []

    for project_work_id, g in source.groupby(
        "project_work_id",
        sort=False,
    ):

        pair_counts = sorted(
            set(
                g[
                    "pair_count"
                ].tolist()
            )
        )

        if len(pair_counts) != 1:
            raise RuntimeError(
                f"{project_work_id}: multiple pair_count values: "
                f"{pair_counts}"
            )

        pairsets = sorted(
            set(
                g[
                    "pairset_sha256"
                ].tolist()
            )
        )

        if len(pairsets) != 1:
            raise RuntimeError(
                f"{project_work_id}: multiple pairset hashes"
            )

        llm_entity_states = sorted(
            set(
                g[
                    "llm_entity_status"
                ].tolist()
            )
        )

        if len(
            llm_entity_states
        ) == 1:
            project_status = (
                llm_entity_states[0]
            )
        else:
            project_status = (
                "MULTI_RECORD_CONFLICT"
            )

        reviewed = g.loc[
            g[
                "human_reviewed"
            ]
        ]

        reviewed_entity_statuses = (
            sorted(
                set(
                    reviewed[
                        "human_entity_status"
                    ].tolist()
                )
            )
        )

        disagreement_n = int(
            (
                reviewed[
                    "llm_entity_status"
                ]
                != reviewed[
                    "human_entity_status"
                ]
            ).sum()
        )

        project_rows.append(
            {
                "project_work_id":
                    project_work_id,

                "r2_target_title":
                    joined_values(
                        g[
                            "r2_target_title"
                        ]
                    ),

                "r2_target_author":
                    joined_values(
                        g[
                            "r2_target_author"
                        ]
                    ),

                "diagnostic_type":
                    joined_values(
                        g[
                            "diagnostic_type"
                        ]
                    ),

                "pair_count":
                    pair_counts[0],

                "pairset_sha256":
                    pairsets[0],

                "source_ol_record_count":
                    len(g),

                "current_ol_work_ids":
                    joined_values(
                        g[
                            "current_ol_work_id"
                        ]
                    ),

                "llm_source_entity_statuses":
                    " || ".join(
                        llm_entity_states
                    ),

                "llm_project_entity_status":
                    project_status,

                "human_reviewed_source_record_count":
                    len(reviewed),

                "human_review_coverage":
                    (
                        f"{len(reviewed)}/{len(g)}"
                    ),

                "human_entity_statuses_reviewed":
                    " || ".join(
                        reviewed_entity_statuses
                    ),

                "reviewed_entity_disagreement_source_records":
                    disagreement_n,
            }
        )

    project = pd.DataFrame(
        project_rows
    )

    if len(
        project
    ) != EXPECTED_PROJECT_WORKS:
        raise RuntimeError(
            f"Expected {EXPECTED_PROJECT_WORKS} project works; "
            f"found {len(project)}"
        )

    if not project[
        "project_work_id"
    ].is_unique:
        raise RuntimeError(
            "Project table is not unique by project_work_id"
        )

    risk_pair_mass = int(
        project[
            "pair_count"
        ].sum()
    )

    if (
        risk_pair_mass
        != EXPECTED_RISK_PAIR_MASS
    ):
        raise RuntimeError(
            f"Risk pair mass {risk_pair_mass}; "
            f"expected {EXPECTED_RISK_PAIR_MASS}"
        )

    # --------------------------------------------------
    # Project-level LLM status impact.
    # --------------------------------------------------

    status_summary = {}

    for status in PROJECT_STATUS_ORDER:

        g = project.loc[
            project[
                "llm_project_entity_status"
            ].eq(
                status
            )
        ]

        works = int(
            len(g)
        )

        pairs = int(
            g[
                "pair_count"
            ].sum()
        )

        status_summary[
            status
        ] = {
            "project_works":
                works,

            "pair_mass":
                pairs,

            "share_of_47_project_works":
                (
                    works
                    / EXPECTED_PROJECT_WORKS
                ),

            "share_of_risk_pair_mass":
                (
                    pairs
                    / risk_pair_mass
                ),

            "share_of_baseline_r2a1_pair_mass":
                (
                    pairs
                    / BASELINE_R2A1_PAIRS
                ),
        }

        expected = EXPECTED_STATUS[
            status
        ]

        if (
            works
            != expected[
                "works"
            ]
            or pairs
            != expected[
                "pairs"
            ]
        ):
            raise RuntimeError(
                f"Unexpected status totals for {status}: "
                f"works={works}, pairs={pairs}"
            )

    # --------------------------------------------------
    # Human-reviewed overlay.
    #
    # This is descriptive only. The audit sample was
    # stratified by LLM entity status, not by pair mass.
    # Therefore disagreement pair mass below is NOT an
    # estimator of pair-level error prevalence.
    # --------------------------------------------------

    reviewed_projects = project.loc[
        project[
            "human_reviewed_source_record_count"
        ].gt(0)
    ]

    reviewed_project_pair_mass = int(
        reviewed_projects[
            "pair_count"
        ].sum()
    )

    if (
        reviewed_project_pair_mass
        != EXPECTED_HUMAN_REVIEWED_PROJECT_PAIR_MASS
    ):
        raise RuntimeError(
            "Unexpected human-reviewed project pair mass: "
            f"{reviewed_project_pair_mass}"
        )

    reviewed_disagreements = (
        source.loc[
            source[
                "human_reviewed"
            ]
            & source[
                "llm_entity_status"
            ].ne(
                source[
                    "human_entity_status"
                ]
            ),
            [
                "project_work_id",
                "current_ol_work_id",
                "r2_target_title",
                "r2_target_author",
                "pair_count",
                "llm_entity_status",
                "human_entity_status",
                "llm_confidence",
                "human_confidence",
                "llm_note",
                "human_note",
            ],
        ]
        .copy()
        .sort_values(
            "pair_count",
            ascending=False,
        )
    )

    disagreement_pair_mass = int(
        reviewed_disagreements[
            "pair_count"
        ].sum()
    )

    if (
        disagreement_pair_mass
        != EXPECTED_REVIEWED_ENTITY_DISAGREEMENT_PAIR_MASS
    ):
        raise RuntimeError(
            "Unexpected reviewed disagreement pair mass: "
            f"{disagreement_pair_mass}"
        )

    # --------------------------------------------------
    # Write.
    # --------------------------------------------------

    source_out = (
        source.sort_values(
            [
                "pair_count",
                "project_work_id",
                "current_ol_work_id",
            ],
            ascending=[
                False,
                True,
                True,
            ],
        )
        .reset_index(
            drop=True
        )
    )

    project_out = (
        project.sort_values(
            [
                "pair_count",
                "project_work_id",
            ],
            ascending=[
                False,
                True,
            ],
        )
        .reset_index(
            drop=True
        )
    )

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=False,
    )

    atomic_tsv(
        source_out,
        SOURCE_OUT,
    )

    atomic_tsv(
        project_out,
        PROJECT_OUT,
    )

    atomic_tsv(
        reviewed_disagreements,
        REVIEWED_DISAGREE_OUT,
    )

    summary = {
        "release":
            RELEASE,

        "status":
            "pair_impact_diagnostic",

        "baseline_r2a1_pairs":
            BASELINE_R2A1_PAIRS,

        "risk_source_ol_records":
            len(source),

        "risk_project_works":
            len(project),

        "risk_pair_mass":
            risk_pair_mass,

        "risk_share_of_baseline_r2a1_pair_mass":
            (
                risk_pair_mass
                / BASELINE_R2A1_PAIRS
            ),

        "llm_project_entity_status_impact":
            status_summary,

        "multi_record_conflicts":
            project.loc[
                project[
                    "llm_project_entity_status"
                ].eq(
                    "MULTI_RECORD_CONFLICT"
                ),
                [
                    "project_work_id",
                    "r2_target_title",
                    "pair_count",
                    "current_ol_work_ids",
                    "llm_source_entity_statuses",
                    "human_review_coverage",
                    "human_entity_statuses_reviewed",
                ],
            ].to_dict(
                orient="records"
            ),

        "human_review_overlay": {
            "reviewed_project_works":
                int(
                    len(
                        reviewed_projects
                    )
                ),

            "reviewed_project_pair_mass":
                reviewed_project_pair_mass,

            "reviewed_project_pair_mass_share_of_risk":
                (
                    reviewed_project_pair_mass
                    / risk_pair_mass
                ),

            "reviewed_entity_disagreement_source_records":
                int(
                    len(
                        reviewed_disagreements
                    )
                ),

            "reviewed_entity_disagreement_pair_mass":
                disagreement_pair_mass,

            "important_caveat":
                (
                    "The human audit was stratified by "
                    "LLM entity-status class, not by pair "
                    "mass. The observed disagreement pair "
                    "mass among reviewed records is "
                    "descriptive only and must not be "
                    "extrapolated as a pair-level error "
                    "rate."
                ),
        },

        "interpretation_caveat":
            (
                "Pair mass measures the number of "
                "project_work_id × OpenAlex Work candidate "
                "pairs associated with each upstream "
                "target entity. HETEROGENEOUS_CLUSTER does "
                "not mean that every associated OpenAlex "
                "pair is an invalid retrieval. This "
                "analysis quantifies concentration of "
                "retrieval mass in target entities with "
                "different identity/coherence properties; "
                "it is not a corrected retrieval-precision "
                "estimate."
            ),
    }

    atomic_json(
        summary,
        SUMMARY,
    )

    manifest = {
        "release":
            RELEASE,

        "status":
            "frozen_analysis_candidate",

        "inputs": {
            str(
                RISK.relative_to(
                    ROOT
                )
            ):
                sha256_file(RISK),

            str(
                LLM.relative_to(
                    ROOT
                )
            ):
                sha256_file(LLM),

            str(
                HUMAN.relative_to(
                    ROOT
                )
            ):
                sha256_file(HUMAN),
        },

        "outputs": {
            str(
                SOURCE_OUT.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    SOURCE_OUT
                ),

            str(
                PROJECT_OUT.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    PROJECT_OUT
                ),

            str(
                REVIEWED_DISAGREE_OUT.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    REVIEWED_DISAGREE_OUT
                ),

            str(
                SUMMARY.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    SUMMARY
                ),
        },

        "semantics": [
            (
                "The 48 source OL records are collapsed "
                "to 47 project works before pair mass is "
                "summed."
            ),
            (
                "If multiple source OL records under one "
                "project work receive different LLM entity "
                "statuses, the project-level status is "
                "MULTI_RECORD_CONFLICT rather than choosing "
                "one source-record judgment."
            ),
            (
                "Maria Edgeworth therefore contributes "
                "1,885 pairs once, not twice."
            ),
            (
                "Exact candidate-set duplication among "
                "different project works, including the "
                "Charles Lamb group, does not collapse "
                "those project works into one conceptual "
                "work."
            ),
            (
                "Human judgments are retained only as a "
                "review overlay. They do not partially "
                "replace the 48-record frozen LLM "
                "classification."
            ),
            (
                "No status category in this artifact is "
                "itself an OpenAlex retrieval-validity "
                "label."
            ),
        ],
    }

    atomic_json(
        manifest,
        MANIFEST,
    )

    print(
        "=== OL TARGET IDENTITY PAIR IMPACT V1 ==="
    )

    print(
        "source OL records:",
        len(source),
    )

    print(
        "project works:",
        len(project),
    )

    print(
        "risk pair mass:",
        risk_pair_mass,
    )

    print(
        "baseline R2+A1 pair mass:",
        BASELINE_R2A1_PAIRS,
    )

    print(
        "risk share of baseline:",
        f"{risk_pair_mass / BASELINE_R2A1_PAIRS:.6%}",
    )

    print(
        "\n=== PROJECT-LEVEL LLM ENTITY STATUS ==="
    )

    for status in PROJECT_STATUS_ORDER:
        x = status_summary[
            status
        ]

        print(
            status,
            f"works={x['project_works']}",
            f"pairs={x['pair_mass']}",
            (
                "risk_share="
                f"{x['share_of_risk_pair_mass']:.6%}"
            ),
            (
                "baseline_share="
                f"{x['share_of_baseline_r2a1_pair_mass']:.6%}"
            ),
            sep="\t",
        )

    print(
        "\n=== MULTI-RECORD CONFLICT ==="
    )

    conflict = project.loc[
        project[
            "llm_project_entity_status"
        ].eq(
            "MULTI_RECORD_CONFLICT"
        )
    ]

    print(
        conflict[
            [
                "project_work_id",
                "r2_target_title",
                "pair_count",
                "current_ol_work_ids",
                "llm_source_entity_statuses",
                "human_review_coverage",
                "human_entity_statuses_reviewed",
            ]
        ].to_string(
            index=False
        )
    )

    print(
        "\n=== HUMAN REVIEW OVERLAY ==="
    )

    print(
        "reviewed project works:",
        len(
            reviewed_projects
        ),
    )

    print(
        "reviewed project pair mass:",
        reviewed_project_pair_mass,
    )

    print(
        "reviewed entity disagreements:",
        len(
            reviewed_disagreements
        ),
    )

    print(
        "disagreement pair mass:",
        disagreement_pair_mass,
    )

    print(
        "\n=== REVIEWED ENTITY DISAGREEMENTS ==="
    )

    print(
        reviewed_disagreements[
            [
                "project_work_id",
                "current_ol_work_id",
                "r2_target_title",
                "pair_count",
                "llm_entity_status",
                "human_entity_status",
            ]
        ].to_string(
            index=False
        )
    )

    print(
        "\nQC STATUS: PASSED"
    )


if __name__ == "__main__":
    main()
