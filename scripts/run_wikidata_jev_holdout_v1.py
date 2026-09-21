#!/usr/bin/env python3

import hashlib
import importlib.util
import json
import os
import time
from pathlib import Path

from typesafe_sdk import Choice, Noul, TypeSafeClient


MODEL = "jev-1.13.0"
EXPECTED_QUESTION_SPEC_SHA256 = (
    "0261be5dde85512125d6a773f16cf5131829b62d5fe6c42ffba9638518630f59"
)

HOLDOUT = Path(
    "derived/benchmark/holdout/fresh_random100_v6_20260918"
)
PACKETS = HOLDOUT / "stage2_packets.jsonl"

OUT = Path(
    "derived/wikidata_jev/holdout100_jev_v1_20260921"
)
RESULTS = OUT / "raw_predictions_jev-1.13.0.jsonl"
FAILURES = OUT / "failures_jev-1.13.0.jsonl"
MANIFEST = OUT / "run_manifest.json"


SAME_WORK_TEMPLATE = (
    "Does `candidates[{index}]` represent the same underlying literary "
    "work as the target described by `title`, `author`, and `year`? "
    "Judge identity of the work, not merely similarity of title or author. "
    "Return false for a different work, an adaptation, an unrelated "
    "scholarly article, or an edition/translation item that is not itself "
    "the target work-level item."
)

SAME_WORK_CRITERIA = {
    "true": (
        "The candidate represents the same underlying literary work "
        "as the target."
    ),
    "false": (
        "The candidate does not represent the same underlying literary "
        "work as the target."
    ),
}

ANY_MATCH_INSTRUCTIONS = (
    "Does at least one item in `candidates` represent the same underlying "
    "literary work as the target described by `title`, `author`, and `year`? "
    "A mere title similarity, author-name collision, adaptation, unrelated "
    "work, or edition/translation item that is not the target work-level "
    "item does not count."
)

ANY_MATCH_CRITERIA = {
    "true": (
        "At least one supplied candidate represents the target literary work."
    ),
    "false": (
        "None of the supplied candidates represents the target literary work."
    ),
}

BEST_CANDIDATE_INSTRUCTIONS = (
    "Which supplied candidate is the best match for the target literary work "
    "described by `title`, `author`, and `year`? Compare the candidates "
    "relative to one another. Prefer the candidate representing the same "
    "underlying literary work, not an adaptation, unrelated work, scholarly "
    "article, or edition/translation item that is not the work-level item."
)


def canonical_json(obj):
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def append_jsonl(path, obj):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


# --------------------------------------------------
# Freeze question specification
# --------------------------------------------------

question_spec = {
    "same_work_template": SAME_WORK_TEMPLATE,
    "same_work_criteria": SAME_WORK_CRITERIA,
    "any_match_instructions": ANY_MATCH_INSTRUCTIONS,
    "any_match_criteria": ANY_MATCH_CRITERIA,
    "best_candidate_instructions": BEST_CANDIDATE_INSTRUCTIONS,
}

question_spec_sha = hashlib.sha256(
    canonical_json(question_spec).encode("utf-8")
).hexdigest()

if question_spec_sha != EXPECTED_QUESTION_SPEC_SHA256:
    raise RuntimeError(
        "Question specification changed!\n"
        f"expected: {EXPECTED_QUESTION_SPEC_SHA256}\n"
        f"actual:   {question_spec_sha}"
    )


# --------------------------------------------------
# Exact GPT-v6 compact representation
# --------------------------------------------------

GPT_RUNNER = Path("scripts/run_wikidata_v6_judge.py")

spec = importlib.util.spec_from_file_location(
    "gptjudge",
    GPT_RUNNER,
)
gptjudge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gptjudge)


# --------------------------------------------------
# Load ONLY packets -- never human gold / GPT answers
# --------------------------------------------------

packets = []

