# OpenAlex R2+A1 Baseline Human Audit Design v1

Status: ACTIVE
Date: 2026-10-11

## Purpose

Evaluate the reliability of large-scale LLM target-attribution
adjudication for the frozen R2+A1 PRIMARY 800-pair validation sample.

This human audit implements the active strategy defined in:

    OPENALEX_R2A1_BASELINE_VALIDATION_STRATEGY_V2.md

It replaces the earlier plan to manually adjudicate all 800 PRIMARY
candidates.

## Population

The audit population is the frozen PRIMARY random sample of 800
R2+A1 candidate pairs.

Frozen provisional LLM first-pass distribution:

- VALID_TARGET_REFERENCE: 474
- INVALID_TARGET_REFERENCE: 265
- UNCERTAIN: 61

The SECONDARY diagnostic sample is not part of this human audit.

## Stratified human-audit sample

Draw:

- 60 candidates from LLM VALID_TARGET_REFERENCE
- 60 candidates from LLM INVALID_TARGET_REFERENCE
- 30 candidates from LLM UNCERTAIN

Total human-audit sample:

    150 candidates

Selection within each LLM judgment stratum is deterministic using a
predefined SHA256 hash ordering over candidate IDs.

No human judgments are used in sample selection.

## Human-review blinding

The reviewer must NOT be shown:

- the candidate-level LLM judgment;
- LLM reason code;
- LLM confidence;
- LLM note;
- the LLM stratum from which the candidate was sampled;
- retrieval hit location;
- title-token features;
- candidate-volume features;
- other retrieval-risk features.

The reviewer sees only the frozen target identity and OpenAlex
title/abstract/publication context.

Human adjudication follows:

    OPENALEX_R2A1_BASELINE_HUMAN_ADJUDICATION_GUIDE_V1.md

except that only the 150-candidate audit sample is reviewed, as
specified by Validation Strategy v2.

## Interpretation

Because LLM judgment strata are deliberately sampled at unequal rates,
the 150 rows must NOT be pooled unweighted to estimate properties of
the PRIMARY 800.

Within-stratum human audit rates may be calculated directly.

Population-level estimates for the PRIMARY 800 must restore the frozen
stratum proportions:

    474 / 800
    265 / 800
     61 / 800

For any human outcome Y:

    P_hat(Y)
      = sum_h [ N_h / 800 * P_hat(Y | LLM stratum h) ]

where h is one of VALID, INVALID, or UNCERTAIN.

Important quantities include:

- human-confirmed precision of the LLM VALID stratum;
- human-confirmed invalidity rate of the LLM INVALID stratum;
- human outcome distribution within the LLM UNCERTAIN stratum;
- weighted overall human VALID / INVALID / UNCERTAIN prevalence;
- weighted LLM-human agreement.

The human audit is an audit of scalable LLM adjudication, not a
replacement for it.

No final production policy may be tuned from human outcomes before this
audit sample membership is frozen.
