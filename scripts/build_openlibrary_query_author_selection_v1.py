#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

AUDIT_DIR = ROOT / "derived/openlibrary_query_author_audit_v1"
AUTHOR_DIR = ROOT / "derived/openlibrary_author_source_v1"
REVIEW_DIR = ROOT / "derived/openlibrary_query_author_review_v1"

AUDIT = (
    AUDIT_DIR
    / "openlibrary_query_author_status_v1.tsv"
)

AUDIT_MANIFEST = (
    AUDIT_DIR
    / "openlibrary_query_author_audit_v1_manifest.json"
)

WORK_AUTHORS = (
    AUTHOR_DIR
    / "openlibrary_current_work_authors_v1.parquet"
)

AUTHOR_RECORDS = (
    AUTHOR_DIR
    / "openlibrary_author_records_v1.parquet"
)

AUTHOR_SOURCE_MANIFEST = (
    AUTHOR_DIR
    / "openlibrary_author_source_v1_manifest.json"
)

REVIEW_PACKET = (
    REVIEW_DIR
    / "openlibrary_query_author_human_review_v1.tsv"
)

REVIEW_PACKET_MANIFEST = (
    REVIEW_DIR
    / "openlibrary_query_author_human_review_v1_manifest.json"
)

REVIEW_RESULTS = (
    REVIEW_DIR
    / "openlibrary_query_author_human_review_adjudication_results_v8.tsv"
)

REVIEW_RESULTS_MANIFEST = (
    REVIEW_DIR
    / "openlibrary_query_author_human_review_adjudication_results_v8_manifest.json"
)

OUT_DIR = (
    ROOT
    / "derived/openlibrary_query_author_selection_v1"
)

OUT_TSV = (
    OUT_DIR
    / "openlibrary_query_author_selection_v1.tsv"
)

OUT_PARQUET = (
    OUT_DIR
    / "openlibrary_query_author_selection_v1.parquet"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openlibrary_query_author_selection_v1_manifest.json"
)

RELEASE = "openlibrary-query-author-selection-v1"
CREATED_AT = "2026-09-29"

RULE = "openlibrary_query_author_selection_rule"
RULE_VERSION = "v1"

