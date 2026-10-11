#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

QUEUE = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_remediation_queue_v1"
    / "openlibrary_r2a1_target_identity_remediation_queue_v1.tsv"
)

SOURCE_IMPACT = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_pair_impact_v1"
    / "openlibrary_r2a1_target_identity_pair_impact_source_record_v1.tsv"
)

API_SUMMARY = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_diagnostic_v1"
    / "openlibrary_r2a1_target_identity_current_api_summary_v1.tsv"
)

API_EDITIONS = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_diagnostic_v1"
    / "openlibrary_r2a1_target_identity_current_api_editions_v1.tsv"
)

OUT_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_remediation_evidence_v1"
)

PROJECT_OUT = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_remediation_project_evidence_v1.tsv"
)

SOURCE_OUT = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_remediation_source_evidence_v1.tsv"
)

EDITIONS_OUT = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_remediation_edition_evidence_v1.tsv"
)

AUDIT = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_remediation_evidence_v1_audit.json"
)

MANIFEST = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_remediation_evidence_v1_manifest.json"
)

RELEASE = (
    "openlibrary-r2a1-target-identity-remediation-evidence-v1"
)

EXPECTED_PROJECTS = 24
EXPECTED_OL_RECORDS = 25
EXPECTED_EDITION_ROWS = 545
EXPECTED_HUMAN_REVIEWED_OL_RECORDS = 11
EXPECTED_PAIR_MASS = 72_914


def sha256_file(path):
    h = hashlib.sha256()

    with Path(path).open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def atomic_tsv(df, path):
    tmp = path.with_name(path.name + ".tmp")

    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    os.replace(tmp, path)


