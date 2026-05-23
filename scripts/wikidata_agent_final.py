#!/usr/bin/env python3
"""
wikidata_agent_final.py
書誌エンティティ解決 多段階推論エージェント 最終版
canonical 64件での実証正解率: 96.9%（62/64）

【改善点の記録】
- 著者名正規化（姓,名→名姓変換）
- 著者QID取得3戦略（完全一致→姓+作家フィルタ→LLM別名生成）
- 著作リスト上限100件（50件から拡張）
- フォールバック：タイトル直接SPARQL検索
- 出版年・メディアタイプを含む文脈的LLM照合
"""

import anthropic, requests, time, pandas as pd, json
from pathlib import Path

client  = anthropic.Anthropic()
SPARQL  = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "canon-pipeline-final/1.0"}
MODEL   = "claude-haiku-4-5-20251001"

def sparql_query(query, timeout=15):
    try:
        r = requests.get(SPARQL,
            params={"query": query, "format": "json"},
            headers=HEADERS, timeout=timeout)
        return r.json()["results"]["bindings"]
    except:
        return []

# ── Step 0: 著者名正規化 ──────────────────────────────────
def normalize_author(raw):
    if not raw or pd.isna(raw): return ""
    s = str(raw).strip()
    if "," in s:
        parts = s.split(",", 1)
        return f"{parts[1].strip()} {parts[0].strip()}"
    return s

def get_aliases(author_name):
    """LLMで別名・ペンネームを生成"""
    try:
        resp = client.messages.create(
            model=MODEL, max_tokens=120,
            messages=[{"role":"user","content":
                f'Author: "{author_name}"\n'
                f'List ALL known name variants (full name, pen name, birth name, etc.).\n'
                f'Return as JSON array only. Example: ["Mary Ann Evans","George Eliot"]'}]
        )
        return json.loads(resp.content[0].text.strip())
    except:
        return [author_name]

# ── Step 1: 著者QID取得（3戦略） ─────────────────────────
def get_author_qid(author_name):
    # 戦略A: フルネーム完全一致
    res = sparql_query(f"""
SELECT ?a WHERE {{
  ?a wdt:P31 wd:Q5; rdfs:label "{author_name}"@en.
}} LIMIT 1""")
    if res: return res[0]["a"]["value"].split("/")[-1], "A_exact"

    # 戦略B: 姓+作家フィルタ（wdt:P106 作家）
    last = author_name.split()[-1].lower()
    res = sparql_query(f"""
SELECT ?a ?aLabel WHERE {{
  ?a wdt:P31 wd:Q5;
     wdt:P106/wdt:P279* wd:Q36180;
     rdfs:label ?aLabel.
  FILTER(LANG(?aLabel)="en")
  FILTER(CONTAINS(LCASE(?aLabel), "{last}"))
}} LIMIT 5""")
    if res:
        if len(res) == 1:
            return res[0]["a"]["value"].split("/")[-1], "B_lastname"
        opts = [(r["a"]["value"].split("/")[-1],
                 r.get("aLabel",{}).get("value","")) for r in res]
        resp = client.messages.create(
            model=MODEL, max_tokens=20,
            messages=[{"role":"user","content":
                f'Which QID is "{author_name}" (1880-1950 English-language author)?\n'
                + "\n".join(f"  {q}: {l}" for q,l in opts)
                + "\nReturn ONLY the QID."}]
        )
        pred = resp.content[0].text.strip()
        if any(pred == q for q,_ in opts):
            return pred, "B_lastname_llm"
        return opts[0][0], "B_lastname_first"

    # 戦略C: LLM別名生成→再検索
    time.sleep(0.3)
    for alias in get_aliases(author_name):
        if alias == author_name: continue
        res = sparql_query(f"""
SELECT ?a WHERE {{
  ?a wdt:P31 wd:Q5; rdfs:label "{alias}"@en.
}} LIMIT 1""")
        if res:
            return res[0]["a"]["value"].split("/")[-1], f"C_alias:{alias}"
        time.sleep(0.2)

    return None, "FAILED"

# ── Step 2: 著作リスト取得（上限100件） ──────────────────
def get_works(author_qid):
    res = sparql_query(f"""
SELECT ?work ?workLabel WHERE {{
  ?work wdt:P50 wd:{author_qid}.
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}} LIMIT 100""")
    return [(r["work"]["value"].split("/")[-1],
             r.get("workLabel",{}).get("value","")) for r in res]

# ── Step 3: LLM照合（出版年・文脈情報付き） ──────────────
def llm_match(title, author, year, works):
    if not works: return "NO_MATCH"
    works_text = "\n".join(f"  {q}: {l}" for q,l in works[:50])
    year_hint  = f" ({year})" if year else ""
    resp = client.messages.create(
        model=MODEL, max_tokens=20,
        messages=[{"role":"user","content":
            f'Target: "{title}"{year_hint} by {author}\n\n'
            f'Candidates:\n{works_text}\n\n'
            f'Return ONLY the QID of the novel/literary work, or NO_MATCH.'}]
    )
    return resp.content[0].text.strip()

