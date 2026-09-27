from pathlib import Path
from collections import Counter
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

PACKETS = (
    ROOT
    / "derived/identity/aggregation_llm_review_input_v1.jsonl"
)

RESULTS = (
    ROOT
    / "derived/identity/aggregation_llm_review_results_v1.jsonl"
)

ERRORS = (
    ROOT
    / "derived/identity/aggregation_llm_review_errors_v1.jsonl"
)

PROMPT = (
    ROOT
    / "prompts/aggregation_llm_review_v2.md"
)

OUT_TSV = (
    ROOT
    / "derived/identity/aggregation_llm_review_adjudication_v1.tsv"
)

OUT_PARQUET = (
    ROOT
    / "derived/identity/aggregation_llm_review_adjudication_v1.parquet"
)

OUT_MANIFEST = (
    ROOT
    / "derived/identity/aggregation_llm_review_adjudication_v1_manifest.json"
)

CREATED_AT = "2026-09-27"

SAFE_FLAGS = {
    "duplicate_record",
    "title_variant",
    "authorship_variant",
}

EXPECTED_UNITS = 1194
EXPECTED_CURRENT_GATE = 442
EXPECTED_FINAL_ACCEPT = 433
EXPECTED_FINAL_ACCEPT_TARGETS = 923
EXPECTED_HELD_UNITS = 761
EXPECTED_HELD_TARGETS = 2083


