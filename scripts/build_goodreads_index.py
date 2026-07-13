"""
build_goodreads_index.py
========================
UCSDデータから照合用インデックスを構築する。
MajinBook不使用・UCSD完結。

出力:
  derived/goodreads_works_index_v2.tsv
    work_id, title, year, ratings_count, text_reviews_count,
    rating_dist, ratings_5..1, author_last_names, genres

実行時間: 約10〜15分（goodreads_books.json.gz 2GBが律速）
"""

import gzip, json, re, csv
from collections import defaultdict

UCSD_DIR = '/mnt/d/goodreads'

def author_last(name):
    """著者名から姓を抽出"""
    if not name:
        return ''
    name = name.lower().strip()
    has_comma = ',' in name
    name = re.sub(r'[^\w\s]', ' ', name)
    parts = [p for p in name.split() if len(p) > 2]
    if not parts:
        return ''
    return parts[0] if has_comma else parts[-1]

def parse_rating_dist(dist_str):
    result = {}
    if not dist_str:
        return result
    for part in dist_str.split('|'):
        if ':' in part:
            k, v = part.split(':', 1)
            if k in ('1','2','3','4','5'):
                result[f'ratings_{k}'] = v
    return result

# ── Step 1: author_id → 著者姓 ──────────────────────────
print('Step 1: 著者インデックス作成中...')
author_idx = {}  # author_id → last_name
with gzip.open(f'{UCSD_DIR}/goodreads_book_authors.json.gz', 'rt') as f:
    for line in f:
        d = json.loads(line)
        aid = d.get('author_id','')
        name = d.get('name','')
        if aid and name:
            author_idx[str(aid)] = author_last(name)
print(f'  → {len(author_idx):,}件')

# ── Step 2: book_id → 著者姓リスト + work_id ───────────
print('Step 2: books → 著者姓リスト作成中... (2GBのため数分かかります)')
book_to_authors = {}  # book_id → [last_name, ...]
book_to_work = {}     # book_id → work_id
book_to_isbn = {}     # book_id → isbn13 or isbn

n = 0
with gzip.open(f'{UCSD_DIR}/goodreads_books.json.gz', 'rt') as f:
    for line in f:
        d = json.loads(line)
        bid = d.get('book_id','')
        wid = d.get('work_id','')
        if not bid:
            continue
        # 著者姓リスト
        authors = d.get('authors', [])
        lasts = []
        for a in authors:
            aid = str(a.get('author_id',''))
            ln = author_idx.get(aid,'')
            if ln:
                lasts.append(ln)
        if lasts:
            book_to_authors[str(bid)] = lasts
        if wid:
            book_to_work[str(bid)] = str(wid)
        # ISBN
        isbn = d.get('isbn13','') or d.get('isbn','')
        if isbn:
            book_to_isbn[str(bid)] = isbn
        n += 1
        if n % 500000 == 0:
            print(f'  {n:,}件処理中...')
print(f'  → books処理完了: {n:,}件')

# ── Step 3: book_id → genres ────────────────────────────
print('Step 3: ジャンルインデックス作成中...')
book_to_genres = {}  # book_id → genres dict
with gzip.open(f'{UCSD_DIR}/goodreads_book_genres_initial.json.gz', 'rt') as f:
    for line in f:
        d = json.loads(line)
        bid = str(d.get('book_id',''))
        genres = d.get('genres', {})
        if bid and genres:
            # ジャンル名をカンマ区切り文字列に
            genre_names = list(genres.keys())
            book_to_genres[bid] = '|'.join(genre_names[:5])  # 最大5ジャンル
print(f'  → {len(book_to_genres):,}件')

# ── Step 4: works → 統合インデックス ───────────────────
print('Step 4: worksインデックス構築中...')
fieldnames = ['work_id', 'title', 'year', 'ratings_count',
              'text_reviews_count', 'ratings_5', 'ratings_4',
              'ratings_3', 'ratings_2', 'ratings_1',
              'rating_dist', 'author_last_names', 'genres']

out_path = 'derived/goodreads_works_index_v2.tsv'
n_out = 0

with gzip.open(f'{UCSD_DIR}/goodreads_book_works.json.gz', 'rt') as fin, \
     open(out_path, 'w', newline='') as fout:

    writer = csv.DictWriter(fout, fieldnames=fieldnames, delimiter='\t')
    writer.writeheader()

    for line in fin:
        d = json.loads(line)
        wid  = str(d.get('work_id',''))
        year = d.get('original_publication_year','')
        title = d.get('original_title','')
        best_bid = str(d.get('best_book_id',''))

        # 著者姓
        author_lasts = book_to_authors.get(best_bid, [])

        # ジャンル
        genres = book_to_genres.get(best_bid, '')

        # rating_dist パース
        rd = d.get('rating_dist','')
        stars = parse_rating_dist(rd)

        row = {
            'work_id':            wid,
            'title':              title,
            'year':               year,
            'ratings_count':      d.get('ratings_count','0'),
            'text_reviews_count': d.get('text_reviews_count','0'),
            'rating_dist':        rd,
            'author_last_names':  '|'.join(author_lasts),
            'genres':             genres,
            **stars
        }
        writer.writerow(row)
        n_out += 1

print(f'  → {n_out:,}件出力')
print(f'出力: {out_path}')

# 確認
print('\n=== サンプル確認 ===')
with open(out_path) as f:
    reader = csv.DictReader(f, delimiter='\t')
    for i, row in enumerate(reader):
        if row['author_last_names'] and int(row.get('ratings_count') or 0) > 100000:
            print(f"  {row['title'][:40]} / {row['author_last_names']} / {row['year']} / ratings={row['ratings_count']}")
        if i > 50000:
            break