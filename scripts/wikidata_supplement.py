"""
Wikidata SPARQL 補完スクリプト
================================
canonical 98件のうち wikidata_sitelinks.tsv で QID が未取得の62件について、
タイトル + 著者姓でWikidata SPARQLを叩いてQIDとsitelink数を補完する。

既知の問題3件（FORCE_MAPバグ）は除外して処理する：
  OL15345521W (The Good Soldier → Hašek誤登録)
  OL15062619W (Dracula → Greenberg誤登録)
  OL9056552W  (The Prisoner of Zenda → Wear誤登録)

Outputs:
  derived/wikidata_sitelinks_supplemented.tsv  -- 元ファイル + 補完結果でQIDを更新
  derived/wikidata_supplement_log.tsv          -- 補完試行の詳細ログ

Usage:
  python3 scripts/wikidata_supplement.py [--dry-run] [--limit N]

--dry-run : クエリを実行せず対象リストだけ表示
--limit N : 最初のN件だけ処理（テスト用）
"""

import argparse
import re
import time
import urllib.parse
import urllib.request
import json
from pathlib import Path

import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "derived"

JSTOR_PATH = DERIVED / "jstor_mentions.tsv"
WD_PATH    = DERIVED / "wikidata_sitelinks.tsv"
OUT_PATH   = DERIVED / "wikidata_sitelinks_supplemented.tsv"
LOG_PATH   = DERIVED / "wikidata_supplement_log.tsv"

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# FORCE_MAPバグ: 誤ったwork_keyのため補完不可 → スキップ
BAD_FORCE_MAP = {
    "/works/OL15345521W",  # Good Soldier → Hašek
    "/works/OL15062619W",  # Dracula → Greenberg
    "/works/OL9056552W",   # Prisoner of Zenda → Wear
}

# ── Normalization ──────────────────────────────────────────────────────────────

def normalise_key(s: str) -> str:
    s = str(s).strip()
    if not s.startswith("/works/"):
        s = "/works/" + s
    return s


_LEADING_ART = re.compile(r'^(the|a|an)\s+', re.IGNORECASE)
_NON_ALNUM   = re.compile(r'[^a-z0-9\s]')
_MULTI_SPC   = re.compile(r'\s+')

def norm_title(t: str) -> str:
    t = str(t).lower().strip()
    t = _LEADING_ART.sub("", t)
    t = _NON_ALNUM.sub(" ", t)
    t = _MULTI_SPC.sub(" ", t).strip()
    return t

def extract_last_name(author: str) -> str:
    """Extract last name: handles 'Last, First' and 'First Last' formats."""
    author = str(author).strip()
    if "," in author:
        return author.split(",")[0].strip().lower()
    parts = author.strip().split()
    return parts[-1].lower() if parts else ""

# ── SPARQL query ───────────────────────────────────────────────────────────────

def sparql_query(query: str, retries: int = 3) -> list[dict]:
    """Execute SPARQL query against Wikidata. Returns list of result bindings."""
    params = urllib.parse.urlencode({
        "query": query,
        "format": "json"
    })
    url = f"{SPARQL_ENDPOINT}?{params}"
    headers = {
        "User-Agent": "canon-pipeline/1.0 (doctoral research; contact via GitHub haruka0221/canon-pipeline)",
        "Accept": "application/sparql-results+json"
    }
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["results"]["bindings"]
        except Exception as e:
            if attempt < retries - 1:
                wait = 10 * (attempt + 1)
                print(f"    [retry {attempt+1}] {e} — waiting {wait}s")
                time.sleep(wait)
            else:
                print(f"    [FAIL] {e}")
                return []
    return []


def fetch_by_ol_key(ol_key: str) -> list[dict]:
    """
    Strategy 1: P648 (Open Library Work ID) の直接検索
    ol_key から '/works/' プレフィックスを除いたIDで検索
    """
    bare = ol_key.replace("/works/", "")
    query = f"""
SELECT ?item (COUNT(?sitelink) AS ?sitelink_count) WHERE {{
  ?item wdt:P648 "{bare}" .
  OPTIONAL {{ ?sitelink schema:about ?item . }}
}}
GROUP BY ?item
"""
    return sparql_query(query)


