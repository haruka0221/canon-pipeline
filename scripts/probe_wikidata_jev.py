#!/usr/bin/env python3

import json
from pathlib import Path

from typesafe_sdk import Noul, TypeSafeClient


MODEL = "jev-1.13.0"
TARGET_ID = "OL1527021W"

PACKETS = Path(
    "derived/wikidata_production/full_34789_v6_20260918/"
    "stage2_packets_v6_production_with_via_evidence.jsonl"
)

JUDGMENTS = Path(
    "derived/wikidata_production/full_34789_v6_20260918/"
    "judgments_v6_production.jsonl"
)

OUTPUT = Path(
    "derived/wikidata_jev/probes/"
    f"{TARGET_ID}_{MODEL}.json"
)


def load_by_target(path, target_id):
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            x = json.loads(line)
            if x["target_id"] == target_id:
                return x
    raise RuntimeError(f"{target_id} not found in {path}")


packet = load_by_target(PACKETS, TARGET_ID)
gpt = load_by_target(JUDGMENTS, TARGET_ID)

# Probe only:
# preserve the full frozen production packet as Jev state.
state = packet

questions = {}

for i, candidate in enumerate(packet["candidates"]):
    questions[f"candidate_{i}"] = Noul(
        instructions=(
            f"Does `candidates[{i}]` represent the same underlying "
            "literary work as the target described by `title`, `author`, "
            "and `year`? Judge identity of the work, not merely similarity "
            "of title or author. Return false for a different work, "
            "an adaptation, an unrelated scholarly article, or an edition/"
            "translation item that is not itself the target work-level item."
        ),
        criteria={
            "true": (
                "The candidate represents the same underlying literary work "
                "as the target."
            ),
            "false": (
                "The candidate does not represent the same underlying "
                "literary work as the target."
            ),
        },
    )

client = TypeSafeClient(model=MODEL)

response = client.system_one(
    state=state,
    questions=questions,
)

results = []

for i, candidate in enumerate(packet["candidates"]):
    key = f"candidate_{i}"
    probability = response.answers[key].noul

    results.append({
        "candidate_index": i,
        "qid": candidate["qid"],
        "label": candidate.get("label", ""),
        "same_work_probability": probability,
    })

out = {
    "experiment": "single_target_probe",
    "target_id": packet["target_id"],
    "target": {
        "title": packet["title"],
        "author": packet["author"],
        "year": packet["year"],
    },
    "requested_model": MODEL,
    "served_model": response.model,
    "usage": {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    },
    "jev_results": results,
    "gpt_v6_reference_NOT_SHOWN_TO_JEV": {
        "decision": gpt["decision"],
        "selected_qid": gpt["selected_qid"],
        "confidence": gpt["confidence"],
        "reason": gpt["reason"],
    },
}

OUTPUT.write_text(
    json.dumps(out, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

print("=== TARGET ===")
print(
    packet["target_id"],
    "|", packet["title"],
    "|", packet["author"],
    "|", packet["year"],
)

print("\n=== JEV ===")
print("requested model:", MODEL)
print("served model:", response.model)

for x in results:
    print(
        f'{x["qid"]:12s}',
        f'p={x["same_work_probability"]:.6f}',
        "|",
        x["label"],
    )

print("\n=== GPT-v6 REFERENCE (not supplied to Jev) ===")
print(
    gpt["decision"],
    gpt["selected_qid"],
    gpt["confidence"],
)
print(gpt["reason"])

print("\n=== USAGE ===")
print("input_tokens:", response.usage.input_tokens)
print("output_tokens:", response.usage.output_tokens)

print("\nSaved:", OUTPUT)
