"""
Wikidata 補完 Round 2 (revised) — wbsearchentities API 使用
============================================================
SPARQLエンドポイントの代わりにWikidata Action API (wbsearchentities) を使用。
軽量・高速・タイムアウトしない。

手順:
  1. wbsearchentities でタイトル検索 → QID候補リストを取得
  2. 各候補の P50 (著者) を wbgetentities で確認 → 著者姓でフィルタ
  3. 一致したQIDのサイトリンク数を wbgetentities で取得

Output:
  derived/wikidata_supplement_log_r2.tsv
  derived/wikidata_sitelinks_final.tsv   (Round 1 + Round 2 統合)

Usage:
  python3 scripts/wikidata_supplement_r2.py [--dry-run] [--limit N]
"""

import argparse
import re
import time
import urllib.parse
import urllib.request
import json
from pathlib import Path

import pandas as pd

ROOT    = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "derived"

JSTOR_PATH  = DERIVED / "jstor_mentions.tsv"
WD_R1_PATH  = DERIVED / "wikidata_sitelinks_supplemented.tsv"
LOG_PATH    = DERIVED / "wikidata_supplement_log_r2.tsv"
OUT_PATH    = DERIVED / "wikidata_sitelinks_final.tsv"

WD_API = "https://www.wikidata.org/w/api.php"

