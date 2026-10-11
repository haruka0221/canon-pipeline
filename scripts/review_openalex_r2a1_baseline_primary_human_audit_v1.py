#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import shutil

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

PACKET_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_r2a1_baseline_primary_human_audit_packet_v1"
)

MASTER = (
    PACKET_DIR
    / "openalex_r2a1_baseline_primary_human_audit_master_v1.tsv"
)

MANIFEST = (
    PACKET_DIR
    / "openalex_r2a1_baseline_primary_human_audit_packet_v1_manifest.json"
)

DEFAULT_WORKING = (
    Path.home()
    / "openalex_review_working"
    / "r2a1_baseline_primary_human_audit_v1"
    / "human_audit_working.tsv"
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
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def save(df, path):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if path.exists():
        shutil.copy2(
            path,
            path.with_suffix(".previous.tsv"),
        )

    tmp = path.with_suffix(".tmp.tsv")

    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    os.replace(tmp, path)


def choose(prompt, mapping):

    while True:

        print()

        for key, value in mapping.items():
            print(f"  {key}: {value}")

        print("  S: skip this candidate")
        print("  Q: save and quit")

        x = input(
            f"\n{prompt}: "
        ).strip().upper()

        if x in mapping:
            return mapping[x]

        if x == "S":
            return "__SKIP__"

        if x == "Q":
            return "__QUIT__"

        print("Invalid input.")


def main():

    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--batch",
        required=True,
        choices=[
            f"R2A1A{i:02d}"
            for i in range(1, 7)
        ],
    )

    ap.add_argument(
        "--working",
        type=Path,
        default=DEFAULT_WORKING,
    )

    args = ap.parse_args()

    # --------------------------------------------------
    # Verify frozen packet
    # --------------------------------------------------

    manifest = json.loads(
        MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    expected_hash = (
        manifest[
            "outputs"
        ][
            str(
                MASTER.relative_to(ROOT)
            )
        ]
    )

    assert (
        sha256_file(MASTER)
        == expected_hash
    )

    source = pd.read_csv(
        MASTER,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    assert len(source) == 150

    assert source[
        "baseline_candidate_id"
    ].is_unique

    assert source[
        HUMAN_FIELDS
    ].eq("").all().all()

    # Explicit blindness guard.
    assert not any(
        c.startswith("llm_")
        for c in source.columns
    )

    forbidden = {
        "llm_first_pass_judgment",
        "selection_rank_within_stratum",
        "stratum_population_n",
        "stratum_sample_n",
        "stratum_sampling_fraction",
        "analysis_weight",
        "hit_location",
        "title_token_bucket",
        "work_candidate_count",
        "work_volume_bucket",
    }

    assert not (
        forbidden
        & set(source.columns)
    )

    # --------------------------------------------------
    # Load or initialize working copy outside Git repo
    # --------------------------------------------------

    if args.working.exists():

        df = pd.read_csv(
            args.working,
            sep="\t",
            dtype=str,
            keep_default_na=False,
        )

        assert (
            list(df.columns)
            == list(source.columns)
        )

        assert (
            df[
                "baseline_candidate_id"
            ].tolist()
            == source[
                "baseline_candidate_id"
            ].tolist()
        )

    else:

        df = source.copy()

        save(
            df,
            args.working,
        )

    batch_mask = (
        df[
            "review_batch_id"
        ].eq(args.batch)
    )

    assert int(
        batch_mask.sum()
    ) == 25

    completed = int(
        df.loc[
            batch_mask,
            "human_target_attribution_judgment",
        ]
        .ne("")
        .sum()
    )

    print()
    print(
        "=== R2+A1 BASELINE "
        "BLIND HUMAN AUDIT V1 ==="
    )

    print(
        "batch:",
        args.batch,
    )

    print(
        "completed:",
        completed,
        "/ 25",
    )

    print(
        "working file:",
        args.working,
    )

    print()
    print(
        "Candidate-level LLM judgments "
        "and sampling strata are NOT displayed."
    )

    print(
        "Use only the supplied target and "
        "OpenAlex record context."
    )

    print(
        "Do not browse the web."
    )

    # --------------------------------------------------
    # Review
    # --------------------------------------------------

    indices = df.index[
        batch_mask
    ].tolist()

    for idx in indices:

        row = df.loc[idx]

        if row[
            "human_target_attribution_judgment"
        ]:
            continue

        print()
        print("=" * 78)

        print(
            f"Review order: "
            f"{row['review_order']} "
            f"({args.batch})"
        )

        print(
            "Candidate:",
            row[
                "baseline_candidate_id"
            ],
        )

        print(
            "Project work:",
            row[
                "project_work_id"
            ],
        )

        print("\nTARGET")

        print(
            "Title :",
            row["target_title"],
        )

        print(
            "Author:",
            row["target_author"],
        )

        print("\nOPENALEX RECORD")

        print(
            "ID   :",
            row["openalex_work_id"],
        )

        print(
            "Title:",
            row[
                "openalex_display_name"
            ],
        )

        print("\nAbstract:")

        abstract = (
            row[
                "openalex_abstract"
            ].strip()
        )

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

        print(
            "DOI:",
            row["doi"],
        )

        judgment = choose(
            "Judgment",
            {
                "V":
                    "VALID_TARGET_REFERENCE",

                "I":
                    "INVALID_TARGET_REFERENCE",

                "U":
                    "UNCERTAIN",
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

        reasons = (
            REASONS[judgment]
        )

        reason_map = {
            str(i + 1): reason
            for i, reason
            in enumerate(reasons)
        }

        print()
        print("Reason codes:")

        for key, value in (
            reason_map.items()
        ):
            print(
                f"  {key}: {value}"
            )

        while True:

            value = input(
                "\nReason number: "
            ).strip()

            if value in reason_map:
                reason = (
                    reason_map[value]
                )
                break

            print(
                "Invalid reason number."
            )

        note = input(
            "\nReviewer note:\n> "
        ).strip()

        # Make negative/uncertain judgments auditable.
        if (
            judgment
            in {
                "INVALID_TARGET_REFERENCE",
                "UNCERTAIN",
            }
            and not note
        ):
            print(
                "INVALID/UNCERTAIN requires "
                "a brief reviewer note."
            )
            continue

        if (
            reason == "OTHER"
            and not note
        ):
            print(
                "OTHER requires a "
                "reviewer note."
            )
            continue

        timestamp = (
            datetime.now(
                timezone.utc
            )
            .isoformat(
                timespec="seconds"
            )
            .replace(
                "+00:00",
                "Z",
            )
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

        save(
            df,
            args.working,
        )

        done = int(
            df.loc[
                batch_mask,
                "human_target_attribution_judgment",
            ]
            .ne("")
            .sum()
        )

        print(
            f"\nSaved: "
            f"{done}/25 in "
            f"{args.batch}"
        )

    print()
    print(
        f"=== {args.batch} COMPLETE ==="
    )

    print(
        df.loc[
            batch_mask,
            "human_target_attribution_judgment",
        ]
        .value_counts()
        .to_string()
    )


if __name__ == "__main__":
    main()
