#!/usr/bin/env python3

import argparse
import csv
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

WORK_RE = re.compile(rb"/works/(OL[0-9]+W)")


def read_target_ids(path):
    with path.open(encoding="utf-8", newline="") as f:
        rows = csv.DictReader(f, delimiter="\t")
        ids = {
            r["target_id"].strip()
            for r in rows
            if r.get("target_id", "").strip()
        }
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", type=Path, required=True)
    ap.add_argument("--targets", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--summary", type=Path, required=True)
    ap.add_argument("--pigz-threads", type=int, default=4)
    ap.add_argument("--progress-every", type=int, default=1_000_000)
    ap.add_argument("--limit-lines", type=int, default=None)
    args = ap.parse_args()

    target_ids = read_target_ids(args.targets)
    print("target works:", len(target_ids))

    args.output.parent.mkdir(parents=True, exist_ok=True)

    tmp = Path(str(args.output) + ".part")
    if tmp.exists():
        raise RuntimeError(f"partial output already exists: {tmp}")
    if args.output.exists():
        raise RuntimeError(f"output already exists: {args.output}")

    cmd = [
        "pigz", "-dc",
        "-p", str(args.pigz_threads),
        str(args.dump),
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
    )

    lines = 0
    regex_prefilter = 0
    parsed = 0
    matched_editions = 0
    parse_errors = 0
    target_link_counts = Counter()

    limited = False

    try:
        with tmp.open("w", encoding="utf-8") as out:
            assert proc.stdout is not None

            for raw in proc.stdout:
                lines += 1

                if args.limit_lines and lines > args.limit_lines:
                    limited = True
                    break

                if args.progress_every and lines % args.progress_every == 0:
                    print(
                        f"lines={lines:,} "
                        f"matched_editions={matched_editions:,} "
                        f"targets_seen={len(target_link_counts):,}"
                    )

                # Cheap prefilter: do not JSON-decode unrelated editions.
                raw_work_ids = {
                    x.decode("ascii")
                    for x in WORK_RE.findall(raw)
                }

                if not (raw_work_ids & target_ids):
                    continue

                regex_prefilter += 1

                parts = raw.rstrip(b"\n").split(b"\t", 4)
                if len(parts) != 5:
                    parse_errors += 1
                    continue

                try:
                    ed = json.loads(parts[4])
                except Exception:
                    parse_errors += 1
                    continue

                parsed += 1

                # Validate against the actual structured works field.
                actual_work_ids = set()
                for w in ed.get("works") or []:
                    if isinstance(w, dict):
                        key = str(w.get("key", ""))
                    else:
                        key = str(w)

                    if key.startswith("/works/"):
                        actual_work_ids.add(key.split("/")[-1])

                matched = sorted(actual_work_ids & target_ids)
                if not matched:
                    continue

                row = {
                    "edition_key": parts[1].decode(
                        "utf-8", errors="replace"
                    ),
                    "revision": parts[2].decode(
                        "utf-8", errors="replace"
                    ),
                    "last_modified": parts[3].decode(
                        "utf-8", errors="replace"
                    ),
                    "matched_target_ids": matched,
                    "edition": ed,
                }

                out.write(
                    json.dumps(row, ensure_ascii=False) + "\n"
                )

                matched_editions += 1
                for tid in matched:
                    target_link_counts[tid] += 1

        if limited:
            proc.terminate()
            proc.wait()
        else:
            rc = proc.wait()
            if rc != 0:
                raise RuntimeError(f"pigz exited with code {rc}")

        tmp.replace(args.output)

    except Exception:
        if proc.poll() is None:
            proc.terminate()
            proc.wait()
        raise

    summary = {
        "source_dump": str(args.dump),
        "source_dump_size_bytes": args.dump.stat().st_size,
        "targets_file": str(args.targets),
        "target_work_count": len(target_ids),
        "lines_scanned": lines if not limited else min(lines, args.limit_lines),
        "limited_smoke_run": limited,
        "regex_prefilter_rows": regex_prefilter,
        "json_parsed_rows": parsed,
        "matched_edition_rows": matched_editions,
        "target_works_with_at_least_one_edition": len(target_link_counts),
        "parse_errors": parse_errors,
    }

    args.summary.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\nDONE")
    for k, v in summary.items():
        print(f"{k}: {v}")
    print("output:", args.output)
    print("summary:", args.summary)


if __name__ == "__main__":
    main()
