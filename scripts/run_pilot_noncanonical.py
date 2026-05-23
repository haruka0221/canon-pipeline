import sys, time, json
import pandas as pd
from pathlib import Path

sys.path.insert(0, "/home/haruka221/canon-pipeline/scripts")
from wikidata_agent_final import resolve

BASE   = Path("/home/haruka221/canon-pipeline")
IN_    = BASE / "derived/benchmark/pilot_50_noncanonical.tsv"
OUT    = BASE / "derived/benchmark/pilot_noncanonical_results.tsv"
CKPT   = BASE / "derived/benchmark/pilot_noncanonical_checkpoint.jsonl"

df = pd.read_csv(IN_, sep="\t")
print(f"対象: {len(df)}件\n")

# チェックポイント読み込み（途中再開用）
done = {}
if CKPT.exists():
    with open(CKPT) as f:
        for line in f:
            r = json.loads(line)
            done[r["work_key"]] = r
    print(f"チェックポイントから{len(done)}件再開")

results = []
for i, row in df.iterrows():
    wk = row["work_key"]

    # 済みはスキップ
    if wk in done:
        results.append(done[wk])
        continue

    title  = str(row["title"])
    author = str(row["author_name"])
    year   = int(row["first_publish_year"]) if pd.notna(row["first_publish_year"]) else None

    print(f"[{i+1:02d}/50] {title[:40]:40s} / {author[:20]}")

    try:
        pred_qid, log = resolve(title, author, year, verbose=False)
    except Exception as e:
        pred_qid = "ERROR"
        log = [str(e)]

    rec = {
        "work_key":  wk,
        "title":     title,
        "author":    author,
        "year":      year,
        "pred_qid":  pred_qid,
        "jstor":     row["jstor_mention_count"],
        "log":       " | ".join(log)
    }
    results.append(rec)

    # チェックポイント書き込み
    with open(CKPT, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"         → {pred_qid}")
    time.sleep(1)

# 保存
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

# JSTOR別
for label, cond in [
    ("JSTOR=0", result_df["jstor"]==0),
    ("JSTOR>0", result_df["jstor"]>0)
]:
    sub = result_df[cond]
    m   = (sub["pred_qid"] != "NO_MATCH") & (sub["pred_qid"] != "ERROR")
    print(f"{label}: QID発見 {m.sum()}/{len(sub)}")

print(f"\n出力: {OUT}")
