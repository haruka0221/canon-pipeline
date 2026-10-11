#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os
import subprocess

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

SAMPLE_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_r2a1_baseline_validation_sample_v1"
)

SAMPLE = (
    SAMPLE_DIR
    / "openalex_r2a1_baseline_validation_sample_combined_v1.parquet"
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

BLIND_MANIFEST = (
    BLIND_DIR
    / "openalex_r2a1_baseline_validation_review_input_v1_manifest.json"
)

GUIDE = (
    ROOT
    / "docs"
    / "OPENALEX_R2A1_BASELINE_HUMAN_ADJUDICATION_GUIDE_V1.md"
)

OUT_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_r2a1_baseline_primary_human_review_packet_v1"
)

BATCH_DIR = (
    OUT_DIR
    / "batches"
)

MASTER = (
    OUT_DIR
    / "openalex_r2a1_baseline_primary_human_review_master_v1.tsv"
)

INDEX = (
    OUT_DIR
    / "openalex_r2a1_baseline_primary_human_review_batch_index_v1.tsv"
)

MANIFEST = (
    OUT_DIR
    / "openalex_r2a1_baseline_primary_human_review_packet_v1_manifest.json"
)

AUDIT = (
    OUT_DIR
    / "openalex_r2a1_baseline_primary_human_review_packet_v1_audit.json"
)

RELEASE = "openalex-r2a1-baseline-primary-human-review-packet-v1"
VERSION = "v1"
CREATED_AT = "2026-10-11"

EXPECTED_ROWS = 800
BATCH_SIZE = 40
EXPECTED_BATCHES = 20

