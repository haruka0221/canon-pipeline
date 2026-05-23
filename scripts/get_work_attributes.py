import pandas as pd
import requests
import time
from pathlib import Path

BASE    = Path("/home/haruka221/canon-pipeline")
SPARQL  = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "canon-pipeline/1.0"}

def get_work_attributes(work_qid):
    query = f"""
    SELECT ?genreLabel ?awardLabel ?languageLabel WHERE {{
      OPTIONAL {{ wd:{work_qid} wdt:P136 ?genre . }}
      OPTIONAL {{ wd:{work_qid} wdt:P166 ?award . }}
      OPTIONAL {{ wd:{work_qid} wdt:P407 ?language . }}
      SERVICE wikibase:label {{
        bd:serviceParam wikibase:language "en" .
      }}
    }}
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
        genres    = list(set(b.get("genreLabel",{}).get("value","") for b in rows if b.get("genreLabel")))
        awards    = list(set(b.get("awardLabel",{}).get("value","") for b in rows if b.get("awardLabel")))
        languages = list(set(b.get("languageLabel",{}).get("value","") for b in rows if b.get("languageLabel")))
        return {
            "genres":        " | ".join(genres),
            "awards":        " | ".join(awards),
            "language_count": len(languages),
            "languages":     " | ".join(languages)
        }
    except Exception as e:
        return {"error": str(e)}

# canonical + non-canonical両方を処理
canonical = pd.read_csv(
    BASE / "derived/benchmark/full_eval_130items.tsv", sep="\t"
)
canonical = canonical[canonical["type"] == "positive"].copy()
canonical["source"] = "canonical"

top200 = pd.read_csv(
    BASE / "derived/benchmark/top200_wikidata_results.tsv", sep="\t"
)
top200 = top200[
    (top200["pred_qid"] != "NO_MATCH") &
    (top200["pred_qid"] != "ERROR") &
    (top200["pred_qid"].notna())
].copy()
top200 = top200.rename(columns={"pred_qid": "gold_qid_final"})
top200["source"] = "non_canonical"

# 結合
all_works = pd.concat([
    canonical[["title","gold_qid_final","source"]],
    top200[["title","gold_qid_final","source"]]
]).reset_index(drop=True)

print(f"対象: {len(all_works)}件（canonical {len(canonical)}件 + non-canonical {len(top200)}件）\n")

results = []
for i, row in all_works.iterrows():
    qid  = str(row["gold_qid_final"])
    attr = get_work_attributes(qid)
    rec  = {
        "title":   row["title"],
        "qid":     qid,
        "source":  row["source"],
    }
    if attr and "error" not in attr:
        rec.update(attr)
        award_str = attr["awards"][:30] if attr["awards"] else "なし"
        print(f"[{i+1:03d}] {row['title'][:35]:35s} | 翻訳{attr['language_count']:3d}言語 | 受賞: {award_str}")
    else:
        print(f"[{i+1:03d}] {row['title'][:35]:35s} | ERROR")
    results.append(rec)
    time.sleep(2)

result_df = pd.DataFrame(results)
result_df.to_csv(
    BASE / "derived/benchmark/work_attributes.tsv",
    sep="\t", index=False
)

# 集計
print(f"\n=== canonical vs non-canonical 比較 ===")
for src in ["canonical", "non_canonical"]:
    sub = result_df[result_df["source"] == src]
    print(f"\n--- {src} ({len(sub)}件) ---")

    # 受賞歴
    has_award = sub["awards"].fillna("").str.strip() != ""
    print(f"受賞歴あり: {has_award.sum()}件 ({has_award.mean()*100:.1f}%)")

    # 翻訳言語数
    lc = sub["language_count"].fillna(0)
    print(f"翻訳言語数 中央値: {lc.median():.0f} / 平均: {lc.mean():.1f} / 最大: {lc.max():.0f}")

    # ジャンル上位
    genres = sub["genres"].fillna("").str.split(" \| ").explode()
    genres = genres[genres != ""]
    if len(genres) > 0:
        print(f"ジャンル上位5:")
        print(genres.value_counts().head(5).to_string())

    # 受賞作上位
    awards = sub["awards"].fillna("").str.split(" \| ").explode()
    awards = awards[awards != ""]
    if len(awards) > 0:
        print(f"受賞歴上位5:")
        print(awards.value_counts().head(5).to_string())

print(f"\n出力: {BASE / 'derived/benchmark/work_attributes.tsv'}")
