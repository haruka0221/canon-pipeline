#!/usr/bin/env python3
"""
match_phd_corpus_v2.py
======================
phd_corpus → OL母集団の照合スクリプト改善版。

v1との違い:
  - タイトルfuzzy matchのみ → タイトル + 年(±5) + 著者姓 の3条件
  - 同名作品が複数ある場合に正しい版を選べるようになった
  - 照合結果の詳細ログを出力（何が変わったか確認できる）

マッチング優先順位:
  1. タイトルスコア≥80 AND 年±5 AND 著者姓一致  → 確定マッチ（best）
  2. タイトルスコア≥80 AND 年±5                → 年一致マッチ（good）
  3. タイトルスコア≥80 のみ                    → タイトルのみマッチ（v1と同じ・fallback）

出力:
  derived/ol_dump_population_with_canonical_v2.tsv   （新しいcanonicalフラグ付き母集団）
  derived/phd_match_comparison.tsv                   （v1との差分・変わった件を確認用）
  derived/phd_corpus_not_matched_v2.tsv              （未マッチ）
"""

import csv
import re
from pathlib import Path
from rapidfuzz import fuzz

# ─── パス ───────────────────────────────────────────────────
PHD     = Path("data/phd_corpus_1880_1950_cleaned.csv")
POP     = Path("derived/ol_dump_population_with_author.tsv")
OLD_OUT = Path("derived/ol_dump_population_with_canonical.tsv")   # v1の結果（比較用）
OUT     = Path("derived/ol_dump_population_with_canonical_v2.tsv")
DIFF    = Path("derived/phd_match_comparison.tsv")
MISS    = Path("derived/phd_corpus_not_matched_v2.tsv")

THRESHOLD   = 80
YEAR_MARGIN = 5

# 年+著者条件では誤マッチするため正しいwork_keyを直接指定
FORCE_MAP = {
    "The Prisoner of Zenda": "/works/OL9056552W",   # Anthony Hope (1894)
    "The Good Soldier":      "/works/OL15345521W",  # Ford Madox Ford (1915)
    "Dracula":               "/works/OL15062619W",  # Bram Stoker (1897)
}

OCR_FIX = {
    "HouseOfMirth copy":              "The House of Mirth",
    "TurnoftheScrew copy":            "The Turn of the Screw",
    "TheAmbassadors copy":            "The Ambassadors",
    "Silas Lap ham":                  "The Rise of Silas Lapham",
    "Lady Chatter leys Lover":        "Lady Chatterley's Lover",
    "The Rise of David Levin sky":    "The Rise of David Levinsky",
}

# ─── 正規化（v3確定版） ──────────────────────────────────────
_LEADING_ART = re.compile(r'^(the|a|an)\s+', re.IGNORECASE)
_DROP_CHARS  = re.compile(r"['\-\u2018\u2019\u201c\u201d]")
_NON_ALNUM   = re.compile(r'[^a-z0-9\s]')
_MULTI_SPC   = re.compile(r'\s+')

def normalize(text: str) -> str:
    t = text.lower()
    t = _LEADING_ART.sub('', t)
    t = _DROP_CHARS.sub('', t)
    t = _NON_ALNUM.sub(' ', t)
    return _MULTI_SPC.sub(' ', t).strip()

def extract_last_name(author_str: str) -> str:
    s = author_str.strip()
    if not s:
        return ''
    last = s.split(',')[0].strip() if ',' in s else (s.split() or [''])[-1]
    return normalize(last)

def year_ok(phd_year: int, ol_year_str: str) -> bool:
    try:
        ol_year = int(ol_year_str)
        return abs(phd_year - ol_year) <= YEAR_MARGIN
    except (ValueError, TypeError):
        return False  # OL側に年がない場合は「年不明」として通さない

def author_ok(phd_author: str, ol_author: str) -> bool:
    phd_last = extract_last_name(phd_author)
    ol_last  = extract_last_name(ol_author)
    if not phd_last or not ol_last:
        return False
    # 著者姓が部分一致（片方がもう片方を含む）
    return phd_last in ol_last or ol_last in phd_last

