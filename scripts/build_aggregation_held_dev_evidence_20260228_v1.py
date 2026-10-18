#!/usr/bin/env python3
"""Build blind, full-coverage OL Edition evidence for 20 development review units.

Reads frozen historical/current OL targets, unit memberships, and the workshop
2026-02-28 full-dump Edition tables. Does not read previous LLM verdicts or
held-out evaluation IDs; does not call APIs, assign Project W IDs, or alter
existing releases. Outputs are a new, non-overwriting local-QC directory.

Run from the canon-pipeline worktree:
    python ~/build_aggregation_held_dev_evidence_20260228_v1.py
"""
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

RELEASE = "aggregation-held-dev-evidence-20260228-v1"
OUT_REL = Path("derived/identity/aggregation_held_dev_evidence_20260228_v1")
SAMPLE_REL = Path("derived/identity/aggregation_held_units_sampling_v1")
TARGET_REL = Path("derived/identity/openlibrary_analysis_targets_v1.tsv")
MEMBER_REL = Path("derived/identity/aggregation_review_members_v1.tsv")
EXPECTED = {"units": 20, "ol_works": 51, "edition_links": 528, "unique_editions": 528}


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_tsv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def write_tsv(path, records, columns):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=columns, delimiter="\t", lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(records)


def verify_manifest_outputs(manifest_path, directory, names):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    outputs = manifest["outputs"]
    for name in names:
        if name not in outputs:
            raise RuntimeError(f"No frozen SHA in {manifest_path}: {name}")
        recorded = outputs[name]
        # The sampling manifest uses bare SHA strings; the workshop tables
        # manifest uses objects such as {"sha256": "..."}.
        expected_hash = recorded["sha256"] if isinstance(recorded, dict) else recorded
        actual = sha(directory / name)
        if actual != expected_hash:
            raise RuntimeError(f"Frozen input checksum mismatch: {directory/name}")
    return manifest


