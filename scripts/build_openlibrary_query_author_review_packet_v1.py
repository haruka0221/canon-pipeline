#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

AUDIT_DIR = (
    ROOT
    / "derived/openlibrary_query_author_audit_v1"
)

INPUT = (
    AUDIT_DIR
    / "openlibrary_multi_author_audit_v1.tsv"
)

AUDIT_MANIFEST = (
    AUDIT_DIR
    / "openlibrary_query_author_audit_v1_manifest.json"
)

OUT_DIR = (
    ROOT
    / "derived/openlibrary_query_author_review_v1"
)

OUT = (
    OUT_DIR
    / "openlibrary_query_author_human_review_v1.tsv"
)

MANIFEST = (
    OUT_DIR
    / "openlibrary_query_author_human_review_v1_manifest.json"
)

SEED = 20260928

TARGET_N = {
    "MULTI_BASELINE": 50,
    "MULTI_LOW": 50,
    "MULTI_MEDIUM": 50,
    "MULTI_HIGH": None,  # all
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(block)

    return h.hexdigest()


def clean_cell(value):
    if pd.isna(value):
        return ""

    if isinstance(value, str):
        return value.rstrip()

    return value


def main() -> None:
    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    audit_manifest = json.loads(
        AUDIT_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    expected_sha = (
        audit_manifest["outputs"]
        ["multi_author_audit"]
        ["sha256"]
    )

    actual_sha = sha256_file(INPUT)

    if actual_sha != expected_sha:
        raise RuntimeError(
            "Frozen audit input SHA256 mismatch"
        )

    df = pd.read_csv(
        INPUT,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    parts = []

    for bucket, n in TARGET_N.items():
        x = df[
            df["review_bucket"].eq(bucket)
        ].copy()

        if n is None:
            sample = x
        else:
            sample = x.sample(
                n=min(n, len(x)),
                random_state=SEED,
            )

        parts.append(sample)

    review = pd.concat(
        parts,
        ignore_index=True,
    )

    bucket_order = {
        "MULTI_HIGH": 0,
        "MULTI_MEDIUM": 1,
        "MULTI_LOW": 2,
        "MULTI_BASELINE": 3,
    }

    review["_bucket_order"] = (
        review["review_bucket"]
        .map(bucket_order)
    )

    review = (
        review.sort_values(
            [
                "_bucket_order",
                "author_entry_count",
                "source_title",
                "current_ol_work_id",
            ],
            ascending=[
                True,
                False,
                True,
                True,
            ],
            kind="stable",
        )
        .drop(
            columns=["_bucket_order"]
        )
        .reset_index(drop=True)
    )

    # Remove source-derived trailing spaces from the
    # review presentation only. Frozen audit v1 is unchanged.
    for col in review.columns:
        review[col] = review[col].map(
            clean_cell
        )

    review.insert(
        0,
        "review_id",
        [
            f"OAR{i:04d}"
            for i in range(
                1,
                len(review) + 1,
            )
        ],
    )

    review["ordinal0_retrieval_safe"] = ""
    review["preferred_author_ordinal"] = ""
    review["preferred_author_name"] = ""
    review["review_case_type"] = ""
    review["review_note"] = ""
    review["reviewer"] = ""
    review["reviewed_at"] = ""

    keep = [
        "review_id",
        "review_bucket",
        "current_entity_id",
        "current_ol_work_id",
        "source_title",
        "author_entry_count",
        "review_reasons",
        "ordinal0_author_id",
        "ordinal0_name",
        "all_author_ids",
        "all_author_names",
        "ordinal0_retrieval_safe",
        "preferred_author_ordinal",
        "preferred_author_name",
        "review_case_type",
        "review_note",
        "reviewer",
        "reviewed_at",
    ]

    review = review[keep]

    review.to_csv(
        OUT,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    counts = (
        review["review_bucket"]
        .value_counts()
        .to_dict()
    )

    manifest = {
        "release":
            "openlibrary-query-author-human-review-v1",
        "created_at":
            "2026-09-28",
        "purpose": (
            "Stratified manual review of multi-author "
            "Open Library targets before freezing "
            "query_author_selection_rule v1."
        ),
        "review_question": (
            "Is Open Library author ordinal 0 safe to use "
            "as the retrieval author in an OpenAlex "
            "title+author query for this target?"
        ),
        "input": {
            "artifact":
                str(INPUT.relative_to(ROOT)),
            "sha256":
                actual_sha,
            "source_release":
                audit_manifest["release"],
        },
        "sampling": {
            "seed": SEED,
            "MULTI_BASELINE": 50,
            "MULTI_LOW": 50,
            "MULTI_MEDIUM": 50,
            "MULTI_HIGH": "all",
        },
        "review_values": {
            "ordinal0_retrieval_safe": [
                "YES",
                "NO",
                "UNCLEAR",
            ],
            "review_case_type": [
                "straightforward",
                "duplicate_same_person",
                "translator_editor_adapter",
                "coauthor_collaborator",
                "anthology_collection",
                "organization_or_publisher",
                "missing_author_record",
                "target_or_scope_problem",
                "other",
            ],
        },
        "counts": {
            "rows": len(review),
            "by_bucket": counts,
        },
        "output": {
            "artifact":
                str(OUT.relative_to(ROOT)),
            "sha256":
                sha256_file(OUT),
        },
    }

    MANIFEST.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print("rows:", len(review))

    print(
        review["review_bucket"]
        .value_counts()
        .to_string()
    )

    print()
    print(OUT.relative_to(ROOT))
    print(MANIFEST.relative_to(ROOT))


if __name__ == "__main__":
    main()
