import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


BASE = Path.home() / "research-data/wikidata-source-layer/2026-08-05"

RAW = BASE / "wikidata_target_items_raw_v2.jsonl"
SUMMARY = BASE / "extract_v2_summary.json"

OUT = BASE / "wikidata_entities.parquet"
TMP_OUT = BASE / "wikidata_entities.parquet.tmp"
OUT_SUMMARY = BASE / "wikidata_entities_summary.json"
MISSING = BASE / "missing_qids.tsv"


PROPERTIES = [
    # general / work
    "P31",
    "P106",
    "P50",
    "P629",
    "P577",
    "P1476",
    "P407",

    # bibliographic / relation metadata
    "P655",
    "P98",
    "P747",
    "P9745",
    "P123",
    "P291",

    # person identity
    "P569",
    "P570",
    "P742",
    "P1477",
]


def lang_value(obj, lang):
    x = (obj or {}).get(lang)
    if isinstance(x, dict):
        return x.get("value")
    return None


def alias_values(obj, lang):
    result = []
    for x in (obj or {}).get(lang, []) or []:
        if isinstance(x, dict) and x.get("value"):
            value = x["value"]
            if value not in result:
                result.append(value)
    return result


def merge_unique(*lists):
    result = []
    for xs in lists:
        for x in xs or []:
            if x not in result:
                result.append(x)
    return result


def normalize_datavalue(value):
    if value is None:
        return None

    if isinstance(value, str):
        return value

    if isinstance(value, (int, float, bool)):
        return str(value)

    if isinstance(value, dict):
        # Wikidata entity reference
        if value.get("id"):
            return value["id"]

        # time value
        if value.get("time"):
            return value["time"]

        # monolingual text
        if value.get("text") is not None:
            return str(value["text"])

        # quantity
        if value.get("amount") is not None:
            return str(value["amount"])

        # coordinates
        if "latitude" in value and "longitude" in value:
            return f'{value["latitude"]},{value["longitude"]}'

        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    return str(value)


def claim_values(record, prop):
    result = []

    for statement in (record.get("claims") or {}).get(prop, []):
        snak = statement.get("mainsnak") or {}

        if snak.get("snaktype") != "value":
            continue

        datavalue = snak.get("datavalue")
        if not datavalue:
            continue

        value = normalize_datavalue(datavalue.get("value"))

        if value is not None and value not in result:
            result.append(value)

    return result


rows = []

with RAW.open(encoding="utf-8") as f:
    for line_no, line in enumerate(f, 1):
        if not line.strip():
            continue

        wrapper = json.loads(line)
        record = wrapper["record"]

        qid = wrapper["source_id"]

        if record.get("id") != qid:
            raise ValueError(
                f"QID mismatch at line {line_no}: "
                f"{qid} != {record.get('id')}"
            )

        labels = record.get("labels") or {}
        aliases = record.get("aliases") or {}

        label_en = lang_value(labels, "en")
        label_ja = lang_value(labels, "ja")
        label_mul = lang_value(labels, "mul")

        aliases_en = alias_values(aliases, "en")
        aliases_ja = alias_values(aliases, "ja")
        aliases_mul = alias_values(aliases, "mul")

        enwiki = (record.get("sitelinks") or {}).get("enwiki") or {}
        jawiki = (record.get("sitelinks") or {}).get("jawiki") or {}

        row = {
            "qid": qid,

            # Preserve explicit Wikidata language values
            "label_en": label_en,
            "label_ja": label_ja,
            "label_mul": label_mul,

            # Practical values for matching / display
            "label_en_effective": label_en or label_mul,
            "label_ja_effective": label_ja or label_mul,

            "description_en": lang_value(
                record.get("descriptions"), "en"
            ),
            "description_ja": lang_value(
                record.get("descriptions"), "ja"
            ),

            "aliases_en": aliases_en,
            "aliases_ja": aliases_ja,
            "aliases_mul": aliases_mul,

            "aliases_en_effective": merge_unique(
                aliases_en, aliases_mul
            ),
            "aliases_ja_effective": merge_unique(
                aliases_ja, aliases_mul
            ),

            "has_enwiki": bool(enwiki),
            "enwiki_title": enwiki.get("title"),

            "has_jawiki": bool(jawiki),
            "jawiki_title": jawiki.get("title"),

            "modified": record.get("modified"),
            "lastrevid": (
                str(record.get("lastrevid"))
                if record.get("lastrevid") is not None
                else None
            ),

            "source_snapshot": wrapper.get("snapshot_date"),
        }

        for prop in PROPERTIES:
            row[prop] = claim_values(record, prop)

        rows.append(row)


