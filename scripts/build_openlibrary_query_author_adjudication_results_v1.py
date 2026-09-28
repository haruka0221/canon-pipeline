#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

DIR = ROOT / "derived/openlibrary_query_author_review_v1"

TEMPLATE = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_v1.tsv"
)

TEMPLATE_MANIFEST = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_v1_manifest.json"
)

REVIEW_PACKET = (
    DIR
    / "openlibrary_query_author_human_review_v1.tsv"
)

RESULTS = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v1.tsv"
)

RESULTS_MANIFEST = (
    DIR
    / "openlibrary_query_author_human_review_adjudication_results_v1_manifest.json"
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
    "OAR0001": {
        "safe": "NO",
        "action": "USE_OTHER_ORDINAL",
        "ordinals": "2",
        "names": "Sade Collins",
        "types": "publisher_or_production_entity",
        "basis": "PACKET_AND_EXTERNAL",
        "refs": "BookBaby: A Lover's Mentality",
        "note": (
            "Ordinal 0 is a production entity and ordinal 1 an "
            "editing-service record; Sade Collins is the work author."
        ),
    },

    "OAR0002": {
        "safe": "NO",
        "action": "NO_OL_AUTHOR",
        "ordinals": "NONE",
        "names": "NONE",
        "types": (
            "corporate_or_institutional_author;"
            "target_or_scope_problem"
        ),
        "basis": "PACKET_AND_EXTERNAL",
        "refs": (
            "Emporia State Research Studies: "
            "Sisson and Walthall bibliography"
        ),
        "note": (
            "The OL author edges contain the institution rather than "
            "the named authors S. Hull Sisson and Harry Walthall; "
            "the target is also a thesis bibliography rather than "
            "a literary work."
        ),
    },

    "OAR0003": {
        "safe": "NO",
        "action": "NO_OL_AUTHOR",
        "ordinals": "NONE",
        "names": "NONE",
        "types": (
            "anthology_collection;"
            "publisher_or_production_entity"
        ),
        "basis": "PACKET_ONLY",
        "refs": "frozen review packet",
        "note": (
            "Ordinal 0 is a publisher/corporate record and ordinal 1 "
            "is the generic label Multiple Authors; neither is a "
            "useful retrieval-author string."
        ),
    },

    "OAR0004": {
        "safe": "NO",
        "action": "NO_OL_AUTHOR",
        "ordinals": "NONE",
        "names": "NONE",
        "types": "publisher_or_production_entity",
        "basis": "PACKET_ONLY",
        "refs": "frozen review packet",
        "note": (
            "Both OL author edges are company/printer-like records; "
            "no usable literary query author is present."
        ),
    },

    "OAR0005": {
        "safe": "NO",
        "action": "NO_OL_AUTHOR",
        "ordinals": "NONE",
        "names": "NONE",
        "types": (
            "missing_author_record;"
            "translator_editor_adapter"
        ),
        "basis": "PACKET_AND_EXTERNAL",
        "refs": (
            "Project Gutenberg ebook 28693; "
            "Google Books: Tales of the Fish Patrol"
        ),
        "note": (
            "The work author is Jack London, who is absent from the "
            "available OL author edges; George Varian is the illustrator."
        ),
    },

    "OAR0006": {
        "safe": "YES",
        "action": "USE_ORDINAL0",
        "ordinals": "0",
        "names": "Miguel Ángel Asturias",
        "types": "duplicate_same_person",
        "basis": "PACKET_ONLY",
        "refs": "frozen review packet",
        "note": (
            "Ordinal 0 is a usable canonical-looking author string; "
            "several later edges are duplicate name variants."
        ),
    },

    "OAR0007": {
        "safe": "YES",
        "action": "USE_ORDINAL0",
        "ordinals": "0",
        "names": "Benito Pérez Galdós",
        "types": "duplicate_same_person",
        "basis": "PACKET_ONLY",
        "refs": "frozen review packet",
        "note": (
            "Ordinal 0 is a usable author string; later edges include "
            "duplicate variants and contributors."
        ),
    },

    "OAR0008": {
        "safe": "YES",
        "action": "USE_ORDINAL0",
        "ordinals": "0",
        "names": "Norman Douglas",
        "types": "duplicate_same_person",
        "basis": "PACKET_ONLY",
        "refs": "frozen review packet",
        "note": (
            "Ordinal 0 is the cleanest usable form among numerous "
            "duplicate or malformed Norman Douglas records."
        ),
    },

    "OAR0009": {
        "safe": "YES",
        "action": "USE_MULTIPLE_OL_AUTHORS",
        "ordinals": "0;1",
        "names": "William Dean Howells;Henry Mills Alden",
        "types": "anthology_collection;coauthor_collaborator",
        "basis": "PACKET_AND_EXTERNAL",
        "refs": "The Online Books Page: Their Husbands' Wives",
        "note": (
            "Howells and Alden are co-editors; both are legitimate "
            "retrieval-author candidates for the anthology."
        ),
    },

    "OAR0010": {
        "safe": "YES",
        "action": "USE_ORDINAL0",
        "ordinals": "0",
        "names": "Hans Christian Andersen",
        "types": "straightforward",
        "basis": "PACKET_ONLY",
        "refs": "frozen review packet",
        "note": (
            "Ordinal 0 is the appropriate literary author; later "
            "records are edition-related contributors."
        ),
    },

    "OAR0011": {
        "safe": "YES",
        "action": "USE_MULTIPLE_OL_AUTHORS",
        "ordinals": "0;1",
        "names": "Bertha B. Cobb;Ernest Cobb",
        "types": "coauthor_collaborator",
        "basis": "PACKET_AND_EXTERNAL",
        "refs": "Fall River Public Library Estes Collection: Anita",
        "note": (
            "Anita is credited to Bertha B. Cobb and Ernest Cobb; "
            "both are valid retrieval-author candidates."
        ),
    },

    "OAR0012": {
        "safe": "NO",
        "action": "USE_OTHER_ORDINAL",
        "ordinals": "1",
        "names": "E. W. Hornung",
        "types": "name_variant_or_error;duplicate_same_person",
        "basis": "PACKET_AND_EXTERNAL",
        "refs": "Project Gutenberg Australia: E. W. Hornung / Raffles",
        "note": (
            "Ordinal 0 contains Harnung, while later OL records give "
            "the established author string E. W. Hornung."
        ),
    },

    "OAR0013": {
        "safe": "YES",
        "action": "USE_MULTIPLE_OL_AUTHORS",
        "ordinals": "0;1",
        "names": "Raymond J. Healy;J. Francis McComas",
        "types": "anthology_collection;coauthor_collaborator",
        "basis": "PACKET_AND_EXTERNAL",
        "refs": "Google Books: Adventures in Time and Space",
        "note": (
            "Healy and McComas are the anthology's co-editors; both "
            "are valid retrieval-author candidates."
        ),
    },

    "OAR0014": {
        "safe": "NO",
        "action": "USE_OTHER_ORDINAL",
        "ordinals": "1",
        "names": "Charles Dickens",
        "types": "translator_editor_adapter",
        "basis": "PACKET_AND_EXTERNAL",
        "refs": "Google Books / CiNii Books: Bleak House",
        "note": (
            "Charles Dickens is the work author; Andrew Lang supplied "
            "editorial/introduction material for this edition."
        ),
    },

    "OAR0015": {
        "safe": "YES",
        "action": "USE_ORDINAL0",
        "ordinals": "0",
        "names": "Alice Corkran",
        "types": "straightforward",
        "basis": "PACKET_AND_EXTERNAL",
        "refs": "Project Gutenberg ebook 57413",
        "note": (
            "Alice Corkran is explicitly credited as the author; "
            "Gordon Browne is the illustrator."
        ),
    },

    "OAR0016": {
        "safe": "YES",
        "action": "USE_ORDINAL0",
        "ordinals": "0",
        "names": "Charles Dickens",
        "types": "straightforward",
        "basis": "PACKET_ONLY",
        "refs": "frozen review packet",
        "note": "Ordinal 0 is the appropriate literary author.",
    },

    "OAR0017": {
        "safe": "YES",
        "action": "USE_ORDINAL0",
        "ordinals": "0",
        "names": "Richmal Crompton",
        "types": "straightforward;duplicate_same_person",
        "basis": "PACKET_ONLY",
        "refs": "frozen review packet",
        "note": (
            "Ordinal 0 is the clean usable author string; later edges "
            "include an abbreviated duplicate and edition contributors."
        ),
    },

    "OAR0018": {
        "safe": "YES",
        "action": "USE_ORDINAL0",
        "ordinals": "0",
        "names": "Émile Zola",
        "types": "straightforward;translator_editor_adapter",
        "basis": "PACKET_ONLY",
        "refs": "frozen review packet",
        "note": (
            "Ordinal 0 is the literary author; later records are "
            "edition-related contributors."
        ),
    },

    "OAR0019": {
        "safe": "YES",
        "action": "USE_ORDINAL0",
        "ordinals": "0",
        "names": "Jacob Abbott",
        "types": "straightforward",
        "basis": "PACKET_AND_EXTERNAL",
        "refs": "Bibliographic listing: Marco Paul's Voyages and Travels: Boston",
        "note": "Jacob Abbott is the work author.",
    },

    "OAR0020": {
        "safe": "YES",
        "action": "USE_ORDINAL0",
        "ordinals": "0",
        "names": "James Stephens",
        "types": "straightforward;translator_editor_adapter",
        "basis": "PACKET_AND_EXTERNAL",
        "refs": "Project Gutenberg ebook 24742",
        "note": (
            "James Stephens is the author; Padraic Colum is credited "
            "for the introduction/commentary."
        ),
    },
}


