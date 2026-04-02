"""
Stage 4g: Internet Archive アクセス指標取得
============================================
ol_ocaid_list.tsv のocaidを使い、Internet Archive APIから
各作品のダウンロード数・貸出数を取得する。

指標の意味:
  downloads: 全期間の累計ダウンロード数（著作権切れ作品の公衆アクセス規模）
  loans:     現在の貸出可能冊数（controlled digital lending対象作品）

Outputs:
  derived/ia_access_counts.tsv   -- work_key, ocaid, downloads, loans, ia_available

対象: ol_ocaid_list.tsv の全件（population中ocaidあり作品）
      + canonicalで ocaidなし作品は IA search API でタイトル補完を試みる

Usage:
  python3 scripts/fetch_ia_access.py [--limit N] [--canonical-only]

--limit N:          最初のN件だけ処理（テスト用）
--canonical-only:   canonical 98件のみ処理
"""

import argparse
import time
import urllib.parse
import urllib.request
import json
from pathlib import Path

import pandas as pd

ROOT    = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "derived"

OCAID_PATH  = DERIVED / "ol_ocaid_list.tsv"
JSTOR_PATH  = DERIVED / "jstor_mentions.tsv"
OUT_PATH    = DERIVED / "ia_access_counts.tsv"

IA_META_URL   = "https://archive.org/metadata/{ocaid}"
IA_SEARCH_URL = "https://archive.org/advancedsearch.php"

# ── API helpers ───────────────────────────────────────────────────────────────

def fetch_json(url: str, retries: int = 3) -> dict:
    headers = {"User-Agent": "canon-pipeline/1.0 (doctoral research; github: haruka0221)"}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            wait = 5 * (attempt + 1)
            if attempt < retries - 1:
                time.sleep(wait)
            else:
                return {}
    return {}

def get_ia_stats(ocaid: str) -> dict:
    """
    metadata APIからdownloads等を取得。
    返り値: {"downloads": int, "loans": int, "mediatype": str, "available": bool}
    """
    url = IA_META_URL.format(ocaid=ocaid)
    data = fetch_json(url)
    if not data:
        return {"downloads": 0, "loans": 0, "mediatype": "", "available": False}

    meta = data.get("metadata", {})
    files = data.get("files", [])

    # downloads: item_statsから取得（なければfileサイズから推定しない）
    item_stats = data.get("item_stats", {})
    downloads = item_stats.get("downloads", 0)
    # 旧形式: metadata内にdownloadsがある場合
    if not downloads:
        downloads = meta.get("downloads", 0)
    try:
        downloads = int(downloads)
    except (ValueError, TypeError):
        downloads = 0

    # loans: lending_statusから
    lending = data.get("lending_status", {})
    is_lendable = lending.get("is_lendable", False)
    available   = lending.get("available_to_borrow", False)

    mediatype = meta.get("mediatype", "")

    return {
        "downloads":  downloads,
        "loans":      1 if is_lendable else 0,  # 貸出可能フラグ
        "mediatype":  mediatype,
        "available":  bool(mediatype),  # metadataが返れば存在確認済み
    }

