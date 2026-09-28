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
    / "openlibrary_query_author_human_review_adjudication_results_v3.tsv"
)

SOURCE_MANIFEST = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v3_manifest.json"
)

OUT = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v4.tsv"
)

OUT_MANIFEST = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v4_manifest.json"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


D = {
    "OAR0061": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="André Maurois",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; later edges are "
            "edition- or translation-related contributors."
        ),
    ),

    "OAR0062": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Molesworth Mrs",
        types="straightforward;translator_editor_adapter;publisher_or_production_entity",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; Walter Crane is an "
            "illustrator and later edges are publisher/printer records."
        ),
    ),

    "OAR0063": dict(
        safe="YES",
        action="USE_MULTIPLE_OL_AUTHORS",
        ordinals="0;1;2;3",
        names="Arthur Conan Doyle;J. M. Barrie;William Gillette;Arthur Whitaker",
        types="anthology_collection;coauthor_collaborator",
        basis="PACKET_AND_EXTERNAL",
        refs="Open Library: Sherlock Holmes, The Published Apocrypha",
        note=(
            "The target is a collection of Sherlock Holmes apocrypha "
            "containing material by all four credited writers. "
            "Separate retrieval routes may therefore use each name."
        ),
    ),

    "OAR0064": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Helen Marion Burnside",
        types="anthology_collection;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="Online Books Page: The Arabian Nights, 1892/1898",
        note=(
            "Helen Marion Burnside is credited as editor; Will and "
            "Frances Brundage and J. Willis Grey are illustrators."
        ),
    ),

    "OAR0065": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="George Chetwynd Griffith",
        types="straightforward;duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the cleanest full author representation; "
            "later Griffith edges are variants/duplicates."
        ),
    ),

    "OAR0066": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="W. H. D. Rouse",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is a usable literary responsibility name; "
            "later edges are illustration or edition-related records."
        ),
    ),

    "OAR0067": dict(
        safe="NO",
        action="NO_OL_AUTHOR",
        ordinals="NONE",
        names="NONE",
        types="translator_editor_adapter;target_or_scope_problem",
        basis="PACKET_AND_EXTERNAL",
        refs="Grand Comics Database; DC Database: Wonder Woman Through the Years",
        note=(
            "The available OL edges correspond to cover-art credits "
            "rather than the collection's writers. No available OL "
            "author edge is selected. The 2020 collection also raises "
            "a separate target/scope issue."
        ),
    ),

    "OAR0068": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Лев Толстой",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is Tolstoy, the literary author; later edges "
            "are translation/edition contributors."
        ),
    ),

    "OAR0069": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Russell Blankenship",
        types="straightforward;target_or_scope_problem",
        basis="PACKET_AND_EXTERNAL",
        refs="Routledge: American Literature as an Expression of the National Mind",
        note=(
            "Russell Blankenship is the author and is retrieval-safe. "
            "The target is literary history rather than fiction, which "
            "is a separate scope issue."
        ),
    ),

    "OAR0070": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Anna Sewell",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; later edges are "
            "edition/institutional contributors."
        ),
    ),

    "OAR0071": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Sholem Aleichem",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; later edges are "
            "translation/edition contributors."
        ),
    ),

    "OAR0072": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Edward Bulwer Lytton, Baron Lytton",
        types="duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "All three OL edges are variants of Edward Bulwer-Lytton; "
            "ordinal 0 is retrieval-safe."
        ),
    ),

    "OAR0073": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Slobodkina, Esphyr",
        types="straightforward;duplicate_same_person;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is a usable author form; ordinal 1 is another "
            "form of the same author and ordinal 2 is edition-related."
        ),
    ),

    "OAR0074": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Elizabeth Foreman Lewis",
        types="straightforward;duplicate_same_person;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the clean author form; ordinal 1 is a fuller "
            "duplicate and Kurt Wiese is an illustration contributor."
        ),
    ),

    "OAR0075": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Izumo Takeda",
        types="coauthor_collaborator;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs=(
            "Kabuki21: Kanadehon Chushingura; "
            "University of Virginia Japanese Text Initiative; "
            "Waseda University Library"
        ),
        note=(
            "Takeda Izumo is a genuine author of Kanadehon Chushingura. "
            "Authoritative sources identify the other original authors "
            "as Miyoshi Shoraku and Namiki Senryu, not the later OL "
            "Monzaemon Chikamatsu edge. F. Victor Dickins is associated "
            "with an English translation. Therefore only ordinal 0 is "
            "selected from the available OL edges."
        ),
    ),

    "OAR0076": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Olive Higgins Prouty",
        types="straightforward;publisher_or_production_entity",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; later edges are "
            "publisher/printer records."
        ),
    ),

    "OAR0077": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Elizabeth Cleghorn Gaskell",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; later edges are "
            "illustration/edition contributors."
        ),
    ),

    "OAR0078": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Максим Горький",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; later edges are "
            "translation or edition-related contributors."
        ),
    ),

    "OAR0079": dict(
        safe="YES",
        action="USE_MULTIPLE_OL_AUTHORS",
        ordinals="0;2",
        names="Nordhoff, Charles;James N. Hall",
        types="coauthor_collaborator;duplicate_same_person",
        basis="PACKET_AND_EXTERNAL",
        refs="Australian War Memorial; Google Books: Falcons of France",
        note=(
            "Falcons of France is co-authored by Charles Nordhoff "
            "and James Norman Hall. Ordinal 1 duplicates Nordhoff; "
            "ordinals 0 and 2 are selected."
        ),
    ),

    "OAR0080": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Jonathan Swift",
        types="straightforward;translator_editor_adapter;publisher_or_production_entity",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; Rex Whistler is an "
            "illustration contributor and Cresset Press is a publisher."
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
            "Frozen adjudication results v3 SHA256 mismatch"
        )

    df = pd.read_csv(
        SOURCE,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    expected_ids = {
        f"OAR{i:04d}"
        for i in range(61, 81)
    }

    if set(D) != expected_ids:
        raise RuntimeError(
            "Batch must contain exactly OAR0061-OAR0080"
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
                f"{rid} is not PENDING in source v3"
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
        df.loc[mask, "reviewed_at"] = "2026-09-28"

    reviewed = df[
        df["ordinal0_retrieval_safe"].ne("PENDING")
    ]

    pending = df[
        df["ordinal0_retrieval_safe"].eq("PENDING")
    ]

    if len(reviewed) != 80:
        raise RuntimeError(
            f"Expected 80 reviewed rows; got {len(reviewed)}"
        )

    if len(pending) != 75:
        raise RuntimeError(
            f"Expected 75 pending rows; got {len(pending)}"
        )

    df.to_csv(
        OUT,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    manifest = {
        "release":
            "openlibrary-query-author-human-adjudication-results-v4",
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
                ["OAR0061-OAR0080"],
            "rows":
                20,
            "method":
                "manual bibliographic review with ChatGPT assistance",
        },
        "counts": {
            "rows": len(df),
            "reviewed": len(reviewed),
            "pending": len(pending),
            "ordinal0_retrieval_safe":
                dict(Counter(df["ordinal0_retrieval_safe"])),
            "recommended_query_author_action":
                dict(Counter(df["recommended_query_author_action"])),
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
