"""
match_phd_corpus.py
phd_corpus（1880-1950）を ol_dump_population_fiction に fuzzy matching で照合し
canonical フラグを付与する。手動追加は一切しない。
"""

import csv, re
from pathlib import Path
from rapidfuzz import fuzz

PHD   = Path("data/phd_corpus_1880_1950_cleaned.csv")
POP   = Path("derived/ol_dump_population_fiction_2026-02-28.tsv")
OUT   = Path("derived/ol_dump_population_with_canonical.tsv")
MISS  = Path("derived/phd_corpus_not_matched.tsv")
THRESHOLD = 80  # 予備調査と同じ

# OCRエラー修正（引き継ぎ書 §6 より）
OCR_FIX = {
    "HouseOfMirth copy":              "The House of Mirth",
    "TurnoftheScrew copy":            "The Turn of the Screw",
    "TheAmbassadors copy":            "The Ambassadors",
    "Silas Lap ham":                  "The Rise of Silas Lapham",
    "Lady Chatter leys Lover":        "Lady Chatterley's Lover",
    "The Rise of David Levin sky":    "The Rise of David Levinsky",
}

def normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"^(the|a|an)\s+", "", s)
    s = re.sub(r"[^a-z0-9\s]", "", s)
    return s.strip()


# ── phd_corpus 読み込み（1880-1950のみ）────────────────────────
phd_works = []
with open(PHD, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        yr = int(row["PubYear"])
        if not (1880 <= yr <= 1950):
            continue
        title = OCR_FIX.get(row["Title"], row["Title"])
        phd_works.append({
            "phd_year":   yr,
            "phd_author": row["AuthorName"],
            "phd_title":  title,
            "phd_title_norm": normalize(title),
        })

print(f"phd_corpus (1880-1950): {len(phd_works)} works")

# ── OL母集団 読み込み ──────────────────────────────────────────
pop = []
with open(POP, encoding="utf-8") as f:
    for row in csv.DictReader(f, delimiter="\t"):
        row["title_norm"] = normalize(row["title"])
        pop.append(row)

print(f"OL fiction population: {len(pop):,} works")

# ── fuzzy matching ─────────────────────────────────────────────
# OL側に canonical フラグを立てる
canonical_keys = set()
matched_phd    = []
unmatched_phd  = []

for phd in phd_works:
    best_score = 0
    best_row   = None
    for row in pop:
        score = fuzz.token_sort_ratio(phd["phd_title_norm"], row["title_norm"])
        if score > best_score:
            best_score = score
            best_row   = row
    if best_score >= THRESHOLD and best_row:
        canonical_keys.add(best_row["work_key"])
        matched_phd.append({**phd, "ol_work_key": best_row["work_key"],
                             "ol_title": best_row["title"], "score": best_score})
    else:
        unmatched_phd.append({**phd, "best_score": best_score,
                               "best_ol_title": best_row["title"] if best_row else ""})

print(f"Matched: {len(matched_phd)} / {len(phd_works)}")
print(f"Unmatched: {len(unmatched_phd)} (recorded as limitations)")

# ── 出力：母集団 + canonical フラグ ───────────────────────────
with open(POP, encoding="utf-8") as f, \
     open(OUT, "w", newline="", encoding="utf-8") as out:
    reader = csv.DictReader(f, delimiter="\t")
    fieldnames = reader.fieldnames + ["canonical"]
    writer = csv.DictWriter(out, fieldnames=fieldnames, delimiter="\t")
    writer.writeheader()
    for row in reader:
        row["canonical"] = 1 if row["work_key"] in canonical_keys else 0
        writer.writerow(row)

# ── 出力：照合できなかった phd 作品 ───────────────────────────
with open(MISS, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=unmatched_phd[0].keys(), delimiter="\t")
    writer.writeheader()
    writer.writerows(unmatched_phd)

print(f"Output: {OUT}")
print(f"Unmatched log: {MISS}")
