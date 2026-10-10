#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os

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

OA_RECORDS = (
    SCAN_DIR
    / "openalex_retrieval_full_r23_oa_records_v1.parquet"
)

SCAN_MANIFEST = (
    SCAN_DIR
    / "openalex_retrieval_full_r23_scan_v1_manifest.json"
)

MATCH_REGISTRY = (
    ROOT
    / "derived/openalex_production/"
      "retrieval_match_registry_full_v1/"
      "openalex_retrieval_match_registry_full_v1.parquet"
)

ALIASES = (
    ROOT
    / "derived/openalex_production/"
      "registry_v4/"
      "openalex_aliases_v4.parquet"
)

CALIBRATION = (
    ROOT
    / "derived/openalex_production/"
      "retrieval_precision_review_candidates_v3/"
      "full_profile_57959e90/"
      "openalex_retrieval_precision_review_candidates_v3.parquet"
)

HELDOUT = (
    ROOT
    / "derived/openalex_production/"
      "retrieval_a2_validation_candidates_v1/"
      "openalex_a2_validation_candidates_v1.parquet"
)

OUT_DIR = (
    ROOT
    / "derived/openalex_production/"
      "retrieval_a2_production_routing_v1"
)

RELEASE = "openalex-a2-production-routing-v1"
VERSION = "v1"
CREATED_AT = "2026-10-10"

SNAPSHOT_SHA256 = (
    "57959e90573d6ef2adb953fd747ba718"
    "54819880f762077f680083476d490fc9"
)

MATCH_REGISTRY_SHA256 = (
    "ce19cdfc0929139a04f8ee36ec27bd34"
    "b8898c0b969b75fd2f0017fce8147878"
)

ALIAS_REGISTRY_SHA256 = (
    "c9146c34bc6f5599ea87551c259607d0"
    "bdd5dc6d9aaefa414c92a5e2ad92aaa7"
)


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


def pair_set(df: pd.DataFrame):
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


def joined(values) -> str:
    return " || ".join(
        sorted({
            str(v)
            for v in values
            if pd.notna(v)
            and str(v) != ""
        })
    )


def candidate_id(wid, oid):
    s = (
        "A2_AUTHOR_REVERSAL"
        f"\t{wid}\t{oid}"
    )

    return (
        "OA2PRODV1_"
        + hashlib.sha256(
            s.encode("utf-8")
        ).hexdigest()[:16]
    )


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


def write_parquet(df, path):
    tmp = path.with_name(
        path.name + ".tmp"
    )

    df.to_parquet(
        tmp,
        index=False,
        engine="pyarrow",
    )

    os.replace(tmp, path)


