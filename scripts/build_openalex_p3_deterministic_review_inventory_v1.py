#!/usr/bin/env python3
"""Build a deterministic descriptive P3 human-review inventory (no judgments)."""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_v1/full_profile_57959e90"
PACKAGE = PACKAGE_DIR / "openalex_retrieval_precision_review_human_adjudication_v1.tsv"
GROUP_DIR = ROOT / "derived/openalex_production/p2_deterministic_grouping_v1/full_profile_57959e90"
BATCH_DIR = ROOT / "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_batches_v1/full_profile_57959e90"
P2_AGG_DIR = ROOT / "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_P2_complete_v1/full_profile_57959e90"
DEFAULT_OUT = ROOT / "derived/openalex_production/p3_deterministic_review_inventory_v1/full_profile_57959e90"
SIGNATURE_FIELDS = [
    "title_match_norms", "author_a1_norms", "author_a2_reverse_norms",
    "any_title_match_in_title", "any_title_match_in_abstract", "any_author_a1_hit",
    "any_author_a2_reverse_hit", "hit_location", "abstract_available", "provenance_multiplicity",
]
HUMAN_FIELDS = [c for c in (
    "human_target_attribution_judgment", "human_adjudication_confidence",
    "human_attribution_reason_code", "human_reviewer_note", "human_reviewer_id",
    "human_adjudicated_at_utc", "human_evidence_used_oa_title", "human_evidence_used_oa_abstract",
    "human_evidence_used_project_provenance", "human_evidence_used_external_check",
    "human_external_check_reference", "human_external_check_note")]
MAX_BATCH_SIZE = 25
GROUPING_NOTICE = "Grouping is a review aid only and does not authorize shared human judgments."


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def tree_hashes(path):
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(Path(path).rglob("*")) if p.is_file()}


def read_tsv(path):
    with Path(path).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t", strict=True))


def write_tsv(path, columns, rows):
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, delimiter="\t", lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def canon(values):
    return json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest_id(prefix, values):
    return prefix + hashlib.sha256(canon(values)).hexdigest()[:16]


def bool_value(value):
    if value == "True":
        return True
    if value == "False":
        return False
    return None


def counter(values):
    return dict(sorted(Counter(values).items(), key=lambda x: x[0]))


def values_distribution(rows, field):
    return counter(r[field] for r in rows)


def duplicate_groups(rows, fields):
    groups = defaultdict(list)
    for row in rows:
        key = tuple(row.get(field, "") for field in fields)
        if not any(key):
            continue
        groups[key].append(row)
    return [members for _, members in sorted(groups.items(), key=lambda kv: kv[0]) if len(members) > 1]


def complexity(candidate_count, signature_count):
    # Review-load descriptors only. No label permits or recommends judgment propagation.
    if candidate_count > 8 or signature_count >= 4:
        return "HIGH_REVIEW_LOAD"
    if candidate_count <= 3 and signature_count == 1:
        return "LOW_REVIEW_LOAD"
    return "MODERATE_REVIEW_LOAD"


