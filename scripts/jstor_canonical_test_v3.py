#!/usr/bin/env python3
"""
jstor_canonical_test_v3.py
canonical 98件 JSTOR 検索 - 第3版

v2 からの変更点:
  1. 正規化バグ修正:
       アポストロフィ・ハイフン等を「スペースに置換」→「削除」に変更
       例: "Howard's End" → "howards end"（v2: "howard s end"）
           "D'Urbervilles" → "durbervilles"（v2: "d urbervilles"）
  2. 著者姓マッチングを creators_string 優先に変更:
       v2: lname in jstor_title_norm OR lname in creators_norm
       v3: creators_norm を優先チェック → なければ jstor_title_norm にフォールバック
       → creators_string の充填率は 77.5% なので、未充填時はタイトルフォールバックで補う
  3. match_source 列を追加（"title_only" / "title+creators" / "title+jtitle"）
       → マッチがどちらの経路で拾われたか可視化

実行方法:
    cd ~/canon-pipeline
    source .venv/bin/activate
    python scripts/jstor_canonical_test_v3.py

出力:
    derived/jstor_canonical_test_v3.tsv
    logs/jstor_canonical_test_v3_report.txt
"""

import json
import re
import csv
import sys
from pathlib import Path
from collections import Counter

# ─────────────────────────────────────────
# 設定
# ─────────────────────────────────────────
JSTOR_FILE      = Path("data/jstor_metadata_2025-07-04.jsonl")
CANONICAL_FILE  = Path("data/phd_corpus_1880_1950_cleaned.csv")
POPULATION_FILE = Path("derived/ol_dump_population_with_canonical.tsv")

OUT_TSV    = Path("derived/jstor_canonical_test_v3.tsv")
OUT_REPORT = Path("logs/jstor_canonical_test_v3_report.txt")

MAX_HITS = 20  # work_id ごとのサンプル保存上限

# ─────────────────────────────────────────
# 正規化（v3: アポストロフィ等は削除、スペースに置換しない）
# ─────────────────────────────────────────
_LEADING_ART = re.compile(r'^(the|a|an)\s+', re.IGNORECASE)
_DROP_CHARS  = re.compile(r"['\-\u2018\u2019\u201c\u201d]")   # アポストロフィ・ハイフン → 削除
_NON_ALNUM   = re.compile(r'[^a-z0-9\s]')                     # その他記号 → スペース
_MULTI_SPC   = re.compile(r'\s+')

def normalize(text: str) -> str:
    """
    小文字化 → 先頭冠詞除去 → アポストロフィ等削除 → 残り記号をスペース → 空白正規化
    """
    if not text:
        return ""
    t = text.lower()
    t = _LEADING_ART.sub('', t)
    t = _DROP_CHARS.sub('', t)       # ← v3変更点: 削除（スペース置換ではない）
    t = _NON_ALNUM.sub(' ', t)
    t = _MULTI_SPC.sub(' ', t).strip()
    return t

def extract_last_name(author_str: str) -> str:
    """著者姓を正規化して返す（"姓, 名" / "名 姓" 両対応）"""
    if not author_str:
        return ""
    s = author_str.strip()
    last = s.split(',')[0].strip() if ',' in s else s.split()[-1]
    return normalize(last)

