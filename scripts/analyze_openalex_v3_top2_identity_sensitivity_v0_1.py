#!/usr/bin/env python3
"""Read-only sensitivity test for two major shared-R2-query clusters.

Scenarios are HYPOTHETICAL analytical grouping, not a Project W identity
decision or correction of the frozen OpenAlex v3. In particular,
OL8137762W may represent a multi-work publication rather than the standalone
novella. No OpenAI calls; old data, human labels, holdout untouched.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from collections import OrderedDict
import hashlib, json, tempfile
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OA = ROOT / "derived/openalex_production"
V3 = OA / "integrated_work_visibility_v3_r2a1_model_provisional"
P = V3 / "integrated_candidate_dispositions_v3_provisional.parquet"
Q = OA / "registry_v4/openalex_queries_v4.tsv"
AUDIT = OA / "analysis_v3_shared_r2_query_identity_risk_v0_1/shared_r2_title_author_clusters.tsv"
OUT = OA / "analysis_v3_top2_identity_sensitivity_v0_1"

GROUPS = OrderedDict([
    ("SENS_ULYSSES_JOYCE", {
        "title": "Ulysses", "author": "James Joyce",
        "wids": {"W000030950","W000017666","W000016985"},
        "expected_repeated_placements": 8779,
    }),
    ("SENS_HEART_OF_DARKNESS_CONRAD", {
        "title": "Heart of Darkness", "author": "Joseph Conrad",
        "wids": {"W000014272","W000014830","W000017583","W000030652"},
        "expected_repeated_placements": 5851,
    }),
])


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for buf in iter(lambda: f.read(1024 * 1024), b""):
            h.update(buf)
    return h.hexdigest()


def require(ok, reason):
    if not ok:
        raise RuntimeError("QC FAILED: " + reason)


def scenario_counts(pairs, replacements):
    z = pairs.copy()
    z["analysis_work_id"] = z.project_work_id.replace(replacements)
    z = z.drop_duplicates(subset=["analysis_work_id", "openalex_work_id"])
    counts = z.groupby("analysis_work_id").size().rename("candidate_pairs").reset_index()
    return counts, len(z)


def main():
    require(not OUT.exists(), "Output exists; never overwrite.")
    for p in (P, Q, AUDIT):
        require(p.exists(), f"Missing input: {p}")
    df = pd.read_parquet(P, columns=[
        "project_work_id","openalex_work_id","v3_provisional_include"])
    require(len(df) == 291859, "Unexpected v3 source cardinality")
    inc = df.loc[df.v3_provisional_include.eq(True),
                 ["project_work_id", "openalex_work_id"]].copy()
    require(len(inc) == 173897, "Expected 173,897 included pairs")
    require(not inc.duplicated(["project_work_id","openalex_work_id"]).any(),
            "Unexpected same-W duplicate")

    query = pd.read_csv(Q, sep="\t", dtype=str, keep_default_na=False)
    require({"project_work_id","query_route","query_title","query_author"} <= set(query.columns),
            "Query registry schema missing required fields")
    r2 = query.loc[query.query_route.eq("R2")]
    names = r2.sort_values(["project_work_id","query_title","query_author"]).drop_duplicates(
        "project_work_id").set_index("project_work_id")[["query_title","query_author"]].to_dict("index")
    a = pd.read_csv(AUDIT, sep="\t", dtype=str, keep_default_na=False)
    require({"query_title","query_author","project_w_ids",
             "cross_w_repeated_pair_placements"} <= set(a.columns),
            "Audit cluster schema missing required fields")

    for k, info in GROUPS.items():
        match = a.loc[
            a.query_title.str.casefold().eq(info["title"].casefold()) &
            a.query_author.str.casefold().eq(info["author"].casefold())
        ]
        require(len(match) == 1, f"Expected one source-audit cluster for {k}")
        found = set(match.iloc[0].project_w_ids.split(";"))
        require(found == info["wids"], f"Unexpected W members for {k}: {sorted(found)}")
        require(int(match.iloc[0].cross_w_repeated_pair_placements) ==
                info["expected_repeated_placements"],
                f"Source-audit repeated placements changed: {k}")

    mapping_ulysses = {wid:"SENS_ULYSSES_JOYCE"
                       for wid in GROUPS["SENS_ULYSSES_JOYCE"]["wids"]}
    mapping_both = dict(mapping_ulysses)
    mapping_both.update({wid:"SENS_HEART_OF_DARKNESS_CONRAD"
                         for wid in GROUPS["SENS_HEART_OF_DARKNESS_CONRAD"]["wids"]})
    scenarios = OrderedDict([
        ("V3_UNCHANGED", {}),
        ("HYPOTHETICAL_ULYSSES_GROUP_ONLY", mapping_ulysses),
        ("HYPOTHETICAL_ULYSSES_AND_HOD_GROUPS", mapping_both),
    ])

    outputs, summary = [], []
    for scenario, mapping in scenarios.items():
        counts, n = scenario_counts(inc, mapping)
        expected = 173897
        if mapping:
            expected -= 8779
        if "SENS_HEART_OF_DARKNESS_CONRAD" in mapping.values():
            expected -= 5851
        require(n == expected, f"Unexpected dedup union size for {scenario}: {n} != {expected}")
        counts["scenario"] = scenario
        counts["query_title_label"] = counts.analysis_work_id.map(
            lambda x: GROUPS[x]["title"] if x in GROUPS else names.get(x, {}).get("query_title", ""))
        counts["query_author_label"] = counts.analysis_work_id.map(
            lambda x: GROUPS[x]["author"] if x in GROUPS else names.get(x, {}).get("query_author", ""))
        counts = counts.sort_values(["candidate_pairs","analysis_work_id"],
                                    ascending=[False,True]).reset_index(drop=True)
        counts["rank_scenario"] = counts.candidate_pairs.rank(
            method="min", ascending=False).astype(int)
        outputs.append(counts)
        summary.append({
            "scenario": scenario, "work_document_candidate_pairs": int(n),
            "change_vs_raw_v3": int(n-173897),
            "positive_analysis_work_units": int(len(counts)),
            "top10_share": float(counts.head(10).candidate_pairs.sum()/n),
            "top100_share": float(counts.head(100).candidate_pairs.sum()/n),
            "model_attribution_only": True,
        })

    with tempfile.TemporaryDirectory(prefix=".sensitivity_v3_", dir=OA) as temp:
        stage = Path(temp)
        allp = stage / "scenario_work_candidate_counts.tsv"
        top = stage / "scenario_top20.tsv"
        sp = stage / "summary.json"
        mp = stage / "manifest.json"
        full = pd.concat(outputs, ignore_index=True)
        full.to_csv(allp, sep="\t", index=False)
        full.loc[full.rank_scenario.le(20)].to_csv(top, sep="\t", index=False)
        sp.write_text(json.dumps({
            "release":"v3-top2-query-identity-sensitivity-v0_1",
            "status":"HYPOTHETICAL_NOT_AN_IDENTITY_ADJUDICATION",
            "generated_utc":datetime.now(timezone.utc).isoformat(),
            "scenarios":summary,
            "important_caveats":[
                "Only the two large repeated R2 title+author clusters are hypothetically grouped.",
                "No existing Project W identity is altered or merged.",
                "OL8137762W includes a multi-work edition of Heart of Darkness and The Secret Sharer; grouping it is NOT a work-identity finding.",
                "Other 831 shared query groups are not grouped.",
                "OpenAlex Work reuse across genuinely distinct literary works is permitted.",
                "Counts are LLM-attributed provisional document candidate pairs, NOT scholarly-eligible references.",
                "The freeze of production predictions, model prompt, human labels, and holdout 600 is unchanged.",
            ]
        },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        mp.write_text(json.dumps({
            "inputs_sha256": {str(p.relative_to(ROOT)):digest(p) for p in [P,Q,AUDIT]},
            "outputs_sha256":{p.name:digest(p) for p in [allp,top,sp]},
            "builder_sha256":digest(Path(__file__)),
            "no_existing_data_modified":True,
        },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        require(not OUT.exists(), "Output created during processing")
        stage.rename(OUT)
    print("QC: PASSED / READ-ONLY TO V3 / NO API")
    print("These are HYPOTHETICAL sensitivity scenarios, NOT corrected identities.")
    for q in summary:
        print(q["scenario"], "pairs=",q["work_document_candidate_pairs"],
              "delta=",q["change_vs_raw_v3"],
              "units=",q["positive_analysis_work_units"],
              "top10_share=",f'{q["top10_share"]:.1%}',
              "top100_share=",f'{q["top100_share"]:.1%}')
    print("\nTop 12 work units by scenario:")
    for name in scenarios:
        print("\n",name)
        d = next(o for o in outputs if o.scenario.iloc[0] == name)
        print(d[["rank_scenario","analysis_work_id","query_title_label",
                 "query_author_label","candidate_pairs"]].head(12).to_string(index=False))
    print("\nOutput:",OUT)


if __name__ == "__main__":
    main()
