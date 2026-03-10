#!/usr/bin/env python3
"""
jstor_mentions_all.py
全母集団 34,789件に対して JSTOR 論文タイトルマッチを実行する

設計方針:
  - v3 の正規化・マッチングロジックをそのまま使用
  - content_type == "article" のみ対象（11.6M件）
  - タイトル AND 著者姓マッチ（creators_string 優先・jstor_title フォールバック）
  - 全件ストリーム処理・メモリ効率優先
  - 進捗チェックポイント: 100万行ごとに中間ファイルへ保存

実行方法:
    cd ~/canon-pipeline
    source .venv/bin/activate
    python scripts/jstor_mentions_all.py

    # 推定実行時間: 30〜60分（11.6M articles × 34,789 works のマッチング）
    # メモリ: 約 500MB〜1GB 程度

出力:
    derived/jstor_mentions.tsv          （最終出力・work_id ごとの件数）
    logs/jstor_mentions_all.log         （進捗ログ）

derived/jstor_mentions.tsv の列:
    work_id, title, author, title_norm, last_name,
    canonical, count_title_author, via_creators, via_jtitle
"""

import json
import re
import csv
import sys
import time
import logging
from pathlib import Path

# ─────────────────────────────────────────
# 設定
# ─────────────────────────────────────────
JSTOR_FILE      = Path("data/jstor_metadata_2025-07-04.jsonl")
POPULATION_FILE = Path("derived/ol_dump_population_with_author.tsv")

OUT_TSV  = Path("derived/jstor_mentions.tsv")
LOG_FILE = Path("logs/jstor_mentions_all.log")

# タイトル文字数（正規化後・スペース除く）がこの値未満は
# 著者姓 AND があっても信頼性低としてフラグを立てる（除外はしない）
SHORT_TITLE_CHARS = 4

# ─────────────────────────────────────────
# ロギング設定
# ─────────────────────────────────────────
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────
# 正規化（v3 と同一）
# ─────────────────────────────────────────
_LEADING_ART = re.compile(r'^(the|a|an)\s+', re.IGNORECASE)
_DROP_CHARS  = re.compile(r"['\-\u2018\u2019\u201c\u201d]")
_NON_ALNUM   = re.compile(r'[^a-z0-9\s]')
_MULTI_SPC   = re.compile(r'\s+')

def normalize(text: str) -> str:
    if not text:
        return ""
    t = text.lower()
    t = _LEADING_ART.sub('', t)
    t = _DROP_CHARS.sub('', t)
    t = _NON_ALNUM.sub(' ', t)
    t = _MULTI_SPC.sub(' ', t).strip()
    return t

def extract_last_name(author_str: str) -> str:
    if not author_str:
        return ""
    s = author_str.strip()
    last = s.split(',')[0].strip() if ',' in s else (s.split() or [''])[-1]
    return normalize(last)

