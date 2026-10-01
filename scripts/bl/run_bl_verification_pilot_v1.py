#!/usr/bin/env python3
"""BL SRU verification pilot v1 runner.

Implements docs/BL_VERIFICATION_PILOT_V1_PROTOCOL.md (frozen at commit b7ad972).

Modes
-----
  (default)            dry run: build the query plan only, send nothing
  --execute            send SRU requests (requires --contact)
  --max-requests N     stop after N HTTP requests (for a smoke test)

Outputs (plan and logs) go to derived/bl_calibration/verification_pilot_v1/.
Raw SRU responses go OUTSIDE the repository (default ~/bl_raw/verification_pilot_v1/).

The run is resumable: completed (query, startRecord) pairs recorded in
physical_requests.tsv are never re-sent.

Interpretation of protocol §4 caps, fixed here before execution:
  * every physical query first requests startRecord=1, maximumRecords=20;
    this page also serves as the A1 count probe;
  * non-A1 routes then page until min(numberOfRecords, 200) records are
    requested; if numberOfRecords > 200 the query is marked CAPPED;
  * A1 pages further only if numberOfRecords <= 200; otherwise it is marked
    SKIPPED_POLICY_CAP after the first page.
"""

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SCRIPT_VERSION = "bl_verification_pilot_v1_runner_1"
FREEZE_COMMIT = "b7ad972"

PROTOCOL = "docs/BL_VERIFICATION_PILOT_V1_PROTOCOL.md"
SAMPLE = "derived/bl_calibration/verification_pilot_v1/bl_verification_pilot_v1_sample.tsv"
ALIASES = "derived/openalex_production/registry_v3/openalex_aliases_v3.tsv"
QUERY_AUTHORS = ("derived/openlibrary_query_author_selection_v1/"
                 "openlibrary_query_author_selection_v1.tsv")
OUT_DIR = "derived/bl_calibration/verification_pilot_v1"

ENDPOINT = "https://eu06.alma.exlibrisgroup.com/view/sru/44BL_MAIN"
SRU_VERSION = "1.2"
RECORD_SCHEMA = "marcxml"
PAGE_SIZE = 20
CAP = 200
MIN_INTERVAL_S = 3.0
RETRY_WAIT_S = 30.0
MAX_RETRIES = 3
TIMEOUT_S = 60

ROUTES_PER_TITLE = ("T1", "T2", "T3", "K1")

LOG_FIELDS = [
    "request_id", "phys_id", "route_class", "start_record", "maximum_records",
    "attempt", "request_started_utc", "elapsed_ms", "http_status", "outcome",
    "number_of_records", "records_in_response", "diagnostic",
    "raw_relpath", "raw_sha256", "url",
]


# ---------------------------------------------------------------- helpers

