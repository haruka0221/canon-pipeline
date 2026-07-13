"""
validate_body_quotations.py — Phase 1c 精度検証ツール

用途:
  1. カテゴリ別サンプルを目視確認用に出力
  2. 手動修正を入力してFスコア計算
  3. Phase 1b との対比テーブル出力

使用方法:
  # サンプル出力（各カテゴリ20件ずつ）
  python3 validate_body_quotations.py --tsv derived/ci_body_quotations/classifications.tsv --sample 20

  # 対比テーブル出力（Phase 1b との比較）
  python3 validate_body_quotations.py --tsv derived/ci_body_quotations/classifications.tsv --compare
"""

import argparse
import csv
import random
from pathlib import Path
from collections import defaultdict


LABEL = {
    "A": "批評家・理論家",
    "B": "作家語（作品外）",
    "C": "文学作品テキスト",
    "D": "その他一次資料",
    "X": "判定不能",
}

# Phase 1b の確定値（論文使用値・カテゴリ0除く実質比率）
PHASE_1B_STATS = {
    "4(A)": {"count": 5694, "pct_count": 76.9, "label": "二次的学術文献 → A"},
    "1a(C)": {"count": 669, "pct_count": 9.0,  "label": "文学・芸術テキスト → C"},
    "1b(D)": {"count": 714, "pct_count": 9.6,  "label": "哲学・政治テキスト → D"},
    "2(-)":  {"count": 141, "pct_count": 1.9,  "label": "社会的流通証拠"},
    "3(-)":  {"count": 137, "pct_count": 1.9,  "label": "制度的証拠"},
    "5(-)":  {"count": 46,  "pct_count": 0.6,  "label": "定量的書誌データ"},
}


