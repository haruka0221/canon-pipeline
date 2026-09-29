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
    / "openlibrary_query_author_human_review_adjudication_results_v7.tsv"
)

SOURCE_MANIFEST = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v7_manifest.json"
)

OUT = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v8.tsv"
)

OUT_MANIFEST = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v8_manifest.json"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


D = {
    "OAR0141": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Amelia E. Johnson",
        types="straightforward;duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is a clean author representation; A. E. Johnson "
            "is a shorter representation of the same author."
        ),
    ),

    "OAR0142": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Ralph F. Cummings",
        types="corporate_or_institutional_author;target_or_scope_problem",
        basis="PACKET_AND_EXTERNAL",
        refs="Open Library: Ralph F. Cummings; Johannsen Collection",
        note=(
            "Ralph F. Cummings is the appropriate bibliographic "
            "responsibility name. Johannsen Collection is a collection/"
            "institutional provenance entity rather than an additional "
            "personal author. The target is a catalogue of dime and "
            "nickel novels rather than a fiction work, which is a "
            "separate population/scope issue."
        ),
    ),

    "OAR0143": dict(
        safe="YES",
        action="USE_MULTIPLE_OL_AUTHORS",
        ordinals="0;1",
        names="Glen Rounds;Lydia Rosier",
        types="coauthor_collaborator",
        basis="PACKET_AND_EXTERNAL",
        refs="Open Library: The Blind Colt",
        note=(
            "The Blind Colt is bibliographically credited to Glen "
            "Rounds and Lydia Rosier. Both available OL names are "
            "retained as separate retrieval routes."
        ),
    ),

    "OAR0144": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="William S. Hart",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="Online Books Page: The Golden West Boys",
        note=(
            "William S. Hart is the literary author. Harold James Cue "
            "is associated with illustration in the Golden West Boys "
            "series and is not selected as an additional work-level "
            "retrieval author."
        ),
    ),

    "OAR0145": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="William Caxton",
        types="translator_editor_adapter;target_or_scope_problem",
        basis="PACKET_AND_EXTERNAL",
        refs=(
            "CiNii Books: The lyf of the noble and Crysten prynce, "
            "Charles the Grete"
        ),
        note=(
            "William Caxton translated the text from French and printed "
            "it in 1485; Sidney J. H. Herrtage edited the 1880-1881 "
            "Early English Text Society edition. Caxton is a useful "
            "retrieval responsibility name, while the target's medieval "
            "origin and later scholarly edition constitute a separate "
            "1880-1950 population/scope issue."
        ),
    ),

    "OAR0146": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Eleanor Estes",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; Louis Slobodkin is "
            "illustration-related."
        ),
    ),

    "OAR0147": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Shirley Jackson",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="Penguin Random House: The Road Through the Wall",
        note=(
            "Shirley Jackson is the literary author. Ruth Franklin "
            "supplied the foreword to a later Penguin edition and is "
            "not selected as an additional work-level retrieval author."
        ),
    ),

    "OAR0148": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Charles Young",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="Google Play Books: The Shark-hunter",
        note=(
            "Charles Young is the literary author. The later R. André "
            "edge is not selected as an additional work-level retrieval "
            "author."
        ),
    ),

    "OAR0149": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="J. B. Naylor",
        types="duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "J. B. Naylor and James Ball Naylor represent the same "
            "author; ordinal 0 is retained as the retrieval form."
        ),
    ),

    "OAR0150": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Johann Wolfgang von Goethe",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; William Rose is "
            "translation-related."
        ),
    ),

    "OAR0151": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Ann Lane Petry",
        types="duplicate_same_person",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ann Lane Petry and Ann Petry represent the same literary "
            "author; ordinal 0 is retrieval-safe."
        ),
    ),

    "OAR0152": dict(
        safe="YES",
        action="USE_MULTIPLE_OL_AUTHORS",
        ordinals="0;1",
        names="Alexandre Dumas;Auguste Maquet",
        types="coauthor_collaborator",
        basis="PACKET_AND_EXTERNAL",
        refs="Google Books: The Three Musketeers",
        note=(
            "The Three Musketeers was produced through the collaboration "
            "of Alexandre Dumas and Auguste Maquet, and historical "
            "bibliographic records credit both names. Both available "
            "OL names are retained as separate retrieval routes."
        ),
    ),

    "OAR0153": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Marcelle Tinayre",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="European War Fiction in English bibliography: To Arms!",
        note=(
            "Marcelle Tinayre is the literary author; Lucy Henderson "
            "Humphrey supplied the authorized English translation."
        ),
    ),

    "OAR0154": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Mark Twain",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; John D. Seelye is "
            "edition/editorial-related."
        ),
    ),

    "OAR0155": dict(
        safe="YES",
        action="USE_MULTIPLE_OL_AUTHORS",
        ordinals="0;1",
        names="Dudley, Dorothy;Juanita Sheridan",
        types="coauthor_collaborator",
        basis="PACKET_AND_EXTERNAL",
        refs=(
            "Mystery File Midnite Mysteries bibliography; "
            "Camp Lejeune Globe 1945"
        ),
        note=(
            "What Dark Secret is bibliographically credited to Dorothy "
            "Dudley and Juanita Sheridan. Both available OL names are "
            "retained as separate retrieval routes."
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
            "Frozen adjudication results v7 SHA256 mismatch"
        )

    df = pd.read_csv(
        SOURCE,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    expected_ids = {
        f"OAR{i:04d}"
        for i in range(141, 156)
    }

    if set(D) != expected_ids:
        raise RuntimeError(
            "Batch must contain exactly OAR0141-OAR0155"
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
                f"{rid} is not PENDING in source v7"
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

    if len(reviewed) != 155:
        raise RuntimeError(
            f"Expected 155 reviewed rows; got {len(reviewed)}"
        )

    if len(pending) != 0:
        raise RuntimeError(
            f"Expected 0 pending rows; got {len(pending)}"
        )

    df.to_csv(
        OUT,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    manifest = {
        "release":
            "openlibrary-query-author-human-adjudication-results-v8",
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
                ["OAR0141-OAR0155"],
            "rows":
                15,
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