def year_value(value):
    value = str(value).strip()
    if not value:
        return None
    if len(value) != 4 or not value.isascii() or not value.isdigit():
        raise ValueError(f"Unexpected strict publish_year: {value!r}")
    return int(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--tables", type=Path,
        default=Path.home() / "workshop-20261016/data_sources" /
                "ol_editions_34792targets_tables_20260228_v1",
    )
    args = parser.parse_args()
    root = args.repo.resolve()
    tables = args.tables.resolve()
    output_dir = root / OUT_REL
    sample = root / SAMPLE_REL
    targets_path = root / TARGET_REL
    members_path = root / MEMBER_REL
    queue_path = sample / "development_review_queue_v1.tsv"
    summary_path = tables / "work_edition_summary_v1.tsv"
    links_path = tables / "edition_work_links_v1.tsv"
    editions_path = tables / "edition_details_v1.tsv"

    if output_dir.exists():
        raise SystemExit(f"STOP: output already exists: {output_dir}")
    for path in [queue_path, targets_path, members_path, summary_path,
                 links_path, editions_path]:
        if not path.is_file():
            raise FileNotFoundError(path)

    verify_manifest_outputs(sample / "manifest_v1.json", sample,
                            [queue_path.name])
    upstream = verify_manifest_outputs(tables / "manifest_v1.json", tables,
              [summary_path.name, links_path.name, editions_path.name])

    queue = load_tsv(queue_path)
    if len(queue) != EXPECTED["units"]:
        raise RuntimeError("Unexpected development queue size")
    if set(queue[0]) != {"review_order", "unit_anchor_entity_id"}:
        raise RuntimeError("Development queue unexpectedly exposes other fields")
    orders = [int(q["review_order"]) for q in queue]
    if sorted(orders) != list(range(1, EXPECTED["units"] + 1)):
        raise RuntimeError("Bad development review order")
    queue = sorted(queue, key=lambda q: int(q["review_order"]))
    selected_anchors = {q["unit_anchor_entity_id"] for q in queue}
    if len(selected_anchors) != EXPECTED["units"]:
        raise RuntimeError("Duplicate unit in development sample")
    order_of = {q["unit_anchor_entity_id"]: int(q["review_order"])
                for q in queue}

    current_targets = {}
    for r in load_tsv(targets_path):
        eid = r["current_entity_id"]
        if eid in current_targets:
            raise RuntimeError(f"Duplicate current E: {eid}")
        current_targets[eid] = r

    groups = defaultdict(list)
    seen_entity = set()
    for r in load_tsv(members_path):
        anchor, eid = r["unit_anchor_entity_id"], r["entity_id"]
        if anchor not in selected_anchors or eid not in current_targets:
            continue
        if eid in seen_entity:
            raise RuntimeError(f"Overlapping development membership: {eid}")
        seen_entity.add(eid)
        groups[anchor].append(current_targets[eid])
    if set(groups) != selected_anchors:
        raise RuntimeError("Missing one or more development units")

    ol_lookup = {}
    for anchor, members in groups.items():
        if len(members) < 2:
            raise RuntimeError(f"Unexpected single-target review unit: {anchor}")
        for r in members:
            ol = r["current_ol_work_id"]
            if ol in ol_lookup:
                raise RuntimeError(f"Repeated OL Work in review units: {ol}")
            ol_lookup[ol] = (anchor, r)
    if len(ol_lookup) != EXPECTED["ol_works"]:
        raise RuntimeError(f"Expected 51 OL Works, found {len(ol_lookup)}")

    summary = {r["source_ol_work_id"]: r
               for r in load_tsv(summary_path)
               if r["source_ol_work_id"] in ol_lookup}
    if set(summary) != set(ol_lookup):
        raise RuntimeError("Missing OL Works from workshop edition summary")

    # Stream the complete 421,754-link table, selecting exact OL IDs only.
    links_by_work = defaultdict(list)
    ed_owner = {}
    seen_pairs = set()
    with links_path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            ol = r["source_ol_work_id"]
            if ol not in ol_lookup:
                continue
            ed = r["edition_key"]
            pair = (ed, ol)
            if pair in seen_pairs:
                raise RuntimeError(f"Duplicate Edition/Work link: {pair}")
            seen_pairs.add(pair)
            if ed in ed_owner:
                raise RuntimeError(
                    f"Edition linked to multiple sampled OL Works: "
                    f"{ed}: {ed_owner[ed]} and {ol}"
                )
            ed_owner[ed] = ol
            links_by_work[ol].append(r)

    if len(seen_pairs) != EXPECTED["edition_links"]:
        raise RuntimeError(f"Expected 528 Edition links, got {len(seen_pairs)}")
    if len(ed_owner) != EXPECTED["unique_editions"]:
        raise RuntimeError("Unexpected unique Edition count")
    for ol in ol_lookup:
        actual = len(links_by_work[ol])
        expected = int(summary[ol]["edition_count"])
        if actual != expected:
            raise RuntimeError(f"Edition count mismatch for {ol}: {actual} != {expected}")

    # Stream the full Edition detail table, materializing only 528 requested rows.
    editions = {}
    with editions_path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            eid = r["edition_key"]
            if eid not in ed_owner:
                continue
            if eid in editions:
                raise RuntimeError(f"Duplicate Edition detail row: {eid}")
            editions[eid] = r
    if set(editions) != set(ed_owner):
        raise RuntimeError("Missing detail records for sampled Edition links")

    work_rows, unit_rows, ed_rows, title_rows = [], [], [], []
    for q in queue:
        anchor = q["unit_anchor_entity_id"]
        order = int(q["review_order"])
        work_sums, all_years = [], []
        unit_editions = 0
        for r in sorted(groups[anchor], key=lambda x: x["current_ol_work_id"]):
            ol = r["current_ol_work_id"]
            linkrows = sorted(links_by_work[ol], key=lambda x: x["edition_key"])
            records = [editions[x["edition_key"]] for x in linkrows]
            years = [y for y in (year_value(x["publish_year"]) for x in records)
                     if y is not None]
            all_years.extend(years)
            titles = Counter(x["edition_title"] for x in records)
            statuses = Counter(x["publish_year_parse_status"] for x in records)
            unit_editions += len(records)
            work_sums.append(ol)

            work_rows.append({
                "review_order": order,
                "unit_anchor_entity_id": anchor,
                "current_entity_id": r["current_entity_id"],
                "historical_ol_work_id": r["historical_ol_work_id"],
                "current_ol_work_id": ol,
                "target_resolution": r["target_resolution"],
                "work_title": r["title"],
                "work_author_keys": r["author_keys"],
                "historical_first_publish_year_not_verified_original": r["first_publish_year"],
                "edition_count": len(records),
                "distinct_raw_edition_title_count": len(titles),
                "edition_rows_with_parsed_year": len(years),
                "edition_rows_without_parsed_year": len(records) - len(years),
                "earliest_parsed_edition_year_not_original": min(years) if years else "",
                "latest_parsed_edition_year_not_original": max(years) if years else "",
                "edition_date_parse_status_counts_json": json.dumps(
                    statuses, ensure_ascii=False, sort_keys=True),
            })

            for value, count in sorted(titles.items(),
                                       key=lambda kv: (-kv[1], kv[0].casefold(), kv[0])):
                sample_key = min(x["edition_key"] for x in records
                                 if x["edition_title"] == value)
                title_rows.append({
                    "review_order": order,
                    "unit_anchor_entity_id": anchor,
                    "current_ol_work_id": ol,
                    "edition_title_raw": value,
                    "edition_count": count,
                    "example_edition_key": sample_key,
                })

            for lr in linkrows:
                edition = editions[lr["edition_key"]]
                ed_rows.append({
                    "review_order": order,
                    "unit_anchor_entity_id": anchor,
                    "current_entity_id": r["current_entity_id"],
                    "current_ol_work_id": ol,
                    "work_link_ordinal": lr["work_link_ordinal"],
                    "is_extraction_target": lr["is_extraction_target"],
                    **edition,
                })

        unit_rows.append({
            "review_order": order,
            "unit_anchor_entity_id": anchor,
            "ol_work_count": len(work_sums),
            "edition_count": unit_editions,
            "earliest_parsed_edition_year_not_original": min(all_years) if all_years else "",
            "latest_parsed_edition_year_not_original": max(all_years) if all_years else "",
            "ol_work_ids": ";".join(work_sums),
        })

    if len(unit_rows) != 20 or len(work_rows) != 51 or len(ed_rows) != 528:
        raise RuntimeError("Unexpected output row counts")

    file_rows = {
        "development_units_v1.tsv": (unit_rows, [
            "review_order", "unit_anchor_entity_id", "ol_work_count", "edition_count",
            "earliest_parsed_edition_year_not_original",
            "latest_parsed_edition_year_not_original", "ol_work_ids"]),
        "development_ol_works_v1.tsv": (work_rows, [
            "review_order", "unit_anchor_entity_id", "current_entity_id",
            "historical_ol_work_id", "current_ol_work_id", "target_resolution",
            "work_title", "work_author_keys",
            "historical_first_publish_year_not_verified_original", "edition_count",
            "distinct_raw_edition_title_count", "edition_rows_with_parsed_year",
            "edition_rows_without_parsed_year",
            "earliest_parsed_edition_year_not_original",
            "latest_parsed_edition_year_not_original",
            "edition_date_parse_status_counts_json"]),
        "development_editions_all_v1.tsv": (ed_rows, [
            "review_order", "unit_anchor_entity_id", "current_entity_id",
            "current_ol_work_id", "edition_key", "edition_title",
            "publish_date_raw", "publish_year", "publish_year_parse_status",
            "publishers_json", "publish_places_json", "languages_json",
            "number_of_pages", "isbn_10_json", "isbn_13_json",
            "source_snapshot", "work_link_ordinal", "is_extraction_target"]),
        "development_edition_titles_v1.tsv": (title_rows, [
            "review_order", "unit_anchor_entity_id", "current_ol_work_id",
            "edition_title_raw", "edition_count", "example_edition_key"]),
    }

    # Inputs are fixed before any output is written. Skip fields containing
    # earlier LLM prediction, confidence, safety gates, or sampling strata.
    input_files = [queue_path, targets_path, members_path,
                   summary_path, links_path, editions_path,
                   sample / "manifest_v1.json", tables / "manifest_v1.json"]
    input_hashes = {str(p.relative_to(root) if p.is_relative_to(root)
                        else p): sha(p) for p in input_files}

    output_dir.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name, (records, columns) in file_rows.items():
        path = output_dir / name
        write_tsv(path, records, columns)
        hashes[name] = sha(path)

    manifest = {
        "release": RELEASE,
        "status": "LOCAL_EVIDENCE_PREP_NOT_ADJUDICATED",
        "sampling_source_status": "SAMPLE_FROZEN_REVIEW_NOT_STARTED",
        "source_snapshot": "Open Library Editions dump 2026-02-28",
        "inputs": input_hashes,
        "workshop_tables_upstream_status": upstream.get("status", ""),
        "counts": {
            **EXPECTED,
            "raw_edition_title_rows": len(title_rows),
            "edition_year_parsed_rows": sum(bool(r["publish_year"]) for r in ed_rows),
            "edition_year_unparsed_rows": sum(not bool(r["publish_year"]) for r in ed_rows),
        },
        "outputs": hashes,
        "interpretation": {
            "source_work_title_and_authors": "Work-level metadata; author IDs are not Edition-level authorship evidence.",
            "historical_first_publish_year": "OL target field; not a validated conceptual original publication year.",
            "publish_year": "Strict edition-date parser result; not a conceptual original publication year.",
            "title_distribution": "Exact raw strings; no title normalization or deduplication.",
            "complete_sample_edition_coverage": "All 528 extracted Edition links for the 51 selected OL Works.",
            "not_independent_evidence": "Open Library Edition metadata is source-internal to OL Work clustering.",
            "blinding": "Only development queue is read; prior LLM verdicts and held-out sample are not read or written.",
            "review_status": "No human, LLM, or project identity decision made.",
            "no_corpus_scope_decision": True,
            "no_existing_release_modified": True,
        },
    }
    (output_dir / "manifest_v1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    print("=== HELD UNIT DEVELOPMENT EVIDENCE V1 ===")
    print("Units:", len(unit_rows), "OL Works:", len(work_rows))
    print("Edition records:", len(ed_rows), "distinct title rows:", len(title_rows))
    print("Parsed edition years:", manifest["counts"]["edition_year_parsed_rows"])
    print("Output:", output_dir)
    print("Status:", manifest["status"])
    print("No API, identity decision, held-out evaluation access, or source modification.")


if __name__ == "__main__":
    main()
