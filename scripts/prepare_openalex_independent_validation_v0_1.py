#!/usr/bin/env python3
"""Prepare independent OpenAlex R2+A1 LLM development and blind holdout samples.

Reads only frozen project data. No API calls. Does not change existing releases.
The 600-pair holdout is simple-random pair sampling from the explicitly
identified new, previously unreviewed population; development material is
selected afterward, with no reused OA document IDs across the two arms.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "derived/openalex_production"
V2 = BASE / "integrated_work_visibility_v2/integrated_candidate_dispositions_v2.parquet"
POST = BASE / "retrieval_r2a1_post_identity_candidates_v1/openalex_r2a1_post_identity_candidates_v1.parquet"
OLD = BASE / "retrieval_r2a1_baseline_validation_sample_v1/openalex_r2a1_baseline_validation_sample_combined_v1.tsv"
PREVIOUS_PILOT = BASE / "retrieval_r2a1_llm_new_pilot_input_v0_1"
REGISTRY = BASE / "registry_v4/openalex_queries_v4.parquet"
OA = Path("/media/hdd1/user/tsutsui/openalex/scans/full_r23_v1/full_2040files_4a275210/openalex_retrieval_full_r23_oa_records_v1.parquet")
OUT = BASE / "retrieval_r2a1_independent_validation_v0_1"
RANDOM_SEED = 20261021
HOLDOUT_N, DEVELOPMENT_RANDOM_N, DEVELOPMENT_RISK_N = 600, 120, 40
KEY = ["project_work_id", "openalex_work_id"]


def require(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Required frozen input not found: {path}")


def cid(wid: str, oid: str) -> str:
    return "OABASEV1_" + hashlib.sha256(
        f"R2_A1_BASELINE\t{wid}\t{oid}".encode("utf-8")
    ).hexdigest()[:16]


def sha(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def sample(df: pd.DataFrame, n: int, rng: random.Random) -> pd.DataFrame:
    if len(df) < n:
        raise RuntimeError(f"Insufficient eligible pairs: {len(df)} < {n}")
    indices = rng.sample(range(len(df)), n)
    return df.iloc[indices].copy().sort_values("baseline_candidate_id", kind="stable").reset_index(drop=True)


def normalized(text: object) -> str:
    return " ".join(re.findall(r"\w+", str(text or "").casefold()))


def risk_signal(row):
    title = normalized(row["target_title"])
    author = normalized(row["target_author"])
    if author and title == author:
        return "TITLE_EQUALS_AUTHOR_NAME"
    if author and title == author.split()[-1]:
        return "TITLE_EQUALS_AUTHOR_SURNAME"
    if title in {"works", "novels", "poems", "poetry", "stories", "tales", "fairy tales", "collected works", "collected poems", "complete works", "selected works"}:
        return "GENERIC_COLLECTION_LIKE_TITLE"
    return "NO_SIMPLE_TITLE_FLAG"


def previous_pilot_ids(path: Path) -> set[str]:
    require(path)
    files = list(path.rglob("*.tsv"))
    if not files:
        raise RuntimeError("Previous 100-pair pilot has no TSV input; cannot protect it")
    ids: set[str] = set()
    for p in files:
        head = pd.read_csv(p, sep="\t", nrows=0)
        if "baseline_candidate_id" in head.columns:
            c = pd.read_csv(p, sep="\t", dtype=str, usecols=["baseline_candidate_id"], keep_default_na=False)
            ids.update(c["baseline_candidate_id"].tolist())
    if len(ids) != 100:
        raise RuntimeError(f"Expected 100 frozen pilot IDs; found {len(ids)}")
    return ids


def main():
    for p in (V2, POST, OLD, REGISTRY, OA):
        require(p)
    if OUT.exists():
        raise RuntimeError(f"STOP: output directory already exists; no overwrites: {OUT}")

    included = pd.read_parquet(V2, columns=KEY + ["route", "disposition", "operational_include", "source_candidate_id"])
    mask = (
        included["route"].eq("R2_A1_BASELINE")
        & included["disposition"].eq("INCLUDE_BASELINE_UNADJUDICATED")
        & included["operational_include"].eq(True)
    )
    unjudged = included.loc[mask, KEY + ["source_candidate_id"]].copy()
    if len(unjudged) != 224830 or unjudged.duplicated(KEY).any():
        raise RuntimeError(f"Unexpected unadjudicated R2+A1 population: {len(unjudged)}")

    extra = pd.read_parquet(POST, columns=KEY + [
        "baseline_candidate_id", "hit_location", "title_match_token_count_min"
    ])
    if extra.duplicated(KEY).any():
        raise RuntimeError("Duplicate baseline pair keys in post-identity source")
    x = unjudged.merge(extra, on=KEY, how="left", validate="one_to_one", indicator=True)
    if not x["_merge"].eq("both").all():
        raise RuntimeError("Missing pair in the frozen baseline evidence")
    x = x.drop(columns=["_merge"])
    if not x["baseline_candidate_id"].eq(x["source_candidate_id"]).all():
        raise RuntimeError("Mismatch between v2 source candidate ID and frozen baseline ID")
    if not x["baseline_candidate_id"].is_unique:
        raise RuntimeError("Nonunique baseline candidate IDs")
    # Recompute ID on a small deterministic group as a guard against semantic rekeying.
    for r in x.iloc[:10].itertuples(index=False):
        if r.baseline_candidate_id != cid(r.project_work_id, r.openalex_work_id):
            raise RuntimeError("Candidate ID semantics unexpectedly changed")

    old = pd.read_csv(OLD, sep="\t", dtype=str, usecols=["baseline_candidate_id"], keep_default_na=False)
    old_ids = set(old["baseline_candidate_id"])
    if len(old_ids) != 1147:
        raise RuntimeError(f"Old evaluation candidates unexpectedly changed: {len(old_ids)}")
    old_in_unjudged = int(x["baseline_candidate_id"].isin(old_ids).sum())
    if old_in_unjudged != 855:
        raise RuntimeError(f"Expected 855 old evaluation IDs in unjudged frame; got {old_in_unjudged}")
    prior_ids = previous_pilot_ids(PREVIOUS_PILOT)
    if not prior_ids.isdisjoint(old_ids):
        raise RuntimeError("Previous pilot overlaps old evaluation set")
    prior_in_unjudged = int(x["baseline_candidate_id"].isin(prior_ids).sum())
    if prior_in_unjudged != 100:
        raise RuntimeError(f"Expected 100 prior pilot IDs in unjudged frame; got {prior_in_unjudged}")
    x = x.loc[~x["baseline_candidate_id"].isin(old_ids | prior_ids)].copy()
    if len(x) != 223875:
        raise RuntimeError(f"Expected new, unseen evaluation frame 223875; got {len(x)}")

    q = pd.read_parquet(REGISTRY, columns=[
        "target_lane", "project_work_id", "query_route", "query_title", "query_author", "alias_source_record_id"
    ])
    q = q.loc[q["target_lane"].eq("resolved_w") & q["query_route"].eq("R2")].copy()
    if q["project_work_id"].duplicated().any():
        raise RuntimeError("R2 does not have one representative query per W")
    q = q.rename(columns={"query_title":"target_title", "query_author":"target_author", "alias_source_record_id":"representative_ol_source_record"})
    x = x.merge(q[["project_work_id", "target_title", "target_author", "representative_ol_source_record"]], on="project_work_id", how="left", validate="many_to_one")
    if x[["target_title", "target_author"]].isna().any().any():
        raise RuntimeError("Missing frozen R2 representative title or author")
    x["title_risk_signal"] = x.apply(risk_signal, axis=1)
    x = x.sort_values("baseline_candidate_id", kind="stable").reset_index(drop=True)

    rng = random.Random(RANDOM_SEED)
    holdout = sample(x, HOLDOUT_N, rng)
    holdout["sample_cohort"] = "INDEPENDENT_PAIR_HOLDOUT_600"
    holdout["pair_inclusion_probability"] = HOLDOUT_N / len(x)
    # Prevent reusing the same OpenAlex document in development.
    dev_pool = x.loc[~x["openalex_work_id"].isin(holdout["openalex_work_id"])].copy().reset_index(drop=True)
    dev_random = sample(dev_pool, DEVELOPMENT_RANDOM_N, rng)
    dev_random["sample_cohort"] = "DEVELOPMENT_RANDOM_120"
    dev_random["pair_inclusion_probability"] = pd.NA
    picked_oa = set(dev_random["openalex_work_id"]) | set(holdout["openalex_work_id"])
    risk_pool = dev_pool.loc[
        (~dev_pool["openalex_work_id"].isin(picked_oa))
        & (~dev_pool["title_risk_signal"].eq("NO_SIMPLE_TITLE_FLAG"))
    ].copy().reset_index(drop=True)
    dev_risk = sample(risk_pool, DEVELOPMENT_RISK_N, rng)
    dev_risk["sample_cohort"] = "DEVELOPMENT_TITLE_RISK_40"
    dev_risk["pair_inclusion_probability"] = pd.NA
    dev = pd.concat([dev_random, dev_risk], ignore_index=True)
    if len(holdout) != 600 or len(dev) != 160:
        raise RuntimeError("Unexpected sample size")
    if set(dev["baseline_candidate_id"]) & set(holdout["baseline_candidate_id"]):
        raise RuntimeError("Overlapping pair IDs")
    if set(dev["openalex_work_id"]) & set(holdout["openalex_work_id"]):
        raise RuntimeError("OpenAlex document leakage across development/holdout")

    keys = set(dev["openalex_work_id"]) | set(holdout["openalex_work_id"])
    dataset = ds.dataset(str(OA), format="parquet")
    cols = ["openalex_work_id", "display_name", "abstract", "publication_year", "doi"]
    meta = dataset.to_table(columns=cols, filter=ds.field("openalex_work_id").isin(sorted(keys))).to_pandas()
    if meta["openalex_work_id"].duplicated().any() or set(meta["openalex_work_id"]) != keys:
        raise RuntimeError(f"Selected OA metadata mismatch: {len(meta)} rows for {len(keys)} IDs")
    meta = meta.rename(columns={"display_name":"openalex_title", "abstract":"openalex_abstract", "publication_year":"openalex_publication_year", "doi":"openalex_doi"})

    def attach(s):
        out = s.merge(meta, on="openalex_work_id", how="left", validate="many_to_one")
        cols = ["baseline_candidate_id", "project_work_id", "representative_ol_source_record", "target_title", "target_author", "openalex_work_id", "openalex_title", "openalex_abstract", "openalex_publication_year", "openalex_doi"]
        blinded = out[cols].copy().fillna("")
        blinded.insert(0, "review_case_id", ["R2VAL_" + z for z in blinded["baseline_candidate_id"]])
        blinded["researcher_identity_status"] = ""
        blinded["researcher_target_attribution_judgment"] = ""
        blinded["researcher_reason_code"] = ""
        blinded["researcher_notes"] = ""
        return out, blinded

    dev, dev_review = attach(dev)
    holdout, holdout_review = attach(holdout)
    OUT.mkdir(parents=True, exist_ok=False)
    files = {}
    for name, frame in [
        ("development_160_unblinded.tsv", dev),
        ("development_160_blind_review.tsv", dev_review),
        ("holdout_600_design.tsv", holdout.drop(columns=["openalex_title", "openalex_abstract", "openalex_publication_year", "openalex_doi"])),
        ("holdout_600_blind_review.tsv", holdout_review),
    ]:
        path = OUT / name
        frame.to_csv(path, sep="\t", index=False, lineterminator="\n")
        files[name] = sha(path)
    for name, frame in [("development_160.parquet", dev), ("holdout_600.parquet", holdout)]:
        path = OUT / name
        frame.to_parquet(path, index=False)
        files[name] = sha(path)

    summary = {
        "release":"openalex-r2a1-independent-validation-v0_1",
        "status":"FROZEN_SAMPLE_SELECTION_ONLY_NO_ADJUDICATION",
        "population_definition":"Operationally included unadjudicated R2+A1, excluding 1,147 earlier evaluation IDs and 100 earlier development-pilot IDs by exact candidate ID",
        "integrated_v2_unadjudicated_R2A1":224830,
        "old_evaluation_excluded_from_frame": old_in_unjudged,
        "prior_pilot_excluded_from_frame":prior_in_unjudged,
        "new_frame_n":len(x),
        "seed":RANDOM_SEED,
        "holdout_n":HOLDOUT_N,
        "holdout_sampling":"SRS without replacement of unique Project W x OA pair from the 223875 frame; no forced unique W or OA within holdout",
        "holdout_pair_inclusion_probability":HOLDOUT_N / len(x),
        "development_random_n":DEVELOPMENT_RANDOM_N,
        "development_risk_n":DEVELOPMENT_RISK_N,
        "development_sampling":"Pilot only. After holdout draw, excludes OA IDs seen in holdout. Risk cohort is purposive, not an estimator.",
        "holdout_review_rule":"Do not inspect holdout judgments or tune methods on holdout; human review blind to model predictions, sampled risk and cohort labels.",
        "review_semantics":"Target attribution only; reviewer identity verification separate; source R2 title and author are retrieval representatives, not proven canonical work identity.",
        "scope":"Not a novel/period scope decision. Do not derive target-attribution correctness from corpus scope.",
        "model_calls":0,"researcher_judgments":0,
        "holdout_distinct_project_works":int(holdout["project_work_id"].nunique()),
        "holdout_distinct_openalex_works":int(holdout["openalex_work_id"].nunique()),
        "dev_risk_signals":{str(k):int(v) for k,v in dev_risk["title_risk_signal"].value_counts().items()},
        "inputs":{"integrated_v2":str(V2),"post_identity":str(POST),"old_evaluation":str(OLD),"old_pilot":str(PREVIOUS_PILOT),"query_registry":str(REGISTRY),"frozen_oa_metadata":str(OA)},
        "output_sha256":files,
    }
    manifest = OUT / "sampling_manifest_v0_1.json"
    manifest.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("=== OPENALEX R2+A1 INDEPENDENT VALIDATION SAMPLE (NO API) ===")
    print("R2+A1 operational, not adjudicated:", 224830)
    print("Exclude old evaluation:",old_in_unjudged, "previous 100 pilot:",prior_in_unjudged)
    print("New pair frame:",len(x))
    print("Development:",len(dev), "= 120 random + 40 risk")
    print("Blind holdout:",len(holdout), "SRS of pair frame")
    print("Holdout unique W:",holdout["project_work_id"].nunique(),"unique OA:",holdout["openalex_work_id"].nunique())
    print("Overlap development/holdout OA IDs: 0")
    print("Blank abstracts (dev/holdout):",int(dev["openalex_abstract"].fillna("").eq("").sum()),"/",int(holdout["openalex_abstract"].fillna("").eq("").sum()))
    print("Outputs:",OUT)
    print("No model calls; no old source, decisions, or integrated release altered.")

if __name__ == "__main__":
    main()
