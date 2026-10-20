#!/usr/bin/env python3
"""Create a non-adjudicative 438-unit Edition-backed research queue (v3).

Inputs are the immutable output bytes of the v1 title screen and v2 frozen
raw-dump enrichment. This post-hoc exploratory triage is NOT an independent
identity classifier, evaluation, new gold label, or permission to merge/split.

Usage from canon-pipeline repository root:
    python scripts/build_held_one_work_research_triage_v3.py

Only creates a new output directory. Existing releases, Project W, labels,
Git state, and the OL source dump are never written or requested.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path.cwd()
BASE = ROOT / "derived/identity"
V1 = BASE / "aggregation_held_one_work_bibliographic_screen_v1"
V2 = BASE / "aggregation_held_one_work_raw_edition_enrichment_v2"
OUT = BASE / "aggregation_held_one_work_research_triage_v3"
FROZEN_REVIEW = (BASE / "aggregation_held_heldout_human_review_draft_v1"
                 / "heldout_researcher_review_frozen_v1.tsv")

EXPECTED = {
    V1 / "unit_screen_v1.tsv": "560f50be62cddb3dbf7b8b5c76f6ee054d36d1df8a587c2fbb840c5645232cc5",
    V1 / "work_screen_v1.tsv": "5b9591d1869aaa8fe01cbf380184ef5387792b331102132a63cfc0250de91f2a",
    V1 / "edition_evidence_v1.tsv": "40ea3d224b7dc6195c65e9cafc0db372794b5619ef1f4b65ea0f0d55049e69d7",
    V1 / "manifest_v1.json": "10505c674b2949515e54ac56d582bb0aa00ccfa4136b4ca3e1e6496ff655f174",
    V2 / "unit_raw_metadata_screen_v2.tsv": "d74089b713c59ea50db673c8f6c8b4929d86365a628a4a109301015ea89abc70",
    V2 / "raw_edition_enrichment_v2.tsv": "3dcdea64a24b1dc7020bea64131be8a8bc810d2921246b4c0cdf8ce50ef862f4",
    V2 / "manifest_v2.json": "6f25f6ea7a9219d3ca405e4fe772c8258373346b2d46b28ccb3b3fccd0a080ba",
    FROZEN_REVIEW: "9b9dea1b7ec54710affab9b739797de0dc5d01b7f8d9049d9e723a2962a91c8d",
}

# Descriptive evidence routing, explicitly not predicted identity labels.
STRONG_CONTENT_NOTES = {"NOTE_WITH_BOUND_ITEM", "NOTE_COLLECTION_OR_ADAPTATION_WORDING"}
SCOPE_TITLE_MARKERS = {"COLLECTION_TITLE_WORDING", "VOLUME_TITLE_WORDING", "DRAMATIC_TITLE_WORDING"}
TIER_ORDER = {
    "T1_CONTENT_CLUE": 1,
    "T2_SCOPE_OR_PAGINATION": 2,
    "T3_GENERAL_METADATA_VARIATION": 3,
    "T4_NO_DEFINED_PROMPT": 4,
}
MAX_EXAMPLES_PER_SIGNAL = 3


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def read_json(value: str):
    return json.loads(value)


def compact(value: object, max_chars: int = 280) -> str:
    if isinstance(value, dict) and isinstance(value.get("value"), str):
        value = value["value"]
    if isinstance(value, list):
        chunks = []
        for x in value[:3]:
            if isinstance(x, dict):
                chunks.append(str(x.get("title") or x.get("value") or x))
            else:
                chunks.append(str(x))
        value = " | ".join(chunks)
    if isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    return value[:max_chars]


def ordered_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def raw_evidence_excerpt(r: dict[str, str], signal: str) -> tuple[str, str]:
    field = {
        "SUBTITLE_JOINT_SEPARATOR": "subtitle",
        "MULTI_ARABIC_SEGMENT_PAGINATION": "pagination",
        "NOTE_WITH_BOUND_ITEM": "notes",
        "NOTE_COLLECTION_OR_ADAPTATION_WORDING": "notes",
        "TABLE_OF_CONTENTS_PRESENT": "table_of_contents",
    }.get(signal, "")
    if not field:
        return "", ""
    value = read_json(r[field + "_json"])
    return field, compact(value, 400)


def tier_for(v1_signals: set[str], v2_signals: set[str],
             paired_pagination_subtitle: bool) -> tuple[str, list[str]]:
    reasons = []
    if v2_signals & STRONG_CONTENT_NOTES:
        reasons.append("NOTE_DESCRIBES_OTHER_ITEM_OR_COLLECTION_OR_ADAPTATION")
    if paired_pagination_subtitle:
        reasons.append("SAME_EDITION_MULTI_ARABIC_PAGINATION_AND_SUBTITLE")
    if reasons:
        return "T1_CONTENT_CLUE", reasons
    if v1_signals & SCOPE_TITLE_MARKERS:
        reasons.append("EXPLICIT_SCOPE_OR_FORM_WORDING_IN_TITLE")
    if "MULTI_ARABIC_SEGMENT_PAGINATION" in v2_signals:
        reasons.append("MULTI_ARABIC_PAGINATION")
    if reasons:
        return "T2_SCOPE_OR_PAGINATION", reasons
    if v1_signals or v2_signals:
        return "T3_GENERAL_METADATA_VARIATION", ["BROAD_OR_NON_SPECIFIC_METADATA_CLUE"]
    return "T4_NO_DEFINED_PROMPT", ["NO_DEFINED_SIGNAL_NOT_PROOF_OF_SAFETY"]


def write_tsv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    assert rows, f"Empty output not allowed: {path}"
    with path.open("x", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    assert not OUT.exists(), f"STOP: refusing to overwrite existing directory: {OUT}"
    for path, expected in EXPECTED.items():
        assert path.is_file(), f"Missing frozen file: {path}"
        assert sha(path) == expected, f"SHA256 mismatch: {path}"

    units1 = load_tsv(V1 / "unit_screen_v1.tsv")
    units2 = load_tsv(V2 / "unit_raw_metadata_screen_v2.tsv")
    works = load_tsv(V1 / "work_screen_v1.tsv")
    editions1 = load_tsv(V1 / "edition_evidence_v1.tsv")
    editions2 = load_tsv(V2 / "raw_edition_enrichment_v2.tsv")

    assert len(units1) == len(units2) == 438
    assert len(works) == 1249
    assert len(editions1) == len(editions2) == 40305
    by1 = {r["unit_anchor_entity_id"]: r for r in units1}
    by2 = {r["unit_anchor_entity_id"]: r for r in units2}
    assert len(by1) == len(by2) == 438 and set(by1) == set(by2)
    ed1 = {r["edition_key"]: r for r in editions1}
    ed2 = {r["edition_key"]: r for r in editions2}
    assert len(ed1) == len(ed2) == 40305 and set(ed1) == set(ed2)

    works_by_unit = defaultdict(list)
    for r in works:
        assert r["unit_anchor_entity_id"] in by1
        works_by_unit[r["unit_anchor_entity_id"]].append(r)

    by_unit_edition = defaultdict(list)
    assert all(r["unit_anchor_entity_id"] in by1 for r in editions1)
    for key, r1 in ed1.items():
        r2 = ed2[key]
        assert r1["unit_anchor_entity_id"] == r2["unit_anchor_entity_id"], key
        assert r1["current_ol_work_id"] == r2["current_ol_work_id"], key
        assert r1["source_snapshot"] == r2["source_snapshot"] == "OL_EDITIONS_2026-02-28", key
        by_unit_edition[r1["unit_anchor_entity_id"]].append(key)

    unit_rows = []
    evidence_rows = []
    tier_counts = Counter()
    unit_presence_counts = Counter()
    example_counters = Counter()

    for anchor in sorted(by1):
        a = by1[anchor]
        b = by2[anchor]
        assert a["historical_sampling_stratum"] == b["historical_sampling_stratum"]
        assert int(a["ol_work_count"]) == int(b["ol_work_count"])
        assert int(a["edition_link_count"]) == int(b["edition_link_count"])
        assert len(works_by_unit[anchor]) == int(a["ol_work_count"])
        ids = sorted(by_unit_edition[anchor])
        assert len(ids) == int(a["edition_link_count"]), anchor

        old_signals = set(read_json(a["signals_json"]))
        new_signals = set(read_json(b["v2_raw_metadata_review_prompts_json"]))
        old_seen = set()
        new_seen = set()
        pairing_ids = []
        per_signal_evidence = defaultdict(list)

        for eid in ids:
            r1, r2 = ed1[eid], ed2[eid]
            v1_title_markers = set(read_json(r1["title_markers_json"]))
            v2_prompts = set(read_json(r2["bibliographic_review_prompts_json"]))
            old_seen.update(v1_title_markers)
            new_seen.update(v2_prompts)
            subtitle = read_json(r2["subtitle_json"])
            has_subtitle = bool(subtitle and isinstance(subtitle, str))
            paired = "MULTI_ARABIC_SEGMENT_PAGINATION" in v2_prompts and has_subtitle
            if paired:
                pairing_ids.append(eid)
                per_signal_evidence["SAME_EDITION_PAGINATION_AND_SUBTITLE"].append({
                    "edition_key": eid, "source": "v2", "work": r1["current_ol_work_id"],
                    "field": "pagination + subtitle",
                    "excerpt": ("pagination=" + compact(read_json(r2["pagination_json"]), 130)
                                + "; subtitle=" + compact(subtitle, 180))[:400],
                    "title": r1["edition_title"],
                    "source_records": read_json(r2["source_records_json"]),
                })
            for flag in sorted(v2_prompts):
                field, excerpt = raw_evidence_excerpt(r2, flag)
                if field:
                    per_signal_evidence[flag].append({
                        "edition_key": eid, "source": "v2", "work": r1["current_ol_work_id"],
                        "field": field, "excerpt": excerpt, "title": r1["edition_title"],
                        "source_records": read_json(r2["source_records_json"]),
                    })
            for flag in sorted(v1_title_markers):
                per_signal_evidence[flag].append({
                    "edition_key": eid, "source": "v1", "work": r1["current_ol_work_id"],
                    "field": "edition_title", "excerpt": compact(r1["edition_title"]),
                    "title": r1["edition_title"],
                    "source_records": read_json(r2["source_records_json"]),
                })

        assert new_seen == new_signals, (anchor, new_seen ^ new_signals)
        # v1 unit signals may also arise from source OL Work titles or cross-work metadata.
        assert old_seen.issubset(old_signals), (anchor, old_seen - old_signals)
        for w in works_by_unit[anchor]:
            for flag in read_json(w["title_markers_json"]):
                if flag in per_signal_evidence:
                    continue
                per_signal_evidence[flag].append({
                    "edition_key": "", "source": "v1", "work": w["current_ol_work_id"],
                    "field": "ol_work_title", "excerpt": compact(w["work_title"]),
                    "title": w["work_title"], "source_records": [],
                })
        # Structural non-title flags are included in the unit-level queue and work list.
        tier, reasons = tier_for(old_signals, new_signals, bool(pairing_ids))
        tier_counts[tier] += 1
        unit_presence_counts[(bool(old_signals), bool(new_signals))] += 1

        examples_by_flag = {}
        for flag in sorted(per_signal_evidence):
            entries = sorted(per_signal_evidence[flag], key=lambda r: (r["edition_key"], r["work"]))
            selected = entries[:MAX_EXAMPLES_PER_SIGNAL]
            examples_by_flag[flag] = [x["edition_key"] or ("WORK:" + x["work"]) for x in selected]
            for entry in selected:
                evidence_rows.append({
                    "unit_anchor_entity_id": anchor,
                    "triage_tier": tier,
                    "signal": flag,
                    "signal_source": entry["source"],
                    "current_ol_work_id": entry["work"],
                    "edition_key": entry["edition_key"],
                    "evidence_field": entry["field"],
                    "evidence_excerpt_nonverbatim_truncated": entry["excerpt"],
                    "edition_or_work_title": compact(entry["title"], 220),
                    "source_records_example_json": ordered_json(entry["source_records"][:4] if isinstance(entry["source_records"], list) else []),
                    "interpretation": "INSPECT_ORIGINAL_BIBLIOGRAPHY_NO_IDENTITY_CLAIM",
                })
                example_counters[flag] += 1

        # Unit source Work titles and representative Edition IDs maintain auditability.
        work_descriptors = sorted([{
            "ol_work_id": w["current_ol_work_id"],
            "title": w["work_title"],
            "author_keys": w["author_keys"],
            "edition_count": int(w["edition_link_count"]),
        } for w in works_by_unit[anchor]], key=lambda x: x["ol_work_id"])
        all_example_ids = sorted({
            edid for items in examples_by_flag.values() for edid in items
            if edid.startswith("/books/")
        })
        unit_rows.append({
            "unit_anchor_entity_id": anchor,
            "triage_tier": tier,
            "triage_reasons_json": ordered_json(reasons),
            "historical_sampling_stratum": a["historical_sampling_stratum"],
            "ol_work_count": a["ol_work_count"],
            "edition_link_count": a["edition_link_count"],
            "v1_normalized_work_title_count": a["normalized_work_title_count"],
            "v1_ol_works_with_internal_edition_title_variation": a["ol_works_with_internal_edition_title_variation"],
            "v1_signals_json": ordered_json(sorted(old_signals)),
            "v2_review_prompts_json": ordered_json(sorted(new_signals)),
            "same_edition_pagination_and_subtitle_count": str(len(pairing_ids)),
            "v1_signal_present": "1" if old_signals else "0",
            "v2_prompt_present": "1" if new_signals else "0",
            "ol_works_titles_counts_json": ordered_json(work_descriptors),
            "evidence_example_edition_ids_json": ordered_json(all_example_ids),
            "examples_by_signal_json": ordered_json(examples_by_flag),
            "research_instruction": "TRIAGE_ONLY_NOT_A_WORK_IDENTITY_DECISION",
        })

    assert sum(tier_counts.values()) == 438
    assert unit_presence_counts == {
        (True, True): 215, (True, False): 130,
        (False, True): 27, (False, False): 66,
    }, unit_presence_counts
    by_anchor = {r["unit_anchor_entity_id"]: r for r in unit_rows}
    assert len(by_anchor) == 438
    assert "MULTI_ARABIC_SEGMENT_PAGINATION" in read_json(by_anchor["E000019492"]["v2_review_prompts_json"])
    assert by_anchor["E000019492"]["triage_tier"] == "T1_CONTENT_CLUE"
    # Do not use frozen reviewer labels to construct tiers or evidence.

    unit_rows.sort(key=lambda x: (TIER_ORDER[x["triage_tier"]], x["unit_anchor_entity_id"]))
    evidence_rows.sort(key=lambda x: (
        TIER_ORDER[x["triage_tier"]], x["unit_anchor_entity_id"],
        x["signal"], x["edition_key"], x["current_ol_work_id"]
    ))
    for i, row in enumerate(unit_rows, 1):
        row_with_order = {"queue_order": str(i), **row}
        unit_rows[i - 1] = row_with_order

    output = {
        "research_queue_v3.tsv": unit_rows,
        "review_evidence_examples_v3.tsv": evidence_rows,
    }
    OUT.mkdir(parents=True, exist_ok=False)
    for name, rows in output.items():
        write_tsv(OUT / name, rows, list(rows[0]))

    manifest = {
        "release": "aggregation-held-one-work-research-triage-v3",
        "status": "EXPLORATORY_NON_ADJUDICATIVE_LOCAL_NOT_COMMITTED",
        "created_at_jst": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(),
        "frame": "438 HOLD_FOR_LATER_REVIEW units with historical LLM ONE_WORK",
        "source_snapshot": "OL_EDITIONS_2026-02-28",
        "inputs_sha256": {str(path.relative_to(ROOT)): sha(path) for path in EXPECTED},
        "counts": {
            "units": len(unit_rows),
            "ol_works": len(works),
            "unique_editions": len(ed1),
            "evidence_example_rows": len(evidence_rows),
            "v1_v2_presence": {f"v1_{int(k[0])}_v2_{int(k[1])}": n for k,n in sorted(unit_presence_counts.items())},
            "triage_tiers": dict(sorted(tier_counts.items())),
            "examples_by_signal": dict(sorted(example_counters.items())),
        },
        "triage_definition": {
            "T1_CONTENT_CLUE": "Notes indicating another bound item or collection/adaptation, OR same Edition has multi-Arabic pagination and a non-empty subtitle",
            "T2_SCOPE_OR_PAGINATION": "Explicit collection, volume or dramatic title wording, OR multi-Arabic pagination without same-Edition subtitle",
            "T3_GENERAL_METADATA_VARIATION": "Other v1 title/author variation or v2 review prompt (including contents presence or subtitle separators)",
            "T4_NO_DEFINED_PROMPT": "Neither screen generated a prompt; NEVER evidence of safe merger",
            "max_example_records_per_signal_per_unit": MAX_EXAMPLES_PER_SIGNAL,
            "ranking_input": "v1 and v2 bibliographic signals only; no held-out reviewer decisions, historical LLM confidence, or prior approval outcomes",
        },
        "limitations": [
            "A document with multiple pagination segments need not contain multiple conceptual works.",
            "A With: note may refer to later library binding instead of publisher-issued composite.",
            "A subtitle with and/or punctuation often describes one work.",
            "An Edition table_of_contents may describe chapters, not independent works.",
            "Tiers prioritize further checking; they are not estimates of identity-error probability.",
            "No defined prompt must never be treated as an automatic merge authorization.",
            "Case 11-13 were known before these exploratory rules were designed; sensitivity is not independent validation.",
            "Selection only covers 438 historical held ONE_WORK units, not the full OL corpus.",
            "Underlying workshop-derived Edition tables were marked LOCAL_VALIDATION_NOT_PUBLISHED.",
            "No human labels, source entities, Project W identities, or earlier screening releases were changed.",
        ],
        "output_sha256": {name: sha(OUT / name) for name in output},
        "frozen_researcher_review_modified": False,
        "project_w_modified": False,
        "git_committed": False,
    }
    (OUT / "manifest_v3.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    for name, digest in manifest["output_sha256"].items():
        assert sha(OUT / name) == digest
    for path, expected in EXPECTED.items():
        assert sha(path) == expected
    assert len(load_tsv(OUT / "research_queue_v3.tsv")) == 438

    print("=== 438-UNIT RESEARCH TRIAGE V3 CREATED ===")
    print("Unit queue:", len(unit_rows))
    print("Edition evidence example rows:", len(evidence_rows))
    print("Tiers:", dict(sorted(tier_counts.items())))
    print("V1 and V2 coverage:", dict(sorted(unit_presence_counts.items())))
    for p in sorted(OUT.iterdir()):
        print(p.name, sha(p))
    print("Case 12 tier:", by_anchor["E000019492"]["triage_tier"])
    print("No adjudications, existing data modifications, Git operations, or Project W changes")


if __name__ == "__main__":
    main()
