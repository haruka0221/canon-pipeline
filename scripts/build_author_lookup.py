#!/usr/bin/env python3
"""
build_author_lookup.py
OL Authors ダンプから author_key → name の変換テーブルを作成し、
population ファイルに著者名列を追加する

実行方法:
    cd ~/canon-pipeline
    source .venv/bin/activate
    python scripts/build_author_lookup.py

入力:
    raw/ol_dump/ol_dump_authors_2026-02-28.txt.gz  （Authorsダンプ）
    derived/ol_dump_population_with_canonical.tsv  （母集団）

出力:
    derived/ol_author_lookup.tsv          （author_key → name・中間ファイル）
    derived/ol_dump_population_with_author.tsv  （著者名列追加済み母集団）
"""

import gzip
import json
import csv
import sys
import re
from pathlib import Path

# ─────────────────────────────────────────
# 設定
# ─────────────────────────────────────────
# ダンプの日付は実際のファイル名に合わせて変更してください
AUTHORS_DUMP    = Path("raw/ol_dump/ol_dump_authors_2026-02-28.txt.gz")
POPULATION_FILE = Path("derived/ol_dump_population_with_canonical.tsv")

OUT_LOOKUP     = Path("derived/ol_author_lookup.tsv")
OUT_POPULATION = Path("derived/ol_dump_population_with_author.tsv")

# ─────────────────────────────────────────
# Step 1: Authorsダンプ → author_key: name テーブル
# ─────────────────────────────────────────
def build_lookup(authors_dump: Path, out_lookup: Path) -> dict:
    """
    Authorsダンプをストリーム処理し、
    /authors/OL123A → "Fitzgerald, F. Scott" の辞書を作る。

    OL Authorレコードの名前フィールド優先順:
      1. personal_name  （最も多い・"姓, 名" 形式）
      2. name           （フォールバック）
      3. fuller_name    （さらなるフォールバック）
    """
    print(f"Authorsダンプを処理中: {authors_dump}", flush=True)
    lookup = {}
    total  = 0
    no_name = 0

    with gzip.open(authors_dump, 'rt', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            if total % 1_000_000 == 0:
                print(f"  {total:,} records ...", flush=True)

            parts = line.split('\t')
            if len(parts) < 5:
                continue
            author_key = parts[1]  # /authors/OL123A

            try:
                rec = json.loads(parts[4])
            except json.JSONDecodeError:
                continue

            name = (
                rec.get('personal_name') or
                rec.get('name') or
                rec.get('fuller_name') or
                ''
            )
            if name:
                lookup[author_key] = name.strip()
            else:
                no_name += 1

    print(f"  完了: {total:,} authors / 名前あり: {len(lookup):,} / 名前なし: {no_name:,}")

    # 中間ファイルに保存
    out_lookup.parent.mkdir(parents=True, exist_ok=True)
    with open(out_lookup, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['author_key', 'author_name'])
        for k, v in sorted(lookup.items()):
            writer.writerow([k, v])
    print(f"  ルックアップテーブル: {out_lookup}  ({len(lookup):,} rows)")

    return lookup

# ─────────────────────────────────────────
# Step 2: 母集団に著者名列を追加
# ─────────────────────────────────────────
def enrich_population(population_file: Path, lookup: dict, out_population: Path):
    """
    population の author_keys 列（複数の場合は"|"区切りを想定）を
    lookup で名前に変換し、author_name 列として追加する。
    """
    print(f"\n母集団に著者名を付与中: {population_file}", flush=True)
    total  = 0
    hit    = 0
    miss   = 0
    multi  = 0  # 複数著者

    out_population.parent.mkdir(parents=True, exist_ok=True)

    with open(population_file, 'r', encoding='utf-8') as fin, \
         open(out_population, 'w', encoding='utf-8', newline='') as fout:

        reader = csv.DictReader(fin, delimiter='\t')
        fieldnames = (reader.fieldnames or []) + ['author_name']
        writer = csv.DictWriter(fout, fieldnames=fieldnames, delimiter='\t',
                                extrasaction='ignore')
        writer.writeheader()

        for row in reader:
            total += 1
            raw_keys = row.get('author_keys', '') or ''

            # "|" 区切りで複数著者に対応
            keys = [k.strip() for k in re.split(r'[|;,]', raw_keys) if k.strip()]

            names = []
            for k in keys:
                n = lookup.get(k, '')
                if n:
                    names.append(n)

            if len(keys) > 1:
                multi += 1

            author_name = names[0] if names else ''  # 筆頭著者のみ使用
            if author_name:
                hit += 1
            else:
                miss += 1

            row['author_name'] = author_name
            writer.writerow(row)

    print(f"  完了: {total:,} works")
    print(f"  著者名あり: {hit:,} ({hit/total*100:.1f}%)")
    print(f"  著者名なし: {miss:,} ({miss/total*100:.1f}%)")
    print(f"  複数著者  : {multi:,} ({multi/total*100:.1f}%)（筆頭著者を使用）")
    print(f"  出力: {out_population}")

# ─────────────────────────────────────────
# 動作確認：canonical 数件をサンプル表示
# ─────────────────────────────────────────
def show_canonical_sample(out_population: Path, n: int = 10):
    print(f"\n=== canonical サンプル {n}件（著者名確認） ===")
    shown = 0
    with open(out_population, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            if row.get('canonical') in ('1', 'True', 'true', '1.0'):
                print(f"  {row['title']:<40}  {row.get('author_name', ''):<30}  {row.get('work_key','')}")
                shown += 1
                if shown >= n:
                    break

# ─────────────────────────────────────────
# エントリーポイント
# ─────────────────────────────────────────
if __name__ == '__main__':
    # ファイル名を自動検索（日付違いに対応）
    if not AUTHORS_DUMP.exists():
        candidates = sorted(Path("raw/ol_dump").glob("ol_dump_authors_*.txt.gz"))
        if candidates:
            authors_dump = candidates[-1]  # 最新版を使用
            print(f"Authorsダンプを自動検出: {authors_dump}")
        else:
            sys.exit(
                f"ERROR: Authorsダンプが見つかりません。\n"
                f"以下でダウンロードしてください:\n"
                f"  wget -P raw/ol_dump/ "
                f"https://archive.org/download/ol_dump_2026-02-28/ol_dump_authors_2026-02-28.txt.gz"
            )
    else:
        authors_dump = AUTHORS_DUMP

    if not POPULATION_FILE.exists():
        sys.exit(f"ERROR: {POPULATION_FILE} が見つかりません")

    lookup = build_lookup(authors_dump, OUT_LOOKUP)
    enrich_population(POPULATION_FILE, lookup, OUT_POPULATION)
    show_canonical_sample(OUT_POPULATION)
    print("\n完了。次は jstor_mentions_all.py の POPULATION_FILE を")
    print(f"  '{OUT_POPULATION}' に変更して再実行してください。")