# OpenAlex Marginal Retrieval Policy v1

## Status

Calibration-selected policy for the audited marginal OpenAlex retrieval routes.

This document freezes the routing rule selected from the calibration audit.
As of 2026-10-08, the `A2_AUTHOR_REVERSAL` rule has additionally been
evaluated on a calibration-external held-out validation sample without
threshold tuning or work-specific exceptions.

The `ALIAS_EXPANSION` rule remains supported by the finite-population audit
of the current release; same-release held-out validation is not available
for that route.

Neither route by itself establishes operational performance on the full
production retrieval population.

This policy applies only to:

- `ALIAS_EXPANSION`
- `A2_AUTHOR_REVERSAL`

It does **not** establish precision or acceptance policy for:

- the R2 baseline route,
- R4 title-only retrieval,
- recall,
- coverage,
- or the complete OpenAlex production pipeline.

The calibration evidence is descriptive of the frozen audited
65-work / 661-candidate marginal universe only.

## Frozen calibration basis

Authoritative calibration layers:

- `openalex_retrieval_precision_results_v1`
- `openalex_retrieval_by_work_error_analysis_v1`

Frozen by-work error-analysis baseline:

- commit: `fdb47b210733149eb507e51a4ae0f6b05d57cfeb`
- profile: `full_profile_57959e90`
- audited marginal candidates: 661
- audited works: 65

Human adjudication outcomes are used only to evaluate candidate rules.
Human judgment labels and human reason codes are not production-policy
inputs.

`UNCERTAIN` is not treated as `INVALID`.

## Allowed actions

The policy defines two routing actions for the audited marginal routes:

- `ACCEPT`
- `REVIEW`

There is no automatic `REJECT` action in v1.

A candidate sent to `REVIEW` is not classified as invalid.
It is only withheld from automatic acceptance pending review.

## Policy A: A2 author reversal

For `increment_type == A2_AUTHOR_REVERSAL`:

```text
REVIEW if:

    hit_location == ABSTRACT_ONLY

    AND

    (
        title_match_token_count_min == 1

        OR

        any_cross_w_title_collision == True
    )

otherwise:

    ACCEPT
```

Calibration result in the frozen audited universe:

- candidates: 252
- REVIEW: 17
- ACCEPT: 235

REVIEW outcomes:

- VALID: 7
- INVALID: 10
- UNCERTAIN: 0

ACCEPT outcomes:

- VALID: 234
- INVALID: 0
- UNCERTAIN: 1

The single accepted `UNCERTAIN` case is not recoded as invalid.

## Policy B: alias expansion

For `increment_type == ALIAS_EXPANSION`:

```text
REVIEW if:

    hit_location == ABSTRACT_ONLY

    AND

    title_match_token_count_min <= 4

otherwise:

    ACCEPT
```

Calibration result in the frozen audited universe:

- candidates: 409
- REVIEW: 217
- ACCEPT: 192

REVIEW outcomes:

- VALID: 182
- INVALID: 22
- UNCERTAIN: 13

ACCEPT outcomes:

- VALID: 182
- INVALID: 2
- UNCERTAIN: 8

Among the token thresholds from one through six examined in this
audit, four tokens is the smallest threshold at which the observed
audited INVALID capture reaches its maximum:

- <= 3 tokens: 16 / 24 INVALID, across 5 INVALID-bearing works
- <= 4 tokens: 22 / 24 INVALID, across 7 INVALID-bearing works
- <= 5 tokens: 22 / 24 INVALID, across 7 INVALID-bearing works
- <= 6 tokens: 22 / 24 INVALID, across 7 INVALID-bearing works

Therefore the move from four to five or six tokens adds review burden
without additional audited INVALID or UNCERTAIN capture.

## Residual alias errors

Two audited `INVALID_TARGET_REFERENCE` candidates remain automatically
accepted under the four-token policy.

Both belong to `Cavalleria rusticana`, are TITLE_ONLY matches, and were
adjudicated `TITLE_COLLISION_DIFFERENT_WORK`.

Their display names indicate operatic or musical material. This observation
is post-hoc descriptive evidence and is not converted into a generic
cross-media production rule.

The exploratory audit did not identify a sufficiently reliable generic
pre-adjudication feature for separating these cases.

In particular, OpenAlex `type` and `primary_topic_name` are not used as
policy inputs because they did not cleanly separate valid, invalid, and
uncertain cases in the frozen audit.

No work-specific exception is introduced.

## Feature semantics

### `hit_location`

Derived deterministically from:

- `any_title_match_in_title`
- `any_title_match_in_abstract`

Values include:

- `TITLE_ONLY`
- `ABSTRACT_ONLY`
- `TITLE_AND_ABSTRACT`

### `title_match_token_count_min`

For candidates supported by multiple title-match forms, use the minimum
token count across the deterministic set of matched normalized title forms.

No arbitrary representative query or alias may be selected.

### `any_cross_w_title_collision`

True when at least one supporting alias's frozen normalized title occurs
against more than one resolved project work in the frozen alias registry.

This is a corpus-level cross-project-work collision signal.

