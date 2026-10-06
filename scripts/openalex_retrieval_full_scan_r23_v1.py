#!/usr/bin/env python3

# Full frozen-snapshot scanner for OpenAlex R2/R3 retrieval.
#
# IMPORTANT:
# - R4 title-only retrieval is deliberately excluded.
# - Matching semantics are inherited unchanged from the
#   frozen calibration scanner / match-registry contract.
# - Raw evidence retains title hits even when author
#   conditions do not match.
# - query_id is release-local provenance only.

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from glob import glob
import argparse
import gzip
import hashlib
import json
import os
import time
import unicodedata

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]

MATCH_DIR = (
    ROOT
    / "derived/openalex_production/"
      "retrieval_match_registry_full_v1"
)

MATCH_REGISTRY = (
    MATCH_DIR
    / "openalex_retrieval_match_registry_full_v1.parquet"
)

MATCH_MANIFEST = (
    MATCH_DIR
    / "openalex_retrieval_match_registry_full_v1_manifest.json"
)

DEFAULT_SNAPSHOT_DIR = Path(
    "/media/hdd1/user/tsutsui/openalex/"
    "snapshots/release_20260923"
)

EXPECTED_FULL_REGISTRY_ROWS = 101706
EXPECTED_R23_ROWS = 66917
EXPECTED_R2_ROWS = 32489
EXPECTED_R3_ROWS = 34428
EXPECTED_R23_EXECUTIONS = 32237

EXPECTED_SNAPSHOT_FILE_COUNT = 2040
EXPECTED_SNAPSHOT_TOTAL_BYTES = 659026072445
EXPECTED_SNAPSHOT_INVENTORY_SHA256 = (
    "57959e90573d6ef2adb953fd747ba718"
    "54819880f762077f680083476d490fc9"
)

SCANNER_VERSION = "v1"
MATCHING_CONTRACT_VERSION = (
    "openalex_snapshot_title_abstract_token_phrase_v1"
)


EVIDENCE_SCHEMA = pa.schema([
    ("query_id", pa.string()),
    ("execution_id", pa.string()),
    ("target_lane", pa.string()),
    ("project_work_id", pa.string()),
    ("unresolved_unit_anchor_entity_id", pa.string()),
    ("alias_id", pa.string()),
    ("alias_project_source_entity_id", pa.string()),
    ("query_route", pa.string()),
    ("query_form", pa.string()),

    ("openalex_work_id", pa.string()),

    ("title_match_in_title", pa.bool_()),
    ("title_match_in_abstract", pa.bool_()),

    ("author_a1_in_title", pa.bool_()),
    ("author_a1_in_abstract", pa.bool_()),
    ("author_a1_hit", pa.bool_()),

    ("author_a2_reverse_in_title", pa.bool_()),
    ("author_a2_reverse_in_abstract", pa.bool_()),
    ("author_a2_reverse_hit", pa.bool_()),
    ("author_a2_hit", pa.bool_()),

    ("author_a3_in_title", pa.bool_()),
    ("author_a3_in_abstract", pa.bool_()),
    ("author_a3_hit", pa.bool_()),

    ("snapshot_source_file", pa.string()),
])


OA_RECORD_SCHEMA = pa.schema([
    ("openalex_work_id", pa.string()),
    ("openalex_id_url", pa.string()),
    ("snapshot_source_file", pa.string()),

    ("display_name", pa.string()),
    ("abstract", pa.string()),
    ("abstract_present", pa.bool_()),

    ("publication_year", pa.int64()),
    ("publication_date", pa.string()),
    ("type", pa.string()),
    ("language", pa.string()),
    ("doi", pa.string()),

    ("is_retracted", pa.bool_()),
    ("is_paratext", pa.bool_()),
    ("has_fulltext", pa.bool_()),

    ("primary_topic_id", pa.string()),
    ("primary_topic_name", pa.string()),
])


COUNT_COLUMNS = [
    "title_hit_count",
    "title_in_title_count",
    "title_in_abstract_count",
    "title_in_both_count",

    "a1_hit_count",
    "a1_in_title_count",
    "a1_in_abstract_count",

    "a2_hit_count",
    "a2_reverse_hit_count",
    "a2_incremental_over_a1_count",

    "a3_hit_count",
    "a3_in_title_count",
    "a3_in_abstract_count",
    "a3_incremental_over_a2_count",
]


