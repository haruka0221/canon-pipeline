#!/usr/bin/env python3
"""
benchmark_entity_resolution.py
書誌エンティティ解決ベンチマーク
タスク: title + author_name + first_publish_year → 正しいWikidata QID
3手法比較: Baseline-1(API上位1件) / Baseline-2(+fuzzy) / LLM(Claude Haiku)
実行場所: ~/canon-pipeline/
"""

#!/usr/bin/env python3

import os
import re
import time
from pathlib import Path

import pandas as pd
import requests
from rapidfuzz import fuzz
from openai import OpenAI

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4")
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
SLEEP_WIKIDATA = 0.4
SLEEP_LLM = 0.3
FUZZY_THRESHOLD = 80
OUT_DIR = Path("derived/benchmark")
OUT_DIR.mkdir(exist_ok=True)

# ここが重要
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "canon-pipeline-benchmark/0.1 (research script; your-email@example.com)",
    "Accept": "application/json",
})


# ── Step 1: Gold set構築 ───────────────────────────────────────
def build_gold_set() -> pd.DataFrame:
    pop = pd.read_csv(
        "derived/ol_dump_population_with_author.tsv", sep="\t", low_memory=False
    )
    wiki = pd.read_csv(
        "derived/wikidata_sitelinks_final.tsv", sep="\t", low_memory=False
    )

    pop["work_id_short"] = pop["work_key"].str.replace("/works/", "", regex=False)
    can = pop[pop["canonical"] == 1].copy()
    merged = can.merge(wiki, left_on="work_id_short", right_on="work_id", how="left")

    gold = merged[merged["qid"].notna()].copy()
    gold = gold[["work_key", "title", "author_name", "first_publish_year", "qid"]]
    gold = gold.reset_index(drop=True)

    print(f"Gold set: {len(gold)} 件（QID確認済み canonical作品）")
    print(f"除外（QIDなし）: {len(can) - len(gold)} 件\n")
    return gold


# ── Step 2: Wikidata検索ユーティリティ ────────────────────────
def search_wikidata(query: str, limit: int = 5) -> list[dict]:
    params = {
        "action": "wbsearchentities",
        "search": query,
        "language": "en",
        "type": "item",
        "limit": limit,
        "format": "json",
    }
    try:
        r = SESSION.get(WIKIDATA_API, params=params, timeout=10)
        r.raise_for_status()
        return r.json().get("search", [])
    except Exception as e:
        print(f"  [Wikidata Error] '{query}': {e}")
        return []
    

# ── Step 3: 3手法の実装 ───────────────────────────────────────
def baseline1_top1(title: str) -> str | None:
    """タイトルでWikidata検索、上位1件のQIDをそのまま返す"""
    results = search_wikidata(title, limit=1)
    return results[0]["id"] if results else None


def baseline2_fuzzy(title: str) -> str | None:
    """上位5件を取得し、fuzzy title照合（閾値80）でフィルタ"""
    results = search_wikidata(title, limit=5)
    best_qid, best_score = None, 0
    for item in results:
        label = item.get("label", "")
        score = fuzz.token_sort_ratio(title.lower(), label.lower())
        if score >= FUZZY_THRESHOLD and score > best_score:
            best_score = score
            best_qid = item["id"]
    return best_qid


LLM_SYSTEM = (
    "You are a bibliographic entity resolution expert for literary works. "
    "Given a work's metadata and Wikidata candidates, identify the correct QID.\n\n"
    "Rules:\n"
    "- Return ONLY the QID (e.g. Q12345) if you are confident it is the correct match\n"
    "- Return no_match if none of the candidates match\n"
    "- The match must be the EXACT work by the CORRECT author\n"
    "- Reject: geographic entities, other authors' works with same title, films, "
    "  collections, or anything that is not a literary novel/story by the named author\n"
    "- One author can write multiple works — title alone is not enough\n"
    "Respond with ONLY the QID or no_match. No explanation."
)


def llm_resolve(title: str, author: str, year: int, client: OpenAI) -> str | None:
    candidates = search_wikidata(title, limit=5)
    time.sleep(SLEEP_WIKIDATA)

    if not candidates:
        return None

    cand_lines = "\n".join(
        f'- {c["id"]}: "{c.get("label","")}" — {c.get("description","(no description)")}'
        for c in candidates
    )

    user_msg = (
        f"Work to identify:\n"
        f"  Title: {title}\n"
        f"  Author: {author}\n"
        f"  First published: {year}\n\n"
        f"Wikidata candidates:\n{cand_lines}\n\n"
        f"Return the correct QID or no_match:"
    )

    try:
        resp = client.responses.create(
            model=MODEL,
            instructions=LLM_SYSTEM,
            input=user_msg,
        )
        answer = resp.output_text.strip().rstrip(".")
        if answer == "no_match":
            return "no_match"
        elif answer.startswith("Q") and answer[1:].isdigit():
            return answer
        else:
            m = re.search(r"\bQ\d+\b", answer)
            return m.group(0) if m else None
    except Exception as e:
        print(f"  [LLM Error] '{title}': {e}")
        return None


