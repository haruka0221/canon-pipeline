#!/usr/bin/env python3
"""BL SRU calibration v2 runner (dry-run by default; nothing is sent without --execute).

Reuses the v1 request/parse code (run_bl_verification_pilot_v1.py) with the
v2 protocol's safety rules:

  * routes T2, K1, A1 only (T1/T3 dropped); A1 count-probe first, full A1
    only if count <= CAP (200); title/keyword routes paged up to CAP
  * sends only while Europe/London local time is in the night window
    [NIGHT_START, NIGHT_END); checked before EVERY request
  * >= MIN_INTERVAL_S after the previous RESPONSE was received
  * NO retries: HTTP 429, HTTP >= 500, connection error, timeout, SRU
    diagnostic, or XML parse error -> the run STOPS (exit 3); a human restarts
  * cumulative cap CUMULATIVE_CAP (counted from physical_requests.tsv across
    invocations) and per-invocation cap --max-requests (default 2500)
  * resumable: completed (phys_id, startRecord) pages are never re-sent
  * raw XML goes to --raw-root, which MUST be outside the repository
  * --phase early  : only queries of the 30 S1 early-check targets
    --phase rest   : all other queries (refuses to start unless the early
                     phase is complete and --early-check-ack is given)

Inputs (frozen, sha256 verified):
  derived/bl_calibration/calibration_v2/sample_targets_v1.tsv
  derived/bl_calibration/calibration_v2/sample_aliases_v1.tsv
Outputs (public tree; no BL record content, only the plan and the request log):
  derived/bl_calibration/calibration_v2/retrieval/{logical_queries,physical_queries,
      physical_requests,physical_query_status}.tsv, run_manifest_*.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, time as dtime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

SCRIPT_VERSION = "run_bl_calibration_v2_v1"
ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "derived" / "bl_calibration" / "calibration_v2"
SAMPLE = DIR / "sample_targets_v1.tsv"
ALIASES = DIR / "sample_aliases_v1.tsv"
OUT = DIR / "retrieval"
EXPECTED_SHA = {
    "sample_targets_v1.tsv": "71553b94cb2536a98fec22c2c0eb27fa7b48fc3691ce1a6ddb0c2dc2314f3c27",
    "sample_aliases_v1.tsv": "a8a88e20185e7a7f5ff4861b6d734653a989a30c201be5900b4b19699832e5f5",
}

ENDPOINT = "https://eu06.alma.exlibrisgroup.com/view/sru/44BL_MAIN"
SRU_VERSION = "1.2"
RECORD_SCHEMA = "marcxml"
PAGE_SIZE = 20
CAP = 200
MIN_INTERVAL_S = 3.0          # after the previous response
TIMEOUT_S = 60
CUMULATIVE_CAP = 4000
DEFAULT_PER_RUN_CAP = 2500
LONDON = ZoneInfo("Europe/London")
NIGHT_START, NIGHT_END = dtime(22, 0), dtime(6, 0)

LOG_FIELDS = ["request_id", "phys_id", "route_class", "start_record", "maximum_records",
              "request_started_utc", "request_started_london", "elapsed_ms", "http_status",
              "outcome", "number_of_records", "records_in_response", "diagnostic",
              "raw_relpath", "raw_sha256", "url"]
STOP_OUTCOMES = ("STOP_HTTP", "STOP_NETWORK", "STOP_DIAGNOSTIC", "STOP_PARSE")


# ---------------------------------------------------------------- helpers (v1)
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
    s = unicodedata.normalize("NFKC", cql).casefold()
    return " ".join(s.split())


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


# ---------------------------------------------------------------- plan (v2)
def build_plan():
    sample = read_tsv(SAMPLE).sort_values("sample_id")
    al = read_tsv(ALIASES)
    logical, qn = [], 0

    def add(s, route, title_norm, title_raw, alias_ids, author, cql, note=""):
        nonlocal qn
        qn += 1
        logical.append({
            "bl_query_id": f"BLQ2_{qn:05d}", "sample_id": s.sample_id, "stratum": s.stratum,
            "target_lane": s.target_lane, "target_id": s.target_id,
            "s1_early_order": s.s1_early_order, "route": route,
            "title_norm": title_norm, "title_raw": title_raw, "source_alias_ids": alias_ids,
            "author_name": author, "cql": cql,
            "physical_signature": signature(cql) if cql else "", "plan_note": note,
        })

    for s in sample.itertuples(index=False):
        rows = al[al.sample_id == s.sample_id].sort_values("ol_entity_id")
        if rows.empty:
            sys.exit(f"ERROR: no aliases for {s.sample_id}")
        titles = {}
        for r in rows.itertuples(index=False):
            t = titles.setdefault(signature(r.source_title),
                                  {"raw": r.source_title, "ids": [], "authors": []})
            t["ids"].append(r.ol_entity_id)
            if r.query_author_name and r.query_author_name not in t["authors"]:
                t["authors"].append(r.query_author_name)
        for tnorm, t in titles.items():
            tv, ids = cql_value(t["raw"]), ";".join(t["ids"])
            add(s, "T2", tnorm, t["raw"], ids, "", f'alma.title == "{tv}"')
            if t["authors"]:
                for a in t["authors"]:
                    add(s, "K1", tnorm, t["raw"], ids, a,
                        f'alma.all_for_ui all "{cql_value(t["raw"] + " " + surname(a))}"')
            else:
                add(s, "K1", tnorm, t["raw"], ids, "", "", "SKIPPED_NO_AUTHOR")
        authors = []
        for r in rows.itertuples(index=False):
            if r.query_author_name and r.query_author_name not in authors:
                authors.append(r.query_author_name)
        for a in authors:
            add(s, "A1", "", "", "", a, f'alma.creator all "{cql_value(a)}"')
        if not authors:
            add(s, "A1", "", "", "", "", "", "SKIPPED_NO_AUTHOR")

    physical, by_sig = [], {}
    for q in logical:
        if not q["cql"]:
            q["phys_id"] = ""
            continue
        sig = q["physical_signature"]
        if sig not in by_sig:
            by_sig[sig] = f"BLP2_{len(physical) + 1:04d}"
            physical.append({"phys_id": by_sig[sig], "physical_signature": sig,
                             "cql_sent": q["cql"],
                             "route_class": "A1" if q["route"] == "A1" else "TITLE_OR_KEYWORD",
                             "n_logical": 0, "early": False, "targets": set()})
        q["phys_id"] = by_sig[sig]
        p = physical[int(by_sig[sig][5:]) - 1]
        p["n_logical"] += 1
        p["targets"].add(q["sample_id"])
        if int(q["s1_early_order"] or 0) > 0:
            p["early"] = True
    for p in physical:
        p["targets"] = ";".join(sorted(p["targets"]))
    return logical, physical


# ---------------------------------------------------------------- runner (v2)
class StopRun(Exception):
    pass


class Runner:
    def __init__(self, out, raw_root, contact, endpoint, per_run_cap):
        self.out, self.raw_root, self.endpoint = out, raw_root, endpoint
        self.ua = f"canon-pipeline BL calibration v2 (academic research; contact: {contact})"
        self.per_run_cap, self.sent, self.last_response = per_run_cap, 0, 0.0
        self.log_path = out / "physical_requests.tsv"
        self.done, self.req_n, self.cumulative = {}, 0, 0
        if self.log_path.exists():
            for r in read_tsv(self.log_path).itertuples(index=False):
                self.req_n = max(self.req_n, int(r.request_id[5:]))
                self.cumulative += 1
                if r.outcome == "COMPLETE":
                    self.done[(r.phys_id, int(r.start_record))] = r.number_of_records
        else:
            with open(self.log_path, "w", encoding="utf-8", newline="") as f:
                csv.writer(f, delimiter="\t", lineterminator="\n").writerow(LOG_FIELDS)

    def log(self, row):
        with open(self.log_path, "a", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=LOG_FIELDS, delimiter="\t",
                           lineterminator="\n").writerow(row)

    def guard(self):
        if self.cumulative >= CUMULATIVE_CAP:
            raise StopRun(f"cumulative cap {CUMULATIVE_CAP} reached")
        if self.sent >= self.per_run_cap:
            raise StopRun(f"per-run cap {self.per_run_cap} reached")
        now = datetime.now(LONDON)
        if not in_night_window(now):
            raise StopRun(f"outside night window, London time {now:%H:%M}")

    def request(self, p, start):
        self.guard()
        params = {"version": SRU_VERSION, "operation": "searchRetrieve",
                  "query": p["cql_sent"], "recordSchema": RECORD_SCHEMA,
                  "maximumRecords": str(PAGE_SIZE), "startRecord": str(start)}
        url = self.endpoint + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        wait = self.last_response + MIN_INTERVAL_S - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self.sent += 1
        self.cumulative += 1
        self.req_n += 1
        rid = f"BLR2_{self.req_n:06d}"
        started_utc, started_ldn = utc_now(), datetime.now(LONDON).isoformat()
        t0 = time.monotonic()
        status, body, err, outcome = "", b"", "", ""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self.ua})
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                status, body = str(resp.status), resp.read()
        except urllib.error.HTTPError as e:
            status, body, err, outcome = str(e.code), e.read() or b"", f"HTTP {e.code}", "STOP_HTTP"
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            err, outcome = f"{type(e).__name__}: {e}", "STOP_NETWORK"
        self.last_response = time.monotonic()
        elapsed = int((self.last_response - t0) * 1000)

        relpath, digest = "", ""
        if body:
            relpath = f"{p['phys_id']}/{p['phys_id']}_s{start:04d}_{rid}.xml"
            path = self.raw_root / relpath
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            digest = sha256_file(path)
        row = {"request_id": rid, "phys_id": p["phys_id"], "route_class": p["route_class"],
               "start_record": start, "maximum_records": PAGE_SIZE,
               "request_started_utc": started_utc, "request_started_london": started_ldn,
               "elapsed_ms": elapsed, "http_status": status, "number_of_records": "",
               "records_in_response": "", "diagnostic": err, "raw_relpath": relpath,
               "raw_sha256": digest, "url": url}
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
        row["number_of_records"] = "" if n is None else n
        row["records_in_response"], row["diagnostic"] = recs, diag
        if diag or n is None:
            row["outcome"] = "STOP_DIAGNOSTIC"
            self.log(row)
            raise StopRun(f"STOP_DIAGNOSTIC: {diag}")
        row["outcome"] = "COMPLETE"
        self.log(row)
        self.done[(p["phys_id"], start)] = n
        return n

    def run_query(self, p):
        key1 = (p["phys_id"], 1)
        n = int(self.done[key1]) if key1 in self.done else self.request(p, 1)
        if p["route_class"] == "A1" and n > CAP:
            return "SKIPPED_POLICY_CAP"
        for start in range(1 + PAGE_SIZE, min(n, CAP) + 1, PAGE_SIZE):
            if (p["phys_id"], start) not in self.done:
                self.request(p, start)
        return "CAPPED" if n > CAP else "COMPLETE"


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--execute", action="store_true", help="actually send requests")
    ap.add_argument("--phase", choices=["early", "rest"], required=True)
    ap.add_argument("--early-check-ack", action="store_true",
                    help="rest phase: human has reviewed the early-30 request count")
    ap.add_argument("--contact", help="contact e-mail for the User-Agent")
    ap.add_argument("--max-requests", type=int, default=DEFAULT_PER_RUN_CAP)
    ap.add_argument("--raw-root", default=str(Path.home() / "bl_raw" / "calibration_v2"))
    ap.add_argument("--out-dir", default=str(OUT),
                    help="log/plan directory; must be non-default for a mock run")
    ap.add_argument("--endpoint", default=ENDPOINT,
                    help="override ONLY for the mock server test")
    ap.add_argument("--skip", nargs="*", default=[],
                    help="phys_ids the BL rejected as invalid CQL; recorded as SKIPPED_INVALID_QUERY, never sent")
    ap.add_argument("--ignore-night-window", action="store_true",
                    help="allowed ONLY with a non-default --endpoint (mock server)")
    args = ap.parse_args()

    for p in (SAMPLE, ALIASES):
        got = sha256_file(p)
        if got != EXPECTED_SHA[p.name]:
            sys.exit(f"ERROR: {p.name} sha256 {got} != frozen value")
    out = Path(args.out_dir).expanduser().resolve()
    if args.endpoint != ENDPOINT and out == OUT.resolve():
        sys.exit("ERROR: a mock --endpoint needs a non-default --out-dir")
    if args.endpoint == ENDPOINT and out != OUT.resolve():
        sys.exit("ERROR: the real endpoint writes only to the default --out-dir")
    out.mkdir(parents=True, exist_ok=True)
    logical, physical = build_plan()
    write_tsv(out / "logical_queries.tsv", logical, list(logical[0]))
    write_tsv(out / "physical_queries.tsv",
              [{k: v for k, v in p.items()} for p in physical], list(physical[0]))
    todo = [p for p in physical if p["early"] == (args.phase == "early")]
    n_early = sum(1 for p in physical if p["early"])
    print(f"logical {len(logical)}  physical {len(physical)}  early-phase physical {n_early}")
    print(f"phase {args.phase}: {len(todo)} physical queries; "
          f"per-run cap {args.max_requests}, cumulative cap {CUMULATIVE_CAP}")

    if not args.execute:
        print("\nDRY RUN: nothing was sent.")
        return 0
    if not args.contact:
        sys.exit("ERROR: --execute requires --contact")
    if args.ignore_night_window and args.endpoint == ENDPOINT:
        sys.exit("ERROR: --ignore-night-window is only allowed with a mock --endpoint")
    raw_root = Path(args.raw_root).expanduser().resolve()
    if ROOT in raw_root.parents or raw_root == ROOT:
        sys.exit(f"ERROR: --raw-root must be outside the repository: {raw_root}")
    raw_root.mkdir(parents=True, exist_ok=True)
    if args.phase == "rest":
        status_path = out / "physical_query_status_early.tsv"
        if not status_path.exists() or not args.early_check_ack:
            sys.exit("ERROR: rest phase needs a completed early phase and --early-check-ack")
    if args.ignore_night_window:
        global NIGHT_START, NIGHT_END
        NIGHT_START, NIGHT_END = dtime(0, 0), dtime(0, 0)

    runner = Runner(out, raw_root, args.contact, args.endpoint, args.max_requests)
    statuses, stop_reason, rc = [], "", 0
    try:
        for p in todo:
            st = "SKIPPED_INVALID_QUERY" if p["phys_id"] in args.skip else runner.run_query(p)
            statuses.append({"phys_id": p["phys_id"], "route_class": p["route_class"],
                             "targets": p["targets"], "status": st})
            print(f"{p['phys_id']}  {st:<20} {p['cql_sent']}")
    except StopRun as e:
        stop_reason, rc = str(e), 3
        print(f"\nSTOPPED: {stop_reason}", file=sys.stderr)
    if statuses:
        write_tsv(out / f"physical_query_status_{args.phase}.tsv", statuses, list(statuses[0]))
    manifest = {
        "script_version": SCRIPT_VERSION, "script_sha256": sha256_file(__file__),
        "git_head": git_head(), "phase": args.phase, "endpoint": args.endpoint,
        "mock_run": args.endpoint != ENDPOINT, "sru_version": SRU_VERSION,
        "record_schema": RECORD_SCHEMA, "page_size": PAGE_SIZE, "cap": CAP,
        "min_interval_s": MIN_INTERVAL_S, "retries": 0, "cumulative_cap": CUMULATIVE_CAP,
        "per_run_cap": args.max_requests, "night_window_london": "22:00-06:00",
        "raw_root": str(raw_root), "run_finished_utc": utc_now(),
        "http_requests_this_invocation": runner.sent,
        "http_requests_cumulative": runner.cumulative,
        "stop_reason": stop_reason, "skipped_invalid_query": args.skip, "inputs": {p.name: sha256_file(p) for p in (SAMPLE, ALIASES)},
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (out / f"run_manifest_{stamp}.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"\nHTTP requests this invocation: {runner.sent}; cumulative: {runner.cumulative}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
