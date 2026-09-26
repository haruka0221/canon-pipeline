#!/usr/bin/env python3

import bz2
import csv
import json
import time
from pathlib import Path

import orjson

from wikidata_resolver_production import (
    normalize_author,
    normalize_title,
)

ROOT = Path(__file__).resolve().parents[1]

DUMP = Path(
    "/media/hdd1/user/tsutsui/wikidata/"
    "wikidata-20260805-all.json.bz2"
)

TARGETS = (
    ROOT
    / "derived/goodreads_wikidata_missing_gr_names_v1.tsv"
)

COMPACT_OUT = (
    ROOT
    / "derived/goodreads_wikidata_person_name_index_v1.tsv"
)

SOURCE_DIR = (
    Path.home()
    / "research-data/goodreads-wikidata-person-layer/2026-08-05"
)

RAW_OUT = (
    SOURCE_DIR
    / "goodreads_wikidata_person_items_raw_v1.jsonl"
)

SUMMARY_OUT = (
    SOURCE_DIR
    / "goodreads_wikidata_person_items_raw_v1_summary.json"
)

MISSING_OUT = (
    SOURCE_DIR
    / "goodreads_wikidata_person_names_missing_v1.tsv"
)


def keys_for_name(s):
    if not s:
        return set()

    return {
        normalize_title(s),
        normalize_title(normalize_author(s)),
    } - {""}


def lang_value(mapping, lang):
    x = mapping.get(lang)

    if isinstance(x, dict):
        return x.get("value", "") or ""

    return ""


def lang_aliases(ent, lang):
    return [
        x.get("value", "")
        for x in ent.get("aliases", {}).get(lang, [])
        if x.get("value")
    ]


def claim_values(ent, prop):
    """
    Flatten common Wikidata datavalue types for compact output.
    Full claims remain preserved in RAW_OUT.
    """
    out = []
    seen = set()

    for claim in ent.get("claims", {}).get(prop, []):
        try:
            v = claim["mainsnak"]["datavalue"]["value"]
        except Exception:
            continue

        value = None

        if isinstance(v, str):
            value = v

        elif isinstance(v, dict):
            if v.get("id"):
                value = v["id"]
            elif v.get("time"):
                value = v["time"]
            elif v.get("text"):
                value = v["text"]
            elif v.get("amount"):
                value = v["amount"]

        if value is not None:
            value = str(value)

            if value not in seen:
                seen.add(value)
                out.append(value)

    return out


def is_human(ent):
    return "Q5" in claim_values(ent, "P31")


def wikipedia_title(ent, key):
    x = ent.get("sitelinks", {}).get(key)

    if isinstance(x, dict):
        return x.get("title", "") or ""

    return ""


# ------------------------------------------------------------
# Load 781 target Goodreads names
# ------------------------------------------------------------

target_names = []

with TARGETS.open(encoding="utf-8") as f:
    for r in csv.DictReader(f, delimiter="\t"):
        name = (r.get("name") or "").strip()

        if name:
            target_names.append(name)

target_names = sorted(set(target_names))

key_to_targets = {}

for name in target_names:
    for key in keys_for_name(name):
        key_to_targets.setdefault(key, set()).add(name)

target_keys = set(key_to_targets)

print("target names:", len(target_names))
print("normalized target keys:", len(target_keys))
print("dump:", DUMP)
print("compact output:", COMPACT_OUT)
print("raw output:", RAW_OUT)

if not DUMP.exists():
    raise FileNotFoundError(DUMP)

if not TARGETS.exists():
    raise FileNotFoundError(TARGETS)


# ------------------------------------------------------------
# Output preparation
# Use temporary files so partial runs are not mistaken
# for completed outputs.
# ------------------------------------------------------------

SOURCE_DIR.mkdir(parents=True, exist_ok=True)
COMPACT_OUT.parent.mkdir(parents=True, exist_ok=True)

