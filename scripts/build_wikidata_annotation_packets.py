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

OUT_JSONL = ROOT / "derived/benchmark/wikidata_annotation_packets_130.jsonl"
OUT_TSV = ROOT / "derived/benchmark/wikidata_annotation_packets_130.tsv"

API = "https://www.wikidata.org/w/api.php"
SPARQL = "https://query.wikidata.org/sparql"

HEADERS = {
    "User-Agent": "canon-pipeline-annotation-packets/1.0"
}

session = requests.Session()
session.headers.update(HEADERS)

entity_cache = {}
author_items_cache = {}


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


def similarity(a, b):
    return SequenceMatcher(
        None,
        norm(a),
        norm(b),
    ).ratio()


def api_call(params):
    for attempt in range(6):
        r = session.get(
            API,
            params=params,
            timeout=30,
        )

        if r.status_code == 429:
            wait = 15 * (attempt + 1)
            print(f"      Wikidata 429; waiting {wait}s")
            time.sleep(wait)
            continue

        r.raise_for_status()
        return r.json()

    raise RuntimeError("Wikidata API repeatedly failed")


def get_entities(qids):
    qids = [
        q for q in dict.fromkeys(qids)
        if q and q.startswith("Q")
    ]

    missing = [
        q for q in qids
        if q not in entity_cache
    ]

    for i in range(0, len(missing), 50):
        batch = missing[i:i+50]

        data = api_call({
            "action": "wbgetentities",
            "ids": "|".join(batch),
            "props": "labels|descriptions|claims",
            "languages": "en",
            "languagefallback": 1,
            "format": "json",
        })

        entity_cache.update(data["entities"])
        time.sleep(1)

    return {
        q: entity_cache.get(q, {})
        for q in qids
    }


def item_ids(ent, prop):
    out = []

    for claim in ent.get("claims", {}).get(prop, []):
        try:
            v = claim["mainsnak"]["datavalue"]["value"]
            if isinstance(v, dict) and "id" in v:
                out.append(v["id"])
        except Exception:
            pass

    return list(dict.fromkeys(out))


def label(ent):
    return (
        ent.get("labels", {})
        .get("en", {})
        .get("value", "")
    )


def description(ent):
    return (
        ent.get("descriptions", {})
        .get("en", {})
        .get("value", "")
    )


def publication_dates(ent):
    vals = []

    for claim in ent.get("claims", {}).get("P577", []):
        try:
            t = claim["mainsnak"]["datavalue"]["value"]["time"]
            vals.append(t.lstrip("+")[:10])
        except Exception:
            pass

    return sorted(set(vals))


def stated_titles(ent):
    vals = []

    for claim in ent.get("claims", {}).get("P1476", []):
        try:
            v = claim["mainsnak"]["datavalue"]["value"]
            if isinstance(v, dict):
                text = v.get("text", "")
                if text:
                    vals.append(text)
        except Exception:
            pass

    return list(dict.fromkeys(vals))


def collapse_qid(qid):
    current = qid
    seen = set()

    for _ in range(10):
        if current in seen:
            return qid

        seen.add(current)

        ent = get_entities([current]).get(current, {})
        parents = item_ids(ent, "P629")

        if len(parents) == 1:
            current = parents[0]
            continue

        return current

    return current


def get_author_items(author_qid):
    if author_qid in author_items_cache:
        return author_items_cache[author_qid]

    q = f"""
SELECT DISTINCT ?item WHERE {{
  ?item wdt:P50 wd:{author_qid}.
}}
"""

    for attempt in range(5):
        try:
            r = session.get(
                SPARQL,
                params={
                    "query": q,
                    "format": "json",
                },
                timeout=90,
            )

            if r.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"      WDQS 429; waiting {wait}s")
                time.sleep(wait)
                continue

            r.raise_for_status()

            qids = [
                x["item"]["value"].split("/")[-1]
                for x in r.json()["results"]["bindings"]
            ]

            get_entities(qids)

            items = []

            for qid in qids:
                ent = entity_cache.get(qid, {})

                vals = [label(ent)]
                vals.extend(stated_titles(ent))
                vals = [x for x in vals if x]

                items.append({
                    "qid": qid,
                    "texts": vals,
                })

            author_items_cache[author_qid] = items
            time.sleep(1)

            return items

        except Exception as e:
            if attempt == 4:
                print("      author retrieval failed:", e)
                return []

            time.sleep(2 ** attempt)

    return []


def title_search(title, limit=10):
    data = api_call({
        "action": "wbsearchentities",
        "search": title,
        "language": "en",
        "uselang": "en",
        "type": "item",
        "limit": limit,
        "format": "json",
    })

    time.sleep(1)

    return [
        x["id"]
        for x in data.get("search", [])
    ]


def best_score(target, item):
    if not item["texts"]:
        return 0.0

    return max(
        similarity(target, x)
        for x in item["texts"]
    )


def is_exact(target, item):
    tn = norm(target)

    return any(
        norm(x) == tn
        for x in item["texts"]
    )