def require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def match_tokens(value: str) -> str:
    """
    Must remain identical in semantics to
    retrieval_match_registry_v1.

    NFKC + casefold; Unicode letters/numbers/combining
    marks retained; other characters become token
    boundaries.
    """
    s = unicodedata.normalize(
        "NFKC",
        str(value or ""),
    ).casefold()

    chars = []

    for ch in s:
        cat = unicodedata.category(ch)

        if ch.isalnum() or cat.startswith("M"):
            chars.append(ch)
        else:
            chars.append(" ")

    return " ".join(
        "".join(chars).split()
    )


def reconstruct_abstract(
    inverted_index,
) -> str:
    """
    Reconstruct OpenAlex abstract_inverted_index in token
    position order.

    We need matching text and later human/LLM review text,
    so retain the reconstructed abstract rather than only
    the normalized representation.
    """
    if not isinstance(inverted_index, dict):
        return ""

    positioned = []

    for token, positions in inverted_index.items():
        if not isinstance(positions, list):
            continue

        for pos in positions:
            if isinstance(pos, int):
                positioned.append(
                    (pos, str(token))
                )

    if not positioned:
        return ""

    positioned.sort(
        key=lambda x: (
            x[0],
            x[1],
        )
    )

    return " ".join(
        token
        for _, token in positioned
    )


def normalize_openalex_id(
    value: str,
) -> str:
    value = str(value or "").strip()

    if not value:
        return ""

    return value.rstrip("/").split("/")[-1]


def build_automaton(patterns):
    try:
        import ahocorasick
    except ImportError as exc:
        raise RuntimeError(
            "pyahocorasick is required. "
            "Install it in the active environment first."
        ) from exc

    A = ahocorasick.Automaton()

    for pattern in sorted(set(patterns)):
        if not pattern:
            continue

        # Padding enforces whole-token phrase boundaries.
        needle = f" {pattern} "

        A.add_word(
            needle,
            pattern,
        )

    A.make_automaton()

    return A


def find_patterns(
    automaton,
    normalized_text: str,
) -> set[str]:
    if not normalized_text:
        return set()

    padded = f" {normalized_text} "

    return {
        pattern
        for _, pattern
        in automaton.iter(padded)
    }


def snapshot_inventory(
    snapshot_dir: Path,
):
    files = sorted(
        Path(x)
        for x in glob(
            str(
                snapshot_dir
                / "updated_date=*"
                / "part_*.gz"
            )
        )
    )

    if not files:
        raise RuntimeError(
            f"No snapshot files found under {snapshot_dir}"
        )

    records = []

    h = hashlib.sha256()

    total_bytes = 0
    dates = []

    for path in files:
        rel = path.relative_to(
            snapshot_dir
        ).as_posix()

        size = path.stat().st_size

        total_bytes += size

        parent = path.parent.name

        if parent.startswith("updated_date="):
            dates.append(
                parent.split("=", 1)[1]
            )

        line = f"{rel}\t{size}\n"

        h.update(
            line.encode("utf-8")
        )

        records.append(
            {
                "path": path,
                "relative_path": rel,
                "size": size,
            }
        )

    return {
        "files": files,
        "records": records,
        "file_count": len(files),
        "total_bytes": total_bytes,
        "inventory_sha256": h.hexdigest(),
        "updated_date_min": (
            min(dates)
            if dates
            else ""
        ),
        "updated_date_max": (
            max(dates)
            if dates
            else ""
        ),
    }


