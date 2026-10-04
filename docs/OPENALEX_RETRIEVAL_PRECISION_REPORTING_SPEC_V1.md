# OpenAlex Retrieval-Precision Reporting Specification v1

**Status:** Methodological specification for later descriptive reporting. No
precision value, percentage, rate, confidence interval, or other performance
metric is calculated or reported here.

## 1. Purpose and estimand

The frozen 661-row authoritative human-adjudication set evaluates **target-
attribution precision among marginal retrieval candidates introduced by the
calibrated incremental retrieval mechanisms**. A candidate is valid when the
retrieved title/author evidence sufficiently establishes that it refers to the
intended project work under the frozen human-review protocol.

The estimand is therefore the confirmed-valid proportion within the defined
marginal candidate set, overall and within the reporting strata in Section 4.
It is not overall OpenAlex retrieval precision and does not describe the
absolute precision of the complete OpenAlex retrieval pipeline.

The candidate universe is fixed by the frozen snapshot, profile, and candidate
generation represented by the authoritative 661-row review package. It is a
finite set, not a sample drawn from an unbounded stream of OpenAlex records.

## 2. Units and aggregation

### Primary unit

The primary observational unit is one candidate pair, identified by
`review_candidate_id`. Each candidate pair contributes once to its applicable
stratum.

### Pair-level micro aggregation

The primary descriptive aggregation is pair-level micro: count candidate
judgments across the relevant stratum, then apply the quantities defined in
Section 5. Each candidate pair has equal weight, so project works with more
retrieved candidates contribute more pairs.

### Secondary macro-W aggregation

The secondary robustness aggregation is macro-W: calculate the same
candidate-level quantity separately within each `project_work_id` represented
in the relevant stratum, then take the unweighted arithmetic mean across those
works. Every represented project work receives equal weight regardless of its
candidate count.

Micro and macro-W answer different questions. Micro describes the candidate
pairs in the marginal retrieval set. Macro-W describes the average within-work
candidate result over represented project works. Report them separately and do
not substitute one for the other.

## 3. Frozen human judgments

Use the authoritative field `human_target_attribution_judgment` with these
labels:

- `VALID_TARGET_REFERENCE` (denoted V below)
- `INVALID_TARGET_REFERENCE` (denoted I below)
- `UNCERTAIN` (denoted U below)

The labels and the accompanying confidence, reason, note, reviewer, and
timestamp fields come only from the frozen authoritative adjudication aggregate
at commit `0455647`. The human-review protocol version is `v1`.

`UNCERTAIN` remains a distinct adjudication state. It is never silently
reclassified as valid or invalid.

## 4. Required reporting strata

Later descriptive reporting must show these strata separately:

1. All 661 marginal candidates combined.
2. Candidates with `increment_type = ALIAS_EXPANSION`.
3. Candidates with `increment_type = A2_AUTHOR_REVERSAL`.

Inspection of the frozen aggregate confirmed the exact increment labels and
membership:

| Stratum | Candidate pairs | Distinct `project_work_id` values |
| --- | ---: | ---: |
| All candidates | 661 | 65 |
| `ALIAS_EXPANSION` | 409 | 38 |
| `A2_AUTHOR_REVERSAL` | 252 | 27 |

The two increment candidate sets are disjoint: no `review_candidate_id` occurs
in both. In this frozen set, their project-work sets are also disjoint. The
combined stratum counts each candidate once.

These are inventory counts, not performance measures.

## 5. Required descriptive quantities

For any reporting stratum, let N be its candidate count and V, I, and U the
counts of valid, invalid, and uncertain human judgments, respectively. The
later calculation must report the following quantities using formulas, not
relabeling or recoding the adjudications.

### Confirmed-valid proportion: primary operational quantity

`V / N`

This treats only `VALID_TARGET_REFERENCE` as confirmed valid. `UNCERTAIN`
remains in the denominator and is not counted as valid.

### Adjudication-uncertainty bounds

