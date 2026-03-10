#!/usr/bin/env python3
"""
openalex_concepts_test.py
canonical 98件の Wikidata QID → OpenAlex Concepts API で
論文タグ付け数（works_count）を取得するテスト

OpenAlex Concepts は Wikidata と直接マッピングされており、
小説作品の QID が Concept として登録されている場合がある。

実行方法:
    cd ~/canon-pipeline
    source .venv/bin/activate
    python scripts/openalex_concepts_test.py

入力:
    derived/wikidata_sitelinks.tsv  （work_id, qid, sitelink_count）
    derived/ol_dump_population_with_canonical.tsv  （canonical フラグ）

出力:
    derived/openalex_concepts_test.tsv
    logs/openalex_concepts_test_report.txt
"""

import csv
import json
import time
import sys
import urllib.request
import urllib.error
from pathlib import Path

# ─────────────────────────────────────────
# 設定
# ─────────────────────────────────────────
SITELINKS_FILE  = Path("derived/wikidata_sitelinks.tsv")
POPULATION_FILE = Path("derived/ol_dump_population_with_canonical.tsv")

OUT_TSV    = Path("derived/openalex_concepts_test.tsv")
OUT_REPORT = Path("logs/openalex_concepts_test_report.txt")

OPENALEX_EMAIL = "tsutsui@nihu.jp"  # ← 自分のメールアドレスに変更してください
                                        #   （polite pool 適用のため推奨）
SLEEP_SEC = 0.5   # API レート制限対策（polite pool: 10 req/sec まで）

# ─────────────────────────────────────────
# OpenAlex Concepts API
# ─────────────────────────────────────────
def fetch_concept(qid: str, email: str) -> dict | None:
    """
    Wikidata QID → OpenAlex Concept を取得。
    見つからない場合は None を返す。

    エンドポイント:
      https://api.openalex.org/concepts?filter=wikidata:Q{id}
    """
    # QID から数字部分を取得（"Q208460" → "Q208460"）
    wikidata_url = f"https://www.wikidata.org/entity/{qid}"
    url = (
        f"https://api.openalex.org/concepts"
        f"?filter=wikidata:{wikidata_url}"
        f"&mailto={email}"
    )

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": f"canon-pipeline/1.0 (mailto:{email})"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        results = data.get('results', [])
        if results:
            return results[0]  # 最初のヒットを返す
        return None

    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} for QID={qid}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  Error for QID={qid}: {e}", file=sys.stderr)
        return None

