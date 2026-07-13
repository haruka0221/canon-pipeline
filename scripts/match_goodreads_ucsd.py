"""
match_goodreads_ucsd.py  v4
===========================
v3からの変更:
  - RATINGS_MAX_NOAUTH を廃止
  - 著者が一致しない場合は必ずNO_MATCH_AUTHとする（誤照合防止）
  - RATINGS_MAX は著者確認済みの場合のみ

出力:
  derived/goodreads_ucsd_match.tsv
"""

import csv, re, unicodedata
from collections import defaultdict


def normalize_title(t):
    if not t:
        return ''
    t = t.split(':')[0].split(';')[0]
    t = t.lower()
    t = unicodedata.normalize('NFKD', t)
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\b(the|a|an)\b', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def author_last_from_ol(a):
    if not a:
        return ''
    a = a.lower().strip()
    has_comma = ',' in a
    a = re.sub(r'[^\w\s]', ' ', a)
    parts = [p for p in a.split() if len(p) > 2]
    if not parts:
        return ''
    return parts[0] if has_comma else parts[-1]


def author_match(ol_last, ucsd_author_lasts_str):
    """OLの著者姓とUCSDの著者姓リストが一致するか。
    どちらかが不明な場合はTrueを返す（フィルタしない）。"""
    if not ol_last:
        return True
    if not ucsd_author_lasts_str:
        return True  # UCSDに著者情報なし → フィルタ不可
    ucsd_lasts = ucsd_author_lasts_str.split('|')
    return any(ol_last in n or n in ol_last for n in ucsd_lasts if n)


def parse_rating_dist(dist_str):
    result = {'ratings_5': '', 'ratings_4': '', 'ratings_3': '',
              'ratings_2': '', 'ratings_1': ''}
    if not dist_str:
        return result
    for part in dist_str.split('|'):
        if ':' in part:
            k, v = part.split(':', 1)
            if k in ('1', '2', '3', '4', '5'):
                result[f'ratings_{k}'] = v
    return result


def apply_match(out, c, match_type):
    rd = c.get('rating_dist', '')
    stars = parse_rating_dist(rd)
    out.update({
        'work_id':            c['work_id'],
        'ratings_count':      c['ratings_count'],
        'text_reviews_count': c['text_reviews_count'],
        'rating_dist':        rd,
        'genres':             c.get('genres', ''),
        'match_type':         match_type,
        'candidates':         '',
        **stars
    })


# ── edition_count読み込み ─────────────────────────────────
print('edition_count読み込み中...')
editions = {}
with open('derived/ol_edition_counts.tsv') as f:
    for row in csv.DictReader(f, delimiter='\t'):
        editions[row['work_key']] = int(row.get('edition_count', 0) or 0)

# ── UCSDインデックス読み込み ──────────────────────────────
print('UCSDインデックス読み込み中...')
gw = defaultdict(list)
with open('derived/goodreads_works_index_v2.tsv') as f:
    for row in csv.DictReader(f, delimiter='\t'):
        nt = normalize_title(row['title'])
        if nt:
            gw[nt].append(row)
print(f'  → ユニークタイトル数: {len(gw):,}')

# ── OL母集団照合 ─────────────────────────────────────────
print('OL母集団照合中...')

fieldnames = ['work_key', 'title', 'author_name', 'first_publish_year',
              'canonical', 'work_id', 'ratings_count', 'text_reviews_count',
              'ratings_5', 'ratings_4', 'ratings_3', 'ratings_2', 'ratings_1',
              'rating_dist', 'genres', 'match_type', 'candidates']

counts = defaultdict(int)

