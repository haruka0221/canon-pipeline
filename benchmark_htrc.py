#!/usr/bin/env python3
"""
benchmark_htrc.py
HathiTrust LLM再照合ベンチマーク
OCLC照合で失敗した1923年以前のcanonical作品をタイトル検索+LLMで再挑戦
"""

from openai import OpenAI
import pandas as pd, time, json, re
from pathlib import Path
from rapidfuzz import fuzz

client = OpenAI()
MODEL  = "gpt-5.4"
OUTDIR = Path("derived/benchmark")
OUTDIR.mkdir(exist_ok=True)

# ── データ読み込み ──────────────────────────────────────
htrc_all = pd.read_csv("data/htrc-fiction_metadata.csv",
                        dtype={"oclc": str, "startdate": str},
                        low_memory=False)
htrc_all["title_norm"] = htrc_all["title"].fillna("").str.lower().str.strip()
htrc_all["author_norm"] = htrc_all["author"].fillna("").str.lower().str.strip()

# ── 対象作品リスト（除外2件済み）──────────────────────
targets = [
    {"work_id": "/works/OL35695219W", "title": "Ulysses",
     "author": "James Joyce", "year": 1922},
    {"work_id": "/works/OL31971259W", "title": "Heart of Darkness",
     "author": "Joseph Conrad", "year": 1899},
    {"work_id": "/works/OL86320W",    "title": "Dubliners",
     "author": "James Joyce", "year": 1914},
    {"work_id": "/works/OL82929W",    "title": "As I Lay Dying",
     "author": "William Faulkner", "year": 1915},
    {"work_id": "/works/OL40252771W", "title": "The Turn of the Screw",
     "author": "Henry James", "year": 1898},
    {"work_id": "/works/OL35383W",    "title": "Three Lives",
     "author": "Gertrude Stein", "year": 1909},
    {"work_id": "/works/OL14864528W", "title": "The Rise of David Levinsky",
     "author": "Abraham Cahan", "year": 1917},
    {"work_id": "/works/OL39329W",    "title": "Jacob's Room",
     "author": "Virginia Woolf", "year": 1922},
    {"work_id": "/works/OL20839W",    "title": "Maggie: A Girl of the Streets",
     "author": "Stephen Crane", "year": 1893},
    {"work_id": "/works/OL88813W",    "title": "A Room with a View",
     "author": "E. M. Forster", "year": 1905},
    {"work_id": "/works/OL468362W",   "title": "The Beautiful and Damned",
     "author": "F. Scott Fitzgerald", "year": 1920},
    {"work_id": "/works/OL7461553W",  "title": "The Innocents",
     "author": "Alfred Machard", "year": 1918},
    {"work_id": "/works/OL15062619W", "title": "Dracula",
     "author": "Bram Stoker", "year": 1897},  # FORCE_MAPバグ修正
    {"work_id": "/works/OL7842965W",  "title": "Trelawny",
     "author": "Holman Freeland", "year": 1903},
    {"work_id": "/works/OL715553W",   "title": "New Grub Street",
     "author": "George Gissing", "year": 1891},
    {"work_id": "/works/OL18397742W", "title": "The North Star",
     "author": "M. E. Henry-Ruffin", "year": 1904},
]

# ── ステップ1：fuzzyタイトル候補抽出 ─────────────────
def get_candidates(title: str, author: str, top_n: int = 15) -> pd.DataFrame:
    title_norm = title.lower().strip()
    author_last = author.split()[-1].lower()

    # タイトルfuzzyスコア計算
    htrc_all["score"] = htrc_all["title_norm"].apply(
        lambda t: fuzz.token_sort_ratio(title_norm, t)
    )
    # 著者姓を含むものにボーナス
    htrc_all["author_bonus"] = htrc_all["author_norm"].apply(
        lambda a: 5 if author_last in a else 0
    )
    htrc_all["total_score"] = htrc_all["score"] + htrc_all["author_bonus"]

    top = htrc_all.nlargest(top_n, "total_score")[
        ["htid", "title", "author", "date", "total_score", "prob80precise"]
    ].copy()
    return top

# ── ステップ2：LLM判定 ────────────────────────────────
SYSTEM = """You are a bibliographic expert matching literary works to library catalog records.

Given a target work (title, author, year) and a list of HathiTrust catalog candidates,
identify which candidate(s) are editions of the target work.

Rules:
- The target work may appear under slightly different titles (e.g. "The Turn of the Screw" vs "Turn of the Screw")
- Multiple editions of the same work are all valid matches
- Return ONLY the htids of matching records, one per line
- If no candidates match the target work, return: NO_MATCH
- Do NOT match compilations or anthologies unless the target is clearly the main work

Respond with ONLY htids (one per line) or NO_MATCH."""

def llm_judge(title: str, author: str, year: int,
              candidates: pd.DataFrame) -> list[str]:
    cand_text = "\n".join(
        f"  htid={row.htid} | title={row.title!r} | "
        f"author={row.author!r} | date={row.date}"
        for _, row in candidates.iterrows()
    )
    msg = (f"Target: {title!r} by {author} ({year})\n\n"
           f"Candidates:\n{cand_text}\n\n"
           f"Which htids are editions of the target work?")

    resp = client.responses.create(
        model=MODEL,
        instructions=SYSTEM,
        input=msg
    )
    raw = resp.output_text.strip()
    if raw == "NO_MATCH" or not raw:
        return []
    return [h.strip() for h in raw.splitlines() if h.strip().startswith("htid=") == False and h.strip()]

# ── メイン処理 ────────────────────────────────────────
print("=" * 60)
print("  HathiTrust LLM再照合ベンチマーク（n=16）")
print("=" * 60)

results = []
for t in targets:
    print(f"\n▶ {t['title']} / {t['author']} ({t['year']})")

    # Step1: fuzzy候補
    cands = get_candidates(t["title"], t["author"], top_n=15)
    print(f"  fuzzy top候補: {len(cands)}件 (最高スコア={cands['total_score'].max():.0f})")

    # Step2: LLM判定
    matched_htids = llm_judge(t["title"], t["author"], t["year"], cands)
    time.sleep(0.5)

    found = len(matched_htids) > 0
    print(f"  LLM結果: {'✓ ' + str(len(matched_htids)) + '件一致' if found else '✗ NO_MATCH'}")
    if found:
        for htid in matched_htids[:3]:
            row = htrc_all[htrc_all["htid"] == htid]
            if not row.empty:
                print(f"    → {htid}: {row.iloc[0]['title']!r} ({row.iloc[0]['date']})")

    results.append({
        "work_id": t["work_id"],
        "title": t["title"],
        "author": t["author"],
        "year": t["year"],
        "n_candidates": len(cands),
        "top_fuzzy_score": int(cands["total_score"].max()),
        "llm_matched": found,
        "n_matched_htids": len(matched_htids),
        "matched_htids": "|".join(matched_htids[:5]),
    })

# ── 集計 ──────────────────────────────────────────────
solved = sum(1 for r in results if r["llm_matched"])
total  = len(results)
print(f"\n{'=' * 60}")
print(f"  結果: {solved}/{total} 件で照合成功")
print(f"  OCLC識別子照合では全件失敗していたケース")
print(f"{'=' * 60}")

# 保存
out = pd.DataFrame(results)
out.to_csv(OUTDIR / "htrc_llm_benchmark.tsv", sep="\t", index=False)
print(f"\n→ derived/benchmark/htrc_llm_benchmark.tsv")
