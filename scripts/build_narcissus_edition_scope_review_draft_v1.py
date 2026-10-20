#!/usr/bin/env python3
"""Create an immutable-source, NON-ADJUDICATIVE Conrad Edition review worksheet.

Reads frozen 2026-02-28 Edition v1/v2 evidence. Creates a new, versioned
review DRAFT only: all researcher judgments intentionally remain blank.
Never edits Project W, previous evaluations, source TSVs, or Git.

Run from canon-pipeline repo root:
    python scripts/build_narcissus_edition_scope_review_draft_v1.py --self-test
    python scripts/build_narcissus_edition_scope_review_draft_v1.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import tempfile
from collections import Counter
from pathlib import Path

ANCHOR = "E000019634"
TARGET_OL_WORK = "OL38815W"
SNAPSHOT = "OL_EDITIONS_2026-02-28"
EDITION_IDS = (
    "/books/OL11558585M",
    "/books/OL11952490M",
    "/books/OL15364763M",
    "/books/OL20710563M",
    "/books/OL21568672M",
    "/books/OL8132525M",
    "/books/OL8132526M",
    "/books/OL8132533M",
    "/books/OL8794202M",
    "/books/OL8968317M",
)
EXPECTED = {
    "aggregation_held_one_work_bibliographic_screen_v1/edition_evidence_v1.tsv":
        "40ea3d224b7dc6195c65e9cafc0db372794b5619ef1f4b65ea0f0d55049e69d7",
    "aggregation_held_one_work_bibliographic_screen_v1/work_screen_v1.tsv":
        "5b9591d1869aaa8fe01cbf380184ef5387792b331102132a63cfc0250de91f2a",
    "aggregation_held_one_work_raw_edition_enrichment_v2/raw_edition_enrichment_v2.tsv":
        "3dcdea64a24b1dc7020bea64131be8a8bc810d2921246b4c0cdf8ce50ef862f4",
    "aggregation_held_one_work_refined_evidence_v4/refined_unit_queue_v4.tsv":
        "abd74e0e68c0abbc43214eb1cb095a0f1524a9d55dae5e64054d21d779042970",
    "aggregation_held_heldout_human_review_draft_v1/heldout_researcher_review_frozen_v1.tsv":
        "9b9dea1b7ec54710affab9b739797de0dc5d01b7f8d9049d9e723a2962a91c8d",
}


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_selected_tsv(path: Path, relevant_keys: set[str], lookup_col: str) -> dict[str, dict]:
    selected = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        assert reader.fieldnames is not None and lookup_col in reader.fieldnames, path
        for row in reader:
            key = row[lookup_col]
            if key in relevant_keys:
                if key in selected:
                    raise RuntimeError(f"Duplicate row for {key} in {path}")
                selected[key] = row
    if set(selected) != relevant_keys:
        raise RuntimeError(f"Missing keys in {path}: {sorted(relevant_keys - set(selected))}")
    return selected


def decode(row: dict, field: str):
    return json.loads(row[field + "_json"])


def text_value(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("value", "") if isinstance(value.get("value"), str) else ""
    return ""


def toc_titles(value) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, dict):
        return [text_value(value)] if text_value(value) else []
    if isinstance(value, list):
        return [s for item in value if (s := (
            item.get("title", "") if isinstance(item, dict) else item
        )) and isinstance(s, str) and s.strip()]
    return []


def normalize_preview(value: str, limit: int = 450) -> str:
    return re.sub(r"\s+", " ", value).strip()[:limit]


def observations(raw: dict) -> list[str]:
    """Metadata-only cues, never claims that a work is or is not present."""
    title = raw["raw_title"]
    subtitle = text_value(decode(raw, "subtitle"))
    toc = toc_titles(decode(raw, "table_of_contents"))
    joined_contents = " ".join(toc)
    cues = []
    if re.search(r"nigg\w*\s+of\s+the\s+[\"'‘’]?narciss", joined_contents, re.I):
        cues.append("TOC_EXPLICIT_TARGET_TITLE_MENTION")
    if "complete short fiction" in (title + " " + subtitle).casefold():
        cues.append("TITLE_OR_SUBTITLE_COMPLETE_SHORT_FICTION")
    if "heart of darkness" in subtitle.casefold():
        cues.append("SUBTITLE_NAMES_HEART_OF_DARKNESS")
    if "author's notes" in subtitle.casefold() or "authors' notes" in subtitle.casefold():
        cues.append("SUBTITLE_AUTHORS_NOTES")
    if len(toc) >= 15 and sum(len(x.strip()) <= 1 for x in toc) / len(toc) >= .70:
        cues.append("TOC_CHARACTER_SPLIT_SUSPECT")
    if not cues:
        cues.append("NO_DEFINED_CUE_NOT_ABSENCE")
    return cues


def write_tsv(path: Path, rows: list[dict], columns: list[str]):
    with path.open("x", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def self_test():
    assert toc_titles([{"title": "The Nigger of the Narcissus"}]) == ["The Nigger of the Narcissus"]
    assert toc_titles("Nigger of the Narcissus - Heart of darkness")[0].startswith("Nigger")
    assert "TOC_EXPLICIT_TARGET_TITLE_MENTION" in observations({
        "raw_title": "Joseph Conrad", "subtitle_json": "null",
        "table_of_contents_json": '[{"title":"Nigger of the Narcissus"}]'
    })
    assert "TOC_CHARACTER_SPLIT_SUSPECT" in observations({
        "raw_title": "Joseph Conrad", "subtitle_json": '"the complete short fiction"',
        "table_of_contents_json": json.dumps([{"title": c} for c in "v.1-2.TheseStories"]),
    })
    assert "NO_DEFINED_CUE_NOT_ABSENCE" in observations({
        "raw_title": "Joseph Conrad", "subtitle_json": "null", "table_of_contents_json": "null",
    })
    print("SELF-TEST PASSED: source parsing and descriptive signals; no files written")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=Path.cwd())
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        self_test()
        return

    base = args.repo.resolve() / "derived/identity"
    out = base / "aggregation_held_narcissus_edition_scope_review_draft_v1"
    if out.exists():
        raise SystemExit(f"STOP: refusing to overwrite: {out}")
    for subpath, digest in EXPECTED.items():
        path = base / subpath
        if not path.is_file() or sha_file(path) != digest:
            raise SystemExit(f"STOP: missing or SHA mismatch: {path}")

    keys = set(EDITION_IDS)
    v1 = load_selected_tsv(
        base / "aggregation_held_one_work_bibliographic_screen_v1/edition_evidence_v1.tsv",
        keys, "edition_key")
    v2 = load_selected_tsv(
        base / "aggregation_held_one_work_raw_edition_enrichment_v2/raw_edition_enrichment_v2.tsv",
        keys, "edition_key")

    edition_rows = []
    for key in EDITION_IDS:
        a, b = v1[key], v2[key]
        for r in (a, b):
            if r["unit_anchor_entity_id"] != ANCHOR or r["current_ol_work_id"] != TARGET_OL_WORK:
                raise RuntimeError(f"Unit/Work mismatch for {key}")
        if b["source_snapshot"] != SNAPSHOT:
            raise RuntimeError(f"Wrong Edition snapshot: {key}")
        links = decode(b, "works")
        if not isinstance(links, list) or not any(
                isinstance(w, dict) and w.get("key") == "/works/" + TARGET_OL_WORK
                for w in links):
            raise RuntimeError(f"Raw Work reference does not match {key}")
        toc = toc_titles(decode(b, "table_of_contents"))
        sources = decode(b, "source_records")
        cue = observations(b)
        edition_rows.append({
            "unit_anchor_entity_id": ANCHOR,
            "edition_key": key,
            "linked_current_ol_work_id": TARGET_OL_WORK,
            "source_snapshot": SNAPSHOT,
            "publish_year": a["publish_year"],
            "edition_title": normalize_preview(b["raw_title"], 500),
            "subtitle_preview": normalize_preview(text_value(decode(b, "subtitle")), 500),
            "pagination_preview": normalize_preview(text_value(decode(b, "pagination")), 250),
            "notes_preview": normalize_preview(text_value(decode(b, "notes")), 450),
            "contents_type": type(decode(b, "table_of_contents")).__name__,
            "contents_item_count": str(len(toc)),
            "contents_preview": normalize_preview(" | ".join(toc), 700),
            "source_records_json": json.dumps(sources, ensure_ascii=False, separators=(",", ":")),
            "raw_work_references_json": json.dumps(links, ensure_ascii=False, separators=(",", ":")),
            "machine_observation_cues_json": json.dumps(cue, ensure_ascii=False, separators=(",", ":")),
            "researcher_review_status": "NOT_REVIEWED",
            "researcher_target_presence": "",
            "researcher_publication_scope": "",
            "researcher_physical_relationship": "",
            "researcher_edition_work_linkage": "",
            "researcher_additional_source": "",
            "researcher_evidence_note": "",
            "researcher_name": "",
            "reviewed_at": "",
        })

    # Separate work-identity axis. Do not infer identity from Edition content.
    work_ids = {"OL38815W", "OL44245458W"}
    work_map = load_selected_tsv(
        base / "aggregation_held_one_work_bibliographic_screen_v1/work_screen_v1.tsv",
        work_ids, "current_ol_work_id")
    work_rows = []
    for work_id in sorted(work_map):
        r = work_map[work_id]
        if r["unit_anchor_entity_id"] != ANCHOR:
            raise RuntimeError(f"Wrong work member: {work_id}")
        work_rows.append({
            "unit_anchor_entity_id": ANCHOR,
            "current_ol_work_id": work_id,
            "work_title": r["work_title"],
            "author_keys": r["author_keys"],
            "edition_link_count": r["edition_link_count"],
            "researcher_identity_review_status": "NOT_REVIEWED",
            "researcher_identity_evidence_note": "",
        })
    assert len(edition_rows) == 10 and len(work_rows) == 2
    assert Counter(x["researcher_review_status"] for x in edition_rows) == {"NOT_REVIEWED": 10}

    readme = """# Conrad Narcissus: bibliographic review worksheet (DRAFT)

