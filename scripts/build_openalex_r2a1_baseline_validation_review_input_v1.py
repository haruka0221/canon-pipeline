#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd
import pyarrow.dataset as ds


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

SAMPLE_MANIFEST = (
    SAMPLE_DIR
    / "openalex_r2a1_baseline_validation_sample_v1_manifest.json"
)

MATCH_REGISTRY = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_match_registry_full_v1"
    / "openalex_retrieval_match_registry_full_v1.parquet"
)

SCAN_DIR = Path(
    "/media/hdd1/user/tsutsui/openalex/scans/"
    "full_r23_v1/full_2040files_4a275210"
)

OA_RECORDS = (
    SCAN_DIR
    / "openalex_retrieval_full_r23_oa_records_v1.parquet"
)

SCAN_MANIFEST = (
    SCAN_DIR
    / "openalex_retrieval_full_r23_scan_v1_manifest.json"
)

OUT_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_r2a1_baseline_validation_review_input_v1"
)

OUT_TSV = (
    OUT_DIR
    / "openalex_r2a1_baseline_validation_blind_v1.tsv"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openalex_r2a1_baseline_validation_review_input_v1_manifest.json"
)

RELEASE = "openalex-r2a1-baseline-validation-review-input-v1"
VERSION = "v1"
CREATED_AT = "2026-10-11"

SNAPSHOT_SHA256 = (
    "57959e90573d6ef2adb953fd747ba718"
    "54819880f762077f680083476d490fc9"
)


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
        ) + "\n",
        encoding="utf-8",
    )

    os.replace(tmp, path)


def joined(values):
    return " || ".join(
        sorted({
            str(v)
            for v in values
            if pd.notna(v)
            and str(v).strip() != ""
        })
    )


