import pandas as pd
import requests
import time
from pathlib import Path

BASE   = Path("/home/haruka221/canon-pipeline")
OUT    = BASE / "derived/benchmark/author_attributes.tsv"

SPARQL = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "canon-pipeline/1.0"}

df = pd.read_csv(
    BASE / "derived/benchmark/full_eval_130items.tsv",
    sep="\t"
)
positives = df[df["type"] == "positive"].copy()
qids = positives["gold_qid_final"].dropna().tolist()
print(f"対象: {len(qids)}件\n")

def get_attributes(work_qid):
    query = f"""
    SELECT ?author ?authorLabel ?genderLabel ?nationalityLabel ?movementLabel WHERE {{
      wd:{work_qid} wdt:P50 ?author .
      OPTIONAL {{ ?author wdt:P21 ?gender . }}
      OPTIONAL {{ ?author wdt:P27 ?nationality . }}
      OPTIONAL {{ ?author wdt:P135 ?movement . }}
      SERVICE wikibase:label {{
        bd:serviceParam wikibase:language "en" .
      }}
    }}
    LIMIT 5
    """
    try:
        r = requests.get(
            SPARQL,
            params={"query": query, "format": "json"},
            headers=HEADERS,
            timeout=15
        )
        rows = r.json()["results"]["bindings"]
        if not rows:
            return None
        # 複数movementがある場合は結合
        authors   = list(set(b.get("authorLabel",{}).get("value","") for b in rows))
        genders   = list(set(b.get("genderLabel",{}).get("value","") for b in rows if b.get("genderLabel")))
        nations   = list(set(b.get("nationalityLabel",{}).get("value","") for b in rows if b.get("nationalityLabel")))
        movements = list(set(b.get("movementLabel",{}).get("value","") for b in rows if b.get("movementLabel")))
        return {
            "author_qid":  rows[0].get("author",{}).get("value","").split("/")[-1],
            "author_name": authors[0] if authors else "",
            "gender":      genders[0] if genders else "",
            "nationality": nations[0] if nations else "",
            "movements":   " | ".join(movements)
        }
    except Exception as e:
        return {"error": str(e)}

results = []
for i, row in positives.iterrows():
    qid = str(row["gold_qid_final"])
    attr = get_attributes(qid)
    rec = {
        "work_qid":  qid,
        "title":     row["title"],
        "author":    row["author"],
    }
    if attr and "error" not in attr:
        rec.update(attr)
        print(f"✓ {row['title'][:35]:35s} | {attr.get('gender','?'):6} | {attr.get('nationality','?')[:15]:15} | {attr.get('movements','?')[:30]}")
    elif attr and "error" in attr:
        print(f"ERROR: {row['title'][:35]} → {attr['error']}")
    else:
        print(f"- {row['title'][:35]:35s} | 著者なし")
    results.append(rec)
    time.sleep(2)

result_df = pd.DataFrame(results)
result_df.to_csv(OUT, sep="\t", index=False)
print(f"\n出力: {OUT}")
print(f"gender取得: {result_df['gender'].notna().sum()}件")
print(f"nationality取得: {result_df['nationality'].notna().sum()}件")
print(f"movements取得: {result_df['movements'].notna().sum()}件")
