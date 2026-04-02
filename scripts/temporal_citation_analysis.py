#!/usr/bin/env python3
"""
temporal_citation_analysis.py — Stage 6c: Temporal Citation Analysis
OpenAlexスナップショット（ローカル /mnt/d/openalex/works/）から
canonical 98作品の counts_by_year（年別被引用数）を抽出し、
decade別推移を集計する。API不使用・完全ローカル処理。

Usage:
    python3 scripts/temporal_citation_analysis.py

Inputs:
    /mnt/d/openalex/works/           外部SSDスナップショット
    derived/jstor_mentions.tsv       canonical flag, title, author

Outputs:
    derived/temporal_citations_raw.tsv      作品×年の被引用数
    derived/temporal_citations_decade.tsv   decade別集計
    derived/temporal_citations_summary.txt  サマリー
    logs/temporal_citation_{date}.log

依存: rapidfuzz (pip install rapidfuzz --break-system-packages)
所要時間: 約30〜60分（スナップショット全件スキャン）
"""

import csv, gzip, glob, json, logging, re, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

try:
    from rapidfuzz import fuzz
except ImportError:
    print("rapidfuzz not found. Run: pip install rapidfuzz --break-system-packages")
    sys.exit(1)

# ── Logging ──────────────────────────────────────────────────────────────────
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_path = log_dir / f"temporal_citation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
SNAPSHOT_DIR      = Path("/mnt/d/openalex/works")
DECADE_START      = 1950
DECADE_END        = 2025
TITLE_THRESHOLD   = 88   # rapidfuzz token_sort_ratio
MIN_TITLE_LEN     = 6

# ── Normalization (§5a v3-final) ──────────────────────────────────────────────
_LEADING_ART = re.compile(r'^(the|a|an)\s+', re.IGNORECASE)
_DROP        = re.compile(r"['\-\u2018\u2019\u201c\u201d]")
_NON_ALNUM   = re.compile(r'[^a-z0-9\s]')
_MULTI_SPC   = re.compile(r'\s+')

def normalize(t: str) -> str:
    t = t.lower()
    t = _LEADING_ART.sub('', t)
    t = _DROP.sub('', t)
    t = _NON_ALNUM.sub(' ', t)
    return _MULTI_SPC.sub(' ', t).strip()

def last_name(author: str) -> str:
    if not author:
        return ""
    parts = re.split(r'[,\s]+', author.strip())
    return normalize(parts[0]) if parts else ""

# ── Load canonical works ──────────────────────────────────────────────────────
def load_canonical(path: Path) -> list[dict]:
    works = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if int(row.get("canonical", 0)) != 1:
                continue
            title = row.get("title", "").strip()
            tn    = normalize(title)
            if len(tn) < MIN_TITLE_LEN:
                continue
            works.append({
                "work_id":    row["work_id"],
                "title":      title,
                "title_norm": tn,
                "last_name":  last_name(row.get("author", "")),
                "jstor":      int(row.get("jstor_mention_count", 0)),
            })
    return works

# ── Scan snapshot ─────────────────────────────────────────────────────────────
def scan_snapshot(canonical: list[dict]):
    # 3語プレフィックスインデックス（高速フィルタ用）
    title_index: dict[str, list[dict]] = defaultdict(list)
    for w in canonical:
        key = " ".join(w["title_norm"].split()[:3])
        title_index[key].append(w)

    cby_data: dict[str, list]  = {}   # work_id → counts_by_year
    matched_oa: dict[str, str] = {}   # work_id → OA display_name

    files = sorted(glob.glob(str(SNAPSHOT_DIR / "updated_date=*" / "part_*.gz")))
    log.info(f"Scanning {len(files)} snapshot files...")

    for i, fpath in enumerate(files):
        if i % 100 == 0:
            log.info(f"  {i}/{len(files)} ({100*i/len(files):.1f}%) "
                     f"| matched={len(cby_data)}/{len(canonical)}")
        if len(cby_data) == len(canonical):
            log.info("All canonical works matched — stopping early")
            break
        try:
            with gzip.open(fpath, 'rt', encoding='utf-8') as f:
                for line in f:
                    w   = json.loads(line)
                    cby = w.get("counts_by_year")
                    if not cby:
                        continue                         # counts_by_yearなし → スキップ
                    oa_title = w.get("display_name", "") or ""
                    oa_norm  = normalize(oa_title)
                    if len(oa_norm) < MIN_TITLE_LEN:
                        continue
                    key = " ".join(oa_norm.split()[:3])
                    candidates = title_index.get(key, [])
                    if not candidates:
                        continue

                    pub_year = w.get("publication_year") or 0
                    # 1880-1950の作品 → 出版年が1960以降なら別作品
                    if pub_year and not (1870 <= pub_year <= 1955):
                        continue

                    # 著者姓セット
                    oa_authors = set()
                    for a in (w.get("authorships") or []):
                        ln = last_name((a.get("author") or {}).get("display_name",""))
                        if ln:
                            oa_authors.add(ln)

                    for cand in candidates:
                        wid = cand["work_id"]
                        if wid in cby_data:
                            continue
                        score = fuzz.token_sort_ratio(oa_norm, cand["title_norm"])
                        if score < TITLE_THRESHOLD:
                            continue
                        cand_ln = cand["last_name"]
                        if cand_ln and oa_authors and cand_ln not in oa_authors:
                            continue   # 著者不一致
                        log.info(f"  MATCH '{cand['title'][:45]}' "
                                 f"← '{oa_title[:45]}' "
                                 f"score={score} year={pub_year}")
                        cby_data[wid]   = cby
                        matched_oa[wid] = oa_title
                        break
        except Exception as e:
            log.warning(f"Error {fpath}: {e}")

    log.info(f"Scan done: {len(cby_data)}/{len(canonical)} matched")
    return cby_data, matched_oa

