# OpenAlex A2 Held-Out Validation Final Adjudication Protocol v1

## Status

Final adjudication protocol for the frozen A2 held-out candidate universe,
written before overlaying the locked A2 retrieval policy.

This document records the procedure that was actually used. It supersedes the
earlier local draft `OPENALEX_A2_VALIDATION_TARGETED_HUMAN_AUDIT_PROTOCOL_V1.md`
if that draft has not been frozen in Git. Do not rewrite previously frozen
history if it has already been committed; in that case retain both documents
and treat this file as the forward finalization record.

## Frozen candidate universe

- candidate release: `openalex-a2-validation-candidates-v1`
- candidate unit: `(project_work_id, openalex_work_id)`
- candidate pairs: 248
- project works: 64
- unique OpenAlex works: 243
- source blind-batch Git commit:
  `746b7b3196c6795f990299ff1e97fd1d0051a328`

The adjudication stage did not use the locked A2 policy fields or policy action.

## Adjudication labels

The frozen vocabulary is:

- `VALID_TARGET_REFERENCE`
- `INVALID_TARGET_REFERENCE`
- `UNCERTAIN`

`UNCERTAIN` is distinct from `INVALID_TARGET_REFERENCE` and is never counted
as a false positive merely by being unresolved.

## Stage 1: blind LLM first pass

All 248 candidate pairs were adjudicated from the frozen blind evidence using:

- target title
- target author
- OpenAlex display name
- OpenAlex abstract
- bibliographic metadata already present in the blind batch

No locked-policy feature was used.

First-pass counts:

- `VALID_TARGET_REFERENCE`: 243
- `INVALID_TARGET_REFERENCE`: 3
- `UNCERTAIN`: 2

## Stage 2: same-model consistency pass

All 248 pairs received a second consistency check by the same model in the
same project context.

Result:

- judgment disagreements: 0

This is a consistency check only. It is **not** an independent annotator,
independent model, or inter-annotator agreement study.

## Stage 3: supplementary cross-model QA

A separate Claude-assisted review was performed on 25 candidates:

- all 5 first-pass `INVALID_TARGET_REFERENCE` / `UNCERTAIN` candidates;
- a deterministic sample of 20 first-pass `VALID_TARGET_REFERENCE` candidates.

The uploaded review workbook records agreement with the first-pass LLM on all
25 cases.

However, the workbook notes explicitly state that this Claude-assisted review
also verified records against the live OpenAlex API on 2026-10-07.

Therefore this stage is treated only as **supplementary QA**:

- it is not part of the blind held-out label-generation procedure;
- it is not human adjudication;
- it does not override the frozen blind evidence;
- its outcome may be reported as an auxiliary robustness check, with the live
  API caveat stated explicitly.

## Stage 4: targeted human adjudication

The human reviewer directly adjudicated the five candidates that were not
first-pass VALID.

The human task was restricted to the substantive question:

> Does this OpenAlex record refer to the target literary work?

The five human judgments were:

| candidate_id | first-pass | human judgment | relation |
| --- | --- | --- | --- |
| A2V1_0005 | UNCERTAIN | INVALID_TARGET_REFERENCE | override |
| A2V1_0066 | INVALID_TARGET_REFERENCE | INVALID_TARGET_REFERENCE | agree |
| A2V1_0081 | INVALID_TARGET_REFERENCE | INVALID_TARGET_REFERENCE | agree |
| A2V1_0074 | INVALID_TARGET_REFERENCE | INVALID_TARGET_REFERENCE | agree |
| A2V1_0006 | UNCERTAIN | INVALID_TARGET_REFERENCE | override |

For the two `Drift` cases, the human reviewer judged that Peter Cowan's name
and lexical uses of *drift* did not establish a reference to Cowan's specific
work *Drift*. These two cases therefore move from `UNCERTAIN` to
`INVALID_TARGET_REFERENCE`.

Human reason codes for the two overrides are assigned post hoc from the frozen
reason-code vocabulary as `GENERIC_OR_LEXICAL_MATCH`. Reason codes are
explanatory metadata and are not policy inputs.

## Final operational labels

After targeted human adjudication:

- `VALID_TARGET_REFERENCE`: 243
- `INVALID_TARGET_REFERENCE`: 5
- `UNCERTAIN`: 0

Final label provenance is retained per candidate.

The principal provenance categories are:

- `HUMAN_AUDITED_AGREE`
- `HUMAN_AUDITED_OVERRIDE`
- `LLM_BLIND_FIRST_PASS_CONSISTENT_UNAUDITED`

A separate flag records whether a candidate participated in the supplementary
Claude-assisted cross-model QA.

The 243 VALID labels must **not** be described as 243 human-adjudicated cases.
Most remain LLM-assisted blind labels.

## Interpretation and reporting

The held-out result is an LLM-assisted validation with targeted human
adjudication of every first-pass non-VALID candidate, plus a supplementary
cross-model spot check.

It is not:

- a fully human-adjudicated 248-pair gold standard;
- an independent double-coded annotation study;
- evidence about recall;
- evidence about whole-pipeline precision;
- a basis for an ordinary sampling confidence interval over an assumed
  infinite population.

The held-out candidate universe remains the finite A2 marginal candidate set
generated from the frozen OpenAlex snapshot and the frozen 500-work
validation sample.

## Policy overlay

Only after this final-label release is frozen may the locked A2 policy be
overlaid.

The locked A2 rule must not be altered in response to these validation labels.

Report:

- pair-level micro performance as primary;
- work-level macro performance as secondary;
- ACCEPT and REVIEW separately;
- candidate and project-work counts;
- `UNCERTAIN` separately if any arise in future releases;
- label provenance and the distinction between blind LLM labels, human
  adjudication, and supplementary cross-model QA.

Do not claim R2 baseline performance, R4 performance, recall, coverage, or
overall production-pipeline precision from this validation release.
