#!/usr/bin/env python3

from pathlib import Path
import argparse
import hashlib
import json

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

PROFILE_DIR = (
    ROOT
    / "derived/openalex_production/"
      "retrieval_calibration_profile_v2/"
      "full_inventory_57959e90"
)

EVIDENCE = (
    PROFILE_DIR
    / "openalex_a12_candidate_query_evidence_v2.parquet"
)

OA_RECORDS = (
    PROFILE_DIR
    / "openalex_a12_candidate_oa_records_v2.parquet"
)

QUERIES = (
    PROFILE_DIR
    / "openalex_query_profile_counts_v2.parquet"
)

PROFILE_MANIFEST = (
    PROFILE_DIR
    / "openalex_retrieval_calibration_profile_v2_manifest.json"
)

PROFILE_AUDIT = (
    PROFILE_DIR
    / "openalex_retrieval_calibration_profile_v2_audit_v1.json"
)

EXPECTED_PROFILE_RELEASE = (
    "openalex-retrieval-calibration-profile-v2"
)

EXPECTED_INVENTORY_SHA256 = (
    "57959e90573d6ef2adb953fd747ba718"
    "54819880f762077f680083476d490fc9"
)

EXPECTED_ALIAS_INCREMENT = 409
EXPECTED_A2_INCREMENT = 268
EXPECTED_UNION = 677
EXPECTED_UNION_WORKS = 69


def sha256_file(path):
    h = hashlib.sha256()

    with Path(path).open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def pair_set(df):
    z = df[
        ["project_work_id", "openalex_work_id"]
    ].drop_duplicates()

    return set(
        map(
            tuple,
            z.itertuples(
                index=False,
                name=None,
            ),
        )
    )


def joined(values):
    vals = sorted({
        str(x)
        for x in values
        if pd.notna(x)
        and str(x) != ""
    })

    return " || ".join(vals)


