"""
extract_body_quotations.py — Stage 7 Phase 1c
CI本文直接引用の抽出・分類パイプライン

対象: Critical Inquiry PDFs (2019–2025), 248ファイル
目的: 本文中のブロック引用・クォーテーション付き直接引用（3語以上）を抽出し、
      A(批評家)/B(作家言葉・作品外)/C(文学作品テキスト)/D(その他一次資料)に分類する

出力:
  derived/ci_body_quotations/
    quotations_raw.tsv       — 抽出済み全引用スパン（分類前）
    classifications.tsv      — LLM分類結果
    checkpoint.jsonl         — チェックポイント（中断再開用）
    summary_stats.tsv        — カテゴリ別件数・語数集計

使用方法:
  # Step 1のみ（抽出・LLM分類なし）: テスト・目視確認用
  python3 extract_body_quotations.py --step extract

  # Step 1+2（抽出→分類）: 本番実行
  python3 extract_body_quotations.py --step all

  # Step 2のみ（既存 quotations_raw.tsv から分類再実行）
  python3 extract_body_quotations.py --step classify

  # サンプルモード（最初の5ファイルのみ）: 動作確認用
  python3 extract_body_quotations.py --step all --sample 5

注意:
  - CI PDFのパスは WORKFLOW.md の記録に基づきデフォルト設定（--pdf-dir で変更可）
  - Anthropic APIキーは環境変数 ANTHROPIC_API_KEY から取得（Phase 1b と同様）
  - チェックポイントにより中断・再開が可能
"""

import os
import re
import json
import time
import argparse
import csv
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
import pdfplumber


# ────────────────────────────────────────────────
# 設定
# ────────────────────────────────────────────────

DEFAULT_PDF_DIR = "/mnt/c/Users/tsuts/Desktop/色々使えるデータ/Critical Inquiry"
DEFAULT_OUT_DIR = "derived/ci_body_quotations"
MIN_WORDS = 3          # 最小語数（3語以上を引用として扱う）
API_MODEL  = "claude-haiku-4-5-20251001"
API_SLEEP  = 0.3       # リクエスト間隔（秒）
BATCH_SIZE = 20        # チェックポイント保存間隔

# ────────────────────────────────────────────────
# 分類スキーム（Phase 1b の証拠タイプと対応）
# ────────────────────────────────────────────────

CLASSIFICATION_SCHEMA = """
あなたは文学研究の引用分類の専門家です。
以下の引用テキストとその文脈（前後の文）を読んで、引用元を分類してください。

【分類カテゴリ】
A  批評家・理論家・学者の言葉
   学術書、学術論文、批評エッセイ、理論書からの直接引用。
   フーコー、デリダ、モレッティ等の批評家・理論家が含まれる。
   ※ Phase 1b カテゴリ4 に対応

B  作家・芸術家の言葉（作品テキスト外）
   小説家・詩人・劇作家の書簡、日記、エッセイ、インタビュー、
   序文・後記、ノートブック等からの引用。
   作品テキストそのものではなく、作家自身の「語り」。
   ※ Phase 1b カテゴリ1a の一部に対応

C  文学・芸術作品テキストそのもの
   小説・詩・戯曲・映画・絵画タイトルからの直接引用。
   ページ番号や章番号が括弧で添えられていることが多い。
   ※ Phase 1b カテゴリ1a に対応

D  その他一次資料
   哲学・政治・法律・科学・歴史・宗教テキスト（作品テキスト外）。
   Plato、Hobbes、Wittgenstein等の非文学・非批評テキスト。
   新聞・政府文書・法的文書も含む。
   ※ Phase 1b カテゴリ1b に対応

X  判定不能
   文脈が不十分で分類できない場合のみ使用。

【回答形式】
カテゴリ記号（A/B/C/D/X）のみを1文字で回答してください。
理由や説明は不要です。
"""

# ────────────────────────────────────────────────
# データクラス
# ────────────────────────────────────────────────

