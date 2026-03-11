#!/usr/bin/env python3
"""
openalex_mentions_all.py  (v5 - 2026-03-11)
============================================
修正内容:
  - oa_count_title（参考値）を廃止 → 1作品1リクエストに削減
  - INTERVAL を 1.0秒 に変更（429対策）
  - Max retries exceeded 後に 600秒スリープ → 429連鎖を防止
  - リトライ sleep を固定値に変更（60s → 120s → 180s ...ではなく全て120s）

入力:  derived/ol_dump_population_with_author.tsv
出力:  derived/openalex_mentions.tsv
チェックポイント: derived/openalex_mentions_checkpoint.tsv（中断再開可能）
ログ:  logs/openalex_mentions_all_YYYYMMDD_HHMMSS.log

実行:
    nohup python scripts/openalex_mentions_all.py > logs/oa_nohup.log 2>&1 &
    tail -f logs/oa_nohup.log

推定時間: ~10時間（1.0秒インターバル × 34,789件・1リクエスト/件）

出力列:
    work_key, title, author, last_name, canonical,
    oa_count_author,  # タイトル AND 著者姓（正式指標）
    year_json         # 年別内訳JSON {"1980":3,"2005":12} （時系列分析用）
"""

import csv
import json
import logging
import re
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

import requests

# ─── パス設定 ───────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent.parent
INPUT_TSV  = BASE_DIR / "derived" / "ol_dump_population_with_author.tsv"
OUTPUT_TSV = BASE_DIR / "derived" / "openalex_mentions.tsv"
CHECKPOINT = BASE_DIR / "derived" / "openalex_mentions_checkpoint.tsv"
LOG_DIR    = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ─── ロガー設定 ─────────────────────────────────────────────
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_path  = LOG_DIR / f"openalex_mentions_all_{timestamp}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ─── 正規化ルール（v3確定版・§10.3 準拠） ───────────────────
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

def extract_last_name(author_str: str) -> str:
    s = author_str.strip()
    if not s:
        return ''
    last = s.split(',')[0].strip() if ',' in s else (s.split() or [''])[-1]
    return normalize(last)

# ─── OpenAlex API ────────────────────────────────────────────
OA_BASE       = "https://api.openalex.org/works"
MAILTO        = "tsutsui@nihu.jp"
INTERVAL      = 1.0    # 秒（429対策で余裕を持たせる）
RETRY_SLEEP   = 120    # 秒（429時の固定待機）
MAX_RETRY     = 5
AFTER_FAIL    = 600    # 秒（max retries 超過後の長めの待機）

def _get(params: dict) -> dict | None:
    url = f"{OA_BASE}?{urllib.parse.urlencode(params)}"
    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                log.warning(f"HTTP 429 – sleep {RETRY_SLEEP}s (attempt {attempt}/{MAX_RETRY})")
                time.sleep(RETRY_SLEEP)
            else:
                log.warning(f"HTTP {resp.status_code} | {url}")
                return None
        except requests.RequestException as e:
            log.warning(f"RequestException: {e} – sleep {RETRY_SLEEP}s (attempt {attempt}/{MAX_RETRY})")
            time.sleep(RETRY_SLEEP)

    log.error(f"Max retries exceeded | {url}")
    log.warning(f"429連鎖防止: {AFTER_FAIL}秒待機します...")
    time.sleep(AFTER_FAIL)   # ← ここが重要：連鎖を断ち切る
    return None


def fetch_count_and_years(title_norm: str, last_name: str) -> tuple[int, str]:
    """
    タイトル AND 著者姓の件数 + 年別内訳を1リクエストで取得。
    group_by=publication_year により年別内訳を同時取得。
    ※ group_by 使用時は select を付けない（HTTP 400になる）。
    """
    query = f"{title_norm} {last_name}".strip()
    if not query:
        return (-1, "")

    data = _get({
        "filter":   f"title.search:{query}",
        "per_page": 1,
        "group_by": "publication_year",
        "mailto":   MAILTO,
    })
    if data is None:
        return (-1, "")

    count = data.get("meta", {}).get("count", 0)
    year_dict = {
        str(item["key"]): item["count"]
        for item in data.get("group_by", [])
        if str(item.get("key", "")).isdigit()
    }
    year_json = json.dumps(year_dict, ensure_ascii=False) if year_dict else ""
    return (count, year_json)


