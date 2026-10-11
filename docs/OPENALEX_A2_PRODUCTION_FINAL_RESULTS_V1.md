# OpenAlex A2 Production Final Results v1

## Status

Final production-stage summary for the frozen `A2_AUTHOR_REVERSAL` marginal retrieval route.

This memo records the state of the A2 production analysis through the work-level coverage freeze completed on 2026-10-11.

Latest work-level freeze:

- commit: `1b29427133cbb6f3733d6681866d5ae7aa569014`

This memo summarizes the relationship among the frozen retrieval policy, calibration evidence, calibration-external held-out evaluation, full-production routing, targeted production review, pair-level final disposition, and work-level operational coverage.

The A2 rule was not retuned after held-out validation or production review.

---

## 1. Scope

The A2 route addresses a specific author-name normalization problem in the resolved-work R3 retrieval layer: author names appearing in reversed order relative to the A1 form.

The production A2 marginal candidate universe is defined at the `project_work_id × OpenAlex Work` level as:

```text
(R3 + A2) - (R3 + A1)
```

Accordingly, these candidates represent OpenAlex Work matches recovered by the A2 author-reversal form that were not already recovered for the same project work under A1.

The resulting full-production marginal universe contains:

| Measure | Count |
|---|---:|
| A2 marginal candidate pairs | 963 |
| Project works represented | 231 |
| Unique OpenAlex works | 916 |

These counts describe retrieval candidates. They do not by themselves establish that all 963 pairs are correct references to the target literary works.

---

## 2. Frozen A2 routing rule

The A2 production policy was selected from the frozen calibration audit and fixed before held-out validation.

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

There is no automatic `REJECT` action.

`REVIEW` is a routing decision rather than an invalidity judgment. Candidates routed to review are withheld from automatic acceptance pending further evaluation.

`UNCERTAIN` remains distinct from `INVALID_TARGET_REFERENCE`.

Authoritative policy document:

```text
docs/OPENALEX_MARGINAL_RETRIEVAL_POLICY_V1.md
```

---

## 3. Calibration evidence

The frozen calibration universe contained 661 marginal candidates across 65 project works, including 252 `A2_AUTHOR_REVERSAL` candidates.

All 252 A2 calibration candidates received complete human adjudication.

Final A2 calibration labels were:

| Judgment | Count |
|---|---:|
| `VALID_TARGET_REFERENCE` | 241 |
| `INVALID_TARGET_REFERENCE` | 10 |
| `UNCERTAIN` | 1 |
| Total | 252 |

Applying the frozen A2 routing rule to these 252 candidates produced:

| Policy action | VALID | INVALID | UNCERTAIN | Total |
|---|---:|---:|---:|---:|
| ACCEPT | 234 | 0 | 1 | 235 |
| REVIEW | 7 | 10 | 0 | 17 |

Thus the calibration audit motivated the use of the short-title / cross-work-collision condition as a review-routing signal. These calibration proportions are descriptive of the audited calibration universe and are not treated as estimates of full-production performance.

---

## 4. Calibration-external held-out evaluation

After the routing rule had been frozen, it was evaluated on a calibration-external held-out sample.

The held-out design used 500 sampled project works from 1,474 eligible calibration-external A2-sensitive resolved works. Retrieval against the frozen OpenAlex snapshot produced 248 A2 marginal candidate pairs across 64 candidate-bearing project works.

Final held-out labels were:

| Judgment | Count |
|---|---:|
| `VALID_TARGET_REFERENCE` | 243 |
| `INVALID_TARGET_REFERENCE` | 5 |
| `UNCERTAIN` | 0 |
| Total | 248 |

The final-label layer was produced through blind LLM-assisted adjudication followed by direct human adjudication of every first-pass non-VALID case. Therefore, the 243 VALID labels must not be described as 243 independently human-adjudicated cases.

Under the already frozen rule:

| Policy action | VALID | INVALID | Total |
|---|---:|---:|---:|
| ACCEPT | 212 | 1 | 213 |
| REVIEW | 31 | 4 | 35 |

Pair-level confirmed-valid precision among held-out ACCEPT candidates was:

```text
212 / 213 = 0.995305
```

The REVIEW rule captured:

```text
4 / 5 held-out INVALID candidate pairs
```

One held-out INVALID candidate remained in ACCEPT. This residual error was retained as evidence and did not trigger threshold modification or a work-specific exception.

---

## 5. Full-production routing

The frozen rule was then applied without modification to the complete production A2 marginal universe.

Production routing results were:

| Policy action | Candidate pairs |
|---|---:|
| ACCEPT | 863 |
| REVIEW | 100 |
| Total | 963 |

The observed production review share was:

```text
100 / 963 = 10.3842%
```

The 963 candidates consisted of three evaluation-provenance groups:

| Evaluation source | ACCEPT | REVIEW | Total |
|---|---:|---:|---:|
| CALIBRATION | 235 | 17 | 252 |
| HELDOUT | 213 | 35 | 248 |
| NEW_PRODUCTION | 415 | 48 | 463 |
| Total | 863 | 100 | 963 |