- Lower bound: `V / N`
- Upper bound: `(V + U) / N`

These are identification/adjudication bounds reflecting unresolved human
judgments. They are **not statistical confidence intervals**.

### Resolved-case sensitivity

`V / (V + I)`

This is a resolved-case descriptive sensitivity measure that excludes
`UNCERTAIN`. Label it explicitly and report it alongside the primary quantity;
do not silently substitute it for the confirmed-valid proportion. If a stratum
has no resolved cases, the quantity is undefined and must be reported as such.

## 6. Macro-W versions

For each required stratum, let W be its represented project works. For work w,
let N_w be its number of candidates and V_w, I_w, and U_w its judgment counts.

- **Macro-W confirmed-valid:** calculate `V_w / N_w` for every work with at
  least one candidate in the stratum, then average those work-level values
  equally. Uncertain candidates remain in N_w and are not counted in V_w.
- **Macro-W adjudication bounds:** calculate the work-level lower endpoint
  `V_w / N_w` and upper endpoint `(V_w + U_w) / N_w`, then average each endpoint
  equally across all works represented in the stratum. The resulting pair is
  an average identification/adjudication interval, not a confidence interval.
- **Macro-W resolved-case sensitivity:** for each represented work with at
  least one resolved candidate (`V_w + I_w > 0`), calculate
  `V_w / (V_w + I_w)` and average equally over those eligible works. Uncertain
  candidates are excluded from each work's resolved denominator. A work with
  only uncertain candidates has no defined resolved-case value; omit it from
  this resolved-case average and report the number of eligible works alongside
  the result. Do not treat that omission as a valid or invalid judgment.

The reporting table should identify the candidate count and represented-work
count for each stratum. For the resolved-case macro-W sensitivity, also identify
the number of works with at least one resolved candidate.

## 7. Statistical uncertainty and finite-population interpretation

The frozen review-package audit confirms that its 661 candidate IDs exactly
equal the frozen review-view candidate set, with no missing, extra, or duplicate
candidates. The package contains all candidates in the defined marginal
candidate universe for this frozen snapshot/profile, partitioned into P1, P2,
and P3 workflow priorities. All 661 candidates have authoritative human
adjudications. The adjudication aggregate preserves that candidate membership.

Accordingly, the later descriptive quantities are finite-population
descriptions of this defined set. Ordinary binomial confidence intervals are
not required and must not be added by convention. The bounds in Section 5
describe adjudication uncertainty, not sampling uncertainty.

If a future question concerns inference to a broader population of project
works, snapshots, profiles, or retrieval settings, that is a separate estimand
and requires a separate methodology decision. Work-level resampling may be
considered for such a distinct inferential question; it is outside this
specification's primary descriptive result.

## 8. Scope and exclusions

These metrics characterize only the audited marginal candidate sets represented
by the frozen 661-row review universe. They do **not** estimate:

- absolute R2 baseline precision;
- R4 title-only precision;
- recall;
- overall OpenAlex coverage; or
- precision of the complete pipeline across all retrieved records.

Do not describe the results as “overall OpenAlex retrieval precision.” The
candidate review asks whether each retrieved marginal candidate is attributable
to its intended project work; it does not evaluate all records returned by the
complete retrieval pipeline.

## 9. Reproducibility and source control

The sole source of human judgments is the frozen authoritative aggregate:

`derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_complete_v1/full_profile_57959e90/`

Its authoritative baseline is commit `0455647` on branch
`kakenc-integration-20260927`. Use the frozen original review package for
candidate-universe and canonical structural metadata. Do not replace or revise
judgments using LLM suggestions or any mutable working copy.

Before later reporting, verify the aggregate audit, candidate membership,
priority and increment labels, and frozen hashes. Preserve the three reporting
strata and the treatment of `UNCERTAIN` as defined here. No precision,
percentage, rate, interval, accuracy value, or retrieval-policy recommendation
is produced by this specification.
