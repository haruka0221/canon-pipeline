#!/usr/bin/env python3

import csv
import importlib.util
import json
import random
from collections import defaultdict
from pathlib import Path

SEED = 20260921
N_PER_CLASS = 5
MAX_CANDIDATES = 8
MAX_STATE_CHARS = 60000

OUT = Path(
    "derived/wikidata_production/full_34789_v6_20260918"
)
PILOT = Path(
    "derived/wikidata_jev/pilot15_seed20260921"
)

PACKETS = OUT / "stage2_packets_v6_production_with_via_evidence.jsonl"
JUDGMENTS = OUT / "judgments_v6_production.jsonl"
SELECTION = PILOT / "selection.tsv"
MANIFEST = PILOT / "selection_manifest.json"

# Load the exact GPT-v6 compact_packet() implementation.
spec = importlib.util.spec_from_file_location(
    "gptjudge",
    "scripts/run_wikidata_v6_judge.py",
)
gptjudge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gptjudge)

judgments = {}
with JUDGMENTS.open(encoding="utf-8") as f:
    for line in f:
        if line.strip():
            x = json.loads(line)
            judgments[x["target_id"]] = x

eligible = defaultdict(list)

with PACKETS.open(encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue

        p = json.loads(line)
        tid = p["target_id"]
        j = judgments.get(tid)

        if not j:
            continue

        decision = j["decision"]

        if decision not in {"MATCH", "NO_MATCH", "AMBIGUOUS"}:
            continue

        # The one production context-fallback case is excluded from
        # this ordinary compact-packet pilot.
        if j.get("context_safe_fallback"):
            continue

        n_candidates = len(p.get("candidates", []))

        if not (1 <= n_candidates <= MAX_CANDIDATES):
            continue

        compact = gptjudge.compact_packet(p)
        state_chars = len(
            json.dumps(compact, ensure_ascii=False)
        )

        if state_chars > MAX_STATE_CHARS:
            continue

        eligible[decision].append({
            "target_id": tid,
            "title": p["title"],
            "author": p["author"],
            "year": p["year"],
            "candidate_count": n_candidates,
            "compact_state_chars": state_chars,
            "gpt_decision": decision,
            "gpt_selected_qid": j.get("selected_qid") or "",
            "gpt_confidence": j.get("confidence", ""),
        })

rng = random.Random(SEED)
selected = []

for decision in ["MATCH", "NO_MATCH", "AMBIGUOUS"]:
    pool = sorted(
        eligible[decision],
        key=lambda x: x["target_id"],
    )

    if len(pool) < N_PER_CLASS:
        raise RuntimeError(
            f"Not enough eligible {decision}: {len(pool)}"
        )

    picks = rng.sample(pool, N_PER_CLASS)
    selected.extend(picks)

PILOT.mkdir(parents=True, exist_ok=True)

fields = [
    "target_id",
    "title",
    "author",
    "year",
    "candidate_count",
    "compact_state_chars",
    "gpt_decision",
    "gpt_selected_qid",
    "gpt_confidence",
]

with SELECTION.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(
        f,
        fieldnames=fields,
        delimiter="\t",
        lineterminator="\n",
    )
    w.writeheader()
    w.writerows(selected)

manifest = {
    "purpose": (
        "Exploratory Jev behavior pilot; not an accuracy evaluation "
        "and GPT-v6 decisions are not treated as gold."
    ),
    "seed": SEED,
    "n_per_gpt_decision": N_PER_CLASS,
    "total_selected": len(selected),
    "filters": {
        "max_candidates": MAX_CANDIDATES,
        "max_compact_state_chars": MAX_STATE_CHARS,
        "exclude_context_safe_fallback": True,
    },
    "input_representation": (
        "Exact compact_packet() implementation from "
        "scripts/run_wikidata_v6_judge.py"
    ),
    "jev_model_planned": "jev-1.13.0",
}

MANIFEST.write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

print("=== ELIGIBLE COUNTS ===")
for d in ["MATCH", "NO_MATCH", "AMBIGUOUS"]:
    print(d, len(eligible[d]))

print("\n=== SELECTED PILOT ===")
for x in selected:
    print(
        f'{x["gpt_decision"]:9s}',
        x["target_id"],
        f'cand={x["candidate_count"]}',
        f'chars={x["compact_state_chars"]}',
        "|",
        x["title"],
        "|",
        x["author"],
    )

print("\nSaved:", SELECTION)
print("Saved:", MANIFEST)
