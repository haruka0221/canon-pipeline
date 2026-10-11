#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import shutil

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

PACKET_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_r2a1_baseline_primary_human_review_packet_v1"
)

MASTER = (
    PACKET_DIR
    / "openalex_r2a1_baseline_primary_human_review_master_v1.tsv"
)

MANIFEST = (
    PACKET_DIR
    / "openalex_r2a1_baseline_primary_human_review_packet_v1_manifest.json"
)

DEFAULT_WORKING = (
    Path.home()
    / "openalex_review_working"
    / "r2a1_baseline_primary_v1"
    / "human_adjudication_working.tsv"
)

REVIEWER_ID = "haruka_tsutsui"

HUMAN_FIELDS = [
    "human_target_attribution_judgment",
    "human_adjudication_confidence",
    "human_attribution_reason_code",
    "human_reviewer_note",
    "human_reviewer_id",
    "human_adjudicated_at_utc",
]

REASONS = {
    "VALID_TARGET_REFERENCE": [
        "DIRECT_TARGET_REFERENCE",
        "VALID_TITLE_VARIANT",
        "VALID_CONTEXTUAL_REFERENCE",
    ],
    "INVALID_TARGET_REFERENCE": [
        "TITLE_COLLISION_DIFFERENT_WORK",
        "GENERIC_OR_LEXICAL_TITLE_USE",
        "AUTHOR_COLLISION_DIFFERENT_PERSON",
        "TITLE_AUTHOR_UNLINKED_COOCCURRENCE",
        "WRONG_WORK_SAME_AUTHOR",
        "ALIAS_NOT_TARGET_EQUIVALENT",
        "METADATA_TEXT_ARTIFACT",
        "OTHER",
    ],
    "UNCERTAIN": [
        "INSUFFICIENT_CONTEXT",
        "AMBIGUOUS_TARGET_REFERENCE",
    ],
}


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        backup = path.with_suffix(".previous.tsv")
        shutil.copy2(path, backup)

    tmp = path.with_suffix(".tmp.tsv")

    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    tmp.replace(path)


def choose(prompt, mapping):
    while True:
        print()
        for key, value in mapping.items():
            print(f"  {key}: {value}")

        x = input(f"\n{prompt}: ").strip().upper()

        if x in mapping:
            return mapping[x]

        if x == "Q":
            return "__QUIT__"

        if x == "S":
            return "__SKIP__"

        print("Invalid input.")


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--batch",
        required=True,
        help="Example: R2A1H01",
    )

    ap.add_argument(
        "--working",
        type=Path,
        default=DEFAULT_WORKING,
    )

    args = ap.parse_args()

    manifest = json.loads(
        MANIFEST.read_text(encoding="utf-8")
    )

    expected_hash = manifest["outputs"][
        str(MASTER.relative_to(ROOT))
    ]

    assert sha256_file(MASTER) == expected_hash

    source = pd.read_csv(
        MASTER,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    assert len(source) == 800

    if args.working.exists():
        df = pd.read_csv(
            args.working,
            sep="\t",
            dtype=str,
            keep_default_na=False,
        )

        assert list(df.columns) == list(source.columns)

        assert (
            df["baseline_candidate_id"].tolist()
            == source["baseline_candidate_id"].tolist()
        )
    else:
        df = source.copy()
        save(df, args.working)

    batch = df.loc[
        df["review_batch_id"].eq(args.batch)
    ].copy()

    if len(batch) != 40:
        raise RuntimeError(
            f"{args.batch}: expected 40 rows, got {len(batch)}"
        )

    completed = (
        batch[
            "human_target_attribution_judgment"
        ].ne("").sum()
    )

    print()
    print("=== R2+A1 BASELINE HUMAN REVIEW ===")
    print("batch:", args.batch)
    print("completed:", completed, "/ 40")
    print("working file:", args.working)
    print()
    print("Candidate-level LLM output is NOT displayed.")
    print("Do not browse the web.")
    print()

    indices = batch.index.tolist()

    for idx in indices:
        row = df.loc[idx]

        if row[
            "human_target_attribution_judgment"
        ]:
            continue

        print("=" * 78)
        print(
            f"Review order: {row['review_order']} "
            f"({args.batch})"
        )
        print(
            "Candidate:",
            row["baseline_candidate_id"],
        )
        print(
            "Project work:",
            row["project_work_id"],
        )

        print("\nTARGET")
        print("Title :", row["target_title"])
        print("Author:", row["target_author"])

        print("\nOPENALEX RECORD")
        print("ID   :", row["openalex_work_id"])
        print("Title:", row["openalex_display_name"])

        print("\nAbstract:")
        abstract = row["openalex_abstract"].strip()
        print(
            abstract
            if abstract
            else "[No abstract available]"
        )

        print("\nPublication:")
        print(
            row["publication_year"],
            row["publication_date"],
        )
        print("DOI:", row["doi"])

        judgment = choose(
            "Judgment (Q=quit, S=skip)",
            {
                "V": "VALID_TARGET_REFERENCE",
                "I": "INVALID_TARGET_REFERENCE",
                "U": "UNCERTAIN",
            },
        )

        if judgment == "__QUIT__":
            save(df, args.working)
            print("Saved. Exiting.")
            return

        if judgment == "__SKIP__":
            continue

        confidence = choose(
            "Confidence",
            {
                "H": "HIGH",
                "M": "MEDIUM",
                "L": "LOW",
            },
        )

        if confidence == "__QUIT__":
            save(df, args.working)
            print("Saved. Exiting.")
            return

        if confidence == "__SKIP__":
            continue

        reasons = REASONS[judgment]

        reason_map = {
            str(i + 1): r
            for i, r in enumerate(reasons)
        }

        print("\nReason codes:")
        for k, v in reason_map.items():
            print(f"  {k}: {v}")

        while True:
            r = input("\nReason number: ").strip()

            if r in reason_map:
                reason = reason_map[r]
                break

            print("Invalid reason number.")

        note = input(
            "\nReviewer note "
            "(concise; recommended for INVALID/UNCERTAIN):\n> "
        ).strip()

        if reason == "OTHER" and not note:
            print("OTHER requires a reviewer note.")
            continue

        timestamp = (
            datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )

        df.at[
            idx,
            "human_target_attribution_judgment",
        ] = judgment

        df.at[
            idx,
            "human_adjudication_confidence",
        ] = confidence

        df.at[
            idx,
            "human_attribution_reason_code",
        ] = reason

        df.at[
            idx,
            "human_reviewer_note",
        ] = note

        df.at[
            idx,
            "human_reviewer_id",
        ] = REVIEWER_ID

        df.at[
            idx,
            "human_adjudicated_at_utc",
        ] = timestamp

        save(df, args.working)

        done = (
            df.loc[
                df["review_batch_id"].eq(args.batch),
                "human_target_attribution_judgment",
            ]
            .ne("")
            .sum()
        )

        print(
            f"\nSaved: {done}/40 in {args.batch}"
        )

    print()
    print(
        f"=== {args.batch} COMPLETE ==="
    )

    print(
        df.loc[
            df["review_batch_id"].eq(args.batch),
            "human_target_attribution_judgment",
        ]
        .value_counts()
        .to_string()
    )


if __name__ == "__main__":
    main()
