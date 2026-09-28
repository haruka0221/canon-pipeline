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
    / "openlibrary_query_author_human_review_adjudication_results_v2.tsv"
)

SOURCE_MANIFEST = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v2_manifest.json"
)

OUT = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v3.tsv"
)

OUT_MANIFEST = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v3_manifest.json"
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
    "OAR0041": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Edward Gaitens",
        types="straightforward;duplicate_same_person",
        basis="PACKET_AND_EXTERNAL",
        refs="Google Books: Dance of the Apprentices",
        note=(
            "Edward Gaitens is the work author; both OL edges "
            "represent the same person."
        ),
    ),

    "OAR0042": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="H. Rider Haggard",
        types="straightforward;duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note="Both OL edges are duplicate representations of the author.",
    ),

    "OAR0043": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Elizabeth Bowen",
        types="straightforward;duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note="Both OL edges are duplicate representations of the author.",
    ),

    "OAR0044": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="C. S. Forester",
        types="duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is a clean author representation; "
            "ordinal 1 is a spacing variant."
        ),
    ),

    "OAR0045": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Hans Peterson",
        types="straightforward;duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note="Both OL edges are duplicate representations of the author.",
    ),

    "OAR0046": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Willa Cather",
        types="straightforward;duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note="Both OL edges are duplicate representations of the author.",
    ),

    "OAR0047": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Wyndham Lewis",
        types="straightforward;duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note="Both OL edges are duplicate representations of the author.",
    ),

    "OAR0048": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="George Gissing",
        types="straightforward;duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note="Both OL edges are duplicate representations of the author.",
    ),

    "OAR0049": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="C. Alphonso Smith",
        types="straightforward;duplicate_same_person;target_or_scope_problem",
        basis="PACKET_AND_EXTERNAL",
        refs="The American Short Story by C. Alphonso Smith",
        note=(
            "C. Alphonso Smith is the author and both OL edges "
            "represent the same person. The target appears to be "
            "literary history/criticism rather than fiction, which "
            "is a separate scope issue."
        ),
    ),

    "OAR0050": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="André Salmon",
        types="duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "The two OL edges are orthographic/Unicode variants "
            "of the same author."
        ),
    ),

    "OAR0051": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Patrick Kavanagh",
        types="straightforward;duplicate_same_person;target_or_scope_problem",
        basis="PACKET_AND_EXTERNAL",
        refs="Penguin: The Great Hunger by Patrick Kavanagh",
        note=(
            "Patrick Kavanagh is the author and both OL edges "
            "represent the same person. The target is poetry rather "
            "than fiction, which is a separate scope issue."
        ),
    ),

    "OAR0052": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Grautoff, Christiane",
        types="straightforward;duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note="Both OL edges are duplicate representations of the author.",
    ),

    "OAR0053": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Tom Koch",
        types="straightforward;duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note="Both OL edges are duplicate representations of the author.",
    ),

    "OAR0054": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="O. Henry",
        types="straightforward;duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note="Both OL edges are duplicate representations of the author.",
    ),

    "OAR0055": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Edward J. O'Brien",
        types="anthology_collection",
        basis="PACKET_AND_EXTERNAL",
        refs="Project Gutenberg ebook 20303",
        note=(
            "Edward J. O'Brien is the editor of the anthology; "
            "later OL edges are included story authors."
        ),
    ),

    "OAR0056": dict(
        safe="YES",
        action="USE_MULTIPLE_OL_AUTHORS",
        ordinals="0;1",
        names="Margaretta Morris;Louise Buffum Congdon",
        types="anthology_collection;coauthor_collaborator",
        basis="PACKET_AND_EXTERNAL",
        refs="Project Gutenberg ebook 43482",
        note=(
            "Margaretta Morris and Louise Buffum Congdon are "
            "the co-editors of the collection. Both are useful "
            "retrieval responsibility names."
        ),
    ),

    "OAR0057": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Lizzie Lawson",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs=(
            "AbeBooks/Kessinger: A Day's Pleasure for Little People; "
            "Online Books Page"
        ),
        note=(
            "Modern bibliographic records identify Lizzie Lawson "
            "as author and Miriam Kerns and Charlotte Weeks as "
            "illustrators. Some older cataloging describes all "
            "named contributors as illustrators, but Lizzie Lawson "
            "remains a useful retrieval disambiguator."
        ),
    ),

    "OAR0058": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Margaret Oliphant",
        types="straightforward;publisher_or_production_entity",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; later edges are "
            "publisher/printer records."
        ),
    ),

    "OAR0059": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Katherine Mansfield",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; later edges are "
            "edition-related scholarly contributors."
        ),
    ),

    "OAR0060": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Susan Coolidge",
        types="straightforward;publisher_or_production_entity",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; later edges are "
            "publisher/printer records."
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
            "Frozen adjudication results v2 SHA256 mismatch"
        )

    df = pd.read_csv(
        SOURCE,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    expected_ids = {
        f"OAR{i:04d}"
        for i in range(41, 61)
    }

    if set(D) != expected_ids:
        raise RuntimeError(
            "Batch must contain exactly OAR0041-OAR0060"
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
                f"{rid} is not PENDING in source v2"
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

    if len(reviewed) != 60:
        raise RuntimeError(
            f"Expected 60 reviewed rows; got {len(reviewed)}"
        )

    if len(pending) != 95:
        raise RuntimeError(
            f"Expected 95 pending rows; got {len(pending)}"
        )

    df.to_csv(
        OUT,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    manifest = {
        "release":
            "openlibrary-query-author-human-adjudication-results-v3",
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
                ["OAR0041-OAR0060"],
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