compact_tmp = COMPACT_OUT.with_suffix(
    COMPACT_OUT.suffix + ".tmp"
)
raw_tmp = RAW_OUT.with_suffix(
    RAW_OUT.suffix + ".tmp"
)

matched_target_names = set()
matched_qids = set()

q_items = 0
human_items = 0
bad_json = 0
compact_rows = 0

started = time.time()


# ------------------------------------------------------------
# One full dump scan
# ------------------------------------------------------------

with compact_tmp.open(
    "w",
    encoding="utf-8",
    newline="",
) as compact_f, raw_tmp.open(
    "w",
    encoding="utf-8",
) as raw_f:

    fieldnames = [
        "target_name",
        "qid",
        "wikidata_label",
        "label_en",
        "label_mul",
        "description_en",
        "description_mul",
        "matched_name",
        "matched_source",
        "aliases_en",
        "aliases_mul",
        "P106_occupation_qids",
        "P569_birth",
        "P570_death",
        "P742_pseudonym",
        "P1477_birth_name",
        "enwiki_title",
        "jawiki_title",
        "source_snapshot",
    ]

    writer = csv.DictWriter(
        compact_f,
        fieldnames=fieldnames,
        delimiter="\t",
    )
    writer.writeheader()

    with bz2.open(DUMP, "rb") as fin:

        for raw in fin:

            line = raw.strip()

            if not line or line in (b"[", b"]"):
                continue

            if line.endswith(b","):
                line = line[:-1]

            try:
                ent = orjson.loads(line)
            except Exception:
                bad_json += 1
                continue

            qid = ent.get("id", "")

            if (
                not isinstance(qid, str)
                or not qid.startswith("Q")
            ):
                continue

            q_items += 1

            if not is_human(ent):
                if q_items % 1_000_000 == 0:
                    elapsed = time.time() - started

                    print(
                        f"scanned={q_items:,} "
                        f"humans={human_items:,} "
                        f"matched_qids={len(matched_qids):,} "
                        f"target_names_hit={len(matched_target_names):,} "
                        f"elapsed={elapsed/3600:.2f}h",
                        flush=True,
                    )

                continue

            human_items += 1

            labels = ent.get("labels", {})
            descriptions = ent.get("descriptions", {})

            label_en = lang_value(labels, "en")
            label_mul = lang_value(labels, "mul")

            description_en = lang_value(
                descriptions, "en"
            )
            description_mul = lang_value(
                descriptions, "mul"
            )

            aliases_en = lang_aliases(ent, "en")
            aliases_mul = lang_aliases(ent, "mul")

            p742 = claim_values(ent, "P742")
            p1477 = claim_values(ent, "P1477")

            searchable = []

            if label_en:
                searchable.append(
                    ("label_en", label_en)
                )

            if label_mul:
                searchable.append(
                    ("label_mul", label_mul)
                )

            searchable.extend(
                ("alias_en", x)
                for x in aliases_en
            )

            searchable.extend(
                ("alias_mul", x)
                for x in aliases_mul
            )

            searchable.extend(
                ("P742_pseudonym", x)
                for x in p742
            )

            searchable.extend(
                ("P1477_birth_name", x)
                for x in p1477
            )

            # target_name -> first matching Wikidata string/source
            target_hits = {}

            for source, value in searchable:

                for key in keys_for_name(value):

                    if key not in target_keys:
                        continue

                    for target_name in key_to_targets[key]:

                        target_hits.setdefault(
                            target_name,
                            (value, source),
                        )

            if not target_hits:
                continue

            matched_qids.add(qid)
            matched_target_names.update(
                target_hits.keys()
            )

            wikidata_label = (
                label_en
                or label_mul
            )

            p106 = claim_values(ent, "P106")
            p569 = claim_values(ent, "P569")
            p570 = claim_values(ent, "P570")

            for target_name, (
                matched_name,
                matched_source,
            ) in sorted(target_hits.items()):

                writer.writerow({
                    "target_name":
                        target_name,

                    "qid":
                        qid,

                    "wikidata_label":
                        wikidata_label,

                    "label_en":
                        label_en,

                    "label_mul":
                        label_mul,

                    "description_en":
                        description_en,

                    "description_mul":
                        description_mul,

                    "matched_name":
                        matched_name,

                    "matched_source":
                        matched_source,

                    "aliases_en":
                        " | ".join(aliases_en),

                    "aliases_mul":
                        " | ".join(aliases_mul),

                    "P106_occupation_qids":
                        "|".join(p106),

                    "P569_birth":
                        "|".join(p569),

                    "P570_death":
                        "|".join(p570),

                    "P742_pseudonym":
                        " | ".join(p742),

                    "P1477_birth_name":
                        " | ".join(p1477),

                    "enwiki_title":
                        wikipedia_title(
                            ent, "enwiki"
                        ),

                    "jawiki_title":
                        wikipedia_title(
                            ent, "jawiki"
                        ),

                    "source_snapshot":
                        "2026-08-05",
                })

                compact_rows += 1

            # ------------------------------------------------
            # Critical: preserve the complete Wikidata item.
            # One raw item per matched QID.
            # ------------------------------------------------

            wrapper = {
                "source": "wikidata",
                "source_namespace": "item",
                "source_id": qid,
                "snapshot_date": "2026-08-05",
                "matched_target_names":
                    sorted(target_hits.keys()),
                "record": ent,
            }

            raw_f.write(
                json.dumps(
                    wrapper,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )

            if q_items % 1_000_000 == 0:
                elapsed = time.time() - started

                print(
                    f"scanned={q_items:,} "
                    f"humans={human_items:,} "
                    f"matched_qids={len(matched_qids):,} "
                    f"target_names_hit={len(matched_target_names):,} "
                    f"elapsed={elapsed/3600:.2f}h",
                    flush=True,
                )


# ------------------------------------------------------------
# Finished successfully: promote temp outputs
# ------------------------------------------------------------

compact_tmp.replace(COMPACT_OUT)
raw_tmp.replace(RAW_OUT)

missing_names = sorted(
    set(target_names)
    - matched_target_names
)

with MISSING_OUT.open(
    "w",
    encoding="utf-8",
    newline="",
) as f:

    w = csv.writer(
        f,
        delimiter="\t",
    )

    w.writerow(["name"])

    for name in missing_names:
        w.writerow([name])


elapsed = time.time() - started

summary = {
    "source": "Wikidata",
    "snapshot_date": "2026-08-05",
    "source_dump": str(DUMP),
    "target_file": str(TARGETS),
    "target_names": len(target_names),
    "normalized_target_keys": len(target_keys),
    "target_names_with_hit":
        len(matched_target_names),
    "target_names_without_hit":
        len(missing_names),
    "matched_unique_qids":
        len(matched_qids),
    "compact_match_rows":
        compact_rows,
    "q_items_scanned":
        q_items,
    "human_items_scanned":
        human_items,
    "bad_json_lines":
        bad_json,
    "elapsed_seconds":
        elapsed,
    "compact_output":
        str(COMPACT_OUT),
    "raw_output":
        str(RAW_OUT),
    "missing_names_output":
        str(MISSING_OUT),
}

SUMMARY_OUT.write_text(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


print("\n=== COMPLETE ===")
print("target names:", len(target_names))
print(
    "target names with hit:",
    len(matched_target_names),
)
print(
    "target names without hit:",
    len(missing_names),
)
print(
    "matched unique QIDs:",
    len(matched_qids),
)
print(
    "compact match rows:",
    compact_rows,
)
print(
    "Q-items scanned:",
    f"{q_items:,}",
)
print(
    "human items scanned:",
    f"{human_items:,}",
)
print("bad JSON:", bad_json)
print(
    "elapsed hours:",
    round(elapsed / 3600, 3),
)
print("compact:", COMPACT_OUT)
print("raw:", RAW_OUT)
print("missing:", MISSING_OUT)
print("summary:", SUMMARY_OUT)
