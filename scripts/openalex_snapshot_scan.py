"""
openalex_snapshot_scan.py  —  v3 Aho-Corasick版
v2比で~100倍高速・途中再開対応

Usage:
    pip install pyahocorasick --break-system-packages
    python scripts/openalex_snapshot_scan.py --workers 16
    python scripts/openalex_snapshot_scan.py --workers 16 --resume
"""
import argparse, csv, gzip, json, logging, multiprocessing as mp
import os, re, sys, time
from glob import glob
from pathlib import Path

SNAPSHOT_DIR   = "/mnt/d/openalex/works"
POPULATION_TSV = "derived/ol_dump_population_with_author.tsv"
OUTPUT_TSV     = "derived/openalex_snapshot_mentions.tsv"
CHECKPOINT_TSV = "derived/openalex_snapshot_checkpoint.tsv"
DONE_JSON      = "derived/openalex_snapshot_done_partitions.json"
DEFAULT_WORKERS = max(1, mp.cpu_count() - 2)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("logs/openalex_snapshot_scan.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

_LEADING_ART = re.compile(r'^(the|a|an)\s+', re.IGNORECASE)
_DROP_CHARS  = re.compile(r"['\-\u2018\u2019\u201c\u201d]")
_NON_ALNUM   = re.compile(r'[^a-z0-9\s]')
_MULTI_SPC   = re.compile(r'\s+')

def normalize(text):
    if not text: return ""
    t = text.lower()
    t = _LEADING_ART.sub('', t)
    t = _DROP_CHARS.sub('', t)
    t = _NON_ALNUM.sub(' ', t)
    return _MULTI_SPC.sub(' ', t).strip()

def extract_last_name(author):
    if not author: return ""
    s = author.strip()
    last = s.split(',')[0].strip() if ',' in s else (s.split() or [''])[-1]
    return normalize(last)

def load_population(path):
    works = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            tn = normalize(row.get("title", ""))
            if len(tn) < 6:
                continue
            works.append({
                "work_key":   row["work_key"],
                "title":      row["title"],
                "title_norm": tn,
                "author":     row.get("author_name", ""),
                "last_name":  extract_last_name(row.get("author_name", "")),
                "canonical":  row.get("canonical", "0"),
            })
    return works

def scan_file(args):
    gz_path, population_tsv = args
    works = load_population(population_tsv)

    # title_norm → [work_keys]
    tn_to_keys = {}
    for w in works:
        tn_to_keys.setdefault(w["title_norm"], []).append(w["work_key"])

    # Aho-Corasick オートマトン構築
    try:
        import ahocorasick
        A = ahocorasick.Automaton()
        for tn, keys in tn_to_keys.items():
            A.add_word(tn, (tn, keys))
        A.make_automaton()
        use_aho = True
    except ImportError:
        use_aho = False

    # work_key → last_name
    author_idx = {w["work_key"]: w["last_name"] for w in works}

    counts = {w["work_key"]: {"total":0,"via_title":0,"via_abstract":0} for w in works}

    try:
        with gzip.open(gz_path, "rt", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue

                oa_title = normalize(obj.get("display_name",""))
                if not oa_title:
                    continue

                aii = {}  # abstract照合無効化
                abs_words = set(normalize(w) for w in aii.keys()) if aii else set()

                author_lns = set()
                for a in (obj.get("authorships") or []):
                    raw = (a.get("raw_author_name")
                           or (a.get("author") or {}).get("display_name",""))
                    ln = extract_last_name(raw)
                    if ln: author_lns.add(ln)

                # タイトル照合
                if use_aho:
                    for _, (tn, keys) in A.iter(oa_title):
                        for wk in keys:
                            ln = author_idx.get(wk,"")
                            if ln and ln not in author_lns: continue
                            counts[wk]["total"]     += 1
                            counts[wk]["via_title"] += 1
                else:
                    for tn, keys in tn_to_keys.items():
                        if tn not in oa_title: continue
                        for wk in keys:
                            ln = author_idx.get(wk,"")
                            if ln and ln not in author_lns: continue
                            counts[wk]["total"]     += 1
                            counts[wk]["via_title"] += 1

                # abstract照合
                if abs_words:
                    for tn, keys in tn_to_keys.items():
                        if not set(tn.split()).issubset(abs_words): continue
                        for wk in keys:
                            ln = author_idx.get(wk,"")
                            if ln and ln not in author_lns: continue
                            counts[wk]["total"]        += 1
                            counts[wk]["via_abstract"] += 1

    except Exception as ex:
        sys.stderr.write(f"ERROR {gz_path}: {ex}\n")

    return counts

def merge_counts(base, new):
    for wk, c in new.items():
        if wk not in base:
            base[wk] = {"total":0,"via_title":0,"via_abstract":0}
        base[wk]["total"]        += c["total"]
        base[wk]["via_title"]    += c["via_title"]
        base[wk]["via_abstract"] += c["via_abstract"]
    return base

def save_tsv(counts, works, path):
    with open(path,"w",newline="",encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["work_key","title","author","last_name","canonical",
                    "oa_count","via_title","via_abstract"])
        for e in works:
            c = counts.get(e["work_key"],{"total":0,"via_title":0,"via_abstract":0})
            w.writerow([e["work_key"],e["title"],e["author"],e["last_name"],
                        e["canonical"],c["total"],c["via_title"],c["via_abstract"]])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--snapshot-dir", default=SNAPSHOT_DIR)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    os.makedirs("logs", exist_ok=True)
    log.info(f"ワーカー数: {args.workers} / CPU: {mp.cpu_count()}")

    try:
        import ahocorasick
        log.info("Aho-Corasick: 有効 ✓")
    except ImportError:
        log.warning("Aho-Corasick: 無効 → pip install pyahocorasick を推奨")

    works = load_population(POPULATION_TSV)
    log.info(f"母集団: {len(works)} works")

    gz_files = sorted(glob(f"{args.snapshot_dir}/updated_date=*/part_*.gz"))
    log.info(f"スキャン対象: {len(gz_files)} ファイル")

    partitions = {}
    for gz in gz_files:
        part = Path(gz).parent.name
        partitions.setdefault(part, []).append(gz)

    done_parts = set()
    merged = {}

    if args.resume and Path(DONE_JSON).exists() and Path(CHECKPOINT_TSV).exists():
        with open(DONE_JSON) as f:
            done_parts = set(json.load(f))
        with open(CHECKPOINT_TSV, encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                merged[row["work_key"]] = {
                    "total":        int(row["oa_count"]),
                    "via_title":    int(row["via_title"]),
                    "via_abstract": int(row["via_abstract"]),
                }
        log.info(f"再開: {len(done_parts)} パーティション完了済みをスキップ")

    t_start = time.time()
    done_files = sum(len(partitions[p]) for p in done_parts if p in partitions)

    for pi, (partition, files) in enumerate(sorted(partitions.items())):
        if partition in done_parts:
            continue

        log.info(f"[{pi+1}/{len(partitions)}] {partition} — {len(files)} files")
        tasks = [(gz, POPULATION_TSV) for gz in files]

        with mp.Pool(processes=args.workers) as pool:
            results = pool.map(scan_file, tasks)

        for r in results:
            merge_counts(merged, r)

        done_files += len(files)
        done_parts.add(partition)
        elapsed = time.time() - t_start
        rate = done_files / elapsed if elapsed > 0 else 1
        eta = (len(gz_files) - done_files) / rate
        log.info(f"  {done_files}/{len(gz_files)} files | "
                 f"経過 {elapsed/60:.1f}分 | 残り推定 {eta/60:.1f}分")

        save_tsv(merged, works, CHECKPOINT_TSV)
        with open(DONE_JSON,"w") as f:
            json.dump(list(done_parts), f)

    save_tsv(merged, works, OUTPUT_TSV)
    log.info(f"完了 → {OUTPUT_TSV}")

    def median(vals):
        s = sorted(vals); return s[len(s)//2] if s else 0

    c_vals = [merged.get(w["work_key"],{}).get("total",0) for w in works if w["canonical"]=="1"]
    n_vals = [merged.get(w["work_key"],{}).get("total",0) for w in works if w["canonical"]=="0"]
    log.info(f"canonical 中央値: {median(c_vals)}  non-canon 中央値: {median(n_vals)}")

if __name__ == "__main__":
    main()