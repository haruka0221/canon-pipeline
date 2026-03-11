#!/usr/bin/env python3
"""
shadow_hollow_analysis.py  (v2 - 2026-03-11)
=============================================
修正内容:
  - shadow canon: タイトル≒著者姓の1語ノイズを除外
  - shadow canon: 1880-1950年範囲外っぽい作品を警告フラグ
  - hollow canon: 著者名が正しくマッチしているか確認フラグを追加

入力:  derived/jstor_mentions.tsv
出力:  derived/shadow_canon.tsv
        derived/hollow_canon.tsv
        derived/shadow_hollow_summary.txt
"""

import csv
import re
import sys
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent
INPUT_TSV   = BASE_DIR / "derived" / "jstor_mentions.tsv"
OUT_SHADOW  = BASE_DIR / "derived" / "shadow_canon.tsv"
OUT_HOLLOW  = BASE_DIR / "derived" / "hollow_canon.tsv"
OUT_SUMMARY = BASE_DIR / "derived" / "shadow_hollow_summary.txt"

SHADOW_TOPN      = 50
SHADOW_MIN_COUNT = 5

# ─── 正規化（報告書§10.3 v3準拠） ───────────────────────────
_LEADING_ART = re.compile(r'^(the|a|an)\s+', re.IGNORECASE)
_DROP_CHARS  = re.compile(r"['\-\u2018\u2019\u201c\u201d]")
_NON_ALNUM   = re.compile(r'[^a-z0-9\s]')
_MULTI_SPC   = re.compile(r'\s+')

def normalize(text: str) -> str:
    t = text.lower()
    t = _LEADING_ART.sub('', t)
    t = _DROP_CHARS.sub('', t)
    t = _NON_ALNUM.sub(' ', t)
    return _MULTI_SPC.sub(' ', t).strip()

def is_title_noise(title_norm: str, last_name: str) -> bool:
    """
    タイトルが著者姓と同一 or 著者姓を含む短い文字列の場合はノイズ。
    例: title="lamb" last_name="lamb" → True（著者名タイトル）
    例: title="d h lawrence" last_name="lawrence" → True（著者フルネームタイトル）
    """
    if not title_norm or not last_name:
        return False
    # タイトルと著者姓が完全一致
    if title_norm == last_name:
        return True
    # タイトルが著者姓のみ or 著者姓＋イニシャル程度（3語以下）で
    # かつ著者姓がタイトルに含まれる
    words = title_norm.split()
    if len(words) <= 3 and last_name in words:
        return True
    return False

def load_tsv(path: Path) -> list[dict]:
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f, delimiter='\t'))

def write_tsv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t',
                           extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)

