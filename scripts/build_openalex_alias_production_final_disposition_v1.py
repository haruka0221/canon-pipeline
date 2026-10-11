#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

DIAGNOSTICS = (
    ROOT
    / "derived/openalex_production"
    / "openalex_retrieval_by_work_error_analysis_v1"
    / "full_profile_57959e90"
    / "openalex_retrieval_by_work_error_analysis_v1_candidate_diagnostics.parquet"
)

HUMAN = (
    ROOT
    / "derived/openalex_production"
    / "openalex_retrieval_precision_review_human_adjudication_complete_v1"
    / "full_profile_57959e90"
    / "openalex_retrieval_precision_review_human_adjudication_complete_v1.parquet"
)

OUT_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_alias_production_final_disposition_v1"
)

OUT_TSV = (
    OUT_DIR
    / "openalex_alias_production_final_disposition_v1.tsv"
)

OUT_PARQUET = (
    OUT_DIR
    / "openalex_alias_production_final_disposition_v1.parquet"
)

OUT_SUMMARY = (
    OUT_DIR
    / "openalex_alias_production_final_disposition_summary_v1.json"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openalex_alias_production_final_disposition_v1_manifest.json"
)

RELEASE = "openalex-alias-production-final-disposition-v1"
CREATED_AT = "2026-10-11"


def sha256_file(path):
    h = hashlib.sha256()

    with Path(path).open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def write_tsv(df, path):
    tmp = path.with_name(path.name + ".tmp")

    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    os.replace(tmp, path)


def write_parquet(df, path):
    tmp = path.with_name(path.name + ".tmp")

    df.to_parquet(
        tmp,
        index=False,
        engine="pyarrow",
    )

    os.replace(tmp, path)


