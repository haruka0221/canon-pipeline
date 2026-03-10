#!/usr/bin/env python3
"""
openalex_works_test.py
canonical 98件を OpenAlex Works API の title.search で検索し、
論文言及数（count）を取得するテスト

方針:
  - filter=title.search:"作品名" 著者姓
  - title.search は論文タイトル + abstract を対象とする
  - count のみ取得（全件取得不要・meta.count だけ読む）
  - JSTOR テスト v3 と同じ正規化・著者姓マッチを使用

実行方法:
    cd ~/canon-pipeline
    source .venv/bin/activate
    python scripts/openalex_works_test.py

入力:
    data/phd_corpus_1880_1950_cleaned.csv
    derived/ol_dump_population_with_canonical.tsv

出力:
    derived/openalex_works_test.tsv
    logs/openalex_works_test_report.txt
"""

import csv
import json
import time
import re
import sys
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

# ─────────────────────────────────────────
# 設定
# ─────────────────────────────────────────
CANONICAL_FILE  = Path("data/phd_corpus_1880_1950_cleaned.csv")
POPULATION_FILE = Path("derived/ol_dump_population_with_canonical.tsv")

OUT_TSV    = Path("derived/openalex_works_test.tsv")
OUT_REPORT = Path("logs/openalex_works_test_report.txt")

EMAIL     = "tsutsui@nihu.jp"
SLEEP_SEC = 0.2   # polite pool: 10 req/sec まで

# ─────────────────────────────────────────
# 正規化（v3 と同一）
# ─────────────────────────────────────────
_LEADING_ART = re.compile(r'^(the|a|an)\s+', re.IGNORECASE)
_DROP_CHARS  = re.compile(r"['\-\u2018\u2019\u201c\u201d]")
_NON_ALNUM   = re.compile(r'[^a-z0-9\s]')
_MULTI_SPC   = re.compile(r'\s+')

def normalize(text: str) -> str:
    if not text: return ""
    t = text.lower()
    t = _LEADING_ART.sub('', t)
    t = _DROP_CHARS.sub('', t)
    t = _NON_ALNUM.sub(' ', t)
    return _MULTI_SPC.sub(' ', t).strip()

def extract_last_name(author_str: str) -> str:
    if not author_str: return ""
    s = author_str.strip()
    last = s.split(',')[0].strip() if ',' in s else (s.split() or [''])[-1]
    return normalize(last)

