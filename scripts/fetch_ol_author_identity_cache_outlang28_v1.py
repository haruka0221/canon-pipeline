#!/usr/bin/env python3

import json
import re
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]

TRANSFER = ROOT / "derived/goodreads_outlang_singleton_full28_v1.tsv"
RES = ROOT / "derived/goodreads_resolution_status_v4.tsv"
BASE_CACHE = ROOT / "derived/openlibrary_author_identity_cache_v1.jsonl"
OUT = ROOT / "derived/openlibrary_author_identity_cache_outlang28_v1.jsonl"

transfer = pd.read_csv(
    TRANSFER,
    sep="\t",
    dtype=str,
).fillna("")

res = pd.read_csv(
    RES,
    sep="\t",
    dtype=str,
).fillna("")

x = transfer[["work_key"]].merge(
    res[["work_key", "author_keys"]],
    on="work_key",
    how="left",
    validate="one_to_one",
)

target_keys = sorted({
    key.strip()
    for s in x["author_keys"]
    for key in re.split(r"[;|]", s)
    if key.strip()
})

base = set()

with BASE_CACHE.open(encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        base.add(rec["author_key"])

needed = sorted(set(target_keys) - base)

done = {}

if OUT.exists():
    with OUT.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            done[rec["author_key"]] = rec

print("28-case author keys:", len(target_keys))
print("already in base cache:", len(set(target_keys) & base))
print("supplemental target keys:", len(needed))
print("already cached:", len(done))

assert len(target_keys) == 30
assert len(needed) == 25
assert set(done).issubset(set(needed))

session = requests.Session()
session.headers.update({
    "User-Agent": "canon-pipeline/1.0 literary-research"
})

for i, key in enumerate(needed, 1):
    if key in done:
        continue

    print(f"[{i}/{len(needed)}] {key}")

    rec = {
        "author_key": key,
        "status": "",
        "name": "",
        "personal_name": "",
        "alternate_names": [],
    }

    url = f"https://openlibrary.org{key}.json"

    for attempt in range(3):
        try:
            r = session.get(url, timeout=30)

            if r.status_code == 200:
                obj = r.json()
                rec["status"] = "OK"
                rec["name"] = obj.get("name") or ""
                rec["personal_name"] = obj.get("personal_name") or ""
                rec["alternate_names"] = (
                    obj.get("alternate_names") or []
                )
                break

            rec["status"] = f"HTTP_{r.status_code}"

            if r.status_code == 404:
                break

        except Exception as e:
            rec["status"] = f"ERROR:{type(e).__name__}"

        time.sleep(2 + attempt * 2)

    with OUT.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(rec, ensure_ascii=False) + "\n"
        )

    time.sleep(0.2)

print("\noutput:", OUT)
print("finished")
