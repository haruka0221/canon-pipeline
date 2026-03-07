#!/usr/bin/env python3
"""
Audit identifier coverage in editions JSONs.

For each work in the 100-sample audit set:
  - Reads raw/editions_year_audit/{work_id}.json          (offset0)
  - Optionally reads {work_id}_offset50.json / _offset100.json

Outputs:
  derived/identifier_audit_offset0.tsv       -- per-work, offset0 only
  derived/identifier_audit_comparison.tsv    -- per-work, offset0 vs offset50 (size_top>50 subset)
"""
from __future__ import annotations
import csv, json
from pathlib import Path

RAW_DIR   = Path("raw/editions_year_audit")
WORK_LIST = Path("tmp/work_keys_year_audit.txt")
OUT_OFFSET0    = Path("derived/identifier_audit_offset0.tsv")
OUT_COMPARISON = Path("derived/identifier_audit_comparison.tsv")

# ---- 確認済みフィールド名 ----
# oclc_number（単数）と oclc_numbers（複数）の両方が存在するため両方チェック
# ocaid（Internet Archive ID）も追加
IDENTIFIER_FIELDS = [
    "isbn_10",
    "isbn_13",
    "oclc_numbers",   # リスト形式
    "oclc_number",    # 単数形（別フィールドとして存在する場合あり）
    "lccn",
    "ocaid",          # Internet Archive ID（文字列）
]


def load_json(p: Path):
    if not p.exists():
        return None
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def entry_has(entry: dict, field: str) -> bool:
    """フィールドが存在し、空でないリストまたは空でない文字列か判定"""
    v = entry.get(field)
    if v is None:
        return False
    if isinstance(v, list):
        return len(v) > 0
    if isinstance(v, str):
        return v.strip() != ""
    return False


def entry_has_languages(entry: dict) -> bool:
    # languages は [{"key": "/languages/eng"}] 形式
    v = entry.get("languages")
    if isinstance(v, list):
        return len(v) > 0
    return False


def entry_has_oclc(entry: dict) -> bool:
    # oclc_numbers（リスト）または oclc_number（文字列）のどちらかがあればTrue
    return entry_has(entry, "oclc_numbers") or entry_has(entry, "oclc_number")


def count_entries(entries: list[dict]) -> dict:
    """エントリリストから識別子付与カウントを集計"""
    n = len(entries)
    counts = {"n_entries": n}

    for field in IDENTIFIER_FIELDS:
        counts[f"n_{field}"] = sum(1 for e in entries if entry_has(e, field))

    # 集約カウント
    counts["n_isbn_any"] = sum(
        1 for e in entries
        if entry_has(e, "isbn_10") or entry_has(e, "isbn_13")
    )
    counts["n_oclc_any"] = sum(1 for e in entries if entry_has_oclc(e))
    counts["n_languages"] = sum(1 for e in entries if entry_has_languages(e))
    return counts


def rates(counts: dict) -> dict:
    """件数を割合（rate）に変換して返す"""
    n = counts["n_entries"]
    r = {}
    for k, v in counts.items():
        if k == "n_entries":
            continue
        label = k.replace("n_", "rate_", 1)
        r[label] = round(v / n, 4) if n > 0 else None
    return r


