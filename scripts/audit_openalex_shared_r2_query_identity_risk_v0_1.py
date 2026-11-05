#!/usr/bin/env python3
"""Audit duplicated R2 query title+author across Project W in provisional v3.

READ-ONLY to all existing datasets. Writes versioned diagnostic outputs only.
Identical R2 query strings do NOT prove conceptual-work identity.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, re, tempfile
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OA = ROOT / "derived/openalex_production"
V3 = OA / "integrated_work_visibility_v3_r2a1_model_provisional" / "integrated_candidate_dispositions_v3_provisional.parquet"
Q = OA / "registry_v4/openalex_queries_v4.tsv"
H = ROOT / "derived/ol_dump_population_fiction_2026-02-28.tsv"
OUT = OA / "analysis_v3_shared_r2_query_identity_risk_v0_1"
TOP_THREE = {"W000030950", "W000017666", "W000016985"}

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024*1024), b""):
            h.update(part)
    return h.hexdigest()

def norm(s):
    return re.sub(r"\s+", " ", s.strip()).casefold()

def fail(s):
    raise RuntimeError("QC FAILED: " + s)

def main():
    if OUT.exists():
        fail(f"Output exists, refusing to overwrite: {OUT}")
    for path in [V3, Q, H]:
        if not path.is_file():
            fail(f"Missing input {path}")
    pair = pd.read_parquet(V3)
    if len(pair) != 291859 or pair[["project_work_id","openalex_work_id"]].duplicated().any():
        fail("v3 not frozen expected pair set")
    inc = pair.loc[pair.v3_provisional_include.eq(True), ["project_work_id", "openalex_work_id"]]
    if len(inc) != 173897:
        fail("v3 included count mismatch")
    by_w = inc.groupby("project_work_id").openalex_work_id.agg(lambda z: set(z)).to_dict()

    query = pd.read_csv(Q, sep="\t", dtype=str, keep_default_na=False)
    needed = {"project_work_id", "query_route", "query_title", "query_author", "alias_source_record_id"}
    if not needed.issubset(query.columns):
        fail(f"R2 query registry missing: {sorted(needed - set(query.columns))}")
    r2 = query.loc[query.query_route.eq("R2")].copy()
    r2["title_key"] = r2.query_title.map(norm)
    r2["author_key"] = r2.query_author.map(norm)
    r2 = r2.loc[r2.title_key.ne("") & r2.author_key.ne("")].copy()
    r2 = r2.drop_duplicates(["project_work_id", "title_key", "author_key", "alias_source_record_id"])
    hist = pd.read_csv(H, sep="\t", dtype=str, keep_default_na=False)
    if not {"work_key", "title", "first_publish_year"}.issubset(hist.columns):
        fail("Historical OL population unexpected schema")
    hist["ol_id"] = hist.work_key.str.replace("/works/", "", regex=False)
    old = hist.set_index("ol_id")[["title", "first_publish_year"]].to_dict("index")
    clusters, members = [], []
    for (title_key, author_key), group in r2.groupby(["title_key", "author_key"], sort=False):
        wids = sorted(set(group.project_work_id))
        if len(wids) < 2:
            continue
        sets = [by_w.get(wid, set()) for wid in wids]
        total_pairs = sum(map(len, sets))
        union = set().union(*sets)
        common = set.intersection(*sets) if sets else set()
        row = group.sort_values(["project_work_id", "alias_source_record_id"]).iloc[0]
        cluster_id = "R2Q_" + hashlib.sha256((title_key+"\t"+author_key).encode()).hexdigest()[:16]
        clusters.append({
            "cluster_id": cluster_id,
            "query_title": row.query_title,
            "query_author": row.query_author,
            "distinct_project_w": len(wids),
            "v3_candidate_pairs_across_w": total_pairs,
            "distinct_openalex_ids_union": len(union),
            "openalex_ids_common_to_all_w": len(common),
            "cross_w_repeated_pair_placements": total_pairs-len(union),
            "project_w_ids": ";".join(wids),
            "identity_status": "UNREVIEWED_SHARED_QUERY_SIGNAL_NOT_MERGED"
        })
        for wid in wids:
            groupw = group.loc[group.project_work_id.eq(wid)]
            ids = sorted(set(groupw.alias_source_record_id) - {""})
            historical = [old.get(z,{}) for z in ids]
            members.append({
                "cluster_id":cluster_id, "project_work_id":wid,
                "ol_work_ids_in_queries": ";".join(ids),
                "historical_ol_titles": ";".join(sorted({x.get("title","") for x in historical if x.get("title")})),
                "historical_edition_min_years": ";".join(sorted({x.get("first_publish_year","") for x in historical if x.get("first_publish_year")})),
                "v3_candidate_pairs_for_w": len(by_w.get(wid, set())),
                "review_status": "UNREVIEWED"
            })
    if not clusters:
        fail("No same-title-author R2 query clusters (unexpected)")
    c = pd.DataFrame(clusters).sort_values(
        ["cross_w_repeated_pair_placements","distinct_project_w","cluster_id"],
        ascending=[False,False,True])
    m = pd.DataFrame(members)
    match3 = c.loc[c.project_w_ids.map(lambda s: TOP_THREE.issubset(set(s.split(";"))))]
    if len(match3) != 1:
        fail("Expected top-three Ulysses group absent or nonunique")
    target = match3.iloc[0]
    summary = {
        "release": "analysis-v3-shared-r2-query-identity-risk-v0_1",
        "status": "READ_ONLY_POTENTIAL_IDENTITY_RISK_NO_AUTOMATIC_MERGE",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_shared_exact_r2_title_author_clusters": len(c),
        "distinct_project_w_in_shared_clusters": len(set(";".join(c.project_w_ids).split(";"))),
        "ulysses_cluster": {k:(int(v) if isinstance(v, (int,)) else v)
                           for k,v in target.to_dict().items()},
        "notes": [
            "Shared search strings do not automatically imply the same underlying literary work.",
            "Repeated pair placements across Project W are NOT an error estimate.",
            "No Project W or candidate records have been merged, excluded, or edited.",
            "The source publication-year field is edition-derived minimum, not proven original work first-publication year.",
            "The sensitivity analysis of confirmed SAME-work clusters belongs in a separate subsequent release."
        ],
    }
    with tempfile.TemporaryDirectory(prefix=".shared_r2q_", dir=OA) as temp:
        tmp = Path(temp)
        cp = tmp / "shared_r2_title_author_clusters.tsv"
        mp = tmp / "shared_r2_query_cluster_members.tsv"
        sp = tmp / "summary.json"
        hp = tmp / "manifest.json"
        c.to_csv(cp, sep="\t", index=False)
        m.to_csv(mp, sep="\t", index=False)
        sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        hp.write_text(json.dumps({
            "inputs_sha256": {str(p.relative_to(ROOT)): sha(p) for p in [V3,Q,H]},
            "outputs_sha256": {p.name:sha(p) for p in [cp,mp,sp]},
            "script_sha256": sha(Path(__file__)),
            "no_existing_data_modified":True
        },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        if OUT.exists():
            fail("Output directory unexpectedly appeared")
        tmp.rename(OUT)
    print("QC PASSED / NO API / ORIGINAL V3 AND IDENTITY UNCHANGED")
    print("Exact repeated title+author R2 query clusters:",len(c))
    print("Project W appearing in shared query clusters:",summary["distinct_project_w_in_shared_clusters"])
    print("\nUlysses cluster:")
    print(match3[["query_title","query_author","distinct_project_w",
                  "v3_candidate_pairs_across_w","distinct_openalex_ids_union",
                  "openalex_ids_common_to_all_w","cross_w_repeated_pair_placements"]].to_string(index=False))
    print("\nTop 15 identity-risk query clusters:")
    print(c[["query_title","query_author","distinct_project_w",
             "cross_w_repeated_pair_placements"]].head(15).to_string(index=False))
    print("\nHistorical OL details for Ulysses:")
    print(m.loc[m.cluster_id.eq(target.cluster_id)].to_string(index=False))
    print("\nOutput:",OUT)

if __name__ == "__main__":
    main()
