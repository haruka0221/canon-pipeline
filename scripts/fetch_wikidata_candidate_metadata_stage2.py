#!/usr/bin/env python3

import json
import time
from pathlib import Path

import requests

SRC = Path(
    "derived/benchmark/wikidata_candidates_stage1b_130.jsonl"
)

CACHE = Path(
    "derived/benchmark/wikidata_candidate_metadata_cache.json"
)

OUT = Path(
    "derived/benchmark/wikidata_annotation_packets_stage2_130.jsonl"
)

API = "https://www.wikidata.org/w/api.php"

session = requests.Session()
session.headers.update({
    "User-Agent": "canon-pipeline-candidate-metadata/2.0"
})


# --------------------------------------------------
# Read stage1b
# --------------------------------------------------

rows = []

with open(SRC, encoding="utf-8") as f:
    for line in f:
        if line.strip():
            rows.append(json.loads(line))


# --------------------------------------------------
# Cache
# --------------------------------------------------

if CACHE.exists():
    with open(CACHE, encoding="utf-8") as f:
        cache = json.load(f)
    print(f"Loaded cache: {len(cache)} entities")
else:
    cache = {}


def save_cache():
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(
            cache,
            f,
            ensure_ascii=False
        )


def fetch_entities(qids):
    qids = list(dict.fromkeys(
        q for q in qids
        if q and q.startswith("Q")
    ))

    missing = [
        q for q in qids
        if q not in cache
    ]

    print(
        f"Requested: {len(qids)} | "
        f"Missing: {len(missing)}"
    )

    for i in range(0, len(missing), 40):
        batch = missing[i:i+40]

        print(
            f"  fetching "
            f"{i+1}-{min(i+40, len(missing))}"
            f"/{len(missing)}"
        )

        for attempt in range(8):
            try:
                r = session.get(
                    API,
                    params={
                        "action": "wbgetentities",
                        "ids": "|".join(batch),
                        "props":
                            "labels|descriptions|aliases|claims|sitelinks",
                        "languages": "en",
                        "languagefallback": 1,
                        "sitefilter": "enwiki",
                        "format": "json",
                        "maxlag": 5,
                    },
                    timeout=60,
                )

                if r.status_code in (429, 503):
                    wait = 20 * (attempt + 1)
                    print(
                        f"    HTTP {r.status_code}; "
                        f"waiting {wait}s"
                    )
                    time.sleep(wait)
                    continue

                r.raise_for_status()

                data = r.json()

                # maxlag can also appear as an API error
                if "error" in data:
                    wait = 20 * (attempt + 1)
                    print(
                        f"    API error "
                        f"{data['error'].get('code')}; "
                        f"waiting {wait}s"
                    )
                    time.sleep(wait)
                    continue

                cache.update(data["entities"])
                save_cache()

                # Deliberately conservative
                time.sleep(4)
                break

            except Exception as e:
                if attempt == 7:
                    raise

                wait = 10 * (attempt + 1)
                print(
                    f"    {type(e).__name__}: {e}; "
                    f"waiting {wait}s"
                )
                time.sleep(wait)


def item_ids(ent, prop):
    out = []

    for claim in ent.get("claims", {}).get(prop, []):
        try:
            value = claim[
                "mainsnak"
            ]["datavalue"]["value"]

            if isinstance(value, dict) and "id" in value:
                out.append(value["id"])

        except Exception:
            pass

    return list(dict.fromkeys(out))


def dates(ent):
    out = []

    for claim in ent.get("claims", {}).get("P577", []):
        try:
            value = claim[
                "mainsnak"
            ]["datavalue"]["value"]

            out.append(
                value["time"].lstrip("+")
            )
        except Exception:
            pass

    return list(dict.fromkeys(out))


def monolingual_text(ent, prop):
    out = []

    for claim in ent.get("claims", {}).get(prop, []):
        try:
            value = claim[
                "mainsnak"
            ]["datavalue"]["value"]

            if isinstance(value, dict):
                text = value.get("text")
                lang = value.get("language")

                if text:
                    out.append({
                        "text": text,
                        "language": lang,
                    })
        except Exception:
            pass

    return out


def label(qid):
    ent = cache.get(qid, {})

    return (
        ent.get("labels", {})
        .get("en", {})
        .get("value", "")
    )


# --------------------------------------------------
# 1. Fetch all candidate entities
# --------------------------------------------------

candidate_qids = []

for row in rows:
    candidate_qids.extend(
        row.get("candidate_qids", [])
    )

candidate_qids = list(dict.fromkeys(candidate_qids))

print()
print("Unique candidate QIDs:", len(candidate_qids))

fetch_entities(candidate_qids)


# --------------------------------------------------
# 2. Fetch referenced P31/P50/P629 entities in bulk
# --------------------------------------------------

related = set()

for qid in candidate_qids:
    ent = cache.get(qid, {})

    for prop in ("P31", "P50", "P629"):
        related.update(
            item_ids(ent, prop)
        )

print()
print("Related entities:", len(related))

fetch_entities(sorted(related))


# --------------------------------------------------
# 3. Build enriched packets
# --------------------------------------------------

packets = []

for row in rows:

    title_search_added = set(
        row.get("title_search_added", [])
    )

    candidates = []

    for position, qid in enumerate(
        row.get("candidate_qids", []),
        start=1
    ):
        ent = cache.get(qid, {})

        p31 = item_ids(ent, "P31")
        p50 = item_ids(ent, "P50")
        p629 = item_ids(ent, "P629")

        # Preserve provenance instead of treating the
        # combined list as one meaningful ranking.
        if qid in title_search_added:
            source = "title_search"
        elif (
            row.get("exact_count", 0) > 0
            and position <= row.get("exact_count", 0)
        ):
            source = "author_exact"
        else:
            source = "author_fuzzy"

        candidates.append({
            "qid": qid,
            "source": source,
            "combined_position": position,

            "label": label(qid),

            "description": (
                ent.get("descriptions", {})
                .get("en", {})
                .get("value", "")
            ),

            "aliases": [
                x["value"]
                for x in (
                    ent.get("aliases", {})
                    .get("en", [])
                )
            ],

            "stated_titles": monolingual_text(
                ent,
                "P1476"
            ),

            "publication_dates": dates(ent),

            "instance_of": [
                {
                    "qid": x,
                    "label": label(x),
                }
                for x in p31
            ],

            "authors": [
                {
                    "qid": x,
                    "label": label(x),
                }
                for x in p50
            ],

            "edition_or_translation_of": [
                {
                    "qid": x,
                    "label": label(x),
                }
                for x in p629
            ],

            "has_enwiki": (
                "enwiki"
                in ent.get("sitelinks", {})
            ),
        })

    packet = {
        "target_id": row["target_id"],
        "title": row["title"],
        "author": row["author"],
        "author_qid": row.get("author_qid"),
        "route": row.get("route"),
        "exact_count": row.get("exact_count"),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }

    packets.append(packet)


with open(OUT, "w", encoding="utf-8") as f:
    for packet in packets:
        f.write(
            json.dumps(
                packet,
                ensure_ascii=False
            ) + "\n"
        )


print()
print("=" * 70)
print("STAGE 2 COMPLETE")
print("targets:", len(packets))
print("unique candidate QIDs:", len(candidate_qids))
print("cache entities:", len(cache))
print("saved:", OUT)
print("cache:", CACHE)
