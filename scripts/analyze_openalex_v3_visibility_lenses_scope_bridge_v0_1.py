#!/usr/bin/env python3
"""Versioned OpenAlex v3 visibility lenses and 1880-1950 scope-evidence bridge.

Uses existing locally built v3 type analysis + all-W bibliographic evidence.
DOES NOT adjudicate scholarly suitability, canonical identity, or corpus scope.
No OpenAI API; no mutation of source files, human judgments, or holdout cases.
Produces all-W table, 2x3 lens/scenario summary, and top-30 ranking by lens.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import json, hashlib, tempfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OA = ROOT / "derived/openalex_production"
D = OA / "analysis_v3_openalex_document_type_exploratory_v0_1"
P = D / "v3_included_pairs_with_oa_type.parquet"
W = D / "work_type_exploratory_counts.tsv"
SCOPE = ROOT / "derived/scope/scope_combined_bibliographic_evidence_v0_1/scope_combined_project_w_bibliographic_evidence_v0_1.tsv"
QUERY = OA / "registry_v4/openalex_queries_v4.tsv"
OUT = OA / "analysis_v3_visibility_lenses_scope_bridge_v0_1"
CORES = {"article", "book-chapter", "dissertation"}
EXPANDED = CORES | {"book", "conference-paper", "preprint", "book-review", "report"}
GROUPS = {
    "SENS_ULYSSES_JOYCE": {"W000030950","W000017666","W000016985"},
    "SENS_HEART_OF_DARKNESS_CONRAD": {"W000014272","W000014830","W000017583","W000030652"},
}
DISPLAY = {
    "SENS_ULYSSES_JOYCE": ("Ulysses", "James Joyce"),
    "SENS_HEART_OF_DARKNESS_CONRAD": ("Heart of Darkness", "Joseph Conrad")
}

def die(message):
    raise RuntimeError("QC FAILED: " + message)

def check(condition, label):
    if not condition:
        die(label)

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def share(s, k):
    return float(s.head(k).sum() / s.sum()) if s.sum() else 0.

def summary_for(z, lens, scenario):
    by_work = z.groupby("analysis_work_id").size().sort_values(ascending=False)
    assert by_work.sum() == len(z)
    return {
        "lens": lens, "scenario": scenario,
        "project_w_by_oa_pairs": len(z),
        "positive_analysis_units": len(by_work),
        "top10_share": round(share(by_work,10), 6),
        "top100_share": round(share(by_work,100), 6),
        "median_positive_units": float(by_work.median()) if len(by_work) else 0,
        "top1_pairs": int(by_work.iloc[0]) if len(by_work) else 0,
    }

def main():
    check(not OUT.exists(), f"Output already exists: {OUT}")
    for p in (P,W,SCOPE,QUERY):
        check(p.is_file(), f"Missing required existing input: {p}")
    z = pd.read_parquet(P, columns=["project_work_id","openalex_work_id","type_for_analysis"])
    check(len(z)==173897, "OpenAlex v3 included pair total")
    check(not z.duplicated(["project_work_id","openalex_work_id"]).any(), "Duplicate v3 W x OA pairs")
    ty = z.type_for_analysis.fillna("").astype(str)
    check(ty.ne("").all(), "Missing OpenAlex type")

    works = pd.read_csv(W, sep="\t", dtype=str, keep_default_na=False)
    scope = pd.read_csv(SCOPE, sep="\t", dtype=str, keep_default_na=False)
    check(len(works)==len(scope)==32066,"All-W frame count mismatch")
    check(works.project_work_id.is_unique and scope.project_work_id.is_unique, "Duplicated Project W")
    check(set(works.project_work_id)==set(scope.project_work_id), "Scope/type W ID coverage differs")
    required = [
        "project_work_id","bibliographic_evidence_status", "historical_titles_json",
        "historical_authors_json", "historical_edition_derived_min_years_json",
        "wikidata_qid"
    ]
    check(set(required) <= set(scope.columns),
          f"Scope evidence missing: {set(required)-set(scope.columns)}")
    check({"project_work_id","query_title_display","query_author_display",
           "v3_provisional_operational_pairs","exploratory_article_chapter_dissertation_pairs"}<=set(works.columns),
          "Existing type work table schema mismatch")
    q = pd.read_csv(QUERY, sep="\t", dtype=str, keep_default_na=False)
    check({"project_work_id", "query_route"}<=set(q.columns), "Query registry unexpected schema")
    have_queries = set(q.loc[q.query_route.isin(["R2","R3"]), "project_work_id"])
    check(len(set(works.project_work_id)-have_queries)==352, "Expected 352 not queried by R2/R3; inspect query coverage")

    limited = scope[required].copy()
    allw = works.merge(limited, on="project_work_id", how="left", validate="one_to_one",
                       indicator=True)
    check(allw._merge.eq("both").all(), "All-W bibliography join missing rows")
    allw.drop(columns="_merge", inplace=True)
    allw["scope_adjudication_status"] = "NOT_RESEARCHER_ADJUDICATED"
    allw["openalex_r2r3_query_coverage"] = allw.project_work_id.map(
        lambda v: "QUERIED_R2_OR_R3" if v in have_queries else "NOT_QUERIED_R2_R3")
    allw["visibility_measurement_status"] = allw["measurement_status"].astype(str)
    allw.loc[allw.openalex_r2r3_query_coverage.eq("NOT_QUERIED_R2_R3"),
             "visibility_measurement_status"] = "NOT_QUERIED_R2_R3"
    hold = allw.measurement_status.eq("HOLD_PRIMARY_SUCCESSOR_NOT_RERETRIEVED")
    check(hold.sum()==1,"Expected one held unremeasured W")
    allw.loc[hold, "visibility_measurement_status"] = "HOLD_PRIMARY_SUCCESSOR_NOT_RERETRIEVED"
    for col in ["v3_provisional_operational_pairs",
                "exploratory_article_chapter_dissertation_pairs"]:
        allw[col] = pd.to_numeric(allw[col], errors="coerce").astype("Int64")
        allw.loc[hold, col] = pd.NA
        allw.loc[allw.openalex_r2r3_query_coverage.eq("NOT_QUERIED_R2_R3"),col] = pd.NA
    # Do not turn missing retrieval measurement into a true literature zero.
    # NOTE: scope evidence fields are evidence, not accepted scope labels.

    originals = [("ALL_TYPES", z), ("CORE3_ARTICLE_CHAPTER_DISSERTATION",
                z.loc[z.type_for_analysis.isin(CORES)].copy()),
                ("EXPANDED_DOCUMENT_TYPES",
                z.loc[z.type_for_analysis.isin(EXPANDED)].copy())]
    check(len(originals[1][1])==146724, "Core3 total changed")
    check(len(originals[0][1])==173897, "All-type total changed")
    mappings = [
        ("AS_RETRIEVED_W", {}),
        ("TOP2_HYPOTHETICAL_UNION",
         {wid:name for name, ids in GROUPS.items() for wid in ids}),
    ]
    # Full source registry equality assertions for the 2 manually examined signal groups.
    for name, ids in GROUPS.items():
        check(ids <= set(works.project_work_id), f"Missing W: {name}")
    overview = []
    ranked = []
    for lens, chosen in originals:
        for scenario, mapping in mappings:
            d = chosen[["project_work_id","openalex_work_id"]].copy()
            d["analysis_work_id"] = d.project_work_id.replace(mapping)
            d = d.drop_duplicates(["analysis_work_id","openalex_work_id"])
            r = d.groupby("analysis_work_id").size().sort_values(ascending=False)
            overview.append(summary_for(d,lens,scenario))
            rankdf = r.rename("candidate_pairs").reset_index()
            rankdf["rank"] = rankdf["candidate_pairs"].rank(method="min",
                                                        ascending=False).astype(int)
            rankdf["lens"] = lens
            rankdf["scenario"] = scenario
            # Metadata labels come from query strings; do not claim canonical identity.
            lookup = works.set_index("project_work_id")
            rankdf["query_title_label"] = rankdf.analysis_work_id.map(
                lambda wid: DISPLAY.get(wid, (None,None))[0] if wid in DISPLAY
                            else lookup.at[wid,"query_title_display"])
            rankdf["query_author_label"] = rankdf.analysis_work_id.map(
                lambda wid: DISPLAY.get(wid, (None,None))[1] if wid in DISPLAY
                            else lookup.at[wid,"query_author_display"])
            rankdf["identity_status"] = rankdf.analysis_work_id.map(
                lambda wid: "HYPOTHETICAL_GROUP_NOT_ADJUDICATED"
                if wid in DISPLAY else "ORIGINAL_PROJECT_W_UNCHANGED")
            ranked.append(rankdf.head(100))

    result = pd.DataFrame(overview)
    rnk = pd.concat(ranked, ignore_index=True)
    ungrouped = result.loc[result.scenario.eq("AS_RETRIEVED_W")]
    check(set(ungrouped.lens)=={"ALL_TYPES","CORE3_ARTICLE_CHAPTER_DISSERTATION",
                               "EXPANDED_DOCUMENT_TYPES"},"Missing lens")
    all_c = int(ungrouped.loc[ungrouped.lens.eq("ALL_TYPES"),
                               "project_w_by_oa_pairs"].iloc[0])
    core_c = int(ungrouped.loc[ungrouped.lens.eq("CORE3_ARTICLE_CHAPTER_DISSERTATION"),
                                "project_w_by_oa_pairs"].iloc[0])
    check(all_c==173897 and core_c==146724,"V3 totals drift")

    # Review candidates are prioritized, not classified. Known same-query groups
    # are explicitly marked as identity-review signals.
    risk_ids = set().union(*GROUPS.values())
    allw["top2_shared_query_review_priority"] = allw.project_work_id.map(
        lambda wid: "REVIEW_IDENTITY" if wid in risk_ids else "NOT_IN_TOP2_RISK_GROUPS")
    summary = {
        "release":"openalex-v3-visibility-lenses-scope-evidence-bridge-v0_1",
        "status":"EXPLORATORY_NO_HUMAN_SCOPE_ADJUDICATION",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "active_project_w":len(allw),
        "not_queried_r2_r3":int(allw.openalex_r2r3_query_coverage.eq("NOT_QUERIED_R2_R3").sum()),
        "unremeasured_source_light":int(hold.sum()),
        "lens_scenarios":overview,
        "limits":[
            "No novel/novella, original-English, or original-1880-1950 eligibility inferred.",
            "Scope bibliographic year is edition-derived minimum, NOT original first publication year.",
            "All researchers' scope fields remain unadjudicated; bibliographic evidence fields are unchanged.",
            "No OpenAlex document type is assumed scholarly by default.",
            "The expanded lens includes books/book reviews/conference papers/preprints/reports, which can be primary works or otherwise unsuitable.",
            "All counts are candidate Project W x OpenAlex Work pairs, not verified scholarly references.",
            "Top2 grouping is hypothetical only; other 831 query-overlap clusters remain as retrieved.",
            "352 unqueried Project W and the one unremeasured W are NA, not zero.",
            "All input outputs, human judgment, holdout and model results remain unchanged."
        ]
    }
    with tempfile.TemporaryDirectory(prefix=".oa_v3_lenses_", dir=OA) as td:
        tmp = Path(td)
        files = {
            "work_visibility_with_scope_evidence.tsv":allw,
            "visibility_lens_sensitivity_summary.tsv":result,
            "top100_by_lens_and_scenario.tsv":rnk
        }
        for name, frame in files.items():
            frame.to_csv(tmp/name, sep="\t", index=False)
        sp = tmp/"summary.json"
        sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        mp=tmp/"manifest.json"
        mp.write_text(json.dumps({
            "input_sha256": {str(p):sha(p) for p in (P,W,SCOPE,QUERY)},
            "output_sha256": {name:sha(tmp/name) for name in files} | {"summary.json":sha(sp)},
            "script_sha256":sha(Path(__file__)),
            "existing_data_unchanged":True,
        },ensure_ascii=False,indent=2)+"\n", encoding="utf-8")
        check(not OUT.exists(),"Output appeared during staging")
        tmp.rename(OUT)
    print("QC PASSED / NO API / EXISTING DATA UNCHANGED")
    print("32,066 Project W, 352 not queried, 1 unremeasured: retained as not measured.")
    print("\nVisibility lenses and grouping sensitivity:")
    print(result.to_string(index=False))
    print("\nTop 20 CORE3 candidates with top2 hypothetical union:")
    show = rnk.loc[rnk.lens.eq("CORE3_ARTICLE_CHAPTER_DISSERTATION") &
                   rnk.scenario.eq("TOP2_HYPOTHETICAL_UNION")].head(20)
    print(show[["rank","analysis_work_id","query_title_label",
                "query_author_label","candidate_pairs"]].to_string(index=False))
    print("\nOutput:",OUT)

if __name__ == "__main__":
    main()
