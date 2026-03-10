#!/usr/bin/env python3
"""
jstor_canonical_test_v2.py
canonical 98件を JSTOR 論文タイトルで検索（改訂版）

v1 からの変更点:
  - 著者姓 AND を「全タイトル」に必須化（v1 は短タイトルのみ）
  - title_only / title_and_author の2カウントを並列集計し比較可能にする
  - 著者姓の別名（first_name / last_name）も対応

実行方法:
    cd ~/canon-pipeline
    source .venv/bin/activate
    python scripts/jstor_canonical_test_v2.py

出力:
    derived/jstor_canonical_test_v2.tsv
    logs/jstor_canonical_test_v2_report.txt
"""

import json
import re
import csv
import sys
from pathlib import Path

# ─────────────────────────────────────────
# 設定
# ─────────────────────────────────────────
JSTOR_FILE      = Path("data/jstor_metadata_2025-07-04.jsonl")
CANONICAL_FILE  = Path("data/phd_corpus_1880_1950_cleaned.csv")
POPULATION_FILE = Path("derived/ol_dump_population_with_canonical.tsv")

OUT_TSV    = Path("derived/jstor_canonical_test_v2.tsv")
OUT_REPORT = Path("logs/jstor_canonical_test_v2_report.txt")

MAX_HITS_PER_WORK = 20

# ─────────────────────────────────────────
# 正規化
# ─────────────────────────────────────────
_LEADING_ARTICLES = re.compile(r'^(the|a|an)\s+', re.IGNORECASE)
_NON_ALNUM        = re.compile(r'[^a-z0-9\s]')
_MULTI_SPACE      = re.compile(r'\s+')

def normalize(text: str) -> str:
    if not text:
        return ""
    t = text.lower()
    t = _LEADING_ARTICLES.sub('', t)
    t = _NON_ALNUM.sub(' ', t)
    t = _MULTI_SPACE.sub(' ', t).strip()
    return t

def extract_last_name(author_str: str) -> str:
    """著者姓を正規化して返す。"姓, 名" と "名 姓" の両形式に対応。"""
    if not author_str:
        return ""
    s = author_str.strip()
    if ',' in s:
        last = s.split(',')[0].strip()
    else:
        parts = s.split()
        last = parts[-1] if parts else s
    # 記号除去・小文字化のみ（冠詞除去は不要）
    last = re.sub(r'[^a-z0-9\s]', ' ', last.lower()).strip()
    return last

