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
    / "openlibrary_r2a1_target_identity_llm_v1"
)

LLM = (
    LLM_DIR
    / "openlibrary_r2a1_target_identity_llm_v1.tsv"
)

LLM_MANIFEST = (
    LLM_DIR
    / "openlibrary_r2a1_target_identity_llm_v1_manifest.json"
)

SRC_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_diagnostic_v1"
)

SUMMARY = (
    SRC_DIR
    / "openlibrary_r2a1_target_identity_current_api_summary_v1.tsv"
)

EDITIONS = (
    SRC_DIR
    / "openlibrary_r2a1_target_identity_current_api_editions_v1.tsv"
)

OUT_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_human_audit_sample_v1"
)

SELECTION = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_human_audit_selection_v1.tsv"
)

REVIEW = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_human_audit_review_input_v1.tsv"
)

EDITION_PACKET = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_human_audit_editions_v1.tsv"
)

AUDIT = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_human_audit_sample_v1_audit.json"
)

MANIFEST = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_human_audit_sample_v1_manifest.json"
)


RELEASE = (
    "openlibrary-r2a1-target-identity-human-audit-sample-v1"
)

CREATED_AT = "2026-10-11"

SELECTION_SALT = (
    "openlibrary-r2a1-target-identity-human-audit-v1"
)

EXPECTED_LLM_ROWS = 48
EXPECTED_SAMPLE_ROWS = 20

ALLOC = {
    "HETEROGENEOUS_CLUSTER": 6,
    "COHERENT_COLLECTION": 6,
    "COHERENT_SINGLE_WORK": 5,
    "UNCERTAIN": 3,
}


