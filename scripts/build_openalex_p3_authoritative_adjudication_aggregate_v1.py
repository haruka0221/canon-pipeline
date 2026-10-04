#!/usr/bin/env python3
"""Build and audit the frozen-ready aggregate of authoritative P3 adjudications.

The TSV rows are copied as parsed string cells from P3_batch01..P3_batch25 and
sorted by review_order. No adjudication field is interpreted or rewritten.
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
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
RELEASE = "openalex_retrieval_precision_review_human_adjudication_P3_complete_v1"
OUTPUT_DIR = ROOT / "derived/openalex_production" / RELEASE / "full_profile_57959e90"
BATCH_ROOT = ROOT / "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_batches_v1/full_profile_57959e90"
INVENTORY = ROOT / "derived/openalex_production/p3_deterministic_review_inventory_v1/full_profile_57959e90/openalex_p3_deterministic_review_inventory_v1_candidates.tsv"
SHEET_ROOT = ROOT / "derived/openalex_production/openalex_retrieval_precision_review_P3_human_review_sheets_v1/full_profile_57959e90"
REVIEW_PACKAGE_ROOT = ROOT / "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_v1/full_profile_57959e90"
P2_GROUPING_ROOT = ROOT / "derived/openalex_production/p2_deterministic_grouping_v1/full_profile_57959e90"
P2_COMPLETE_ROOT = ROOT / "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_P2_complete_v1/full_profile_57959e90"
PROTOCOL = ROOT / "docs/OPENALEX_PRECISION_REVIEW_PROTOCOL_V1.md"

SCHEMA = [
    "review_order",
    "review_priority",
    "review_candidate_id",
    "project_work_id",
    "openalex_work_id",
    "increment_type",
    "review_semantic_group_id",
    "review_protocol_version",
    "human_target_attribution_judgment",
    "human_adjudication_confidence",
    "human_attribution_reason_code",
    "human_reviewer_note",
    "human_reviewer_id",
    "human_adjudicated_at_utc",
]
HUMAN_FIELDS = SCHEMA[8:]
EXPECTED_JUDGMENTS = {
    "VALID_TARGET_REFERENCE": 487,
    "INVALID_TARGET_REFERENCE": 1,
    "UNCERTAIN": 5,
}
EXPECTED_CONFIDENCE = {"HIGH": 493}
EXPECTED_REASONS = {
    "DIRECT_TARGET_REFERENCE": 462,
    "VALID_CONTEXTUAL_REFERENCE": 25,
    "INSUFFICIENT_CONTEXT": 1,
    "WRONG_WORK_SAME_AUTHOR": 1,
    "AMBIGUOUS_TARGET_REFERENCE": 4,
}
VALID_JUDGMENTS = set(EXPECTED_JUDGMENTS)
VALID_CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}
VALID_REASONS = {
    "DIRECT_TARGET_REFERENCE", "VALID_TITLE_VARIANT", "VALID_CONTEXTUAL_REFERENCE",
    "TITLE_COLLISION_DIFFERENT_WORK", "GENERIC_OR_LEXICAL_TITLE_USE",
    "AUTHOR_COLLISION_DIFFERENT_PERSON", "TITLE_AUTHOR_UNLINKED_COOCCURRENCE",
    "WRONG_WORK_SAME_AUTHOR", "ALIAS_NOT_TARGET_EQUIVALENT", "METADATA_TEXT_ARTIFACT",
    "INSUFFICIENT_CONTEXT", "AMBIGUOUS_TARGET_REFERENCE", "OTHER",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        if reader.fieldnames is None:
            raise ValueError(f"TSV has no header: {path}")
        rows = list(reader)
        if any(None in row for row in rows):
            raise ValueError(f"TSV row has more cells than the header: {path}")
        return list(reader.fieldnames), rows


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def tracked_paths() -> list[str]:
    data = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [p.decode() for p in data.split(b"\0") if p]


def protected_prefixes() -> tuple[str, ...]:
    return (
        "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_batches_v1/full_profile_57959e90/P1_batch",
        "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_batches_v1/full_profile_57959e90/P2_batch",
        "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_batches_v1/full_profile_57959e90/P3_batch",
        "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_P2_complete_v1/",
        "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_v1/",
        "derived/openalex_production/p2_deterministic_grouping_v1/",
        "derived/openalex_production/p3_deterministic_review_inventory_v1/",
        "derived/openalex_production/openalex_retrieval_precision_review_P3_human_review_sheets_v1/",
        "derived/bl_calibration/",
        "derived/benchmark/",
    )


def snapshot_protected() -> dict[str, str]:
    return {
        rel: sha256(ROOT / rel)
        for rel in tracked_paths()
        if any(rel.startswith(prefix) for prefix in protected_prefixes())
    }


def counts(rows: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "columns": len(SCHEMA),
        "review_priority": dict(Counter(r["review_priority"] for r in rows)),
        "human_target_attribution_judgment": dict(Counter(r["human_target_attribution_judgment"] for r in rows)),
        "human_adjudication_confidence": dict(Counter(r["human_adjudication_confidence"] for r in rows)),
        "human_attribution_reason_code": dict(Counter(r["human_attribution_reason_code"] for r in rows)),
        "reviewer_id": dict(Counter(r["human_reviewer_id"] for r in rows)),
    }


def dump_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise SystemExit(f"Refusing to overwrite existing output directory: {output_dir}")

    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    head = git_head()
    created_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    generator_hash = sha256(Path(__file__).resolve())
    before = snapshot_protected()

    # Read and validate the authoritative P3 review inventory and all review sheets.
    inventory_header, inventory_rows = read_tsv(INVENTORY)
    required_inventory_fields = {
        "review_priority", "p3_review_order", "review_candidate_id", "project_work_id",
        "openalex_work_id", "increment_type", "review_semantic_group_id", "review_protocol_version",
        "p3_review_batch_id",
    }
    if not required_inventory_fields.issubset(inventory_header):
        raise ValueError("Frozen P3 inventory is missing required fields")
    p3_inventory = [r for r in inventory_rows if r["review_priority"] == "P3"]
    inventory_by_order = {int(r["p3_review_order"]): r for r in p3_inventory}
    expected_orders = list(range(1, 494))
    expected_ids = {r["review_candidate_id"] for r in p3_inventory}
    if len(p3_inventory) != 493 or len(expected_ids) != 493 or set(inventory_by_order) != set(expected_orders):
        raise ValueError("Frozen P3 inventory does not contain the exact 493 candidates/orders")

    sheet_members: list[tuple[int, str]] = []
    for sequence in range(1, 26):
        sheet = SHEET_ROOT / f"P3B{sequence:02d}.md"
        if not sheet.is_file():
            raise FileNotFoundError(sheet)
        content = sheet.read_text(encoding="utf-8")
        sheet_members.extend(
            (int(order), candidate_id)
            for candidate_id, order in re.findall(
                r"#### Candidate (OAPRV3_[A-Za-z0-9]+) — review order (\d+)", content
            )
        )
    expected_sheet_members = [(o, inventory_by_order[o]["review_candidate_id"]) for o in expected_orders]
    if sheet_members != expected_sheet_members:
        raise ValueError("Frozen review-sheet membership/order differs from the P3 inventory")

    # Read the 25 authoritative batches with csv.DictReader (quoted tabs/newlines preserved).
    batch_rows: list[dict[str, str]] = []
    source_batches: list[dict[str, Any]] = []
    batch_files_before: dict[str, str] = {}
    for sequence in range(1, 26):
        batch_name = f"P3_batch{sequence:02d}"
        batch_dir = BATCH_ROOT / batch_name
        stem = f"openalex_retrieval_precision_review_human_adjudication_{batch_name}_v1"
        tsv_path = batch_dir / f"{stem}.tsv"
        parquet_path = batch_dir / f"{stem}.parquet"
        audit_path = batch_dir / f"{stem}_audit_v1.json"
        manifest_path = batch_dir / f"{stem}_manifest.json"
        if not all(p.is_file() for p in (tsv_path, parquet_path, audit_path, manifest_path)):
            raise FileNotFoundError(f"Incomplete source batch: {batch_name}")
        source_header, rows = read_tsv(tsv_path)
        if source_header != SCHEMA:
            raise ValueError(f"Unexpected columns in {batch_name}: {source_header}")
        batch_audit = read_json(audit_path)
        if batch_audit.get("audit_status") != "PASSED":
            raise ValueError(f"Source batch audit did not pass: {batch_name}")
        parquet_rows = pq.read_table(parquet_path).to_pylist()
        if parquet_rows != rows:
            raise ValueError(f"Source TSV/Parquet cell parity failed: {batch_name}")
        for p in (tsv_path, parquet_path, audit_path, manifest_path):
            rel = p.relative_to(ROOT).as_posix()
            batch_files_before[rel] = sha256(p)
        source_batches.append({
            "batch": batch_name,
            "path": batch_dir.relative_to(ROOT).as_posix(),
            "rows": len(rows),
            "columns": len(source_header),
            "audit_status": batch_audit["audit_status"],
            "files_sha256": {
                tsv_path.name: batch_files_before[tsv_path.relative_to(ROOT).as_posix()],
                parquet_path.name: batch_files_before[parquet_path.relative_to(ROOT).as_posix()],
                audit_path.name: batch_files_before[audit_path.relative_to(ROOT).as_posix()],
                manifest_path.name: batch_files_before[manifest_path.relative_to(ROOT).as_posix()],
            },
            "tsv_parquet_cell_parity": True,
        })
        batch_rows.extend(rows)

    # Stable numeric order; all source cells remain unchanged strings.
    aggregate = sorted(batch_rows, key=lambda row: int(row["review_order"]))
    if any(list(row.keys()) != SCHEMA for row in aggregate):
        raise ValueError("Source rows do not share the exact adjudication schema")

    package_tsv = REVIEW_PACKAGE_ROOT / "openalex_retrieval_precision_review_human_adjudication_v1.tsv"
    _, package_rows = read_tsv(package_tsv)
    package_by_id = {r["review_candidate_id"]: r for r in package_rows}
    if len(package_by_id) != len(package_rows):
        raise ValueError("Frozen review package candidate IDs are not unique")

    identity_fields = [
        "review_priority", "review_candidate_id", "project_work_id", "openalex_work_id",
        "increment_type", "review_semantic_group_id", "review_protocol_version",
    ]
    for row in aggregate:
        order = int(row["review_order"])
        inv = inventory_by_order.get(order)
        package = package_by_id.get(row["review_candidate_id"])
        if inv is None or package is None:
            raise ValueError(f"Aggregate row lacks frozen inventory/package identity: {order}")
        if row["review_priority"] != "P3" or inv["review_priority"] != "P3" or package["review_priority"] != "P3":
            raise ValueError(f"Non-P3 candidate present at review order {order}")
        if row["review_candidate_id"] != inv["review_candidate_id"]:
            raise ValueError(f"Candidate/order mismatch against inventory at {order}")
        if any(row[k] != inv[k] or row[k] != package[k] for k in identity_fields):
            raise ValueError(f"Frozen identity/provenance mismatch at review order {order}")
        if any(not row[k] or not row[k].strip() for k in HUMAN_FIELDS):
            raise ValueError(f"Empty human adjudication field at review order {order}")
        if row["human_reviewer_id"] != "haruka_tsutsui":
            raise ValueError(f"Unexpected reviewer at review order {order}")
        if row["human_target_attribution_judgment"] not in VALID_JUDGMENTS:
            raise ValueError(f"Invalid judgment at review order {order}")
        if row["human_adjudication_confidence"] not in VALID_CONFIDENCE:
            raise ValueError(f"Invalid confidence at review order {order}")
        if row["human_attribution_reason_code"] not in VALID_REASONS:
            raise ValueError(f"Invalid reason code at review order {order}")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", row["human_adjudicated_at_utc"]):
            raise ValueError(f"Invalid UTC timestamp at review order {order}")

    orders = [int(r["review_order"]) for r in aggregate]
    ids = [r["review_candidate_id"] for r in aggregate]
    judgment_counts = dict(Counter(r["human_target_attribution_judgment"] for r in aggregate))
    confidence_counts = dict(Counter(r["human_adjudication_confidence"] for r in aggregate))
    reason_counts = dict(Counter(r["human_attribution_reason_code"] for r in aggregate))
    reviewer_counts = dict(Counter(r["human_reviewer_id"] for r in aggregate))
    missing = sorted(expected_ids - set(ids))
    extra = sorted(set(ids) - expected_ids)

    run_prefix = "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_batches_v1/full_profile_57959e90/"
    p3_prior_paths = {
        rel: digest for rel, digest in before.items()
        if rel.startswith(run_prefix + "P3_batch") and not rel.startswith(run_prefix + "P3_batch26")
    }
    frozen_review_package = {
        rel: digest for rel, digest in before.items()
        if rel.startswith(REVIEW_PACKAGE_ROOT.relative_to(ROOT).as_posix() + "/")
    }
    frozen_sheets = {
        rel: digest for rel, digest in before.items()
        if rel.startswith(SHEET_ROOT.relative_to(ROOT).as_posix() + "/")
    }
    frozen_inventory = {
        rel: digest for rel, digest in before.items()
        if rel.startswith(INVENTORY.parent.relative_to(ROOT).as_posix() + "/")
    }

    checks = {
        "exactly_25_source_P3_batches_present": len(source_batches) == 25 and [b["batch"] for b in source_batches] == [f"P3_batch{i:02d}" for i in range(1, 26)],
        "all_source_batch_audits_passed": all(b["audit_status"] == "PASSED" for b in source_batches),
        "all_source_batch_TSV_Parquet_cell_parity": all(b["tsv_parquet_cell_parity"] for b in source_batches),
        "source_batch_row_counts_sum_to_493": sum(b["rows"] for b in source_batches) == 493 and len(batch_rows) == 493,
        "exactly_493_aggregate_rows": len(aggregate) == 493,
        "exact_review_order_coverage_1_through_493": orders == expected_orders,
        "review_candidate_id_unique": len(ids) == len(set(ids)) == 493,
        "review_order_unique": len(orders) == len(set(orders)) == 493,
        "exact_candidate_ID_set_to_frozen_P3_inventory": set(ids) == expected_ids and not missing and not extra,
        "exact_candidate_membership_and_order_from_frozen_sheets": sheet_members == expected_sheet_members,
        "all_candidates_are_P3_no_P1_or_P2": all(r["review_priority"] == "P3" for r in aggregate),
        "source_identity_and_provenance_fields_match_inventory_and_review_package": True,
        "aggregate_rows_logically_equal_authoritative_source_batch_rows": sorted(batch_rows, key=lambda r: int(r["review_order"])) == aggregate,
        "all_six_human_fields_nonempty": all(all(r[k] and r[k].strip() for k in HUMAN_FIELDS) for r in aggregate),
        "reviewer_id_haruka_tsutsui_all_rows": reviewer_counts == {"haruka_tsutsui": 493},
        "controlled_vocabularies_valid": all(r["human_target_attribution_judgment"] in VALID_JUDGMENTS and r["human_adjudication_confidence"] in VALID_CONFIDENCE and r["human_attribution_reason_code"] in VALID_REASONS for r in aggregate),
        "expected_descriptive_judgment_counts": judgment_counts == EXPECTED_JUDGMENTS,
        "expected_descriptive_confidence_counts": confidence_counts == EXPECTED_CONFIDENCE,
        "expected_descriptive_reason_counts": reason_counts == EXPECTED_REASONS,
        "all_P3_batch01_through_25_byte_identical_before_after": all(sha256(ROOT / rel) == digest for rel, digest in p3_prior_paths.items()) and all(rel.startswith(run_prefix + "P3_batch") for rel in p3_prior_paths),
        "frozen_review_package_byte_identical_before_after": all(sha256(ROOT / rel) == digest for rel, digest in frozen_review_package.items()),
        "frozen_P3_inventory_byte_identical_before_after": all(sha256(ROOT / rel) == digest for rel, digest in frozen_inventory.items()),
        "frozen_P3_review_sheets_byte_identical_before_after": all(sha256(ROOT / rel) == digest for rel, digest in frozen_sheets.items()),
        "all_prior_P1_P2_and_P2_aggregate_artifacts_byte_identical": all(sha256(ROOT / rel) == digest for rel, digest in before.items() if "/P1_batch" in rel or "/P2_batch" in rel or "P2_complete_v1/" in rel or "p2_deterministic_grouping_v1/" in rel),
        "no_BL_paths_changed": all(sha256(ROOT / rel) == digest for rel, digest in before.items() if rel.startswith("derived/bl_calibration/") or rel.startswith("derived/benchmark/")),
        "no_precision_calculation": True,
    }
    if not all(checks.values()):
        raise ValueError(f"Aggregate audit checks failed: {[k for k, v in checks.items() if not v]}")

    output_dir.mkdir(parents=True)
    stem = f"{RELEASE}"
    tsv_path = output_dir / f"{stem}.tsv"
    parquet_path = output_dir / f"{stem}.parquet"
    audit_path = output_dir / f"{stem}_audit_v1.json"
    manifest_path = output_dir / f"{stem}_manifest.json"
    with tsv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SCHEMA, delimiter="\t", lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(aggregate)
    aggregate_table = pa.Table.from_pylist(aggregate, schema=pa.schema([(field, pa.string()) for field in SCHEMA]))
    pq.write_table(aggregate_table, parquet_path, compression="zstd", version="2.6")

    # Read outputs back through independent parsers for row/cell parity.
    output_header, output_tsv_rows = read_tsv(tsv_path)
    output_parquet_rows = pq.read_table(parquet_path).to_pylist()
    if output_header != SCHEMA or output_tsv_rows != aggregate or output_parquet_rows != aggregate:
        raise ValueError("Aggregate output TSV/Parquet cell parity failed")
    checks["aggregate_TSV_Parquet_cell_parity"] = output_tsv_rows == output_parquet_rows == aggregate
    checks["aggregate_TSV_header_exact_schema"] = output_header == SCHEMA
    after = snapshot_protected()
    checks["all_frozen_source_files_byte_identical_before_after"] = before == after
    checks["all_P3_batch01_through_25_byte_identical_before_after"] = all(after.get(rel) == digest for rel, digest in batch_files_before.items()) and checks["all_P3_batch01_through_25_byte_identical_before_after"]
    checks["no_BL_paths_changed"] = checks["no_BL_paths_changed"] and all(after.get(rel) == digest for rel, digest in before.items() if rel.startswith("derived/bl_calibration/") or rel.startswith("derived/benchmark/"))
    if not all(checks.values()):
        raise ValueError(f"Post-write audit checks failed: {[k for k, v in checks.items() if not v]}")

    output_records = {
        tsv_path.name: {"path": tsv_path.name, "bytes": tsv_path.stat().st_size, "rows": 493, "columns": 14, "sha256": sha256(tsv_path)},
        parquet_path.name: {"path": parquet_path.name, "bytes": parquet_path.stat().st_size, "rows": 493, "columns": 14, "sha256": sha256(parquet_path)},
    }
    audit = {
        "audit": "openalex-authoritative-P3-complete-aggregate-v1-audit",
        "audit_status": "PASSED",
        "authoritative": True,
        "artifact_status": "AUTHORITATIVE_P3_COMPLETE_HUMAN_ADJUDICATION_AGGREGATE",
        "created_at_utc": created_at,
        "source_branch": branch,
        "source_head": head,
        "checks": checks,
        "counts": {
            **counts(aggregate),
            "semantic_groups": len({r["review_semantic_group_id"] for r in aggregate}),
        },
        "review_order_range": [1, 493],
        "candidate_set_equality": {"equal": not missing and not extra, "expected": 493, "actual": len(ids), "missing": missing, "extra": extra},
        "source_batches": {b["batch"]: b for b in source_batches},
        "source_file_hashes_before_after": {"before": before, "after": after},
        "aggregate_hashes": {"tsv": sha256(tsv_path), "parquet": sha256(parquet_path)},
        "statement": "No precision, accuracy, rates, percentages, confidence intervals, or any other performance metric was calculated.",
    }
    dump_json(audit_path, audit)
    manifest = {
        "release": RELEASE,
        "release_version": "v1",
        "artifact_status": "AUTHORITATIVE_P3_COMPLETE_HUMAN_ADJUDICATION_AGGREGATE",
        "authoritative": True,
        "status": "PASSED",
        "source_branch": branch,
        "source_HEAD": head,
        "frozen_baseline_commit": head,
        "creation_utc": created_at,
        "review_protocol_version": "v1",
        "source_review_package": {
            "path": REVIEW_PACKAGE_ROOT.relative_to(ROOT).as_posix(),
            "rows": len(package_rows),
            "files_sha256": {rel: digest for rel, digest in before.items() if rel.startswith(REVIEW_PACKAGE_ROOT.relative_to(ROOT).as_posix() + "/")},
        },
        "source_P3_inventory": {
            "path": INVENTORY.relative_to(ROOT).as_posix(),
            "rows": len(p3_inventory),
            "files_sha256": frozen_inventory,
        },
        "source_P3_review_sheets": {
            "path": SHEET_ROOT.relative_to(ROOT).as_posix(),
            "sheets": 25,
            "files_sha256": frozen_sheets,
        },
        "source_batches": source_batches,
        "dimensions": {"rows": 493, "columns": 14},
        "review_order_range": {"minimum": 1, "maximum": 493, "complete": True},
        "counts": counts(aggregate),
        "outputs": {
            **output_records,
            audit_path.name: {"path": audit_path.name, "sha256": sha256(audit_path)},
        },
        "generator": {
            "path": Path(__file__).resolve().relative_to(ROOT).as_posix(),
            "sha256": generator_hash,
        },
        "no_precision_calculated": True,
        "explicit_statement": "No precision, accuracy, rates, percentages, confidence intervals, or any other performance metric was calculated.",
    }
    dump_json(manifest_path, manifest)
    print(json.dumps({
        "output_dir": output_dir.relative_to(ROOT).as_posix() if output_dir.is_relative_to(ROOT) else str(output_dir),
        "audit_status": audit["audit_status"],
        "checks": checks,
        "counts": counts(aggregate),
        "hashes": {p.name: sha256(p) for p in (tsv_path, parquet_path, audit_path, manifest_path)},
        "source_batches": len(source_batches),
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"P3 authoritative aggregate generation failed: {exc}", file=sys.stderr)
        raise
