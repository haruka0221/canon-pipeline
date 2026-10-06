# OpenAlex Marginal Retrieval Policy v1

## Status

Calibration-selected policy candidate for the audited marginal OpenAlex retrieval routes.

This document freezes the routing rule selected from the calibration audit.
It does not by itself establish operational performance on the full
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

## Next step: independent validation

This frozen policy is a calibration-selected policy candidate. It must not be
treated as an independently validated production policy on the basis of the
same adjudicated calibration candidates used to select its thresholds.

### A2 author reversal

Independent validation is feasible for the A2 route. In the frozen registry,
1,474 A2-sensitive resolved project works lie outside the complete retrieval
calibration sample.

The primary validation sample will therefore be drawn at the
`project_work_id` level from those calibration-external A2-sensitive works.
The locked policy must be applied without threshold tuning or work-specific
exceptions.

All A2 marginal candidates generated for sampled works must be adjudicated,
with `UNCERTAIN` kept separate from `INVALID`.

Validation reporting must retain the existing hierarchy:

- pair-level micro performance as the primary precision summary;
- work-level macro performance as a secondary summary;
- ACCEPT and REVIEW performance reported separately;
- candidate and work counts reported explicitly;
- `UNCERTAIN` never silently recoded as an error.

### Alias expansion

Independent same-release held-out validation is not available for the Alias
route under the current frozen registry. All 138 resolved works whose R2 and
R3 matching-signature sets differ were included in the retrieval calibration
sample; all 550 multi-alias resolved works were likewise included.

The current Alias evidence should therefore be described as a finite-population
audit of the current release, not as an independent validation of the selected
threshold for future releases.

A future registry or corpus release can provide genuinely new Alias-expansion
works for out-of-sample validation.

### Production application

Only after the independent A2 validation has been frozen and evaluated should
the policy candidate be applied to the complete production marginal-candidate
population.

No human-label-based feature may enter either validation sampling features or
production policy application.
