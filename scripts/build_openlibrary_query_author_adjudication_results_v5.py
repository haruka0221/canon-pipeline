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
    / "openlibrary_query_author_human_review_adjudication_results_v4.tsv"
)

SOURCE_MANIFEST = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v4_manifest.json"
)

OUT = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v5.tsv"
)

OUT_MANIFEST = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v5_manifest.json"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


D = {
    "OAR0081": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Rubén Dario Sálaz",
        types="duplicate_same_person;name_variant_or_error;target_or_scope_problem",
        basis="PACKET_AND_EXTERNAL",
        refs="ABAA: I am Tecumseh! Book 1",
        note=(
            "Rubén Darío Sálaz is the author; the later Salaz-Marquez "
            "form appears to represent the same person. The book was "
            "published in 1980, so its presence is also a separate "
            "1880-1950 population/scope issue."
        ),
    ),

    "OAR0082": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Pierre Loti",
        types="straightforward;translator_editor_adapter;duplicate_same_person",
        basis="PACKET_AND_EXTERNAL",
        refs="Project Gutenberg ebook 67061",
        note=(
            "Pierre Loti is the literary author; M. B. Richards / "
            "Mary B. Richards is the translator represented twice."
        ),
    ),

    "OAR0083": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Joseph Hergesheimer",
        types="straightforward;publisher_or_production_entity",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; later edges are "
            "publisher or production entities."
        ),
    ),

    "OAR0084": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Vernon L. Kellogg",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="Project Gutenberg ebook 39248",
        note=(
            "Vernon Kellogg is the principal author. Charlotte Kellogg "
            "contributed songs and Milo Winter supplied illustrations."
        ),
    ),

    "OAR0085": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Marianne Busser",
        types="straightforward;translator_editor_adapter;target_or_scope_problem",
        basis="PACKET_AND_EXTERNAL",
        refs="Open British National Bibliography: On the road with Poppa Whopper",
        note=(
            "Marianne Busser is the author; later edges are contributors. "
            "The English edition is from 1995, so the target also raises "
            "a separate 1880-1950 population/scope issue."
        ),
    ),

    "OAR0086": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Harriet Beecher Stowe",
        types="straightforward;duplicate_same_person;name_variant_or_error",
        basis="PACKET_AND_EXTERNAL",
        refs="Project Gutenberg ebook 2486",
        note=(
            "Harriet Beecher Stowe is the author. Ordinal 1 is a "
            "name variant; the title-like ordinal 2 is not a useful "
            "author representation."
        ),
    ),

    "OAR0087": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Felix Dahn",
        types="straightforward;translator_editor_adapter;duplicate_same_person",
        basis="PACKET_AND_EXTERNAL",
        refs="Project Gutenberg ebook 32443",
        note=(
            "Felix Dahn is the author; the two Sophie Veitch edges "
            "represent the translator."
        ),
    ),

    "OAR0088": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Ramy Allison White",
        types="straightforward;translator_editor_adapter;duplicate_same_person",
        basis="PACKET_AND_EXTERNAL",
        refs="Sunny Boy with the Circus bibliographic records",
        note=(
            "Ramy Allison White is the credited series author; "
            "Howard L. Hastings is the illustrator and is duplicated "
            "in the OL edges."
        ),
    ),

    "OAR0089": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="William Somerset Maugham",
        types="anthology_collection",
        basis="PACKET_AND_EXTERNAL",
        refs="Christie's / Open Library: Tellers of Tales",
        note=(
            "Maugham selected and introduced/edited the anthology. "
            "Doyle and Chekhov are included story authors rather than "
            "additional collection-level retrieval responsibility names."
        ),
    ),

    "OAR0090": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Arthur M. Winfield",
        types="straightforward;translator_editor_adapter;publisher_or_production_entity",
        basis="PACKET_AND_EXTERNAL",
        refs="Wikisource: The Rover Boys at School",
        note=(
            "Arthur M. Winfield is the credited author name; later "
            "edges are illustration/publishing related."
        ),
    ),

    "OAR0091": dict(
        safe="YES",
        action="USE_MULTIPLE_OL_AUTHORS",
        ordinals="0;1",
        names="Kathryn Jackson;Byron Jackson",
        types="coauthor_collaborator;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="Penguin Random House / Google Books: The Saggy Baggy Elephant",
        note=(
            "Kathryn Jackson and Byron Jackson are coauthors. "
            "Gustaf Tenggren is the illustrator."
        ),
    ),

    "OAR0092": dict(
        safe="NO",
        action="USE_OTHER_ORDINAL",
        ordinals="1",
        names="Nathaniel Hawthorne",
        types="publisher_or_production_entity;name_variant_or_error",
        basis="PACKET_AND_EXTERNAL",
        refs="Open Library: The Scarlet Letter",
        note=(
            "Lake Education is not the literary author. Nathaniel "
            "Hawthorne at ordinal 1 is the appropriate retrieval author."
        ),
    ),

    "OAR0093": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Jules Verne",
        types="straightforward;translator_editor_adapter;publisher_or_production_entity",
        basis="PACKET_AND_EXTERNAL",
        refs="Online Books Page: The Giant Raft",
        note=(
            "Jules Verne is the literary author; W. J. Gordon is "
            "edition/translation related and Charles Scribner's Sons "
            "is a publisher."
        ),
    ),

    "OAR0094": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="J. J. Bell",
        types="straightforward;translator_editor_adapter;publisher_or_production_entity",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; later edges represent "
            "illustration and publishing responsibility."
        ),
    ),

    "OAR0095": dict(
        safe="YES",
        action="USE_MULTIPLE_OL_AUTHORS",
        ordinals="0;1;2",
        names="Alfred Foulet;E. C. Armstrong;Milan Sylvanus La Du",
        types="anthology_collection;coauthor_collaborator;target_or_scope_problem",
        basis="PACKET_AND_EXTERNAL",
        refs="BnF: The Medieval French Roman d'Alexandre",
        note=(
            "The record represents a multi-volume scholarly edition "
            "with different editorial responsibility across volumes. "
            "Foulet, Armstrong, and La Du are all useful retrieval "
            "responsibility names and should generate separate routes. "
            "The target is a scholarly edition rather than a fiction "
            "work, which is a separate population/scope issue."
        ),
    ),

    "OAR0096": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Francis Cowley Burnand",
        types="straightforward;translator_editor_adapter;publisher_or_production_entity",
        basis="PACKET_AND_EXTERNAL",
        refs="CiNii Books: The real adventures of Robinson Crusoe",
        note=(
            "F. C. Burnand is the author; Linley Sambourne is the "
            "illustrator and Bradbury, Agnew & Co. is the publisher."
        ),
    ),

    "OAR0097": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="A. S. Novikov-Priboĭ",
        types="duplicate_same_person;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is a usable author form; ordinal 1 is another "
            "representation of the same author and E. Paul is "
            "translation-related."
        ),
    ),

    "OAR0098": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="G. A. Henty",
        types="straightforward;translator_editor_adapter;publisher_or_production_entity",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; later edges are "
            "illustration and publisher records."
        ),
    ),

    "OAR0099": dict(
        safe="YES",
        action="USE_MULTIPLE_OL_AUTHORS",
        ordinals="0;1",
        names="John Bunyan;Samuel Joseph Reid",
        types="translator_editor_adapter;coauthor_collaborator",
        basis="PACKET_AND_EXTERNAL",
        refs="Library of Congress / Internet Archive: Young people's Pilgrim's progress",
        note=(
            "John Bunyan is the source author and Samuel Joseph Reid "
            "prepared the young readers' adaptation/exposition. "
            "George W. Truett supplied introductory material, so "
            "ordinals 0 and 1 are selected for separate retrieval routes."
        ),
    ),

    "OAR0100": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Mary Eleanor Wilkins Freeman",
        types="straightforward;publisher_or_production_entity",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; ordinal 1 is the "
            "publishing company."
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
            "Frozen adjudication results v4 SHA256 mismatch"
        )

    df = pd.read_csv(
        SOURCE,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    expected_ids = {
        f"OAR{i:04d}"
        for i in range(81, 101)
    }

    if set(D) != expected_ids:
        raise RuntimeError(
            "Batch must contain exactly OAR0081-OAR0100"
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
                f"{rid} is not PENDING in source v4"
            )

        df.loc[mask, "ordinal0_retrieval_safe"] = d["safe"]
        df.loc[mask, "recommended_query_author_action"] = d["action"]
        df.loc[mask, "preferred_author_ordinals"] = d["ordinals"]
        df.loc[mask, "preferred_author_names"] = d["names"]
        df.loc[mask, "review_case_types"] = d["types"]
        df.loc[mask, "review_note"] = d["note"]
        df.loc[mask, "review_evidence_basis"] = d["basis"]
        df.loc[mask, "review_evidence_refs"] = d["refs"]
        df.loc[mask, "reviewer"] = (
            "Haruka Tsutsui (ChatGPT-assisted review)"
        )
        df.loc[mask, "reviewed_at"] = "2026-09-29"

    reviewed = df[
        df["ordinal0_retrieval_safe"].ne("PENDING")
    ]

    pending = df[
        df["ordinal0_retrieval_safe"].eq("PENDING")
    ]

    if len(reviewed) != 100:
        raise RuntimeError(
            f"Expected 100 reviewed rows; got {len(reviewed)}"
        )

    if len(pending) != 55:
        raise RuntimeError(
            f"Expected 55 pending rows; got {len(pending)}"
        )

    df.to_csv(
        OUT,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    manifest = {
        "release":
            "openlibrary-query-author-human-adjudication-results-v5",
        "created_at":
            "2026-09-29",
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
                ["OAR0081-OAR0100"],
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
