#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

SAMPLE_DIR = (
    ROOT
    / "derived/openalex_production/"
      "retrieval_a2_validation_sample_v1"
)

VALIDATION_QUERIES = (
    SAMPLE_DIR
    / "openalex_a2_validation_queries_v1.parquet"
)

SAMPLE_MANIFEST = (
    SAMPLE_DIR
    / "openalex_a2_validation_sample_v1_manifest.json"
)

FULL_REGISTRY = (
    ROOT
    / "derived/openalex_production/"
      "retrieval_match_registry_full_v1/"
      "openalex_retrieval_match_registry_full_v1.parquet"
)

RELEASE = "openalex-a2-validation-candidates-v1"
VERSION = "v1"
CREATED_AT = "2026-10-07"

EXPECTED_CANDIDATE_PAIRS = 248
EXPECTED_CANDIDATE_WORKS = 64
EXPECTED_UNIQUE_OA_WORKS = 243
EXPECTED_SHARED_OA_IDS = 5

EXPECTED_HIT_LOCATION = {
    "ABSTRACT_ONLY": 131,
    "TITLE_AND_ABSTRACT": 75,
    "TITLE_ONLY": 42,
}

EXPECTED_CROSS_W_COLLISION_TRUE = 25


def require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def write_atomic_tsv(
    df: pd.DataFrame,
    path: Path,
) -> None:
    tmp = path.with_name(path.name + ".tmp")

    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    os.replace(tmp, path)


def write_atomic_parquet(
    df: pd.DataFrame,
    path: Path,
) -> None:
    tmp = path.with_name(path.name + ".tmp")

    df.to_parquet(
        tmp,
        index=False,
        engine="pyarrow",
    )

    os.replace(tmp, path)


def write_atomic_json(
    obj: dict,
    path: Path,
) -> None:
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


