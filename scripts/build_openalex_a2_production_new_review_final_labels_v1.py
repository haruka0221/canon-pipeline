#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

LLM_TSV = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_production_review_llm_first_pass_v1"
    / "openalex_a2_production_review_llm_first_pass_v1.tsv"
)

HUMAN_TSV = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_production_human_review_final_v1"
    / "openalex_a2_production_human_review_final_v1.tsv"
)

OUT_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_production_new_review_final_labels_v1"
)

OUT_TSV = (
    OUT_DIR
    / "openalex_a2_production_new_review_final_labels_v1.tsv"
)

OUT_PARQUET = (
    OUT_DIR
    / "openalex_a2_production_new_review_final_labels_v1.parquet"
)

OUT_SUMMARY = (
    OUT_DIR
    / "openalex_a2_production_new_review_final_labels_summary_v1.json"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openalex_a2_production_new_review_final_labels_v1_manifest.json"
)

RELEASE = "openalex-a2-production-new-review-final-labels-v1"
CREATED_AT = "2026-10-10"


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
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

    for p in [LLM_TSV, HUMAN_TSV]:
        if not p.exists():
            raise FileNotFoundError(p)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory exists: {OUT_DIR}"
        )

    llm = pd.read_csv(
        LLM_TSV,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    human = pd.read_csv(
        HUMAN_TSV,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    # --------------------------------------------------
    # Frozen-input invariants
    # --------------------------------------------------

    assert len(llm) == 48
    assert llm["production_candidate_id"].is_unique

    assert len(human) == 25
    assert human["production_candidate_id"].is_unique

    llm_nonvalid_ids = set(
        llm.loc[
            ~llm[
                "llm_first_pass_judgment"
            ].eq("VALID_TARGET_REFERENCE"),
            "production_candidate_id",
        ]
    )

    human_ids = set(
        human["production_candidate_id"]
    )

    # Human review must cover exactly every LLM-nonvalid case.
    assert len(llm_nonvalid_ids) == 25
    assert human_ids == llm_nonvalid_ids

    # The 23 cases not directly human-reviewed must all have
    # been blind first-pass VALID.
    llm_valid_ids = set(
        llm.loc[
            llm[
                "llm_first_pass_judgment"
            ].eq("VALID_TARGET_REFERENCE"),
            "production_candidate_id",
        ]
    )

    assert len(llm_valid_ids) == 23
    assert llm_valid_ids.isdisjoint(human_ids)

    # --------------------------------------------------
    # Merge human outcomes onto the 48-candidate layer.
    # Drop original blank human columns first.
    # --------------------------------------------------

    base = llm.drop(
        columns=[
            "human_judgment",
            "human_reason_code",
            "human_notes",
        ],
        errors="raise",
    ).copy()

    h = human[
        [
            "production_candidate_id",
            "human_judgment",
            "human_reason_code",
            "human_notes",
        ]
    ].copy()

    out = base.merge(
        h,
        on="production_candidate_id",
        how="left",
        validate="one_to_one",
    )

    for c in [
        "human_judgment",
        "human_reason_code",
        "human_notes",
    ]:
        out[c] = out[c].fillna("")

    out["direct_human_reviewed"] = (
        out["human_judgment"].ne("")
    )

    assert int(
        out["direct_human_reviewed"].sum()
    ) == 25

    # --------------------------------------------------
    # Final label:
    # human judgment overrides LLM first pass where
    # direct human review occurred.
    #
    # Otherwise the blind LLM VALID is retained, but
    # provenance explicitly states that it was not
    # directly human reviewed.
    # --------------------------------------------------

    out["final_judgment"] = out[
        "llm_first_pass_judgment"
    ]

    out["final_reason_code"] = out[
        "llm_first_pass_reason_code"
    ]

    m = out["direct_human_reviewed"]

    out.loc[
        m,
        "final_judgment",
    ] = out.loc[
        m,
        "human_judgment",
    ]

    out.loc[
        m,
        "final_reason_code",
    ] = out.loc[
        m,
        "human_reason_code",
    ]

    out["final_label_source"] = (
        "BLIND_LLM_FIRST_PASS_VALID_NO_DIRECT_HUMAN_REVIEW"
    )

    out.loc[
        m,
        "final_label_source",
    ] = (
        "DIRECT_HUMAN_REVIEW_AFTER_LLM_NONVALID"
    )

    # Non-human-reviewed rows must still all be VALID.
    assert out.loc[
        ~m,
        "final_judgment",
    ].eq(
        "VALID_TARGET_REFERENCE"
    ).all()

    # Human reviewed rows:
    # 24 invalid + 1 uncertain.
    human_counts = (
        out.loc[
            m,
            "final_judgment",
        ]
        .value_counts()
        .to_dict()
    )

    assert human_counts == {
        "INVALID_TARGET_REFERENCE": 24,
        "UNCERTAIN": 1,
    }

    final_counts = (
        out["final_judgment"]
        .value_counts()
        .to_dict()
    )

    expected_final = {
        "VALID_TARGET_REFERENCE": 23,
        "INVALID_TARGET_REFERENCE": 24,
        "UNCERTAIN": 1,
    }

    assert final_counts == expected_final, final_counts

    # Descriptive agreement only:
    # all 25 LLM-nonvalid cases were confirmed without
    # changing category in direct review.
    agreement = (
        out.loc[
            m,
            "llm_first_pass_judgment",
        ].reset_index(drop=True)
        ==
        out.loc[
            m,
            "human_judgment",
        ].reset_index(drop=True)
    )

    assert agreement.all()

    out = (
        out.sort_values(
            [
                "project_work_id",
                "production_candidate_id",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    assert len(out) == 48
    assert out["project_work_id"].nunique() == 20

    # --------------------------------------------------
    # Write
    # --------------------------------------------------

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=False,
    )

    write_tsv(out, OUT_TSV)
    write_parquet(out, OUT_PARQUET)

    summary = {
        "release": RELEASE,
        "created_at": CREATED_AT,

        "candidate_rows": 48,
        "project_works": 20,

        "final_judgment_counts": expected_final,

        "direct_human_review": {
            "candidate_rows": 25,
            "project_works": int(
                out.loc[
                    m,
                    "project_work_id",
                ].nunique()
            ),
            "invalid": 24,
            "uncertain": 1,
            "valid": 0,
            "llm_human_category_agreement": "25/25",
        },

        "not_directly_human_reviewed": {
            "candidate_rows": 23,
            "judgment": "VALID_TARGET_REFERENCE",
            "label_source": (
                "BLIND_LLM_FIRST_PASS_VALID_NO_DIRECT_HUMAN_REVIEW"
            ),
        },

        "interpretation": [
            (
                "The 23 VALID labels retained from the blind LLM "
                "first pass were not directly human reviewed."
            ),
            (
                "All 25 first-pass non-VALID cases received direct "
                "human review."
            ),
            (
                "UNCERTAIN remains distinct from INVALID."
            ),
            (
                "These production-review outcomes must not be used "
                "to retune the frozen A2 routing policy."
            ),
        ],
    }

    write_json(summary, OUT_SUMMARY)

    manifest = {
        "release": RELEASE,
        "created_at": CREATED_AT,

        "sources": {
            str(
                LLM_TSV.relative_to(ROOT)
            ):
                sha256_file(LLM_TSV),

            str(
                HUMAN_TSV.relative_to(ROOT)
            ):
                sha256_file(HUMAN_TSV),
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

    write_json(manifest, OUT_MANIFEST)

    print(
        "=== A2 PRODUCTION NEW REVIEW FINAL LABELS V1 ==="
    )
    print("candidate rows:", len(out))
    print(
        "project works:",
        out["project_work_id"].nunique(),
    )
    print("VALID:", 23)
    print("INVALID:", 24)
    print("UNCERTAIN:", 1)
    print("direct human reviewed:", 25)
    print("LLM-valid not directly human reviewed:", 23)
    print("LLM/human agreement on reviewed cases: 25/25")
    print("output:", OUT_DIR)


if __name__ == "__main__":
    main()
