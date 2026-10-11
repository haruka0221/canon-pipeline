#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

SAMPLE = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_r2a1_baseline_validation_sample_v1"
    / "openalex_r2a1_baseline_validation_sample_combined_v1.parquet"
)

LLM_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_r2a1_baseline_validation_llm_first_pass_v1"
)

LLM = (
    LLM_DIR
    / "openalex_r2a1_baseline_validation_llm_first_pass_v1.tsv"
)

LLM_MANIFEST = (
    LLM_DIR
    / "openalex_r2a1_baseline_validation_llm_first_pass_v1_manifest.json"
)

DESIGN = (
    ROOT
    / "docs"
    / "OPENALEX_R2A1_BASELINE_HUMAN_AUDIT_DESIGN_V1.md"
)

OUT_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_r2a1_baseline_primary_human_audit_sample_v1"
)

OUT_TSV = (
    OUT_DIR
    / "openalex_r2a1_baseline_primary_human_audit_sample_v1.tsv"
)

OUT_PARQUET = (
    OUT_DIR
    / "openalex_r2a1_baseline_primary_human_audit_sample_v1.parquet"
)

SUMMARY = (
    OUT_DIR
    / "openalex_r2a1_baseline_primary_human_audit_sample_summary_v1.json"
)

MANIFEST = (
    OUT_DIR
    / "openalex_r2a1_baseline_primary_human_audit_sample_v1_manifest.json"
)

RELEASE = (
    "openalex-r2a1-baseline-primary-"
    "human-audit-sample-v1"
)

CREATED_AT = "2026-10-11"

SALT = (
    "openalex-r2a1-baseline-primary-"
    "human-audit-sample-v1"
)

EXPECTED_PRIMARY = 800

POPULATION_COUNTS = {
    "VALID_TARGET_REFERENCE": 474,
    "INVALID_TARGET_REFERENCE": 265,
    "UNCERTAIN": 61,
}

