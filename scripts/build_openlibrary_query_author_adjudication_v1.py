#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

REVIEW_DIR = (
    ROOT
    / "derived/openlibrary_query_author_review_v1"
)

REVIEW_PACKET = (
    REVIEW_DIR
    / "openlibrary_query_author_human_review_v1.tsv"
)

REVIEW_MANIFEST = (
    REVIEW_DIR
    / "openlibrary_query_author_human_review_v1_manifest.json"
)

OUT = (
    REVIEW_DIR
    / "openlibrary_query_author_human_review_adjudication_v1.tsv"
)

MANIFEST = (
    REVIEW_DIR
    / "openlibrary_query_author_human_review_adjudication_v1_manifest.json"
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


def main() -> None:
    source_manifest = json.loads(
        REVIEW_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    expected_sha = (
        source_manifest["output"]["sha256"]
    )

    actual_sha = sha256_file(
        REVIEW_PACKET
    )

    if actual_sha != expected_sha:
        raise RuntimeError(
            "Frozen review packet SHA256 mismatch"
        )

    review = pd.read_csv(
        REVIEW_PACKET,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    if review["review_id"].duplicated().any():
        raise RuntimeError(
            "Duplicate review_id in review packet"
        )

    adjudication = pd.DataFrame({
        "review_id":
            review["review_id"],
        "ordinal0_retrieval_safe":
            "PENDING",
        "recommended_query_author_action":
            "PENDING",
        "preferred_author_ordinals":
            "PENDING",
        "preferred_author_names":
            "PENDING",
        "review_case_types":
            "PENDING",
        "review_note":
            "PENDING",
        "review_evidence_basis":
            "PENDING",
        "review_evidence_refs":
            "PENDING",
        "reviewer":
            "PENDING",
        "reviewed_at":
            "PENDING",
    })

    adjudication.to_csv(
        OUT,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    manifest = {
        "release":
            "openlibrary-query-author-human-adjudication-v1",
        "created_at":
            "2026-09-28",
        "source_review_packet": {
            "artifact":
                str(REVIEW_PACKET.relative_to(ROOT)),
            "sha256":
                actual_sha,
            "rows":
                len(review),
        },
        "semantics": {
            "ordinal0_retrieval_safe": [
                "YES",
                "NO",
                "UNCLEAR",
                "PENDING",
            ],
            "recommended_query_author_action": [
                "USE_ORDINAL0",
                "USE_OTHER_ORDINAL",
                "USE_MULTIPLE_OL_AUTHORS",
                "NO_OL_AUTHOR",
                "UNCLEAR",
                "PENDING",
            ],
            "preferred_author_ordinals":
                "Semicolon-separated OL author ordinals, NONE, UNCLEAR, or PENDING.",
            "preferred_author_names":
                "Human-readable corresponding author names, NONE, UNCLEAR, or PENDING.",
            "review_case_types": {
                "format":
                    "Semicolon-separated one or more values.",
                "allowed_values": [
                    "straightforward",
                    "duplicate_same_person",
                    "name_variant_or_error",
                    "translator_editor_adapter",
                    "coauthor_collaborator",
                    "anthology_collection",
                    "corporate_or_institutional_author",
                    "publisher_or_production_entity",
                    "missing_author_record",
                    "target_or_scope_problem",
                    "other",
                    "PENDING",
                ],
            },
            "review_evidence_basis": [
                "PACKET_ONLY",
                "EXTERNAL_BIBLIOGRAPHIC",
                "PACKET_AND_EXTERNAL",
                "PENDING",
            ],
            "review_evidence_refs":
                "Identifiers, URLs, or short source labels supporting the adjudication, or PENDING.",
            "important_note": (
                "The review asks whether an Open Library "
                "author value is safe and useful as an "
                "OpenAlex retrieval disambiguator. It does "
                "not attempt to establish definitive "
                "literary authorship."
            ),
        },
        "output": {
            "artifact":
                str(OUT.relative_to(ROOT)),
            "rows":
                len(adjudication),
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

    print("rows:", len(adjudication))
    print(
        adjudication[
            "ordinal0_retrieval_safe"
        ].value_counts().to_string()
    )
    print()
    print(OUT.relative_to(ROOT))
    print(MANIFEST.relative_to(ROOT))


if __name__ == "__main__":
    main()
