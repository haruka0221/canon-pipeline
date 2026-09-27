from pathlib import Path
from typing import Literal
import json
import time

from openai import OpenAI
from pydantic import BaseModel, ConfigDict


ROOT = Path(__file__).resolve().parents[1]

PROMPT = ROOT / "prompts/aggregation_llm_review_v2.md"

INPUT = (
    ROOT
    / "derived/identity/aggregation_llm_review_input_v1.jsonl"
)

OUT = (
    ROOT
    / "derived/identity/aggregation_llm_review_results_v1.jsonl"
)

ERRORS = (
    ROOT
    / "derived/identity/aggregation_llm_review_errors_v1.jsonl"
)

MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "medium"

RISKY_FLAGS = {
    "translation",
    "collection_or_omnibus",
    "part_whole",
    "series_or_volume",
    "adaptation",
    "revised_version",
    "external_source_overmerge",
    "external_source_conflict",
    "uncertain_relation",
}

AUTO_ACCEPT_YEAR_SPREAD = 10

Decision = Literal[
    "ONE_WORK",
    "MULTIPLE_WORKS",
    "UNRESOLVED",
]

Confidence = Literal[
    "high",
    "medium",
    "low",
]

RelationFlag = Literal[
    "duplicate_record",
    "title_variant",
    "authorship_variant",
    "collection_or_omnibus",
    "part_whole",
    "series_or_volume",
    "translation",
    "adaptation",
    "revised_version",
    "external_source_overmerge",
    "external_source_conflict",
    "uncertain_relation",
]


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_anchor_entity_id: str
    decision: Decision
    clusters: list[list[str]]
    relation_flags: list[RelationFlag]
    confidence: Confidence
    evidence_summary: str
    needs_human_review: bool


def load_jsonl(path):
    rows = []

    if not path.exists():
        return rows

    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    return rows


