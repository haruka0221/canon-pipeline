#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

# Full frozen A2 marginal production universe: 963 pairs
ROUTING = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_production_routing_v1"
    / "openalex_a2_production_candidates_v1.parquet"
)

# Calibration candidate identity: 252 A2 pairs among 661 candidates
CAL_CAND = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_precision_review_candidates_v3"
    / "full_profile_57959e90"
    / "openalex_retrieval_precision_review_candidates_v3.parquet"
)

# Calibration complete human adjudication: all 661
CAL_LABEL = (
    ROOT
    / "derived/openalex_production"
    / "openalex_retrieval_precision_review_human_adjudication_complete_v1"
    / "full_profile_57959e90"
    / "openalex_retrieval_precision_review_human_adjudication_complete_v1.parquet"
)

# Held-out candidate identity: 248 pairs
HELD_CAND = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_validation_candidates_v1"
    / "openalex_a2_validation_candidates_v1.parquet"
)

# Held-out final labels: 248
HELD_LABEL = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_validation_final_labels_v1"
    / "openalex_a2_validation_final_labels_v1.tsv"
)

# Frozen REVIEW-100 final labels.
# For this script we use only its 48 NEW_PRODUCTION rows.
REVIEW_FINAL = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_production_review_final_labels_v1"
    / "openalex_a2_production_review_final_labels_v1.parquet"
)

OUT_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_production_final_disposition_v1"
)

OUT_TSV = (
    OUT_DIR
    / "openalex_a2_production_final_disposition_v1.tsv"
)

OUT_PARQUET = (
    OUT_DIR
    / "openalex_a2_production_final_disposition_v1.parquet"
)

OUT_SUMMARY = (
    OUT_DIR
    / "openalex_a2_production_final_disposition_summary_v1.json"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openalex_a2_production_final_disposition_v1_manifest.json"
)

RELEASE = "openalex-a2-production-final-disposition-v1"
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


def parse_bool_series(s):
    x = (
        s.astype(str)
        .str.strip()
        .str.upper()
    )

    assert set(x.unique()) <= {
        "TRUE",
        "FALSE",
    }

    return x.map({
        "TRUE": True,
        "FALSE": False,
    }).astype(bool)


def counts_with_unlabeled(df):
    vc = (
        df["final_judgment"]
        .fillna("")
        .value_counts()
        .to_dict()
    )

    return {
        "VALID_TARGET_REFERENCE":
            int(vc.get(
                "VALID_TARGET_REFERENCE",
                0,
            )),
        "INVALID_TARGET_REFERENCE":
            int(vc.get(
                "INVALID_TARGET_REFERENCE",
                0,
            )),
        "UNCERTAIN":
            int(vc.get(
                "UNCERTAIN",
                0,
            )),
        "UNADJUDICATED":
            int(vc.get("", 0)),
    }