with PACKETS.open(encoding="utf-8") as f:
    for line in f:
        if line.strip():
            packets.append(json.loads(line))

if len(packets) != 100:
    raise RuntimeError(f"expected 100 packets, got {len(packets)}")

target_ids = [x["target_id"] for x in packets]

if len(set(target_ids)) != 100:
    raise RuntimeError("duplicate target IDs")


# --------------------------------------------------
# Manifest before predictions
# --------------------------------------------------

manifest = {
    "experiment": "wikidata_jev_holdout_v1",
    "purpose": (
        "Prediction-blind Jev run on frozen Wikidata v6 holdout packets. "
        "Human gold and GPT-v6 holdout judgments are not read by this runner."
    ),
    "model": MODEL,
    "question_spec_sha256": question_spec_sha,
    "packets_path": str(PACKETS),
    "packets_sha256": sha256_file(PACKETS),
    "compact_packet_source": str(GPT_RUNNER),
    "compact_packet_source_sha256": sha256_file(GPT_RUNNER),
    "human_gold_accessed_by_runner": False,
    "gpt_holdout_judgments_accessed_by_runner": False,
    "zero_candidate_policy": (
        "No Jev API call. Record deterministic retrieval-stage NO_MATCH-like "
        "outcome without asserting absence of a Wikidata work item."
    ),
    "total_packets": len(packets),
    "candidate_positive_packets": sum(
        bool(x.get("candidates")) for x in packets
    ),
    "zero_candidate_packets": sum(
        not bool(x.get("candidates")) for x in packets
    ),
}

OUT.mkdir(parents=True, exist_ok=True)

MANIFEST.write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)


# --------------------------------------------------
# Resume support
# --------------------------------------------------

completed = set()

if RESULTS.exists():
    with RESULTS.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                x = json.loads(line)
                completed.add(x["target_id"])


if not os.environ.get("TYPESAFE_API_KEY"):
    raise RuntimeError("TYPESAFE_API_KEY is not set")

client = TypeSafeClient(model=MODEL)


print("model:", MODEL)
print("question_spec_sha256:", question_spec_sha)
print("packets:", len(packets))
print(
    "candidate>0:",
    sum(bool(x.get("candidates")) for x in packets),
)
print(
    "candidate=0:",
    sum(not bool(x.get("candidates")) for x in packets),
)
print("already completed:", len(completed))
print()


