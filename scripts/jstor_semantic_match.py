import json, anthropic, time
import pandas as pd
from pathlib import Path

BASE   = Path("/home/haruka221/canon-pipeline")
JSTOR  = BASE / "data/jstor_metadata_2025-07-04.jsonl"
OUT    = BASE / "derived/benchmark/jstor_semantic_results.tsv"
client = anthropic.Anthropic()

# C3グループ（JSTOR=0かつOpenAlex>0の10件）
C3 = [
    {"title": "White Fang",            "author": "Jack London",           "year": 1906},
    {"title": "The Moon and Sixpence", "author": "W. Somerset Maugham",   "year": 1919},
    {"title": "The Yearling",          "author": "Marjorie Kinnan Rawlings","year": 1938},
    {"title": "Tarzan of the Apes",    "author": "Edgar Rice Burroughs",  "year": 1914},
    {"title": "Senator North",         "author": "Gertrude Atherton",     "year": 1900},
    {"title": "The Mystery of Cloomber","author": "Arthur Conan Doyle",   "year": 1888},
    {"title": "The Grand Babylon Hotel","author": "Arnold Bennett",        "year": 1902},
    {"title": "The Golden Cage",       "author": "Iris Bromige",          "year": 1949},
    {"title": "The Innocents",         "author": "Alfred Machard",        "year": 1925},
    {"title": "The Sea Witch",         "author": "Alexander Laing",       "year": 1933},
]

def find_candidates(target_title, max_candidates=20):
    """JSTORメタデータからキーワード候補を抽出する"""
    keywords = [w.lower() for w in target_title.split()
                if len(w) > 3 and w.lower() not in
                {"the","and","of","in","a","an","to","for"}]
    
    candidates = []
    with open(JSTOR) as f:
        for line in f:
            if len(candidates) >= max_candidates:
                break
            try:
                obj = json.loads(line)
                t = (obj.get("title") or "").lower()
                if not t:
                    continue
                # 複数キーワードのうち少なくとも1つがタイトルに含まれる
                if any(kw in t for kw in keywords):
                    candidates.append({
                        "title":   obj.get("title",""),
                        "creator": obj.get("creators_string",""),
                        "date":    obj.get("published_date",""),
                        "type":    obj.get("content_type","")
                    })
            except:
                continue
    return candidates

def llm_judge(target, candidates):
    """候補論文がtargetの作品について書かれているかLLMに判定させる"""
    if not candidates:
        return [], 0

    cand_text = "\n".join([
        f"{i+1}. \"{c['title']}\" by {c['creator']} ({c['date']})"
        for i, c in enumerate(candidates)
    ])

    prompt = f"""You are a literary scholar. Judge whether each paper is about the novel "{target['title']}" ({target['year']}) by {target['author']}.

Candidates:
{cand_text}

For each candidate, respond with its number and YES or NO and one-line reason.
Format: "1. YES - about the novel" or "1. NO - unrelated topic"
Only mark YES if the paper clearly discusses this specific novel."""

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role":"user","content":prompt}]
    )
    text = resp.content[0].text
    
    relevant = []
    for i, c in enumerate(candidates):
        marker = f"{i+1}. YES"
        if marker in text:
            relevant.append(c)
    
    return relevant, len(relevant)

results = []
for work in C3:
    print(f"\n{'='*50}")
    print(f"対象: {work['title']} / {work['author']}")
    
    # Step1: キーワード候補抽出
    candidates = find_candidates(work["title"], max_candidates=30)
    print(f"候補数: {len(candidates)}件")
    
    if candidates:
        for c in candidates[:5]:
            print(f"  候補例: {c['title'][:60]}")
    
    # Step2: LLM判定
    relevant, count = llm_judge(work, candidates)
    print(f"関連論文: {count}件")
    for r in relevant:
        print(f"  ✓ {r['title'][:60]} / {r['creator']}")
    
    results.append({
        "title":           work["title"],
        "author":          work["author"],
        "year":            work["year"],
        "candidates_found": len(candidates),
        "relevant_count":  count,
        "relevant_titles": " | ".join([r["title"] for r in relevant])
    })
    time.sleep(1)

df = pd.DataFrame(results)
df.to_csv(OUT, sep="\t", index=False)

print(f"\n{'='*50}")
print("=== 最終集計 ===")
print(df[["title","candidates_found","relevant_count"]].to_string(index=False))
print(f"\nJSTOR=0だが実際に関連論文あり: {(df['relevant_count']>0).sum()}件")
print(f"出力: {OUT}")
