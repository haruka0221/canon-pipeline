"""
全4,833 works の editions から OCLC 番号を一括取得する。
- OL Editions API: https://openlibrary.org/works/{work_key}/editions.json?limit=50
- 1件ずつ取得、0.5秒インターバル
- 既取得分はスキップ（再開可能）
- 出力: derived/ol_dump_oclc_all.tsv（work_id, oclc）
"""
import requests, time, json, os, csv
from pathlib import Path

POPULATION = 'derived/ol_dump_population_fiction_2026-02-28.tsv'
OUT_FILE   = 'derived/ol_dump_oclc_all.tsv'
RAW_DIR    = Path('raw/editions_oclc')
RAW_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {'User-Agent': 'HarukaResearch (tsutsui@nihu.jp)'}

def extract_oclc(entries):
    oclcs = set()
    for e in entries:
        for v in e.get('oclc_numbers', []):
            oclcs.add(str(v).strip())
        if 'oclc_number' in e:
            v = e['oclc_number']
            if isinstance(v, list):
                oclcs.update(str(x).strip() for x in v)
            else:
                oclcs.add(str(v).strip())
    return oclcs

# 進捗読み込み（再開用）
done = set()
if os.path.exists(OUT_FILE):
    with open(OUT_FILE) as f:
        for row in csv.reader(f, delimiter='\t'):
            if row:
                done.add(row[0])
print(f"既取得済み: {len(done)} works")

# 母集団読み込み
works = []
with open(POPULATION) as f:
    next(f)  # header
    for line in f:
        wid = line.split('\t')[0].strip().lstrip('/works/')
        if not wid.startswith('OL'):
            wid = line.split('\t')[0].strip().split('/')[-1]
        works.append(wid)
print(f"総 works 数: {len(works)}")

# 取得ループ
with open(OUT_FILE, 'a', newline='') as out:
    writer = csv.writer(out, delimiter='\t')
    for i, wid in enumerate(works):
        if wid in done:
            continue
        raw_path = RAW_DIR / f"{wid}.json"
        # キャッシュがあれば再利用
        if raw_path.exists():
            data = json.loads(raw_path.read_text())
        else:
            url = f"https://openlibrary.org/works/{wid}/editions.json?limit=50"
            try:
                r = requests.get(url, headers=HEADERS, timeout=15)
                if r.status_code != 200:
                    print(f"  SKIP {wid}: HTTP {r.status_code}")
                    writer.writerow([wid, ''])
                    continue
                data = r.json()
                raw_path.write_text(json.dumps(data))
            except Exception as ex:
                print(f"  ERROR {wid}: {ex}")
                continue
            time.sleep(0.5)

        oclcs = extract_oclc(data.get('entries', []))
        if oclcs:
            for oc in oclcs:
                writer.writerow([wid, oc])
        else:
            writer.writerow([wid, ''])
        done.add(wid)

        if (i+1) % 100 == 0:
            print(f"  {i+1}/{len(works)} 完了")

print("完了")
