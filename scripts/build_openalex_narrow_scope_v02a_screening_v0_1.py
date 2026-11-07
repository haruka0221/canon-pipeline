#!/usr/bin/env python3
"""Build source-signal-only v0.2a screening for 32,066 active Project W.

This is NOT an eligibility classifier or a released literary corpus.
Its four-way routing labels prioritize bibliographic REVIEW, never assert
original publication year, original language, work form, or source identity.
The independent researcher-accepted random-80 overlay is kept provisional.

No web/API calls, no changes to upstream, no OpenAlex/Goodreads value joins.
Run at repository root:
  python -B scripts/build_openalex_narrow_scope_v02a_screening_v0_1.py --check-only
  python -B scripts/build_openalex_narrow_scope_v02a_screening_v0_1.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

VERSION = "openalex_narrow_v02a_source_screening_v0_1"
POLICY = "scope_v0.2a_RESEARCHER_ACCEPTED_PROVISIONAL"
DEFAULT_COMBINED = "derived/scope/scope_combined_bibliographic_evidence_v0_1/scope_combined_project_w_bibliographic_evidence_v0_1.tsv"
DEFAULT_REVIEW80 = "derived/scope/narrow_v02_researcher_accepted_2026_11_07/random80_researcher_accepted_provisional_v0_1.tsv"
DEFAULT_OUTPUT = "derived/scope/narrow_v02a_all_w_source_screening_v0_1"
EXPECTED_ACTIVE = 32066
EXPECTED_RANDOM = 80
# Upstream immutable source snapshot, not a scholarly first-publication proof.
EXPECTED_COMBINED_SHA256 = "e6d01748327ef0eed243e0dc35f862cd9480714f10efaba7380ee3d5d38e523c"

REQUIRED_SOURCE = {
    "project_work_id", "current_ol_work_ids_json", "historical_titles_json",
    "historical_authors_json", "historical_edition_derived_min_years_json",
    "historical_subject_keys_json", "wikidata_qid", "wd_p577_parsed_positive_years_json",
    "wd_p407_values_json", "bibliographic_source_combination",
}
REQUIRED_REVIEW = {
    "random_rank", "project_work_id", "source_ol_work_id", "researcher_accepted_assessment_v02",
    "novel_novella_only_assessment", "reviewer_acceptance_status", "release_status",
    "source_claims_independently_human_verified", "unresolved_or_qc_notes",
}
ROUTES = (
    "FORM_OR_IDENTITY_UNRESOLVED",
    "POSSIBLE_EXCLUSION_FOR_REVIEW",
    "ELIGIBLE_CANDIDATE",
    "INSUFFICIENT_EVIDENCE",
)
SCOPE_STATUSES = {"IN_SCOPE", "OUT_OF_SCOPE", "UNRESOLVED"}
COLLECTION_TITLE = re.compile(r"(?i)(?:and other (?:stories|tales|sketches)|short stories|collected (?:stories|tales))")
NONFICTION_CUE = re.compile(r"(?:^|_)(?:bibliograph\w*|catalog\w*|criticism|literary_criticism|writing_manual|reference_works|history_and_criticism)(?:_|$)")
FICTION_CUE = re.compile(r"(?:^|_)(?:fiction|juvenile_fiction|novel|novels|romance|short_stories|american_short_stories)(?:_|$)")


def check(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError("QC FAILED: " + reason)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_tsv(path: Path, required: set[str], label: str) -> list[dict[str, str]]:
    check(path.is_file(), f"missing {label}: {path}")
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        check(reader.fieldnames is not None, f"no {label} header")
        check(required <= set(reader.fieldnames), f"{label} missing columns: {sorted(required - set(reader.fieldnames))}")
        rows = list(reader)
    check(all(None not in row for row in rows), f"{label} has malformed columns")
    ids = [row["project_work_id"] for row in rows]
    check(all(re.fullmatch(r"W\d+", w or "") for w in ids), f"{label} invalid Project W IDs")
    check(len(set(ids)) == len(ids), f"{label} has duplicate Project W IDs")
    return rows


def as_array(raw: str, desc: str) -> list:
    try:
        values = json.loads(raw) if raw.strip() else []
    except json.JSONDecodeError as exc:
        raise ValueError("QC FAILED: invalid JSON array in " + desc) from exc
    check(isinstance(values, list), f"non-array in {desc}")
    return values


def years(raw: str, desc: str) -> list[int]:
    result = []
    for value in as_array(raw, desc):
        if re.fullmatch(r"\d{4}", str(value)):
            y = int(value)
            if 1000 <= y <= 2100:
                result.append(y)
    return sorted(set(result))


def period_signals(ol: list[int], wd: list[int]) -> str:
    dates = ol + wd
    if not dates:
        return "NO_SOURCE_YEAR"
    in_period = any(1880 <= y <= 1950 for y in dates)
    out_period = any(y < 1880 or y > 1950 for y in dates)
    if in_period and out_period:
        return "MIXED_SOURCE_DATES_NOT_ORIGINAL_YEAR"
    if in_period:
        return "ONLY_IN_PERIOD_SOURCE_DATES_NOT_ORIGINAL_YEAR"
    return "ONLY_OUT_OF_PERIOD_SOURCE_DATES_NOT_ORIGINAL_YEAR"


def source_triage(row: dict[str, str]) -> dict[str, str]:
    w = row["project_work_id"]
    ol = [str(z) for z in as_array(row["current_ol_work_ids_json"], w + ".ol")]
    titles = [str(z) for z in as_array(row["historical_titles_json"], w + ".titles")]
    authors = [str(z) for z in as_array(row["historical_authors_json"], w + ".authors")]
    subjects = [str(z).lower() for z in as_array(row["historical_subject_keys_json"], w + ".subjects")]
    ol_years = years(row["historical_edition_derived_min_years_json"], w + ".ol_years")
    wd_years = years(row["wd_p577_parsed_positive_years_json"], w + ".wd_years")
    langs = [str(z) for z in as_array(row["wd_p407_values_json"], w + ".wd_languages")]
    period = period_signals(ol_years, wd_years)
    collection_cue = any(COLLECTION_TITLE.search(title) for title in titles)
    fiction_cue = any(FICTION_CUE.search(s) for s in subjects)
    nonfic_cue = any(NONFICTION_CUE.search(s) for s in subjects)
    reasons = []
    if len(ol) != 1:
        reasons.append("OL_WORK_LINK_COUNT_NOT_ONE")
    if not ol_years and not wd_years:
        reasons.append("NO_YEAR_EVIDENCE")
    if period == "MIXED_SOURCE_DATES_NOT_ORIGINAL_YEAR":
        reasons.append("CONFLICTING_SOURCE_YEAR_PERIODS")
    if langs and "Q1860" not in langs:
        reasons.append("WD_P407_NO_ENGLISH_STATEMENT_NOT_ORIGINAL_LANGUAGE")
    if nonfic_cue:
        reasons.append("OL_NONFICTION_OR_REFERENCE_SUBJECT")
    if collection_cue:
        reasons.append("COLLECTION_TITLE_CUE_NOT_CONFIRMED_CONTENTS")
    if fiction_cue:
        reasons.append("OL_FICTION_SUBJECT_NOT_VERIFIED_FORM")
    if not row.get("wikidata_qid", ""):
        reasons.append("NO_ADOPTED_WIKIDATA_QID")
    # Prioritization only. No subject/date/language statement proves original form.
    if len(ol) != 1 or period in {"MIXED_SOURCE_DATES_NOT_ORIGINAL_YEAR", "NO_SOURCE_YEAR"} or (langs and "Q1860" not in langs):
        route = "FORM_OR_IDENTITY_UNRESOLVED"
    elif nonfic_cue or period == "ONLY_OUT_OF_PERIOD_SOURCE_DATES_NOT_ORIGINAL_YEAR":
        route = "POSSIBLE_EXCLUSION_FOR_REVIEW"
    elif fiction_cue or collection_cue:
        route = "ELIGIBLE_CANDIDATE"
    else:
        route = "INSUFFICIENT_EVIDENCE"
    check(route in ROUTES, "undefined review route")
    return {
        "project_work_id": w,
        "scope_policy": POLICY,
        "screening_version": VERSION,
        "triage_route_not_scope": route,
        "review_reasons_json": json.dumps(reasons, ensure_ascii=False, separators=(",", ":")),
        "current_ol_work_ids_json": json.dumps(ol, ensure_ascii=False, separators=(",", ":")),
        "historical_titles_json": json.dumps(titles, ensure_ascii=False, separators=(",", ":")),
        "historical_authors_json": json.dumps(authors, ensure_ascii=False, separators=(",", ":")),
        "historical_subject_keys_json": json.dumps(subjects, ensure_ascii=False, separators=(",", ":")),
        "wikidata_qid": row["wikidata_qid"],
        "wd_p31_type_statements_source_only_json": row.get("wd_p31_values_json", ""),
        "ol_edition_years_source_only_json": json.dumps(ol_years),
        "wd_p577_years_source_only_json": json.dumps(wd_years),
        "wd_p407_language_statements_source_only_json": json.dumps(langs),
        "period_signal_source_only": period,
        "ol_fiction_subject_cue": str(fiction_cue),
        "ol_nonfiction_subject_cue": str(nonfic_cue),
        "collection_title_cue": str(collection_cue),
        "bibliographic_source_combination": row["bibliographic_source_combination"],
        "random80_review_provenance": "NOT_IN_FROZEN_RANDOM80",
        "random80_researcher_accepted_provisional_assessment": "",
        "random80_researcher_novel_only_provisional_assessment": "",
        "random80_openlibrary_source_target_mismatch_flag": "",
        "random80_evidence_verified": "",
        "random80_unresolved_notes": "",
        "auto_analysis_scope_decision": "NONE_NOT_ADJUDICATED",
        "release_status": "NOT_RELEASED",
        "original_language_independently_verified": "",
        "original_publication_event_independently_verified": "",
        "form_independently_verified": "",
        "target_work_edition_independently_verified": "",
    }


def overlay_review(row: dict[str, str], reviewer: dict[str, str]) -> None:
    w = row["project_work_id"]
    route = reviewer["researcher_accepted_assessment_v02"]
    check(route in SCOPE_STATUSES, f"invalid review provisional status for {w}")
    check(reviewer["release_status"] == "HOLD_NOT_RELEASED", f"upstream researcher release changed for {w}")
    row["random80_review_provenance"] = reviewer["reviewer_acceptance_status"]
    row["random80_researcher_accepted_provisional_assessment"] = route
    row["random80_researcher_novel_only_provisional_assessment"] = reviewer["novel_novella_only_assessment"]
    row["random80_evidence_verified"] = reviewer["source_claims_independently_human_verified"]
    row["random80_unresolved_notes"] = reviewer["unresolved_or_qc_notes"]
    ids = as_array(row["current_ol_work_ids_json"], w + ".target")
    target = reviewer["source_ol_work_id"].strip()
    row["random80_openlibrary_source_target_mismatch_flag"] = str(bool(target and target not in ids))


def build(combined: list[dict[str, str]], review80: list[dict[str, str]], *, expected_active=EXPECTED_ACTIVE, expected_random=EXPECTED_RANDOM):
    check(len(combined) == expected_active, f"expected {expected_active} active W, got {len(combined)}")
    check(len(review80) == expected_random, f"expected {expected_random} sample rows, got {len(review80)}")
    ranks = sorted(int(r["random_rank"]) for r in review80)
    check(ranks == list(range(1, expected_random + 1)), "random ranks not 1..80 contiguous")
    scope_w = {r["project_work_id"] for r in combined}
    check({r["project_work_id"] for r in review80} <= scope_w, "random80 includes unknown W")
    ledger = {r["project_work_id"]: r for r in review80}
    out = []
    for source in sorted(combined, key=lambda x: x["project_work_id"]):
        item = source_triage(source)
        if item["project_work_id"] in ledger:
            overlay_review(item, ledger[item["project_work_id"]])
        out.append(item)
    sample = [r for r in out if r["random80_review_provenance"] != "NOT_IN_FROZEN_RANDOM80"]
    check(len(sample) == expected_random, "random80 overlay length changed")
    # Preserve audit source sampling rank order, not an arbitrary W ordering.
    sample.sort(key=lambda r: int(ledger[r["project_work_id"]]["random_rank"]))
    acceptance = Counter(r["random80_researcher_accepted_provisional_assessment"] for r in sample)
    if expected_random == 80:
        check(acceptance == {"IN_SCOPE": 41, "OUT_OF_SCOPE": 19, "UNRESOLVED": 20}, "random80 approval counts drift")
    check(all(r["auto_analysis_scope_decision"] == "NONE_NOT_ADJUDICATED" and r["release_status"] == "NOT_RELEASED" for r in out), "unreleased status violated")
    counts = Counter(r["triage_route_not_scope"] for r in out)
    risk = [r for r in out if r["triage_route_not_scope"] in ("FORM_OR_IDENTITY_UNRESOLVED", "POSSIBLE_EXCLUSION_FOR_REVIEW")]
    # This prioritized queue is for bibliography verification; never use it as an independent probability sample.
    risks = {"FORM_OR_IDENTITY_UNRESOLVED":0, "POSSIBLE_EXCLUSION_FOR_REVIEW":1}
    risk.sort(key=lambda r: (risks[r["triage_route_not_scope"]], r["project_work_id"]))
    # Separate, purposive/stratified diagnostic quality-control review. It is
    # deliberately NOT pooled with the independent fixed random80 probability sample.
    audit_set = {r["project_work_id"] for r in sample}
    diagnostic_by_stratum = {}
    for stratum in ROUTES:
        candidates = [r for r in out if r["triage_route_not_scope"] == stratum
                      and r["project_work_id"] not in audit_set]
        candidates.sort(key=lambda r: hashlib.sha256(
            ("narrow_v02a_stratum_qc_v0_1\x1f" + r["project_work_id"]).encode("utf-8")
        ).hexdigest())
        diagnostic_by_stratum[stratum] = candidates[:50]
    diagnostic = [row for route in ROUTES for row in diagnostic_by_stratum[route]]
    check(not ({r["project_work_id"] for r in diagnostic} & audit_set),
          "diagnostic and random80 sampling overlap")
    summary = {
        "version": VERSION,
        "policy": POLICY,
        "status": "SOURCE_SCREENING_ONLY_NO_SCOPE_RELEASE",
        "active_project_w": len(out),
        "random80_provisional_accepted": len(sample),
        "random80_provisional_bookkeeping": dict(sorted(acceptance.items())),
        "source_only_review_routes": dict(sorted(counts.items())),
        "priority_bibliographic_review_rows": len(risk),
        "stratified_diagnostic_review_rows_excluding_random80": len(diagnostic),
        "stratified_diagnostic_counts": {k:len(v) for k,v in diagnostic_by_stratum.items()},
        "automatic_in_scope": 0,
        "automatic_out_of_scope": 0,
        "membership_released": False,
        "openalex_or_goodreads_metrics_imported": False,
        "methodological_limits": [
            "OL edition-minimum year is not first original publication.",
            "Wikidata P577 is not verified first-publication year; P407 is not proof of original language.",
            "OL fiction/criticism/short-story subject fields are only review signals.",
            "Accepted provisional random-80 judgments are not independently checked final labels.",
            "All 32,066 W remain represented, including possible exclusions and 4 source-light W.",
            "No eligibility prevalence estimate or all-W primary scope denominator is produced.",
            "No OpenAlex measures, Goodreads missingness, source IDs or frozen corpora were modified.",
        ],
    }
    return out, risk, sample, diagnostic, summary


def write_tsv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, delimiter="\t", lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", type=Path, default=Path.cwd())
    ap.add_argument("--combined", type=Path, default=Path(DEFAULT_COMBINED))
    ap.add_argument("--review80", type=Path, default=Path(DEFAULT_REVIEW80))
    ap.add_argument("--output-dir", type=Path, default=Path(DEFAULT_OUTPUT))
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--skip-frozen-sha-check", action="store_true", help="Only for tests, never for production")
    args = ap.parse_args()
    root = args.repo_root.resolve()
    resolve = lambda p: p if p.is_absolute() else root / p
    combined = resolve(args.combined)
    review = resolve(args.review80)
    output = resolve(args.output_dir)
    if not args.check_only:
        check(not output.exists(), f"refuse overwrite: {output}")
    if not args.skip_frozen_sha_check:
        check(sha256(combined) == EXPECTED_COMBINED_SHA256, "frozen combined evidence SHA mismatch")
    source = read_tsv(combined, REQUIRED_SOURCE, "combined")
    review80 = read_tsv(review, REQUIRED_REVIEW, "review80")
    full, queue, sample, diagnostic, summary = build(source, review80)
    print("QC PASS / NO AUTOMATIC SCOPE DECISION / NO UPSTREAM CHANGES")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.check_only:
        print("CHECK ONLY: nothing written")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".v02a_screen_", dir=output.parent) as tmpdir:
        tmp = Path(tmpdir)
        artifacts = {
            "all_project_w_scope_source_screening_v0_1.tsv": full,
            "bibliographic_exception_queue_v0_1.tsv": queue,
            "fixed_random80_provisional_overlay_v0_1.tsv": sample,
            "separate_stratified_diagnostic_review_v0_1.tsv": diagnostic,
        }
        hashes = {}
        fields = list(full[0])
        for name, data in artifacts.items():
            path = tmp / name
            write_tsv(path, data, fields)
            hashes[name] = {"rows":len(data), "sha256":sha256(path)}
        report = tmp / "summary_v0_1.json"
        report.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        hashes[report.name] = {"sha256":sha256(report)}
        manifest = {
            "version": VERSION,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "inputs": {"combined": {"path":str(combined), "sha256":sha256(combined)},
                       "researcher_accepted_random80": {"path":str(review), "sha256":sha256(review)}},
            "script_sha256": sha256(Path(__file__)),
            "outputs": hashes,
            "source_mutation": False,
            "release": False,
        }
        (tmp / "manifest_v0_1.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        check(not output.exists(), "output appeared during calculation")
        tmp.rename(output)
    print("NEW OUTPUT:", output)


if __name__ == "__main__":
    main()