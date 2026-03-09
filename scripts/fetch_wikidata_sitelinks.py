"""
OL母集団全件のWikidata sitelink数・QIDを取得する
- P648（OL Work ID）でWikidataとリンク
- 50件ずつバッチSPARQL
- 既取得分はスキップ（再開可能）
- 出力: derived/wikidata_sitelinks.tsv（work_id, qid, sitelink_count）
"""
import pandas as pd, requests, time, csv, os
from pathlib import Path

POPULATION = 'derived/ol_dump_population_fiction_2026-02-28.tsv'
OUT_FILE   = 'derived/wikidata_sitelinks.tsv'
BATCH_SIZE = 50
SLEEP_SEC  = 1.0  # Wikidata推奨インターバル

SPARQL_URL = 'https://query.wikidata.org/sparql'
HEADERS    = {'User-Agent': 'HarukaResearch/1.0 (tsutsui@nihu.jp)'}

# ── 1. 母集団読み込み ─────────────────────────────────────────────
ol = pd.read_csv(POPULATION, sep='\t')
# work_key列: /works/OLxxxxxW → OLxxxxxW
if 'work_key' in ol.columns:
    ol['work_id'] = ol['work_key'].str.split('/').str[-1]
else:
    ol['work_id'] = ol.iloc[:, 0].str.split('/').str[-1]
all_ids = ol['work_id'].dropna().unique().tolist()
print(f"母集団: {len(all_ids):,} works", flush=True)

# ── 2. 既取得分スキップ ───────────────────────────────────────────
done = set()
if os.path.exists(OUT_FILE):
    with open(OUT_FILE) as f:
        for row in csv.reader(f, delimiter='\t'):
            if row:
                done.add(row[0])
print(f"既取得済み: {len(done):,} works（スキップ）", flush=True)

todo = [wid for wid in all_ids if wid not in done]
print(f"今回取得対象: {len(todo):,} works", flush=True)

# ── 3. バッチSPARQL ──────────────────────────────────────────────
def fetch_batch(wids):
    values = ' '.join(f'"{wid}"' for wid in wids)
    query = f"""
SELECT ?item ?olid (COUNT(DISTINCT ?sitelink) AS ?sitelink_count)
WHERE {{
  VALUES ?olid {{ {values} }}
  ?item wdt:P648 ?olid .
  ?sitelink schema:about ?item .
}}
GROUP BY ?item ?olid
"""
    for attempt in range(3):
        try:
            r = requests.get(SPARQL_URL,
                             params={'query': query, 'format': 'json'},
                             headers=HEADERS, timeout=30)
            if r.status_code == 429:
                print(f"  429 Too Many Requests → 60秒待機", flush=True)
                time.sleep(60)
                continue
            if r.status_code != 200:
                print(f"  HTTP {r.status_code} → スキップ", flush=True)
                return {}
            rows = r.json()['results']['bindings']
            return {
                row['olid']['value']: {
                    'qid': row['item']['value'].split('/')[-1],
                    'sitelink_count': int(row['sitelink_count']['value'])
                }
                for row in rows
            }
        except Exception as e:
            print(f"  ERROR (attempt {attempt+1}): {e}", flush=True)
            time.sleep(5)
    return {}

# ── 4. 実行・書き出し ────────────────────────────────────────────
total_hit = 0
total_miss = 0
batches = [todo[i:i+BATCH_SIZE] for i in range(0, len(todo), BATCH_SIZE)]

with open(OUT_FILE, 'a', newline='') as out:
    writer = csv.writer(out, delimiter='\t')
    # ヘッダー（新規ファイルのみ）
    if len(done) == 0:
        writer.writerow(['work_id', 'qid', 'sitelink_count'])

    for b_idx, batch in enumerate(batches):
        results = fetch_batch(batch)

        for wid in batch:
            if wid in results:
                r = results[wid]
                writer.writerow([wid, r['qid'], r['sitelink_count']])
                total_hit += 1
            else:
                writer.writerow([wid, '', 0])
                total_miss += 1

        if (b_idx + 1) % 20 == 0:
            pct = (b_idx + 1) / len(batches) * 100
            print(f"  {b_idx+1}/{len(batches)} バッチ完了 ({pct:.1f}%) "
                  f"ヒット={total_hit} ミス={total_miss}", flush=True)

        time.sleep(SLEEP_SEC)

print(f"\n完了: ヒット={total_hit:,} / ミス={total_miss:,}", flush=True)
print(f"ヒット率: {total_hit/(total_hit+total_miss)*100:.1f}%", flush=True)
print(f"→ {OUT_FILE}", flush=True)