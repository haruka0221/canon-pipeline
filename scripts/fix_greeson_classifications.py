"""
fix_greeson_classifications.py
Greeson 2025の誤分類を手動修正し、全論文のノイズ（脚注・著者紹介）を除外する

修正内容:
  1. Greeson 2025: C→D（Hobbes EL・植民地文書18件中17件）
  2. Greeson 2025: A→D（HobbesがAに誤分類された10件）
  3. Greeson 2025: A→除外（脚注・著者紹介・メタデータ13件）
  4. 全論文: blockのノイズ除外（著者紹介バイオ・脚注テキスト・図版キャプション）

出力:
  derived/ci_body_quotations/classifications_v3_fixed.tsv
  derived/ci_body_quotations/summary_stats_v3_fixed.tsv
"""

import csv
import re
from pathlib import Path
from collections import defaultdict

IN_TSV  = "derived/ci_body_quotations/classifications_v3.tsv"
OUT_TSV = "derived/ci_body_quotations/classifications_v3_fixed.tsv"
OUT_SUM = "derived/ci_body_quotations/summary_stats_v3_fixed.tsv"

# ────────────────────────────────────────────────────
# ノイズ判定（著者紹介・脚注・図版キャプション）
# ────────────────────────────────────────────────────

# 著者紹介バイオの特徴: "is associate/assistant/professor of"
AUTHOR_BIO_RE = re.compile(
    r'\bis\s+(associate|assistant|full)?\s*professor\s+of\b'
    r'|\bis\s+an?\s+(associate|assistant)?\s*professor\b'
    r'|\bPh\.?D\.?\s+candidate\b'
    r'|\bpostdoctoral\s+(fellow|researcher)\b',
    re.IGNORECASE
)

# 脚注テキストの特徴: 行頭が数字+ピリオド or "See " + 書誌情報
FOOTNOTE_RE = re.compile(
    r'^\s*\d{1,3}\.\s+(?:See|Ibid|Quoted|For|Compare|Note|cf\.)',
    re.IGNORECASE
)

# 論文メタデータ: "Critical Inquiry, volume N"
CI_META_RE = re.compile(r'Critical Inquiry,\s+volume\s+\d+', re.IGNORECASE)

# 謝辞テキスト: "I'd like to thank"
THANKS_RE = re.compile(r"I(?:'d| would) like to thank\b", re.IGNORECASE)

# 図版キャプション: "FIGURE N."
FIGURE_RE = re.compile(r'^FIGURE\s+\d+[\.\s]', re.IGNORECASE)

def is_noise(row: dict) -> bool:
    """著者紹介・脚注・メタデータ・図版キャプションを除外"""
    text = row.get("text", "")
    return bool(
        AUTHOR_BIO_RE.search(text)
        or CI_META_RE.search(text)
        or THANKS_RE.search(text)
        or FIGURE_RE.match(text)
        or (row.get("quot_type") == "block" and FOOTNOTE_RE.match(text))
    )

# ────────────────────────────────────────────────────
# Greeson 2025 の個別修正ルール
# quot_idのページ番号 + テキスト冒頭でマッチ
# ────────────────────────────────────────────────────

# C→D: Hobbes EL・植民地文書（ELref付き・または植民地文書固有フレーズ）
GREESON_C_TO_D_PATTERNS = [
    re.compile(r'\(EL'),                    # Hobbes Elements of Law
    re.compile(r'\(TC'),                    # Somers Islands文書
    re.compile(r'execuccon of the sentence'),
    re.compile(r'cons\[ign him\]'),
    re.compile(r'inhabitants themselves are all'),
    re.compile(r'cannott be \[under taken\]'),
    re.compile(r'iudgment of a Company'),
    re.compile(r'King \.+\.hates all assemblies'),
    re.compile(r'Good therefore.*sort of Government', re.DOTALL),
    re.compile(r'nothing really.*motion in some internal', re.DOTALL),
    re.compile(r'estate of men.*natural liberty', re.DOTALL),
    re.compile(r'invasion on the one part.*resistance', re.DOTALL),
    re.compile(r'that he is his.*may of any other thing', re.DOTALL),
    re.compile(r'goods of the master in perpetuum'),
]

# C→A: 批評家の文（"he devoted at least half his time"）
GREESON_C_TO_A_PATTERNS = [
    re.compile(r'he devoted at least half his time'),
]

# A→D: AにいるHobbesテキスト（ELref付き or Hobbes固有フレーズ）
GREESON_A_TO_D_PATTERNS = [
    re.compile(r'\(EL'),
    re.compile(r'Reason.*is nothing but Reckoning', re.DOTALL),
    re.compile(r'nothing more nor less than the justification of Tyranny'),
    re.compile(r'are nothing really.*motion', re.DOTALL),
    re.compile(r'it does not matter if we have a knife'),
    re.compile(r'wars, invasions, pillage, dispossessions'),
    re.compile(r'refus\[ed\] to recognize consent'),
    re.compile(r'deprive\[d enslaved people\]'),
]

