#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os
import random

import pandas as pd
import pyarrow.dataset as ds


ROOT = Path(__file__).resolve().parents[1]

SCAN_DIR = Path(
    "/media/hdd1/user/tsutsui/openalex/scans/"
    "full_r23_v1/full_2040files_4a275210"
)

EVIDENCE = (
    SCAN_DIR
    / "openalex_retrieval_full_r23_hit_evidence_v1.parquet"
)

SCAN_MANIFEST = (
    SCAN_DIR
    / "openalex_retrieval_full_r23_scan_v1_manifest.json"
)

MATCH_REGISTRY = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_match_registry_full_v1"
    / "openalex_retrieval_match_registry_full_v1.parquet"
)

OUT_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_r2a1_baseline_validation_sample_v1"
)

PRIMARY_TSV = (
    OUT_DIR
    / "openalex_r2a1_baseline_primary_pair_sample_v1.tsv"
)

PRIMARY_PARQUET = (
    OUT_DIR
    / "openalex_r2a1_baseline_primary_pair_sample_v1.parquet"
)

SECONDARY_TSV = (
    OUT_DIR
    / "openalex_r2a1_baseline_secondary_work_diagnostic_sample_v1.tsv"
)

SECONDARY_PARQUET = (
    OUT_DIR
    / "openalex_r2a1_baseline_secondary_work_diagnostic_sample_v1.parquet"
)

COMBINED_TSV = (
    OUT_DIR
    / "openalex_r2a1_baseline_validation_sample_combined_v1.tsv"
)

COMBINED_PARQUET = (
    OUT_DIR
    / "openalex_r2a1_baseline_validation_sample_combined_v1.parquet"
)

SUMMARY = (
    OUT_DIR
    / "openalex_r2a1_baseline_validation_sample_summary_v1.json"
)

MANIFEST = (
    OUT_DIR
    / "openalex_r2a1_baseline_validation_sample_v1_manifest.json"
)

RELEASE = "openalex-r2a1-baseline-validation-sample-v1"
CREATED_AT = "2026-10-11"

PRIMARY_N = 800
PRIMARY_SEED = 20261011

SECONDARY_WORKS_PER_NONEXTREME_STRATUM = 60
SECONDARY_WORK_SEED = 20261012

SNAPSHOT_SHA256 = (
    "57959e90573d6ef2adb953fd747ba718"
    "54819880f762077f680083476d490fc9"
)