SAMPLE_COUNTS = {
    "VALID_TARGET_REFERENCE": 60,
    "INVALID_TARGET_REFERENCE": 60,
    "UNCERTAIN": 30,
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


def stable_key(stratum, candidate_id):
    return hashlib.sha256(
        (
            SALT
            + "\0"
            + stratum
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


def atomic_parquet(df, path):
    tmp = path.with_name(path.name + ".tmp")

    df.to_parquet(
        tmp,
        index=False,
        engine="pyarrow",
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
        SAMPLE,
        LLM,
        LLM_MANIFEST,
        DESIGN,
    ]:
        if not path.exists():
            raise FileNotFoundError(path)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory already exists: {OUT_DIR}"
        )

    sample = pd.read_parquet(SAMPLE)

    primary = sample.loc[
        sample[
            "in_primary_pair_sample"
        ].astype(bool),
        [
            "baseline_candidate_id",
            "project_work_id",
            "openalex_work_id",
        ],
    ].copy()

    assert len(primary) == EXPECTED_PRIMARY
    assert primary[
        "baseline_candidate_id"
    ].is_unique

    llm = pd.read_csv(
        LLM,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    assert llm[
        "baseline_candidate_id"
    ].is_unique

    x = primary.merge(
        llm[
            [
                "baseline_candidate_id",
                "llm_first_pass_judgment",
            ]
        ],
        on="baseline_candidate_id",
        how="left",
        validate="one_to_one",
    )

    assert len(x) == EXPECTED_PRIMARY

    actual_population = (
        x[
            "llm_first_pass_judgment"
        ]
        .value_counts()
        .to_dict()
    )

    assert (
        actual_population
        == POPULATION_COUNTS
    ), actual_population

    parts = []

    for stratum, n_sample in (
        SAMPLE_COUNTS.items()
    ):

        z = (
            x.loc[
                x[
                    "llm_first_pass_judgment"
                ].eq(stratum)
            ]
            .copy()
        )

        n_population = len(z)

        assert (
            n_population
            == POPULATION_COUNTS[
                stratum
            ]
        )

        z["_selection_key"] = [
            stable_key(
                stratum,
                cid,
            )
            for cid in z[
                "baseline_candidate_id"
            ]
        ]

        z = (
            z.sort_values(
                [
                    "_selection_key",
                    "baseline_candidate_id",
                ],
                kind="stable",
            )
            .head(n_sample)
            .copy()
        )

        z[
            "selection_rank_within_stratum"
        ] = range(
            1,
            n_sample + 1,
        )

        z[
            "stratum_population_n"
        ] = n_population

        z[
            "stratum_sample_n"
        ] = n_sample

        z[
            "stratum_sampling_fraction"
        ] = (
            n_sample
            / n_population
        )

        z[
            "analysis_weight"
        ] = (
            n_population
            / n_sample
        )

        parts.append(z)

    out = pd.concat(
        parts,
        ignore_index=True,
    )

    assert len(out) == 150

    assert out[
        "baseline_candidate_id"
    ].is_unique

    assert (
        out[
            "llm_first_pass_judgment"
        ]
        .value_counts()
        .to_dict()
        == SAMPLE_COUNTS
    )

    out = (
        out.drop(
            columns=[
                "_selection_key"
            ]
        )
        .sort_values(
            [
                "llm_first_pass_judgment",
                "selection_rank_within_stratum",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=False,
    )

    atomic_tsv(
        out,
        OUT_TSV,
    )

    atomic_parquet(
        out,
        OUT_PARQUET,
    )

    summary = {
        "release":
            RELEASE,

        "created_at":
            CREATED_AT,

        "population":
            EXPECTED_PRIMARY,

        "population_llm_stratum_counts":
            POPULATION_COUNTS,

        "human_audit_sample_n":
            len(out),

        "sample_llm_stratum_counts":
            SAMPLE_COUNTS,

        "selection": {
            "method":
                (
                    "deterministic SHA256 rank "
                    "within frozen LLM judgment "
                    "strata"
                ),

            "salt":
                SALT,
        },

        "analysis": {
            "unweighted_pooling_allowed":
                False,

            "restore_population_stratum_weights":
                True,

            "population_stratum_proportions": {
                k: v / EXPECTED_PRIMARY
                for k, v
                in POPULATION_COUNTS.items()
            },
        },

        "human_review_blinding": {
            "selection_stratum_must_be_hidden":
                True,

            "candidate_level_llm_output_must_be_hidden":
                True,

            "risk_features_must_be_hidden":
                True,
        },
    }

    atomic_json(
        summary,
        SUMMARY,
    )

    manifest = {
        "release":
            RELEASE,

        "created_at":
            CREATED_AT,

        "sources": {
            str(
                SAMPLE.relative_to(ROOT)
            ):
                sha256_file(SAMPLE),

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
                DESIGN.relative_to(ROOT)
            ):
                sha256_file(DESIGN),
        },

        "outputs": {
            str(
                OUT_TSV.relative_to(ROOT)
            ):
                sha256_file(OUT_TSV),

            str(
                OUT_PARQUET.relative_to(ROOT)
            ):
                sha256_file(
                    OUT_PARQUET
                ),

            str(
                SUMMARY.relative_to(ROOT)
            ):
                sha256_file(SUMMARY),
        },
    }

    atomic_json(
        manifest,
        MANIFEST,
    )

    print(
        "=== R2+A1 BASELINE PRIMARY "
        "HUMAN AUDIT SAMPLE V1 ==="
    )

    print(
        "population:",
        EXPECTED_PRIMARY,
    )

    print(
        "audit sample:",
        len(out),
    )

    print()
    print(
        out[
            "llm_first_pass_judgment"
        ]
        .value_counts()
        .to_string()
    )

    print()
    print(
        "unique candidate IDs:",
        out[
            "baseline_candidate_id"
        ].nunique(),
    )

    print(
        "output:",
        OUT_DIR,
    )


if __name__ == "__main__":
    main()