def risk_flags(row, project_n, project_sig_n, oa_id_duplicate, title_duplicate, abstract_duplicate, pair_duplicate):
    flags = []
    title_hit = bool_value(row["any_title_match_in_title"])
    abstract_hit = bool_value(row["any_title_match_in_abstract"])
    author_a1 = bool_value(row["any_author_a1_hit"])
    author_a2 = bool_value(row["any_author_a2_reverse_hit"])
    abstract_available = bool_value(row["abstract_available"])
    if row["hit_location"] == "TITLE_ONLY": flags.append("TITLE_ONLY_EVIDENCE")
    if abstract_available is False: flags.append("ABSTRACT_UNAVAILABLE")
    if author_a1 is False and author_a2 is False: flags.append("NO_AUTHOR_MATCH_HIT_FLAG")
    if row.get("title_token_count", "").isdigit() and int(row["title_token_count"]) <= 2:
        flags.append(f"SHORT_TITLE_MATCH_{row['title_token_count']}_TOKENS")
    if row["provenance_multiplicity"] == "MULTIPLE": flags.append("MULTIPLE_PROVENANCE_ROUTES")
    if project_n > 1: flags.append("MULTIPLE_CANDIDATES_FOR_PROJECT_WORK")
    if project_sig_n > 1: flags.append("MULTIPLE_EVIDENCE_PATTERNS_FOR_PROJECT_WORK")
    if oa_id_duplicate: flags.append("OPENALEX_WORK_ID_REUSED_IN_P3")
    if title_duplicate: flags.append("RAW_DISPLAY_NAME_REUSED_IN_P3")
    if abstract_duplicate: flags.append("RAW_ABSTRACT_REUSED_IN_P3")
    if pair_duplicate: flags.append("RAW_TITLE_ABSTRACT_PAIR_REUSED_IN_P3")
    if row.get("is_retracted") == "True": flags.append("OPENALEX_RETRACTED_FLAG")
    if row.get("is_paratext") == "True": flags.append("OPENALEX_PARATEXT_FLAG")
    if not row.get("display_name", "").strip(): flags.append("EMPTY_OPENALEX_DISPLAY_NAME")
    if not row.get("language", "").strip(): flags.append("MISSING_LANGUAGE_METADATA")
    if not row.get("publication_year", "").strip(): flags.append("MISSING_PUBLICATION_YEAR_METADATA")
    if bool_value(row["abstract_available"]) is not None and bool_value(row["abstract_available"]) != bool(row.get("abstract", "").strip()):
        flags.append("ABSTRACT_AVAILABILITY_FLAG_MISMATCH")
    if title_hit is not None and abstract_hit is not None and row["hit_location"] in {"TITLE_ONLY", "ABSTRACT_ONLY", "TITLE_AND_ABSTRACT", "NEITHER"}:
        expected = {(True, False): "TITLE_ONLY", (False, True): "ABSTRACT_ONLY", (True, True): "TITLE_AND_ABSTRACT", (False, False): "NEITHER"}.get((title_hit, abstract_hit))
        if expected != row["hit_location"]: flags.append("HIT_LOCATION_FLAG_MISMATCH")
    if row.get("llm_human_attention_required") == "True": flags.append("LLM_HUMAN_ATTENTION_FLAG")
    if row.get("llm_taxonomy_issue") == "True": flags.append("LLM_TAXONOMY_ISSUE_FLAG")
    return sorted(flags)


def form_batches(ordered_rows):
    """Pack whole project-work blocks up to 25; split only blocks exceeding 25."""
    blocks = []
    by_work = defaultdict(list)
    for row in ordered_rows:
        by_work[row["project_work_id"]].append(row)
    for work in sorted(by_work):
        blocks.append((work, by_work[work]))
    batches = []
    pending = []
    def flush():
        nonlocal pending
        if pending:
            batches.append(pending)
            pending = []
    for work, block in blocks:
        if len(block) > MAX_BATCH_SIZE:
            flush()
            for start in range(0, len(block), MAX_BATCH_SIZE):
                batches.append(block[start:start + MAX_BATCH_SIZE])
        else:
            if pending and len(pending) + len(block) > MAX_BATCH_SIZE:
                flush()
            pending.extend(block)
    flush()
    for batch_no, batch in enumerate(batches, 1):
        batch_id = f"P3B{batch_no:02d}"
        for row in batch:
            row["p3_review_batch_id"] = batch_id
    return batches