for pos, packet in enumerate(packets, start=1):
    tid = packet["target_id"]

    if tid in completed:
        print(f"[{pos:03d}/100] {tid} SKIP")
        continue

    state = gptjudge.compact_packet(packet)

    state_serialized = canonical_json(state)
    state_sha = hashlib.sha256(
        state_serialized.encode("utf-8")
    ).hexdigest()

    candidates = state.get("candidates", [])

    # ----------------------------------------------
    # Zero candidate: no model call
    # ----------------------------------------------
    if not candidates:
        result = {
            "experiment": "wikidata_jev_holdout_v1",
            "target_id": tid,
            "target": {
                "title": packet["title"],
                "author": packet["author"],
                "year": packet["year"],
            },
            "candidate_count": 0,
            "prediction_source": "deterministic_no_candidate",
            "requested_model": None,
            "served_model": None,
            "compact_state_sha256": state_sha,
            "question_spec_sha256": question_spec_sha,
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
            },
            "latency_ms": 0.0,
            "candidate_nouls": [],
            "any_candidate_match": None,
            "best_candidate_choice": None,
        }

        append_jsonl(RESULTS, result)

        print(
            f"[{pos:03d}/100] {tid} "
            "candidate=0 -> deterministic retrieval-stage"
        )
        continue

    # ----------------------------------------------
    # Jev questions
    # ----------------------------------------------
    questions = {}

    for i, candidate in enumerate(candidates):
        questions[f"candidate_{i}"] = Noul(
            instructions=SAME_WORK_TEMPLATE.format(index=i),
            criteria=SAME_WORK_CRITERIA,
        )

    questions["any_candidate_match"] = Noul(
        instructions=ANY_MATCH_INSTRUCTIONS,
        criteria=ANY_MATCH_CRITERIA,
    )

    choice_criteria = {
        candidate["qid"]: (
            f"The candidate represented by `candidates[{i}]`."
        )
        for i, candidate in enumerate(candidates)
    }

    questions["best_candidate"] = Choice(
        instructions=BEST_CANDIDATE_INSTRUCTIONS,
        criteria=choice_criteria,
    )

    print(
        f"[{pos:03d}/100] {tid} "
        f"{packet['title']} | candidates={len(candidates)}"
    )

    response = None
    last_error = None
    latency_ms = None

    for attempt in range(1, 4):
        try:
            started = time.perf_counter()

            response = client.system_one(
                state=state,
                questions=questions,
            )

            latency_ms = (
                time.perf_counter() - started
            ) * 1000.0

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
        append_jsonl(
            FAILURES,
            {
                "target_id": tid,
                "requested_model": MODEL,
                "error_type": type(last_error).__name__,
                "error": str(last_error),
            },
        )

        print("    FAILED; recorded and continuing")
        continue

    candidate_results = []

    for i, candidate in enumerate(candidates):
        answer = response.answers[f"candidate_{i}"]

        candidate_results.append({
            "candidate_index": i,
            "qid": candidate["qid"],
            "label": candidate.get("label", ""),
            "same_work_probability": float(answer.noul),
        })

    ranked_noul = sorted(
        candidate_results,
        key=lambda x: x["same_work_probability"],
        reverse=True,
    )

    any_answer = response.answers["any_candidate_match"]
    choice_answer = response.answers["best_candidate"]

    choice_probabilities = {
        str(k): float(v)
        for k, v in choice_answer.probabilities.items()
    }

    ranked_choice = sorted(
        choice_probabilities.items(),
        key=lambda kv: kv[1],
        reverse=True,
    )

    result = {
        "experiment": "wikidata_jev_holdout_v1",
        "target_id": tid,
        "target": {
            "title": packet["title"],
            "author": packet["author"],
            "year": packet["year"],
        },
        "candidate_count": len(candidates),
        "prediction_source": "jev",
        "requested_model": MODEL,
        "served_model": response.model,
        "input_representation": "GPT-v6 compact_packet()",
        "compact_state_sha256": state_sha,
        "compact_state_chars": len(state_serialized),
        "question_spec_sha256": question_spec_sha,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
        "latency_ms": latency_ms,
        "candidate_nouls": candidate_results,
        "any_candidate_match": {
            "probability": float(any_answer.noul),
        },
        "best_candidate_choice": {
            "choice": choice_answer.choice,
            "confidence": float(choice_answer.confidence),
            "probabilities": choice_probabilities,
        },
        "noul_top_candidate": (
            ranked_noul[0] if ranked_noul else None
        ),
        "noul_second_candidate": (
            ranked_noul[1]
            if len(ranked_noul) > 1
            else None
        ),
        "choice_top_candidate": (
            {
                "qid": ranked_choice[0][0],
                "probability": ranked_choice[0][1],
            }
            if ranked_choice
            else None
        ),
    }

    append_jsonl(RESULTS, result)

    print(
        "    any_match:",
        f'{float(any_answer.noul):.3f}',
        "| Noul top:",
        ranked_noul[0]["qid"],
        f'{ranked_noul[0]["same_work_probability"]:.3f}',
        "| Choice:",
        choice_answer.choice,
        f'{float(choice_answer.confidence):.3f}',
        "| latency:",
        f"{latency_ms:.0f}ms",
    )


print()
print("RESULTS:", RESULTS)
print("FAILURES:", FAILURES if FAILURES.exists() else "none")
print("MANIFEST:", MANIFEST)
