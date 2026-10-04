#!/usr/bin/env python3
"""Calculate and audit descriptive marginal-candidate results per frozen spec."""

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
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
RELEASE = "openalex_retrieval_precision_results_v1"
OUTPUT_DIR = ROOT / "derived/openalex_production" / RELEASE / "full_profile_57959e90"
INPUT = ROOT / "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_complete_v1/full_profile_57959e90/openalex_retrieval_precision_review_human_adjudication_complete_v1.tsv"
INPUT_AUDIT = INPUT.with_name("openalex_retrieval_precision_review_human_adjudication_complete_v1_audit_v1.json")
SPEC = ROOT / "docs/OPENALEX_RETRIEVAL_PRECISION_REPORTING_SPEC_V1.md"
EXPECTED_HEAD = "c82324055bba36c04a2892d8f6ba9bd3c2b8c302"
EXPECTED_INPUT_SHA256 = "a6d7dfe0e59407210c3fbb06f03ed4719b1a00f2aae1a516acb27b81c570c667"
EXPECTED_SPEC_SHA256 = "73220eca910c7fd5883f2a74d55a745938cbc4a66cba7da31c404949ea070259"
EXPECTED_PRIORITY = {"P1": 49, "P2": 119, "P3": 493}
EXPECTED_INCREMENT = {"ALIAS_EXPANSION": 409, "A2_AUTHOR_REVERSAL": 252}
EXPECTED_JUDGMENT = {"VALID_TARGET_REFERENCE": 605, "INVALID_TARGET_REFERENCE": 34, "UNCERTAIN": 22}
EXPECTED_CONFIDENCE = {"HIGH": 661}
STRATA = (
    ("ALL_MARGINAL_CANDIDATES", None),
    ("ALIAS_EXPANSION", "ALIAS_EXPANSION"),
    ("A2_AUTHOR_REVERSAL", "A2_AUTHOR_REVERSAL"),
)
METRICS = (
    ("confirmed_valid", "valid", "candidate_count"),
    ("adjudication_lower", "valid", "candidate_count"),
    ("adjudication_upper", "valid_plus_uncertain", "candidate_count"),
    ("resolved_case", "valid", "resolved_count"),
)
ROUNDING = "Display values are proportions rounded to 6 decimal places using decimal ROUND_HALF_EVEN; machine values are float64 round-trip values, and exact rational numerators/denominators are retained."
SCOPE = "Descriptive precision estimates for the audited marginal candidate universe only; not overall OpenAlex retrieval precision, R2 baseline precision, R4 title-only precision, recall, coverage, or complete-pipeline precision."
NO_CI = "No ordinary statistical confidence interval (including binomial or Wilson intervals) was calculated. Adjudication bounds are identification/adjudication bounds, not confidence intervals."


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames is None:
            raise ValueError(f"Missing TSV header: {path}")
        rows = list(reader)
        if any(None in row for row in rows):
            raise ValueError(f"Extra TSV cells detected: {path}")
        return list(reader.fieldnames), rows


def json_read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git(args: list[str]) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def tracked_hashes() -> dict[str, str]:
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    protected = (
        "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_complete_v1/",
        "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_batches_v1/",
        "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_P2_complete_v1/",
        "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_P3_complete_v1/",
        "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_v1/",
        "derived/openalex_production/p3_deterministic_review_inventory_v1/",
        "derived/openalex_production/openalex_retrieval_precision_review_P3_human_review_sheets_v1/",
        "derived/openalex_production/p2_deterministic_grouping_v1/",
        "derived/bl_calibration/", "derived/benchmark/",
        "docs/OPENALEX_RETRIEVAL_PRECISION_REPORTING_SPEC_V1.md",
    )
    result = {}
    for raw in names:
        if not raw:
            continue
        rel = raw.decode()
        if rel.startswith(protected):
            result[rel] = digest(ROOT / rel)
    return result


def as_num(value: Fraction | None) -> float | None:
    return None if value is None else float(value)


def rounded_display(value: Fraction | None) -> str:
    if value is None:
        return ""
    with localcontext() as ctx:
        ctx.prec = 60
        decimal_value = Decimal(value.numerator) / Decimal(value.denominator)
        return format(decimal_value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN), "f")