# ── Step 4: 評価関数 ──────────────────────────────────────────
def evaluate(gold_qids: list, predicted: list) -> dict:
    tp = sum(1 for g, p in zip(gold_qids, predicted) if p and p == g)
    fp = sum(1 for g, p in zip(gold_qids, predicted) if p and p != g)
    fn = sum(1 for g, p in zip(gold_qids, predicted) if not p or p != g)
    prec = tp / (tp + fp) if (tp + fp) else 0
    rec  = tp / (tp + fn) if (tp + fn) else 0
    f1   = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
    return dict(tp=tp, fp=fp, fn=fn,
                precision=round(prec, 3),
                recall=round(rec, 3),
                f1=round(f1, 3))


# ── Step 5: メイン ────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  書誌エンティティ解決ベンチマーク")
    print("=" * 55 + "\n")

    gold = build_gold_set()
    gold.to_csv(OUT_DIR / "gold_set.tsv", sep="\t", index=False)

    # コスト概算（Haiku: $0.80/1M input tokens）
    est_tokens = len(gold) * 250
    est_cost_usd = est_tokens / 1_000_000 * 0.80
    print(f"LLM API費用概算: ~${est_cost_usd:.3f} USD ({len(gold)}件 × ~250 tokens)\n")

    client = OpenAI()
    gold_qids = gold["qid"].tolist()
    b1_preds, b2_preds, llm_preds = [], [], []
    rows = []

    for idx, row in gold.iterrows():
        n = idx + 1
        title  = str(row["title"])
        author = str(row["author_name"]) if pd.notna(row["author_name"]) else ""
        year   = int(row["first_publish_year"])
        gqid   = str(row["qid"])

        print(f"[{n:>2}/{len(gold)}] {title[:45]:<45} ({year})")

        # Baseline-1
        b1 = baseline1_top1(title)
        time.sleep(SLEEP_WIKIDATA)

        # Baseline-2
        b2 = baseline2_fuzzy(title)
        time.sleep(SLEEP_WIKIDATA)

        # LLM
        llm_raw = llm_resolve(title, author, year, client)
        time.sleep(SLEEP_LLM)

        # no_match は「判定不能」として None 扱い
        llm = llm_raw if (llm_raw and llm_raw != "no_match") else None

        b1_preds.append(b1)
        b2_preds.append(b2)
        llm_preds.append(llm)

        marks = {
            "B1": "✓" if b1 == gqid else "✗",
            "B2": "✓" if b2 == gqid else "✗",
            "LLM": "✓" if llm == gqid else ("?" if llm_raw == "no_match" else "✗"),
        }
        print(
            f"       gold={gqid}  "
            f"B1={b1}{marks['B1']}  "
            f"B2={b2}{marks['B2']}  "
            f"LLM={llm_raw}{marks['LLM']}"
        )

        rows.append(dict(
            work_key=row["work_key"], title=title,
            author_name=author, first_publish_year=year,
            gold_qid=gqid,
            b1_pred=b1, b1_correct=(b1 == gqid),
            b2_pred=b2, b2_correct=(b2 == gqid),
            llm_pred=llm_raw, llm_correct=(llm == gqid),
        ))

    # ── 結果保存 ──
    df = pd.DataFrame(rows)
    out_path = OUT_DIR / "benchmark_results.tsv"
    df.to_csv(out_path, sep="\t", index=False)

    # ── スコア表示 ──
    print("\n" + "=" * 55)
    print("  評価結果")
    print("=" * 55)
    for name, preds in [
        ("Baseline-1  (Wikidata top-1)", b1_preds),
        ("Baseline-2  (top-5 + fuzzy≥80)", b2_preds),
        ("LLM         (Claude Haiku)", llm_preds),
    ]:
        s = evaluate(gold_qids, preds)
        print(f"\n{name}")
        print(f"  TP={s['tp']:>2}  FP={s['fp']:>2}  FN={s['fn']:>2}")
        print(f"  Precision={s['precision']:.3f}  Recall={s['recall']:.3f}  F1={s['f1']:.3f}")

    # ── 誤答分析 ──
    print("\n" + "=" * 55)
    print("  LLM 誤答・棄権ケース（申請書の失敗事例候補）")
    print("=" * 55)
    errors = df[~df["llm_correct"]]
    if len(errors) == 0:
        print("  （誤答なし）")
    for _, r in errors.iterrows():
        status = "no_match" if r["llm_pred"] == "no_match" else f"誤答={r['llm_pred']}"
        print(f"  {r['title']:<40} gold={r['gold_qid']}  {status}")

    print(f"\n結果ファイル: {out_path}")
    print("完了\n")


if __name__ == "__main__":
    main()