"""
match_hathifiles_title.py
=========================
HathiFilesのタイトル+著者検索でOCLC照合漏れを補完する。

対象:
  - ht_api_full.tsvでhtid_count=0の作品
  - ht_api_full.tsvに未収録（OCLCなし）の作品
  合計約15,866件

処理:
  HathiFilesを1行ずつストリーム処理（awk不使用・Python完結）
  タイトル正規化 + 著者姓フィルタ + 年フィルタ（1870-1960）

出力:
  derived/ht_hathifiles_match.tsv
"""

import csv, re, gzip, unicodedata
from collections import defaultdict

HF_PATH = '/mnt/d/hathitrust/hathi_full_20260501.txt.gz'
HT_API  = 'derived/ht_api_full.tsv'
POP_TSV = 'derived/ol_dump_population_with_scope.tsv'
OUT_PATH = 'derived/ht_hathifiles_match.tsv'

PD_CODES = {'pd', 'pdus', 'cc-by', 'cc-by-nd', 'cc-by-sa', 'cc-zero'}


def normalize_title(t):
    if not t: return ''
    t = t.split(":")[0].split(";")[0].split("/")[0]
    t = t.lower()
    t = unicodedata.normalize('NFKD', t)
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\b(the|a|an)\b', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def author_last(a):
    if not a: return ''
    a = a.lower().strip()
    has_comma = ',' in a
    a = re.sub(r'[^\w\s]', ' ', a)
    parts = [p for p in a.split() if len(p) > 2]
    if not parts: return ''
    return parts[0] if has_comma else parts[-1]


# ── Step 1: OCLC照合済みでhtid>0の作品を除外リストに ──
print('Step 1: OCLC照合済み結果を読み込み中...')
already_found = set()   # htid>0が確定しているwork_key
oclc_done = set()       # ht_api_full.tsvに収録済みのwork_key

if True:
    try:
        with open(HT_API) as f:
            for row in csv.DictReader(f, delimiter='\t'):
                wk = row.get('work_key', '').replace('/works/', '')
                oclc_done.add(wk)
                if int(row.get('htid_count', 0) or 0) > 0:
                    already_found.add(wk)
    except FileNotFoundError:
        print('  ht_api_full.tsv なし → 全件対象')

print(f'  OCLC照合済み: {len(oclc_done):,}件')
print(f'  htid>0確定:  {len(already_found):,}件（これはスキップ）')

# ── Step 2: 対象作品のタイトルインデックスを構築 ──
print('Step 2: OL母集団インデックス構築中...')

# nt → [{'work_key', 'title', 'author_last', 'year', 'canonical'}]
ol_index = defaultdict(list)
target_wks = set()

with open(POP_TSV) as f:
    for row in csv.DictReader(f, delimiter='\t'):
        wk = row['work_key'].replace('/works/', '')
        scope = row.get('scope_flag', 'in_scope')
        if scope == 'out_lang':
            continue
        if wk in already_found:
            continue  # htid>0確定済みはスキップ

        title = row.get('title', '')
        auth = row.get('author_name', '')
        year = row.get('first_publish_year', '')
        canon = row.get('canonical', '0')

        nt = normalize_title(title)
        al = author_last(auth)
        yr = int(year) if year.isdigit() else None

        if nt:
            ol_index[nt].append({
                'work_key':  wk,
                'title':     title,
                'auth_last': al,
                'year':      yr,
                'canonical': canon,
            })
            target_wks.add(wk)

print(f'  対象作品数: {len(target_wks):,}件')
print(f'  ユニークタイトル: {len(ol_index):,}件')

# ── Step 3: HathiFilesストリーム検索 ──
print('Step 3: HathiFilesストリーム検索中（数分かかります）...')

# work_key → 最良ヒット
best_hits = {}   # work_key → {htid_count, pd_count, sample_htids, matched_title}

processed = 0
hit_count = 0

