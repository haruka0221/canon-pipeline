from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

MATCH_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_match_registry_full_v1"
)

CAL_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_calibration_sample_v2"
)

OUT_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_a2_validation_sample_v1"
)

MATCH_REGISTRY = (
    MATCH_DIR
    / "openalex_retrieval_match_registry_full_v1.parquet"
)

MATCH_MANIFEST = (
    MATCH_DIR
    / "openalex_retrieval_match_registry_full_v1_manifest.json"
)

CAL_TARGETS = (
    CAL_DIR
    / "openalex_retrieval_calibration_targets_v2.parquet"
)

CAL_MANIFEST = (
    CAL_DIR
    / "openalex_retrieval_calibration_sample_v2_manifest.json"
)

OUT_POP_TSV = (
    OUT_DIR
    / "openalex_a2_validation_population_v1.tsv"
)

OUT_POP_PARQUET = (
    OUT_DIR
    / "openalex_a2_validation_population_v1.parquet"
)

OUT_QUERIES_TSV = (
    OUT_DIR
    / "openalex_a2_validation_queries_v1.tsv"
)

OUT_QUERIES_PARQUET = (
    OUT_DIR
    / "openalex_a2_validation_queries_v1.parquet"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openalex_a2_validation_sample_v1_manifest.json"
)

RELEASE = "openalex-a2-validation-sample-v1"
VERSION = "v1"
CREATED_AT = "2026-10-06"

SEED = 20261006
COHORT_NAME = "a2_primary_validation_v1"

N_VALIDATE = 500

EXPECTED_RESOLVED_W = 32082
EXPECTED_CALIBRATION_W = 1846
EXPECTED_A2_SENSITIVE_W = 1692
EXPECTED_CAL_A2_SENSITIVE_W = 218
EXPECTED_ELIGIBLE_W = 1474

EXPECTED_SELECTED_W = 500
EXPECTED_SELECTED_LOGICAL_QUERIES = 1000
EXPECTED_SELECTED_R2 = 500
EXPECTED_SELECTED_R3 = 500
EXPECTED_SELECTED_EXECUTIONS = 496


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


def write_atomic_parquet(
    df: pd.DataFrame,
    path: Path,
) -> None:
    tmp = path.with_name(
        path.name + ".tmp"
    )

    df.to_parquet(
        tmp,
        index=False,
        engine="pyarrow",
    )

    os.replace(tmp, path)


def write_atomic_json(
    value: dict,
    path: Path,
) -> None:
    tmp = path.with_name(
        path.name + ".tmp"
    )

    tmp.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    os.replace(tmp, path)