Only the 48 `NEW_PRODUCTION` REVIEW candidates required new production-stage review. The calibration and held-out candidates already had existing evaluation histories.

---

## 6. New-production REVIEW evaluation

The 48 previously unevaluated production REVIEW candidates were first assessed using a blind LLM first pass based only on the review evidence supplied for each candidate.

The first pass produced:

| Judgment | Count |
|---|---:|
| `VALID_TARGET_REFERENCE` | 23 |
| `INVALID_TARGET_REFERENCE` | 24 |
| `UNCERTAIN` | 1 |

All 25 first-pass non-VALID cases then received direct human review while the prior LLM judgments and policy diagnostics remained hidden from the reviewer.

The direct-review outcomes were:

| Judgment | Count |
|---|---:|
| `INVALID_TARGET_REFERENCE` | 24 |
| `UNCERTAIN` | 1 |
| `VALID_TARGET_REFERENCE` | 0 |

The human judgments agreed with the LLM first-pass judgment category in all 25 escalated cases.

This 25/25 agreement must not be interpreted as an overall LLM accuracy estimate. Human review was conditionally targeted to candidates that the first pass had already labeled non-VALID, rather than drawn as an independent random validation sample.

For the final 48-candidate production layer, human judgments override the first-pass labels where direct review occurred. The remaining 23 first-pass VALID candidates retain their operational LLM labels with explicit provenance indicating that they did not receive direct human review.

The resulting 48 final labels are therefore:

```text
VALID      23
INVALID    24
UNCERTAIN   1
```

---

## 7. Final results for the 100-candidate REVIEW queue

Combining calibration, held-out, and new-production evidence resolves all 100 candidates routed to REVIEW.

| Evaluation source | VALID | INVALID | UNCERTAIN | Total |
|---|---:|---:|---:|---:|
| CALIBRATION | 7 | 10 | 0 | 17 |
| HELDOUT | 31 | 4 | 0 | 35 |
| NEW_PRODUCTION | 23 | 24 | 1 | 48 |
| **Total** | **61** | **38** | **1** | **100** |

Thus the production REVIEW queue contains:

```text
61 VALID
38 INVALID
1 UNCERTAIN
```

Forty-six of these 100 REVIEW candidates received direct human review: 17 calibration candidates, 4 held-out REVIEW candidates, and 25 new-production candidates.

The 61% VALID proportion describes the deliberately difficult REVIEW queue. It is not an estimate of A2 precision as a whole.

---

## 8. Final pair-level disposition across all 963 candidates

Existing calibration and held-out labels were then overlaid across the entire 963-pair production universe, including candidates routed to ACCEPT.

This step is essential because policy `ACCEPT` is not equivalent to an adjudicated `VALID_TARGET_REFERENCE`.

Among the 548 candidates with an existing or newly established final label:

| Final judgment | Candidate pairs |
|---|---:|
| `VALID_TARGET_REFERENCE` | 507 |
| `INVALID_TARGET_REFERENCE` | 39 |
| `UNCERTAIN` | 2 |
| Total final-labeled | 548 |

The remaining 415 pairs are `NEW_PRODUCTION` policy ACCEPT candidates without individual final adjudication.

The relationship between routing and final labels is:

| Policy action | VALID | INVALID | UNCERTAIN | Unadjudicated | Total |
|---|---:|---:|---:|---:|---:|
| ACCEPT | 446 | 1 | 1 | 415 | 863 |
| REVIEW | 61 | 38 | 1 | 0 | 100 |
| Total | 507 | 39 | 2 | 415 | 963 |

The final operational disposition is therefore:

| Operational disposition | Candidate pairs |
|---|---:|
| `INCLUDE_FINAL_VALID` | 507 |
| `INCLUDE_POLICY_ACCEPT_UNADJUDICATED` | 415 |
| `EXCLUDE_FINAL_INVALID` | 39 |
| `HOLD_UNCERTAIN` | 2 |
| Total | 963 |

Operational inclusion contains:

```text
507 + 415 = 922 candidate pairs
```

The 415 unadjudicated ACCEPT pairs must not be described as individually validated or human-confirmed matches.

A total of 282 of the 963 marginal candidates received direct human review: all 252 calibration A2 candidates, 5 held-out candidates, and 25 new-production candidates.

---

## 9. Work-level effect of A2

Before final disposition, R3+A1 produced candidate coverage for 6,899 project works.

Adding A2 at the candidate-generation stage increased this to:

```text
7,106 project works
```

This is a candidate-stage gain of:

```text
7,106 - 6,899 = 207 project works
```

The 963 A2 marginal candidate pairs occur across 231 project works. Of those 231 works, 24 already had at least one R3+A1 candidate, while 207 represented genuinely new work-level candidate coverage attributable to A2.

After applying known final labels and the frozen operational disposition, 195 of those 207 newly covered works retain at least one operationally included A2 candidate.

Therefore:

```text
R3+A1 operational work coverage:        6,899
A2 operational work-level gain:          +195
R3+A1 + operational A2 coverage:        7,094
```

