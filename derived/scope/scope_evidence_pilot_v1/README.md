# Scope evidence pilot v1 — NON-ADJUDICATIVE

Generated from frozen OpenAlex integrated v2, Project W v7, OpenAlex registry v4,
Open Library author-enriched historical source population, and current identity
provenance. No outside publication-year or genre adjudication is performed.

## Contents
- `sampling_frame_v1.tsv`: all 32,066 active Project W, with sampling membership,
  OpenAlex count, and query-coverage diagnostics.
- `scope_evidence_review_template_v1.tsv`: one row per selected Project W,
  source-native data, identity provenance, and EMPTY reviewer decision fields.
- `summary_v1.json`: counts, sampling design, limitations.
- `manifest_v1.json`: SHA256 inputs and generated outputs.

## Sampling
`RANDOM_ACTIVE_80` is an independent, uniformly ranked SHA256 draw from the
entire active W frame (deterministic fixed seed). Other cohorts are purposive:
Top 30, the frozen 21-W author-name screen, 15 high-Jaccard diagnostic W,
12 contrast W, 13 numeric/symbol-only titles, 12 random NOT_QUERIED, and
12 random non-ASCII-screen W. Cohorts overlap; selection labels are retained.
The mixed pilot is NOT a representative sample for an unweighted prevalence
estimate. Do not use targeted records as an independent held-out precision set.

## Evidence and non-decisions
`historical_edition_derived_min_year` reproduces OL source evidence and MUST NOT
be treated as the original publication year of the conceptual work. Titles,
authors, and subject signals are copied from the historical OL source layer and
may mix translations, collections, non-novels, or corrupted records.

All `*_review` decision fields start blank; `review_status=NOT_REVIEWED`.
Document external independent evidence before issuing any scope decision.
A sample row or `*_flag` never constitutes `IN_SCOPE` / `OUT_*` adjudication.
Do not overwrite frozen W identity, earlier human/LLM decisions, OpenAlex v2,
or the closed OL Edition audit. Do not auto-retrieve or reopen held work.

`NOT_QUERIED_R2_R3` means that the frozen registry lacks the production
R2/R3 queries; R4 title-only calibration queries are not operationally counted.
`NOT_REMEASURED` is a separate missingness category. `QUERIED_NO_OPERATIONAL_CANDIDATE`
is NOT a claim that no scholarly reference exists.
