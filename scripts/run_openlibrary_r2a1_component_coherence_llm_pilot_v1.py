#!/usr/bin/env python3

from collections import Counter
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]

IN_DIR = (
    ROOT / "derived/identity"
    / "openlibrary_r2a1_component_coherence_review_input_v1"
)
SOURCE = IN_DIR / "component_coherence_review_input_v1.jsonl"
INDEX = IN_DIR / "component_coherence_review_index_v1.tsv"
SOURCE_MANIFEST = IN_DIR / "component_coherence_review_manifest_v1.json"

PROMPT = (
    ROOT / "docs"
    / "OPENLIBRARY_R2A1_COMPONENT_COHERENCE_LLM_PROMPT_V1.md"
)

OUT = (
    ROOT / "derived/identity"
    / "openlibrary_r2a1_component_coherence_llm_pilot_v1"
)

FROZEN_HEAD = "dde7af0177f0dc942fd20b587d1f27f262a765e0"
MODEL = "gpt-6.1-sol"

PILOT = {
    "W000030498_C04": ("CCV1_0066", 2),
    "W000021761_C04": ("CCV1_0052", 8),
    "W000014024_C02": ("CCV1_0040", 4),
}

DECISIONS = [
    "ONE_PUBLICATION_FAMILY",
    "MULTIPLE_PUBLICATION_FAMILIES",
    "INSUFFICIENT_EVIDENCE",
    "NOT_ASSESSABLE_SINGLE_EDITION",
]

FLAGS = [
    "DIFFERENT_EDITED_SELECTIONS",
    "MIXED_COLLECTION_OR_OMNIBUS",
    "AUTHOR_SUBJECT_CONFUSION",
    "GENERIC_TITLE_AMBIGUITY",
    "MISSING_EDITORIAL_INFORMATION",
    "FORMAT_CONTENT_UNVERIFIED",
    "OTHER_EVIDENCE_CONFLICT",
]