# ─── 読み込み ────────────────────────────────────────────────
phd_works = []
with open(PHD, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        yr = int(row["PubYear"])
        if not (1880 <= yr <= 1950):
            continue
        title = OCR_FIX.get(row["Title"], row["Title"])
        phd_works.append({
            "phd_year":        yr,
            "phd_author":      row["AuthorName"],
            "phd_title":       title,
            "phd_title_norm":  normalize(title),
            "phd_last_name":   extract_last_name(row["AuthorName"]),
        })
print(f"phd_corpus (1880-1950): {len(phd_works)} works")

pop = []
with open(POP, encoding="utf-8") as f:
    for row in csv.DictReader(f, delimiter="\t"):
        row["title_norm"] = normalize(row["title"])
        pop.append(row)
print(f"OL fiction population: {len(pop):,} works")

# v1のcanonical_keys（比較用）
v1_canonical = set()
if OLD_OUT.exists():
    with open(OLD_OUT, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row.get("canonical") == "1":
                v1_canonical.add(row["work_key"])
    print(f"v1 canonical keys loaded: {len(v1_canonical)}")

# ─── マッチング ──────────────────────────────────────────────
canonical_keys = set()
matched_phd    = []
unmatched_phd  = []

for phd in phd_works:
    # FORCE_MAP: 誤マッチが確認されている作品は直接指定
    if phd["phd_title"] in FORCE_MAP:
        forced_key = FORCE_MAP[phd["phd_title"]]
        forced_row = next((r for r in pop if r["work_key"] == forced_key), None)
        if forced_row:
            canonical_keys.add(forced_key)
            matched_phd.append({
                "phd_title": phd["phd_title"], "phd_author": phd["phd_author"],
                "phd_year": phd["phd_year"], "ol_work_key": forced_key,
                "ol_title": forced_row["title"], "ol_author": forced_row.get("author_name",""),
                "ol_year": forced_row.get("first_publish_year",""),
                "title_score": 999, "yr_match": True, "au_match": True,
                "quality": "forced", "v1_key": forced_key, "changed": False,
                "n_candidates": 1,
            })
            continue

    # タイトルスコアが閾値以上の候補を全件収集
    candidates = []
    for row in pop:
        score = fuzz.token_sort_ratio(phd["phd_title_norm"], row["title_norm"])
        if score >= THRESHOLD:
            yr_match  = year_ok(phd["phd_year"], row.get("first_publish_year", ""))
            au_match  = author_ok(phd["phd_author"], row.get("author_name", ""))
            candidates.append({
                "row":      row,
                "score":    score,
                "yr_match": yr_match,
                "au_match": au_match,
            })

    if not candidates:
        # タイトルすら閾値未満 → 未マッチ
        unmatched_phd.append({**phd, "best_score": 0, "best_ol_title": "", "reason": "no_title_match"})
        continue

    # 優先順位でソート: (年一致, 著者一致, スコア) の降順
    candidates.sort(key=lambda c: (c["yr_match"], c["au_match"], c["score"]), reverse=True)
    best = candidates[0]
    best_row = best["row"]

    # マッチ品質を判定
    if best["yr_match"] and best["au_match"]:
        quality = "best"       # 年+著者+タイトル全一致
    elif best["yr_match"]:
        quality = "year_only"  # 年+タイトル（著者名なし/不一致）
    else:
        quality = "title_only" # タイトルのみ（v1 fallback）

    canonical_keys.add(best_row["work_key"])
    matched_phd.append({
        "phd_title":      phd["phd_title"],
        "phd_author":     phd["phd_author"],
        "phd_year":       phd["phd_year"],
        "ol_work_key":    best_row["work_key"],
        "ol_title":       best_row["title"],
        "ol_author":      best_row.get("author_name", ""),
        "ol_year":        best_row.get("first_publish_year", ""),
        "title_score":    best["score"],
        "yr_match":       best["yr_match"],
        "au_match":       best["au_match"],
        "quality":        quality,
        "v1_key":         ", ".join(
                              c["row"]["work_key"] for c in candidates
                              if c["row"]["work_key"] in v1_canonical
                          ) or "(none)",
        "changed":        best_row["work_key"] not in v1_canonical,
        "n_candidates":   len(candidates),
    })

print(f"\nMatched:   {len(matched_phd)} / {len(phd_works)}")
print(f"Unmatched: {len(unmatched_phd)}")
print(f"  quality=best:       {sum(1 for m in matched_phd if m['quality']=='best')}")
print(f"  quality=year_only:  {sum(1 for m in matched_phd if m['quality']=='year_only')}")
print(f"  quality=title_only: {sum(1 for m in matched_phd if m['quality']=='title_only')}")

changed = [m for m in matched_phd if m["changed"]]
print(f"\nv1から変更された照合: {len(changed)} 件")
for m in changed:
    print(f"  [{m['quality']}] {m['phd_title']} ({m['phd_year']})")
    print(f"    v1: {m['v1_key']}")
    print(f"    v2: {m['ol_work_key']} 「{m['ol_title']}」/ {m['ol_author']} ({m['ol_year']})")

# ─── 出力 ────────────────────────────────────────────────────
# 新しいcanonicalフラグ付き母集団
with open(POP, encoding="utf-8") as f, \
     open(OUT, "w", newline="", encoding="utf-8") as out_f:
    reader    = csv.DictReader(f, delimiter="\t")
    fieldnames = reader.fieldnames + ["canonical"]
    writer    = csv.DictWriter(out_f, fieldnames=fieldnames, delimiter="\t")
    writer.writeheader()
    for row in reader:
        row["canonical"] = 1 if row["work_key"] in canonical_keys else 0
        writer.writerow(row)

# v1との比較ログ
diff_fields = ["phd_title","phd_author","phd_year","ol_work_key","ol_title",
               "ol_author","ol_year","title_score","yr_match","au_match",
               "quality","v1_key","changed","n_candidates"]
with open(DIFF, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=diff_fields, delimiter="\t")
    w.writeheader()
    w.writerows(matched_phd)

# 未マッチ
if unmatched_phd:
    with open(MISS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=unmatched_phd[0].keys(), delimiter="\t")
        w.writeheader()
        w.writerows(unmatched_phd)

print(f"\nOutput:     {OUT}")
print(f"Comparison: {DIFF}")
print(f"Unmatched:  {MISS}")