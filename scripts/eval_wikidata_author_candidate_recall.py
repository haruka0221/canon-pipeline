#!/usr/bin/env python3

import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "derived/benchmark/full_eval_130items.tsv"
OUT = ROOT / "derived/benchmark/wikidata_author_candidate_recall.tsv"

API = "https://www.wikidata.org/w/api.php"
SPARQL = "https://query.wikidata.org/sparql"

HEADERS = {
    "User-Agent": "canon-pipeline-candidate-recall/1.0"
}

session = requests.Session()
session.headers.update(HEADERS)

author_works_cache = {}


def norm_title(s):
    s = str(s).lower()

    # Existing pipeline conventions
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
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\b(the|a|an)\b", " ", s)

    return " ".join(s.split())


def similarity(a, b):
    return SequenceMatcher(
        None,
        norm_title(a),
        norm_title(b),
    ).ratio()


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
            qid = claim["mainsnak"]["datavalue"]["value"]["id"]
            out.append(qid)
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
                timeout=60,
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

    query = f"""
SELECT DISTINCT ?work ?workLabel WHERE {{
  ?work wdt:P50 wd:{author_qid}.
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en".
  }}
}}
"""

    rows = sparql(query)

    if rows is None:
        return None

    works = []

    for row in rows:
        qid = row["work"]["value"].split("/")[-1]
        label = row.get("workLabel", {}).get("value", "")

        works.append({
            "qid": qid,
            "label": label,
        })

    author_works_cache[author_qid] = works

    # Be gentle with WDQS
    time.sleep(1.0)

    return works


df = pd.read_csv(BENCH, sep="\t")
df = df[df["type"] == "positive"].copy()

gold_qids = df["gold_qid_final"].astype(str).tolist()

# Get the P50 authors directly from the gold QIDs.
# This intentionally isolates the candidate-generation stage:
# "assuming the correct author entity is already known".
gold_entities = {}

for i in range(0, len(gold_qids), 50):
    batch = gold_qids[i:i+50]
    gold_entities.update(get_entities(batch))
    time.sleep(1.0)


results = []

for n, (_, row) in enumerate(df.iterrows(), 1):
    title = str(row["title"])
    gold = str(row["gold_qid_final"])

    print(f"[{n:2d}/{len(df)}] {title}")

    ent = gold_entities.get(gold, {})
    author_qids = get_p50(ent)

    if not author_qids:
        print("    no P50 on gold entity")

        results.append({
            "title": title,
            "author": row["author"],
            "gold_qid": gold,
            "author_qids": "",
            "n_author_works": 0,
            "gold_score": None,
            "rank": None,
            "tie_aware_rank": None,
            "same_score_count": None,
            "status": "NO_P50",
        })
        continue

    all_works = {}

    failed = False

    for author_qid in author_qids:
        works = get_author_works(author_qid)

        if works is None:
            failed = True
            break

        for w in works:
            all_works[w["qid"]] = w

    if failed:
        results.append({
            "title": title,
            "author": row["author"],
            "gold_qid": gold,
            "author_qids": ";".join(author_qids),
            "n_author_works": 0,
            "gold_score": None,
            "rank": None,
            "tie_aware_rank": None,
            "same_score_count": None,
            "status": "RETRIEVAL_ERROR",
        })
        continue

    ranked = []

    for qid, w in all_works.items():
        score = similarity(title, w["label"])
        ranked.append((score, qid, w["label"]))

    # deterministic secondary sort only for reporting
    ranked.sort(key=lambda x: (-x[0], x[1]))

    gold_rows = [
        (i, score, qid, label)
        for i, (score, qid, label) in enumerate(ranked, 1)
        if qid == gold
    ]

    if not gold_rows:
        print(
            f"    GOLD NOT IN AUTHOR WORKS "
            f"(authors={author_qids}, works={len(ranked)})"
        )

        results.append({
            "title": title,
            "author": row["author"],
            "gold_qid": gold,
            "author_qids": ";".join(author_qids),
            "n_author_works": len(ranked),
            "gold_score": None,
            "rank": None,
            "tie_aware_rank": None,
            "same_score_count": None,
            "status": "GOLD_NOT_LINKED_BY_P50",
        })
        continue

    rank, gold_score, _, gold_label = gold_rows[0]

    # Tie-aware rank:
    # 1 + number of candidates with strictly better similarity.
    # This prevents arbitrary QID ordering from penalizing two exact-title Kims.
    tie_aware_rank = (
        1 + sum(score > gold_score for score, _, _ in ranked)
    )

    same_score_count = sum(
        score == gold_score
        for score, _, _ in ranked
    )

    print(
        f"    rank={rank}, tie-aware={tie_aware_rank}, "
        f"score={gold_score:.3f}, works={len(ranked)}, "
        f"label={gold_label!r}"
    )

    results.append({
        "title": title,
        "author": row["author"],
        "gold_qid": gold,
        "author_qids": ";".join(author_qids),
        "n_author_works": len(ranked),
        "gold_score": gold_score,
        "rank": rank,
        "tie_aware_rank": tie_aware_rank,
        "same_score_count": same_score_count,
        "status": "OK",
    })


out = pd.DataFrame(results)
out.to_csv(OUT, sep="\t", index=False)

ok = out[out["status"] == "OK"].copy()

print()
print("=" * 72)
print("AUTHOR-FIRST CANDIDATE RECALL")
print("Condition: correct author QID known; ALL P50 works retrieved")
print()
print(f"Positive benchmark items: {len(out)}")
print(f"Rankable: {len(ok)}")
print(f"No P50: {(out['status'] == 'NO_P50').sum()}")
print(
    "Gold not linked by P50:",
    (out["status"] == "GOLD_NOT_LINKED_BY_P50").sum()
)
print(
    "Retrieval errors:",
    (out["status"] == "RETRIEVAL_ERROR").sum()
)

print()
print("Tie-aware candidate recall:")

for k in [1, 5, 10, 20, 50]:
    hit = (ok["tie_aware_rank"] <= k).sum()
    denom = len(out)
    print(
        f"Recall@{k:<2} = "
        f"{hit}/{denom} = {hit/denom:.3f}"
    )

print()
print("Misses beyond top 20:")
miss20 = ok[ok["tie_aware_rank"] > 20]

if len(miss20):
    print(
        miss20[
            [
                "title",
                "author",
                "gold_qid",
                "n_author_works",
                "gold_score",
                "tie_aware_rank",
            ]
        ].to_string(index=False)
    )
else:
    print("None")

print()
print("Special cases not rankable:")
special = out[out["status"] != "OK"]

if len(special):
    print(
        special[
            [
                "title",
                "author",
                "gold_qid",
                "status",
            ]
        ].to_string(index=False)
    )
else:
    print("None")

print()
print("Saved:", OUT)