def write_json(obj, path):
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
        DIAGNOSTICS,
        HUMAN,
    ]:
        if not path.exists():
            raise FileNotFoundError(path)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory already exists: {OUT_DIR}"
        )

    # --------------------------------------------------------
    # 1. Frozen audited marginal candidate universe
    # --------------------------------------------------------

    diag = pd.read_parquet(
        DIAGNOSTICS
    )

    assert len(diag) == 661
    assert diag["review_candidate_id"].is_unique

    alias = (
        diag.loc[
            diag[
                "increment_type"
            ].eq(
                "ALIAS_EXPANSION"
            )
        ]
        .copy()
    )

    assert len(alias) == 409

    assert (
        alias[
            "project_work_id"
        ].nunique()
        == 38
    )

    assert not alias[
        [
            "project_work_id",
            "openalex_work_id",
        ]
    ].duplicated().any()

    # --------------------------------------------------------
    # 2. Authoritative complete human adjudication
    # --------------------------------------------------------

    human = pd.read_parquet(
        HUMAN
    )

    assert len(human) == 661
    assert human["review_candidate_id"].is_unique

    keep = [
        "review_candidate_id",
        "human_target_attribution_judgment",
        "human_attribution_reason_code",
        "human_reviewer_note",
        "human_reviewer_id",
        "human_adjudicated_at_utc",
    ]

    out = alias.merge(
        human[keep],
        on="review_candidate_id",
        how="left",
        validate="one_to_one",
    )

    assert (
        out[
            "human_target_attribution_judgment"
        ]
        .notna()
        .all()
    )

    expected_labels = {
        "VALID_TARGET_REFERENCE": 364,
        "INVALID_TARGET_REFERENCE": 24,
        "UNCERTAIN": 21,
    }

    actual_labels = (
        out[
            "human_target_attribution_judgment"
        ]
        .value_counts()
        .to_dict()
    )

    assert actual_labels == expected_labels, actual_labels

    # Candidate diagnostics already contain a frozen post-hoc
    # copy of the human label. Require exact parity.
    assert (
        out[
            "posthoc_human_target_attribution_judgment"
        ].astype(str)
        ==
        out[
            "human_target_attribution_judgment"
        ].astype(str)
    ).all()

    # --------------------------------------------------------
    # 3. Apply the already frozen Alias routing policy
    #
    # REVIEW iff:
    #
    #   ABSTRACT_ONLY
    #   AND
    #   title_match_token_count_min <= 4
    #
    # Otherwise ACCEPT.
    #
    # This is a routing action, not a truth label.
    # --------------------------------------------------------

    out[
        "title_match_token_count_min"
    ] = pd.to_numeric(
        out[
            "title_match_token_count_min"
        ],
        errors="raise",
    ).astype(int)

    review_mask = (
        out[
            "hit_location"
        ].eq(
            "ABSTRACT_ONLY"
        )
        &
        out[
            "title_match_token_count_min"
        ].le(4)
    )

    out[
        "policy_action"
    ] = "ACCEPT"

    out.loc[
        review_mask,
        "policy_action",
    ] = "REVIEW"

    policy_counts = (
        out[
            "policy_action"
        ]
        .value_counts()
        .to_dict()
    )

    assert policy_counts == {
        "REVIEW": 217,
        "ACCEPT": 192,
    }, policy_counts

    # --------------------------------------------------------
    # 4. Frozen policy × human-label cross-check
    # --------------------------------------------------------

    cross = (
        out.groupby(
            [
                "policy_action",
                "human_target_attribution_judgment",
            ]
        )
        .size()
        .to_dict()
    )

    expected_cross = {
        (
            "ACCEPT",
            "VALID_TARGET_REFERENCE",
        ): 182,

        (
            "ACCEPT",
            "INVALID_TARGET_REFERENCE",
        ): 2,

        (
            "ACCEPT",
            "UNCERTAIN",
        ): 8,

        (
            "REVIEW",
            "VALID_TARGET_REFERENCE",
        ): 182,

        (
            "REVIEW",
            "INVALID_TARGET_REFERENCE",
        ): 22,

        (
            "REVIEW",
            "UNCERTAIN",
        ): 13,
    }

    assert cross == expected_cross, cross

    # --------------------------------------------------------
    # 5. Final disposition
    #
    # Because the entire current-release Alias marginal
    # universe has complete human adjudication, final
    # disposition follows the authoritative human label.
    #
    # Frozen policy action is retained separately for
    # methodological / future-deployment analysis.
    # --------------------------------------------------------

    out = out.rename(
        columns={
            "human_target_attribution_judgment":
                "final_judgment",

            "human_attribution_reason_code":
                "final_reason_code",

            "human_reviewer_note":
                "final_note",
        }
    )

    out[
        "source_label_release"
    ] = (
        "openalex-retrieval-precision-review-"
        "human-adjudication-complete-v1"
    )

    out[
        "source_final_label_source"
    ] = "COMPLETE_HUMAN_ADJUDICATION"

    out[
        "direct_human_reviewed"
    ] = True

    out[
        "final_operational_disposition"
    ] = ""

    out.loc[
        out[
            "final_judgment"
        ].eq(
            "VALID_TARGET_REFERENCE"
        ),
        "final_operational_disposition",
    ] = "INCLUDE_FINAL_VALID"

    out.loc[
        out[
            "final_judgment"
        ].eq(
            "INVALID_TARGET_REFERENCE"
        ),
        "final_operational_disposition",
    ] = "EXCLUDE_FINAL_INVALID"

    out.loc[
        out[
            "final_judgment"
        ].eq(
            "UNCERTAIN"
        ),
        "final_operational_disposition",
    ] = "HOLD_UNCERTAIN"

    disposition_counts = (
        out[
            "final_operational_disposition"
        ]
        .value_counts()
        .to_dict()
    )

    expected_dispositions = {
        "INCLUDE_FINAL_VALID": 364,
        "EXCLUDE_FINAL_INVALID": 24,
        "HOLD_UNCERTAIN": 21,
    }

    assert (
        disposition_counts
        == expected_dispositions
    ), disposition_counts

    out[
        "include_in_operational_alias_indicator"
    ] = (
        out[
            "final_operational_disposition"
        ]
        .eq(
            "INCLUDE_FINAL_VALID"
        )
    )

    assert int(
        out[
            "include_in_operational_alias_indicator"
        ].sum()
    ) == 364

    assert int(
        out[
            "direct_human_reviewed"
        ].sum()
    ) == 409

    # --------------------------------------------------------
    # 6. Stable order
    # --------------------------------------------------------

    out = (
        out.sort_values(
            [
                "project_work_id",
                "openalex_work_id",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    # Drop duplicated post-hoc label columns now that
    # authoritative final columns are present.
    drop_cols = [
        c
        for c in [
            "posthoc_human_target_attribution_judgment",
            "posthoc_human_attribution_reason_code",
        ]
        if c in out.columns
    ]

    out = out.drop(
        columns=drop_cols
    )

    # --------------------------------------------------------
    # 7. Write
    # --------------------------------------------------------

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=False,
    )

    write_tsv(
        out,
        OUT_TSV,
    )

    write_parquet(
        out,
        OUT_PARQUET,
    )

    summary = {
        "release": RELEASE,
        "created_at": CREATED_AT,
        "status":
            "final_current_release_alias_marginal_disposition",

        "scope": {
            "candidate_pairs": 409,
            "project_works": 38,
            "increment_type":
                "ALIAS_EXPANSION",
            "universe_status":
                (
                    "Complete current-release "
                    "Alias marginal universe"
                ),
        },

        "human_adjudication": {
            "candidate_pairs": 409,
            "direct_human_reviewed_rows": 409,
            "VALID_TARGET_REFERENCE": 364,
            "INVALID_TARGET_REFERENCE": 24,
            "UNCERTAIN": 21,
            "missing_labels": 0,
        },

        "frozen_policy_routing": {
            "ACCEPT": 192,
            "REVIEW": 217,
        },

        "policy_action_label_crosscheck": {
            "ACCEPT": {
                "VALID_TARGET_REFERENCE": 182,
                "INVALID_TARGET_REFERENCE": 2,
                "UNCERTAIN": 8,
                "candidate_pairs": 192,
            },

            "REVIEW": {
                "VALID_TARGET_REFERENCE": 182,
                "INVALID_TARGET_REFERENCE": 22,
                "UNCERTAIN": 13,
                "candidate_pairs": 217,
            },
        },

        "final_operational_disposition_counts":
            expected_dispositions,

        "operational_include_count": 364,
        "operational_exclude_count": 24,
        "operational_hold_uncertain_count": 21,

        "interpretation": [
            (
                "The 409 Alias marginal candidate pairs "
                "constitute the complete current-release "
                "Alias marginal universe."
            ),
            (
                "All 409 candidates have direct human "
                "adjudication."
            ),
            (
                "No additional LLM adjudication is "
                "required for the current release."
            ),
            (
                "Final current-release disposition uses "
                "the authoritative human judgment."
            ),
            (
                "The frozen ACCEPT/REVIEW rule is retained "
                "as a routing policy for methodological "
                "evaluation and possible future releases; "
                "policy ACCEPT is not itself a truth label."
            ),
            (
                "UNCERTAIN remains separate from INVALID "
                "and is held rather than excluded."
            ),
            (
                "Because the current release exhausts the "
                "available Alias-expansion universe, these "
                "results are a finite-population audit, not "
                "an independent held-out validation."
            ),
            (
                "The frozen Alias policy must not be "
                "retuned from these same adjudicated data."
            ),
        ],
    }

    write_json(
        summary,
        OUT_SUMMARY,
    )

    manifest = {
        "release": RELEASE,
        "created_at": CREATED_AT,

        "sources": {
            str(
                DIAGNOSTICS.relative_to(ROOT)
            ):
                sha256_file(DIAGNOSTICS),

            str(
                HUMAN.relative_to(ROOT)
            ):
                sha256_file(HUMAN),
        },

        "outputs": {
            str(
                OUT_TSV.relative_to(ROOT)
            ):
                sha256_file(OUT_TSV),

            str(
                OUT_PARQUET.relative_to(ROOT)
            ):
                sha256_file(OUT_PARQUET),

            str(
                OUT_SUMMARY.relative_to(ROOT)
            ):
                sha256_file(OUT_SUMMARY),
        },
    }

    write_json(
        manifest,
        OUT_MANIFEST,
    )

    print(
        "=== ALIAS PRODUCTION FINAL DISPOSITION V1 ==="
    )
    print("candidate pairs:", len(out))
    print(
        "project works:",
        out[
            "project_work_id"
        ].nunique(),
    )
    print()
    print("HUMAN FINAL LABELS")
    print("VALID: 364")
    print("INVALID: 24")
    print("UNCERTAIN: 21")
    print()
    print("FROZEN POLICY")
    print("ACCEPT: 192")
    print("REVIEW: 217")
    print()
    print("FINAL OPERATIONAL DISPOSITION")
    print("INCLUDE_FINAL_VALID: 364")
    print("EXCLUDE_FINAL_INVALID: 24")
    print("HOLD_UNCERTAIN: 21")
    print()
    print("direct human reviewed: 409")
    print("output:", OUT_DIR)


if __name__ == "__main__":
    main()
