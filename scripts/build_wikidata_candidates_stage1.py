#!/usr/bin/env python3

import json
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]

BENCH = ROOT / "derived/benchmark/full_eval_130items_worklevel_v2.tsv"
LUNA = ROOT / "derived/benchmark/wikidata_luna_enhanced_light_eval_130.tsv"

OUT = ROOT / "derived/benchmark/wikidata_candidates_stage1_130.jsonl"

SPARQL = "https://query.wikidata.org/sparql"
HEADERS = {
    "User-Agent": "canon-pipeline-candidate-stage1/1.0"
}

session = requests.Session()
session.headers.update(HEADERS)

author_cache = {}


def norm(s):
    s = str(s or "").strip()

    s = re.sub(
        r"^textplus\s*[-:]\s*",
        "",
        s,
        flags=re.I,
    )

    s = unicodedata.normalize("NFKD", s).lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)

    return s.strip()


def score(a, b):
    return SequenceMatcher(
        None,
        norm(a),
        norm(b),
    ).ratio()


def get_author_items(author_qid):
    if author_qid in author_cache:
        return author_cache[author_qid]

    q = f"""
SELECT ?item ?label ?statedTitle ?parent WHERE {{
  ?item wdt:P50 wd:{author_qid}.

  OPTIONAL {{
    ?item rdfs:label ?label.
    FILTER(LANG(?label) = "en")
  }}

  OPTIONAL {{
    ?item wdt:P1476 ?statedTitle.
    FILTER(
      LANG(?statedTitle) = "en"
      || LANG(?statedTitle) = ""
    )
  }}

  OPTIONAL {{
    ?item wdt:P629 ?parent.
  }}
}}
"""

    for attempt in range(6):
        try:
            r = session.get(
                SPARQL,
                params={
                    "query": q,
                    "format": "json",
                },
                timeout=120,
            )

            if r.status_code == 429:
                wait = 20 * (attempt + 1)
                print(f"      WDQS 429; waiting {wait}s")
                time.sleep(wait)
                continue

            r.raise_for_status()

            rows = r.json()["results"]["bindings"]
            break

        except Exception as e:
            if attempt == 5:
                print("      FAILED:", e)
                return None

            wait = 5 * (attempt + 1)
            time.sleep(wait)

    merged = {}

    for x in rows:
        qid = x["item"]["value"].split("/")[-1]

        if qid not in merged:
            merged[qid] = {
                "qid": qid,
                "texts": [],
                "parents": [],
            }

        if "label" in x:
            t = x["label"]["value"]
            if t not in merged[qid]["texts"]:
                merged[qid]["texts"].append(t)

        if "statedTitle" in x:
            t = x["statedTitle"]["value"]
            if t not in merged[qid]["texts"]:
                merged[qid]["texts"].append(t)

        if "parent" in x:
            p = x["parent"]["value"].split("/")[-1]
            if p not in merged[qid]["parents"]:
                merged[qid]["parents"].append(p)

    items = list(merged.values())
    author_cache[author_qid] = items

    # WDQSに少し余裕を持たせる
    time.sleep(2)

    return items


def canonical_qid(item):
    # edition -> work
    if len(item["parents"]) == 1:
        return item["parents"][0]

    return item["qid"]


def best_score(title, item):
    if not item["texts"]:
        return 0.0

    return max(
        score(title, x)
        for x in item["texts"]
    )


def is_exact(title, item):
    target = norm(title)

    return any(
        norm(x) == target
        for x in item["texts"]
    )


bench = pd.read_csv(BENCH, sep="\t")
luna = pd.read_csv(LUNA, sep="\t")


def parse_author_qid(log):
    m = re.search(
        r"author_qid=(Q\d+)",
        str(log)
    )
    return m.group(1) if m else None


luna["resolved_author_qid"] = (
    luna["light_log"].apply(parse_author_qid)
)

author_map = dict(zip(
    luna["wk"].astype(str),
    luna["resolved_author_qid"]
))


# 既に完了しているtargetを読む
done = {}

if OUT.exists():
    with open(OUT, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                x = json.loads(line)
                done[str(x["target_id"])] = x

    print(f"Resuming: {len(done)} targets already saved")


for n, (_, row) in enumerate(bench.iterrows(), 1):

    wk = str(row["wk"])
    title = str(row["title"])
    author = str(row["author"])

    if wk in done:
        print(f"[{n:3d}/130] SKIP {title}")
        continue

    author_qid = author_map.get(wk)

    print(f"[{n:3d}/130] {title} / {author}")

    if not author_qid:
        # Edwin Brown Graham case:
        # author unresolved and title searches already manually checked
        packet = {
            "target_id": wk,
            "title": title,
            "author": author,
            "author_qid": None,
            "route": "author_unresolved",
            "author_item_count": 0,
            "exact_count": 0,
            "candidate_qids": [],
        }

    else:
        items = get_author_items(author_qid)

        if items is None:
            print("      RETRIEVAL ERROR -- not saving")
            continue

        exact = [
            x for x in items
            if is_exact(title, x)
        ]

        exact_qids = []

        for item in exact:
            q = canonical_qid(item)

            if q not in exact_qids:
                exact_qids.append(q)

        ranked = sorted(
            items,
            key=lambda x: best_score(title, x),
            reverse=True,
        )

        fuzzy_qids = []

        for item in ranked:
            q = canonical_qid(item)

            if q not in fuzzy_qids:
                fuzzy_qids.append(q)

            if len(fuzzy_qids) >= 20:
                break

        # exactは全部保持、その後fuzzy上位20で補完
        candidates = list(exact_qids)

        for q in fuzzy_qids:
            if q not in candidates:
                candidates.append(q)

        packet = {
            "target_id": wk,
            "title": title,
            "author": author,
            "author_qid": author_qid,
            "route": (
                "author_exact"
                if exact_qids
                else "author_fuzzy"
            ),
            "author_item_count": len(items),
            "exact_count": len(exact_qids),
            "candidate_qids": candidates,
        }

        print(
            f"    works={len(items)} "
            f"exact={len(exact_qids)} "
            f"candidates={len(candidates)}"
        )

    # 1 targetごとに即保存
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                packet,
                ensure_ascii=False
            ) + "\n"
        )


print()
print("=" * 70)

rows = []

with open(OUT, encoding="utf-8") as f:
    for line in f:
        if line.strip():
            rows.append(json.loads(line))

print("Saved targets:", len(rows))

counts = [
    len(x["candidate_qids"])
    for x in rows
]

if counts:
    print(
        "Candidate mean:",
        round(sum(counts) / len(counts), 2)
    )
    print("Candidate max:", max(counts))

print("Saved:", OUT)