def atomic_json(obj, path):
    tmp = path.with_name(path.name + ".tmp")

    tmp.write_text(
        json.dumps(
            obj,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    os.replace(tmp, path)


def main():

    for p in [
        QUEUE,
        SOURCE_IMPACT,
        API_SUMMARY,
        API_EDITIONS,
    ]:
        if not p.exists():
            raise FileNotFoundError(p)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory already exists: {OUT_DIR}"
        )

    queue = pd.read_csv(
        QUEUE,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    source = pd.read_csv(
        SOURCE_IMPACT,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    summary = pd.read_csv(
        API_SUMMARY,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    editions = pd.read_csv(
        API_EDITIONS,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    if len(queue) != EXPECTED_PROJECTS:
        raise RuntimeError(
            f"Expected {EXPECTED_PROJECTS} queue rows; "
            f"found {len(queue)}"
        )

    if not queue["project_work_id"].is_unique:
        raise RuntimeError(
            "Queue project_work_id is not unique"
        )

    queue["pair_count"] = pd.to_numeric(
        queue["pair_count"],
        errors="raise",
    )

    pair_mass = int(
        queue["pair_count"].sum()
    )

    if pair_mass != EXPECTED_PAIR_MASS:
        raise RuntimeError(
            f"Queue pair mass {pair_mass}; "
            f"expected {EXPECTED_PAIR_MASS}"
        )

    project_ids = set(
        queue["project_work_id"]
    )

    selected_source = (
        source.loc[
            source["project_work_id"].isin(
                project_ids
            )
        ]
        .copy()
    )

    selected_summary = (
        summary.loc[
            summary["project_work_id"].isin(
                project_ids
            )
        ]
        .copy()
    )

    selected_editions = (
        editions.loc[
            editions["project_work_id"].isin(
                project_ids
            )
        ]
        .copy()
    )

    if len(selected_source) != EXPECTED_OL_RECORDS:
        raise RuntimeError(
            f"Expected {EXPECTED_OL_RECORDS} source rows; "
            f"found {len(selected_source)}"
        )

    if len(selected_summary) != EXPECTED_OL_RECORDS:
        raise RuntimeError(
            f"Expected {EXPECTED_OL_RECORDS} API summary rows; "
            f"found {len(selected_summary)}"
        )

    if len(selected_editions) != EXPECTED_EDITION_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_EDITION_ROWS} edition rows; "
            f"found {len(selected_editions)}"
        )

    if not selected_source[
        "current_ol_work_id"
    ].is_unique:
        raise RuntimeError(
            "Selected source evidence is not unique by OL Work"
        )

    if not selected_summary[
        "current_ol_work_id"
    ].is_unique:
        raise RuntimeError(
            "Selected API summary is not unique by OL Work"
        )

    source_ids = set(
        selected_source[
            "current_ol_work_id"
        ]
    )

    summary_ids = set(
        selected_summary[
            "current_ol_work_id"
        ]
    )

    edition_ids = set(
        selected_editions[
            "current_ol_work_id"
        ]
    )

    if source_ids != summary_ids:
        raise RuntimeError(
            "Source/API-summary OL Work sets differ"
        )

    if edition_ids != source_ids:
        raise RuntimeError(
            "Edition/API-summary OL Work sets differ"
        )

    # --------------------------------------------------
    # Project-level evidence: exactly the frozen queue.
    # No resolution decision is made here.
    # --------------------------------------------------

    project_out = queue.copy()

    project_out = project_out.sort_values(
        "remediation_priority_rank",
        key=lambda s: pd.to_numeric(
            s,
            errors="raise",
        ),
    )

    # --------------------------------------------------
    # Source-record evidence:
    # pair-impact/LLM/human fields + current API metadata.
    # --------------------------------------------------

    api_fields = [
        "current_ol_work_id",
        "api_status",
        "current_work_key",
        "current_work_title",
        "current_work_description",
        "current_work_first_publish_date",
        "current_work_subjects",
        "edition_total_reported",
        "edition_rows_fetched",
        "distinct_edition_titles",
        "edition_titles",
        "edition_subtitles",
        "edition_publish_dates",
        "edition_publishers",
        "work_json_sha256",
        "api_final_url",
        "retrieved_at_utc",
    ]

    source_out = selected_source.merge(
        selected_summary[
            api_fields
        ],
        on="current_ol_work_id",
        how="left",
        validate="one_to_one",
    )

    project_rank = dict(
        zip(
            queue["project_work_id"],
            pd.to_numeric(
                queue[
                    "remediation_priority_rank"
                ],
                errors="raise",
            ),
        )
    )

    source_out[
        "remediation_priority_rank"
    ] = source_out[
        "project_work_id"
    ].map(
        project_rank
    )

    source_out = source_out.sort_values(
        [
            "remediation_priority_rank",
            "current_ol_work_id",
        ]
    )

    # --------------------------------------------------
    # Edition evidence.
    # --------------------------------------------------

    selected_editions[
        "remediation_priority_rank"
    ] = selected_editions[
        "project_work_id"
    ].map(
        project_rank
    )

    edition_out = selected_editions.sort_values(
        [
            "remediation_priority_rank",
            "project_work_id",
            "current_ol_work_id",
            "publish_date",
            "edition_key",
        ],
        kind="stable",
    )

    human_reviewed_n = int(
        source_out[
            "human_reviewed"
        ].astype(str).str.lower().eq(
            "true"
        ).sum()
    )

    if (
        human_reviewed_n
        != EXPECTED_HUMAN_REVIEWED_OL_RECORDS
    ):
        raise RuntimeError(
            f"Expected "
            f"{EXPECTED_HUMAN_REVIEWED_OL_RECORDS} "
            f"human-reviewed OL records; "
            f"found {human_reviewed_n}"
        )

    multi_ol = (
        source_out.groupby(
            "project_work_id"
        )[
            "current_ol_work_id"
        ]
        .nunique()
    )

    multi_ol = multi_ol[
        multi_ol.gt(1)
    ]

    if (
        len(multi_ol) != 1
        or multi_ol.index[0]
        != "W000031690"
        or int(multi_ol.iloc[0]) != 2
    ):
        raise RuntimeError(
            "Unexpected multi-OL project structure"
        )

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=False,
    )

    atomic_tsv(
        project_out,
        PROJECT_OUT,
    )

    atomic_tsv(
        source_out,
        SOURCE_OUT,
    )

    atomic_tsv(
        edition_out,
        EDITIONS_OUT,
    )

    audit = {
        "release":
            RELEASE,

        "qc_status":
            "PASSED",

        "project_works":
            len(project_out),

        "source_ol_records":
            len(source_out),

        "edition_rows":
            len(edition_out),

        "human_reviewed_ol_records":
            human_reviewed_n,

        "queue_pair_mass":
            pair_mass,

        "multi_ol_projects": {
            str(k): int(v)
            for k, v in multi_ol.items()
        },

        "all_queue_projects_have_source_evidence":
            (
                set(
                    project_out[
                        "project_work_id"
                    ]
                )
                ==
                set(
                    source_out[
                        "project_work_id"
                    ]
                )
            ),

        "all_source_records_have_edition_evidence":
            (
                source_ids
                ==
                edition_ids
            ),
    }

    atomic_json(
        audit,
        AUDIT,
    )

    manifest = {
        "release":
            RELEASE,

        "status":
            "frozen_evidence_packet_candidate",

        "purpose":
            (
                "Freeze the evidence packet for "
                "project-level remediation decisions "
                "on the 24-work target-identity queue."
            ),

        "inputs": {
            str(
                QUEUE.relative_to(ROOT)
            ):
                sha256_file(QUEUE),

            str(
                SOURCE_IMPACT.relative_to(ROOT)
            ):
                sha256_file(SOURCE_IMPACT),

            str(
                API_SUMMARY.relative_to(ROOT)
            ):
                sha256_file(API_SUMMARY),

            str(
                API_EDITIONS.relative_to(ROOT)
            ):
                sha256_file(API_EDITIONS),
        },

        "outputs": {
            str(
                PROJECT_OUT.relative_to(ROOT)
            ):
                sha256_file(PROJECT_OUT),

            str(
                SOURCE_OUT.relative_to(ROOT)
            ):
                sha256_file(SOURCE_OUT),

            str(
                EDITIONS_OUT.relative_to(ROOT)
            ):
                sha256_file(EDITIONS_OUT),

            str(
                AUDIT.relative_to(ROOT)
            ):
                sha256_file(AUDIT),
        },

        "semantics": [
            (
                "This artifact freezes evidence only; "
                "it does not encode remediation decisions."
            ),
            (
                "Pair counts and priority ranks describe "
                "retrieval impact and prioritization. "
                "They are not identity evidence."
            ),
            (
                "Current Open Library API metadata is "
                "diagnostic evidence retrieved on "
                "2026-10-11 and does not replace the "
                "frozen 2026-02-28 source population."
            ),
            (
                "LLM and prior human judgments are "
                "included as provenance/evidence, but "
                "the final remediation decision remains "
                "a separate project-level assertion."
            ),
            (
                "Temporal, language, and fiction-scope "
                "eligibility remain outside this "
                "identity-remediation evidence packet."
            ),
        ],
    }

    atomic_json(
        manifest,
        MANIFEST,
    )

    print(
        "=== OL TARGET IDENTITY REMEDIATION EVIDENCE V1 ==="
    )

    print(
        "project works:",
        len(project_out),
    )

    print(
        "source OL records:",
        len(source_out),
    )

    print(
        "edition rows:",
        len(edition_out),
    )

    print(
        "human-reviewed OL records:",
        human_reviewed_n,
    )

    print(
        "queue pair mass:",
        pair_mass,
    )

    print(
        "multi-OL projects:",
        {
            str(k): int(v)
            for k, v in multi_ol.items()
        },
    )

    print(
        "QC STATUS: PASSED"
    )


if __name__ == "__main__":
    main()
