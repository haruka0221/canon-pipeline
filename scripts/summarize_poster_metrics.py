#!/usr/bin/env python3

import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTEGRATED = ROOT / "derived" / "canon_integrated.tsv"
BENCHMARK = ROOT / "derived" / "benchmark" / "full_eval_130items.tsv"
OUTPUT = ROOT / "results_for_poster.md"

POPULATION_N = 34789
CANONICAL_TARGETS = [
    ("Heart of Darkness", "Conrad"),
    ("White Fang", "London"),
    ("Ulysses", "Joyce"),
]


def load_tsv(path):
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def to_int(value):
    if value is None:
        return 0
    text = str(value).strip()
    if not text:
        return 0
    return int(float(text))


def pct(n, total=POPULATION_N):
    return f"n={n:,}件, {n / total * 100:.1f}%"


def pct_pp(sub_n, sub_total, base_n, base_total):
    sub_rate = sub_n / sub_total * 100 if sub_total else 0.0
    base_rate = base_n / base_total * 100 if base_total else 0.0
    diff = sub_rate - base_rate
    return f"{diff:+.1f} pt"


def is_positive_numeric(row, column):
    return to_int(row[column]) > 0


def has_wikidata(row):
    return bool(row["wikidata_qid"].strip())


def gr_status_bucket(row):
    status = row["gr_match"].strip()
    ratings = to_int(row["gr_ratings"])
    success = {"UNIQUE", "YEAR_AUTH", "RATINGS_MAX", "LLM", "MANUAL_FIX"}
    if ratings > 0:
        return "positive"
    if status in success:
        return "matched_zero"
    return "unmatched"


def db_match_flags(row):
    return {
        "Open Library": is_positive_numeric(row, "edition_count"),
        "JSTOR": is_positive_numeric(row, "jstor_count"),
        "OpenAlex": is_positive_numeric(row, "oa_count"),
        "HathiTrust": is_positive_numeric(row, "htid_count"),
        "Goodreads": gr_status_bucket(row) != "unmatched",
        "Wikidata": has_wikidata(row),
    }


def find_representative(rows, title_sub, author_sub):
    hits = [
        row for row in rows
        if title_sub.lower() in row["title"].lower()
        and author_sub.lower() in row["author_name"].lower()
    ]
    if not hits:
        return None, []
    canonical_hits = [row for row in hits if row["canonical"] == "1"]
    if canonical_hits:
        return canonical_hits[0], hits
    return sorted(
        hits,
        key=lambda r: (
            -(to_int(r["jstor_count"]) + to_int(r["oa_count"]) + to_int(r["edition_count"])
              + to_int(r["htid_count"]) + to_int(r["gr_ratings"]) + to_int(r["sitelink_count"])),
            r["work_key"],
        ),
    )[0], hits


