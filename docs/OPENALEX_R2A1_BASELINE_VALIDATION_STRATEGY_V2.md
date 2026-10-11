# OpenAlex R2+A1 Baseline Validation Strategy v2

Status: ACTIVE

Date: 2026-10-11

## Supersession

This document supersedes the validation strategy described in:

- `OPENALEX_R2A1_BASELINE_HUMAN_ADJUDICATION_GUIDE_V1.md`

with respect to the planned extent and statistical role of human
adjudication.

The v1 guide proposed complete human adjudication of all 800 candidates
in the frozen PRIMARY validation sample.

That plan was NOT executed.

The frozen human-review packet remains a valid judgment-free blind
representation of the PRIMARY 800 sample, but complete human review of
all 800 candidates is no longer planned.

No authoritative human judgments had been created under that plan when
this strategy was adopted.

## Rationale

The broader project methodology uses LLM-based semantic adjudication for
large candidate populations, with human review used to estimate,
diagnose, and audit LLM performance rather than to replace large-scale
LLM adjudication with exhaustive manual classification.

Requiring complete manual adjudication of the PRIMARY 800 sample would
therefore be inconsistent with the intended production methodology and
would not scale to the full R2+A1 candidate universe.

## Active validation design

The frozen PRIMARY 800-pair probability sample remains unchanged.

The frozen SECONDARY 348-work diagnostic sample also remains unchanged.

The already-frozen blind LLM first pass over the combined 1,147 unique
candidates remains valid provisional adjudication evidence.

For the PRIMARY 800 sample:

1. LLM target-attribution adjudication is the scalable classification
   method under evaluation.

2. A smaller blind human audit sample will be drawn from the frozen
   PRIMARY 800.

3. Human reviewers will not be shown candidate-level LLM judgments,
   confidence, reason codes, retrieval-risk variables, or sampling
   stratum during adjudication.

4. The human audit will be used to estimate LLM performance and diagnose
   error patterns.

5. If the human audit indicates materially different error rates across
   LLM judgment strata or retrieval-risk strata, those differences may
   inform a subsequently frozen production adjudication policy.

6. The human audit sample and analysis procedure must be frozen before
   its human judgments are produced.

## Statistical interpretation

The following quantities must remain distinct:

- the raw distribution of LLM judgments in the PRIMARY 800;
- human-audited accuracy within LLM judgment strata;
- any weighted estimate of LLM classification performance;
- retrieval precision after application of a final production
  adjudication policy.

The 1,147-row combined PRIMARY + SECONDARY LLM first-pass distribution
must not be reported as overall R2+A1 precision.

The SECONDARY diagnostic sample must not be pooled unweighted with the
PRIMARY probability sample for pair-level population inference.

## Status of prior artifacts

The following remain active and valid:

- frozen R2+A1 baseline candidate universe;
- PRIMARY 800 and SECONDARY 348 sampling memberships;
- blind validation input;
- frozen LLM first-pass prompt/protocol;
- frozen LLM first-pass results.

The v1 800-row blank human-review packet is retained for provenance and
as a blind source from which a smaller human-audit sample may be drawn.

Its blank judgment fields do not constitute an incomplete or partially
executed human adjudication.

The requirement in the v1 human-adjudication guide to complete all 800
human judgments is superseded by this v2 strategy.
