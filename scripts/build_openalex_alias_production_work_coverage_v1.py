#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd
import pyarrow.dataset as ds


ROOT = Path(__file__).resolve().parents[1]

FINAL = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_alias_production_final_disposition_v1"
    / "openalex_alias_production_final_disposition_v1.parquet"
)

EVIDENCE = Path(
    "/media/hdd1/user/tsutsui/openalex/scans/"
    "full_r23_v1/full_2040files_4a275210/"
    "openalex_retrieval_full_r23_hit_evidence_v1.parquet"
)

OUT_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_alias_production_work_coverage_v1"
)

OUT_TSV = (
    OUT_DIR
    / "openalex_alias_production_work_coverage_v1.tsv"
)

OUT_PARQUET = (
    OUT_DIR
    / "openalex_alias_production_work_coverage_v1.parquet"
)

OUT_SUMMARY = (
    OUT_DIR
    / "openalex_alias_production_work_coverage_summary_v1.json"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openalex_alias_production_work_coverage_v1_manifest.json"
)

RELEASE = "openalex-alias-production-work-coverage-v1"
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


def pair_set(df):
    return set(
        map(
            tuple,
            df[
                [
                    "project_work_id",
                    "openalex_work_id",
                ]
            ]
            .drop_duplicates()
            .itertuples(
                index=False,
                name=None,
            ),
        )
    )


