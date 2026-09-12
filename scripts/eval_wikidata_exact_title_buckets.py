#!/usr/bin/env python3

import re
import time
import unicodedata
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "derived/benchmark/full_eval_130items.tsv"
OUT = ROOT / "derived/benchmark/wikidata_exact_title_buckets.tsv"

API = "https://www.wikidata.org/w/api.php"
SPARQL = "https://query.wikidata.org/sparql"

HEADERS = {
    "User-Agent": "canon-pipeline-exact-title-test/1.0"
}

session = requests.Session()
session.headers.update(HEADERS)

author_works_cache = {}


def norm_title(s):
    s = str(s).strip()

    # corpus-specific prefixes / bibliographic suffixes
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

    s = unicodedata.normalize("NFKD", s)
    s = s.lower()

    # normalize punctuation to spaces
    s = s.replace("&", " and ")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)

    return s.strip()


def get_entities(qids):
    r = session.get(
        API,
        params={
            "action": "wbgetentities",
            "ids": "|".join(qids),
            "props": "claims|labels",
            "languages": "en",
            "languagefallback": 1,
            "format": "json",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["entities"]


def get_p50(ent):
    out = []

    for claim in ent.get("claims", {}).get("P50", []):
        try:
            out.append(
                claim["mainsnak"]["datavalue"]["value"]["id"]
            )
        except Exception:
            pass

    return list(dict.fromkeys(out))


def sparql(query):
    for attempt in range(5):
        try:
            r = session.get(
                SPARQL,
                params={
                    "query": query,
                    "format": "json",
                },
                timeout=90,
            )

            if r.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"      WDQS 429; wait {wait}s")
                time.sleep(wait)
                continue

            r.raise_for_status()
            return r.json()["results"]["bindings"]

        except Exception as e:
            if attempt == 4:
                print(f"      WDQS FAILED: {e}")
                return None

            wait = 2 ** attempt
            print(f"      WDQS retry; wait {wait}s")
            time.sleep(wait)

    return None


def get_author_works(author_qid):
    if author_qid in author_works_cache:
        return author_works_cache[author_qid]

    q = f"""
SELECT DISTINCT ?work ?workLabel WHERE {{
  ?work wdt:P50 wd:{author_qid}.
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en".
  }}
}}
"""

    rows = sparql(q)

    if rows is None:
        return None

    works = []

    for row in rows:
        qid = row["work"]["value"].split("/")[-1]
        label = row.get("workLabel", {}).get("value", "")

        works.append({
            "qid": qid,
            "label": label,
            "norm": norm_title(label),
        })

    author_works_cache[author_qid] = works
    time.sleep(1.0)

    return works


df = pd.read_csv(BENCH, sep="\t")
df = df[df["type"] == "positive"].copy()

gold_qids = df["gold_qid_final"].astype(str).tolist()

gold_entities = {}

for i in range(0, len(gold_qids), 50):
    batch = gold_qids[i:i+50]
    gold_entities.update(get_entities(batch))
    time.sleep(1.0)


rows_out = []

for n, (_, row) in enumerate(df.iterrows(), 1):
    title = str(row["title"])
    gold = str(row["gold_qid_final"])
    target_norm = norm_title(title)

    print(f"[{n:2d}/{len(df)}] {title}")

    ent = gold_entities.get(gold, {})
    author_qids = get_p50(ent)

    all_works = {}

    for aq in author_qids:
        works = get_author_works(aq)

        if works is None:
            continue

        for w in works:
            all_works[w["qid"]] = w

    exact = [
        w for w in all_works.values()
        if w["norm"] == target_norm
    ]

    exact_qids = [w["qid"] for w in exact]
    gold_in_exact = gold in exact_qids

    print(
        f"    works={len(all_works)}, "
        f"exact_bucket={len(exact)}, "
        f"gold_in_exact={gold_in_exact}"
    )

    if exact:
        for w in exact[:20]:
            mark = " <== GOLD" if w["qid"] == gold else ""
            print(
                f'      {w["qid"]:12s} | {w["label"]}{mark}'
            )

        if len(exact) > 20:
            print(f"      ... +{len(exact)-20} more")

    rows_out.append({
        "title": title,
        "author": row["author"],
        "gold_qid": gold,
        "author_qids": ";".join(author_qids),
        "n_author_works": len(all_works),
        "target_norm": target_norm,
        "exact_bucket_size": len(exact),
        "gold_in_exact": gold_in_exact,
        "exact_qids": ";".join(exact_qids),
        "exact_labels": " || ".join(
            f'{w["qid"]}:{w["label"]}'
            for w in exact
        ),
    })


out = pd.DataFrame(rows_out)
out.to_csv(OUT, sep="\t", index=False)

print()
print("=" * 72)
print("EXACT-TITLE BUCKET SUMMARY")
print()

print(
    "Gold contained in exact bucket:",
    f'{out["gold_in_exact"].sum()}/{len(out)}',
    f'= {out["gold_in_exact"].mean():.3f}'
)

print()
print("Bucket-size distribution:")
print(
    out["exact_bucket_size"]
    .value_counts()
    .sort_index()
    .to_string()
)

print()
for k in [1, 2, 3, 5, 10, 20]:
    n = (
        (out["gold_in_exact"] == True)
        & (out["exact_bucket_size"] <= k)
    ).sum()

    print(
        f"Gold found with bucket <= {k:2}: "
        f"{n}/{len(out)} = {n/len(out):.3f}"
    )

print()
print("Gold NOT captured by exact title:")
miss = out[out["gold_in_exact"] != True]

if len(miss):
    print(
        miss[
            [
                "title",
                "author",
                "gold_qid",
                "n_author_works",
                "exact_bucket_size",
            ]
        ].to_string(index=False)
    )
else:
    print("None")

print()
print("Large exact-title buckets (>5):")
large = out[out["exact_bucket_size"] > 5]

if len(large):
    print(
        large[
            [
                "title",
                "author",
                "gold_qid",
                "exact_bucket_size",
                "exact_qids",
            ]
        ].to_string(index=False)
    )
else:
    print("None")

print()
print("Saved:", OUT)