def append_jsonl(path, row):
    with path.open(
        "a",
        encoding="utf-8",
        newline="\n",
    ) as f:
        f.write(
            json.dumps(
                row,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )
        f.flush()


def validate_partition(packet, result):
    anchor = packet["unit_anchor_entity_id"]

    if result.unit_anchor_entity_id != anchor:
        raise ValueError(
            "anchor mismatch: "
            f"{result.unit_anchor_entity_id} != {anchor}"
        )

    expected = [
        r["entity_id"]
        for r in packet["openlibrary_records"]
    ]

    expected_set = set(expected)

    if any(len(cluster) == 0 for cluster in result.clusters):
        raise ValueError("empty cluster")

    flat = [
        entity_id
        for cluster in result.clusters
        for entity_id in cluster
    ]

    if len(flat) != len(set(flat)):
        raise ValueError(
            "an OL entity appears in more than one cluster"
        )

    if set(flat) != expected_set:
        missing = sorted(expected_set - set(flat))
        extra = sorted(set(flat) - expected_set)

        raise ValueError(
            f"partition mismatch; missing={missing}, extra={extra}"
        )

    if len(flat) != len(expected):
        raise ValueError(
            "partition does not contain each OL entity exactly once"
        )

    if result.decision == "ONE_WORK":
        if len(result.clusters) != 1:
            raise ValueError(
                "ONE_WORK must have exactly one cluster"
            )

        if set(result.clusters[0]) != expected_set:
            raise ValueError(
                "ONE_WORK cluster must contain every OL entity"
            )

    elif result.decision == "MULTIPLE_WORKS":
        if len(result.clusters) < 2:
            raise ValueError(
                "MULTIPLE_WORKS requires at least two clusters"
            )

    elif result.decision == "UNRESOLVED":
        if len(expected) > 1 and len(result.clusters) < 2:
            raise ValueError(
                "UNRESOLVED must preserve at least two "
                "possible conceptual-work groups"
            )

    if (
        not result.needs_human_review
        and result.confidence != "high"
    ):
        raise ValueError(
            "needs_human_review=false requires confidence=high"
        )


def auto_accept_gate(packet, result):
    blockers = []

    if result.decision != "ONE_WORK":
        blockers.append("decision_not_one_work")

    if result.confidence != "high":
        blockers.append("confidence_not_high")

    if result.needs_human_review:
        blockers.append("llm_requests_human_review")

    risky = sorted(
        set(result.relation_flags)
        & RISKY_FLAGS
    )

    if risky:
        blockers.append(
            "risky_flags:" + ",".join(risky)
        )

    if (
        packet["structural_class"]
        == "cross_source_conflict"
    ):
        blockers.append(
            "structural_cross_source_conflict"
        )

    years = []

    for r in packet["openlibrary_records"]:
        value = str(
            r.get("first_publish_year", "")
        ).strip()

        if value.isdigit():
            years.append(int(value))

    if len(years) >= 2:
        spread = max(years) - min(years)
    else:
        spread = None

    if (
        spread is not None
        and spread >= AUTO_ACCEPT_YEAR_SPREAD
    ):
        blockers.append(
            f"year_spread_ge_{AUTO_ACCEPT_YEAR_SPREAD}:"
            f"{spread}"
        )

    return {
        "auto_accept_eligible": (
            len(blockers) == 0
        ),
        "auto_accept_blockers": blockers,
        "first_publish_year_spread": spread,
    }


def main():
    assert PROMPT.exists()
    assert INPUT.exists()

    prompt = PROMPT.read_text(encoding="utf-8")
    packets = load_jsonl(INPUT)

    assert len(packets) == 1194

    existing = load_jsonl(OUT)

    done = {
        row["unit_anchor_entity_id"]
        for row in existing
        if row.get("status") == "ok"
    }

    client = OpenAI()

    print("=== FULL REVIEW RUN ===")
    print("model:", MODEL)
    print("reasoning:", REASONING_EFFORT)
    print("packets:", len(packets))
    print("already completed:", len(done))
    print()

    for i, packet in enumerate(packets, 1):
        anchor = packet["unit_anchor_entity_id"]

        if anchor in done:
            print(
                f"[{i:04d}/{len(packets)}] {anchor} SKIP already completed"
            )
            continue

        print(
            f"[{i:04d}/{len(packets)}] {anchor} "
            f"OL={packet['current_target_count']} ..."
        )

        last_error = None

        for attempt in range(1, 4):
            parsed = None

            try:
                response = client.responses.parse(
                    model=MODEL,
                    reasoning={
                        "effort": REASONING_EFFORT,
                    },
                    input=[
                        {
                            "role": "system",
                            "content": prompt,
                        },
                        {
                            "role": "user",
                            "content": (
                                "Review this packet. "
                                "Treat it as closed-book evidence. "
                                "Do not use outside knowledge.\n\n"
                                + json.dumps(
                                    packet,
                                    ensure_ascii=False,
                                    sort_keys=True,
                                )
                            ),
                        },
                    ],
                    text_format=ReviewDecision,
                    store=False,
                    max_output_tokens=4000,
                )

                parsed = response.output_parsed

                if parsed is None:
                    raise ValueError(
                        "response.output_parsed is None"
                    )

                validate_partition(
                    packet,
                    parsed,
                )

                gate = auto_accept_gate(
                    packet,
                    parsed,
                )

                result = {
                    "status": "ok",
                    "unit_anchor_entity_id": anchor,
                    "model_requested": MODEL,
                    "model_returned": getattr(
                        response,
                        "model",
                        "",
                    ),
                    "reasoning_effort": REASONING_EFFORT,
                    "response_id": response.id,
                    "review": parsed.model_dump(
                        mode="json"
                    ),
                    **gate,
                    "usage": (
                        response.usage.model_dump(
                            mode="json"
                        )
                        if response.usage
                        else {}
                    ),
                }

                append_jsonl(
                    OUT,
                    result,
                )

                done.add(anchor)

                print(
                    "   ->",
                    parsed.decision,
                    parsed.confidence,
                    "human_review="
                    + str(parsed.needs_human_review),
                )

                break

            except Exception as exc:
                last_error = exc

                print(
                    f"   attempt {attempt} failed:",
                    type(exc).__name__,
                    str(exc)[:300],
                )

                if attempt < 3:
                    time.sleep(2 ** attempt)

        else:
            error_row = {
                "status": "error",
                "unit_anchor_entity_id": anchor,
                "model_requested": MODEL,
                "reasoning_effort": REASONING_EFFORT,
                "error_type": type(
                    last_error
                ).__name__,
                "error": str(last_error),
            }

            if parsed is not None:
                error_row["parsed_output"] = (
                    parsed.model_dump(
                        mode="json"
                    )
                )

            append_jsonl(
                ERRORS,
                error_row,
            )

            print("   -> ERROR recorded")

    results = [
        row
        for row in load_jsonl(OUT)
        if row.get("status") == "ok"
    ]

    # Keep only one successful result per anchor.
    latest = {
        row["unit_anchor_entity_id"]: row
        for row in results
    }

    results = list(latest.values())

    print()
    print("=== FULL REVIEW SUMMARY ===")
    print("successful:", len(results))
    print(
        "errors:",
        len(load_jsonl(ERRORS)),
    )

    decision_counts = {}

    confidence_counts = {}

    human_counts = {}

    for row in results:
        review = row["review"]

        decision_counts[
            review["decision"]
        ] = (
            decision_counts.get(
                review["decision"],
                0,
            )
            + 1
        )

        confidence_counts[
            review["confidence"]
        ] = (
            confidence_counts.get(
                review["confidence"],
                0,
            )
            + 1
        )

        key = str(
            review["needs_human_review"]
        )

        human_counts[key] = (
            human_counts.get(key, 0)
            + 1
        )

    print("\ndecisions:")
    for k in sorted(decision_counts):
        print(" ", k, decision_counts[k])

    print("\nconfidence:")
    for k in sorted(confidence_counts):
        print(" ", k, confidence_counts[k])

    print("\nneeds_human_review:")
    for k in sorted(human_counts):
        print(" ", k, human_counts[k])

    eligible = sum(
        bool(row.get("auto_accept_eligible"))
        for row in results
    )

    print()
    print("auto_accept_eligible:", eligible)
    print(
        "not_auto_accept:",
        len(results) - eligible,
    )

    print()
    print("results:", OUT)
    print("errors:", ERRORS)


if __name__ == "__main__":
    main()
