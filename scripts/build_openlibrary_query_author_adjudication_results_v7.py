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
    / "openlibrary_query_author_human_review_adjudication_results_v6.tsv"
)

SOURCE_MANIFEST = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v6_manifest.json"
)

OUT = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v7.tsv"
)

OUT_MANIFEST = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v7_manifest.json"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


D = {
    "OAR0121": dict(
        safe="YES",
        action="USE_MULTIPLE_OL_AUTHORS",
        ordinals="0;1",
        names="Richard Lockridge;Frances Louise Davis Lockridge",
        types="coauthor_collaborator",
        basis="PACKET_AND_EXTERNAL",
        refs="Google Books / Goodreads: I Want to Go Home",
        note=(
            "I Want to Go Home is coauthored by Richard and Frances "
            "Lockridge. Both available OL names are retained as "
            "separate retrieval routes."
        ),
    ),

    "OAR0122": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Lucy Maud Montgomery",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author. The later OL edge does "
            "not displace Montgomery as the appropriate retrieval author."
        ),
    ),

    "OAR0123": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Juan Valera y Alcalá-Galiano",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; Robert M. Fedorchek is "
            "edition/translation-related."
        ),
    ),

    "OAR0124": dict(
        safe="YES",
        action="USE_MULTIPLE_OL_AUTHORS",
        ordinals="0;1",
        names="Gina Mayer;Mercer Mayer",
        types="coauthor_collaborator;target_or_scope_problem",
        basis="PACKET_AND_EXTERNAL",
        refs=(
            "TeachingBooks / Goodreads / Mercer Mayer bibliography: "
            "Just Like Dad"
        ),
        note=(
            "The 1993 Just Like Dad is credited to Gina Mayer and "
            "Mercer Mayer, so both names are useful retrieval routes. "
            "Its 1993 publication date is a separate 1880-1950 "
            "population/scope issue."
        ),
    ),

    "OAR0125": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Rudyard Kipling",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; Joseph M. Gleeson is "
            "illustration-related."
        ),
    ),

    "OAR0126": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Restif de La Bretonne",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; Gilbert Rouger is "
            "edition/editorial-related."
        ),
    ),

    "OAR0127": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Octave Mirbeau",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; Brian Stableford is "
            "translation/edition-related."
        ),
    ),

    "OAR0128": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Valerie Tripp",
        types="straightforward;translator_editor_adapter;target_or_scope_problem",
        basis="PACKET_AND_EXTERNAL",
        refs="Google Books / TeachingBooks: Meet Molly",
        note=(
            "Valerie Tripp is the literary author. Katherine Kellgren "
            "is an audiobook narrator rather than a coauthor. Meet Molly "
            "was published in 1986, which is a separate 1880-1950 "
            "population/scope issue."
        ),
    ),

    "OAR0129": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Wilhelmina Harper",
        types="anthology_collection;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 provides the collection-level literary/editorial "
            "responsibility name; the later contributor is not selected "
            "as an additional retrieval author."
        ),
    ),

    "OAR0130": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Carolyn Sherwin Bailey",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="bibliographic records: Miss Hickory",
        note=(
            "Carolyn Sherwin Bailey is the author; Ruth Chrisman "
            "Gannett is the illustrator."
        ),
    ),

    "OAR0131": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Henryk Sienkiewicz",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; Jeremiah Curtin is "
            "translation-related."
        ),
    ),

    "OAR0132": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Nevil Shute",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="Libraries SA: Pied Piper / Nevil Shute; introduction by John Boyne",
        note=(
            "Nevil Shute is the literary author. John Boyne supplied "
            "an introduction to a later edition and is not selected "
            "as an additional work-level retrieval author."
        ),
    ),

    "OAR0133": dict(
        safe="YES",
        action="USE_MULTIPLE_OL_AUTHORS",
        ordinals="0;1",
        names=(
            "G. D. H. (George Douglas Howard) Cole;"
            "Margaret Cole"
        ),
        types="coauthor_collaborator",
        basis="PACKET_AND_EXTERNAL",
        refs="Open Library / bibliographies of G. D. H. and Margaret Cole",
        note=(
            "Poison in the Garden Suburb is coauthored by G. D. H. "
            "Cole and Margaret Cole. Both available OL names are "
            "retained as separate retrieval routes."
        ),
    ),

    "OAR0134": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Vercors",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="Morgan Library / Cambridge University Library: Put Out the Light",
        note=(
            "Vercors is the literary author. Cyril Connolly translated "
            "Le silence de la mer into English as Put Out the Light."
        ),
    ),

    "OAR0135": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Herman Melville",
        types="anthology_collection;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="CiNii / WorldCat: Selected Tales and Poems",
        note=(
            "The texts are by Herman Melville; Richard Chase edited "
            "the selection and supplied an introduction. Melville alone "
            "is retained as the work-level retrieval author."
        ),
    ),

    "OAR0136": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Patricia Highsmith",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="Google Books: Strangers on a Train, Pearson English Readers",
        note=(
            "Patricia Highsmith is the literary author. Michael Nation "
            "is associated with the later simplified/adapted reader "
            "edition and is not selected as an additional work-level "
            "retrieval author."
        ),
    ),

    "OAR0137": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Denis Mackail",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; the later OL contributor "
            "is not selected as an additional work-level retrieval author."
        ),
    ),

    "OAR0138": dict(
        safe="YES",
        action="USE_MULTIPLE_OL_AUTHORS",
        ordinals="0;1",
        names="Sidney Lanier;Thomas Malory",
        types="translator_editor_adapter;coauthor_collaborator",
        basis="PACKET_AND_EXTERNAL",
        refs="Project Gutenberg / Google Books: The Boy's King Arthur",
        note=(
            "The Boy's King Arthur is Sidney Lanier's edited/abridged "
            "version of Thomas Malory's Le Morte d'Arthur. Lanier is "
            "central to the target-specific adaptation while Malory is "
            "the source author; both names may support distinct "
            "retrieval routes."
        ),
    ),

    "OAR0139": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Dexter J. Forrester",
        types="duplicate_same_person;name_variant_or_error",
        basis="PACKET_AND_EXTERNAL",
        refs="Science Fiction Encyclopedia / Project Gutenberg",
        note=(
            "Dexter J. Forrester is a pseudonym used by John Henry "
            "Goldfrap for the Bungalow Boys series. The two OL edges "
            "represent the same writer; the publication-specific "
            "pseudonym at ordinal 0 is retained."
        ),
    ),

    "OAR0140": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="James Hanley",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="James Hanley bibliography / ABA catalogue: The German Prisoner",
        note=(
            "James Hanley is the literary author. Richard Aldington "
            "supplied the introduction and is not selected as an "
            "additional work-level retrieval author."
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
            "Frozen adjudication results v6 SHA256 mismatch"
        )

    df = pd.read_csv(
        SOURCE,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    expected_ids = {
        f"OAR{i:04d}"
        for i in range(121, 141)
    }

    if set(D) != expected_ids:
        raise RuntimeError(
            "Batch must contain exactly OAR0121-OAR0140"
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
                f"{rid} is not PENDING in source v6"
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

    if len(reviewed) != 140:
        raise RuntimeError(
            f"Expected 140 reviewed rows; got {len(reviewed)}"
        )

    if len(pending) != 15:
        raise RuntimeError(
            f"Expected 15 pending rows; got {len(pending)}"
        )

    df.to_csv(
        OUT,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    manifest = {
        "release":
            "openlibrary-query-author-human-adjudication-results-v7",
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
                ["OAR0121-OAR0140"],
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
