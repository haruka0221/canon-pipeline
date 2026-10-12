#!/usr/bin/env python3

from pathlib import Path
from collections import Counter
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_openlibrary_r2a1_component_coherence_llm_pilot_v1 import (
    make_schema,
    validate,
    MODEL,
)

from openai import OpenAI

BASE = ROOT / "derived/identity"

INPUT = (
    BASE / "openlibrary_r2a1_component_coherence_review_input_v1"
)
SOURCE = INPUT / "component_coherence_review_input_v1.jsonl"
INPUT_MANIFEST = INPUT / "component_coherence_review_manifest_v1.json"

PROMPT = (
    ROOT / "docs"
    / "OPENLIBRARY_R2A1_COMPONENT_COHERENCE_LLM_PROMPT_V1.md"
)

PILOT_CONFIG = (
    BASE / "openlibrary_r2a1_component_coherence_llm_pilot_v1"
    / "pilot_run_config_v1.json"
)

OUT = BASE / "openlibrary_r2a1_component_coherence_llm_full_v1"
CASE_DIR = OUT / "cases"

MAX_WORKERS = 4
MAX_ATTEMPTS = 3


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path, obj):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def atomic_jsonl(path, rows):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        "".join(
            json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n"
            for x in rows
        ),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def main():
    source_manifest = json.loads(INPUT_MANIFEST.read_text())
    pilot_config = json.loads(PILOT_CONFIG.read_text())

    assert sha(SOURCE) == source_manifest["outputs"][SOURCE.name]
    assert sha(PROMPT) == pilot_config["prompt_sha256"]

    pilot_runner = (
        ROOT / "scripts"
        / "run_openlibrary_r2a1_component_coherence_llm_pilot_v1.py"
    )
    assert sha(pilot_runner) == pilot_config["runner_sha256"]

    cases = [
        json.loads(line)
        for line in SOURCE.read_text(
            encoding="utf-8"
        ).splitlines()
    ]

    assert len(cases) == 71
    assert len({c["case_id"] for c in cases}) == 71
    assert len({c["component_id"] for c in cases}) == 71

    all_keys = [
        e["edition_key"]
        for c in cases
        for e in c["editions"]
    ]

    assert len(all_keys) == 371
    assert len(set(all_keys)) == 371

    cases = sorted(cases, key=lambda c: c["case_id"])
    prompt = PROMPT.read_text(encoding="utf-8")

    config = {
        "release": "openlibrary-r2a1-component-coherence-llm-full-v1",
        "model": MODEL,
        "cases": 71,
        "editions": 371,
        "max_workers": MAX_WORKERS,
        "source_sha256": sha(SOURCE),
        "prompt_sha256": sha(PROMPT),
        "pilot_runner_sha256": sha(pilot_runner),
        "full_runner_sha256": sha(Path(__file__)),
    }

    config_path = OUT / "full_run_config_v1.json"

    if OUT.exists():
        assert config_path.exists(), (
            "Existing output has no run config; stopping"
        )
        assert json.loads(config_path.read_text()) == config, (
            "Run config changed; refusing to mix releases"
        )
    else:
        CASE_DIR.mkdir(parents=True, exist_ok=False)
        atomic_json(config_path, config)

    CASE_DIR.mkdir(parents=True, exist_ok=True)

    pending = []

    for c in cases:
        path = CASE_DIR / (c["case_id"] + ".json")

        if path.exists():
            saved = json.loads(path.read_text())
            assert saved["component_id"] == c["component_id"]
            assert saved["case_id"] == c["case_id"]
            validate(c, saved["result"])
        else:
            pending.append(c)

    print("=== FULL COHERENCE REVIEW V1 ===", flush=True)
    print("total cases:", len(cases), flush=True)
    print("completed:", len(cases) - len(pending), flush=True)
    print("pending:", len(pending), flush=True)
    print("model:", MODEL, flush=True)

    if pending:
        assert os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY missing"

        client = OpenAI()

        def run_case(case):
            case_id = case["case_id"]
            path = CASE_DIR / (case_id + ".json")

            last_error = None

            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    response = client.responses.create(
                        model=MODEL,
                        input=(
                            prompt
                            + "\n\nCASE JSON (EVIDENCE ONLY)\n"
                            + json.dumps(case, ensure_ascii=False)
                        ),
                        text={
                            "format": {
                                "type": "json_schema",
                                "name": "ol_component_coherence_full_v1",
                                "strict": True,
                                "schema": make_schema(case),
                            }
                        },
                    )

                    assert response.status == "completed"
                    result = json.loads(response.output_text)
                    validate(case, result)

                    saved = {
                        "case_id": case_id,
                        "component_id": case["component_id"],
                        "edition_rows": len(case["editions"]),
                        "result": result,
                        "response_id": response.id,
                        "model_returned": response.model,
                        "raw_response": response.model_dump(
                            mode="json"
                        ),
                    }

                    atomic_json(path, saved)

                    return (
                        case_id,
                        result["coherence_decision"],
                        len(case["editions"]),
                    )

                except Exception as exc:
                    last_error = exc
                    if attempt < MAX_ATTEMPTS:
                        time.sleep(2 ** attempt)

            raise RuntimeError(
                f"{case_id}: {type(last_error).__name__}: "
                f"{last_error}"
            )

        failures = []

        with ThreadPoolExecutor(
            max_workers=MAX_WORKERS
        ) as pool:
            futures = {
                pool.submit(run_case, c): c["case_id"]
                for c in pending
            }

            for future in as_completed(futures):
                case_id = futures[future]
                try:
                    cid, decision, n = future.result()
                    print(
                        "DONE:", cid, decision, n,
                        flush=True,
                    )
                except Exception as exc:
                    failures.append((case_id, str(exc)))
                    print(
                        "FAILED:", case_id, exc,
                        flush=True,
                    )

        if failures:
            print("=== INCOMPLETE; RESULTS PRESERVED ===")
            for case_id, error in failures:
                print(case_id, error)
            raise SystemExit(1)

    results = []
    counts = Counter()
    decisions = Counter()

    for case in cases:
        path = CASE_DIR / (case["case_id"] + ".json")
        assert path.exists()

        saved = json.loads(path.read_text())
        assert saved["case_id"] == case["case_id"]
        assert saved["component_id"] == case["component_id"]

        validate(case, saved["result"])

        results.append({
            k: v for k, v in saved.items()
            if k != "raw_response"
        })

        counts["cases"] += 1
        counts["editions"] += len(case["editions"])
        counts["proposed_groups"] += len(
            saved["result"]["proposed_groups"]
        )
        counts["unresolved_editions"] += len(
            saved["result"]["unresolved_edition_keys"]
        )

        decisions[
            saved["result"]["coherence_decision"]
        ] += 1

    assert counts["cases"] == 71
    assert counts["editions"] == 371

    result_path = OUT / "full_results_v1.jsonl"
    audit_path = OUT / "full_audit_v1.json"

    atomic_jsonl(result_path, results)

    audit = {
        "status": "FULL_QC_PASSED",
        "counts": dict(counts),
        "decisions": dict(decisions),
        "human_identity_decisions_created": 0,
    }

    atomic_json(audit_path, audit)

    atomic_json(
        OUT / "full_manifest_v1.json",
        {
            "release": config["release"],
            "inputs": {
                "source": sha(SOURCE),
                "prompt": sha(PROMPT),
                "pilot_runner": sha(pilot_runner),
                "full_runner": sha(Path(__file__)),
            },
            "outputs": {
                result_path.name: sha(result_path),
                audit_path.name: sha(audit_path),
                config_path.name: sha(config_path),
            },
            "case_file_sha256": {
                c["case_id"]: sha(
                    CASE_DIR / (c["case_id"] + ".json")
                )
                for c in cases
            },
            "semantics": (
                "Provisional LLM coherence diagnostic only. "
                "No project work IDs or identity assertions created."
            ),
        },
    )

    print("\n=== FULL QC: PASSED ===")
    print(json.dumps(
        audit, ensure_ascii=False, indent=2
    ))
    print("output:", OUT)


if __name__ == "__main__":
    main()
