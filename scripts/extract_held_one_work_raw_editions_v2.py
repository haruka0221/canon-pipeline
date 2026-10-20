#!/usr/bin/env python3
"""Non-adjudicative raw OL Edition evidence enrichment for 438 held ONE_WORK units.

Reads the entire *compressed* 2026-02-28 Edition dump once, decodes JSON only
for the 40,305 Edition IDs selected by the already frozen exploratory screen v1.
Writes a NEW v2 output directory only; never edits review labels or Project W.

No live API, no external network, no Git mutation. Run at canon-pipeline repo root.
"""

import argparse
import csv
import gzip
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

EXPECTED_V1_SHA = {
    "unit_screen_v1.tsv": "560f50be62cddb3dbf7b8b5c76f6ee054d36d1df8a587c2fbb840c5645232cc5",
    "work_screen_v1.tsv": "5b9591d1869aaa8fe01cbf380184ef5387792b331102132a63cfc0250de91f2a",
    "edition_evidence_v1.tsv": "40ea3d224b7dc6195c65e9cafc0db372794b5619ef1f4b65ea0f0d55049e69d7",
    "manifest_v1.json": "10505c674b2949515e54ac56d582bb0aa00ccfa4136b4ca3e1e6496ff655f174",
}
EXPECTED_FROZEN_REVIEW_SHA = "9b9dea1b7ec54710affab9b739797de0dc5d01b7f8d9049d9e723a2962a91c8d"
RAW_FIELDS = (
    "subtitle", "pagination", "table_of_contents", "notes", "description",
    "source_records", "series", "edition_name", "physical_format",
    "oclc_numbers", "lccn", "identifiers", "works",
)
FIELD_EVIDENCE_SIGNALS = (
    "MULTI_ARABIC_SEGMENT_PAGINATION",
    "NOTE_WITH_BOUND_ITEM",
    "TABLE_OF_CONTENTS_PRESENT",
    "SUBTITLE_JOINT_SEPARATOR",
    "NOTE_COLLECTION_OR_ADAPTATION_WORDING",
    "RAW_TITLE_VARIATION_FROM_V1",
    "RAW_WORKS_DO_NOT_INCLUDE_SELECTED_WORK",
)

# These are bibliographic *review prompts*, not independent-work predictions.
# A Roman numeral followed by Arabic pagination is intentionally NOT counted
# as multiple Arabic-numbered page segments (e.g., 'xiii, 434 p.').
MULTI_ARABIC = re.compile(r"(?<![0-9])\d{1,5}\s*[,;]\s*\d{1,5}(?![0-9])")
WITH_NOTE = re.compile(r"\bwith\s*:", flags=re.I)
JOINT_SEP = re.compile(r"\s+[&/]\s+|;|\s+and\s+", flags=re.I)
NOTE_COLLECTION = re.compile(
    r"\b(?:contains|bound with|bound together|also includes|"
    r"collected works|anthology|omnibus|adapted for (?:the )?stage|"
    r"dramati[sz]ation|other tales|other stories)\b", flags=re.I
)


