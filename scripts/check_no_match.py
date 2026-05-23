import pandas as pd
import requests
import time

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "canon-pipeline-research/1.0"}

def search_relaxed(title, gold_qid):
    """タイトルを正規化して再検索する"""
    # 正規化：小文字化、サブタイトル除去、プレフィックス除去
    clean = title.lower()
    clean = clean.replace("textplus - ", "")
    clean = clean.replace(", a novel", "")
    clean = clean.replace(", a story of california", "")
    # 最初の単語列だけ使う（30文字）
    clean = clean[:40].strip()
    
    query = f"""
    SELECT ?work ?workLabel WHERE {{
      VALUES ?type {{ wd:Q7725634 wd:Q571 wd:Q8261 wd:Q49084 }}
      ?work wdt:P31 ?type .
      ?work rdfs:label ?workLabel .
      FILTER(LANG(?workLabel) = "en")
      FILTER(LCASE(?workLabel) = "{clean}")
    }}
    LIMIT 5
    """
    
    try:
        r = requests.get(
            SPARQL_ENDPOINT,
            params={"query": query, "format": "json"},
            headers=HEADERS,
            timeout=10
        )
        results = r.json()["results"]["bindings"]
        if results:
            qids = [b["work"]["value"].split("/")[-1] for b in results]
            matched = gold_qid in qids
            return qids[0], matched, "found"
        return "NO_MATCH", False, "not_in_wikidata"
    except Exception as e:
        return "ERROR", False, "error"

# filter_baseline_resultsからNO_MATCHだけ取る
df = pd.read_csv(
    "/home/haruka221/canon-pipeline/derived/benchmark/filter_baseline_results.tsv",
    sep="\t"
)

# full_eval_130からgold_qidも取る
full = pd.read_csv(
    "/home/haruka221/canon-pipeline/derived/benchmark/full_eval_130items.tsv",
    sep="\t"
)

no_match = df[df["pred_filter"] == "NO_MATCH"].copy()
no_match = no_match.merge(
    full[["title", "gold_qid_final", "author"]],
    on="title", how="left"
)

print(f"NO_MATCH件数: {len(no_match)}")
print()

results = []
for _, row in no_match.iterrows():
    pred, correct, reason = search_relaxed(row["title"], row["gold"])
    results.append({
        "title": row["title"],
        "gold": row["gold"],
        "pred_relaxed": pred,
        "correct": correct,
        "reason": reason,
        "sitelink_count": row["sitelink_count"]
    })
    status = "✓ 表記ゆれで取れた" if correct else ("→ やはりない" if reason == "not_in_wikidata" else f"→ 別QID: {pred}")
    print(f"{row['title'][:45]:45s} {status}")
    time.sleep(2)

result_df = pd.DataFrame(results)
result_df.to_csv(
    "/home/haruka221/canon-pipeline/derived/benchmark/no_match_recheck.tsv",
    sep="\t", index=False
)

# 集計
found = result_df[result_df["reason"] == "found"]
not_found = result_df[result_df["reason"] == "not_in_wikidata"]
correct = result_df[result_df["correct"] == True]

print(f"\n--- 集計 ---")
print(f"表記ゆれで取れた（正解）: {correct['correct'].sum()}件")
print(f"別QIDが返った（誤マッチ）: {len(found) - correct['correct'].sum()}件")
print(f"やはりNO_MATCH: {len(not_found)}件")