def main():

    sources = [
        ROUTING,
        CAL_CAND,
        CAL_LABEL,
        HELD_CAND,
        HELD_LABEL,
        REVIEW_FINAL,
    ]

    for p in sources:
        if not p.exists():
            raise FileNotFoundError(p)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory exists: {OUT_DIR}"
        )

    # ======================================================
    # 1. Frozen 963-candidate A2 marginal universe
    # ======================================================

    routing = pd.read_parquet(
        ROUTING
    )

    assert len(routing) == 963

    assert routing[
        "production_candidate_id"
    ].is_unique

    assert not routing[
        [
            "project_work_id",
            "openalex_work_id",
        ]
    ].duplicated().any()

    assert routing[
        "increment_type"
    ].eq(
        "A2_AUTHOR_REVERSAL"
    ).all()

    assert (
        routing[
            "project_work_id"
        ].nunique()
        == 231
    )

    assert routing[
        "policy_action"
    ].value_counts().to_dict() == {
        "ACCEPT": 863,
        "REVIEW": 100,
    }

    assert routing[
        "evaluation_source"
    ].value_counts().to_dict() == {
        "NEW_PRODUCTION": 463,
        "CALIBRATION": 252,
        "HELDOUT": 248,
    }

    # ======================================================
    # 2. Calibration labels:
    # all 252 A2 calibration candidates have
    # complete human adjudication.
    # ======================================================

    cal_cand = pd.read_parquet(
        CAL_CAND
    )

    cal_a2 = (
        cal_cand.loc[
            cal_cand[
                "increment_type"
            ].eq(
                "A2_AUTHOR_REVERSAL"
            ),
            [
                "review_candidate_id",
                "project_work_id",
                "openalex_work_id",
            ],
        ]
        .copy()
    )

    assert len(cal_a2) == 252

    assert cal_a2[
        "review_candidate_id"
    ].is_unique

    cal_lab = pd.read_parquet(
        CAL_LABEL
    )

    assert len(cal_lab) == 661

    assert cal_lab[
        "review_candidate_id"
    ].is_unique

    cal = cal_a2.merge(
        cal_lab[
            [
                "review_candidate_id",
                "human_target_attribution_judgment",
                "human_attribution_reason_code",
                "human_reviewer_note",
                "human_reviewer_id",
                "human_adjudicated_at_utc",
            ]
        ],
        on="review_candidate_id",
        how="left",
        validate="one_to_one",
    )

    assert cal[
        "human_target_attribution_judgment"
    ].notna().all()

    assert (
        cal[
            "human_target_attribution_judgment"
        ]
        .value_counts()
        .to_dict()
        == {
            "VALID_TARGET_REFERENCE": 241,
            "INVALID_TARGET_REFERENCE": 10,
            "UNCERTAIN": 1,
        }
    )

    cal = cal.rename(
        columns={
            "review_candidate_id":
                "source_candidate_id",

            "human_target_attribution_judgment":
                "final_judgment",

            "human_attribution_reason_code":
                "final_reason_code",

            "human_reviewer_note":
                "final_note",
        }
    )

    cal["evaluation_source"] = "CALIBRATION"

    cal["source_label_release"] = (
        "openalex-retrieval-precision-review-"
        "human-adjudication-complete-v1"
    )

    cal["source_final_label_source"] = (
        "COMPLETE_HUMAN_ADJUDICATION"
    )

    cal["direct_human_reviewed"] = True

    # ======================================================
    # 3. Held-out labels:
    # all 248 have operational final labels,
    # with human-review provenance retained.
    # ======================================================

    held_cand = pd.read_parquet(
        HELD_CAND
    )

    assert len(held_cand) == 248

    assert held_cand[
        "validation_candidate_id"
    ].is_unique

    held_lab = pd.read_csv(
        HELD_LABEL,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    assert len(held_lab) == 248

    assert held_lab[
        "validation_candidate_id"
    ].is_unique

    assert (
        held_lab[
            "final_judgment"
        ]
        .value_counts()
        .to_dict()
        == {
            "VALID_TARGET_REFERENCE": 243,
            "INVALID_TARGET_REFERENCE": 5,
        }
    )

    held = (
        held_cand[
            [
                "validation_candidate_id",
                "project_work_id",
                "openalex_work_id",
            ]
        ]
        .merge(
            held_lab[
                [
                    "validation_candidate_id",
                    "human_reviewed",
                    "final_judgment",
                    "final_reason_code",
                    "final_label_source",
                    "final_note",
                ]
            ],
            on="validation_candidate_id",
            how="left",
            validate="one_to_one",
        )
    )

    held = held.rename(
        columns={
            "validation_candidate_id":
                "source_candidate_id",

            "final_label_source":
                "source_final_label_source",
        }
    )

    held[
        "direct_human_reviewed"
    ] = parse_bool_series(
        held["human_reviewed"]
    )

    assert int(
        held[
            "direct_human_reviewed"
        ].sum()
    ) == 5

    held = held.drop(
        columns=["human_reviewed"]
    )

    held["evaluation_source"] = "HELDOUT"

    held["source_label_release"] = (
        "openalex-a2-validation-final-labels-v1"
    )

    held["human_reviewer_id"] = ""
    held["human_adjudicated_at_utc"] = ""

    # ======================================================
    # 4. NEW_PRODUCTION REVIEW labels:
    # 48 review candidates only.
    #
    # The remaining 415 NEW_PRODUCTION ACCEPT rows remain
    # explicitly unadjudicated.
    # ======================================================

    review_final = pd.read_parquet(
        REVIEW_FINAL
    )

    assert len(review_final) == 100

    new_review = (
        review_final.loc[
            review_final[
                "evaluation_source"
            ].eq(
                "NEW_PRODUCTION"
            ),
            [
                "production_candidate_id",
                "project_work_id",
                "openalex_work_id",
                "source_candidate_id",
                "source_label_release",
                "source_final_label_source",
                "direct_human_reviewed",
                "final_judgment",
                "final_reason_code",
                "final_note",
                "human_reviewer_id",
                "human_adjudicated_at_utc",
            ],
        ]
        .copy()
    )

    assert len(new_review) == 48

    assert (
        new_review[
            "final_judgment"
        ]
        .value_counts()
        .to_dict()
        == {
            "INVALID_TARGET_REFERENCE": 24,
            "VALID_TARGET_REFERENCE": 23,
            "UNCERTAIN": 1,
        }
    )

    assert int(
        new_review[
            "direct_human_reviewed"
        ].astype(bool).sum()
    ) == 25

    new_review[
        "evaluation_source"
    ] = "NEW_PRODUCTION"

    # ======================================================
    # 5. Standardize all known label sources
    # ======================================================

    label_cols = [
        "evaluation_source",
        "project_work_id",
        "openalex_work_id",
        "source_candidate_id",
        "source_label_release",
        "source_final_label_source",
        "direct_human_reviewed",
        "final_judgment",
        "final_reason_code",
        "final_note",
        "human_reviewer_id",
        "human_adjudicated_at_utc",
    ]

    known = pd.concat(
        [
            cal[label_cols],
            held[label_cols],
            new_review[label_cols],
        ],
        ignore_index=True,
    )

    assert len(known) == 548

    assert not known[
        [
            "evaluation_source",
            "project_work_id",
            "openalex_work_id",
        ]
    ].duplicated().any()

    assert (
        known[
            "final_judgment"
        ]
        .value_counts()
        .to_dict()
        == {
            "VALID_TARGET_REFERENCE": 507,
            "INVALID_TARGET_REFERENCE": 39,
            "UNCERTAIN": 2,
        }
    )

    # ======================================================
    # 6. Merge known labels onto all 963 production pairs
    # ======================================================

    out = routing.merge(
        known,
        on=[
            "evaluation_source",
            "project_work_id",
            "openalex_work_id",
        ],
        how="left",
        validate="one_to_one",
    )

    assert len(out) == 963

    # Normalize missing string provenance fields.
    string_cols = [
        "source_candidate_id",
        "source_label_release",
        "source_final_label_source",
        "final_judgment",
        "final_reason_code",
        "final_note",
        "human_reviewer_id",
        "human_adjudicated_at_utc",
    ]

    for c in string_cols:
        out[c] = out[c].fillna("")

    out[
        "direct_human_reviewed"
    ] = (
        out[
            "direct_human_reviewed"
        ]
        .fillna(False)
        .astype(bool)
    )

    out["has_final_adjudication_label"] = (
        out[
            "final_judgment"
        ].ne("")
    )

    assert int(
        out[
            "has_final_adjudication_label"
        ].sum()
    ) == 548

    assert int(
        out[
            "direct_human_reviewed"
        ].sum()
    ) == 282

    # Every unlabeled row must be exactly a
    # NEW_PRODUCTION policy ACCEPT.
    unlabeled = out.loc[
        ~out[
            "has_final_adjudication_label"
        ]
    ]

    assert len(unlabeled) == 415

    assert unlabeled[
        "evaluation_source"
    ].eq(
        "NEW_PRODUCTION"
    ).all()

    assert unlabeled[
        "policy_action"
    ].eq(
        "ACCEPT"
    ).all()

    # ======================================================
    # 7. Final operational disposition
    #
    # IMPORTANT:
    # policy ACCEPT is not rewritten as VALID.
    # ======================================================

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

    out.loc[
        ~out[
            "has_final_adjudication_label"
        ],
        "final_operational_disposition",
    ] = (
        "INCLUDE_POLICY_ACCEPT_UNADJUDICATED"
    )

    disposition_counts = (
        out[
            "final_operational_disposition"
        ]
        .value_counts()
        .to_dict()
    )

    expected_dispositions = {
        "INCLUDE_FINAL_VALID": 507,
        "INCLUDE_POLICY_ACCEPT_UNADJUDICATED": 415,
        "EXCLUDE_FINAL_INVALID": 39,
        "HOLD_UNCERTAIN": 2,
    }

    assert (
        disposition_counts
        == expected_dispositions
    ), disposition_counts

    out[
        "include_in_operational_a2_indicator"
    ] = out[
        "final_operational_disposition"
    ].isin([
        "INCLUDE_FINAL_VALID",
        "INCLUDE_POLICY_ACCEPT_UNADJUDICATED",
    ])

    assert int(
        out[
            "include_in_operational_a2_indicator"
        ].sum()
    ) == 922

    # ======================================================
    # 8. Critical cross-checks by policy action
    # ======================================================

    accept = out.loc[
        out[
            "policy_action"
        ].eq("ACCEPT")
    ]

    review = out.loc[
        out[
            "policy_action"
        ].eq("REVIEW")
    ]

    assert len(accept) == 863
    assert len(review) == 100

    # ACCEPT is NOT equivalent to adjudicated VALID.
    assert counts_with_unlabeled(
        accept
    ) == {
        "VALID_TARGET_REFERENCE": 446,
        "INVALID_TARGET_REFERENCE": 1,
        "UNCERTAIN": 1,
        "UNADJUDICATED": 415,
    }

    assert counts_with_unlabeled(
        review
    ) == {
        "VALID_TARGET_REFERENCE": 61,
        "INVALID_TARGET_REFERENCE": 38,
        "UNCERTAIN": 1,
        "UNADJUDICATED": 0,
    }

    # ======================================================
    # 9. Cross-checks by evaluation source
    # ======================================================

    cal_out = out.loc[
        out[
            "evaluation_source"
        ].eq("CALIBRATION")
    ]

    held_out = out.loc[
        out[
            "evaluation_source"
        ].eq("HELDOUT")
    ]

    new_out = out.loc[
        out[
            "evaluation_source"
        ].eq("NEW_PRODUCTION")
    ]

    assert counts_with_unlabeled(
        cal_out
    ) == {
        "VALID_TARGET_REFERENCE": 241,
        "INVALID_TARGET_REFERENCE": 10,
        "UNCERTAIN": 1,
        "UNADJUDICATED": 0,
    }

    assert counts_with_unlabeled(
        held_out
    ) == {
        "VALID_TARGET_REFERENCE": 243,
        "INVALID_TARGET_REFERENCE": 5,
        "UNCERTAIN": 0,
        "UNADJUDICATED": 0,
    }

    assert counts_with_unlabeled(
        new_out
    ) == {
        "VALID_TARGET_REFERENCE": 23,
        "INVALID_TARGET_REFERENCE": 24,
        "UNCERTAIN": 1,
        "UNADJUDICATED": 415,
    }

    # ======================================================
    # 10. Stable ordering + write
    # ======================================================

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
        "status": (
            "final_operational_a2_marginal_disposition"
        ),

        "scope": {
            "candidate_pairs": 963,
            "project_works": 231,
            "increment_type":
                "A2_AUTHOR_REVERSAL",
        },

        "frozen_policy_routing": {
            "ACCEPT": 863,
            "REVIEW": 100,
        },

        "evaluation_source_counts": {
            "CALIBRATION": 252,
            "HELDOUT": 248,
            "NEW_PRODUCTION": 463,
        },

        "known_final_labels": {
            "candidate_pairs": 548,
            "VALID_TARGET_REFERENCE": 507,
            "INVALID_TARGET_REFERENCE": 39,
            "UNCERTAIN": 2,
        },

        "unadjudicated_policy_accept": {
            "candidate_pairs": 415,
            "evaluation_source":
                "NEW_PRODUCTION",
            "policy_action":
                "ACCEPT",
        },

        "policy_action_label_crosscheck": {
            "ACCEPT": {
                "candidate_pairs": 863,
                "VALID_TARGET_REFERENCE": 446,
                "INVALID_TARGET_REFERENCE": 1,
                "UNCERTAIN": 1,
                "UNADJUDICATED": 415,
            },
            "REVIEW": {
                "candidate_pairs": 100,
                "VALID_TARGET_REFERENCE": 61,
                "INVALID_TARGET_REFERENCE": 38,
                "UNCERTAIN": 1,
                "UNADJUDICATED": 0,
            },
        },

        "final_operational_disposition_counts":
            expected_dispositions,

        "operational_include_count": 922,
        "operational_exclude_count": 39,
        "operational_hold_uncertain_count": 2,

        "direct_human_reviewed_rows":
            int(
                out[
                    "direct_human_reviewed"
                ].sum()
            ),

        "interpretation": [
            (
                "Policy ACCEPT is not equivalent to "
                "adjudicated VALID."
            ),
            (
                "Known calibration and held-out labels "
                "are applied even when the frozen policy "
                "action was ACCEPT."
            ),
            (
                "The 415 NEW_PRODUCTION ACCEPT pairs "
                "without individual adjudication retain "
                "their frozen policy status and are "
                "explicitly marked unadjudicated."
            ),
            (
                "UNCERTAIN remains distinct from INVALID "
                "and is held separately."
            ),
            (
                "Operational inclusion of an unadjudicated "
                "policy ACCEPT does not constitute a claim "
                "of human-validated correctness."
            ),
            (
                "The frozen A2 routing rule is not retuned "
                "from these adjudication outcomes."
            ),
            (
                "This artifact concerns the A2 marginal "
                "candidate universe only and does not "
                "validate the global A1 baseline."
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
            str(p.relative_to(ROOT)):
                sha256_file(p)
            for p in sources
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
        "=== A2 PRODUCTION FINAL DISPOSITION V1 ==="
    )
    print("candidate pairs:", len(out))
    print(
        "project works:",
        out[
            "project_work_id"
        ].nunique(),
    )
    print()
    print("FROZEN POLICY")
    print("ACCEPT: 863")
    print("REVIEW: 100")
    print()
    print("KNOWN FINAL LABELS")
    print("VALID: 507")
    print("INVALID: 39")
    print("UNCERTAIN: 2")
    print("UNADJUDICATED POLICY ACCEPT: 415")
    print()
    print("OPERATIONAL DISPOSITION")
    print("INCLUDE_FINAL_VALID: 507")
    print(
        "INCLUDE_POLICY_ACCEPT_UNADJUDICATED: 415"
    )
    print("EXCLUDE_FINAL_INVALID: 39")
    print("HOLD_UNCERTAIN: 2")
    print()
    print("operational include:", 922)
    print(
        "direct human reviewed:",
        int(
            out[
                "direct_human_reviewed"
            ].sum()
        ),
    )
    print("output:", OUT_DIR)


if __name__ == "__main__":
    main()
