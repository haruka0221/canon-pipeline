#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

ROUTING = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_production_routing_v1"
    / "openalex_a2_production_policy_review_queue_v1.parquet"
)

CAL_CAND = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_precision_review_candidates_v3"
    / "full_profile_57959e90"
    / "openalex_retrieval_precision_review_candidates_v3.parquet"
)

CAL_LABEL = (
    ROOT
    / "derived/openalex_production"
    / "openalex_retrieval_precision_review_human_adjudication_complete_v1"
    / "full_profile_57959e90"
    / "openalex_retrieval_precision_review_human_adjudication_complete_v1.parquet"
)

HELD_CAND = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_validation_candidates_v1"
    / "openalex_a2_validation_candidates_v1.parquet"
)

HELD_LABEL = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_validation_final_labels_v1"
    / "openalex_a2_validation_final_labels_v1.tsv"
)

NEW_LABEL = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_production_new_review_final_labels_v1"
    / "openalex_a2_production_new_review_final_labels_v1.parquet"
)

OUT_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_production_review_final_labels_v1"
)

OUT_TSV = (
    OUT_DIR
    / "openalex_a2_production_review_final_labels_v1.tsv"
)

OUT_PARQUET = (
    OUT_DIR
    / "openalex_a2_production_review_final_labels_v1.parquet"
)

OUT_SUMMARY = (
    OUT_DIR
    / "openalex_a2_production_review_final_summary_v1.json"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openalex_a2_production_review_final_labels_v1_manifest.json"
)

RELEASE = "openalex-a2-production-review-final-labels-v1"
CREATED_AT = "2026-10-10"


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

    allowed = {"TRUE", "FALSE"}
    assert set(x.unique()) <= allowed

    return x.map({
        "TRUE": True,
        "FALSE": False,
    }).astype(bool)


def judgment_counts(df):
    c = (
        df["final_judgment"]
        .value_counts()
        .to_dict()
    )

    return {
        "VALID_TARGET_REFERENCE":
            int(c.get(
                "VALID_TARGET_REFERENCE",
                0,
            )),
        "INVALID_TARGET_REFERENCE":
            int(c.get(
                "INVALID_TARGET_REFERENCE",
                0,
            )),
        "UNCERTAIN":
            int(c.get(
                "UNCERTAIN",
                0,
            )),
    }