def full_numeric(value: Fraction | None) -> str:
    return "" if value is None else format(float(value), ".17g")


def frac_fields(prefix: str, value: Fraction | None) -> dict[str, Any]:
    return {
        f"{prefix}_numerator": "" if value is None else str(value.numerator),
        f"{prefix}_denominator": "" if value is None else str(value.denominator),
        prefix: as_num(value),
        f"{prefix}_display": rounded_display(value),
    }


def work_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counter = Counter(row["human_target_attribution_judgment"] for row in rows)
    return {
        "candidate_count": len(rows),
        "valid_count": counter["VALID_TARGET_REFERENCE"],
        "invalid_count": counter["INVALID_TARGET_REFERENCE"],
        "uncertain_count": counter["UNCERTAIN"],
    }


def quantities(counts: dict[str, int]) -> dict[str, Fraction | None]:
    n = counts["candidate_count"]
    valid = counts["valid_count"]
    invalid = counts["invalid_count"]
    uncertain = counts["uncertain_count"]
    resolved = valid + invalid
    return {
        "confirmed_valid": Fraction(valid, n) if n else None,
        "adjudication_lower": Fraction(valid, n) if n else None,
        "adjudication_upper": Fraction(valid + uncertain, n) if n else None,
        "resolved_case": Fraction(valid, resolved) if resolved else None,
    }


SUMMARY_FIELDS = [
    "stratum", "candidate_count", "project_work_count", "valid_count", "invalid_count", "uncertain_count",
    "micro_confirmed_valid_numerator", "micro_confirmed_valid_denominator", "micro_confirmed_valid", "micro_confirmed_valid_display",
    "micro_adjudication_lower_numerator", "micro_adjudication_lower_denominator", "micro_adjudication_lower", "micro_adjudication_lower_display",
    "micro_adjudication_upper_numerator", "micro_adjudication_upper_denominator", "micro_adjudication_upper", "micro_adjudication_upper_display",
    "micro_resolved_case_numerator", "micro_resolved_case_denominator", "micro_resolved_case", "micro_resolved_case_display",
    "macro_w_confirmed_valid_contributing_work_count", "macro_w_confirmed_valid_numerator", "macro_w_confirmed_valid_denominator", "macro_w_confirmed_valid", "macro_w_confirmed_valid_display",
    "macro_w_adjudication_lower_contributing_work_count", "macro_w_adjudication_lower_numerator", "macro_w_adjudication_lower_denominator", "macro_w_adjudication_lower", "macro_w_adjudication_lower_display",
    "macro_w_adjudication_upper_contributing_work_count", "macro_w_adjudication_upper_numerator", "macro_w_adjudication_upper_denominator", "macro_w_adjudication_upper", "macro_w_adjudication_upper_display",
    "macro_w_resolved_case_contributing_work_count", "macro_w_resolved_case_numerator", "macro_w_resolved_case_denominator", "macro_w_resolved_case", "macro_w_resolved_case_display",
]

WORK_FIELDS = [
    "stratum", "project_work_id", "candidate_count", "valid_count", "invalid_count", "uncertain_count", "resolved_count",
    "confirmed_valid_numerator", "confirmed_valid_denominator", "confirmed_valid", "confirmed_valid_display",
    "adjudication_lower_numerator", "adjudication_lower_denominator", "adjudication_lower", "adjudication_lower_display",
    "adjudication_upper_numerator", "adjudication_upper_denominator", "adjudication_upper", "adjudication_upper_display",
    "resolved_case_numerator", "resolved_case_denominator", "resolved_case", "resolved_case_display",
]


def arrow_schema(fields: list[str]) -> pa.Schema:
    string_fields = {"stratum", "project_work_id"}
    integer_names = {"candidate_count", "project_work_count", "valid_count", "invalid_count", "uncertain_count", "resolved_count"}
    integer_names |= {name for name in fields if name.endswith("_contributing_work_count")}
    string_fields |= {name for name in fields if name.endswith("_numerator") or name.endswith("_denominator")}
    display_names = {name for name in fields if name.endswith("_display")}
    schema = []
    for name in fields:
        if name in string_fields or name in display_names:
            dtype = pa.string()
        elif name in integer_names:
            dtype = pa.int64()
        else:
            dtype = pa.float64()
        schema.append(pa.field(name, dtype))
    return pa.schema(schema)