RELATIONS = [
    "AUTHOR_TEXT",
    "ABOUT_AUTHOR",
    "MIXED",
    "UNKNOWN",
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_jsonl(path, rows):
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(
                json.dumps(row, ensure_ascii=False, sort_keys=True)
                + "\n"
            )
    os.replace(temp, path)


def write_json(path, data):
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(
        json.dumps(
            data, ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n",
        encoding="utf-8",
    )
    os.replace(temp, path)


def make_schema(case):
    keys = sorted(e["edition_key"] for e in case["editions"])

    group = {
        "type": "object",
        "properties": {
            "local_group_id": {"type": "string"},
            "edition_keys": {
                "type": "array",
                "items": {"type": "string", "enum": keys},
            },
            "provisional_label": {"type": "string"},
            "authorship_relation": {
                "type": "string",
                "enum": RELATIONS,
            },
            "evidence_note": {"type": "string"},
        },
        "required": [
            "local_group_id",
            "edition_keys",
            "provisional_label",
            "authorship_relation",
            "evidence_note",
        ],
        "additionalProperties": False,
    }

    return {
        "type": "object",
        "properties": {
            "case_id": {
                "type": "string",
                "enum": [case["case_id"]],
            },
            "coherence_decision": {
                "type": "string",
                "enum": DECISIONS,
            },
            "confidence": {
                "type": "string",
                "enum": ["HIGH", "MEDIUM", "LOW"],
            },
            "proposed_groups": {
                "type": "array",
                "items": group,
            },
            "unresolved_edition_keys": {
                "type": "array",
                "items": {"type": "string", "enum": keys},
            },
            "diagnostic_flags": {
                "type": "array",
                "items": {"type": "string", "enum": FLAGS},
            },
            "evidence_note": {"type": "string"},
        },
        "required": [
            "case_id",
            "coherence_decision",
            "confidence",
            "proposed_groups",
            "unresolved_edition_keys",
            "diagnostic_flags",
            "evidence_note",
        ],
        "additionalProperties": False,
    }


def validate(case, obj):
    assert obj["case_id"] == case["case_id"]

    keys = [e["edition_key"] for e in case["editions"]]
    assert len(keys) == len(set(keys))

    groups = obj["proposed_groups"]
    group_ids = [g["local_group_id"] for g in groups]

    assert len(group_ids) == len(set(group_ids))
    assert all(re.fullmatch(r"G\d{2}", k) for k in group_ids)
    assert all(g["edition_keys"] for g in groups)
    assert all(
        g["provisional_label"].strip()
        and g["evidence_note"].strip()
        for g in groups
    )

    used = (
        [e for g in groups for e in g["edition_keys"]]
        + obj["unresolved_edition_keys"]
    )

    assert len(used) == len(set(used)) == len(keys)
    assert set(used) == set(keys)
    assert len(obj["diagnostic_flags"]) == len(
        set(obj["diagnostic_flags"])
    )
    assert obj["evidence_note"].strip()

    decision = obj["coherence_decision"]

    if decision == "ONE_PUBLICATION_FAMILY":
        assert len(groups) == 1
        assert not obj["unresolved_edition_keys"]

    if decision == "MULTIPLE_PUBLICATION_FAMILIES":
        assert len(groups) >= 2

    if decision == "NOT_ASSESSABLE_SINGLE_EDITION":
        assert len(keys) == 1


def main():
    parser = argparse.ArgumentParser()

    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--dry-run", action="store_true")
    action.add_argument("--run", action="store_true")

    args = parser.parse_args()

    assert all(
        p.is_file()
        for p in [SOURCE, INDEX, SOURCE_MANIFEST, PROMPT]
    ), "Missing input or prompt"

    manifest = json.loads(
        SOURCE_MANIFEST.read_text(encoding="utf-8")
    )

    assert sha(SOURCE) == manifest["outputs"][SOURCE.name]
    assert sha(INDEX) == manifest["outputs"][INDEX.name]
    assert manifest["upstream_commit"] == (
        "c2a18cec290532ae529d87b2c3e28d0b4b61e201"
    )

    cases = [
        json.loads(line)
        for line in SOURCE.read_text(
            encoding="utf-8"
        ).splitlines()
    ]

    assert len(cases) == 71

    by_component = {
        c["component_id"]: c for c in cases
    }
    assert len(by_component) == 71

    chosen = []

    for cid, (case_id, n) in PILOT.items():
        c = by_component[cid]

        assert c["case_id"] == case_id
        assert len(c["editions"]) == n
        assert len({
            e["edition_key"] for e in c["editions"]
        }) == n

        chosen.append(c)

    assert sum(len(c["editions"]) for c in chosen) == 14

    prompt = PROMPT.read_text(encoding="utf-8")

    head = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()

    assert head == FROZEN_HEAD, (
        f"Unexpected local HEAD: {head}"
    )

    print("=== PILOT PREFLIGHT ===")
    print(
        "cases:",
        [
            (
                c["case_id"],
                c["component_id"],
                len(c["editions"]),
            )
            for c in chosen
        ],
    )
    print("input_sha256:", sha(SOURCE))
    print("prompt_sha256:", sha(PROMPT))
    print("head:", head)

    if args.dry_run:
        print("DRY RUN PASSED — NO API CALLS OR FILE WRITES")
        return

    assert not OUT.exists(), (
        f"Output already exists; refusing overwrite: {OUT}"
    )
    assert os.getenv("OPENAI_API_KEY"), (
        "OPENAI_API_KEY not set"
    )

    from openai import OpenAI
    client = OpenAI()

    OUT.mkdir(parents=True, exist_ok=False)

    config = {
        "release": (
            "openlibrary-r2a1-component-coherence-llm-pilot-v1"
        ),
        "mode": "3_case_pilot_only",
        "input_freeze_commit": head,
        "model_requested": MODEL,
        "case_ids": [
            c["case_id"] for c in chosen
        ],
        "input_sha256": sha(SOURCE),
        "input_manifest_sha256": sha(SOURCE_MANIFEST),
        "prompt_sha256": sha(PROMPT),
        "runner_sha256": sha(Path(__file__)),
    }

    write_json(
        OUT / "pilot_run_config_v1.json",
        config,
    )

    results = []
    raw_responses = []

    for case in chosen:
        print(
            "CALL:",
            case["case_id"],
            case["component_id"],
            flush=True,
        )

        for attempt in range(1, 4):
            try:
                response = client.responses.create(
                    model=MODEL,
                    input=(
                        prompt
                        + "\n\nCASE JSON (EVIDENCE ONLY)\n"
                        + json.dumps(
                            case, ensure_ascii=False
                        )
                    ),
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": (
                                "ol_component_coherence_pilot_v1"
                            ),
                            "strict": True,
                            "schema": make_schema(case),
                        }
                    },
                )

                assert response.status == "completed", (
                    f"Unexpected status: {response.status}"
                )

                obj = json.loads(response.output_text)
                validate(case, obj)
                break

            except Exception as exc:
                if attempt == 3:
                    raise RuntimeError(
                        f"{case['case_id']} failed: "
                        f"{type(exc).__name__}: {exc}"
                    ) from exc

                time.sleep(2 ** attempt)

        usage = response.usage

        results.append({
            "case_id": case["case_id"],
            "component_id": case["component_id"],
            "expected_edition_rows": len(case["editions"]),
            "result": obj,
            "response_id": response.id,
            "model_returned": response.model,
            "input_tokens": getattr(
                usage, "input_tokens", None
            ),
            "output_tokens": getattr(
                usage, "output_tokens", None
            ),
        })

        raw_responses.append({
            "case_id": case["case_id"],
            "response": response.model_dump(mode="json"),
        })

        write_jsonl(
            OUT / "pilot_responses.partial.jsonl",
            results,
        )
        write_jsonl(
            OUT / "pilot_raw_api_responses.partial.jsonl",
            raw_responses,
        )

        print(
            "  VALID:",
            obj["coherence_decision"],
            "groups:",
            len(obj["proposed_groups"]),
            "unresolved:",
            len(obj["unresolved_edition_keys"]),
            flush=True,
        )

    assert len(results) == len(raw_responses) == 3

    result_path = OUT / "pilot_responses_v1.jsonl"
    raw_path = OUT / "pilot_raw_api_responses_v1.jsonl"
    audit_path = OUT / "pilot_audit_v1.json"

    write_jsonl(result_path, results)
    write_jsonl(raw_path, raw_responses)

    audit = {
        "status": "PILOT_QC_PASSED",
        "cases": len(results),
        "edition_rows": sum(
            x["expected_edition_rows"] for x in results
        ),
        "decisions": dict(Counter(
            x["result"]["coherence_decision"]
            for x in results
        )),
        "human_identity_decisions_created": 0,
    }

    write_json(audit_path, audit)

    write_json(
        OUT / "pilot_manifest_v1.json",
        {
            **config,
            "outputs": {
                p.name: sha(p)
                for p in [
                    result_path,
                    raw_path,
                    audit_path,
                    OUT / "pilot_run_config_v1.json",
                ]
            },
            "semantics": (
                "Provisional LLM diagnostic; not an identity "
                "adjudication, scope decision, or approved successor."
            ),
        },
    )

    (OUT / "pilot_responses.partial.jsonl").unlink()
    (OUT / "pilot_raw_api_responses.partial.jsonl").unlink()

    print("=== PILOT QC: PASSED ===")
    print(json.dumps(
        audit, ensure_ascii=False, indent=2
    ))
    print("output:", OUT)


if __name__ == "__main__":
    main()