ORDER_SALT = (
    "openalex-r2a1-baseline-primary-"
    "human-review-v1"
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

    for path in [
        SAMPLE,
        BLIND,
        BLIND_MANIFEST,
        GUIDE,
    ]:
        if not path.exists():
            raise FileNotFoundError(path)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory already exists: {OUT_DIR}"
        )

    # --------------------------------------------------
    # 1. Frozen primary membership
    # --------------------------------------------------

    sample = pd.read_parquet(
        SAMPLE
    )

    assert len(sample) == 1147
    assert sample[
        "baseline_candidate_id"
    ].is_unique

    primary_ids = set(
        sample.loc[
            sample[
                "in_primary_pair_sample"
            ].astype(bool),
            "baseline_candidate_id",
        ].astype(str)
    )

    assert len(primary_ids) == EXPECTED_ROWS

    # --------------------------------------------------
    # 2. Blind source only
    #
    # Deliberately do NOT read the LLM first-pass
    # artifact anywhere in this builder.
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

    for col in [
        "human_judgment",
        "human_reason_code",
        "human_notes",
    ]:
        assert blind[col].eq("").all()

    review = (
        blind.loc[
            blind[
                "baseline_candidate_id"
            ].isin(primary_ids),
            CONTEXT_COLUMNS,
        ]
        .copy()
    )

    assert len(review) == EXPECTED_ROWS

    assert set(
        review[
            "baseline_candidate_id"
        ]
    ) == primary_ids

    assert review[
        "baseline_candidate_id"
    ].is_unique

    # --------------------------------------------------
    # 3. Deterministic blind review order
    # --------------------------------------------------

    review[
        "_stable_order"
    ] = review[
        "baseline_candidate_id"
    ].map(stable_key)

    review = (
        review.sort_values(
            [
                "_stable_order",
                "baseline_candidate_id",
            ],
            kind="stable",
        )
        .drop(
            columns=[
                "_stable_order"
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
        f"R2A1H{((i - 1) // BATCH_SIZE) + 1:02d}"
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
    # 4. Strong blindness assertions
    # --------------------------------------------------

    forbidden = {
        "llm_first_pass_judgment",
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
        & set(review.columns)
    )

    assert review[
        HUMAN_COLUMNS
    ].eq("").all().all()

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
    # 5. Write master + 20 frozen blank batches
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

    index_rows = []
    batch_paths = []

    for batch_no in range(
        1,
        EXPECTED_BATCHES + 1,
    ):

        batch_id = (
            f"R2A1H{batch_no:02d}"
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
                "openalex_r2a1_baseline_"
                f"primary_human_review_{batch_id}.tsv"
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
    # 6. Manifest + audit
    # --------------------------------------------------

    head = subprocess.check_output(
        [
            "git",
            "rev-parse",
            "HEAD",
        ],
        cwd=ROOT,
        text=True,
    ).strip()

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

        "version":
            VERSION,

        "created_at":
            CREATED_AT,

        "source_head":
            head,

        "purpose": (
            "Freeze a human-adjudication packet "
            "for the 800-pair PRIMARY random "
            "validation sample of the R2+A1 "
            "OpenAlex baseline."
        ),

        "review_population": {
            "primary_candidate_pairs":
                EXPECTED_ROWS,

            "batch_size":
                BATCH_SIZE,

            "batch_count":
                EXPECTED_BATCHES,

            "secondary_diagnostic_included":
                False,
        },

        "ordering": {
            "method":
                (
                    "SHA256(salt + NUL + "
                    "baseline_candidate_id)"
                ),

            "salt":
                ORDER_SALT,
        },

        "blinding": {
            "llm_first_pass_read_by_builder":
                False,

            "llm_output_in_packet":
                False,

            "retrieval_risk_features_in_packet":
                False,

            "work_candidate_volume_in_packet":
                False,

            "hit_location_in_packet":
                False,

            "title_token_features_in_packet":
                False,
        },

        "adjudication": {
            "review_protocol_version":
                REVIEW_PROTOCOL_VERSION,

            "external_web_allowed":
                False,

            "authoritative_precision_source":
                "human judgments of PRIMARY 800",

            "allowed_judgments": [
                "VALID_TARGET_REFERENCE",
                "INVALID_TARGET_REFERENCE",
                "UNCERTAIN",
            ],
        },

        "sources": {
            str(
                SAMPLE.relative_to(ROOT)
            ):
                sha256_file(SAMPLE),

            str(
                BLIND.relative_to(ROOT)
            ):
                sha256_file(BLIND),

            str(
                BLIND_MANIFEST.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    BLIND_MANIFEST
                ),

            str(
                GUIDE.relative_to(ROOT)
            ):
                sha256_file(GUIDE),
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
            "exactly_800_primary_candidates":
                len(review) == 800,

            "candidate_set_exactly_primary":
                set(
                    review[
                        "baseline_candidate_id"
                    ]
                ) == primary_ids,

            "unique_candidate_ids":
                review[
                    "baseline_candidate_id"
                ].is_unique,

            "exactly_20_batches":
                len(counts) == 20,

            "exactly_40_candidates_per_batch":
                bool(
                    (
                        counts
                        == 40
                    ).all()
                ),

            "all_human_fields_blank":
                bool(
                    review[
                        HUMAN_COLUMNS
                    ].eq("").all().all()
                ),

            "llm_fields_absent":
                not any(
                    str(c).startswith(
                        "llm_"
                    )
                    for c in review.columns
                ),

            "risk_fields_absent":
                not bool(
                    forbidden
                    & set(
                        review.columns
                    )
                ),

            "secondary_only_candidates_absent":
                not bool(
                    set(
                        sample.loc[
                            sample[
                                "sample_membership"
                            ].eq(
                                "SECONDARY_ONLY"
                            ),
                            "baseline_candidate_id",
                        ].astype(str)
                    )
                    & set(
                        review[
                            "baseline_candidate_id"
                        ]
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
            "This packet contains no human "
            "judgments and no LLM first-pass "
            "information. It is a frozen blank "
            "input for independent human review."
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
        "HUMAN REVIEW PACKET V1 ==="
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
        "LLM information included: NO"
    )

    print(
        "risk features included: NO"
    )

    print(
        "human judgment fields blank:",
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