It is not equivalent to external adaptation or cross-media collision.

## Explicit exclusions

The following must not be used as automatic policy inputs in v1:

- human attribution judgment
- human attribution reason code
- human reviewer notes
- OpenAlex `primary_topic_name`
- OpenAlex `type`
- work-specific exception lists

`query_id` is release-local provenance and must not be treated as persistent
cross-release identity.

## Interpretation

This policy is calibration-selected, not statistically inferred for the
wider literary population.

The observed calibration proportions must not be interpreted as expected
full-production review rates.

Operational burden must be measured after the same deterministic features
are generated over the full production retrieval population.

## Independent validation status

### A2 author reversal: held-out validation completed

Independent held-out evaluation was completed for the frozen
`A2_AUTHOR_REVERSAL` policy using calibration-external project works.

Validation design:

- eligible calibration-external A2-sensitive resolved works: 1,474
- held-out sample: 500 project works
- sampling unit: `project_work_id`
- A2 marginal candidate pairs generated in the frozen OpenAlex snapshot: 248
- candidate-bearing project works: 64
- unique OpenAlex works among candidates: 243
- policy thresholds were frozen before validation
- no work-specific exception was introduced after validation

Frozen validation releases:

- final-label freeze:
  `0a8e35697270e90ad5fc021f0ea0d863cdd5ad8c`
- locked-policy overlay freeze:
  `c15f0229b259fc3f3794671b8fafb4cf69393dcf`

The final validation labels were produced using blind LLM-assisted
adjudication followed by targeted human adjudication of every first-pass
non-VALID case.

Final labels:

- `VALID_TARGET_REFERENCE`: 243
- `INVALID_TARGET_REFERENCE`: 5
- `UNCERTAIN`: 0

The 243 VALID candidates must not be described as 243 independently
human-adjudicated cases. The validation release retains per-candidate label
provenance.

The locked A2 rule was then overlaid without modification.

Overall held-out outcomes:

- candidates: 248
- project works: 64
- VALID: 243
- INVALID: 5
- UNCERTAIN: 0
- pair-level confirmed-valid proportion: 243 / 248 = 0.979839
- work-level macro confirmed-valid proportion: 0.965625

`ACCEPT` outcomes:

- candidates: 213
- project works represented: 55
- VALID: 212
- INVALID: 1
- UNCERTAIN: 0
- pair-level confirmed-valid precision: 212 / 213 = 0.995305
- work-level macro confirmed-valid precision: 0.981818

`REVIEW` outcomes:

- candidates: 35
- project works represented: 13
- VALID: 31
- INVALID: 4
- UNCERTAIN: 0
- pair-level confirmed-valid proportion: 31 / 35 = 0.885714
- work-level macro confirmed-valid proportion: 0.846154

The frozen REVIEW rule captured:

- 4 / 5 INVALID candidate pairs = 0.800000
- INVALID candidates from 3 / 4 INVALID-bearing project works = 0.750000

The observed held-out REVIEW share was:

- 35 / 248 candidate pairs = 0.141129

This is a review share within the held-out A2 marginal-candidate universe.
It is **not** an estimate of whole-production review burden.

One INVALID candidate remained automatically accepted:

- validation candidate: `A2V1_0081`
- target: `Mumbo jumbo`
- target author: `Clews, Henry`
- OpenAlex work: `W639618852`
- `hit_location`: `ABSTRACT_ONLY`
- `title_match_token_count_min`: 2
- `any_cross_w_title_collision`: `False`

This residual error is retained as validation evidence. The frozen policy is
not modified to create a work-specific exception or a post-validation
threshold adjustment.

Because the final held-out release contains no `UNCERTAIN` cases, confirmed,
upper-bound, and resolved-only pair-level proportions coincide for this
specific release. This does not change the general requirement that
`UNCERTAIN` remain separate from `INVALID`.

### Alias expansion

Independent same-release held-out validation is not available for the Alias
route under the current frozen registry.

All 138 resolved works whose R2 and R3 matching-signature sets differ were
included in the retrieval calibration sample; all 550 multi-alias resolved
works were likewise included.

The current Alias evidence must therefore continue to be described as a
finite-population audit of the current release, not as an independent
held-out validation of the selected threshold for future releases.

A future registry or corpus release can provide genuinely new
Alias-expansion works for out-of-sample validation.

### Reporting hierarchy

For the A2 validation, retain the existing reporting hierarchy:

- pair-level micro performance as the primary precision summary;
- work-level macro performance as a secondary summary;
- ACCEPT and REVIEW outcomes separately;
- candidate and work counts explicitly;
- `UNCERTAIN` separately from `INVALID`;
- no ordinary confidence interval for the finite held-out candidate universe;
- no claim about R2 baseline precision, R4 precision, recall, coverage, or
  complete-pipeline precision.

### Production application

The A2 held-out validation is now complete.

The next operational step is to apply the already frozen A2 rule to the
complete production A2 marginal-candidate population and measure the actual
production routing burden.

The Alias route remains governed by the current finite-population audit until
genuinely new out-of-sample evidence becomes available.

No human-label-based feature may enter production policy application.