def load_work_ids() -> list[str]:
    """/works/OLxxxxxW 形式も OLxxxxxW 形式も両方対応"""
    ids = []
    with WORK_LIST.open(encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith("/works/"):
                s = s.split("/works/")[-1]
            ids.append(s)
    return ids


def audit_one(work_id: str, offset: int = 0) -> dict | None:
    if offset == 0:
        p = RAW_DIR / f"{work_id}.json"
    else:
        p = RAW_DIR / f"{work_id}_offset{offset}.json"

    data = load_json(p)
    if data is None:
        return None

    entries = data.get("entries", [])
    size_top = data.get("size")

    counts = count_entries(entries)
    r = rates(counts)

    return {
        "work_id": work_id,
        "offset": offset,
        "size_top": "" if size_top is None else str(size_top),
        **{k: str(v) for k, v in counts.items()},
        **{k: ("" if v is None else str(v)) for k, v in r.items()},
    }


def print_summary(label: str, rows: list[dict]):
    total = len(rows)
    total_entries = sum(int(r["n_entries"]) for r in rows)
    print(f"\n=== {label} (n={total}, total_entries={total_entries}) ===")

    print("  [work単位: >=1件でも識別子あり の work 数]")
    for field in ["isbn_any", "isbn_13", "isbn_10", "oclc_any", "oclc_numbers",
                  "oclc_number", "lccn", "ocaid", "languages"]:
        col = f"n_{field}"
        has = sum(1 for r in rows if int(r.get(col, 0) or 0) > 0)
        print(f"    {field:<18}: {has:>3}/{total}  ({100*has/total:.1f}%)")

    print("  [エントリ単位: 識別子あり の edition 数]")
    for field in ["isbn_any", "isbn_13", "isbn_10", "oclc_any", "oclc_numbers",
                  "oclc_number", "lccn", "ocaid", "languages"]:
        ncol = f"n_{field}"
        n_with = sum(int(r.get(ncol, 0) or 0) for r in rows)
        print(f"    {field:<18}: {n_with:>4}/{total_entries}  ({100*n_with/total_entries:.1f}%)")


def main():
    work_ids = load_work_ids()
    print(f"work count: {len(work_ids)}")

    # --- offset0: 全100件 ---
    rows_offset0 = []
    large_works = []  # size_top > 50

    for wid in work_ids:
        row = audit_one(wid, offset=0)
        if row is None:
            print(f"  WARN: no file for {wid} offset0")
            continue
        rows_offset0.append(row)
        try:
            if int(row["size_top"]) > 50:
                large_works.append(wid)
        except (ValueError, KeyError):
            pass

    print(f"offset0 rows: {len(rows_offset0)}")
    print(f"size_top>50 works: {len(large_works)}")

    # 書き出し
    OUT_OFFSET0.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows_offset0[0].keys()) if rows_offset0 else []
    with OUT_OFFSET0.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        w.writeheader()
        w.writerows(rows_offset0)
    print(f"wrote: {OUT_OFFSET0}")

    print_summary("offset0 summary (all works)", rows_offset0)

    # --- offset50 比較: size_top>50 subset ---
    comparison_rows = []
    missing_offset50 = []

    for wid in large_works:
        r50 = audit_one(wid, offset=50)
        if r50 is None:
            missing_offset50.append(wid)
        else:
            comparison_rows.append(r50)

    # offset0 の large_works 分と offset50 を合わせて比較TSVに書く
    offset0_large = [r for r in rows_offset0 if r["work_id"] in large_works]
    all_comparison = sorted(
        offset0_large + comparison_rows,
        key=lambda x: (x["work_id"], int(x["offset"]))
    )

    if all_comparison:
        fieldnames2 = list(all_comparison[0].keys())
        with OUT_COMPARISON.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames2, delimiter="\t")
            w.writeheader()
            w.writerows(all_comparison)
        print(f"\nwrote: {OUT_COMPARISON}  (rows: {len(all_comparison)})")

    if missing_offset50:
        print(f"\noffset50 missing ({len(missing_offset50)} works) → Step3 で取得が必要:")
        missing_path = Path("tmp/missing_offset50.txt")
        with missing_path.open("w", encoding="utf-8") as f:
            for wid in missing_offset50:
                f.write(wid + "\n")
                print(f"  {wid}")
        print(f"wrote: {missing_path}")
    else:
        print("\noffset50: 全 size_top>50 works のファイルが揃っています ✓")

    if comparison_rows:
        print_summary("offset50 summary (size_top>50 subset)", comparison_rows)


if __name__ == "__main__":
    main()