def typed_tsv_rows(header: list[str], rows: list[dict[str, str]], schema: pa.Schema) -> list[dict[str, Any]]:
    types = {field.name: field.type for field in schema}
    converted = []
    for row in rows:
        value: dict[str, Any] = {}
        for name in header:
            raw = row[name]
            if raw == "":
                value[name] = None if pa.types.is_integer(types[name]) or pa.types.is_floating(types[name]) else ""
            elif pa.types.is_integer(types[name]):
                value[name] = int(raw)
            elif pa.types.is_floating(types[name]):
                value[name] = float(raw)
            else:
                value[name] = raw
        converted.append(value)
    return converted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    outdir = args.output_dir.resolve()
    expected_files = {
        f"{RELEASE}_summary.tsv", f"{RELEASE}_summary.parquet",
        f"{RELEASE}_by_work.tsv", f"{RELEASE}_by_work.parquet",
        f"{RELEASE}_audit_v1.json", f"{RELEASE}_manifest.json",
    }
    if outdir.exists() and {path.name for path in outdir.iterdir()} != expected_files:
        raise SystemExit(f"Refusing to overwrite a result directory with unexpected contents: {outdir}")

    branch = git(["git", "branch", "--show-current"])
    head = git(["git", "rev-parse", "HEAD"])
    status = git(["git", "status", "--porcelain=v1"])
    allowed_paths = {path.relative_to(ROOT).as_posix() for path in outdir.glob("*")} | {
        "scripts/build_openalex_retrieval_precision_results_v1.py"
    }
    status_paths = {line[3:] for line in status.splitlines() if len(line) >= 4}
    if branch != "kakenc-integration-20260927" or head != EXPECTED_HEAD:
        raise ValueError(f"Unexpected branch/HEAD: {branch} {head}")
    if not status_paths.issubset(allowed_paths):
        raise ValueError(f"Unexpected worktree changes; refusing to calculate/write: {status}")
    if digest(INPUT) != EXPECTED_INPUT_SHA256 or digest(SPEC) != EXPECTED_SPEC_SHA256:
        raise ValueError("Frozen input or specification SHA256 does not match the expected baseline")
    input_audit = json_read(INPUT_AUDIT)
    if input_audit.get("audit_status") != "PASSED":
        raise ValueError("Frozen authoritative aggregate audit is not PASSED")

    created = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    frozen_before = tracked_hashes()
    header, input_rows = read_tsv(INPUT)
    if header != [
        "review_order", "review_priority", "review_candidate_id", "project_work_id", "openalex_work_id",
        "increment_type", "review_semantic_group_id", "review_protocol_version",
        "human_target_attribution_judgment", "human_adjudication_confidence", "human_attribution_reason_code",
        "human_reviewer_note", "human_reviewer_id", "human_adjudicated_at_utc",
    ]:
        raise ValueError("Authoritative input does not have the frozen 14-column schema")
    ids = [row["review_candidate_id"] for row in input_rows]
    orders = [int(row["review_order"]) for row in input_rows]
    priority_counts = dict(Counter(row["review_priority"] for row in input_rows))
    increment_counts = dict(Counter(row["increment_type"] for row in input_rows))
    judgment_counts = dict(Counter(row["human_target_attribution_judgment"] for row in input_rows))
    confidence_counts = dict(Counter(row["human_adjudication_confidence"] for row in input_rows))
    reviewer_counts = dict(Counter(row["human_reviewer_id"] for row in input_rows))
    if len(input_rows) != 661 or len(set(ids)) != 661 or orders != list(range(1, 662)):
        raise ValueError("Authoritative input row, uniqueness, or global order validation failed")
    if priority_counts != EXPECTED_PRIORITY or judgment_counts != EXPECTED_JUDGMENT or confidence_counts != EXPECTED_CONFIDENCE:
        raise ValueError("Frozen priority or judgment/confidence totals differ from requested integrity checks")
    if increment_counts != EXPECTED_INCREMENT or sum(increment_counts.values()) != 661:
        raise ValueError(f"Unexpected increment_type labels/counts: {increment_counts}")
    if reviewer_counts != {"haruka_tsutsui": 661}:
        raise ValueError("Unexpected reviewer ID count")
    if any(not row[field].strip() for row in input_rows for field in header[8:]):
        raise ValueError("A human-adjudication field is empty")

    alias_rows = [row for row in input_rows if row["increment_type"] == "ALIAS_EXPANSION"]
    reversal_rows = [row for row in input_rows if row["increment_type"] == "A2_AUTHOR_REVERSAL"]
    alias_ids = {row["review_candidate_id"] for row in alias_rows}
    reversal_ids = {row["review_candidate_id"] for row in reversal_rows}
    alias_works = {row["project_work_id"] for row in alias_rows}
    reversal_works = {row["project_work_id"] for row in reversal_rows}
    if alias_ids & reversal_ids or alias_works & reversal_works:
        raise ValueError("Increment candidate or project-work strata overlap")
    if len(alias_works) != 38 or len(reversal_works) != 27 or len(alias_works | reversal_works) != 65:
        raise ValueError("Increment project-work counts differ from frozen reporting specification inventory")

    rows_by_stratum: dict[str, list[dict[str, str]]] = {}
    for name, increment in STRATA:
        rows_by_stratum[name] = input_rows if increment is None else [r for r in input_rows if r["increment_type"] == increment]

    by_work_rows: list[dict[str, Any]] = []
    by_work_index: dict[tuple[str, str], dict[str, Any]] = {}
    summary_rows: list[dict[str, Any]] = []
    work_counts_by_stratum: dict[str, dict[str, dict[str, int]]] = {}
    undefined_macro_work_ids: dict[str, list[str]] = {}
    for stratum, stratum_rows in rows_by_stratum.items():
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in stratum_rows:
            grouped[row["project_work_id"]].append(row)
        work_data: dict[str, dict[str, int]] = {}
        work_metric_values: dict[str, dict[str, Fraction | None]] = {}
        for work_id in sorted(grouped):
            counts = work_counts(grouped[work_id])
            counts["resolved_count"] = counts["valid_count"] + counts["invalid_count"]
            metrics = quantities(counts)
            work_data[work_id] = counts
            work_metric_values[work_id] = metrics
            result: dict[str, Any] = {"stratum": stratum, "project_work_id": work_id, **counts}
            for metric, _, _ in METRICS:
                result.update(frac_fields(metric, metrics[metric]))
            by_work_rows.append(result)
            by_work_index[(stratum, work_id)] = result
        work_counts_by_stratum[stratum] = work_data
        undefined_macro_work_ids[stratum] = sorted(work_id for work_id, metrics in work_metric_values.items() if metrics["resolved_case"] is None)

        pair_counts = work_counts(stratum_rows)
        pair_counts["resolved_count"] = pair_counts["valid_count"] + pair_counts["invalid_count"]
        micro = quantities(pair_counts)
        summary: dict[str, Any] = {
            "stratum": stratum, "candidate_count": pair_counts["candidate_count"],
            "project_work_count": len(grouped), "valid_count": pair_counts["valid_count"],
            "invalid_count": pair_counts["invalid_count"], "uncertain_count": pair_counts["uncertain_count"],
        }
        for metric, _, _ in METRICS:
            summary.update(frac_fields(f"micro_{metric}", micro[metric]))
            eligible = [values[metric] for values in work_metric_values.values() if values[metric] is not None]
            macro_value = sum(eligible, Fraction(0, 1)) / len(eligible) if eligible else None
            summary[f"macro_w_{metric}_contributing_work_count"] = len(eligible)
            summary.update(frac_fields(f"macro_w_{metric}", macro_value))
        summary_rows.append(summary)

    # Independent audit recomputes all formulas and verifies the emitted summaries.
    recomputed_by_work: dict[tuple[str, str], dict[str, Any]] = {}
    for stratum, stratum_rows in rows_by_stratum.items():
        grouped = defaultdict(list)
        for row in stratum_rows:
            grouped[row["project_work_id"]].append(row)
        for work_id, candidates in grouped.items():
            counts = work_counts(candidates)
            counts["resolved_count"] = counts["valid_count"] + counts["invalid_count"]
            q = quantities(counts)
            recomputed_by_work[(stratum, work_id)] = {"counts": counts, "quantities": q}
            output = by_work_index[(stratum, work_id)]
            for key, value in counts.items():
                if output[key] != value:
                    raise ValueError(f"By-work count recomputation mismatch: {stratum}/{work_id}/{key}")
            for metric, value in q.items():
                if output[f"{metric}_numerator"] != ("" if value is None else str(value.numerator)) or output[f"{metric}_denominator"] != ("" if value is None else str(value.denominator)):
                    raise ValueError(f"By-work rational recomputation mismatch: {stratum}/{work_id}/{metric}")
                if output[metric] != as_num(value) or output[f"{metric}_display"] != rounded_display(value):
                    raise ValueError(f"By-work numeric/display mismatch: {stratum}/{work_id}/{metric}")

    summary_by_stratum = {row["stratum"]: row for row in summary_rows}
    for stratum, stratum_rows in rows_by_stratum.items():
        counts = work_counts(stratum_rows)
        counts["resolved_count"] = counts["valid_count"] + counts["invalid_count"]
        micro = quantities(counts)
        summary = summary_by_stratum[stratum]
        if any(summary[k] != counts[k] for k in ("candidate_count", "valid_count", "invalid_count", "uncertain_count")):
            raise ValueError(f"Summary counts mismatch: {stratum}")
        for metric, value in micro.items():
            if summary[f"micro_{metric}_numerator"] != ("" if value is None else str(value.numerator)) or summary[f"micro_{metric}_denominator"] != ("" if value is None else str(value.denominator)):
                raise ValueError(f"Micro fraction mismatch: {stratum}/{metric}")
            if summary[f"micro_{metric}"] != as_num(value) or summary[f"micro_{metric}_display"] != rounded_display(value):
                raise ValueError(f"Micro value/display mismatch: {stratum}/{metric}")
        for metric, _, _ in METRICS:
            eligible = [entry["quantities"][metric] for (s, _), entry in recomputed_by_work.items() if s == stratum and entry["quantities"][metric] is not None]
            exact_macro = sum(eligible, Fraction(0, 1)) / len(eligible) if eligible else None
            if summary[f"macro_w_{metric}_contributing_work_count"] != len(eligible):
                raise ValueError(f"Macro contributing-work count mismatch: {stratum}/{metric}")
            if summary[f"macro_w_{metric}_numerator"] != ("" if exact_macro is None else str(exact_macro.numerator)) or summary[f"macro_w_{metric}_denominator"] != ("" if exact_macro is None else str(exact_macro.denominator)):
                raise ValueError(f"Macro exact fraction mismatch: {stratum}/{metric}")
            if summary[f"macro_w_{metric}"] != as_num(exact_macro) or summary[f"macro_w_{metric}_display"] != rounded_display(exact_macro):
                raise ValueError(f"Macro value/display mismatch: {stratum}/{metric}")

    # Confirm no macro denominator was silently chosen for a work with only UNCERTAIN.
    expected_undefined = {"ALL_MARGINAL_CANDIDATES": ["W000004216"], "ALIAS_EXPANSION": [], "A2_AUTHOR_REVERSAL": ["W000004216"]}
    if undefined_macro_work_ids != expected_undefined:
        raise ValueError(f"Unexpected resolved-case undefined work set: {undefined_macro_work_ids}")

    checks = {
        "frozen_authoritative_input_SHA256_verified": digest(INPUT) == EXPECTED_INPUT_SHA256,
        "frozen_reporting_spec_SHA256_verified": digest(SPEC) == EXPECTED_SPEC_SHA256,
        "input_661_rows_14_columns_and_order_valid": len(input_rows) == 661 and len(header) == 14 and orders == list(range(1, 662)),
        "input_candidate_ids_unique": len(set(ids)) == 661,
        "priority_counts_exact": priority_counts == EXPECTED_PRIORITY,
        "increment_counts_exact": increment_counts == EXPECTED_INCREMENT,
        "work_counts_exact": len({r["project_work_id"] for r in input_rows}) == 65 and len(alias_works) == 38 and len(reversal_works) == 27,
        "human_label_counts_exact": judgment_counts == EXPECTED_JUDGMENT and confidence_counts == EXPECTED_CONFIDENCE,
        "increment_candidate_sets_disjoint": not (alias_ids & reversal_ids),
        "increment_project_work_sets_disjoint": not (alias_works & reversal_works),
        "pair_level_counts_and_formulas_recompute": True,
        "every_by_work_row_recomputed_from_candidate_rows": len(by_work_rows) == sum(len({r["project_work_id"] for r in rs}) for rs in rows_by_stratum.values()),
        "every_macro_value_recomputed_from_by_work_rows": len(summary_rows) == 3,
        "summary_by_work_consistency": all(summary_by_stratum[s]["project_work_count"] == len(work_counts_by_stratum[s]) for s, _ in STRATA),
        "undefined_macro_resolved_case_work_documented": undefined_macro_work_ids == expected_undefined,
        "no_statistical_confidence_interval_calculated": True,
        "adjudication_bounds_not_called_confidence_intervals": True,
        "correct_branch_HEAD_and_no_unexpected_initial_changes": branch == "kakenc-integration-20260927" and head == EXPECTED_HEAD and status_paths.issubset(allowed_paths),
    }
    if not all(checks.values()):
        raise ValueError(f"Pre-write audit checks failed: {[key for key, value in checks.items() if not value]}")

    outdir.mkdir(parents=True, exist_ok=True)
    summary_tsv = outdir / f"{RELEASE}_summary.tsv"
    summary_parquet = outdir / f"{RELEASE}_summary.parquet"
    work_tsv = outdir / f"{RELEASE}_by_work.tsv"
    work_parquet = outdir / f"{RELEASE}_by_work.parquet"
    audit_path = outdir / f"{RELEASE}_audit_v1.json"
    manifest_path = outdir / f"{RELEASE}_manifest.json"

    def write_table(tsv_path: Path, parquet_path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
        with tsv_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="raise", quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows([{k: ("" if value is None else full_numeric(value) if isinstance(value, float) else str(value)) for k, value in row.items()} for row in rows])
        schema = arrow_schema(fields)
        table = pa.Table.from_pylist(rows, schema=schema)
        pq.write_table(table, parquet_path, compression="zstd", version="2.6")
        out_header, parsed = read_tsv(tsv_path)
        if out_header != fields:
            raise ValueError(f"Output header mismatch: {tsv_path}")
        typed = typed_tsv_rows(out_header, parsed, schema)
        parquet_rows = pq.read_table(parquet_path).to_pylist()
        if typed != parquet_rows or typed != rows:
            raise ValueError(f"Output TSV/Parquet parity failed: {tsv_path}")

    write_table(summary_tsv, summary_parquet, SUMMARY_FIELDS, summary_rows)
    write_table(work_tsv, work_parquet, WORK_FIELDS, by_work_rows)
    after = tracked_hashes()
    immutable = frozen_before == after
    checks["no_frozen_source_or_BL_artifact_changed"] = immutable
    if not immutable:
        changed = sorted(set(frozen_before) ^ set(after) | {key for key in frozen_before.keys() & after.keys() if frozen_before[key] != after[key]})
        raise ValueError(f"Frozen source files changed: {changed}")
    checks["summary_TSV_Parquet_cell_parity"] = True
    checks["by_work_TSV_Parquet_cell_parity"] = True
    if not all(checks.values()):
        raise ValueError(f"Final audit checks failed: {[key for key, value in checks.items() if not value]}")

    summary_dims = {"rows": len(summary_rows), "columns": len(SUMMARY_FIELDS)}
    work_dims = {"rows": len(by_work_rows), "columns": len(WORK_FIELDS)}
    output_hashes = {path.name: digest(path) for path in (summary_tsv, summary_parquet, work_tsv, work_parquet)}
    audit = {
        "audit": "openalex-retrieval-precision-results-v1-audit", "audit_status": "PASSED",
        "created_at_utc": created, "source_branch": branch, "source_head": head,
        "input_path": INPUT.relative_to(ROOT).as_posix(), "input_sha256": digest(INPUT),
        "reporting_spec_path": SPEC.relative_to(ROOT).as_posix(), "reporting_spec_sha256": digest(SPEC),
        "checks": checks, "input_integrity_counts": {
            "rows": len(input_rows), "columns": len(header), "review_priority": priority_counts,
            "increment_type": increment_counts, "judgment": judgment_counts,
            "confidence": confidence_counts, "reviewer_id": reviewer_counts,
            "project_work_count": len({row["project_work_id"] for row in input_rows}),
            "project_work_count_by_increment": {"ALIAS_EXPANSION": len(alias_works), "A2_AUTHOR_REVERSAL": len(reversal_works)},
        },
        "strata": summary_rows,
        "undefined_macro_w_resolved_case_work_ids": undefined_macro_work_ids,
        "dimensions": {summary_tsv.name: summary_dims, summary_parquet.name: summary_dims,
                       work_tsv.name: work_dims, work_parquet.name: work_dims},
        "output_sha256": output_hashes, "frozen_source_hashes_before": frozen_before,
        "frozen_source_hashes_after": after, "rounding_convention": ROUNDING,
        "statistical_uncertainty": NO_CI,
        "scope_statement": SCOPE,
    }
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "release": RELEASE, "release_version": "v1", "status": "PASSED",
        "source_branch": branch, "source_HEAD": head,
        "authoritative_input": {"path": INPUT.relative_to(ROOT).as_posix(), "release": "openalex_retrieval_precision_review_human_adjudication_complete_v1", "sha256": digest(INPUT), "rows": 661, "columns": 14},
        "reporting_specification": {"path": SPEC.relative_to(ROOT).as_posix(), "sha256": digest(SPEC)},
        "profile": "full_profile_57959e90", "calculation_timestamp_utc": created,
        "formulas": {
            "micro_confirmed_valid": "VALID / N",
            "micro_adjudication_lower": "VALID / N",
            "micro_adjudication_upper": "(VALID + UNCERTAIN) / N",
            "micro_resolved_case": "VALID / (VALID + INVALID)",
            "macro_w_confirmed_valid": "unweighted mean over represented project_work_id values of VALID_w / N_w",
            "macro_w_adjudication_lower": "unweighted mean over represented project_work_id values of VALID_w / N_w",
            "macro_w_adjudication_upper": "unweighted mean over represented project_work_id values of (VALID_w + UNCERTAIN_w) / N_w",
            "macro_w_resolved_case": "unweighted mean of VALID_w / (VALID_w + INVALID_w) over works with at least one resolved candidate; works with denominator zero are omitted and counted separately",
        },
        "rounding_display_convention": ROUNDING,
        "exact_fraction_storage": "Every reported ratio and macro-W average retains exact integer numerator and denominator as decimal digit strings (macro-W rational components can exceed fixed-width integer storage); numeric fields are float64 for machine consumption, with a separately rounded display field.",
        "scope_statement": SCOPE,
        "statistical_confidence_intervals": NO_CI,
        "strata": summary_rows,
        "undefined_macro_w_resolved_case_work_ids": undefined_macro_work_ids,
        "outputs": {**{name: {"sha256": value} for name, value in output_hashes.items()}, audit_path.name: {"sha256": digest(audit_path)}},
        "calculations_limited_to_frozen_specification": True,
        "ordinary_statistical_CI_calculated": False,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output_dir": outdir.relative_to(ROOT).as_posix(), "audit_status": "PASSED",
        "dimensions": {"summary": summary_dims, "by_work": work_dims},
        "input_sha256": digest(INPUT), "spec_sha256": digest(SPEC),
        "increment_counts": increment_counts, "work_counts": {"all": 65, "ALIAS_EXPANSION": 38, "A2_AUTHOR_REVERSAL": 27},
        "undefined_macro_w_resolved_case_work_ids": undefined_macro_work_ids,
        "results": summary_rows,
        "hashes": {path.name: digest(path) for path in (summary_tsv, summary_parquet, work_tsv, work_parquet, audit_path, manifest_path)},
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Retrieval-precision results build failed: {exc}", file=sys.stderr)
        raise
