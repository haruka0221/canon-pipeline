#!/usr/bin/env python3
"""
wikidata_agent_v2.py
多段階推論エージェント完全版
今日の実験で判明した改善を全て組み込み
"""

import requests, time, pandas as pd, json
from pathlib import Path
from openai import OpenAI

client = OpenAI()
SPARQL  = "https://query.wikidata.org/sparql"
MODEL   = "gpt-5.4"
HEADERS = {"User-Agent": "canon-pipeline-v2/1.0"}

def sparql_query(query, timeout=15):
    try:
        r = requests.get(SPARQL,
            params={"query": query, "format": "json"},
            headers=HEADERS, timeout=timeout)
        return r.json()["results"]["bindings"]
    except:
        return []

# ── Step 0: 著者名前処理 ──────────────────────────────────
def normalize_author(raw_name):
    """姓,名 → 名 姓 変換"""
    if not raw_name or pd.isna(raw_name):
        return ""
    name = str(raw_name).strip()
    if "," in name:
        parts = name.split(",", 1)
        return f"{parts[1].strip()} {parts[0].strip()}"
    return name

def get_author_aliases(author_name):
    """LLMで著者の別名・ペンネームを生成"""
    resp = client.responses.create(
        model=MODEL,
        input=(
            f'Author: "{author_name}"\n'
            f'List all known name variants for this person '
            f'(full name, pen name, birth name, etc.).\n'
            f'Return as JSON array of strings. Example: ["Mary Ann Evans", "George Eliot"]\n'
            f'Return ONLY the JSON array.'
        )
    )
    try:
        text = resp.output_text.strip()
        return json.loads(text)
    except:
        return [author_name]

# ── Step 1: 著者QID取得（3戦略） ─────────────────────────
def get_author_qid(author_name, use_aliases=True):
    """
    戦略A: フルネーム完全一致
    戦略B: 姓+作家フィルタ
    戦略C: LLM別名生成→再検索
    """
    candidates = [author_name]

    # 戦略A: フルネーム完全一致
    for name in candidates:
        results = sparql_query(f"""
SELECT ?a WHERE {{
  ?a wdt:P31 wd:Q5; rdfs:label "{name}"@en.
}} LIMIT 1""")
        if results:
            return results[0]["a"]["value"].split("/")[-1], "A_exact"

    # 戦略B: 姓+作家フィルタ
    last_name = author_name.split()[-1].lower()
    results = sparql_query(f"""
SELECT ?a ?aLabel WHERE {{
  ?a wdt:P31 wd:Q5;
     wdt:P106/wdt:P279* wd:Q36180;
     rdfs:label ?aLabel.
  FILTER(LANG(?aLabel)="en")
  FILTER(CONTAINS(LCASE(?aLabel), "{last_name}"))
}} LIMIT 5""")
    if results:
        # 複数候補はLLMに選ばせる
        if len(results) == 1:
            return results[0]["a"]["value"].split("/")[-1], "B_lastname"
        opts = [(r["a"]["value"].split("/")[-1],
                 r.get("aLabel",{}).get("value","")) for r in results]
        resp = client.responses.create(
            model=MODEL,
            input=(
                f'Which QID is the author "{author_name}" (1880-1950 English literature)?\n'
                + "\n".join(f"  {q}: {l}" for q,l in opts)
                + "\nReturn ONLY the QID."
            )
        )
        pred = resp.output_text.strip()
        if any(pred == q for q,_ in opts):
            return pred, "B_lastname_llm"

    # 戦略C: LLM別名生成→再検索
    if use_aliases:
        time.sleep(0.3)
        aliases = get_author_aliases(author_name)
        for alias in aliases:
            if alias == author_name:
                continue
            results = sparql_query(f"""
SELECT ?a WHERE {{
  ?a wdt:P31 wd:Q5; rdfs:label "{alias}"@en.
}} LIMIT 1""")
            if results:
                return results[0]["a"]["value"].split("/")[-1], f"C_alias:{alias}"
            time.sleep(0.2)

    return None, "FAILED"

# ── Step 2: 著作リスト取得（上限100件） ──────────────────
def get_works(author_qid):
    results = sparql_query(f"""
SELECT ?work ?workLabel WHERE {{
  ?work wdt:P50 wd:{author_qid}.
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}} LIMIT 100""")
    return [(r["work"]["value"].split("/")[-1],
             r.get("workLabel",{}).get("value","")) for r in results]

# ── Step 3: LLM照合 ──────────────────────────────────────
def llm_match(title, author, works):
    if not works:
        return "NO_MATCH"
    works_text = "\n".join(f"  {q}: {l}" for q,l in works[:50])
    resp = client.responses.create(
        model=MODEL,
        input=(
            f'Target: "{title}" by {author}\n\nCandidates:\n{works_text}\n\n'
            f'Return ONLY the QID of this specific work, or NO_MATCH.'
        )
    )
    return resp.output_text.strip()

