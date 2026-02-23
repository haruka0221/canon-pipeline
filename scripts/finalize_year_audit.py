#!/usr/bin/env python3
from __future__ import annotations
import csv, json, re
from pathlib import Path

YEAR_RE = re.compile(r'(?<!\d)(1[0-9]\d{2}|20\d{2})(?!\d)')

RAW_DIR = Path("raw/editions_year_audit")
FP_TSV  = Path("derived/year_audit_first_publish_year.tsv")
OUT_TSV = Path("derived/year_audit_final.tsv")

def min_year_from_json(p: Path):
    if not p.exists():
        return None, 0, 0
    j = json.load(p.open(encoding="utf-8"))
    entries = j.get("entries", [])
    years=[]
    for e in entries:
        s = e.get("publish_date")
        if isinstance(s, str):
            m = YEAR_RE.search(s)
            if m:
                years.append(int(m.group(1)))
    return (min(years) if years else None, len(entries), len(years))

def main():
    rows=[]
    with FP_TSV.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            wid = row["work_id"]
            fpy = row.get("first_publish_year","").strip()
            try:
                fpy_i = int(fpy) if fpy else None
            except:
                fpy_i = None

            p0 = RAW_DIR / f"{wid}.json"
            p50 = RAW_DIR / f"{wid}_offset50.json"
            p100 = RAW_DIR / f"{wid}_offset100.json"

            m0, n0, y0 = min_year_from_json(p0)
            m50, n50, y50 = min_year_from_json(p50)
            m100, n100, y100 = min_year_from_json(p100)

            observed = [x for x in [m0, m50, m100] if x is not None]
            min_observed = min(observed) if observed else None

            # simple status classification
            status = ""
            if fpy_i is None or min_observed is None:
                status = "unknown"
            else:
                if min_observed == fpy_i:
                    status = "matched"
                elif abs(min_observed - fpy_i) <= 2:
                    status = "near_match"
                else:
                    status = "mismatch"

            rows.append({
                "work_id": wid,
                "work_key": row.get("work_key",""),
                "first_publish_year": fpy,
                "min_year_offset0": "" if m0 is None else str(m0),
                "min_year_offset50": "" if m50 is None else str(m50),
                "min_year_offset100": "" if m100 is None else str(m100),
                "min_year_observed": "" if min_observed is None else str(min_observed),
                "status": status,
                "offset0_entries": str(n0),
                "offset50_entries": str(n50),
                "offset100_entries": str(n100),
            })

    OUT_TSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_TSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter="\t")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda x: x["work_id"]))

    print("wrote", OUT_TSV, "rows", len(rows))
    # quick summary
    from collections import Counter
    c = Counter(r["status"] for r in rows)
    print("status_counts:", dict(c))

if __name__ == "__main__":
    main()