def evenly_spaced_files(
    files: list[Path],
    n: int,
) -> list[Path]:
    if n <= 0:
        raise ValueError(
            "smoke-files must be >= 1"
        )

    if n >= len(files):
        return files

    if n == 1:
        return [
            files[len(files) // 2]
        ]

    indices = []

    for i in range(n):
        idx = round(
            i
            * (len(files) - 1)
            / (n - 1)
        )

        indices.append(idx)

    # round() theoretically could duplicate an index.
    indices = sorted(set(indices))

    return [
        files[i]
        for i in indices
    ]


def subset_inventory_hash(
    snapshot_dir: Path,
    files: list[Path],
) -> str:
    h = hashlib.sha256()

    for path in files:
        rel = path.relative_to(
            snapshot_dir
        ).as_posix()

        size = path.stat().st_size

        h.update(
            f"{rel}\t{size}\n"
            .encode("utf-8")
        )

    return h.hexdigest()


class BufferedParquetWriter:
    def __init__(
        self,
        path: Path,
        schema: pa.Schema,
        batch_size: int = 50000,
    ):
        self.path = path
        self.schema = schema
        self.batch_size = batch_size

        self.buffer = []
        self.writer = None
        self.row_count = 0

    def append(self, row: dict) -> None:
        self.buffer.append(row)

        if len(self.buffer) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        if not self.buffer:
            return

        table = pa.Table.from_pylist(
            self.buffer,
            schema=self.schema,
        )

        if self.writer is None:
            self.writer = pq.ParquetWriter(
                self.path,
                self.schema,
                compression="zstd",
            )

        self.writer.write_table(
            table
        )

        self.row_count += len(
            self.buffer
        )

        self.buffer.clear()

    def close(self) -> None:
        self.flush()

        if self.writer is not None:
            self.writer.close()
            return

        # Produce a valid empty parquet file.
        table = pa.Table.from_pylist(
            [],
            schema=self.schema,
        )

        pq.write_table(
            table,
            self.path,
            compression="zstd",
        )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=DEFAULT_SNAPSHOT_DIR,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )

    mode = parser.add_mutually_exclusive_group(
        required=True
    )

    mode.add_argument(
        "--smoke-files",
        type=int,
    )

    mode.add_argument(
        "--all-files",
        action="store_true",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
    )

    args = parser.parse_args()

    for path in [
        MATCH_REGISTRY,
        MATCH_MANIFEST,
    ]:
        require(path)

    # --------------------------------------------------------
    # Load / verify frozen full matching registry.
    # --------------------------------------------------------

    registry_full = pd.read_parquet(
        MATCH_REGISTRY
    ).fillna("")

    match_manifest = json.loads(
        MATCH_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    if (
        match_manifest.get("release")
        != "openalex-retrieval-match-registry-full-v1"
    ):
        raise RuntimeError(
            "Unexpected full match-registry release"
        )

    if len(registry_full) != EXPECTED_FULL_REGISTRY_ROWS:
        raise RuntimeError(
            "Unexpected full registry row count: "
            f"{len(registry_full)}"
        )

    if not registry_full[
        "query_id"
    ].is_unique:
        raise RuntimeError(
            "full registry query_id is not unique"
        )

    # R4 is deliberately excluded from this scan.
    registry = (
        registry_full.loc[
            registry_full[
                "query_route"
            ].isin(["R2", "R3"])
        ]
        .copy()
        .reset_index(drop=True)
    )

    if len(registry) != EXPECTED_R23_ROWS:
        raise RuntimeError(
            "Unexpected R2/R3 registry row count: "
            f"{len(registry)}"
        )

    route_counts = (
        registry[
            "query_route"
        ]
        .value_counts()
        .to_dict()
    )

    if route_counts != {
        "R3": EXPECTED_R3_ROWS,
        "R2": EXPECTED_R2_ROWS,
    }:
        raise RuntimeError(
            f"Unexpected R2/R3 route counts: "
            f"{route_counts}"
        )

    if not registry[
        "query_form"
    ].eq("title_author").all():
        raise RuntimeError(
            "R2/R3 scan received non-title_author query"
        )

    if (
        registry[
            "execution_id"
        ].nunique()
        != EXPECTED_R23_EXECUTIONS
    ):
        raise RuntimeError(
            "Unexpected R2/R3 physical execution count: "
            f"{registry['execution_id'].nunique()}"
        )

    if not registry[
        "query_id"
    ].is_unique:
        raise RuntimeError(
            "R2/R3 query_id is not unique"
        )

    # --------------------------------------------------------
    # Build compact query index.
    # --------------------------------------------------------

    title_to_queries = defaultdict(list)

    for row in registry.to_dict(
        "records"
    ):
        pattern = str(
            row["title_match_norm"]
        )

        if not pattern:
            raise RuntimeError(
                "Empty title_match_norm"
            )

        compact = {
            "query_id": str(
                row["query_id"]
            ),
            "execution_id": str(
                row["execution_id"]
            ),
            "target_lane": str(
                row["target_lane"]
            ),
            "project_work_id": str(
                row["project_work_id"]
            ),
            "unresolved_unit_anchor_entity_id": str(
                row[
                    "unresolved_unit_anchor_entity_id"
                ]
            ),
            "alias_id": str(
                row["alias_id"]
            ),
            "alias_project_source_entity_id": str(
                row[
                    "alias_project_source_entity_id"
                ]
            ),
            "query_route": str(
                row["query_route"]
            ),
            "query_form": str(
                row["query_form"]
            ),
            "title_match_norm": pattern,
            "author_a1_norm": str(
                row["author_a1_norm"]
            ),
            "author_a2_reverse_norm": str(
                row[
                    "author_a2_reverse_norm"
                ]
            ),
            "author_a3_anchor": str(
                row["author_a3_anchor"]
            ),
        }

        title_to_queries[
            pattern
        ].append(compact)

    title_patterns = set(
        title_to_queries
    )

    author_patterns = set()

    for rows in title_to_queries.values():
        for row in rows:
            for key in [
                "author_a1_norm",
                "author_a2_reverse_norm",
                "author_a3_anchor",
            ]:
                value = row[key]

                if value:
                    author_patterns.add(
                        value
                    )

    print(
        "Building title automaton:",
        len(title_patterns),
        "patterns",
    )

    title_automaton = build_automaton(
        title_patterns
    )

    print(
        "Building author automaton:",
        len(author_patterns),
        "patterns",
    )

    author_automaton = build_automaton(
        author_patterns
    )

    # --------------------------------------------------------
    # Snapshot inventory.
    # --------------------------------------------------------

    inventory = snapshot_inventory(
        args.snapshot_dir
    )

    if (
        inventory["file_count"]
        != EXPECTED_SNAPSHOT_FILE_COUNT
    ):
        raise RuntimeError(
            "Frozen snapshot file-count mismatch: "
            f"{inventory['file_count']}"
        )

    if (
        inventory["total_bytes"]
        != EXPECTED_SNAPSHOT_TOTAL_BYTES
    ):
        raise RuntimeError(
            "Frozen snapshot byte-count mismatch: "
            f"{inventory['total_bytes']}"
        )

    if (
        inventory["inventory_sha256"]
        != EXPECTED_SNAPSHOT_INVENTORY_SHA256
    ):
        raise RuntimeError(
            "Frozen snapshot inventory SHA256 mismatch: "
            f"{inventory['inventory_sha256']}"
        )

    all_files = inventory["files"]

    if args.all_files:
        selected_files = all_files
        run_mode = "full"
    else:
        selected_files = evenly_spaced_files(
            all_files,
            args.smoke_files,
        )
        run_mode = (
            f"smoke_evenly_spaced_"
            f"{len(selected_files)}"
        )

    processed_inventory_sha256 = (
        subset_inventory_hash(
            args.snapshot_dir,
            selected_files,
        )
    )

    print(
        "\nSnapshot files total:",
        inventory["file_count"],
    )

    print(
        "Snapshot total bytes:",
        inventory["total_bytes"],
    )

    print(
        "Snapshot updated_date range:",
        inventory["updated_date_min"],
        "to",
        inventory["updated_date_max"],
    )

    print(
        "Full inventory SHA256:",
        inventory["inventory_sha256"],
    )

    print(
        "Files selected for this run:",
        len(selected_files),
    )

    for p in selected_files:
        print(
            " ",
            p.relative_to(
                args.snapshot_dir
            ),
        )

    # --------------------------------------------------------
    # Output setup.
    # --------------------------------------------------------

    out_dir = args.output_dir

    evidence_path = (
        out_dir
        / "openalex_retrieval_full_r23_hit_evidence_v1.parquet"
    )

    records_path = (
        out_dir
        / "openalex_retrieval_full_r23_oa_records_v1.parquet"
    )

    counts_tsv = (
        out_dir
        / "openalex_retrieval_full_r23_query_counts_v1.tsv"
    )

    counts_parquet = (
        out_dir
        / "openalex_retrieval_full_r23_query_counts_v1.parquet"
    )

    manifest_path = (
        out_dir
        / "openalex_retrieval_full_r23_scan_v1_manifest.json"
    )

    output_paths = [
        evidence_path,
        records_path,
        counts_tsv,
        counts_parquet,
        manifest_path,
    ]

    if out_dir.exists():
        existing = [
            p
            for p in output_paths
            if p.exists()
        ]

        if existing and not args.overwrite:
            raise RuntimeError(
                "Output files already exist. "
                "Use --overwrite only if this run is "
                "intentionally being replaced:\n"
                + "\n".join(
                    str(x)
                    for x in existing
                )
            )

    out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for path in output_paths:
        if path.exists():
            path.unlink()

    evidence_writer = (
        BufferedParquetWriter(
            evidence_path,
            EVIDENCE_SCHEMA,
        )
    )

    records_writer = (
        BufferedParquetWriter(
            records_path,
            OA_RECORD_SCHEMA,
        )
    )

    # One Counter per logical query.
    query_counts = {
        qid: Counter()
        for qid
        in registry["query_id"]
    }

    global_counts = Counter()

    t0 = time.time()

    # --------------------------------------------------------
    # Scan.
    # --------------------------------------------------------

    try:
        for file_i, gz_path in enumerate(
            selected_files,
            start=1,
        ):
            rel = gz_path.relative_to(
                args.snapshot_dir
            ).as_posix()

            file_counts = Counter()

            file_start = time.time()

            with gzip.open(
                gz_path,
                "rt",
                encoding="utf-8",
                errors="replace",
            ) as f:
                for line in f:
                    global_counts[
                        "snapshot_rows_read"
                    ] += 1

                    file_counts[
                        "snapshot_rows_read"
                    ] += 1

                    try:
                        obj = json.loads(line)
                    except Exception:
                        global_counts[
                            "json_errors"
                        ] += 1

                        file_counts[
                            "json_errors"
                        ] += 1

                        continue

                    oa_url = str(
                        obj.get("id") or ""
                    )

                    oa_id = normalize_openalex_id(
                        oa_url
                    )

                    if not oa_id:
                        global_counts[
                            "missing_openalex_id"
                        ] += 1
                        continue

                    display_name = str(
                        obj.get(
                            "display_name"
                        )
                        or ""
                    )

                    if not display_name:
                        global_counts[
                            "missing_display_name"
                        ] += 1

                    abstract_raw = (
                        reconstruct_abstract(
                            obj.get(
                                "abstract_inverted_index"
                            )
                        )
                    )

                    if abstract_raw:
                        global_counts[
                            "rows_with_abstract"
                        ] += 1

                    title_norm = match_tokens(
                        display_name
                    )

                    abstract_norm = match_tokens(
                        abstract_raw
                    )

                    title_patterns_in_title = (
                        find_patterns(
                            title_automaton,
                            title_norm,
                        )
                    )

                    title_patterns_in_abstract = (
                        find_patterns(
                            title_automaton,
                            abstract_norm,
                        )
                    )

                    matched_title_patterns = (
                        title_patterns_in_title
                        | title_patterns_in_abstract
                    )

                    if not matched_title_patterns:
                        continue

                    global_counts[
                        "oa_records_with_any_title_hit"
                    ] += 1

                    file_counts[
                        "oa_records_with_any_title_hit"
                    ] += 1

                    # Only scan author patterns after at least
                    # one target title has matched.
                    author_patterns_in_title = (
                        find_patterns(
                            author_automaton,
                            title_norm,
                        )
                    )

                    author_patterns_in_abstract = (
                        find_patterns(
                            author_automaton,
                            abstract_norm,
                        )
                    )

                    topic = (
                        obj.get(
                            "primary_topic"
                        )
                        or {}
                    )

                    records_writer.append({
                        "openalex_work_id": oa_id,
                        "openalex_id_url": oa_url,
                        "snapshot_source_file": rel,

                        "display_name": display_name,
                        "abstract": abstract_raw,
                        "abstract_present": bool(
                            abstract_raw
                        ),

                        "publication_year": (
                            int(
                                obj[
                                    "publication_year"
                                ]
                            )
                            if isinstance(
                                obj.get(
                                    "publication_year"
                                ),
                                int,
                            )
                            else None
                        ),
                        "publication_date": str(
                            obj.get(
                                "publication_date"
                            )
                            or ""
                        ),
                        "type": str(
                            obj.get("type")
                            or ""
                        ),
                        "language": str(
                            obj.get("language")
                            or ""
                        ),
                        "doi": str(
                            obj.get("doi")
                            or ""
                        ),

                        "is_retracted": bool(
                            obj.get(
                                "is_retracted"
                            )
                            or False
                        ),
                        "is_paratext": bool(
                            obj.get(
                                "is_paratext"
                            )
                            or False
                        ),
                        "has_fulltext": bool(
                            obj.get(
                                "has_fulltext"
                            )
                            or False
                        ),

                        "primary_topic_id": str(
                            topic.get("id")
                            or ""
                        ),
                        "primary_topic_name": str(
                            topic.get(
                                "display_name"
                            )
                            or ""
                        ),
                    })

                    # ----------------------------------------
                    # Expand physical title hits back to
                    # logical query provenance.
                    # ----------------------------------------

                    for title_pattern in (
                        matched_title_patterns
                    ):
                        in_title = (
                            title_pattern
                            in title_patterns_in_title
                        )

                        in_abstract = (
                            title_pattern
                            in title_patterns_in_abstract
                        )

                        for qrow in (
                            title_to_queries[
                                title_pattern
                            ]
                        ):
                            a1 = qrow[
                                "author_a1_norm"
                            ]

                            a2r = qrow[
                                "author_a2_reverse_norm"
                            ]

                            a3 = qrow[
                                "author_a3_anchor"
                            ]

                            a1_title = bool(
                                a1
                                and a1
                                in author_patterns_in_title
                            )

                            a1_abstract = bool(
                                a1
                                and a1
                                in author_patterns_in_abstract
                            )

                            a1_hit = (
                                a1_title
                                or a1_abstract
                            )

                            a2r_title = bool(
                                a2r
                                and a2r
                                in author_patterns_in_title
                            )

                            a2r_abstract = bool(
                                a2r
                                and a2r
                                in author_patterns_in_abstract
                            )

                            a2r_hit = (
                                a2r_title
                                or a2r_abstract
                            )

                            a2_hit = (
                                a1_hit
                                or a2r_hit
                            )

                            a3_title = bool(
                                a3
                                and a3
                                in author_patterns_in_title
                            )

                            a3_abstract = bool(
                                a3
                                and a3
                                in author_patterns_in_abstract
                            )

                            a3_hit = (
                                a3_title
                                or a3_abstract
                            )

                            evidence_writer.append({
                                "query_id": qrow[
                                    "query_id"
                                ],
                                "execution_id": qrow[
                                    "execution_id"
                                ],
                                "target_lane": qrow[
                                    "target_lane"
                                ],
                                "project_work_id": qrow[
                                    "project_work_id"
                                ],
                                "unresolved_unit_anchor_entity_id": qrow[
                                    "unresolved_unit_anchor_entity_id"
                                ],
                                "alias_id": qrow[
                                    "alias_id"
                                ],
                                "alias_project_source_entity_id": qrow[
                                    "alias_project_source_entity_id"
                                ],
                                "query_route": qrow[
                                    "query_route"
                                ],
                                "query_form": qrow[
                                    "query_form"
                                ],

                                "openalex_work_id": oa_id,

                                "title_match_in_title": (
                                    in_title
                                ),
                                "title_match_in_abstract": (
                                    in_abstract
                                ),

                                "author_a1_in_title": (
                                    a1_title
                                ),
                                "author_a1_in_abstract": (
                                    a1_abstract
                                ),
                                "author_a1_hit": (
                                    a1_hit
                                ),

                                "author_a2_reverse_in_title": (
                                    a2r_title
                                ),
                                "author_a2_reverse_in_abstract": (
                                    a2r_abstract
                                ),
                                "author_a2_reverse_hit": (
                                    a2r_hit
                                ),
                                "author_a2_hit": (
                                    a2_hit
                                ),

                                "author_a3_in_title": (
                                    a3_title
                                ),
                                "author_a3_in_abstract": (
                                    a3_abstract
                                ),
                                "author_a3_hit": (
                                    a3_hit
                                ),

                                "snapshot_source_file": (
                                    rel
                                ),
                            })

                            c = query_counts[
                                qrow["query_id"]
                            ]

                            c[
                                "title_hit_count"
                            ] += 1

                            if in_title:
                                c[
                                    "title_in_title_count"
                                ] += 1

                            if in_abstract:
                                c[
                                    "title_in_abstract_count"
                                ] += 1

                            if (
                                in_title
                                and in_abstract
                            ):
                                c[
                                    "title_in_both_count"
                                ] += 1

                            if a1_hit:
                                c[
                                    "a1_hit_count"
                                ] += 1

                            if a1_title:
                                c[
                                    "a1_in_title_count"
                                ] += 1

                            if a1_abstract:
                                c[
                                    "a1_in_abstract_count"
                                ] += 1

                            if a2_hit:
                                c[
                                    "a2_hit_count"
                                ] += 1

                            if a2r_hit:
                                c[
                                    "a2_reverse_hit_count"
                                ] += 1

                            if (
                                a2_hit
                                and not a1_hit
                            ):
                                c[
                                    "a2_incremental_over_a1_count"
                                ] += 1

                            if a3_hit:
                                c[
                                    "a3_hit_count"
                                ] += 1

                            if a3_title:
                                c[
                                    "a3_in_title_count"
                                ] += 1

                            if a3_abstract:
                                c[
                                    "a3_in_abstract_count"
                                ] += 1

                            if (
                                a3_hit
                                and not a2_hit
                            ):
                                c[
                                    "a3_incremental_over_a2_count"
                                ] += 1

            elapsed_file = (
                time.time() - file_start
            )

            elapsed_total = (
                time.time() - t0
            )

            print(
                f"[{file_i}/{len(selected_files)}] "
                f"{rel} | "
                f"rows={file_counts['snapshot_rows_read']:,} "
                f"title-hit OA="
                f"{file_counts['oa_records_with_any_title_hit']:,} "
                f"| {elapsed_file:.1f}s "
                f"| total {elapsed_total/60:.1f}m"
            )

    finally:
        evidence_writer.close()
        records_writer.close()

    # --------------------------------------------------------
    # Query-level counts.
    # --------------------------------------------------------

    count_rows = []

    for row in registry.to_dict(
        "records"
    ):
        qid = row["query_id"]

        c = query_counts[qid]

        out = {
            "query_id": qid,
            "execution_id": (
                row["execution_id"]
            ),
            "target_lane": (
                row["target_lane"]
            ),
            "project_work_id": (
                row["project_work_id"]
            ),
            "unresolved_unit_anchor_entity_id": (
                row[
                    "unresolved_unit_anchor_entity_id"
                ]
            ),
            "alias_id": row["alias_id"],
            "query_route": (
                row["query_route"]
            ),
            "query_form": (
                row["query_form"]
            ),
            "query_title": (
                row["query_title"]
            ),
            "query_author": (
                row["query_author"]
            ),
            "title_match_norm": (
                row["title_match_norm"]
            ),
            "title_match_token_count": int(
                row[
                    "title_match_token_count"
                ]
            ),
            "author_a1_norm": (
                row["author_a1_norm"]
            ),
            "author_a2_reverse_norm": (
                row[
                    "author_a2_reverse_norm"
                ]
            ),
            "author_a3_anchor": (
                row["author_a3_anchor"]
            ),
        }

        for col in COUNT_COLUMNS:
            out[col] = int(
                c.get(col, 0)
            )

        count_rows.append(out)

    counts_df = pd.DataFrame(
        count_rows
    )

    counts_df.to_csv(
        counts_tsv,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    counts_df.to_parquet(
        counts_parquet,
        index=False,
        engine="pyarrow",
    )

    # --------------------------------------------------------
    # Summary diagnostics.
    # --------------------------------------------------------

    route_summary = (
        counts_df
        .groupby(
            [
                "target_lane",
                "query_route",
                "query_form",
            ],
            dropna=False,
        )[
            [
                "title_hit_count",
                "a1_hit_count",
                "a2_hit_count",
                "a2_incremental_over_a1_count",
                "a3_hit_count",
                "a3_incremental_over_a2_count",
            ]
        ]
        .sum()
        .reset_index()
    )

    route_summary_records = (
        route_summary.to_dict(
            "records"
        )
    )

    elapsed = time.time() - t0

    manifest = {
        "release": (
            "openalex-retrieval-full-r23-scan-v1"
        ),
        "scanner_version": (
            SCANNER_VERSION
        ),
        "matching_contract_version": (
            MATCHING_CONTRACT_VERSION
        ),
        "run_mode": run_mode,
        "status": (
            "smoke_test"
            if not args.all_files
            else "full_scan"
        ),
        "source_releases": {
            "match_registry": (
                match_manifest["release"]
            ),
        },
        "route_scope": {
            "included": [
                "R2",
                "R3",
            ],
            "excluded": [
                "R4",
            ],
            "reason": (
                "R4 title-only retrieval is outside "
                "OpenAlex marginal retrieval policy v1."
            ),
        },
        "matching_semantics": {
            "searchable_fields": [
                "display_name",
                "reconstructed abstract_inverted_index",
            ],
            "title_matching": (
                "T1 contiguous whole-token phrase "
                "under retrieval_match_registry_full_v1 "
                "normalization"
            ),
            "author_A1": (
                "source-order full-name token phrase"
            ),
            "author_A2": (
                "A1 OR conservative simple-comma "
                "reversed variant"
            ),
            "author_A3": (
                "experimental surname-like anchor"
            ),
            "field_policy": (
                "Title and abstract evidence are stored "
                "separately. Aggregate A1/A2/A3 hit means "
                "presence in either field."
            ),
            "raw_evidence_policy": (
                "Every R2/R3 logical query whose title pattern "
                "matches the OpenAlex Work title and/or "
                "abstract receives an evidence row, even "
                "when no author condition matches."
            ),
        },
        "snapshot": {
            "root": str(
                args.snapshot_dir
            ),
            "full_file_count": int(
                inventory["file_count"]
            ),
            "full_total_bytes": int(
                inventory["total_bytes"]
            ),
            "full_inventory_sha256": (
                inventory[
                    "inventory_sha256"
                ]
            ),
            "updated_date_min": (
                inventory[
                    "updated_date_min"
                ]
            ),
            "updated_date_max": (
                inventory[
                    "updated_date_max"
                ]
            ),
            "processed_file_count": (
                len(selected_files)
            ),
            "processed_inventory_sha256": (
                processed_inventory_sha256
            ),
            "processed_files": [
                p.relative_to(
                    args.snapshot_dir
                ).as_posix()
                for p in selected_files
            ],
        },
        "counts": {
            key: int(value)
            for key, value
            in global_counts.items()
        },
        "outputs": {
            "hit_evidence": {
                "artifact": str(
                    evidence_path
                ),
                "rows": int(
                    evidence_writer.row_count
                ),
                "sha256": (
                    sha256_file(
                        evidence_path
                    )
                ),
            },
            "oa_records": {
                "artifact": str(
                    records_path
                ),
                "rows": int(
                    records_writer.row_count
                ),
                "sha256": (
                    sha256_file(
                        records_path
                    )
                ),
            },
            "query_counts_tsv": {
                "artifact": str(
                    counts_tsv
                ),
                "rows": int(
                    len(counts_df)
                ),
                "sha256": (
                    sha256_file(
                        counts_tsv
                    )
                ),
            },
            "query_counts_parquet": {
                "artifact": str(
                    counts_parquet
                ),
                "rows": int(
                    len(counts_df)
                ),
                "sha256": (
                    sha256_file(
                        counts_parquet
                    )
                ),
            },
        },
        "route_summary": (
            route_summary_records
        ),
        "elapsed_seconds": (
            round(elapsed, 3)
        ),
        "inputs": {
            str(
                MATCH_REGISTRY.relative_to(ROOT)
            ): sha256_file(
                MATCH_REGISTRY
            ),
            str(
                MATCH_MANIFEST.relative_to(ROOT)
            ): sha256_file(
                MATCH_MANIFEST
            ),
        },
    }

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

    print(
        "\n=== SCAN COMPLETE ==="
    )

    print(
        "mode:",
        run_mode,
    )

    print(
        "snapshot rows read:",
        global_counts[
            "snapshot_rows_read"
        ],
    )

    print(
        "OA records with any title hit:",
        global_counts[
            "oa_records_with_any_title_hit"
        ],
    )

    print(
        "query × OA evidence rows:",
        evidence_writer.row_count,
    )

    print(
        "OA metadata rows:",
        records_writer.row_count,
    )

    print(
        "\n=== ROUTE SUMMARY ==="
    )

    print(
        route_summary.to_string(
            index=False
        )
    )

    print(
        "\nOutputs:",
        out_dir,
    )

    print(
        "\nOpenAlex retrieval full R2/R3 "
        "scan v1 completed."
    )


if __name__ == "__main__":
    main()
