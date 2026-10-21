#!/usr/bin/env python3
"""Frozen identity-aware Luna validation on the independent 600-pair holdout.

Must be saved in the project's scripts/ directory alongside the two earlier
"run_openalex_r2a1_development_*" scripts. Reuses exactly the DEVELOPMENT
prompt, JSON schema, model, and Project-W bibliographic payload.

1. DRY RUN (no API, no writes):
   python -B scripts/run_openalex_r2a1_holdout_600_v0_1.py
2. OPTIONAL create a model-blind, independently preselected 200-pair human
   review sheet (no API, no predictions displayed):
   python -B scripts/run_openalex_r2a1_holdout_600_v0_1.py --prepare-blind-200
3. EXPLICIT PAID TEST (checkpointed and resumable):
   python -B scripts/run_openalex_r2a1_holdout_600_v0_1.py --execute --max-new 25

No human judgments are accessed, created, or modified by the LLM runner.
Do NOT inspect holdout LLM JSONL until the blind researcher labels are saved.
This is PAIR-LEVEL target attribution validation only, not scope, citation
verification, substantive mention strength, or bibliographic identity gold.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random

import pandas as pd

import run_openalex_r2a1_development_20_v0_1 as dev20
import run_openalex_r2a1_development_remaining_140_v0_1 as dev140

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "derived/openalex_production"
SAMPLE = BASE / "retrieval_r2a1_independent_validation_v0_1"
HOLDOUT_PARQUET = SAMPLE / "holdout_600.parquet"
HOLDOUT_BLIND_TSV = SAMPLE / "holdout_600_blind_review.tsv"
SAMPLE_MANIFEST = SAMPLE / "sampling_manifest_v0_1.json"
OUT = BASE / "retrieval_r2a1_holdout_600_identity_aware_v0_1"
REVIEW_OUT = BASE / "retrieval_r2a1_holdout_first_200_blind_review_v0_1"
MODEL = dev20.MODEL_DEFAULT
RELEASE = "openalex-r2a1-independent-holdout-600-luna-v0_1"
BLIND200_SEED = 20261022
NUM_HUMAN_FIRST = 200
ALLOWED = dev20.ALLOWED_REASONS


def sha(path: Path) -> str:
    return dev20.sha(path)


def require(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Frozen input not found: {path}")


def frozen_and_prepared() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Validate independent holdout and completed development *without* viewing predictions."""
    for p in (HOLDOUT_PARQUET, HOLDOUT_BLIND_TSV, SAMPLE_MANIFEST, dev20.BIB):
        require(p)
    sampling = json.loads(SAMPLE_MANIFEST.read_text(encoding="utf-8"))
    if (sampling.get("status") != "FROZEN_SAMPLE_SELECTION_ONLY_NO_ADJUDICATION"
        or sampling.get("new_frame_n") != 223875 or sampling.get("holdout_n") != 600
        or sampling.get("development_random_n") != 120
        or sampling.get("development_risk_n") != 40):
        raise RuntimeError("Unrecognized sample population/design; stopping")
    outputs = sampling["output_sha256"]
    for p in (HOLDOUT_PARQUET, HOLDOUT_BLIND_TSV):
        if sha(p) != outputs[p.name]:
            raise RuntimeError(f"Frozen independent holdout hash differs: {p}")

    holdout = pd.read_parquet(HOLDOUT_PARQUET).fillna("")
    blind = pd.read_csv(HOLDOUT_BLIND_TSV, sep="\t", dtype=str,
                        keep_default_na=False, encoding="utf-8-sig")
    for name, df in (("holdout parquet", holdout), ("blind human packet", blind)):
        if len(df) != 600 or "baseline_candidate_id" not in df.columns:
            raise RuntimeError(f"{name}: must contain exactly 600 pairs")
        if df["baseline_candidate_id"].eq("").any() or not df["baseline_candidate_id"].is_unique:
            raise RuntimeError(f"{name}: duplicate/blank candidate IDs")
    if holdout["sample_cohort"].value_counts().to_dict() != {
        "INDEPENDENT_PAIR_HOLDOUT_600": 600,
    }:
        raise RuntimeError("Unexpected holdout cohort")
    if holdout["openalex_work_id"].nunique() != 600:
        raise RuntimeError("Historical 600-distinct-OA holdout invariant violated")
    if holdout["project_work_id"].nunique() != 339:
        raise RuntimeError("Historical holdout W cardinality changed")
    keys = ["baseline_candidate_id", "project_work_id", "openalex_work_id",
            "target_title", "target_author", "openalex_title", "openalex_abstract"]
    for col in keys:
        if col not in holdout.columns or col not in blind.columns:
            raise RuntimeError(f"Missing shared holdout field: {col}")
    left = holdout[keys].sort_values("baseline_candidate_id").reset_index(drop=True)
    right = blind[keys].sort_values("baseline_candidate_id").reset_index(drop=True)
    if not left.equals(right):
        raise RuntimeError("Frozen human-blind packet and holdout parquet differ")
    # Do not load human judgments; this is the original, untouched frozen packet.
    human_columns = [c for c in blind.columns if c.startswith("researcher_")]
    if not human_columns or blind[human_columns].ne("").any().any():
        raise RuntimeError("Frozen blind packet should remain untouched; use a separate judged copy")

    # Require successful completion of all 160 development model requests.
    first20 = dev20.inputs()
    first20_path = dev20.OUT / "model_results_v0_1.jsonl"
    last140_path = dev140.OUT / "model_results_v0_1.jsonl"
    require(first20_path)
    require(last140_path)
    if not (dev20.OUT / "run_config.json").is_file():
        raise RuntimeError("Development-20 config missing")
    old_cfg = json.loads((dev20.OUT / "run_config.json").read_text(encoding="utf-8"))
    if old_cfg != dev20.config(MODEL, first20):
        raise RuntimeError("Development-20 frozen model/prompt/schema/inputs have changed")
    saved20 = dev140.load_jsonl(first20_path)
    if len(saved20) != 20 or set(x["baseline_candidate_id"] for x in saved20) != set(first20.baseline_candidate_id):
        raise RuntimeError("Development-20 not completed consistently")
    remaining140 = dev140.prepare()
    if not (dev140.OUT / "run_config.json").is_file():
        raise RuntimeError("Development-140 config missing")
    later_cfg = json.loads((dev140.OUT / "run_config.json").read_text(encoding="utf-8"))
    if later_cfg != dev140.current_config(remaining140):
        raise RuntimeError("Development-140 configuration changed")
    saved140 = dev140.saved_results(last140_path, set(remaining140.baseline_candidate_id))
    if len(saved140) != 140:
        raise RuntimeError("Development-140 not completed")

    # The independent 600-pair sample must be separate from all development pairs.
    development = pd.read_csv(dev20.INPUT, sep="\t", dtype=str, keep_default_na=False)
    if set(holdout.baseline_candidate_id) & set(development.baseline_candidate_id):
        raise RuntimeError("Holdout contains development candidate IDs")
    if set(holdout.openalex_work_id) & set(development.openalex_work_id):
        raise RuntimeError("Holdout contains development OA document IDs")
    # A human review *diagnostic*, not a statistical precision estimate.
    diagnosis = BASE / "retrieval_r2a1_development_160_review_v0_1" / "researcher_review_v0_1" \
        / "development_40_luna_comparison_v0_1" / "development_40_comparison_summary_v0_1.json"
    require(diagnosis)
    development_summary = json.loads(diagnosis.read_text(encoding="utf-8"))
    if development_summary.get("reviewed_n") != 40 or development_summary.get("exact_agreement") != 36:
        raise RuntimeError("Expected completed 40-case diagnostic was not found")

    bibcols = ["project_work_id", "current_ol_work_ids_json", "historical_titles_json",
               "historical_authors_json", "historical_edition_derived_min_years_json",
               "historical_subject_keys_json", "wikidata_label_en_effective", "wikidata_qid"]
    bib = pd.read_csv(dev20.BIB, sep="\t", dtype=str, keep_default_na=False, usecols=bibcols)
    if len(bib) != 32066 or not bib["project_work_id"].is_unique:
        raise RuntimeError("Incomplete frozen bibliographic evidence frame")
    cases = holdout.merge(bib, on="project_work_id", how="left", validate="many_to_one", indicator=True)
    if not cases["_merge"].eq("both").all():
        raise RuntimeError("Project W bibliographic context missing")
    cases = cases.drop(columns="_merge")
    for _, row in cases.iterrows():
        p = dev20.case_payload(row)
        if not isinstance(p["openalex_document"]["title"], str) or not isinstance(p["openalex_document"]["abstract"], str):
            raise RuntimeError("OpenAlex text fields must be strings; blanks are permitted")
    # Deterministic execution order determined without model outcomes or gold labels.
    cases["_order"] = cases["baseline_candidate_id"].map(
        lambda s: hashlib.sha256(("holdout-600-execution-v0_1\t" + s).encode("utf-8")).hexdigest()
    )
    cases = cases.sort_values(["_order", "baseline_candidate_id"], kind="stable")\
                 .drop(columns="_order").reset_index(drop=True)
    return cases, blind, development_summary


