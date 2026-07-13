"""
extract_body_quotations_v3.py — Stage 7 Phase 1c

v1→v2→v3 変更履歴:
  v1: 座標ベースblock検出 → ページ全体を誤検出
  v2: インデントベースblock検出 → block=0件（CI PDFで機能せず）
      inline最小語数3→8語、OCRノイズ除去
  v3: [修正A] block: フォントサイズ差ベースに戻す
              ページ語数比50%超・200語超は除外
              has_nospace_artifact でさらにノイズ除去
      [修正B] ref_hint: (PL,p.193) 形式パターン追加
              context_after から regex で直接検索
      [修正C] テキスト正規化: 複数スペース・改行を圧縮

使用方法:
  python3 extract_body_quotations_v3.py --step extract --sample 5
  python3 extract_body_quotations_v3.py --step all
"""

import os, re, json, time, argparse, csv
from pathlib import Path
from dataclasses import dataclass, asdict
from collections import Counter
import pdfplumber

# ──────────────────────────────────────────────
# 設定
# ──────────────────────────────────────────────
DEFAULT_PDF_DIR = "/mnt/c/Users/tsuts/Desktop/色々使えるデータ/Critical Inquiry"
DEFAULT_OUT_DIR = "derived/ci_body_quotations"
MIN_WORDS_INLINE   = 8
MIN_WORDS_BLOCK    = 10
MAX_WORDS_BLOCK    = 200    # 200語超はページ全体誤検出とみなす
BLOCK_FONT_RATIO   = 0.92   # 本文フォントの92%以下をブロック引用候補
PAGE_RATIO_LIMIT   = 0.50   # ページ全語数の50%超は除外
API_MODEL  = "claude-haiku-4-5-20251001"
API_SLEEP  = 0.3
BATCH_SIZE = 20

# ──────────────────────────────────────────────
# [修正B] ref_hint パターン（拡張版）
# ──────────────────────────────────────────────
_REF_PATTERNS = [
    # ("PGS," p.170) / ("CC,"p.603) / ("I," pp.5,6)
    re.compile(r'\(["\u201c][A-Z]{1,6}["\u201d,.]?["\u201d]?,?\s*pp?\.\s*\d{1,4}(?:[,\s]\d{1,4})?\)'),
    # (PL,p.193) / (PL, p.193) ← v2で未対応だった形式
    re.compile(r'\([A-Z]{1,6},\s*pp?\.\s*\d{1,4}(?:[,\s]\d{1,4})?\)'),
    # (Author 1977, 23) / (Foucault 1977)
    re.compile(r'\([A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z][a-z]+)?\s*,?\s*\d{4}[^)]{0,30}\)'),
    # (p. 19) / (pp. 19–23)
    re.compile(r'\(pp?\.\s*\d{1,4}(?:[–\-]\d{1,4})?\)'),
]

def extract_ref_hint(text_after: str) -> str:
    """引用直後150文字から参照ヒントを抽出"""
    window = re.sub(r'\s+', ' ', text_after[:200])  # 正規化してから検索
    for pat in _REF_PATTERNS:
        m = pat.search(window)
        if m:
            return m.group(0).strip()
    return ""

# ──────────────────────────────────────────────
# テキスト品質チェック
# ──────────────────────────────────────────────
def normalize_text(text: str) -> str:
    """[修正C] 複数スペース・改行を1スペースに圧縮"""
    return re.sub(r'\s+', ' ', text).strip()

def is_spaced_ocr(text: str) -> bool:
    """"W h a t ' s" のようなOCR展開テキストを検出"""
    tokens = text.split()
    if len(tokens) < 10:
        return False
    return sum(1 for t in tokens if len(t) <= 1) / len(tokens) > 0.5

def has_nospace_artifact(text: str) -> bool:
    """スペースなし長連続文字列（改行跨ぎ）を検出"""
    for token in text.split():
        if len(re.sub(r'[^a-zA-Z]', '', token)) >= 20:
            return True
    return False

def is_valid_quote(text: str) -> bool:
    """引用として適切かの基本チェック"""
    tokens = text.split()
    if not tokens:
        return False
    valid = sum(1 for t in tokens if len(re.sub(r'[^a-zA-Z]', '', t)) >= 2)
    return valid / len(tokens) >= 0.55

# ──────────────────────────────────────────────
# データクラス
# ──────────────────────────────────────────────
@dataclass
class Quotation:
    quot_id: str
    pdf_file: str
    page_num: int
    quot_type: str
    text: str
    word_count: int
    context_before: str
    context_after: str
    ref_hint: str
    category: str = ""
    raw_response: str = ""