def sha256_file(path):
    h = hashlib.sha256()

    with Path(path).open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def selection_hash(oid):
    return hashlib.sha256(
        (
            SELECTION_SALT
            + "\0"
            + str(oid)
        ).encode("utf-8")
    ).hexdigest()


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
        LLM,
        LLM_MANIFEST,
        SUMMARY,
        EDITIONS,
    ]:
        if not p.exists():
            raise FileNotFoundError(p)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory exists: {OUT_DIR}"
        )

    llm = pd.read_csv(
        LLM,
        sep="\t",
        dtype=str,
        keep_default_na=False,
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

    if len(llm) != EXPECTED_LLM_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_LLM_ROWS} LLM rows; "
            f"found {len(llm)}"
        )

    if not llm[
        "current_ol_work_id"
    ].is_unique:
        raise RuntimeError(
            "LLM current_ol_work_id not unique"
        )

    if not src[
        "current_ol_work_id"
    ].is_unique:
        raise RuntimeError(
            "Source current_ol_work_id not unique"
        )

    expected_counts = {
        "COHERENT_COLLECTION": 20,
        "HETEROGENEOUS_CLUSTER": 20,
        "COHERENT_SINGLE_WORK": 5,
        "UNCERTAIN": 3,
    }

    actual_counts = (
        llm[
            "llm_entity_status"
        ]
        .value_counts()
        .to_dict()
    )

    if actual_counts != expected_counts:
        raise RuntimeError(
            f"Unexpected LLM strata: {actual_counts}"
        )

    # --------------------------------------------------
    # Deterministic stratified selection
    # --------------------------------------------------

    sel_parts = []

    for stratum, n in ALLOC.items():

        s = llm.loc[
            llm[
                "llm_entity_status"
            ].eq(stratum)
        ].copy()

        s[
            "selection_hash"
        ] = s[
            "current_ol_work_id"
        ].map(
            selection_hash
        )

        s = (
            s.sort_values(
                [
                    "selection_hash",
                    "current_ol_work_id",
                ],
                kind="stable",
            )
            .head(n)
            .copy()
        )

        s[
            "audit_sampling_stratum"
        ] = stratum

        s[
            "audit_stratum_population_n"
        ] = actual_counts[
            stratum
        ]

        s[
            "audit_stratum_sample_n"
        ] = n

        sel_parts.append(
            s
        )

    selected = pd.concat(
        sel_parts,
        ignore_index=True,
    )

    if len(selected) != EXPECTED_SAMPLE_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_SAMPLE_ROWS}; "
            f"found {len(selected)}"
        )

    if not selected[
        "current_ol_work_id"
    ].is_unique:
        raise RuntimeError(
            "Duplicate selected OL Work"
        )

    # Independent review order.
    selected[
        "review_order_hash"
    ] = selected[
        "current_ol_work_id"
    ].map(
        lambda x:
        hashlib.sha256(
            (
                SELECTION_SALT
                + "\0REVIEW\0"
                + x
            ).encode("utf-8")
        ).hexdigest()
    )

    selected = (
        selected.sort_values(
            "review_order_hash",
            kind="stable",
        )
        .reset_index(drop=True)
    )

    selected[
        "review_order"
    ] = range(
        1,
        len(selected) + 1,
    )

    # --------------------------------------------------
    # Internal selection artifact:
    # preserves LLM strata and selection provenance.
    # --------------------------------------------------

    selection_cols = [
        "review_order",
        "current_ol_work_id",
        "project_work_id",
        "audit_sampling_stratum",
        "audit_stratum_population_n",
        "audit_stratum_sample_n",
        "selection_hash",
        "review_order_hash",
    ]

    selection_out = selected[
        selection_cols
    ].copy()

    # --------------------------------------------------
    # Blind human review input.
    #
    # NO LLM labels.
    # NO pair_count.
    # NO diagnostic_type.
    # NO duplicate/fingerprint/risk fields.
    # --------------------------------------------------

    selected_ids = set(
        selected[
            "current_ol_work_id"
        ]
    )

    review = (
        src.loc[
            src[
                "current_ol_work_id"
            ].isin(
                selected_ids
            )
        ]
        .merge(
            selected[
                [
                    "current_ol_work_id",
                    "review_order",
                ]
            ],
            on="current_ol_work_id",
            how="inner",
            validate="one_to_one",
        )
    )

    forbidden = {
        "pair_count",
        "pairset_sha256",
        "diagnostic_type",
        "exact_pairset_duplicate_group",
        "has_exact_pairset_duplicate",
        "identity_judgment",
        "identity_confidence",
        "identity_reason",
        "identity_note",
    }

    visible_cols = [
        "review_order",
        "project_work_id",
        "current_ol_work_id",
        "r2_target_title",
        "r2_target_author",
        "title",
        "first_publish_year",
        "current_work_title",
        "current_work_description",
        "current_work_first_publish_date",
        "current_work_subjects",
        "edition_total_reported",
        "edition_rows_fetched",
        "distinct_edition_titles",
        "edition_titles",
        "edition_subtitles",
        "edition_publish_dates",
        "edition_publishers",
    ]

    for c in visible_cols:
        if c not in review.columns:
            raise RuntimeError(
                f"Missing review field: {c}"
            )

    review = review[
        visible_cols
    ].copy()

    review[
        "human_entity_status"
    ] = ""

    review[
        "human_content_type"
    ] = ""

    review[
        "human_date_window_assessment"
    ] = ""

    review[
        "human_confidence"
    ] = ""

    review[
        "human_note"
    ] = ""

    review = review.sort_values(
        "review_order",
        kind="stable",
    )

    if forbidden & set(
        review.columns
    ):
        raise RuntimeError(
            "Forbidden field leaked into blind review input"
        )

    # --------------------------------------------------
    # Edition-level evidence for selected records only.
    # Also blind to all LLM/risk information.
    # --------------------------------------------------

    ed = editions.loc[
        editions[
            "current_ol_work_id"
        ].isin(
            selected_ids
        )
    ].copy()

    ed = ed.merge(
        selected[
            [
                "current_ol_work_id",
                "review_order",
            ]
        ],
        on="current_ol_work_id",
        how="left",
        validate="many_to_one",
    )

    ed = ed.sort_values(
        [
            "review_order",
            "current_ol_work_id",
            "edition_key",
        ],
        kind="stable",
    )

    # --------------------------------------------------
    # Write
    # --------------------------------------------------

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=False,
    )

    atomic_tsv(
        selection_out,
        SELECTION,
    )

    atomic_tsv(
        review,
        REVIEW,
    )

    atomic_tsv(
        ed,
        EDITION_PACKET,
    )

    audit = {
        "release":
            RELEASE,

        "audit_status":
            "PASSED",

        "population_rows":
            len(llm),

        "sample_rows":
            len(review),

        "sampling_allocation":
            ALLOC,

        "population_strata":
            actual_counts,

        "unique_sample_ol_works":
            int(
                review[
                    "current_ol_work_id"
                ].nunique()
            ),

        "blind_review_llm_fields_visible":
            False,

        "blind_review_risk_fields_visible":
            False,

        "edition_rows_in_packet":
            len(ed),
    }

    atomic_json(
        audit,
        AUDIT,
    )

    manifest = {
        "release":
            RELEASE,

        "created_at":
            CREATED_AT,

        "status":
            "blind_human_audit_sample_frozen",

        "purpose": (
            "Freeze a 20-record blind human audit "
            "sample of the 48-record Open Library "
            "target-identity LLM risk-set adjudication."
        ),

        "sampling_design": {
            "population":
                (
                    "48 Open Library Works in "
                    "openlibrary-r2a1-target-identity-llm-v1"
                ),

            "stratification":
                "frozen LLM entity-status class",

            "selection":
                (
                    "deterministic SHA256 ordering "
                    "within each stratum"
                ),

            "allocation":
                ALLOC,

            "human_blinding": (
                "LLM judgments, pair counts, retrieval "
                "risk diagnostics, and duplicate-set "
                "information are withheld."
            ),

            "analysis_note": (
                "Do not use the unweighted 20-row sample "
                "as the 48-row risk-set agreement estimate. "
                "Any aggregate agreement estimate must "
                "post-stratify using the frozen stratum "
                "population sizes."
            ),
        },

        "inputs": {
            str(
                LLM.relative_to(ROOT)
            ):
                sha256_file(LLM),

            str(
                LLM_MANIFEST.relative_to(ROOT)
            ):
                sha256_file(
                    LLM_MANIFEST
                ),

            str(
                SUMMARY.relative_to(ROOT)
            ):
                sha256_file(
                    SUMMARY
                ),

            str(
                EDITIONS.relative_to(ROOT)
            ):
                sha256_file(
                    EDITIONS
                ),
        },

        "outputs": {
            str(
                SELECTION.relative_to(ROOT)
            ):
                sha256_file(
                    SELECTION
                ),

            str(
                REVIEW.relative_to(ROOT)
            ):
                sha256_file(
                    REVIEW
                ),

            str(
                EDITION_PACKET.relative_to(ROOT)
            ):
                sha256_file(
                    EDITION_PACKET
                ),

            str(
                AUDIT.relative_to(ROOT)
            ):
                sha256_file(
                    AUDIT
                ),
        },
    }

    atomic_json(
        manifest,
        MANIFEST,
    )

    print(
        "=== OL TARGET IDENTITY HUMAN AUDIT SAMPLE V1 ==="
    )

    print(
        "population:",
        len(llm),
    )

    print(
        "sample:",
        len(review),
    )

    print(
        "\n=== SAMPLE BY FROZEN LLM ENTITY STRATUM ==="
    )

    print(
        selection_out[
            "audit_sampling_stratum"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print(
        "\nreview project works:",
        review[
            "project_work_id"
        ].nunique(),
    )

    print(
        "edition evidence rows:",
        len(ed),
    )

    print(
        "\n=== BLIND REVIEW COLUMNS ==="
    )

    print(
        "\n".join(
            review.columns
        )
    )

    print(
        "\nQC STATUS: PASSED"
    )


if __name__ == "__main__":
    main()
