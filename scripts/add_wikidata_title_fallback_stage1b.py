#!/usr/bin/env python3

import json
import re
import time
from pathlib import Path

import requests

SRC = Path(
    "derived/benchmark/wikidata_candidates_stage1_130.jsonl"
)
OUT = Path(
    "derived/benchmark/wikidata_candidates_stage1b_130.jsonl"
)

API = "https://www.wikidata.org/w/api.php"

session = requests.Session()
session.headers.update({
    "User-Agent": "canon-pipeline-title-fallback/1.0"
})


def search(title, limit=10):
    for attempt in range(6):
        r = session.get(
            API,
            params={
                "action": "wbsearchentities",
                "search": title,
                "language": "en",
                "uselang": "en",
                "type": "item",
                "limit": limit,
                "format": "json",
            },
            timeout=30,
        )

        if r.status_code == 429:
            wait = 20 * (attempt + 1)
            print(f"      429; waiting {wait}s")
            time.sleep(wait)
            continue

        r.raise_for_status()

        time.sleep(3)

        return [
            x["id"]
            for x in r.json().get("search", [])
        ]

    raise RuntimeError("Wikidata search repeatedly failed")


def variants(title):
    vals = [title]

    cleaned = re.sub(
        r"^textplus\s*[-:]\s*",
        "",
        title,
        flags=re.I,
    ).strip()

    if cleaned != title:
        vals.append(cleaned)

    # Conservative shorter variants only as fallback.
    for sep in [";", ":"]:
        if sep in cleaned:
            short = cleaned.split(sep, 1)[0].strip()
            if short:
                vals.append(short)

    return list(dict.fromkeys(vals))


rows = []

with open(SRC, encoding="utf-8") as f:
    for line in f:
        if line.strip():
            rows.append(json.loads(line))


for i, row in enumerate(rows, 1):

    if row["exact_count"] != 0:
        continue

    title = row["title"]

    print(
        f"[{i:3d}/130] {title}"
    )

    added = []

    for query in variants(title):
        hits = search(query, 10)

        print(
            f"    search={query!r} "
            f"hits={len(hits)}"
        )

        for qid in hits:
            if (
                qid not in row["candidate_qids"]
                and qid not in added
            ):
                added.append(qid)

    row["candidate_qids"].extend(added)

    row["route"] = (
        str(row["route"])
        + "+title_search"
    )

    row["title_search_added"] = added

    print(
        f"    added={len(added)} "
        f"total={len(row['candidate_qids'])}"
    )

    # checkpoint after every target
    with open(OUT, "w", encoding="utf-8") as f:
        for x in rows:
            f.write(
                json.dumps(
                    x,
                    ensure_ascii=False
                ) + "\n"
            )


# If there were no exact=0 rows for some reason,
# still ensure output exists.
if not OUT.exists():
    with open(OUT, "w", encoding="utf-8") as f:
        for x in rows:
            f.write(
                json.dumps(
                    x,
                    ensure_ascii=False
                ) + "\n"
            )

print()
print("Saved:", OUT)