def main():

    for path in [FINAL, EVIDENCE]:
        if not path.exists():
            raise FileNotFoundError(path)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory exists: {OUT_DIR}"
        )

    final = pd.read_parquet(FINAL)

    assert len(final) == 409
    assert final["project_work_id"].nunique() == 38

    assert (
        final["final_judgment"]
        .value_counts()
        .to_dict()
        == {
            "VALID_TARGET_REFERENCE": 364,
            "INVALID_TARGET_REFERENCE": 24,
            "UNCERTAIN": 21,
        }
    )

    assert final[
        "direct_human_reviewed"
    ].astype(bool).all()

    # --------------------------------------------------
    # 1. Frozen R2+A2 and R3+A2 coverage
    # --------------------------------------------------

    dataset = ds.dataset(
        str(EVIDENCE),
        format="parquet",
    )

    r2 = dataset.to_table(
        columns=[
            "project_work_id",
            "openalex_work_id",
        ],
        filter=(
            (ds.field("target_lane") == "resolved_w")
            & (ds.field("query_route") == "R2")
            & (ds.field("author_a2_hit") == True)
        ),
    ).to_pandas()

    r3 = dataset.to_table(
        columns=[
            "project_work_id",
            "openalex_work_id",
        ],
        filter=(
            (ds.field("target_lane") == "resolved_w")
            & (ds.field("query_route") == "R3")
            & (ds.field("author_a2_hit") == True)
        ),
    ).to_pandas()

    r2_pairs = pair_set(r2)
    r3_pairs = pair_set(r3)

    assert len(r2_pairs) == 291450
    assert len(r3_pairs) == 291859

    alias_pairs = r3_pairs - r2_pairs

    assert len(alias_pairs) == 409

    final_pairs = set(
        final[
            [
                "project_work_id",
                "openalex_work_id",
            ]
        ].itertuples(
            index=False,
            name=None,
        )
    )

    assert alias_pairs == final_pairs

    r2_works = set(
        r2[
            "project_work_id"
        ]
        .dropna()
        .astype(str)
    )

    r3_works = set(
        r3[
            "project_work_id"
        ]
        .dropna()
        .astype(str)
    )

    assert len(r2_works) == 7080
    assert len(r3_works) == 7106

    marginal_works = set(
        final[
            "project_work_id"
        ].astype(str)
    )

    assert len(marginal_works) == 38

    alias_new_works = (
        marginal_works - r2_works
    )

    alias_already_covered = (
        marginal_works & r2_works
    )

    assert len(alias_new_works) == 26
    assert len(alias_already_covered) == 12

    # --------------------------------------------------
    # 2. Work-level aggregation
    # --------------------------------------------------

    rows = []

    for wid, g in final.groupby(
        "project_work_id",
        sort=True,
    ):

        valid_count = int(
            g[
                "final_judgment"
            ]
            .eq(
                "VALID_TARGET_REFERENCE"
            )
            .sum()
        )

        invalid_count = int(
            g[
                "final_judgment"
            ]
            .eq(
                "INVALID_TARGET_REFERENCE"
            )
            .sum()
        )

        uncertain_count = int(
            g[
                "final_judgment"
            ]
            .eq(
                "UNCERTAIN"
            )
            .sum()
        )

        include_count = int(
            g[
                "include_in_operational_alias_indicator"
            ]
            .astype(bool)
            .sum()
        )

        had_r2_a2 = wid in r2_works
        is_alias_new = wid in alias_new_works

        adds_final_valid_coverage = (
            is_alias_new
            and valid_count > 0
        )

        loses_all = (
            is_alias_new
            and include_count == 0
        )

        if is_alias_new:
            if adds_final_valid_coverage:
                status = (
                    "ALIAS_NEW_RETAINED_WITH_FINAL_VALID"
                )
            else:
                status = (
                    "ALIAS_NEW_LOST_AFTER_FINAL_DISPOSITION"
                )
        else:
            status = (
                "ALREADY_R2_A2_COVERED_ALIAS_MARGINAL"
            )

        rows.append({
            "project_work_id": wid,

            "had_r2_a2_candidate":
                had_r2_a2,

            "is_alias_new_work_level_coverage":
                is_alias_new,

            "alias_marginal_candidate_count":
                int(len(g)),

            "final_valid_candidate_count":
                valid_count,

            "final_invalid_candidate_count":
                invalid_count,

            "uncertain_candidate_count":
                uncertain_count,

            "operational_include_candidate_count":
                include_count,

            "adds_final_valid_work_level_coverage":
                adds_final_valid_coverage,

            "loses_all_alias_candidates_after_final_disposition":
                loses_all,

            "work_level_alias_status":
                status,
        })

    out = pd.DataFrame(rows)

    assert len(out) == 38
    assert out["project_work_id"].is_unique

    # --------------------------------------------------
    # 3. Expected work-level results
    # --------------------------------------------------

    assert int(
        out[
            "is_alias_new_work_level_coverage"
        ].sum()
    ) == 26

    assert int(
        out[
            "adds_final_valid_work_level_coverage"
        ].sum()
    ) == 26

    assert int(
        out[
            "loses_all_alias_candidates_after_final_disposition"
        ].sum()
    ) == 0

    status_counts = (
        out[
            "work_level_alias_status"
        ]
        .value_counts()
        .to_dict()
    )

    expected_status = {
        "ALIAS_NEW_RETAINED_WITH_FINAL_VALID": 26,
        "ALREADY_R2_A2_COVERED_ALIAS_MARGINAL": 12,
    }

    assert status_counts == expected_status, status_counts

    # Useful descriptive value:
    # among all 38 marginal works, how many have >=1 VALID alias pair?
    marginal_works_with_valid = int(
        (
            out[
                "final_valid_candidate_count"
            ] > 0
        ).sum()
    )

    # Final work-level coverage:
    # every one of the 26 newly covered works survives.
    final_coverage_works = (
        r2_works | alias_new_works
    )

    assert len(final_coverage_works) == 7106

    # --------------------------------------------------
    # 4. Write
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

        "scope": {
            "alias_marginal_candidate_pairs": 409,
            "alias_marginal_project_works": 38,
            "all_candidate_pairs_direct_human_reviewed": True,
        },

        "candidate_stage_work_coverage": {
            "r2_a2_project_works": 7080,
            "r3_a2_project_works": 7106,
            "alias_candidate_stage_work_gain": 26,
        },

        "final_human_adjudicated_work_coverage": {
            "r2_a2_project_works": 7080,
            "alias_final_valid_work_gain": 26,
            "r2_a2_plus_final_valid_alias_project_works": 7106,
            "alias_new_works_losing_all_candidates": 0,
            "retention_rate_of_candidate_stage_alias_gain": 1.0,
        },

        "marginal_work_structure": {
            "alias_marginal_project_works": 38,
            "already_covered_by_r2_a2": 12,
            "new_work_level_coverage": 26,
            "marginal_works_with_at_least_one_final_valid_candidate":
                marginal_works_with_valid,
        },

        "work_level_status_counts":
            expected_status,

        "interpretation": [
            (
                "Alias expansion adds candidate-stage "
                "work-level coverage for 26 project works "
                "beyond R2+A2."
            ),
            (
                "All 26 newly covered works have at least "
                "one directly human-adjudicated "
                "VALID_TARGET_REFERENCE Alias candidate."
            ),
            (
                "No Alias-new work loses all candidates "
                "after final disposition."
            ),
            (
                "The final human-adjudicated Alias "
                "work-level gain therefore remains +26."
            ),
            (
                "The 409-pair Alias universe is a complete "
                "finite-population audit of the current "
                "release, not a held-out estimate for "
                "future releases."
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
                FINAL.relative_to(ROOT)
            ):
                sha256_file(FINAL),

            str(EVIDENCE):
                sha256_file(EVIDENCE),
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
        "=== ALIAS PRODUCTION WORK COVERAGE V1 ==="
    )
    print("Alias marginal works:", 38)
    print("already covered by R2+A2:", 12)
    print("Alias-new works:", 26)
    print()
    print(
        "Alias-new works with >=1 final VALID:",
        26,
    )
    print(
        "Alias-new works losing all candidates:",
        0,
    )
    print()
    print("R2+A2 work coverage:", 7080)
    print(
        "R2+A2 + final-valid Alias coverage:",
        7106,
    )
    print(
        "all marginal works with >=1 final VALID:",
        marginal_works_with_valid,
    )
    print("output:", OUT_DIR)


if __name__ == "__main__":
    main()