@dataclass
class Quotation:
    """抽出された1件の引用"""
    quot_id: str          # 一意ID: {pdf_stem}_{page}_{idx}
    pdf_file: str         # PDFファイル名
    page_num: int         # ページ番号（1始まり）
    quot_type: str        # "block" or "inline"
    text: str             # 引用テキスト
    word_count: int       # 語数
    context_before: str   # 引用直前の文（最大200字）
    context_after: str    # 引用直後の文（最大200字）
    ref_hint: str         # 括弧内の参照ヒント（例: "Joyce 19", "Foucault 1977"）
    category: str = ""    # LLM分類結果（A/B/C/D/X）
    raw_response: str = ""  # LLM生の応答


# ────────────────────────────────────────────────
# Step 1: 引用スパン抽出
# ────────────────────────────────────────────────

# 括弧内参照パターン（引用直後に現れる書誌情報）
# 例: (Joyce 19), (Foucault 1977, 23), (Ulysses, p. 19), (2001, 34)
REF_PATTERN = re.compile(
    r'\(([^)]{2,80}?(?:\d{1,4}|p{1,2}\.\s*\d{1,4})[^)]{0,30})\)'
)

# インライン引用パターン: "..." または "..."
# 3語以上を保証するためword_countで後処理
INLINE_QUOTE_PATTERN = re.compile(
    r'["\u201c\u201d]([^"\u201c\u201d]{10,600})["\u201c\u201d]'
)

# ブロック引用の判定: pdfplumber のフォントサイズ・インデントで検出
BLOCK_INDENT_THRESHOLD = 30   # ポイント（左マージンがこれ以上なら候補）
BLOCK_FONT_RATIO       = 0.85  # 本文フォントの何倍以下ならブロック引用候補


def extract_ref_hint(text_after: str) -> str:
    """引用直後テキストから括弧内参照を抽出"""
    m = REF_PATTERN.search(text_after[:200])
    return m.group(1).strip() if m else ""


def count_words(text: str) -> int:
    return len(text.split())


def normalize_quote_text(text: str) -> str:
    """引用テキストの正規化"""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_from_pdf(pdf_path: Path) -> list[Quotation]:
    """1PDFから引用スパンを全件抽出"""
    quotations = []
    pdf_stem = pdf_path.stem

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            # 本文フォントサイズの推定（最頻値）
            all_sizes = []
            full_text_by_page = []

            for page in pdf.pages:
                words = page.extract_words(extra_attrs=["size"])
                sizes = [w["size"] for w in words if "size" in w and w["size"] > 0]
                all_sizes.extend(sizes)
                full_text_by_page.append(page.extract_text() or "")

            if not all_sizes:
                return []

            # 本文フォントサイズ（最頻値）
            from collections import Counter
            size_counter = Counter(round(s, 1) for s in all_sizes)
            body_font_size = size_counter.most_common(1)[0][0]

            # ページ別処理
            for page_idx, page in enumerate(pdf.pages):
                page_num = page_idx + 1
                page_text = full_text_by_page[page_idx]
                if not page_text:
                    continue

                quot_idx = 0

                # ── (1) ブロック引用検出 ──
                # pdfplumber のword単位でインデント・フォントサイズを確認
                words = page.extract_words(
                    extra_attrs=["size", "x0", "top"],
                    use_text_flow=True
                )

                # インデント・フォントサイズで候補行をグルーピング
                block_candidate_lines = []
                current_block_words = []
                current_block_x0 = None

                for w in words:
                    x0 = w.get("x0", 0)
                    size = w.get("size", body_font_size)

                    is_indented = x0 > BLOCK_INDENT_THRESHOLD + 20
                    is_smaller = size < body_font_size * BLOCK_FONT_RATIO

                    if is_indented or is_smaller:
                        current_block_words.append(w["text"])
                        if current_block_x0 is None:
                            current_block_x0 = x0
                    else:
                        if current_block_words:
                            block_text = " ".join(current_block_words)
                            if count_words(block_text) >= MIN_WORDS:
                                block_candidate_lines.append(block_text)
                            current_block_words = []
                            current_block_x0 = None

                # 残余処理
                if current_block_words:
                    block_text = " ".join(current_block_words)
                    if count_words(block_text) >= MIN_WORDS:
                        block_candidate_lines.append(block_text)

                for block_text in block_candidate_lines:
                    block_text = normalize_quote_text(block_text)
                    wc = count_words(block_text)
                    if wc < MIN_WORDS:
                        continue

                    # 前後文脈（ページテキストから）
                    pos = page_text.find(block_text[:30])
                    ctx_before = page_text[max(0, pos - 200):pos].strip() if pos > 0 else ""
                    ctx_after  = page_text[pos + len(block_text):pos + len(block_text) + 200].strip()
                    ref_hint   = extract_ref_hint(ctx_after)

                    q = Quotation(
                        quot_id=f"{pdf_stem}_p{page_num}_b{quot_idx}",
                        pdf_file=pdf_path.name,
                        page_num=page_num,
                        quot_type="block",
                        text=block_text,
                        word_count=wc,
                        context_before=ctx_before[-200:],
                        context_after=ctx_after[:200],
                        ref_hint=ref_hint,
                    )
                    quotations.append(q)
                    quot_idx += 1

                # ── (2) インライン引用検出 ──
                # 脚注テキストを除去してから本文テキストに適用
                # （簡易: 脚注は本文末尾の上付き数字以降とみなす）
                body_text = _remove_footnote_section(page_text)

                for m in INLINE_QUOTE_PATTERN.finditer(body_text):
                    quote_text = normalize_quote_text(m.group(1))
                    wc = count_words(quote_text)
                    if wc < MIN_WORDS:
                        continue

                    start = m.start()
                    end   = m.end()
                    ctx_before = body_text[max(0, start - 200):start].strip()
                    ctx_after  = body_text[end:end + 200].strip()
                    ref_hint   = extract_ref_hint(ctx_after)

                    q = Quotation(
                        quot_id=f"{pdf_stem}_p{page_num}_i{quot_idx}",
                        pdf_file=pdf_path.name,
                        page_num=page_num,
                        quot_type="inline",
                        text=quote_text,
                        word_count=wc,
                        context_before=ctx_before[-200:],
                        context_after=ctx_after[:200],
                        ref_hint=ref_hint,
                    )
                    quotations.append(q)
                    quot_idx += 1

    except Exception as e:
        print(f"  ⚠ 抽出エラー {pdf_path.name}: {e}")

    return quotations


