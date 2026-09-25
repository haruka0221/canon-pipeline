#!/usr/bin/env python3

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

CACHE = ROOT / "derived/openlibrary_author_identity_cache_v1.jsonl"
BATCH = ROOT / "derived/goodreads_llm_review_batch1_v3.tsv"
POP = ROOT / "derived/ol_dump_population_with_scope.tsv"
EV = ROOT / "derived/goodreads_contributor_evidence_v3.tsv"
OUT = ROOT / "derived/goodreads_ol_author_identity_evidence_v1.tsv"


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.casefold()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


cache = {}
with CACHE.open(encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        cache[r["author_key"]] = r


batch = pd.read_csv(BATCH, sep="\t", dtype=str).fillna("")
pop = pd.read_csv(POP, sep="\t", dtype=str).fillna("")
ev = pd.read_csv(EV, sep="\t", dtype=str).fillna("")

x = batch.merge(
    pop[["work_key", "author_keys"]],
    left_on="ol_work_key",
    right_on="work_key",
    how="left",
)


candidate_ids = set(batch["goodreads_work_id"])

primary = {}

for _, r in ev.iterrows():
    gid = r["goodreads_work_id"]

    if gid not in candidate_ids:
        continue

    role = r["role_raw"].strip().casefold()

    if role in {"", "author", "original author"}:
        name = r["author_name"].strip()
        if name:
            primary.setdefault(gid, set()).add(name)


out = []

for _, r in x.iterrows():

    target_ol = norm(r["ol_author_name"])

    author_records = []

    for key in r["author_keys"].split(";"):
        key = key.strip()
        rec = cache.get(key)

        if not rec:
            continue

        core = {
            norm(rec.get("name", "")),
            norm(rec.get("personal_name", "")),
        }
        core.discard("")

        if target_ol in core:
            author_records.append((key, rec))

    if len(author_records) != 1:
        out.append({
            "ol_work_key": r["ol_work_key"],
            "ol_title": r["ol_title"],
            "ol_author_name": r["ol_author_name"],
            "goodreads_work_id": r["goodreads_work_id"],
            "gr_primary_contributors":
                " | ".join(sorted(primary.get(
                    r["goodreads_work_id"], set()
                ))),
            "ol_author_key": "",
            "identity_status": "OL_AUTHOR_KEY_AMBIGUOUS",
            "matched_gr_name": "",
            "matched_ol_name_raw": "",
            "ol_evidence_type": "",
        })
        continue

    key, rec = author_records[0]

    direct_raw = [
        rec.get("name", ""),
        rec.get("personal_name", ""),
    ]

    aliases_raw = rec.get("alternate_names") or []

    direct_map = {
        norm(v): v
        for v in direct_raw
        if norm(v)
    }

    alias_map = {}

    for v in aliases_raw:
        if norm(v):
            alias_map.setdefault(norm(v), []).append(v)

    gr_names = sorted(primary.get(
        r["goodreads_work_id"], set()
    ))

    found = None

    for g in gr_names:
        ng = norm(g)

        if ng in direct_map:
            found = (
                "DIRECT_NAME_MATCH",
                g,
                direct_map[ng],
                "OL_NAME_OR_PERSONAL_NAME",
            )
            break

        if ng in alias_map:
            raws = alias_map[ng]
            raw = " | ".join(raws)

            marker = raw.casefold()

            if (
                "pseud" in marker
                or "pen name" in marker
            ):
                etype = "OL_EXPLICIT_PSEUDONYM_ALIAS"
            else:
                etype = "OL_ALTERNATE_NAME"

            found = (
                "OL_ALIAS_MATCH",
                g,
                raw,
                etype,
            )
            break

    if found:
        status, gr_name, ol_raw, etype = found
    else:
        status = "UNRESOLVED"
        gr_name = ""
        ol_raw = ""
        etype = ""

    out.append({
        "ol_work_key": r["ol_work_key"],
        "ol_title": r["ol_title"],
        "ol_author_name": r["ol_author_name"],
        "goodreads_work_id": r["goodreads_work_id"],
        "gr_primary_contributors": " | ".join(gr_names),
        "ol_author_key": key,
        "identity_status": status,
        "matched_gr_name": gr_name,
        "matched_ol_name_raw": ol_raw,
        "ol_evidence_type": etype,
    })


df = pd.DataFrame(out)

df.to_csv(
    OUT,
    sep="\t",
    index=False,
)

print("=== IDENTITY STATUS ===")
print(df["identity_status"].value_counts().to_string())

print("\n=== EVIDENCE TYPE ===")
print(
    df.loc[
        df["identity_status"] != "UNRESOLVED",
        "ol_evidence_type",
    ].value_counts().to_string()
)

print("\noutput:", OUT)