def sha_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_tsv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def json_txt(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def nonempty(value):
    return value is not None and value != "" and value != [] and value != {}


def text_value(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        v = value.get("value", "")
        return v if isinstance(v, str) else ""
    return ""


def checks_for_edition(raw, v1):
    """Return conservative prompts; never infer conceptual identity."""
    result = set()
    pagination = text_value(raw.get("pagination"))
    note = text_value(raw.get("notes"))
    subtitle = text_value(raw.get("subtitle"))
    if MULTI_ARABIC.search(pagination):
        result.add("MULTI_ARABIC_SEGMENT_PAGINATION")
    if WITH_NOTE.search(note):
        result.add("NOTE_WITH_BOUND_ITEM")
    if nonempty(raw.get("table_of_contents")):
        result.add("TABLE_OF_CONTENTS_PRESENT")
    if JOINT_SEP.search(subtitle):
        result.add("SUBTITLE_JOINT_SEPARATOR")
    if NOTE_COLLECTION.search(note):
        result.add("NOTE_COLLECTION_OR_ADAPTATION_WORDING")
    if raw.get("title", "") != v1["edition_title"]:
        result.add("RAW_TITLE_VARIATION_FROM_V1")
    works = raw.get("works")
    if isinstance(works, list):
        source_keys = {
            w.get("key") for w in works
            if isinstance(w, dict) and isinstance(w.get("key"), str)
        }
        expected = "/works/" + v1["current_ol_work_id"]
        if source_keys and expected not in source_keys:
            result.add("RAW_WORKS_DO_NOT_INCLUDE_SELECTED_WORK")
    return sorted(result)


class HashingReader:
    """Hash compressed bytes as gzip consumes them; avoids a second 12 GB pass."""
    def __init__(self, source):
        self.source = source
        self.digest = hashlib.sha256()
        self.count = 0

    def read(self, n=-1):
        block = self.source.read(n)
        self.digest.update(block)
        self.count += len(block)
        return block


def write_tsv(path, rows, fields):
    with path.open("x", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--dump", type=Path,
        default=Path("/media/hdd1/user/tsutsui/openlibrary/ol_dump_editions_2026-02-28.txt.gz"),
    )
    parser.add_argument("--progress-every", type=int, default=5_000_000)
    args = parser.parse_args()
    assert args.progress_every > 0

    repo = args.repo.resolve()
    identity = repo / "derived/identity"
    v1 = identity / "aggregation_held_one_work_bibliographic_screen_v1"
    out = identity / "aggregation_held_one_work_raw_edition_enrichment_v2"
    frozen = (identity / "aggregation_held_heldout_human_review_draft_v1" /
              "heldout_researcher_review_frozen_v1.tsv")
    dump = args.dump.resolve()

    if out.exists():
        raise SystemExit(f"STOP: refusing to overwrite existing v2 output: {out}")
    if not dump.is_file():
        raise SystemExit(f"STOP: frozen source dump missing: {dump}")
    for name, wanted in EXPECTED_V1_SHA.items():
        p = v1 / name
        assert p.is_file(), f"Missing v1 artifact: {p}"
        assert sha_file(p) == wanted, f"v1 SHA256 mismatch: {p}"
    assert sha_file(frozen) == EXPECTED_FROZEN_REVIEW_SHA

    units = load_tsv(v1 / "unit_screen_v1.tsv")
    editions = load_tsv(v1 / "edition_evidence_v1.tsv")
    works = load_tsv(v1 / "work_screen_v1.tsv")
    assert len(units) == 438 and len(works) == 1249 and len(editions) == 40305
    units_by_anchor = {x["unit_anchor_entity_id"]: x for x in units}
    assert len(units_by_anchor) == 438
    lookup = {row["edition_key"]: row for row in editions}
    assert len(lookup) == 40305, "Duplicate v1 Edition keys: stop and investigate"
    assert all(row["unit_anchor_entity_id"] in units_by_anchor for row in editions)
    assert all(key.startswith("/books/") for key in lookup)

    dump_before_stat = dump.stat()
    dump_edition_keys = {key.encode("utf-8"): key for key in lookup}
    print("=== FROZEN RAW EDITION V2 EXTRACTION STARTED ===", flush=True)
    print("Source:", dump, flush=True)
    print("Compressed bytes:", dump_before_stat.st_size, flush=True)
    print("Requested Edition IDs:", len(lookup), flush=True)
    print("Full sequential gzip pass; JSON decode only for requested IDs.", flush=True)
    print("No outputs will be written until all requested IDs are found.", flush=True)

    found = {}
    records_scanned = 0
    record_fields = Counter()
    unit_fields = defaultdict(Counter)
    raw_flag_counts = Counter()
    unit_raw_flags = defaultdict(set)
    unit_signal_editions = defaultdict(lambda: defaultdict(list))
    started = time.monotonic()

    # Compressed-file bytes hashed while reading; no second whole-file pass.
    with dump.open("rb") as compressed:
        reader = HashingReader(compressed)
        with gzip.GzipFile(fileobj=reader, mode="rb") as decompressed:
            for raw_line in decompressed:
                records_scanned += 1
                parts = raw_line.rstrip(b"\r\n").split(b"\t", 4)
                if len(parts) != 5:
                    raise RuntimeError(f"Malformed dump line at record {records_scanned}")
                key = dump_edition_keys.get(parts[1])
                if key is not None:
                    if key in found:
                        raise RuntimeError(f"Duplicate Edition ID in dump: {key}")
                    raw = json.loads(parts[4])
                    if not isinstance(raw, dict):
                        raise RuntimeError(f"Unexpected non-object JSON: {key}")
                    if raw.get("key", key) != key:
                        raise RuntimeError(f"Edition key mismatch within raw JSON: {key}")
                    v1_row = lookup[key]
                    anchor = v1_row["unit_anchor_entity_id"]
                    present = [field for field in RAW_FIELDS if nonempty(raw.get(field))]
                    record_fields.update(present)
                    unit_fields[anchor].update(present)
                    flags = checks_for_edition(raw, v1_row)
                    raw_flag_counts.update(flags)
                    unit_raw_flags[anchor].update(flags)
                    for flag in flags:
                        # Constrain manifest size: up to 10 examples per flag per unit.
                        if len(unit_signal_editions[anchor][flag]) < 10:
                            unit_signal_editions[anchor][flag].append(key)

                    row = {
                        "unit_anchor_entity_id": anchor,
                        "current_ol_work_id": v1_row["current_ol_work_id"],
                        "edition_key": key,
                        "edition_title_from_v1": v1_row["edition_title"],
                        "raw_title": raw.get("title") if isinstance(raw.get("title"), str) else "",
                        "raw_record_type": parts[0].decode("utf-8", "replace"),
                        "raw_revision": parts[2].decode("utf-8", "replace"),
                        "raw_last_modified": parts[3].decode("utf-8", "replace"),
                        "edition_raw_field_presence_json": json_txt(present),
                        "bibliographic_review_prompts_json": json_txt(flags),
                        "source_snapshot": "OL_EDITIONS_2026-02-28",
                    }
                    for field in RAW_FIELDS:
                        row[field + "_json"] = json_txt(raw.get(field))
                    found[key] = row

                if records_scanned % args.progress_every == 0:
                    print(
                        "Scanned:", f"{records_scanned:,}",
                        "matched:", f"{len(found):,}/{len(lookup):,}",
                        "elapsed_min:", round((time.monotonic() - started) / 60, 1),
                        flush=True,
                    )
        compressed_sha = reader.digest.hexdigest()
        compressed_bytes = reader.count

    dump_after_stat = dump.stat()
    assert dump_before_stat.st_size == dump_after_stat.st_size, "Dump size changed during scan"
    assert dump_before_stat.st_mtime_ns == dump_after_stat.st_mtime_ns, "Dump mtime changed during scan"
    assert compressed_bytes == dump_before_stat.st_size, (
        "Not all compressed bytes were consumed", compressed_bytes, dump_before_stat.st_size
    )

    missing = sorted(set(lookup) - set(found))
    if missing:
        print("=== STOP: ORIGINAL RAW DUMP MISSING REQUESTED EDITIONS ===")
        print("Missing:", len(missing), "examples:", missing[:30])
        print("Nothing written; investigate snapshot alignment.")
        raise SystemExit(2)
    assert len(found) == 40305

    # Create a conservative, explicitly NON-adjudicative per-unit evidence summary.
    enriched_unit_rows = []
    for u in sorted(units, key=lambda x: x["unit_anchor_entity_id"]):
        anchor = u["unit_anchor_entity_id"]
        flags = sorted(unit_raw_flags[anchor])
        old_signals = json.loads(u["signals_json"])
        summary = {
            "unit_anchor_entity_id": anchor,
            "historical_sampling_stratum": u["historical_sampling_stratum"],
            "ol_work_count": u["ol_work_count"],
            "edition_link_count": u["edition_link_count"],
            "v1_title_based_signals_json": json_txt(old_signals),
            "v2_raw_metadata_review_prompts_json": json_txt(flags),
            "v2_prompt_example_editions_json": json_txt(dict(unit_signal_editions[anchor])),
            "subtitle_edition_count": unit_fields[anchor]["subtitle"],
            "pagination_edition_count": unit_fields[anchor]["pagination"],
            "table_of_contents_edition_count": unit_fields[anchor]["table_of_contents"],
            "notes_edition_count": unit_fields[anchor]["notes"],
            "source_records_edition_count": unit_fields[anchor]["source_records"],
            "screening_instruction": "RESEARCH_TRIAGE_ONLY_NOT_IDENTITY_ADJUDICATION",
        }
        enriched_unit_rows.append(summary)

    records = [found[key] for key in sorted(found)]
    out.mkdir(parents=True, exist_ok=False)
    ed_name = "raw_edition_enrichment_v2.tsv"
    unit_name = "unit_raw_metadata_screen_v2.tsv"
    write_tsv(out / ed_name, records, list(records[0]))
    write_tsv(out / unit_name, enriched_unit_rows, list(enriched_unit_rows[0]))

    case12_key = "/books/OL52630896M"
    case12 = found.get(case12_key)
    case12_observation = None
    if case12 is not None:
        case12_observation = {
            "edition_key": case12_key,
            "subtitle_json": case12["subtitle_json"],
            "pagination_json": case12["pagination_json"],
            "bibliographic_review_prompts_json": case12["bibliographic_review_prompts_json"],
        }

    manifest = {
        "release": "aggregation-held-one-work-raw-edition-enrichment-v2",
        "status": "EXPLORATORY_NON_ADJUDICATIVE_LOCAL",
        "source_snapshot": "OL_EDITIONS_2026-02-28",
        "input": {
            "compressed_dump_path": str(dump),
            "compressed_dump_sha256": compressed_sha,
            "compressed_dump_bytes": compressed_bytes,
            "v1_screen_input_sha256": EXPECTED_V1_SHA,
            "frozen_researcher_review_sha256": EXPECTED_FROZEN_REVIEW_SHA,
        },
        "counts": {
            "units": len(units),
            "ol_works": len(works),
            "editions_requested": len(lookup),
            "editions_found": len(found),
            "dump_records_scanned": records_scanned,
            "unit_without_v2_review_prompts": sum(not unit_raw_flags[u["unit_anchor_entity_id"]] for u in units),
            "raw_field_edition_counts": dict(sorted(record_fields.items())),
            "v2_review_prompt_edition_counts": dict(sorted(raw_flag_counts.items())),
            "v2_review_prompt_unit_counts": dict(sorted(Counter(
                sig for anchor in units_by_anchor for sig in unit_raw_flags[anchor]
            ).items())),
        },
        "case12_catalogue_observation_in_frozen_raw_dump": case12_observation,
        "output_sha256": {name: sha_file(out / name) for name in (ed_name, unit_name)},
        "limitations": [
            "No identity adjudication, merge/split or Project W change is authorized.",
            "This v2 was designed after the held-out adjudication was unblinded; prompt sensitivity on known cases is NOT independent validation.",
            "A missing or present metadata field does not establish work identity.",
            "Multi-Arabic pagination can represent multiple segments within one work, not necessarily multiple literary works.",
            "A With: note does not establish whether volumes were publisher-issued together or later bound together.",
            "The 2026-02-28 dump may differ from the later live OL API record.",
            "Contents may describe chapters, not distinct works; subtitle may be descriptive, not a second novel.",
            "The upstream v1 Edition tables have LOCAL_VALIDATION_NOT_PUBLISHED status.",
            "Only 438 held historical LLM ONE_WORK units are included; the 761-unit frame and 34789-target population are distinct.",
        ],
        "frozen_review_modified": False,
        "project_work_release_modified": False,
    }
    (out / "manifest_v2.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    assert sha_file(frozen) == EXPECTED_FROZEN_REVIEW_SHA
    assert len(load_tsv(out / unit_name)) == 438
    assert len(load_tsv(out / ed_name)) == 40305
    for name, digest in manifest["output_sha256"].items():
        assert sha_file(out / name) == digest

    print("\n=== HELD ONE_WORK RAW METADATA ENRICHMENT V2 CREATED ===")
    print("Source dump SHA256:", compressed_sha)
    print("Dump records scanned:", f"{records_scanned:,}")
    print("Units:", len(units), "OL Works:", len(works))
    print("Matched exact Editions:", len(found))
    print("Raw metadata field counts:", dict(sorted(record_fields.items())))
    print("Review prompt unit counts:", manifest["counts"]["v2_review_prompt_unit_counts"])
    print("Units without v2 review prompts:", manifest["counts"]["unit_without_v2_review_prompts"])
    print("Case 12 frozen raw observation:", json_txt(case12_observation))
    for p in sorted(out.iterdir()):
        print(p.name, sha_file(p))
    print("Frozen held-out labels unchanged; Project W unchanged; no Git operation")


if __name__ == "__main__":
    main()
