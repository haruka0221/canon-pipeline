# Held-out aggregation review: historical LLM comparison v1

**Status:** Frozen evaluation report v1 (version-controlled)

## Evaluation design

- Sampling frame: **761 held aggregation units** across six strata.
- Held-out reviewed sample: **20 units**.
- Reference judgments: **researcher-accepted, AI-assisted**.
- These are **not independent, unaided human gold labels**.
- Frozen review SHA-256: `9b9dea1b7ec54710affab9b739797de0dc5d01b7f8d9049d9e723a2962a91c8d`
- Sampling internal SHA-256: `c4eb577d5b351cc479276eb2ee8733dc0e72ed94506c30aaa9eef8c58faeb432`
- Historical predictions were inspected **after** the 20 reviews were frozen.

## Observed held-out results

- Exact agreement: **12/20 = 60.0%**.
- Historical LLM non-abstentions: **15/20**.
- Agreement among non-abstentions: **12/15 = 80.0%**.
- Potential over-merges: **3/12 historical ONE_WORK predictions**.
- Over-merge disagreement cases: **11, 12, 13**.
- All five historical UNRESOLVED cases received a resolved
  researcher-accepted judgment after additional research.

## Stratified frame-level results

| Metric | Result |
|---|---:|
| Historical LLM resolved coverage | 457/761 = 60.05% |
| Estimated agreement among resolved decisions | 67.23% |
| Estimated potential over-merge rate among historical ONE_WORK | 34.19% |
| Estimated potential over-merge count among 438 | 149.75 |
| Exploratory design-based standard error of over-merge rate | 17.86% |

The last three quantities are estimates, **not observed population
totals**. The standard error is large, and strata with no observed
disagreements have highly uncertain error rates. No formal confidence
interval is claimed.

## Stratum-level observed results

| Stratum | Frame N | Held-out n | Disagreements |
|---|---:|---:|---:|
| `MULTIPLE_WORKS` | 19 | 3 | 0 |
| `ONE_COMPLEX_STRONG` | 237 | 4 | 1 |
| `ONE_COMPLEX_WEAK` | 6 | 2 | 0 |
| `ONE_SIMPLE_STRONG` | 181 | 4 | 2 |
| `ONE_SIMPLE_WEAK` | 14 | 2 | 0 |
| `UNRESOLVED` | 304 | 5 | 5 |

## Interpretation

Cases 11, 12, and 13 expose potential overaggregation arising
from anthology scope, combined publications, and adaptation /
textual-form distinctions. Historical UNRESOLVED predictions are
abstentions, not automatically unsafe merge decisions.

The design generator draws each stratum with
`random.Random(seed).sample(sorted(stratum_ids), n_dev + n_eval)`
and assigns the latter portion to evaluation. Therefore evaluation
membership is uniform within unaffected strata under the documented
randomization design.

One previously exposed evaluation unit in the UNRESOLVED stratum
was replaced by a deterministic hash-selected eligible unit.
Population-weighted findings in this report consequently exclude
that stratum. Resolved coverage is calculated directly from
the original 761-unit frame distribution.

## Methodological boundaries

- The analysis addresses the **761-unit frame only**.
- The reference labels were **AI-assisted and researcher accepted**.
- Case 12's combined-edition evidence was audited before label freeze.
- Case 16's precise Edition partition remains undetermined.
- Case 17's ONE_WORK decision concerns duplicate records of a
  two-novel aggregate, not the identity of its constituent novels.
- No actual changes or demonstrated errors in Project W v7
  follow automatically from this comparison.
- This report is a fixed evaluation artifact; it does not amend the frozen review.
