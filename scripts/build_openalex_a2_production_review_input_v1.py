#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

SOURCE_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_production_routing_v1"
)

SOURCE = (
    SOURCE_DIR
    / "openalex_a2_production_new_review_queue_v1.parquet"
)

SOURCE_MANIFEST = (
    SOURCE_DIR
    / "openalex_a2_production_routing_v1_manifest.json"
)

OUT_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_production_review_input_v1"
)

OUT_TSV = (
    OUT_DIR
    / "openalex_a2_production_review_blind_v1.tsv"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openalex_a2_production_review_input_v1_manifest.json"
)

RELEASE = "openalex-a2-production-review-input-v1"
VERSION = "v1"
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


def write_atomic_tsv(df, path):
    tmp = path.with_name(path.name + ".tmp")
    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )
    os.replace(tmp, path)


def write_atomic_json(obj, path):
    tmp = path.with_name(path.name + ".tmp")
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

    for p in [
        SOURCE,
        SOURCE_MANIFEST,
    ]:
        if not p.exists():
            raise FileNotFoundError(p)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory already exists: {OUT_DIR}"
        )

    src = pd.read_parquet(SOURCE)

    # --------------------------------------------------------
    # Frozen source invariants
    # --------------------------------------------------------

    assert len(src) == 48

    assert (
        src["project_work_id"].nunique()
        == 20
    )

    assert src[
        "policy_action"
    ].eq("REVIEW").all()

    assert src[
        "evaluation_source"
    ].eq("NEW_PRODUCTION").all()

    assert src[
        "requires_new_review"
    ].astype(bool).all()

    assert src[
        "production_candidate_id"
    ].is_unique

    # --------------------------------------------------------
    # Blind adjudication view
    #
    # Deliberately exclude:
    # - policy_action
    # - hit_location
    # - token counts
    # - cross-W collision
    # - A1/A2 matching fields
    # - candidate frequency
    #
    # Adjudicator receives only target identity context
    # and OpenAlex title/abstract metadata.
    # --------------------------------------------------------

    out = pd.DataFrame({
        "production_candidate_id":
            src[
                "production_candidate_id"
            ],

        "project_work_id":
            src[
                "project_work_id"
            ],

        "target_title":
            src[
                "r2_baseline_titles"
            ],

        "target_author":
            src[
                "r2_baseline_authors"
            ],

        "openalex_work_id":
            src[
                "openalex_work_id"
            ],

        "openalex_display_name":
            src[
                "display_name"
            ],

        "openalex_abstract":
            src[
                "abstract"
            ],

        "publication_year":
            src[
                "publication_year"
            ],

        "publication_date":
            src[
                "publication_date"
            ],

        "doi":
            src[
                "doi"
            ],

        "human_judgment":
            "",

        "human_reason_code":
            "",

        "human_notes":
            "",
    })

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
    assert out[
        "production_candidate_id"
    ].is_unique

    # Ensure forbidden policy fields are not present.
    forbidden = {
        "policy_action",
        "hit_location",
        "title_match_token_count_min",
        "title_match_token_count_max",
        "any_cross_w_title_collision",
        "author_a1_norm_set",
        "author_a2_reverse_norm_set",
        "evaluation_source",
        "requires_new_review",
    }

    assert not (
        forbidden
        & set(out.columns)
    )

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=False,
    )

    write_atomic_tsv(
        out,
        OUT_TSV,
    )

    manifest = {
        "release": RELEASE,
        "version": VERSION,
        "created_at": CREATED_AT,

        "purpose": (
            "Freeze the blind adjudication input for the "
            "48 NEW_PRODUCTION candidates routed to REVIEW "
            "by the already-frozen A2 production policy."
        ),

        "counts": {
            "candidate_rows": 48,
            "project_works": 20,
        },

        "adjudication_scope": {
            "judgments": [
                "VALID_TARGET_REFERENCE",
                "INVALID_TARGET_REFERENCE",
                "UNCERTAIN",
            ],

            "policy_features_hidden":
                True,

            "external_web_required":
                False,

            "candidate_frequency_hidden":
                True,
        },

        "source": {
            str(
                SOURCE.relative_to(ROOT)
            ):
                sha256_file(SOURCE),

            str(
                SOURCE_MANIFEST.relative_to(ROOT)
            ):
                sha256_file(
                    SOURCE_MANIFEST
                ),
        },

        "output": {
            str(
                OUT_TSV.relative_to(ROOT)
            ):
                sha256_file(OUT_TSV),
        },

        "interpretation": (
            "This release contains no adjudication "
            "outcomes. Routing was frozen before this "
            "blind review input was generated."
        ),
    }

    write_atomic_json(
        manifest,
        OUT_MANIFEST,
    )

    print(
        "=== A2 PRODUCTION REVIEW INPUT V1 ==="
    )
    print("candidate rows:", len(out))
    print(
        "project works:",
        out["project_work_id"].nunique(),
    )
    print(
        "policy features hidden: YES"
    )
    print(
        "judgment columns blank:",
        (
            out[
                [
                    "human_judgment",
                    "human_reason_code",
                    "human_notes",
                ]
            ]
            .eq("")
            .all()
            .all()
        ),
    )
    print("output:", OUT_TSV)


if __name__ == "__main__":
    main()