def main():

    for path in [
        SAMPLE,
        SAMPLE_MANIFEST,
        MATCH_REGISTRY,
        OA_RECORDS,
        SCAN_MANIFEST,
    ]:
        if not path.exists():
            raise FileNotFoundError(path)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory already exists: {OUT_DIR}"
        )

    # --------------------------------------------------------
    # 1. Frozen source checks
    # --------------------------------------------------------

    sample_manifest = json.loads(
        SAMPLE_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    assert (
        sample_manifest["release"]
        == "openalex-r2a1-baseline-validation-sample-v1"
    )

    scan_manifest = json.loads(
        SCAN_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    assert (
        scan_manifest["release"]
        == "openalex-retrieval-full-r23-scan-v1"
    )

    assert scan_manifest["status"] == "full_scan"
    assert scan_manifest["run_mode"] == "full"

    assert (
        scan_manifest["snapshot"][
            "full_inventory_sha256"
        ]
        == SNAPSHOT_SHA256
    )

    assert (
        scan_manifest["snapshot"][
            "processed_inventory_sha256"
        ]
        == SNAPSHOT_SHA256
    )

    # --------------------------------------------------------
    # 2. Frozen validation sample membership
    # --------------------------------------------------------

    sample = pd.read_parquet(
        SAMPLE
    )

    assert len(sample) == 1147
    assert sample[
        "baseline_candidate_id"
    ].is_unique

    assert not sample[
        [
            "project_work_id",
            "openalex_work_id",
        ]
    ].duplicated().any()

    assert int(
        sample[
            "in_primary_pair_sample"
        ].astype(bool).sum()
    ) == 800

    assert int(
        sample[
            "in_secondary_work_diagnostic_sample"
        ].astype(bool).sum()
    ) == 348

    assert int(
        (
            sample[
                "in_primary_pair_sample"
            ].astype(bool)
            &
            sample[
                "in_secondary_work_diagnostic_sample"
            ].astype(bool)
        ).sum()
    ) == 1

    # --------------------------------------------------------
    # 3. Target identity context from frozen R2 registry
    #
    # Do not expose query-level/risk features in the blind
    # output. R2 title/author strings are used only as target
    # identity context.
    # --------------------------------------------------------

    q = pd.read_parquet(
        MATCH_REGISTRY,
        columns=[
            "target_lane",
            "project_work_id",
            "query_route",
            "query_title",
            "query_author",
        ],
    ).fillna("")

    r2_context = (
        q.loc[
            q["target_lane"].eq(
                "resolved_w"
            )
            & q["query_route"].eq(
                "R2"
            )
            & q["project_work_id"].ne("")
        ]
        .groupby(
            "project_work_id",
            sort=True,
        )
        .agg(
            target_title=(
                "query_title",
                joined,
            ),
            target_author=(
                "query_author",
                joined,
            ),
        )
        .reset_index()
    )

    assert r2_context[
        "project_work_id"
    ].is_unique

    out = sample[
        [
            "baseline_candidate_id",
            "project_work_id",
            "openalex_work_id",
        ]
    ].merge(
        r2_context,
        on="project_work_id",
        how="left",
        validate="many_to_one",
    )

    assert out[
        "target_title"
    ].notna().all()

    assert out[
        "target_title"
    ].astype(str).str.strip().ne("").all()

    assert out[
        "target_author"
    ].notna().all()

    assert out[
        "target_author"
    ].astype(str).str.strip().ne("").all()

    # --------------------------------------------------------
    # 4. OpenAlex record metadata
    # --------------------------------------------------------

    oa_ids = sorted(
        set(
            out[
                "openalex_work_id"
            ].astype(str)
        )
    )

    oa_dataset = ds.dataset(
        str(OA_RECORDS),
        format="parquet",
    )

    oa = oa_dataset.to_table(
        columns=[
            "openalex_work_id",
            "display_name",
            "abstract",
            "publication_year",
            "publication_date",
            "doi",
        ],
        filter=(
            ds.field(
                "openalex_work_id"
            ).isin(oa_ids)
        ),
    ).to_pandas()

    assert oa[
        "openalex_work_id"
    ].is_unique

    assert (
        set(
            oa[
                "openalex_work_id"
            ].astype(str)
        )
        == set(oa_ids)
    )

    out = out.merge(
        oa,
        on="openalex_work_id",
        how="left",
        validate="many_to_one",
    )

    out = out.rename(
        columns={
            "display_name":
                "openalex_display_name",

            "abstract":
                "openalex_abstract",
        }
    )

    # --------------------------------------------------------
    # 5. Blind adjudication columns
    #
    # These are intentionally the ONLY judgment fields
    # included here. They are blank in the frozen input.
    # --------------------------------------------------------

    out[
        "human_judgment"
    ] = ""

    out[
        "human_reason_code"
    ] = ""

    out[
        "human_notes"
    ] = ""

    final_columns = [
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
        "human_judgment",
        "human_reason_code",
        "human_notes",
    ]

    out = out[
        final_columns
    ]

    # Deterministic opaque ordering.
    #
    # Do not order by sample component, risk feature,
    # candidate volume, or project-work volume.
    out = (
        out.sort_values(
            [
                "baseline_candidate_id",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    assert len(out) == 1147

    assert out[
        "baseline_candidate_id"
    ].is_unique

    assert out[
        [
            "human_judgment",
            "human_reason_code",
            "human_notes",
        ]
    ].eq("").all().all()

    # --------------------------------------------------------
    # 6. Explicit blindness check
    # --------------------------------------------------------

    forbidden = {
        "evidence_row_count",
        "query_count",
        "title_match_token_count_min",
        "title_match_token_count_max",
        "any_title_match_in_title",
        "any_title_match_in_abstract",
        "hit_location",
        "title_token_bucket",
        "work_candidate_count",
        "work_volume_bucket",
        "in_primary_pair_sample",
        "in_secondary_work_diagnostic_sample",
        "sample_membership",
        "sample_component",
        "sampling_probability",
        "secondary_sampling_stratum",
        "query_id",
        "query_route",
        "author_a1_hit",
    }

    assert not (
        forbidden
        & set(out.columns)
    )

    # --------------------------------------------------------
    # 7. Write frozen blind input
    # --------------------------------------------------------

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
        "version": VERSION,
        "created_at": CREATED_AT,

        "purpose": (
            "Freeze a judgment-free blind target-attribution "
            "view for the already-frozen R2+A1 baseline "
            "validation samples."
        ),

        "counts": {
            "unique_candidate_pairs": 1147,
            "primary_pair_sample_members": 800,
            "secondary_work_diagnostic_members": 348,
            "primary_secondary_overlap": 1,
        },

        "adjudication_target": (
            "Whether the supplied OpenAlex scholarly record "
            "genuinely refers to the target literary work."
        ),

        "allowed_judgments": [
            "VALID_TARGET_REFERENCE",
            "INVALID_TARGET_REFERENCE",
            "UNCERTAIN",
        ],

        "blindness": {
            "sample_membership_hidden": True,
            "hit_location_hidden": True,
            "title_token_features_hidden": True,
            "work_candidate_volume_hidden": True,
            "query_provenance_hidden": True,
            "retrieval_risk_features_hidden": True,
            "document_scope_classification_not_requested_here": True,
            "mention_strength_classification_not_requested_here": True,
        },

        "sources": {
            str(
                SAMPLE.relative_to(ROOT)
            ):
                sha256_file(SAMPLE),

            str(
                SAMPLE_MANIFEST.relative_to(ROOT)
            ):
                sha256_file(
                    SAMPLE_MANIFEST
                ),

            str(
                MATCH_REGISTRY.relative_to(ROOT)
            ):
                sha256_file(
                    MATCH_REGISTRY
                ),

            str(SCAN_MANIFEST):
                sha256_file(
                    SCAN_MANIFEST
                ),
        },

        "output": {
            str(
                OUT_TSV.relative_to(ROOT)
            ):
                sha256_file(
                    OUT_TSV
                ),
        },

        "interpretation": [
            (
                "This release contains no adjudication "
                "outcomes."
            ),
            (
                "Primary versus secondary sample membership "
                "is deliberately absent from the blind view."
            ),
            (
                "The same blind candidate view may support "
                "a separate LLM first pass and later human "
                "adjudication, but their outputs must be "
                "stored in separate versioned artifacts."
            ),
            (
                "Sampling membership remains recoverable "
                "only by joining baseline_candidate_id back "
                "to the frozen validation-sample release."
            ),
        ],
    }

    write_json(
        manifest,
        OUT_MANIFEST,
    )

    print(
        "=== R2+A1 BASELINE VALIDATION REVIEW INPUT V1 ==="
    )
    print(
        "blind candidate rows:",
        len(out),
    )
    print(
        "unique candidate IDs:",
        out[
            "baseline_candidate_id"
        ].nunique(),
    )
    print(
        "sample membership hidden: YES"
    )
    print(
        "risk features hidden: YES"
    )
    print(
        "judgment columns blank:",
        out[
            [
                "human_judgment",
                "human_reason_code",
                "human_notes",
            ]
        ].eq("").all().all(),
    )
    print(
        "output:",
        OUT_TSV,
    )


if __name__ == "__main__":
    main()