# ─────────────────────────────────────────
# canonical リスト読み込み
# ─────────────────────────────────────────
def load_canonical(canonical_file: Path, population_file: Path) -> list[dict]:
    pop_map = {}
    if population_file.exists():
        with open(population_file, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f, delimiter='\t'):
                if row.get('canonical') in ('1', 'True', 'true', '1.0'):
                    pop_map[normalize(row.get('title', ''))] = row.get('work_id', '')

    works = []
    with open(canonical_file, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
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
def scan_jstor(jstor_file: Path, works: list[dict]) -> dict:
    """
    集計カラム:
      count_title_only    : タイトルのみ（参考値）
      count_title_author  : タイトル AND 著者姓（推奨指標）
        match_via_creators  うち creators_string 経由
        match_via_jtitle    うち 論文タイトル経由（creators が空の場合のフォールバック）
    """
    index = {w['title_norm']: w for w in works}

    results = {
        tnorm: {
            'work'              : w,
            'count_title_only'  : 0,
            'count_title_author': 0,
            'match_via_creators': 0,
            'match_via_jtitle'  : 0,
            'hits'              : [],
        }
        for tnorm, w in index.items()
    }

    total = articles = 0
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

            creators_raw  = rec.get('creators_string') or ''
            creators_norm = normalize(creators_raw)

            for tnorm, w in index.items():
                if tnorm not in jnorm:
                    continue

                r     = results[tnorm]
                lname = w['last_name']

                # title_only
                r['count_title_only'] += 1

                # title_author（creators_string 優先 → 論文タイトルフォールバック）
                matched_author = False
                via            = None

                if lname:
                    if creators_norm and lname in creators_norm:
                        matched_author = True
                        via = 'creators'
                    elif lname in jnorm:
                        matched_author = True
                        via = 'jtitle'

                if matched_author:
                    r['count_title_author'] += 1
                    r[f'match_via_{via}'] += 1
                    if len(r['hits']) < MAX_HITS:
                        r['hits'].append({
                            'jstor_title': jstor_raw,
                            'doi'        : rec.get('ithaka_doi', ''),
                            'date'       : rec.get('published_date', ''),
                            'creators'   : creators_raw,
                            'via'        : via,
                        })

    print(f"  完了: 総行数 {total:,} / article {articles:,}", flush=True)
    return results

# ─────────────────────────────────────────
# 出力
# ─────────────────────────────────────────
def write_outputs(results: dict, out_tsv: Path, out_report: Path):
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    out_report.parent.mkdir(parents=True, exist_ok=True)

    # TSV
    with open(out_tsv, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter='\t')
        w.writerow([
            'work_id', 'title', 'author', 'last_name',
            'count_title_only', 'count_title_author',
            'via_creators', 'via_jtitle',
            'noise_ratio', 'sample_hits'
        ])
        for tnorm, r in sorted(results.items(), key=lambda x: -x[1]['count_title_author']):
            wk = r['work']
            ct = r['count_title_only']
            ca = r['count_title_author']
            nr = f"{(ct-ca)/ct*100:.0f}%" if ct > 0 else "n/a"
            samples = ' ||| '.join(
                f"{h['jstor_title'][:60]} [{h['via']}]" for h in r['hits'][:3]
            )
            w.writerow([
                wk['work_id'], wk['title'], wk['author'], wk['last_name'],
                ct, ca, r['match_via_creators'], r['match_via_jtitle'],
                nr, samples
            ])
    print(f"TSV: {out_tsv}")

    # レポート
    ta = [r['count_title_author'] for r in results.values()]
    to = [r['count_title_only']   for r in results.values()]
    N  = len(ta)

    def stats(counts, label):
        z   = sum(1 for c in counts if c == 0)
        g1  = sum(1 for c in counts if c >= 1)
        g5  = sum(1 for c in counts if c >= 5)
        g10 = sum(1 for c in counts if c >= 10)
        tot = sum(counts)
        return (
            f"\n### {label}\n"
            f"  総マッチ    : {tot:,}\n"
            f"  ゼロヒット  : {z} 件 ({z/N*100:.1f}%)\n"
            f"  1件以上     : {g1} 件 ({g1/N*100:.1f}%)\n"
            f"  5件以上     : {g5} 件 ({g5/N*100:.1f}%)\n"
            f"  10件以上    : {g10} 件 ({g10/N*100:.1f}%)"
        )

    lines = [
        "=" * 60,
        "JSTOR canonical テスト v3",
        "  正規化修正（apostrophe削除）+ creators_string優先マッチ",
        "=" * 60,
        f"\n対象件数: {N}",
        stats(to, "タイトルのみ（参考）"),
        stats(ta, "タイトル AND 著者姓（推奨）"),
    ]

    # v2比較
    lines += [
        "\n### v2 → v3 変化（特に Howard's End・D'Urbervilles 等）",
        "  ※ v2 の数字を貼って手動比較してください",
    ]

    # ランキング
    top = sorted(results.items(), key=lambda x: -x[1]['count_title_author'])
    lines.append(f"\n## ランキング（title AND author、全件）\n")
    lines.append(f"  {'タイトル':<42} {'著者':<22} {'to':>7} {'ta':>7}  {'noise':>6}  via_cr  via_jt")
    lines.append("  " + "-" * 105)
    for tnorm, r in top:
        wk = r['work']
        ct = r['count_title_only']
        ca = r['count_title_author']
        nr = f"{(ct-ca)/ct*100:.0f}%" if ct > 0 else "-"
        lines.append(
            f"  {wk['title'][:42]:<42} {wk['author'][:22]:<22} "
            f"{ct:>7,} {ca:>7,}  {nr:>6}  "
            f"{r['match_via_creators']:>6}  {r['match_via_jtitle']:>6}"
        )

    # ゼロヒット
    zeros = [(tnorm, r) for tnorm, r in results.items() if r['count_title_author'] == 0]
    lines.append(f"\n## ゼロヒット（title AND author = 0）  {len(zeros)} 件\n")
    lines.append(f"  {'タイトル':<42} {'著者':<22} {'title_norm':<35} {'to':>7}")
    lines.append("  " + "-" * 110)
    for tnorm, r in sorted(zeros, key=lambda x: x[1]['work']['title']):
        wk = r['work']
        lines.append(
            f"  {wk['title'][:42]:<42} {wk['author'][:22]:<22} "
            f"{wk['title_norm'][:35]:<35} {r['count_title_only']:>7,}"
        )

    # サンプルヒット（上位15）
    lines.append("\n## サンプルヒット詳細（上位15作品・各3件）\n")
    for tnorm, r in top[:15]:
        wk = r['work']
        lines.append(
            f"  ▶ {wk['title']} ({wk['author']})  "
            f"to={r['count_title_only']:,}  ta={r['count_title_author']:,}  "
            f"via_cr={r['match_via_creators']}  via_jt={r['match_via_jtitle']}"
        )
        for h in r['hits'][:3]:
            lines.append(f"      [{h['via']:8}] {h['jstor_title'][:75]}")
            lines.append(f"                  doi:{h['doi']}  date:{h['date']}")
            if h['creators']:
                lines.append(f"                  creators: {h['creators'][:60]}")

    # 要注意（ノイズ高）
    lines.append("\n## 要注意：ノイズ率高（title_only>=20 かつ ta/to < 10%）\n")
    for tnorm, r in sorted(results.items(), key=lambda x: -x[1]['count_title_only']):
        ct = r['count_title_only']
        ca = r['count_title_author']
        if ct >= 20 and (ca == 0 or ca/ct < 0.10):
            wk = r['work']
            lines.append(
                f"  {wk['title']:<42} to={ct:,}  ta={ca}  "
                f"norm='{wk['title_norm']}'"
            )

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

    # 正規化の動作確認
    print("=== 正規化テスト ===")
    test_cases = [
        ("Howard's End",          "howards end"),
        ("Tess of the D'Urbervilles", "tess of durbervilles"),
        ("A Portrait of the Artist as a Young Man", "portrait of artist as young man"),
        ("Nineteen Eighty-Four",  "nineteen eightyfour"),
        ("The Great Gatsby",      "great gatsby"),
    ]
    all_ok = True
    for raw, expected in test_cases:
        got = normalize(raw)
        ok  = "✓" if got == expected else "✗"
        if got != expected:
            all_ok = False
        print(f"  {ok} '{raw}' → '{got}'  (expected: '{expected}')")
    if not all_ok:
        print("\nWARNING: 正規化に予期しない結果があります。スクリプトを確認してください。")
    print()

    print("canonical リストを読み込み中...")
    works = load_canonical(CANONICAL_FILE, POPULATION_FILE)
    print(f"  {len(works)} 件")
    no_lname = [w for w in works if not w['last_name']]
    if no_lname:
        print(f"  WARNING: 著者姓が取得できない: {[w['title'] for w in no_lname]}")

    results = scan_jstor(JSTOR_FILE, works)
    write_outputs(results, OUT_TSV, OUT_REPORT)
    print("\n完了。")