import csv
from pathlib import Path

JSTOR_TOTALS = Path("derived/jstor_work_comparison/work_visibility_totals.csv")
OS_MATCHES = Path("derived/open_syllabus/open_syllabus_target_matches.csv")
OUT = Path("derived/open_syllabus/jstor_open_syllabus_work_comparison.csv")

OUT.parent.mkdir(parents=True, exist_ok=True)

with JSTOR_TOTALS.open(encoding="utf-8-sig", newline="") as f:
    jstor_rows = {r["slug"]: r for r in csv.DictReader(f)}

with OS_MATCHES.open(encoding="utf-8-sig", newline="") as f:
    os_rows = {r["slug"]: r for r in csv.DictReader(f)}

slugs = sorted(set(jstor_rows) | set(os_rows))

rows = []
for slug in slugs:
    j = jstor_rows.get(slug, {})
    o = os_rows.get(slug, {})

    rows.append({
        "slug": slug,
        "work_title": j.get("work_title") or o.get("work_title"),
        "author": j.get("author") or o.get("author"),
        "first_pub_year": j.get("first_pub_year") or o.get("first_pub_year"),
        "jstor_mentions_1940_2019": j.get("mentions_1940_2019", ""),
        "jstor_mentions_per_1000": j.get("mentions_per_1000", ""),
        "open_syllabus_rank": o.get("open_syllabus_rank", ""),
        "open_syllabus_appearances": o.get("appearances", ""),
        "open_syllabus_score": o.get("score", ""),
        "open_syllabus_matched": o.get("matched", ""),
    })

with OUT.open("w", encoding="utf-8", newline="") as f:
    fieldnames = [
        "slug", "work_title", "author", "first_pub_year",
        "jstor_mentions_1940_2019", "jstor_mentions_per_1000",
        "open_syllabus_rank", "open_syllabus_appearances",
        "open_syllabus_score", "open_syllabus_matched",
    ]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print("=== JSTOR x Open Syllabus comparison ===")
for r in rows:
    print(
        f"{r['work_title']:<45} "
        f"JSTOR={r['jstor_mentions_1940_2019']:<5} "
        f"per1000={r['jstor_mentions_per_1000']:<8} "
        f"OS_rank={r['open_syllabus_rank']:<4} "
        f"OS_app={r['open_syllabus_appearances']}"
    )

print()
print(f"Saved: {OUT}")