with gzip.open(HF_PATH, 'rt', encoding='utf-8', errors='replace') as f:
    for line in f:
        processed += 1
        if processed % 2000000 == 0:
            print(f'  {processed:,}行処理中... ヒット: {hit_count:,}件')

        parts = line.rstrip('\n').split('\t')
        if len(parts) < 25:
            continue

        # 列: 1=htid, 2=access, 3=rights, 8=oclc, 12=title, 17=pub_year, 18=lang, $NF=author
        htid   = parts[0]
        rights = parts[2]
        lang   = parts[18] if len(parts) > 17 else ''
        title  = parts[11] if len(parts) > 11 else ''  # 0-indexed → col12 = parts[11]
        year_s = parts[16] if len(parts) > 16 else ''  # col17 = parts[16]
        author = parts[-1]

        # 英語フィルタ
        if lang != 'eng':
            continue

        # 年フィルタ
        yr_ht = int(year_s) if year_s.isdigit() else None
        if yr_ht and not (1870 <= yr_ht <= 1960):
            continue

        nt = normalize_title(title)
        if not nt or len(nt) < 4:
            continue

        candidates = ol_index.get(nt)
        if not candidates:
            continue

        al_ht = author_last(author)
        pd = rights in PD_CODES

        for cand in candidates:
            wk = cand['work_key']
            al_ol = cand['auth_last']
            yr_ol = cand['year']

            # 著者確認（どちらかが不明ならスキップしない）
            if al_ol and al_ht:
                if al_ol not in al_ht and al_ht not in al_ol:
                    continue

            # 年確認（±15年・どちらかが不明ならスキップしない）
            if yr_ol and yr_ht:
                if yr_ht < yr_ol - 5:
                    continue

            # ヒット記録（htid_countを累積）
            if wk not in best_hits:
                best_hits[wk] = {
                    'htid_count':   0,
                    'pd_count':     0,
                    'sample_htids': [],
                    'matched_title': title,
                    'matched_author': author,
                }
            best_hits[wk]['htid_count'] += 1
            if pd:
                best_hits[wk]['pd_count'] += 1
            if len(best_hits[wk]['sample_htids']) < 3:
                best_hits[wk]['sample_htids'].append(htid)
            hit_count += 1

print(f'  完了: {processed:,}行処理 / ヒット作品数: {len(best_hits):,}件')

# ── Step 4: 出力 ──
print('Step 4: 出力中...')

fieldnames = ['work_key', 'title', 'author_name', 'first_publish_year',
              'canonical', 'htid_count', 'pd_count', 'sample_htids',
              'matched_title', 'matched_author', 'source']

# OL母集団から作品情報を取得
pop_info = {}
with open(POP_TSV) as f:
    for row in csv.DictReader(f, delimiter='\t'):
        wk = row['work_key'].replace('/works/', '')
        pop_info[wk] = row

with open(OUT_PATH, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
    writer.writeheader()

    for wk, hit in best_hits.items():
        info = pop_info.get(wk, {})
        writer.writerow({
            'work_key':       wk,
            'title':          info.get('title', ''),
            'author_name':    info.get('author_name', ''),
            'first_publish_year': info.get('first_publish_year', ''),
            'canonical':      info.get('canonical', '0'),
            'htid_count':     hit['htid_count'],
            'pd_count':       hit['pd_count'],
            'sample_htids':   '|'.join(hit['sample_htids']),
            'matched_title':  hit['matched_title'][:60],
            'matched_author': hit['matched_author'][:40],
            'source':         'hathifiles_title',
        })

print(f'出力: {OUT_PATH}（{len(best_hits):,}件）')

# サマリ
canon_hits = [wk for wk, h in best_hits.items()
              if pop_info.get(wk, {}).get('canonical') == '1']
print(f'canonical新規ヒット: {len(canon_hits)}件')
for wk in canon_hits:
    info = pop_info.get(wk, {})
    h = best_hits[wk]
    print(f'  {info.get("title","")[:40]}  htid={h["htid_count"]}  pd={h["pd_count"]}')