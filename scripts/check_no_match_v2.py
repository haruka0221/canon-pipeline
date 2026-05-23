import pandas as pd
import requests
import time

def search_wikidata_api(title):
    """SPARQLではなくWikidata Search APIを使う（軽い）"""
    clean = title.lower()
    clean = clean.replace("textplus - ", "")
    clean = clean.replace(", a novel", "")
    clean = clean.replace(", a story of california", "")
    
    r = requests.get(
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbsearchentities",
            "search": clean,
            "language": "en",
            "type": "item",
            "limit": 5,
            "format": "json"
        },
        headers={"User-Agent": "canon-pipeline/1.0"},
        timeout=10
    )
    results = r.json().get("search", [])
    return [(r["id"], r.get("label",""), r.get("description","")) for r in results]

df = pd.read_csv(
    "/home/haruka221/canon-pipeline/derived/benchmark/filter_baseline_results.tsv",
    sep="\t"
)
full = pd.read_csv(
    "/home/haruka221/canon-pipeline/derived/benchmark/full_eval_130items.tsv",
    sep="\t"
)

no_match = df[df["pred_filter"] == "NO_MATCH"].copy()
no_match = no_match.merge(full[["title","gold_qid_final"]], on="title", how="left")

print(f"NO_MATCH件数: {len(no_match)}\n")

results = []
for _, row in no_match.iterrows():
    try:
        candidates = search_wikidata_api(row["title"])
        gold = row["gold"]
        
        qids = [c[0] for c in candidates]
        correct = gold in qids
        
        if correct:
            status = "✓ 取れた"
            pred = gold
        elif candidates:
            top = candidates[0]
            status = f"✗ 別物: {top[0]} ({top[2][:40]})"
            pred = top[0]
        else:
            status = "→ やはりない"
            pred = "NO_MATCH"
            
        print(f"{row['title'][:45]:45s} {status}")
        results.append({
            "title": row["title"],
            "gold": gold,
            "pred": pred,
            "correct": correct,
            "candidates": str(candidates)
        })
    except Exception as e:
        print(f"{row['title'][:45]:45s} ERROR: {e}")
        results.append({"title": row["title"], "gold": row["gold"],
                       "pred": "ERROR", "correct": False, "candidates": ""})
    time.sleep(1)

result_df = pd.DataFrame(results)
result_df.to_csv(
    "/home/haruka221/canon-pipeline/derived/benchmark/no_match_recheck_v2.tsv",
    sep="\t", index=False
)

correct_n = result_df["correct"].sum()
no_match_n = (result_df["pred"] == "NO_MATCH").sum()
wrong_n = len(result_df) - correct_n - no_match_n

print(f"\n--- 集計 ---")
print(f"取れた（正解）: {correct_n}件")
print(f"やはりない: {no_match_n}件")
print(f"別物を返した: {wrong_n}件")