def sha256_file(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def load_jsonl(path):
    if not path.exists():
        return []

    with path.open(encoding="utf-8") as f:
        return [
            json.loads(line)
            for line in f
            if line.strip()
        ]


def strong_external_support(packet):
    ol_ids = {
        x["entity_id"]
        for x in packet["openlibrary_records"]
    }

    gr_ids = {
        x["entity_id"]
        for x in packet["external_entities"]
        if x["source"] == "goodreads"
    }

    wd_ids = {
        x["entity_id"]
        for x in packet["external_entities"]
        if x["source"] == "wikidata"
    }

    assertions = packet["identity_assertions"]

    strong_gr = False

    if len(gr_ids) == 1:
        gr_id = next(iter(gr_ids))

        gr_rows = [
            x
            for x in assertions
            if (
                x["left_entity_id"] in ol_ids
                and x["right_entity_id"] == gr_id
                and x["identity_decision"] == "SAME"
            )
        ]

        covered = {
            x["left_entity_id"]
            for x in gr_rows
        }

        gr_ok = True

        for x in gr_rows:
            ev = x.get("evidence", {})

            if ev.get(
                "resolution_status_detail"
            ) not in {
                "AUTO_MATCH_HIGH",
                "AUTO_MATCH_IDENTITY_EVIDENCE",
            }:
                gr_ok = False

            if str(
                ev.get("review_needed", "")
            ) != "0":
                gr_ok = False

            if ev.get(
                "title_match_type"
            ) not in {
                "WORK_FULL",
                "BOOK_FULL",
            }:
                gr_ok = False

        strong_gr = (
            covered == ol_ids
            and len(gr_rows) == len(ol_ids)
            and gr_ok
        )

    strong_wd = False

    if len(wd_ids) == 1:
        wd_id = next(iter(wd_ids))

        wd_rows = [
            x
            for x in assertions
            if (
                x["left_entity_id"] in ol_ids
                and x["right_entity_id"] == wd_id
                and x["identity_decision"] == "SAME"
            )
        ]

        covered = {
            x["left_entity_id"]
            for x in wd_rows
        }

        strong_wd = (
            covered == ol_ids
            and len(wd_rows) == len(ol_ids)
            and all(
                x.get("confidence") == "high"
                for x in wd_rows
            )
        )

    return strong_gr, strong_wd


def main():
    for p in [
        PACKETS,
        RESULTS,
        ERRORS,
        PROMPT,
    ]:
        if not p.exists():
            raise FileNotFoundError(p)

    packet_rows = load_jsonl(PACKETS)

    packets = {
        x["unit_anchor_entity_id"]: x
        for x in packet_rows
    }

    raw_results = [
        x
        for x in load_jsonl(RESULTS)
        if x.get("status") == "ok"
    ]

    # Latest successful result wins if a rerun ever
    # produced more than one success for one anchor.
    results = {
        x["unit_anchor_entity_id"]: x
        for x in raw_results
    }

    errors = load_jsonl(ERRORS)

    assert len(packets) == EXPECTED_UNITS
    assert len(results) == EXPECTED_UNITS
    assert set(packets) == set(results)

    historical_error_anchors = {
        x["unit_anchor_entity_id"]
        for x in errors
    }

    assert not (
        historical_error_anchors
        - set(results)
    )

    rows = []

    for anchor in sorted(packets):
        packet = packets[anchor]
        result = results[anchor]
        review = result["review"]

        strong_gr, strong_wd = (
            strong_external_support(packet)
        )

        strict_blockers = []

        flags = set(
            review["relation_flags"]
        )

        if "duplicate_record" not in flags:
            strict_blockers.append(
                "missing_duplicate_record_flag"
            )

        if not flags.issubset(SAFE_FLAGS):
            strict_blockers.append(
                "non_safe_relation_flag"
            )

        if (
            packet["structural_class"]
            != "multi_ol_no_explicit_split"
        ):
            strict_blockers.append(
                "not_multi_ol_no_explicit_split"
            )

        if not (strong_gr or strong_wd):
            strict_blockers.append(
                "no_strong_common_external_support"
            )

        current_gate = bool(
            result.get(
                "auto_accept_eligible",
                False,
            )
        )

        final_accept = (
            current_gate
            and not strict_blockers
        )

        runner_blockers = result.get(
            "auto_accept_blockers",
            [],
        )

        if final_accept:
            disposition = (
                "AUTO_ACCEPT_ONE_WORK"
            )
        else:
            disposition = (
                "HOLD_FOR_LATER_REVIEW"
            )

        rows.append(
            {
                "unit_anchor_entity_id": anchor,
                "structural_class": (
                    packet["structural_class"]
                ),
                "current_target_count": int(
                    packet["current_target_count"]
                ),
                "metadata_pattern": (
                    packet["metadata_profile"][
                        "pattern"
                    ]
                ),
                "llm_decision": (
                    review["decision"]
                ),
                "llm_confidence": (
                    review["confidence"]
                ),
                "llm_needs_human_review": (
                    review[
                        "needs_human_review"
                    ]
                ),
                "llm_relation_flags_json": (
                    json.dumps(
                        review[
                            "relation_flags"
                        ],
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                ),
                "llm_clusters_json": (
                    json.dumps(
                        review["clusters"],
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                ),
                "llm_evidence_summary": (
                    review[
                        "evidence_summary"
                    ]
                ),
                "runner_auto_accept_eligible": (
                    current_gate
                ),
                "runner_blockers_json": (
                    json.dumps(
                        runner_blockers,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                ),
                "first_publish_year_spread": (
                    result.get(
                        "first_publish_year_spread",
                        "",
                    )
                ),
                "strong_goodreads_support": (
                    strong_gr
                ),
                "strong_wikidata_support": (
                    strong_wd
                ),
                "strict_gate_blockers_json": (
                    json.dumps(
                        strict_blockers,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                ),
                "final_auto_accept_eligible": (
                    final_accept
                ),
                "final_disposition": (
                    disposition
                ),
                "model_requested": (
                    result.get(
                        "model_requested",
                        "",
                    )
                ),
                "model_returned": (
                    result.get(
                        "model_returned",
                        "",
                    )
                ),
                "reasoning_effort": (
                    result.get(
                        "reasoning_effort",
                        "",
                    )
                ),
                "response_id": (
                    result.get(
                        "response_id",
                        "",
                    )
                ),
                "historical_error_logged": (
                    anchor
                    in historical_error_anchors
                ),
                "created_at": CREATED_AT,
            }
        )

    out = pd.DataFrame(rows)

    assert len(out) == EXPECTED_UNITS
    assert out[
        "unit_anchor_entity_id"
    ].is_unique

    assert int(
        out[
            "runner_auto_accept_eligible"
        ].sum()
    ) == EXPECTED_CURRENT_GATE

    accepted = out[
        out[
            "final_auto_accept_eligible"
        ]
    ]

    held = out[
        ~out[
            "final_auto_accept_eligible"
        ]
    ]

    assert len(accepted) == EXPECTED_FINAL_ACCEPT
    assert int(
        accepted[
            "current_target_count"
        ].sum()
    ) == EXPECTED_FINAL_ACCEPT_TARGETS

    assert len(held) == EXPECTED_HELD_UNITS
    assert int(
        held[
            "current_target_count"
        ].sum()
    ) == EXPECTED_HELD_TARGETS

    assert set(
        accepted["llm_decision"]
    ) == {"ONE_WORK"}

    assert set(
        accepted["llm_confidence"]
    ) == {"high"}

    assert not accepted[
        "llm_needs_human_review"
    ].any()

    assert set(
        accepted["structural_class"]
    ) == {
        "multi_ol_no_explicit_split"
    }

    assert (
        accepted[
            "strong_goodreads_support"
        ]
        | accepted[
            "strong_wikidata_support"
        ]
    ).all()

    tmp = OUT_TSV.with_name(
        OUT_TSV.name + ".tmp"
    )

    out.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    os.replace(tmp, OUT_TSV)

    tmp = OUT_PARQUET.with_name(
        OUT_PARQUET.name + ".tmp"
    )

    out.to_parquet(
        tmp,
        index=False,
        engine="pyarrow",
    )

    os.replace(tmp, OUT_PARQUET)

    manifest = {
        "release": (
            "aggregation-llm-review-adjudication-v1"
        ),
        "created_at": CREATED_AT,
        "semantics": {
            "purpose": (
                "Freeze the complete 1,194-unit LLM "
                "review and the deterministic safety "
                "gates used to select units eligible "
                "for automatic ONE_WORK aggregation."
            ),
            "llm_results_are_not_project_decisions": True,
            "final_auto_accept_rule": (
                "Runner auto-accept must pass, "
                "relation flags must be limited to "
                "duplicate_record/title_variant/"
                "authorship_variant and include "
                "duplicate_record, the unit must be "
                "multi_ol_no_explicit_split, and all "
                "OL targets must share at least one "
                "strong directly asserted Goodreads "
                "or Wikidata identity."
            ),
            "held_units": (
                "Units not passing the final gate "
                "remain unresolved for the current "
                "OL/Goodreads/Wikidata stage and are "
                "not automatically split or merged."
            ),
        },
        "inputs": {
            "review_packets": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_llm_review_input_v1.jsonl"
                ),
                "sha256": sha256_file(PACKETS),
            },
            "raw_results": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_llm_review_results_v1.jsonl"
                ),
                "sha256": sha256_file(RESULTS),
            },
            "historical_errors": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_llm_review_errors_v1.jsonl"
                ),
                "sha256": sha256_file(ERRORS),
                "note": (
                    "The logged quota error was later "
                    "resolved by a successful rerun."
                ),
            },
            "prompt": {
                "artifact": (
                    "prompts/"
                    "aggregation_llm_review_v2.md"
                ),
                "sha256": sha256_file(PROMPT),
            },
        },
        "counts": {
            "review_units": EXPECTED_UNITS,
            "runner_auto_accept": (
                EXPECTED_CURRENT_GATE
            ),
            "final_auto_accept_units": (
                EXPECTED_FINAL_ACCEPT
            ),
            "final_auto_accept_current_targets": (
                EXPECTED_FINAL_ACCEPT_TARGETS
            ),
            "held_units": EXPECTED_HELD_UNITS,
            "held_current_targets": (
                EXPECTED_HELD_TARGETS
            ),
            "historical_error_rows": len(errors),
            "unresolved_error_anchors": 0,
        },
        "llm_decisions": dict(
            Counter(
                out["llm_decision"]
            )
        ),
        "llm_confidence": dict(
            Counter(
                out["llm_confidence"]
            )
        ),
        "accepted_metadata_patterns": dict(
            Counter(
                accepted[
                    "metadata_pattern"
                ]
            )
        ),
        "outputs": {
            "tsv": (
                "derived/identity/"
                "aggregation_llm_review_adjudication_v1.tsv"
            ),
            "parquet": (
                "derived/identity/"
                "aggregation_llm_review_adjudication_v1.parquet"
            ),
        },
    }

    manifest["outputs"]["tsv_sha256"] = (
        sha256_file(OUT_TSV)
    )

    manifest["outputs"]["parquet_sha256"] = (
        sha256_file(OUT_PARQUET)
    )

    tmp = OUT_MANIFEST.with_name(
        OUT_MANIFEST.name + ".tmp"
    )

    tmp.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    os.replace(tmp, OUT_MANIFEST)

    print("=== LLM REVIEW ADJUDICATION V1 ===")
    print("review units:", len(out))
    print(
        "runner auto-accept:",
        int(
            out[
                "runner_auto_accept_eligible"
            ].sum()
        ),
    )
    print(
        "final auto-accept units:",
        len(accepted),
    )
    print(
        "final auto-accept OL targets:",
        int(
            accepted[
                "current_target_count"
            ].sum()
        ),
    )
    print(
        "held units:",
        len(held),
    )
    print(
        "held OL targets:",
        int(
            held[
                "current_target_count"
            ].sum()
        ),
    )

    print("\n=== LLM DECISIONS ===")
    print(
        out[
            "llm_decision"
        ].value_counts().to_string()
    )

    print("\n=== ACCEPTED METADATA PATTERNS ===")
    print(
        accepted[
            "metadata_pattern"
        ].value_counts().to_string()
    )

    print("\n=== OUTPUT SHA256 ===")
    print("tsv:", sha256_file(OUT_TSV))
    print(
        "parquet:",
        sha256_file(OUT_PARQUET),
    )
    print(
        "manifest:",
        sha256_file(OUT_MANIFEST),
    )


if __name__ == "__main__":
    main()