def stable_score(
    project_work_id: str,
) -> str:
    payload = (
        f"{SEED}\x1f"
        f"{COHORT_NAME}\x1f"
        f"{project_work_id}"
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def main() -> None:

    for path in [
        MATCH_REGISTRY,
        MATCH_MANIFEST,
        CAL_TARGETS,
        CAL_MANIFEST,
    ]:
        require(path)

    full = pd.read_parquet(
        MATCH_REGISTRY
    ).fillna("")

    cal = pd.read_parquet(
        CAL_TARGETS
    ).fillna("")

    match_manifest = json.loads(
        MATCH_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    cal_manifest = json.loads(
        CAL_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    if (
        match_manifest.get("release")
        != "openalex-retrieval-match-registry-full-v1"
    ):
        raise RuntimeError(
            "Unexpected full match registry release"
        )

    if (
        cal_manifest.get("release")
        != "openalex-retrieval-calibration-sample-v2"
    ):
        raise RuntimeError(
            "Unexpected calibration sample release"
        )

    # --------------------------------------------------------
    # Full resolved-W universe
    # --------------------------------------------------------

    resolved = full.loc[
        full["target_lane"].eq(
            "resolved_w"
        )
        & full["project_work_id"].ne("")
    ].copy()

    all_w = set(
        resolved["project_work_id"]
    )

    if (
        len(all_w)
        != EXPECTED_RESOLVED_W
    ):
        raise RuntimeError(
            "Unexpected resolved-W count: "
            f"{len(all_w)}"
        )

    # --------------------------------------------------------
    # Complete calibration exclusion
    # --------------------------------------------------------

    cal_w = set(
        cal.loc[
            cal["target_lane"].eq(
                "resolved_w"
            )
            & cal[
                "project_work_id"
            ].ne(""),
            "project_work_id",
        ]
    )

    if (
        len(cal_w)
        != EXPECTED_CALIBRATION_W
    ):
        raise RuntimeError(
            "Unexpected calibration-W count: "
            f"{len(cal_w)}"
        )

    # --------------------------------------------------------
    # A2-sensitive population
    #
    # A2 marginal route is defined on R3:
    #   R3+A2 minus R3+A1
    #
    # Therefore sensitivity is defined by availability
    # of a non-empty conservative A2 reverse on R3.
    # --------------------------------------------------------

    r3 = resolved.loc[
        resolved["query_route"].eq("R3")
    ].copy()

    a2_sensitive_w = set(
        r3.loc[
            r3[
                "author_a2_reverse_available"
            ].eq(True),
            "project_work_id",
        ]
    )

    if (
        len(a2_sensitive_w)
        != EXPECTED_A2_SENSITIVE_W
    ):
        raise RuntimeError(
            "Unexpected A2-sensitive W count: "
            f"{len(a2_sensitive_w)}"
        )

    cal_a2_w = (
        a2_sensitive_w
        & cal_w
    )

    if (
        len(cal_a2_w)
        != EXPECTED_CAL_A2_SENSITIVE_W
    ):
        raise RuntimeError(
            "Unexpected calibration A2-sensitive "
            "W count: "
            f"{len(cal_a2_w)}"
        )

    eligible_w = sorted(
        a2_sensitive_w
        - cal_w
    )

    if (
        len(eligible_w)
        != EXPECTED_ELIGIBLE_W
    ):
        raise RuntimeError(
            "Unexpected validation population: "
            f"{len(eligible_w)}"
        )

    # --------------------------------------------------------
    # Stable work-level probability sample
    # --------------------------------------------------------

    population = pd.DataFrame({
        "project_work_id":
            eligible_w,
    })

    population[
        "validation_score_sha256"
    ] = (
        population[
            "project_work_id"
        ].map(stable_score)
    )

    population = (
        population.sort_values(
            [
                "validation_score_sha256",
                "project_work_id",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    population[
        "validation_rank"
    ] = (
        population.index
        + 1
    )

    population[
        "primary_validation_selected"
    ] = (
        population[
            "validation_rank"
        ].le(N_VALIDATE)
    )

    population[
        "sampling_frame"
    ] = (
        "A2_sensitive_resolved_W_"
        "outside_complete_calibration_sample_v2"
    )

    population[
        "sampling_unit"
    ] = "project_work_id"

    population[
        "sampling_method"
    ] = "stable_sha256_rank"

    population[
        "sampling_seed"
    ] = SEED

    selected_w = set(
        population.loc[
            population[
                "primary_validation_selected"
            ],
            "project_work_id",
        ]
    )

    if len(selected_w) != N_VALIDATE:
        raise RuntimeError(
            "Unexpected selected validation W count"
        )

    if len(selected_w) != EXPECTED_SELECTED_W:
        raise RuntimeError(
            "Frozen selected validation W count changed: "
            f"{len(selected_w)}"
        )

    if selected_w & cal_w:
        raise RuntimeError(
            "Validation sample overlaps calibration"
        )

    if not selected_w.issubset(
        a2_sensitive_w
    ):
        raise RuntimeError(
            "Validation sample contains "
            "non-A2-sensitive W"
        )

    # --------------------------------------------------------
    # Freeze R2/R3 logical-query subset for selected works.
    #
    # R2 is retained for route-comparison diagnostics.
    # R4 remains outside the validation scan.
    # --------------------------------------------------------

    queries = resolved.loc[
        resolved[
            "project_work_id"
        ].isin(selected_w)
        & resolved[
            "query_route"
        ].isin(
            ["R2", "R3"]
        )
    ].copy()

    queries = (
        queries.sort_values(
            "query_id",
            kind="stable",
        )
        .reset_index(drop=True)
    )

    if not queries[
        "query_id"
    ].is_unique:
        raise RuntimeError(
            "Validation query_id is not unique"
        )

    if set(
        queries["project_work_id"]
    ) != selected_w:
        missing = (
            selected_w
            - set(
                queries[
                    "project_work_id"
                ]
            )
        )

        raise RuntimeError(
            "Selected W missing R2/R3 queries: "
            f"{sorted(missing)[:20]}"
        )

    if not set(
        queries["query_route"]
    ).issubset(
        {"R2", "R3"}
    ):
        raise RuntimeError(
            "Unexpected route in validation queries"
        )

    r3_selected_w = set(
        queries.loc[
            queries[
                "query_route"
            ].eq("R3"),
            "project_work_id",
        ]
    )

    if r3_selected_w != selected_w:
        raise RuntimeError(
            "Every selected W must have R3"
        )

    # --------------------------------------------------------
    # Diagnostics
    # --------------------------------------------------------

    route_counts = {
        str(k): int(v)
        for k, v
        in queries[
            "query_route"
        ].value_counts()
        .sort_index()
        .items()
    }

    selected_execution_count = int(
        queries[
            "execution_id"
        ].nunique()
    )

    if (
        len(queries)
        != EXPECTED_SELECTED_LOGICAL_QUERIES
    ):
        raise RuntimeError(
            "Frozen validation logical-query count changed: "
            f"{len(queries)}"
        )

    if route_counts != {
        "R2": EXPECTED_SELECTED_R2,
        "R3": EXPECTED_SELECTED_R3,
    }:
        raise RuntimeError(
            "Frozen validation route counts changed: "
            f"{route_counts}"
        )

    if (
        selected_execution_count
        != EXPECTED_SELECTED_EXECUTIONS
    ):
        raise RuntimeError(
            "Frozen validation execution count changed: "
            f"{selected_execution_count}"
        )

    selected_alias_count = int(
        queries[
            "alias_id"
        ].replace(
            "",
            pd.NA,
        ).nunique(
            dropna=True
        )
    )

    # --------------------------------------------------------
    # Write immutable sample release
    # --------------------------------------------------------

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory exists: "
            f"{OUT_DIR}"
        )

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=False,
    )

    write_atomic_tsv(
        population,
        OUT_POP_TSV,
    )

    write_atomic_parquet(
        population,
        OUT_POP_PARQUET,
    )

    write_atomic_tsv(
        queries,
        OUT_QUERIES_TSV,
    )

    write_atomic_parquet(
        queries,
        OUT_QUERIES_PARQUET,
    )

    manifest = {
        "release": RELEASE,
        "version": VERSION,
        "created_at": CREATED_AT,
        "status":
            "a2_validation_sample_frozen",

        "purpose":
            (
                "Freeze an independent work-level "
                "validation sample for the calibration-"
                "selected A2 author-reversal marginal "
                "retrieval policy."
            ),

        "sampling": {
            "sampling_unit":
                "project_work_id",

            "sampling_frame":
                (
                    "Resolved project works with an "
                    "available R3 conservative A2 reverse "
                    "variant, excluding every resolved "
                    "work in retrieval calibration "
                    "sample v2."
                ),

            "method":
                "stable_sha256_rank",

            "seed":
                SEED,

            "cohort_name":
                COHORT_NAME,

            "score_payload":
                (
                    "seed + ASCII Unit Separator + "
                    "cohort_name + ASCII Unit Separator + "
                    "project_work_id"
                ),

            "primary_validation_n":
                N_VALIDATE,

            "policy_blind_sampling":
                True,

            "human_adjudication_used_for_sampling":
                False,
        },

        "counts": {
            "resolved_population_w":
                len(all_w),

            "calibration_resolved_w":
                len(cal_w),

            "a2_sensitive_w":
                len(a2_sensitive_w),

            "a2_sensitive_in_calibration_w":
                len(cal_a2_w),

            "eligible_validation_population_w":
                len(eligible_w),

            "primary_validation_selected_w":
                len(selected_w),

            "reserved_unselected_w":
                len(eligible_w)
                - len(selected_w),

            "selected_logical_queries":
                len(queries),

            "selected_unique_execution_ids":
                selected_execution_count,

            "selected_unique_alias_ids":
                selected_alias_count,

            "selected_queries_by_route":
                route_counts,
        },

        "route_scope": {
            "included":
                ["R2", "R3"],

            "validation_target":
                "A2_AUTHOR_REVERSAL",

            "R4_status":
                "excluded",

            "alias_policy_status":
                (
                    "Not independently validated by this "
                    "sample. Current-release Alias-risk "
                    "works were exhausted by calibration."
                ),
        },

        "interpretation": {
            "primary":
                (
                    "This is a held-out descriptive "
                    "validation sample of frozen current-"
                    "release A2-sensitive works."
                ),

            "not_claimed":
                [
                    "population-wide statistical inference",
                    "validation of R4 title-only retrieval",
                    "independent validation of Alias expansion",
                    "recall estimation",
                ],

            "policy_lock":
                (
                    "The frozen A2 ACCEPT/REVIEW rule "
                    "must not be tuned using validation "
                    "judgments."
                ),

            "uncertain_policy":
                (
                    "UNCERTAIN must remain distinct from "
                    "INVALID."
                ),
        },

        "source_releases": {
            "full_match_registry":
                match_manifest["release"],

            "calibration_sample":
                cal_manifest["release"],
        },

        "inputs": {
            str(
                MATCH_REGISTRY.relative_to(ROOT)
            ):
                sha256_file(
                    MATCH_REGISTRY
                ),

            str(
                MATCH_MANIFEST.relative_to(ROOT)
            ):
                sha256_file(
                    MATCH_MANIFEST
                ),

            str(
                CAL_TARGETS.relative_to(ROOT)
            ):
                sha256_file(
                    CAL_TARGETS
                ),

            str(
                CAL_MANIFEST.relative_to(ROOT)
            ):
                sha256_file(
                    CAL_MANIFEST
                ),
        },

        "outputs": {
            str(
                OUT_POP_TSV.relative_to(ROOT)
            ):
                sha256_file(
                    OUT_POP_TSV
                ),

            str(
                OUT_POP_PARQUET.relative_to(ROOT)
            ):
                sha256_file(
                    OUT_POP_PARQUET
                ),

            str(
                OUT_QUERIES_TSV.relative_to(ROOT)
            ):
                sha256_file(
                    OUT_QUERIES_TSV
                ),

            str(
                OUT_QUERIES_PARQUET.relative_to(ROOT)
            ):
                sha256_file(
                    OUT_QUERIES_PARQUET
                ),
        },

        "next_step":
            (
                "Build a validation-specific R2/R3 "
                "matching registry/scanner input from "
                "this frozen sample and scan the complete "
                "frozen OpenAlex snapshot without changing "
                "the locked A2 policy."
            ),
    }

    write_atomic_json(
        manifest,
        OUT_MANIFEST,
    )

    print("=== A2 VALIDATION SAMPLE V1 ===")
    print(
        "A2-sensitive W:",
        len(a2_sensitive_w),
    )
    print(
        "in calibration:",
        len(cal_a2_w),
    )
    print(
        "eligible outside calibration:",
        len(eligible_w),
    )
    print(
        "selected:",
        len(selected_w),
    )
    print(
        "reserved:",
        len(eligible_w) - len(selected_w),
    )

    print("\nquery routes:")
    print(
        queries[
            "query_route"
        ].value_counts()
        .sort_index()
        .to_string()
    )

    print(
        "\nunique executions:",
        selected_execution_count,
    )

    print("\nfirst 10 selected W:")
    print(
        "\n".join(
            population.loc[
                population[
                    "primary_validation_selected"
                ],
                "project_work_id",
            ]
            .head(10)
            .tolist()
        )
    )

    print("\noutputs:")
    for p in [
        OUT_POP_TSV,
        OUT_POP_PARQUET,
        OUT_QUERIES_TSV,
        OUT_QUERIES_PARQUET,
        OUT_MANIFEST,
    ]:
        print(
            p.relative_to(ROOT)
        )


if __name__ == "__main__":
    main()
