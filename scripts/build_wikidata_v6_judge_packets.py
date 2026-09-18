#!/usr/bin/env python3

import json
import re
from pathlib import Path

V5_PACKETS = Path(
    "derived/wikidata_production/"
    "judge_v5_random100_20260916/stage2_packets.jsonl"
)

EDITION_JSONL = Path(
    "derived/wikidata_production/"
    "ol_edition_random100_coverage_20260918/"
    "selected_editions.jsonl"
)

OUTDIR = Path(
    "derived/wikidata_production/"
    "judge_v6_random100_20260918"
)

OUT = OUTDIR / "stage2_packets.jsonl"

OUTDIR.mkdir(parents=True, exist_ok=True)


def text_value(v):
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return str(v.get("value", ""))
    if isinstance(v, list):
        return " | ".join(map(str, v))
    return str(v)


# Conservative source-work relations only.
SOURCE_PATTERNS = [
    (
        "translation_of",
        re.compile(
            r"\btranslation\s+of\s+(.+?)(?=(?:[\.;\n]|$))",
            re.I,
        ),
    ),
    (
        "abridged_from",
        re.compile(
            r"\babridged\s+from\s+(.+?)(?=(?:\s+by\b|[\.;\n]|$))",
            re.I,
        ),
    ),
    (
        "adapted_from",
        re.compile(
            r"\badapted\s+from\s+(.+?)(?=(?:\s+by\b|[\.;\n]|$))",
            re.I,
        ),
    ),
    (
        "based_on",
        re.compile(
            r"\bbased\s+on\s+(.+?)(?=(?:\s+with\b|;|\n|$))",
            re.I,
        ),
    ),
]

# These may indicate edition/responsibility information,
# but do NOT by themselves establish a different conceptual work.
RESP_PAT = re.compile(
    r"\b("
    r"translat\w*|"
    r"abridg\w*|"
    r"adapt\w*|"
    r"based\s+on|"
    r"version\s+of|"
    r"retold|"
    r"revised|"
    r"edited"
    r")\b",
    re.I,
)


def extract_source_relations(ed):
    found = []

    for field in ["notes", "by_statement", "full_title"]:
        txt = " ".join(text_value(ed.get(field)).split())

        if not txt:
            continue

        for relation, pat in SOURCE_PATTERNS:
            for m in pat.finditer(txt):
                found.append({
                    "relation": relation,
                    "source_work_text": " ".join(m.group(1).split()).rstrip(" .;"),
                    "field": field,
                    "evidence": " ".join(m.group(0).split()),
                })

    return found


def extract_responsibility_notes(ed):
    found = []

    for field in [
        "title",
        "full_title",
        "subtitle",
        "by_statement",
        "notes",
    ]:
        txt = " ".join(text_value(ed.get(field)).split())

        if txt and RESP_PAT.search(txt):
            found.append({
                "field": field,
                "text": txt,
            })

    return found


# ------------------------------------------------------------
# edition evidence by target
# ------------------------------------------------------------

edition_by_target = {}

with EDITION_JSONL.open(encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue

        x = json.loads(line)
        tid = x["target_id"]
        ed = x["edition"]

        item = edition_by_target.setdefault(
            tid,
            {
                "selection_scope": x["selection_scope"],
                "source_relations": [],
                "work_titles": [],
                "responsibility_notes": [],
            },
        )

        item["source_relations"].extend(
            extract_source_relations(ed)
        )

        for wt in ed.get("work_titles") or []:
            item["work_titles"].append(str(wt))

        item["responsibility_notes"].extend(
            extract_responsibility_notes(ed)
        )


def dedupe_dicts(rows):
    seen = set()
    out = []

    for r in rows:
        k = json.dumps(
            r,
            ensure_ascii=False,
            sort_keys=True,
        )

        if k not in seen:
            seen.add(k)
            out.append(r)

    return out


for tid, e in edition_by_target.items():
    e["source_relations"] = dedupe_dicts(
        e["source_relations"]
    )

    e["work_titles"] = list(
        dict.fromkeys(e["work_titles"])
    )

    e["responsibility_notes"] = dedupe_dicts(
        e["responsibility_notes"]
    )

    # Keep packets small.
    e["source_relations"] = e["source_relations"][:10]
    e["work_titles"] = e["work_titles"][:10]
    e["responsibility_notes"] = (
        e["responsibility_notes"][:10]
    )


# ------------------------------------------------------------
# enrich frozen v5 packets
# ------------------------------------------------------------

n = 0
with_evidence = 0
with_source_relation = 0

with V5_PACKETS.open(encoding="utf-8") as src, \
     OUT.open("w", encoding="utf-8") as dst:

    for line in src:
        if not line.strip():
            continue

        p = json.loads(line)
        tid = p["target_id"]

        e = edition_by_target.get(tid)

        if e:
            has_useful = bool(
                e["source_relations"]
                or e["work_titles"]
                or e["responsibility_notes"]
            )

            if has_useful:
                p["openlibrary_edition_evidence"] = e
                with_evidence += 1

            if e["source_relations"]:
                with_source_relation += 1

        dst.write(
            json.dumps(
                p,
                ensure_ascii=False,
            )
            + "\n"
        )

        n += 1


print("packets:", n)
print(
    "with edition evidence:",
    with_evidence,
)
print(
    "with explicit source relation:",
    with_source_relation,
)
print("saved:", OUT)
