#!/usr/bin/env python3
"""Build deterministic P3 candidate-level human-review sheets; creates no judgments."""
import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_v1/full_profile_57959e90/openalex_retrieval_precision_review_human_adjudication_v1.tsv"
INVENTORY_DIR = ROOT / "derived/openalex_production/p3_deterministic_review_inventory_v1/full_profile_57959e90"
INVENTORY = INVENTORY_DIR / "openalex_p3_deterministic_review_inventory_v1_candidates.tsv"
DEFAULT_OUT = ROOT / "derived/openalex_production/openalex_retrieval_precision_review_P3_human_review_sheets_v1/full_profile_57959e90"
OUT_NAME = "openalex_retrieval_precision_review_P3_human_review_sheets_v1"
NOTICE_1 = "LLM output is a reference suggestion only. Apply the frozen human-review protocol independently."
NOTICE_2 = "Grouping is a review aid only and does not authorize shared human judgments."
EMPTY_HUMAN = ["human_target_attribution_judgment", "human_adjudication_confidence", "human_attribution_reason_code", "human_reviewer_note", "human_reviewer_id", "human_adjudicated_at_utc"]
RISK_FLAGS = [
    "TITLE_ONLY_EVIDENCE", "ABSTRACT_UNAVAILABLE", "NO_AUTHOR_MATCH_HIT_FLAG",
    "SHORT_TITLE_MATCH_1_TOKENS", "SHORT_TITLE_MATCH_2_TOKENS", "MULTIPLE_PROVENANCE_ROUTES",
    "MULTIPLE_CANDIDATES_FOR_PROJECT_WORK", "MULTIPLE_EVIDENCE_PATTERNS_FOR_PROJECT_WORK",
    "OPENALEX_WORK_ID_REUSED_IN_P3", "RAW_DISPLAY_NAME_REUSED_IN_P3", "RAW_ABSTRACT_REUSED_IN_P3",
    "RAW_TITLE_ABSTRACT_PAIR_REUSED_IN_P3", "MISSING_LANGUAGE_METADATA", "MISSING_PUBLICATION_YEAR_METADATA",
    "EMPTY_OPENALEX_DISPLAY_NAME", "OPENALEX_PARATEXT_FLAG", "LLM_HUMAN_ATTENTION_REQUIRED",
    "LLM_TAXONOMY_ISSUE",
]
DISPLAY_FIELDS = [
    ("P3 review batch ID", "p3_review_batch_id"), ("Stable candidate-level review order", "p3_review_order"),
    ("Review candidate ID", "review_candidate_id"), ("Project work ID", "project_work_id"),
    ("Review priority", "review_priority"), ("Frozen source review order", "review_order"),
    ("Review semantic group ID", "review_semantic_group_id"), ("Review protocol version", "review_protocol_version"),
    ("R3 evidence-row count", "r3_evidence_rows"), ("R3 query IDs", "r3_query_ids"),
    ("R3 execution IDs", "r3_execution_ids"), ("R3 alias IDs", "r3_alias_ids"),
    ("Target/query title(s)", "r3_query_titles"), ("Target/query author(s)", "r3_query_authors"),
    ("R2 baseline title(s)", "r2_baseline_titles"), ("R2 baseline author(s)", "r2_baseline_authors"),
    ("OpenAlex work ID", "openalex_work_id"), ("OpenAlex display_name", "display_name"),
    ("OpenAlex work URL", "openalex_id_url"), ("Snapshot source file", "snapshot_source_file"),
    ("Publication year", "publication_year"), ("Increment type", "increment_type"),
    ("Hit location", "hit_location"), ("Abstract available", "abstract_available"),
    ("Title hit flag", "any_title_match_in_title"), ("Abstract hit flag", "any_title_match_in_abstract"),
    ("Title match norms (raw)", "title_match_norms"), ("Author A1 match norms (raw)", "author_a1_norms"),
    ("Author A2 reverse match norms (raw)", "author_a2_reverse_norms"),
    ("Author A1 hit flag", "any_author_a1_hit"), ("Author A2 reverse hit flag", "any_author_a2_reverse_hit"),
    ("Provenance multiplicity", "provenance_multiplicity"),
    ("Exact deterministic evidence-signature ID", "p3_evidence_signature_id"),
    ("Project-specific evidence subgroup ID", "p3_project_evidence_subgroup_id"),
    ("Project-work candidate count", "p3_project_work_candidate_count"),
    ("Project-work evidence-signature count", "p3_project_work_evidence_pattern_count"),
    ("Project-work complexity class", "p3_project_work_complexity_class"),
    ("Deterministic review/risk flags", "p3_risk_flags"),
]


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    return sha_bytes(Path(path).read_bytes())


def read_tsv(path):
    with Path(path).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t", strict=True))


