#!/usr/bin/env python3
from pathlib import Path
import csv
import glob
import os
from datetime import datetime

def file_info(p: Path) -> str:
    if not p.exists():
        return f"- MISS {p}"
    st = p.stat()
    return f"- OK {p} ({st.st_size} bytes, mtime={datetime.fromtimestamp(st.st_mtime)})"

def tsv_head(p: Path, n=5) -> str:
    if not p.exists():
        return ""
    lines=[]
    with p.open("r", encoding="utf-8", errors="replace", newline="") as f:
        for i, line in enumerate(f):
            lines.append(line.rstrip("\n"))
            if i+1>=n: break
    return "\n".join(lines)

def tsv_lines(p: Path) -> int:
    if not p.exists():
        return 0
    with p.open("r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)

def main():
    required = [
        Path("derived/ol_works_final_population.tsv"),
        Path("derived/README_population.txt"),
        Path("derived/editions_min_year_limit50.tsv"),
        Path("derived/year_audit_first_publish_year.tsv"),
        Path("derived/year_audit_joined_limit50.tsv"),
    ]
    out = Path("derived/inventory_report.md")
    raw_dir = Path("raw/editions_year_audit")

    with out.open("w", encoding="utf-8") as w:
        w.write("# canon-pipeline inventory report\n\n")
        w.write("## Required artifacts\n")
        for p in required:
            w.write(file_info(p) + "\n")

        w.write("\n## TSV quick stats\n")
        for p in [
            Path("derived/editions_min_year_limit50.tsv"),
            Path("derived/year_audit_first_publish_year.tsv"),
            Path("derived/year_audit_joined_limit50.tsv"),
        ]:
            w.write(f"\n### {p}\n")
            w.write(f"- lines: {tsv_lines(p)}\n")
            w.write("```tsv\n")
            w.write(tsv_head(p, 6) + "\n")
            w.write("```\n")

        w.write("\n## raw/editions_year_audit\n")
        if not raw_dir.exists():
            w.write("- MISS raw/editions_year_audit\n")
        else:
            all_json = sorted(raw_dir.glob("*.json"))
            offset_json = sorted(raw_dir.glob("*_offset*.json"))
            w.write(f"- total json: {len(all_json)}\n")
            w.write(f"- offset json: {len(offset_json)}\n\n")
            offsets={}
            for p in offset_json:
                wid = p.name.split("_offset")[0]
                offsets.setdefault(wid, []).append(p.name)
            w.write("### work_ids with offsets\n")
            for wid in sorted(offsets.keys()):
                w.write(f"- {wid}: {', '.join(sorted(offsets[wid]))}\n")

    print("wrote", out)

if __name__ == "__main__":
    main()