def main():

    sources = [
        ROUTING,
        CAL_CAND,
        CAL_LABEL,
        HELD_CAND,
        HELD_LABEL,
        NEW_LABEL,
    ]

    for p in sources:
        if not p.exists():
            raise FileNotFoundError(p)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory exists: {OUT_DIR}"
        )

    # ======================================================
    # 1. Frozen production REVIEW universe
    # ======================================================

    routing = pd.read_parquet(
        ROUTING
    )

    assert len(routing) == 100
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
        "policy_action"
    ].eq("REVIEW").all()

    assert routing[
        "increment_type"
    ].eq(
        "A2_AUTHOR_REVERSAL"
    ).all()

    source_counts = (
        routing[
            "evaluation_source"
        ]
        .value_counts()
        .to_dict()
    )

    assert source_counts == {
        "NEW_PRODUCTION": 48,
        "HELDOUT": 35,
        "CALIBRATION": 17,
    }, source_counts

    # ======================================================
    # 2. CALIBRATION:
    #
    # candidate pair
    #   -> review_candidate_id
    #   -> complete human adjudication
    # ======================================================

    cal_cand = pd.read_parquet(
        CAL_CAND
    )

    assert len(cal_cand) == 661
    assert cal_cand[
        "review_candidate_id"
    ].is_unique

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

    assert not cal_a2[
        [
            "project_work_id",
            "openalex_work_id",
        ]
    ].duplicated().any()

    cal_lab = pd.read_parquet(
        CAL_LABEL
    )

    assert len(cal_lab) == 661
    assert cal_lab[
        "review_candidate_id"
    ].is_unique

    cal_all_counts = (
        cal_lab[
            "human_target_attribution_judgment"
        ]
        .value_counts()
        .to_dict()
    )

    assert cal_all_counts == {
        "VALID_TARGET_REFERENCE": 605,
        "INVALID_TARGET_REFERENCE": 34,
        "UNCERTAIN": 22,
    }, cal_all_counts

    cal_map = cal_a2.merge(
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

    assert len(cal_map) == 252

    assert cal_map[
        "human_target_attribution_judgment"
    ].ne("").all()

    cal_map = cal_map.rename(
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

    cal_map["evaluation_source"] = (
        "CALIBRATION"
    )

    cal_map["source_label_release"] = (
        "openalex-retrieval-precision-review-"
        "human-adjudication-complete-v1"
    )

    cal_map["source_final_label_source"] = (
        "COMPLETE_HUMAN_ADJUDICATION"
    )

    cal_map["direct_human_reviewed"] = True

    # ======================================================
    # 3. HELDOUT:
    #
    # pair
    #   -> validation_candidate_id
    #   -> held-out final label
    # ======================================================

    held_cand = pd.read_parquet(
        HELD_CAND
    )

    assert len(held_cand) == 248
    assert held_cand[
        "validation_candidate_id"
    ].is_unique

    assert not held_cand[
        [
            "project_work_id",
            "openalex_work_id",
        ]
    ].duplicated().any()

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

    held_counts = (
        held_lab[
            "final_judgment"
        ]
        .value_counts()
        .to_dict()
    )

    assert held_counts == {
        "VALID_TARGET_REFERENCE": 243,
        "INVALID_TARGET_REFERENCE": 5,
    }, held_counts

    held_map = (
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

    held_map = held_map.rename(
        columns={
            "validation_candidate_id":
                "source_candidate_id",
            "final_label_source":
                "source_final_label_source",
        }
    )

    held_map[
        "direct_human_reviewed"
    ] = parse_bool_series(
        held_map["human_reviewed"]
    )

    held_map = held_map.drop(
        columns=["human_reviewed"]
    )

    held_map["evaluation_source"] = (
        "HELDOUT"
    )

    held_map["source_label_release"] = (
        "openalex-a2-validation-final-labels-v1"
    )

    # No named human reviewer fields in the standardized
    # held-out final-label layer.
    held_map["human_reviewer_id"] = ""
    held_map["human_adjudicated_at_utc"] = ""

    # ======================================================
    # 4. NEW PRODUCTION:
    #
    # already has pair identity + final labels
    # ======================================================

    new = pd.read_parquet(
        NEW_LABEL
    )

    assert len(new) == 48

    assert new[
        "production_candidate_id"
    ].is_unique

    assert not new[
        [
            "project_work_id",
            "openalex_work_id",
        ]
    ].duplicated().any()

    new_counts = (
        new[
            "final_judgment"
        ]
        .value_counts()
        .to_dict()
    )

    assert new_counts == {
        "INVALID_TARGET_REFERENCE": 24,
        "VALID_TARGET_REFERENCE": 23,
        "UNCERTAIN": 1,
    }, new_counts

    new_map = new[
        [
            "production_candidate_id",
            "project_work_id",
            "openalex_work_id",
            "direct_human_reviewed",
            "final_judgment",
            "final_reason_code",
            "final_label_source",
            "human_notes",
            "llm_first_pass_note",
        ]
    ].copy()

    new_map = new_map.rename(
        columns={
            "production_candidate_id":
                "source_candidate_id",
            "final_label_source":
                "source_final_label_source",
        }
    )

    new_map["final_note"] = (
        new_map["llm_first_pass_note"]
    )

    hm = new_map[
        "direct_human_reviewed"
    ].astype(bool)

    new_map.loc[
        hm,
        "final_note",
    ] = new_map.loc[
        hm,
        "human_notes",
    ]

    new_map = new_map.drop(
        columns=[
            "human_notes",
            "llm_first_pass_note",
        ]
    )

    new_map["evaluation_source"] = (
        "NEW_PRODUCTION"
    )

    new_map["source_label_release"] = (
        "openalex-a2-production-new-review-"
        "final-labels-v1"
    )

    new_map["human_reviewer_id"] = ""
    new_map["human_adjudicated_at_utc"] = ""

    # ======================================================
    # 5. Standardize three provenance layers
    # ======================================================

    label_columns = [
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

    labels = pd.concat(
        [
            cal_map[label_columns],
            held_map[label_columns],
            new_map[label_columns],
        ],
        ignore_index=True,
    )

    assert len(labels) == (
        252 + 248 + 48
    )

    assert not labels[
        [
            "evaluation_source",
            "project_work_id",
            "openalex_work_id",
        ]
    ].duplicated().any()

    # ======================================================
    # 6. Merge labels onto frozen production REVIEW 100
    # ======================================================

    out = routing.merge(
        labels,
        on=[
            "evaluation_source",
            "project_work_id",
            "openalex_work_id",
        ],
        how="left",
        validate="one_to_one",
    )

    assert len(out) == 100

    assert out[
        "final_judgment"
    ].notna().all()

    assert out[
        "source_candidate_id"
    ].notna().all()

    allowed = {
        "VALID_TARGET_REFERENCE",
        "INVALID_TARGET_REFERENCE",
        "UNCERTAIN",
    }

    assert set(
        out["final_judgment"]
    ) <= allowed

    # ======================================================
    # 7. Frozen expected outcome counts
    # ======================================================

    expected_by_source = {
        "CALIBRATION": {
            "VALID_TARGET_REFERENCE": 7,
            "INVALID_TARGET_REFERENCE": 10,
            "UNCERTAIN": 0,
        },
        "HELDOUT": {
            "VALID_TARGET_REFERENCE": 31,
            "INVALID_TARGET_REFERENCE": 4,
            "UNCERTAIN": 0,
        },
        "NEW_PRODUCTION": {
            "VALID_TARGET_REFERENCE": 23,
            "INVALID_TARGET_REFERENCE": 24,
            "UNCERTAIN": 1,
        },
    }

    actual_by_source = {}

    for source in [
        "CALIBRATION",
        "HELDOUT",
        "NEW_PRODUCTION",
    ]:
        g = out.loc[
            out[
                "evaluation_source"
            ].eq(source)
        ]

        actual_by_source[source] = (
            judgment_counts(g)
        )

    assert (
        actual_by_source
        == expected_by_source
    ), actual_by_source

    final_counts = judgment_counts(out)

    assert final_counts == {
        "VALID_TARGET_REFERENCE": 61,
        "INVALID_TARGET_REFERENCE": 38,
        "UNCERTAIN": 1,
    }, final_counts

    assert out[
        "policy_action"
    ].eq("REVIEW").all()

    assert out[
        "production_candidate_id"
    ].is_unique

    # Direct human review is provenance, not a validity
    # criterion. Do not relabel unreviewed rows.
    direct_human_count = int(
        out[
            "direct_human_reviewed"
        ].astype(bool).sum()
    )

    # ======================================================
    # 8. Stable ordering + outputs
    # ======================================================

    source_order = {
        "CALIBRATION": 0,
        "HELDOUT": 1,
        "NEW_PRODUCTION": 2,
    }

    out["_source_order"] = (
        out[
            "evaluation_source"
        ].map(source_order)
    )

    out = (
        out.sort_values(
            [
                "_source_order",
                "project_work_id",
                "openalex_work_id",
            ],
            kind="stable",
        )
        .drop(
            columns=["_source_order"]
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

    valid = final_counts[
        "VALID_TARGET_REFERENCE"
    ]

    invalid = final_counts[
        "INVALID_TARGET_REFERENCE"
    ]

    uncertain = final_counts[
        "UNCERTAIN"
    ]

    resolved_n = valid + invalid

    summary = {
        "release": RELEASE,
        "created_at": CREATED_AT,
        "status": (
            "final_production_review_queue_labels"
        ),

        "scope": {
            "policy_action": "REVIEW",
            "increment_type": "A2_AUTHOR_REVERSAL",
            "candidate_rows": 100,
            "project_works": int(
                out[
                    "project_work_id"
                ].nunique()
            ),
        },

        "evaluation_source_counts": {
            "CALIBRATION": 17,
            "HELDOUT": 35,
            "NEW_PRODUCTION": 48,
        },

        "final_judgment_counts": final_counts,

        "final_judgment_counts_by_evaluation_source":
            actual_by_source,

        "direct_human_reviewed_rows":
            direct_human_count,

        "descriptive_review_queue_rates": {
            "confirmed_valid_share":
                valid / 100,
            "upper_valid_share_if_uncertain_valid":
                (valid + uncertain) / 100,
            "resolved_valid_share_excluding_uncertain":
                valid / resolved_n,
        },

        "interpretation": [
            (
                "This artifact resolves the frozen 100-candidate "
                "A2 policy REVIEW queue only."
            ),
            (
                "UNCERTAIN remains separate from INVALID and is "
                "not treated as a false positive."
            ),
            (
                "Label provenance differs across CALIBRATION, "
                "HELDOUT, and NEW_PRODUCTION and is preserved "
                "row by row."
            ),
            (
                "Not every final VALID label in this artifact "
                "received direct human review."
            ),
            (
                "These outcomes must not be used to retune the "
                "already frozen A2 routing policy."
            ),
            (
                "This artifact does not validate the 863 "
                "production ACCEPT candidates or the global A1 "
                "baseline."
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
            str(OUT_TSV.relative_to(ROOT)):
                sha256_file(OUT_TSV),

            str(OUT_PARQUET.relative_to(ROOT)):
                sha256_file(OUT_PARQUET),

            str(OUT_SUMMARY.relative_to(ROOT)):
                sha256_file(OUT_SUMMARY),
        },
    }

    write_json(
        manifest,
        OUT_MANIFEST,
    )

    print(
        "=== A2 PRODUCTION REVIEW FINAL LABELS V1 ==="
    )
    print("candidate rows:", len(out))
    print(
        "project works:",
        out[
            "project_work_id"
        ].nunique(),
    )
    print()
    print("CALIBRATION:    V7  I10 U0")
    print("HELDOUT:        V31 I4  U0")
    print("NEW_PRODUCTION: V23 I24 U1")
    print()
    print("ALL REVIEW:")
    print("VALID:", valid)
    print("INVALID:", invalid)
    print("UNCERTAIN:", uncertain)
    print(
        "direct human reviewed:",
        direct_human_count,
    )
    print(
        "confirmed valid share:",
        f"{valid / 100:.4%}",
    )
    print(
        "upper valid share:",
        f"{(valid + uncertain) / 100:.4%}",
    )
    print(
        "resolved valid share:",
        f"{valid / resolved_n:.4%}",
    )
    print("output:", OUT_DIR)


if __name__ == "__main__":
    main()
