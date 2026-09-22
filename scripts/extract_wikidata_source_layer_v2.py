#!/usr/bin/env python3

import bz2
import csv
import json
import time
from pathlib import Path

import orjson

DUMP = Path(
    "/media/hdd1/user/tsutsui/wikidata/"
    "wikidata-20260805-all.json.bz2"
)

TARGETS = (
    Path.home()
    / "research-data/wikidata-source-layer/2026-08-05"
    / "target_qids_v2.tsv"
)

OUTDIR = (
    Path.home()
    / "research-data/wikidata-source-layer/2026-08-05"
)

RAW_OUT = OUTDIR / "wikidata_target_items_raw_v2.jsonl"
SUMMARY_OUT = OUTDIR / "extract_v2_summary.json"

EXPECTED_TARGETS = 12951


def load_targets():
    rows = {}

    with TARGETS.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            qid = r["qid"].strip()
            rows[qid] = r

    return rows


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)

    target_rows = load_targets()
    targets = set(target_rows)

    print("target QIDs:", len(targets))

    if len(targets) != EXPECTED_TARGETS:
        raise RuntimeError(
            f"Expected {EXPECTED_TARGETS} target QIDs; "
            f"found {len(targets)}"
        )

    found = set()
    malformed = 0
    q_items_scanned = 0
    started = time.time()

    # Fresh extraction.
    # Each matching raw item is written immediately.
    with bz2.open(DUMP, "rb") as fin, \
         RAW_OUT.open("w", encoding="utf-8") as fout:

        for raw in fin:
            line = raw.strip()

            if not line or line in (b"[", b"]"):
                continue

            if line.endswith(b","):
                line = line[:-1]

            try:
                item = orjson.loads(line)
            except Exception:
                malformed += 1
                continue

            qid = item.get("id", "")

            if not isinstance(qid, str) or not qid.startswith("Q"):
                continue

            q_items_scanned += 1

            if qid in targets:
                wrapper = {
                    "source": "wikidata",
                    "source_namespace": "item",
                    "source_id": qid,
                    "snapshot_date": "2026-08-05",
                    "record": item,
                }

                fout.write(
                    json.dumps(
                        wrapper,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                fout.flush()

                found.add(qid)

                if len(found) % 250 == 0:
                    elapsed = time.time() - started
                    print(
                        f"found {len(found):,}/{len(targets):,} "
                        f"after {elapsed/3600:.2f}h",
                        flush=True,
                    )

                if len(found) == len(targets):
                    print(
                        "All target QIDs found; stopping early.",
                        flush=True,
                    )
                    break

            if q_items_scanned % 1_000_000 == 0:
                elapsed = time.time() - started
                rate = q_items_scanned / elapsed if elapsed else 0

                print(
                    f"scanned {q_items_scanned:,} Q-items; "
                    f"found {len(found):,}/{len(targets):,}; "
                    f"rate {rate:,.0f}/s; "
                    f"elapsed {elapsed/3600:.2f}h",
                    flush=True,
                )

    elapsed = time.time() - started
    missing = sorted(targets - found)

    summary = {
        "source": "Wikidata",
        "snapshot_date": "2026-08-05",
        "source_dump": str(DUMP),
        "target_file": str(TARGETS),
        "target_qids": len(targets),
        "found_qids": len(found),
        "missing_qids": len(missing),
        "missing_qid_list": missing,
        "q_items_scanned": q_items_scanned,
        "malformed_lines": malformed,
        "elapsed_seconds": elapsed,
        "raw_output": str(RAW_OUT),
    }

    SUMMARY_OUT.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n=== EXTRACTION COMPLETE ===")
    print("target QIDs:", len(targets))
    print("found QIDs:", len(found))
    print("missing QIDs:", len(missing))
    print("Q-items scanned:", q_items_scanned)
    print("malformed:", malformed)
    print("elapsed hours:", round(elapsed / 3600, 3))
    print("raw output:", RAW_OUT)
    print("summary:", SUMMARY_OUT)

    if missing:
        print("\nfirst missing QIDs:")
        for qid in missing[:50]:
            print(" ", qid)


if __name__ == "__main__":
    main()
