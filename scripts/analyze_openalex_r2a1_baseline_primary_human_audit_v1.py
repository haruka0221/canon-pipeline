#!/usr/bin/env python3

from pathlib import Path
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
import os

ROOT = Path(__file__).resolve().parents[1]

SAMPLE = (
    ROOT / "derived/openalex_production"
    / "retrieval_r2a1_baseline_primary_human_audit_sample_v1"
    / "openalex_r2a1_baseline_primary_human_audit_sample_v1.tsv"
)

HUMAN = (
    ROOT / "derived/openalex_production"
    / "retrieval_r2a1_baseline_primary_human_adjudication_v1"
    / "openalex_r2a1_baseline_primary_human_adjudication_v1.tsv"
)

OUT_DIR = (
    ROOT / "derived/openalex_production"
    / "retrieval_r2a1_baseline_primary_human_audit_analysis_v1"
)

JOINED = OUT_DIR / "openalex_r2a1_baseline_primary_human_audit_join_v1.tsv"
SUMMARY = OUT_DIR / "openalex_r2a1_baseline_primary_human_audit_analysis_summary_v1.json"
AUDIT = OUT_DIR / "openalex_r2a1_baseline_primary_human_audit_analysis_v1_audit.json"
MANIFEST = OUT_DIR / "openalex_r2a1_baseline_primary_human_audit_analysis_v1_manifest.json"

LABELS = [
    "VALID_TARGET_REFERENCE",
    "INVALID_TARGET_REFERENCE",
    "UNCERTAIN",
]

PRIMARY_N = 800

EXPECTED = {
    "VALID_TARGET_REFERENCE": (474, 60),
    "INVALID_TARGET_REFERENCE": (265, 60),
    "UNCERTAIN": (61, 30),
}

Z95 = 1.959963984540054


def read_tsv(path):
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(obj, path):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def design_estimate(contingency, outcome):
    estimate = 0.0
    variance = 0.0

    for stratum in LABELS:
        N_h, n_h = EXPECTED[stratum]
        x_h = contingency[stratum][outcome]

        p_h = x_h / n_h
        W_h = N_h / PRIMARY_N

        estimate += W_h * p_h

        # SRSWOR design-based variance estimate.
        s2 = (
            p_h * (1 - p_h) * n_h / (n_h - 1)
            if n_h > 1 else 0.0
        )

        variance += (
            W_h ** 2
            * (1 - n_h / N_h)
            * s2 / n_h
        )

    se = math.sqrt(variance)

    return {
        "estimate": estimate,
        "estimated_primary_count": estimate * PRIMARY_N,
        "standard_error_design_based": se,
        "ci95_lower_approx": max(0.0, estimate - Z95 * se),
        "ci95_upper_approx": min(1.0, estimate + Z95 * se),
    }


