#!/usr/bin/env python3
"""Combine 20+140 saved Luna development predictions; prepare blinded review.

No API requests. Does not read/open the 600-pair holdout or change prior files.
Run from canon-pipeline-openalex-a2val:
    python -B scripts/prepare_openalex_development_160_review_v0_1.py

Outputs a 40-pair purposive diagnostic review with *no model results* in the
blind review file, separately preserved model key, whole-160 diagnostic tables,
and manifest. This is NOT an independent precision estimator.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT_DEFAULT = Path(__file__).resolve().parents[1]
BASE_REL = Path("derived/openalex_production")
SAMPLE_REL = BASE_REL / "retrieval_r2a1_independent_validation_v0_1"
FIRST_REL = BASE_REL / "retrieval_r2a1_development_20_identity_aware_v0_1"
SECOND_REL = BASE_REL / "retrieval_r2a1_development_remaining_140_identity_aware_v0_1"
BIB_REL = Path("derived/scope/scope_combined_bibliographic_evidence_v0_1/scope_combined_project_w_bibliographic_evidence_v0_1.tsv")
OUT_REL = BASE_REL / "retrieval_r2a1_development_160_review_v0_1"
JUDGMENTS = {"VALID_TARGET_REFERENCE", "INVALID_TARGET_REFERENCE", "UNCERTAIN"}
COHORTS = {"DEVELOPMENT_RANDOM_120":120,"DEVELOPMENT_TITLE_RISK_40":40}
SELECT_N = 40
SEED_LABEL = "r2a1-dev160-diagnostic-review-v0_1"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def require(path):
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def read_jsonl(path):
    rows=[]
    for i,line in enumerate(require(path).read_text(encoding="utf-8").splitlines(),1):
        if not line.strip():
            raise ValueError(f"Empty JSONL line {i} at {path}")
        obj=json.loads(line)
        if not isinstance(obj,dict):
            raise ValueError(f"JSONL line {i} not object at {path}")
        rows.append(obj)
    return pd.DataFrame(rows)


def canonical_order(values):
    return sorted(values, key=lambda v: (hashlib.sha256(f"{SEED_LABEL}\t{v}".encode()).hexdigest(),v))


def pick_review(full):
    """All UNCERTAIN up to 20; balance model labels/cohorts; fill deterministically.

    Selection uses model outputs only for diagnostic enrichment; subsequent
    human judgments must be blinded. No representativeness/precision claim.
    """
    chosen=[]
    taken=set()
    def add_from(frame, limit):
        available=frame.loc[~frame.baseline_candidate_id.isin(taken)]
        ordered=canonical_order(available.baseline_candidate_id.tolist())[:limit]
        chosen.extend(ordered)
        taken.update(ordered)
    u=full.loc[full.judgment.eq("UNCERTAIN")]
    add_from(u, min(20,len(u)))
    # Preserve diagnostic coverage of both natural and title-risk cohorts.
    for cohort in COHORTS:
        for judgment in ("VALID_TARGET_REFERENCE", "INVALID_TARGET_REFERENCE"):
            add_from(full.loc[full.sample_cohort.eq(cohort) & full.judgment.eq(judgment)],4)
    # Balance remaining VALID and INVALID slots, without risking over-selection.
    for j in ("INVALID_TARGET_REFERENCE","VALID_TARGET_REFERENCE"):
        add_from(full.loc[full.judgment.eq(j)], max(0,(SELECT_N-len(chosen))//2))
    if len(chosen)<SELECT_N:
        add_from(full, SELECT_N-len(chosen))
    if len(chosen)!=SELECT_N or len(set(chosen))!=SELECT_N:
        raise RuntimeError(f"Unexpected diagnostic review size {len(chosen)}")
    return chosen


def grouped_dict(df, keys):
    counts=df.groupby(keys,dropna=False).size()
    return [{**{k:str(v) for k,v in zip(keys,idx if isinstance(idx,tuple) else (idx,))},"n":int(n)} for idx,n in counts.items()]


def build(root:Path, out:Path):
    sample=root/SAMPLE_REL
    dev_file=require(sample/"development_160_unblinded.tsv")
    manifest_file=require(sample/"sampling_manifest_v0_1.json")
    dev_manifest=json.loads(manifest_file.read_text(encoding="utf-8"))
    if dev_manifest.get("status")!="FROZEN_SAMPLE_SELECTION_ONLY_NO_ADJUDICATION":
        raise ValueError("Unexpected sample manifest status")
    if dev_manifest.get("new_frame_n")!=223875 or dev_manifest.get("holdout_n")!=600:
        raise ValueError("Unexpected sample manifest size")
    if sha(dev_file)!=dev_manifest["output_sha256"][dev_file.name]:
        raise ValueError("Frozen 160 development input hash mismatch")
    dev=pd.read_csv(dev_file,sep="\t",dtype=str,keep_default_na=False)
    if len(dev)!=160 or not dev.baseline_candidate_id.is_unique:
        raise ValueError("Expected 160 distinct frozen development candidates")
    if dev.sample_cohort.value_counts().to_dict()!=COHORTS:
        raise ValueError("Unexpected frozen development strata")
    a=root/FIRST_REL/"model_results_v0_1.jsonl"
    b=root/SECOND_REL/"model_results_v0_1.jsonl"
    prev=read_jsonl(a)
    recent=read_jsonl(b)
    if len(prev)!=20 or len(recent)!=140:
        raise ValueError(f"Expected 20 + 140 LLM results; found {len(prev)} + {len(recent)}")
    models=pd.concat([prev,recent],ignore_index=True)
    required={"baseline_candidate_id","project_work_id","openalex_work_id","sample_cohort","title_risk_signal","model","judgment","reason_code","confidence","identity_context_adequacy","note","input_tokens","output_tokens"}
    missing=required-set(models.columns)
    if missing:
        raise ValueError(f"Missing result fields: {sorted(missing)}")
    if not models.baseline_candidate_id.is_unique:
        raise ValueError("Duplicate model candidate ID")
    if set(models.baseline_candidate_id)!=set(dev.baseline_candidate_id):
        raise ValueError("Development candidate IDs mismatch")
    if set(models.model)!={"gpt-6-luna"} or not set(models.judgment).issubset(JUDGMENTS):
        raise ValueError("Unexpected model or judgment")
    check=dev.merge(models[["baseline_candidate_id","project_work_id","openalex_work_id","sample_cohort","title_risk_signal"]],on="baseline_candidate_id",validate="one_to_one",suffixes=("_input","_model"))
    for col in ("project_work_id","openalex_work_id","sample_cohort","title_risk_signal"):
        if not check[f"{col}_input"].equals(check[f"{col}_model"]):
            raise ValueError(f"Saved model metadata differs on {col}")
    labelcols=["baseline_candidate_id","judgment","reason_code","confidence","identity_context_adequacy","note","input_tokens","output_tokens","model"]
    full=dev.merge(models[labelcols],on="baseline_candidate_id",how="left",validate="one_to_one")
    if full[labelcols[1:]].isna().any().any():
        raise ValueError("Missing LLM data after merge")
    for token in ("input_tokens","output_tokens"):
        full[token]=pd.to_numeric(full[token],errors="raise").astype(int)
        if (full[token]<0).any():
            raise ValueError("Negative token usage")
    selected=pick_review(full)
    review=full.set_index("baseline_candidate_id").loc[selected].reset_index()
    # Review sheet matches the MODEL'S bibliographic input but never reveals its predictions.
    bibcols=["project_work_id","current_ol_work_ids_json","historical_titles_json","historical_authors_json","historical_edition_derived_min_years_json","historical_subject_keys_json","wikidata_qid","wikidata_label_en_effective"]
    bib=pd.read_csv(require(root/BIB_REL),sep="\t",dtype=str,keep_default_na=False,usecols=bibcols)
    if len(bib)!=32066 or not bib.project_work_id.is_unique:
        raise ValueError("Frozen bibliographic evidence W frame changed")
    blindcols=["baseline_candidate_id","project_work_id","target_title","target_author","representative_ol_source_record","openalex_work_id","openalex_title","openalex_abstract","openalex_publication_year","openalex_doi"]
    for col in blindcols:
        if col not in review.columns:
            raise ValueError(f"Missing development field {col}")
    blind=review[blindcols].merge(bib,on="project_work_id",how="left",validate="many_to_one",indicator=True)
    if not blind._merge.eq("both").all():
        raise ValueError("Bibliographic evidence missing for selected works")
    blind.drop(columns="_merge",inplace=True)
    blind.insert(0,"review_case_id",[f"R2DEV160_{i:03d}" for i in range(1,SELECT_N+1)])
    for col in ("reviewer_identity_context_status","reviewer_target_attribution_judgment","reviewer_reason_code","reviewer_evidence_note","reviewer_external_sources","reviewer_name","review_date"):
        blind[col]=""
    keyed=review[["baseline_candidate_id","project_work_id","openalex_work_id","sample_cohort","title_risk_signal","judgment","reason_code","confidence","identity_context_adequacy","note"]].copy()
    keyed.insert(0,"review_case_id",blind.review_case_id)
    keyed["sampling_component"]="MODEL_STRATIFIED_DIAGNOSTIC_NOT_ESTIMATOR"
    report={
        "release":"openalex-r2a1-development-160-review-v0_1",
        "status":"DIAGNOSTIC_SELECTION_NO_HUMAN_GOLD",
        "interpretation":"Selected 40 are purposive for error discovery, NOT a probability sample for inference",
        "development_total":len(full),
        "prediction_totals":{k:int(v) for k,v in full.judgment.value_counts().items()},
        "prediction_by_cohort":grouped_dict(full,["sample_cohort","judgment"]),
        "prediction_by_risk_signal":grouped_dict(full,["title_risk_signal","judgment"]),
        "identity_context":{k:int(v) for k,v in full.identity_context_adequacy.value_counts().items()},
        "no_abstract_by_cohort":{k:int(v) for k,v in full.openalex_abstract.eq("").groupby(full.sample_cohort).sum().items()},
        "token_totals":{"input":int(full.input_tokens.sum()),"output":int(full.output_tokens.sum())},
        "review_selected":len(blind),
        "review_selected_by_cohort_label":grouped_dict(keyed,["sample_cohort","judgment"]),
        "review_selection":"up to 20 UNCERTAIN, up to four each VALID/INVALID per development cohort, balanced deterministic fill",
        "holdout_accessed":False,
        "reviewer_blinded_to_llm":True,
        "notes":[
            "The review packet's bibliographic context is source-native, not researcher-verified identity.",
            "The project W target's corpus scope and an OpenAlex record's scholarly genre are independent questions.",
            "Never convert these 40 diagnostic cases into a population-wide precision estimate without accounting for biased selection.",
            "Model predictions are in a separate file; do not consult until after reviewer decisions are saved.",
        ],
    }
    if out.exists():
        raise FileExistsError(f"Refusing overwrite of existing output dir: {out}")
    out.mkdir(parents=True,exist_ok=False)
    predictions=out/"development_160_predictions_v0_1.tsv"
    blind_file=out/"development_40_blind_review_v0_1.tsv"
    key_file=out/"development_40_model_key_DO_NOT_OPEN_BEFORE_BLIND_REVIEW_v0_1.tsv"
    summary=out/"development_160_summary_v0_1.json"
    README=out/"README.md"
    full.sort_values("baseline_candidate_id",kind="stable").to_csv(predictions,sep="\t",index=False,lineterminator="\n")
    blind.to_csv(blind_file,sep="\t",index=False,lineterminator="\n")
    keyed.to_csv(key_file,sep="\t",index=False,lineterminator="\n")
    summary.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    README.write_text(
        "# R2+A1 development 160: diagnostic review packet\n\n"
        "- All 160 predictions are provisional Luna outputs, not human gold.\n"
        "- The 40 cases are selected with model outcomes to find errors; NOT a representatively sampled estimator.\n"
        "- First review `development_40_blind_review_v0_1.tsv`, using the OA record and source-native bibliography.\n"
        "- Do not open `development_40_model_key_DO_NOT_OPEN_BEFORE_BLIND_REVIEW_v0_1.tsv` until the researcher review is complete.\n"
        "- Leave missing/ambiguous identities unresolved; never force a binary judgment.\n"
        "- Do not equate work-specific attribution, novel corpus scope, and OA scholarly document type.\n"
        "- No changes to previous 20/140, integrated v2, or 600-pair holdout.\n",encoding="utf-8"
    )
    im={str(p.relative_to(root)):{"sha256":sha(p),"bytes":p.stat().st_size} for p in (dev_file,manifest_file,a,b,root/BIB_REL)}
    artifacts=(predictions,blind_file,key_file,summary,README)
    provenance={"release":report["release"],"inputs":im,"outputs":{p.name:sha(p) for p in artifacts},"holdout_accessed":False,"no_api_calls":True}
    (out/"manifest_v0_1.json").write_text(json.dumps(provenance,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("=== OPENALEX DEVELOPMENT 160 REVIEW PACKET (NO API) ===")
    print("Luna labels (NOT GOLD):",report["prediction_totals"])
    print("By development cohort:")
    for row in report["prediction_by_cohort"]:
        print(" ",row)
    print("Identity-context adequacy:",report["identity_context"])
    print("Cumulative input/output tokens:",report["token_totals"])
    print("Blind diagnostic review cases:",len(blind))
    print("Selected by cohort and LLM judgment (for selection diagnostics only):")
    for row in report["review_selected_by_cohort_label"]:
        print(" ",row)
    print("Blind review file:",blind_file)
    print("DO NOT OPEN model key until blind review done:",key_file)
    print("No API calls; no holdout reads; no prior artifacts modified.")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo",type=Path,default=ROOT_DEFAULT)
    p.add_argument("--output",type=Path,default=None)
    args=p.parse_args()
    root=args.repo.resolve()
    out=(args.output or OUT_REL)
    out=out if out.is_absolute() else root/out
    build(root,out)


if __name__=="__main__":
    main()
