import pandas as pd
import requests
import time
from pathlib import Path

BASE   = Path("/home/haruka221/canon-pipeline")
IN_    = BASE / "derived/benchmark/top200_wikidata_results.tsv"
OUT    = BASE / "derived/benchmark/top200_author_attributes.tsv"

SPARQL  = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "canon-pipeline/1.0"}

df = pd.read_csv(IN_, sep="\t")
# QIDが取れたもののみ
matched = df[
    (df["pred_qid"] != "NO_MATCH") &
    (df["pred_qid"] != "ERROR") &
    (df["pred_qid"].notna())
].copy()
print(f"対象: {len(matched)}件\n")

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
        genders   = list(set(b.get("genderLabel",{}).get("value","") for b in rows if b.get("genderLabel")))
        nations   = list(set(b.get("nationalityLabel",{}).get("value","") for b in rows if b.get("nationalityLabel")))
        movements = list(set(b.get("movementLabel",{}).get("value","") for b in rows if b.get("movementLabel")))
        author_label = rows[0].get("authorLabel",{}).get("value","")
        return {
            "author_label": author_label,
            "gender":       genders[0] if genders else "",
            "nationality":  nations[0] if nations else "",
            "movements":    " | ".join(movements)
        }
    except:
        return None

results = []
for i, row in matched.iterrows():
    attr = get_attributes(str(row["pred_qid"]))
    rec = {
        "work_key":     row["work_key"],
        "title":        row["title"],
        "author":       row["author"],
        "edition_count": row["edition_count"],
        "pred_qid":     row["pred_qid"],
    }
    if attr:
        rec.update(attr)
        print(f"✓ {row['title'][:35]:35s} | {attr.get('gender','?'):6} | {attr.get('nationality','?')[:20]:20} | {attr.get('movements','')[:25]}")
    else:
        print(f"- {row['title'][:35]:35s} | 属性なし")
    results.append(rec)
    time.sleep(2)

result_df = pd.DataFrame(results)
result_df.to_csv(OUT, sep="\t", index=False)

print(f"\n=== 取得結果 ===")
print(f"gender取得: {(result_df.get('gender','') != '').sum()}件")
print(f"nationality取得: {(result_df.get('nationality','') != '').sum()}件")
print(f"movements取得: {(result_df.get('movements','') != '').sum()}件")
print(f"\n文学運動分布:")
if "movements" in result_df.columns:
    mv = result_df["movements"].dropna().str.split(" \| ").explode()
    mv = mv[mv != ""]
    print(mv.value_counts().head(10).to_string())
print(f"\n国籍分布（上位10）:")
if "nationality" in result_df.columns:
    print(result_df["nationality"].value_counts().head(10).to_string())
