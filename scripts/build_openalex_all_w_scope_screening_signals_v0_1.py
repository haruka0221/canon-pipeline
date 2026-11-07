#!/usr/bin/env python3
"""Exploratory, non-adjudicative all-W scope evidence/screening-priority diagnostic.

Inputs are frozen combined OL/Wikidata evidence and frozen v0.2 comparison.
No original-publication-year inference, Work merges, corpus labels or metric changes.
Does not inspect any model predictions/holdouts. --check-only writes nothing.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

VERSION = "scope_all_w_source_signal_priority_v0_1"
EXPECTED_W = 32066
DEFAULT_SCOPE = "derived/scope/scope_combined_bibliographic_evidence_v0_1/scope_combined_project_w_bibliographic_evidence_v0_1.tsv"
DEFAULT_VIS = "derived/openalex_production/analysis_v3_ol_goodreads_provisional_comparison_v0_2/all_project_w_provisional_visibility_ol_goodreads.tsv"
DEFAULT_TEMPLATE = "derived/scope/scope_evidence_pilot_v1/scope_evidence_review_template_v1.tsv"
DEFAULT_OUT = "derived/scope/scope_all_w_source_signal_priority_v0_1"
REQUIRED_SCOPE = {
    "project_work_id", "current_ol_work_ids_json", "historical_titles_json",
    "historical_authors_json", "historical_edition_derived_min_years_json",
    "historical_subject_keys_json", "bibliographic_evidence_status",
    "wikidata_qid", "wd_p577_parsed_positive_years_json",
    "wd_p407_values_json", "wd_p31_values_json", "bibliographic_source_combination",
}
REQUIRED_VIS = {
    "project_work_id", "query_title_display", "query_author_display",
    "exploratory_article_chapter_dissertation_pairs", "v3_provisional_operational_pairs",
    "goodreads_metric_status", "goodreads_ratings_count", "accepted_goodreads_work_id",
    "visibility_measurement_status", "any_shared_query_risk", "scope_researcher_status",
}
SUBJECT_PATTERN = re.compile(r"(?i)\b(?:poetry|poems|plays|dramatic works|drama|literary criticism|criticism|bibliograph(?:y|ies)|short stories|antholog(?:y|ies)|collected works|essays|reference works|textbooks)\b")


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as stream:
        for part in iter(lambda: stream.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def verify(condition, message):
    if not condition:
        raise ValueError("QC FAILED: " + message)


def read_tsv(path: Path, required, label: str) -> list[dict[str, str]]:
    verify(path.is_file(), f"{label} file missing: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        verify(reader.fieldnames is not None, f"{label} empty header")
        verify(required <= set(reader.fieldnames), f"{label} missing columns: {sorted(required - set(reader.fieldnames))}")
        records = list(reader)
    verify(all(None not in r for r in records), f"{label} row column mismatch")
    verify(all(r["project_work_id"] for r in records), f"{label} blank W ID")
    verify(len({r["project_work_id"] for r in records}) == len(records), f"{label} duplicate W IDs")
    return records


def array(raw: str, label: str) -> list:
    try:
        result = json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"QC FAILED: bad JSON in {label}: {raw[:120]}") from exc
    verify(isinstance(result, list), f"{label} must be JSON array")
    return result


def positive_years(items: list) -> list[int]:
    years = []
    for item in items:
        s = str(item).strip()
        if re.fullmatch(r"\d{4}", s):
            y = int(s)
            if 1000 <= y <= 2100:
                years.append(y)
    return sorted(set(years))


def numeric(raw: str, label: str) -> int | None:
    s = str(raw).strip()
    if not s:
        return None
    verify(re.fullmatch(r"\d+(?:\.0+)?", s) is not None, f"bad numeric {label}: {s}")
    return int(float(s))


def yes(raw: str) -> bool:
    s = str(raw).strip().lower()
    verify(s in {"true", "false", "1", "0", "yes", "no"}, f"bad boolean: {raw}")
    return s in {"true", "1", "yes"}


def year_signal(years: list[int]) -> str:
    if not years:
        return "NO_DATED_SIGNAL"
    inside = any(1880 <= y <= 1950 for y in years)
    before = any(y < 1880 for y in years)
    after = any(y > 1950 for y in years)
    if sum((inside, before, after)) > 1:
        return "MIXED_PERIOD_YEAR_SIGNALS"
    if inside:
        return "ONLY_1880_1950_YEAR_SIGNALS"
    if before:
        return "ONLY_PRE_1880_YEAR_SIGNALS"
    return "ONLY_POST_1950_YEAR_SIGNALS"


def write_tsv(path: Path, rows: list[dict], columns: list[str]):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, delimiter="\t", lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def build(scope: list[dict], vis: list[dict], random_w: set[str]):
    verify(len(scope) == len(vis) == EXPECTED_W, f"input W counts differ from {EXPECTED_W}: {len(scope)} {len(vis)}")
    src = {r["project_work_id"]: r for r in scope}
    vf = {r["project_work_id"]: r for r in vis}
    verify(set(src) == set(vf), "W sets mismatch")
    verify(len(random_w) == 80 and random_w <= set(src), "frozen random 80 is missing or mismatched")
    out = []
    counters = defaultdict(Counter)
    oa_measured = 0
    gr_observed = 0
    shared = 0
    shared_with_observed_goodreads = 0
    adopted_qid_w = 0
    for wid in sorted(src):
        s, v = src[wid], vf[wid]
        ol_ids = array(s["current_ol_work_ids_json"], wid + ".ol")
        ol_years = positive_years(array(s["historical_edition_derived_min_years_json"], wid + ".olyear"))
        wd_years = positive_years(array(s["wd_p577_parsed_positive_years_json"], wid + ".wdyear"))
        wd_langs = [str(a) for a in array(s["wd_p407_values_json"], wid + ".wdlang")]
        wd_types = [str(a) for a in array(s["wd_p31_values_json"], wid + ".wdtype")]
        titles = array(s["historical_titles_json"], wid + ".titles")
        authors = array(s["historical_authors_json"], wid + ".authors")
        subjects = [str(a) for a in array(s["historical_subject_keys_json"], wid + ".subjects")]
        matched_terms = sorted({sub for sub in subjects if SUBJECT_PATTERN.search(sub)})
        core = numeric(v["exploratory_article_chapter_dissertation_pairs"], "core3=" + wid)
        total = numeric(v["v3_provisional_operational_pairs"], "alltypes=" + wid)
        ratings = numeric(v["goodreads_ratings_count"], "ratings=" + wid)
        verify(core is None or total is not None, "CORE3 measured when all types missing " + wid)
        verify(core is None or core <= total, "CORE3 exceeds total " + wid)
        risk = yes(v["any_shared_query_risk"])
        measured = core is not None
        observed = ratings is not None
        has_wd = bool(s["wikidata_qid"])
        ol_sig, wd_sig = year_signal(ol_years), year_signal(wd_years)
        dated = year_signal(sorted(set(ol_years + wd_years)))
        prior_review = v["scope_researcher_status"].strip()
        verify(prior_review in {"NOT_RESEARCHER_ADJUDICATED", "", "NOT_ADJUDICATED"},
               "unexpected prior human scope status " + wid + ": " + prior_review)
        # This is only a source-signal review inventory, NEVER original-language or period classification.
        if dated == "NO_DATED_SIGNAL":
            period_signal = "NO_DATE_EVIDENCE"
        elif dated == "MIXED_PERIOD_YEAR_SIGNALS":
            period_signal = "MIXED_DATE_EVIDENCE_REVIEW"
        else:
            period_signal = dated
        # Priority is for bibliographic review effort, NOT inclusion status or literary value.
        score = 0
        reasons = []
        if wid in random_w:
            reasons.append("FROZEN_INDEPENDENT_RANDOM_80")
        if risk:
            score += 4; reasons.append("SHARED_QUERY_IDENTITY_RISK")
        if len(ol_ids) != 1:
            score += 3; reasons.append("ZERO_OR_MULTIPLE_OL_TARGETS")
        if not ol_years and not wd_years:
            score += 2; reasons.append("NO_YEAR_SIGNAL")
        if dated == "MIXED_PERIOD_YEAR_SIGNALS":
            score += 3; reasons.append("MIXED_YEAR_SIGNALS")
        if wd_langs and "Q1860" not in wd_langs:
            score += 2; reasons.append("WD_P407_WITHOUT_ENGLISH_SIGNAL")
        if matched_terms:
            score += 2; reasons.append("OL_SUBJECT_NON_NOVEL_REVIEW_SIGNAL")
        if core is not None and core >= 25:
            score += 3; reasons.append("HIGH_CORE3_CANDIDATE_PAIRS")
        elif core is not None and core >= 10:
            score += 2; reasons.append("CORE3_TEN_PLUS")
        if core is None:
            reasons.append("OPENALEX_NOT_MEASURED")
        if not has_wd:
            reasons.append("NO_ADOPTED_WIKIDATA_QID")
        if not observed:
            reasons.append("GOODREADS_NOT_OBSERVED")
        rec = {
            "project_work_id": wid,
            "query_title_display": v["query_title_display"],
            "query_author_display": v["query_author_display"],
            "frozen_random_80": str(wid in random_w),
            "bibliographic_source_combination": s["bibliographic_source_combination"],
            "current_ol_work_ids_json": s["current_ol_work_ids_json"],
            "current_ol_count": len(ol_ids),
            "historical_titles_json": json.dumps(titles, ensure_ascii=False, separators=(",", ":")),
            "historical_authors_json": json.dumps(authors, ensure_ascii=False, separators=(",", ":")),
            "ol_edition_derived_years_json": json.dumps(ol_years, separators=(",", ":")),
            "ol_edition_derived_year_signal": ol_sig,
            "wikidata_qid": s["wikidata_qid"],
            "wd_p577_years_json": json.dumps(wd_years, separators=(",", ":")),
            "wd_p577_year_signal": wd_sig,
            "wd_p407_values_json": json.dumps(wd_langs, ensure_ascii=False, separators=(",", ":")),
            "wd_p407_includes_english_statement": str("Q1860" in wd_langs),
            "wd_p31_values_json": json.dumps(wd_types, ensure_ascii=False, separators=(",", ":")),
            "ol_subject_form_review_terms_json": json.dumps(matched_terms, ensure_ascii=False, separators=(",", ":")),
            "combined_period_signal_not_original_year": period_signal,
            "review_priority_score": score,
            "review_reasons_json": json.dumps(reasons, ensure_ascii=False, separators=(",", ":")),
            "shared_query_identity_risk": str(risk),
            "openalex_core3_candidate_pairs": "" if core is None else core,
            "openalex_all_types_candidate_pairs": "" if total is None else total,
            "goodreads_historical_ratings_observed": str(observed),
            "goodreads_metric_status": v["goodreads_metric_status"],
            "existing_scope_researcher_status": prior_review,
            "automatic_scope_decision": "NONE_NOT_ADJUDICATED",
            "original_publication_year_verified": "",
            "original_language_verified": "",
            "individual_novel_or_novella_verified": "",
            "source_entity_link_verified": "",
            "researcher_scope_decision": "",
            "reviewer_notes": "",
        }
        out.append(rec)
        counters["period_signal"][period_signal] += 1
        counters["ol_edition_year_signal"][ol_sig] += 1
        counters["wd_year_signal"][wd_sig] += 1
        counters["bibliographic_source_combination"][s["bibliographic_source_combination"]] += 1
        counters["priority_score"][str(score)] += 1
        oa_measured += measured
        gr_observed += observed
        shared += risk
        shared_with_observed_goodreads += bool(risk and observed)
        adopted_qid_w += has_wd
    verify(oa_measured == 31713, f"OA measured expected 31713, got {oa_measured}")
    verify(gr_observed == 4642, f"GR historical ratings expected 4642, got {gr_observed}")
    verify(shared == 1797, f"shared risk expected 1797, got {shared}")
    verify(shared_with_observed_goodreads == 0, "unexpected GR observed within frozen shared-query-risk cohort")
    verify(adopted_qid_w == 6177, f"adopted Wikidata QID coverage expected 6177, got {adopted_qid_w}")
    verify(sum(v for v in counters["bibliographic_source_combination"].values()) == EXPECTED_W, "broken source totals")
    queue = sorted(out, key=lambda r:(-int(r["review_priority_score"]), -int(r["openalex_core3_candidate_pairs"] or 0), r["project_work_id"]))[:400]
    random = [r for r in out if r["project_work_id"] in random_w]
    verify(len(random) == 80, "random subset not 80")
    summary = {
        "release": VERSION,
        "status": "EXPLORATORY_EVIDENCE_SIGNALS_AND_REVIEW_PRIORITY_ONLY",
        "active_project_w": EXPECTED_W,
        "oa_measured_w": oa_measured,
        "historical_goodreads_observed_w": gr_observed,
        "shared_query_risk_w": shared,
        "shared_query_risk_w_with_goodreads_observed": shared_with_observed_goodreads,
        "adopted_wikidata_qid_w": adopted_qid_w,
        "frozen_independent_random80_w": len(random),
        "all_w_automatic_scope_decisions": 0,
        "researcher_scope_decisions_created": 0,
        "categories": {k:dict(sorted(v.items())) for k,v in counters.items()},
        "limits": [
            "OL historical minimum years come from linked editions; they are NOT original-work publication years.",
            "Wikidata P577 years are bibliographic statements, not verified first-original years.",
            "Wikidata P407 language statements are NOT proof of an English original; P31 is NOT proof of a single novel/novella.",
            "Historical OL subjects can describe topics, editions or collections; form regex is a review signal only.",
            "Priority scores rank follow-up effort, not evidence confidence or literary canonicity.",
            "No work-level IN_SCOPE or OUT_OF_SCOPE has been asserted.",
            "Goodreads observed values are historical UCSD carrier observations in frozen v0.2 only.",
            "OA core3 counts are unverified candidate document pairs; 353 unmeasured W stay NA.",
            "Random 80 remains separately identifiable; no correctness/prevalence estimates inferred from AI candidate labels.",
            "No Project W merges, metric allocations, reranked percentiles, source updates or human adjudications."
        ],
    }
    return out, queue, random, summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", type=Path, default=Path.cwd())
    ap.add_argument("--combined", type=Path, default=Path(DEFAULT_SCOPE))
    ap.add_argument("--comparison", type=Path, default=Path(DEFAULT_VIS))
    ap.add_argument("--random80", type=Path, default=Path(DEFAULT_TEMPLATE))
    ap.add_argument("--output-dir", type=Path, default=Path(DEFAULT_OUT))
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()
    root = args.repo_root.resolve()
    def resolve(x): return x if x.is_absolute() else root / x
    files = {"combined":resolve(args.combined), "comparison":resolve(args.comparison), "random80_template":resolve(args.random80)}
    dest = resolve(args.output_dir)
    if not args.check_only:
        verify(not dest.exists(), f"output directory already exists; refuse overwrite: {dest}")
    s = read_tsv(files["combined"], REQUIRED_SCOPE, "scope")
    v = read_tsv(files["comparison"], REQUIRED_VIS, "comparison")
    t = read_tsv(files["random80_template"], {"project_work_id", "is_independent_random_active_sample"}, "random80 template")
    random_w = {r["project_work_id"] for r in t if yes(r["is_independent_random_active_sample"])}
    full, queue, random, summary = build(s, v, random_w)
    print("QC PASSED (inputs validated, no upstream mutation)")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.check_only:
        print("CHECK ONLY: NO FILES WRITTEN")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".scope_signal_v0_1_", dir=dest.parent) as scratch:
        tmp = Path(scratch)
        outputs = {
            "all_project_w_bibliographic_source_signals_v0_1.tsv":full,
            "review_priority_top400_source_signals_v0_1.tsv":queue,
            "fixed_random80_source_signals_v0_1.tsv":random,
        }
        sha_out = {}
        cols = list(full[0])
        for name, rows in outputs.items():
            f = tmp / name
            write_tsv(f, rows, cols)
            sha_out[name] = {"rows":len(rows),"sha256":sha(f)}
        sumfile = tmp / "summary_v0_1.json"
        sumfile.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        sha_out[sumfile.name] = {"sha256":sha(sumfile)}
        manifest = {
            "release": VERSION,
            "created_utc":datetime.now(timezone.utc).isoformat(),
            "input_sha256":{k:{"path":str(p),"sha256":sha(p)} for k,p in files.items()},
            "builder_sha256":sha(Path(__file__)),
            "outputs":sha_out,
            "upstream_mutated":False,
        }
        (tmp / "manifest_v0_1.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        verify(not dest.exists(), f"output directory appeared during processing: {dest}")
        tmp.rename(dest)
    print("OUTPUT:", dest)


if __name__ == "__main__":
    main()