def main():
    sample = read_tsv(SAMPLE)
    human = read_tsv(HUMAN)

    assert len(sample) == 150
    assert len(human) == 150

    human_by_id = {
        r["baseline_candidate_id"]: r
        for r in human
    }

    sample_ids = {
        r["baseline_candidate_id"]
        for r in sample
    }
    human_ids = set(human_by_id)

    assert sample_ids == human_ids

    stratum_counts = Counter(
        r["llm_first_pass_judgment"]
        for r in sample
    )

    for label, (N_h, n_h) in EXPECTED.items():
        assert stratum_counts[label] == n_h

        observed_N = {
            int(r["stratum_population_n"])
            for r in sample
            if r["llm_first_pass_judgment"] == label
        }
        assert observed_N == {N_h}

    contingency = {
        llm: {human_label: 0 for human_label in LABELS}
        for llm in LABELS
    }

    joined = []

    for s in sample:
        cid = s["baseline_candidate_id"]
        h = human_by_id[cid]

        assert s["project_work_id"] == h["project_work_id"]
        assert s["openalex_work_id"] == h["openalex_work_id"]

        llm_label = s["llm_first_pass_judgment"]
        human_label = h["human_target_attribution_judgment"]

        contingency[llm_label][human_label] += 1

        joined.append({
            "baseline_candidate_id": cid,
            "project_work_id": s["project_work_id"],
            "openalex_work_id": s["openalex_work_id"],
            "llm_first_pass_judgment": llm_label,
            "human_target_attribution_judgment": human_label,
            "human_adjudication_confidence": h["human_adjudication_confidence"],
            "human_attribution_reason_code": h["human_attribution_reason_code"],
            "stratum_population_n": s["stratum_population_n"],
            "stratum_sample_n": s["stratum_sample_n"],
            "analysis_weight": s["analysis_weight"],
            "exact_agreement": str(llm_label == human_label).lower(),
        })

    raw_human = Counter(
        r["human_target_attribution_judgment"]
        for r in human
    )

    raw_exact_agreement_n = sum(
        contingency[x][x]
        for x in LABELS
    )

    weighted = {
        outcome: design_estimate(contingency, outcome)
        for outcome in LABELS
    }

    # Weighted exact agreement.
    agreement_contingency = {
        label: {
            "AGREE": contingency[label][label],
            "DISAGREE": EXPECTED[label][1] - contingency[label][label],
        }
        for label in LABELS
    }

    agreement_estimate = 0.0
    agreement_variance = 0.0

    for label in LABELS:
        N_h, n_h = EXPECTED[label]
        p_h = contingency[label][label] / n_h
        W_h = N_h / PRIMARY_N

        agreement_estimate += W_h * p_h

        s2 = p_h * (1 - p_h) * n_h / (n_h - 1)

        agreement_variance += (
            W_h ** 2
            * (1 - n_h / N_h)
            * s2 / n_h
        )

    agreement_se = math.sqrt(agreement_variance)

    summary = {
        "release": "openalex-r2a1-baseline-primary-human-audit-analysis-v1",
        "estimand": "Primary-800 pair-level target-attribution distribution",
        "primary_population_n": PRIMARY_N,
        "phase2_audit_n": 150,
        "strata": {
            label: {
                "primary_n": EXPECTED[label][0],
                "audit_n": EXPECTED[label][1],
                "human_counts": contingency[label],
            }
            for label in LABELS
        },
        "raw_human_counts_150": dict(raw_human),
        "raw_exact_agreement_n": raw_exact_agreement_n,
        "raw_exact_agreement_fraction": raw_exact_agreement_n / 150,
        "weighted_primary_estimates": weighted,
        "weighted_exact_agreement": {
            "estimate": agreement_estimate,
            "standard_error_design_based": agreement_se,
            "ci95_lower_approx": max(0.0, agreement_estimate - Z95 * agreement_se),
            "ci95_upper_approx": min(1.0, agreement_estimate + Z95 * agreement_se),
        },
        "ci_note": (
            "Approximate design-based normal 95% intervals with finite-population "
            "correction under stratified SRSWOR. A stratum with zero observed "
            "within-stratum variance contributes zero estimated variance; use a "
            "more conservative interval method for final publication reporting."
        ),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    fields = list(joined[0].keys())
    tmp = JOINED.with_name(JOINED.name + ".tmp")

    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=fields,
            delimiter="\t",
            lineterminator="\n",
        )
        w.writeheader()
        w.writerows(joined)

    os.replace(tmp, JOINED)

    write_json(summary, SUMMARY)

    audit = {
        "status": "PASSED",
        "checks": {
            "audit_rows_150": True,
            "human_rows_150": True,
            "candidate_membership_exact": True,
            "project_work_ids_match": True,
            "openalex_work_ids_match": True,
            "llm_valid_stratum_60": True,
            "llm_invalid_stratum_60": True,
            "llm_uncertain_stratum_30": True,
            "stratum_primary_sizes_match_474_265_61": True,
        },
    }
    write_json(audit, AUDIT)

    manifest = {
        "sources": {
            str(SAMPLE.relative_to(ROOT)): sha256(SAMPLE),
            str(HUMAN.relative_to(ROOT)): sha256(HUMAN),
        },
        "outputs": {
            str(JOINED.relative_to(ROOT)): sha256(JOINED),
            str(SUMMARY.relative_to(ROOT)): sha256(SUMMARY),
            str(AUDIT.relative_to(ROOT)): sha256(AUDIT),
        },
    }
    write_json(manifest, MANIFEST)

    print("=== R2+A1 HUMAN AUDIT ANALYSIS V1 ===")
    print("contingency:")
    for label in LABELS:
        print(" ", label, contingency[label])

    print()
    print("weighted Primary-800 estimates:")
    for label in LABELS:
        x = weighted[label]
        print(
            f"  {label}: "
            f"{x['estimate']:.6f} "
            f"(approx 95% CI "
            f"{x['ci95_lower_approx']:.6f}–"
            f"{x['ci95_upper_approx']:.6f})"
        )

    print()
    print(
        "weighted exact agreement:",
        f"{agreement_estimate:.6f}",
    )
    print("QC STATUS: PASSED")


if __name__ == "__main__":
    main()