def main() -> None:
    manifest = json.loads(
        TEMPLATE_MANIFEST.read_text(encoding="utf-8")
    )

    expected = manifest["output"]["sha256"]
    actual = sha256_file(TEMPLATE)

    if actual != expected:
        raise RuntimeError(
            "Frozen adjudication template SHA256 mismatch"
        )

    df = pd.read_csv(
        TEMPLATE,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    packet = pd.read_csv(
        REVIEW_PACKET,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    if set(D) - set(df["review_id"]):
        raise RuntimeError("Decision review_id missing from template")

    expected_ids = {
        f"OAR{i:04d}"
        for i in range(1, 21)
    }

    if set(D) != expected_ids:
        raise RuntimeError(
            "Calibration batch must contain exactly OAR0001-OAR0020"
        )

    packet_ids = set(packet["review_id"])
    if not set(D).issubset(packet_ids):
        raise RuntimeError(
            "Calibration review_id missing from frozen review packet"
        )

    for rid, d in D.items():
        mask = df["review_id"].eq(rid)

        if int(mask.sum()) != 1:
            raise RuntimeError(
                f"Expected exactly one row for {rid}"
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
        ] = "Haruka Tsutsui (ChatGPT-assisted calibration)"
        df.loc[
            mask,
            "reviewed_at",
        ] = "2026-09-28"

    remaining = df[
        ~df["review_id"].isin(D)
    ]

    if not (
        remaining["ordinal0_retrieval_safe"]
        .eq("PENDING")
        .all()
    ):
        raise RuntimeError(
            "Rows outside calibration batch are no longer PENDING"
        )

    df.to_csv(
        RESULTS,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    out_manifest = {
        "release":
            "openlibrary-query-author-human-adjudication-results-v1",
        "created_at":
            "2026-09-28",
        "source_template": {
            "artifact":
                str(TEMPLATE.relative_to(ROOT)),
            "sha256":
                actual,
        },
        "source_review_packet": {
            "artifact":
                str(REVIEW_PACKET.relative_to(ROOT)),
            "sha256":
                sha256_file(REVIEW_PACKET),
        },
        "calibration_batch": {
            "review_ids":
                ["OAR0001-OAR0020"],
            "rows":
                20,
            "method":
                "manual bibliographic calibration with ChatGPT assistance",
        },
        "counts": {
            "rows":
                len(df),
            "reviewed":
                int(
                    df[
                        "ordinal0_retrieval_safe"
                    ].ne("PENDING").sum()
                ),
            "pending":
                int(
                    df[
                        "ordinal0_retrieval_safe"
                    ].eq("PENDING").sum()
                ),
            "ordinal0_retrieval_safe":
                dict(
                    Counter(
                        df[
                            "ordinal0_retrieval_safe"
                        ]
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
                str(RESULTS.relative_to(ROOT)),
            "sha256":
                sha256_file(RESULTS),
        },
    }

    RESULTS_MANIFEST.write_text(
        json.dumps(
            out_manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print("rows:", len(df))
    print(
        df[
            "ordinal0_retrieval_safe"
        ].value_counts().to_string()
    )

    print()
    print(
        df[
            "recommended_query_author_action"
        ].value_counts().to_string()
    )

    print()
    print(RESULTS.relative_to(ROOT))
    print(RESULTS_MANIFEST.relative_to(ROOT))


if __name__ == "__main__":
    main()