Status: **NOT REVIEWED, NOT ADJUDICATED**. Prepared 2026-10-20.
Frozen source snapshot: `OL_EDITIONS_2026-02-28`; no live-API source mixing.

Scope: ten deliberately selected Editions currently linked to `OL38815W`,
under held unit `E000019634`. This is exploratory selection, **not** a random
sample. A second Work ID, `OL44245458W`, is recorded separately to retain
work-identity context. Neither historical ONE_WORK nor Project W is modified.

The Edition worksheet contains source-derived **excerpts**. To inspect the
complete contents, notes, and other raw fields, consult the immutable
`raw_edition_enrichment_v2.tsv` by `edition_key`. `source_records_json` preserves
source-record pointers, **not** proof of cataloguing accuracy.

Researcher judgment cells are intentionally blank. Fill them only after
checking suitable evidence for each Edition (catalogue, digitized copy,
contents, or authoritative original record). Recommended controlled values:

- `researcher_target_presence`: `PRESENT_CONFIRMED`, `ABSENT_CONFIRMED`,
  `UNDETERMINED`.
- `researcher_publication_scope`: `SINGLE_WORK`, `COLLECTION_OR_JOINT_VOLUME`,
  `CRITICAL_OR_ANNOTATED`, `AUTHOR_PARATEXT`, `OTHER`, `UNDETERMINED`.