# ─── 起動時 sanity check ─────────────────────────────────────
def run_sanity_check():
    log.info("=== Sanity check: Ulysses / joyce ===")
    count, year_json = fetch_count_and_years("ulysses", "joyce")
    log.info(f"  oa_count_author = {count}  (expected ~530)")
    log.info(f"  year_json sample = {year_json[:120]}")
    if count < 100:
        log.error(f"Sanity check FAILED (count={count}). 中止します。")
        sys.exit(1)
    log.info("Sanity check PASSED.")


# ─── チェックポイント管理 ─────────────────────────────────────
OUTPUT_COLS      = ["work_key", "title", "author", "last_name",
                    "canonical", "oa_count_author", "year_json"]
CHECKPOINT_EVERY = 1000

def load_checkpoint() -> set[str]:
    done = set()
    if CHECKPOINT.exists():
        with open(CHECKPOINT, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f, delimiter='\t'):
                done.add(row["work_key"])
        log.info(f"Checkpoint loaded: {len(done)} works already done")
    return done

def append_rows(path: Path, rows: list[dict], write_header: bool) -> None:
    with open(path, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_COLS, delimiter='\t',
                           extrasaction='ignore')
        if write_header:
            w.writeheader()
        w.writerows(rows)


# ─── メイン処理 ──────────────────────────────────────────────
def main():
    log.info("=== openalex_mentions_all.py v5 start ===")
    log.info(f"Input:  {INPUT_TSV}")
    log.info(f"Output: {OUTPUT_TSV}")
    log.info(f"Log:    {log_path}")
    log.info(f"INTERVAL={INTERVAL}s  RETRY_SLEEP={RETRY_SLEEP}s  AFTER_FAIL={AFTER_FAIL}s")

    if not INPUT_TSV.exists():
        log.error(f"Input file not found: {INPUT_TSV}")
        sys.exit(1)

    run_sanity_check()

    # 直前セッションの429ペナルティが残っている場合の回復待機
    warmup = 60
    log.info(f"ウォームアップ待機 {warmup}秒（レート制限リセット確保）...")
    time.sleep(warmup)

    done_keys = load_checkpoint()

    with open(INPUT_TSV, newline='', encoding='utf-8') as f:
        all_rows = list(csv.DictReader(f, delimiter='\t'))

    total   = len(all_rows)
    pending = [r for r in all_rows if r["work_key"] not in done_keys]
    log.info(f"Total: {total}  Done: {len(done_keys)}  Remaining: {len(pending)}")

    buffer      = []
    error_count = 0
    skipped     = 0
    cp_header   = not CHECKPOINT.exists()

    for i, row in enumerate(pending, 1):
        work_key  = row["work_key"]
        title     = row.get("title", "").strip()
        author    = row.get("author_name", "").strip()
        canonical = row.get("canonical", "0").strip()
        last_name = extract_last_name(author) if author else ""

        title_norm = normalize(title)

        if not title_norm or not last_name:
            # タイトルなし or 著者姓なし → スキップ
            count, year_json = -1, ""
            skipped += 1
        else:
            count, year_json = fetch_count_and_years(title_norm, last_name)
            if count == -1:
                error_count += 1
            time.sleep(INTERVAL)

        buffer.append({
            "work_key":       work_key,
            "title":          title,
            "author":         author,
            "last_name":      last_name,
            "canonical":      canonical,
            "oa_count_author": count,
            "year_json":      year_json,
        })

        if i % 100 == 0:
            pct = (len(done_keys) + i) / total * 100
            log.info(
                f"Progress: {len(done_keys)+i}/{total} ({pct:.1f}%)"
                f" | errors={error_count} skipped={skipped}"
            )

        if len(buffer) >= CHECKPOINT_EVERY:
            append_rows(CHECKPOINT, buffer, write_header=cp_header)
            cp_header = False
            log.info(f"Checkpoint saved (+{len(buffer)} rows)")
            buffer.clear()

    if buffer:
        append_rows(CHECKPOINT, buffer, write_header=cp_header)
        log.info(f"Final checkpoint saved (+{len(buffer)} rows)")

    log.info(f"Writing final output → {OUTPUT_TSV}")
    CHECKPOINT.replace(OUTPUT_TSV)
    log.info(f"=== Done. total={total} errors={error_count} skipped={skipped} ===")


if __name__ == "__main__":
    main()