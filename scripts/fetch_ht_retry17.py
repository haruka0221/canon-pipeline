"""
fetch_ht_retry17.py
===================
htid_count=0 だった17件を OL API でISBN・LCCNを取得し、
HathiTrust Bibliographic API で再挑戦する。

使い方:
  python3 scripts/fetch_ht_retry17.py

出力:
  derived/ht_api_retry17.tsv
"""

import csv, json, time, urllib.request, urllib.error
from pathlib import Path

ROOT     = Path(__file__).resolve().parent.parent
POP_TSV  = ROOT / "derived" / "ol_dump_population_with_author.tsv"
OUT_PATH = ROOT / "derived" / "ht_api_retry17.tsv"

SLEEP    = 1.2
TIMEOUT  = 20
PD_CODES = {"pd", "pdus", "cc-by", "cc-by-nd", "cc-by-sa", "cc-zero"}

# htid=0 だった17件
ZERO_WKS = {
    "OL100203W","OL1168083W","OL1253285W","OL15062619W",
    "OL18397742W","OL19870W","OL20163024W","OL276365W",
    "OL38989822W","OL39453744W","OL43405505W","OL44622934W",
    "OL5138118W","OL65430W","OL6926191W","OL86320W","OL98501W",
}

# ── ユーティリティ ────────────────────────────────────────

def fetch_json(url: str) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "canon-pipeline/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"  [WARN] {url}: {e}")
        return None


def get_identifiers_from_ol(work_key: str) -> dict:
    """
    OL editions API からISBN・LCCNを収集する。
    戻り値: {"isbn": [...], "lccn": [...]}
    """
    url = f"https://openlibrary.org/works/{work_key}/editions.json?limit=20"
    time.sleep(SLEEP)
    data = fetch_json(url)
    if not data:
        return {"isbn": [], "lccn": []}

    isbns, lccns = [], []
    for entry in data.get("entries", []):
        ids = entry.get("identifiers", {})
        isbns += ids.get("isbn_10", []) + ids.get("isbn_13", [])
        isbns += entry.get("isbn_10", []) + entry.get("isbn_13", [])
        lccns += ids.get("lccn", []) + entry.get("lccn", [])

    # 重複除去
    return {
        "isbn": list(dict.fromkeys(isbns))[:5],   # 最大5件
        "lccn": list(dict.fromkeys(lccns))[:5],
    }


def ht_lookup(id_type: str, id_value: str) -> dict | None:
    """
    HathiTrust Bibliographic API を1件叩く。
    id_type: "oclc" | "isbn" | "lccn"
    """
    url = f"https://catalog.hathitrust.org/api/volumes/brief/{id_type}/{id_value}.json"
    time.sleep(SLEEP)
    data = fetch_json(url)
    if not data:
        return None
    items   = data.get("items", [])
    records = data.get("records", {})
    return {
        "htid_count":   len(items),
        "pd_count":     sum(1 for i in items if i.get("rightsCode","") in PD_CODES),
        "record_count": len(records),
        "sample_htids": "|".join(i["htid"] for i in items[:3] if "htid" in i),
        "matched_id":   f"{id_type}:{id_value}",
    }


def try_all_ids(work_key: str, ids: dict) -> dict:
    """ISBN → LCCN の順で試し、最初にヒットした結果を返す。"""
    for id_type in ("isbn", "lccn"):
        for val in ids.get(id_type, []):
            result = ht_lookup(id_type, val)
            if result and result["htid_count"] > 0:
                print(f"    ✓ {id_type}:{val}  htid={result['htid_count']}")
                return result
    return {
        "htid_count": 0, "pd_count": 0, "record_count": 0,
        "sample_htids": "", "matched_id": "NO_MATCH",
    }


# ── メイン ───────────────────────────────────────────────

def main():
    # population から タイトル・著者を取得
    pop = {}
    with open(POP_TSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            wk = row["work_key"].replace("/works/", "")
            if wk in ZERO_WKS:
                pop[wk] = {
                    "title":       row.get("title", ""),
                    "author_name": row.get("author_name", ""),
                    "first_publish_year": row.get("first_publish_year", ""),
                }

    fieldnames = ["work_key", "title", "author_name", "first_publish_year",
                  "htid_count", "pd_count", "record_count",
                  "matched_id", "sample_htids",
                  "isbn_found", "lccn_found"]

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()

        for i, wk in enumerate(sorted(ZERO_WKS), 1):
            meta = pop.get(wk, {})
            title = meta.get("title", "?")
            print(f"\n[{i}/17] {title}  ({wk})")

            # Step1: OL editions から識別子取得
            print(f"  → OL API で識別子取得...")
            ids = get_identifiers_from_ol(wk)
            print(f"    isbn: {ids['isbn'][:3]}  lccn: {ids['lccn'][:3]}")

            # Step2: HathiTrust 再挑戦
            print(f"  → HathiTrust 再挑戦...")
            result = try_all_ids(wk, ids)

            row = {
                "work_key":           wk,
                "title":              title,
                "author_name":        meta.get("author_name", ""),
                "first_publish_year": meta.get("first_publish_year", ""),
                "isbn_found":         "|".join(ids["isbn"]),
                "lccn_found":         "|".join(ids["lccn"]),
            } | {k: result.get(k, "") for k in
                 ["htid_count","pd_count","record_count","matched_id","sample_htids"]}

            writer.writerow(row)

    # ── サマリ ──
    print("\n=== 結果サマリ ===")
    with open(OUT_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    hits  = [r for r in rows if int(r["htid_count"] or 0) > 0]
    zeros = [r for r in rows if int(r["htid_count"] or 0) == 0]
    print(f"復活: {len(hits)}件")
    for r in hits:
        print(f"  ✓ {r['title'][:40]}  htid={r['htid_count']}  via {r['matched_id']}")
    print(f"依然ゼロ: {len(zeros)}件")
    for r in zeros:
        print(f"  ✗ {r['title'][:40]}  isbn={r['isbn_found'][:30]}  lccn={r['lccn_found'][:20]}")


if __name__ == "__main__":
    main()