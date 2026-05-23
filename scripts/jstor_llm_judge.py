import anthropic, time
import pandas as pd
from pathlib import Path

client = anthropic.Anthropic()

# 要判定の候補（手動で絞り込んだもの）
to_judge = {
    "White Fang (Jack London, 1906)": [
        "White Fang / Walt Foreman / Ploughshares / 1999"
    ],
    "Tarzan of the Apes (Edgar Rice Burroughs, 1914)": [
        "Tarzan of the Apes / Frederick Rebsamen / The Antioch Review"
    ],
    "The Sea Witch (Alexander Laing, 1933)": [
        "The Sea Witch / Carolyn Turgeon / Fairy Tale Review"
    ],
    "The Innocents (Alfred Machard, 1925)": [
        "Book Review: THE INNOCENTS / Edward D. Radin / American Bar Association Journal",
        "Book Review: The Innocents / Anne Fontaine / Film Comment",
        "Romancing the Stones: Jack Clayton's The Innocents / Donald Chase / Film Comment",
        "The Innocents / Ellen Bryant Voigt / Harvard Book Review",
        "Book Review: The Innocents / Clyde Ware / Western American Literature",
    ],
    "The Golden Cage (Iris Bromige, 1949)": [
        "The Golden Cage: Stability of the Institution of Marriage in India / K Srinivasan / Economic and Political Weekly",
        "Book Review: The Golden Cage (The Enigma of Anorexia Nervosa) / Hilde Bruch / Psychotherapy and Psychosomatics",
        "Book Review: The Golden Cage: Regeneration in Lusophone / David Brookshaw / Research in African Literatures",
    ],
}

results = []
for target, candidates in to_judge.items():
    cand_text = "\n".join([f"{i+1}. {c}" for i, c in enumerate(candidates)])
    prompt = f"""You are a literary scholar. For each candidate, judge whether it is a scholarly paper about the novel "{target}".

Candidates:
{cand_text}

Reply format: "1. YES - reason" or "1. NO - reason"
Only YES if clearly about this specific novel."""

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    text = resp.content[0].text
    yes_count = text.count("YES")
    print(f"\n{target}")
    print(text)
    results.append({
        "target": target,
        "candidates": len(candidates),
        "relevant": yes_count,
        "response": text
    })
    time.sleep(1)

print("\n=== 最終集計 ===")
confirmed = ["The Moon and Sixpence", "The Yearling"]
print(f"論文あり確定: {confirmed}")
for r in results:
    status = "あり" if r["relevant"] > 0 else "なし"
    print(f"{r['target'][:40]}: {status}（{r['relevant']}/{r['candidates']}件）")