def write_json(obj, path):
    tmp = path.with_name(
        path.name + ".tmp"
    )

    tmp.write_text(
        json.dumps(
            obj,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    os.replace(tmp, path)


def main():

    for p in [
        EVIDENCE,
        OA_RECORDS,
        SCAN_MANIFEST,
        MATCH_REGISTRY,
        ALIASES,
        CALIBRATION,
        HELDOUT,
    ]:
        require(p)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory already exists: {OUT_DIR}"
        )

    # --------------------------------------------------------
    # 1. Frozen-source audit
    # --------------------------------------------------------

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
            "processed_file_count"
        ]
        == 2040
    )

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

    assert (
        sha256_file(MATCH_REGISTRY)
        == MATCH_REGISTRY_SHA256
    )

    assert (
        sha256_file(ALIASES)
        == ALIAS_REGISTRY_SHA256
    )

    # --------------------------------------------------------
    # 2. Full A2 marginal candidate universe
    #
    # resolved-W:
    #
    #       (R3 + A2) - (R3 + A1)
    #
    # at project_work_id × OpenAlex Work level.
    # --------------------------------------------------------

    dataset = ds.dataset(
        str(EVIDENCE),
        format="parquet",
    )

    x = dataset.to_table(
        columns=[
            "query_id",
            "execution_id",
            "project_work_id",
            "alias_id",
            "openalex_work_id",
            "title_match_in_title",
            "title_match_in_abstract",
            "author_a1_hit",
            "author_a2_reverse_hit",
            "author_a2_hit",
        ],
        filter=(
            (ds.field("target_lane") == "resolved_w")
            & (ds.field("query_route") == "R3")
            & (ds.field("author_a2_hit") == True)
        ),
    ).to_pandas()

    assert len(x) == 307699

    r3_a2 = pair_set(x)

    r3_a1 = pair_set(
        x.loc[
            x["author_a1_hit"]
            .astype(bool)
        ]
    )

    a2_increment = (
        r3_a2 - r3_a1
    )

    assert len(r3_a2) == 291859
    assert len(r3_a1) == 290896
    assert len(a2_increment) == 963

    x["pair_key"] = list(
        zip(
            x["project_work_id"],
            x["openalex_work_id"],
        )
    )

    support = x.loc[
        x["pair_key"].isin(
            a2_increment
        )
    ].copy()

    # --------------------------------------------------------
    # 3. Frozen query features
    # --------------------------------------------------------

    q = pd.read_parquet(
        MATCH_REGISTRY,
        columns=[
            "query_id",
            "target_lane",
            "project_work_id",
            "query_route",
            "query_title",
            "query_author",
            "title_match_norm",
            "title_match_token_count",
            "author_a1_norm",
            "author_a2_reverse_norm",
        ],
    ).fillna("")

    assert q["query_id"].is_unique

    support = support.merge(
        q[
            [
                "query_id",
                "query_title",
                "query_author",
                "title_match_norm",
                "title_match_token_count",
                "author_a1_norm",
                "author_a2_reverse_norm",
            ]
        ],
        on="query_id",
        how="left",
        validate="many_to_one",
    )

    support[
        "title_match_token_count"
    ] = pd.to_numeric(
        support[
            "title_match_token_count"
        ],
        errors="raise",
    ).astype(int)

    # R2 baseline context for human-readable provenance.
    r2_context = (
        q.loc[
            q["target_lane"].eq(
                "resolved_w"
            )
            & q["query_route"].eq("R2")
            & q["project_work_id"].ne("")
        ]
        .groupby(
            "project_work_id",
            sort=True,
        )
        .agg(
            r2_baseline_titles=(
                "query_title",
                joined,
            ),
            r2_baseline_authors=(
                "query_author",
                joined,
            ),
        )
        .reset_index()
    )

    # --------------------------------------------------------
    # 4. Frozen cross-W collision feature
    # --------------------------------------------------------

    aliases = pd.read_parquet(
        ALIASES,
        columns=[
            "alias_id",
            "target_lane",
            "project_work_id",
            "alias_value_norm",
        ],
    ).fillna("")

    assert aliases[
        "alias_id"
    ].is_unique

    resolved_aliases = (
        aliases.loc[
            aliases["target_lane"]
            .eq("resolved_w")
            & aliases[
                "project_work_id"
            ].ne("")
        ]
        .copy()
    )

    nworks = (
        resolved_aliases
        .groupby(
            "alias_value_norm"
        )[
            "project_work_id"
        ]
        .nunique()
    )

    alias_collision = dict(
        zip(
            aliases["alias_id"],
            aliases[
                "alias_value_norm"
            ]
            .map(nworks)
            .fillna(0)
            .astype(int),
        )
    )

    # --------------------------------------------------------
    # 5. Candidate-level aggregation + frozen rule
    # --------------------------------------------------------

    rows = []

    for (
        wid,
        oid,
    ), g in support.groupby(
        [
            "project_work_id",
            "openalex_work_id",
        ],
        sort=True,
    ):

        title_hit = bool(
            g[
                "title_match_in_title"
            ].astype(bool).any()
        )

        abstract_hit = bool(
            g[
                "title_match_in_abstract"
            ].astype(bool).any()
        )

        if title_hit and abstract_hit:
            hit_location = (
                "TITLE_AND_ABSTRACT"
            )
        elif title_hit:
            hit_location = (
                "TITLE_ONLY"
            )
        elif abstract_hit:
            hit_location = (
                "ABSTRACT_ONLY"
            )
        else:
            raise RuntimeError(
                f"No title evidence: {wid} {oid}"
            )

        token_min = int(
            g[
                "title_match_token_count"
            ].min()
        )

        token_max = int(
            g[
                "title_match_token_count"
            ].max()
        )

        alias_ids = sorted(
            set(
                g["alias_id"]
                .astype(str)
            )
        )

        collision_counts = [
            int(
                alias_collision[aid]
            )
            for aid in alias_ids
        ]

        cross_w = any(
            n > 1
            for n in collision_counts
        )

        review = (
            hit_location
            == "ABSTRACT_ONLY"
            and (
                token_min == 1
                or cross_w
            )
        )

        rows.append({
            "production_candidate_id":
                candidate_id(
                    wid,
                    oid,
                ),

            "increment_type":
                "A2_AUTHOR_REVERSAL",

            "project_work_id":
                wid,

            "openalex_work_id":
                oid,

            "provenance_evidence_row_count":
                int(len(g)),

            "provenance_query_count_release_local":
                int(
                    g[
                        "query_id"
                    ].nunique()
                ),

            "provenance_execution_count_release_local":
                int(
                    g[
                        "execution_id"
                    ].nunique()
                ),

            "provenance_alias_count":
                len(alias_ids),

            "query_id_set_release_local":
                joined(
                    g["query_id"]
                ),

            "execution_id_set_release_local":
                joined(
                    g["execution_id"]
                ),

            "alias_id_set":
                " || ".join(
                    alias_ids
                ),

            "query_title_set":
                joined(
                    g["query_title"]
                ),

            "query_author_set":
                joined(
                    g["query_author"]
                ),

            "title_match_norm_set":
                joined(
                    g[
                        "title_match_norm"
                    ]
                ),

            "author_a1_norm_set":
                joined(
                    g[
                        "author_a1_norm"
                    ]
                ),

            "author_a2_reverse_norm_set":
                joined(
                    g[
                        "author_a2_reverse_norm"
                    ]
                ),

            "title_match_token_count_min":
                token_min,

            "title_match_token_count_max":
                token_max,

            "any_title_match_in_title":
                title_hit,

            "any_title_match_in_abstract":
                abstract_hit,

            "hit_location":
                hit_location,

            "any_cross_w_title_collision":
                cross_w,

            "cross_w_collision_alias_count":
                int(
                    sum(
                        n > 1
                        for n
                        in collision_counts
                    )
                ),

            "max_distinct_project_work_count":
                int(
                    max(
                        collision_counts
                    )
                ),

            "policy_action":
                (
                    "REVIEW"
                    if review
                    else "ACCEPT"
                ),
        })

    cand = pd.DataFrame(rows)

    assert len(cand) == 963

    assert not cand[
        [
            "project_work_id",
            "openalex_work_id",
        ]
    ].duplicated().any()

    assert cand[
        "production_candidate_id"
    ].is_unique

    cand = cand.merge(
        r2_context,
        on="project_work_id",
        how="left",
        validate="many_to_one",
    )

    # --------------------------------------------------------
    # 6. Existing-evaluation provenance
    # --------------------------------------------------------

    calibration = pd.read_parquet(
        CALIBRATION,
        columns=[
            "increment_type",
            "project_work_id",
            "openalex_work_id",
        ],
    )

    calibration = (
        calibration.loc[
            calibration[
                "increment_type"
            ].eq(
                "A2_AUTHOR_REVERSAL"
            )
        ]
    )

    calibration_pairs = (
        pair_set(calibration)
    )

    heldout = pd.read_parquet(
        HELDOUT,
        columns=[
            "project_work_id",
            "openalex_work_id",
        ],
    )

    heldout_pairs = pair_set(
        heldout
    )

    assert (
        len(calibration_pairs)
        == 252
    )

    assert (
        len(heldout_pairs)
        == 248
    )

    assert not (
        calibration_pairs
        & heldout_pairs
    )

    full_pairs = pair_set(cand)

    assert not (
        calibration_pairs
        - full_pairs
    )

    assert not (
        heldout_pairs
        - full_pairs
    )

    cand[
        "evaluation_source"
    ] = [
        (
            "CALIBRATION"
            if (w, o)
            in calibration_pairs

            else "HELDOUT"
            if (w, o)
            in heldout_pairs

            else "NEW_PRODUCTION"
        )

        for w, o
        in cand[
            [
                "project_work_id",
                "openalex_work_id",
            ]
        ].itertuples(
            index=False,
            name=None,
        )
    ]

    cand[
        "requires_new_review"
    ] = (
        cand[
            "policy_action"
        ].eq("REVIEW")
        & cand[
            "evaluation_source"
        ].eq("NEW_PRODUCTION")
    )

    # --------------------------------------------------------
    # 7. Frozen expected routing counts
    # --------------------------------------------------------

    assert (
        cand[
            "project_work_id"
        ].nunique()
        == 231
    )

    assert (
        cand[
            "openalex_work_id"
        ].nunique()
        == 916
    )

    assert int(
        cand[
            "policy_action"
        ].eq("ACCEPT").sum()
    ) == 863

    assert int(
        cand[
            "policy_action"
        ].eq("REVIEW").sum()
    ) == 100

    expected = {
        (
            "CALIBRATION",
            "ACCEPT",
        ): 235,
        (
            "CALIBRATION",
            "REVIEW",
        ): 17,
        (
            "HELDOUT",
            "ACCEPT",
        ): 213,
        (
            "HELDOUT",
            "REVIEW",
        ): 35,
        (
            "NEW_PRODUCTION",
            "ACCEPT",
        ): 415,
        (
            "NEW_PRODUCTION",
            "REVIEW",
        ): 48,
    }

    actual = (
        cand.groupby(
            [
                "evaluation_source",
                "policy_action",
            ]
        )
        .size()
        .to_dict()
    )

    assert actual == expected

    review = cand.loc[
        cand[
            "policy_action"
        ].eq("REVIEW")
    ].copy()

    new_review = cand.loc[
        cand[
            "requires_new_review"
        ]
    ].copy()

    assert len(review) == 100
    assert len(new_review) == 48

    assert (
        review[
            "project_work_id"
        ].nunique()
        == 41
    )

    assert (
        new_review[
            "project_work_id"
        ].nunique()
        == 20
    )

    # --------------------------------------------------------
    # 8. Enrich REVIEW rows with OpenAlex metadata only.
    #
    # Policy itself does not use these fields.
    # --------------------------------------------------------

    oa_ids = sorted(
        set(
            review[
                "openalex_work_id"
            ]
        )
    )

    oa_dataset = ds.dataset(
        str(OA_RECORDS),
        format="parquet",
    )

    oa = oa_dataset.to_table(
        columns=[
            "openalex_work_id",
            "openalex_id_url",
            "display_name",
            "abstract",
            "publication_year",
            "publication_date",
            "type",
            "language",
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
        set(oa["openalex_work_id"])
        == set(oa_ids)
    )

    review = review.merge(
        oa,
        on="openalex_work_id",
        how="left",
        validate="many_to_one",
    )

    new_review = (
        review.loc[
            review[
                "requires_new_review"
            ]
        ]
        .copy()
    )

    # --------------------------------------------------------
    # 9. Work-level routing burden
    # --------------------------------------------------------

    by_work = (
        cand.groupby(
            "project_work_id",
            sort=True,
        )
        .agg(
            candidate_count=(
                "production_candidate_id",
                "size",
            ),

            accept_count=(
                "policy_action",
                lambda s:
                int(
                    s.eq("ACCEPT").sum()
                ),
            ),

            review_count=(
                "policy_action",
                lambda s:
                int(
                    s.eq("REVIEW").sum()
                ),
            ),

            new_production_candidate_count=(
                "evaluation_source",
                lambda s:
                int(
                    s.eq(
                        "NEW_PRODUCTION"
                    ).sum()
                ),
            ),

            new_review_count=(
                "requires_new_review",
                lambda s:
                int(s.sum()),
            ),
        )
        .reset_index()
    )

    assert len(by_work) == 231

    # --------------------------------------------------------
    # 10. Stable ordering
    # --------------------------------------------------------

    source_order = {
        "CALIBRATION": 0,
        "HELDOUT": 1,
        "NEW_PRODUCTION": 2,
    }

    cand["_source_order"] = (
        cand[
            "evaluation_source"
        ].map(source_order)
    )

    cand = (
        cand.sort_values(
            [
                "_source_order",
                "project_work_id",
                "openalex_work_id",
            ],
            kind="stable",
        )
        .drop(
            columns=[
                "_source_order"
            ]
        )
        .reset_index(drop=True)
    )

    review["_source_order"] = (
        review[
            "evaluation_source"
        ].map(source_order)
    )

    review = (
        review.sort_values(
            [
                "_source_order",
                "project_work_id",
                "openalex_work_id",
            ],
            kind="stable",
        )
        .drop(
            columns=[
                "_source_order"
            ]
        )
        .reset_index(drop=True)
    )

    new_review = (
        new_review.sort_values(
            [
                "project_work_id",
                "openalex_work_id",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # 11. Outputs
    # --------------------------------------------------------

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=False,
    )

    candidate_tsv = (
        OUT_DIR
        / "openalex_a2_production_candidates_v1.tsv"
    )

    candidate_parquet = (
        OUT_DIR
        / "openalex_a2_production_candidates_v1.parquet"
    )

    review_tsv = (
        OUT_DIR
        / "openalex_a2_production_policy_review_queue_v1.tsv"
    )

    review_parquet = (
        OUT_DIR
        / "openalex_a2_production_policy_review_queue_v1.parquet"
    )

    new_review_tsv = (
        OUT_DIR
        / "openalex_a2_production_new_review_queue_v1.tsv"
    )

    new_review_parquet = (
        OUT_DIR
        / "openalex_a2_production_new_review_queue_v1.parquet"
    )

    by_work_tsv = (
        OUT_DIR
        / "openalex_a2_production_routing_by_work_v1.tsv"
    )

    by_work_parquet = (
        OUT_DIR
        / "openalex_a2_production_routing_by_work_v1.parquet"
    )

    summary_path = (
        OUT_DIR
        / "openalex_a2_production_routing_summary_v1.json"
    )

    manifest_path = (
        OUT_DIR
        / "openalex_a2_production_routing_v1_manifest.json"
    )

    write_tsv(
        cand,
        candidate_tsv,
    )

    write_parquet(
        cand,
        candidate_parquet,
    )

    write_tsv(
        review,
        review_tsv,
    )

    write_parquet(
        review,
        review_parquet,
    )

    write_tsv(
        new_review,
        new_review_tsv,
    )

    write_parquet(
        new_review,
        new_review_parquet,
    )

    write_tsv(
        by_work,
        by_work_tsv,
    )

    write_parquet(
        by_work,
        by_work_parquet,
    )

    summary = {
        "release": RELEASE,
        "version": VERSION,
        "created_at": CREATED_AT,

        "scope": (
            "Complete resolved-W A2 marginal "
            "candidate universe under the frozen "
            "2026-09-23 OpenAlex snapshot."
        ),

        "candidate_definition": (
            "W×OpenAlex pairs in resolved-W R3+A2 "
            "minus W×OpenAlex pairs in resolved-W R3+A1."
        ),

        "frozen_policy": {
            "action_review_if": (
                "hit_location == ABSTRACT_ONLY "
                "AND "
                "(title_match_token_count_min == 1 "
                "OR any_cross_w_title_collision == True)"
            ),
            "otherwise":
                "ACCEPT",
            "reject_action":
                False,
        },

        "counts": {
            "candidate_pairs":
                963,

            "candidate_project_works":
                231,

            "unique_openalex_works":
                916,

            "accept_pairs":
                863,

            "review_pairs":
                100,

            "review_share_pairs":
                100 / 963,

            "review_project_works":
                41,

            "calibration_pairs":
                252,

            "heldout_pairs":
                248,

            "new_production_pairs":
                463,

            "new_production_accept_pairs":
                415,

            "new_production_review_pairs":
                48,

            "new_production_review_project_works":
                20,
        },

        "routing_by_evaluation_source": {
            "CALIBRATION": {
                "ACCEPT": 235,
                "REVIEW": 17,
            },
            "HELDOUT": {
                "ACCEPT": 213,
                "REVIEW": 35,
            },
            "NEW_PRODUCTION": {
                "ACCEPT": 415,
                "REVIEW": 48,
            },
        },

        "parity": {
            "calibration_a2_pairs":
                252,
            "calibration_missing_from_full":
                0,
            "heldout_a2_pairs":
                248,
            "heldout_missing_from_full":
                0,
            "status":
                "PASSED",
        },

        "interpretation": [
            (
                "The 100 REVIEW candidates are policy "
                "routing outcomes, not invalid labels."
            ),
            (
                "Only 48 REVIEW candidates across 20 "
                "project works are new production cases "
                "without prior calibration/held-out "
                "evaluation."
            ),
            (
                "The 415 NEW_PRODUCTION ACCEPT candidates "
                "are automatically accepted by the frozen "
                "rule but are not individually adjudicated "
                "by this release."
            ),
            (
                "Held-out validation performance remains "
                "separate from these production routing "
                "counts."
            ),
            (
                "This release does not establish R2 "
                "baseline precision, R4 precision, recall, "
                "coverage, Alias-expansion performance, or "
                "whole-pipeline precision."
            ),
        ],
    }

    write_json(
        summary,
        summary_path,
    )

    output_paths = [
        candidate_tsv,
        candidate_parquet,
        review_tsv,
        review_parquet,
        new_review_tsv,
        new_review_parquet,
        by_work_tsv,
        by_work_parquet,
        summary_path,
    ]

    manifest = {
        "release": RELEASE,
        "version": VERSION,
        "created_at": CREATED_AT,

        "source_scan": {
            "release":
                scan_manifest["release"],

            "snapshot_inventory_sha256":
                SNAPSHOT_SHA256,

            "processed_file_count":
                2040,

            "snapshot_rows_read":
                476196327,

            "hit_evidence_rows":
                966265050,

            "scan_manifest_sha256":
                sha256_file(
                    SCAN_MANIFEST
                ),

            "hit_evidence_sha256":
                scan_manifest[
                    "outputs"
                ][
                    "hit_evidence"
                ][
                    "sha256"
                ],
        },

        "frozen_registry_inputs": {
            str(
                MATCH_REGISTRY.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    MATCH_REGISTRY
                ),

            str(
                ALIASES.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    ALIASES
                ),

            str(
                CALIBRATION.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    CALIBRATION
                ),

            str(
                HELDOUT.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    HELDOUT
                ),
        },

        "outputs": {
            str(
                p.relative_to(ROOT)
            ):
                sha256_file(p)
            for p
            in output_paths
        },

        "counts":
            summary["counts"],

        "parity":
            summary["parity"],

        "policy_feature_semantics": {
            "candidate_identity":
                "project_work_id × openalex_work_id",

            "title_match_token_count":
                (
                    "minimum and maximum across "
                    "supporting R3+A2 query evidence"
                ),

            "hit_location":
                (
                    "deterministic any-title / "
                    "any-abstract aggregation across "
                    "supporting evidence"
                ),

            "cross_w_collision":
                (
                    "any supporting frozen alias whose "
                    "alias_value_norm occurs against "
                    "more than one resolved project work"
                ),

            "query_id":
                (
                    "release-local provenance only; "
                    "not persistent cross-release identity"
                ),
        },
    }

    write_json(
        manifest,
        manifest_path,
    )

    print(
        "=== OPENALEX A2 PRODUCTION ROUTING V1 ==="
    )

    print(
        "candidate pairs: 963"
    )

    print(
        "candidate project works: 231"
    )

    print(
        "unique OpenAlex works: 916"
    )

    print(
        "ACCEPT: 863"
    )

    print(
        "REVIEW: 100"
    )

    print(
        "review share: "
        f"{100/963:.6f}"
    )

    print(
        "new production candidates: 463"
    )

    print(
        "new production ACCEPT: 415"
    )

    print(
        "new production REVIEW: 48"
    )

    print(
        "new production REVIEW works: 20"
    )

    print(
        "calibration parity: PASSED"
    )

    print(
        "held-out parity: PASSED"
    )

    print(
        "output:",
        OUT_DIR,
    )


if __name__ == "__main__":
    main()
