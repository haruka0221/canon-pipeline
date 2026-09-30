#!/usr/bin/env python3

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from glob import glob
import argparse
import gzip
import hashlib
import json
import platform
import subprocess
import sys
import time
import unicodedata
from importlib.metadata import PackageNotFoundError, version as package_version

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]

MATCH_DIR = (
    ROOT
    / "derived/openalex_production/"
      "retrieval_match_registry_v1"
)

MATCH_REGISTRY = (
    MATCH_DIR
    / "openalex_retrieval_match_registry_v1.parquet"
)

MATCH_MANIFEST = (
    MATCH_DIR
    / "openalex_retrieval_match_registry_v1_manifest.json"
)

DEFAULT_SNAPSHOT_DIR = Path("/mnt/d/openalex/works")

SNAPSHOT_PROVENANCE_DIR = (
    ROOT
    / "derived/openalex_production/"
      "snapshot_provenance_release_20260923_v1"
)

SNAPSHOT_VERIFICATION = (
    SNAPSHOT_PROVENANCE_DIR
    / "snapshot_verification_v1.json"
)

SNAPSHOT_UPSTREAM_MANIFEST = (
    SNAPSHOT_PROVENANCE_DIR
    / "upstream_manifest.json"
)

EXPECTED_QUERIES = 11008
EXPECTED_TITLE_PATTERNS = 2858

PROFILE_VERSION = "v2"
PROFILE_RELEASE = (
    "openalex-retrieval-calibration-profile-v2"
)

EXPECTED_SNAPSHOT_DATE = "2026-09-23"
EXPECTED_SNAPSHOT_FILES = 2040
EXPECTED_SNAPSHOT_BYTES = 659026072445
EXPECTED_SNAPSHOT_RECORDS = 476196327
EXPECTED_SNAPSHOT_UPDATED_DATE_MIN = "2016-06-24"
EXPECTED_SNAPSHOT_UPDATED_DATE_MAX = "2026-09-23"

EXPECTED_SNAPSHOT_MANIFEST_SHA256 = (
    "441a4d047be6e5f21146c30525c3a6fee"
    "6a820b171f7fd6b6f0c069cdad9d05e"
)

EXPECTED_SNAPSHOT_INVENTORY_SHA256 = (
    "57959e90573d6ef2adb953fd747ba718"
    "54819880f762077f680083476d490fc9"
)

MATCHING_CONTRACT_VERSION = (
    "openalex_snapshot_title_abstract_token_phrase_v1"
)


A12_EVIDENCE_SCHEMA = pa.schema([
    ("query_id", pa.string()),
    ("execution_id", pa.string()),
    ("target_lane", pa.string()),
    ("project_work_id", pa.string()),
    ("unresolved_unit_anchor_entity_id", pa.string()),
    ("alias_id", pa.string()),
    ("alias_project_source_entity_id", pa.string()),
    ("query_route", pa.string()),

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

    ("snapshot_source_file", pa.string()),
])


OA_SCHEMA = pa.schema([
    ("openalex_work_id", pa.string()),
    ("openalex_id_url", pa.string()),
    ("snapshot_source_file", pa.string()),

    ("display_name", pa.string()),
    ("abstract", pa.string()),

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

    "a2_hit_count",
    "a2_reverse_hit_count",
    "a2_incremental_over_a1_count",

    "a3_hit_count",
    "a3_incremental_over_a2_count",
]


def sha256_file(path):
    h = hashlib.sha256()

    with Path(path).open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def git_state():
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
    ).strip()

    dirty = bool(
        subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            text=True,
        ).strip()
    )

    return {
        "commit": commit,
        "dirty": dirty,
    }


def installed_version(distribution):
    try:
        return package_version(distribution)
    except PackageNotFoundError:
        return ""


def runtime_environment():
    state = git_state()

    return {
        "python":
            sys.version.split()[0],
        "platform":
            platform.platform(),
        "pandas":
            pd.__version__,
        "pyarrow":
            pa.__version__,
        "pyahocorasick":
            installed_version("pyahocorasick"),
        "git_commit":
            state["commit"],
        "git_dirty":
            state["dirty"],
    }