def cfg(cases: pd.DataFrame) -> dict:
    comparison_file = BASE / "retrieval_r2a1_development_160_review_v0_1" \
        / "researcher_review_v0_1/development_40_luna_comparison_v0_1/development_40_comparison_summary_v0_1.json"
    return {
        "release": RELEASE,
        "method_status": "FROZEN_PRE_HELDOUT_VALIDATION_PROMPT_NO_HOLDOUT_TUNING",
        "model": MODEL,
        "project_w_unit": "project_work_id x openalex_work_id",
        "heldout_n": 600,
        "heldout_sampling": "SRS pairs from new unjudged R2+A1 frame of 223875",
        "sample_manifest_sha256": sha(SAMPLE_MANIFEST),
        "holdout_parquet_sha256": sha(HOLDOUT_PARQUET),
        "holdout_blind_tsv_sha256": sha(HOLDOUT_BLIND_TSV),
        "bibliographic_evidence_sha256": sha(dev20.BIB),
        "dev_20_model_results_sha256": sha(dev20.OUT / "model_results_v0_1.jsonl"),
        "dev_140_model_results_sha256": sha(dev140.OUT / "model_results_v0_1.jsonl"),
        "dev_40_comparison_sha256": sha(comparison_file),
        "instructions_sha256": hashlib.sha256(dev20.PROMPT.encode("utf-8")).hexdigest(),
        "schema_sha256": hashlib.sha256(json.dumps(dev20.SCHEMA, sort_keys=True).encode()).hexdigest(),
        "ordered_holdout_ids_sha256": hashlib.sha256("\n".join(cases.baseline_candidate_id).encode()).hexdigest(),
        "no_human_judgments_supplied_to_model": True,
        "no_llm_outputs_in_human_review_sheet": True,
        "human_adjudication_not_yet_assessed": True,
    }