# ── Step 4: フォールバック（タイトル直接検索） ────────────
def fallback_title_search(title, author):
    """著者QIDが取れなかった場合、タイトルで直接検索"""
    author_last = author.split()[-1].lower()
    results = sparql_query(f"""
SELECT ?work ?workLabel ?authorLabel WHERE {{
  ?work rdfs:label "{title}"@en.
  OPTIONAL {{
    ?work wdt:P50 ?auth.
    ?auth rdfs:label ?authorLabel.
    FILTER(LANG(?authorLabel)="en")
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}} LIMIT 10""")
    if not results:
        return "NO_MATCH"
    # 著者名でフィルタ
    for r in results:
        auth_label = r.get("authorLabel",{}).get("value","").lower()
        if author_last in auth_label:
            return r["work"]["value"].split("/")[-1]
    # 著者一致なし→LLMに判断させる
    opts = [(r["work"]["value"].split("/")[-1],
             r.get("workLabel",{}).get("value","")) for r in results]
    works_text = "\n".join(f"  {q}: {l}" for q,l in opts)
    resp = client.responses.create(
        model=MODEL,
        input=(
            f'Is any of these the work "{title}" by {author}?\n{works_text}\n'
            f'Return ONLY the QID or NO_MATCH.'
        )
    )
    return resp.output_text.strip()

# ── メインパイプライン ────────────────────────────────────
def resolve(title, author_raw, verbose=True):
    """
    完全な多段階推論エージェント
    Returns: (pred_qid, steps_log)
    """
    log = []
    author = normalize_author(author_raw)
    log.append(f"author_normalized: {author}")

    # Step 1
    author_qid, strategy = get_author_qid(author)
    log.append(f"author_qid: {author_qid} via {strategy}")
    time.sleep(0.3)

    # Step 2
    works = get_works(author_qid) if author_qid else []
    log.append(f"works: {len(works)}件")
    time.sleep(0.3)

    # Step 3
    if works:
        pred = llm_match(title, author, works)
        log.append(f"llm_match: {pred}")
    else:
        pred = "NO_MATCH"

    # Step 4: フォールバック
    if pred == "NO_MATCH":
        time.sleep(0.3)
        pred = fallback_title_search(title, author)
        log.append(f"fallback: {pred}")

    if verbose:
        print(f"  [{strategy}] {title}: {pred} ({len(works)}works)")
    return pred, log

# ── 評価実行 ──────────────────────────────────────────────
if __name__ == "__main__":
    jstor = pd.read_csv("derived/jstor_mentions.tsv", sep="\t", low_memory=False)
    wd    = pd.read_csv("derived/wikidata_sitelinks_final.tsv", sep="\t", low_memory=False)
    wd["wk"] = wd["work_id"].str.replace("/works/","")
    jstor["wk"] = jstor["work_id"].str.replace("/works/","")
    can = jstor[jstor["canonical"]==1].merge(
        wd[["wk","qid","sitelink_count"]], on="wk", how="left")

    OUTDIR = Path("derived/benchmark")
    OUTDIR.mkdir(exist_ok=True)

    print(f"canonical {len(can)}件に完全版エージェントを適用\n")
    results = []

    for i, row in can.iterrows():
        title  = str(row.get("title",""))
        author = str(row.get("author",""))
        gold   = str(row.get("qid","")) if pd.notna(row.get("qid")) else ""
        sitelink = row.get("sitelink_count", 0)

        pred, log = resolve(title, author, verbose=True)
        time.sleep(0.3)

        correct = (pred == gold) if gold else None
        status  = "✓" if correct==True else ("✗" if correct==False else "?")
        print(f"  [{i:3d}] {status} gold={gold} | {' | '.join(log)}")

        results.append({
            "wk": row.get("wk",""), "title": title,
            "author_raw": author, "jstor": row.get("jstor_mention_count",0),
            "sitelink": sitelink, "gold_qid": gold,
            "pred_qid": pred, "correct": correct,
            "log": " | ".join(log)
        })

    df = pd.DataFrame(results)
    df.to_csv(OUTDIR / "canonical_agentv2_results.tsv", sep="\t", index=False)

    has_gold = df[df["gold_qid"] != ""]
    correct  = has_gold["correct"].sum()
    total    = len(has_gold)
    print(f"\n{'='*50}")
    print(f"完全版エージェント: {int(correct)}/{total} ({correct/total*100:.1f}%)")
    print(f"旧エージェント初回: 50/64 (78.1%)")
    print(f"改善幅: +{int(correct)-50}件")

    # 失敗件数
    wrong = has_gold[has_gold["correct"]==False]
    print(f"\n残り失敗: {len(wrong)}件")
    for _, r in wrong.iterrows():
        print(f"  {r['title']}: pred={r['pred_qid']} gold={r['gold_qid']}")