- `researcher_physical_relationship`: `PUBLISHER_JOINT_VOLUME`,
  `COPY_SPECIFIC_BOUND_WITH`, `SEPARATE_VOLUMES_IN_CASE`, `NOT_APPLICABLE`,
  `UNDETERMINED`.
- `researcher_edition_work_linkage`: `SUPPORTED`, `QUESTIONABLE`,
  `UNSUPPORTED`, `UNDETERMINED`.

These axes are not interchangeable: a collection may include the target
novel, a copy-specific `Bound with` note does not establish edition-wide
publication scope, and a lack of title mention is not proof of absence.

`machine_observation_cues_json` lists **descriptive hints only**. Example:
`TOC_EXPLICIT_TARGET_TITLE_MENTION` means the original OL metadata explicitly
mentions the target in a contents field; it is not a researcher-confirmed
full-text inspection. `TOC_CHARACTER_SPLIT_SUSPECT` flags the observed
letter-by-letter contents metadata anomaly. `NO_DEFINED_CUE_NOT_ABSENCE`
does NOT mean the target novel is absent.

`work_identity_context_v1.tsv` is deliberately separate: it does not decide
whether the two OL Work IDs represent one conceptual literary work. Edition
review must not silently overwrite or re-interpret frozen held-out labels.

Methodological note: This exploration follows exposure to earlier held-out
and development cases. Do **not** use it as independent evaluation of screen
accuracy or an estimate of overall OL Edition linkage-error prevalence.

