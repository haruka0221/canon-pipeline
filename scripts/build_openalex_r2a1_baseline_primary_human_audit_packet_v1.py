#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

AUDIT_SAMPLE_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_r2a1_baseline_primary_human_audit_sample_v1"
)

AUDIT_SAMPLE = (
    AUDIT_SAMPLE_DIR
    / "openalex_r2a1_baseline_primary_human_audit_sample_v1.parquet"
)

AUDIT_SAMPLE_MANIFEST = (
    AUDIT_SAMPLE_DIR
    / "openalex_r2a1_baseline_primary_human_audit_sample_v1_manifest.json"
)

BLIND_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_r2a1_baseline_validation_review_input_v1"
)

BLIND = (
    BLIND_DIR
    / "openalex_r2a1_baseline_validation_blind_v1.tsv"
)

DESIGN = (
    ROOT
    / "docs"
    / "OPENALEX_R2A1_BASELINE_HUMAN_AUDIT_DESIGN_V1.md"
)

STRATEGY = (
    ROOT
    / "docs"
    / "OPENALEX_R2A1_BASELINE_VALIDATION_STRATEGY_V2.md"
)

OUT_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_r2a1_baseline_primary_human_audit_packet_v1"
)

BATCH_DIR = OUT_DIR / "batches"

MASTER = (
    OUT_DIR
    / "openalex_r2a1_baseline_primary_human_audit_master_v1.tsv"
)

INDEX = (
    OUT_DIR
    / "openalex_r2a1_baseline_primary_human_audit_batch_index_v1.tsv"
)

MANIFEST = (
    OUT_DIR
    / "openalex_r2a1_baseline_primary_human_audit_packet_v1_manifest.json"
)

AUDIT = (
    OUT_DIR
    / "openalex_r2a1_baseline_primary_human_audit_packet_v1_audit.json"
)

RELEASE = (
    "openalex-r2a1-baseline-primary-human-audit-packet-v1"
)

CREATED_AT = "2026-10-11"

EXPECTED_ROWS = 150
BATCH_SIZE = 25
EXPECTED_BATCHES = 6

ORDER_SALT = (
    "openalex-r2a1-baseline-primary-human-audit-review-order-v1"
)

REVIEW_PROTOCOL_VERSION = "v1"


CONTEXT_COLUMNS = [
    "baseline_candidate_id",
    "project_work_id",
    "target_title",
    "target_author",
    "openalex_work_id",
    "openalex_display_name",
    "openalex_abstract",
    "publication_year",
    "publication_date",
    "doi",
]

HUMAN_COLUMNS = [
    "human_target_attribution_judgment",
    "human_adjudication_confidence",
    "human_attribution_reason_code",
    "human_reviewer_note",
    "human_reviewer_id",
    "human_adjudicated_at_utc",
]

OUTPUT_COLUMNS = [
    "review_batch_id",
    "review_order",
    *CONTEXT_COLUMNS,
    "review_protocol_version",
    *HUMAN_COLUMNS,
]


def sha256_file(path):
    h = hashlib.sha256()

    with Path(path).open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def stable_key(candidate_id):
    return hashlib.sha256(
        (
            ORDER_SALT
            + "\0"
            + candidate_id
        ).encode("utf-8")
    ).hexdigest()


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