def make_outputs(source_rows):
    p3 = [dict(r) for r in source_rows if r["review_priority"] == "P3"]
    source_columns = list(source_rows[0])
    if len(p3) != 493:
        raise ValueError(f"Expected 493 P3 candidates, got {len(p3)}")
    by_work = defaultdict(list)
    for row in p3:
        by_work[row["project_work_id"]].append(row)
    signature_rows = defaultdict(list)
    work_sig_members = defaultdict(lambda: defaultdict(list))
    for row in p3:
        raw_sig = tuple(row[field] for field in SIGNATURE_FIELDS)
        sig_id = digest_id("OAP3ES1_", list(raw_sig))
        work_sig_id = digest_id("OAP3WES1_", [row["project_work_id"], *raw_sig])
        row["p3_evidence_signature_id"] = sig_id
        row["p3_project_evidence_subgroup_id"] = work_sig_id
        signature_rows[raw_sig].append(row)
        work_sig_members[row["project_work_id"]][raw_sig].append(row)
    # Reject shortened-hash collisions over distinct canonical values.
    def collision_free(id_to_key):
        seen = {}
        for key, identifier in id_to_key.items():
            if identifier in seen and seen[identifier] != key:
                return False
            seen[identifier] = key
        return True
    sig_ids = {sig: digest_id("OAP3ES1_", list(sig)) for sig in signature_rows}
    work_sig_ids = {(work, sig): digest_id("OAP3WES1_", [work, *sig]) for work, sigs in work_sig_members.items() for sig in sigs}
    if not collision_free(sig_ids) or not collision_free(work_sig_ids):
        raise ValueError("Truncated SHA256 identifier collision")
    # Stable candidate order: project work, exact raw signature values, source order, candidate ID.
    ordered = sorted(p3, key=lambda r: (r["project_work_id"], tuple(r[f] for f in SIGNATURE_FIELDS), int(r["review_order"]), r["review_candidate_id"]))
    project_counts = {work: len(members) for work, members in by_work.items()}
    project_sig_counts = {work: len(sigs) for work, sigs in work_sig_members.items()}
    for idx, row in enumerate(ordered, 1):
        row["p3_review_order"] = str(idx)
        row["p3_project_work_candidate_count"] = str(project_counts[row["project_work_id"]])
        row["p3_project_work_evidence_pattern_count"] = str(project_sig_counts[row["project_work_id"]])
        row["p3_project_work_complexity_class"] = complexity(project_counts[row["project_work_id"]], project_sig_counts[row["project_work_id"]])
    # Exact raw-record reuse indicators are descriptive only.
    oa_groups = defaultdict(list)
    for row in ordered: oa_groups[row["openalex_work_id"]].append(row)
    title_groups = defaultdict(list); abstract_groups = defaultdict(list); pair_groups = defaultdict(list)
    for row in ordered:
        if row.get("display_name", ""): title_groups[row["display_name"]].append(row)
        if row.get("abstract", ""): abstract_groups[row["abstract"]].append(row)
        pair = (row.get("display_name", ""), row.get("abstract", ""))
        if any(pair): pair_groups[pair].append(row)
    dup_oa = {v[0]["openalex_work_id"] for v in oa_groups.values() if len(v) > 1}
    dup_title = {k for k, v in title_groups.items() if len(v) > 1}
    dup_abstract = {k for k, v in abstract_groups.items() if len(v) > 1}
    dup_pair = {k for k, v in pair_groups.items() if len(v) > 1}
    for row in ordered:
        row["p3_evidence_signature_candidate_count"] = str(len(signature_rows[tuple(row[f] for f in SIGNATURE_FIELDS)]))
        row["p3_project_evidence_subgroup_candidate_count"] = str(len(work_sig_members[row["project_work_id"]][tuple(row[f] for f in SIGNATURE_FIELDS)]))
        flags = risk_flags(row, project_counts[row["project_work_id"]], project_sig_counts[row["project_work_id"]], row["openalex_work_id"] in dup_oa, row.get("display_name", "") in dup_title, row.get("abstract", "") in dup_abstract, (row.get("display_name", ""), row.get("abstract", "")) in dup_pair)
        row["p3_risk_flags"] = "|".join(flags)
    batches = form_batches(ordered)
    # Candidate mapping keeps every frozen source cell and appends deterministic review aids.
    candidate_columns = source_columns + [
        "p3_review_order", "p3_evidence_signature_id", "p3_project_evidence_subgroup_id",
        "p3_evidence_signature_candidate_count", "p3_project_evidence_subgroup_candidate_count",
        "p3_project_work_candidate_count", "p3_project_work_evidence_pattern_count",
        "p3_project_work_complexity_class", "p3_review_batch_id", "p3_risk_flags"]
    project_columns = ["project_work_id", "candidate_count", "evidence_pattern_count", "project_work_complexity_class", "p3_review_order_start", "p3_review_order_end", "review_batch_ids", "risk_flagged_candidate_count", "risk_flag_counts"]
    project_summary = []
    for work in sorted(by_work):
        members = [r for r in ordered if r["project_work_id"] == work]
        class_name = complexity(project_counts[work], project_sig_counts[work])
        all_flags = Counter(flag for r in members for flag in r["p3_risk_flags"].split("|") if flag)
        project_summary.append({"project_work_id": work, "candidate_count": str(len(members)), "evidence_pattern_count": str(project_sig_counts[work]), "project_work_complexity_class": class_name, "p3_review_order_start": members[0]["p3_review_order"], "p3_review_order_end": members[-1]["p3_review_order"], "review_batch_ids": "|".join(sorted({r["p3_review_batch_id"] for r in members})), "risk_flagged_candidate_count": str(sum(bool(r["p3_risk_flags"]) for r in members)), "risk_flag_counts": json.dumps(dict(sorted(all_flags.items())), separators=(",", ":"))})
    signature_columns = ["p3_evidence_signature_id", "candidate_count", "project_work_count", "project_work_subgroup_count", *SIGNATURE_FIELDS, "p3_review_order_start", "p3_review_order_end", "project_work_ids", "review_candidate_ids"]
    signature_summary = []
    for sig in sorted(signature_rows):
        members = sorted(signature_rows[sig], key=lambda r: int(r["p3_review_order"]))
        signature_summary.append({"p3_evidence_signature_id": sig, "candidate_count": str(len(members)), "project_work_count": str(len({r["project_work_id"] for r in members})), "project_work_subgroup_count": str(len({r["p3_project_evidence_subgroup_id"] for r in members})), **dict(zip(SIGNATURE_FIELDS, sig)), "p3_review_order_start": members[0]["p3_review_order"], "p3_review_order_end": members[-1]["p3_review_order"], "project_work_ids": "|".join(sorted({r["project_work_id"] for r in members})), "review_candidate_ids": "|".join(r["review_candidate_id"] for r in members)})
    batch_summary = []
    for index, batch in enumerate(batches, 1):
        batch_summary.append({"review_batch_id": f"P3B{index:02d}", "candidate_count": len(batch), "p3_review_order_start": int(batch[0]["p3_review_order"]), "p3_review_order_end": int(batch[-1]["p3_review_order"]), "project_work_ids": sorted({r["project_work_id"] for r in batch}), "oversized_project_work_split": len(batch) == MAX_BATCH_SIZE and len({r["project_work_id"] for r in batch}) == 1 and project_counts[batch[0]["project_work_id"]] > MAX_BATCH_SIZE})
    return p3, ordered, candidate_columns, project_summary, project_columns, signature_summary, signature_columns, batch_summary, by_work, work_sig_members


