#!/usr/bin/env python3
"""Complete the unused 140 of the frozen 160-pair R2+A1 development sample.

Requires the existing development-20 identity-aware run to have saved ALL 20
successful gpt-6-luna responses. Reuses its prompt/schema/payload exactly;
never reads the 600-pair holdout, calls it, or writes to earlier artifacts.

Safe dry run (no API, no writes):
    python -B scripts/run_openalex_r2a1_development_remaining_140_v0_1.py

Explicit paid batch (up to 10 calls, restartable):
    python -B scripts/run_openalex_r2a1_development_remaining_140_v0_1.py --execute --max-new 10
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

import pandas as pd
import run_openalex_r2a1_development_20_v0_1 as earlier

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "derived/openalex_production"
OUT = BASE / "retrieval_r2a1_development_remaining_140_identity_aware_v0_1"
OLD_OUT = earlier.OUT
MODEL = earlier.MODEL_DEFAULT
RELEASE = "openalex-r2a1-development-remaining-140-identity-aware-v0_1"


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing checkpoint: {path}")
    rows: list[dict] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise RuntimeError(f"Blank checkpoint line at {path}:{i}")
        try:
            r = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Broken JSONL at {path}:{i}; refusing modification") from exc
        if not isinstance(r, dict) or not r.get("baseline_candidate_id"):
            raise RuntimeError(f"Malformed checkpoint at {path}:{i}")
        rows.append(r)
    ids = [r["baseline_candidate_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise RuntimeError(f"Duplicate saved IDs in {path}")
    return rows


def prepare() -> pd.DataFrame:
    # Verify all preexisting development-20 results. These are inputs, not gold.
    if not earlier.INPUT.is_file() or not earlier.MANIFEST.is_file() or not earlier.BIB.is_file():
        raise FileNotFoundError("Frozen development inputs or bibliographic evidence absent")
    manifest = json.loads(earlier.MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("status") != "FROZEN_SAMPLE_SELECTION_ONLY_NO_ADJUDICATION":
        raise RuntimeError("Unrecognized frozen sample")
    if manifest.get("new_frame_n") != 223875 or manifest.get("development_random_n") != 120 or manifest.get("development_risk_n") != 40 or manifest.get("holdout_n") != 600:
        raise RuntimeError("Frozen sample configuration differs")
    if earlier.sha(earlier.INPUT) != manifest["output_sha256"][earlier.INPUT.name]:
        raise RuntimeError("Development input SHA mismatch")

    dev = pd.read_csv(earlier.INPUT, sep="\t", dtype=str, keep_default_na=False)
    if len(dev) != 160 or not dev["baseline_candidate_id"].is_unique:
        raise RuntimeError("Development sample is not 160 unique pairs")
    if dev["sample_cohort"].value_counts().to_dict() != {
        "DEVELOPMENT_RANDOM_120": 120,
        "DEVELOPMENT_TITLE_RISK_40": 40,
    }:
        raise RuntimeError("Unexpected development strata")

    first20 = earlier.pick(dev)
    if not (OLD_OUT / "run_config.json").is_file():
        raise FileNotFoundError("Missing original development-20 run_config.json")
    stored20 = json.loads((OLD_OUT / "run_config.json").read_text(encoding="utf-8"))
    if stored20 != earlier.config(MODEL, first20):
        raise RuntimeError("Original 20-case run config no longer matches frozen prompt/inputs")
    prev_results = load_jsonl(OLD_OUT / "model_results_v0_1.jsonl")
    orig20ids = set(first20["baseline_candidate_id"])
    if len(prev_results) != 20 or {r["baseline_candidate_id"] for r in prev_results} != orig20ids:
        raise RuntimeError("Original development-20 run must be 20/20 complete")
    for r in prev_results:
        if r.get("model") != MODEL or r.get("judgment") not in earlier.ALLOWED_REASONS:
            raise RuntimeError("Unexpected saved development-20 model/judgment")
        if r.get("reason_code") not in earlier.ALLOWED_REASONS[r["judgment"]]:
            raise RuntimeError("Unexpected saved development-20 reason code")

    remaining = dev.loc[~dev["baseline_candidate_id"].isin(orig20ids)].copy()
    if len(remaining) != 140 or remaining["sample_cohort"].value_counts().to_dict() != {
        "DEVELOPMENT_RANDOM_120": 110,
        "DEVELOPMENT_TITLE_RISK_40": 30,
    }:
        raise RuntimeError("Remaining development rows differ from 110 random + 30 risk")
    # Deterministic, judgment-blind execution order mixes sample components.
    remaining["_order"] = remaining["baseline_candidate_id"].map(
        lambda x: hashlib.sha256(("r2a1-dev140-order-v0_1\t" + x).encode("utf-8")).hexdigest()
    )
    remaining.sort_values(["_order", "baseline_candidate_id"], kind="stable", inplace=True)
    remaining.drop(columns=["_order"], inplace=True)
    remaining.reset_index(drop=True, inplace=True)

    bibcols = [
        "project_work_id", "current_ol_work_ids_json",
        "historical_titles_json", "historical_authors_json",
        "historical_edition_derived_min_years_json", "historical_subject_keys_json",
        "wikidata_label_en_effective", "wikidata_qid",
    ]
    bibliographic = pd.read_csv(earlier.BIB, sep="\t", dtype=str, keep_default_na=False, usecols=bibcols)
    if len(bibliographic) != 32066 or not bibliographic["project_work_id"].is_unique:
        raise RuntimeError("Combined Project-W bibliographic evidence is not intact")
    remaining = remaining.merge(bibliographic, on="project_work_id", how="left", validate="many_to_one", indicator=True)
    if not remaining["_merge"].eq("both").all():
        raise RuntimeError("Unmatched Project W in frozen bibliographic evidence")
    remaining.drop(columns=["_merge"], inplace=True)
    # Validate field names by building one payload without invoking the API.
    for _, row in remaining.iterrows():
        payload = earlier.case_payload(row)
        if not payload["openalex_document"]["title"]:
            raise RuntimeError("OpenAlex title is missing")
    return remaining


def current_config(cases: pd.DataFrame) -> dict:
    return {
        "release": RELEASE,
        "model": MODEL,
        "development_input_sha256": earlier.sha(earlier.INPUT),
        "bibliographic_input_sha256": earlier.sha(earlier.BIB),
        "sampling_manifest_sha256": earlier.sha(earlier.MANIFEST),
        "development_20_results_sha256": earlier.sha(OLD_OUT / "model_results_v0_1.jsonl"),
        "development_20_config_sha256": earlier.sha(OLD_OUT / "run_config.json"),
        "prompt_sha256": hashlib.sha256(earlier.PROMPT.encode()).hexdigest(),
        "schema_sha256": hashlib.sha256(json.dumps(earlier.SCHEMA, sort_keys=True).encode()).hexdigest(),
        "remaining_ids_ordered_sha256": hashlib.sha256("\n".join(cases["baseline_candidate_id"]).encode()).hexdigest(),
        "selected_count": len(cases),
        "uses_holdout": False,
        "judgment_status": "PROVISIONAL_LLM_ONLY_NOT_HUMAN_VALIDATED",
        "reuses_previous_prompt_and_payload": True,
    }


def saved_results(path: Path, expected_ids: set[str]) -> list[dict]:
    if not path.exists():
        return []
    rows = load_jsonl(path)
    for r in rows:
        if r["baseline_candidate_id"] not in expected_ids:
            raise RuntimeError("Checkpoint contains candidate outside frozen remaining-140 sample")
        if r.get("model") != MODEL or r.get("judgment") not in earlier.ALLOWED_REASONS:
            raise RuntimeError("Checkpoint model/judgment changed")
        if r.get("reason_code") not in earlier.ALLOWED_REASONS[r["judgment"]]:
            raise RuntimeError("Checkpoint reason code invalid")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Allow paid API calls")
    parser.add_argument("--max-new", type=int, default=10, help="Max paid new calls in this invocation, 1–140")
    args = parser.parse_args()
    if not 1 <= args.max_new <= 140:
        parser.error("--max-new must be between 1 and 140")

    cases = prepare()
    cfg = current_config(cases)
    conf_path = OUT / "run_config.json"
    result_path = OUT / "model_results_v0_1.jsonl"
    if OUT.exists() and not conf_path.is_file():
        raise RuntimeError("Refusing existing output directory without run_config.json")
    if conf_path.exists() and json.loads(conf_path.read_text(encoding="utf-8")) != cfg:
        raise RuntimeError("Run configuration changed: refusing checkpoint continuation")

    saved = saved_results(result_path, set(cases["baseline_candidate_id"]))
    done = {r["baseline_candidate_id"] for r in saved}
    todo = cases.loc[~cases["baseline_candidate_id"].isin(done)]
    print("=== OPENALEX R2+A1 DEVELOPMENT REMAINING 140 (IDENTITY AWARE) ===")
    print("Source: frozen development 160; previous 20 verified; holdout 600 NOT OPENED")
    print("Remaining cohort: 110 random + 30 title-risk")
    print("Cases in this release:", len(cases), "already saved:", len(saved), "remaining:", len(todo))
    print("Model:", MODEL, "maximum new this invocation:", args.max_new)
    print("Missing abstracts:", int(cases["openalex_abstract"].eq("").sum()))
    print("Current LLM provisional labels:", dict(Counter(r["judgment"] for r in saved)))
    print("Existing output:", OUT if OUT.exists() else "none")
    if not args.execute:
        print("DRY RUN: no API calls, no writes, no holdout access.")
        return
    if todo.empty:
        print("COMPLETE: no new API requests required")
        return
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not available; no API calls made")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("OpenAI Python SDK not installed") from exc
    if not OUT.exists():
        OUT.mkdir(parents=True, exist_ok=False)
        conf_path.write_text(json.dumps(cfg, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    client = OpenAI(timeout=120.0, max_retries=2)
    tally = Counter(r["judgment"] for r in saved)
    failures = 0
    for _, r in todo.head(args.max_new).iterrows():
        try:
            response = client.responses.create(
                model=MODEL,
                instructions=earlier.PROMPT,
                input=json.dumps(earlier.case_payload(r), ensure_ascii=False),
                text={"format": {"type": "json_schema", "name": "literary_attribution_dev_v0_1", "schema": earlier.SCHEMA, "strict": True}},
                store=False,
            )
            if response.status != "completed" or not response.output_text:
                raise RuntimeError(f"Bad response status: {response.status}")
            label = json.loads(response.output_text)
            if set(label) != set(earlier.SCHEMA["required"]):
                raise RuntimeError("Unexpected label keys")
            if label.get("judgment") not in earlier.ALLOWED_REASONS:
                raise RuntimeError("Unexpected label judgment")
            if label.get("reason_code") not in earlier.ALLOWED_REASONS[label["judgment"]]:
                raise RuntimeError("Unexpected label reason")
            if not isinstance(label.get("note"), str) or not label["note"].strip():
                raise RuntimeError("Empty or invalid rationale")
            usage = response.usage
            record = {
                "baseline_candidate_id": r["baseline_candidate_id"],
                "project_work_id": r["project_work_id"],
                "openalex_work_id": r["openalex_work_id"],
                "sample_cohort": r["sample_cohort"],
                "title_risk_signal": r["title_risk_signal"],
                "model": MODEL,
                "response_id": response.id,
                "input_tokens": int(usage.input_tokens or 0) if usage else 0,
                "output_tokens": int(usage.output_tokens or 0) if usage else 0,
                **label,
            }
            with result_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            tally[label["judgment"]] += 1
        except Exception as exc:
            failures += 1
            print("STOP ON API/VALIDATION ERROR:", type(exc).__name__, str(exc)[:240])
            break
    now = saved_results(result_path, set(cases["baseline_candidate_id"]))
    print("Saved successes:", len(now), "/140; failed attempts this invocation:", failures)
    print("Provisional LLM distribution (NOT gold):", dict(Counter(r["judgment"] for r in now)))
    print("Input/output tokens on saved successes:", sum(r.get("input_tokens", 0) for r in now), "/", sum(r.get("output_tokens", 0) for r in now))
    print("Output:", result_path)
    print("Previous 20, blind holdout 600, frozen decisions and integrated v2 unchanged.")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