def main():

    for path in [
        AUDIT_SAMPLE,
        AUDIT_SAMPLE_MANIFEST,
        BLIND,
        DESIGN,
        STRATEGY,
    ]:
        if not path.exists():
            raise FileNotFoundError(path)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory already exists: {OUT_DIR}"
        )

    # --------------------------------------------------
    # 1. Frozen 150-candidate audit membership
    # --------------------------------------------------

    sample = pd.read_parquet(
        AUDIT_SAMPLE
    )

    assert len(sample) == EXPECTED_ROWS

    assert sample[
        "baseline_candidate_id"
    ].is_unique

    audit_ids = set(
        sample[
            "baseline_candidate_id"
        ].astype(str)
    )

    assert len(audit_ids) == EXPECTED_ROWS

    # These fields exist in the selection artifact,
    # but MUST NOT enter the human-review packet.
    selection_only_fields = {
        "llm_first_pass_judgment",
        "selection_rank_within_stratum",
        "stratum_population_n",
        "stratum_sample_n",
        "stratum_sampling_fraction",
        "analysis_weight",
    }

    assert (
        "llm_first_pass_judgment"
        in sample.columns
    )

    # --------------------------------------------------
    # 2. Human-visible content comes from blind source
    # --------------------------------------------------

    blind = pd.read_csv(
        BLIND,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    assert len(blind) == 1147
    assert blind[
        "baseline_candidate_id"
    ].is_unique

    review = (
        blind.loc[
            blind[
                "baseline_candidate_id"
            ].isin(audit_ids),
            CONTEXT_COLUMNS,
        ]
        .copy()
    )

    assert len(review) == EXPECTED_ROWS
    assert review[
        "baseline_candidate_id"
    ].is_unique

    assert (
        set(
            review[
                "baseline_candidate_id"
            ]
        )
        == audit_ids
    )

    # --------------------------------------------------
    # 3. Deterministic review order independent of
    #    LLM judgment stratum
    # --------------------------------------------------

    review[
        "_review_order_key"
    ] = review[
        "baseline_candidate_id"
    ].map(stable_key)

    review = (
        review.sort_values(
            [
                "_review_order_key",
                "baseline_candidate_id",
            ],
            kind="stable",
        )
        .drop(
            columns=[
                "_review_order_key"
            ]
        )
        .reset_index(drop=True)
    )

    review[
        "review_order"
    ] = range(
        1,
        EXPECTED_ROWS + 1,
    )

    review[
        "review_batch_id"
    ] = [
        f"R2A1A{((i - 1) // BATCH_SIZE) + 1:02d}"
        for i in review[
            "review_order"
        ]
    ]

    review[
        "review_protocol_version"
    ] = REVIEW_PROTOCOL_VERSION

    for col in HUMAN_COLUMNS:
        review[col] = ""

    review = review[
        OUTPUT_COLUMNS
    ]

    # --------------------------------------------------
    # 4. Blindness checks
    # --------------------------------------------------

    forbidden = {
        *selection_only_fields,

        "llm_first_pass_reason_code",
        "llm_first_pass_confidence",
        "llm_first_pass_note",
        "llm_model_requested",
        "llm_model_returned",
        "llm_response_id",

        "hit_location",
        "title_token_bucket",
        "work_candidate_count",
        "work_volume_bucket",
        "sample_membership",
        "in_primary_pair_sample",
        "in_secondary_work_diagnostic_sample",
        "sampling_probability",

        "query_id",
        "query_route",
        "author_a1_hit",
    }

    assert not (
        forbidden
        & set(
            review.columns
        )
    )

    assert review[
        HUMAN_COLUMNS
    ].eq("").all().all()

    # --------------------------------------------------
    # 5. Batch invariants
    # --------------------------------------------------

    counts = (
        review[
            "review_batch_id"
        ]
        .value_counts()
        .sort_index()
    )

    assert len(counts) == EXPECTED_BATCHES

    assert (
        counts
        == BATCH_SIZE
    ).all()

    assert list(
        review[
            "review_order"
        ]
    ) == list(
        range(
            1,
            EXPECTED_ROWS + 1,
        )
    )

    # --------------------------------------------------
    # 6. Write frozen blank packet
    # --------------------------------------------------

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=False,
    )

    BATCH_DIR.mkdir(
        parents=True,
        exist_ok=False,
    )

    atomic_tsv(
        review,
        MASTER,
    )

    batch_paths = []
    index_rows = []

    for batch_no in range(
        1,
        EXPECTED_BATCHES + 1,
    ):

        batch_id = (
            f"R2A1A{batch_no:02d}"
        )

        b = review.loc[
            review[
                "review_batch_id"
            ].eq(batch_id)
        ].copy()

        assert len(b) == BATCH_SIZE

        path = (
            BATCH_DIR
            / (
                "openalex_r2a1_baseline_primary_"
                f"human_audit_{batch_id}.tsv"
            )
        )

        atomic_tsv(
            b,
            path,
        )

        batch_paths.append(path)

        index_rows.append({
            "review_batch_id":
                batch_id,

            "candidate_count":
                len(b),

            "first_review_order":
                int(
                    b[
                        "review_order"
                    ].min()
                ),

            "last_review_order":
                int(
                    b[
                        "review_order"
                    ].max()
                ),

            "artifact":
                str(
                    path.relative_to(
                        OUT_DIR
                    )
                ),

            "sha256":
                sha256_file(path),
        })

    index = pd.DataFrame(
        index_rows
    )

    atomic_tsv(
        index,
        INDEX,
    )

    # --------------------------------------------------
    # 7. Manifest and audit
    # --------------------------------------------------

    outputs = {
        str(
            MASTER.relative_to(ROOT)
        ):
            sha256_file(MASTER),

        str(
            INDEX.relative_to(ROOT)
        ):
            sha256_file(INDEX),
    }

    for path in batch_paths:
        outputs[
            str(
                path.relative_to(ROOT)
            )
        ] = sha256_file(path)

    manifest = {
        "release":
            RELEASE,

        "created_at":
            CREATED_AT,

        "review_population": {
            "candidate_pairs":
                EXPECTED_ROWS,

            "batch_count":
                EXPECTED_BATCHES,

            "batch_size":
                BATCH_SIZE,

            "source":
                (
                    "frozen stratified human-audit "
                    "sample from PRIMARY 800"
                ),
        },

        "review_order": {
            "method":
                (
                    "SHA256(salt + NUL + "
                    "baseline_candidate_id)"
                ),

            "salt":
                ORDER_SALT,

            "uses_llm_stratum":
                False,
        },

        "blinding": {
            "candidate_level_llm_judgment_visible":
                False,

            "llm_reason_visible":
                False,

            "llm_confidence_visible":
                False,

            "llm_note_visible":
                False,

            "llm_sampling_stratum_visible":
                False,

            "analysis_weight_visible":
                False,

            "retrieval_risk_features_visible":
                False,
        },

        "adjudication": {
            "review_protocol_version":
                REVIEW_PROTOCOL_VERSION,

            "external_web_allowed":
                False,

            "allowed_judgments": [
                "VALID_TARGET_REFERENCE",
                "INVALID_TARGET_REFERENCE",
                "UNCERTAIN",
            ],
        },

        "sources": {
            str(
                AUDIT_SAMPLE.relative_to(ROOT)
            ):
                sha256_file(
                    AUDIT_SAMPLE
                ),

            str(
                AUDIT_SAMPLE_MANIFEST.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    AUDIT_SAMPLE_MANIFEST
                ),

            str(
                BLIND.relative_to(ROOT)
            ):
                sha256_file(BLIND),

            str(
                DESIGN.relative_to(ROOT)
            ):
                sha256_file(DESIGN),

            str(
                STRATEGY.relative_to(ROOT)
            ):
                sha256_file(STRATEGY),
        },

        "outputs":
            outputs,
    }

    atomic_json(
        manifest,
        MANIFEST,
    )

    audit = {
        "release":
            RELEASE,

        "status":
            "PASSED",

        "checks": {
            "exactly_150_candidates":
                len(review) == 150,

            "candidate_set_exactly_frozen_audit_sample":
                set(
                    review[
                        "baseline_candidate_id"
                    ]
                ) == audit_ids,

            "unique_candidate_ids":
                review[
                    "baseline_candidate_id"
                ].is_unique,

            "exactly_6_batches":
                len(counts) == 6,

            "exactly_25_candidates_per_batch":
                bool(
                    (
                        counts
                        == 25
                    ).all()
                ),

            "all_human_fields_blank":
                bool(
                    review[
                        HUMAN_COLUMNS
                    ].eq("").all().all()
                ),

            "all_llm_fields_absent":
                not any(
                    str(c).startswith(
                        "llm_"
                    )
                    for c in review.columns
                ),

            "all_selection_stratum_fields_absent":
                not bool(
                    selection_only_fields
                    & set(
                        review.columns
                    )
                ),

            "all_risk_fields_absent":
                not bool(
                    forbidden
                    & set(
                        review.columns
                    )
                ),
        },

        "dimensions": {
            "candidates":
                len(review),

            "batches":
                len(counts),

            "project_works":
                int(
                    review[
                        "project_work_id"
                    ].nunique()
                ),
        },

        "statement": (
            "This is a blank blind human-audit "
            "packet. Candidate-level LLM results, "
            "LLM sampling strata, analysis weights, "
            "and retrieval-risk features are absent."
        ),
    }

    assert all(
        audit[
            "checks"
        ].values()
    )

    atomic_json(
        audit,
        AUDIT,
    )

    print(
        "=== R2+A1 BASELINE PRIMARY "
        "HUMAN AUDIT PACKET V1 ==="
    )

    print(
        "candidate rows:",
        len(review),
    )

    print(
        "project works:",
        review[
            "project_work_id"
        ].nunique(),
    )

    print(
        "batches:",
        len(counts),
    )

    print(
        "rows per batch:",
        sorted(
            counts.unique().tolist()
        ),
    )

    print(
        "LLM candidate judgments visible: NO"
    )

    print(
        "LLM sampling strata visible: NO"
    )

    print(
        "risk features visible: NO"
    )

    print(
        "human fields blank:",
        review[
            HUMAN_COLUMNS
        ].eq("").all().all(),
    )

    print(
        "audit status:",
        audit[
            "status"
        ],
    )

    print(
        "output:",
        OUT_DIR,
    )


if __name__ == "__main__":
    main()