ADDITIONAL_USAGE = (
    "CALIBRATION_EVIDENCE_NOT_AUTOMATIC_PRODUCTION_ROUTE"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(block)

    return h.hexdigest()


def verify_sha(
    path: Path,
    expected_sha: str,
) -> str:
    actual = sha256_file(path)

    if actual != expected_sha:
        raise RuntimeError(
            f"SHA256 mismatch for {path}: "
            f"{actual} != {expected_sha}"
        )

    return actual


def split_ordinals(value: str) -> list[int]:
    value = str(value or "").strip()

    if not value or value in {
        "NONE",
        "PENDING",
        "UNCLEAR",
    }:
        return []

    return [
        int(x)
        for x in value.split(";")
        if x != ""
    ]


def main() -> None:
    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ---------------------------------------------------------
    # Verify frozen inputs
    # ---------------------------------------------------------

    audit_manifest = json.loads(
        AUDIT_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    author_manifest = json.loads(
        AUTHOR_SOURCE_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    packet_manifest = json.loads(
        REVIEW_PACKET_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    results_manifest = json.loads(
        REVIEW_RESULTS_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    if (
        audit_manifest["release"]
        != "openlibrary-query-author-audit-v1"
    ):
        raise RuntimeError(
            "Unexpected audit release"
        )

    if (
        author_manifest["release"]
        != "openlibrary-author-source-v1"
    ):
        raise RuntimeError(
            "Unexpected author-source release"
        )

    if (
        packet_manifest["release"]
        != "openlibrary-query-author-human-review-v1"
    ):
        raise RuntimeError(
            "Unexpected review-packet release"
        )

    if (
        results_manifest["release"]
        != "openlibrary-query-author-human-adjudication-results-v8"
    ):
        raise RuntimeError(
            "Unexpected adjudication release"
        )

    input_hashes = {}

    input_hashes[
        str(AUDIT.relative_to(ROOT))
    ] = verify_sha(
        AUDIT,
        audit_manifest[
            "outputs"
        ][
            "all_work_status"
        ][
            "sha256"
        ],
    )

    input_hashes[
        str(WORK_AUTHORS.relative_to(ROOT))
    ] = verify_sha(
        WORK_AUTHORS,
        author_manifest[
            "outputs"
        ][
            "work_authors_parquet"
        ][
            "sha256"
        ],
    )

    input_hashes[
        str(AUTHOR_RECORDS.relative_to(ROOT))
    ] = verify_sha(
        AUTHOR_RECORDS,
        author_manifest[
            "outputs"
        ][
            "author_records_parquet"
        ][
            "sha256"
        ],
    )

    input_hashes[
        str(REVIEW_PACKET.relative_to(ROOT))
    ] = verify_sha(
        REVIEW_PACKET,
        packet_manifest[
            "output"
        ][
            "sha256"
        ],
    )

    input_hashes[
        str(REVIEW_RESULTS.relative_to(ROOT))
    ] = verify_sha(
        REVIEW_RESULTS,
        results_manifest[
            "output"
        ][
            "sha256"
        ],
    )

    # ---------------------------------------------------------
    # Load frozen source layers
    # ---------------------------------------------------------

    audit = pd.read_csv(
        AUDIT,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    edges = pd.read_parquet(
        WORK_AUTHORS
    )

    authors = pd.read_parquet(
        AUTHOR_RECORDS
    )

    packet = pd.read_csv(
        REVIEW_PACKET,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    results = pd.read_csv(
        REVIEW_RESULTS,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    if len(audit) != 34789:
        raise RuntimeError(
            f"Expected 34789 audit rows; "
            f"found {len(audit)}"
        )

    if not audit[
        "current_ol_work_id"
    ].is_unique:
        raise RuntimeError(
            "Audit current_ol_work_id is not unique"
        )

    # ---------------------------------------------------------
    # Attach Author.name to Work -> Author edges
    # ---------------------------------------------------------

    edges["author_ordinal"] = (
        pd.to_numeric(
            edges["author_ordinal"],
            errors="raise",
        )
        .astype(int)
    )

    author_meta = authors[
        [
            "author_source_key",
            "author_source_id",
            "author_source_snapshot",
            "author_source_artifact",
            "name",
        ]
    ].copy()

    author_meta = author_meta.rename(
        columns={
            "name": "author_name",
        }
    )

    edges = edges.merge(
        author_meta,
        on=[
            "author_source_key",
            "author_source_id",
        ],
        how="left",
        validate="m:1",
    )

    for col in [
        "author_source_key",
        "author_source_id",
        "author_name",
        "author_source_snapshot",
        "author_source_artifact",
        "author_role_key",
    ]:
        if col not in edges.columns:
            edges[col] = ""

        edges[col] = (
            edges[col]
            .fillna("")
            .astype(str)
        )

    if edges.duplicated(
        [
            "current_ol_work_id",
            "author_ordinal",
        ]
    ).any():
        bad = edges.loc[
            edges.duplicated(
                [
                    "current_ol_work_id",
                    "author_ordinal",
                ],
                keep=False,
            ),
            [
                "current_ol_work_id",
                "author_ordinal",
            ],
        ]

        raise RuntimeError(
            "Duplicate Work/author ordinal edges:\n"
            + bad.to_string(index=False)
        )

    edge_lookup = {
        (
            str(row.current_ol_work_id),
            int(row.author_ordinal),
        ): row
        for row in edges.itertuples(
            index=False
        )
    }

    # ---------------------------------------------------------
    # Human-review lookup
    # ---------------------------------------------------------

    review = packet[
        [
            "review_id",
            "current_ol_work_id",
            "review_bucket",
        ]
    ].merge(
        results,
        on="review_id",
        how="inner",
        validate="1:1",
    )

    if len(review) != 155:
        raise RuntimeError(
            f"Expected 155 reviewed rows; "
            f"found {len(review)}"
        )

    if not review[
        "current_ol_work_id"
    ].is_unique:
        raise RuntimeError(
            "Reviewed current_ol_work_id is not unique"
        )

    if (
        review[
            "ordinal0_retrieval_safe"
        ]
        .eq("PENDING")
        .any()
    ):
        raise RuntimeError(
            "Human review still contains PENDING"
        )

    review_map = (
        review
        .set_index(
            "current_ol_work_id"
        )
        .to_dict("index")
    )

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    def get_source_author(
        work_id: str,
        ordinal: int,
    ):
        key = (
            work_id,
            int(ordinal),
        )

        if key not in edge_lookup:
            raise RuntimeError(
                f"Missing author edge: {key}"
            )

        edge = edge_lookup[key]

        if not edge.author_source_key:
            raise RuntimeError(
                f"Selected author has no source key: "
                f"{key}"
            )

        if not edge.author_source_id:
            raise RuntimeError(
                f"Selected author has no source ID: "
                f"{key}"
            )

        if not edge.author_name:
            raise RuntimeError(
                f"Selected author has no Author.name: "
                f"{key}"
            )

        return edge

    # ---------------------------------------------------------
    # Apply selection rule
    # ---------------------------------------------------------

    out_rows = []

    for row in audit.to_dict("records"):
        work_id = str(
            row["current_ol_work_id"]
        )

        complexity = str(
            row["selection_complexity"]
        )

        bucket = str(
            row["review_bucket"]
        )

        human = review_map.get(
            work_id
        )

        primary_action = ""
        primary_ordinal = None
        selection_basis = ""

        human_review_id = ""
        human_safe = ""
        human_action = ""
        human_case_types = ""

        additional_ordinals: list[int] = []

        if complexity == "NO_AUTHOR_ENTRY":
            primary_action = "NO_OL_AUTHOR"
            selection_basis = (
                "NO_AUTHOR_ENTRY"
            )

        elif complexity == "SINGLE_UNRESOLVED":
            primary_action = "NO_OL_AUTHOR"
            selection_basis = (
                "SINGLE_UNRESOLVED"
            )

        elif complexity == "SINGLE_RESOLVED":
            primary_action = "USE_ORDINAL0"
            primary_ordinal = 0
            selection_basis = (
                "AUTO_SINGLE_RESOLVED"
            )

        elif complexity == "MULTI":
            if human is not None:
                human_review_id = str(
                    human["review_id"]
                )

                human_safe = str(
                    human[
                        "ordinal0_retrieval_safe"
                    ]
                )

                human_action = str(
                    human[
                        "recommended_query_author_action"
                    ]
                )

                human_case_types = str(
                    human[
                        "review_case_types"
                    ]
                )

                preferred = split_ordinals(
                    human[
                        "preferred_author_ordinals"
                    ]
                )

                if human_action in {
                    "USE_ORDINAL0",
                    "USE_MULTIPLE_OL_AUTHORS",
                }:
                    if human_safe != "YES":
                        raise RuntimeError(
                            f"Inconsistent human YES action: "
                            f"{human_review_id}"
                        )

                    primary_action = (
                        "USE_ORDINAL0"
                    )

                    primary_ordinal = 0

                    selection_basis = (
                        "HUMAN_REVIEW_CONFIRMED_ORDINAL0"
                    )

                    if (
                        human_action
                        == "USE_MULTIPLE_OL_AUTHORS"
                    ):
                        if 0 not in preferred:
                            raise RuntimeError(
                                f"Multiple-author review "
                                f"does not include ordinal 0: "
                                f"{human_review_id}"
                            )

                        additional_ordinals = [
                            x
                            for x in preferred
                            if x != 0
                        ]

                elif (
                    human_action
                    == "USE_OTHER_ORDINAL"
                ):
                    if human_safe != "NO":
                        raise RuntimeError(
                            f"Inconsistent human override: "
                            f"{human_review_id}"
                        )

                    if not preferred:
                        raise RuntimeError(
                            f"No replacement ordinal: "
                            f"{human_review_id}"
                        )

                    if 0 in preferred:
                        raise RuntimeError(
                            f"Replacement includes ordinal 0: "
                            f"{human_review_id}"
                        )

                    primary_action = (
                        "USE_OTHER_ORDINAL"
                    )

                    primary_ordinal = preferred[0]

                    selection_basis = (
                        "HUMAN_REVIEW_OVERRIDE"
                    )

                    additional_ordinals = (
                        preferred[1:]
                    )

                elif (
                    human_action
                    == "NO_OL_AUTHOR"
                ):
                    if human_safe != "NO":
                        raise RuntimeError(
                            f"Inconsistent human no-author: "
                            f"{human_review_id}"
                        )

                    if preferred:
                        raise RuntimeError(
                            f"NO_OL_AUTHOR has ordinals: "
                            f"{human_review_id}"
                        )

                    primary_action = (
                        "NO_OL_AUTHOR"
                    )

                    selection_basis = (
                        "HUMAN_REVIEW_NO_OL_AUTHOR"
                    )

                else:
                    raise RuntimeError(
                        (
                            human_review_id,
                            human_action,
                        )
                    )

            else:
                # Every MULTI_HIGH case was reviewed.
                if bucket not in {
                    "MULTI_BASELINE",
                    "MULTI_LOW",
                    "MULTI_MEDIUM",
                }:
                    raise RuntimeError(
                        (
                            work_id,
                            bucket,
                        )
                    )

                primary_action = (
                    "USE_ORDINAL0"
                )

                primary_ordinal = 0

                selection_basis = (
                    "AUTO_MULTI_ORDINAL0_CALIBRATED"
                )

        else:
            raise RuntimeError(
                (
                    work_id,
                    complexity,
                )
            )

        # -----------------------------------------------------
        # Primary source-native author provenance
        # -----------------------------------------------------

        primary_edge = None

        if primary_ordinal is not None:
            primary_edge = get_source_author(
                work_id,
                primary_ordinal,
            )

        # -----------------------------------------------------
        # Reviewed additional-author evidence
        # -----------------------------------------------------

        additional_edges = [
            get_source_author(
                work_id,
                ordinal,
            )
            for ordinal
            in additional_ordinals
        ]

        out_rows.append({
            "current_entity_id":
                row["current_entity_id"],
            "current_ol_work_id":
                work_id,
            "source_title":
                row["source_title"],

            "selection_complexity":
                complexity,
            "review_bucket":
                bucket,

            "primary_action":
                primary_action,

            "query_author_selected":
                primary_edge is not None,

            "query_author_ordinal":
                (
                    str(primary_ordinal)
                    if primary_ordinal
                    is not None
                    else ""
                ),

            "query_author_source_key":
                (
                    primary_edge.author_source_key
                    if primary_edge is not None
                    else ""
                ),

            "query_author_source_id":
                (
                    primary_edge.author_source_id
                    if primary_edge is not None
                    else ""
                ),

            "query_author_name_type":
                (
                    "name"
                    if primary_edge is not None
                    else ""
                ),

            "query_author_name":
                (
                    primary_edge.author_name
                    if primary_edge is not None
                    else ""
                ),

            "query_author_role_key":
                (
                    primary_edge.author_role_key
                    if primary_edge is not None
                    else ""
                ),

            "query_author_source_snapshot":
                (
                    primary_edge.author_source_snapshot
                    if primary_edge is not None
                    else ""
                ),

            "query_author_source_artifact":
                (
                    primary_edge.author_source_artifact
                    if primary_edge is not None
                    else ""
                ),

            "selection_basis":
                selection_basis,

            "query_author_selection_rule":
                RULE,

            "query_author_selection_version":
                RULE_VERSION,

            "human_review_id":
                human_review_id,

            "human_ordinal0_retrieval_safe":
                human_safe,

            "human_review_action":
                human_action,

            "human_review_case_types":
                human_case_types,

            "reviewed_additional_author_count":
                len(additional_edges),

            "reviewed_additional_author_ordinals":
                ";".join(
                    str(x)
                    for x in additional_ordinals
                ),

            "reviewed_additional_author_source_ids":
                ";".join(
                    x.author_source_id
                    for x in additional_edges
                ),

            "reviewed_additional_author_names":
                ";".join(
                    x.author_name
                    for x in additional_edges
                ),

            "reviewed_additional_author_usage":
                (
                    ADDITIONAL_USAGE
                    if additional_edges
                    else ""
                ),
        })

    out = pd.DataFrame(
        out_rows
    )

    # ---------------------------------------------------------
    # Release validation
    # ---------------------------------------------------------

    if len(out) != 34789:
        raise RuntimeError(
            f"Expected 34789 output rows; "
            f"found {len(out)}"
        )

    if not out[
        "current_ol_work_id"
    ].is_unique:
        raise RuntimeError(
            "Output current_ol_work_id is not unique"
        )

    expected_primary_actions = {
        "USE_ORDINAL0": 34424,
        "NO_OL_AUTHOR": 361,
        "USE_OTHER_ORDINAL": 4,
    }

    actual_primary_actions = (
        out[
            "primary_action"
        ]
        .value_counts()
        .to_dict()
    )

    if (
        actual_primary_actions
        != expected_primary_actions
    ):
        raise RuntimeError(
            "Unexpected primary-action counts: "
            f"{actual_primary_actions}"
        )

    expected_basis = {
        "AUTO_SINGLE_RESOLVED": 32704,
        "AUTO_MULTI_ORDINAL0_CALIBRATED": 1575,
        "NO_AUTHOR_ENTRY": 354,
        "HUMAN_REVIEW_CONFIRMED_ORDINAL0": 145,
        "HUMAN_REVIEW_NO_OL_AUTHOR": 6,
        "HUMAN_REVIEW_OVERRIDE": 4,
        "SINGLE_UNRESOLVED": 1,
    }

    actual_basis = (
        out[
            "selection_basis"
        ]
        .value_counts()
        .to_dict()
    )

    if actual_basis != expected_basis:
        raise RuntimeError(
            "Unexpected selection-basis counts: "
            f"{actual_basis}"
        )

    selected = out[
        out["query_author_selected"]
    ]

    unselected = out[
        ~out["query_author_selected"]
    ]

    if len(selected) != 34428:
        raise RuntimeError(
            f"Expected 34428 selected primary authors; "
            f"found {len(selected)}"
        )

    if len(unselected) != 361:
        raise RuntimeError(
            f"Expected 361 no-author rows; "
            f"found {len(unselected)}"
        )

    for col in [
        "query_author_source_key",
        "query_author_source_id",
        "query_author_name",
        "query_author_source_snapshot",
        "query_author_source_artifact",
    ]:
        if not selected[col].str.strip().ne("").all():
            raise RuntimeError(
                f"Selected primary author missing {col}"
            )

    if (
        unselected[
            "query_author_name"
        ]
        .str.strip()
        .ne("")
        .any()
    ):
        raise RuntimeError(
            "NO_OL_AUTHOR row has query_author_name"
        )

    additional = out[
        out[
            "reviewed_additional_author_count"
        ]
        .astype(int)
        .gt(0)
    ]

    if len(additional) != 22:
        raise RuntimeError(
            f"Expected 22 targets with reviewed "
            f"additional-author evidence; "
            f"found {len(additional)}"
        )

    additional_edge_count = int(
        out[
            "reviewed_additional_author_count"
        ]
        .astype(int)
        .sum()
    )

    if additional_edge_count != 25:
        raise RuntimeError(
            f"Expected 25 reviewed additional "
            f"author edges; found "
            f"{additional_edge_count}"
        )

    calibrated = out[
        out[
            "selection_basis"
        ]
        .eq(
            "AUTO_MULTI_ORDINAL0_CALIBRATED"
        )
    ]

    calibrated_bucket_counts = (
        calibrated[
            "review_bucket"
        ]
        .value_counts()
        .to_dict()
    )

    expected_calibrated_buckets = {
        "MULTI_BASELINE": 969,
        "MULTI_LOW": 384,
        "MULTI_MEDIUM": 222,
    }

    if (
        calibrated_bucket_counts
        != expected_calibrated_buckets
    ):
        raise RuntimeError(
            "Unexpected calibrated bucket counts: "
            f"{calibrated_bucket_counts}"
        )

    # ---------------------------------------------------------
    # Write release
    # ---------------------------------------------------------

    out.to_csv(
        OUT_TSV,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    out.to_parquet(
        OUT_PARQUET,
        index=False,
    )

    counts = {
        "rows":
            len(out),

        "query_author_selected":
            len(selected),

        "no_query_author_selected":
            len(unselected),

        "primary_action":
            actual_primary_actions,

        "selection_basis":
            actual_basis,

        "calibrated_multi_by_bucket":
            calibrated_bucket_counts,

        "human_reviewed_targets":
            int(
                out[
                    "human_review_id"
                ]
                .ne("")
                .sum()
            ),

        "reviewed_additional_author_targets":
            len(additional),

        "reviewed_additional_author_edges":
            additional_edge_count,
    }

    manifest = {
        "release":
            RELEASE,

        "created_at":
            CREATED_AT,

        "purpose": (
            "Freeze the first project-wide "
            "Open Library-derived primary query-author "
            "selection rule for OpenAlex retrieval."
        ),

        "semantics": {
            "query_author": (
                "Derived retrieval value for OpenAlex "
                "query disambiguation; not definitive "
                "literary-historical authorship."
            ),

            "primary_r2_policy": (
                "One primary Open Library-derived "
                "query author per eligible target."
            ),

            "reviewed_additional_author_policy": (
                "Additional author names observed in "
                "the stratified human-review sample "
                "are retained as calibration evidence "
                "only and are not automatically enabled "
                "as production query routes."
            ),

            "unreviewed_multi_policy": (
                "For unreviewed MULTI_BASELINE, "
                "MULTI_LOW, and MULTI_MEDIUM targets, "
                "ordinal 0 is used as a calibrated "
                "default. All MULTI_HIGH targets were "
                "human reviewed."
            ),

            "author_name_policy": (
                "The selected raw query-author string "
                "is Open Library Author.name from the "
                "frozen 2026-02-28 author source layer. "
                "personal_name, fuller_name, and "
                "alternate_names are not substituted "
                "in selection v1."
            ),
        },

        "query_author_selection_rule":
            RULE,

        "query_author_selection_version":
            RULE_VERSION,

        "source_releases": {
            "author_source":
                author_manifest["release"],
            "query_author_audit":
                audit_manifest["release"],
            "human_review_packet":
                packet_manifest["release"],
            "human_adjudication":
                results_manifest["release"],
        },

        "input_sha256":
            input_hashes,

        "counts":
            counts,

        "outputs": {
            "tsv": {
                "artifact":
                    str(
                        OUT_TSV.relative_to(
                            ROOT
                        )
                    ),
                "sha256":
                    sha256_file(
                        OUT_TSV
                    ),
            },

            "parquet": {
                "artifact":
                    str(
                        OUT_PARQUET.relative_to(
                            ROOT
                        )
                    ),
                "sha256":
                    sha256_file(
                        OUT_PARQUET
                    ),
            },
        },
    }

    OUT_MANIFEST.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    # ---------------------------------------------------------
    # Console summary
    # ---------------------------------------------------------

    print("=== PRIMARY ACTION ===")
    print(
        out[
            "primary_action"
        ]
        .value_counts()
        .to_string()
    )

    print("\n=== SELECTION BASIS ===")
    print(
        out[
            "selection_basis"
        ]
        .value_counts()
        .to_string()
    )

    print(
        "\n=== CALIBRATED MULTI "
        "DEFAULTS BY BUCKET ==="
    )
    print(
        calibrated[
            "review_bucket"
        ]
        .value_counts()
        .to_string()
    )

    print(
        "\n=== REVIEWED ADDITIONAL "
        "AUTHOR EVIDENCE ==="
    )
    print(
        "targets:",
        len(additional),
    )
    print(
        "author edges:",
        additional_edge_count,
    )

    print(
        "\n=== OUTPUTS ==="
    )
    print(
        OUT_TSV.relative_to(
            ROOT
        )
    )
    print(
        OUT_PARQUET.relative_to(
            ROOT
        )
    )
    print(
        OUT_MANIFEST.relative_to(
            ROOT
        )
    )

    print(
        "\nOpen Library query-author "
        "selection v1 build checks passed."
    )


if __name__ == "__main__":
    main()