# ──────────────────────────────────────────────
# インライン引用パターン（v2と同一）
# ──────────────────────────────────────────────
INLINE_QUOTE_RE = re.compile(
    r'(?<![a-zA-Z])["\u201c]'
    r'([^"\u201c\u201d]{30,600})'
    r'["\u201d]'
)

# ──────────────────────────────────────────────
# Step 1: 抽出
# ──────────────────────────────────────────────
def extract_from_pdf(pdf_path: Path) -> list:
    quotations = []
    pdf_stem = pdf_path.stem

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:

            # ── 本文フォントサイズの推定（PDF全体から） ──
            all_sizes = []
            for pg in pdf.pages:
                ws = pg.extract_words(extra_attrs=["size"])
                all_sizes.extend(w["size"] for w in ws if w.get("size", 0) > 6)
            if not all_sizes:
                return []
            size_ctr = Counter(round(s, 1) for s in all_sizes)
            body_font = size_ctr.most_common(1)[0][0]

            for page_idx, page in enumerate(pdf.pages):
                page_num = page_idx + 1

                # ── テキスト取得（layout=False: スペースなし連結を防ぐ） ──
                page_text = page.extract_text() or ""
                if not page_text.strip():
                    continue

                # 脚注除去
                body_text = _remove_footnotes(page_text)
                page_word_count = len(body_text.split())

                quot_idx = 0

                # ── (1) ブロック引用 [修正A]: フォントサイズ差ベース ──
                words = page.extract_words(
                    extra_attrs=["size", "top"],
                    use_text_flow=True
                )
                block_threshold = body_font * BLOCK_FONT_RATIO

                # 小フォントの単語を連続したブロックにグループ化
                current_block: list[str] = []
                prev_top = None

                def flush_block():
                    nonlocal current_block
                    if not current_block:
                        return
                    raw = " ".join(current_block)
                    text = normalize_text(raw)
                    wc = len(text.split())
                    current_block = []

                    # フィルタ群
                    if is_spaced_ocr(text): return
                    if has_nospace_artifact(text): return
                    if not is_valid_quote(text): return
                    if wc < MIN_WORDS_BLOCK: return
                    if wc > MAX_WORDS_BLOCK: return
                    if page_word_count and wc / page_word_count > PAGE_RATIO_LIMIT: return

                    # 前後文脈: page_text 内で検索
                    anchor = text[:35]
                    pos = page_text.find(anchor)
                    if pos < 0:
                        # anchor が改行跨ぎで見つからない場合、最初の5語で再検索
                        short_anchor = ' '.join(text.split()[:5])
                        pos = page_text.find(short_anchor)
                    ctx_b = normalize_text(page_text[max(0,pos-200):pos]) if pos>=0 else ""
                    ctx_a = normalize_text(page_text[pos+len(anchor):pos+len(anchor)+200]) if pos>=0 else ""
                    ref = extract_ref_hint(ctx_a)

                    quotations.append(Quotation(
                        quot_id=f"{pdf_stem}_p{page_num}_b{quot_idx}",
                        pdf_file=pdf_path.name, page_num=page_num,
                        quot_type="block", text=text, word_count=wc,
                        context_before=ctx_b[-200:], context_after=ctx_a[:200],
                        ref_hint=ref,
                    ))
                    # quot_idx は外側でインクリメント（nonlocal不要にするためリスト使用）
                    quotations[-1].quot_id = f"{pdf_stem}_p{page_num}_b{len([q for q in quotations if q.quot_type=='block' and q.page_num==page_num])-1}"

                for w in words:
                    size = w.get("size", body_font)
                    top  = w.get("top", 0)

                    if size < block_threshold:
                        # 行が変わって大きく離れていたら一度フラッシュ
                        if prev_top is not None and abs(top - prev_top) > 15:
                            flush_block()
                        current_block.append(w["text"])
                        prev_top = top
                    else:
                        flush_block()
                        prev_top = None

                flush_block()

                # ── (2) インライン引用 ──
                # layout=False のテキストを使う（スペース連結ノイズを避ける）
                inline_text = body_text

                for m in INLINE_QUOTE_RE.finditer(inline_text):
                    raw_q = m.group(1)
                    text  = normalize_text(raw_q)  # [修正C]
                    wc    = len(text.split())

                    if is_spaced_ocr(text): continue
                    if has_nospace_artifact(text): continue
                    if not is_valid_quote(text): continue
                    if wc < MIN_WORDS_INLINE: continue

                    start = m.start()
                    end   = m.end()
                    ctx_b = normalize_text(inline_text[max(0,start-200):start])
                    ctx_a = normalize_text(inline_text[end:end+200])
                    ref   = extract_ref_hint(ctx_a)

                    quot_idx += 1
                    quotations.append(Quotation(
                        quot_id=f"{pdf_stem}_p{page_num}_i{quot_idx}",
                        pdf_file=pdf_path.name, page_num=page_num,
                        quot_type="inline", text=text, word_count=wc,
                        context_before=ctx_b[-200:], context_after=ctx_a[:200],
                        ref_hint=ref,
                    ))

    except Exception as e:
        print(f"  WARNING: {pdf_path.name}: {e}")
        import traceback; traceback.print_exc()

    return quotations


