#!/usr/bin/env python3
"""Non-destructive v3 OpenAlex × Open Library editions × Goodreads metrics.

Exploratory; not an approved corpus-scope or scholarly-visibility release.
- Only current Goodreads crosswalk MATCH identities are accepted.
- Older UCSD Goodreads match file is used solely as a work-ID -> counts carrier,
  never to assign new Goodreads identities.
- Missing/unresolved identities/metrics remain NA (never zero).
- The OL edition measure is source-Work-specific; multi-OL work totals are
  retained only as labeled diagnostics, not used for one-to-one correlations.
- Project W identity overlaps and original-work scope are NOT fixed here.
No external APIs and no modifications to any upstream dataset.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
import json, hashlib, tempfile
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OA = ROOT / "derived/openalex_production"
BRIDGE = OA / "analysis_v3_visibility_lenses_scope_bridge_v0_1/work_visibility_with_scope_evidence.tsv"
CROSS = ROOT / "derived/crosswalks/goodreads_work_crosswalk_v1.tsv"
CROSS_SUMMARY = ROOT / "derived/crosswalks/goodreads_work_crosswalk_v1_summary.json"
EDITIONS = ROOT / "derived/ol_edition_counts.tsv"
UCSD = ROOT / "derived/goodreads_ucsd_match.tsv"
OUT = OA / "analysis_v3_ol_goodreads_provisional_comparison_v0_1"
TOP2_IDS = {
    "W000030950", "W000017666", "W000016985",
    "W000014272", "W000014830", "W000017583", "W000030652"
}

def verify(ok, why):
    if not ok:
        raise RuntimeError("QC FAILED: " + why)

def sha(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for part in iter(lambda: f.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()

def read(path):
    return pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)

def ol_id(x):
    s = str(x).strip()
    if s.startswith("/works/"):
        s = s[len("/works/"):]
    return s

def numeric(x):
    return pd.to_numeric(x.replace("", pd.NA), errors="coerce")

def id_list(v):
    a = json.loads(v)
    verify(isinstance(a, list), "Expected JSON array of OL IDs")
    items = [ol_id(x) for x in a]
    verify(all(items) and len(items) == len(set(items)), "Invalid/duplicate OL work ID in source array")
    return items

def corr_table(df, x, y, cohort):
    d = df.loc[
        df[x].notna() & df[y].notna() &
        df.openalex_r2r3_query_coverage.eq("QUERIED_R2_OR_R3")
    ].copy()
    if cohort == "EXCLUDE_TOP2_RISK_W":
        d = d.loc[~d.project_work_id.isin(TOP2_IDS)]
    verify((d[[x,y]] >= 0).all().all(), "Negative counts in correlation sample")
    n = len(d)
    return {
        "academic_indicator":x, "comparison_indicator":y, "cohort":cohort,
        "complete_case_works":n,
        "spearman_rank_corr": (
            round(float(d[x].rank().corr(d[y].rank())), 6)
            if n >= 3 else None),
        "pearson_corr_log1p": (
            round(float(np.log1p(d[x].astype(float)).corr(
                np.log1p(d[y].astype(float)))), 6)
            if n >= 3 else None)
    }

def main():
    verify(not OUT.exists(), f"Output already exists: {OUT}")
    for p in (BRIDGE, CROSS, CROSS_SUMMARY, EDITIONS, UCSD):
        verify(p.is_file(), f"Missing input: {p}")
    x = read(BRIDGE)
    verify(len(x)==32066 and x.project_work_id.is_unique,
           "All W evidence bridge cardinality differs")
    verify({"project_work_id","current_ol_work_ids_json","openalex_r2r3_query_coverage",
           "query_title_display","query_author_display",
           "v3_provisional_operational_pairs",
           "exploratory_article_chapter_dissertation_pairs",
           "visibility_measurement_status"} <= set(x.columns),
           "Required columns missing in visibility/scope bridge")
    x["ol_work_ids"] = x.current_ol_work_ids_json.map(id_list)
    x["current_ol_source_work_count"] = x.ol_work_ids.map(len)
    x["single_current_ol_work_id"] = x.ol_work_ids.map(
        lambda ids: ids[0] if len(ids)==1 else "")
    x["current_ol_work_ids_semicolon"] = x.ol_work_ids.map(lambda a:";".join(a))

    ed = read(EDITIONS)
    verify({"work_key","edition_count"} <= set(ed.columns),
           "Edition counts unexpected schema")
    ed["ol_work_id"] = ed.work_key.map(ol_id)
    verify(ed.ol_work_id.is_unique, "Duplicate OL Work IDs in edition counts")
    ed["editions_n"] = numeric(ed.edition_count)
    verify(ed.editions_n.dropna().ge(0).all(), "Negative OL edition count")
    editions = ed.set_index("ol_work_id")["editions_n"].to_dict()
    x["ol_edition_count_single_source_work"] = x.single_current_ol_work_id.map(editions)
    x["ol_edition_count_multiple_sources_exploratory_sum"] = x.ol_work_ids.map(
        lambda ids: (sum(int(editions[z]) for z in ids)
                     if len(ids)>1 and all(z in editions and pd.notna(editions[z]) for z in ids)
                     else pd.NA))
    x["ol_edition_count_metric"] = x.ol_edition_count_single_source_work
    x.loc[x.current_ol_source_work_count.ne(1), "ol_edition_count_metric"] = pd.NA

    cw = read(CROSS)
    verify({"ol_work_id","crosswalk_decision","goodreads_work_id",
            "candidate_goodreads_work_id"} <= set(cw.columns),
           "Current Goodreads crosswalk columns missing")
    verify(cw.ol_work_id.is_unique and len(cw)==34789,
           "Crosswalk cardinality/uniqueness changed")
    expected = json.loads(CROSS_SUMMARY.read_text())["crosswalk_decision_counts"]
    actual = cw.crosswalk_decision.value_counts().to_dict()
    verify(actual == expected, f"Crosswalk status count mismatch: {actual}")
    verify((cw.loc[cw.crosswalk_decision.eq("MATCH"),"goodreads_work_id"] != "").all(),
           "Accepted Goodreads Work ID missing")
    verify((cw.loc[~cw.crosswalk_decision.eq("MATCH"),"goodreads_work_id"] == "").all(),
           "Nonaccepted Goodreads ID unexpectedly populated")
    accepted = cw.loc[cw.crosswalk_decision.eq("MATCH")].set_index("ol_work_id")[
        "goodreads_work_id"].to_dict()
    x["accepted_goodreads_ids"] = x.ol_work_ids.map(
        lambda ids: sorted({accepted[z] for z in ids if z in accepted}))
    x["accepted_goodreads_id_count"] = x.accepted_goodreads_ids.map(len)
    x["accepted_goodreads_work_id"] = x.accepted_goodreads_ids.map(
        lambda a: a[0] if len(a)==1 else "")
    x["accepted_goodreads_ids_semicolon"] = x.accepted_goodreads_ids.map(
        lambda a: ";".join(a))

    # Older match rows are NOT trusted as identity judgments here; only use
    # their numerical counts when exact Goodreads Work ID equals current MATCH.
    old = read(UCSD)
    verify({"work_id","ratings_count","text_reviews_count"} <= set(old.columns),
           "Legacy UCSD metric carrier unexpected schema")
    old = old.loc[old.work_id.ne("")].copy()
    for metric in ("ratings_count", "text_reviews_count"):
        old[metric] = numeric(old[metric])
    verify(old[["ratings_count","text_reviews_count"]].dropna().ge(0).all().all(),
           "Negative UCSD count")
    conflict = set()
    metric_rows = []
    for gr_id, group in old.groupby("work_id", sort=False):
        values = []
        conflict_here = False
        for metric in ("ratings_count","text_reviews_count"):
            unique = group[metric].dropna().unique()
            if len(unique)>1:
                conflict_here = True
            values.append(unique[0] if len(unique)==1 else pd.NA)
        if conflict_here:
            conflict.add(gr_id)
            continue
        metric_rows.append((gr_id,*values))
    lookup = pd.DataFrame(metric_rows, columns=[
        "goodreads_work_id","goodreads_ratings_count","goodreads_text_reviews_count"])
    verify(lookup.goodreads_work_id.is_unique,
           "Duplicate GR Work IDs in metric carrier after QC")
    metrics = lookup.set_index("goodreads_work_id")
    for c in ["goodreads_ratings_count","goodreads_text_reviews_count"]:
        x[c] = x.accepted_goodreads_work_id.map(metrics[c])
        x.loc[x.accepted_goodreads_id_count.ne(1),c] = pd.NA
    x["goodreads_identity_status"] = np.select(
        [
            x.accepted_goodreads_id_count.eq(0),
            x.accepted_goodreads_id_count.eq(1),
            x.accepted_goodreads_id_count.gt(1)
        ], ["NO_ACCEPTED_IDENTITY","ONE_ACCEPTED_IDENTITY",
            "MULTIPLE_ACCEPTED_IDS_REVIEW"],default="ERROR")
    x["goodreads_metric_status"] = np.select(
        [
            x.accepted_goodreads_id_count.eq(0),
            x.accepted_goodreads_id_count.gt(1),
            x.accepted_goodreads_work_id.isin(conflict),
            x.goodreads_ratings_count.isna(),
            x.goodreads_ratings_count.notna(),
        ], ["NO_ACCEPTED_IDENTITY", "MULTIPLE_ACCEPTED_IDS_REVIEW",
            "CONFLICTING_LEGACY_METRIC_VALUES",
            "ACCEPTED_ID_NO_LEGACY_METRIC", "ACCEPTED_ID_WITH_METRIC"],
        default="UNEXPECTED")
    x["top2_identity_risk"] = x.project_work_id.isin(TOP2_IDS)
    x["publication_scope_status"] = "NOT_RESEARCHER_ADJUDICATED"
    x["ol_edition_metric_status"] = np.select(
        [
            x.current_ol_source_work_count.eq(0),
            x.current_ol_source_work_count.gt(1),
            x.ol_edition_count_metric.isna(),
            x.ol_edition_count_metric.notna()
        ], ["NO_CURRENT_OL_WORK","MULTIPLE_CURRENT_OL_WORKS_REVIEW",
            "SOURCE_OL_EDITION_COUNT_MISSING","ONE_OL_WITH_EDITION_COUNT"],
        default="UNEXPECTED")
    # Source (OL) Edition counts and GR count are not an origin-year or
    # corpus-scope decision. Keep historical scope evidence columns untouched.
    measures = [
        "v3_provisional_operational_pairs",
        "exploratory_article_chapter_dissertation_pairs",
        "ol_edition_count_metric", "goodreads_ratings_count",
        "goodreads_text_reviews_count",
    ]
    for name in measures:
        x[name] = pd.to_numeric(x[name],errors="coerce")
    # Nonqueried works and one source-light W were already NA in upstream bridge.
    check_na = x.visibility_measurement_status.isin(
        ["NOT_QUERIED_R2_R3", "HOLD_PRIMARY_SUCCESSOR_NOT_RERETRIEVED"])
    verify(x.loc[check_na,"v3_provisional_operational_pairs"].isna().all(),
           "Nonmeasured work was incorrectly turned into zero")
    verify(x["v3_provisional_operational_pairs"].notna().sum()==32066-353,
           "OpenAlex visibility measured-W count unexpected")

    comparisons = []
    academic = ["v3_provisional_operational_pairs",
                "exploratory_article_chapter_dissertation_pairs"]
    for ac in academic:
        for co in ["ol_edition_count_metric","goodreads_ratings_count",
                   "goodreads_text_reviews_count"]:
            for cohort in ["ALL_ELIGIBLE_BRIDGE_ROWS","EXCLUDE_TOP2_RISK_W"]:
                comparisons.append(corr_table(x,ac,co,cohort))
    c = pd.DataFrame(comparisons)
    # Only compare paired nonmissing values; the ranking difference describes
    # empirical percentile asymmetry in this matched sample, NOT a canon label.
    contrast = x.loc[
        x.openalex_r2r3_query_coverage.eq("QUERIED_R2_OR_R3") &
        ~x.top2_identity_risk &
        x.exploratory_article_chapter_dissertation_pairs.notna() &
        x.goodreads_ratings_count.notna()].copy()
    contrast["oa_percentile"] = contrast[
        "exploratory_article_chapter_dissertation_pairs"].rank(pct=True)
    contrast["goodreads_percentile"] = contrast.goodreads_ratings_count.rank(pct=True)
    contrast["academic_minus_public_percentile"] = (
        contrast.oa_percentile-contrast.goodreads_percentile)
    contrast = contrast.sort_values(
        ["academic_minus_public_percentile","project_work_id"],
        ascending=[False,True])
    selected = [
        "project_work_id","query_title_display","query_author_display",
        "exploratory_article_chapter_dissertation_pairs",
        "goodreads_ratings_count","oa_percentile","goodreads_percentile",
        "academic_minus_public_percentile","current_ol_work_ids_semicolon",
        "accepted_goodreads_work_id","publication_scope_status"
    ]
    notes = {
        "release":"openalex-v3-ol-goodreads-provisional-comparison-v0_1",
        "status":"EXPLORATORY_MATCHED_DATA_NOT_SCOPE_ADJUDICATED",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "all_project_w":len(x),
        "queried_and_measured_w":int(x.v3_provisional_operational_pairs.notna().sum()),
        "goodreads_crosswalk_current_status_counts":actual,
        "w_with_one_accepted_goodreads_id":int(x.accepted_goodreads_id_count.eq(1).sum()),
        "w_with_multiple_accepted_goodreads_ids":int(x.accepted_goodreads_id_count.gt(1).sum()),
        "w_with_goodreads_numeric_ratings":int(x.goodreads_ratings_count.notna().sum()),
        "w_with_one_ol_and_known_editions":int(x.ol_edition_count_metric.notna().sum()),
        "legacy_goodreads_metric_conflict_ids":len(conflict),
        "paired_non-top2_core3_vs_goodreads":len(contrast),
        "correlations":comparisons,
        "limitations":[
            "Current Goodreads v1 MATCH defines accepted identities; older UCSD match provides only numeric metrics at identical Goodreads ID.",
            "Goodreads metrics come from the historical UCSD dataset, not current real-time ratings.",
            "No accepted Goodreads identity or missing numerical metric is converted into zero.",
            "OL editions count Open Library Edition records, not independent publication events.",
            "Multi-OL Work groups are held out from the one-source-editions correlation; exploratory sums are diagnostic only.",
            "No original-English/1880-1950/novel form scope adjudication.",
            "Article+chapter+dissertation remains a type-based proxy, not scholarly verification.",
            "Raw W-level comparisons include possible duplicate identities; excluding top two shared-query clusters is sensitivity only.",
            "Matched complete cases are not a random sample, correlations are descriptive and subject to crosswalk selection bias.",
            "Data cannot support claims of causal canon formation or corpus-wide missingness from these descriptive correlations.",
            "The 600 holdout and all input metrics/results remain unchanged."
        ]
    }
    with tempfile.TemporaryDirectory(prefix=".oa_ol_gr_", dir=OA) as td:
        stage = Path(td)
        outfiles = {
            "all_project_w_provisional_visibility_ol_goodreads.tsv":x.drop(
                columns=["ol_work_ids","accepted_goodreads_ids"]),
            "complete_case_correlations.tsv":c,
            "academic_vs_goodreads_percentile_contrasts.tsv":contrast[selected],
        }
        for n, frame in outfiles.items():
            frame.to_csv(stage/n,sep="\t",index=False)
        s = stage/"summary.json"
        s.write_text(json.dumps(notes,ensure_ascii=False,indent=2)+"\n",
                     encoding="utf-8")
        man = stage/"manifest.json"
        man.write_text(json.dumps({
            "source_sha256":{str(p):sha(p) for p in (BRIDGE,CROSS,CROSS_SUMMARY,EDITIONS,UCSD)},
            "outputs_sha256":{n:sha(stage/n) for n in outfiles} |
                             {"summary.json":sha(s)},
            "builder_sha256":sha(Path(__file__)),
            "no_existing_data_modified":True
        },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        verify(not OUT.exists(),"Output directory appeared during preparation")
        stage.rename(OUT)
    print("QC PASSED / NO API / UPSTREAM UNCHANGED")
    print("All works:",len(x))
    print("OpenAlex measured:",notes["queried_and_measured_w"])
    print("OL works with single-source edition count:",notes["w_with_one_ol_and_known_editions"])
    print("W with single accepted GR identity:",notes["w_with_one_accepted_goodreads_id"])
    print("W with numerical GR ratings:",notes["w_with_goodreads_numeric_ratings"])
    print("Legacy GR metric IDs with conflicts (excluded):",len(conflict))
    print("\nDescriptive correlations (matched cases only; NO SCOPE SCREENING):")
    print(c.to_string(index=False))
    print("\nTop 15 provisional academic-over-public percentile differences:")
    print(contrast[selected].head(15).to_string(index=False))
    print("\nOutput:",OUT)

if __name__ == "__main__":
    main()
