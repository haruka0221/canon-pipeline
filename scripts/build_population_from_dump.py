"""
build_population_from_dump.py  v2
メモリ効率版：除外リスト（小）だけをメモリに保持する3パス処理
"""

import gzip, json, re, csv, datetime
from pathlib import Path
from collections import defaultdict

WORKS_DUMP    = Path("raw/ol_dump/ol_dump_works_2026-02-28.txt.gz")
EDITIONS_DUMP = Path("raw/ol_dump/ol_dump_editions_2026-02-28.txt.gz")
OUTPUT        = Path("derived/ol_dump_population_2026-02-28.tsv")
LOG           = Path("logs/build_population_from_dump.log")

EXCLUDE_KEYS = {
    "plays","dramatic_works","scripts","poetry","poems","ballads",
    "stories_in_rhyme","nonsense_verses","verse","picture_books",
    "literary_criticism","nonfiction","biography__autobiography"
}
PROTECT_KEYS = {
    "novel","novels","short_stories","literary_fiction",
    "fiction_general","english_fiction","american_fiction"
}
YEAR_RE = re.compile(r'\b(1[0-9]{3}|20[0-2][0-9])\b')


def normalize_subject(s):
    return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')

def should_exclude(skeys):
    if skeys & PROTECT_KEYS: return False
    return bool(skeys & EXCLUDE_KEYS)

def log(msg):
    print(msg, flush=True)
    with open(LOG, "a") as f:
        f.write(msg + "\n")


# ── Pass 1: 除外すべき work_key を収集（小さいセット） ──────────
def pass1_collect_excluded():
    log("=== Pass 1: collect excluded work_keys ===")
    excluded = set()
    total = 0
    with gzip.open(WORKS_DUMP, "rt", encoding="utf-8") as f:
        for line in f:
            total += 1
            if total % 2_000_000 == 0:
                log(f"  Pass 1: {total:,} records, {len(excluded):,} excluded so far")
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5: continue
            try: rec = json.loads(parts[4])
            except: continue
            skeys = {normalize_subject(s) for s in rec.get("subjects", [])}
            if should_exclude(skeys):
                excluded.add(rec.get("key",""))
    log(f"Pass 1 done: {total:,} works, {len(excluded):,} excluded")
    return excluded


# ── Pass 2: Editions をストリーム処理して通過 work_key を収集 ───
def pass2_editions(excluded):
    log("=== Pass 2: editions → year + language filter ===")
    # work_key → 最古年
    work_min_year = defaultdict(lambda: 9999)
    work_has_eng  = set()
    total = matched = 0

    with gzip.open(EDITIONS_DUMP, "rt", encoding="utf-8") as f:
        for line in f:
            total += 1
            if total % 2_000_000 == 0:
                log(f"  Pass 2: {total:,} editions, {matched:,} matched, "
                    f"{len(work_has_eng):,} eng works so far")
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5: continue
            try: rec = json.loads(parts[4])
            except: continue
            wf = rec.get("works", [])
            if not wf: continue
            wk = wf[0].get("key","") if isinstance(wf[0], dict) else ""
            if not wk or wk in excluded: continue
            matched += 1

            pd = rec.get("publish_date","")
            if pd:
                m = YEAR_RE.search(pd)
                if m:
                    yr = int(m.group())
                    if yr < work_min_year[wk]:
                        work_min_year[wk] = yr

            for lang in rec.get("languages", []):
                if isinstance(lang, dict) and lang.get("key","").endswith("/eng"):
                    work_has_eng.add(wk)
                    break

    # 1880〜1950 かつ eng の work_key だけ残す
    target = {
        wk: work_min_year[wk]
        for wk in work_has_eng
        if 1880 <= work_min_year[wk] <= 1950
    }
    log(f"Pass 2 done: {total:,} editions, {len(target):,} works pass year+lang filter")
    return target


# ── Pass 3: Works を再スキャンして対象作品のメタデータを出力 ────
def pass3_output(target):
    log("=== Pass 3: output final population ===")
    OUTPUT.parent.mkdir(exist_ok=True)
    written = 0

    with gzip.open(WORKS_DUMP, "rt", encoding="utf-8") as f, \
         open(OUTPUT, "w", newline="", encoding="utf-8") as out:

        writer = csv.writer(out, delimiter="\t")
        writer.writerow([
            "work_key","title","author_keys",
            "subject_keys_str","first_publish_year"
        ])

        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5: continue
            try: rec = json.loads(parts[4])
            except: continue
            wk = rec.get("key","")
            if wk not in target: continue

            title = rec.get("title","")
            author_keys = ";".join(
                a["author"]["key"]
                for a in rec.get("authors", [])
                if isinstance(a, dict) and "author" in a
                and isinstance(a.get("author"), dict)
            )
            skeys = ";".join(sorted(
                normalize_subject(s) for s in rec.get("subjects", [])
            ))
            writer.writerow([wk, title, author_keys, skeys, target[wk]])
            written += 1

    log(f"Pass 3 done: {written:,} works written to {OUTPUT}")
    return written


if __name__ == "__main__":
    LOG.parent.mkdir(exist_ok=True)
    log(f"Started: {datetime.datetime.now()}")
    excluded = pass1_collect_excluded()
    target   = pass2_editions(excluded)
    n        = pass3_output(target)
    log(f"Finished: {datetime.datetime.now()}")
    log(f"Final population: {n:,} works → {OUTPUT}")