# ── Aggregate & write ─────────────────────────────────────────────────────────
def main():
    jstor_path = Path("derived/jstor_mentions.tsv")
    if not jstor_path.exists():
        log.error(f"Not found: {jstor_path}"); sys.exit(1)
    if not SNAPSHOT_DIR.exists():
        log.error(f"Snapshot not found: {SNAPSHOT_DIR}"); sys.exit(1)

    canonical = load_canonical(jstor_path)
    log.info(f"Canonical works: {len(canonical)}")

    cby_data, matched_oa = scan_snapshot(canonical)

    decades = [f"{d}s" for d in range(DECADE_START, DECADE_END + 1, 10)]
    raw_rows    = []
    decade_rows = []

    for work in canonical:
        wid = work["work_id"]
        cby = cby_data.get(wid, [])
        dec_counts: dict[str, int] = defaultdict(int)

        for entry in cby:
            year  = entry.get("year", 0)
            count = entry.get("cited_by_count", 0)
            raw_rows.append({
                "work_id": wid, "title": work["title"],
                "author_ln": work["last_name"], "jstor": work["jstor"],
                "oa_match": matched_oa.get(wid, ""),
                "year": year, "cited_by_count": count,
            })
            if DECADE_START <= year <= DECADE_END:
                dec_counts[f"{(year//10)*10}s"] += count

        total = sum(dec_counts.values())
        peak  = max(decades, key=lambda d: dec_counts.get(d,0)) if total else "—"
        row   = {
            "work_id": wid, "title": work["title"][:60],
            "last_name": work["last_name"], "jstor": work["jstor"],
            "matched": int(wid in cby_data), "oa_total": total, "peak_decade": peak,
        }
        for dec in decades:
            row[dec] = dec_counts.get(dec, 0)
        decade_rows.append(row)

    decade_rows.sort(key=lambda r: r["oa_total"], reverse=True)

    # Write raw
    if raw_rows:
        with open("derived/temporal_citations_raw.tsv","w",newline="",encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(raw_rows[0].keys()), delimiter="\t")
            w.writeheader(); w.writerows(raw_rows)
        log.info(f"Raw → derived/temporal_citations_raw.tsv ({len(raw_rows)} rows)")

    # Write decade
    fieldnames = ["work_id","title","last_name","jstor","matched","oa_total","peak_decade"]+decades
    with open("derived/temporal_citations_decade.tsv","w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        w.writeheader(); w.writerows(decade_rows)
    log.info(f"Decade → derived/temporal_citations_decade.tsv ({len(decade_rows)} rows)")

    # Summary
    matched   = [r for r in decade_rows if r["matched"]]
    unmatched = [r for r in decade_rows if not r["matched"]]
    dec_totals = defaultdict(int)
    for r in matched:
        for dec in decades:
            dec_totals[dec] += r.get(dec,0)

    lines = [
        "="*70, "TEMPORAL CITATION ANALYSIS (Stage 6c)",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", "="*70,
        f"\nCanonical works : {len(decade_rows)}",
        f"Matched in OA   : {len(matched)} ({100*len(matched)/max(len(decade_rows),1):.1f}%)",
        f"Unmatched       : {len(unmatched)}",
        "", "TOP 20 BY OA CITATIONS:",
        f"  {'Title':<43} {'JSTOR':>6} {'OA':>7}  Peak", "  "+"-"*65,
    ]
    for r in decade_rows[:20]:
        pv = r.get(r["peak_decade"],0) if r["peak_decade"]!="—" else 0
        lines.append(f"  {r['title'][:43]:<43} {r['jstor']:>6} {r['oa_total']:>7}"
                     f"  {r['peak_decade']}({pv})")
    lines += ["","DECADE TOTALS:", f"  {'Decade':<8} {'Citations':>12}", "  "+"-"*22]
    for dec in decades:
        lines.append(f"  {dec:<8} {dec_totals[dec]:>12,}")
    if unmatched:
        lines += [f"","UNMATCHED ({len(unmatched)}):"]
        for r in unmatched:
            lines.append(f"  {r['title'][:55]}  jstor={r['jstor']}")

    summary = "\n".join(lines)
    print("\n"+summary)
    Path("derived/temporal_citations_summary.txt").write_text(summary, encoding="utf-8")
    log.info("Stage 6c complete.")

if __name__ == "__main__":
    main()