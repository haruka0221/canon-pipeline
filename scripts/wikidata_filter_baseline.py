import pandas as pd
import requests
import time

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "canon-pipeline-research/1.0"}

def search_with_filter(title, author):
    # タイトルのクォートをエスケープ
    title_safe = title[:30].replace('"', '').replace("'", "")
    
    # 軽いクエリ：instance of novel/book/literary work を直接指定（再帰なし）
    query = f"""
    SELECT ?work WHERE {{
      VALUES ?type {{ wd:Q7725634 wd:Q571 wd:Q8261 wd:Q49084 }}
      ?work wdt:P31 ?type .
      ?work rdfs:label "{title_safe}"@en .
    }}
    LIMIT 3
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
            return results[0]["work"]["value"].split("/")[-1]
        return "NO_MATCH"
    except Exception as e:
        return "ERROR"

df = pd.read_csv(
    "/home/haruka221/canon-pipeline/derived/benchmark/full_eval_130items.tsv",
    sep="\t"
)

positives = df[df["type"] == "positive"].copy()
print(f"正例件数: {len(positives)}")

results = []
for i, row in positives.iterrows():
    pred = search_with_filter(row["title"], row["author"])
    correct = (pred == row["gold_qid_final"])
    results.append({
        "title": row["title"],
        "gold": row["gold_qid_final"],
        "pred_filter": pred,
        "correct": correct,
        "sitelink_count": row["sitelink_count"]
    })
    print(f"{row['title'][:40]:40s} → {pred} {'✓' if correct else '✗'}")
    time.sleep(2)

result_df = pd.DataFrame(results)
result_df.to_csv(
    "/home/haruka221/canon-pipeline/derived/benchmark/filter_baseline_results.tsv",
    sep="\t", index=False
)

total = len(result_df)
correct_n = result_df["correct"].sum()
no_match = (result_df["pred_filter"] == "NO_MATCH").sum()
error_n = (result_df["pred_filter"] == "ERROR").sum()

print(f"\n--- 結果 ---")
print(f"正解: {correct_n}/{total} = {correct_n/total:.3f}")
print(f"NO_MATCH: {no_match}件")
print(f"ERROR: {error_n}件")

for label, low, high in [("Easy(≥50)", 50, 9999), ("Medium(5-49)", 5, 49), ("Hard(<5)", 0, 4)]:
    sub = result_df[(result_df["sitelink_count"] >= low) & (result_df["sitelink_count"] <= high)]
    if len(sub) > 0:
        print(f"{label}: {sub['correct'].sum()}/{len(sub)} = {sub['correct'].mean():.3f}")