def _remove_footnote_section(page_text: str) -> str:
    """
    簡易脚注除去: ページ末尾の脚注セクションをカット
    Phase 1b の ci_extract_citations.py と同じ方針
    """
    # 上付き数字 + 本文らしき文が始まる部分以降を除去
    # （簡易版: 行番号マーカーのみの行で分割）
    lines = page_text.split('\n')
    body_lines = []
    footnote_mode = False

    for line in lines:
        # 脚注開始の簡易判定: 行頭が数字1–2桁のみ（上付き数字が独立した行）
        if re.match(r'^\s*\d{1,2}\s*$', line):
            footnote_mode = True
        if not footnote_mode:
            body_lines.append(line)

    return '\n'.join(body_lines)


# ────────────────────────────────────────────────
# Step 2: LLM分類（Haiku・チェックポイント方式）
# ────────────────────────────────────────────────

def classify_quotations(
    quotations: list[Quotation],
    checkpoint_path: Path,
    out_dir: Path,
) -> list[Quotation]:
    """
    引用リストを Haiku で A/B/C/D/X に分類する
    Phase 1b と同じチェックポイント方式
    """
    import anthropic

    client = anthropic.Anthropic()

    # チェックポイント読み込み
    done_ids: dict[str, str] = {}
    if checkpoint_path.exists():
        with open(checkpoint_path) as f:
            for line in f:
                rec = json.loads(line)
                done_ids[rec["quot_id"]] = rec["category"]
        print(f"  チェックポイント: {len(done_ids)}件 再開")

    # 分類済みをマージ
    for q in quotations:
        if q.quot_id in done_ids:
            q.category = done_ids[q.quot_id]

    # 未分類の引用を処理
    todo = [q for q in quotations if not q.category]
    print(f"  分類対象: {len(todo)}件（分類済み: {len(quotations) - len(todo)}件）")

    checkpoint_file = open(checkpoint_path, "a")

    for i, q in enumerate(todo):
        prompt = _build_prompt(q)
        try:
            resp = client.messages.create(
                model=API_MODEL,
                max_tokens=10,
                system=CLASSIFICATION_SCHEMA,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip().upper()
            # A/B/C/D/X のみ受け付ける
            category = raw[0] if raw and raw[0] in "ABCDX" else "X"
        except Exception as e:
            print(f"    APIエラー (id={q.quot_id}): {e}")
            category = "X"
            raw = f"ERROR: {e}"

        q.category = category
        q.raw_response = raw

        rec = {"quot_id": q.quot_id, "category": category, "raw": raw}
        checkpoint_file.write(json.dumps(rec, ensure_ascii=False) + "\n")

        if (i + 1) % BATCH_SIZE == 0:
            checkpoint_file.flush()
            print(f"    進捗: {i+1}/{len(todo)} 件")

        time.sleep(API_SLEEP)

    checkpoint_file.close()
    return quotations


def _build_prompt(q: Quotation) -> str:
    """分類プロンプト構築"""
    ref = f"（参照ヒント: {q.ref_hint}）" if q.ref_hint else ""
    return f"""【引用テキスト（{q.quot_type}・{q.word_count}語）{ref}】
{q.text}

【直前の文脈】
{q.context_before[-300:] if q.context_before else '（なし）'}

【直後の文脈】
{q.context_after[:300] if q.context_after else '（なし）'}
"""


# ────────────────────────────────────────────────
# Step 3: 出力・集計
# ────────────────────────────────────────────────

TSV_FIELDS = [
    "quot_id", "pdf_file", "page_num", "quot_type",
    "word_count", "ref_hint", "category",
    "text", "context_before", "context_after", "raw_response",
]


def save_quotations_tsv(quotations: list[Quotation], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TSV_FIELDS, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        for q in quotations:
            row = asdict(q)
            # テキスト内の改行・タブをエスケープ
            row["text"]           = row["text"].replace("\n", " ").replace("\t", " ")
            row["context_before"] = row["context_before"].replace("\n", " ").replace("\t", " ")
            row["context_after"]  = row["context_after"].replace("\n", " ").replace("\t", " ")
            writer.writerow(row)
    print(f"  保存: {path} ({len(quotations)}件)")


def save_summary(quotations: list[Quotation], path: Path) -> None:
    """カテゴリ別件数・語数の集計サマリー"""
    from collections import defaultdict

    count_by_cat: dict[str, int]      = defaultdict(int)
    words_by_cat: dict[str, int]      = defaultdict(int)
    count_by_type: dict[str, dict]    = defaultdict(lambda: defaultdict(int))

    for q in quotations:
        cat = q.category or "?"
        count_by_cat[cat] += 1
        words_by_cat[cat] += q.word_count
        count_by_type[q.quot_type][cat] += 1

    total_count = len(quotations)
    total_words = sum(q.word_count for q in quotations)

    rows = []
    for cat in ["A", "B", "C", "D", "X", "?"]:
        n = count_by_cat[cat]
        w = words_by_cat[cat]
        rows.append({
            "category": cat,
            "label": {
                "A": "批評家・理論家",
                "B": "作家の言葉（作品外）",
                "C": "文学作品テキスト",
                "D": "その他一次資料",
                "X": "判定不能",
                "?": "未分類",
            }.get(cat, ""),
            "count": n,
            "pct_count": f"{n/total_count*100:.1f}" if total_count else "0",
            "total_words": w,
            "pct_words": f"{w/total_words*100:.1f}" if total_words else "0",
            "block_count": count_by_type["block"][cat],
            "inline_count": count_by_type["inline"][cat],
        })

    # Phase 1b 対比用: 分類0除く実質比率も出力
    classified = [q for q in quotations if q.category in "ABCD"]
    total_classified = len(classified)
    total_words_classified = sum(q.word_count for q in classified)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["category", "label", "count", "pct_count",
                        "total_words", "pct_words", "block_count", "inline_count"],
            delimiter="\t"
        )
        writer.writeheader()
        writer.writerows(rows)

        # 集計行
        f.write(f"\n# 総引用件数: {total_count}\n")
        f.write(f"# 総引用語数: {total_words}\n")
        f.write(f"# A–D分類済み: {total_classified}件\n")
        if total_classified:
            for cat in ["A", "B", "C", "D"]:
                n = count_by_cat[cat]
                w = words_by_cat[cat]
                f.write(
                    f"#   {cat}: {n}件 ({n/total_classified*100:.1f}%)  "
                    f"{w}語 ({w/total_words_classified*100:.1f}%)\n"
                )

    print(f"  集計保存: {path}")

    # コンソール表示
    print("\n" + "="*55)
    print(f"  【本文引用分類 サマリー】 総計{total_count}件・{total_words}語")
    print("="*55)
    print(f"  {'カテゴリ':<20}{'件数':>7}{'件数%':>7}{'語数':>9}{'語数%':>7}")
    print("-"*55)
    labels = {"A":"批評家・理論家","B":"作家語(作品外)","C":"文学作品テキスト","D":"その他一次資料","X":"判定不能","?":"未分類"}
    for row in rows:
        if row["count"] > 0:
            print(f"  {row['category']} {labels[row['category']]:<18}{row['count']:>7}{row['pct_count']:>6}%{row['total_words']:>9}{row['pct_words']:>6}%")
    print("="*55)


# ────────────────────────────────────────────────
# メイン
# ────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="CI本文引用抽出・分類（Phase 1c）")
    p.add_argument("--pdf-dir",  default=DEFAULT_PDF_DIR)
    p.add_argument("--out-dir",  default=DEFAULT_OUT_DIR)
    p.add_argument("--step",     choices=["extract", "classify", "all"],
                   default="all", help="実行ステップ")
    p.add_argument("--sample",   type=int, default=0,
                   help="サンプルモード: 最初のN件のPDFのみ処理")
    p.add_argument("--min-words", type=int, default=MIN_WORDS)
    return p.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_tsv        = out_dir / "quotations_raw.tsv"
    classified_tsv = out_dir / "classifications.tsv"
    checkpoint_path= out_dir / "checkpoint.jsonl"
    summary_tsv    = out_dir / "summary_stats.tsv"

    # PDF一覧取得
    pdf_dir = Path(args.pdf_dir)
    if not pdf_dir.exists():
        print(f"⚠ PDFディレクトリが見つかりません: {pdf_dir}")
        print("  --pdf-dir オプションで正しいパスを指定してください")
        return

    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if args.sample:
        pdf_files = pdf_files[:args.sample]
    print(f"対象PDF: {len(pdf_files)}件  出力先: {out_dir}")

    # ─── Step 1: 抽出 ─────────────────────────────
    if args.step in ("extract", "all"):
        print("\n【Step 1】本文引用スパン抽出")
        all_quotations: list[Quotation] = []

        for i, pdf_path in enumerate(pdf_files):
            print(f"  [{i+1}/{len(pdf_files)}] {pdf_path.name}")
            quots = extract_from_pdf(pdf_path)
            print(f"    → {len(quots)}件抽出 "
                  f"(block:{sum(1 for q in quots if q.quot_type=='block')} "
                  f"inline:{sum(1 for q in quots if q.quot_type=='inline')})")
            all_quotations.extend(quots)

        print(f"\n  抽出完了: 計{len(all_quotations)}件")
        save_quotations_tsv(all_quotations, raw_tsv)

    # ─── Step 2: 分類 ─────────────────────────────
    if args.step in ("classify", "all"):
        if args.step == "classify":
            # raw_tsv を読み込んで分類
            all_quotations = _load_quotations_tsv(raw_tsv)
            print(f"  読み込み: {len(all_quotations)}件")

        print(f"\n【Step 2】LLM分類（モデル: {API_MODEL}）")
        all_quotations = classify_quotations(
            all_quotations, checkpoint_path, out_dir
        )

        save_quotations_tsv(all_quotations, classified_tsv)
        save_summary(all_quotations, summary_tsv)

    elif args.step == "extract":
        print("\n  --step extract のみ: 分類はスキップ")
        print(f"  目視確認後に --step classify で分類を実行してください")

    print("\n完了")


def _load_quotations_tsv(path: Path) -> list[Quotation]:
    """TSVから Quotation オブジェクトを復元"""
    quotations = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            q = Quotation(
                quot_id=row["quot_id"],
                pdf_file=row["pdf_file"],
                page_num=int(row["page_num"]),
                quot_type=row["quot_type"],
                text=row["text"],
                word_count=int(row["word_count"]),
                context_before=row["context_before"],
                context_after=row["context_after"],
                ref_hint=row["ref_hint"],
                category=row.get("category", ""),
                raw_response=row.get("raw_response", ""),
            )
            quotations.append(q)
    return quotations


if __name__ == "__main__":
    main()