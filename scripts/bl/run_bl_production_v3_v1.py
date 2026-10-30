#!/usr/bin/env python3
"""BL SRU production v3 runner (dry-run by default; nothing is sent without --execute).

Inherits run_bl_calibration_v2_v1.py (request/parse code, no retries, night window,
resume, raw root outside the repo) with the v3 protocol changes:

  * input  derived/bl_production/production_v3/targets_v1.tsv, one --batch N at a time
  * routes T2, K1, A1 as in v2; several query authors (';'-joined) each get K1 and A1
  * a route whose CQL would contain a double quote is NOT sent: it is logged as
    SKIPPED_INVALID_QUERY, and a quote-stripped twin (T2q / K1q / A1q) is sent instead
  * caps: per invocation --max-requests (default 7000); cumulative CUMULATIVE_CAP
    (200,000) counted over the physical_requests.tsv of ALL batches
  * outputs under derived/bl_production/production_v3/retrieval/batch_NNN/
    (plan, request log, status, manifests; no record content)
  * --raw-root must be outside the repository (default the server's private directory)

Night window Europe/London 22:00-06:00; >= 3 s after each response; stops (exit 3) on
HTTP 429 / >= 500 / network error / SRU diagnostic / XML parse error.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import http.client
import json
import subprocess
import sys
import time
import traceback
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, time as dtime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

SCRIPT_VERSION = "run_bl_production_v3_v1"
ROOT = Path(__file__).resolve().parents[2]
PROD = ROOT / "derived" / "bl_production" / "production_v3"
TARGETS = PROD / "targets_v1.tsv"
RET = PROD / "retrieval"
TARGETS_SHA = "6006775089c09c168cb082cb823bcfb39744b68327a75040d39e1cb5c6307ab4"

ENDPOINT = "https://eu06.alma.exlibrisgroup.com/view/sru/44BL_MAIN"
SRU_VERSION, RECORD_SCHEMA, PAGE_SIZE, CAP = "1.2", "marcxml", 20, 200
MIN_INTERVAL_S, TIMEOUT_S = 3.0, 60
CUMULATIVE_CAP, DEFAULT_PER_RUN_CAP = 200_000, 7_000
LONDON = ZoneInfo("Europe/London")
NIGHT_START, NIGHT_END = dtime(22, 0), dtime(6, 0)
DEFAULT_RAW = "/media/hdd1/user/tsutsui/bl/production_v3_raw"

LOG_FIELDS = ["request_id", "phys_id", "route_class", "start_record", "maximum_records",
              "request_started_utc", "request_started_london", "elapsed_ms", "http_status",
              "outcome", "number_of_records", "records_in_response", "diagnostic",
              "raw_relpath", "raw_sha256", "url"]


# ---------------------------------------------------------------- helpers (v1/v2)
def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cql_value(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def signature(cql):
    return " ".join(unicodedata.normalize("NFKC", cql).casefold().split())


def surname(author):
    toks = author.split()
    return toks[-1] if toks else ""


def read_tsv(path):
    return pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)


def write_tsv(path, rows, fields):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def git_head():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def local(tag):
    return tag.rsplit("}", 1)[-1]


def parse_sru(body):
    root = ET.fromstring(body)
    n, recs, diag = None, 0, []
    for el in root.iter():
        name = local(el.tag)
        if name == "numberOfRecords" and n is None:
            n = int((el.text or "0").strip())
        elif name == "recordData":
            recs += 1
        elif name == "diagnostic":
            parts = [(c.text or "").strip() for c in el]
            diag.append(" | ".join(p for p in parts if p))
    return n, recs, " || ".join(diag)


def in_night_window(now_london):
    t = now_london.time()
    return t >= NIGHT_START or t < NIGHT_END


def strip_quotes(s):
    return " ".join(s.replace('"', " ").split())


# ---------------------------------------------------------------- plan (v3)
def build_plan(batch_rows):
    """Logical queries for one batch. Quote-bearing routes become SKIPPED + a 'q' twin."""
    logical, qn = [], 0

    def add(t, route, title_raw, alias_ids, author, cql, note=""):
        nonlocal qn
        qn += 1
        logical.append({"bl_query_id": f"BLQ3_{t['batch']:03d}_{qn:05d}", "batch": t["batch"],
                        "target_id": t["target_id"], "target_lane": t["target_lane"], "route": route,
                        "title_raw": title_raw, "source_alias_ids": alias_ids, "author_name": author,
                        "cql": cql, "physical_signature": signature(cql) if cql else "", "plan_note": note})

    for tid, rows in batch_rows.groupby("target_id", sort=True):
        rows = rows.sort_values("ol_entity_id")
        t = {"batch": int(rows.iloc[0]["batch"]), "target_id": tid, "target_lane": rows.iloc[0]["target_lane"]}
        authors = []
        for r in rows.itertuples(index=False):
            for a in r.query_authors.split(";"):
                if a and a not in authors:
                    authors.append(a)
        titles = {}
        for r in rows.itertuples(index=False):
            titles.setdefault(signature(r.query_title), {"raw": r.query_title, "ids": []})["ids"].append(r.ol_entity_id)

        for t_sig, tt in titles.items():
            raw, ids = tt["raw"], ";".join(tt["ids"])
            tq = '"' in raw
            # T2
            if tq:
                add(t, "T2", raw, ids, "", "", "SKIPPED_INVALID_QUERY")
                add(t, "T2q", raw, ids, "", f'alma.title == "{cql_value(strip_quotes(raw))}"', "QUOTE_STRIPPED")
            else:
                add(t, "T2", raw, ids, "", f'alma.title == "{cql_value(raw)}"')
            # K1 per author
            if authors:
                for a in authors:
                    kq = tq or ('"' in a)
                    kw = raw + " " + surname(a)
                    if kq:
                        add(t, "K1", raw, ids, a, "", "SKIPPED_INVALID_QUERY")
                        add(t, "K1q", raw, ids, a, f'alma.all_for_ui all "{cql_value(strip_quotes(kw))}"', "QUOTE_STRIPPED")
                    else:
                        add(t, "K1", raw, ids, a, f'alma.all_for_ui all "{cql_value(kw)}"')
            else:
                add(t, "K1", raw, ids, "", "", "SKIPPED_NO_AUTHOR")
        # A1 per author
        for a in authors:
            if '"' in a:
                add(t, "A1", "", "", a, "", "SKIPPED_INVALID_QUERY")
                add(t, "A1q", "", "", a, f'alma.creator all "{cql_value(strip_quotes(a))}"', "QUOTE_STRIPPED")
            else:
                add(t, "A1", "", "", a, f'alma.creator all "{cql_value(a)}"')
        if not authors:
            add(t, "A1", "", "", "", "", "SKIPPED_NO_AUTHOR")

    physical, by_sig = [], {}
    for q in logical:
        if not q["cql"]:
            q["phys_id"] = ""
            continue
        sig = q["physical_signature"]
        if sig not in by_sig:
            by_sig[sig] = f"BLP3_{q['batch']:03d}_{len(physical) + 1:05d}"
            physical.append({"phys_id": by_sig[sig], "physical_signature": sig, "cql_sent": q["cql"],
                             "route_class": "A1" if q["route"] in ("A1", "A1q") else "TITLE_OR_KEYWORD",
                             "n_logical": 0, "targets": set()})
        q["phys_id"] = by_sig[sig]
        p = physical[int(by_sig[sig].rsplit("_", 1)[1]) - 1]
        p["n_logical"] += 1
        p["targets"].add(q["target_id"])
    for p in physical:
        p["targets"] = ";".join(sorted(p["targets"]))
    return logical, physical


# ---------------------------------------------------------------- runner (v2, cumulative over batches)
class StopRun(Exception):
    pass


def cumulative_requests(ret_root: Path) -> int:
    n = 0
    for p in ret_root.glob("batch_*/physical_requests.tsv"):
        with open(p, encoding="utf-8") as f:
            n += max(0, sum(1 for _ in f) - 1)
    return n


class Runner:
    def __init__(self, out, ret_root, raw_root, contact, endpoint, per_run_cap):
        self.out, self.raw_root, self.endpoint = out, raw_root, endpoint
        self.ua = f"canon-pipeline BL production v3 (academic research; contact: {contact})"
        self.per_run_cap, self.sent, self.last_response = per_run_cap, 0, 0.0
        self.log_path = out / "physical_requests.tsv"
        self.done, self.req_n = {}, 0
        self.cumulative = cumulative_requests(ret_root)
        if self.log_path.exists():
            for r in read_tsv(self.log_path).itertuples(index=False):
                self.req_n = max(self.req_n, int(r.request_id.rsplit("_", 1)[1]))
                if r.outcome == "COMPLETE":
                    self.done[(r.phys_id, int(r.start_record))] = r.number_of_records
        else:
            with open(self.log_path, "w", encoding="utf-8", newline="") as f:
                csv.writer(f, delimiter="\t", lineterminator="\n").writerow(LOG_FIELDS)

    def log(self, row):
        with open(self.log_path, "a", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=LOG_FIELDS, delimiter="\t", lineterminator="\n").writerow(row)

    def guard(self):
        if self.cumulative >= CUMULATIVE_CAP:
            raise StopRun(f"cumulative cap {CUMULATIVE_CAP} reached")
        if self.sent >= self.per_run_cap:
            raise StopRun(f"per-run cap {self.per_run_cap} reached")
        now = datetime.now(LONDON)
        if not in_night_window(now):
            raise StopRun(f"outside night window, London time {now:%H:%M}")

    def request(self, p, start, batch):
        self.guard()
        params = {"version": SRU_VERSION, "operation": "searchRetrieve", "query": p["cql_sent"],
                  "recordSchema": RECORD_SCHEMA, "maximumRecords": str(PAGE_SIZE), "startRecord": str(start)}
        url = self.endpoint + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        wait = self.last_response + MIN_INTERVAL_S - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self.sent += 1
        self.cumulative += 1
        self.req_n += 1
        rid = f"BLR3_{batch:03d}_{self.req_n:06d}"
        started_utc, started_ldn = utc_now(), datetime.now(LONDON).isoformat()
        t0 = time.monotonic()
        status, body, err, outcome = "", b"", "", ""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self.ua})
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                status, body = str(resp.status), resp.read()
        except urllib.error.HTTPError as e:
            status, body, err, outcome = str(e.code), e.read() or b"", f"HTTP {e.code}", "STOP_HTTP"
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as e:
            err, outcome = f"{type(e).__name__}: {e}", "STOP_NETWORK"
        self.last_response = time.monotonic()
        elapsed = int((self.last_response - t0) * 1000)
        relpath, digest = "", ""
        if body:
            relpath = f"batch_{batch:03d}/{p['phys_id']}/{p['phys_id']}_s{start:04d}_{rid}.xml"
            path = self.raw_root / relpath
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            digest = sha256_file(path)
        row = {"request_id": rid, "phys_id": p["phys_id"], "route_class": p["route_class"], "start_record": start,
               "maximum_records": PAGE_SIZE, "request_started_utc": started_utc, "request_started_london": started_ldn,
               "elapsed_ms": elapsed, "http_status": status, "number_of_records": "", "records_in_response": "",
               "diagnostic": err, "raw_relpath": relpath, "raw_sha256": digest, "url": url}
        if outcome:
            row["outcome"] = outcome
            self.log(row)
            raise StopRun(f"{outcome}: {err}")
        try:
            n, recs, diag = parse_sru(body)
        except ET.ParseError as e:
            row["outcome"], row["diagnostic"] = "STOP_PARSE", f"ParseError: {e}"
            self.log(row)
            raise StopRun(f"STOP_PARSE: {e}")
        row["number_of_records"], row["records_in_response"], row["diagnostic"] = ("" if n is None else n), recs, diag
        if diag or n is None:
            row["outcome"] = "STOP_DIAGNOSTIC"
            self.log(row)
            raise StopRun(f"STOP_DIAGNOSTIC: {diag}")
        row["outcome"] = "COMPLETE"
        self.log(row)
        self.done[(p["phys_id"], start)] = n
        return n

    def run_query(self, p, batch):
        key1 = (p["phys_id"], 1)
        n = int(self.done[key1]) if key1 in self.done else self.request(p, 1, batch)
        if p["route_class"] == "A1" and n > CAP:
            return "SKIPPED_POLICY_CAP"
        for start in range(1 + PAGE_SIZE, min(n, CAP) + 1, PAGE_SIZE):
            if (p["phys_id"], start) not in self.done:
                self.request(p, start, batch)
        return "CAPPED" if n > CAP else "COMPLETE"


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch", type=int, required=True, help="batch number from targets_v1.tsv (1..34)")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--contact")
    ap.add_argument("--max-requests", type=int, default=DEFAULT_PER_RUN_CAP)
    ap.add_argument("--raw-root", default=DEFAULT_RAW)
    ap.add_argument("--out-dir", default=str(RET), help="retrieval root; must be non-default for a mock run")
    ap.add_argument("--endpoint", default=ENDPOINT, help="override ONLY for the mock server")
    ap.add_argument("--ignore-night-window", action="store_true", help="ONLY with a mock --endpoint")
    ap.add_argument("--skip", nargs="*", default=[], help="phys_ids to record as SKIPPED_INVALID_QUERY without sending")
    args = ap.parse_args()

    if sha256_file(TARGETS) != TARGETS_SHA:
        sys.exit("ERROR: targets_v1.tsv sha256 != frozen value")
    ret_root = Path(args.out_dir).expanduser().resolve()
    if args.endpoint != ENDPOINT and ret_root == RET.resolve():
        sys.exit("ERROR: a mock --endpoint needs a non-default --out-dir")
    if args.endpoint == ENDPOINT and ret_root != RET.resolve():
        sys.exit("ERROR: the real endpoint writes only to the default --out-dir")
    if args.ignore_night_window and args.endpoint == ENDPOINT:
        sys.exit("ERROR: --ignore-night-window is only allowed with a mock --endpoint")

    T = read_tsv(TARGETS)
    rows = T[T["batch"].astype(int) == args.batch]
    if rows.empty:
        sys.exit(f"ERROR: no targets in batch {args.batch}")
    out = ret_root / f"batch_{args.batch:03d}"
    out.mkdir(parents=True, exist_ok=True)
    logical, physical = build_plan(rows)
    write_tsv(out / "logical_queries.tsv", logical, list(logical[0]))
    write_tsv(out / "physical_queries.tsv", physical, list(physical[0]))
    n_skip = sum(1 for q in logical if q["plan_note"] == "SKIPPED_INVALID_QUERY")
    n_q = sum(1 for q in logical if q["plan_note"] == "QUOTE_STRIPPED")
    print(f"batch {args.batch}: targets {rows['target_id'].nunique()}  logical {len(logical)}  physical {len(physical)}  "
          f"quote-skipped {n_skip}  quote-stripped twins {n_q}")
    print(f"cumulative requests so far (all batches): {cumulative_requests(ret_root)}; per-run cap {args.max_requests}; "
          f"cumulative cap {CUMULATIVE_CAP}")
    if not args.execute:
        print("\nDRY RUN: nothing was sent.")
        return 0
    if not args.contact:
        sys.exit("ERROR: --execute requires --contact")
    raw_root = Path(args.raw_root).expanduser().resolve()
    if ROOT in raw_root.parents or raw_root == ROOT:
        sys.exit(f"ERROR: --raw-root must be outside the repository: {raw_root}")
    raw_root.mkdir(parents=True, exist_ok=True)
    if args.ignore_night_window:
        global NIGHT_START, NIGHT_END
        NIGHT_START, NIGHT_END = dtime(0, 0), dtime(0, 0)

    runner = Runner(out, ret_root, raw_root, args.contact, args.endpoint, args.max_requests)
    statuses, stop_reason, rc = [], "", 0
    try:
        for p in physical:
            st = "SKIPPED_INVALID_QUERY" if p["phys_id"] in args.skip else runner.run_query(p, args.batch)
            statuses.append({"phys_id": p["phys_id"], "route_class": p["route_class"], "targets": p["targets"], "status": st})
    except StopRun as e:
        stop_reason, rc = str(e), 3
        print(f"\nSTOPPED: {stop_reason}", file=sys.stderr)
    except Exception as e:  # never exit without a manifest; the driver treats rc 4 as fatal
        stop_reason, rc = f"UNHANDLED {type(e).__name__}: {e}", 4
        traceback.print_exc()
        print(f"\nSTOPPED: {stop_reason}", file=sys.stderr)
    if statuses:
        write_tsv(out / "physical_query_status.tsv", statuses, list(statuses[0]))
    done_ids = {s["phys_id"] for s in statuses}
    manifest = {"script_version": SCRIPT_VERSION, "script_sha256": sha256_file(__file__), "git_head": git_head(),
                "batch": args.batch, "endpoint": args.endpoint, "mock_run": args.endpoint != ENDPOINT,
                "sru_version": SRU_VERSION, "record_schema": RECORD_SCHEMA, "page_size": PAGE_SIZE, "cap": CAP,
                "min_interval_s": MIN_INTERVAL_S, "retries": 0, "night_window_london": "22:00-06:00",
                "per_run_cap": args.max_requests, "cumulative_cap": CUMULATIVE_CAP, "raw_root": str(raw_root),
                "run_finished_utc": utc_now(), "http_requests_this_invocation": runner.sent,
                "http_requests_cumulative_all_batches": runner.cumulative,
                "physical_queries_in_batch": len(physical), "physical_queries_with_status": len(done_ids),
                "batch_complete": len(done_ids) == len(physical) and not stop_reason,
                "stop_reason": stop_reason, "skipped_by_flag": args.skip, "targets_sha256": TARGETS_SHA}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (out / f"run_manifest_{stamp}.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"\nbatch {args.batch}: {len(done_ids)}/{len(physical)} physical queries have a status; "
          f"requests this invocation {runner.sent}; cumulative {runner.cumulative}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
