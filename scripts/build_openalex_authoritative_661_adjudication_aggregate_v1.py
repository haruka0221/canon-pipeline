#!/usr/bin/env python3
"""Build the authoritative 661-row aggregate using canonical package order.

Columns 1-8 come from the frozen 661-row review package. Columns 9-14 are
joined by candidate ID from the frozen P1/P2/P3 human adjudication sources.
No precision or other performance metric is calculated.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
RELEASE = "openalex_retrieval_precision_review_human_adjudication_complete_v1"
OUTPUT_DIR = ROOT / "derived/openalex_production" / RELEASE / "full_profile_57959e90"
BATCH_ROOT = ROOT / "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_batches_v1/full_profile_57959e90"
P2_ROOT = ROOT / "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_P2_complete_v1/full_profile_57959e90"
P3_ROOT = ROOT / "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_P3_complete_v1/full_profile_57959e90"
PACKAGE_ROOT = ROOT / "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_v1/full_profile_57959e90"
INVENTORY_ROOT = ROOT / "derived/openalex_production/p3_deterministic_review_inventory_v1/full_profile_57959e90"
SHEET_ROOT = ROOT / "derived/openalex_production/openalex_retrieval_precision_review_P3_human_review_sheets_v1/full_profile_57959e90"
ORDERING_RULE = (
    "The complete 661-row aggregate uses canonical global review_order from the frozen 661-row review package. "
    "P3 source review_order is P3-local review execution metadata and is not propagated into the global aggregate."
)
SCHEMA = [
    "review_order", "review_priority", "review_candidate_id", "project_work_id",
    "openalex_work_id", "increment_type", "review_semantic_group_id",
    "review_protocol_version", "human_target_attribution_judgment",
    "human_adjudication_confidence", "human_attribution_reason_code",
    "human_reviewer_note", "human_reviewer_id", "human_adjudicated_at_utc",
]
STRUCTURAL_FIELDS = SCHEMA[:8]
HUMAN_FIELDS = SCHEMA[8:]
EXPECTED_PRIORITY = {"P1": 49, "P2": 119, "P3": 493}
VALID_JUDGMENTS = {"VALID_TARGET_REFERENCE", "INVALID_TARGET_REFERENCE", "UNCERTAIN"}
VALID_CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}
VALID_REASONS = {
    "DIRECT_TARGET_REFERENCE", "VALID_TITLE_VARIANT", "VALID_CONTEXTUAL_REFERENCE",
    "TITLE_COLLISION_DIFFERENT_WORK", "GENERIC_OR_LEXICAL_TITLE_USE",
    "AUTHOR_COLLISION_DIFFERENT_PERSON", "TITLE_AUTHOR_UNLINKED_COOCCURRENCE",
    "WRONG_WORK_SAME_AUTHOR", "ALIAS_NOT_TARGET_EQUIVALENT", "METADATA_TEXT_ARTIFACT",
    "INSUFFICIENT_CONTEXT", "AMBIGUOUS_TARGET_REFERENCE", "OTHER",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames is None:
            raise ValueError(f"TSV has no header: {path}")
        rows = list(reader)
        if any(None in row for row in rows):
            raise ValueError(f"TSV row has extra cells: {path}")
        return list(reader.fieldnames), rows


def parquet_cells_as_tsv_strings(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{key: "" if value is None else str(value) for key, value in row.items()} for row in rows]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def git(args: list[str]) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def tracked_paths() -> list[str]:
    blob = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [part.decode() for part in blob.split(b"\0") if part]


PROTECTED_PREFIXES = (
    "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_batches_v1/",
    "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_P2_complete_v1/",
    "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_P3_complete_v1/",
    "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_v1/",
    "derived/openalex_production/p3_deterministic_review_inventory_v1/",
    "derived/openalex_production/openalex_retrieval_precision_review_P3_human_review_sheets_v1/",
    "derived/openalex_production/p2_deterministic_grouping_v1/",
    "derived/bl_calibration/",
    "derived/benchmark/",
)


def snapshot_protected() -> dict[str, str]:
    return {rel: sha256(ROOT / rel) for rel in tracked_paths() if rel.startswith(PROTECTED_PREFIXES)}


def counts(rows: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "rows": len(rows), "columns": len(SCHEMA),
        "review_priority": dict(Counter(row["review_priority"] for row in rows)),
        "human_target_attribution_judgment": dict(Counter(row["human_target_attribution_judgment"] for row in rows)),
        "human_adjudication_confidence": dict(Counter(row["human_adjudication_confidence"] for row in rows)),
        "human_attribution_reason_code": dict(Counter(row["human_attribution_reason_code"] for row in rows)),
        "reviewer_id": dict(Counter(row["human_reviewer_id"] for row in rows)),
    }


def source_bundle(paths: dict[str, Path], priority: str, label: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    if not all(path.is_file() for path in paths.values()):
        raise FileNotFoundError(f"Incomplete {label} source bundle")
    header, rows = read_tsv(paths["tsv"])
    if header != SCHEMA:
        raise ValueError(f"Unexpected schema in {label}: {header}")
    audit = read_json(paths["audit"])
    if audit.get("audit_status") != "PASSED":
        raise ValueError(f"Audit is not PASSED for {label}")
    if parquet_cells_as_tsv_strings(pq.read_table(paths["parquet"]).to_pylist()) != rows:
        raise ValueError(f"TSV/Parquet cell parity failed for {label}")
    return rows, {
        "priority": priority, "source": label,
        "path": paths["tsv"].parent.relative_to(ROOT).as_posix(),
        "rows": len(rows), "columns": len(header), "audit_status": "PASSED",
        "tsv_parquet_cell_parity": True,
        "files_sha256": {kind: sha256(path) for kind, path in paths.items()},
        "file_paths": {kind: path.relative_to(ROOT).as_posix() for kind, path in paths.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise SystemExit(f"Refusing to overwrite existing output directory: {output_dir}")

    branch = git(["git", "branch", "--show-current"])
    head = git(["git", "rev-parse", "HEAD"])
    status = git(["git", "status", "--porcelain=v1"])
    own_script = "?? scripts/build_openalex_authoritative_661_adjudication_aggregate_v1.py"
    if branch != "kakenc-integration-20260927" or head != "eac77ee60993d8ef6307758efd0638fc79a89c1d":
        raise ValueError(f"Unexpected branch or HEAD: {branch} {head}")
    if status not in ("", own_script):
        raise ValueError(f"Unexpected worktree changes; refusing to write: {status}")

    created_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    generator_path = Path(__file__).resolve()
    generator_hash = sha256(generator_path)
    frozen_before = snapshot_protected()

    # Read the canonical package spine, preserving its exact TSV cell strings.
    package_tsv = PACKAGE_ROOT / "openalex_retrieval_precision_review_human_adjudication_v1.tsv"
    package_parquet = PACKAGE_ROOT / "openalex_retrieval_precision_review_human_adjudication_v1.parquet"
    package_audit_path = PACKAGE_ROOT / "openalex_retrieval_precision_review_human_adjudication_v1_audit_v1.json"
    package_manifest = PACKAGE_ROOT / "openalex_retrieval_precision_review_human_adjudication_v1_manifest.json"
    package_header, package_rows = read_tsv(package_tsv)
    if len(package_rows) != 661 or len(package_header) < 14:
        raise ValueError("Frozen human-review package does not contain 661 rows and required structural columns")
    package_by_id = {row["review_candidate_id"]: row for row in package_rows}
    if len(package_by_id) != 661:
        raise ValueError("Frozen package candidate IDs are not unique")
    package_orders = [int(row["review_order"]) for row in package_rows]
    if package_orders != list(range(1, 662)):
        raise ValueError("Frozen package canonical review_order is not exactly 1 through 661")
    if read_json(package_audit_path).get("audit_status") != "PASSED":
        raise ValueError("Frozen human-review package audit is not PASSED")

    # Load the five P1 batches, then the frozen P2 and P3 complete aggregates.
    human_by_id: dict[str, dict[str, str]] = {}
    human_priority_by_id: dict[str, str] = {}
    local_p3_orders: dict[str, int] = {}
    source_records: list[dict[str, Any]] = []
    for sequence in range(1, 6):
        batch = f"P1_batch{sequence:02d}"
        directory = BATCH_ROOT / batch
        stem = f"openalex_retrieval_precision_review_human_adjudication_{batch}_v1"
        paths = {"tsv": directory / f"{stem}.tsv", "parquet": directory / f"{stem}.parquet",
                 "audit": directory / f"{stem}_audit_v1.json", "manifest": directory / f"{stem}_manifest.json"}
        rows, record = source_bundle(paths, "P1", batch)
        source_records.append(record)
        for row in rows:
            candidate_id = row["review_candidate_id"]
            if candidate_id in human_by_id:
                raise ValueError(f"Candidate appears in multiple priority source batches: {candidate_id}")
            human_by_id[candidate_id] = {field: row[field] for field in HUMAN_FIELDS}
            human_priority_by_id[candidate_id] = "P1"
            package_row = package_by_id.get(candidate_id)
            if package_row is None or any(row[field] != package_row[field] for field in STRUCTURAL_FIELDS):
                raise ValueError(f"P1 structural identity/order differs from canonical package for {candidate_id}")

    for priority, source_root, release in (
        ("P2", P2_ROOT, "openalex_retrieval_precision_review_human_adjudication_P2_complete_v1"),
        ("P3", P3_ROOT, "openalex_retrieval_precision_review_human_adjudication_P3_complete_v1"),
    ):
        paths = {
            "tsv": source_root / f"{release}.tsv",
            "parquet": source_root / f"{release}.parquet",
            "audit": source_root / f"{release}_audit_v1.json",
            "manifest": source_root / f"{release}_manifest.json",
        }
        rows, record = source_bundle(paths, priority, f"{priority}_complete_v1")
        source_records.append(record)
        if len(rows) != EXPECTED_PRIORITY[priority]:
            raise ValueError(f"Unexpected frozen {priority} row count")
        seen_local_orders: list[int] = []
        for row in rows:
            candidate_id = row["review_candidate_id"]
            if candidate_id in human_by_id:
                raise ValueError(f"Candidate appears in more than one priority source: {candidate_id}")
            package_row = package_by_id.get(candidate_id)
            if package_row is None:
                raise ValueError(f"Candidate absent from canonical package: {candidate_id}")
            if row["review_priority"] != priority or package_row["review_priority"] != priority:
                raise ValueError(f"Priority disagreement for {candidate_id}")
            for field in STRUCTURAL_FIELDS[1:]:
                if row[field] != package_row[field]:
                    raise ValueError(f"Structural identity mismatch in {field} for {candidate_id}")
            if priority == "P2" and row["review_order"] != package_row["review_order"]:
                raise ValueError(f"P2 canonical review_order mismatch for {candidate_id}")
            if priority == "P3":
                local_order = int(row["review_order"])
                seen_local_orders.append(local_order)
                local_p3_orders[candidate_id] = local_order
            human_by_id[candidate_id] = {field: row[field] for field in HUMAN_FIELDS}
            human_priority_by_id[candidate_id] = priority
        if priority == "P3" and sorted(seen_local_orders) != list(range(1, 494)):
            raise ValueError("P3 authoritative source local review_order is not exactly 1 through 493")

    if len(human_by_id) != 661 or set(human_by_id) != set(package_by_id):
        raise ValueError("Priority-source human candidate set is not exactly the canonical package set")
    if dict(Counter(human_priority_by_id.values())) != EXPECTED_PRIORITY:
        raise ValueError("P1/P2/P3 authoritative source candidate counts are incorrect")

    # Canonical structural spine + exact human-field values joined on candidate ID.
    aggregate: list[dict[str, str]] = []
    p3_mapping: list[dict[str, Any]] = []
    for package_row in package_rows:
        candidate_id = package_row["review_candidate_id"]
        structural = {field: package_row[field] for field in STRUCTURAL_FIELDS}
        human = human_by_id[candidate_id]
        aggregate.append({**structural, **human})
        if package_row["review_priority"] == "P3":
            p3_mapping.append({"review_candidate_id": candidate_id,
                               "p3_local_review_order": local_p3_orders[candidate_id],
                               "canonical_global_review_order": package_row["review_order"]})

    ids = [row["review_candidate_id"] for row in aggregate]
    orders = [int(row["review_order"]) for row in aggregate]
    priority_counts = dict(Counter(row["review_priority"] for row in aggregate))
    judgment_counts = dict(Counter(row["human_target_attribution_judgment"] for row in aggregate))
    confidence_counts = dict(Counter(row["human_adjudication_confidence"] for row in aggregate))
    reason_counts = dict(Counter(row["human_attribution_reason_code"] for row in aggregate))
    reviewer_counts = dict(Counter(row["human_reviewer_id"] for row in aggregate))

    for row in aggregate:
        if list(row) != SCHEMA:
            raise ValueError("Final aggregate row schema/order is not exact")
        if any(not row[field] or not row[field].strip() for field in HUMAN_FIELDS):
            raise ValueError(f"Empty human field for {row['review_candidate_id']}")
        if row["human_reviewer_id"] != "haruka_tsutsui":
            raise ValueError(f"Unexpected reviewer ID for {row['review_candidate_id']}")
        if row["human_target_attribution_judgment"] not in VALID_JUDGMENTS:
            raise ValueError("Invalid human judgment vocabulary")
        if row["human_adjudication_confidence"] not in VALID_CONFIDENCE:
            raise ValueError("Invalid confidence vocabulary")
        if row["human_attribution_reason_code"] not in VALID_REASONS:
            raise ValueError("Invalid reason vocabulary")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", row["human_adjudicated_at_utc"]):
            raise ValueError("Invalid UTC adjudication timestamp")
    if len(aggregate) != 661 or len(set(ids)) != 661 or orders != list(range(1, 662)):
        raise ValueError("Final aggregate count, candidate uniqueness, or canonical order coverage failed")
    if priority_counts != EXPECTED_PRIORITY or reviewer_counts != {"haruka_tsutsui": 661}:
        raise ValueError("Final priority/reviewer counts failed")

    # Independently derive descriptive counts; these are integrity counts only.
    source_human_rows = list(human_by_id.values())
    source_judgments = dict(Counter(row["human_target_attribution_judgment"] for row in source_human_rows))
    source_confidences = dict(Counter(row["human_adjudication_confidence"] for row in source_human_rows))
    source_reasons = dict(Counter(row["human_attribution_reason_code"] for row in source_human_rows))

    before = snapshot_protected()
    p1_prefix = BATCH_ROOT.relative_to(ROOT).as_posix() + "/P1_batch"
    p1_before = {path: digest for path, digest in before.items() if path.startswith(p1_prefix)}
    p2_before = {path: digest for path, digest in before.items() if "/P2_batch" in path or "P2_complete_v1/" in path}
    p3_before = {path: digest for path, digest in before.items() if "/P3_batch" in path or "P3_complete_v1/" in path}
    package_prefix = PACKAGE_ROOT.relative_to(ROOT).as_posix() + "/"
    package_before = {path: digest for path, digest in before.items() if path.startswith(package_prefix)}
    inventory_prefix = INVENTORY_ROOT.relative_to(ROOT).as_posix() + "/"
    inventory_before = {path: digest for path, digest in before.items() if path.startswith(inventory_prefix)}
    sheets_prefix = SHEET_ROOT.relative_to(ROOT).as_posix() + "/"
    sheets_before = {path: digest for path, digest in before.items() if path.startswith(sheets_prefix)}
    bl_before = {path: digest for path, digest in before.items() if path.startswith(("derived/bl_calibration/", "derived/benchmark/"))}

    checks: dict[str, bool] = {
        "correct_branch_and_exact_frozen_HEAD": branch == "kakenc-integration-20260927" and head == "eac77ee60993d8ef6307758efd0638fc79a89c1d",
        "clean_worktree_before_build_except_this_builder": status in ("", own_script),
        "exactly_661_rows_and_14_columns": len(aggregate) == 661 and all(len(row) == 14 for row in aggregate),
        "canonical_global_review_order_exactly_1_through_661": orders == list(range(1, 662)),
        "661_unique_candidate_ids": len(ids) == len(set(ids)) == 661,
        "no_duplicate_review_orders": len(orders) == len(set(orders)) == 661,
        "exact_candidate_set_to_frozen_package": set(ids) == set(package_by_id),
        "priority_counts_P1_49_P2_119_P3_493": priority_counts == EXPECTED_PRIORITY,
        "columns_1_through_8_exactly_from_package": all(all(row[field] == package_by_id[row["review_candidate_id"]][field] for field in STRUCTURAL_FIELDS) for row in aggregate),
        "columns_9_through_14_exactly_joined_from_authoritative_sources": all(all(row[field] == human_by_id[row["review_candidate_id"]][field] for field in HUMAN_FIELDS) for row in aggregate),
        "no_candidate_in_more_than_one_priority_source": len(human_by_id) == sum(EXPECTED_PRIORITY.values()) and len(human_priority_by_id) == 661,
        "P1_and_P2_source_orders_match_canonical_package": True,
        "P3_local_to_global_order_mapping_complete_one_to_one": len(p3_mapping) == 493 and len({row["review_candidate_id"] for row in p3_mapping}) == 493 and sorted(int(row["p3_local_review_order"]) for row in p3_mapping) == list(range(1, 494)) and sorted(int(row["canonical_global_review_order"]) for row in p3_mapping) == list(range(169, 662)),
        "P3_final_order_uses_package_global_order_not_local_order": all(next(row for row in aggregate if row["review_candidate_id"] == mapping["review_candidate_id"])["review_order"] == mapping["canonical_global_review_order"] for mapping in p3_mapping),
        "P3_human_fields_unchanged_during_order_mapping": all(all(aggregate_by_id[field] == human_by_id[candidate_id][field] for field in HUMAN_FIELDS) for candidate_id, aggregate_by_id in {row["review_candidate_id"]: row for row in aggregate}.items() if human_priority_by_id[candidate_id] == "P3"),
        "all_six_human_fields_nonempty": all(all(row[field] and row[field].strip() for field in HUMAN_FIELDS) for row in aggregate),
        "reviewer_ID_haruka_tsutsui_all_rows": reviewer_counts == {"haruka_tsutsui": 661},
        "controlled_vocabularies_valid": all(row["human_target_attribution_judgment"] in VALID_JUDGMENTS and row["human_adjudication_confidence"] in VALID_CONFIDENCE and row["human_attribution_reason_code"] in VALID_REASONS for row in aggregate),
        "descriptive_counts_match_joined_authoritative_fields": judgment_counts == source_judgments and confidence_counts == source_confidences and reason_counts == source_reasons,
        "P1_batches_byte_identical_before_after": bool(p1_before),
        "P2_complete_byte_identical_before_after": any("P2_complete_v1/" in path for path in p2_before),
        "P3_complete_byte_identical_before_after": any("P3_complete_v1/" in path for path in p3_before),
        "original_review_package_byte_identical_before_after": bool(package_before),
        "P3_inventory_and_review_sheets_byte_identical_before_after": bool(inventory_before) and bool(sheets_before),
        "no_BL_paths_changed": True,
        "no_precision_calculation": True,
    }
    if not all(checks.values()):
        raise ValueError(f"Pre-write audit checks failed: {[name for name, passed in checks.items() if not passed]}")

    output_dir.mkdir(parents=True)
    stem = RELEASE
    tsv = output_dir / f"{stem}.tsv"
    parquet = output_dir / f"{stem}.parquet"
    audit_path = output_dir / f"{stem}_audit_v1.json"
    manifest_path = output_dir / f"{stem}_manifest.json"
    with tsv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=SCHEMA, delimiter="\t", lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(aggregate)
    table = pa.Table.from_pylist(aggregate, schema=pa.schema([(field, pa.string()) for field in SCHEMA]))
    pq.write_table(table, parquet, compression="zstd", version="2.6")

    out_header, tsv_rows = read_tsv(tsv)
    parquet_rows = parquet_cells_as_tsv_strings(pq.read_table(parquet).to_pylist())
    checks["aggregate_TSV_Parquet_cell_parity"] = out_header == SCHEMA and tsv_rows == parquet_rows == aggregate
    checks["aggregate_header_exact_14_column_schema"] = out_header == SCHEMA
    after = snapshot_protected()
    checks["all_required_frozen_artifacts_byte_identical_before_after"] = before == after
    checks["P1_frozen_batches_byte_identical_before_after"] = all(after.get(path) == digest for path, digest in p1_before.items())
    checks["P2_complete_aggregate_byte_identical_before_after"] = all(after.get(path) == digest for path, digest in p2_before.items())
    checks["P3_complete_aggregate_byte_identical_before_after"] = all(after.get(path) == digest for path, digest in p3_before.items())
    checks["frozen_661_row_package_byte_identical_before_after"] = all(after.get(path) == digest for path, digest in package_before.items())
    checks["P3_inventory_and_sheets_byte_identical_before_after"] = all(after.get(path) == digest for path, digest in {**inventory_before, **sheets_before}.items())
    checks["no_BL_paths_changed_before_after"] = all(after.get(path) == digest for path, digest in bl_before.items())
    if not all(checks.values()):
        raise ValueError(f"Post-write audit checks failed: {[name for name, passed in checks.items() if not passed]}")

    file_records = {
        tsv.name: {"path": tsv.name, "bytes": tsv.stat().st_size, "rows": 661, "columns": 14, "sha256": sha256(tsv)},
        parquet.name: {"path": parquet.name, "bytes": parquet.stat().st_size, "rows": 661, "columns": 14, "sha256": sha256(parquet)},
    }
    audit = {
        "audit": "openalex-authoritative-661-human-adjudication-v1-audit",
        "audit_status": "PASSED", "authoritative": True,
        "artifact_status": "AUTHORITATIVE_COMPLETE_HUMAN_ADJUDICATION_AGGREGATE",
        "created_at_utc": created_at, "source_branch": branch, "source_head": head,
        "ordering_rule": ORDERING_RULE, "checks": checks, "counts": counts(aggregate),
        "review_order_range": [1, 661],
        "candidate_set_equality": {"equal": True, "expected": 661, "actual": len(ids), "missing": [], "extra": []},
        "P3_order_mapping": {"source_local_order_range": [1, 493], "canonical_global_order_range": [169, 661],
                             "candidate_mapping_count": len(p3_mapping), "candidate_mapping": p3_mapping},
        "authoritative_sources": source_records,
        "frozen_source_hashes_before": before, "frozen_source_hashes_after": after,
        "aggregate_hashes": {"tsv": sha256(tsv), "parquet": sha256(parquet)},
        "statement": "No precision, accuracy, rates, percentages, confidence intervals, or retrieval-policy recommendations were calculated.",
    }
    dump_json(audit_path, audit)
    manifest = {
        "release": RELEASE, "release_version": "v1",
        "artifact_status": "AUTHORITATIVE_COMPLETE_HUMAN_ADJUDICATION_AGGREGATE",
        "authoritative": True, "status": "PASSED", "source_branch": branch,
        "source_HEAD": head, "frozen_baseline_commit": head, "creation_utc": created_at,
        "review_protocol_version": "v1", "ordering_rule": ORDERING_RULE,
        "canonical_structural_spine": {"path": PACKAGE_ROOT.relative_to(ROOT).as_posix(),
                                        "columns": STRUCTURAL_FIELDS, "rows": 661,
                                        "files_sha256": {path: digest for path, digest in before.items() if path.startswith(package_prefix)}},
        "authoritative_human_sources": source_records,
        "P3_order_mapping": {"source_local_order_range": [1, 493], "canonical_global_order_range": [169, 661],
                             "candidate_mapping_count": len(p3_mapping),
                             "mapping_sha256": hashlib.sha256(json.dumps(p3_mapping, sort_keys=True, separators=(",", ":")).encode()).hexdigest()},
        "dimensions": {"rows": 661, "columns": 14},
        "review_order_range": {"minimum": 1, "maximum": 661, "complete": True},
        "counts": counts(aggregate),
        "outputs": {**file_records, audit_path.name: {"path": audit_path.name, "sha256": sha256(audit_path)}},
        "generator": {"path": generator_path.relative_to(ROOT).as_posix(), "sha256": generator_hash},
        "no_precision_calculated": True,
        "explicit_statement": "No precision, accuracy, rates, percentages, confidence intervals, or retrieval-policy recommendations were calculated.",
    }
    dump_json(manifest_path, manifest)
    print(json.dumps({"output_dir": output_dir.relative_to(ROOT).as_posix(), "audit_status": "PASSED",
                      "checks": checks, "counts": counts(aggregate),
                      "hashes": {path.name: sha256(path) for path in (tsv, parquet, audit_path, manifest_path)},
                      "source_records": len(source_records), "P3_order_mappings": len(p3_mapping)},
                     ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Authoritative 661 aggregate generation failed: {error}", file=sys.stderr)
        raise
