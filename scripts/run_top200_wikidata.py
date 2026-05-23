import sys, time, json
import pandas as pd
from pathlib import Path

sys.path.insert(0, "/home/haruka221/canon-pipeline/scripts")
from wikidata_agent_final import resolve

BASE  = Path("/home/haruka221/canon-pipeline")
IN_   = BASE / "derived/benchmark/top200_noncanonical.tsv"
OUT   = BASE / "derived/benchmark/top200_wikidata_results.tsv"
CKPT  = BASE / "derived/benchmark/top200_wikidata_checkpoint.jsonl"

df = pd.read_csv(IN_, sep="\t")
print(f"対象: {len(df)}件\n")

# チェックポイント読み込み
done = {}
if CKPT.exists():
    with open(CKPT) as f:
        for line in f:
            r = json.loads(line)
            done[r["work_key"]] = r
    print(f"チェックポイントから{len(done)}件再開\n")

results = []
for i, row in df.iterrows():
    wk = row["work_key"]
    if wk in done:
        results.append(done[wk])
        continue

    title  = str(row["title"])
    author = str(row["author_name"])
    year   = int(row["first_publish_year"]) if pd.notna(row["first_publish_year"]) else None

    print(f"[{i+1:03d}/200] {title[:40]:40s} / {author[:20]}")

    try:
        pred_qid, log = resolve(title, author, year, verbose=False)
    except Exception as e:
        pred_qid = "ERROR"
        log = [str(e)]

    rec = {
        "work_key":     wk,
        "title":        title,
        "author":       author,
        "year":         year,
        "edition_count": row["edition_count"],
        "pred_qid":     pred_qid,
        "log":          " | ".join(log)
    }
    results.append(rec)

    with open(CKPT, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"           → {pred_qid}")
    time.sleep(1)

result_df = pd.DataFrame(results)
result_df.to_csv(OUT, sep="\t", index=False)

# 集計
total    = len(result_df)
matched  = (result_df["pred_qid"] != "NO_MATCH") & (result_df["pred_qid"] != "ERROR")
no_match = (result_df["pred_qid"] == "NO_MATCH").sum()
error    = (result_df["pred_qid"] == "ERROR").sum()

print(f"\n--- 集計 ---")
print(f"QID発見: {matched.sum()}件 / {total}件 ({matched.sum()/total*100:.1f}%)")
print(f"NO_MATCH: {no_match}件")
print(f"ERROR: {error}件")

# edition_count別
for label, low, high in [
    ("版数1000以上", 1000, 9999),
    ("版数500-999",   500,  999),
    ("版数259-499",   259,  499),
]:
    sub = result_df[
        (result_df["edition_count"] >= low) &
        (result_df["edition_count"] <= high)
    ]
    m = (sub["pred_qid"] != "NO_MATCH") & (sub["pred_qid"] != "ERROR")
    print(f"{label}: QID発見 {m.sum()}/{len(sub)} ({m.sum()/len(sub)*100:.1f}%)")

print(f"\nQID発見作品（上位20件）:")
found = result_df[matched].sort_values("edition_count", ascending=False)
print(found[["title","author","edition_count","pred_qid"]].head(20).to_string(index=False))

print(f"\nNO_MATCH作品（版数上位10件）:")
nm = result_df[result_df["pred_qid"]=="NO_MATCH"].sort_values("edition_count", ascending=False)
print(nm[["title","author","edition_count"]].head(10).to_string(index=False))