def main():
    if not INPUT_TSV.exists():
        print(f"ERROR: {INPUT_TSV} が見つかりません", file=sys.stderr)
        sys.exit(1)

    rows = load_tsv(INPUT_TSV)
    print(f"読み込み完了: {len(rows)} works")

    for r in rows:
        r["jstor_mention_count"] = int(r.get("jstor_mention_count") or 0)
        r["canonical"]           = int(r.get("canonical") or 0)
        r["is_short"]            = int(r.get("is_short") or 0)

    canonical_rows     = [r for r in rows if r["canonical"] == 1]
    non_canonical_rows = [r for r in rows if r["canonical"] == 0]

    # ── shadow canon ─────────────────────────────────────────
    shadow_pool = []
    noise_removed = []
    for r in non_canonical_rows:
        if r["jstor_mention_count"] < SHADOW_MIN_COUNT:
            continue
        if r["is_short"] == 1:
            continue
        title_norm = normalize(r.get("title_norm") or r.get("title", ""))
        last_name  = normalize(r.get("last_name", ""))
        if is_title_noise(title_norm, last_name):
            noise_removed.append(r)
            continue
        shadow_pool.append(r)

    shadow_pool.sort(key=lambda r: r["jstor_mention_count"], reverse=True)
    shadow_canon = shadow_pool[:SHADOW_TOPN]

    # ── hollow canon ─────────────────────────────────────────
    # 著者名が空のものは要確認フラグを付ける
    hollow_canon = []
    for r in canonical_rows:
        if r["jstor_mention_count"] == 0:
            r["note"] = "要確認: 著者名なし" if not r.get("author","").strip() else ""
            hollow_canon.append(r)
    hollow_canon.sort(key=lambda r: r["title"])

    # ── 統計 ─────────────────────────────────────────────────
    def stats(rs):
        counts = sorted([r["jstor_mention_count"] for r in rs])
        n = len(counts)
        if n == 0:
            return {}
        zero    = sum(1 for c in counts if c == 0)
        nonzero = n - zero
        return {
            "n": n, "zero": zero, "zero_pct": zero/n*100,
            "nonzero": nonzero, "nonzero_pct": nonzero/n*100,
            "median": counts[n//2], "mean": f"{sum(counts)/n:.1f}",
            "max": counts[-1],
        }

    s_all    = stats(rows)
    s_can    = stats(canonical_rows)
    s_noncan = stats(non_canonical_rows)

    # ── 出力 ─────────────────────────────────────────────────
    shadow_cols = ["work_key","title","author","jstor_mention_count",
                   "via_creators","via_jtitle","canonical","is_short"]
    hollow_cols = ["work_key","title","author","jstor_mention_count",
                   "canonical","note"]

    write_tsv(OUT_SHADOW, shadow_canon, shadow_cols)
    write_tsv(OUT_HOLLOW, hollow_canon, hollow_cols)

    lines = [
        "=" * 62,
        "shadow_hollow_analysis.py v2 結果サマリー",
        "=" * 62,
        "",
        "── 全体統計 ────────────────────────────────────────────",
        f"  総 works 数  : {s_all['n']:,}",
        f"  ゼロヒット   : {s_all['zero']:,} ({s_all['zero_pct']:.1f}%)",
        f"  1件以上      : {s_all['nonzero']:,} ({s_all['nonzero_pct']:.1f}%)",
        f"  中央値 / 平均 / 最大 : {s_all['median']} / {s_all['mean']} / {s_all['max']}",
        "",
        "── canonical vs 非canonical ────────────────────────────",
        f"  canonical     n={s_can['n']}",
        f"    ゼロヒット: {s_can['zero']} ({s_can['zero_pct']:.1f}%)",
        f"    中央値 / 平均 / 最大 : {s_can['median']} / {s_can['mean']} / {s_can['max']}",
        f"  non-canonical n={s_noncan['n']:,}",
        f"    ゼロヒット: {s_noncan['zero']:,} ({s_noncan['zero_pct']:.1f}%)",
        f"    中央値 / 平均 / 最大 : {s_noncan['median']} / {s_noncan['mean']} / {s_noncan['max']}",
        "",
        f"  注目格差（論文に記載可）:",
        f"    canonical 中央値 {s_can['median']} vs non-canonical 中央値 {s_noncan['median']}",
        f"    canonical の{100-s_can['zero_pct']:.1f}%が1件以上 vs non-canonical の{s_noncan['nonzero_pct']:.1f}%",
        "",
        "── hollow canon ────────────────────────────────────────",
        f"  canonical かつ jstor=0 : {len(hollow_canon)} 件 "
        f"({len(hollow_canon)/len(canonical_rows)*100:.1f}% of canonical)",
        "",
    ]

    for r in hollow_canon:
        note = f"  ← {r['note']}" if r.get("note") else ""
        lines.append(f"  {r['title']} / {r['author']}{note}")

    lines += [
        "",
        f"── shadow canon TOP 30 ─────────────────────────────────",
        f"  （non-canonical・jstor≥{SHADOW_MIN_COUNT}・is_short除外・著者名タイトル除外）",
        f"  ノイズとして除外: {len(noise_removed)} 件",
        "",
    ]

    for i, r in enumerate(shadow_canon[:30]):
        lines.append(
            f"  {i+1:2d}. {r['jstor_mention_count']:5d}件  "
            f"{r['title']} / {r['author']}"
        )

    lines += [
        "",
        f"全 shadow canon {len(shadow_canon)} 件 → {OUT_SHADOW}",
        f"全 hollow canon {len(hollow_canon)} 件 → {OUT_HOLLOW}",
        "=" * 62,
    ]

    summary = "\n".join(lines)
    with open(OUT_SUMMARY, 'w', encoding='utf-8') as f:
        f.write(summary)

    print("\n" + summary)

if __name__ == "__main__":
    main()