def enrich_candidates(qids):
    qids = list(dict.fromkeys(qids))
    ents = get_entities(qids)

    related = set()

    for ent in ents.values():
        related.update(item_ids(ent, "P31"))
        related.update(item_ids(ent, "P50"))

    related_ents = get_entities(list(related))

    out = []

    for qid in qids:
        ent = ents.get(qid, {})

        p31 = item_ids(ent, "P31")
        p50 = item_ids(ent, "P50")

        out.append({
            "qid": qid,
            "label": label(ent),
            "description": description(ent),
            "instance_of": [
                {
                    "qid": x,
                    "label": label(related_ents.get(x, {}))
                }
                for x in p31
            ],
            "authors": [
                {
                    "qid": x,
                    "label": label(related_ents.get(x, {}))
                }
                for x in p50
            ],
            "publication_dates": publication_dates(ent),
            "stated_titles": stated_titles(ent),
        })

    return out


bench = pd.read_csv(BENCH, sep="\t")
luna = pd.read_csv(LUNA, sep="\t")


def parse_author_qid(log):
    m = re.search(
        r"author_qid=(Q\d+)",
        str(log)
    )
    return m.group(1) if m else None


luna["resolved_author_qid"] = (
    luna["light_log"]
    .apply(parse_author_qid)
)

author_map = dict(zip(
    luna["wk"],
    luna["resolved_author_qid"]
))

packets = []
tsv_rows = []


for n, (_, row) in enumerate(bench.iterrows(), 1):

    title = str(row["title"])
    author = str(row["author"])
    wk = str(row["wk"])

    author_qid = author_map.get(wk)

    print(
        f"[{n:3d}/{len(bench)}] "
        f"{title} / {author}"
    )

    candidates = []
    route = []

    if author_qid:
        items = get_author_items(author_qid)

        exact_items = [
            x for x in items
            if is_exact(title, x)
        ]

        exact_collapsed = []

        for item in exact_items:
            qid = collapse_qid(item["qid"])
            if qid not in exact_collapsed:
                exact_collapsed.append(qid)

        candidates.extend(exact_collapsed)

        if exact_collapsed:
            route.append("author_exact")
        else:
            route.append("author_no_exact")

        ranked = sorted(
            items,
            key=lambda x: best_score(title, x),
            reverse=True,
        )

        fuzzy = []

        for item in ranked:
            qid = collapse_qid(item["qid"])

            if qid not in fuzzy:
                fuzzy.append(qid)

            if len(fuzzy) >= 10:
                break

        for qid in fuzzy:
            if qid not in candidates:
                candidates.append(qid)

        route.append("author_fuzzy10")

    else:
        route.append("author_unresolved")

    # If no exact author-title hit, supplement by global title search
    if (
        not author_qid
        or "author_no_exact" in route
    ):
        variants = [title]

        cleaned = re.sub(
            r"^textplus\s*[-:]\s*",
            "",
            title,
            flags=re.I,
        ).strip()

        if cleaned != title:
            variants.append(cleaned)

        if "," in cleaned:
            variants.append(
                cleaned.split(",")[0].strip()
            )

        seen_variants = set()

        for variant in variants:
            if not variant or variant in seen_variants:
                continue

            seen_variants.add(variant)

            for qid in title_search(variant, 10):
                qid2 = collapse_qid(qid)

                if qid2 not in candidates:
                    candidates.append(qid2)

        route.append("title_search")

    enriched = enrich_candidates(candidates)

    packet = {
        "target_id": wk,
        "title": title,
        "author": author,
        "author_qid": author_qid,
        "first_publish_year": None,
        "candidate_route": route,
        "candidates": enriched,
    }

    packets.append(packet)

    tsv_rows.append({
        "wk": wk,
        "title": title,
        "author": author,
        "author_qid": author_qid or "",
        "candidate_route": ";".join(route),
        "candidate_count": len(enriched),
        "candidate_qids": ";".join(
            x["qid"]
            for x in enriched
        ),
        "candidate_json": json.dumps(
            enriched,
            ensure_ascii=False
        ),
    })

    print(
        f"    route={'+'.join(route)} "
        f"candidates={len(enriched)}"
    )


with open(
    OUT_JSONL,
    "w",
    encoding="utf-8"
) as f:
    for packet in packets:
        f.write(
            json.dumps(
                packet,
                ensure_ascii=False
            )
            + "\n"
        )


pd.DataFrame(tsv_rows).to_csv(
    OUT_TSV,
    sep="\t",
    index=False
)

print()
print("=" * 70)
print("ANNOTATION PACKETS")
print("targets:", len(packets))
print(
    "candidate mean:",
    round(
        sum(len(x["candidates"]) for x in packets)
        / len(packets),
        2
    )
)
print(
    "candidate max:",
    max(len(x["candidates"]) for x in packets)
)
print()
print("Saved:")
print(OUT_JSONL)
print(OUT_TSV)