# A→除外: 脚注・著者紹介・メタデータ（Greeson固有）
GREESON_A_NOISE_PATTERNS = [
    re.compile(r"I(?:'d| would) like to thank"),
    re.compile(r'Critical Inquiry, volume'),
    re.compile(r'Jennifer Rae Greeson is associate'),
    re.compile(r'^\s*\d{1,2}\.\s+(?:See|The|For|Compare|Hobbes|Quoted)', re.IGNORECASE),
    re.compile(r'Willams.*American Indian in Western'),
    re.compile(r'Katharine Gerbner'),
    re.compile(r'Eric Williams.*Origin of Negro Slavery'),
    re.compile(r'Kingsbery assembles'),
    re.compile(r'For an overview of this vein'),
    re.compile(r'Jean Jacquot.*Sir Charles Cavendish'),
    re.compile(r'Logically, then, Robert Nichols'),
    re.compile(r'Tercentenary of the English Revolution'),
    re.compile(r"Hobbes's name first appears in the Records"),
]

def fix_greeson(row: dict) -> dict:
    """Greeson 2025の分類を修正"""
    text = row.get("text", "")
    cat  = row.get("category", "")

    if cat == "C":
        for pat in GREESON_C_TO_A_PATTERNS:
            if pat.search(text):
                row = dict(row); row["category"] = "A"; return row
        for pat in GREESON_C_TO_D_PATTERNS:
            if pat.search(text):
                row = dict(row); row["category"] = "D"; return row

    elif cat == "A":
        for pat in GREESON_A_NOISE_PATTERNS:
            if pat.search(text):
                row = dict(row); row["category"] = "0"; return row
        for pat in GREESON_A_TO_D_PATTERNS:
            if pat.search(text):
                row = dict(row); row["category"] = "D"; return row

    elif cat == "D":
        if FIGURE_RE.match(text):
            row = dict(row); row["category"] = "0"; return row

    elif cat == "X":
        # X→除外（脚注テキスト）
        if FOOTNOTE_RE.match(text) or re.match(r'^\s*\d{1,3}\.\s+', text):
            row = dict(row); row["category"] = "0"; return row

    return row

# ────────────────────────────────────────────────────
# メイン処理
# ────────────────────────────────────────────────────

def main():
    rows = []
    with open(IN_TSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)

    print(f"読み込み: {len(rows)}件")

    # 変更カウンター
    changes = defaultdict(int)
    noise_removed = 0

    fixed_rows = []
    for row in rows:
        original_cat = row["category"]
        is_greeson = "Greeson" in row.get("pdf_file", "")

        # Step 1: 全論文のノイズ除外
        if is_noise(row):
            row = dict(row)
            row["category"] = "0"
            noise_removed += 1
            changes[f"{original_cat}→0(noise)"] += 1
            fixed_rows.append(row)
            continue

        # Step 2: Greeson固有修正
        if is_greeson:
            fixed = fix_greeson(row)
            if fixed["category"] != original_cat:
                changes[f"{original_cat}→{fixed['category']}"] += 1
            fixed_rows.append(fixed)
        else:
            fixed_rows.append(row)

    # 結果サマリー
    print("\n【修正内容】")
    for change, count in sorted(changes.items()):
        print(f"  {change}: {count}件")

    # 統計（0除く）
    active = [r for r in fixed_rows if r["category"] not in ("0", "X", "?")]
    count_by_cat = defaultdict(int)
    words_by_cat = defaultdict(int)
    for r in active:
        cat = r["category"]
        count_by_cat[cat] += int(r.get("word_count", 0))
        words_by_cat[cat] += int(r.get("word_count", 0))

    count_by_cat2 = defaultdict(int)
    for r in active:
        count_by_cat2[r["category"]] += 1

    total_cls = len(active)
    total_wds = sum(int(r.get("word_count",0)) for r in active)

    labels = {"A":"批評家・理論家","B":"作家語(作品外)",
              "C":"文学作品テキスト","D":"その他一次資料"}

    print(f"\n【修正後サマリー】（0・X除く {total_cls}件）")
    print(f"  {'カテゴリ':<22}{'件数':>6}{'件数%':>7}{'語数':>9}{'語数%':>7}")
    print(f"  {'-'*52}")
    for cat in ["A","B","C","D"]:
        n = count_by_cat2[cat]
        w = sum(int(r.get("word_count",0)) for r in active if r["category"]==cat)
        pn = f"{n/total_cls*100:.1f}"
        pw = f"{w/total_wds*100:.1f}"
        print(f"  {cat} {labels[cat]:<20}{n:>6}{pn:>6}%{w:>9}{pw:>6}%")

    removed = sum(1 for r in fixed_rows if r["category"] == "0")
    x_count = sum(1 for r in fixed_rows if r["category"] == "X")
    print(f"\n  除外（ノイズ）: {removed}件")
    print(f"  X（判定不能）: {x_count}件")

    # 対比表示
    print(f"\n【Phase 1b vs Phase 1c 修正後】")
    print(f"  {'':22} {'脚注1b':>8} {'本文件数%':>10} {'本文語数%':>10}")
    phase1b = {"A":76.9, "C":9.0, "D":9.6, "B":"N/A"}
    for cat in ["A","B","C","D"]:
        n = count_by_cat2[cat]
        w = sum(int(r.get("word_count",0)) for r in active if r["category"]==cat)
        b = f"{phase1b[cat]}%" if phase1b[cat] != "N/A" else "N/A"
        print(f"  {cat} {labels[cat]:<20} {b:>8} {n/total_cls*100:>9.1f}% {w/total_wds*100:>9.1f}%")

    # 保存
    fieldnames = list(rows[0].keys())
    with open(OUT_TSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(fixed_rows)
    print(f"\n保存: {OUT_TSV} ({len(fixed_rows)}件)")

if __name__ == "__main__":
    main()