def derive_hit_location(row) -> str:
    title = bool(
        row["title_match_in_title"]
    )

    abstract = bool(
        row["title_match_in_abstract"]
    )

    if title and abstract:
        return "TITLE_AND_ABSTRACT"

    if title:
        return "TITLE_ONLY"

    if abstract:
        return "ABSTRACT_ONLY"

    raise RuntimeError(
        "Candidate has no title match"
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--scan-dir",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    scan_dir = args.scan_dir
    out_dir = args.output_dir

    evidence_path = (
        scan_dir
        / "openalex_retrieval_a2_validation_hit_evidence_v1.parquet"
    )

    oa_path = (
        scan_dir
        / "openalex_retrieval_a2_validation_oa_records_v1.parquet"
    )

    scan_manifest_path = (
        scan_dir
        / "openalex_retrieval_a2_validation_scan_v1_manifest.json"
    )

    for path in [
        evidence_path,
        oa_path,
        scan_manifest_path,
        VALIDATION_QUERIES,
        SAMPLE_MANIFEST,
        FULL_REGISTRY,
    ]:
        require(path)

    if out_dir.exists():
        raise RuntimeError(
            f"Output directory exists: {out_dir}"
        )

    scan_manifest = json.loads(
        scan_manifest_path.read_text(
            encoding="utf-8"
        )
    )

    sample_manifest = json.loads(
        SAMPLE_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    if (
        scan_manifest.get("release")
        != "openalex-retrieval-a2-validation-scan-v1"
    ):
        raise RuntimeError(
            "Unexpected validation scan release"
        )

    if (
        scan_manifest.get("status")
        != "validation_full_scan"
    ):
        raise RuntimeError(
            "Source is not a completed full validation scan"
        )

    if (
        scan_manifest[
            "snapshot"
        ][
            "processed_file_count"
        ]
        != 2040
    ):
        raise RuntimeError(
            "Validation scan did not process 2040 files"
        )

    if (
        sample_manifest.get("release")
        != "openalex-a2-validation-sample-v1"
    ):
        raise RuntimeError(
            "Unexpected validation sample release"
        )

    # --------------------------------------------------------
    # Build finite A2 marginal candidate universe:
    #
    # R3 + A2 minus R3 + A1.
    # --------------------------------------------------------

    evidence = pd.read_parquet(
        evidence_path,
        columns=[
            "query_id",
            "execution_id",
            "target_lane",
            "project_work_id",
            "alias_id",
            "alias_project_source_entity_id",
            "query_route",
            "query_form",
            "openalex_work_id",
            "title_match_in_title",
            "title_match_in_abstract",
            "author_a1_in_title",
            "author_a1_in_abstract",
            "author_a1_hit",
            "author_a2_reverse_in_title",
            "author_a2_reverse_in_abstract",
            "author_a2_reverse_hit",
            "author_a2_hit",
            "snapshot_source_file",
        ],
    ).fillna("")

    candidates = evidence.loc[
        evidence["target_lane"].eq(
            "resolved_w"
        )
        & evidence["query_route"].eq("R3")
        & evidence["author_a2_hit"].astype(bool)
        & ~evidence["author_a1_hit"].astype(bool)
    ].copy()

    if len(candidates) != EXPECTED_CANDIDATE_PAIRS:
        raise RuntimeError(
            "Unexpected A2 candidate-pair count: "
            f"{len(candidates)}"
        )

    if candidates.duplicated(
        [
            "project_work_id",
            "openalex_work_id",
        ]
    ).any():
        raise RuntimeError(
            "Duplicate project-work × OpenAlex-work candidate"
        )

    # --------------------------------------------------------
    # Frozen query metadata
    # --------------------------------------------------------

    queries = pd.read_parquet(
        VALIDATION_QUERIES
    ).fillna("")

    r3 = queries.loc[
        queries["query_route"].eq("R3"),
        [
            "query_id",
            "project_work_id",
            "query_title",
            "query_author",
            "title_match_norm",
            "title_match_token_count",
            "author_a1_norm",
            "author_a2_reverse_norm",
        ],
    ].copy()

    if len(r3) != 500:
        raise RuntimeError(
            f"Unexpected R3 query count: {len(r3)}"
        )

    candidates = candidates.merge(
        r3,
        on=[
            "query_id",
            "project_work_id",
        ],
        how="left",
        validate="many_to_one",
    )

    if candidates[
        "query_title"
    ].eq("").any():
        raise RuntimeError(
            "Missing frozen query metadata"
        )

    candidates["hit_location"] = (
        candidates.apply(
            derive_hit_location,
            axis=1,
        )
    )

    # --------------------------------------------------------
    # Corpus-level cross-W collision feature
    # --------------------------------------------------------

    registry = pd.read_parquet(
        FULL_REGISTRY,
        columns=[
            "target_lane",
            "project_work_id",
            "title_match_norm",
        ],
    ).fillna("")

    registry = registry.loc[
        registry["target_lane"].eq(
            "resolved_w"
        )
        & registry["project_work_id"].ne("")
        & registry["title_match_norm"].ne("")
    ].copy()

    cross_w = (
        registry.groupby(
            "title_match_norm"
        )["project_work_id"]
        .nunique()
    )

    candidates[
        "cross_w_resolved_work_count"
    ] = (
        candidates[
            "title_match_norm"
        ]
        .map(cross_w)
        .fillna(0)
        .astype(int)
    )

    candidates[
        "any_cross_w_title_collision"
    ] = (
        candidates[
            "cross_w_resolved_work_count"
        ].gt(1)
    )

    # --------------------------------------------------------
    # OpenAlex metadata
    # --------------------------------------------------------

    candidate_oa_ids = set(
        candidates["openalex_work_id"]
    )

    oa = pd.read_parquet(
        oa_path
    ).fillna("")

    oa = oa.loc[
        oa["openalex_work_id"].isin(
            candidate_oa_ids
        )
    ].copy()

    if set(
        oa["openalex_work_id"]
    ) != candidate_oa_ids:
        raise RuntimeError(
            "OA metadata coverage mismatch"
        )

    if oa.duplicated(
        "openalex_work_id"
    ).any():
        raise RuntimeError(
            "Duplicate OA metadata row"
        )

    candidates = candidates.merge(
        oa,
        on="openalex_work_id",
        how="left",
        validate="many_to_one",
    )

    # --------------------------------------------------------
    # Deterministic release-local candidate ID
    # --------------------------------------------------------

    candidates = (
        candidates.sort_values(
            [
                "project_work_id",
                "openalex_work_id",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    candidates.insert(
        0,
        "validation_candidate_id",
        [
            f"A2V1_{i:04d}"
            for i in range(
                1,
                len(candidates) + 1,
            )
        ],
    )

    candidates.insert(
        1,
        "increment_type",
        "A2_AUTHOR_REVERSAL",
    )

    # --------------------------------------------------------
    # Frozen invariants from read-only exploration
    # --------------------------------------------------------

    if (
        candidates[
            "project_work_id"
        ].nunique()
        != EXPECTED_CANDIDATE_WORKS
    ):
        raise RuntimeError(
            "Unexpected candidate-work count"
        )

    if (
        candidates[
            "openalex_work_id"
        ].nunique()
        != EXPECTED_UNIQUE_OA_WORKS
    ):
        raise RuntimeError(
            "Unexpected unique OA-work count"
        )

    shared = (
        candidates.groupby(
            "openalex_work_id"
        )["project_work_id"]
        .nunique()
        .gt(1)
        .sum()
    )

    if int(shared) != EXPECTED_SHARED_OA_IDS:
        raise RuntimeError(
            f"Unexpected shared OA ID count: {shared}"
        )

    hit_counts = (
        candidates[
            "hit_location"
        ]
        .value_counts()
        .to_dict()
    )

    if hit_counts != EXPECTED_HIT_LOCATION:
        raise RuntimeError(
            "Unexpected hit-location distribution: "
            f"{hit_counts}"
        )

    collision_true = int(
        candidates[
            "any_cross_w_title_collision"
        ].sum()
    )

    if (
        collision_true
        != EXPECTED_CROSS_W_COLLISION_TRUE
    ):
        raise RuntimeError(
            "Unexpected cross-W collision count: "
            f"{collision_true}"
        )

    # --------------------------------------------------------
    # Blind adjudication sheet.
    #
    # Deliberately excludes:
    # - hit_location
    # - title token count
    # - cross-W collision
    # - A1/A2 matching features
    # - policy action / policy condition
    # --------------------------------------------------------

    blind = candidates[
        [
            "validation_candidate_id",
            "project_work_id",
            "query_title",
            "query_author",
            "openalex_work_id",
            "display_name",
            "abstract",
            "publication_year",
            "publication_date",
            "doi",
        ]
    ].copy()

    blind = blind.rename(
        columns={
            "query_title":
                "target_title",
            "query_author":
                "target_author",
            "display_name":
                "openalex_display_name",
            "abstract":
                "openalex_abstract",
        }
    )

    blind[
        "human_judgment"
    ] = ""

    blind[
        "human_reason_code"
    ] = ""

    blind[
        "human_notes"
    ] = ""

    # --------------------------------------------------------
    # Write
    # --------------------------------------------------------

    out_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    candidates_tsv = (
        out_dir
        / "openalex_a2_validation_candidates_v1.tsv"
    )

    candidates_parquet = (
        out_dir
        / "openalex_a2_validation_candidates_v1.parquet"
    )

    blind_tsv = (
        out_dir
        / "openalex_a2_validation_blind_adjudication_v1.tsv"
    )

    manifest_path = (
        out_dir
        / "openalex_a2_validation_candidates_v1_manifest.json"
    )

    write_atomic_tsv(
        candidates,
        candidates_tsv,
    )

    write_atomic_parquet(
        candidates,
        candidates_parquet,
    )

    write_atomic_tsv(
        blind,
        blind_tsv,
    )

    manifest = {
        "release": RELEASE,
        "version": VERSION,
        "created_at": CREATED_AT,
        "status":
            "pre_adjudication_candidates_frozen",

        "candidate_unit":
            (
                "project_work_id × openalex_work_id"
            ),

        "candidate_id_semantics":
            (
                "validation_candidate_id is release-local "
                "provenance only and is not a persistent "
                "cross-release identity."
            ),

        "candidate_definition":
            (
                "Resolved-W R3+A2 pairs minus resolved-W "
                "R3+A1 pairs in the frozen 500-work "
                "held-out validation sample."
            ),

        "counts": {
            "candidate_pairs":
                len(candidates),

            "candidate_project_works":
                int(
                    candidates[
                        "project_work_id"
                    ].nunique()
                ),

            "unique_openalex_works":
                int(
                    candidates[
                        "openalex_work_id"
                    ].nunique()
                ),

            "openalex_ids_shared_across_project_works":
                int(shared),

            "hit_location":
                {
                    str(k): int(v)
                    for k, v
                    in hit_counts.items()
                },

            "cross_w_collision_true":
                collision_true,
        },

        "blind_adjudication": {
            "policy_action_included":
                False,

            "policy_condition_included":
                False,

            "policy_driving_features_hidden":
                [
                    "hit_location",
                    "title_match_token_count",
                    "any_cross_w_title_collision",
                    "author matching fields",
                ],

            "allowed_human_judgments":
                [
                    "VALID_TARGET_REFERENCE",
                    "INVALID_TARGET_REFERENCE",
                    "UNCERTAIN",
                ],
        },

        "policy_status":
            (
                "Frozen calibration-selected A2 policy "
                "exists but is not materialized per "
                "candidate before blind adjudication."
            ),

        "source_releases": {
            "validation_sample":
                sample_manifest["release"],

            "validation_scan":
                scan_manifest["release"],
        },

        "inputs": {
            "validation_scan_manifest": {
                "artifact":
                    str(scan_manifest_path),

                "sha256":
                    sha256_file(
                        scan_manifest_path
                    ),
            },

            "validation_queries": {
                "artifact":
                    str(VALIDATION_QUERIES),

                "sha256":
                    sha256_file(
                        VALIDATION_QUERIES
                    ),
            },

            "full_match_registry": {
                "artifact":
                    str(FULL_REGISTRY),

                "sha256":
                    sha256_file(
                        FULL_REGISTRY
                    ),
            },
        },

        "outputs": {
            "candidates_tsv": {
                "artifact":
                    candidates_tsv.name,

                "sha256":
                    sha256_file(
                        candidates_tsv
                    ),
            },

            "candidates_parquet": {
                "artifact":
                    candidates_parquet.name,

                "sha256":
                    sha256_file(
                        candidates_parquet
                    ),
            },

            "blind_adjudication_tsv": {
                "artifact":
                    blind_tsv.name,

                "sha256":
                    sha256_file(
                        blind_tsv
                    ),
            },
        },

        "next_step":
            (
                "Blindly adjudicate all 248 candidate "
                "pairs before materializing the locked "
                "A2 ACCEPT/REVIEW policy action."
            ),
    }

    write_atomic_json(
        manifest,
        manifest_path,
    )

    print(
        "=== A2 VALIDATION CANDIDATES V1 ==="
    )

    print(
        "candidate pairs:",
        len(candidates),
    )

    print(
        "candidate works:",
        candidates[
            "project_work_id"
        ].nunique(),
    )

    print(
        "unique OA works:",
        candidates[
            "openalex_work_id"
        ].nunique(),
    )

    print(
        "shared OA IDs:",
        int(shared),
    )

    print("\nhit location:")
    print(
        candidates[
            "hit_location"
        ]
        .value_counts()
        .to_string()
    )

    print(
        "\ncross-W collision:",
        collision_true,
    )

    print(
        "\nblind columns:"
    )

    for col in blind.columns:
        print(" ", col)

    print(
        "\noutputs:",
        out_dir,
    )


if __name__ == "__main__":
    main()