def match_tokens(value):
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


def reconstruct_abstract(index):
    if not isinstance(index, dict):
        return ""

    values = []

    for token, positions in index.items():
        if not isinstance(positions, list):
            continue

        for pos in positions:
            if isinstance(pos, int):
                values.append(
                    (pos, str(token))
                )

    values.sort(
        key=lambda x: (
            x[0],
            x[1],
        )
    )

    return " ".join(
        token
        for _, token in values
    )


def oa_id(value):
    value = str(value or "").strip()

    if not value:
        return ""

    return value.rstrip("/").split("/")[-1]


def build_automaton(patterns):
    import ahocorasick

    a = ahocorasick.Automaton()

    for pattern in sorted(set(patterns)):
        if pattern:
            a.add_word(
                f" {pattern} ",
                pattern,
            )

    a.make_automaton()

    return a


def find_patterns(automaton, text):
    if not text:
        return set()

    padded = f" {text} "

    return {
        pattern
        for _, pattern
        in automaton.iter(padded)
    }


def snapshot_inventory(snapshot_dir):
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
            "No snapshot files found"
        )

    h = hashlib.sha256()
    total_bytes = 0
    dates = []

    for path in files:
        rel = path.relative_to(
            snapshot_dir
        ).as_posix()

        size = path.stat().st_size
        total_bytes += size

        h.update(
            f"{rel}\t{size}\n"
            .encode("utf-8")
        )

        parent = path.parent.name

        if parent.startswith("updated_date="):
            dates.append(
                parent.split("=", 1)[1]
            )

    return {
        "files": files,
        "file_count": len(files),
        "total_bytes": total_bytes,
        "inventory_sha256": h.hexdigest(),
        "updated_date_min": min(dates),
        "updated_date_max": max(dates),
    }


def verify_snapshot_provenance(inv):
    for path in [
        SNAPSHOT_VERIFICATION,
        SNAPSHOT_UPSTREAM_MANIFEST,
    ]:
        if not path.exists():
            raise FileNotFoundError(path)

    audit = json.loads(
        SNAPSHOT_VERIFICATION.read_text(
            encoding="utf-8"
        )
    )

    if audit.get("status") != "VERIFIED_COMPLETE":
        raise RuntimeError(
            "Snapshot provenance is not VERIFIED_COMPLETE"
        )

    checks = audit.get("checks", {})

    if not checks or not all(checks.values()):
        raise RuntimeError(
            "Snapshot verification checks are not all true"
        )

    manifest_sha256 = sha256_file(
        SNAPSHOT_UPSTREAM_MANIFEST
    )

    expected = {
        "release_date":
            EXPECTED_SNAPSHOT_DATE,
        "files":
            EXPECTED_SNAPSHOT_FILES,
        "bytes":
            EXPECTED_SNAPSHOT_BYTES,
        "records":
            EXPECTED_SNAPSHOT_RECORDS,
        "inventory_sha256":
            EXPECTED_SNAPSHOT_INVENTORY_SHA256,
        "manifest_sha256":
            EXPECTED_SNAPSHOT_MANIFEST_SHA256,
        "updated_date_min":
            EXPECTED_SNAPSHOT_UPDATED_DATE_MIN,
        "updated_date_max":
            EXPECTED_SNAPSHOT_UPDATED_DATE_MAX,
    }

    observed = {
        "release_date":
            audit["release"]["date"],
        "files":
            inv["file_count"],
        "bytes":
            inv["total_bytes"],
        "records":
            audit["manifest"]["record_count"],
        "inventory_sha256":
            inv["inventory_sha256"],
        "manifest_sha256":
            manifest_sha256,
        "updated_date_min":
            inv["updated_date_min"],
        "updated_date_max":
            inv["updated_date_max"],
    }

    for key in expected:
        if observed[key] != expected[key]:
            raise RuntimeError(
                f"Snapshot contract mismatch for {key}: "
                f"expected {expected[key]!r}, "
                f"observed {observed[key]!r}"
            )

    if (
        audit["manifest"]["content_length"]
        != EXPECTED_SNAPSHOT_BYTES
    ):
        raise RuntimeError(
            "Snapshot audit byte count mismatch"
        )

    if (
        audit["actual_inventory"]["files"]
        != EXPECTED_SNAPSHOT_FILES
    ):
        raise RuntimeError(
            "Snapshot audit file count mismatch"
        )

    if (
        audit["actual_inventory"][
            "inventory_path_size_sha256"
        ]
        != EXPECTED_SNAPSHOT_INVENTORY_SHA256
    ):
        raise RuntimeError(
            "Snapshot audit inventory hash mismatch"
        )

    return {
        "verification_version":
            audit["verification_version"],
        "official_manifest_sha256":
            manifest_sha256,
        "inventory_sha256":
            inv["inventory_sha256"],
        "record_count":
            EXPECTED_SNAPSHOT_RECORDS,
    }