Do not edit this generated draft in-place after it is frozen; make a new
researcher-annotated copy with provenance/versioning for actual decisions.
"""

    parent = out.parent
    with tempfile.TemporaryDirectory(prefix=".narcissus_review_stage_", dir=parent) as temporary:
        stage = Path(temporary)
        edname = "edition_scope_review_draft_v1.tsv"
        workname = "work_identity_context_v1.tsv"
        readmename = "README_review_protocol_v1.md"
        write_tsv(stage / edname, edition_rows, list(edition_rows[0]))
        write_tsv(stage / workname, work_rows, list(work_rows[0]))
        (stage / readmename).write_text(readme, encoding="utf-8")
        output_hashes = {name: sha_file(stage / name) for name in (edname, workname, readmename)}
        manifest = {
            "release": "held-narcissus-edition-scope-review-draft-v1",
            "status": "DRAFT_NON_ADJUDICATIVE_NOT_REVIEWED",
            "snapshot": SNAPSHOT,
            "unit_anchor_entity_id": ANCHOR,
            "target_ol_work_id": TARGET_OL_WORK,
            "selected_edition_ids": list(EDITION_IDS),
            "input_sha256": EXPECTED,
            "counts": {"editions": 10, "work_context_rows": 2, "researcher_decisions_made": 0},
            "observation_cue_counts": dict(sorted(Counter(
                cue for row in edition_rows for cue in json.loads(row["machine_observation_cues_json"])
            ).items())),
            "output_sha256": output_hashes,
            "restrictions": [
                "All researcher decision columns are blank, with status NOT_REVIEWED.",
                "No inference of ABSENT_CONFIRMED from missing title or contents metadata.",
                "Exploratory, not an independent validation sample.",
                "No Project W, source artifacts, frozen held-out decisions or Git mutations.",
            ],
        }
        (stage / "manifest_v1.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        assert len(load_selected_tsv(stage / edname, keys, "edition_key")) == 10
        assert len(load_selected_tsv(stage / workname, work_ids, "current_ol_work_id")) == 2
        for name, digest in output_hashes.items():
            assert sha_file(stage / name) == digest
        if out.exists():
            raise SystemExit(f"STOP: output appeared during generation: {out}")
        stage.rename(out)
    print("=== NON-ADJUDICATIVE NARCISSUS EDITION REVIEW DRAFT CREATED ===")
    print("Edition review rows: 10 | Work context rows: 2 | Reviewer judgments: 0")
    print("Machine observation cues:", dict(sorted(Counter(
        cue for row in edition_rows for cue in json.loads(row["machine_observation_cues_json"])
    ).items())))
    print("Output:", out)
    for f in sorted(out.iterdir()):
        print(f.name, sha_file(f))
    print("No Project W, historical labels, source files, or Git changes")


if __name__ == "__main__":
    main()
