#!/usr/bin/env python3
"""
benchmark_multistep.py
多段階推論エージェントのベンチマーク
対象: 前回のno_match 7件 + 著者名逆転形式を持つケース
"""

import os
import requests
import time
import re
import json
from pathlib import Path
from openai import OpenAI

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4")
SLEEP = 0.4
OUT = Path("derived/benchmark")

client = OpenAI()

# ── 著者名正規化 ──────────────────────────────────────────────
def normalize_author(raw: str) -> str:
    """'Conrad, Joseph' → 'Joseph Conrad' / 'H. G. Wells' → そのまま"""
    raw = raw.strip()
    if "," in raw:
        parts = [p.strip() for p in raw.split(",", 1)]
        return f"{parts[1]} {parts[0]}"
    return raw

# ── Wikidata検索 ──────────────────────────────────────────────
def wikidata_search(query: str, limit: int = 10) -> list:
    try:
        r = requests.get(
            "https://www.wikidata.org/w/api.php",
            params={"action": "wbsearchentities", "search": query,
                    "language": "en", "type": "item",
                    "limit": limit, "format": "json"},
            headers={"User-Agent": "canon-pipeline-multistep/0.1 (tsutsui@nihu.jp)",
                     "Accept": "application/json"},
            timeout=15)
        r.raise_for_status()
        return r.json().get("search", [])
    except Exception as e:
        print(f"    [Wikidata Error] {e}")
        return []

def fmt_candidates(results: list) -> str:
    if not results:
        return "(候補なし)"
    return "\n".join(
        f"  {c['id']}: \"{c.get('label','')}\" — {c.get('description','')[:70]}"
        for c in results)

# ── LLM判定 ──────────────────────────────────────────────────
SYSTEM = """You are a bibliographic entity resolution expert.
Given a literary work's metadata and Wikidata search results, identify the correct QID.
Rules:
- Return ONLY the QID (e.g. Q12345) if confident it is the correct literary work by the correct author
- Return no_match if none of the candidates match
- Reject: geographic entities, character names, films, adaptations, other authors' works
- Author and title must BOTH match
Respond with ONLY the QID or no_match."""

def llm_judge(title: str, author_normalized: str, year: int,
              candidates: list, step_label: str) -> str | None:
    if not candidates:
        return None
    msg = (f"Work: \"{title}\" by {author_normalized} ({year})\n\n"
           f"Candidates ({step_label}):\n{fmt_candidates(candidates)}\n\n"
           f"Return correct QID or no_match:")
    try:
        resp = client.responses.create(
            model=MODEL,
            instructions=SYSTEM,
            input=msg,
        )
        ans = resp.output_text.strip().rstrip(".")
    except Exception as e:
        print(f"    [OpenAI Error] {e}")
        return None

    if ans == "no_match":
        return "no_match"
    m = re.search(r"\bQ\d+\b", ans)
    return m.group(0) if m else None

