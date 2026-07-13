import csv
import json
import time
import requests
from pathlib import Path
from datetime import datetime

OUT_DIR = Path("derived/dh_reception")
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "haruka0221@canon-pipeline"}
BASE = "https://api.openalex.org/works"
PERIOD = "2016-2025"
YEAR_FILTER = "publication_year:2016-2025"

journals = {
    "PMLA": {
        "issn": "0030-8129",
        "position": "英文学・MLA",
    },
    "ELH": {
        "issn": "0013-8304",
        "position": "英文学",
    },
    "Novel": {
        "issn": "0029-5132",
        "position": "小説研究",
    },
    "Critical Inquiry": {
        "issn": "0093-1896",
        "position": "批評理論",
    },
    "Modernism/modernity": {
        "issn": "1071-6068",
        "position": "モダニズム",
    },
    "Journal of Modern Literature": {
        "issn": "0022-281X",
        "position": "20世紀文学",
    },
    "Shakespeare Quarterly": {
        "issn": "0037-3222",
        "position": "近世",
    },
    "Victorian Studies": {
        "issn": "0042-5222",
        "position": "ヴィクトリア朝",
    },
    "English Literature in Transition 1880–1920": {
        "issn": "0013-8339",
        "position": "後期ヴィクトリア朝〜20世紀初頭",
    },
    "Cultural Analytics": {
        "issn": "2371-4549",
        "position": "比較：計量・DH系",
    },
    "Digital Scholarship in the Humanities": {
        "issn": "2055-7671",
        "position": "比較：DH専門誌",
    },
    "American Historical Review": {
        "issn": "0002-8762",
        "position": "比較：歴史学",
    },
}

keywords = [
    "digital humanities",
    "distant reading",
    "computational literary",
    "text mining",
    "stylometry",
    "topic model",
]

def get_json(params, retries=3):
    for i in range(retries):
        try:
            r = requests.get(BASE, params=params, headers=HEADERS, timeout=40)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if i == retries - 1:
                raise
            print(f"  retry {i+1}/{retries}: {e}")
            time.sleep(2)
    raise RuntimeError("unreachable")

def get_total_count(issn):
    data = get_json({
        "filter": f"primary_location.source.issn:{issn},{YEAR_FILTER}",
        "per-page": 1,
    })
    return data.get("meta", {}).get("count", 0)

def get_keyword_hits(issn, keyword):
    hits = {}
    cursor = "*"

    while True:
        data = get_json({
            "filter": f"primary_location.source.issn:{issn},{YEAR_FILTER}",
            "search": keyword,
            "per-page": 200,
            "cursor": cursor,
            "select": "id,title,publication_year,type,doi",
        })

        for w in data.get("results", []):
            wid = w.get("id")
            if wid:
                hits[wid] = {
                    "openalex_id": wid,
                    "title": w.get("title") or "",
                    "publication_year": w.get("publication_year") or "",
                    "type": w.get("type") or "",
                    "doi": w.get("doi") or "",
                }

        next_cursor = data.get("meta", {}).get("next_cursor")
        if not next_cursor or next_cursor == cursor:
            break

        cursor = next_cursor
        time.sleep(0.2)

    return hits

summary_rows = []
detail_rows = []

print("\nOpenAlex DH keyword search")
print(f"Period: {PERIOD}")
print("Keywords:", " / ".join(keywords))
print("=" * 80)

for journal, meta in journals.items():
    issn = meta["issn"]
    position = meta["position"]

    print(f"\n{journal} ({issn})")
    total = get_total_count(issn)
    print(f"  total works: {total}")

    dedup = {}
    kw_counts = {}

    for kw in keywords:
        hits = get_keyword_hits(issn, kw)
        kw_counts[kw] = len(hits)
        print(f"  {kw}: {len(hits)}")

        for wid, rec in hits.items():
            if wid not in dedup:
                dedup[wid] = {
                    **rec,
                    "journal": journal,
                    "issn": issn,
                    "position": position,
                    "keywords": [],
                }
            dedup[wid]["keywords"].append(kw)

        time.sleep(0.3)

    hit_count = len(dedup)
    pct = (hit_count / total * 100) if total else 0.0
    slide_format = f"{hit_count}/{total} = {pct:.1f}%"

    summary = {
        "journal": journal,
        "issn": issn,
        "position": position,
        "period": PERIOD,
        "total_works": total,
        "dedup_keyword_hits": hit_count,
        "pct": f"{pct:.1f}",
        "slide_format": slide_format,
    }

    for kw in keywords:
        summary[f"raw_{kw.replace(' ', '_')}"] = kw_counts[kw]

    summary_rows.append(summary)

    for rec in sorted(
        dedup.values(),
        key=lambda x: (x["publication_year"] or 0, x["title"]),
        reverse=True,
    ):
        detail_rows.append({
            "journal": rec["journal"],
            "issn": rec["issn"],
            "position": rec["position"],
            "publication_year": rec["publication_year"],
            "type": rec["type"],
            "title": rec["title"],
            "doi": rec["doi"],
            "keywords": "|".join(sorted(set(rec["keywords"]))),
            "openalex_id": rec["openalex_id"],
        })

    print(f"  DEDUP: {slide_format}")

summary_path = OUT_DIR / "openalex_dh_keyword_summary_2016_2025.tsv"
detail_path = OUT_DIR / "openalex_dh_keyword_hits_2016_2025.tsv"
html_path = OUT_DIR / "openalex_dh_keyword_summary_rows.html"
metadata_path = OUT_DIR / "openalex_dh_keyword_search_metadata.json"

with summary_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()), delimiter="\t")
    writer.writeheader()
    writer.writerows(summary_rows)

with detail_path.open("w", newline="", encoding="utf-8") as f:
    fieldnames = [
        "journal",
        "issn",
        "position",
        "publication_year",
        "type",
        "title",
        "doi",
        "keywords",
        "openalex_id",
    ]
    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
    writer.writeheader()
    writer.writerows(detail_rows)

with html_path.open("w", encoding="utf-8") as f:
    for row in summary_rows:
        f.write("      <tr>\n")
        f.write(f"        <td class=\"hi\">{row['journal']}</td>\n")
        f.write(f"        <td class=\"n\">{row['slide_format']}</td>\n")
        f.write("        <td>OpenAlex検索上限値。重複除去済み。実践論文数ではない</td>\n")
        f.write("      </tr>\n\n")

metadata = {
    "created_at": datetime.now().isoformat(timespec="seconds"),
    "period": PERIOD,
    "openalex_endpoint": BASE,
    "filter_template": "primary_location.source.issn:{issn},publication_year:2016-2025",
    "search_method": "For each journal and each keyword, retrieve OpenAlex works using search=keyword; deduplicate by OpenAlex work id within each journal.",
    "keywords": keywords,
    "journals": journals,
    "outputs": {
        "summary": str(summary_path),
        "detail": str(detail_path),
        "html_rows": str(html_path),
    },
    "note": "Counts are upper-bound keyword hits, not verified DH practice articles. They may include book reviews, special issues, general uses of terms, and false positives.",
}

with metadata_path.open("w", encoding="utf-8") as f:
    json.dump(metadata, f, ensure_ascii=False, indent=2)

print("\n" + "=" * 80)
print("DONE")
print("=" * 80)
print(f"Summary TSV: {summary_path}")
print(f"Detail TSV : {detail_path}")
print(f"HTML rows  : {html_path}")
print(f"Metadata   : {metadata_path}")

print("\nSlide format:")
for row in summary_rows:
    print(f"{row['journal']}: {row['slide_format']}")