# ─────────────────────────────────────────
# canonical リスト読み込み
# ─────────────────────────────────────────
def load_canonical(canonical_file: Path, population_file: Path) -> list[dict]:
    # population → work_id マップ（title_norm → work_id）
    pop_map = {}
    if population_file.exists():
        with open(population_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                if row.get('canonical') in ('1', 'True', 'true', '1.0'):
                    tnorm = normalize(row.get('title', ''))
                    pop_map[tnorm] = row.get('work_id', '')
    else:
        print(f"WARNING: {population_file} が見つかりません", file=sys.stderr)

    works = []
    with open(canonical_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            title  = row.get('Title') or row.get('title') or ''
            author = row.get('AuthorName') or row.get('author') or ''
            tnorm  = normalize(title)
            lname  = extract_last_name(author)
            works.append({
                'work_id'   : pop_map.get(tnorm, ''),
                'title'     : title,
                'author'    : author,
                'title_norm': tnorm,
                'last_name' : lname,
            })
    return works

# ─────────────────────────────────────────
# JSTOR スキャン
# ─────────────────────────────────────────
def scan_jstor(jstor_file: Path, canonical_works: list[dict]) -> dict:
    """
    各 work について以下を並列集計:
      count_title_only   : タイトルのみマッチ（著者姓不問）
      count_title_author : タイトル AND 著者姓マッチ（推奨指標）
    """
    # インデックス: title_norm → work entry
    index = {w['title_norm']: w for w in canonical_works}

    results = {
        w['title_norm']: {
            'work': w,
            'count_title_only'  : 0,
            'count_title_author': 0,
            'hits_title_only'   : [],   # サンプル（著者マッチしなかったもの）
            'hits_title_author' : [],   # サンプル（著者マッチしたもの）
        }
        for w in canonical_works
    }

    total    = 0
    articles = 0

    print(f"Scanning {jstor_file} ...", flush=True)

    with open(jstor_file, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            total += 1
            if total % 1_000_000 == 0:
                print(f"  {total:,} lines / {articles:,} articles ...", flush=True)

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

            # creators_string も著者判定に使う
            creators_raw = rec.get('creators_string') or ''
            creators_norm = normalize(creators_raw)

            for tnorm, w in index.items():
                if tnorm not in jnorm:
                    continue

                r = results[tnorm]
                hit_info = {
                    'jstor_title': jstor_raw,
                    'doi'        : rec.get('ithaka_doi', ''),
                    'date'       : rec.get('published_date', ''),
                    'creators'   : creators_raw,
                }

                # title_only カウント（常にインクリメント）
                r['count_title_only'] += 1
                if len(r['hits_title_only']) < MAX_HITS_PER_WORK:
                    r['hits_title_only'].append(hit_info)

                # title_author カウント（著者姓がタイトルか著者欄に含まれる場合）
                lname = w['last_name']
                if lname and (lname in jnorm or lname in creators_norm):
                    r['count_title_author'] += 1
                    if len(r['hits_title_author']) < MAX_HITS_PER_WORK:
                        r['hits_title_author'].append(hit_info)

    print(f"  完了: 総行数 {total:,} / article {articles:,}", flush=True)
    return results

# ─────────────────────────────────────────
# 出力
# ─────────────────────────────────────────
def write_outputs(results: dict, out_tsv: Path, out_report: Path):
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    out_report.parent.mkdir(parents=True, exist_ok=True)

    # ── TSV ──
    with open(out_tsv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow([
            'work_id', 'title', 'author', 'last_name',
            'count_title_only', 'count_title_author',
            'noise_ratio',
            'sample_title_only', 'sample_title_author'
        ])
        for tnorm, r in sorted(results.items(), key=lambda x: -x[1]['count_title_author']):
            w = r['work']
            ct = r['count_title_only']
            ca = r['count_title_author']
            ratio = f"{(ct-ca)/ct*100:.0f}%" if ct > 0 else "n/a"
            s_only   = ' ||| '.join(h['jstor_title'] for h in r['hits_title_only'][:3])
            s_author = ' ||| '.join(h['jstor_title'] for h in r['hits_title_author'][:3])
            writer.writerow([
                w['work_id'], w['title'], w['author'], w['last_name'],
                ct, ca, ratio, s_only, s_author
            ])
    print(f"TSV出力: {out_tsv}")

    # ── レポート ──
    ta_counts   = [r['count_title_author'] for r in results.values()]
    to_counts   = [r['count_title_only']   for r in results.values()]
    total_works = len(ta_counts)

    def summary(counts, label):
        zero = sum(1 for c in counts if c == 0)
        ge1  = sum(1 for c in counts if c >= 1)
        ge5  = sum(1 for c in counts if c >= 5)
        ge10 = sum(1 for c in counts if c >= 10)
        total= sum(counts)
        lines = [
            f"\n### {label}",
            f"  総マッチ件数   : {total:,}",
            f"  ゼロヒット     : {zero} 件  ({zero/total_works*100:.1f}%)",
            f"  1件以上ヒット  : {ge1} 件  ({ge1/total_works*100:.1f}%)",
            f"  5件以上ヒット  : {ge5} 件  ({ge5/total_works*100:.1f}%)",
            f"  10件以上ヒット : {ge10} 件  ({ge10/total_works*100:.1f}%)",
        ]
        return "\n".join(lines)

    lines = []
    lines.append("=" * 60)
    lines.append("JSTOR canonical テスト v2（著者姓AND対比）")
    lines.append("=" * 60)
    lines.append(f"\n対象canonical件数 : {total_works}")
    lines.append(summary(to_counts,  "タイトルのみ（v1相当）"))
    lines.append(summary(ta_counts,  "タイトル AND 著者姓（v2推奨）"))

    # ノイズ削減サマリー
    total_to = sum(to_counts)
    total_ta = sum(ta_counts)
    if total_to > 0:
        lines.append(f"\n### ノイズ削減効果")
        lines.append(f"  タイトルのみ合計   : {total_to:,}")
        lines.append(f"  著者AND合計        : {total_ta:,}")
        lines.append(f"  削減率             : {(total_to-total_ta)/total_to*100:.1f}%")

    # ランキング（title_author 順）
    lines.append("\n## マッチ数ランキング（title AND author、上位30）\n")
    top = sorted(results.items(), key=lambda x: -x[1]['count_title_author'])[:30]
    lines.append(f"  {'タイトル':<40} {'著者':<25} {'title_only':>10} {'title+auth':>10}  {'ノイズ率':>7}")
    lines.append("  " + "-" * 100)
    for tnorm, r in top:
        w  = r['work']
        ct = r['count_title_only']
        ca = r['count_title_author']
        ratio = f"{(ct-ca)/ct*100:.0f}%" if ct > 0 else "-"
        lines.append(
            f"  {w['title'][:40]:<40} {w['author'][:25]:<25} {ct:>10,} {ca:>10,}  {ratio:>7}"
        )

    # ゼロヒット（title_author）
    lines.append("\n## ゼロヒット一覧（title AND author）\n")
    zeros = [(tnorm, r) for tnorm, r in results.items() if r['count_title_author'] == 0]
    lines.append(f"  {'タイトル':<40} {'著者':<25} {'title_only':>10}")
    lines.append("  " + "-" * 80)
    for tnorm, r in sorted(zeros, key=lambda x: x[1]['work']['title']):
        w  = r['work']
        ct = r['count_title_only']
        lines.append(f"  {w['title'][:40]:<40} {w['author'][:25]:<25} {ct:>10,}")

    # サンプルヒット詳細（title_author、上位10）
    lines.append("\n## サンプルヒット詳細（title AND author、上位10作品・各3件）\n")
    for tnorm, r in top[:10]:
        w = r['work']
        lines.append(f"  ▶ {w['title']} ({w['author']}) → title_only={r['count_title_only']:,}  title+author={r['count_title_author']:,}")
        for h in r['hits_title_author'][:3]:
            lines.append(f"      - {h['jstor_title'][:80]}")
            lines.append(f"        doi: {h['doi']}  date: {h['date']}")
            if h['creators']:
                lines.append(f"        creators: {h['creators'][:60]}")

    # 疑わしいケース（title_only は多いが title_author が少ない）
    lines.append("\n## 要注意：ノイズ率が高い作品（title_only>=20 かつ title_author/title_only < 10%）\n")
    for tnorm, r in sorted(results.items(), key=lambda x: -x[1]['count_title_only']):
        ct = r['count_title_only']
        ca = r['count_title_author']
        if ct >= 20 and (ca == 0 or ca / ct < 0.10):
            w = r['work']
            ratio = f"{ca/ct*100:.1f}%" if ct > 0 else "-"
            lines.append(f"  {w['title']:<40} {w['author']:<25} title_only={ct:,}  title+auth={ca}  ratio={ratio}")

    report = "\n".join(lines)
    out_report.write_text(report, encoding='utf-8')
    print(f"レポート: {out_report}")
    print("\n" + report)

# ─────────────────────────────────────────
# エントリーポイント
# ─────────────────────────────────────────
if __name__ == '__main__':
    for p in [JSTOR_FILE, CANONICAL_FILE]:
        if not p.exists():
            sys.exit(f"ERROR: {p} が見つかりません")

    print("canonical 作品リストを読み込み中...")
    canonical_works = load_canonical(CANONICAL_FILE, POPULATION_FILE)
    print(f"  {len(canonical_works)} 件読み込み完了")
    for w in canonical_works:
        if not w['last_name']:
            print(f"  WARNING: 著者姓が取得できません → '{w['title']}' / '{w['author']}'",
                  file=sys.stderr)

    results = scan_jstor(JSTOR_FILE, canonical_works)
    write_outputs(results, OUT_TSV, OUT_REPORT)
    print("\n完了。")