def describe(ordered, by_work, work_sig_members, batches):
    work_counts = Counter(len(x) for x in by_work.values())
    sig_count_dist = Counter(len(x) for x in work_sig_members.values())
    return {
        "candidate_count": len(ordered), "project_work_count": len(by_work),
        "candidates_per_project_work_distribution": dict(sorted(work_counts.items())),
        "singleton_project_works": sum(n for size, n in work_counts.items() if size == 1),
        "multi_candidate_project_works": sum(n for size, n in work_counts.items() if size > 1),
        "work_candidate_count_max": max(work_counts),
        "project_work_evidence_pattern_count_distribution": dict(sorted(sig_count_dist.items())),
        "project_works_spanning_multiple_evidence_patterns": sum(n for size, n in sig_count_dist.items() if size > 1),
        "distinct_raw_evidence_pattern_signatures": len({tuple(r[f] for f in SIGNATURE_FIELDS) for r in ordered}),
        "project_work_evidence_subgroups": sum(len(sigs) for sigs in work_sig_members.values()),
        "review_batch_count": len(batches), "review_batch_capacity": MAX_BATCH_SIZE,
        "complexity_classes": dict(sorted(Counter(complexity(len(by_work[w]), len(work_sig_members[w])) for w in by_work).items())),
        "distributions": {field: values_distribution(ordered, field) for field in [
            "llm_target_attribution_judgment", "llm_adjudication_confidence", "llm_attribution_reason_code", "increment_type", "hit_location", "abstract_available", "any_title_match_in_title", "any_title_match_in_abstract", "any_author_a1_hit", "any_author_a2_reverse_hit", "provenance_multiplicity", "title_token_count", "title_token_bucket", "type", "language", "is_retracted", "is_paratext", "llm_human_attention_required", "llm_taxonomy_issue"]}}


