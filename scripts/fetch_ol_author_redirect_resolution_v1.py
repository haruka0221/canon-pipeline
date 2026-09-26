#!/usr/bin/env python3

import json
import time
from collections import Counter
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]

BASE = ROOT / "derived/openlibrary_author_identity_cache_v1.jsonl"
OUT = ROOT / "derived/openlibrary_author_redirect_resolution_v1.jsonl"

empty_keys = []

with BASE.open(encoding="utf-8") as f:
    for line in f:
        rec = json.loads(line)

        empty_identity = (
            not (rec.get("name") or "").strip()
            and not (rec.get("personal_name") or "").strip()
            and not (rec.get("alternate_names") or [])
        )

        if rec.get("status") == "OK" and empty_identity:
            empty_keys.append(rec["author_key"])

assert len(empty_keys) == 10

session = requests.Session()
session.headers.update({
    "User-Agent": "canon-pipeline/1.0 literary-research"
})

rows = []

for i, source_key in enumerate(sorted(empty_keys), 1):
    print(f"[{i}/{len(empty_keys)}] {source_key}")

    current = source_key
    chain = []
    seen = set()

    final = {
        "source_author_key": source_key,
        "redirect_chain": [],
        "final_author_key": "",
        "final_type": "",
        "name": "",
        "personal_name": "",
        "alternate_names": [],
        "resolution_status": "",
    }

    for depth in range(10):
        if current in seen:
            final["resolution_status"] = "REDIRECT_LOOP"
            break

        seen.add(current)

        r = session.get(
            f"https://openlibrary.org{current}.json",
            timeout=30,
        )

        if r.status_code != 200:
            final["resolution_status"] = f"HTTP_{r.status_code}"
            break

        obj = r.json()

        typ = (
            obj.get("type", {}).get("key", "")
            if isinstance(obj.get("type"), dict)
            else str(obj.get("type") or "")
        )

        chain.append(current)

        if typ == "/type/author":
            final["final_author_key"] = current
            final["final_type"] = typ
            final["name"] = obj.get("name") or ""
            final["personal_name"] = obj.get("personal_name") or ""
            final["alternate_names"] = obj.get("alternate_names") or []
            final["resolution_status"] = "REDIRECT_RESOLVED_AUTHOR"
            break

        if typ != "/type/redirect":
            final["final_author_key"] = current
            final["final_type"] = typ
            final["resolution_status"] = "REDIRECT_TARGET_OTHER"
            break

        nxt = obj.get("location") or ""

        if not nxt:
            final["resolution_status"] = "REDIRECT_WITHOUT_LOCATION"
            break

        if not nxt.startswith("/"):
            nxt = "/" + nxt

        current = nxt
        time.sleep(0.1)

    else:
        final["resolution_status"] = "MAX_REDIRECT_DEPTH"

    final["redirect_chain"] = chain
    rows.append(final)

with OUT.open("w", encoding="utf-8") as f:
    for rec in rows:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

print("\n=== STATUS ===")
print(Counter(r["resolution_status"] for r in rows))

print("\n=== RESULTS ===")
for r in rows:
    print(
        r["source_author_key"],
        "=>",
        r["final_author_key"],
        "|",
        r["name"],
        "| chain:",
        " -> ".join(r["redirect_chain"]),
    )

assert len(rows) == 10
assert all(
    r["resolution_status"] == "REDIRECT_RESOLVED_AUTHOR"
    for r in rows
)

print("\noutput:", OUT)
