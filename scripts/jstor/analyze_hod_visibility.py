import json
import csv
from pathlib import Path
from collections import Counter

INPUT = Path("derived/jstor_ll_articles.jsonl")
OUT_DIR = Path("derived/jstor_hod")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_PHRASE = "heart of darkness"

START_YEAR = 1940
END_YEAR = 2025
BIN_SIZE = 5

total_by_year = Counter()
target_by_year = Counter()
target_records = []

with INPUT.open(encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue

        try:
            article = json.loads(line)
        except Exception:
            continue

        date = str(article.get("date", ""))
        if not date[:4].isdigit():
            continue

        year = int(date[:4])
        if not (START_YEAR <= year <= END_YEAR):
            continue

        title = str(article.get("title", ""))
        creator = article.get("creator", "")
        discipline = article.get("discipline", "")

        total_by_year[year] += 1

        if TARGET_PHRASE in title.lower():
            target_by_year[year] += 1
            target_records.append({
                "year": year,
                "title": title,
                "creator": creator,
                "discipline": discipline,
            })

# 1. 年別結果
yearly_rows = []
for year in range(START_YEAR, END_YEAR + 1):
    total = total_by_year[year]
    target = target_by_year[year]
    per_1000 = target / total * 1000 if total else 0

    yearly_rows.append({
        "year": year,
        "ll_total": total,
        "hod_mentions": target,
        "hod_per_1000": round(per_1000, 6),
    })

yearly_path = OUT_DIR / "hod_visibility_yearly.csv"
with yearly_path.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=yearly_rows[0].keys())
    writer.writeheader()
    writer.writerows(yearly_rows)

# 2. 5年区切り結果
bin_rows = []
for start in range(START_YEAR, END_YEAR + 1, BIN_SIZE):
    end = min(start + BIN_SIZE - 1, END_YEAR)
    years = range(start, end + 1)

    total = sum(total_by_year[y] for y in years)
    target = sum(target_by_year[y] for y in years)
    per_1000 = target / total * 1000 if total else 0

    bin_rows.append({
        "period": f"{start}-{end}",
        "ll_total": total,
        "hod_mentions": target,
        "hod_per_1000": round(per_1000, 6),
    })

bins_path = OUT_DIR / "hod_visibility_5year_bins.csv"
with bins_path.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=bin_rows[0].keys())
    writer.writeheader()
    writer.writerows(bin_rows)

# 3. 該当タイトル一覧
records_path = OUT_DIR / "hod_title_mentions.csv"
with records_path.open("w", encoding="utf-8", newline="") as f:
    fieldnames = ["year", "title", "creator", "discipline"]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(sorted(target_records, key=lambda r: (r["year"], r["title"])))

# 4. ターミナルにも表示
print("Period | L&L total | HoD mentions | HoD per 1,000")
print("-" * 60)
for row in bin_rows:
    print(
        f"{row['period']} | {row['ll_total']:>9,} | "
        f"{row['hod_mentions']:>4} | {row['hod_per_1000']:>8.3f}"
    )

print()
print(f"Saved: {yearly_path}")
print(f"Saved: {bins_path}")
print(f"Saved: {records_path}")
