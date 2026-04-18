#!/usr/bin/env python3
"""
classify_ci_footnotes.py
CI脚注8,940行をLLMで証拠タイプ分類する
チェックポイント機能付き（中断・再開可能）
"""

from openai import OpenAI
import pandas as pd, time, json
from pathlib import Path

MODEL  = "gpt-5.4"
OUTDIR = Path("derived/ci_footnote_classification")
OUTDIR.mkdir(exist_ok=True)
CKPT   = OUTDIR / "checkpoint.jsonl"   # 途中経過
FINAL  = OUTDIR / "classifications.tsv"

client = OpenAI()

SYSTEM = """You classify footnotes from Critical Inquiry (a literary studies journal).
IMPORTANT: Text may have spaces removed due to PDF extraction.
"SeeHarrietMartineau" means "See Harriet Martineau". Read accordingly.

Classify the footnote into ONE category:

1 = TEXT_EVIDENCE
  Direct reference to or quotation from the CONTENT of a literary/artistic work.
  The footnote is evidence about WHAT a text says, contains, or means.
  Examples: quoting a passage, citing a specific page for a plot point,
            referencing a scene or character's words.

2 = SOCIAL_CIRCULATION
  Evidence about HOW a work moved through society.
  Includes: book reviews, newspaper coverage, publication/edition history,
            translation records, reader letters, lending/borrowing records,
            sales figures mentioned in passing, correspondence about reception.
  Key signal: the footnote documents a SOCIAL EVENT around a text, not the text itself.

3 = INSTITUTIONAL
  Evidence about formal institutional treatment of works.
  Includes: syllabi/reading lists, prize/award records, publisher decisions,
            censorship records, library acquisition policies, canon-formation documents.

4 = SECONDARY_SCHOLARSHIP
  References to other critics, theorists, or scholars.
  Includes: academic books, journal articles, critical essays, theoretical works.
  Key signal: the footnote cites someone's ARGUMENT or INTERPRETATION.

5 = QUANTITATIVE_BIBLIOGRAPHIC
  Any numerical/statistical data about texts or authors.
  Includes: citation counts, library holding statistics, survey results,
            publication counts, readership numbers.

0 = OTHER
  Does not fit above: biographical notes, copyright notices,
  methodological notes, self-referential notes ("see chapter 3"), etc.

Reply with ONLY a single digit: 0, 1, 2, 3, 4, or 5."""


def classify(text: str) -> str:
    try:
        r = client.responses.create(
            model=MODEL,
            instructions=SYSTEM,
            input=f"Footnote:\n{text[:600]}")
        raw = r.output_text.strip()
        for ch in raw:
            if ch in "012345":
                return ch
        return "0"
    except Exception as e:
        print(f"    [API Error] {e}")
        time.sleep(5)
        return "E"


def main():
    df = pd.read_csv("derived/ci_footnotes.tsv", sep="\t",
                     dtype=str, low_memory=False)
    print(f"Total footnotes: {len(df)}")

    # チェックポイント読み込み（再開用）
    done = {}
    if CKPT.exists():
        with open(CKPT) as f:
            for line in f:
                rec = json.loads(line)
                done[rec["idx"]] = rec["category"]
        print(f"Resuming: {len(done)} already done")

    # 分類ループ
    ckpt_handle = open(CKPT, "a")
    for i, row in df.iterrows():
        if i in done:
            continue

        text = str(row.get("fn_text", ""))
        cat  = classify(text)
        done[i] = cat

        rec = {"idx": i,
               "filename": str(row.get("filename", "")),
               "fn_num":   str(row.get("fn_num", "")),
               "category": cat}
        ckpt_handle.write(json.dumps(rec) + "\n")
        ckpt_handle.flush()

        if i % 200 == 0:
            print(f"  [{i}/{len(df)}] cat={cat} | "
                  f"{text[:80].replace(chr(10),' ')}")
        time.sleep(0.08)   # Haiku rate limit対策

    ckpt_handle.close()

    # 最終TSV出力
    df["category"] = df.index.map(done)
    df.to_csv(FINAL, sep="\t", index=False)

    # 集計
    CAT_LABELS = {
        "1": "テキスト証拠         (TEXT_EVIDENCE)",
        "2": "社会的流通証拠       (SOCIAL_CIRCULATION)",
        "3": "制度的証拠           (INSTITUTIONAL)",
        "4": "二次的学術文献       (SECONDARY_SCHOLARSHIP)",
        "5": "定量的書誌データ     (QUANTITATIVE_BIBLIOGRAPHIC)",
        "0": "その他               (OTHER)",
        "E": "APIエラー",
    }
    counts = df["category"].value_counts().to_dict()
    total  = len(df)

    print(f"\n{'='*55}")
    print(f"  分類結果（n={total}）")
    print(f"{'='*55}")
    for k, label in CAT_LABELS.items():
        n   = counts.get(k, 0)
        pct = n / total * 100
        print(f"  {k}  {label}: {n:4d}  ({pct:5.1f}%)")
    print(f"{'='*55}")
    print(f"\n→ {FINAL}")
    print(f"→ {CKPT}  （中断時の再開用）")


if __name__ == "__main__":
    main()
