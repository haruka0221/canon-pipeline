#!/usr/bin/env python3

import json
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]

BATCH = ROOT / "derived/goodreads_llm_review_batch1_v3.tsv"
POP = ROOT / "derived/ol_dump_population_with_scope.tsv"
OUT = ROOT / "derived/openlibrary_author_identity_cache_v1.jsonl"

batch = pd.read_csv(BATCH, sep="\t", dtype=str).fillna("")
pop = pd.read_csv(POP, sep="\t", dtype=str).fillna("")

x = batch[["ol_work_key"]].merge(
    pop[["work_key", "author_keys"]],
    left_on="ol_work_key",
    right_on="work_key",
    how="left",
)

author_keys = sorted({
    k.strip()
    for s in x["author_keys"]
    for k in s.split(";")
    if k.strip()
})

done = {}

if OUT.exists():
    with OUT.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            done[rec["author_key"]] = rec

print("target author keys:", len(author_keys))
print("already cached:", len(done))

session = requests.Session()
session.headers.update({
    "User-Agent": "canon-pipeline/1.0 literary-research"
})

for i, key in enumerate(author_keys, 1):
    if key in done:
        continue

    print(f"[{i}/{len(author_keys)}] {key}")

    url = f"https://openlibrary.org{key}.json"

    rec = {
        "author_key": key,
        "status": "",
        "name": "",
        "personal_name": "",
        "alternate_names": [],
    }

    for attempt in range(3):
        try:
            r = session.get(url, timeout=30)

            if r.status_code == 200:
                obj = r.json()

                rec["status"] = "OK"
                rec["name"] = obj.get("name") or ""
                rec["personal_name"] = obj.get("personal_name") or ""
                rec["alternate_names"] = obj.get("alternate_names") or []
                break

            rec["status"] = f"HTTP_{r.status_code}"

            if r.status_code == 404:
                break

        except Exception as e:
            rec["status"] = f"ERROR:{type(e).__name__}"

        time.sleep(2 + attempt * 2)

    with OUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    time.sleep(0.2)

print("\noutput:", OUT)
print("finished")