# ─────────────────────────────────────────
# データ読み込み
# ─────────────────────────────────────────
def load_canonical(canonical_file: Path, population_file: Path) -> list[dict]:
    """phd_corpus から canonical 作品リストを読み込む"""
    # population から work_key マップ
    pop_map = {}
    with open(population_file, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            if row.get('canonical') in ('1', 'True', 'true', '1.0'):
                tnorm = normalize(row.get('title', ''))
                pop_map[tnorm] = row.get('work_key', '')

    works = []
    with open(canonical_file, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            title  = row.get('Title') or row.get('title') or ''
            author = row.get('AuthorName') or row.get('author') or ''
            tnorm  = normalize(title)
            lname  = extract_last_name(author)
            works.append({
                'work_key'  : pop_map.get(tnorm, ''),
                'title'     : title,
                'author'    : author,
                'title_norm': tnorm,
                'last_name' : lname,
            })
    return works

# ─────────────────────────────────────────
# OpenAlex API
# ─────────────────────────────────────────
def fetch_count(title: str, last_name: str, email: str) -> tuple[int, int]:
    """
    (count_title_only, count_title_author) を返す。

    title.search:"作品名" → タイトル+abstractに作品名を含む論文数
    title.search:"作品名" 著者姓 → さらに著者姓も含む

    注意: title.search はフレーズ検索（""）と単語検索（スペース区切り）を組み合わせる
    """
    base = "https://api.openalex.org/works"

    # 作品名をそのまま使う（OpenAlex側で正規化される）
    # 冠詞除去はしない（OpenAlex は全文検索なので不要）
    title_q = f'"{title}"'  # フレーズ検索

    def query(q: str) -> int:
        params = urllib.parse.urlencode({
            'filter': f'title.search:{q}',
            'mailto': email,
            'per_page': '1',
        })
        url = f"{base}?{params}"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": f"canon-pipeline/1.0 (mailto:{email})"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            return data.get('meta', {}).get('count', 0)
        except urllib.error.HTTPError as e:
            print(f"\n  HTTP {e.code}: {url}", file=sys.stderr)
            return -1
        except Exception as e:
            print(f"\n  Error: {e}", file=sys.stderr)
            return -1

    count_title = query(title_q)
    time.sleep(SLEEP_SEC)

    if last_name:
        # タイトル + 著者姓の組み合わせ（スペースで AND 検索）
        count_author = query(f'{title_q} {last_name}')
        time.sleep(SLEEP_SEC)
    else:
        count_author = -1

    return count_title, count_author

# ─────────────────────────────────────────
# メイン
# ─────────────────────────────────────────
def run(works: list[dict]) -> list[dict]:
    results = []
    N = len(works)
    print(f"\nOpenAlex Works API を {N} 件クエリ中...\n")

    for i, w in enumerate(works, 1):
        print(
            f"  [{i:3}/{N}] {w['title'][:40]:<40} "
            f"({w['last_name'] or '?'})",
            end=' ... ', flush=True
        )

        ct, ca = fetch_count(w['title'], w['last_name'], EMAIL)

        noise = f"{(ct-ca)/ct*100:.0f}%" if ct > 0 and ca >= 0 else "-"
        print(f"title={ct:>5,}  title+author={ca:>5,}  noise={noise}")

        results.append({
            'work_key'          : w['work_key'],
            'title'             : w['title'],
            'author'            : w['author'],
            'last_name'         : w['last_name'],
            'oa_count_title'    : ct,
            'oa_count_author'   : ca,
        })

    return results

# ─────────────────────────────────────────
# 出力
# ─────────────────────────────────────────
def write_outputs(results: list[dict], out_tsv: Path, out_report: Path):
    out_tsv.parent.mkdir(parents=True, exist_ok=True)

    with open(out_tsv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, delimiter='\t', fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(sorted(results, key=lambda x: -x['oa_count_author']))
    print(f"\nTSV: {out_tsv}")

    # レポート
    counts_ta = [r['oa_count_author'] for r in results if r['oa_count_author'] >= 0]
    counts_to = [r['oa_count_title']  for r in results if r['oa_count_title']  >= 0]
    N = len(results)

    def stats(counts, label):
        if not counts: return f"{label}: データなし"
        z  = sum(1 for c in counts if c == 0)
        g1 = sum(1 for c in counts if c >= 1)
        g5 = sum(1 for c in counts if c >= 5)
        g10= sum(1 for c in counts if c >= 10)
        return (
            f"\n### {label}\n"
            f"  総カウント  : {sum(counts):,}\n"
            f"  ゼロ        : {z} 件 ({z/N*100:.1f}%)\n"
            f"  1件以上     : {g1} 件 ({g1/N*100:.1f}%)\n"
            f"  5件以上     : {g5} 件 ({g5/N*100:.1f}%)\n"
            f"  10件以上    : {g10} 件 ({g10/N*100:.1f}%)\n"
            f"  中央値      : {sorted(counts)[len(counts)//2]}\n"
            f"  最大値      : {max(counts)}"
        )

    lines = [
        "=" * 60,
        "OpenAlex Works title.search テスト結果（canonical 142件）",
        "=" * 60,
        stats(counts_to, "title のみ（参考）"),
        stats(counts_ta, "title AND 著者姓（推奨）"),
    ]

    lines.append("\n## ランキング（title AND author 降順）\n")
    lines.append(f"  {'タイトル':<42} {'著者':<22} {'title':>7} {'t+auth':>7}  {'noise':>6}")
    lines.append("  " + "-" * 90)
    for r in sorted(results, key=lambda x: -x['oa_count_author']):
        ct = r['oa_count_title']
        ca = r['oa_count_author']
        noise = f"{(ct-ca)/ct*100:.0f}%" if ct > 0 and ca >= 0 else "-"
        lines.append(
            f"  {r['title'][:42]:<42} {r['author'][:22]:<22} "
            f"{ct:>7,} {ca:>7,}  {noise:>6}"
        )

    lines.append("\n## ゼロヒット（title AND author = 0）\n")
    for r in sorted(results, key=lambda x: x['title']):
        if r['oa_count_author'] == 0:
            lines.append(f"  {r['title']:<42} {r['author']:<22}  title={r['oa_count_title']}")

    report = "\n".join(lines)
    out_report.write_text(report, encoding='utf-8')
    print(f"レポート: {out_report}")
    print("\n" + report)

# ─────────────────────────────────────────
# エントリーポイント
# ─────────────────────────────────────────
if __name__ == '__main__':
    for p in [CANONICAL_FILE, POPULATION_FILE]:
        if not p.exists():
            sys.exit(f"ERROR: {p} が見つかりません")

    works   = load_canonical(CANONICAL_FILE, POPULATION_FILE)
    print(f"canonical: {len(works)} 件読み込み完了")

    results = run(works)
    write_outputs(results, OUT_TSV, OUT_REPORT)
    print("\n完了。")