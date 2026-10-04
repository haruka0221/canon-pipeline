#!/usr/bin/env python3
"""Build deterministic P2 evidence subgroup mapping and review sheets."""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_v1/full_profile_57959e90/openalex_retrieval_precision_review_human_adjudication_v1.tsv"
OUT = ROOT / "derived/openalex_production/p2_deterministic_grouping_v1/full_profile_57959e90"
FIELDS = ["title_match_norms", "author_a1_norms", "author_a2_reverse_norms",
          "any_title_match_in_title", "any_title_match_in_abstract", "any_author_a1_hit",
          "any_author_a2_reverse_hit", "hit_location", "abstract_available", "provenance_multiplicity"]
IDENTITY = ["review_priority", "review_order", "review_candidate_id", "project_work_id",
            "openalex_work_id", "increment_type", "review_semantic_group_id"]
HUMAN = ["human_target_attribution_judgment", "human_adjudication_confidence",
         "human_attribution_reason_code", "human_reviewer_note", "human_reviewer_id",
         "human_adjudicated_at_utc", "human_evidence_used_oa_title", "human_evidence_used_oa_abstract",
         "human_evidence_used_project_provenance", "human_evidence_used_external_check",
         "human_external_check_reference", "human_external_check_note"]
HASH_FIELDS = {"algorithm": "SHA-256", "canonicalization": "UTF-8 JSON array; ensure_ascii=False; separators=(',', ':'); no Unicode normalization; field order exactly signature_fields", "input": "JSON array [review_semantic_group_id, ...10 raw TSV string values...]", "output": "OAPESG1_ followed by first 16 lowercase hexadecimal SHA-256 characters"}

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def read_tsv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))

def canonical(values):
    return json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