def duplicate_report(rows):
    oa = duplicate_groups(rows, ["openalex_work_id"])
    title = duplicate_groups(rows, ["display_name"])
    abstract = duplicate_groups(rows, ["abstract"])
    title_year = duplicate_groups(rows, ["display_name", "publication_year"])
    pair = duplicate_groups(rows, ["display_name", "abstract"])
    doi = duplicate_groups([r for r in rows if r.get("doi", "").strip()], ["doi"])
    def details(groups, key_fields):
        return [{"matched_raw_fields_sha256": hashlib.sha256(canon([g[0].get(field, "") for field in key_fields])).hexdigest(), "candidate_count": len(g), "review_candidate_ids": [r["review_candidate_id"] for r in sorted(g, key=lambda x: int(x["review_order"]))], "project_work_ids": sorted({r["project_work_id"] for r in g}), "openalex_work_ids": sorted({r["openalex_work_id"] for r in g})} for g in groups]
    return {
        "same_openalex_work_id": {"duplicate_groups": len(oa), "excess_candidate_rows": sum(len(g)-1 for g in oa), "groups": details(oa, ["openalex_work_id"])},
        "same_raw_display_name": {"duplicate_groups": len(title), "excess_candidate_rows": sum(len(g)-1 for g in title), "groups": details(title, ["display_name"])},
        "same_raw_abstract": {"duplicate_groups": len(abstract), "excess_candidate_rows": sum(len(g)-1 for g in abstract), "groups": details(abstract, ["abstract"])},
        "same_raw_display_name_and_publication_year": {"duplicate_groups": len(title_year), "excess_candidate_rows": sum(len(g)-1 for g in title_year), "groups": details(title_year, ["display_name", "publication_year"])},
        "same_raw_display_name_and_abstract": {"duplicate_groups": len(pair), "excess_candidate_rows": sum(len(g)-1 for g in pair), "groups": details(pair, ["display_name", "abstract"])},
        "same_nonempty_doi": {"duplicate_groups": len(doi), "excess_candidate_rows": sum(len(g)-1 for g in doi), "groups": details(doi, ["doi"])},
        "interpretation": "Exact repeated frozen-field values are retrieval/review cues only. Different candidate identities remain distinct; repeated title or abstract alone does not establish duplicate works. No fuzzy or semantic near-duplicate inference is performed."}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--skip-byte-replay", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    out = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"Refusing to overwrite nonempty output directory: {out}")
    source_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
    source_branch = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
    source_hash = sha(PACKAGE)
    package_hashes_before = tree_hashes(PACKAGE_DIR)
    grouping_hashes_before = tree_hashes(GROUP_DIR)
    batch_hashes_before = tree_hashes(BATCH_DIR)
    p2_aggregate_hashes_before = tree_hashes(P2_AGG_DIR)
    bl_before = subprocess.run(["git", "status", "--porcelain", "--", "derived/bl_calibration", "scripts/bl"], cwd=ROOT, text=True, capture_output=True, check=True).stdout
    package_rows = read_tsv(PACKAGE)
    if len(package_rows) != 661 or not package_rows:
        raise SystemExit("Frozen human-review package must contain exactly 661 rows")
    source_columns = list(package_rows[0])
    if any(list(r) != source_columns for r in package_rows):
        raise SystemExit("Frozen package row columns differ")
    p3_source = [r for r in package_rows if r["review_priority"] == "P3"]
    outputs = make_outputs(package_rows)
    p3, ordered, candidate_columns, project_summary, project_columns, signature_summary, signature_columns, batch_summary, by_work, work_sig_members = outputs
    if {r["review_candidate_id"] for r in p3} != {r["review_candidate_id"] for r in p3_source}:
        raise SystemExit("P3 selection changed during deterministic derivation")
    OUT_DIR = out
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prefix = "openalex_p3_deterministic_review_inventory_v1"
    candidate_path = OUT_DIR / f"{prefix}_candidates.tsv"
    project_path = OUT_DIR / f"{prefix}_project_work_summary.tsv"
    signature_path = OUT_DIR / f"{prefix}_evidence_signature_summary.tsv"
    audit_path = OUT_DIR / f"{prefix}_audit_v1.json"
    manifest_path = OUT_DIR / f"{prefix}_manifest.json"
    plan_path = OUT_DIR / f"{prefix}_review_plan.md"
    write_tsv(candidate_path, candidate_columns, ordered)
    write_tsv(project_path, project_columns, project_summary)
    write_tsv(signature_path, signature_columns, signature_summary)
    summary = describe(ordered, by_work, work_sig_members, batch_summary)
    dupes = duplicate_report(p3)
    # Source cell preservation check covers every source package field for every selected row.
    package_by_id = {r["review_candidate_id"]: r for r in package_rows}
    source_copy_exact = all(all(row[c] == package_by_id[row["review_candidate_id"]][c] for c in source_columns) for row in ordered)
    p3_ids = {r["review_candidate_id"] for r in p3_source}
    map_ids = {r["review_candidate_id"] for r in ordered}
    human_empty = all(not any(r.get(c, "") for c in HUMAN_FIELDS) for r in ordered)
    # Independent deterministic derivation repeat, including review order and membership.
    replay_outputs = make_outputs(package_rows)
    replay_map = replay_outputs[1]
    derivation_repeat = replay_map == ordered and replay_outputs[3] == project_summary and replay_outputs[5] == signature_summary and replay_outputs[7] == batch_summary
    # Assess target selection excludes all non-P3 records and no duplicates.
    selected_priority = all(r["review_priority"] == "P3" for r in ordered)
    risk_counts = Counter(flag for r in ordered for flag in r["p3_risk_flags"].split("|") if flag)
    # Protect every frozen input/adjudication artifact; output location is separate.
    package_hashes_after = tree_hashes(PACKAGE_DIR)
    grouping_hashes_after = tree_hashes(GROUP_DIR)
    batch_hashes_after = tree_hashes(BATCH_DIR)
    p2_aggregate_hashes_after = tree_hashes(P2_AGG_DIR)
    bl_after = subprocess.run(["git", "status", "--porcelain", "--", "derived/bl_calibration", "scripts/bl"], cwd=ROOT, text=True, capture_output=True, check=True).stdout
    checks = {
        "exactly_493_P3_candidates": len(ordered) == 493,
        "candidate_set_exactly_frozen_P3": map_ids == p3_ids,
        "no_P1_P2_candidates": selected_priority,
        "no_candidate_duplication": len(map_ids) == len(ordered) == 493,
        "all_source_identity_provenance_cells_copied_exactly": source_copy_exact,
        "deterministic_derivation_repeat_identical": derivation_repeat,
        "deterministic_output_reproducibility_byte_identical": True,
        "no_human_judgments_created": human_empty,
        "no_existing_frozen_artifact_changed": package_hashes_before == package_hashes_after and grouping_hashes_before == grouping_hashes_after and batch_hashes_before == batch_hashes_after and p2_aggregate_hashes_before == p2_aggregate_hashes_after,
        "no_BL_changes": bl_before == bl_after == "",
    }
    if not all(checks.values()):
        raise SystemExit(f"P3 inventory audit failed: {checks}")
    project_distribution = summary["candidates_per_project_work_distribution"]
    complexity_counts = summary["complexity_classes"]
    short_title_counts = {k: risk_counts.get(k, 0) for k in ["SHORT_TITLE_MATCH_1_TOKENS", "SHORT_TITLE_MATCH_2_TOKENS"]}
    audit = {
        "audit": "openalex-p3-deterministic-review-inventory-v1-audit",
        "audit_status": "PASSED", "artifact_status": "DETERMINISTIC_DESCRIPTIVE_REVIEW_INVENTORY_ONLY",
        "authoritative": False, "source_branch": source_branch, "source_HEAD": source_head,
        "source_package": {"path": str(PACKAGE.relative_to(ROOT)), "rows": len(package_rows), "sha256": source_hash},
        "checks": checks, "dimensions": {"candidate_rows": len(ordered), "candidate_columns": len(candidate_columns), "project_work_rows": len(project_summary), "project_work_columns": len(project_columns), "evidence_signature_rows": len(signature_summary), "evidence_signature_columns": len(signature_columns)},
        "p3_candidate_set": {"expected": len(p3_ids), "actual": len(map_ids), "missing": sorted(p3_ids-map_ids), "extra": sorted(map_ids-p3_ids)},
        "summary": summary, "distinct_exact_signature_fields": SIGNATURE_FIELDS,
        "complexity_rule": {"HIGH_REVIEW_LOAD": "project candidate count > 8 OR project-specific exact evidence-pattern count >= 4", "LOW_REVIEW_LOAD": "project candidate count <= 3 AND exact evidence-pattern count == 1", "MODERATE_REVIEW_LOAD": "otherwise", "interpretation": "Structural review-load descriptors only; they do not authorize shared judgments."},
        "review_batch_rule": {"maximum_candidates": MAX_BATCH_SIZE, "ordering": "project_work_id ascending; within work, exact raw evidence tuple lexicographic; then frozen review_order; then review_candidate_id", "boundaries": "Greedily keep whole project-work blocks together when they fit within 25 candidates. Split only project-work blocks larger than 25 into consecutive candidate-level chunks. Batch boundaries are logistics only."},
        "review_batches": batch_summary, "duplicate_and_near_duplicate_cues": dupes,
        "risk_flag_counts": dict(sorted(risk_counts.items())), "short_title_match_flag_counts": short_title_counts,
        "author_field_limit": "The frozen package has aggregate any_author_a1_hit/any_author_a2_reverse_hit booleans but does not encode whether title and author evidence co-occur in the same title/abstract field or sentence. No co-occurrence is inferred; inspect candidate evidence directly.",
        "frozen_hashes_before": {"review_package": package_hashes_before, "p2_grouping": grouping_hashes_before, "p1_p2_batches": batch_hashes_before, "p2_complete_aggregate": p2_aggregate_hashes_before},
        "frozen_hashes_after": {"review_package": package_hashes_after, "p2_grouping": grouping_hashes_after, "p1_p2_batches": batch_hashes_after, "p2_complete_aggregate": p2_aggregate_hashes_after},
        "statement": GROUPING_NOTICE + " No human judgments were created and no precision or other performance metric was calculated."
    }
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Deterministic review plan: data distributions plus explicit review-aid boundary.
    md = ["# OpenAlex P3 deterministic review inventory v1", "", "Status: descriptive inventory and workflow-design aid only. No human judgments are included.", "", f"> {GROUPING_NOTICE}", "", "## Scope and counts", "", f"- P3 candidates: {len(ordered)}", f"- Distinct project works: {len(by_work)}", f"- Exact raw evidence-pattern signatures: {summary['distinct_raw_evidence_pattern_signatures']}", f"- Project-specific evidence subgroups: {summary['project_work_evidence_subgroups']}", f"- Project works spanning multiple evidence patterns: {summary['project_works_spanning_multiple_evidence_patterns']}", f"- Suggested review batches: {len(batch_summary)} (maximum {MAX_BATCH_SIZE} candidates)", "", "## Candidate and evidence distributions", ""]
    for title, key in [("Candidates per project work", "candidates_per_project_work_distribution"), ("LLM judgment suggestions (descriptive only)", None), ("LLM confidence suggestions (descriptive only)", None), ("LLM reason suggestions (descriptive only)", None), ("Increment type", None), ("Hit location", None), ("Abstract availability", None), ("Title hit flag", None), ("Abstract hit flag", None), ("Author A1 hit flag", None), ("Author A2 reverse hit flag", None), ("Provenance multiplicity", None), ("Title token count", None)]:
        if key: dist = summary[key]
        else:
            field = {"LLM judgment suggestions (descriptive only)":"llm_target_attribution_judgment", "LLM confidence suggestions (descriptive only)":"llm_adjudication_confidence", "LLM reason suggestions (descriptive only)":"llm_attribution_reason_code", "Increment type":"increment_type", "Hit location":"hit_location", "Abstract availability":"abstract_available", "Title hit flag":"any_title_match_in_title", "Abstract hit flag":"any_title_match_in_abstract", "Author A1 hit flag":"any_author_a1_hit", "Author A2 reverse hit flag":"any_author_a2_reverse_hit", "Provenance multiplicity":"provenance_multiplicity", "Title token count":"title_token_count"}[title]
            dist = summary["distributions"][field]
        md.append(f"### {title}\n\n" + ", ".join(f"`{k}`: {v}" for k,v in dist.items()) + "\n")
    md += ["## Project-work review-load classes", "", "| Class | Project works |", "|---|---:|"] + [f"| {k} | {v} |" for k,v in complexity_counts.items()]
    md += ["", "Classes use project candidate count and distinct exact evidence patterns only. They do not imply that cases in a group share a correct judgment.", "", "## Deterministic review ordering and batches", "", "Candidates are sorted by project_work_id, then exact raw evidence signature fields in lexicographic order, then frozen review_order and candidate ID. `p3_review_order` assigns 1–493 in that sequence. Reviewers can use the evidence-signature summary to navigate candidate-level records.", "", "Batch packing keeps a project-work block intact where it fits within the 25-candidate capacity; project works larger than 25 are split into sequential candidate-level chunks. These are proposed logistics, not adjudication units.", "", "| Batch | P3 order | Candidates | Project works |", "|---|---:|---:|---:|"]
    for b in batch_summary:
        md.append(f"| {b['review_batch_id']} | {b['p3_review_order_start']}–{b['p3_review_order_end']} | {b['candidate_count']} | {', '.join(b['project_work_ids'])} |")
    md += ["", "## Deterministic review flags", "", "Flags identify observable review conditions, including title-only matches, unavailable abstracts, short title-token counts, absent aggregate author-hit flags, multiple provenance routes, multiple candidates or patterns per project work, repeated OpenAlex work IDs, repeated raw titles/abstracts, metadata missingness, and available LLM attention/taxonomy flags. A flag is a prompt to inspect the individual row; it is not a target-attribution judgment.", "", "Exact repeated-field cues: "]
    md.append("; ".join(f"{k}: {v['duplicate_groups']} groups ({v['excess_candidate_rows']} excess rows)" for k,v in dupes.items() if isinstance(v,dict) and "duplicate_groups" in v) + ".")
    md += ["", audit["author_field_limit"], "", "## Reproduction", "", "Run `python3 scripts/build_openalex_p3_deterministic_review_inventory_v1.py` from the repository root. The generator refuses a nonempty destination. Pass `--output-dir /tmp/<new-directory>` to generate a replay for byte-level reproducibility comparison.", ""]
    plan_path.write_text("\n".join(md), encoding="utf-8")
    output_hashes = {p.name: sha(p) for p in [candidate_path, project_path, signature_path, audit_path, plan_path]}
    manifest = {
        "release": "openalex_p3_deterministic_review_inventory_v1", "release_version": "v1",
        "artifact_status": "DETERMINISTIC_DESCRIPTIVE_REVIEW_INVENTORY_ONLY", "authoritative": False,
        "status": "PASSED", "source_branch": source_branch, "source_HEAD": source_head,
        "frozen_baseline_commit": "76d5524c042bbc7ac55f376f142125f632d579d1",
        "builder": {"path": "scripts/build_openalex_p3_deterministic_review_inventory_v1.py", "sha256": sha(Path(__file__))},
        "method_specification": "docs/OPENALEX_P3_DETERMINISTIC_REVIEW_INVENTORY_V1.md",
        "source_package": {"path": str(PACKAGE_DIR.relative_to(ROOT)), "rows": len(package_rows), "file_hashes": package_hashes_before, "candidate_tsv_sha256": source_hash},
        "source_deterministic_grouping": {"path": str(GROUP_DIR.relative_to(ROOT)), "file_hashes": grouping_hashes_before},
        "frozen_prior_artifact_hashes": {"p1_p2_batches": batch_hashes_before, "p2_complete_aggregate": p2_aggregate_hashes_before},
        "dimensions": audit["dimensions"], "summary": summary,
        "expected_review_notice": GROUPING_NOTICE, "review_batches": batch_summary,
        "risk_flag_counts": dict(sorted(risk_counts.items())), "duplicate_and_near_duplicate_cues": dupes,
        "outputs": {**{name: {"sha256": digest, "bytes": (OUT_DIR / name).stat().st_size} for name,digest in output_hashes.items()}, "openalex_p3_deterministic_review_inventory_v1_manifest.json": {"path": manifest_path.name}},
        "audit": {"path": audit_path.name, "sha256": sha(audit_path)},
        "explicit_statement": "No human judgments were created. No precision, accuracy, rates, percentages, confidence intervals, or any other performance metric was calculated."
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.skip_byte_replay:
        with tempfile.TemporaryDirectory(prefix="openalex_p3_inventory_replay_") as temp_dir:
            replay_dir = Path(temp_dir) / "replay"
            subprocess.run([sys.executable, str(Path(__file__).resolve()), "--output-dir", str(replay_dir), "--skip-byte-replay"], cwd=ROOT, check=True, capture_output=True, text=True)
            expected_names = sorted(p.name for p in OUT_DIR.iterdir() if p.is_file())
            replay_names = sorted(p.name for p in replay_dir.iterdir() if p.is_file())
            replay_identical = expected_names == replay_names and all(sha(OUT_DIR / name) == sha(replay_dir / name) for name in expected_names)
        if not replay_identical:
            audit["checks"]["deterministic_output_reproducibility_byte_identical"] = False
            audit["audit_status"] = "FAILED"
            audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            manifest["status"] = "FAILED"
            manifest["audit"]["sha256"] = sha(audit_path)
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"audit_status":audit["audit_status"], "candidates":len(ordered), "project_works":len(by_work), "raw_signatures":len(signature_summary), "project_signature_subgroups":summary["project_work_evidence_subgroups"], "review_batches":len(batch_summary), "complexity":complexity_counts, "outputs_sha256":{p.name:sha(p) for p in [candidate_path,project_path,signature_path,audit_path,plan_path,manifest_path]}}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
