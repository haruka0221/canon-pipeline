"""
fetch_hathitrust_api.py  (checkpoint + 0.5s版)
================================================
- 途中で止めても再開できる（処理済みwork_keyをスキップ）
- sleep=0.5秒（従来の倍速）

使い方:
  python3 scripts/fetch_hathitrust_api.py          # canonical のみ
  python3 scripts/fetch_hathitrust_api.py --full   # 全件
"""

import csv, json, time, logging, argparse, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime
from collections import defaultdict

ROOT     = Path(__file__).resolve().parent.parent
OCLC_TSV = ROOT / "derived" / "ol_dump_oclc_all.tsv"
POP_TSV  = ROOT / "derived" / "ol_dump_population_with_author.tsv"
OUT_DIR  = ROOT / "derived"
LOG_DIR  = ROOT / "logs"

API_BASE  = "https://catalog.hathitrust.org/api/volumes/brief/oclc/{oclc}.json"
SLEEP_SEC = 0.5
TIMEOUT   = 20
PD_CODES  = {"pd", "pdus", "cc-by", "cc-by-nd", "cc-by-sa", "cc-zero"}

LOG_DIR.mkdir(exist_ok=True)
log_path = LOG_DIR / f"fetch_hathitrust_api_{datetime.today().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(log_path), logging.StreamHandler()]
)
log = logging.getLogger(__name__)


def normalize_wk(wk: str) -> str:
    return wk.strip().replace("/works/", "")


def load_done(out_path: Path) -> set:
    """出力ファイルが既にあれば、処理済みwork_keyを返す（チェックポイント）。"""
    done = set()
    if not out_path.exists():
        return done
    with open(out_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            wk = row.get("work_key", "").strip()
            if wk:
                done.add(wk)
    log.info(f"Checkpoint: {len(done)} works already done, skipping.")
    return done


def load_canonical_work_keys() -> set:
    keys = set()
    with open(POP_TSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if row.get("canonical", "0").strip() == "1":
                keys.add(normalize_wk(row["work_key"]))
    log.info(f"Canonical work_keys loaded: {len(keys)}")
    return keys


def load_oclc_map(canonical_only: bool, canonical_keys: set) -> dict:
    wk_to_oclcs = defaultdict(list)
    with open(OCLC_TSV, newline="", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            wk   = normalize_wk(parts[0])
            oclc = parts[1].strip()
            if not wk or not oclc:
                continue
            if canonical_only and wk not in canonical_keys:
                continue
            wk_to_oclcs[wk].append(oclc)
    log.info(f"Works with OCLC loaded: {len(wk_to_oclcs)}")
    return dict(wk_to_oclcs)


def fetch_oclc(oclc: str) -> dict | None:
    url = API_BASE.format(oclc=oclc)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "canon-pipeline/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        log.warning(f"HTTP {e.code} for OCLC {oclc}")
        return None
    except Exception as e:
        log.warning(f"Error fetching OCLC {oclc}: {e}")
        return None

    items        = data.get("items", [])
    records      = data.get("records", {})
    htid_count   = len(items)
    pd_count     = sum(1 for i in items if i.get("rightsCode", "") in PD_CODES)
    record_count = len(records)
    sample_htids = "|".join(i["htid"] for i in items[:3] if "htid" in i)
    return {
        "htid_count":   htid_count,
        "pd_count":     pd_count,
        "record_count": record_count,
        "sample_htids": sample_htids,
    }


def resolve_work(work_key: str, oclcs: list) -> dict:
    best = {"htid_count": 0, "pd_count": 0, "record_count": 0,
            "sample_htids": "", "matched_oclc": ""}
    for oclc in oclcs[:10]:
        time.sleep(SLEEP_SEC)
        result = fetch_oclc(oclc)
        if result is None:
            continue
        if result["htid_count"] > best["htid_count"]:
            best = result | {"matched_oclc": oclc}
        if best["htid_count"] > 0:
            break
    return best | {"work_key": work_key, "oclc_tried": len(oclcs[:10])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()

    canonical_keys = load_canonical_work_keys()
    oclc_map = load_oclc_map(
        canonical_only=not args.full,
        canonical_keys=canonical_keys
    )

    if not oclc_map:
        log.error("OCLC map is empty. Check file paths.")
        return

    out_name = "ht_api_full.tsv" if args.full else "ht_api_canonical.tsv"
    out_path = OUT_DIR / out_name

    # チェックポイント読み込み
    done = load_done(out_path)
    remaining = {wk: oclcs for wk, oclcs in oclc_map.items() if wk not in done}
    log.info(f"Remaining: {len(remaining)} / {len(oclc_map)} works")

    if not remaining:
        log.info("All done already!")
        return

    fieldnames = ["work_key", "canonical", "htid_count", "pd_count",
                  "record_count", "matched_oclc", "oclc_tried", "sample_htids"]

    # 追記モード
    write_header = not out_path.exists() or out_path.stat().st_size == 0
    with open(out_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        if write_header:
            writer.writeheader()

        total = len(remaining)
        for i, (work_key, oclcs) in enumerate(remaining.items(), 1):
            result = resolve_work(work_key, oclcs)
            result["canonical"] = "1" if work_key in canonical_keys else "0"
            writer.writerow({k: result.get(k, "") for k in fieldnames})
            f.flush()  # 1件ごとにディスクに書く

            if i % 100 == 0 or i == total:
                log.info(f"[{i}/{total}] {work_key}  htid={result['htid_count']}")

    # サマリ
    with open(out_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    hits = sum(1 for r in rows if int(r.get("htid_count") or 0) > 0)
    log.info(f"Total done: {len(rows)} | htid>0: {hits} ({hits/len(rows)*100:.1f}%)")


if __name__ == "__main__":
    main()