# ─────────────────────────────────────────
# データ読み込み
# ─────────────────────────────────────────
def load_canonical_qids(sitelinks_file: Path, population_file: Path) -> list[dict]:
    """canonical 98件の work_id → QID マッピングを返す"""

    # population から canonical work_key を取得
    canonical_keys = set()
    canonical_titles = {}
    with open(population_file, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            if row.get('canonical') in ('1', 'True', 'true', '1.0'):
                wk = row.get('work_key', '')
                canonical_keys.add(wk)
                canonical_titles[wk] = row.get('title', '')

    # sitelinks から QID を取得
    works = []
    with open(sitelinks_file, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            work_id = row.get('work_id', '')
            # work_id が /works/OL123W 形式か OL123W 形式か両対応
            wk = work_id if work_id.startswith('/') else f"/works/{work_id}"
            qid = row.get('qid', '')

            if wk in canonical_keys and qid and qid != 'nan':
                works.append({
                    'work_key'     : wk,
                    'title'        : canonical_titles.get(wk, ''),
                    'qid'          : qid,
                    'sitelink_count': int(float(row.get('sitelink_count', 0))),
                })

    print(f"canonical QID あり: {len(works)} 件 / canonical 全体: {len(canonical_keys)} 件")
    return works

# ─────────────────────────────────────────
# メイン処理
# ─────────────────────────────────────────
def run(works: list[dict], email: str) -> list[dict]:
    results = []
    total   = len(works)

    print(f"\nOpenAlex Concepts API を {total} 件クエリ中...")
    print(f"メールアドレス: {email}")
    print(f"インターバル: {SLEEP_SEC}秒\n")

    for i, w in enumerate(works, 1):
        qid = w['qid']
        print(f"  [{i:3}/{total}] {w['title'][:45]:<45} QID={qid}", end=' ... ', flush=True)

        concept = fetch_concept(qid, email)
        time.sleep(SLEEP_SEC)

        if concept:
            oa_id        = concept.get('id', '')
            display_name = concept.get('display_name', '')
            works_count  = concept.get('works_count', 0)
            level        = concept.get('level', '')
            print(f"✓ works_count={works_count:,}  level={level}  name='{display_name}'")
        else:
            oa_id = display_name = works_count = level = ''
            print("✗ not found")

        results.append({
            'work_key'      : w['work_key'],
            'title'         : w['title'],
            'qid'           : qid,
            'sitelink_count': w['sitelink_count'],
            'oa_concept_id' : oa_id,
            'oa_name'       : display_name,
            'oa_works_count': works_count,
            'oa_level'      : level,
        })

    return results

# ─────────────────────────────────────────
# 出力
# ─────────────────────────────────────────
def write_outputs(results: list[dict], out_tsv: Path, out_report: Path):
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    out_report.parent.mkdir(parents=True, exist_ok=True)

    with open(out_tsv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, delimiter='\t', fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"\nTSV: {out_tsv}")

    # レポート
    found  = [r for r in results if r['oa_concept_id']]
    missed = [r for r in results if not r['oa_concept_id']]
    N      = len(results)

    counts = [int(r['oa_works_count']) for r in found if r['oa_works_count'] != '']
    counts_sorted = sorted(counts, reverse=True)

    lines = [
        "=" * 60,
        "OpenAlex Concepts テスト結果（canonical works）",
        "=" * 60,
        f"\n対象: {N} 件（Wikidata QID あり canonical）",
        f"Concept 発見: {len(found)} 件 ({len(found)/N*100:.1f}%)",
        f"Concept なし: {len(missed)} 件 ({len(missed)/N*100:.1f}%)",
    ]

    if counts:
        lines += [
            f"\n--- works_count 統計（発見分のみ）---",
            f"  合計    : {sum(counts):,}",
            f"  最大値  : {max(counts):,}",
            f"  中央値  : {counts_sorted[len(counts_sorted)//2]:,}",
            f"  最小値  : {min(counts):,}",
            f"  0件     : {sum(1 for c in counts if c==0)} 件",
            f"  1件以上 : {sum(1 for c in counts if c>=1)} 件",
            f"  10件以上: {sum(1 for c in counts if c>=10)} 件",
        ]

    lines.append("\n## 発見された Concept（works_count 降順）\n")
    lines.append(f"  {'タイトル':<40} {'QID':<12} {'works_count':>11}  {'OA name'}")
    lines.append("  " + "-" * 90)
    for r in sorted(found, key=lambda x: -int(x['oa_works_count'] or 0)):
        lines.append(
            f"  {r['title'][:40]:<40} {r['qid']:<12} "
            f"{int(r['oa_works_count'] or 0):>11,}  {r['oa_name']}"
        )

    lines.append("\n## Concept が見つからなかった作品\n")
    for r in missed:
        lines.append(f"  {r['title']:<40} {r['qid']}")

    report = "\n".join(lines)
    out_report.write_text(report, encoding='utf-8')
    print(f"レポート: {out_report}")
    print("\n" + report)

# ─────────────────────────────────────────
# エントリーポイント
# ─────────────────────────────────────────
if __name__ == '__main__':
    if OPENALEX_EMAIL == "haruka@example.com":
        print("WARNING: OPENALEX_EMAIL をご自身のメールアドレスに変更してください（推奨）")

    for p in [SITELINKS_FILE, POPULATION_FILE]:
        if not p.exists():
            sys.exit(f"ERROR: {p} が見つかりません")

    works   = load_canonical_qids(SITELINKS_FILE, POPULATION_FILE)
    if not works:
        sys.exit("ERROR: canonical QID が取得できませんでした。ファイルの列名を確認してください。")

    results = run(works, OPENALEX_EMAIL)
    write_outputs(results, OUT_TSV, OUT_REPORT)
    print("\n完了。")