def complexity(rows):
    signatures = {tuple(r[k] for k in FIELDS) for r in rows}
    reasons = {r["llm_attribution_reason_code"] for r in rows}
    judgments = {r["llm_target_attribution_judgment"] for r in rows}
    n = len(rows)
    if n > 8 or len(reasons) > 1 or len(judgments) > 1 or len(signatures) >= 4:
        return "HETEROGENEOUS"
    if n <= 3 and len(signatures) == 1:
        return "SIMPLE_HOMOGENEOUS"
    return "MODERATE"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheets-dir", type=Path, help="Optional output directory for Markdown review sheets")
    ap.add_argument("--out-dir", type=Path, default=OUT)
    ap.add_argument("--source", type=Path, default=SOURCE)
    ap.add_argument("--compare-sheets-dir", type=Path)
    args = ap.parse_args()
    rows = read_tsv(args.source)
    source_by_id = {r["review_candidate_id"]: r for r in rows}
    if len(source_by_id) != len(rows) or len(rows) != 661:
        raise SystemExit("Expected 661 unique rows in frozen review package")
    p2 = [r for r in rows if r["review_priority"] == "P2"]
    if len(p2) != 119:
        raise SystemExit(f"Expected 119 P2 rows, got {len(p2)}")
    by_sem = defaultdict(list)
    for r in p2:
        by_sem[r["review_semantic_group_id"]].append(r)
    if len(by_sem) != 16:
        raise SystemExit(f"Expected 16 semantic groups, got {len(by_sem)}")
    out = []
    sig_members = defaultdict(list)
    sem_counts = {g: len(v) for g, v in by_sem.items()}
    for sem, members in by_sem.items():
        sig_groups = defaultdict(list)
        for r in members:
            sig = tuple(r[k] for k in FIELDS)
            sig_groups[sig].append(r)
        for sig, subgroup in sig_groups.items():
            digest = hashlib.sha256(canonical([sem, *sig])).hexdigest()[:16]
            subgroup_id = "OAPESG1_" + digest
            sig_members[(sem, sig)] = subgroup
            for r in subgroup:
                out.append({"review_order": r["review_order"], "review_candidate_id": r["review_candidate_id"],
                    "project_work_id": r["project_work_id"], "review_semantic_group_id": sem,
                    "evidence_subgroup_id": subgroup_id, **{k: r[k] for k in FIELDS},
                    "semantic_group_candidate_count": str(sem_counts[sem]),
                    "evidence_subgroup_candidate_count": str(len(subgroup)),
                    "deterministic_complexity_class": complexity(members),
                    "llm_target_attribution_judgment": r["llm_target_attribution_judgment"],
                    "llm_attribution_reason_code": r["llm_attribution_reason_code"]})
    out.sort(key=lambda x: int(x["review_order"]))
    columns = list(out[0])
    args.out_dir.mkdir(parents=True, exist_ok=True)
    mapping_path = args.out_dir / "openalex_p2_deterministic_grouping_v1.tsv"
    with mapping_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, delimiter="\t", lineterminator="\n")
        w.writeheader(); w.writerows(out)
    group_stats = []
    for sem, members in sorted(by_sem.items()):
        signatures = {tuple(r[k] for k in FIELDS) for r in members}
        subgroup_id_map = {hashlib.sha256(canonical([sem, *sig])).hexdigest()[:16]: group for (g, sig), group in sig_members.items() if g == sem}
        group_stats.append({"review_semantic_group_id": sem, "candidate_count": len(members), "evidence_subgroup_count": len(signatures), "complexity_class": complexity(members)})
    audit = {
      "audit": "openalex-p2-deterministic-grouping-v1", "audit_status": "PASSED",
      "checks": {"exactly_119_P2_rows": len(out)==119, "exactly_16_semantic_groups": len(by_sem)==16,
       "exactly_29_evidence_subgroups": len(sig_members)==29, "largest_subgroup_32": max(map(len,sig_members.values()))==32,
       "every_candidate_once": len({r["review_candidate_id"] for r in out})==119,
       "P1_P3_excluded": all(r["review_priority"]=="P2" for r in p2),
       "source_identity_exact": all(source_by_id[r["review_candidate_id"]]["review_priority"]=="P2" and source_by_id[r["review_candidate_id"]]["review_order"]==r["review_order"] and source_by_id[r["review_candidate_id"]]["project_work_id"]==r["project_work_id"] and source_by_id[r["review_candidate_id"]]["review_semantic_group_id"]==r["review_semantic_group_id"] for r in out),
       "membership_exact_tuple_equality": all(len({tuple(r[k] for k in FIELDS) for r in g})==1 for g in sig_members.values()),
       "complexity_thresholds_exact": all(next(s["complexity_class"] for s in group_stats if s["review_semantic_group_id"]==sem)==complexity(m) for sem,m in by_sem.items()),
       "no_human_fields_populated": all(not any(r.get(k, "") for k in HUMAN) for r in p2),
       "no_P1_P3_rows": set(r["review_priority"] for r in p2)=={"P2"}},
      "counts": {"rows":len(out), "semantic_groups":len(by_sem), "evidence_subgroups":len(sig_members), "largest_subgroup":max(map(len,sig_members.values())), "complexity":dict(Counter(r["complexity_class"] for r in group_stats))},
      "semantic_groups": group_stats, "signature_fields": FIELDS, "hash_procedure": HASH_FIELDS,
      "source": {"path":str(args.source), "sha256":sha(args.source)},
      "frozen_openalex_inputs": {"review_package":sha(args.source), "review_view_tsv":sha(ROOT/"derived/openalex_production/precision_review_view_v1/full_profile_57959e90/openalex_precision_review_view_v1.tsv"), "llm_evidence_tsv":sha(ROOT/"derived/openalex_production/openalex_retrieval_precision_review_llm_evidence_v1/full_profile_57959e90/openalex_retrieval_precision_review_llm_evidence_v1.tsv")}}
    audit_path = args.out_dir / "openalex_p2_deterministic_grouping_v1_audit_v1.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    manifest = {"release":"openalex_p2_deterministic_grouping_v1", "version":"v1", "status":"PASSED", "artifact_status":"DETERMINISTIC_GROUPING_REVIEW_SUPPORT_ONLY", "authoritative":False, "human_adjudication_performed":False, "precision_calculated":False, "frozen_baseline_commit":"60b22bd55726d02c4c20aaa11763b1ddad784788", "builder":{"path":"scripts/build_openalex_p2_deterministic_grouping_v1.py","sha256":sha(Path(__file__))}, "specification":"docs/OPENALEX_P2_DETERMINISTIC_GROUPING_V1.md", "source":audit["source"], "rows":len(out), "columns":len(columns), "semantic_groups":len(by_sem), "evidence_subgroups":len(sig_members), "outputs":{mapping_path.name:{"sha256":sha(mapping_path),"rows":len(out),"columns":len(columns)}, audit_path.name:{"sha256":sha(audit_path)}}}
    (args.out_dir / "openalex_p2_deterministic_grouping_v1_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    if args.sheets_dir:
        args.sheets_dir.mkdir(parents=True, exist_ok=True)
        for sem, members in sorted(by_sem.items()):
            lines=[f"# P2 deterministic review sheet — {sem}", "", f"- Candidate count: {len(members)}", f"- Evidence subgroups: {len({tuple(r[k] for k in FIELDS) for r in members})}", f"- Complexity class: {complexity(members)}", "", "Grouping is deterministic review support only. No human target-attribution judgment is assigned.", ""]
            for i,(sig,sg) in enumerate(sorted(((s,g) for (g,s),g in sig_members.items() if g==sem), key=lambda x:min(int(r['review_order']) for r in x[1])),1):
                lines += [f"## Evidence subgroup {i:02d}", "", "- Candidate IDs: "+", ".join(r["review_candidate_id"] for r in sg), "- review_order: "+", ".join(r["review_order"] for r in sg), ""]
            (args.sheets_dir / f"{sem}.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    if args.compare_sheets_dir:
        previous = {}
        for path in args.compare_sheets_dir.glob("*.md"):
            sem = path.stem
            text = path.read_text(encoding="utf-8")
            chunks = re.split(r"(?m)^### Evidence subgroup ", text)[1:]
            previous[sem] = []
            for chunk in chunks:
                match = re.search(r"(?m)^- Candidate IDs: (.*)$", chunk)
                if match:
                    previous[sem].append(set(x.strip() for x in match.group(1).split(",") if x.strip()))
        current = {}
        for sem in by_sem:
            current[sem] = [set(r["review_candidate_id"] for r in g) for (gsem,_),g in sig_members.items() if gsem==sem]
        norm = lambda d: {k: sorted([tuple(sorted(s)) for s in v]) for k,v in d.items()}
        comparison_ok = norm(current) == norm(previous)
        audit["checks"]["existing_tmp_sheet_membership_exact"] = comparison_ok
        audit["existing_sheet_comparison"] = {"path":str(args.compare_sheets_dir), "sheet_count":len(previous), "membership_equal":comparison_ok}
        audit["audit_status"] = "PASSED" if all(audit["checks"].values()) else "FAILED"
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        manifest["status"] = audit["audit_status"]
        manifest["audit_sha256"] = sha(audit_path)
        manifest["outputs"][audit_path.name]["sha256"] = sha(audit_path)
        (args.out_dir / "openalex_p2_deterministic_grouping_v1_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"rows":len(out),"semantic_groups":len(by_sem),"evidence_subgroups":len(sig_members),"largest_subgroup":max(map(len,sig_members.values())),"complexity":audit["counts"]["complexity"],"mapping_sha256":sha(mapping_path),"audit_status":"PASSED"},sort_keys=True))

if __name__ == "__main__": main()