def evenly_spaced(files, n):
    if n >= len(files):
        return files

    if n == 1:
        return [files[len(files) // 2]]

    idx = sorted(set(
        round(
            i * (len(files) - 1) / (n - 1)
        )
        for i in range(n)
    ))

    return [files[i] for i in idx]


class Writer:
    def __init__(
        self,
        path,
        schema,
        batch_size=25000,
    ):
        self.path = Path(path)
        self.schema = schema
        self.batch_size = batch_size

        self.rows = []
        self.writer = None
        self.row_count = 0

    def append(self, row):
        self.rows.append(row)

        if len(self.rows) >= self.batch_size:
            self.flush()

    def flush(self):
        if not self.rows:
            return

        table = pa.Table.from_pylist(
            self.rows,
            schema=self.schema,
        )

        if self.writer is None:
            self.writer = pq.ParquetWriter(
                self.path,
                self.schema,
                compression="zstd",
            )

        self.writer.write_table(table)

        self.row_count += len(self.rows)
        self.rows.clear()

    def close(self):
        self.flush()

        if self.writer is not None:
            self.writer.close()
        else:
            pq.write_table(
                pa.Table.from_pylist(
                    [],
                    schema=self.schema,
                ),
                self.path,
                compression="zstd",
            )


def main():
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

    reg = pd.read_parquet(
        MATCH_REGISTRY
    ).fillna("")

    manifest_in = json.loads(
        MATCH_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    if (
        manifest_in.get("release")
        != "openalex-retrieval-match-registry-v1"
    ):
        raise RuntimeError(
            "Unexpected match registry"
        )

    if len(reg) != EXPECTED_QUERIES:
        raise RuntimeError(
            f"Expected {EXPECTED_QUERIES} queries; "
            f"found {len(reg)}"
        )

    title_to_queries = defaultdict(list)

    for row in reg.to_dict("records"):
        title_to_queries[
            row["title_match_norm"]
        ].append(row)

    if (
        len(title_to_queries)
        != EXPECTED_TITLE_PATTERNS
    ):
        raise RuntimeError(
            "Unexpected title-pattern count"
        )

    title_patterns = set(
        title_to_queries
    )

    author_patterns = set()

    for rows in title_to_queries.values():
        for row in rows:
            for col in [
                "author_a1_norm",
                "author_a2_reverse_norm",
                "author_a3_anchor",
            ]:
                v = str(row[col])

                if v:
                    author_patterns.add(v)

    title_automaton = build_automaton(
        title_patterns
    )

    author_automaton = build_automaton(
        author_patterns
    )

    inv = snapshot_inventory(
        args.snapshot_dir
    )

    snapshot_provenance = (
        verify_snapshot_provenance(inv)
    )

    if args.all_files:
        files = inv["files"]
        run_mode = "full_profile"
    else:
        files = evenly_spaced(
            inv["files"],
            args.smoke_files,
        )
        run_mode = (
            f"smoke_evenly_spaced_{len(files)}"
        )

    out = args.output_dir

    if out.exists() and not args.overwrite:
        raise RuntimeError(
            f"{out} already exists"
        )

    out.mkdir(
        parents=True,
        exist_ok=True,
    )

    paths = {
        "patterns_tsv":
            out / "openalex_title_pattern_counts_v2.tsv",
        "patterns_parquet":
            out / "openalex_title_pattern_counts_v2.parquet",
        "queries_tsv":
            out / "openalex_query_profile_counts_v2.tsv",
        "queries_parquet":
            out / "openalex_query_profile_counts_v2.parquet",
        "a12_evidence":
            out / "openalex_a12_candidate_query_evidence_v2.parquet",
        "a12_records":
            out / "openalex_a12_candidate_oa_records_v2.parquet",
        "manifest":
            out / "openalex_retrieval_calibration_profile_v2_manifest.json",
    }

    if args.overwrite:
        for path in paths.values():
            if path.exists():
                path.unlink()

    evidence_writer = Writer(
        paths["a12_evidence"],
        A12_EVIDENCE_SCHEMA,
    )

    records_writer = Writer(
        paths["a12_records"],
        OA_SCHEMA,
    )

    query_counts = {
        qid: Counter()
        for qid in reg["query_id"]
    }

    pattern_counts = {
        pattern: Counter()
        for pattern in title_patterns
    }

    global_counts = Counter()

    start = time.time()

    for file_i, path in enumerate(
        files,
        start=1,
    ):
        rel = path.relative_to(
            args.snapshot_dir
        ).as_posix()

        fc = Counter()
        t_file = time.time()

        with gzip.open(
            path,
            "rt",
            encoding="utf-8",
            errors="replace",
        ) as f:
            for line in f:
                global_counts["rows"] += 1
                fc["rows"] += 1

                try:
                    obj = json.loads(line)
                except Exception:
                    global_counts["json_errors"] += 1
                    continue

                oid = oa_id(
                    obj.get("id")
                )

                if not oid:
                    continue

                display = str(
                    obj.get("display_name")
                    or ""
                )

                abstract = reconstruct_abstract(
                    obj.get(
                        "abstract_inverted_index"
                    )
                )

                title_norm = match_tokens(
                    display
                )

                abstract_norm = match_tokens(
                    abstract
                )

                pt = find_patterns(
                    title_automaton,
                    title_norm,
                )

                pa_ = find_patterns(
                    title_automaton,
                    abstract_norm,
                )

                matched = pt | pa_

                if not matched:
                    continue

                global_counts[
                    "oa_with_any_title_hit"
                ] += 1

                fc[
                    "oa_with_any_title_hit"
                ] += 1

                at = find_patterns(
                    author_automaton,
                    title_norm,
                )

                aa = find_patterns(
                    author_automaton,
                    abstract_norm,
                )

                any_a12 = False
                a12_rows = []

                for pattern in matched:
                    pc = pattern_counts[
                        pattern
                    ]

                    pc["hit"] += 1

                    if pattern in pt:
                        pc["in_title"] += 1

                    if pattern in pa_:
                        pc["in_abstract"] += 1

                    if (
                        pattern in pt
                        and pattern in pa_
                    ):
                        pc["in_both"] += 1

                    for q in title_to_queries[
                        pattern
                    ]:
                        qc = query_counts[
                            q["query_id"]
                        ]

                        qc["title_hit_count"] += 1

                        if pattern in pt:
                            qc[
                                "title_in_title_count"
                            ] += 1

                        if pattern in pa_:
                            qc[
                                "title_in_abstract_count"
                            ] += 1

                        if (
                            pattern in pt
                            and pattern in pa_
                        ):
                            qc[
                                "title_in_both_count"
                            ] += 1

                        a1 = str(
                            q["author_a1_norm"]
                        )

                        a2r = str(
                            q[
                                "author_a2_reverse_norm"
                            ]
                        )

                        a3 = str(
                            q["author_a3_anchor"]
                        )

                        a1_t = bool(
                            a1 and a1 in at
                        )

                        a1_a = bool(
                            a1 and a1 in aa
                        )

                        a1_hit = (
                            a1_t or a1_a
                        )

                        a2r_t = bool(
                            a2r and a2r in at
                        )

                        a2r_a = bool(
                            a2r and a2r in aa
                        )

                        a2r_hit = (
                            a2r_t or a2r_a
                        )

                        a2_hit = (
                            a1_hit or a2r_hit
                        )

                        a3_hit = bool(
                            a3
                            and (
                                a3 in at
                                or a3 in aa
                            )
                        )

                        if a1_hit:
                            qc[
                                "a1_hit_count"
                            ] += 1

                        if a2_hit:
                            qc[
                                "a2_hit_count"
                            ] += 1

                        if a2r_hit:
                            qc[
                                "a2_reverse_hit_count"
                            ] += 1

                        if (
                            a2_hit
                            and not a1_hit
                        ):
                            qc[
                                "a2_incremental_over_a1_count"
                            ] += 1

                        if a3_hit:
                            qc[
                                "a3_hit_count"
                            ] += 1

                        if (
                            a3_hit
                            and not a2_hit
                        ):
                            qc[
                                "a3_incremental_over_a2_count"
                            ] += 1

                        # Keep all A1/A2-qualified candidate
                        # provenance. Do NOT materialize R4
                        # title-only candidate IDs here.
                        if (
                            q["query_form"]
                            == "title_author"
                            and a2_hit
                        ):
                            any_a12 = True

                            a12_rows.append({
                                "query_id":
                                    q["query_id"],
                                "execution_id":
                                    q["execution_id"],
                                "target_lane":
                                    q["target_lane"],
                                "project_work_id":
                                    q["project_work_id"],
                                "unresolved_unit_anchor_entity_id":
                                    q[
                                        "unresolved_unit_anchor_entity_id"
                                    ],
                                "alias_id":
                                    q["alias_id"],
                                "alias_project_source_entity_id":
                                    q[
                                        "alias_project_source_entity_id"
                                    ],
                                "query_route":
                                    q["query_route"],

                                "openalex_work_id":
                                    oid,

                                "title_match_in_title":
                                    pattern in pt,
                                "title_match_in_abstract":
                                    pattern in pa_,

                                "author_a1_in_title":
                                    a1_t,
                                "author_a1_in_abstract":
                                    a1_a,
                                "author_a1_hit":
                                    a1_hit,

                                "author_a2_reverse_in_title":
                                    a2r_t,
                                "author_a2_reverse_in_abstract":
                                    a2r_a,
                                "author_a2_reverse_hit":
                                    a2r_hit,
                                "author_a2_hit":
                                    a2_hit,

                                "snapshot_source_file":
                                    rel,
                            })

                if any_a12:
                    for row in a12_rows:
                        evidence_writer.append(
                            row
                        )

                    topic = (
                        obj.get("primary_topic")
                        or {}
                    )

                    records_writer.append({
                        "openalex_work_id":
                            oid,
                        "openalex_id_url":
                            str(obj.get("id") or ""),
                        "snapshot_source_file":
                            rel,

                        "display_name":
                            display,
                        "abstract":
                            abstract,

                        "publication_year":
                            (
                                obj.get(
                                    "publication_year"
                                )
                                if isinstance(
                                    obj.get(
                                        "publication_year"
                                    ),
                                    int,
                                )
                                else None
                            ),
                        "publication_date":
                            str(
                                obj.get(
                                    "publication_date"
                                )
                                or ""
                            ),
                        "type":
                            str(
                                obj.get("type")
                                or ""
                            ),
                        "language":
                            str(
                                obj.get("language")
                                or ""
                            ),
                        "doi":
                            str(
                                obj.get("doi")
                                or ""
                            ),

                        "is_retracted":
                            bool(
                                obj.get(
                                    "is_retracted"
                                )
                                or False
                            ),
                        "is_paratext":
                            bool(
                                obj.get(
                                    "is_paratext"
                                )
                                or False
                            ),
                        "has_fulltext":
                            bool(
                                obj.get(
                                    "has_fulltext"
                                )
                                or False
                            ),

                        "primary_topic_id":
                            str(
                                topic.get("id")
                                or ""
                            ),
                        "primary_topic_name":
                            str(
                                topic.get(
                                    "display_name"
                                )
                                or ""
                            ),
                    })

        print(
            f"[{file_i}/{len(files)}] "
            f"{rel} | "
            f"rows={fc['rows']:,} | "
            f"title-hit OA="
            f"{fc['oa_with_any_title_hit']:,} | "
            f"{time.time()-t_file:.1f}s"
        )

    evidence_writer.close()
    records_writer.close()

    # --------------------------------------------------------
    # Physical title-pattern table
    # --------------------------------------------------------

    p_rows = []

    for pattern, qrows in sorted(
        title_to_queries.items()
    ):
        pc = pattern_counts[
            pattern
        ]

        raw_titles = sorted({
            str(x["query_title"])
            for x in qrows
        })

        p_rows.append({
            "title_match_norm":
                pattern,
            "title_match_token_count":
                len(pattern.split()),
            "logical_query_rows":
                len(qrows),
            "resolved_w":
                len({
                    x["project_work_id"]
                    for x in qrows
                    if x["project_work_id"]
                }),
            "unresolved_units":
                len({
                    x[
                        "unresolved_unit_anchor_entity_id"
                    ]
                    for x in qrows
                    if x[
                        "unresolved_unit_anchor_entity_id"
                    ]
                }),
            "raw_title_variant_count":
                len(raw_titles),
            "raw_title_examples":
                " || ".join(
                    raw_titles[:10]
                ),

            "title_hit_count":
                int(pc["hit"]),
            "title_in_title_count":
                int(pc["in_title"]),
            "title_in_abstract_count":
                int(pc["in_abstract"]),
            "title_in_both_count":
                int(pc["in_both"]),
        })

    pdf = pd.DataFrame(p_rows)

    pdf.to_csv(
        paths["patterns_tsv"],
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    pdf.to_parquet(
        paths["patterns_parquet"],
        index=False,
    )

    # --------------------------------------------------------
    # Logical-query exact-count table
    # --------------------------------------------------------

    q_rows = []

    for row in reg.to_dict("records"):
        qc = query_counts[
            row["query_id"]
        ]

        outrow = {
            "query_id":
                row["query_id"],
            "execution_id":
                row["execution_id"],
            "target_lane":
                row["target_lane"],
            "project_work_id":
                row["project_work_id"],
            "unresolved_unit_anchor_entity_id":
                row[
                    "unresolved_unit_anchor_entity_id"
                ],
            "alias_id":
                row["alias_id"],
            "query_route":
                row["query_route"],
            "query_form":
                row["query_form"],
            "query_title":
                row["query_title"],
            "query_author":
                row["query_author"],
            "title_match_norm":
                row["title_match_norm"],
            "title_match_token_count":
                int(
                    row[
                        "title_match_token_count"
                    ]
                ),
            "author_a1_norm":
                row["author_a1_norm"],
            "author_a2_reverse_norm":
                row[
                    "author_a2_reverse_norm"
                ],
            "author_a3_anchor":
                row["author_a3_anchor"],
        }

        for col in COUNT_COLUMNS:
            outrow[col] = int(
                qc[col]
            )

        q_rows.append(outrow)

    qdf = pd.DataFrame(q_rows)

    qdf.to_csv(
        paths["queries_tsv"],
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    qdf.to_parquet(
        paths["queries_parquet"],
        index=False,
    )

    elapsed = time.time() - start

    if global_counts["json_errors"] != 0:
        raise RuntimeError(
            "JSON errors encountered during snapshot scan: "
            f"{global_counts['json_errors']}"
        )

    if (
        args.all_files
        and global_counts["rows"]
        != EXPECTED_SNAPSHOT_RECORDS
    ):
        raise RuntimeError(
            "Full-scan record count mismatch: "
            f"expected {EXPECTED_SNAPSHOT_RECORDS}, "
            f"read {global_counts['rows']}"
        )

    manifest = {
        "release":
            PROFILE_RELEASE,
        "version":
            PROFILE_VERSION,
        "run_mode":
            run_mode,
        "matching_contract_version":
            MATCHING_CONTRACT_VERSION,

        "snapshot": {
            "root":
                str(args.snapshot_dir),
            "full_file_count":
                inv["file_count"],
            "full_total_bytes":
                inv["total_bytes"],
            "full_inventory_sha256":
                inv["inventory_sha256"],
            "release_date":
                EXPECTED_SNAPSHOT_DATE,
            "official_manifest_sha256":
                snapshot_provenance[
                    "official_manifest_sha256"
                ],
            "official_manifest_record_count":
                snapshot_provenance[
                    "record_count"
                ],
            "snapshot_verification_version":
                snapshot_provenance[
                    "verification_version"
                ],
            "updated_date_min":
                inv["updated_date_min"],
            "updated_date_max":
                inv["updated_date_max"],
            "processed_file_count":
                len(files),
            "processed_files": [
                x.relative_to(
                    args.snapshot_dir
                ).as_posix()
                for x in files
            ],
        },

        "policy": {
            "title_pattern_counts":
                "Exact counts retained for every T1 "
                "physical title pattern.",
            "logical_query_counts":
                "Exact T1/A1/A2/A3 counts retained for "
                "all 11,008 calibration queries.",
            "candidate_materialization":
                "Only A1/A2-qualified title-author "
                "candidate evidence is fully materialized.",
            "r4_candidate_materialization":
                "Deferred until title-risk and production "
                "routing calibration is complete.",
            "a3_candidate_materialization":
                "Deferred; A3 remains experimental.",
        },

        "counts": {
            "snapshot_rows_read":
                int(global_counts["rows"]),
            "json_errors":
                int(global_counts["json_errors"]),
            "oa_with_any_title_hit":
                int(
                    global_counts[
                        "oa_with_any_title_hit"
                    ]
                ),
            "title_patterns":
                len(pdf),
            "logical_queries":
                len(qdf),
            "a12_candidate_query_rows":
                evidence_writer.row_count,
            "a12_oa_record_rows":
                records_writer.row_count,
        },

        "source_release":
            manifest_in["release"],

        "inputs": {
            str(
                MATCH_REGISTRY.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    MATCH_REGISTRY
                ),
            str(
                MATCH_MANIFEST.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    MATCH_MANIFEST
                ),
        },

        "outputs": {
            name: {
                "artifact": str(path),
                "sha256": sha256_file(path),
            }
            for name, path
            in paths.items()
            if name != "manifest"
        },

        "runtime":
            runtime_environment(),

        "elapsed_seconds":
            round(elapsed, 3),
    }

    paths["manifest"].write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print("\n=== PROFILE COMPLETE ===")
    print("release:", PROFILE_RELEASE)
    print("mode:", run_mode)
    print(
        "snapshot inventory SHA256:",
        inv["inventory_sha256"],
    )
    print(
        "JSON errors:",
        global_counts["json_errors"],
    )
    print(
        "snapshot rows:",
        global_counts["rows"],
    )
    print(
        "OA with title hit:",
        global_counts[
            "oa_with_any_title_hit"
        ],
    )
    print(
        "A1/A2 evidence rows:",
        evidence_writer.row_count,
    )
    print(
        "A1/A2 OA records:",
        records_writer.row_count,
    )
    print(
        "title patterns:",
        len(pdf),
    )
    print(
        "logical queries:",
        len(qdf),
    )


if __name__ == "__main__":
    main()
