#!/usr/bin/env python3
from __future__ import annotations

import argparse
import bz2
import json
import time
from pathlib import Path

import orjson


ITEM_PROPS = [
    "P31",    # instance of
    "P106",   # occupation
    "P50",    # author
    "P629",   # edition/version/translation of
    "P407",   # language
    "P655",   # translator
    "P98",    # editor
    "P747",   # has version/edition/translation
    "P9745",  # translation of
    "P123",   # publisher
    "P291",   # place of publication
]


def en_value(mapping):
    x = mapping.get("en")
    return x.get("value", "") if isinstance(x, dict) else ""


def en_aliases(ent):
    return [
        x.get("value", "")
        for x in ent.get("aliases", {}).get("en", [])
        if x.get("value")
    ]


def claim_item_ids(ent, prop):
    out = []
    seen = set()

    for claim in ent.get("claims", {}).get(prop, []):
        try:
            value = claim["mainsnak"]["datavalue"]["value"]
            qid = value.get("id") if isinstance(value, dict) else None

            if qid and qid not in seen:
                seen.add(qid)
                out.append(qid)
        except Exception:
            pass

    return out


def claim_dates(ent):
    out = []
    seen = set()

    for claim in ent.get("claims", {}).get("P577", []):
        try:
            value = (
                claim["mainsnak"]["datavalue"]["value"]["time"]
                .lstrip("+")
            )

            if value not in seen:
                seen.add(value)
                out.append(value)
        except Exception:
            pass

    return out


def stated_titles(ent):
    out = []
    seen = set()

    for claim in ent.get("claims", {}).get("P1476", []):
        try:
            value = claim["mainsnak"]["datavalue"]["value"]

            if isinstance(value, dict) and value.get("text"):
                key = (
                    value["text"],
                    value.get("language", ""),
                )

                if key not in seen:
                    seen.add(key)
                    out.append({
                        "text": value["text"],
                        "language": value.get("language", ""),
                    })
        except Exception:
            pass

    return out


def extract_entity(ent):
    row = {
        "qid": ent.get("id", ""),
        "label_en": en_value(ent.get("labels", {})),
        "description_en": en_value(ent.get("descriptions", {})),
        "aliases_en": en_aliases(ent),
        "p577": claim_dates(ent),
        "p1476": stated_titles(ent),
        "has_enwiki": "enwiki" in ent.get("sitelinks", {}),
        "modified": str(ent.get("modified", "") or ""),
        "lastrevid": str(ent.get("lastrevid", "") or ""),
    }

    for prop in ITEM_PROPS:
        row[prop.lower()] = claim_item_ids(ent, prop)

    return row


def read_qids(path):
    qids = set()

    with path.open(encoding="utf-8") as f:
        for line in f:
            qid = line.strip()
            if qid:
                qids.add(qid)

    return qids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", type=Path, required=True)
    ap.add_argument("--qids", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--progress-every", type=int, default=1_000_000)
    args = ap.parse_args()

    wanted = read_qids(args.qids)
    found = {}

    if args.output.exists():
        with args.output.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    found[row["qid"]] = row

    print("wanted QIDs:", len(wanted))
    print("already saved:", len(found))

    n_entities = 0
    bad_json = 0
    started = time.time()

    with bz2.open(args.dump, "rb") as f:
        for raw in f:
            raw = raw.strip()

            if not raw or raw in {b"[", b"]"}:
                continue

            if raw.endswith(b","):
                raw = raw[:-1]

            try:
                ent = orjson.loads(raw)
            except Exception:
                bad_json += 1
                continue

            n_entities += 1
            qid = ent.get("id", "")

            if qid in wanted and qid not in found:
                found[qid] = extract_entity(ent)

                args.output.parent.mkdir(parents=True, exist_ok=True)
                with args.output.open("a", encoding="utf-8") as out:
                    out.write(
                        json.dumps(found[qid], ensure_ascii=False)
                        + "\n"
                    )

                print(
                    f"FOUND {qid} "
                    f"({len(found)}/{len(wanted)}) "
                    f"{found[qid]['label_en']}"
                )

                if len(found) == len(wanted):
                    break

            if (
                args.progress_every
                and n_entities % args.progress_every == 0
            ):
                elapsed = time.time() - started
                print(
                    f"scanned={n_entities:,} "
                    f"found={len(found)}/{len(wanted)} "
                    f"elapsed={elapsed/60:.1f} min"
                )

    missing = sorted(wanted - set(found))

    print("\nDONE")
    print("scanned entities:", n_entities)
    print("bad json:", bad_json)
    print("found:", len(found))
    print("missing:", len(missing))
    print("output:", args.output)

    if missing:
        print("\nMissing QIDs:")
        for qid in missing:
            print(qid)


if __name__ == "__main__":
    main()