def main():
    rows = load_tsv(INTEGRATED)
    if len(rows) != POPULATION_N:
        raise SystemExit(f"Unexpected row count: {len(rows)} != {POPULATION_N}")

    canonical_rows = [row for row in rows if row["canonical"] == "1"]
    benchmark_rows = load_tsv(BENCHMARK)

    sections = []
    sections.append("# DH2026 Poster Evaluation Numbers\n")
    sections.append(
        f"- Source: `derived/canon_integrated.tsv`\n"
        f"- Population: n={POPULATION_N:,}件\n"
        f"- Canonical subset: n={len(canonical_rows):,}件\n"
    )
    sections.append(
        "- Match definition: numeric DBs are treated as linked when the value is `>0`; "
        "Wikidata is linked when `wikidata_qid` is present; Goodreads uses `gr_match` to "
        "separate `value>0`, `matched but 0`, and `unmatched`.\n"
        "- For JSTOR/OpenAlex/HathiTrust/Open Library, this file does not expose an explicit "
        "processing-status column, so `0` cannot be split further into `searched but zero` vs. `unprocessed`.\n"
    )

    db_specs = [
        ("Open Library", lambda r: is_positive_numeric(r, "edition_count"), None),
        ("JSTOR", lambda r: is_positive_numeric(r, "jstor_count"), None),
        ("OpenAlex", lambda r: is_positive_numeric(r, "oa_count"), None),
        ("HathiTrust", lambda r: is_positive_numeric(r, "htid_count"), None),
        ("Goodreads", lambda r: gr_status_bucket(r) == "positive", lambda r: gr_status_bucket(r) == "matched_zero"),
        ("Wikidata", lambda r: has_wikidata(r), lambda r: has_wikidata(r) and to_int(r["sitelink_count"]) == 0),
    ]

    lines = ["## 1. 全体カバレッジ\n", "| DB | マッチあり | マッチ成功・値0 | 未マッチ |", "|---|---:|---:|---:|"]
    for label, hit_fn, zero_fn in db_specs:
        hit_n = sum(1 for row in rows if hit_fn(row))
        zero_n = sum(1 for row in rows if zero_fn and zero_fn(row) and not hit_fn(row))
        unmatched_n = POPULATION_N - hit_n - zero_n
        zero_text = pct(zero_n) if zero_fn else "判別不可"
        lines.append(f"| {label} | {pct(hit_n)} | {zero_text} | {pct(unmatched_n)} |")
    sections.append("\n".join(lines) + "\n")

    dist_counter = Counter(sum(db_match_flags(row).values()) for row in rows)
    lines = ["## 2. 複数DBに繋がった作品の分布\n", "| 接続DB数（6DB） | 件数 |", "|---|---:|"]
    for k in range(6, -1, -1):
        lines.append(f"| {k}DB | {pct(dist_counter.get(k, 0))} |")
    lines.append("")
    lines.append("注: Open Library は母集団そのものなので `0DB` は構造上 0件、`1DB` は実質的に「Open Library のみ」です。")
    sections.append("\n".join(lines) + "\n")

    jstor_pos = sum(1 for row in rows if to_int(row["jstor_count"]) > 0)
    oa_pos = sum(1 for row in rows if to_int(row["oa_count"]) > 0)
    either_pos = sum(1 for row in rows if to_int(row["jstor_count"]) > 0 or to_int(row["oa_count"]) > 0)
    zero_pos = POPULATION_N - either_pos
    lines = ["## 3. 学術文献のリンク状況\n", "| 指標 | 値 |", "|---|---:|"]
    lines.append(f"| JSTORで引用1件以上 | {pct(jstor_pos)} |")
    lines.append(f"| OpenAlexで引用1件以上 | {pct(oa_pos)} |")
    lines.append(f"| JSTORまたはOpenAlexで引用1件以上 | {pct(either_pos)} |")
    lines.append(f"| 引用ゼロ（JSTOR=0かつOpenAlex=0） | {pct(zero_pos)} |")
    sections.append("\n".join(lines) + "\n")

    lines = ["## 4. Canonical作品での精度\n", "| DB | canonical (n=98) | 全体 (n=34,789) | 差分 |", "|---|---:|---:|---:|"]
    for label, hit_fn, zero_fn in db_specs:
        can_hit_n = sum(1 for row in canonical_rows if hit_fn(row))
        all_hit_n = sum(1 for row in rows if hit_fn(row))
        lines.append(
            f"| {label} | {pct(can_hit_n, len(canonical_rows))} | {pct(all_hit_n, POPULATION_N)} | "
            f"{pct_pp(can_hit_n, len(canonical_rows), all_hit_n, POPULATION_N)} |"
        )
    sections.append("\n".join(lines) + "\n")

    lines = ["## 5. 代表作品プロファイル\n", "| 作品 | 採用work_key | canonical | jstor_count | oa_count | edition_count | htid_count | gr_ratings | wikidata_qid | sitelink_count | 備考 |", "|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|"]
    for title_sub, author_sub in CANONICAL_TARGETS:
        rep, hits = find_representative(rows, title_sub, author_sub)
        if rep is None:
            lines.append(f"| {title_sub} ({author_sub}) | - | - | - | - | - | - | - | - | - | not found |")
            continue
        note = f"候補{len(hits)}件; canonical=1を採用" if rep["canonical"] == "1" else f"候補{len(hits)}件; 最大シグナル行を採用"
        lines.append(
            f"| {title_sub} ({author_sub}) | {rep['work_key']} | {rep['canonical']} | "
            f"{to_int(rep['jstor_count'])} | {to_int(rep['oa_count'])} | {to_int(rep['edition_count'])} | "
            f"{to_int(rep['htid_count'])} | {to_int(rep['gr_ratings'])} | "
            f"{rep['wikidata_qid'] or 'なし'} | {to_int(rep['sitelink_count'])} | {note} |"
        )
    sections.append("\n".join(lines) + "\n")

    gr_counts = Counter(row["gr_match"] for row in rows)
    auto_high = gr_counts["UNIQUE"] + gr_counts["YEAR_AUTH"] + gr_counts["RATINGS_MAX"]
    low_conf_review = gr_counts["LLM"] + gr_counts["MANUAL_FIX"]
    no_match = gr_counts["NO_MATCH"] + gr_counts["NO_MATCH_AUTH"]
    lines = ["## 6. LLM判定の信頼度分布（Goodreads照合ログ由来）\n", "| 指標 | 値 |", "|---|---:|"]
    lines.append(f"| 高信頼度で自動確定（UNIQUE/YEAR_AUTH/RATINGS_MAX） | {pct(auto_high)} |")
    lines.append(f"| 低信頼度で追加判定・人手補正（LLM/MANUAL_FIX） | {pct(low_conf_review)} |")
    lines.append(f"| 一致なし判定（NO_MATCH/NO_MATCH_AUTH） | {pct(no_match)} |")
    lines.append(f"| 補足: LLM最終決定のみ | {pct(gr_counts['LLM'])} |")
    lines.append(f"| 補足: 人手補正のみ | {pct(gr_counts['MANUAL_FIX'])} |")
    sections.append("\n".join(lines) + "\n")

    positive_total = sum(1 for row in benchmark_rows if row["type"] == "positive")
    negative_total = sum(1 for row in benchmark_rows if row["type"] == "negative")
    false_negative_rows = [row for row in benchmark_rows if row["type"] == "positive" and row["correct"] != "True"]
    false_positive_rows = [row for row in benchmark_rows if row["type"] == "negative" and row["correct"] != "True"]

    fn_examples = [
        "Kim: 近接する別QIDへの取り違え。`OL19908W` 側に `Q589868` が付いており、同一題名の重複登録/IDずれが示唆される。",
        "At Fault: gold QIDはあるが `pred_qid=NO_MATCH`。sitelink 0 の疎な項目で、収録制限または探索漏れの可能性が高い。",
        "The octopus, a story of California: gold QIDはあるが `pred_qid=NO_MATCH`。著者作品一覧が 0件取得になっており、収録制限/取得失敗型。",
        "Peter Pan: `Q3435337` ではなく `Q19032697` を返しており、近接する別作品への重複登録・IDずれ型。",
    ]
    fp_examples = [
        "The Capsina: An Historical Novel: gold は `NO_MATCH` だが `Q124087127` を返した。負例への過剰一致で、同名異著者または近接候補の誤採択とみられる。"
    ]
    type_lines = [
        "| 類型 | 件数 | 代表ケース |",
        "|---|---:|---|",
        "| ① ID世代ずれ | 1件 | `Kim` |",
        "| ② 同名異著者 | 1件 | `The Capsina: An Historical Novel` |",
        "| ③ 収録制限 | 2件 | `At Fault`, `The octopus, a story of California` |",
        "| ④ 重複登録 | 1件 | `Peter Pan` |",
    ]
    lines = ["## 7. Wikidataベンチマーク（n=130）の誤り分析\n", "| 指標 | 値 |", "|---|---:|"]
    lines.append(f"| False Positive（negative=48件中の誤一致） | {pct(len(false_positive_rows), negative_total)} |")
    lines.append(f"| False Negative（positive=82件中の見逃し/誤同定） | {pct(len(false_negative_rows), positive_total)} |")
    sections.append("\n".join(lines) + "\n")
    sections.append(
        "### 誤りケースの要約\n- "
        + "\n- ".join([row["title"] for row in false_negative_rows] + [row["title"] for row in false_positive_rows])
        + "\n"
    )
    sections.append("### 類型化（暫定）\n" + "\n".join(type_lines) + "\n")
    sections.append("### 誤り内容メモ\n- " + "\n- ".join(fn_examples + fp_examples) + "\n")

    text = "\n".join(sections).strip() + "\n"
    OUTPUT.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