BAD_FORCE_MAP = {
    "/works/OL15345521W",
    "/works/OL15062619W",
    "/works/OL9056552W",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def normalise_key(s):
    s = str(s).strip()
    return s if s.startswith("/works/") else "/works/" + s

def extract_last_name(author):
    author = str(author).strip()
    if "," in author:
        return author.split(",")[0].strip().lower()
    parts = author.strip().split()
    return parts[-1].lower() if parts else ""

def norm_title_search(title):
    t = re.sub(r"['\u2018\u2019\u201c\u201d]", "", title)
    t = re.sub(r'[^a-zA-Z0-9\s]', ' ', t)
    t = re.sub(r'^\s*(the|a|an)\s+', '', t, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', t).strip()

def api_get(params, retries=3):
    params["format"] = "json"
    url = WD_API + "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": "canon-pipeline/1.0 (doctoral research; github: haruka0221)"}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            wait = 5 * (attempt + 1)
            if attempt < retries - 1:
                print(f"      [retry {attempt+1}] {e} — wait {wait}s")
                time.sleep(wait)
            else:
                print(f"      [FAIL] {e}")
                return {}
    return {}

# ── API calls ─────────────────────────────────────────────────────────────────

def search_by_title(title, limit=5):
    kw = norm_title_search(title)
    data = api_get({
        "action": "wbsearchentities",
        "search": kw,
        "language": "en",
        "type": "item",
        "limit": str(limit),
    })
    return [r["id"] for r in data.get("search", [])]

def get_entities(qids):
    if not qids:
        return {}
    data = api_get({
        "action": "wbgetentities",
        "ids": "|".join(qids),
        "props": "claims|sitelinks|labels",
        "languages": "en",
    })
    return data.get("entities", {})

def get_family_names(author_qids):
    """著者QIDからP734(family name)のラベルを取得"""
    names = []
    for aqid in author_qids[:3]:
        data = api_get({
            "action": "wbgetentities",
            "ids": aqid,
            "props": "claims",
        })
        ent = data.get("entities", {}).get(aqid, {})
        fn_claims = ent.get("claims", {}).get("P734", [])
        fn_qids = [
            c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            for c in fn_claims if c.get("mainsnak", {}).get("datavalue")
        ]
        fn_qids = [q for q in fn_qids if q]
        if fn_qids:
            fn_data = api_get({
                "action": "wbgetentities",
                "ids": "|".join(fn_qids[:2]),
                "props": "labels",
                "languages": "en",
            })
            for fqid in fn_qids[:2]:
                lbl = fn_data.get("entities", {}).get(fqid, {}) \
                             .get("labels", {}).get("en", {}).get("value", "")
                if lbl:
                    names.append(lbl.lower())
        time.sleep(0.3)
    return names

def find_qid(title, last_name, work_key):
    # Step 1: タイトル検索
    candidates = search_by_title(title)
    if not candidates:
        return None
    time.sleep(0.5)

    # Step 2: 著者確認
    entities = get_entities(candidates)
    time.sleep(0.5)

    for qid in candidates:
        ent = entities.get(qid, {})
        sl_count = len(ent.get("sitelinks", {}))

        author_claims = ent.get("claims", {}).get("P50", [])
        author_qids = [
            c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            for c in author_claims if c.get("mainsnak", {}).get("datavalue")
        ]
        author_qids = [q for q in author_qids if q]

        if not author_qids:
            if sl_count >= 10:
                return {"qid": qid, "sitelink_count": sl_count,
                        "strategy": "title_only_high_sl"}
            continue

        fn_names = get_family_names(author_qids)
        if any(last_name in n for n in fn_names):
            return {"qid": qid, "sitelink_count": sl_count,
                    "strategy": "title+author_api"}

    # フォールバック: sitelink最大候補（閾値10）
    best_qid, best_sl = None, 0
    for qid in candidates:
        sl = len(entities.get(qid, {}).get("sitelinks", {}))
        if sl > best_sl:
            best_sl, best_qid = sl, qid
    if best_sl >= 10:
        return {"qid": best_qid, "sitelink_count": best_sl,
                "strategy": "title_best_sl_fallback"}
    return None

# ── Target list ───────────────────────────────────────────────────────────────

def build_targets(jstor_df, wd_r1):
    wd = wd_r1.copy()
    wd["wk_norm"] = wd["work_id"].apply(normalise_key)
    canon = jstor_df[jstor_df["canonical"] == 1][["work_id","title","author"]].copy()
    canon["wk_norm"] = canon["work_id"].apply(normalise_key)
    merged = canon.merge(wd[["wk_norm","qid","sitelink_count"]], on="wk_norm", how="left")
    targets = merged[
        merged["qid"].isna() & ~merged["wk_norm"].isin(BAD_FORCE_MAP)
    ].copy()
    targets["last_name"] = targets["author"].apply(extract_last_name)
    return targets.reset_index(drop=True)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    jstor_df = pd.read_csv(JSTOR_PATH, sep="\t", low_memory=False)
    wd_r1    = pd.read_csv(WD_R1_PATH, sep="\t", low_memory=False)

    targets = build_targets(jstor_df, wd_r1)
    print(f"Round 2 対象: {len(targets)} 件")
    print(targets[["wk_norm","title","last_name"]].to_string(index=False))

    if args.dry_run:
        print("\n--dry-run: 終了")
        return

    if args.limit:
        targets = targets.head(args.limit)
        print(f"\n--limit {args.limit}: 先頭{args.limit}件")

    print(f"\n処理開始 ({len(targets)} 件)\n")
    log_rows = []

    for i, row in targets.iterrows():
        label = f"{row['title'][:40]:40s} ({row['last_name']})"
        print(f"  [{i+1:2d}/{len(targets)}] {label}", end=" ... ", flush=True)

        result = find_qid(row["title"], row["last_name"], row["wk_norm"])

        if result:
            print(f"✓ {result['qid']} sl={result['sitelink_count']} [{result['strategy']}]")
            log_rows.append({
                "work_key": row["wk_norm"], "title": row["title"],
                "author": row["author"], "last_name": row["last_name"],
                **result, "status": "ok"
            })
        else:
            print("✗ not found")
            log_rows.append({
                "work_key": row["wk_norm"], "title": row["title"],
                "author": row["author"], "last_name": row["last_name"],
                "qid": None, "sitelink_count": 0,
                "strategy": "none", "status": "not_found"
            })

        time.sleep(1.0)

    log_df = pd.DataFrame(log_rows)
    log_df.to_csv(LOG_PATH, sep="\t", index=False)

    ok = log_df[log_df["status"] == "ok"]
    print(f"\nRound 2 成功: {len(ok)}/{len(targets)} 件")
    for strat, cnt in ok["strategy"].value_counts().items():
        print(f"  {strat}: {cnt} 件")

    # Round 1 + Round 2 統合
    wd_out = wd_r1.copy()
    wd_out["wk_norm"] = wd_out["work_id"].apply(normalise_key)
    for _, r in ok.iterrows():
        mask = wd_out["wk_norm"] == r["work_key"]
        if mask.any():
            wd_out.loc[mask, "qid"]            = r["qid"]
            wd_out.loc[mask, "sitelink_count"] = r["sitelink_count"]
    wd_out.drop(columns=["wk_norm"], inplace=True)
    wd_out.to_csv(OUT_PATH, sep="\t", index=False)
    print(f"最終ファイル → {OUT_PATH}")

    # 最終coverage
    wd_out["wk_norm"] = wd_out["work_id"].apply(normalise_key)
    canon_keys = set(jstor_df[jstor_df["canonical"]==1]["work_id"].apply(normalise_key))
    sub = wd_out[wd_out["wk_norm"].isin(canon_keys)]
    print(f"\n最終 canonical coverage:")
    print(f"  QIDあり:       {sub['qid'].notna().sum()}/98")
    print(f"  sitelink > 0:  {(sub['sitelink_count'] > 0).sum()}/98")

    still = sub[sub["qid"].isna() & ~sub["wk_norm"].isin(BAD_FORCE_MAP)]
    if len(still):
        print(f"\n依然未取得 ({len(still)} 件):")
        for _, r in still.iterrows():
            t = jstor_df[jstor_df["work_id"].apply(normalise_key)==r["wk_norm"]]["title"].values
            print(f"  {r['wk_norm']}  {t[0] if len(t) else '?'}")

if __name__ == "__main__":
    main()