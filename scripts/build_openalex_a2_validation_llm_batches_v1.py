#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

SOURCE = (
    ROOT
    / "derived/openalex_production/"
      "retrieval_a2_validation_candidates_v1/"
      "openalex_a2_validation_blind_adjudication_v1.tsv"
)

PROMPT = (
    ROOT
    / "docs/"
      "OPENALEX_A2_VALIDATION_LLM_FIRST_PASS_PROMPT_V1.md"
)

OUT = (
    ROOT
    / "derived/openalex_production/"
      "retrieval_a2_validation_llm_batches_v1"
)

RELEASE = "openalex-a2-validation-llm-batches-v1"
SALT = "openalex-a2-validation-llm-first-pass-v1"
BATCH_SIZE = 25
EXPECTED_ROWS = 248


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def stable_key(candidate_id: str) -> str:
    return hashlib.sha256(
        (
            SALT
            + "\0"
            + candidate_id
        ).encode("utf-8")
    ).hexdigest()


def atomic_tsv(df, path):
    tmp = path.with_name(path.name + ".tmp")

    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    os.replace(tmp, path)


def main():
    if OUT.exists():
        raise RuntimeError(
            f"Output already exists: {OUT}"
        )

    df = pd.read_csv(
        SOURCE,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    assert len(df) == EXPECTED_ROWS
    assert df["validation_candidate_id"].is_unique

    for c in [
        "human_judgment",
        "human_reason_code",
        "human_notes",
    ]:
        assert df[c].eq("").all()

    input_columns = [
        "validation_candidate_id",
        "project_work_id",
        "target_title",
        "target_author",
        "openalex_work_id",
        "openalex_display_name",
        "openalex_abstract",
        "publication_year",
        "publication_date",
        "doi",
    ]

    x = df[input_columns].copy()

    x["_stable_order"] = (
        x["validation_candidate_id"]
        .map(stable_key)
    )

    x = (
        x.sort_values(
            [
                "_stable_order",
                "validation_candidate_id",
            ],
            kind="stable",
        )
        .drop(
            columns=["_stable_order"]
        )
        .reset_index(drop=True)
    )

    OUT.mkdir(
        parents=True,
        exist_ok=False,
    )

    batches = []

    for start in range(
        0,
        len(x),
        BATCH_SIZE,
    ):
        batch_no = (
            start // BATCH_SIZE
        ) + 1

        b = x.iloc[
            start:start + BATCH_SIZE
        ].copy()

        name = (
            f"openalex_a2_validation_"
            f"llm_batch_{batch_no:02d}.tsv"
        )

        path = OUT / name

        atomic_tsv(
            b,
            path,
        )

        batches.append({
            "batch": batch_no,
            "artifact": name,
            "rows": len(b),
            "sha256": sha256_file(path),
        })

    assert sum(
        b["rows"]
        for b in batches
    ) == EXPECTED_ROWS

    assert len(batches) == 10
    assert [
        b["rows"]
        for b in batches
    ] == [
        25, 25, 25, 25, 25,
        25, 25, 25, 25, 23,
    ]

    manifest = {
        "release": RELEASE,
        "status":
            "frozen_blind_llm_first_pass_inputs",

        "candidate_rows":
            EXPECTED_ROWS,

        "batch_size":
            BATCH_SIZE,

        "batch_count":
            len(batches),

        "ordering": {
            "method":
                "SHA256(salt + NUL + validation_candidate_id)",
            "salt":
                SALT,
            "purpose":
                (
                    "Deterministically mix project works "
                    "rather than adjudicating candidates "
                    "in project-work blocks."
                ),
        },

        "source": {
            "artifact":
                str(SOURCE.relative_to(ROOT)),
            "sha256":
                sha256_file(SOURCE),
        },

        "prompt": {
            "artifact":
                str(PROMPT.relative_to(ROOT)),
            "sha256":
                sha256_file(PROMPT),
        },

        "policy_information_included":
            False,

        "human_labels_included":
            False,

        "batches":
            batches,
    }

    manifest_path = (
        OUT
        / "openalex_a2_validation_llm_batches_v1_manifest.json"
    )

    manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print("=== LLM FIRST-PASS INPUTS ===")
    print("rows:", len(x))
    print("batches:", len(batches))

    for b in batches:
        print(
            f"batch {b['batch']:02d}: "
            f"{b['rows']} rows"
        )

    print("\noutput:", OUT)
    print("PASSED")


if __name__ == "__main__":
    main()