def load_tsv(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rows.append(row)
    return rows


def sample_by_category(rows: list[dict], n: int, out_dir: Path) -> None:
    """カテゴリ別にサンプルを抽出してTSVに出力"""
    by_cat: dict[str, list] = defaultdict(list)
    for row in rows:
        cat = row.get("category", "?")
        by_cat[cat].append(row)

    out_dir.mkdir(parents=True, exist_ok=True)
    sample_path = out_dir / "validation_sample.tsv"

    all_samples = []
    print("\n【サンプル抽出】")
    for cat in ["A", "B", "C", "D", "X"]:
        pool = by_cat.get(cat, [])
        k = min(n, len(pool))
        sample = random.sample(pool, k)
        for s in sample:
            s["_sample_cat"] = cat
        all_samples.extend(sample)
        print(f"  {cat} ({LABEL[cat]}): {len(pool)}件中 {k}件をサンプル")

    # 出力
    fields = ["_sample_cat", "quot_id", "pdf_file", "page_num",
              "quot_type", "word_count", "ref_hint", "category",
              "text", "context_before", "context_after"]

    with open(sample_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_samples)

    print(f"\n  → {sample_path} に出力（計{len(all_samples)}件）")
    print("  ※ category列を手動修正して validated_category列を追加→精度計算に使用")

    # コンソール表示（最初の3件）
    print("\n【サンプルプレビュー（各カテゴリ最初の1件）】")
    shown = set()
    for row in all_samples:
        cat = row["_sample_cat"]
        if cat not in shown:
            shown.add(cat)
            text_preview = row["text"][:100].replace("\n", " ")
            ref = row.get("ref_hint", "")
            print(f"\n  ─ {cat}: {LABEL[cat]}")
            print(f"    タイプ: {row['quot_type']}, {row['word_count']}語")
            if ref:
                print(f"    参照ヒント: {ref}")
            print(f"    テキスト: 「{text_preview}…」")
            print(f"    直後文脈: {row['context_after'][:80]}…")


def compare_with_phase1b(rows: list[dict]) -> None:
    """Phase 1b の脚注分布と本文引用分布の対比テーブルを出力"""

    count_by_cat: dict[str, int] = defaultdict(int)
    words_by_cat: dict[str, int] = defaultdict(int)

    for row in rows:
        cat = row.get("category", "?")
        wc  = int(row.get("word_count", 0))
        count_by_cat[cat] += 1
        words_by_cat[cat] += wc

    total = len(rows)
    total_classified = sum(count_by_cat[c] for c in "ABCD")
    total_words = sum(words_by_cat.values())
    total_words_abcd = sum(words_by_cat[c] for c in "ABCD")

    print("\n" + "="*70)
    print("【Phase 1b（脚注）vs Phase 1c（本文引用）対比】")
    print("="*70)
    print(f"\n  [Phase 1b] 脚注 n=7,401件（カテゴリ0除く）")
    print(f"  [Phase 1c] 本文引用 n={total}件（全件）/ {total_classified}件（A–D）\n")

    print(f"  {'対応':<14} {'Phase 1b':>9} {'':>6}  {'Phase 1c件数':>12} {'':>6} {'Phase 1c語数':>12} {'':>6}")
    print("-"*70)

    # A: 批評家
    n_1c_a = count_by_cat["A"]
    w_1c_a = words_by_cat["A"]
    pct_1c_a_n = n_1c_a / total_classified * 100 if total_classified else 0
    pct_1c_a_w = w_1c_a / total_words_abcd * 100 if total_words_abcd else 0
    print(f"  A 批評家     1b:76.9%  →  {n_1c_a:>6}件 {pct_1c_a_n:>5.1f}%   {w_1c_a:>8}語 {pct_1c_a_w:>5.1f}%")

    # B: 作家語（Phase 1bに明示的対応なし）
    n_1c_b = count_by_cat["B"]
    w_1c_b = words_by_cat["B"]
    pct_1c_b_n = n_1c_b / total_classified * 100 if total_classified else 0
    pct_1c_b_w = w_1c_b / total_words_abcd * 100 if total_words_abcd else 0
    print(f"  B 作家語     1b: N/A   →  {n_1c_b:>6}件 {pct_1c_b_n:>5.1f}%   {w_1c_b:>8}語 {pct_1c_b_w:>5.1f}%")

    # C: 文学作品テキスト
    n_1c_c = count_by_cat["C"]
    w_1c_c = words_by_cat["C"]
    pct_1c_c_n = n_1c_c / total_classified * 100 if total_classified else 0
    pct_1c_c_w = w_1c_c / total_words_abcd * 100 if total_words_abcd else 0
    print(f"  C 文学作品   1b: 9.0%  →  {n_1c_c:>6}件 {pct_1c_c_n:>5.1f}%   {w_1c_c:>8}語 {pct_1c_c_w:>5.1f}%")

    # D: その他一次資料
    n_1c_d = count_by_cat["D"]
    w_1c_d = words_by_cat["D"]
    pct_1c_d_n = n_1c_d / total_classified * 100 if total_classified else 0
    pct_1c_d_w = w_1c_d / total_words_abcd * 100 if total_words_abcd else 0
    print(f"  D その他一次  1b: 9.6%  →  {n_1c_d:>6}件 {pct_1c_d_n:>5.1f}%   {w_1c_d:>8}語 {pct_1c_d_w:>5.1f}%")

    print("-"*70)
    print(f"  計            1b:100%   →  {total_classified:>6}件             {total_words_abcd:>8}語")
    print("="*70)

    print("\n【解釈の手引き】")
    print(f"  ・件数比率 vs 語数比率の乖離に注目（Cは件数少なくても語数多い可能性）")
    print(f"  ・block vs inline の内訳も summary_stats.tsv に記録済み")
    print(f"  ・X（判定不能）が多い場合はプロンプト修正または手動補完を検討")


def distribution_by_quot_type(rows: list[dict]) -> None:
    """ブロック引用とインライン引用の分布を出力"""
    block_cat: dict[str, int] = defaultdict(int)
    inline_cat: dict[str, int] = defaultdict(int)

    for row in rows:
        cat = row.get("category", "?")
        if row.get("quot_type") == "block":
            block_cat[cat] += 1
        else:
            inline_cat[cat] += 1

    print("\n【引用タイプ別カテゴリ分布】")
    print(f"  {'カテゴリ':<20}{'ブロック':>10}{'インライン':>12}")
    print("-"*42)
    for cat in ["A", "B", "C", "D", "X"]:
        b = block_cat.get(cat, 0)
        i = inline_cat.get(cat, 0)
        if b + i > 0:
            print(f"  {cat} {LABEL[cat]:<18}{b:>10}{i:>12}")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--tsv",     required=True, help="classifications.tsv のパス")
    p.add_argument("--sample",  type=int, default=20, help="カテゴリ別サンプル件数")
    p.add_argument("--compare", action="store_true", help="Phase 1b 対比テーブル出力")
    p.add_argument("--out-dir", default="derived/ci_body_quotations")
    return p.parse_args()


def main():
    args = parse_args()
    tsv_path = Path(args.tsv)

    if not tsv_path.exists():
        print(f"⚠ ファイルが見つかりません: {tsv_path}")
        return

    rows = load_tsv(tsv_path)
    print(f"読み込み: {len(rows)}件")

    sample_by_category(rows, args.sample, Path(args.out_dir))
    distribution_by_quot_type(rows)

    if args.compare:
        compare_with_phase1b(rows)


if __name__ == "__main__":
    main()