#!/usr/bin/env python3
from pathlib import Path
import glob
import os

ROOT = Path(".")
paths_required = [
    Path("derived/editions_min_year_limit50.tsv"),
    Path("derived/year_audit_first_publish_year.tsv"),
    Path("derived/year_audit_joined_limit50.tsv"),
    Path("derived/ol_works_final_population.tsv"),
    Path("derived/README_population.txt"),
]

def exists_line(p: Path) -> str:
    if p.exists():
        return f"OK  {p}  ({p.stat().st_size} bytes)"
    return f"MISS {p}"

def head_lines(p: Path, n=5) -> str:
    if not p.exists():
        return ""
    out=[]
    with p.open("r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            out.append(line.rstrip("\n"))
            if i+1 >= n:
                break
    return "\n".join(out)

def count_lines(p: Path) -> int:
    if not p.exists():
        return 0
    with p.open("r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)

def main():
    print("== Required artifacts ==")
    for p in paths_required:
        print(exists_line(p))

    print("\n== TSV quick stats ==")
    for p in [
        Path("derived/editions_min_year_limit50.tsv"),
        Path("derived/year_audit_first_publish_year.tsv"),
        Path("derived/year_audit_joined_limit50.tsv"),
    ]:
        if p.exists():
            print(f"{p}: lines={count_lines(p)}")
            print("head:")
            print(head_lines(p, 5))
            print("---")

    print("\n== raw/editions_year_audit inventory ==")
    base_dir = Path("raw/editions_year_audit")
    if not base_dir.exists():
        print("MISS raw/editions_year_audit")
        return

    all_json = sorted(base_dir.glob("*.json"))
    offset_json = sorted(base_dir.glob("*_offset*.json"))

    print(f"total json: {len(all_json)}")
    print(f"offset json: {len(offset_json)}")

    # list offsets by work_id
    offsets = {}
    for p in offset_json:
        name = p.name
        # e.g. OL472073W_offset50.json
        wid = name.split("_offset")[0]
        offsets.setdefault(wid, []).append(name)

    if offsets:
        print("\nwork_ids with offsets:")
        for wid in sorted(offsets.keys()):
            files = ", ".join(sorted(offsets[wid]))
            print(f"- {wid}: {files}")
    else:
        print("no offset files found")

if __name__ == "__main__":
    main()
