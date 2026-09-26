#!/usr/bin/env python3

import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

GR = ROOT / "derived/goodreads_wikidata_author_identity_evidence_v1.tsv"
CW = ROOT / "derived/crosswalks/work_to_wikidata.parquet"

ENT = (
    Path.home()
    / "research-data/wikidata-source-layer/2026-08-05"
    / "wikidata_entities.parquet"
)

OUT = ROOT / "derived/goodreads_wikidata_work_author_evidence_v1.tsv"


def norm(s):
    s = str(s or "").strip()

    # "Dixon, Thomas" → "Thomas Dixon"
    if "," in s:
        left, right = s.split(",", 1)
        if left.strip() and right.strip():
            s = f"{right.strip()} {left.strip()}"

    s = unicodedata.normalize("NFKD", s)
    s = "".join(
        c for c in s
        if not unicodedata.combining(c)
    )
    s = s.casefold()
    s = re.sub(r"[^a-z0-9]+", " ", s)

    return " ".join(s.split())


def as_list(v):
    if v is None:
        return []

    if isinstance(v, np.ndarray):
        return [str(x) for x in v if str(x)]

    if isinstance(v, (list, tuple)):
        return [str(x) for x in v if str(x)]

    try:
        if pd.isna(v):
            return []
    except Exception:
        pass

    return [str(v)] if str(v) else []


# ------------------------------------------------------------
# 1. Goodreads difficult cases
# ------------------------------------------------------------

gr = pd.read_csv(
    GR,
    sep="\t",
    dtype=str,
).fillna("")

gr["ol_work_id"] = (
    gr["ol_work_key"]
    .str.replace(r"^/works/", "", regex=True)
)


# ------------------------------------------------------------
# 2. OL → Wikidata work crosswalk
# ------------------------------------------------------------

cw = pd.read_parquet(CW).fillna("")

x = gr.merge(
    cw[
        [
            "ol_work_id",
            "wikidata_qid",
            "decision",
        ]
    ],
    on="ol_work_id",
    how="left",
)

x = x[
    (x["decision"] == "MATCH")
    & (x["wikidata_qid"] != "")
].copy()

print("rows with Wikidata work MATCH:", len(x))


# ------------------------------------------------------------
# 3. Wikidata source layer
# ------------------------------------------------------------

ent = pd.read_parquet(
    ENT,
    columns=[
        "qid",
        "label_en_effective",
        "aliases_en_effective",
        "P50",
    ],
)

entities = {
    r["qid"]: r
    for _, r in ent.iterrows()
}


def person_names(qid):
    r = entities.get(qid)

    if r is None:
        return []

    names = []

    label = r["label_en_effective"]
    if isinstance(label, str) and label:
        names.append(label)

    names.extend(
        as_list(r["aliases_en_effective"])
    )

    # deterministic deduplication
    return list(dict.fromkeys(names))


# ------------------------------------------------------------
# 4. Compare OL / Goodreads names with P50 people
# ------------------------------------------------------------

out = []

for _, r in x.iterrows():

    work_qid = r["wikidata_qid"]
    work = entities.get(work_qid)

    if work is None:
        continue

    p50_qids = as_list(work["P50"])

    ol_name = r["ol_author_name"]
    ol_norm = norm(ol_name)

    gr_names = [
        z.strip()
        for z in r["gr_primary_contributors"].split("|")
        if z.strip()
    ]

    gr_norms = {
        norm(z): z
        for z in gr_names
        if norm(z)
    }

    ol_hits = set()
    gr_hits = set()
    labels = []

    for pqid in p50_qids:

        person = entities.get(pqid)

        if person is None:
            continue

        label = person["label_en_effective"]

        if isinstance(label, str) and label:
            labels.append(f"{pqid}:{label}")
        else:
            labels.append(pqid)

        names = person_names(pqid)

        name_norms = {
            norm(z)
            for z in names
            if norm(z)
        }

        if ol_norm and ol_norm in name_norms:
            ol_hits.add(pqid)

        if set(gr_norms) & name_norms:
            gr_hits.add(pqid)

    shared = ol_hits & gr_hits

    if shared:
        status = "P50_SUPPORTS_BOTH_SAME_PERSON"

    elif ol_hits and gr_hits:
        status = "P50_SUPPORTS_BOTH_DIFFERENT_QIDS"

    elif ol_hits:
        status = "P50_SUPPORTS_OL_ONLY"

    elif gr_hits:
        status = "P50_SUPPORTS_GR_ONLY"

    else:
        status = "P50_NO_EXACT_NAME_SUPPORT"

    out.append({
        "ol_work_key":
            r["ol_work_key"],

        "ol_title":
            r["ol_title"],

        "ol_author_name":
            ol_name,

        "gr_primary_contributors":
            r["gr_primary_contributors"],

        "goodreads_work_id":
            r["goodreads_work_id"],

        "wikidata_work_qid":
            work_qid,

        "wikidata_p50_qids":
            "|".join(p50_qids),

        "wikidata_p50_people":
            " | ".join(labels),

        "ol_matching_p50_qids":
            "|".join(sorted(ol_hits)),

        "gr_matching_p50_qids":
            "|".join(sorted(gr_hits)),

        "shared_p50_qids":
            "|".join(sorted(shared)),

        "work_author_evidence_status":
            status,
    })


result = pd.DataFrame(out)

result.to_csv(
    OUT,
    sep="\t",
    index=False,
)


print("\n=== WORK → P50 EVIDENCE ===")
print(
    result["work_author_evidence_status"]
    .value_counts()
    .to_string()
)


print("\n=== SAME PERSON SAMPLE ===")
cols = [
    "ol_title",
    "ol_author_name",
    "gr_primary_contributors",
    "wikidata_work_qid",
    "wikidata_p50_people",
]

print(
    result[
        result["work_author_evidence_status"]
        == "P50_SUPPORTS_BOTH_SAME_PERSON"
    ][cols]
    .head(20)
    .to_string(index=False)
)


print("\n=== OL ONLY SAMPLE ===")
print(
    result[
        result["work_author_evidence_status"]
        == "P50_SUPPORTS_OL_ONLY"
    ][cols]
    .head(20)
    .to_string(index=False)
)

print("\noutput:", OUT)
