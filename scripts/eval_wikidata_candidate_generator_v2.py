#!/usr/bin/env python3

import re
import time
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "derived/benchmark/full_eval_130items.tsv"
OUT = ROOT / "derived/benchmark/wikidata_candidate_generator_v2.tsv"

SPARQL = "https://query.wikidata.org/sparql"
API = "https://www.wikidata.org/w/api.php"
HEADERS = {"User-Agent": "canon-pipeline-candidate-generator-v2/1.0"}

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

    s = re.sub(
        r",\s*a novel\s*$",
        "",
        s,
        flags=re.I,
    )

    s = unicodedata.normalize("NFKD", s).lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)

    return s.strip()


def sim(a, b):
    return SequenceMatcher(
        None,
        norm(a),
        norm(b),
    ).ratio()


def api_entities(qids):
    if not qids:
        return {}

    r = session.get(
        API,
        params={
            "action": "wbgetentities",
            "ids": "|".join(qids),
            "props": "claims",
            "format": "json",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["entities"]


def p50_qids(ent):
    out = []
    for c in ent.get("claims", {}).get("P50", []):
        try:
            out.append(
                c["mainsnak"]["datavalue"]["value"]["id"]
            )
        except Exception:
            pass
    return list(dict.fromkeys(out))


def get_author_items(author_qid):
    if author_qid in author_cache:
        return author_cache[author_qid]

    q = f"""
SELECT ?work ?label ?parent ?statedTitle WHERE {{
  ?work wdt:P50 wd:{author_qid}.

  OPTIONAL {{
    ?work rdfs:label ?label.
    FILTER(LANG(?label) = "en")
  }}

  OPTIONAL {{
    ?work wdt:P629 ?parent.
  }}

  OPTIONAL {{
    ?work wdt:P1476 ?statedTitle.
    FILTER(
      LANG(?statedTitle) = "en"
      || LANG(?statedTitle) = ""
    )
  }}
}}
"""

    for attempt in range(5):
        try:
            r = session.get(
                SPARQL,
                params={"query": q, "format": "json"},
                timeout=120,
            )

            if r.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"      WDQS 429; wait {wait}s")
                time.sleep(wait)
                continue

            r.raise_for_status()
            rows = r.json()["results"]["bindings"]
            break

        except Exception as e:
            if attempt == 4:
                print("      FAILED:", e)
                return None
            time.sleep(2 ** attempt)

    items = {}

    for x in rows:
        qid = x["work"]["value"].split("/")[-1]

        if qid not in items:
            items[qid] = {
                "qid": qid,
                "labels": set(),
                "titles": set(),
                "parents": set(),
            }

        if "label" in x:
            items[qid]["labels"].add(
                x["label"]["value"]
            )

        if "statedTitle" in x:
            items[qid]["titles"].add(
                x["statedTitle"]["value"]
            )

        if "parent" in x:
            items[qid]["parents"].add(
                x["parent"]["value"].split("/")[-1]
            )

    author_cache[author_qid] = items
    time.sleep(1)

    return items


def canonical_qids(item):
    # P629があれば親workへcollapse
    if item["parents"]:
        return item["parents"]

    return {item["qid"]}


def best_score(target, item):
    vals = (
        list(item["labels"])
        + list(item["titles"])
    )

    if not vals:
        return 0.0

    return max(sim(target, x) for x in vals)


def is_exact(target, item):
    tn = norm(target)

    vals = (
        list(item["labels"])
        + list(item["titles"])
    )

    return any(
        norm(x) == tn
        for x in vals
    )


def title_search(title, limit=20):
    time.sleep(1)

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
    r.raise_for_status()

    return [
        x["id"]
        for x in r.json().get("search", [])
    ]


df = pd.read_csv(BENCH, sep="\t")
df = df[df["type"] == "positive"].copy()

gold_qids = df["gold_qid_final"].astype(str).tolist()

gold_entities = {}

for i in range(0, len(gold_qids), 50):
    batch = gold_qids[i:i+50]
    gold_entities.update(api_entities(batch))
    time.sleep(1)


results = []

for n, (_, row) in enumerate(df.iterrows(), 1):

    title = str(row["title"])
    gold = str(row["gold_qid_final"])

    print(f"[{n:2d}/{len(df)}] {title}")

    ent = gold_entities.get(gold, {})
    authors = p50_qids(ent)

    all_items = {}

    failed = False

    for aq in authors:
        items = get_author_items(aq)

        if items is None:
            failed = True
            break

        all_items.update(items)

    if failed:
        results.append({
            "title": title,
            "gold_qid": gold,
            "candidate_count": 0,
            "gold_in_candidates": False,
            "exact_raw_count": 0,
            "exact_collapsed_count": 0,
            "status": "ERROR",
            "candidate_qids": "",
        })
        continue

    # 1. exact title
    exact_raw = [
        item
        for item in all_items.values()
        if is_exact(title, item)
    ]

    exact_canonical = set()

    for item in exact_raw:
        exact_canonical.update(
            canonical_qids(item)
        )

    # 2. fuzzy title:
    # canonical QIDを重複除去しながら上位20まで
    ranked = sorted(
        all_items.values(),
        key=lambda x: best_score(title, x),
        reverse=True,
    )

    fuzzy_canonical = []

    for item in ranked:
        for qid in canonical_qids(item):
            if qid not in fuzzy_canonical:
                fuzzy_canonical.append(qid)

        if len(fuzzy_canonical) >= 20:
            break

    candidates = set(exact_canonical)
    candidates.update(fuzzy_canonical[:20])

    # 3. exact候補がない場合のみ通常title searchも追加
    used_title_search = False

    if not exact_canonical:
        used_title_search = True

        try:
            candidates.update(
                title_search(title, 20)
            )
        except Exception as e:
            print("      title search failed:", e)

    hit = gold in candidates

    print(
        f"    raw={len(all_items)} "
        f"exact_raw={len(exact_raw)} "
        f"collapsed_exact={len(exact_canonical)} "
        f"candidates={len(candidates)} "
        f"gold={'YES' if hit else 'NO'}"
    )

    results.append({
        "title": title,
        "author": row["author"],
        "gold_qid": gold,
        "n_author_items": len(all_items),
        "exact_raw_count": len(exact_raw),
        "exact_collapsed_count": len(exact_canonical),
        "used_title_search": used_title_search,
        "candidate_count": len(candidates),
        "gold_in_candidates": hit,
        "status": "OK",
        "candidate_qids": ";".join(
            sorted(candidates)
        ),
    })


out = pd.DataFrame(results)
out.to_csv(OUT, sep="\t", index=False)

ok = out[out["status"] == "OK"]

print()
print("=" * 70)
print("CANDIDATE GENERATOR V2")
print()

hits = int(ok["gold_in_candidates"].sum())

print(
    f"Gold coverage: "
    f"{hits}/{len(out)} = {hits/len(out):.3f}"
)

print()
print("Candidate-count summary:")
print(
    ok["candidate_count"]
    .describe()
    .to_string()
)

print()
print("Collapsed exact-title bucket sizes:")
print(
    ok["exact_collapsed_count"]
    .value_counts()
    .sort_index()
    .to_string()
)

print()
print("MISSES:")

miss = ok[ok["gold_in_candidates"] != True]

if len(miss):
    print(
        miss[
            [
                "title",
                "author",
                "gold_qid",
                "n_author_items",
                "exact_raw_count",
                "exact_collapsed_count",
                "candidate_count",
            ]
        ].to_string(index=False)
    )
else:
    print("NONE")

print()
print("Saved:", OUT)