MATCH_REGISTRY_SHA256 = (
    "ce19cdfc0929139a04f8ee36ec27bd34"
    "b8898c0b969b75fd2f0017fce8147878"
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


def candidate_id(wid, oid):
    payload = f"R2_A1_BASELINE\t{wid}\t{oid}"

    return (
        "OABASEV1_"
        + hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()[:16]
    )


def token_bucket(n):
    if n == 1:
        return "1"
    if n == 2:
        return "2"
    if n <= 4:
        return "3-4"
    return "5+"


def volume_bucket(n):
    if n <= 3:
        return "01_1-3"
    if n <= 10:
        return "02_4-10"
    if n <= 50:
        return "03_11-50"
    if n <= 200:
        return "04_51-200"
    if n <= 1000:
        return "05_201-1000"
    return "06_1001+"


def hit_location(row):
    if row["any_title_match_in_title"] and row["any_title_match_in_abstract"]:
        return "TITLE_AND_ABSTRACT"

    if row["any_title_match_in_title"]:
        return "TITLE_ONLY"

    if row["any_title_match_in_abstract"]:
        return "ABSTRACT_ONLY"

    return "NEITHER"


def counts_dict(series):
    return {
        str(k): int(v)
        for k, v
        in series.value_counts().sort_index().items()
    }


def main():

    for path in [
        EVIDENCE,
        SCAN_MANIFEST,
        MATCH_REGISTRY,
    ]:
        if not path.exists():
            raise FileNotFoundError(path)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory already exists: {OUT_DIR}"
        )

    # --------------------------------------------------
    # 1. Frozen-source checks
    # --------------------------------------------------

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
        scan_manifest["snapshot"]["processed_file_count"]
        == 2040
    )

    assert (
        scan_manifest["snapshot"]["full_inventory_sha256"]
        == SNAPSHOT_SHA256
    )

    assert (
        scan_manifest["snapshot"]["processed_inventory_sha256"]
        == SNAPSHOT_SHA256
    )

    assert (
        sha256_file(MATCH_REGISTRY)
        == MATCH_REGISTRY_SHA256
    )

    # --------------------------------------------------
    # 2. Complete R2+A1 baseline candidate universe
    # --------------------------------------------------

    dataset = ds.dataset(
        str(EVIDENCE),
        format="parquet",
    )

    x = dataset.to_table(
        columns=[
            "query_id",
            "project_work_id",
            "openalex_work_id",
            "title_match_in_title",
            "title_match_in_abstract",
            "author_a1_hit",
        ],
        filter=(
            (ds.field("target_lane") == "resolved_w")
            & (ds.field("query_route") == "R2")
            & (ds.field("author_a1_hit") == True)
        ),
    ).to_pandas()

    q = pd.read_parquet(
        MATCH_REGISTRY,
        columns=[
            "query_id",
            "title_match_token_count",
        ],
    ).fillna("")

    assert q["query_id"].is_unique

    x = x.merge(
        q,
        on="query_id",
        how="left",
        validate="many_to_one",
    )

    x["title_match_token_count"] = pd.to_numeric(
        x["title_match_token_count"],
        errors="raise",
    ).astype(int)

    universe = (
        x.groupby(
            [
                "project_work_id",
                "openalex_work_id",
            ],
            sort=True,
        )
        .agg(
            evidence_row_count=(
                "query_id",
                "size",
            ),
            query_count=(
                "query_id",
                "nunique",
            ),
            title_match_token_count_min=(
                "title_match_token_count",
                "min",
            ),
            title_match_token_count_max=(
                "title_match_token_count",
                "max",
            ),
            any_title_match_in_title=(
                "title_match_in_title",
                "any",
            ),
            any_title_match_in_abstract=(
                "title_match_in_abstract",
                "any",
            ),
        )
        .reset_index()
    )

    assert len(universe) == 290480
    assert universe["project_work_id"].nunique() == 6873

    assert not universe[
        [
            "project_work_id",
            "openalex_work_id",
        ]
    ].duplicated().any()

    universe["baseline_candidate_id"] = [
        candidate_id(wid, oid)
        for wid, oid
        in universe[
            [
                "project_work_id",
                "openalex_work_id",
            ]
        ].itertuples(
            index=False,
            name=None,
        )
    ]

    assert universe[
        "baseline_candidate_id"
    ].is_unique

    universe[
        "hit_location"
    ] = universe.apply(
        hit_location,
        axis=1,
    )

    assert not universe[
        "hit_location"
    ].eq("NEITHER").any()

    universe[
        "title_token_bucket"
    ] = universe[
        "title_match_token_count_min"
    ].map(token_bucket)

    work_counts = (
        universe.groupby(
            "project_work_id"
        )
        .size()
    )

    universe[
        "work_candidate_count"
    ] = universe[
        "project_work_id"
    ].map(work_counts)

    universe[
        "work_volume_bucket"
    ] = universe[
        "work_candidate_count"
    ].map(volume_bucket)

    # Frozen full-universe checks from the read-only audit.
    assert counts_dict(
        universe["hit_location"]
    ) == {
        "ABSTRACT_ONLY": 171998,
        "TITLE_AND_ABSTRACT": 56137,
        "TITLE_ONLY": 62345,
    }

    assert counts_dict(
        universe["title_token_bucket"]
    ) == {
        "1": 84290,
        "2": 79265,
        "3-4": 101140,
        "5+": 25785,
    }

    assert counts_dict(
        universe["work_volume_bucket"]
    ) == {
        "01_1-3": 5891,
        "02_4-10": 8013,
        "03_11-50": 25520,
        "04_51-200": 44189,
        "05_201-1000": 61166,
        "06_1001+": 145701,
    }

    work_table = (
        work_counts
        .rename("work_candidate_count")
        .reset_index()
    )

    work_table[
        "work_volume_bucket"
    ] = work_table[
        "work_candidate_count"
    ].map(volume_bucket)

    assert counts_dict(
        work_table["work_volume_bucket"]
    ) == {
        "01_1-3": 3846,
        "02_4-10": 1306,
        "03_11-50": 1076,
        "04_51-200": 443,
        "05_201-1000": 154,
        "06_1001+": 48,
    }

    universe = (
        universe.sort_values(
            [
                "project_work_id",
                "openalex_work_id",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------
    # 3. PRIMARY: simple random pair sample
    #
    # Fixed seed chosen before inspecting any judgments.
    # --------------------------------------------------

    rng = random.Random(
        PRIMARY_SEED
    )

    primary_indices = sorted(
        rng.sample(
            range(len(universe)),
            PRIMARY_N,
        )
    )

    primary = (
        universe.iloc[
            primary_indices
        ]
        .copy()
        .reset_index(drop=True)
    )

    assert len(primary) == PRIMARY_N
    assert primary[
        "baseline_candidate_id"
    ].is_unique

    primary[
        "sample_component"
    ] = "PRIMARY_PAIR_RANDOM"

    primary[
        "sampling_probability"
    ] = (
        PRIMARY_N
        / len(universe)
    )

    # --------------------------------------------------
    # 4. SECONDARY: work-balanced diagnostic
    #
    # 60 works from each of buckets 01-05.
    # All 48 works in bucket 06.
    #
    # One candidate pair is selected per sampled work.
    #
    # This sample is diagnostic, not the estimator for
    # overall pair-level baseline precision.
    # --------------------------------------------------

    work_rng = random.Random(
        SECONDARY_WORK_SEED
    )

    selected_works = []

    buckets = [
        "01_1-3",
        "02_4-10",
        "03_11-50",
        "04_51-200",
        "05_201-1000",
        "06_1001+",
    ]

    for bucket in buckets:

        works = sorted(
            work_table.loc[
                work_table[
                    "work_volume_bucket"
                ].eq(bucket),
                "project_work_id",
            ].astype(str)
        )

        if bucket == "06_1001+":
            chosen = works
        else:
            chosen = sorted(
                work_rng.sample(
                    works,
                    SECONDARY_WORKS_PER_NONEXTREME_STRATUM,
                )
            )

        selected_works.extend(
            (wid, bucket)
            for wid in chosen
        )

    selected_work_df = pd.DataFrame(
        selected_works,
        columns=[
            "project_work_id",
            "secondary_sampling_stratum",
        ],
    )

    assert len(selected_work_df) == 348
    assert selected_work_df[
        "project_work_id"
    ].is_unique

    secondary_parts = []

    for row in selected_work_df.itertuples(
        index=False
    ):
        wid = row.project_work_id

        z = (
            universe.loc[
                universe[
                    "project_work_id"
                ].eq(wid)
            ]
            .sort_values(
                "openalex_work_id",
                kind="stable",
            )
            .copy()
        )

        # Stable per-work pseudo-random draw.
        local_seed = int(
            hashlib.sha256(
                (
                    "openalex-r2a1-workdiag-v1"
                    f"\t{wid}"
                ).encode("utf-8")
            ).hexdigest()[:16],
            16,
        )

        local_rng = random.Random(
            local_seed
        )

        pick = local_rng.randrange(
            len(z)
        )

        one = z.iloc[
            [pick]
        ].copy()

        one[
            "secondary_sampling_stratum"
        ] = row.secondary_sampling_stratum

        secondary_parts.append(
            one
        )

    secondary = pd.concat(
        secondary_parts,
        ignore_index=True,
    )

    assert len(secondary) == 348
    assert secondary[
        "project_work_id"
    ].is_unique
    assert secondary[
        "baseline_candidate_id"
    ].is_unique

    secondary[
        "sample_component"
    ] = "SECONDARY_WORK_DIAGNOSTIC"

    # No single global pair inclusion probability is
    # assigned: this is a stratified work diagnostic.
    secondary[
        "sampling_probability"
    ] = pd.NA

    # --------------------------------------------------
    # 5. Combined membership
    # --------------------------------------------------

    pids = set(
        primary[
            "baseline_candidate_id"
        ]
    )

    sids = set(
        secondary[
            "baseline_candidate_id"
        ]
    )

    union_ids = (
        pids | sids
    )

    combined = (
        universe.loc[
            universe[
                "baseline_candidate_id"
            ].isin(union_ids)
        ]
        .copy()
    )

    combined[
        "in_primary_pair_sample"
    ] = combined[
        "baseline_candidate_id"
    ].isin(pids)

    combined[
        "in_secondary_work_diagnostic_sample"
    ] = combined[
        "baseline_candidate_id"
    ].isin(sids)

    combined[
        "sample_membership"
    ] = "PRIMARY_ONLY"

    combined.loc[
        combined[
            "in_secondary_work_diagnostic_sample"
        ]
        & ~combined[
            "in_primary_pair_sample"
        ],
        "sample_membership",
    ] = "SECONDARY_ONLY"

    combined.loc[
        combined[
            "in_secondary_work_diagnostic_sample"
        ]
        & combined[
            "in_primary_pair_sample"
        ],
        "sample_membership",
    ] = "BOTH"

    combined = (
        combined.sort_values(
            [
                "project_work_id",
                "openalex_work_id",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    overlap_n = len(
        pids & sids
    )

    # --------------------------------------------------
    # 6. Outputs
    # --------------------------------------------------

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=False,
    )

    write_tsv(
        primary,
        PRIMARY_TSV,
    )

    write_parquet(
        primary,
        PRIMARY_PARQUET,
    )

    write_tsv(
        secondary,
        SECONDARY_TSV,
    )

    write_parquet(
        secondary,
        SECONDARY_PARQUET,
    )

    write_tsv(
        combined,
        COMBINED_TSV,
    )

    write_parquet(
        combined,
        COMBINED_PARQUET,
    )

    summary = {
        "release": RELEASE,
        "created_at": CREATED_AT,

        "baseline_universe": {
            "definition":
                "resolved_w R2 + A1",
            "candidate_pairs":
                len(universe),
            "candidate_bearing_project_works":
                int(
                    universe[
                        "project_work_id"
                    ].nunique()
                ),
        },

        "primary_pair_sample": {
            "design":
                "simple random sample without replacement",
            "n": len(primary),
            "seed": PRIMARY_SEED,
            "population_n": len(universe),
            "sampling_fraction":
                len(primary) / len(universe),
            "project_works_represented":
                int(
                    primary[
                        "project_work_id"
                    ].nunique()
                ),
            "hit_location_counts":
                counts_dict(
                    primary[
                        "hit_location"
                    ]
                ),
            "title_token_bucket_counts":
                counts_dict(
                    primary[
                        "title_token_bucket"
                    ]
                ),
            "work_volume_bucket_pair_counts":
                counts_dict(
                    primary[
                        "work_volume_bucket"
                    ]
                ),
        },

        "secondary_work_diagnostic_sample": {
            "design":
                (
                    "stratified work sample by baseline "
                    "candidate volume; one pair per work"
                ),
            "n_pairs": len(secondary),
            "n_works": int(
                secondary[
                    "project_work_id"
                ].nunique()
            ),
            "work_seed":
                SECONDARY_WORK_SEED,
            "work_counts_by_stratum":
                counts_dict(
                    secondary[
                        "secondary_sampling_stratum"
                    ]
                ),
            "all_1001_plus_works_included":
                True,
        },

        "combined": {
            "primary_n": len(primary),
            "secondary_n": len(secondary),
            "overlap_pairs": overlap_n,
            "unique_pairs":
                len(combined),
        },

        "interpretation": [
            (
                "The primary 800-pair sample is the "
                "validation sample for pair-level R2+A1 "
                "baseline target-attribution precision."
            ),
            (
                "The secondary 348-work sample is a "
                "work-balanced diagnostic and is not "
                "pooled unweighted with the primary "
                "sample for overall pair-level precision."
            ),
            (
                "Sampling membership was fixed without "
                "using target-attribution judgments."
            ),
            (
                "Risk features are retained for later "
                "diagnostic analysis but must be hidden "
                "from blind adjudication where they could "
                "bias the reviewer."
            ),
        ],
    }

    write_json(
        summary,
        SUMMARY,
    )

    manifest = {
        "release": RELEASE,
        "created_at": CREATED_AT,

        "source_provenance": {
            "scan_manifest_path":
                str(SCAN_MANIFEST),
            "scan_manifest_sha256":
                sha256_file(
                    SCAN_MANIFEST
                ),
            "match_registry_path":
                str(
                    MATCH_REGISTRY.relative_to(
                        ROOT
                    )
                ),
            "match_registry_sha256":
                sha256_file(
                    MATCH_REGISTRY
                ),
            "snapshot_inventory_sha256":
                SNAPSHOT_SHA256,
        },

        "sampling": {
            "primary_seed":
                PRIMARY_SEED,
            "primary_n":
                PRIMARY_N,
            "secondary_work_seed":
                SECONDARY_WORK_SEED,
            "secondary_nonextreme_works_per_stratum":
                SECONDARY_WORKS_PER_NONEXTREME_STRATUM,
            "secondary_extreme_stratum":
                "06_1001+",
            "secondary_extreme_stratum_rule":
                "complete enumeration of 48 works",
        },

        "outputs": {
            str(
                PRIMARY_TSV.relative_to(ROOT)
            ):
                sha256_file(PRIMARY_TSV),

            str(
                PRIMARY_PARQUET.relative_to(ROOT)
            ):
                sha256_file(PRIMARY_PARQUET),

            str(
                SECONDARY_TSV.relative_to(ROOT)
            ):
                sha256_file(SECONDARY_TSV),

            str(
                SECONDARY_PARQUET.relative_to(ROOT)
            ):
                sha256_file(SECONDARY_PARQUET),

            str(
                COMBINED_TSV.relative_to(ROOT)
            ):
                sha256_file(COMBINED_TSV),

            str(
                COMBINED_PARQUET.relative_to(ROOT)
            ):
                sha256_file(COMBINED_PARQUET),

            str(
                SUMMARY.relative_to(ROOT)
            ):
                sha256_file(SUMMARY),
        },
    }

    write_json(
        manifest,
        MANIFEST,
    )

    print(
        "=== R2+A1 BASELINE VALIDATION SAMPLE V1 ==="
    )
    print()
    print(
        "baseline universe:",
        len(universe),
        "pairs /",
        universe[
            "project_work_id"
        ].nunique(),
        "works",
    )
    print()
    print(
        "PRIMARY pair sample:",
        len(primary),
    )
    print(
        "primary represented works:",
        primary[
            "project_work_id"
        ].nunique(),
    )
    print()
    print(
        "SECONDARY work diagnostic:",
        len(secondary),
        "pairs /",
        secondary[
            "project_work_id"
        ].nunique(),
        "works",
    )
    print()
    print(
        "primary-secondary overlap:",
        overlap_n,
    )
    print(
        "combined unique pairs:",
        len(combined),
    )
    print()
    print("PRIMARY hit location:")
    print(
        primary[
            "hit_location"
        ].value_counts().to_string()
    )
    print()
    print("PRIMARY title token bucket:")
    print(
        primary[
            "title_token_bucket"
        ].value_counts().sort_index().to_string()
    )
    print()
    print("PRIMARY work-volume bucket:")
    print(
        primary[
            "work_volume_bucket"
        ].value_counts().sort_index().to_string()
    )
    print()
    print("SECONDARY work strata:")
    print(
        secondary[
            "secondary_sampling_stratum"
        ].value_counts().sort_index().to_string()
    )
    print()
    print("output:", OUT_DIR)


if __name__ == "__main__":
    main()