def _remove_footnotes(page_text: str) -> str:
    """脚注除去（保守的版）"""
    lines = page_text.split('\n')
    body, fn_markers = [], 0
    for line in lines:
        s = line.strip()
        if re.match(r'^\d{1,2}[\.\s]', s) and len(s) < 200:
            fn_markers += 1
            if fn_markers >= 2:
                break
        else:
            fn_markers = 0
        body.append(line)
    return '\n'.join(body)


# ──────────────────────────────────────────────
# 分類・出力（v2と同一）
# ──────────────────────────────────────────────
SCHEMA = """あなたは文学研究の引用分類の専門家です。引用テキストと文脈を読んで分類してください。
A 批評家・理論家・学者の言葉（学術書・論文・批評エッセイ）
B 作家・芸術家の言葉（書簡・日記・エッセイ・序文、作品テキスト外）
C 文学・芸術作品テキストそのもの（小説・詩・戯曲の本文）
D その他一次資料（哲学・政治・法律・歴史テキスト等）
X 判定不能
回答はA/B/C/D/Xの1文字のみ。"""

TSV_FIELDS = ["quot_id","pdf_file","page_num","quot_type","word_count",
              "ref_hint","category","text","context_before","context_after","raw_response"]

def classify_quotations(quotations, checkpoint_path, out_dir):
    import anthropic
    client = anthropic.Anthropic()
    done = {}
    if checkpoint_path.exists():
        with open(checkpoint_path) as f:
            for line in f:
                r = json.loads(line); done[r["quot_id"]] = r["category"]
        print(f"  checkpoint: {len(done)}件")
    for q in quotations:
        if q.quot_id in done: q.category = done[q.quot_id]
    todo = [q for q in quotations if not q.category]
    print(f"  分類対象: {len(todo)}件")
    cf = open(checkpoint_path, "a")
    for i, q in enumerate(todo):
        ref = f"（参照: {q.ref_hint}）" if q.ref_hint else ""
        prompt = f"【引用{ref} {q.quot_type}・{q.word_count}語】\n{q.text}\n\n【直前】{q.context_before[-200:]}\n【直後】{q.context_after[:200]}"
        try:
            resp = client.messages.create(model=API_MODEL, max_tokens=10,
                system=SCHEMA, messages=[{"role":"user","content":prompt}])
            raw = resp.content[0].text.strip().upper()
            cat = raw[0] if raw and raw[0] in "ABCDX" else "X"
        except Exception as e:
            cat, raw = "X", f"ERROR:{e}"
        q.category, q.raw_response = cat, raw
        cf.write(json.dumps({"quot_id":q.quot_id,"category":cat,"raw":raw},ensure_ascii=False)+"\n")
        if (i+1) % BATCH_SIZE == 0:
            cf.flush(); print(f"    {i+1}/{len(todo)}")
        time.sleep(API_SLEEP)
    cf.close()
    return quotations

