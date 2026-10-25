#!/usr/bin/env python3
"""Parse the BL calibration v2 raw MARCXML responses (reusing the v1 parser).

Inputs
  derived/bl_calibration/calibration_v2/retrieval/physical_requests.tsv   (outcome=COMPLETE rows)
  derived/bl_calibration/calibration_v2/retrieval/logical_queries.tsv     (phys_id -> sample_id, route)
  derived/bl_calibration/calibration_v2/retrieval/run_manifest_*.json      (raw_root)
  raw XML under raw_root (private, outside the repository)

Outputs, PRIVATE (--out-dir, default ~/bl_raw/calibration_v2_derived; never inside the repo):
  records_parsed_v2.tsv        one row per distinct MARC 001, columns as in v1 records_parsed.tsv
  target_record_links_v2.tsv   sample_id x target_id x marc_001 x routes (T2/K1/A1 that returned it)
  parse_conflicts_v2.tsv       MARC 001 seen with differing field values across responses

Output, PUBLIC (repository):
  derived/bl_calibration/calibration_v2/parsed_manifest_v1.json  counts and sha256 of the private files

No matching, no judgment: values are preserved as the v1 parser emits them.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RET = ROOT / "derived" / "bl_calibration" / "calibration_v2" / "retrieval"
PUBLIC_MANIFEST = ROOT / "derived" / "bl_calibration" / "calibration_v2" / "parsed_manifest_v1.json"
V1_PARSER = ROOT / "scripts" / "bl" / "parse_bl_verification_pilot_v1.py"

FIELDNAMES = ['marc_001', 'leader', 'cf008', 'cf008_date1', 'cf008_language',
              'f041_a', 'f041_b', 'f041_h',
              'f245_a', 'f245_b', 'f245_c', 'f246_a', 'f250_a',
              'f260_a', 'f260_b', 'f260_c', 'f264_a', 'f264_b', 'f264_c',
              'f100_entries', 'f700_entries', 'f240_a', 'f130_a',
              'has_f505', 'has_f600_t', 'f015_a', 'f020_a',
              'f336_a', 'f336_b', 'f337_a', 'f337_b', 'f338_a', 'f338_b',
              'has_f776', 'source_files']


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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=str(Path.home() / "bl_raw" / "calibration_v2_derived"))
    ap.add_argument("--raw-root", default=None, help="override raw_root from the run manifests")
    args = ap.parse_args()

    out = Path(args.out_dir).expanduser().resolve()
    if ROOT in out.parents or out == ROOT:
        sys.exit(f"ERROR: --out-dir must be outside the repository: {out}")
    if (out / "records_parsed_v2.tsv").exists():
        sys.exit(f"ERROR: output exists, refusing to overwrite: {out}")

    manifests = sorted(RET.glob("run_manifest_*.json"))
    if not manifests:
        sys.exit("ERROR: no run_manifest_*.json in retrieval/")
    raw_roots = {json.loads(m.read_text())["raw_root"] for m in manifests}
    if args.raw_root:
        raw_root = Path(args.raw_root).expanduser().resolve()
    elif len(raw_roots) == 1:
        raw_root = Path(raw_roots.pop())
    else:
        sys.exit(f"ERROR: manifests disagree on raw_root: {raw_roots}; pass --raw-root")
    if not raw_root.exists():
        sys.exit(f"ERROR: raw_root not found: {raw_root}")

    v1 = load_v1()
    NS = v1.NS

    requests = []
    with open(RET / "physical_requests.tsv", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["outcome"] == "COMPLETE":
                requests.append(row)
    phys_ids = {r["phys_id"] for r in requests}

    # phys_id -> {(sample_id, target_id, route)}
    phys_to_targets = defaultdict(set)
    with open(RET / "logical_queries.tsv", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["phys_id"]:
                phys_to_targets[row["phys_id"]].add((row["sample_id"], row["target_id"], row["route"]))

    records, sources, conflicts = {}, defaultdict(list), []
    links = defaultdict(set)   # (sample_id, target_id, marc_001) -> {routes}
    no_001 = parse_errors = files_missing = 0
    for req in requests:
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
            m = rec.get("marc_001", "")
            if not m:
                no_001 += 1
                continue
            sources[m].append(req["raw_relpath"])
            if m in records:
                for k, v in rec.items():
                    if k != "marc_001" and records[m].get(k) != v:
                        conflicts.append((m, k, records[m].get(k), v))
            else:
                records[m] = rec
            for sample_id, target_id, route in phys_to_targets[req["phys_id"]]:
                links[(sample_id, target_id, m)].add(route)

    out.mkdir(parents=True, exist_ok=True)
    p_rec = out / "records_parsed_v2.tsv"
    with open(p_rec, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter="\t", extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for m in sorted(records):
            r = records[m].copy()
            r["source_files"] = "|".join(sources[m])
            w.writerow(r)

    p_links = out / "target_record_links_v2.tsv"
    with open(p_links, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["sample_id", "target_id", "marc_001", "routes", "n_routes", "via_title_route", "via_a1_only"])
        for (s, t, m), rs in sorted(links.items()):
            title_route = bool(rs & {"T2", "K1"})
            w.writerow([s, t, m, ";".join(sorted(rs)), len(rs), str(title_route), str(not title_route)])

    p_conf = out / "parse_conflicts_v2.tsv"
    with open(p_conf, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["marc_001", "field", "value_first", "value_other"])
        w.writerows(conflicts)

    per_target = defaultdict(set)
    for (s, t, m) in links:
        per_target[s].add(m)
    multi_target = defaultdict(set)
    for (s, t, m) in links:
        multi_target[m].add(s)

    manifest = {
        "release": "bl_calibration_v2_parsed_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "parser": "scripts/bl/parse_bl_verification_pilot_v1.py (parse_record) via scripts/bl/parse_bl_calibration_v2_v1.py",
        "v1_parser_sha256": sha256(V1_PARSER),
        "raw_root": str(raw_root),
        "private_out_dir": str(out),
        "complete_requests": len(requests), "physical_queries_with_complete_pages": len(phys_ids),
        "raw_files_missing": files_missing, "xml_parse_errors": parse_errors, "records_without_001": no_001,
        "distinct_records": len(records),
        "link_rows": len(links),
        "targets_with_records": len(per_target),
        "records_linked_to_multiple_targets": sum(1 for v in multi_target.values() if len(v) > 1),
        "field_conflicts": len(conflicts),
        "private_files_sha256": {p.name: sha256(p) for p in (p_rec, p_links, p_conf)},
        "note": "Private files hold BL record content and stay outside the public repository.",
    }
    PUBLIC_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in manifest.items() if k not in ("private_files_sha256",)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