def fetch_by_title_author(title: str, last_name: str) -> list[dict]:
    """
    Strategy 2: タイトル文字列検索 + 著者姓フィルタ
    rdfs:label での完全一致 (英語) + 著者のfamilyName照合
    """
    # escape quotes for SPARQL
    title_esc = title.replace('"', '\\"')
    query = f"""
SELECT ?item ?itemLabel (COUNT(?sitelink) AS ?sitelink_count) WHERE {{
  ?item wdt:P31 wd:Q7725634 .  # instance of: literary work
  ?item rdfs:label "{title_esc}"@en .
  ?item wdt:P50 ?author .
  ?author wdt:P734 ?familyName .
  ?familyName rdfs:label ?fnLabel .
  FILTER(LANG(?fnLabel) = "en")
  FILTER(CONTAINS(LCASE(?fnLabel), "{last_name}"))
  OPTIONAL {{ ?sitelink schema:about ?item . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
GROUP BY ?item ?itemLabel
LIMIT 5
"""
    return sparql_query(query)


def fetch_sitelink_count(qid: str) -> int:
    """QIDが分かっている場合にsitelink数だけ取得"""
    query = f"""
SELECT (COUNT(?sitelink) AS ?cnt) WHERE {{
  BIND(wd:{qid} AS ?item)
  ?sitelink schema:about ?item .
}}
"""
    results = sparql_query(query)
    if results:
        return int(results[0]["cnt"]["value"])
    return 0

# ── Main processing ────────────────────────────────────────────────────────────

def build_target_list(jstor_df: pd.DataFrame, wd_df: pd.DataFrame) -> pd.DataFrame:
    """QID未取得のcanonical作品62件を特定する"""
    wd_norm = wd_df.copy()
    wd_norm["work_key_norm"] = wd_norm["work_id"].apply(normalise_key)

    canon = jstor_df[jstor_df["canonical"] == 1][
        ["work_id", "title", "author"]
    ].copy()
    canon["work_key_norm"] = canon["work_id"].apply(normalise_key)

    merged = canon.merge(
        wd_norm[["work_key_norm", "qid", "sitelink_count"]],
        on="work_key_norm", how="left"
    )

    # QIDなし かつ BAD_FORCE_MAPでない
    targets = merged[
        merged["qid"].isna() &
        ~merged["work_key_norm"].isin(BAD_FORCE_MAP)
    ].copy()

    targets["last_name"] = targets["author"].apply(extract_last_name)
    targets["title_norm"] = targets["title"].apply(norm_title)
    return targets.reset_index(drop=True)


