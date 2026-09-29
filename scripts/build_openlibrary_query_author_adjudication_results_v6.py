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
    / "openlibrary_query_author_human_review_adjudication_results_v5.tsv"
)

SOURCE_MANIFEST = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v5_manifest.json"
)

OUT = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v6.tsv"
)

OUT_MANIFEST = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v6_manifest.json"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


D = {
    "OAR0101": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Edward Sylvester Ellis",
        types="straightforward;publisher_or_production_entity",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; the later edge is "
            "the publishing company."
        ),
    ),

    "OAR0102": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="William Montgomery Clemens",
        types="straightforward;publisher_or_production_entity",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; Hawthorne Press is "
            "a publishing entity."
        ),
    ),

    "OAR0103": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Harriet Emerson Holmes",
        types="straightforward;corporate_or_institutional_author",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; the later institutional "
            "edge is not selected as a retrieval author."
        ),
    ),

    "OAR0104": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Gilbert Keith Chesterton",
        types="straightforward;publisher_or_production_entity",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; the later publishing "
            "staff record is not selected."
        ),
    ),

    "OAR0105": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Marie Corelli",
        types="straightforward;corporate_or_institutional_author",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; the later library/"
            "collection entity is not a retrieval author."
        ),
    ),

    "OAR0106": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Henry James",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Henry James is the literary author. The later Sara Lopez "
            "edge is not required for work-level retrieval."
        ),
    ),

    "OAR0107": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Лев Толстой",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is Tolstoy, the literary author; Nathan Haskell "
            "Dole is translation-related."
        ),
    ),

    "OAR0108": dict(
        safe="YES",
        action="USE_MULTIPLE_OL_AUTHORS",
        ordinals="0;1",
        names="Edgar Jepson;Maurice Leblanc",
        types="coauthor_collaborator;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs=(
            "Wikisource / Project Gutenberg / Google Books: "
            "Arsene Lupin, 1909"
        ),
        note=(
            "The 1909 novelization is explicitly credited to Edgar "
            "Jepson and Maurice Leblanc. Both available OL names are "
            "useful as separate retrieval routes."
        ),
    ),

    "OAR0109": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Maud Hart Lovelace",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; Lois Lenski is the "
            "illustrator."
        ),
    ),

    "OAR0110": dict(
        safe="YES",
        action="USE_MULTIPLE_OL_AUTHORS",
        ordinals="0;1",
        names="Amanda Mathews Chase;Olive Percival",
        types="anthology_collection;coauthor_collaborator",
        basis="PACKET_AND_EXTERNAL",
        refs="Online Books Page: Cuentos de California, 1904",
        note=(
            "The collection contains contributions credited to multiple "
            "writers, including Amanda Mathews Chase and Olive Percival. "
            "Both available OL names are retained as separate retrieval "
            "routes. Clara Bradley Burdette is also bibliographically "
            "credited but is not present in the available OL author edges."
        ),
    ),

    "OAR0111": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Hermann Sudermann",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="Project Gutenberg: Dame Care",
        note=(
            "Hermann Sudermann is the literary author; Bertha Overbeck "
            "is the translator."
        ),
    ),

    "OAR0112": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Mary Buff",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="Conrad Buff archive / bibliographic records: Dancing Cloud",
        note=(
            "Mary Buff supplied the writing/story; Conrad Buff supplied "
            "the illustrations. Only ordinal 0 is selected as the "
            "retrieval author."
        ),
    ),

    "OAR0113": dict(
        safe="YES",
        action="USE_MULTIPLE_OL_AUTHORS",
        ordinals="0;1",
        names="Mary Buff;Conrad Buff",
        types="coauthor_collaborator",
        basis="PACKET_AND_EXTERNAL",
        refs="CiNii Books / Open Library: Dash & Dart",
        note=(
            "Dash & Dart is bibliographically credited to Mary and "
            "Conrad Buff. Both names are retained as separate retrieval "
            "routes."
        ),
    ),

    "OAR0114": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Harry Sylvester",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="Harry Sylvester bibliography: Dayspring, 1945",
        note=(
            "Harry Sylvester is the author of the 1945 novel Dayspring. "
            "The later Phillip Jenkins edge is not required as a "
            "work-level retrieval author."
        ),
    ),

    "OAR0115": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Edward Everett Hale",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; the later edition-related "
            "name is not selected."
        ),
    ),

    "OAR0116": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Joris-Karl Huysmans",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_ONLY",
        refs="frozen review packet",
        note=(
            "Ordinal 0 is the literary author; Brendan King is "
            "translation-related."
        ),
    ),

    "OAR0117": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Henry Wadsworth Longfellow",
        types="straightforward;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="Online Books Page: Evangeline, Carolyn Sherwin Bailey ed.",
        note=(
            "Longfellow is the literary author. Carolyn Sherwin Bailey "
            "prepared an edition with introduction/prose adaptation, "
            "but is not selected as an additional work-level author route."
        ),
    ),

    "OAR0118": dict(
        safe="YES",
        action="USE_MULTIPLE_OL_AUTHORS",
        ordinals="0;1",
        names="Cecil John Charles Street;John Dickson Carr",
        types="coauthor_collaborator",
        basis="PACKET_AND_EXTERNAL",
        refs="ABAA / bibliographic records: Fatal Descent, 1939",
        note=(
            "Fatal Descent was jointly written by Cecil Street "
            "(John Rhode) and John Dickson Carr (Carter Dickson). "
            "Both available OL names are selected."
        ),
    ),

    "OAR0119": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Hamilton Wright Mabie",
        types="anthology_collection;translator_editor_adapter",
        basis="PACKET_AND_EXTERNAL",
        refs="Project Gutenberg: Heroes Every Child Should Know",
        note=(
            "Hamilton Wright Mabie is the collection editor; Blanche "
            "Ostertag is the illustrator. Mabie is a valid retrieval "
            "responsibility name for the anthology."
        ),
    ),

    "OAR0120": dict(
        safe="YES",
        action="USE_ORDINAL0",
        ordinals="0",
        names="Hebe Elsna",
        types="duplicate_same_person;name_variant_or_error",
        basis="PACKET_AND_EXTERNAL",
        refs="Open British National Bibliography: The Songless Wood",
        note=(
            "Hebe Elsna is the pseudonym under which the 1944 work "
            "I Have Lived Today was published; Lyndon Snow is the same "
            "author's name. Ordinal 0 is retained as the publication-"
            "specific retrieval form."
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
            "Frozen adjudication results v5 SHA256 mismatch"
        )

    df = pd.read_csv(
        SOURCE,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    expected_ids = {
        f"OAR{i:04d}"
        for i in range(101, 121)
    }

    if set(D) != expected_ids:
        raise RuntimeError(
            "Batch must contain exactly OAR0101-OAR0120"
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
                f"{rid} is not PENDING in source v5"
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

    if len(reviewed) != 120:
        raise RuntimeError(
            f"Expected 120 reviewed rows; got {len(reviewed)}"
        )

    if len(pending) != 35:
        raise RuntimeError(
            f"Expected 35 pending rows; got {len(pending)}"
        )

    df.to_csv(
        OUT,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    manifest = {
        "release":
            "openlibrary-query-author-human-adjudication-results-v6",
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
                ["OAR0101-OAR0120"],
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