def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cql_value(s):
    """Backslash-escape backslashes and double quotes; nothing else (§4)."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def signature(cql):
    """Physical dedup key: NFKC, casefold, collapse whitespace."""
    s = unicodedata.normalize("NFKC", cql).casefold()
    return " ".join(s.split())


def surname(author):
    toks = author.split()
    return toks[-1] if toks else ""


def read_tsv(path):
    return pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)


def write_tsv(path, rows, fields):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t",
                           lineterminator="\n", extrasaction="raise")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True)


# ---------------------------------------------------------------- plan

def build_plan():
    sample = read_tsv(SAMPLE).sort_values("sample_id")
    al = read_tsv(ALIASES)
    qa = read_tsv(QUERY_AUTHORS)[["current_ol_work_id", "primary_action",
                                  "query_author_name"]]
    al = al.merge(qa, left_on="alias_source_record_id",
                  right_on="current_ol_work_id", how="left")
    al["query_author_name"] = al["query_author_name"].fillna("")
    al["primary_action"] = al["primary_action"].fillna("")

    expanded, logical = [], []
    qn = 0

    def add(s, route, title_norm, title_raw, alias_ids, author, cql, note=""):
        nonlocal qn
        qn += 1
        logical.append({
            "bl_query_id": f"BLQ{qn:05d}",
            "sample_id": s.sample_id,
            "stratum": s.stratum,
            "target_lane": s.target_lane,
            "project_work_id": s.project_work_id,
            "unresolved_unit_anchor_entity_id": s.unresolved_unit_anchor_entity_id,
            "route": route,
            "title_norm": title_norm,
            "title_raw": title_raw,
            "source_alias_ids": alias_ids,
            "author_name": author,
            "cql": cql,
            "physical_signature": signature(cql) if cql else "",
            "plan_note": note,
        })

    for s in sample.itertuples(index=False):
        if s.target_lane == "resolved_w":
            rows = al[(al.target_lane == "resolved_w") &
                      (al.project_work_id == s.project_work_id)]
        else:
            rows = al[(al.target_lane == "unresolved_source") &
                      (al.unresolved_unit_anchor_entity_id ==
                       s.unresolved_unit_anchor_entity_id)]
        rows = rows.sort_values("alias_id")
        if rows.empty:
            sys.exit(f"ERROR: no aliases for {s.sample_id}")

        for r in rows.itertuples(index=False):
            expanded.append({
                "sample_id": s.sample_id,
                "alias_id": r.alias_id,
                "target_lane": r.target_lane,
                "project_work_id": r.project_work_id,
                "unresolved_unit_anchor_entity_id": r.unresolved_unit_anchor_entity_id,
                "alias_source_record_id": r.alias_source_record_id,
                "alias_value_raw": r.alias_value_raw,
                "alias_value_norm": r.alias_value_norm,
                "alias_quality": r.alias_quality,
                "primary_action": r.primary_action,
                "query_author_name": r.query_author_name,
            })

        # distinct normalized titles, raw form of first alias carrying each
        titles = {}
        for r in rows.itertuples(index=False):
            t = titles.setdefault(r.alias_value_norm,
                                  {"raw": r.alias_value_raw, "ids": [],
                                   "authors": []})
            t["ids"].append(r.alias_id)
            if r.query_author_name and r.query_author_name not in t["authors"]:
                t["authors"].append(r.query_author_name)

        for tnorm, t in titles.items():
            tv = cql_value(t["raw"])
            ids = ";".join(t["ids"])
            # T1: title with each author co-occurring on the same alias rows
            if t["authors"]:
                for a in t["authors"]:
                    add(s, "T1", tnorm, t["raw"], ids, a,
                        f'alma.title == "{tv}" and alma.creator all "{cql_value(a)}"')
            else:
                add(s, "T1", tnorm, t["raw"], ids, "", "", "SKIPPED_NO_AUTHOR")
            add(s, "T2", tnorm, t["raw"], ids, "", f'alma.title == "{tv}"')
            add(s, "T3", tnorm, t["raw"], ids, "", f'alma.title = "{tv}"')
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

    # physical dedup
    physical, by_sig = [], {}
    for q in logical:
        if not q["cql"]:
            q["phys_id"] = ""
            continue
        sig = q["physical_signature"]
        if sig not in by_sig:
            pid = f"BLP{len(physical) + 1:04d}"
            by_sig[sig] = pid
            physical.append({
                "phys_id": pid,
                "physical_signature": sig,
                "cql_sent": q["cql"],
                "route_class": "A1" if q["route"] == "A1" else "TITLE_OR_KEYWORD",
                "n_logical": 0,
            })
        q["phys_id"] = by_sig[sig]
        physical[int(by_sig[sig][3:]) - 1]["n_logical"] += 1

    return expanded, logical, physical


def write_plan(out, expanded, logical, physical):
    write_tsv(out / "expanded_aliases.tsv", expanded, list(expanded[0]))
    write_tsv(out / "logical_queries.tsv", logical, list(logical[0]))
    write_tsv(out / "physical_queries.tsv", physical, list(physical[0]))


def summarize_plan(logical, physical):
    from collections import Counter
    c = Counter(q["route"] for q in logical if q["cql"])
    skipped = sum(1 for q in logical if not q["cql"])
    print(f"logical queries: {len(logical)} (skipped: {skipped})")
    for r in ("T1", "T2", "T3", "K1", "A1"):
        print(f"  {r}: {c.get(r, 0)}")
    print(f"physical queries: {len(physical)} "
          f"(A1: {sum(p['route_class'] == 'A1' for p in physical)})")
    print(f"minimum HTTP requests (first pages only): {len(physical)}; "
          f"at {MIN_INTERVAL_S:.0f}s interval >= "
          f"{len(physical) * MIN_INTERVAL_S / 60:.1f} min")


# ---------------------------------------------------------------- execution

def check_freeze():
    r = git("merge-base", "--is-ancestor", FREEZE_COMMIT, "HEAD")
    if r.returncode != 0:
        sys.exit(f"ERROR: freeze commit {FREEZE_COMMIT} is not an ancestor of HEAD")
    r = git("diff", "--quiet", FREEZE_COMMIT, "--", PROTOCOL, SAMPLE)
    if r.returncode != 0:
        sys.exit("ERROR: protocol or sample differs from the freeze commit")
    return git("rev-parse", "HEAD").stdout.strip()


def local(tag):
    return tag.rsplit("}", 1)[-1]


def parse_sru(body):
    """Return (numberOfRecords or None, records_in_response, diagnostic text)."""
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


class Runner:
    def __init__(self, out, raw_root, contact, max_requests):
        self.out = out
        self.raw_root = raw_root
        self.ua = (f"canon-pipeline BL verification pilot v1 "
                   f"(academic research; contact: {contact})")
        self.max_requests = max_requests
        self.sent = 0
        self.last_start = 0.0
        self.log_path = out / "physical_requests.tsv"
        self.done = {}      # (phys_id, start) -> number_of_records
        self.req_n = 0
        if self.log_path.exists():
            for r in read_tsv(self.log_path).itertuples(index=False):
                self.req_n = max(self.req_n, int(r.request_id[3:]))
                if r.outcome in ("COMPLETE", "SRU_DIAGNOSTIC", "FAILED_FINAL",
                                 "FAILED_PARSE"):
                    self.done[(r.phys_id, int(r.start_record))] = (
                        r.outcome, r.number_of_records)
        else:
            with open(self.log_path, "w", encoding="utf-8", newline="") as f:
                csv.writer(f, delimiter="\t", lineterminator="\n").writerow(LOG_FIELDS)

    def log(self, row):
        with open(self.log_path, "a", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=LOG_FIELDS, delimiter="\t",
                           lineterminator="\n").writerow(row)

    def budget_left(self):
        return self.max_requests is None or self.sent < self.max_requests

    def request(self, p, start):
        """One page with bounded retry. Returns (outcome, number_of_records)."""
        params = {
            "version": SRU_VERSION, "operation": "searchRetrieve",
            "query": p["cql_sent"], "recordSchema": RECORD_SCHEMA,
            "maximumRecords": str(PAGE_SIZE), "startRecord": str(start),
        }
        url = ENDPOINT + "?" + urllib.parse.urlencode(params,
                                                     quote_via=urllib.parse.quote)
        for attempt in range(1, MAX_RETRIES + 2):
            if not self.budget_left():
                return "BUDGET", None
            wait = self.last_start + MIN_INTERVAL_S - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.last_start = time.monotonic()
            self.sent += 1
            self.req_n += 1
            rid = f"BLR{self.req_n:06d}"
            started = utc_now()
            t0 = time.monotonic()
            status, body, transient, err = "", b"", False, ""
            try:
                req = urllib.request.Request(url, headers={"User-Agent": self.ua})
                with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                    status, body = str(resp.status), resp.read()
            except urllib.error.HTTPError as e:
                status, body = str(e.code), e.read() or b""
                transient = e.code == 429 or e.code >= 500
                err = f"HTTP {e.code}"
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                transient, err = True, f"{type(e).__name__}: {e}"
            elapsed = int((time.monotonic() - t0) * 1000)

            relpath, digest = "", ""
            if body:
                relpath = f"{p['phys_id']}/{p['phys_id']}_s{start:04d}_{rid}.xml"
                path = self.raw_root / relpath
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
                digest = sha256_file(path)

            row = {"request_id": rid, "phys_id": p["phys_id"],
                   "route_class": p["route_class"], "start_record": start,
                   "maximum_records": PAGE_SIZE, "attempt": attempt,
                   "request_started_utc": started, "elapsed_ms": elapsed,
                   "http_status": status, "number_of_records": "",
                   "records_in_response": "", "diagnostic": err,
                   "raw_relpath": relpath, "raw_sha256": digest, "url": url}

            if err and transient:
                final = attempt > MAX_RETRIES
                row["outcome"] = "FAILED_FINAL" if final else "RETRY"
                self.log(row)
                if final:
                    return "FAILED_FINAL", None
                time.sleep(RETRY_WAIT_S)
                continue
            if err:
                row["outcome"] = "FAILED_FINAL"
                self.log(row)
                return "FAILED_FINAL", None
            try:
                n, recs, diag = parse_sru(body)
            except ET.ParseError as e:
                row["outcome"], row["diagnostic"] = "FAILED_PARSE", f"ParseError: {e}"
                self.log(row)
                return "FAILED_PARSE", None
            row["number_of_records"] = "" if n is None else n
            row["records_in_response"] = recs
            row["diagnostic"] = diag
            row["outcome"] = "SRU_DIAGNOSTIC" if (diag and n is None) else "COMPLETE"
            self.log(row)
            return row["outcome"], n
        return "FAILED_FINAL", None

    def run_query(self, p):
        key1 = (p["phys_id"], 1)
        if key1 in self.done:
            outcome, n = self.done[key1]
            n = int(n) if str(n).strip() else None
        else:
            outcome, n = self.request(p, 1)
        if outcome != "COMPLETE" or n is None:
            return outcome
        if p["route_class"] == "A1" and n > CAP:
            return "SKIPPED_POLICY_CAP"
        target = min(n, CAP)
        for start in range(1 + PAGE_SIZE, target + 1, PAGE_SIZE):
            if (p["phys_id"], start) in self.done:
                continue
            o, _ = self.request(p, start)
            if o == "BUDGET":
                return "INCOMPLETE_BUDGET"
            if o != "COMPLETE":
                return f"INCOMPLETE_{o}"
        return "CAPPED" if n > CAP else "COMPLETE"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--contact", help="contact e-mail for the User-Agent")
    ap.add_argument("--max-requests", type=int, default=None)
    ap.add_argument("--raw-root", default=str(Path.home() / "bl_raw" /
                                              "verification_pilot_v1"))
    args = ap.parse_args()

    out = Path(OUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    expanded, logical, physical = build_plan()
    write_plan(out, expanded, logical, physical)
    summarize_plan(logical, physical)

    if not args.execute:
        print("\nDRY RUN: nothing was sent. Review logical_queries.tsv and "
              "physical_queries.tsv, then rerun with --execute.")
        return
    if not args.contact:
        sys.exit("ERROR: --execute requires --contact")

    head = check_freeze()
    raw_root = Path(args.raw_root).expanduser().resolve()
    raw_root.mkdir(parents=True, exist_ok=True)
    runner = Runner(out, raw_root, args.contact, args.max_requests)

    statuses = []
    for p in physical:
        st = runner.run_query(p) if runner.budget_left() else "NOT_STARTED_BUDGET"
        if st == "BUDGET":
            st = "NOT_STARTED_BUDGET"
        statuses.append({"phys_id": p["phys_id"], "route_class": p["route_class"],
                         "status": st})
        print(f"{p['phys_id']}  {st:<22} {p['cql_sent']}")
    write_tsv(out / "physical_query_status.tsv", statuses, list(statuses[0]))

    manifest = {
        "script_version": SCRIPT_VERSION,
        "script_sha256": sha256_file(__file__),
        "git_head": head,
        "freeze_commit": FREEZE_COMMIT,
        "endpoint": ENDPOINT,
        "sru_version": SRU_VERSION,
        "record_schema": RECORD_SCHEMA,
        "page_size": PAGE_SIZE, "cap": CAP,
        "min_interval_s": MIN_INTERVAL_S,
        "retry_wait_s": RETRY_WAIT_S, "max_retries": MAX_RETRIES,
        "raw_root": str(raw_root),
        "run_finished_utc": utc_now(),
        "http_requests_this_invocation": runner.sent,
        "inputs": {k: sha256_file(v) for k, v in
                   {"protocol": PROTOCOL, "sample": SAMPLE,
                    "aliases": ALIASES, "query_authors": QUERY_AUTHORS}.items()},
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (out / f"run_manifest_{stamp}.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                           encoding="utf-8")
    print(f"\nHTTP requests sent this invocation: {runner.sent}")


if __name__ == "__main__":
    main()