def process_one(row: pd.Series) -> dict:
    """1作品についてSPARQL補完を試行。結果を辞書で返す"""
    result = {
        "work_key": row["work_key_norm"],
        "title": row["title"],
        "author": row["author"],
        "last_name": row["last_name"],
        "qid_found": None,
        "sitelink_count": 0,
        "strategy": "none",
        "status": "not_found",
    }

    # Strategy 1: P648 直接検索
    bindings = fetch_by_ol_key(row["work_key_norm"])
    if bindings:
        b = bindings[0]
        qid = b["item"]["value"].split("/")[-1]
        cnt = int(b.get("sitelink_count", {}).get("value", 0))
        result.update({"qid_found": qid, "sitelink_count": cnt,
                        "strategy": "P648", "status": "ok"})
        return result

    time.sleep(1.0)  # Wikidata rate limit 配慮

    # Strategy 2: タイトル + 著者姓
    bindings2 = fetch_by_title_author(row["title"], row["last_name"])
    if bindings2:
        b = bindings2[0]
        qid = b["item"]["value"].split("/")[-1]
        cnt = int(b.get("sitelink_count", {}).get("value", 0))
        result.update({"qid_found": qid, "sitelink_count": cnt,
                        "strategy": "title+author", "status": "ok"})
        return result

    result["status"] = "not_found"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    print("Loading files...")
    jstor_df = pd.read_csv(JSTOR_PATH, sep="\t", low_memory=False)
    wd_df    = pd.read_csv(WD_PATH,    sep="\t", low_memory=False)

    targets = build_target_list(jstor_df, wd_df)
    print(f"補完対象: {len(targets)} 件 (BAD_FORCE_MAP 3件は除外済み)")
    print(targets[["work_key_norm", "title", "author"]].to_string(index=False))

    if args.dry_run:
        print("\n--dry-run: クエリ実行せず終了")
        return

    if args.limit:
        targets = targets.head(args.limit)
        print(f"\n--limit {args.limit}: 先頭{args.limit}件のみ処理")

    print(f"\n処理開始 ({len(targets)} 件) — Wikidata SPARQL")
    print("Rate limit対策: 1件ごとに1〜2秒待機します\n")

    log_rows = []
    for i, row in targets.iterrows():
        print(f"  [{i+1:3d}/{len(targets)}] {row['title'][:45]:45s} ({row['last_name']})", end=" ... ")
        res = process_one(row)
        status_str = f"{res['status']} / {res['strategy']}"
        if res["qid_found"]:
            print(f"✓ {res['qid_found']} sitelinks={res['sitelink_count']}")
        else:
            print("✗ not found")
        log_rows.append(res)
        time.sleep(1.5)

    log_df = pd.DataFrame(log_rows)
    log_df.to_csv(LOG_PATH, sep="\t", index=False)
    print(f"\nログ → {LOG_PATH}")

    # 成功件数
    ok = log_df[log_df["status"] == "ok"]
    print(f"成功: {len(ok)}/{len(targets)} 件")
    print(f"  P648経由: {(ok['strategy']=='P648').sum()} 件")
    print(f"  title+author経由: {(ok['strategy']=='title+author').sum()} 件")

    # wikidata_sitelinks.tsv に補完結果をマージして保存
    wd_out = wd_df.copy()
    wd_out["work_key_norm"] = wd_out["work_id"].apply(normalise_key)

    for _, r in ok.iterrows():
        mask = wd_out["work_key_norm"] == r["work_key"]
        if mask.any():
            wd_out.loc[mask, "qid"]            = r["qid_found"]
            wd_out.loc[mask, "sitelink_count"] = r["sitelink_count"]
        else:
            # 行ごと存在しない場合（ありえないはずだが念のため）
            bare = r["work_key"].replace("/works/", "")
            wd_out = pd.concat([wd_out, pd.DataFrame([{
                "work_id": bare,
                "work_key_norm": r["work_key"],
                "qid": r["qid_found"],
                "sitelink_count": r["sitelink_count"],
            }])], ignore_index=True)

    wd_out.drop(columns=["work_key_norm"], inplace=True)
    wd_out.to_csv(OUT_PATH, sep="\t", index=False)
    print(f"補完済みファイル → {OUT_PATH}")

    # 補完後のcanonical coverage確認
    wd_out["work_key_norm"] = wd_out["work_id"].apply(normalise_key)
    canon_keys = set(
        jstor_df[jstor_df["canonical"]==1]["work_id"].apply(normalise_key)
    )
    wd_canon = wd_out[wd_out["work_key_norm"].isin(canon_keys)]
    n_with_qid = wd_canon["qid"].notna().sum()
    n_with_sl  = (wd_canon["sitelink_count"] > 0).sum()
    print(f"\n補完後 canonical coverage:")
    print(f"  QIDあり:          {n_with_qid}/98")
    print(f"  sitelink > 0:     {n_with_sl}/98")
    print(f"  BAD_FORCE_MAP除く実質最大: 95")


if __name__ == "__main__":
    main()