Twelve of the 207 A2-new works lose all A2 candidates after final disposition.

The candidate-stage A2 work gain therefore has an operational retention rate of:

```text
195 / 207 = 94.2029%
```

The 207 A2-new works divide into:

| Work-level status | Project works |
|---|---:|
| Retained with at least one final `VALID_TARGET_REFERENCE` candidate | 88 |
| Retained only through unadjudicated policy ACCEPT candidate(s) | 107 |
| Lose all A2 candidates after final disposition | 12 |
| Total A2-new works | 207 |

The 88-work figure is a stronger-evidence subset of the 195 operationally retained works. It does **not** mean that only 88 of the 195 are correct.

Likewise, “final VALID” does not necessarily mean direct human adjudication in every case. Label provenance differs across calibration, held-out, and new-production layers and must remain available when stronger claims about evidential status are required.

---

## 10. Recommended reporting language

For retrieval coverage, the preferred final statement is:

> The A2 author-reversal retrieval layer initially increased R3 work-level candidate coverage from 6,899 to 7,106 project works, adding 207 works not otherwise covered by R3+A1. After applying previously established calibration and held-out labels together with the final production-review dispositions, 195 of these 207 newly covered works retained at least one operationally included A2 candidate, yielding final operational R3+A1+A2 coverage of 7,094 project works.

When evidential strength needs to be distinguished, add:

> Among the 195 newly retained works, 88 had at least one candidate with a final `VALID_TARGET_REFERENCE` label, whereas 107 were retained solely through the frozen policy's unadjudicated ACCEPT route. The latter are operationally included but should not be described as individually validated matches.

For candidate-level production routing:

> The frozen A2 rule routed 100 of 963 marginal candidate pairs (10.38%) to REVIEW. Final disposition across the full marginal universe retained 922 pairs operationally, excluded 39 final INVALID pairs, and held 2 UNCERTAIN pairs separately.

The following formulations should be avoided:

```text
"A2 found 7,094 verified works."
"All 922 included A2 pairs are validated matches."
"The A2 precision is 61%."
"The 88 final-VALID works are all human-confirmed."
"The held-out 243 VALID candidates were all human adjudicated."
```

These formulations collapse distinctions among retrieval coverage, policy acceptance, final-label provenance, and direct human adjudication.

---

## 11. Interpretation

The production results support the A2 author-reversal route as a small but meaningful extension to the conservative R3+A1 retrieval layer.

At the work level, A2 contributes 195 operationally retained works beyond the A1 candidate coverage. The difference between the initial candidate-stage gain of 207 and the final operational gain of 195 demonstrates the value of keeping retrieval generation separate from evaluation and final disposition.

At the pair level, the frozen routing policy concentrates most observed invalid cases in REVIEW while maintaining a much larger automatic ACCEPT route. However, the existence of one known INVALID and one known UNCERTAIN candidate within ACCEPT shows why policy action and truth label must remain conceptually separate.

The final production artifacts therefore distinguish three different claims:

1. a candidate was retrieved by A2;
2. a candidate was operationally included under the frozen policy;
3. a candidate has a final `VALID_TARGET_REFERENCE` label.

These states must not be treated as interchangeable.

---

## 12. Limitations

This analysis evaluates the marginal contribution of `A2_AUTHOR_REVERSAL` only.

It does not establish precision, recall, or final correctness for the complete OpenAlex pipeline.

In particular:

- the global R3+A1 baseline has not undergone the same production-wide individual validation procedure;
- the 415 new-production A2 ACCEPT pairs remain individually unadjudicated;
- the calibration-external held-out final labels are LLM-assisted with targeted human review rather than a fully human-adjudicated gold standard;
- the production human-review subset was selected conditionally from first-pass non-VALID cases and cannot be used to estimate overall LLM accuracy;
- `UNCERTAIN` is retained as a distinct epistemic category rather than counted as an error;
- no post-validation or post-production threshold tuning is permitted;
- the Alias-expansion route has a separate evidential basis and should not be combined with these A2 results without preserving that distinction;
- the present analysis concerns candidate precision and operational coverage, not recall or the existence of works in OpenAlex generally.

---

## 13. Authoritative artifacts

The principal frozen artifacts underlying this memo are:

```text
docs/OPENALEX_MARGINAL_RETRIEVAL_POLICY_V1.md

derived/openalex_production/
  retrieval_a2_validation_final_labels_v1/
  retrieval_a2_validation_policy_overlay_v1/
  retrieval_a2_production_routing_v1/
  retrieval_a2_production_review_llm_first_pass_v1/
  retrieval_a2_production_human_review_final_v1/
  retrieval_a2_production_new_review_final_labels_v1/
  retrieval_a2_production_review_final_labels_v1/
  retrieval_a2_production_final_disposition_v1/
  retrieval_a2_production_work_coverage_v1/
```

The current work-level production result is frozen through commit:

```text
1b29427133cbb6f3733d6681866d5ae7aa569014
```
