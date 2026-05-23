import pandas as pd
import requests
import time
import re

def clean_title(title):
    """特殊文字を処理する"""
    clean = title.lower()
    # プレフィックス除去
    clean = clean.replace("textplus - ", "")
    clean = clean.replace(", a novel", "")
    clean = clean.replace(", a story of california", "")
    # クォート・アポストロフィを除去
    clean = clean.replace('"', '')
    clean = clean.replace('"', '')
    clean = clean.replace('"', '')
    clean = clean.replace("'", "")
    clean = clean.replace("'", "")
    # ハイフンをスペースに
    clean = clean.replace("-", " ")
    clean = clean.strip()
    return clean

def search_wikidata_api(title):
    clean = clean_title(title)
    print(f"  検索クエリ: '{clean}'")
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

# ERRORだった10件のタイトルを直接指定
error_titles = [
    "The jungle",
    'The "genius"',
    "The shadow-line",
    "The Autobiography of Alice B. Toklas",
    "The story of an African farm",
    "The rise of David Levinsky",
    "The octopus, a story of California",
    "Textplus - New Grub Street",
    "The uncalled, a novel",
    "Tender is the Night",
    "Strange case of Dr. Jekyll and Mr. Hyde",
    "Jude the obscure"
]

# gold QIDを取得
full = pd.read_csv(
    "/home/haruka221/canon-pipeline/derived/benchmark/full_eval_130items.tsv",
    sep="\t"
)
gold_map = dict(zip(full["title"], full["gold_qid_final"]))

print(f"確認件数: {len(error_titles)}\n")

results = []
for title in error_titles:
    gold = gold_map.get(title, "不明")
    print(f"\n{title}")
    try:
        candidates = search_wikidata_api(title)
        qids = [c[0] for c in candidates]
        correct = gold in qids

        if correct:
            status = "✓ 取れた"
            pred = gold
        elif candidates:
            top = candidates[0]
            status = f"✗ 別物: {top[0]} ({top[2][:50]})"
            pred = top[0]
        else:
            status = "→ やはりない"
            pred = "NO_MATCH"

        print(f"  結果: {status}")
        print(f"  gold: {gold}")
        results.append({
            "title": title,
            "gold": gold,
            "pred": pred,
            "correct": correct,
            "top5": str(candidates[:3])
        })
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({
            "title": title,
            "gold": gold,
            "pred": "ERROR",
            "correct": False,
            "top5": ""
        })
    time.sleep(2)

result_df = pd.DataFrame(results)
result_df.to_csv(
    "/home/haruka221/canon-pipeline/derived/benchmark/no_match_error_recheck.tsv",
    sep="\t", index=False
)

correct_n = result_df["correct"].sum()
no_match_n = (result_df["pred"] == "NO_MATCH").sum()
wrong_n = len(result_df) - correct_n - no_match_n - (result_df["pred"] == "ERROR").sum()

print(f"\n--- 集計 ---")
print(f"取れた（正解）: {correct_n}件")
print(f"やはりない: {no_match_n}件")
print(f"別物を返した: {wrong_n}件")
print(f"ERROR: {(result_df['pred'] == 'ERROR').sum()}件")
