#!/usr/bin/env python3
"""Parse the BL production v3 raw MARCXML responses (all batches; v1 parse_record reused).

Inputs
  derived/bl_production/production_v3/retrieval/batch_NNN/physical_requests.tsv   (outcome=COMPLETE rows)
  derived/bl_production/production_v3/retrieval/batch_NNN/logical_queries.tsv     (phys_id -> target_id, route)
  derived/bl_production/production_v3/retrieval/batch_NNN/run_manifest_*.json     (raw_root, batch_complete)
  raw XML under raw_root (private, outside the repository)

Outputs, PRIVATE (--out-dir, default /media/hdd1/user/tsutsui/bl/production_v3_derived; never inside the repo):
  records_parsed_v3.tsv        one row per distinct MARC 001 (same columns as v2)
  target_record_links_v3.tsv   target_id x marc_001 x routes (T2/K1/A1 and their q twins), batch, lanes
  parse_conflicts_v3.tsv       MARC 001 seen with differing field values across responses

Output, PUBLIC
  derived/bl_production/production_v3/parsed_manifest_v1.json   counts per batch and overall; sha256 of private files

Can run while retrieval is still going (--batches 1-3 or default = all batches with a manifest);
incomplete batches are parsed as far as their COMPLETE requests go and flagged in the manifest.
Refuses to overwrite unless --overwrite. No matching, no judgment.
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import importlib.util
import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RET = ROOT / "derived" / "bl_production" / "production_v3" / "retrieval"
PUBLIC_MANIFEST = ROOT / "derived" / "bl_production" / "production_v3" / "parsed_manifest_v1.json"
V1_PARSER = ROOT / "scripts" / "bl" / "parse_bl_verification_pilot_v1.py"
DEFAULT_OUT = "/media/hdd1/user/tsutsui/bl/production_v3_derived"

FIELDNAMES = ['marc_001', 'leader', 'cf008', 'cf008_date1', 'cf008_language',
              'f041_a', 'f041_b', 'f041_h',
              'f245_a', 'f245_b', 'f245_c', 'f246_a', 'f250_a',
              'f260_a', 'f260_b', 'f260_c', 'f264_a', 'f264_b', 'f264_c',
              'f100_entries', 'f700_entries', 'f240_a', 'f130_a',
              'has_f505', 'has_f600_t', 'f015_a', 'f020_a',
              'f336_a', 'f336_b', 'f337_a', 'f337_b', 'f338_a', 'f338_b',
              'has_f776', 'source_files']
TITLE_ROUTES = {"T2", "T2q", "K1", "K1q"}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_v1():
    spec = importlib.util.spec_from_file_location("bl_parse_v1", V1_PARSER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_batches_arg(s: str | None, available: list[int]) -> list[int]:
    if not s:
        return available
    out = set()
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return sorted(b for b in out if b in available)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=DEFAULT_OUT)
    ap.add_argument("--raw-root", default=None, help="override raw_root from the run manifests")
    ap.add_argument("--batches", default=None, help="e.g. 1-3,7 (default: every batch that has a run manifest)")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    out = Path(args.out_dir).expanduser().resolve()
    if ROOT in out.parents or out == ROOT:
        sys.exit(f"ERROR: --out-dir must be outside the repository: {out}")
    if (out / "records_parsed_v3.tsv").exists() and not args.overwrite:
        sys.exit(f"ERROR: output exists (use --overwrite to regenerate): {out}")

    batch_dirs = {int(p.name.split("_")[1]): p for p in RET.glob("batch_*") if list(p.glob("run_manifest_*.json"))}
    if not batch_dirs:
        sys.exit("ERROR: no batch with a run manifest under retrieval/")
    batches = parse_batches_arg(args.batches, sorted(batch_dirs))

    v1 = load_v1()
    NS = v1.NS
    records, sources, conflicts = {}, defaultdict(list), []
    links = defaultdict(set)      # (target_id, marc_001) -> {routes}
    link_batch = {}               # (target_id, marc_001) -> batch
    target_lane = {}
    per_batch, raw_roots = {}, set()
    no_001 = parse_errors = files_missing = 0

    for b in batches:
        bd = batch_dirs[b]
        manifests = sorted(bd.glob("run_manifest_*.json"))
        m = json.loads(manifests[-1].read_text())
        raw_root = Path(args.raw_root).expanduser().resolve() if args.raw_root else Path(m["raw_root"])
        raw_roots.add(str(raw_root))
        reqs = []
        with open(bd / "physical_requests.tsv", encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                if row["outcome"] == "COMPLETE":
                    reqs.append(row)
        phys_to_targets = defaultdict(set)
        with open(bd / "logical_queries.tsv", encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                if row["phys_id"]:
                    phys_to_targets[row["phys_id"]].add((row["target_id"], row["route"]))
                    target_lane[row["target_id"]] = row["target_lane"]
        n_rec_before, n_links_before = len(records), len(links)
        for req in reqs:
            raw_file = raw_root / req["raw_relpath"]
            if not raw_file.exists():
                files_missing += 1
                continue
            try:
                root = ET.parse(raw_file).getroot()
            except ET.ParseError:
                parse_errors += 1
                continue
            for rec_elem in root.findall(".//marc:record", NS):
                rec = v1.parse_record(rec_elem)
                mid = rec.get("marc_001", "")
                if not mid:
                    no_001 += 1
                    continue
                sources[mid].append(req["raw_relpath"])
                if mid in records:
                    for k, v in rec.items():
                        if k != "marc_001" and records[mid].get(k) != v:
                            conflicts.append((mid, k, records[mid].get(k), v))
                else:
                    records[mid] = rec
                for tid, route in phys_to_targets[req["phys_id"]]:
                    links[(tid, mid)].add(route)
                    link_batch.setdefault((tid, mid), b)
        per_batch[b] = {"complete_requests": len(reqs), "batch_complete": bool(m.get("batch_complete")),
                        "new_records": len(records) - n_rec_before, "new_links": len(links) - n_links_before}

    out.mkdir(parents=True, exist_ok=True)
    p_rec = out / "records_parsed_v3.tsv"
    with open(p_rec, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter="\t", extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for mid in sorted(records):
            r = records[mid].copy()
            r["source_files"] = "|".join(sources[mid])
            w.writerow(r)
    p_links = out / "target_record_links_v3.tsv"
    with open(p_links, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["target_id", "target_lane", "marc_001", "batch", "routes", "n_routes", "via_title_route",
                    "via_a1_only", "via_quote_stripped"])
        for (tid, mid), rs in sorted(links.items()):
            title = bool(rs & TITLE_ROUTES)
            w.writerow([tid, target_lane.get(tid, ""), mid, link_batch[(tid, mid)], ";".join(sorted(rs)), len(rs),
                        str(title), str(not title), str(any(r.endswith("q") for r in rs))])
    p_conf = out / "parse_conflicts_v3.tsv"
    with open(p_conf, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["marc_001", "field", "value_first", "value_other"])
        w.writerows(conflicts)

    targets = {tid for tid, _ in links}
    multi = defaultdict(set)
    for tid, mid in links:
        multi[mid].add(tid)
    manifest = {
        "release": "bl_production_v3_parsed_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "parser": "scripts/bl/parse_bl_verification_pilot_v1.py (parse_record) via scripts/bl/parse_bl_production_v3_v1.py",
        "v1_parser_sha256": sha256(V1_PARSER),
        "raw_roots": sorted(raw_roots), "private_out_dir": str(out),
        "batches_parsed": batches, "batches_incomplete": [b for b in batches if not per_batch[b]["batch_complete"]],
        "per_batch": per_batch,
        "raw_files_missing": files_missing, "xml_parse_errors": parse_errors, "records_without_001": no_001,
        "distinct_records": len(records), "link_rows": len(links), "targets_with_records": len(targets),
        "records_linked_to_multiple_targets": sum(1 for v in multi.values() if len(v) > 1),
        "field_conflicts": len(conflicts),
        "private_files_sha256": {p.name: sha256(p) for p in (p_rec, p_links, p_conf)},
        "note": "Private files hold BL record content and stay outside the public repository. Re-run with --overwrite as batches complete.",
    }
    PUBLIC_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in manifest.items() if k not in ("private_files_sha256", "per_batch")}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