def checkpoint(path: Path, candidate_ids: set[str]) -> list[dict]:
    if not path.exists():
        return []
    saved = dev140.load_jsonl(path)
    for r in saved:
        if r["baseline_candidate_id"] not in candidate_ids:
            raise RuntimeError("Unknown candidate in saved holdout JSONL")
        if r.get("model") != MODEL or r.get("judgment") not in ALLOWED:
            raise RuntimeError("Bad saved model/judgment")
        if r.get("reason_code") not in ALLOWED[r["judgment"]]:
            raise RuntimeError("Saved reason-code mismatch")
        if r.get("confidence") not in ("HIGH", "MEDIUM", "LOW"):
            raise RuntimeError("Invalid saved confidence")
        if r.get("identity_context_adequacy") not in ("SUFFICIENT", "INSUFFICIENT", "CONFLICTING"):
            raise RuntimeError("Invalid saved identity adequacy")
    return saved


def make_blind_200(blind: pd.DataFrame, cases: pd.DataFrame) -> None:
    """Choose 200/600 by seed, independent of model output; preserve original sheet."""
    if REVIEW_OUT.exists():
        raise FileExistsError(f"Review output exists; refusing overwrite: {REVIEW_OUT}")
    if len(blind) != 600:
        raise RuntimeError("Cannot select from non-600 packet")
    rng = random.Random(BLIND200_SEED)
    chosen = sorted(rng.sample(range(600), NUM_HUMAN_FIRST))
    selected = blind.iloc[chosen].copy()
    # The frozen 600-blind TSV contains only basic title/abstract evidence.
    # Luna receives source-native OL/Wikidata bibliographic signals as well.
    # Give the human reviewer the SAME compact signals, without model labels.
    source_context = {}
    for _, row in cases.iterrows():
        packet = dev20.case_payload(row)
        source_context[row["baseline_candidate_id"]] = json.dumps(
            packet["source_native_bibliographic_signals_not_verified"],
            ensure_ascii=False, sort_keys=True,
        )
    selected["source_native_bibliographic_signals_given_to_LLM_json"] = (
        selected["baseline_candidate_id"].map(source_context)
    )
    if selected["source_native_bibliographic_signals_given_to_LLM_json"].isna().any():
        raise RuntimeError("Cannot attach equal bibliographic evidence to all reviewer cases")
    selected = selected.sort_values("review_case_id", kind="stable").reset_index(drop=True)
    if len(selected) != 200 or not selected.baseline_candidate_id.is_unique:
        raise RuntimeError("Unexpected blind 200 selection")
    REVIEW_OUT.mkdir(parents=True, exist_ok=False)
    out = REVIEW_OUT / "holdout_first_200_blind_review_v0_1.tsv"
    selected.to_csv(out, sep="\t", index=False, encoding="utf-8-sig", lineterminator="\n")
    info = {
        "release": "openalex-holdout-independent-blind-first-200-v0_1",
        "status": "RESEARCHER_BLIND_TO_LLM_PREDICTIONS",
        "source_sample": str(HOLDOUT_BLIND_TSV.relative_to(ROOT)),
        "source_sha256": sha(HOLDOUT_BLIND_TSV),
        "selection": "Simple random sample of 200 out of the pre-frozen 600, without model labels",
        "seed": BLIND200_SEED,
        "n": 200,
        "followup": "Additional 400 remain in original frozen blind packet; do not evaluate only easy W.",
        "input_schema_note": "The researcher_* fields in the new TSV are deliberately blank; save a separate judged copy. The additional bibliographic JSON is exactly the source-native signal packet given to Luna, NOT verified identity gold.",
        "output_sha256": sha(out),
    }
    (REVIEW_OUT / "blind_200_manifest_v0_1.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("BLIND RESEARCHER REVIEW: 200 pairs selected without inspecting model predictions")
    print("Review TSV:", out)
    print("KEEP MODEL OUTPUT SEALED until researcher judgments are saved.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Perform paid gpt-6-luna API requests")
    parser.add_argument("--max-new", type=int, default=10, help="Number of NEW paid requests this invocation (1..600)")
    parser.add_argument("--prepare-blind-200", action="store_true", help="Create a model-blind first 200 human review TSV; no API")
    args = parser.parse_args()
    if args.max_new < 1 or args.max_new > 600:
        parser.error("--max-new must be in range 1..600")
    if args.execute and args.prepare_blind_200:
        parser.error("Choose either --execute or --prepare-blind-200")
    cases, blind, _ = frozen_and_prepared()
    configuration = cfg(cases)
    conf_file = OUT / "run_config.json"
    results_file = OUT / "HOLDOUT_MODEL_KEY_DO_NOT_OPEN_BEFORE_RESEARCHER_REVIEW.jsonl"
    if OUT.exists() and not conf_file.is_file():
        raise RuntimeError("Output directory exists but has no matching config; refusing modification")
    if conf_file.exists():
        existing_config = json.loads(conf_file.read_text(encoding="utf-8"))
        if existing_config != configuration:
            raise RuntimeError("Saved holdout configuration differs from frozen inputs; stopping")
    saved = checkpoint(results_file, set(cases.baseline_candidate_id))
    done = {r["baseline_candidate_id"] for r in saved}
    todo = cases.loc[~cases.baseline_candidate_id.isin(done)]
    print("=== INDEPENDENT HOLDOUT 600: FROZEN LUNA ATTRIBUTION ===")
    print("Frame: 223875; sample: 600 SRS pairs; prior development completed: 160")
    print("Holdout processed:", len(saved), "/ 600; remaining:", len(todo))
    print("Model:", MODEL, "next permitted:", min(args.max_new, len(todo)))
    print("Missing abstracts:", int(cases.openalex_abstract.eq("").sum()))
    print("Predictions sealed; no judgments or confidence distribution displayed")
    if args.prepare_blind_200:
        make_blind_200(blind, cases)
        return
    if not args.execute:
        print("DRY RUN: no API calls or files written")
        return
    if todo.empty:
        print("COMPLETE: no new API calls needed")
        return
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY missing; no API calls made")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package not installed") from exc
    if not OUT.exists():
        OUT.mkdir(parents=True, exist_ok=False)
        conf_file.write_text(json.dumps(configuration, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    client = OpenAI(timeout=120.0, max_retries=2)
    failures = 0
    for _, row in todo.head(args.max_new).iterrows():
        try:
            response = client.responses.create(
                model=MODEL,
                instructions=dev20.PROMPT,
                input=json.dumps(dev20.case_payload(row), ensure_ascii=False),
                text={"format": {"type": "json_schema", "name": "literary_attribution_dev_v0_1",
                                 "schema": dev20.SCHEMA, "strict": True}},
                store=False,
            )
            if response.status != "completed" or not response.output_text:
                raise RuntimeError(f"Unexpected model status: {response.status}")
            label = json.loads(response.output_text)
            if not isinstance(label, dict) or set(label) != set(dev20.SCHEMA["required"]):
                raise RuntimeError("Structured output keys are unexpected")
            if label.get("judgment") not in ALLOWED:
                raise RuntimeError("Invalid judgment")
            if label.get("reason_code") not in ALLOWED[label["judgment"]]:
                raise RuntimeError("Reason code inconsistent with judgment")
            if label.get("confidence") not in ("HIGH", "MEDIUM", "LOW"):
                raise RuntimeError("Unexpected confidence")
            if label.get("identity_context_adequacy") not in ("SUFFICIENT", "INSUFFICIENT", "CONFLICTING"):
                raise RuntimeError("Unexpected identity context status")
            if not isinstance(label.get("note"), str) or not label["note"].strip():
                raise RuntimeError("Empty rationale")
            usage = response.usage
            record = {
                "baseline_candidate_id": row["baseline_candidate_id"],
                "project_work_id": row["project_work_id"],
                "openalex_work_id": row["openalex_work_id"],
                "sample_cohort": "INDEPENDENT_PAIR_HOLDOUT_600",
                "title_risk_signal": row["title_risk_signal"],
                "model": MODEL,
                "response_id": response.id,
                "input_tokens": int(usage.input_tokens or 0) if usage else 0,
                "output_tokens": int(usage.output_tokens or 0) if usage else 0,
                **label,
            }
            with results_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        except Exception as exc:
            failures += 1
            print("STOP ON MODEL ERROR:", type(exc).__name__, str(exc)[:240])
            break
    now = checkpoint(results_file, set(cases.baseline_candidate_id))
    print("Saved successes:", len(now), "/ 600; failures in this run:", failures)
    print("Total recorded input/output tokens:",
          sum(r["input_tokens"] for r in now), "/", sum(r["output_tokens"] for r in now))
    print("Holdout predictions saved but sealed:", results_file)
    print("NO prior source, developer sample, independent human labels, or integrated-v2 mutations")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