# ── 多段階エージェント ────────────────────────────────────────
def multistep_resolve(title: str, author_raw: str, year: int,
                      gold: str, verbose: bool = True) -> dict:
    author_norm = normalize_author(author_raw)
    lastname = author_norm.split()[-1]

    log = {"title": title, "author_raw": author_raw,
           "author_normalized": author_norm, "gold": gold,
           "steps": [], "final_pred": None, "correct": False}

    def step(label: str, query: str) -> str | None:
        if verbose:
            print(f"    Step {label}: search='{query}'")
        cands = wikidata_search(query, limit=10)
        time.sleep(SLEEP)
        pred = llm_judge(title, author_norm, year, cands, label)
        time.sleep(0.2)
        if verbose:
            mark = "✓" if pred == gold else ("?" if pred == "no_match" else "✗")
            print(f"           → {pred} {mark}")
        log["steps"].append({"label": label, "query": query,
                             "n_candidates": len(cands), "pred": pred})
        return pred

    # Step 1: タイトルのみ（前回と同じ）
    pred = step("1_title_only", title)
    if pred and pred != "no_match":
        log["final_pred"] = pred
        log["correct"] = (pred == gold)
        return log

    # Step 2: 著者正規化後の「タイトル 著者姓」
    pred = step("2_title+lastname", f"{title} {lastname}")
    if pred and pred != "no_match":
        log["final_pred"] = pred
        log["correct"] = (pred == gold)
        return log

    # Step 3: 「著者フルネーム タイトル」
    pred = step("3_author+title", f"{author_norm} {title}")
    if pred and pred != "no_match":
        log["final_pred"] = pred
        log["correct"] = (pred == gold)
        return log

    # Step 4: 著者名のみで人物エンティティを探し、作品名で絞り込み
    if verbose:
        print(f"    Step 4: author-only search='{author_norm}'")
    author_cands = wikidata_search(author_norm, limit=5)
    time.sleep(SLEEP)
    author_qids = [c["id"] for c in author_cands if "author" in c.get("description","").lower()
                   or "writer" in c.get("description","").lower()
                   or "novelist" in c.get("description","").lower()
                   or "poet" in c.get("description","").lower()]
    if verbose:
        print(f"           著者候補QIDs: {author_qids}")

    if author_qids:
        # WDQS SPARQLで著者の著作を検索
        sparql_q = author_qids[0]
        query = f"""SELECT ?work ?workLabel WHERE {{
  ?work wdt:P50 wd:{sparql_q} .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
}} LIMIT 20"""
        try:
            sr = requests.get(
                "https://query.wikidata.org/sparql",
                params={"query": query, "format": "json"},
                headers={"User-Agent": "canon-pipeline-multistep/0.1 (tsutsui@nihu.jp)",
                         "Accept": "application/json"},
                timeout=20)
            sr.raise_for_status()
            works = sr.json().get("results", {}).get("bindings", [])
            time.sleep(SLEEP)
            sparql_cands = [
                {"id": w["work"]["value"].split("/")[-1],
                 "label": w["workLabel"]["value"],
                 "description": f"work by {author_norm}"}
                for w in works]
            if verbose:
                print(f"           SPARQL著作リスト: {len(sparql_cands)}件")
            pred = llm_judge(title, author_norm, year, sparql_cands, "4_sparql_works")
            time.sleep(0.2)
            mark = "✓" if pred == gold else ("?" if pred == "no_match" else "✗")
            if verbose:
                print(f"           → {pred} {mark}")
            log["steps"].append({"label": "4_sparql_works",
                                 "n_candidates": len(sparql_cands), "pred": pred})
            if pred and pred != "no_match":
                log["final_pred"] = pred
                log["correct"] = (pred == gold)
                return log
        except Exception as e:
            if verbose:
                print(f"           [SPARQL Error] {e}")

    log["final_pred"] = None
    log["correct"] = False
    return log

# ── メイン ───────────────────────────────────────────────────
def main():
    # 前回no_matchだった7件
    cases = [
        ("Kim",                                   "Kipling, Rudyard",         1901, "Q19086249"),
        ("The Pit",                               "Frank Norris",             1903, "Q7757284"),
        ("Strange case of Dr. Jekyll and Mr. Hyde","Robert Louis Stevenson",  1886, "Q217352"),
        ("The Awakening",                         "Kate Chopin",              1899, "Q1567505"),
        ("Peter Pan",                             "J. M. Barrie",             1911, "Q3435337"),
        ("Pembroke",                              "Mary Wilkins Freeman",     1894, "Q7161943"),
        ("Orlando",                               "Virginia Woolf",           1928, "Q1629456"),
    ]

    print("=" * 60)
    print("  多段階推論エージェント ベンチマーク（前回no_match 7件）")
    print("=" * 60)

    results = []
    for title, author, year, gold in cases:
        print(f"\n▶ {title} / {author} ({year}) — gold={gold}")
        res = multistep_resolve(title, author, year, gold)
        results.append(res)
        final = res["final_pred"]
        mark = "✓ 解決" if res["correct"] else ("棄権" if not final else "✗ 誤答")
        print(f"  最終: {final} [{mark}]")

    # 集計
    solved  = sum(1 for r in results if r["correct"])
    wrong   = sum(1 for r in results if r["final_pred"] and not r["correct"])
    abstain = sum(1 for r in results if not r["final_pred"])
    print(f"\n{'='*60}")
    print(f"  解決: {solved}/7   誤答: {wrong}   棄権: {abstain}")
    print(f"  前回single-step: 0/7  →  多段階: {solved}/7")
    print(f"{'='*60}")

    # 保存
    OUT.mkdir(exist_ok=True)
    with open(OUT / "multistep_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n結果: derived/benchmark/multistep_results.json")

if __name__ == "__main__":
    main()
