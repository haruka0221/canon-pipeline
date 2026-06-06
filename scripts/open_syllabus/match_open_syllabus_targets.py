import argparse
import csv
import re
from pathlib import Path

DEFAULT_OS = Path("data/manual/open_syllabus_english_literature_top.csv")
DEFAULT_TARGETS = Path("data/manual/work_targets_1880_1950.csv")
DEFAULT_OUT = Path("derived/open_syllabus/open_syllabus_target_matches.csv")


def norm(s):
    s = str(s or "").lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_int(s):
    s = str(s or "").replace(",", "").strip()
    if not s:
        return 0
    return int(float(s))


def main():
    parser = argparse.ArgumentParser(
        description="Match selected 1880-1950 fiction targets against Open Syllabus English Literature top list."
    )
    parser.add_argument("--open-syllabus", type=Path, default=DEFAULT_OS)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)

    with args.open_syllabus.open(encoding="utf-8-sig", newline="") as f:
        os_rows = list(csv.DictReader(f))

    with args.targets.open(encoding="utf-8-sig", newline="") as f:
        target_rows = list(csv.DictReader(f))

    out_rows = []

    for t in target_rows:
        target_title_norm = norm(t["work_title"])
        phrase_norm = norm(t["phrase"])

        best = None
        for r in os_rows:
            os_title_norm = norm(r["title"])

            exact = os_title_norm == target_title_norm
            phrase_match = phrase_norm and phrase_norm in os_title_norm
            reverse_match = os_title_norm and os_title_norm in target_title_norm

            if exact or phrase_match or reverse_match:
                best = r
                break

        if best:
            out_rows.append({
                "slug": t["slug"],
                "work_title": t["work_title"],
                "author": t["author"],
                "first_pub_year": t["first_pub_year"],
                "open_syllabus_rank": parse_int(best.get("rank")),
                "open_syllabus_title": best.get("title", ""),
                "open_syllabus_author": best.get("author", ""),
                "appearances": parse_int(best.get("appearances")),
                "score": best.get("score", ""),
                "matched": 1,
            })
        else:
            out_rows.append({
                "slug": t["slug"],
                "work_title": t["work_title"],
                "author": t["author"],
                "first_pub_year": t["first_pub_year"],
                "open_syllabus_rank": "",
                "open_syllabus_title": "",
                "open_syllabus_author": "",
                "appearances": "",
                "score": "",
                "matched": 0,
            })

    with args.out.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "slug", "work_title", "author", "first_pub_year",
            "open_syllabus_rank", "open_syllabus_title", "open_syllabus_author",
            "appearances", "score", "matched"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print("=== Open Syllabus matches ===")
    for r in out_rows:
        if r["matched"]:
            print(
                f"{r['work_title']:<45} "
                f"rank={r['open_syllabus_rank']:<4} "
                f"appearances={r['appearances']}"
            )
        else:
            print(f"{r['work_title']:<45} not found in supplied OS list")

    print()
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
