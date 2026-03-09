"""
Editionsダンプから直接OCLC番号を取得する（API版の代替）
- 入力: raw/ol_dump/ol_dump_editions_2026-02-28.txt.gz
- 母集団: derived/ol_dump_population_fiction_2026-02-28.tsv（34,789件）
- 出力: derived/ol_dump_oclc_all.tsv（work_id, oclc）
- 既取得分はスキップ（API版との併用・再開可能）
- 所要時間目安: 30〜60分
"""
import gzip, json, csv, os, sys
from pathlib import Path

DUMP      = 'raw/ol_dump/ol_dump_editions_2026-02-28.txt.gz'
POPULATION = 'derived/ol_dump_population_fiction_2026-02-28.tsv'
OUT_FILE  = 'derived/ol_dump_oclc_all.tsv'

# ── 1. 母集団 work_key をセットに読み込む ──────────────────────────
population = set()
with open(POPULATION) as f:
    next(f)  # header
    for line in f:
        wid = line.split('\t')[0].strip()
        # /works/OLxxxxxW 形式と OLxxxxxW 形式の両方に対応
        if wid.startswith('/works/'):
            wid = wid[7:]
        population.add(wid)
print(f"母集団: {len(population):,} works", flush=True)

# ── 2. 既取得 work_id を読み込む（再開用）────────────────────────
done = set()
if os.path.exists(OUT_FILE):
    with open(OUT_FILE) as f:
        for row in csv.reader(f, delimiter='\t'):
            if row:
                done.add(row[0])
print(f"既取得済み: {len(done):,} works（スキップ）", flush=True)

todo = population - done
print(f"今回取得対象: {len(todo):,} works", flush=True)

# ── 3. Editionsダンプをストリーム処理 ────────────────────────────
# 結果を一旦メモリに集約してから書き出す（work単位で集約）
results = {}  # work_id -> set of oclc

processed_lines = 0
matched_editions = 0

print("ダンプ処理開始...", flush=True)

with gzip.open(DUMP, 'rt', encoding='utf-8', errors='replace') as gz:
    for line in gz:
        processed_lines += 1
        if processed_lines % 1_000_000 == 0:
            print(f"  {processed_lines/1_000_000:.0f}M行処理済み / マッチ {matched_editions:,} editions / 取得 {len(results):,} works",
                  flush=True)

        # タブ区切り5列: type / key / revision / last_modified / JSON
        parts = line.split('\t', 4)
        if len(parts) < 5:
            continue
        if parts[0] != '/type/edition':
            continue

        try:
            rec = json.loads(parts[4])
        except json.JSONDecodeError:
            continue

        # work_key を取得
        works_field = rec.get('works', [])
        if not works_field:
            continue
        work_ref = works_field[0].get('key', '')
        if work_ref.startswith('/works/'):
            wid = work_ref[7:]
        else:
            wid = work_ref

        if wid not in todo:
            continue

        matched_editions += 1

        # OCLC番号を抽出
        oclcs = set()
        for v in rec.get('oclc_numbers', []):
            oclcs.add(str(v).strip())
        ocn = rec.get('oclc_number', None)
        if ocn:
            if isinstance(ocn, list):
                oclcs.update(str(x).strip() for x in ocn)
            else:
                oclcs.add(str(ocn).strip())

        if wid not in results:
            results[wid] = set()
        results[wid].update(oclcs)

print(f"\nダンプ処理完了: {processed_lines/1_000_000:.1f}M行 / マッチ {matched_editions:,} editions / {len(results):,} works", flush=True)

# ── 4. 結果を書き出す ────────────────────────────────────────────
written_works = 0
written_rows  = 0

with open(OUT_FILE, 'a', newline='') as out:
    writer = csv.writer(out, delimiter='\t')
    for wid in sorted(results.keys()):
        oclcs = results[wid]
        if oclcs:
            for oc in sorted(oclcs):
                writer.writerow([wid, oc])
                written_rows += 1
        else:
            writer.writerow([wid, ''])
            written_rows += 1
        written_works += 1

    # OCLCなし（ダンプにeditionが存在しなかった）works も空行で記録
    no_edition = todo - set(results.keys())
    for wid in sorted(no_edition):
        writer.writerow([wid, ''])
        written_rows += 1

print(f"\n書き出し完了:", flush=True)
print(f"  OCLC取得あり: {written_works:,} works", flush=True)
print(f"  Edition未収録: {len(no_edition):,} works（空行）", flush=True)
print(f"  総行数追記: {written_rows:,} 行", flush=True)
print(f"→ {OUT_FILE}", flush=True)