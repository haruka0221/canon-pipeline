#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

BLIND = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_production_review_input_v1"
    / "openalex_a2_production_review_blind_v1.tsv"
)

LLM = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_production_review_llm_first_pass_v1"
    / "openalex_a2_production_review_llm_first_pass_v1.tsv"
)

OUT_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_production_human_review_queue_v1"
)

OUT_TSV = (
    OUT_DIR
    / "openalex_a2_production_human_review_queue_v1.tsv"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openalex_a2_production_human_review_queue_v1_manifest.json"
)

RELEASE = "openalex-a2-production-human-review-queue-v1"
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
    tmp = path.with_name(
        path.name + ".tmp"
    )
    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )
    os.replace(tmp, path)


def write_json(obj, path):
    tmp = path.with_name(
        path.name + ".tmp"
    )
    tmp.write_text(
        json.dumps(
            obj,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def main():

    for p in [BLIND, LLM]:
        if not p.exists():
            raise FileNotFoundError(p)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory exists: {OUT_DIR}"
        )

    blind = pd.read_csv(
        BLIND,
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

    assert len(blind) == 48
    assert len(llm) == 48

    assert blind[
        "production_candidate_id"
    ].is_unique

    assert llm[
        "production_candidate_id"
    ].is_unique

    selected_ids = set(
        llm.loc[
            ~llm[
                "llm_first_pass_judgment"
            ].eq(
                "VALID_TARGET_REFERENCE"
            ),
            "production_candidate_id",
        ]
    )

    assert len(selected_ids) == 25

    # Select from original blind input, not from the LLM output.
    # Therefore exact LLM judgment/reason/note are absent.
    out = blind.loc[
        blind[
            "production_candidate_id"
        ].isin(selected_ids)
    ].copy()

    assert len(out) == 25

    # Rename blank human fields to direct-review fields.
    out = out.drop(
        columns=[
            "human_judgment",
            "human_reason_code",
            "human_notes",
        ]
    )

    out["human_judgment"] = ""
    out["human_reason_code"] = ""
    out["human_notes"] = ""

    forbidden = {
        "llm_first_pass_judgment",
        "llm_first_pass_reason_code",
        "llm_first_pass_note",
        "policy_action",
        "hit_location",
        "title_match_token_count_min",
        "any_cross_w_title_collision",
    }

    assert not (
        forbidden
        & set(out.columns)
    )

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

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=False,
    )

    write_tsv(
        out,
        OUT_TSV,
    )

    manifest = {
        "release": RELEASE,
        "created_at": CREATED_AT,

        "purpose": (
            "Direct human review queue for every "
            "production-review candidate whose blind "
            "LLM first-pass judgment was not VALID."
        ),

        "counts": {
            "candidate_rows": 25,
            "project_works":
                int(
                    out[
                        "project_work_id"
                    ].nunique()
                ),
        },

        "selection": {
            "criterion": (
                "llm_first_pass_judgment != "
                "VALID_TARGET_REFERENCE"
            ),
            "llm_exact_judgment_hidden_from_review_sheet":
                True,
            "llm_reason_hidden_from_review_sheet":
                True,
            "policy_features_hidden":
                True,
        },

        "sources": {
            str(
                BLIND.relative_to(ROOT)
            ):
                sha256_file(BLIND),

            str(
                LLM.relative_to(ROOT)
            ):
                sha256_file(LLM),
        },

        "output": {
            str(
                OUT_TSV.relative_to(ROOT)
            ):
                sha256_file(OUT_TSV),
        },

        "allowed_judgments": [
            "VALID_TARGET_REFERENCE",
            "INVALID_TARGET_REFERENCE",
            "UNCERTAIN",
        ],

        "note": (
            "This is targeted human review, not an "
            "independent random human validation sample. "
            "Selection depends on the prior LLM first pass."
        ),
    }

    write_json(
        manifest,
        OUT_MANIFEST,
    )

    print(
        "=== A2 PRODUCTION HUMAN REVIEW QUEUE V1 ==="
    )
    print("rows:", len(out))
    print(
        "project works:",
        out[
            "project_work_id"
        ].nunique(),
    )
    print(
        "LLM exact labels hidden: YES"
    )
    print(
        "policy features hidden: YES"
    )
    print(
        "human fields blank:",
        out[
            [
                "human_judgment",
                "human_reason_code",
                "human_notes",
            ]
        ].eq("").all().all(),
    )
    print("output:", OUT_TSV)


if __name__ == "__main__":
    main()