schema_fields = [
    pa.field("qid", pa.string()),

    pa.field("label_en", pa.string()),
    pa.field("label_ja", pa.string()),
    pa.field("label_mul", pa.string()),
    pa.field("label_en_effective", pa.string()),
    pa.field("label_ja_effective", pa.string()),

    pa.field("description_en", pa.string()),
    pa.field("description_ja", pa.string()),

    pa.field("aliases_en", pa.list_(pa.string())),
    pa.field("aliases_ja", pa.list_(pa.string())),
    pa.field("aliases_mul", pa.list_(pa.string())),
    pa.field("aliases_en_effective", pa.list_(pa.string())),
    pa.field("aliases_ja_effective", pa.list_(pa.string())),

    pa.field("has_enwiki", pa.bool_()),
    pa.field("enwiki_title", pa.string()),

    pa.field("has_jawiki", pa.bool_()),
    pa.field("jawiki_title", pa.string()),

    pa.field("modified", pa.string()),
    pa.field("lastrevid", pa.string()),
    pa.field("source_snapshot", pa.string()),
]

for prop in PROPERTIES:
    schema_fields.append(
        pa.field(prop, pa.list_(pa.string()))
    )

schema = pa.schema(schema_fields)
table = pa.Table.from_pylist(rows, schema=schema)


# Write safely to temporary file first
pq.write_table(
    table,
    TMP_OUT,
    compression="zstd",
)

TMP_OUT.replace(OUT)


# Missing QIDs
summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
missing_qids = summary.get("missing_qid_list", [])

with MISSING.open("w", encoding="utf-8") as f:
    f.write("qid\n")
    for qid in missing_qids:
        f.write(qid + "\n")


has_label_en = sum(
    1 for r in rows if r["label_en"] is not None
)
has_label_mul = sum(
    1 for r in rows if r["label_mul"] is not None
)
has_label_en_effective = sum(
    1 for r in rows if r["label_en_effective"] is not None
)


report = {
    "source_raw": str(RAW),
    "output_parquet": str(OUT),
    "rows": table.num_rows,
    "columns": table.num_columns,
    "missing_qids": len(missing_qids),
    "properties": PROPERTIES,
    "label_coverage": {
        "explicit_en": has_label_en,
        "mul": has_label_mul,
        "effective_en": has_label_en_effective,
    },
}

OUT_SUMMARY.write_text(
    json.dumps(report, ensure_ascii=False, indent=2),
    encoding="utf-8",
)


print("DONE")
print("rows:", table.num_rows)
print("columns:", table.num_columns)
print("parquet:", OUT)
print("size MB:", round(OUT.stat().st_size / 1024 / 1024, 2))
print("missing QIDs:", len(missing_qids))
print("label_en:", has_label_en)
print("label_mul:", has_label_mul)
print("label_en_effective:", has_label_en_effective)

q42 = next((r for r in rows if r["qid"] == "Q42"), None)
if q42:
    print("\nQ42:")
    print(" label_en:", q42["label_en"])
    print(" label_mul:", q42["label_mul"])
    print(" label_en_effective:", q42["label_en_effective"])
    print(" aliases_mul:", q42["aliases_mul"])

print("\nsummary:", OUT_SUMMARY)