def dump_json(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def source_tree_hashes():
    protected = [
        ROOT / "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_v1",
        ROOT / "derived/openalex_production/p2_deterministic_grouping_v1",
        ROOT / "derived/openalex_production/p3_deterministic_review_inventory_v1",
        ROOT / "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_batches_v1",
        ROOT / "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_P2_complete_v1",
        ROOT / "derived/bl_calibration", ROOT / "scripts/bl",
    ]
    result = {}
    for root in protected:
        if root.exists():
            for p in sorted(root.rglob("*")):
                if p.is_file():
                    result[str(p.relative_to(ROOT))] = sha_file(p)
    return result


def git_value(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def markdown_value(s):
    # Table-safe, line-stable rendering. Original cell values remain the source of truth.
    return (s if s != "" else "(blank)").replace("|", "\\|").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


def code_block(text):
    longest = max((len(run) for run in __import__("re").findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}\n{text}\n{fence}"


def sheet_markdown(batch_id, rows):
    out = [f"# P3 human review sheet — {batch_id}", "", f"**Reviewer:** haruka_tsutsui", "", f"> **{NOTICE_1}**", "", f"> **{NOTICE_2}**", "", "Review each candidate independently under the frozen protocol. The work and evidence grouping below is for navigation; it does not determine a judgment.", ""]
    by_work = defaultdict(list)
    for r in rows:
        by_work[r["project_work_id"]].append(r)
    for work_id in sorted(by_work):
        wr = by_work[work_id]
        first = wr[0]
        flags = sorted({f for row in wr for f in row["p3_risk_flags"].split("|") if f})
        out += [f"## Project work {work_id}", "", f"- Candidate count in full P3 inventory: {first['p3_project_work_candidate_count']}", f"- Complexity class: {first['p3_project_work_complexity_class']}", f"- Evidence-signature count for this project work: {first['p3_project_work_evidence_pattern_count']}", f"- Deterministic risk flags present in this batch segment: {', '.join(flags) if flags else 'none'}", "", "Each candidate remains an independent review unit.", ""]
        by_subgroup = defaultdict(list)
        for row in wr:
            by_subgroup[row["p3_project_evidence_subgroup_id"]].append(row)
        for subgroup_id in sorted(by_subgroup, key=lambda k: min(int(r["p3_review_order"]) for r in by_subgroup[k])):
            sr = sorted(by_subgroup[subgroup_id], key=lambda x: int(x["p3_review_order"]))
            out += [f"### Evidence subgroup {subgroup_id}", "", f"Candidates in this sheet: {len(sr)}", ""]
            for r in sr:
                out += [f"#### Candidate {r['review_candidate_id']} — review order {r['p3_review_order']}", "", "| Field | Frozen value |", "|---|---|"]
                for label, key in DISPLAY_FIELDS:
                    out.append(f"| {label} | {markdown_value(r[key])} |")
                out += ["", "**Title context (OpenAlex display_name):**", "", code_block(r["display_name"]), "", "**Abstract context (full frozen text):**", "", code_block(r["abstract"]), "", "**Author-match context:** Compare the raw A1/A2 match information above with the displayed OpenAlex title and abstract; no title/author co-location is inferred by this sheet.", "", "**LLM reference suggestion (non-authoritative):**", "", f"- Judgment: {markdown_value(r['llm_target_attribution_judgment'])}", f"- Confidence: {markdown_value(r['llm_adjudication_confidence'])}", f"- Reason: {markdown_value(r['llm_attribution_reason_code'])}", "- Reviewer note:", "", code_block(r["llm_reviewer_note"]), "", "**Authoritative human adjudication fields (leave blank until independently reviewed):**", ""]
                for field in EMPTY_HUMAN:
                    out.append(f"- `{field}:` ")
                out += ["", "---", ""]
    return ("\n".join(out).rstrip() + "\n").encode("utf-8")


def tsv_bytes(columns, rows):
    import io
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=columns, delimiter="\t", lineterminator="\n", extrasaction="raise")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def build_payload():
    review = read_tsv(PACKAGE)
    inventory = read_tsv(INVENTORY)
    review_by_id = {r["review_candidate_id"]: r for r in review}
    inv_by_id = {r["review_candidate_id"]: r for r in inventory}
    if len(inv_by_id) != len(inventory) or len(review_by_id) != len(review):
        raise ValueError("duplicate candidate ID in source")
    p3 = [r for r in review if r["review_priority"] == "P3"]
    if len(p3) != 493 or set(inv_by_id) != {r["review_candidate_id"] for r in p3}:
        raise ValueError("inventory candidate set is not exact frozen P3 set")
    rows = []
    for base in inventory:
        src = review_by_id[base["review_candidate_id"]]
        if any(base[k] != src[k] for k in src):
            raise ValueError(f"inventory/source mismatch for {base['review_candidate_id']}")
        if src["review_priority"] != "P3" or any(src[k] for k in EMPTY_HUMAN):
            raise ValueError(f"non-P3 or populated human fields: {src['review_candidate_id']}")
        rows.append(base)
    batch_ids = sorted({r["p3_review_batch_id"] for r in rows}, key=lambda x: int(x[3:]))
    if batch_ids != [f"P3B{i:02d}" for i in range(1, 26)]:
        raise ValueError(f"expected 25 frozen P3 batches, got {batch_ids}")
    batches = defaultdict(list)
    for r in rows:
        batches[r["p3_review_batch_id"]].append(r)
    payload = {}
    batch_index = []
    for seq, bid in enumerate(batch_ids, 1):
        br = sorted(batches[bid], key=lambda r: int(r["p3_review_order"]))
        work_ids = sorted({r["project_work_id"] for r in br})
        complexity = dict(sorted(Counter(r["p3_project_work_complexity_class"] for r in {r['project_work_id']: r for r in br}.values()).items()))
        flags = Counter(f for r in br for f in r["p3_risk_flags"].split("|") if f)
        batch_index.append({
            "batch_id": bid, "batch_sequence": str(seq), "candidate_count": str(len(br)),
            "project_work_count": str(len(work_ids)), "project_work_ids": "|".join(work_ids),
            "complexity_class_distribution": json.dumps(complexity, sort_keys=True, separators=(",", ":")),
            "evidence_signature_count": str(len({r["p3_project_evidence_subgroup_id"] for r in br})),
            "raw_evidence_signature_count": str(len({r["p3_evidence_signature_id"] for r in br})),
            "risk_flag_counts": json.dumps(dict(sorted(flags.items())), sort_keys=True, separators=(",", ":")),
            "first_review_order": br[0]["p3_review_order"], "last_review_order": br[-1]["p3_review_order"],
        })
        payload[f"{bid}.md"] = sheet_markdown(bid, br)
    idxcols = ["batch_id", "batch_sequence", "candidate_count", "project_work_count", "project_work_ids", "complexity_class_distribution", "evidence_signature_count", "raw_evidence_signature_count", "risk_flag_counts", "first_review_order", "last_review_order"]
    payload["openalex_retrieval_precision_review_P3_human_review_sheets_v1_batch_index.tsv"] = tsv_bytes(idxcols, batch_index)
    plan = ["# P3 human-review sheets — index and review plan", "", "> **LLM output is a reference suggestion only. Apply the frozen human-review protocol independently.**", "", f"> **{NOTICE_2}**", "", "Reviewer: `haruka_tsutsui`", "", "The 25 batch boundaries and candidate memberships are copied from the frozen P3 deterministic review inventory. Candidate review order is the inventory's stable order. Within each sheet, candidates are grouped by project work and then by frozen project-specific evidence subgroup for navigation. Every candidate requires an independent judgment; structural similarity does not authorize a shared judgment.", "", "## Batch index", "", "| Batch | Candidates | Project works | Evidence subgroups | Complexity distribution | Review-order range |", "|---|---:|---:|---:|---|---:|"]
    for b in batch_index:
        plan.append(f"| {b['batch_id']} | {b['candidate_count']} | {b['project_work_count']} | {b['evidence_signature_count']} | `{b['complexity_class_distribution']}` | {b['first_review_order']}–{b['last_review_order']} |")
    plan += ["", "## Frozen protocol", "", "Apply [OpenAlex retrieval precision review protocol v1](../../../../docs/OPENALEX_PRECISION_REVIEW_PROTOCOL_V1.md) independently to each candidate. LLM fields are shown only as reference suggestions; they are not authoritative. The human adjudication fields in every sheet are intentionally empty.", ""]
    payload["openalex_retrieval_precision_review_P3_human_review_sheets_v1_index.md"] = ("\n".join(plan)).encode("utf-8")

    rendered_ids = []
    for bid in batch_ids:
        rendered_ids.extend(re.findall(r"^#### Candidate (OAPRV3_\S+) — review order \d+$", payload[f"{bid}.md"].decode("utf-8"), re.MULTILINE))
    expected_ids = [r["review_candidate_id"] for r in rows]

    inventory_rel = str(INVENTORY.relative_to(ROOT)); package_rel = str(PACKAGE.relative_to(ROOT))
    source_hashes = source_tree_hashes()
    head = git_value("rev-parse", "HEAD")
    branch = git_value("branch", "--show-current")
    output_hashes = {name: sha_bytes(data) for name, data in sorted(payload.items())}
    manifest = {
        "artifact": OUT_NAME, "version": "v1", "status": "deterministic human-review sheets; no judgments created",
        "source_branch": branch, "source_head": head,
        "reviewer_id_for_manual_review": "haruka_tsutsui",
        "authoritative_inputs": {package_rel: sha_file(PACKAGE), inventory_rel: sha_file(INVENTORY)},
        "protected_source_tree_sha256": source_hashes,
        "candidate_count": len(rows), "batch_count": len(batch_ids), "batch_ids": batch_ids,
        "output_sha256_before_audit_and_manifest": output_hashes,
        "deterministic_notices": [NOTICE_1, NOTICE_2],
        "precision_calculated": False, "human_judgments_created": False,
    }
    manifest_name = "openalex_retrieval_precision_review_P3_human_review_sheets_v1_manifest.json"
    payload[manifest_name] = dump_json(manifest)
    core = {name: sha_bytes(data) for name, data in sorted(payload.items())}
    audit = {
        "artifact": OUT_NAME, "status": "PASSED", "checks": {
            "exactly_493_candidates": len(rows) == 493,
            "candidate_id_set_exactly_frozen_p3": set(inv_by_id) == {r["review_candidate_id"] for r in p3},
            "no_duplicate_candidate_id": len(rows) == len({r["review_candidate_id"] for r in rows}),
            "each_candidate_once_across_sheets": sum(len(batches[b]) for b in batch_ids) == 493 and sum(Counter(r["review_candidate_id"] for r in batches[b]).total() for b in batch_ids) == 493,
            "exactly_25_frozen_batches": batch_ids == [f"P3B{i:02d}" for i in range(1, 26)],
            "exactly_493_candidate_entries_rendered": len(rendered_ids) == 493,
            "rendered_candidate_ids_exactly_match_inventory_once": len(rendered_ids) == len(set(rendered_ids)) and set(rendered_ids) == set(expected_ids),
            "batch_membership_exact_inventory": all(all(r["p3_review_batch_id"] == bid for r in batches[bid]) for bid in batch_ids),
            "review_order_exact_inventory": sorted(int(r["p3_review_order"]) for r in rows) == list(range(1, 494)),
            "all_source_identity_provenance_evidence_fields_match": all(all(inv_by_id[r["review_candidate_id"]][k] == r[k] for k in r) for r in p3),
            "all_human_fields_empty": all(not r[k] for r in rows for k in EMPTY_HUMAN),
            "no_p1_p2_included": all(review_by_id[r["review_candidate_id"]]["review_priority"] == "P3" for r in rows),
            "source_frozen_hashes_recorded": bool(source_hashes),
            "no_bl_changes": True,
            "deterministic_replay_byte_identical": True,
        },
        "dimensions": {"sheets": len(batch_ids), "candidates": len(rows), "project_works": len({r['project_work_id'] for r in rows}), "batches": len(batch_ids)},
        "batch_candidate_counts": {b: len(batches[b]) for b in batch_ids},
        "complexity_class_distribution_project_works": dict(sorted(Counter({r["project_work_id"]: r["p3_project_work_complexity_class"] for r in rows}.values()).items())),
        "risk_flag_candidate_counts": dict(sorted(Counter(f for r in rows for f in set(r["p3_risk_flags"].split("|")) if f).items())),
        "output_hashes_excluding_audit": core,
        "protected_source_tree_sha256": source_hashes,
        "statement": "Review sheets contain no authoritative human judgments and calculate no precision. Grouping is a review aid only and does not authorize shared human judgments.",
    }
    if not all(audit["checks"].values()):
        audit["status"] = "FAILED"
    payload["openalex_retrieval_precision_review_P3_human_review_sheets_v1_audit.json"] = dump_json(audit)
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    out = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"Refusing nonempty destination: {out}")
    # Independently render twice from the frozen inputs and require exact bytes.
    first = build_payload(); second = build_payload()
    if first != second:
        raise SystemExit("Deterministic render replay differs")
    out.mkdir(parents=True, exist_ok=True)
    for name, data in sorted(first.items()):
        (out / name).write_bytes(data)
    if any((out / name).read_bytes() != data for name, data in first.items()):
        raise SystemExit("Written output bytes differ from deterministic render")
    after = source_tree_hashes()
    if after != json.loads((out / "openalex_retrieval_precision_review_P3_human_review_sheets_v1_audit.json").read_text(encoding="utf-8"))["protected_source_tree_sha256"]:
        raise SystemExit("Protected frozen inputs changed during generation")
    if git_value("status", "--porcelain", "--", "derived/bl_calibration", "scripts/bl"):
        raise SystemExit("BL path has git changes")
    audit_path = out / "openalex_retrieval_precision_review_P3_human_review_sheets_v1_audit.json"
    if json.loads(audit_path.read_text(encoding="utf-8"))["status"] != "PASSED":
        raise SystemExit("Audit failed; see audit JSON")
    print(json.dumps({"output_dir": str(out), "files": len(first), "sha256": {n: sha_file(out / n) for n in sorted(first)}, "audit": "PASSED"}, indent=2))


if __name__ == "__main__":
    main()
