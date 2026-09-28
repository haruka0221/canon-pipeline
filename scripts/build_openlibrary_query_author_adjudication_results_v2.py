#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

DIR = ROOT / "derived/openlibrary_query_author_review_v1"

SOURCE = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v1.tsv"
)

SOURCE_MANIFEST = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v1_manifest.json"
)

REVIEW_PACKET = (
    DIR
    / "openlibrary_query_author_human_review_v1.tsv"
)

OUT = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v2.tsv"
)

OUT_MANIFEST = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v2_manifest.json"
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


D = {
    "OAR0021": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Alice Waite",
        types="anthology_collection;duplicate_same_person",
        basis="PACKET_AND_EXTERNAL",
        refs="Google Books/CiNii: Modern Masterpieces of Short Prose Fiction",
        note=(
            "Alice Vinton Waite is a co-editor of the anthology; "
            "ordinal 1 is a fuller duplicate representation."
        ),
    ),

    "OAR0022": dict(
        safe="NO",
        action="NO_OL_AUTHOR",
        ordinals="NONE",
        names="NONE",
        types="other",
        basis="PACKET_AND_EXTERNAL",
        refs="University of London Press / Seized Books: Teleny",
        note=(
            "The work was published anonymously and is regarded as "
            "collaboratively authored; Oscar Wilde's degree of "
            "involvement remains disputed. No single OL author string "
            "is selected for retrieval."
        ),
    ),

    "OAR0023": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Eleanor Estes",
        types="straightforward;duplicate_same_person;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; later edges include "
            "duplicate and edition/contributor records."
        ),
    ),

    "OAR0024": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Molesworth Mrs",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="Project Gutenberg ebook 43126",
        note=(
            "Mrs. Molesworth is the author and Walter Crane is the "
            "illustrator. Ordinal 0 is retrieval-safe."
        ),
    ),

    "OAR0025": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="William Dean Howells",
        types="anthology_collection",
        basis="PACKET_AND_EXTERNAL",
        refs="Google Books: The Great Modern American Stories",
        note=(
            "Howells is the editor/compiler of the anthology; the "
            "remaining OL edges represent included authors."
        ),
    ),

    "OAR0026": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Charles Dickens",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; later edges are "
            "edition-related contributors or organizations."
        ),
    ),

    "OAR0027": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Thomas Head Raddall",
        types="duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the cleanest usable author representation; "
            "later edges are duplicate or abbreviated forms."
        ),
    ),

    "OAR0028": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Oscar Wilde",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author represented by this "
            "collection; later Hesketh Pearson records are "
            "edition-related."
        ),
    ),

    "OAR0029": dict(
        safe="YES",
        action="USE_MULTIPLE_OL_AUTHORS",
        ordinals="0;1",
        names="William Dean Howells;Henry Mills Alden",
        types="anthology_collection;coauthor_collaborator;duplicate_same_person",
        basis="PACKET_AND_EXTERNAL",
        refs="Project Gutenberg ebook 9509",
        note=(
            "Howells and Alden are co-editors of the collection; "
            "later Alden records are duplicates."
        ),
    ),

    "OAR0030": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Sher ʻAlī Jaʻfarī Afsos",
        types="duplicate_same_person;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="Wikimedia Commons IA Araish-i mahfil; Google Books",
        note=(
            "Sher Ali Afsos is the author; Henry Court is the "
            "translator. Ordinal 1 is a variant representation of "
            "the same author."
        ),
    ),

    "OAR0031": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Caroline Singer",
        types="straightforward;duplicate_same_person;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="University of Chicago Library: Cyrus Leroy Baldridge Papers",
        note=(
            "Caroline Singer wrote the work; Cyrus Baldridge supplied "
            "the illustrations. Ordinal 1 duplicates Singer."
        ),
    ),

    "OAR0032": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="C. S. Forester",
        types="duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "All available edges are variants of C. S. Forester; "
            "ordinal 0 is a clean usable representation."
        ),
    ),

    "OAR0033": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Samuel Hopkins Adams",
        types="straightforward;duplicate_same_person;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="Project Gutenberg ebook 44328",
        note=(
            "Samuel Hopkins Adams is the author; Scott Williams is "
            "the illustrator. Ordinal 1 duplicates Adams."
        ),
    ),

    "OAR0034": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Samuel Hopkins Adams",
        types="duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is a clean author representation; later "
            "edges are duplicate/malformed forms of the same person."
        ),
    ),

    "OAR0035": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Jeff Smith",
        types="duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the clean usable author representation; "
            "later edges are abbreviated or duplicate forms."
        ),
    ),

    "OAR0036": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Edward J. O'Brien",
        types="anthology_collection",
        basis="PACKET_AND_EXTERNAL",
        refs="JSTOR/Open Library: The Best Short Stories of 1933",
        note=(
            "Edward J. O'Brien is the editor of the anthology; "
            "the numerous later edges are included story authors."
        ),
    ),

    "OAR0037": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Virginia Church",
        types="anthology_collection",
        basis="PACKET_AND_EXTERNAL",
        refs="WorldCat/NYPL: International short stories (1934)",
        note=(
            "Virginia Church is the editor of the anthology; later "
            "edges are contributors and translators."
        ),
    ),

    "OAR0038": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Walker, Hugh",
        types="anthology_collection;coauthor_collaborator",
        basis="PACKET_AND_EXTERNAL",
        refs="Selected English Short Stories (nineteenth century), 1920",
        note=(
            "Hugh Walker has legitimate editorial responsibility for "
            "the collection; H. S. Milford also shared responsibility "
            "but is not represented in the available OL author edges."
        ),
    ),

    "OAR0039": dict(
        safe="YES",
        action="USE_MULTIPLE_OL_AUTHORS",
        ordinals="0;2",
        names="Barrett Harper Clark;Maxim Lieber",
        types="anthology_collection;coauthor_collaborator;duplicate_same_person",
        basis="PACKET_AND_EXTERNAL",
        refs="Google Books/WorldCat: Great Short Stories of the World",
        note=(
            "Clark and Lieber are the anthology's compiler/editor "
            "pair; ordinal 1 is a duplicate/variant Clark record."
        ),
    ),

    "OAR0040": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Horace Townsend",
        types="straightforward;duplicate_same_person",
        basis="PACKET_AND_EXTERNAL",
        refs="Google Books: A Handful of Silver",
        note=(
            "Horace Townsend is the work author and both OL edges "
            "represent the same person."
        ),
    ),
}


