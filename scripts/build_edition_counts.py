"""
Stage 4f: Edition Count + ocaid Extraction from OL Editions Dump
=================================================================
editions dumpをストリーム処理し、work_keyごとに：
  - edition_count: 版数（出版市場での文化的持続力の代理指標）
  - ocaid_list: Internet Archive ID（IAアクセス指標取得に使用）

Outputs:
  derived/ol_edition_counts.tsv   -- work_key, edition_count, ocaid_first, ocaid_count
  derived/ol_ocaid_list.tsv       -- work_key, ocaid（1件1行・複数版ある場合は最初のもの）

Runtime: ~30分（12GBのgzipをストリーム処理）

Usage:
  python3 scripts/build_edition_counts.py [--limit N]

--limit N: 最初のN行だけ処理（テスト用）
"""

import argparse
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT    = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "derived"
DUMP    = ROOT / "raw/ol_dump/ol_dump_editions_2026-02-28.txt.gz"

OUT_COUNTS = DERIVED / "ol_edition_counts.tsv"
OUT_OCAID  = DERIVED / "ol_ocaid_list.tsv"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if not DUMP.exists():
        print(f"[ERROR] Dump not found: {DUMP}")
        sys.exit(1)

    print(f"Loading population work_keys...")
    pop = pd.read_csv(DERIVED / "ol_dump_population_with_author.tsv", sep="\t")
    pop_keys = set(pop["work_key"].astype(str).str.strip())
    print(f"  対象work_key数: {len(pop_keys):,}")

    # work_key → edition_count, ocaid_list
    edition_counts = defaultdict(int)
    ocaid_map      = defaultdict(list)   # work_key → [ocaid, ...]

    print(f"Streaming editions dump: {DUMP}")
    n_lines = 0
    n_matched = 0

    with gzip.open(DUMP, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            n_lines += 1
            if args.limit and n_lines > args.limit:
                break
            if n_lines % 1_000_000 == 0:
                print(f"  {n_lines/1e6:.0f}M行処理済み / matched editions: {n_matched:,}", flush=True)

            parts = line.strip().split("\t")
            if len(parts) < 5:
                continue
            if parts[0] != "/type/edition":
                continue

            try:
                data = json.loads(parts[4])
            except json.JSONDecodeError:
                continue

            # work_keyを取得
            works = data.get("works", [])
            if not works:
                continue
            work_key = works[0].get("key", "")
            if not work_key or work_key not in pop_keys:
                continue

            n_matched += 1
            edition_counts[work_key] += 1

            # ocaidを取得（あれば）
            ocaid = data.get("ocaid")
            if ocaid:
                ocaid_map[work_key].append(ocaid)

    print(f"\n処理完了: {n_lines:,}行 / マッチeditions: {n_matched:,}")
    print(f"版数あり work_key数: {len(edition_counts):,}")
    print(f"ocaidあり work_key数: {len(ocaid_map):,}")

    # edition_counts TSV
    rows = []
    for wk in pop_keys:
        ec = edition_counts.get(wk, 0)
        ocaids = ocaid_map.get(wk, [])
        rows.append({
            "work_key":      wk,
            "edition_count": ec,
            "ocaid_count":   len(ocaids),
            "ocaid_first":   ocaids[0] if ocaids else "",
        })
    counts_df = pd.DataFrame(rows)
    counts_df = counts_df.sort_values("edition_count", ascending=False)
    counts_df.to_csv(OUT_COUNTS, sep="\t", index=False)
    print(f"\n→ {OUT_COUNTS}")

    # ocaid list TSV（1 work_key × 1 ocaid、複数ある場合は最初の1件）
    ocaid_rows = [
        {"work_key": wk, "ocaid": ocaids[0]}
        for wk, ocaids in ocaid_map.items()
    ]
    ocaid_df = pd.DataFrame(ocaid_rows)
    ocaid_df.to_csv(OUT_OCAID, sep="\t", index=False)
    print(f"→ {OUT_OCAID}")

    # 統計サマリー
    print(f"\n=== Edition Count 統計 ===")
    ec = counts_df["edition_count"]
    print(f"  0版:     {(ec==0).sum():,} works ({(ec==0).mean()*100:.1f}%)")
    print(f"  1版:     {(ec==1).sum():,} works")
    print(f"  2–5版:   {((ec>=2)&(ec<=5)).sum():,} works")
    print(f"  6–20版:  {((ec>=6)&(ec<=20)).sum():,} works")
    print(f"  21版以上: {(ec>20).sum():,} works")
    print(f"  中央値:  {ec.median():.1f}")
    print(f"  最大値:  {ec.max()} ({counts_df.iloc[0]['work_key']})")

    # canonicalの統計
    canon_keys = set(pop[pop["canonical"]==1]["work_key"].astype(str).str.strip())
    can_ec = counts_df[counts_df["work_key"].isin(canon_keys)]["edition_count"]
    non_ec = counts_df[~counts_df["work_key"].isin(canon_keys)]["edition_count"]
    print(f"\n  canonical中央値:     {can_ec.median():.1f}")
    print(f"  non-canonical中央値: {non_ec.median():.1f}")

    print(f"\n  Top 10 by edition_count:")
    for _, r in counts_df.head(10).iterrows():
        canon = "★" if r["work_key"] in canon_keys else " "
        print(f"    {canon} {r['edition_count']:4d}版  {r['work_key']}")

if __name__ == "__main__":
    main()