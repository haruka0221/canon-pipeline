#!/usr/bin/env python3

"""
Build the source-native Open Library author layer for the current
34,789 analysis targets.

Important semantics
-------------------
- Current target identity comes from:
    derived/identity/openlibrary_analysis_targets_v1.parquet
- Work -> Author edges are re-extracted directly from the fixed
  Open Library Works dump dated 2026-02-28.
- Author records and names are extracted directly from the fixed
  Open Library Authors dump dated 2026-02-28.
- Historical population author_keys / author_name columns are NOT used
  as the source of truth for this release.
- No query-author selection is performed here.
- No assumption is made that every entry in Open Library Work.authors
  is the original literary author.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

import pandas as pd
import pyarrow as pa


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TARGETS = (
    ROOT
    / "derived/identity/openlibrary_analysis_targets_v1.parquet"
)

DEFAULT_OUT_DIR = (
    ROOT
    / "derived/openlibrary_author_source_v1"
)

RELEASE = "openlibrary-author-source-v1"
CREATED_AT = "2026-09-28"
SNAPSHOT_DATE = "2026-02-28"

EXPECTED_TARGET_ROWS = 34789

EXPECTED_TARGETS_SHA256 = (
    "7200fe0721a2a112da8351aea2561914"
    "c71322ccac45764d97c425ef5046ff21"
)

EXPECTED_WORKS_SHA256 = (
    "a4714480bd20a7ad41538653d69ed43a"
    "012efecfba57cd5194edb2768cfc26ad"
)

EXPECTED_AUTHORS_SHA256 = (
    "9e28a45c3db56f7d89eceaa01024865b"
    "acc458c84fc83d29044f6897987a363d"
)

WORKS_SOURCE_URL = (
    "https://archive.org/download/ol_dump_2026-02-28/"
    "ol_dump_works_2026-02-28.txt.gz"
)

AUTHORS_SOURCE_URL = (
    "https://archive.org/download/ol_dump_2026-02-28/"
    "ol_dump_authors_2026-02-28.txt.gz"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)

    return h.hexdigest()


def require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)


def git_capture(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        return ""

    return result.stdout.strip()


def scalar_text(value) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
    )


def as_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def author_key_from_entry(entry) -> str:
    if not isinstance(entry, dict):
        return ""

    author = entry.get("author")

    if isinstance(author, dict):
        key = author.get("key")
        return key if isinstance(key, str) else ""

    return ""


def role_key_from_entry(entry) -> str:
    if not isinstance(entry, dict):
        return ""

    value = entry.get("type")

    if isinstance(value, dict):
        key = value.get("key")
        return key if isinstance(key, str) else ""

    if isinstance(value, str):
        return value

    return ""


def write_atomic_tsv(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")

    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    os.replace(tmp, path)


def write_atomic_parquet(
    df: pd.DataFrame,
    path: Path,
) -> None:
    tmp = path.with_name(path.name + ".tmp")

    df.to_parquet(
        tmp,
        index=False,
        engine="pyarrow",
    )

    os.replace(tmp, path)


def write_json_atomic(obj, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")

    tmp.write_text(
        json.dumps(
            obj,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    os.replace(tmp, path)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--works-dump",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--authors-dump",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--targets",
        type=Path,
        default=DEFAULT_TARGETS,
    )

    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
    )

    args = parser.parse_args()

    works_dump = args.works_dump.resolve()
    authors_dump = args.authors_dump.resolve()
    targets_path = args.targets.resolve()
    out_dir = args.out_dir.resolve()

    for path in [
        works_dump,
        authors_dump,
        targets_path,
    ]:
        require(path)

    run_started_at_utc = datetime.now(
        timezone.utc
    ).isoformat()

    script_path = Path(__file__).resolve()

    git_status_at_start = git_capture(
        "status",
        "--porcelain",
    )

    execution_metadata = {
        "run_started_at_utc":
            run_started_at_utc,
        "execution_worktree":
            str(ROOT),
        "builder_script":
            str(script_path.relative_to(ROOT)),
        "builder_script_sha256":
            sha256_file(script_path),
        "builder_git_commit":
            git_capture("rev-parse", "HEAD"),
        "builder_git_branch":
            (
                git_capture(
                    "branch",
                    "--show-current",
                )
                or "(detached)"
            ),
        "git_clean_at_start":
            git_status_at_start == "",
        "python_executable":
            sys.executable,
        "python_version":
            platform.python_version(),
        "pandas_version":
            pd.__version__,
        "pyarrow_version":
            pa.__version__,
        "argv":
            [
                sys.executable,
                *sys.argv,
            ],
    }

    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ---------------------------------------------------------
    # 1. Verify fixed inputs
    # ---------------------------------------------------------

    print("=== INPUT SHA256 ===", flush=True)

    targets_sha = sha256_file(targets_path)
    print("targets:", targets_sha, flush=True)

    if targets_sha != EXPECTED_TARGETS_SHA256:
        raise RuntimeError(
            "openlibrary_analysis_targets_v1 SHA256 mismatch"
        )

    works_sha = sha256_file(works_dump)
    print("works:", works_sha, flush=True)

    if works_sha != EXPECTED_WORKS_SHA256:
        raise RuntimeError(
            "Open Library Works dump SHA256 mismatch"
        )

    authors_sha = sha256_file(authors_dump)
    print("authors:", authors_sha, flush=True)

    if authors_sha != EXPECTED_AUTHORS_SHA256:
        raise RuntimeError(
            "Open Library Authors dump SHA256 mismatch"
        )

    # ---------------------------------------------------------
    # 2. Current analysis targets
    # ---------------------------------------------------------

    targets = (
        pd.read_parquet(targets_path)
        .fillna("")
        .astype(str)
    )

    if len(targets) != EXPECTED_TARGET_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_TARGET_ROWS} targets; "
            f"found {len(targets)}"
        )

    if not targets["current_ol_work_id"].is_unique:
        raise RuntimeError(
            "current_ol_work_id is not unique"
        )

    if not targets["current_entity_id"].is_unique:
        raise RuntimeError(
            "current_entity_id is not unique"
        )

    target_order = {
        work_id: i
        for i, work_id in enumerate(
            targets["current_ol_work_id"]
        )
    }

    target_by_work_key = {}

    for row in targets.to_dict("records"):
        work_id = row["current_ol_work_id"]
        work_key = f"/works/{work_id}"

        target_by_work_key[work_key] = row

    # ---------------------------------------------------------
    # 3. Re-extract current Work records + Work -> Author edges
    # ---------------------------------------------------------

    print(
        "\n=== SCANNING FIXED WORKS DUMP ===",
        flush=True,
    )

    work_records_by_id = {}
    work_author_rows = []

    with gzip.open(
        works_dump,
        "rt",
        encoding="utf-8",
    ) as f:
        for line_no, line in enumerate(f, 1):
            if line_no % 2_000_000 == 0:
                print(
                    f"works scanned: {line_no:,}; "
                    f"targets found: "
                    f"{len(work_records_by_id):,}",
                    flush=True,
                )

            parts = (
                line.rstrip("\n")
                .split("\t", 4)
            )

            if len(parts) < 5:
                continue

            work_key = parts[1]

            target = target_by_work_key.get(work_key)

            if target is None:
                continue

            work_id = target["current_ol_work_id"]

            if work_id in work_records_by_id:
                raise RuntimeError(
                    f"Duplicate Work record in dump: {work_key}"
                )

            try:
                rec = json.loads(parts[4])
            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"Invalid JSON for target {work_key}"
                ) from e

            author_entries = rec.get("authors")

            if not isinstance(author_entries, list):
                author_entries = []

            keyed_author_count = 0

            for ordinal, entry in enumerate(
                author_entries
            ):
                author_key = (
                    author_key_from_entry(entry)
                )

                if author_key:
                    keyed_author_count += 1

                author_id = (
                    author_key
                    .replace("/authors/", "", 1)
                    if author_key.startswith("/authors/")
                    else author_key
                )

                work_author_rows.append({
                    "current_entity_id":
                        target["current_entity_id"],
                    "current_ol_work_id":
                        work_id,
                    "work_source_key":
                        work_key,
                    "target_resolution":
                        target["target_resolution"],
                    "work_source_snapshot":
                        SNAPSHOT_DATE,
                    "work_source_artifact":
                        works_dump.name,
                    "author_ordinal":
                        ordinal,
                    "author_source_key":
                        author_key,
                    "author_source_id":
                        author_id,
                    "author_role_key":
                        role_key_from_entry(entry),
                    "author_entry_json":
                        json.dumps(
                            entry,
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    "author_edge_parse_status":
                        (
                            "author_key_present"
                            if author_key
                            else "author_key_missing"
                        ),
                })

            work_records_by_id[work_id] = {
                "current_entity_id":
                    target["current_entity_id"],
                "current_ol_work_id":
                    work_id,
                "work_source_key":
                    work_key,
                "target_resolution":
                    target["target_resolution"],
                "work_source_snapshot":
                    SNAPSHOT_DATE,
                "work_source_artifact":
                    works_dump.name,
                "source_title":
                    scalar_text(rec.get("title")),
                "source_subtitle":
                    scalar_text(rec.get("subtitle")),
                "source_first_publish_date":
                    scalar_text(
                        rec.get("first_publish_date")
                    ),
                "source_revision":
                    scalar_text(rec.get("revision")),
                "source_latest_revision":
                    scalar_text(
                        rec.get("latest_revision")
                    ),
                "source_created":
                    scalar_text(rec.get("created")),
                "source_last_modified":
                    scalar_text(
                        rec.get("last_modified")
                    ),
                "author_entry_count":
                    len(author_entries),
                "author_key_count":
                    keyed_author_count,
            }

            if (
                len(work_records_by_id)
                == EXPECTED_TARGET_ROWS
            ):
                break

    missing_work_ids = [
        work_id
        for work_id in targets["current_ol_work_id"]
        if work_id not in work_records_by_id
    ]

    if missing_work_ids:
        raise RuntimeError(
            "Current target Works missing from fixed dump: "
            f"{len(missing_work_ids)}; "
            f"examples={missing_work_ids[:20]}"
        )

    work_records = pd.DataFrame(
        [
            work_records_by_id[work_id]
            for work_id in targets["current_ol_work_id"]
        ]
    )

    work_authors = pd.DataFrame(work_author_rows)

    if len(work_authors):
        work_authors["_target_order"] = (
            work_authors["current_ol_work_id"]
            .map(target_order)
        )

        work_authors = (
            work_authors
            .sort_values(
                [
                    "_target_order",
                    "author_ordinal",
                ],
                kind="stable",
            )
            .drop(columns=["_target_order"])
            .reset_index(drop=True)
        )

    author_keys = sorted(
        {
            x
            for x in work_authors.get(
                "author_source_key",
                pd.Series(dtype=str),
            )
            if isinstance(x, str) and x
        }
    )

    # ---------------------------------------------------------
    # 4. Extract referenced Author records
    # ---------------------------------------------------------

    print(
        "\n=== SCANNING FIXED AUTHORS DUMP ===",
        flush=True,
    )

    wanted_author_keys = set(author_keys)

    author_records = {}
    author_name_rows = []

    with gzip.open(
        authors_dump,
        "rt",
        encoding="utf-8",
    ) as f:
        for line_no, line in enumerate(f, 1):
            if line_no % 2_000_000 == 0:
                print(
                    f"authors scanned: {line_no:,}; "
                    f"records found: "
                    f"{len(author_records):,}/"
                    f"{len(wanted_author_keys):,}",
                    flush=True,
                )

            parts = (
                line.rstrip("\n")
                .split("\t", 4)
            )

            if len(parts) < 5:
                continue

            author_key = parts[1]

            if author_key not in wanted_author_keys:
                continue

            if author_key in author_records:
                raise RuntimeError(
                    "Duplicate Author record in dump: "
                    f"{author_key}"
                )

            try:
                rec = json.loads(parts[4])
            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"Invalid JSON for author {author_key}"
                ) from e

            author_id = (
                author_key
                .replace("/authors/", "", 1)
                if author_key.startswith("/authors/")
                else author_key
            )

            author_records[author_key] = {
                "author_source_key":
                    author_key,
                "author_source_id":
                    author_id,
                "author_source_snapshot":
                    SNAPSHOT_DATE,
                "author_source_artifact":
                    authors_dump.name,
                "name":
                    scalar_text(rec.get("name")),
                "personal_name":
                    scalar_text(
                        rec.get("personal_name")
                    ),
                "fuller_name":
                    scalar_text(
                        rec.get("fuller_name")
                    ),
                "title":
                    scalar_text(rec.get("title")),
                "birth_date":
                    scalar_text(
                        rec.get("birth_date")
                    ),
                "death_date":
                    scalar_text(
                        rec.get("death_date")
                    ),
                "created":
                    scalar_text(rec.get("created")),
                "last_modified":
                    scalar_text(
                        rec.get("last_modified")
                    ),
                "revision":
                    scalar_text(rec.get("revision")),
                "latest_revision":
                    scalar_text(
                        rec.get("latest_revision")
                    ),
                "remote_ids_json":
                    json.dumps(
                        rec.get("remote_ids", {}),
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                "source_records_json":
                    json.dumps(
                        as_list(
                            rec.get("source_records")
                        ),
                        ensure_ascii=False,
                    ),
            }

            for name_type in [
                "name",
                "personal_name",
                "fuller_name",
            ]:
                value = rec.get(name_type)

                if isinstance(value, str) and value:
                    author_name_rows.append({
                        "author_source_key":
                            author_key,
                        "author_source_id":
                            author_id,
                        "name_type":
                            name_type,
                        "ordinal":
                            0,
                        "name_value":
                            value,
                        "author_source_snapshot":
                            SNAPSHOT_DATE,
                        "author_source_artifact":
                            authors_dump.name,
                    })

            for ordinal, value in enumerate(
                as_list(rec.get("alternate_names"))
            ):
                if value is None:
                    continue

                value = str(value)

                if not value:
                    continue

                author_name_rows.append({
                    "author_source_key":
                        author_key,
                    "author_source_id":
                        author_id,
                    "name_type":
                        "alternate_name",
                    "ordinal":
                        ordinal,
                    "name_value":
                        value,
                    "author_source_snapshot":
                        SNAPSHOT_DATE,
                    "author_source_artifact":
                        authors_dump.name,
                })

            if (
                len(author_records)
                == len(wanted_author_keys)
            ):
                break

    found_author_keys = set(author_records)
    missing_author_keys = sorted(
        wanted_author_keys - found_author_keys
    )

    author_records_df = pd.DataFrame(
        [
            author_records[key]
            for key in sorted(author_records)
        ]
    )

    author_names_df = pd.DataFrame(
        author_name_rows
    )

    if len(author_names_df):
        name_type_order = {
            "name": 0,
            "personal_name": 1,
            "fuller_name": 2,
            "alternate_name": 3,
        }

        author_names_df["_type_order"] = (
            author_names_df["name_type"]
            .map(name_type_order)
            .fillna(99)
        )

        author_names_df = (
            author_names_df
            .sort_values(
                [
                    "author_source_id",
                    "_type_order",
                    "ordinal",
                    "name_value",
                ],
                kind="stable",
            )
            .drop(columns=["_type_order"])
            .reset_index(drop=True)
        )

    missing_rows = []

    for author_key in missing_author_keys:
        author_id = (
            author_key
            .replace("/authors/", "", 1)
            if author_key.startswith("/authors/")
            else author_key
        )

        linked = work_authors[
            work_authors["author_source_key"]
            .eq(author_key)
        ]

        for row in linked.to_dict("records"):
            missing_rows.append({
                "author_source_key":
                    author_key,
                "author_source_id":
                    author_id,
                "current_entity_id":
                    row["current_entity_id"],
                "current_ol_work_id":
                    row["current_ol_work_id"],
                "author_ordinal":
                    row["author_ordinal"],
                "status":
                    (
                        "AUTHOR_RECORD_NOT_FOUND_IN_"
                        "2026_02_28_AUTHORS_DUMP"
                    ),
            })

    missing_authors_df = pd.DataFrame(
        missing_rows,
        columns=[
            "author_source_key",
            "author_source_id",
            "current_entity_id",
            "current_ol_work_id",
            "author_ordinal",
            "status",
        ],
    )

    work_authors[
        "author_record_found_in_snapshot"
    ] = (
        work_authors["author_source_key"]
        .isin(found_author_keys)
    )

    # Missing key inside a Work author entry is not equivalent
    # to a missing Author record.
    work_authors.loc[
        work_authors["author_source_key"].eq(""),
        "author_record_found_in_snapshot",
    ] = False

    # ---------------------------------------------------------
    # 5. Diagnostics
    # ---------------------------------------------------------

    targets_without_author_edges = int(
        (work_records["author_entry_count"] == 0)
        .sum()
    )

    targets_with_multiple_author_edges = int(
        (work_records["author_entry_count"] > 1)
        .sum()
    )

    print("\n=== SUMMARY ===", flush=True)
    print(
        "current targets:",
        len(work_records),
        flush=True,
    )
    print(
        "work-author edges:",
        len(work_authors),
        flush=True,
    )
    print(
        "unique referenced author IDs:",
        len(wanted_author_keys),
        flush=True,
    )
    print(
        "author records found:",
        len(found_author_keys),
        flush=True,
    )
    print(
        "author records missing:",
        len(missing_author_keys),
        flush=True,
    )
    print(
        "author name evidence rows:",
        len(author_names_df),
        flush=True,
    )
    print(
        "targets without author entries:",
        targets_without_author_edges,
        flush=True,
    )
    print(
        "targets with >1 author entry:",
        targets_with_multiple_author_edges,
        flush=True,
    )

    if missing_author_keys:
        print(
            "\nMissing author IDs:",
            *missing_author_keys[:30],
            sep="\n  ",
            flush=True,
        )

    print(
        "\n=== NAME FIELD COVERAGE ===",
        flush=True,
    )

    for column in [
        "name",
        "personal_name",
        "fuller_name",
    ]:
        count = int(
            author_records_df[column]
            .astype(str)
            .ne("")
            .sum()
        )

        print(
            f"{column}: "
            f"{count:,}/"
            f"{len(author_records_df):,}",
            flush=True,
        )

    # ---------------------------------------------------------
    # 6. Write versioned outputs
    # ---------------------------------------------------------

    outputs = {
        "work_records_tsv":
            out_dir
            / "openlibrary_current_work_records_v1.tsv",
        "work_records_parquet":
            out_dir
            / "openlibrary_current_work_records_v1.parquet",
        "work_authors_tsv":
            out_dir
            / "openlibrary_current_work_authors_v1.tsv",
        "work_authors_parquet":
            out_dir
            / "openlibrary_current_work_authors_v1.parquet",
        "author_records_tsv":
            out_dir
            / "openlibrary_author_records_v1.tsv",
        "author_records_parquet":
            out_dir
            / "openlibrary_author_records_v1.parquet",
        "author_names_tsv":
            out_dir
            / "openlibrary_author_names_v1.tsv",
        "author_names_parquet":
            out_dir
            / "openlibrary_author_names_v1.parquet",
        "missing_authors_tsv":
            out_dir
            / "openlibrary_missing_authors_v1.tsv",
        "missing_authors_parquet":
            out_dir
            / "openlibrary_missing_authors_v1.parquet",
    }

    write_atomic_tsv(
        work_records,
        outputs["work_records_tsv"],
    )
    write_atomic_parquet(
        work_records,
        outputs["work_records_parquet"],
    )

    write_atomic_tsv(
        work_authors,
        outputs["work_authors_tsv"],
    )
    write_atomic_parquet(
        work_authors,
        outputs["work_authors_parquet"],
    )

    write_atomic_tsv(
        author_records_df,
        outputs["author_records_tsv"],
    )
    write_atomic_parquet(
        author_records_df,
        outputs["author_records_parquet"],
    )

    write_atomic_tsv(
        author_names_df,
        outputs["author_names_tsv"],
    )
    write_atomic_parquet(
        author_names_df,
        outputs["author_names_parquet"],
    )

    write_atomic_tsv(
        missing_authors_df,
        outputs["missing_authors_tsv"],
    )
    write_atomic_parquet(
        missing_authors_df,
        outputs["missing_authors_parquet"],
    )

    # ---------------------------------------------------------
    # 7. Manifest
    # ---------------------------------------------------------

    execution_metadata[
        "run_finished_at_utc"
    ] = datetime.now(
        timezone.utc
    ).isoformat()

    manifest = {
        "release": RELEASE,
        "created_at": CREATED_AT,
        "execution": execution_metadata,
        "semantics": {
            "current_target_source": (
                "Current Open Library analysis targets from "
                "openlibrary_analysis_targets_v1."
            ),
            "work_author_edges": (
                "Source-native Work.authors entries re-extracted "
                "from the fixed 2026-02-28 Open Library Works dump."
            ),
            "author_records": (
                "Source-native Open Library Author records referenced "
                "by current Work.author edges and extracted from the "
                "fixed 2026-02-28 Authors dump."
            ),
            "important_note": (
                "Open Library Work.authors entries are preserved as "
                "source evidence and are not assumed to be equivalent "
                "to original literary authorship. No query-author "
                "selection is performed in this release."
            ),
        },
        "inputs": {
            "analysis_targets": {
                "artifact": (
                    "derived/identity/"
                    "openlibrary_analysis_targets_v1.parquet"
                ),
                "rows": len(targets),
                "sha256": targets_sha,
            },
            "works_dump": {
                "snapshot_date": SNAPSHOT_DATE,
                "source_url": WORKS_SOURCE_URL,
                "local_path_at_run": str(works_dump),
                "size_bytes": works_dump.stat().st_size,
                "sha256": works_sha,
                "provenance_manifest": (
                    "derived/"
                    "openlibrary_dump_reacquisition_"
                    "20260928_manifest.json"
                ),
            },
            "authors_dump": {
                "snapshot_date": SNAPSHOT_DATE,
                "source_url": AUTHORS_SOURCE_URL,
                "local_path_at_run": str(authors_dump),
                "size_bytes": authors_dump.stat().st_size,
                "sha256": authors_sha,
                "provenance_manifest": (
                    "derived/"
                    "openlibrary_authors_dump_reacquisition_"
                    "20260928_manifest.json"
                ),
            },
        },
        "counts": {
            "current_targets":
                len(work_records),
            "work_author_edges":
                len(work_authors),
            "unique_referenced_author_ids":
                len(wanted_author_keys),
            "author_records_found":
                len(found_author_keys),
            "author_records_missing":
                len(missing_author_keys),
            "author_name_evidence_rows":
                len(author_names_df),
            "targets_without_author_entries":
                targets_without_author_edges,
            "targets_with_multiple_author_entries":
                targets_with_multiple_author_edges,
            "name_nonempty":
                int(
                    author_records_df["name"]
                    .astype(str)
                    .ne("")
                    .sum()
                ),
            "personal_name_nonempty":
                int(
                    author_records_df[
                        "personal_name"
                    ]
                    .astype(str)
                    .ne("")
                    .sum()
                ),
            "fuller_name_nonempty":
                int(
                    author_records_df[
                        "fuller_name"
                    ]
                    .astype(str)
                    .ne("")
                    .sum()
                ),
        },
        "outputs": {},
    }

    for name, path in outputs.items():
        manifest["outputs"][name] = {
            "artifact": str(
                path.relative_to(ROOT)
            ),
            "sha256": sha256_file(path),
        }

    manifest_path = (
        out_dir
        / "openlibrary_author_source_v1_manifest.json"
    )

    write_json_atomic(
        manifest,
        manifest_path,
    )

    print("\n=== OUTPUTS ===", flush=True)

    for path in outputs.values():
        print(
            path.relative_to(ROOT),
            flush=True,
        )

    print(
        manifest_path.relative_to(ROOT),
        flush=True,
    )


if __name__ == "__main__":
    main()
