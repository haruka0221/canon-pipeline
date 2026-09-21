#!/usr/bin/env python3

import csv
import hashlib
import importlib.util
import json
import os
import time
from pathlib import Path

from typesafe_sdk import Noul, TypeSafeClient


MODEL = "jev-1.13.0"

PROD = Path(
    "derived/wikidata_production/full_34789_v6_20260918"
)
PILOT = Path(
    "derived/wikidata_jev/pilot15_seed20260921"
)

SELECTION = PILOT / "selection.tsv"
PACKETS = PROD / "stage2_packets_v6_production_with_via_evidence.jsonl"
JUDGMENTS = PROD / "judgments_v6_production.jsonl"

RESULTS = PILOT / "results_jev-1.13.0.jsonl"
FAILURES = PILOT / "failures_jev-1.13.0.jsonl"

QUESTION_TEMPLATE = (
    "Does `candidates[{index}]` represent the same underlying literary "
    "work as the target described by `title`, `author`, and `year`? "
    "Judge identity of the work, not merely similarity of title or author. "
    "Return false for a different work, an adaptation, an unrelated "
    "scholarly article, or an edition/translation item that is not itself "
    "the target work-level item."
)

CRITERIA = {
    "true": (
        "The candidate represents the same underlying literary work "
        "as the target."
    ),
    "false": (
        "The candidate does not represent the same underlying literary "
        "work as the target."
    ),
}


def append_jsonl(path, obj):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def load_jsonl_by_target(path, wanted=None):
    out = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            x = json.loads(line)
            tid = x["target_id"]
            if wanted is None or tid in wanted:
                out[tid] = x
    return out


def canonical_json(obj):
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


# Exact GPT-v6 compact_packet implementation.
spec = importlib.util.spec_from_file_location(
    "gptjudge",
    "scripts/run_wikidata_v6_judge.py",
)
gptjudge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gptjudge)


with SELECTION.open(encoding="utf-8") as f:
    selection = list(csv.DictReader(f, delimiter="\t"))

selected_ids = [x["target_id"] for x in selection]
selected_set = set(selected_ids)

packets = load_jsonl_by_target(PACKETS, selected_set)
judgments = load_jsonl_by_target(JUDGMENTS, selected_set)

if set(packets) != selected_set:
    raise RuntimeError(
        f"packet target mismatch: missing={selected_set - set(packets)}"
    )

if set(judgments) != selected_set:
    raise RuntimeError(
        f"judgment target mismatch: missing={selected_set - set(judgments)}"
    )


completed = set()

if RESULTS.exists():
    with RESULTS.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                x = json.loads(line)
                completed.add(x["target_id"])


client = TypeSafeClient(model=MODEL)

question_spec = {
    "template": QUESTION_TEMPLATE,
    "criteria": CRITERIA,
}

question_spec_sha = hashlib.sha256(
    canonical_json(question_spec).encode("utf-8")
).hexdigest()


print("model:", MODEL)
print("selected:", len(selected_ids))
print("already completed:", len(completed))
print("question_spec_sha256:", question_spec_sha)
print()


for pos, sel in enumerate(selection, start=1):
    tid = sel["target_id"]

    if tid in completed:
        print(f"[{pos:02d}/15] {tid} SKIP")
        continue

    packet = packets[tid]
    gpt = judgments[tid]

    # This is exactly the representation GPT-v6 normally received.
    state = gptjudge.compact_packet(packet)

    state_serialized = canonical_json(state)
    state_sha = hashlib.sha256(
        state_serialized.encode("utf-8")
    ).hexdigest()

    questions = {}

    for i, candidate in enumerate(state["candidates"]):
        questions[f"candidate_{i}"] = Noul(
            instructions=QUESTION_TEMPLATE.format(index=i),
            criteria=CRITERIA,
        )

    print(
        f"[{pos:02d}/15] {tid} "
        f"{packet['title']} | "
        f"GPT={gpt['decision']} | "
        f"candidates={len(state['candidates'])}"
    )

    response = None
    last_error = None

    for attempt in range(1, 4):
        try:
            response = client.system_one(
                state=state,
                questions=questions,
            )
            break
        except KeyboardInterrupt:
            raise
        except Exception as e:
            last_error = e
            print(
                f"    API attempt {attempt}/3 failed: "
                f"{type(e).__name__}: {e}"
            )
            if attempt < 3:
                time.sleep(2 * attempt)

    if response is None:
        failure = {
            "target_id": tid,
            "requested_model": MODEL,
            "error_type": type(last_error).__name__,
            "error": str(last_error),
        }
        append_jsonl(FAILURES, failure)
        print("    FAILED; recorded and continuing")
        continue

    candidate_results = []

    for i, candidate in enumerate(state["candidates"]):
        answer = response.answers[f"candidate_{i}"]

        candidate_results.append({
            "candidate_index": i,
            "qid": candidate["qid"],
            "label": candidate.get("label", ""),
            "same_work_probability": float(answer.noul),
        })

    ranked = sorted(
        candidate_results,
        key=lambda x: x["same_work_probability"],
        reverse=True,
    )

    result = {
        "experiment": "jev_pilot15_seed20260921",
        "target_id": tid,
        "target": {
            "title": packet["title"],
            "author": packet["author"],
            "year": packet["year"],
        },
        "candidate_count": len(state["candidates"]),
        "requested_model": MODEL,
        "served_model": response.model,
        "input_representation": (
            "GPT-v6 compact_packet()"
        ),
        "compact_state_sha256": state_sha,
        "compact_state_chars": len(state_serialized),
        "question_spec_sha256": question_spec_sha,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
        "candidates": candidate_results,
        "jev_top_candidate": ranked[0] if ranked else None,
        "jev_second_candidate": ranked[1] if len(ranked) > 1 else None,
        "gpt_v6_reference_NOT_SHOWN_TO_JEV": {
            "decision": gpt["decision"],
            "selected_qid": gpt.get("selected_qid"),
            "confidence": gpt.get("confidence"),
            "reason": gpt.get("reason"),
        },
    }

    append_jsonl(RESULTS, result)

    print(
        "    top:",
        ranked[0]["qid"],
        f'p={ranked[0]["same_work_probability"]:.3f}',
        "|",
        ranked[0]["label"],
    )
    if len(ranked) > 1:
        print(
            "    second:",
            ranked[1]["qid"],
            f'p={ranked[1]["same_work_probability"]:.3f}',
            "|",
            ranked[1]["label"],
        )

    print(
        "    usage:",
        response.usage.input_tokens,
        "input /",
        response.usage.output_tokens,
        "output tokens",
    )


print()
print("RESULTS:", RESULTS)
print("FAILURES:", FAILURES if FAILURES.exists() else "none")
