import csv
import re
import gzip
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HF_PATH = Path("/mnt/d/hathitrust/hathi_full_20260501.txt.gz")
TARGETS = ROOT / "audit" / "hathitrust_retry_3_corrected_metadata.tsv"
OUT = ROOT / "audit" / "hathitrust_retry_3_corrected_results.tsv"

PD_CODES = {"pd", "pdus", "cc-by", "cc-by-nd", "cc-by-sa", "cc-zero"}


def normalize_title(t):
    if not t:
        return ""
    t = t.split(":")[0].split(";")[0].split("/")[0]
    t = t.lower()
    t = unicodedata.normalize("NFKD", t)
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\b(the|a|an)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def author_last(a):
    if not a:
        return ""
    a = a.lower().strip()
    has_comma = "," in a
    a = re.sub(r"[^\w\s]", " ", a)
    parts = [p for p in a.split() if len(p) > 2]
    if not parts:
        return ""
    return parts[0] if has_comma else parts[-1]


targets = {}

with open(TARGETS, encoding="utf-8") as f:
    for r in csv.DictReader(f, delimiter="\t"):
        wk = r["work_key"].replace("/works/", "")
        targets[wk] = {
            "work_key": wk,
            "title": r["title"],
            "author_name": r["author_name"],
            "title_norm": normalize_title(r["title"]),
            "author_last": author_last(r["author_name"]),
            "htid_count": 0,
            "pd_count": 0,
            "sample_htids": [],
            "matched_titles": set(),
            "matched_authors": set(),
        }

print("Targets:")
for x in targets.values():
    print(
        f'  {x["work_key"]}: '
        f'{x["title"]} / {x["author_name"]} '
        f'[{x["title_norm"]} / {x["author_last"]}]'
    )

processed = 0

with gzip.open(HF_PATH, "rt", encoding="utf-8", errors="replace") as f:
    for line in f:
        processed += 1

        if processed % 2_000_000 == 0:
            print(f"{processed:,} lines processed...")

        parts = line.rstrip("\n").split("\t")
        if len(parts) < 25:
            continue

        htid = parts[0]
        rights = parts[2]
        title = parts[11] if len(parts) > 11 else ""
        year_s = parts[16] if len(parts) > 16 else ""
        lang = parts[18] if len(parts) > 18 else ""
        author = parts[-1]

        if lang != "eng":
            continue

        yr = int(year_s) if year_s.isdigit() else None
        if yr and not (1870 <= yr <= 1960):
            continue

        nt = normalize_title(title)
        if not nt:
            continue

        al = author_last(author)

        for x in targets.values():
            if nt != x["title_norm"]:
                continue

            # 今回は corrected author を必須にする。
            # 著者情報のないHathiFiles行は採用しない。
            if not al:
                continue

            if x["author_last"] not in al and al not in x["author_last"]:
                continue

            x["htid_count"] += 1

            if rights in PD_CODES:
                x["pd_count"] += 1

            if len(x["sample_htids"]) < 5:
                x["sample_htids"].append(htid)

            x["matched_titles"].add(title)
            if author:
                x["matched_authors"].add(author)


fieldnames = [
    "work_key",
    "title",
    "author_name",
    "htid_count",
    "pd_count",
    "sample_htids",
    "matched_titles",
    "matched_authors",
    "source",
]

with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
    w.writeheader()

    for x in targets.values():
        w.writerow({
            "work_key": x["work_key"],
            "title": x["title"],
            "author_name": x["author_name"],
            "htid_count": x["htid_count"],
            "pd_count": x["pd_count"],
            "sample_htids": "|".join(x["sample_htids"]),
            "matched_titles": " || ".join(sorted(x["matched_titles"])),
            "matched_authors": " || ".join(sorted(x["matched_authors"])),
            "source": "hathifiles_corrected_metadata_retry",
        })

print("\nRESULTS")
for x in targets.values():
    print(
        f'{x["title"]} / {x["author_name"]}: '
        f'htid={x["htid_count"]}, pd={x["pd_count"]}'
    )
    print("  titles:", " || ".join(sorted(x["matched_titles"])))
    print("  authors:", " || ".join(sorted(x["matched_authors"])))

print("\nCreated:", OUT)
