#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

ADJ = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_remediation_adjudication_v1"
    / "openlibrary_r2a1_target_identity_remediation_adjudication_v1.tsv"
)

EDITIONS = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_remediation_evidence_v1"
    / "openlibrary_r2a1_target_identity_remediation_edition_evidence_v1.tsv"
)

OUT_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_routing_input_v1"
)

OUT_TSV = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_input_v1.tsv"
)

OUT_PROJECTS = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_projects_v1.tsv"
)

AUDIT = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_routing_input_v1_audit.json"
)

EXPECTED_SPLIT_WORKS = 17


def sha256_file(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def atomic_tsv(df, path):
    tmp = path.with_name(
        path.name + ".tmp"
    )

    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    os.replace(
        tmp,
        path,
    )


def atomic_json(obj, path):
    tmp = path.with_name(
        path.name + ".tmp"
    )

    tmp.write_text(
        json.dumps(
            obj,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    os.replace(
        tmp,
        path,
    )


def main():

    for p in [ADJ, EDITIONS]:
        if not p.exists():
            raise FileNotFoundError(p)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory already exists: {OUT_DIR}"
        )

    adj = pd.read_csv(
        ADJ,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    editions = pd.read_csv(
        EDITIONS,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    split = adj.loc[
        adj[
            "resolution_decision"
        ].eq("SPLIT")
    ].copy()

    if len(split) != EXPECTED_SPLIT_WORKS:
        raise RuntimeError(
            f"Expected {EXPECTED_SPLIT_WORKS} "
            f"SPLIT works; found {len(split)}"
        )

    if not split[
        "project_work_id"
    ].is_unique:
        raise RuntimeError(
            "Duplicate SPLIT project_work_id"
        )

    split_ids = set(
        split["project_work_id"]
    )

    z = editions.loc[
        editions[
            "project_work_id"
        ].isin(split_ids)
    ].copy()

    if set(
        z["project_work_id"]
    ) != split_ids:
        raise RuntimeError(
            "Some SPLIT project works have no "
            "edition evidence"
        )

    if not z[
        "edition_key"
    ].is_unique:
        dup = z.loc[
            z["edition_key"].duplicated(
                keep=False
            )
        ]

        raise RuntimeError(
            "Duplicate edition_key in SPLIT evidence:\n"
            + dup.to_string(index=False)
        )

    keep_adj = split[
        [
            "remediation_priority_rank",
            "project_work_id",
            "r2_target_title",
            "r2_target_author",
            "resolution_confidence",
            "resolution_plan",
            "resolution_note",
        ]
    ].copy()

    z = z.merge(
        keep_adj,
        on=[
            "project_work_id",
            "remediation_priority_rank",
        ],
        how="left",
        validate="many_to_one",
    )

    if z[
        "resolution_plan"
    ].eq("").any():
        raise RuntimeError(
            "Missing human resolution plan"
        )

    cols = [
        "remediation_priority_rank",
        "project_work_id",
        "r2_target_title",
        "r2_target_author",
        "current_ol_work_id",
        "edition_key",
        "edition_title",
        "edition_subtitle",
        "publish_date",
        "publishers",
        "edition_author_keys",
        "number_of_pages",
        "ocaid",
        "source_records",
        "retrieved_at_utc",
        "resolution_confidence",
        "resolution_plan",
        "resolution_note",
    ]

    z = z[cols].copy()

    z[
        "remediation_priority_rank"
    ] = pd.to_numeric(
        z[
            "remediation_priority_rank"
        ]
    )

    z = z.sort_values(
        [
            "remediation_priority_rank",
            "project_work_id",
            "publish_date",
            "edition_key",
        ],
        kind="stable",
    ).reset_index(drop=True)

    project_rows = []

    for project_work_id, g in z.groupby(
        "project_work_id",
        sort=False,
    ):
        first = g.iloc[0]

        project_rows.append({
            "remediation_priority_rank":
                int(
                    first[
                        "remediation_priority_rank"
                    ]
                ),

            "project_work_id":
                project_work_id,

            "r2_target_title":
                first[
                    "r2_target_title"
                ],

            "r2_target_author":
                first[
                    "r2_target_author"
                ],

            "current_ol_work_id":
                first[
                    "current_ol_work_id"
                ],

            "edition_rows":
                len(g),

            "resolution_confidence":
                first[
                    "resolution_confidence"
                ],

            "resolution_plan":
                first[
                    "resolution_plan"
                ],

            "resolution_note":
                first[
                    "resolution_note"
                ],
        })

    projects = pd.DataFrame(
        project_rows
    ).sort_values(
        "remediation_priority_rank",
        kind="stable",
    ).reset_index(drop=True)

    if len(projects) != EXPECTED_SPLIT_WORKS:
        raise RuntimeError(
            "Unexpected project count"
        )

    if int(
        projects[
            "edition_rows"
        ].sum()
    ) != len(z):
        raise RuntimeError(
            "Edition count aggregation mismatch"
        )

    OUT_DIR.mkdir(
        parents=True,
    )

    atomic_tsv(
        z,
        OUT_TSV,
    )

    atomic_tsv(
        projects,
        OUT_PROJECTS,
    )

    audit = {
        "status":
            "PASSED",

        "split_project_works":
            len(projects),

        "edition_rows":
            len(z),

        "unique_edition_keys":
            z[
                "edition_key"
            ].nunique(),

        "edition_rows_by_project":
            {
                row[
                    "project_work_id"
                ]:
                    int(
                        row[
                            "edition_rows"
                        ]
                    )
                for row
                in project_rows
            },

        "semantics": [
            (
                "This artifact is an LLM-routing input "
                "only; it does not assign successor "
                "project works."
            ),
            (
                "Human remediation resolution_plan is "
                "copied unchanged and will constrain "
                "edition routing."
            ),
            (
                "Edition publication dates are "
                "manifestation metadata and are not "
                "original-work scope decisions."
            ),
            (
                "Existing project-work candidate hits "
                "are deliberately absent from this "
                "routing input to avoid biasing the "
                "edition-level grouping."
            ),
        ],

        "inputs": {
            str(
                ADJ.relative_to(ROOT)
            ):
                sha256_file(ADJ),

            str(
                EDITIONS.relative_to(ROOT)
            ):
                sha256_file(EDITIONS),
        },

        "outputs": {
            OUT_TSV.name:
                sha256_file(OUT_TSV),

            OUT_PROJECTS.name:
                sha256_file(OUT_PROJECTS),
        },
    }

    atomic_json(
        audit,
        AUDIT,
    )

    print(
        "=== SPLIT EDITION ROUTING INPUT V1 ==="
    )
    print(
        "split project works:",
        len(projects),
    )
    print(
        "edition rows:",
        len(z),
    )
    print(
        "unique edition keys:",
        z["edition_key"].nunique(),
    )

    print()
    print(
        projects[
            [
                "remediation_priority_rank",
                "project_work_id",
                "r2_target_title",
                "edition_rows",
            ]
        ].to_string(
            index=False
        )
    )

    print()
    print("QC STATUS: PASSED")


if __name__ == "__main__":
    main()