def candidate_id(kind, wid, oid):
    payload = f"{kind}\t{wid}\t{oid}"

    return (
        "OAPRV2_"
        + hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()[:16]
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    for path in [
        EVIDENCE,
        OA_RECORDS,
        QUERIES,
        PROFILE_MANIFEST,
        PROFILE_AUDIT,
    ]:
        if not path.exists():
            raise FileNotFoundError(path)

    manifest = json.loads(
        PROFILE_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    audit = json.loads(
        PROFILE_AUDIT.read_text(
            encoding="utf-8"
        )
    )

    if (
        manifest["release"]
        != EXPECTED_PROFILE_RELEASE
    ):
        raise RuntimeError(
            "Unexpected profile release"
        )

    if (
        manifest["snapshot"][
            "full_inventory_sha256"
        ]
        != EXPECTED_INVENTORY_SHA256
    ):
        raise RuntimeError(
            "Unexpected snapshot inventory"
        )

    if audit["audit_status"] != "PASSED":
        raise RuntimeError(
            "Profile v2 audit has not passed"
        )

    ev = pd.read_parquet(
        EVIDENCE
    ).fillna("")

    # Keep OpenAlex metadata dtypes intact.
    # In particular, publication_year is float64 with genuine missing
    # values in the frozen profile. Replacing those missing values with
    # "" creates a mixed float/string object column that cannot be
    # serialized reliably to Parquet.
    oa = pd.read_parquet(
        OA_RECORDS
    )

    q = pd.read_parquet(
        QUERIES
    ).fillna("")

    if not q["query_id"].is_unique:
        raise RuntimeError(
            "query_id not unique"
        )

    if not oa["openalex_work_id"].is_unique:
        raise RuntimeError(
            "OpenAlex metadata IDs not unique"
        )

    # --------------------------------------------------------
    # Resolved-W evidence only.
    # --------------------------------------------------------

    x = ev.loc[
        ev["target_lane"].eq("resolved_w")
        & ev["project_work_id"].ne("")
    ].copy()

    r2_a2 = pair_set(
        x.loc[
            x["query_route"].eq("R2")
            & x["author_a2_hit"].eq(True)
        ]
    )

    r3_a1 = pair_set(
        x.loc[
            x["query_route"].eq("R3")
            & x["author_a1_hit"].eq(True)
        ]
    )

    r3_a2 = pair_set(
        x.loc[
            x["query_route"].eq("R3")
            & x["author_a2_hit"].eq(True)
        ]
    )

    alias_increment = (
        r3_a2 - r2_a2
    )

    a2_increment = (
        r3_a2 - r3_a1
    )

    overlap = (
        alias_increment
        & a2_increment
    )

    union = (
        alias_increment
        | a2_increment
    )

    if len(alias_increment) != EXPECTED_ALIAS_INCREMENT:
        raise RuntimeError(
            f"Expected {EXPECTED_ALIAS_INCREMENT} "
            f"alias-increment pairs; "
            f"found {len(alias_increment)}"
        )

    if len(a2_increment) != EXPECTED_A2_INCREMENT:
        raise RuntimeError(
            f"Expected {EXPECTED_A2_INCREMENT} "
            f"A2-increment pairs; "
            f"found {len(a2_increment)}"
        )

    if overlap:
        raise RuntimeError(
            f"Expected zero intersection; "
            f"found {len(overlap)}"
        )

    if len(union) != EXPECTED_UNION:
        raise RuntimeError(
            f"Expected {EXPECTED_UNION} union pairs; "
            f"found {len(union)}"
        )

    if (
        len({w for w, _ in union})
        != EXPECTED_UNION_WORKS
    ):
        raise RuntimeError(
            "Unexpected union W count"
        )

    # --------------------------------------------------------
    # Query metadata.
    # --------------------------------------------------------

    qcols = [
        "query_id",
        "query_title",
        "query_author",
        "title_match_norm",
        "title_match_token_count",
        "author_a1_norm",
        "author_a2_reverse_norm",
    ]

    qmeta = q[qcols].copy()

    r3ev = x.loc[
        x["query_route"].eq("R3")
        & x["author_a2_hit"].eq(True)
    ].merge(
        qmeta,
        on="query_id",
        how="left",
        validate="many_to_one",
    )

    union_df = pd.DataFrame(
        sorted(
            union,
            key=lambda z: (
                z[0],
                z[1],
            ),
        ),
        columns=[
            "project_work_id",
            "openalex_work_id",
        ],
    )

    union_df["increment_type"] = [
        (
            "ALIAS_EXPANSION"
            if (w, o) in alias_increment
            else "A2_AUTHOR_REVERSAL"
        )
        for w, o
        in union_df[
            [
                "project_work_id",
                "openalex_work_id",
            ]
        ].itertuples(
            index=False,
            name=None,
        )
    ]

    union_df["review_candidate_id"] = [
        candidate_id(kind, wid, oid)
        for kind, wid, oid
        in union_df[
            [
                "increment_type",
                "project_work_id",
                "openalex_work_id",
            ]
        ].itertuples(
            index=False,
            name=None,
        )
    ]

    # --------------------------------------------------------
    # Candidate-level retrieval provenance.
    # --------------------------------------------------------

    provenance_rows = []

    for (wid, oid), g in r3ev.groupby(
        [
            "project_work_id",
            "openalex_work_id",
        ],
        sort=True,
    ):
        if (wid, oid) not in union:
            continue

        provenance_rows.append({
            "project_work_id":
                wid,
            "openalex_work_id":
                oid,

            "r3_evidence_rows":
                len(g),

            "r3_query_ids":
                joined(g["query_id"]),

            "r3_execution_ids":
                joined(g["execution_id"]),

            "r3_alias_ids":
                joined(g["alias_id"]),

            "r3_query_titles":
                joined(g["query_title"]),

            "r3_query_authors":
                joined(g["query_author"]),

            "title_match_norms":
                joined(g["title_match_norm"]),

            "author_a1_norms":
                joined(g["author_a1_norm"]),

            "author_a2_reverse_norms":
                joined(
                    g["author_a2_reverse_norm"]
                ),

            "any_title_match_in_title":
                bool(
                    g[
                        "title_match_in_title"
                    ].any()
                ),

            "any_title_match_in_abstract":
                bool(
                    g[
                        "title_match_in_abstract"
                    ].any()
                ),

            "any_author_a1_hit":
                bool(
                    g[
                        "author_a1_hit"
                    ].any()
                ),

            "any_author_a2_reverse_hit":
                bool(
                    g[
                        "author_a2_reverse_hit"
                    ].any()
                ),
        })

    prov = pd.DataFrame(
        provenance_rows
    )

    out = union_df.merge(
        prov,
        on=[
            "project_work_id",
            "openalex_work_id",
        ],
        how="left",
        validate="one_to_one",
    )

    # --------------------------------------------------------
    # R2 baseline query context for each W.
    # --------------------------------------------------------

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

    out = out.merge(
        r2_context,
        on="project_work_id",
        how="left",
        validate="many_to_one",
    )

    # --------------------------------------------------------
    # OpenAlex metadata.
    # --------------------------------------------------------

    oa_cols = [
        c
        for c in [
            "openalex_work_id",
            "openalex_id_url",
            "snapshot_source_file",
            "display_name",
            "abstract",
            "publication_year",
            "publication_date",
            "type",
            "language",
            "doi",
            "is_retracted",
            "is_paratext",
            "has_fulltext",
            "primary_topic_id",
            "primary_topic_name",
        ]
        if c in oa.columns
    ]

    out = out.merge(
        oa[oa_cols],
        on="openalex_work_id",
        how="left",
        validate="many_to_one",
    )

    if out["display_name"].eq("").all():
        raise RuntimeError(
            "OA metadata merge failed"
        )

    if len(out) != EXPECTED_UNION:
        raise RuntimeError(
            "Unexpected output row count"
        )

    if out[
        [
            "project_work_id",
            "openalex_work_id",
        ]
    ].duplicated().any():
        raise RuntimeError(
            "Duplicate W × OA pair"
        )

    # Stable output order.
    order = {
        "ALIAS_EXPANSION": 0,
        "A2_AUTHOR_REVERSAL": 1,
    }

    out["_kind_order"] = (
        out["increment_type"]
        .map(order)
    )

    out = (
        out.sort_values(
            [
                "_kind_order",
                "project_work_id",
                "openalex_work_id",
            ],
            kind="mergesort",
        )
        .drop(
            columns=["_kind_order"]
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Write immutable review universe.
    # --------------------------------------------------------

    output_dir = args.output_dir

    if output_dir.exists():
        raise RuntimeError(
            f"Output directory exists: "
            f"{output_dir}"
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    tsv = (
        output_dir
        / "openalex_retrieval_precision_review_candidates_v2.tsv"
    )

    parquet = (
        output_dir
        / "openalex_retrieval_precision_review_candidates_v2.parquet"
    )

    manifest_out = (
        output_dir
        / "openalex_retrieval_precision_review_candidates_v2_manifest.json"
    )

    out.to_csv(
        tsv,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    out.to_parquet(
        parquet,
        index=False,
    )

    summary = {
        "release":
            "openalex-retrieval-precision-review-candidates-v2",

        "basis":
            "complete OpenAlex retrieval-calibration profile v2",

        "definition": {
            "alias_increment":
                "resolved-W W×OpenAlex pairs in R3+A2 but not R2+A2",
            "a2_increment":
                "resolved-W W×OpenAlex pairs in R3+A2 but not R3+A1",
            "review_union":
                "union of alias_increment and a2_increment",
        },

        "counts": {
            "alias_increment_pairs":
                len(alias_increment),
            "alias_increment_works":
                len({
                    w
                    for w, _
                    in alias_increment
                }),
            "a2_increment_pairs":
                len(a2_increment),
            "a2_increment_works":
                len({
                    w
                    for w, _
                    in a2_increment
                }),
            "intersection_pairs":
                len(overlap),
            "union_pairs":
                len(union),
            "union_works":
                len({
                    w
                    for w, _
                    in union
                }),
        },

        "source_profile": {
            "release":
                manifest["release"],
            "snapshot_inventory_sha256":
                manifest["snapshot"][
                    "full_inventory_sha256"
                ],
            "profile_manifest_sha256":
                sha256_file(
                    PROFILE_MANIFEST
                ),
            "profile_audit_sha256":
                sha256_file(
                    PROFILE_AUDIT
                ),
        },

        "inputs": {
            EVIDENCE.name:
                sha256_file(EVIDENCE),
            OA_RECORDS.name:
                sha256_file(OA_RECORDS),
            QUERIES.name:
                sha256_file(QUERIES),
        },

        "outputs": {
            tsv.name:
                sha256_file(tsv),
            parquet.name:
                sha256_file(parquet),
        },

        "interpretation":
            (
                "This release freezes the candidate universe "
                "for precision review. It contains no human or "
                "LLM relevance judgments and does not freeze "
                "the production retrieval policy."
            ),
    }

    manifest_out.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "=== PRECISION REVIEW CANDIDATES V2 ==="
    )
    print(
        "alias increment:",
        len(alias_increment),
        "/",
        len({
            w for w, _
            in alias_increment
        }),
        "W",
    )
    print(
        "A2 increment:",
        len(a2_increment),
        "/",
        len({
            w for w, _
            in a2_increment
        }),
        "W",
    )
    print(
        "intersection:",
        len(overlap),
    )
    print(
        "union:",
        len(out),
        "/",
        out["project_work_id"].nunique(),
        "W",
    )
    print()
    print("TSV:", tsv)
    print("Parquet:", parquet)
    print("Manifest:", manifest_out)


if __name__ == "__main__":
    main()