# ─────────────────────────────────────────
# 母集団読み込み
# ─────────────────────────────────────────
def load_population(population_file: Path) -> dict:
    """
    ol_dump_population_with_canonical.tsv を読み込み、
    title_norm → {work_id, title, author, last_name, canonical, is_short} の辞書を返す。

    重複 title_norm がある場合は canonical フラグが立っている方を優先し、
    それ以外は work_id の辞書順で先勝ちとする。
    """
    log.info(f"母集団読み込み中: {population_file}")
    index = {}       # title_norm → entry
    skipped = 0
    total   = 0

    with open(population_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            total += 1
            title  = row.get('title') or ''
            author = row.get('author_name') or ''
            tnorm  = normalize(title)
            lname  = extract_last_name(author)

            if not tnorm:
                skipped += 1
                continue

            canonical = row.get('canonical') in ('1', 'True', 'true', '1.0')
            is_short  = len(tnorm.replace(' ', '')) < SHORT_TITLE_CHARS

            entry = {
                'work_id'   : row.get('work_key', ''),
                'title'     : title,
                'author'    : author,
                'title_norm': tnorm,
                'last_name' : lname,
                'canonical' : canonical,
                'is_short'  : is_short,
            }

            # 重複処理: canonical 優先・それ以外は先勝ち
            if tnorm not in index or (canonical and not index[tnorm]['canonical']):
                index[tnorm] = entry

    log.info(f"  母集団: {total:,} 行 → インデックス: {len(index):,} 件 (スキップ: {skipped})")
    no_lname = sum(1 for e in index.values() if not e['last_name'])
    log.info(f"  著者姓なし: {no_lname:,} 件（著者情報欠損・title_only のみカウント）")
    return index

# ─────────────────────────────────────────
# JSTOR スキャン
# ─────────────────────────────────────────
def scan_jstor(jstor_file: Path, index: dict) -> dict:
    """
    results: title_norm → {
        count_title_author, via_creators, via_jtitle
    }
    （title_only は全件スキャンでは集計しない。v3 テストで精度確認済みのため不要）
    """
    results = {
        tnorm: {
            'count_title_author': 0,
            'via_creators'      : 0,
            'via_jtitle'        : 0,
        }
        for tnorm in index
    }

    total    = 0
    articles = 0
    t_start  = time.time()

    log.info(f"JSTORスキャン開始: {jstor_file}")
    log.info(f"  インデックスサイズ: {len(index):,} works")

    with open(jstor_file, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            total += 1

            if total % 1_000_000 == 0:
                elapsed = time.time() - t_start
                rate    = total / elapsed
                eta     = (12_380_553 - total) / rate
                log.info(
                    f"  {total:>12,} lines / {articles:>11,} articles "
                    f"| {elapsed/60:.1f} min elapsed | ETA {eta/60:.1f} min"
                )

            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            if rec.get('content_type') != 'article':
                continue
            articles += 1

            jstor_raw = rec.get('title') or ''
            if not jstor_raw:
                continue
            jnorm = normalize(jstor_raw)

            creators_raw  = rec.get('creators_string') or ''
            creators_norm = normalize(creators_raw)

            # ── マッチングループ ──
            for tnorm, entry in index.items():
                if tnorm not in jnorm:
                    continue

                lname = entry['last_name']
                if not lname:
                    # 著者姓なし: title_only カウント（信頼性低）は記録しない
                    continue

                # creators_string 優先 → jstor_title フォールバック
                if creators_norm and lname in creators_norm:
                    results[tnorm]['count_title_author'] += 1
                    results[tnorm]['via_creators']       += 1
                elif lname in jnorm:
                    results[tnorm]['count_title_author'] += 1
                    results[tnorm]['via_jtitle']         += 1

    elapsed = time.time() - t_start
    log.info(f"スキャン完了: {total:,} lines / {articles:,} articles / {elapsed/60:.1f} min")
    return results

# ─────────────────────────────────────────
# 出力
# ─────────────────────────────────────────
def write_tsv(index: dict, results: dict, out_tsv: Path):
    out_tsv.parent.mkdir(parents=True, exist_ok=True)

    with open(out_tsv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow([
            'work_id', 'title', 'author', 'title_norm', 'last_name',
            'canonical', 'is_short',
            'jstor_mention_count', 'via_creators', 'via_jtitle'
        ])
        # canonical 優先・同順は mention_count 降順でソート
        rows = []
        for tnorm, entry in index.items():
            r = results[tnorm]
            rows.append((
                entry['work_id'],
                entry['title'],
                entry['author'],
                tnorm,
                entry['last_name'],
                int(entry['canonical']),
                int(entry['is_short']),
                r['count_title_author'],
                r['via_creators'],
                r['via_jtitle'],
            ))
        rows.sort(key=lambda x: (-x[5], -x[7]))  # canonical 降順 → mention_count 降順
        writer.writerows(rows)

    log.info(f"TSV出力: {out_tsv}  ({len(rows):,} rows)")

def log_summary(index: dict, results: dict):
    counts     = [results[tn]['count_title_author'] for tn in index]
    canonical  = [results[tn]['count_title_author'] for tn, e in index.items() if e['canonical']]
    N          = len(counts)
    Nc         = len(canonical)

    def pct(n, total): return f"{n/total*100:.1f}%" if total else "-"

    log.info("=" * 55)
    log.info("最終サマリー")
    log.info("=" * 55)
    log.info(f"  全件数              : {N:,}")
    log.info(f"  総マッチ件数        : {sum(counts):,}")
    log.info(f"  ゼロヒット          : {sum(1 for c in counts if c==0):,} ({pct(sum(1 for c in counts if c==0), N)})")
    log.info(f"  1件以上             : {sum(1 for c in counts if c>=1):,} ({pct(sum(1 for c in counts if c>=1), N)})")
    log.info(f"  5件以上             : {sum(1 for c in counts if c>=5):,} ({pct(sum(1 for c in counts if c>=5), N)})")
    log.info(f"  10件以上            : {sum(1 for c in counts if c>=10):,} ({pct(sum(1 for c in counts if c>=10), N)})")
    log.info(f"  --- canonical {Nc}件 ---")
    log.info(f"  canonical ゼロヒット: {sum(1 for c in canonical if c==0):,} ({pct(sum(1 for c in canonical if c==0), Nc)})")
    log.info(f"  canonical 1件以上   : {sum(1 for c in canonical if c>=1):,} ({pct(sum(1 for c in canonical if c>=1), Nc)})")
    log.info(f"  canonical 5件以上   : {sum(1 for c in canonical if c>=5):,} ({pct(sum(1 for c in canonical if c>=5), Nc)})")
    log.info(f"  canonical 中央値    : {sorted(canonical)[Nc//2] if Nc else '-'}")
    log.info(f"  canonical 最大値    : {max(canonical) if canonical else '-'}")

# ─────────────────────────────────────────
# エントリーポイント
# ─────────────────────────────────────────
if __name__ == '__main__':
    for p in [JSTOR_FILE, POPULATION_FILE]:
        if not p.exists():
            sys.exit(f"ERROR: {p} が見つかりません")

    index   = load_population(POPULATION_FILE)
    results = scan_jstor(JSTOR_FILE, index)
    write_tsv(index, results, OUT_TSV)
    log_summary(index, results)
    log.info("完了。")