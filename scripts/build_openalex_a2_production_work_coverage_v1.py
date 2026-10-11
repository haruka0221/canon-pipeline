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
    / "retrieval_a2_production_final_disposition_v1"
    / "openalex_a2_production_final_disposition_v1.parquet"
)

EVIDENCE = Path(
    "/media/hdd1/user/tsutsui/openalex/scans/"
    "full_r23_v1/full_2040files_4a275210/"
    "openalex_retrieval_full_r23_hit_evidence_v1.parquet"
)

OUT_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_production_work_coverage_v1"
)

OUT_TSV = (
    OUT_DIR
    / "openalex_a2_production_work_coverage_v1.tsv"
)

OUT_PARQUET = (
    OUT_DIR
    / "openalex_a2_production_work_coverage_v1.parquet"
)

OUT_SUMMARY = (
    OUT_DIR
    / "openalex_a2_production_work_coverage_summary_v1.json"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openalex_a2_production_work_coverage_v1_manifest.json"
)

RELEASE = "openalex-a2-production-work-coverage-v1"
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

    for p in [FINAL, EVIDENCE]:
        if not p.exists():
            raise FileNotFoundError(p)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory exists: {OUT_DIR}"
        )

    final = pd.read_parquet(FINAL)

    assert len(final) == 963
    assert final["project_work_id"].nunique() == 231

    # --------------------------------------------------
    # 1. Frozen R3+A1 and R3+A2 work coverage
    # --------------------------------------------------

    dataset = ds.dataset(
        str(EVIDENCE),
        format="parquet",
    )

    x = dataset.to_table(
        columns=[
            "project_work_id",
            "author_a1_hit",
            "author_a2_hit",
        ],
        filter=(
            (ds.field("target_lane") == "resolved_w")
            & (ds.field("query_route") == "R3")
            & (ds.field("author_a2_hit") == True)
        ),
    ).to_pandas()

    a2_candidate_works = set(
        x["project_work_id"]
        .dropna()
        .astype(str)
    )

    a1_works = set(
        x.loc[
            x["author_a1_hit"].astype(bool),
            "project_work_id",
        ]
        .dropna()
        .astype(str)
    )

    assert len(a1_works) == 6899
    assert len(a2_candidate_works) == 7106

    marginal_works = set(
        final["project_work_id"].astype(str)
    )

    assert len(marginal_works) == 231

    a2_new_works = (
        marginal_works - a1_works
    )

    marginal_already_a1 = (
        marginal_works & a1_works
    )

    assert len(a2_new_works) == 207
    assert len(marginal_already_a1) == 24

    # --------------------------------------------------
    # 2. Work-level aggregation of final disposition
    # --------------------------------------------------

    rows = []

    for wid, g in final.groupby(
        "project_work_id",
        sort=True,
    ):

        operational_include_count = int(
            g[
                "include_in_operational_a2_indicator"
            ].astype(bool).sum()
        )

        final_valid_count = int(
            g["final_judgment"]
            .eq("VALID_TARGET_REFERENCE")
            .sum()
        )

        final_invalid_count = int(
            g["final_judgment"]
            .eq("INVALID_TARGET_REFERENCE")
            .sum()
        )

        uncertain_count = int(
            g["final_judgment"]
            .eq("UNCERTAIN")
            .sum()
        )

        unadjudicated_accept_count = int(
            g[
                "final_operational_disposition"
            ]
            .eq(
                "INCLUDE_POLICY_ACCEPT_UNADJUDICATED"
            )
            .sum()
        )

        review_count = int(
            g["policy_action"]
            .eq("REVIEW")
            .sum()
        )

        accept_count = int(
            g["policy_action"]
            .eq("ACCEPT")
            .sum()
        )

        had_a1 = wid in a1_works
        is_a2_new = wid in a2_new_works

        adds_operational = (
            is_a2_new
            and operational_include_count > 0
        )

        adds_adjudicated_valid = (
            is_a2_new
            and final_valid_count > 0
        )

        loses_all = (
            is_a2_new
            and operational_include_count == 0
        )

        if loses_all:
            work_status = (
                "A2_NEW_LOST_AFTER_FINAL_DISPOSITION"
            )
        elif adds_adjudicated_valid:
            work_status = (
                "A2_NEW_RETAINED_WITH_FINAL_VALID"
            )
        elif adds_operational:
            work_status = (
                "A2_NEW_RETAINED_POLICY_ACCEPT_ONLY"
            )
        else:
            work_status = (
                "ALREADY_A1_COVERED_A2_MARGINAL"
            )

        rows.append({
            "project_work_id": wid,

            "had_r3_a1_candidate":
                had_a1,

            "is_a2_new_work_level_coverage":
                is_a2_new,

            "a2_marginal_candidate_count":
                int(len(g)),

            "policy_accept_candidate_count":
                accept_count,

            "policy_review_candidate_count":
                review_count,

            "operational_include_candidate_count":
                operational_include_count,

            "final_valid_candidate_count":
                final_valid_count,

            "final_invalid_candidate_count":
                final_invalid_count,

            "uncertain_candidate_count":
                uncertain_count,

            "unadjudicated_policy_accept_candidate_count":
                unadjudicated_accept_count,

            "adds_operational_work_level_coverage":
                adds_operational,

            "adds_adjudicated_valid_work_level_coverage":
                adds_adjudicated_valid,

            "loses_all_a2_candidates_after_final_disposition":
                loses_all,

            "work_level_a2_status":
                work_status,
        })

    out = pd.DataFrame(rows)

    assert len(out) == 231
    assert out["project_work_id"].is_unique

    # --------------------------------------------------
    # 3. Frozen expected work-level counts
    # --------------------------------------------------

    assert int(
        out[
            "is_a2_new_work_level_coverage"
        ].sum()
    ) == 207

    assert int(
        out[
            "adds_operational_work_level_coverage"
        ].sum()
    ) == 195

    assert int(
        out[
            "loses_all_a2_candidates_after_final_disposition"
        ].sum()
    ) == 12

    assert int(
        out[
            "adds_adjudicated_valid_work_level_coverage"
        ].sum()
    ) == 88

    assert (
        195 + 12 == 207
    )

    status_counts = (
        out[
            "work_level_a2_status"
        ]
        .value_counts()
        .to_dict()
    )

    # 88 A2-new works have at least one final VALID.
    # 107 further A2-new works remain operationally included
    # only via unadjudicated policy ACCEPT candidate(s).
    # 12 lose all A2 marginal candidates.
    # 24 were already covered by A1.
    expected_status = {
        "A2_NEW_RETAINED_WITH_FINAL_VALID": 88,
        "A2_NEW_RETAINED_POLICY_ACCEPT_ONLY": 107,
        "A2_NEW_LOST_AFTER_FINAL_DISPOSITION": 12,
        "ALREADY_A1_COVERED_A2_MARGINAL": 24,
    }

    assert status_counts == expected_status, status_counts

    operational_coverage_works = (
        a1_works
        | set(
            out.loc[
                out[
                    "adds_operational_work_level_coverage"
                ],
                "project_work_id",
            ]
        )
    )

    assert len(
        operational_coverage_works
    ) == 7094

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
            "a2_marginal_candidate_pairs": 963,
            "a2_marginal_project_works": 231,
        },

        "candidate_stage_work_coverage": {
            "r3_a1_project_works": 6899,
            "r3_a2_project_works": 7106,
            "a2_candidate_stage_work_gain": 207,
        },

        "final_operational_work_coverage": {
            "r3_a1_project_works": 6899,
            "a2_operational_work_gain": 195,
            "r3_a1_plus_operational_a2_project_works": 7094,
            "a2_new_works_losing_all_candidates": 12,
            "retention_rate_of_candidate_stage_a2_gain":
                195 / 207,
        },

        "evidence_strength": {
            "a2_new_works_with_at_least_one_final_valid_candidate":
                88,

            "a2_new_works_retained_only_via_unadjudicated_policy_accept":
                107,

            "note": (
                "The 88-work figure is a stronger-evidence subset, "
                "not an estimate of total A2 precision."
            ),
        },

        "work_level_status_counts":
            expected_status,

        "interpretation": [
            (
                "A2 initially adds candidate-level coverage for "
                "207 project works beyond R3+A1."
            ),
            (
                "After applying known final labels and the frozen "
                "operational policy, 195 of those works retain at "
                "least one included A2 candidate."
            ),
            (
                "Twelve A2-new works lose all A2 candidates after "
                "final disposition."
            ),
            (
                "The 107 policy-accept-only works are operationally "
                "retained but do not have an individually adjudicated "
                "VALID candidate."
            ),
            (
                "Work-level operational coverage must not be described "
                "as human-validated coverage."
            ),
        ],
    }

    write_json(summary, OUT_SUMMARY)

    manifest = {
        "release": RELEASE,
        "created_at": CREATED_AT,

        "sources": {
            str(FINAL.relative_to(ROOT)):
                sha256_file(FINAL),

            str(EVIDENCE):
                sha256_file(EVIDENCE),
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

    write_json(manifest, OUT_MANIFEST)

    print(
        "=== A2 PRODUCTION WORK COVERAGE V1 ==="
    )
    print("A2 marginal works:", 231)
    print("A2-new works before disposition:", 207)
    print("operationally retained A2-new works:", 195)
    print("lost A2-new works:", 12)
    print(
        "A2-new works with >=1 final VALID:",
        88,
    )
    print(
        "A2-new works retained via policy ACCEPT only:",
        107,
    )
    print()
    print("R3+A1 work coverage:", 6899)
    print(
        "R3+A1 + operational A2 work coverage:",
        7094,
    )
    print("output:", OUT_DIR)


if __name__ == "__main__":
    main()
