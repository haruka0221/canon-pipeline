#!/usr/bin/env python3

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

BASE = ROOT / "derived/openlibrary_author_identity_cache_v1.jsonl"
REDIR = ROOT / "derived/openlibrary_author_redirect_resolution_v1.jsonl"
BATCH = ROOT / "derived/goodreads_llm_review_batch1_v3.tsv"
RES = ROOT / "derived/goodreads_resolution_status_v5.tsv"
OLD = ROOT / "derived/goodreads_ol_author_identity_evidence_v1.tsv"
OUT = ROOT / "derived/goodreads_ol_author_identity_evidence_v2.tsv"


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(
        c for c in s
        if not unicodedata.combining(c)
    )
    s = s.casefold()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^\w]+", " ", s, flags=re.UNICODE)
    return " ".join(s.split())


def primary_names(s):
    out = set()

    for part in str(s).split("|"):
        part = part.strip()
        if not part:
            continue

        m = re.match(
            r"^(.*?)\s*\[([^\]]*)\]\s*$",
            part,
        )

        if m:
            name = m.group(1).strip()
            role = m.group(2).strip()

            if role == "<EMPTY>":
                role = ""
        else:
            name = part
            role = ""

        if role.casefold() in {
            "",
            "author",
            "original author",
        }:
            if name:
                out.add(name)

    return sorted(out)


# Base OL Author cache.
cache = {}

with BASE.open(encoding="utf-8") as f:
    for line in f:
        rec = json.loads(line)
        cache[rec["author_key"]] = {
            **rec,
            "canonical_author_key": rec["author_key"],
            "redirect_applied": "0",
        }


# Redirect overlay:
# source key gets identity fields from its final canonical Author entity.
with REDIR.open(encoding="utf-8") as f:
    for line in f:
        rec = json.loads(line)

        assert (
            rec["resolution_status"]
            == "REDIRECT_RESOLVED_AUTHOR"
        )

        source = rec["source_author_key"]

        cache[source] = {
            "author_key": source,
            "status": "REDIRECT_RESOLVED_AUTHOR",
            "name": rec["name"],
            "personal_name": rec["personal_name"],
            "alternate_names": rec["alternate_names"],
            "canonical_author_key": rec["final_author_key"],
            "redirect_applied": "1",
        }


batch = pd.read_csv(
    BATCH,
    sep="\t",
    dtype=str,
).fillna("")

res = pd.read_csv(
    RES,
    sep="\t",
    dtype=str,
).fillna("")

old = pd.read_csv(
    OLD,
    sep="\t",
    dtype=str,
).fillna("")

x = batch.merge(
    res[["work_key", "author_keys"]],
    left_on="ol_work_key",
    right_on="work_key",
    how="left",
    validate="one_to_one",
)

out = []

for _, r in x.iterrows():

    target_ol = norm(r["ol_author_name"])

    # canonical key -> matching source records
    matched_by_canonical = {}

    for key in re.split(r"[;|]", r["author_keys"]):
        key = key.strip()

        if not key:
            continue

        rec = cache.get(key)

        if not rec:
            continue

        core = {
            norm(rec.get("name", "")),
            norm(rec.get("personal_name", "")),
        }
        core.discard("")

        if target_ol not in core:
            continue

        canonical = rec["canonical_author_key"]

        matched_by_canonical.setdefault(
            canonical,
            [],
        ).append((key, rec))

    gr_names = primary_names(
        r["goodreads_contributors"]
    )

    if len(matched_by_canonical) != 1:
        out.append({
            "ol_work_key": r["ol_work_key"],
            "ol_title": r["ol_title"],
            "ol_author_name": r["ol_author_name"],
            "goodreads_work_id": r["goodreads_work_id"],
            "gr_primary_contributors":
                " | ".join(gr_names),
            "ol_author_key": "",
            "ol_author_source_keys": "",
            "redirect_applied": "",
            "identity_status":
                "OL_AUTHOR_KEY_AMBIGUOUS",
            "matched_gr_name": "",
            "matched_ol_name_raw": "",
            "ol_evidence_type": "",
        })
        continue

    canonical, records = next(
        iter(matched_by_canonical.items())
    )

    # All records here represent the same canonical person.
    source_keys = sorted({
        key for key, _ in records
    })

    redirect_applied = any(
        rec.get("redirect_applied") == "1"
        for _, rec in records
    )

    direct_map = {}
    alias_map = {}

    for _, rec in records:

        for v in [
            rec.get("name", ""),
            rec.get("personal_name", ""),
        ]:
            if norm(v):
                direct_map.setdefault(
                    norm(v),
                    [],
                ).append(v)

        for v in rec.get("alternate_names", []) or []:
            if norm(v):
                alias_map.setdefault(
                    norm(v),
                    [],
                ).append(v)

    found = None

    for g in gr_names:
        ng = norm(g)

        if ng in direct_map:
            found = (
                "DIRECT_NAME_MATCH",
                g,
                " | ".join(
                    sorted(set(direct_map[ng]))
                ),
                "OL_NAME_OR_PERSONAL_NAME",
            )
            break

        if ng in alias_map:
            raws = sorted(set(alias_map[ng]))
            raw = " | ".join(raws)

            marker = raw.casefold()

            if (
                "pseud" in marker
                or "pen name" in marker
            ):
                etype = (
                    "OL_EXPLICIT_PSEUDONYM_ALIAS"
                )
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
        "gr_primary_contributors":
            " | ".join(gr_names),
        "ol_author_key": canonical,
        "ol_author_source_keys":
            ";".join(source_keys),
        "redirect_applied":
            "1" if redirect_applied else "0",
        "identity_status": status,
        "matched_gr_name": gr_name,
        "matched_ol_name_raw": ol_raw,
        "ol_evidence_type": etype,
    })


df = pd.DataFrame(out)

assert len(df) == 1122
assert df["ol_work_key"].is_unique

df.to_csv(
    OUT,
    sep="\t",
    index=False,
)


print("=== V2 IDENTITY STATUS ===")
print(
    df["identity_status"]
    .value_counts()
    .to_string()
)

print("\n=== REDIRECT USED ===")
print(
    df["redirect_applied"]
    .value_counts()
    .to_string()
)


cmp = old[
    [
        "ol_work_key",
        "identity_status",
    ]
].merge(
    df[
        [
            "ol_work_key",
            "identity_status",
            "matched_gr_name",
            "matched_ol_name_raw",
            "redirect_applied",
        ]
    ],
    on="ol_work_key",
    suffixes=("_v1", "_v2"),
    validate="one_to_one",
)

changed = cmp[
    cmp["identity_status_v1"]
    != cmp["identity_status_v2"]
].copy()

print("\n=== V1 -> V2 CHANGES ===")
print("changed rows:", len(changed))

print(
    pd.crosstab(
        changed["identity_status_v1"],
        changed["identity_status_v2"],
    ).to_string()
)

show = changed.merge(
    batch[
        [
            "ol_work_key",
            "ol_title",
            "ol_author_name",
            "goodreads_contributors",
        ]
    ],
    on="ol_work_key",
    how="left",
)

print("\n=== CHANGED CASES ===")
print(
    show[
        [
            "ol_work_key",
            "ol_title",
            "ol_author_name",
            "identity_status_v1",
            "identity_status_v2",
            "matched_gr_name",
            "matched_ol_name_raw",
            "redirect_applied",
            "goodreads_contributors",
        ]
    ].to_string(index=False)
)

print("\noutput:", OUT)
