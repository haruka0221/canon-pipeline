#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

PROJECT = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_pair_impact_v1"
    / "openlibrary_r2a1_target_identity_pair_impact_project_v1.tsv"
)

OUT_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_remediation_queue_v1"
)

QUEUE = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_remediation_queue_v1.tsv"
)

SUMMARY = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_remediation_queue_v1_summary.json"
)

MANIFEST = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_remediation_queue_v1_manifest.json"
)

RELEASE = (
    "openlibrary-r2a1-target-identity-remediation-queue-v1"
)

BASELINE_PAIRS = 290_480
RISK_PAIR_MASS = 102_128

EXPECTED_PROJECT_ROWS = 47
EXPECTED_QUEUE_ROWS = 24
EXPECTED_QUEUE_PAIR_MASS = 72_914


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


def split_statuses(value):
    return {
        x.strip()
        for x in str(value).split("||")
        if x.strip()
    }


def main():

    if not PROJECT.exists():
        raise FileNotFoundError(PROJECT)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory exists: {OUT_DIR}"
        )

    df = pd.read_csv(
        PROJECT,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    if len(df) != EXPECTED_PROJECT_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_PROJECT_ROWS} project rows; "
            f"found {len(df)}"
        )

    if not df["project_work_id"].is_unique:
        raise RuntimeError(
            "project_work_id is not unique"
        )

    df["pair_count"] = pd.to_numeric(
        df["pair_count"],
        errors="raise",
    )

    reasons = []

    for _, r in df.iterrows():

        row_reasons = []

        llm_status = r[
            "llm_project_entity_status"
        ]

        human_statuses = split_statuses(
            r[
                "human_entity_statuses_reviewed"
            ]
        )

        if llm_status == "HETEROGENEOUS_CLUSTER":
            row_reasons.append(
                "LLM_HETEROGENEOUS_CLUSTER"
            )

        if llm_status == "UNCERTAIN":
            row_reasons.append(
                "LLM_UNCERTAIN"
            )

        if llm_status == "MULTI_RECORD_CONFLICT":
            row_reasons.append(
                "MULTI_RECORD_CONFLICT"
            )

        if (
            "HETEROGENEOUS_CLUSTER"
            in human_statuses
            and llm_status
            != "HETEROGENEOUS_CLUSTER"
        ):
            row_reasons.append(
                "HUMAN_REVIEW_HETEROGENEOUS"
            )

        if (
            "UNCERTAIN"
            in human_statuses
            and llm_status
            != "UNCERTAIN"
        ):
            row_reasons.append(
                "HUMAN_REVIEW_UNCERTAIN"
            )

        if (
            "NONWORK_OR_HEADING_ARTIFACT"
            in human_statuses
            and llm_status
            != "NONWORK_OR_HEADING_ARTIFACT"
        ):
            row_reasons.append(
                "HUMAN_REVIEW_NONWORK"
            )

        reasons.append(
            " || ".join(
                row_reasons
            )
        )

    df[
        "remediation_queue_reason"
    ] = reasons

    q = df.loc[
        df[
            "remediation_queue_reason"
        ].ne("")
    ].copy()

    if len(q) != EXPECTED_QUEUE_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_QUEUE_ROWS} queue rows; "
            f"found {len(q)}"
        )

    pair_mass = int(
        q[
            "pair_count"
        ].sum()
    )

    if pair_mass != EXPECTED_QUEUE_PAIR_MASS:
        raise RuntimeError(
            f"Expected queue pair mass "
            f"{EXPECTED_QUEUE_PAIR_MASS}; "
            f"found {pair_mass}"
        )

    q = (
        q.sort_values(
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

    q[
        "remediation_priority_rank"
    ] = range(
        1,
        len(q) + 1,
    )

    q[
        "share_of_risk_pair_mass"
    ] = (
        q[
            "pair_count"
        ]
        / RISK_PAIR_MASS
    )

    q[
        "share_of_baseline_r2a1_pair_mass"
    ] = (
        q[
            "pair_count"
        ]
        / BASELINE_PAIRS
    )

    # Decision columns deliberately blank.
    q[
        "resolution_decision"
    ] = ""

    q[
        "resolution_confidence"
    ] = ""

    q[
        "resolution_note"
    ] = ""

    keep = [
        "remediation_priority_rank",
        "project_work_id",
        "r2_target_title",
        "r2_target_author",
        "diagnostic_type",
        "pair_count",
        "share_of_risk_pair_mass",
        "share_of_baseline_r2a1_pair_mass",
        "source_ol_record_count",
        "current_ol_work_ids",
        "llm_source_entity_statuses",
        "llm_project_entity_status",
        "human_reviewed_source_record_count",
        "human_review_coverage",
        "human_entity_statuses_reviewed",
        "reviewed_entity_disagreement_source_records",
        "remediation_queue_reason",
        "resolution_decision",
        "resolution_confidence",
        "resolution_note",
    ]

    q = q[
        keep
    ]

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=False,
    )

    atomic_tsv(
        q,
        QUEUE,
    )

    reason_counts = {}

    for value in q[
        "remediation_queue_reason"
    ]:
        for reason in split_statuses(
            value
        ):
            reason_counts[
                reason
            ] = (
                reason_counts.get(
                    reason,
                    0,
                )
                + 1
            )

    summary = {
        "release":
            RELEASE,

        "status":
            "remediation_queue_selection",

        "source_project_works":
            len(df),

        "queue_project_works":
            len(q),

        "queue_pair_mass":
            pair_mass,

        "queue_share_of_risk_pair_mass":
            (
                pair_mass
                / RISK_PAIR_MASS
            ),

        "queue_share_of_baseline_r2a1_pair_mass":
            (
                pair_mass
                / BASELINE_PAIRS
            ),

        "queue_reason_counts":
            dict(
                sorted(
                    reason_counts.items()
                )
            ),

        "selection_rule": [
            "LLM project status HETEROGENEOUS_CLUSTER",
            "LLM project status UNCERTAIN",
            "MULTI_RECORD_CONFLICT",
            (
                "Human-reviewed project flagged as "
                "HETEROGENEOUS_CLUSTER, UNCERTAIN, or "
                "NONWORK_OR_HEADING_ARTIFACT when that "
                "flag is not already represented by the "
                "LLM project status."
            ),
        ],

        "important_semantics": [
            (
                "Queue membership indicates need for "
                "identity-resolution/remediation review; "
                "it is not an exclusion decision."
            ),
            (
                "Pair count is used only to prioritize "
                "remediation impact after identity "
                "diagnostics were frozen."
            ),
            (
                "The queue does not alter the frozen "
                "34,789-record source population."
            ),
            (
                "The queue does not decide temporal, "
                "language, or fiction-scope eligibility."
            ),
        ],
    }

    atomic_json(
        summary,
        SUMMARY,
    )

    manifest = {
        "release":
            RELEASE,

        "status":
            "frozen_selection_candidate",

        "inputs": {
            str(
                PROJECT.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    PROJECT
                ),
        },

        "outputs": {
            str(
                QUEUE.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    QUEUE
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
    }

    atomic_json(
        manifest,
        MANIFEST,
    )

    print(
        "=== OL TARGET IDENTITY REMEDIATION QUEUE V1 ==="
    )

    print(
        "source project works:",
        len(df),
    )

    print(
        "queue project works:",
        len(q),
    )

    print(
        "queue pair mass:",
        pair_mass,
    )

    print(
        "queue share of risk pair mass:",
        f"{pair_mass / RISK_PAIR_MASS:.6%}",
    )

    print(
        "queue share of baseline:",
        f"{pair_mass / BASELINE_PAIRS:.6%}",
    )

    print(
        "\n=== QUEUE REASONS ==="
    )

    for k, v in sorted(
        reason_counts.items()
    ):
        print(
            f"{k}\t{v}"
        )

    print(
        "\n=== QUEUE ==="
    )

    print(
        q[
            [
                "remediation_priority_rank",
                "project_work_id",
                "r2_target_title",
                "pair_count",
                "llm_project_entity_status",
                "human_entity_statuses_reviewed",
                "remediation_queue_reason",
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
