#!/usr/bin/env python3
"""Exploratory OpenAlex document-type stratification for frozen v3 provisional pairs.

No API/LLM; does not change any existing result, identity, scope, or holdout.
Snapshot OA "type" is metadata, NOT a verified scholarly eligibility label.
An article/chapter/dissertation subset is an exploratory proxy only.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, tempfile
import pandas as pd
import pyarrow.dataset as ds

ROOT = Path(__file__).resolve().parents[1]
OA = ROOT / "derived/openalex_production"
PAIRS = OA / "integrated_work_visibility_v3_r2a1_model_provisional/integrated_candidate_dispositions_v3_provisional.parquet"
WORKS = OA / "integrated_work_visibility_v3_r2a1_model_provisional/openalex_visibility_by_project_work_v3_provisional.parquet"
QUERIES = OA / "registry_v4/openalex_queries_v4.tsv"
SCAN = Path("/media/hdd1/user/tsutsui/openalex/scans/full_r23_v1/full_2040files_4a275210")
META = SCAN / "openalex_retrieval_full_r23_oa_records_v1.parquet"
OUT = OA / "analysis_v3_openalex_document_type_exploratory_v0_1"
PROXY = {"article", "book-chapter", "dissertation"}

def sha(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()

def check(test, msg):
    if not test:
        raise RuntimeError("QC FAILED: " + msg)

def main():
    check(not OUT.exists(), "Output directory already exists; do not overwrite")
    for p in [PAIRS, WORKS, QUERIES, META]:
        check(p.exists(), f"Missing input: {p}")
    p = pd.read_parquet(PAIRS, columns=[
        "project_work_id", "openalex_work_id", "route", "disposition",
        "v3_provisional_include", "v3_attribution_basis",
        "r2a1_model_judgment"])
    w = pd.read_parquet(WORKS, columns=[
        "project_work_id", "measurement_status",
        "v3_provisional_operational_pairs"])
    included = p.loc[p.v3_provisional_include.eq(True)].copy()
    check(len(p) == 291859 and len(included) == 173897, "v3 pair counts changed")
    check(not included[["project_work_id", "openalex_work_id"]].duplicated().any(),
          "Duplicate included Project W x OpenAlex Work pair")
    check(len(w) == 32066 and w.project_work_id.is_unique, "v3 work frame changed")
    ids = set(included.openalex_work_id)
    check(len(ids) == 129628, "Expected v3 distinct OpenAlex ID count changed")

    dataset = ds.dataset(str(META), format="parquet")
    cols = ["openalex_work_id", "type", "publication_year", "is_retracted", "doi"]
    check(set(cols).issubset(dataset.schema.names),
          f"Metadata columns missing: {set(cols)-set(dataset.schema.names)}")
    metadata = dataset.to_table(
        columns=cols, filter=ds.field("openalex_work_id").isin(sorted(ids))
    ).to_pandas()
    check(metadata.openalex_work_id.is_unique, "OpenAlex snapshot contains duplicate OA IDs")
    check(set(metadata.openalex_work_id).issubset(ids), "Unexpected OA IDs returned")
    metadata = metadata.rename(columns={
        "type":"openalex_type", "publication_year":"openalex_publication_year",
        "is_retracted":"openalex_is_retracted", "doi":"openalex_doi"
    })
    z = included.merge(metadata, on="openalex_work_id", how="left",
                       validate="many_to_one", indicator=True)
    check(len(z) == 173897, "Metadata join changed candidate pair cardinality")
    z["snapshot_metadata_match"] = z["_merge"].eq("both")
    z = z.drop(columns="_merge")
    z["openalex_type"] = z["openalex_type"].fillna("").astype(str).str.strip()
    z["type_for_analysis"] = z["openalex_type"].where(
        z.openalex_type.ne(""), "UNKNOWN_TYPE")
    z.loc[~z.snapshot_metadata_match, "type_for_analysis"] = "UNMATCHED_SNAPSHOT"
    z["exploratory_article_chapter_dissertation"] = (
        z.type_for_analysis.str.casefold().isin(PROXY))
    # Never force UNKNOWN/UNMATCHED into a definite non-scholarly judgment.
    q = pd.read_csv(QUERIES, sep="\t", dtype=str, keep_default_na=False)
    needed = {"project_work_id", "query_route", "query_title", "query_author"}
    check(needed.issubset(q.columns), "R2 query registry columns missing")
    r2 = q.loc[q.query_route.eq("R2"), sorted(needed - {"query_route"})].copy()
    r2 = r2.sort_values(["project_work_id", "query_title", "query_author"])
    labels = r2.drop_duplicates("project_work_id").set_index("project_work_id")
    by_type = (z.groupby("type_for_analysis").agg(
        candidate_pairs=("openalex_work_id", "size"),
        distinct_openalex_work_ids=("openalex_work_id", "nunique"),
        project_w_with_type=("project_work_id", "nunique"),
    ).sort_values("candidate_pairs", ascending=False).reset_index())
    by_w = z.groupby("project_work_id").agg(
        oa_type_matched_pairs=("snapshot_metadata_match","sum"),
        exploratory_article_chapter_dissertation_pairs=(
            "exploratory_article_chapter_dissertation","sum"),
    )
    counts = pd.crosstab(z.project_work_id, z.type_for_analysis)
    counts.columns = ["oa_type_" + c.replace("-","_").replace(" ","_") + "_pairs"
                      for c in counts.columns]
    by_w = by_w.join(counts, how="left")
    work = w.merge(by_w.reset_index(), on="project_work_id", how="left",
                   validate="one_to_one")
    work["query_title_display"] = work.project_work_id.map(labels["query_title"]).fillna("")
    work["query_author_display"] = work.project_work_id.map(labels["query_author"]).fillna("")
    held = work.measurement_status.eq("HOLD_PRIMARY_SUCCESSOR_NOT_RERETRIEVED")
    generated_cols = ["oa_type_matched_pairs",
                      "exploratory_article_chapter_dissertation_pairs"] + list(counts.columns)
    work[generated_cols] = work[generated_cols].fillna(0).astype("Int64")
    work.loc[held, generated_cols] = pd.NA
    check(int(work.oa_type_matched_pairs.sum()) ==
          int(z.snapshot_metadata_match.sum()), "Work metadata match totals mismatch")
    check(int(work.exploratory_article_chapter_dissertation_pairs.sum()) ==
          int(z.exploratory_article_chapter_dissertation.sum()), "Work proxy totals mismatch")
    work = work.sort_values(
        ["exploratory_article_chapter_dissertation_pairs", "project_work_id"],
        ascending=[False, True], na_position="last")

    summary = {
        "status":"EXPLORATORY_ONLY_NOT_A_SCHOLARLY_VISIBILITY_RELEASE",
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "v3_included_project_w_oa_pairs":len(z),
        "distinct_openalex_ids":len(ids),
        "oa_ids_found_in_snapshot":len(metadata),
        "oa_ids_not_found_in_snapshot":len(ids)-len(metadata),
        "pairs_with_snapshot_metadata":int(z.snapshot_metadata_match.sum()),
        "article_chapter_dissertation_pairs_EXPLORATORY":int(
            z.exploratory_article_chapter_dissertation.sum()),
        "article_chapter_dissertation_types":sorted(PROXY),
        "document_type_pair_counts":{
            str(t):int(n) for t,n in zip(by_type.type_for_analysis,
                                         by_type.candidate_pairs)},
        "caveats":[
            "OpenAlex Work type alone does not establish scholarly relevance.",
            "Primary-text book records, reviews, reprints, retractions, and potential same-content duplicates need further study.",
            "Article/chapter/dissertation is a deliberately incomplete exploratory proxy; not a final inclusion filter.",
            "The numbers count Project W x OpenAlex Work pairs, not unique OA articles or citations.",
            "Same-query Project W groups (e.g., Ulysses/Heart of Darkness) have NOT been merged.",
            "The Project W 1880–1950 English novel/novella scope has NOT been adjudicated.",
            "Query title/author are display labels, not verified canonical work names.",
            "v2, v3, identity, the 600 holdout, and existing LLM predictions remain untouched."
        ]
    }
    with tempfile.TemporaryDirectory(prefix=".oa_v3_type_", dir=OA) as temp:
        stage = Path(temp)
        outputs = [
            (stage/"v3_included_pairs_with_oa_type.parquet", z),
            (stage/"oa_type_distribution.tsv", by_type),
            (stage/"work_type_exploratory_counts.tsv", work),
        ]
        for dest, frame in outputs:
            if dest.suffix == ".parquet":
                frame.to_parquet(dest, index=False)
            else:
                frame.to_csv(dest, sep="\t", index=False)
        sp = stage / "summary.json"
        sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n")
        m = stage / "manifest.json"
        m.write_text(json.dumps({
            "source_sha256":{str(src):sha(src) for src in [PAIRS, WORKS, QUERIES, META]},
            "output_sha256":{dest.name:sha(dest) for dest,_ in outputs} |
                            {sp.name:sha(sp)},
            "script_sha256":sha(Path(__file__)),
            "no_old_outputs_modified":True
        }, ensure_ascii=False, indent=2)+"\n")
        check(not OUT.exists(), "Output appeared during staging")
        stage.rename(OUT)
    print("QC: PASSED / NO API / NO EXISTING DATA MODIFIED")
    print(f"OpenAlex IDs matched: {len(metadata):,}/{len(ids):,}")
    print(f"Included W-OA pairs with metadata: {int(z.snapshot_metadata_match.sum()):,}/{len(z):,}")
    print("\nOpenAlex type distribution (NOT scholarly eligibility):")
    print(by_type.head(25).to_string(index=False))
    print("\nArticle + book-chapter + dissertation exploratory subset:")
    print(f"{int(z.exploratory_article_chapter_dissertation.sum()):,} / {len(z):,} pairs")
    print("\nTop 20 W in this exploratory subset (UNFILTERED work scope):")
    print(work[["project_work_id","query_title_display","query_author_display",
                "exploratory_article_chapter_dissertation_pairs",
                "v3_provisional_operational_pairs"]].head(20).to_string(index=False))
    print("\nOutput:",OUT)

if __name__ == "__main__":
    main()