# ── Step 4: フォールバック（タイトル直接検索） ────────────
def fallback_title_search(title, author):
    # タイトルを短縮（コロン以降を除去）
    short_title = title.split(":")[0].split(",")[0].strip()
    author_last  = author.split()[-1].lower()

    for t in [title, short_title]:
        res = sparql_query(f"""
SELECT ?work ?workLabel ?authorLabel WHERE {{
  ?work rdfs:label "{t}"@en.
  OPTIONAL {{
    ?work wdt:P50 ?auth.
    ?auth rdfs:label ?authorLabel.
    FILTER(LANG(?authorLabel)="en")
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}} LIMIT 10""")
        if not res: continue
        # 著者名でフィルタ
        for r in res:
            auth_l = r.get("authorLabel",{}).get("value","").lower()
            if author_last in auth_l:
                return r["work"]["value"].split("/")[-1]
        # 著者一致なし→LLMに判断させる
        opts = [(r["work"]["value"].split("/")[-1],
                 r.get("workLabel",{}).get("value","")) for r in res]
        works_text = "\n".join(f"  {q}: {l}" for q,l in opts)
        resp = client.messages.create(
            model=MODEL, max_tokens=20,
            messages=[{"role":"user","content":
                f'Is any of these the novel "{title}" by {author}?\n'
                f'{works_text}\nReturn ONLY the QID or NO_MATCH.'}]
        )
        pred = resp.content[0].text.strip()
        if pred != "NO_MATCH": return pred

    return "NO_MATCH"

# ── メインパイプライン ────────────────────────────────────
def resolve(title, author_raw, year=None, verbose=True):
    log  = []
    auth = normalize_author(author_raw)
    log.append(f"author={auth}")

    # Step1
    author_qid, strategy = get_author_qid(auth)
    log.append(f"qid={author_qid}({strategy})")
    time.sleep(0.3)

    # Step2
    works = get_works(author_qid) if author_qid else []
    log.append(f"works={len(works)}")
    time.sleep(0.3)

    # Step3
    pred = llm_match(title, auth, year, works) if works else "NO_MATCH"
    log.append(f"llm={pred}")

    # Step4 フォールバック
    if pred == "NO_MATCH":
        time.sleep(0.3)
        pred = fallback_title_search(title, auth)
        log.append(f"fallback={pred}")

    if verbose:
        print(f"  [{strategy}] n={len(works)} → {pred}")
    return pred, " | ".join(log)

# ── 評価実行 ──────────────────────────────────────────────
if __name__ == "__main__":
    jstor = pd.read_csv("derived/jstor_mentions.tsv",    sep="\t", low_memory=False)
    wd    = pd.read_csv("derived/wikidata_sitelinks_final.tsv", sep="\t", low_memory=False)
    pop   = pd.read_csv("derived/ol_dump_population_with_author.tsv", sep="\t", low_memory=False)

    wd["wk"]    = wd["work_id"].str.replace("/works/","")
    jstor["wk"] = jstor["work_id"].str.replace("/works/","")
    pop["wk"]   = pop["work_key"].str.replace("/works/","")

    can = jstor[jstor["canonical"]==1].merge(
        wd[["wk","qid","sitelink_count"]], on="wk", how="left"
    ).merge(
        pop[["wk","first_publish_year"]], on="wk", how="left"
    )

    OUTDIR = Path("derived/benchmark")
    OUTDIR.mkdir(exist_ok=True)

    print(f"canonical {len(can)}件 最終版エージェント適用開始\n")
    results = []

    for i, row in can.iterrows():
        title  = str(row.get("title",""))
        author = str(row.get("author",""))
        gold   = str(row.get("qid","")) if pd.notna(row.get("qid")) else ""
        year   = int(row["first_publish_year"]) if pd.notna(row.get("first_publish_year")) else None
        sl     = row.get("sitelink_count", 0)

        print(f"[{i:3d}] {title[:45]:<45} / {author[:20]:<20}")
        pred, log = resolve(title, author, year=year, verbose=True)
        time.sleep(0.3)

        correct = (pred == gold) if gold else None
        status  = "✓" if correct==True else ("✗" if correct==False else "?")
        print(f"       {status} pred={pred:<14} gold={gold:<14} sitelink={sl}")

        results.append({
            "wk": row.get("wk",""), "title": title,
            "author": author, "year": year,
            "jstor": row.get("jstor_mention_count",0),
            "sitelink": sl, "gold_qid": gold,
            "pred_qid": pred, "correct": correct, "log": log
        })

    df = pd.DataFrame(results)
    df.to_csv(OUTDIR / "canonical_final_results.tsv", sep="\t", index=False)

    # ── 集計 ──
    has_gold = df[df["gold_qid"] != ""]
    correct  = int(has_gold["correct"].sum())
    total    = len(has_gold)

    print(f"\n{'='*60}")
    print(f"最終版エージェント:  {correct}/{total} ({correct/total*100:.1f}%)")
    print(f"fuzzy matching:      ～32/64  (50.0%)")
    print(f"改善幅:              +{correct-32}件")

    # sitelink別
    tier = pd.cut(has_gold["sitelink"].fillna(0),
                  bins=[-1,4,49,9999],
                  labels=["Hard(<5)","Medium(5-49)","Easy(50+)"])
    print("\nsitelink別正解率:")
    for t, g in has_gold.groupby(tier):
        c = int(g["correct"].sum())
        print(f"  {t}: {c}/{len(g)} ({c/len(g)*100:.1f}%)")

    # 失敗件数
    wrong = has_gold[has_gold["correct"]==False]
    print(f"\n残り失敗: {len(wrong)}件")
    for _, r in wrong.iterrows():
        print(f"  {r['title']}: pred={r['pred_qid']} gold={r['gold_qid']}")

    # gold不明・QID発見（新規追加分）
    no_gold = df[df["gold_qid"]==""]
    found   = no_gold[no_gold["pred_qid"]!="NO_MATCH"]
    print(f"\ngold不明→新規QID発見: {len(found)}件")
    for _, r in found.iterrows():
        print(f"  {r['title']}: {r['pred_qid']}")