def save_tsv(quotations, path):
    with open(path,"w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f,fieldnames=TSV_FIELDS,delimiter="\t",extrasaction="ignore")
        w.writeheader()
        for q in quotations:
            row = asdict(q)
            for k in ("text","context_before","context_after"):
                row[k] = row[k].replace("\n"," ").replace("\t"," ")
            w.writerow(row)
    print(f"  保存: {path} ({len(quotations)}件)")

def save_summary(quotations, path):
    from collections import defaultdict
    cc, wc, ct = defaultdict(int), defaultdict(int), defaultdict(lambda: defaultdict(int))
    for q in quotations:
        cat = q.category or "?"
        cc[cat] += 1; wc[cat] += q.word_count; ct[q.quot_type][cat] += 1
    total = len(quotations)
    total_w = sum(q.word_count for q in quotations)
    cls = [q for q in quotations if q.category in "ABCD"]
    tc = len(cls); tw = sum(q.word_count for q in cls)
    labels = {"A":"批評家・理論家","B":"作家語(作品外)","C":"文学作品テキスト",
              "D":"その他一次資料","X":"判定不能","?":"未分類"}
    rows = [{"category":c,"label":labels[c],"count":cc[c],
             "pct_count":f"{cc[c]/tc*100:.1f}" if tc and c in "ABCD" else "",
             "total_words":wc[c],
             "pct_words":f"{wc[c]/tw*100:.1f}" if tw and c in "ABCD" else "",
             "block_count":ct["block"][c],"inline_count":ct["inline"][c]}
            for c in ["A","B","C","D","X","?"]]
    with open(path,"w",newline="",encoding="utf-8") as f:
        dw = csv.DictWriter(f,fieldnames=list(rows[0].keys()),delimiter="\t")
        dw.writeheader(); dw.writerows(rows)
        f.write(f"\n# 総件数:{total} 総語数:{total_w} A-D分類済:{tc}\n")
    print(f"  集計: {path}")
    print(f"\n{'='*55}")
    print(f"  【本文引用 v3】 {total}件 / {total_w}語")
    print(f"  {'カテゴリ':<22}{'件数':>5}{'%':>6}{'語数':>8}{'%':>6}")
    print(f"  {'-'*47}")
    for r in rows:
        if r["count"]:
            print(f"  {r['category']} {labels[r['category']]:<20}{r['count']:>5}"
                  f"{r['pct_count'] or '—':>5}%{r['total_words']:>8}"
                  f"{r['pct_words'] or '—':>5}%")
    print(f"{'='*55}")

def _load_tsv(path):
    rows = []
    with open(path,newline="",encoding="utf-8") as f:
        for row in csv.DictReader(f,delimiter="\t"):
            rows.append(Quotation(
                quot_id=row["quot_id"],pdf_file=row["pdf_file"],
                page_num=int(row["page_num"]),quot_type=row["quot_type"],
                text=row["text"],word_count=int(row["word_count"]),
                context_before=row["context_before"],context_after=row["context_after"],
                ref_hint=row["ref_hint"],category=row.get("category",""),
                raw_response=row.get("raw_response","")))
    return rows

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--pdf-dir",default=DEFAULT_PDF_DIR)
    p.add_argument("--out-dir",default=DEFAULT_OUT_DIR)
    p.add_argument("--step",choices=["extract","classify","all"],default="all")
    p.add_argument("--sample",type=int,default=0)
    return p.parse_args()

def main():
    args = parse_args()
    out = Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    raw_tsv  = out/"quotations_raw_v3.tsv"
    cls_tsv  = out/"classifications_v3.tsv"
    ckpt     = out/"checkpoint_v3.jsonl"
    sum_tsv  = out/"summary_stats_v3.tsv"

    pdf_dir = Path(args.pdf_dir)
    if not pdf_dir.exists():
        print(f"WARNING: PDFディレクトリが見つかりません: {pdf_dir}"); return

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if args.sample: pdfs = pdfs[:args.sample]
    print(f"対象: {len(pdfs)}件  inline≥{MIN_WORDS_INLINE}語 / block {MIN_WORDS_BLOCK}–{MAX_WORDS_BLOCK}語 / font_ratio<{BLOCK_FONT_RATIO}")

    all_q = []
    if args.step in ("extract","all"):
        print("\n【Step 1】抽出（v3）")
        for i, p in enumerate(pdfs):
            print(f"  [{i+1}/{len(pdfs)}] {p.name}")
            qs = extract_from_pdf(p)
            nb = sum(1 for q in qs if q.quot_type=="block")
            ni = sum(1 for q in qs if q.quot_type=="inline")
            nr = sum(1 for q in qs if q.ref_hint)
            print(f"    -> {len(qs)}件 (block:{nb} inline:{ni}) ref_hint:{nr}件")
            all_q.extend(qs)
        print(f"\n  合計: {len(all_q)}件")
        save_tsv(all_q, raw_tsv)

    if args.step in ("classify","all"):
        if args.step == "classify": all_q = _load_tsv(raw_tsv)
        print(f"\n【Step 2】LLM分類")
        all_q = classify_quotations(all_q, ckpt, out)
        save_tsv(all_q, cls_tsv)
        save_summary(all_q, sum_tsv)
    elif args.step == "extract":
        print("\n  抽出完了。目視確認後に --step classify を実行")
    print("\n完了")

if __name__ == "__main__":
    main()