#!/usr/bin/env python3
"""Freeze a reproducible, LLM-label-blinded development queue for held OL units.

Run from the canon-pipeline worktree. Does not call APIs or alter releases.
The internal selection stores sampling strata separately from the review queue.
"""
import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path.cwd()
SOURCE = ROOT / "derived/identity/aggregation_llm_review_adjudication_v1.tsv"
OUT = ROOT / "derived/identity/aggregation_held_units_sampling_v1"
SEED = 20261018

# (development, evaluation), chosen to cover diverse error mechanisms.
QUOTA = {
    "ONE_SIMPLE_STRONG": (4, 4),
    "ONE_SIMPLE_WEAK": (2, 2),
    "ONE_COMPLEX_STRONG": (4, 4),
    "ONE_COMPLEX_WEAK": (2, 2),
    "UNRESOLVED": (5, 5),
    "MULTIPLE_WORKS": (3, 3),
}
SAFE_FLAGS = {"duplicate_record", "title_variant", "authorship_variant"}
EXCLUDED_EVALUATION_ANCHOR = "E000018716"
EXCLUSION_REASON = (
    "Prior discussion disclosed this unit's LLM decision and blockers "
    "before the evaluation sample was frozen."
)
REPLACEMENT_SALT = "aggregation-held-evaluation-replacement-v1-20261018"
REVIEW_ORDER_SALT = "aggregation-held-development-review-order-v1-20261018"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def hash_of(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def truth(s):
    return str(s).lower() in {"true", "1"}


def write_tsv(path, rows, cols):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main():
    if not SOURCE.is_file():
        raise SystemExit(f"Missing input; run from repo root: {SOURCE}")
    if OUT.exists():
        raise SystemExit(f"STOP: refusing to overwrite existing sample: {OUT}")

    with SOURCE.open(encoding="utf-8-sig", newline="") as f:
        all_rows = list(csv.DictReader(f, delimiter="\t"))
    assert len(all_rows) == 1194, len(all_rows)

    held = [r for r in all_rows if r["final_disposition"] == "HOLD_FOR_LATER_REVIEW"]
    assert len(held) == 761
    by_id = {r["unit_anchor_entity_id"]: r for r in held}
    assert len(by_id) == len(held)
    assert Counter(r["llm_decision"] for r in held) == {
        "ONE_WORK": 438, "UNRESOLVED": 304, "MULTIPLE_WORKS": 19
    }

    strata = defaultdict(list)
    for r in held:
        decision = r["llm_decision"]
        if decision == "ONE_WORK":
            flags = set(json.loads(r["llm_relation_flags_json"] or "[]"))
            simple = ("duplicate_record" in flags and flags <= SAFE_FLAGS
                      and r["structural_class"] == "multi_ol_no_explicit_split")
            strong = (truth(r["strong_goodreads_support"])
                      or truth(r["strong_wikidata_support"]))
            stratum = ("ONE_SIMPLE_" if simple else "ONE_COMPLEX_") + (
                "STRONG" if strong else "WEAK")
        elif decision in {"UNRESOLVED", "MULTIPLE_WORKS"}:
            stratum = decision
        else:
            raise AssertionError(decision)
        strata[stratum].append(r["unit_anchor_entity_id"])

    assert {k: len(v) for k, v in strata.items()} == {
        "ONE_SIMPLE_STRONG": 181, "ONE_SIMPLE_WEAK": 14,
        "ONE_COMPLEX_STRONG": 237, "ONE_COMPLEX_WEAK": 6,
        "UNRESOLVED": 304, "MULTIPLE_WORKS": 19,
    }

    rng = random.Random(SEED)
    dev, eval_ = [], []
    for stratum, (n_dev, n_eval) in QUOTA.items():
        selected = rng.sample(sorted(strata[stratum]), n_dev + n_eval)
        dev.extend((anchor, stratum) for anchor in selected[:n_dev])
        eval_.extend((anchor, stratum) for anchor in selected[n_dev:])

    # Reproduce the previously printed sample before any change.
    assert len(dev) == len(eval_) == 20
    assert len({a for a, _ in dev + eval_}) == 40
    assert EXCLUDED_EVALUATION_ANCHOR not in {a for a, _ in dev}
    assert (EXCLUDED_EVALUATION_ANCHOR, "UNRESOLVED") in eval_

    # One predeclared, documented replacement from the SAME stratum.
    original = {a for a, _ in dev + eval_}
    candidates = set(strata["UNRESOLVED"]) - original
    replacement = min(
        candidates,
        key=lambda x: (hash_of(REPLACEMENT_SALT + "\0" + x), x),
    )
    eval_ = [(replacement if a == EXCLUDED_EVALUATION_ANCHOR else a, s)
             for a, s in eval_]

    assert len(dev) == len(eval_) == 20
    assert len({a for a, _ in dev + eval_}) == 40
    assert replacement not in original
    assert (replacement, "UNRESOLVED") in eval_

    internal = []
    for role, selected in [("DEVELOPMENT", dev), ("HELD_OUT_EVALUATION", eval_)]:
        for anchor, stratum in selected:
            internal.append({
                "role": role,
                "unit_anchor_entity_id": anchor,
                "sampling_stratum": stratum,
                "stratum_population_n": len(strata[stratum]),
                "stratum_draw_n": sum(QUOTA[stratum]),
                "prior_llm_decision": by_id[anchor]["llm_decision"],
            })

    internal.sort(key=lambda r: (r["role"], r["unit_anchor_entity_id"]))

    # Only this queue should be used to develop review guidelines or packets;
    # it deliberately contains no previous model verdict or sampling stratum.
    ordered_dev = sorted(
        [a for a, _ in dev],
        key=lambda a: (hash_of(REVIEW_ORDER_SALT + "\0" + a), a),
    )
    queue = [
        {"review_order": i, "unit_anchor_entity_id": a}
        for i, a in enumerate(ordered_dev, 1)
    ]

    OUT.mkdir(parents=True, exist_ok=False)
    private_name = "sampling_selection_internal_v1.tsv"
    queue_name = "development_review_queue_v1.tsv"
    write_tsv(OUT / private_name, internal, [
        "role", "unit_anchor_entity_id", "sampling_stratum",
        "stratum_population_n", "stratum_draw_n", "prior_llm_decision",
    ])
    write_tsv(OUT / queue_name, queue, [
        "review_order", "unit_anchor_entity_id",
    ])

    manifest = {
        "release": "aggregation-held-units-sampling-v1",
        "status": "SAMPLE_FROZEN_REVIEW_NOT_STARTED",
        "input": {"path": str(SOURCE.relative_to(ROOT)), "sha256": sha(SOURCE)},
        "algorithm": "Python random.Random(seed).sample(sorted(stratum_ids), quota)",
        "seed": SEED,
        "stratum_population_counts": {k: len(strata[k]) for k in QUOTA},
        "per_split_quota": {k: {"development": x, "evaluation": y}
                            for k, (x, y) in QUOTA.items()},
        "known_prior_exposure_exclusion": {
            "excluded_anchor": EXCLUDED_EVALUATION_ANCHOR,
            "reason": EXCLUSION_REASON,
            "replacement_anchor": replacement,
            "replacement_method": "minimum SHA256(salt + null + anchor) among unselected UNRESOLVED units",
            "replacement_salt": REPLACEMENT_SALT,
        },
        "review_order_salt": REVIEW_ORDER_SALT,
        "counts": {"held_population_units": 761,
                   "development_units": 20, "evaluation_units": 20},
        "protocol": {
            "selection_internal_contains_prior_llm_labels": True,
            "development_queue_contains_prior_llm_labels": False,
            "evaluation_evidence_not_opened": True,
            "sampling_is_disproportionate": True,
            "unweighted_sample_is_not_population_accuracy_estimate": True,
            "no_project_work_or_identity_decisions_created": True,
        },
        "outputs": {
            private_name: sha(OUT / private_name),
            queue_name: sha(OUT / queue_name),
        },
    }
    (OUT / "manifest_v1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("=== HELD-UNIT SAMPLE V1 ===")
    print("Input review units:", len(held))
    print("Development:", len(dev), "Held-out:", len(eval_))
    print("Prior-exposed evaluation unit:", EXCLUDED_EVALUATION_ANCHOR)
    print("Deterministic same-stratum replacement:", replacement)
    print("Output:", OUT)
    print("Files:", private_name, queue_name, "manifest_v1.json")
    print("Existing source and W releases unchanged; no API calls.")


if __name__ == "__main__":
    main()