def main() -> None:
    source_manifest = json.loads(
        SOURCE_MANIFEST.read_text(encoding="utf-8")
    )

    expected_sha = source_manifest["output"]["sha256"]
    actual_sha = sha256_file(SOURCE)

    if actual_sha != expected_sha:
        raise RuntimeError(
            "Frozen adjudication results v1 SHA256 mismatch"
        )

    df = pd.read_csv(
        SOURCE,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    expected_ids = {
        f"OAR{i:04d}"
        for i in range(21, 41)
    }

    if set(D) != expected_ids:
        raise RuntimeError(
            "Batch must contain exactly OAR0021-OAR0040"
        )

    for rid, d in D.items():
        mask = df["review_id"].eq(rid)

        if int(mask.sum()) != 1:
            raise RuntimeError(
                f"Expected exactly one row for {rid}"
            )

        if (
            df.loc[
                mask,
                "ordinal0_retrieval_safe",
            ].iloc[0]
            != "PENDING"
        ):
            raise RuntimeError(
                f"{rid} is not PENDING in source v1"
            )

        df.loc[mask, "ordinal0_retrieval_safe"] = d["safe"]
        df.loc[
            mask,
            "recommended_query_author_action",
        ] = d["action"]
        df.loc[
            mask,
            "preferred_author_ordinals",
        ] = d["ordinals"]
        df.loc[
            mask,
            "preferred_author_names",
        ] = d["names"]
        df.loc[
            mask,
            "review_case_types",
        ] = d["types"]
        df.loc[
            mask,
            "review_note",
        ] = d["note"]
        df.loc[
            mask,
            "review_evidence_basis",
        ] = d["basis"]
        df.loc[
            mask,
            "review_evidence_refs",
        ] = d["refs"]
        df.loc[
            mask,
            "reviewer",
        ] = "Haruka Tsutsui (ChatGPT-assisted review)"
        df.loc[
            mask,
            "reviewed_at",
        ] = "2026-09-28"

    reviewed = df[
        df["ordinal0_retrieval_safe"].ne("PENDING")
    ]

    pending = df[
        df["ordinal0_retrieval_safe"].eq("PENDING")
    ]

    if len(reviewed) != 40:
        raise RuntimeError(
            f"Expected 40 reviewed rows; got {len(reviewed)}"
        )

    if len(pending) != 115:
        raise RuntimeError(
            f"Expected 115 pending rows; got {len(pending)}"
        )

    df.to_csv(
        OUT,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    manifest = {
        "release":
            "openlibrary-query-author-human-adjudication-results-v2",
        "created_at":
            "2026-09-28",
        "source_results": {
            "artifact":
                str(SOURCE.relative_to(ROOT)),
            "sha256":
                actual_sha,
            "release":
                source_manifest["release"],
        },
        "added_review_batch": {
            "review_ids":
                ["OAR0021-OAR0040"],
            "rows":
                20,
            "method":
                "manual bibliographic review with ChatGPT assistance",
        },
        "counts": {
            "rows":
                len(df),
            "reviewed":
                len(reviewed),
            "pending":
                len(pending),
            "ordinal0_retrieval_safe":
                dict(
                    Counter(
                        df["ordinal0_retrieval_safe"]
                    )
                ),
            "recommended_query_author_action":
                dict(
                    Counter(
                        df[
                            "recommended_query_author_action"
                        ]
                    )
                ),
        },
        "output": {
            "artifact":
                str(OUT.relative_to(ROOT)),
            "sha256":
                sha256_file(OUT),
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

    print("rows:", len(df))
    print()
    print(
        df["ordinal0_retrieval_safe"]
        .value_counts()
        .to_string()
    )

    print()
    print(
        df["recommended_query_author_action"]
        .value_counts()
        .to_string()
    )

    print()
    print(OUT.relative_to(ROOT))
    print(OUT_MANIFEST.relative_to(ROOT))


if __name__ == "__main__":
    main()