def search_ia_by_title(title: str, author_last: str) -> str | None:
    """
    ocaidなし作品向け: IA full-text searchでタイトル+著者検索 → ocaidを返す
    """
    q = f'title:"{title}" AND creator:"{author_last}" AND mediatype:texts'
    params = urllib.parse.urlencode({
        "q": q,
        "fl[]": "identifier",
        "rows": "3",
        "page": "1",
        "output": "json",
    })
    url = f"{IA_SEARCH_URL}?{params}"
    data = fetch_json(url)
    docs = data.get("response", {}).get("docs", [])
    if docs:
        return docs[0].get("identifier")
    return None

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--canonical-only", action="store_true")
    args = parser.parse_args()

    # 母集団とocaidリストを読み込む
    ocaid_df = pd.read_csv(OCAID_PATH, sep="\t", dtype=str)
    jstor_df = pd.read_csv(JSTOR_PATH, sep="\t")

    print(f"ocaidあり: {len(ocaid_df):,} works")

    # canonicalリスト
    canon_map = dict(zip(
        jstor_df["work_id"].astype(str),
        zip(jstor_df["canonical"], jstor_df["title"], jstor_df["author"])
    ))

    if args.canonical_only:
        canon_keys = set(jstor_df[jstor_df["canonical"]==1]["work_id"].astype(str))
        ocaid_df = ocaid_df[ocaid_df["work_key"].isin(canon_keys)].copy()
        print(f"--canonical-only: {len(ocaid_df)} 件に絞り込み")

        # ocaidなしのcanonical作品をIA検索で補完
        all_canon_keys = set(jstor_df[jstor_df["canonical"]==1]["work_id"].astype(str))
        missing_canon  = all_canon_keys - set(ocaid_df["work_key"])
        if missing_canon:
            print(f"ocaidなしcanonical {len(missing_canon)}件 → IA検索で補完試行")
            extra_rows = []
            for wk in missing_canon:
                info = canon_map.get(wk, (0, "", ""))
                title  = str(info[1])
                author = str(info[2])
                last   = author.split(",")[0].strip() if "," in author else author.split()[-1]
                ocaid  = search_ia_by_title(title, last)
                if ocaid:
                    print(f"  ✓ {title} → {ocaid}")
                    extra_rows.append({"work_key": wk, "ocaid": ocaid})
                time.sleep(0.5)
            if extra_rows:
                ocaid_df = pd.concat(
                    [ocaid_df, pd.DataFrame(extra_rows)], ignore_index=True
                )

    if args.limit:
        ocaid_df = ocaid_df.head(args.limit)
        print(f"--limit {args.limit}: 先頭{args.limit}件")

    print(f"\n処理開始: {len(ocaid_df):,} 件")
    print("(1件あたり約1秒 × 件数 = 推定所要時間)\n")

    results = []
    for i, row in ocaid_df.iterrows():
        wk    = row["work_key"]
        ocaid = str(row["ocaid"]).strip()
        canon_info = canon_map.get(wk, (0, "", ""))
        is_canon = int(canon_info[0])
        title    = str(canon_info[1])[:40] if canon_info[1] else wk[:30]
        flag     = "★" if is_canon else " "

        print(f"  [{i+1:5d}] {flag} {title:40s} ocaid={ocaid[:20]}", end=" ... ", flush=True)

        stats = get_ia_stats(ocaid)

        print(f"dl={stats['downloads']:6d}  lend={stats['loans']}  type={stats['mediatype'][:8]}")

        results.append({
            "work_key":    wk,
            "ocaid":       ocaid,
            "canonical":   is_canon,
            "downloads":   stats["downloads"],
            "is_lendable": stats["loans"],
            "mediatype":   stats["mediatype"],
            "ia_available": stats["available"],
        })

        time.sleep(0.8)

    out_df = pd.DataFrame(results)
    out_df.to_csv(OUT_PATH, sep="\t", index=False)
    print(f"\n→ {OUT_PATH} ({len(out_df):,} 行)")

    # サマリー
    print(f"\n=== Internet Archive アクセス指標 ===")
    print(f"取得成功 (ia_available=True): {out_df['ia_available'].sum():,} / {len(out_df):,}")
    print(f"downloads > 0: {(out_df['downloads']>0).sum():,}")

    can = out_df[out_df["canonical"]==1]
    non = out_df[out_df["canonical"]==0]
    if len(can):
        print(f"\ncanonical:")
        print(f"  downloads 中央値: {can['downloads'].median():.0f}")
        print(f"  downloads 最大値: {can['downloads'].max()}")
        print(f"  downloads > 0:    {(can['downloads']>0).sum()}/{len(can)}")
    if len(non):
        print(f"non-canonical:")
        print(f"  downloads 中央値: {non['downloads'].median():.0f}")
        print(f"  downloads > 0:    {(non['downloads']>0).sum()}/{len(non)}")

    print(f"\nTop 10 by downloads:")
    for _, r in out_df.nlargest(10, "downloads").iterrows():
        flag = "★" if r["canonical"] else " "
        print(f"  {flag} dl={r['downloads']:8,}  {r['work_key']}  ocaid={r['ocaid']}")

if __name__ == "__main__":
    main()