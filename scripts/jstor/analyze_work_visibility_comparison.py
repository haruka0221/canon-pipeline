import argparse
import csv
import json
from pathlib import Path
from collections import Counter, defaultdict

DEFAULT_INPUT = Path("derived/jstor_ll_articles.jsonl")
DEFAULT_TARGETS = Path("data/manual/work_targets_1880_1950.csv")
DEFAULT_OUT_DIR = Path("derived/jstor_work_comparison")

START_YEAR = 1940
END_YEAR = 2019
BIN_SIZE = 5


def load_targets(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["phrase"] = r["phrase"].lower().strip()
    return rows


def main():
    parser = argparse.ArgumentParser(
        description="Compare JSTOR L&L title visibility for selected works."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    targets = load_targets(args.targets)

    total_by_year = Counter()
    counts = {t["slug"]: Counter() for t in targets}
    records = defaultdict(list)

    with args.input.open(encoding="utf-8") as f:
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
            title_l = title.lower()
            creator = article.get("creator", "")
            discipline = article.get("discipline", "")

            total_by_year[year] += 1

            for t in targets:
                if t["phrase"] in title_l:
                    slug = t["slug"]
                    counts[slug][year] += 1
                    records[slug].append({
                        "slug": slug,
                        "work_title": t["work_title"],
                        "year": year,
                        "article_title": title,
                        "creator": creator,
                        "discipline": discipline,
                    })

    # 5-year bins
    rows = []
    for t in targets:
        slug = t["slug"]
        for start in range(START_YEAR, END_YEAR + 1, BIN_SIZE):
            end = min(start + BIN_SIZE - 1, END_YEAR)
            years = range(start, end + 1)

            total = sum(total_by_year[y] for y in years)
            n = sum(counts[slug][y] for y in years)
            per_1000 = n / total * 1000 if total else 0

            rows.append({
                "slug": slug,
                "work_title": t["work_title"],
                "author": t["author"],
                "first_pub_year": t["first_pub_year"],
                "period": f"{start}-{end}",
                "ll_total": total,
                "mentions": n,
                "mentions_per_1000": round(per_1000, 6),
            })

    out_bins = args.out_dir / "work_visibility_5year_bins.csv"
    with out_bins.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "slug", "work_title", "author", "first_pub_year",
            "period", "ll_total", "mentions", "mentions_per_1000"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Overall totals
    total_rows = []
    for t in targets:
        slug = t["slug"]
        n = sum(counts[slug].values())
        total = sum(total_by_year.values())
        per_1000 = n / total * 1000 if total else 0

        total_rows.append({
            "slug": slug,
            "work_title": t["work_title"],
            "author": t["author"],
            "first_pub_year": t["first_pub_year"],
            "mentions_1940_2019": n,
            "ll_total_1940_2019": total,
            "mentions_per_1000": round(per_1000, 6),
        })

    total_rows = sorted(total_rows, key=lambda r: r["mentions_1940_2019"], reverse=True)

    out_totals = args.out_dir / "work_visibility_totals.csv"
    with out_totals.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "slug", "work_title", "author", "first_pub_year",
            "mentions_1940_2019", "ll_total_1940_2019", "mentions_per_1000"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(total_rows)

    # Records
    rec_rows = []
    for slug, items in records.items():
        rec_rows.extend(items)

    out_records = args.out_dir / "work_visibility_records.csv"
    with out_records.open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["slug", "work_title", "year", "article_title", "creator", "discipline"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(rec_rows, key=lambda r: (r["slug"], r["year"], r["article_title"])))

    print("=== JSTOR L&L work visibility totals, 1940-2019 ===")
    for r in total_rows:
        print(
            f"{r['work_title']:<45} "
            f"{r['mentions_1940_2019']:>5} "
            f"({r['mentions_per_1000']:.3f} per 1,000)"
        )

    print()
    print(f"Saved: {out_bins}")
    print(f"Saved: {out_totals}")
    print(f"Saved: {out_records}")


if __name__ == "__main__":
    main()