with open('derived/ol_dump_population_with_scope.tsv') as fin, \
     open('derived/goodreads_ucsd_match.tsv', 'w', newline='') as fout:

    writer = csv.DictWriter(fout, fieldnames=fieldnames, delimiter='\t')
    writer.writeheader()

    for row in csv.DictReader(fin, delimiter='\t'):
        if row.get("scope_flag") == "out_lang":
            counts["SKIP_LANG"] += 1
            continue
        wk    = row['work_key']
        title = row.get('title', '')
        auth  = row.get('author_name', '')
        year  = row.get('first_publish_year', '')
        canon = row.get('canonical', '0')
        ed    = editions.get(wk, 0)

        nt      = normalize_title(title)
        ol_last = author_last_from_ol(auth)
        yr      = int(year) if year.isdigit() else None

        out = {
            'work_key': wk, 'title': title, 'author_name': auth,
            'first_publish_year': year, 'canonical': canon,
            'work_id': '', 'ratings_count': '', 'text_reviews_count': '',
            'ratings_5': '', 'ratings_4': '', 'ratings_3': '',
            'ratings_2': '', 'ratings_1': '', 'rating_dist': '',
            'genres': '', 'match_type': 'NO_MATCH', 'candidates': ''
        }

        # タイトル候補取得
        candidates = gw.get(nt, [])
        # フォールバック：前方10文字
        if not candidates and len(nt) >= 8:
            nt10 = nt[:10]
            candidates = [r for k, v in gw.items()
                          if k[:10] == nt10 for r in v]

        if len(candidates) == 0:
            counts['NO_MATCH'] += 1

        elif len(candidates) == 1:
            c = candidates[0]
            if author_match(ol_last, c.get('author_last_names', '')):
                apply_match(out, c, 'UNIQUE')
                counts['UNIQUE'] += 1
            else:
                out['match_type'] = 'NO_MATCH_AUTH'
                counts['NO_MATCH_AUTH'] += 1

        else:
            # 年±10フィルタ
            yr_cands = candidates
            if yr:
                filtered = [c for c in candidates
                            if c.get('year', '').lstrip('-').isdigit()
                            and abs(int(c['year']) - yr) <= 10]
                if filtered:
                    yr_cands = filtered

            # 著者フィルタ（必須）
            auth_cands = [c for c in yr_cands
                          if author_match(ol_last, c.get('author_last_names', ''))]

            # 著者が一致しない場合はNO_MATCH_AUTH（誤照合防止）
            if not auth_cands:
                out['match_type'] = 'NO_MATCH_AUTH'
                counts['NO_MATCH_AUTH'] += 1
                writer.writerow(out)
                continue

            if len(auth_cands) == 1:
                apply_match(out, auth_cands[0], 'YEAR_AUTH')
                counts['YEAR_AUTH'] += 1

            else:
                best = max(auth_cands,
                           key=lambda c: int(c.get('ratings_count') or 0))
                best_r = int(best.get('ratings_count') or 0)
                sorted_cands = sorted(
                    auth_cands,
                    key=lambda c: -int(c.get('ratings_count') or 0)
                )
                needs_llm = (
                    ed >= 10
                    and len(sorted_cands) >= 2
                    and best_r > 0
                    and int(sorted_cands[1].get('ratings_count') or 0) > best_r * 0.1
                )
                if needs_llm:
                    cand_str = '|'.join(
                        f"{c['work_id']}:{c['title'][:25]}:{c['year']}"
                        for c in auth_cands[:10]
                    )
                    out['candidates'] = cand_str
                    out['match_type'] = 'LLM_PENDING'
                    counts['LLM_PENDING'] += 1
                else:
                    apply_match(out, best, 'RATINGS_MAX')
                    counts['RATINGS_MAX'] += 1

        writer.writerow(out)

# ── サマリ ────────────────────────────────────────────────
print(f'\n=== 結果 ===')
success = {'UNIQUE', 'YEAR_AUTH', 'RATINGS_MAX'}
for k in sorted(counts):
    print(f'  {k}: {counts[k]:,}')
print(f'  照合成功計: {sum(counts[k] for k in success if k in counts):,}')
print(f'  LLM待ち:   {counts["LLM_PENDING"]:,}')
print(f'  NO_MATCH系: {counts["NO_MATCH"] + counts["NO_MATCH_AUTH"]:,}')

with open('derived/goodreads_ucsd_match.tsv') as f:
    rows = list(csv.DictReader(f, delimiter='\t'))

canon = [r for r in rows if r['canonical'] == '1']
canon_hit = [r for r in canon if r['match_type'] in success | {'LLM_PENDING'}]
canon_no  = [r for r in canon if r['match_type'] not in success | {'LLM_PENDING'}]
print(f'\ncanonical照合成功（LLM含む）: {len(canon_hit)}/{len(canon)}件')
print(f'canonical未照合: {len(canon_no)}件')
for r in sorted(canon_no, key=lambda x: x['title']):
    print(f'  [{r["match_type"]}] {r["title"][:40]} / {r["author_name"][:20]}')