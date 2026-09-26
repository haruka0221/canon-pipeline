#!/usr/bin/env python3

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

CACHE_V1 = ROOT / "derived/openlibrary_author_identity_cache_v1.jsonl"
CACHE_SUPP = ROOT / "derived/openlibrary_author_identity_cache_outlang28_v1.jsonl"
TRANSFER = ROOT / "derived/goodreads_outlang_singleton_full28_v1.tsv"
RES = ROOT / "derived/goodreads_resolution_status_v4.tsv"
OUT = ROOT / "derived/goodreads_ol_author_identity_outlang28_v1.tsv"


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.casefold()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^\w]+", " ", s, flags=re.UNICODE)
    return " ".join(s.split())


def parse_primary_contributors(s):
    names = set()

    for part in str(s).split("|"):
        part = part.strip()
        if not part:
            continue

        m = re.match(r"^(.*?)\s*\[([^\]]*)\]\s*$", part)

        if m:
            name = m.group(1).strip()
            role = m.group(2).strip()

            if role == "<EMPTY>":
                role = ""
        else:
            name = part
            role = ""

        if role.casefold() in {"", "author", "original author"}:
            if name:
                names.add(name)

    return sorted(names)


cache = {}

for cache_path in [CACHE_V1, CACHE_SUPP]:
    with cache_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            key = r["author_key"]
            if key in cache:
                raise ValueError(
                    f"duplicate author_key across caches: {key}"
                )
            cache[key] = r

assert len(cache) == 1069


transfer = pd.read_csv(
    TRANSFER,
    sep="\t",
    dtype=str,
).fillna("")

res = pd.read_csv(
    RES,
    sep="\t",
    dtype=str,
).fillna("")

x = transfer.merge(
    res[["work_key", "author_keys"]],
    on="work_key",
    how="left",
    validate="one_to_one",
)

assert len(x) == 28

out = []

for _, r in x.iterrows():

    target_ol = norm(r["author_name"])

    author_records = []

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

        if target_ol in core:
            author_records.append((key, rec))

    gr_names = parse_primary_contributors(
        r["goodreads_contributors"]
    )

    if len(author_records) != 1:
        out.append({
            "ol_work_key": r["work_key"],
            "ol_title": r["title"],
            "ol_author_name": r["author_name"],
            "goodreads_work_id": r["goodreads_work_id"],
            "gr_primary_contributors": " | ".join(gr_names),
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

            if "pseud" in marker or "pen name" in marker:
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
        # Second-stage conservative compatibility check, using the same
        # surname + first-given-name rule as AUTO_MATCH_HIGH.
        def person_parts(name):
            t = unicodedata.normalize(
                "NFKD",
                str(name or "").casefold(),
            )
            t = "".join(
                c for c in t
                if not unicodedata.combining(c)
            )
            t = re.sub(r"[^\w\s,]", " ", t)
            t = re.sub(r"\s+", " ", t).strip()

            if not t:
                return "", []

            if "," in t:
                left, right = t.split(",", 1)
                surname = (
                    left.strip().split()[0]
                    if left.strip()
                    else ""
                )
                given = right.strip().split()
            else:
                parts = t.replace(",", " ").split()
                if not parts:
                    return "", []
                surname = parts[-1]
                given = parts[:-1]

            return surname, given

        def initial_compatible(a, b):
            if not a or not b:
                return False
            return (
                a == b
                or (len(a) == 1 and b.startswith(a))
                or (len(b) == 1 and a.startswith(b))
            )

        def compatible(a, b):
            sa, ga = person_parts(a)
            sb, gb = person_parts(b)

            if not sa or not sb or sa != sb:
                return False

            return (
                bool(ga)
                and bool(gb)
                and initial_compatible(ga[0], gb[0])
            )

        compat = []

        candidate_ol_names = []

        for v in direct_raw:
            if v:
                candidate_ol_names.append(
                    ("OL_NAME_OR_PERSONAL_NAME", v)
                )

        for v in aliases_raw:
            if v:
                candidate_ol_names.append(
                    ("OL_ALTERNATE_NAME", v)
                )

        for source, ol_name in candidate_ol_names:
            for g in gr_names:
                if compatible(ol_name, g):
                    compat.append(
                        (g, ol_name, source)
                    )

        compat = sorted(set(compat))

        if len(compat) == 1:
            gr_name, ol_raw, etype = compat[0]
            status = "GIVEN_NAME_COMPATIBLE"
        else:
            status = "UNRESOLVED"
            gr_name = ""
            ol_raw = ""
            etype = ""

    out.append({
        "ol_work_key": r["work_key"],
        "ol_title": r["title"],
        "ol_author_name": r["author_name"],
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

print("=== OUT_LANG 28 OL AUTHOR IDENTITY ===")
print(df["identity_status"].value_counts().to_string())

print("\n=== EVIDENCE TYPE ===")
print(
    df.loc[
        df["identity_status"].isin(
            ["DIRECT_NAME_MATCH", "OL_ALIAS_MATCH"]
        ),
        "ol_evidence_type",
    ].value_counts().to_string()
)

print("\n=== POSITIVE CASES ===")
print(
    df[
        df["identity_status"].isin(
            ["DIRECT_NAME_MATCH", "OL_ALIAS_MATCH"]
        )
    ][
        [
            "ol_work_key",
            "ol_title",
            "ol_author_name",
            "gr_primary_contributors",
            "ol_author_key",
            "identity_status",
            "matched_gr_name",
            "matched_ol_name_raw",
            "ol_evidence_type",
        ]
    ].to_string(index=False)
)

print("\n=== AMBIGUOUS AUTHOR KEY ===")
print(
    df[
        df["identity_status"] == "OL_AUTHOR_KEY_AMBIGUOUS"
    ][
        [
            "ol_work_key",
            "ol_title",
            "ol_author_name",
            "gr_primary_contributors",
        ]
    ].to_string(index=False)
)

assert len(df) == 28

print("\noutput:", OUT)
