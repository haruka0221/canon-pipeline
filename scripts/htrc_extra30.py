import csv, re
from rapidfuzz import fuzz

def norm(s):
    if not s:
        return ""
    s = re.sub(r'^(the|a|an)\s+', '', s.lower())
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

# extra30
extra = list(csv.DictReader(open("derived/jstor_extra29.tsv"), delimiter="\t"))

# phd_corpusから年代情報を取得
phd = list(csv.DictReader(
    open("data/phd_corpus_1880_1950_cleaned.csv", encoding="utf-8-sig")))
phd_years = {r["Title"].lower().strip(): r.get("PubYear","") for r in phd}

# HTRCメタデータ
htrc = list(csv.DictReader(open("data/htrc-fiction_metadata.csv")))
print(f"HTRCレコード数: {len(htrc)}")
print(f"HTRC列名: {list(htrc[0].keys())[:8]}")

results = []
print(f"\n{'Title':<45} {'htid_count':>11} {'best_match'}")
print("-" * 90)

for r in extra:
    title = r["title"]
    tnorm = norm(title)
    # phd_corpusから年代を取得
    phd_year = ""
    for pt, py in phd_years.items():
        if fuzz.token_sort_ratio(title.lower(), pt) >= 85:
            phd_year = py
            break

    # HTRCでfuzzy match
    candidates = []
    for h in htrc:
        htitle = norm(h.get("title", ""))
        if not htitle:
            continue
        score = fuzz.token_sort_ratio(tnorm, htitle)
        if score >= 85:
            # 年代チェック
            try:
                h_year = int(h.get("rights_date_used", h.get("pub_date", 0)))
                p_year = int(phd_year) if phd_year else 0
                if p_year and abs(h_year - p_year) <= 15:
                    candidates.append((score, h))
                elif not p_year:
                    candidates.append((score, h))
            except:
                candidates.append((score, h))

    htid_count = len(candidates)
    best = candidates[0][1].get("title","")[:35] if candidates else "—"
    flag = "" if htid_count > 0 else "🔴"
    print(f"  {title:<45} {htid_count:>11}  {best} {flag}")

    results.append({
        "work_key":   r["work_key"],
        "title":      title,
        "last_name":  r["last_name"],
        "htid_count": htid_count,
        "source":     "HTRC_fuzzy_2026",
    })

with open("derived/htrc_extra30.tsv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()), delimiter="\t")
    w.writeheader()
    w.writerows(results)

zero = sum(1 for r in results if r["htid_count"] == 0)
print(f"\nhtid=0: {zero}/30件")
print("→ derived/htrc_extra30.tsv 保存完了")
