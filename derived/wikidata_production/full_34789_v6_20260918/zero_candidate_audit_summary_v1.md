# Zero-candidate random-100 manual audit — v1

Date: 2026-09-18

## Purpose

This audit examines a frozen random sample of targets for which the
items-only production candidate generator returned zero Wikidata candidates.

It is intended to distinguish, as far as manual searching permits, between:

- candidate-retrieval misses;
- records for which no corresponding work-level Wikidata item can be identified;
- out-of-scope records; and
- Open Library metadata problems.

This audit is diagnostic only. It was not used to tune the frozen v6 judge.

## Population and sampling

- Zero-candidate population: **10,774**
- Random sample size: **100**
- Sampling method: simple random sample
- Random state: **20260918**
- Frozen sample: `zero_candidate_audit_random100_seed20260918.tsv`
- Sample SHA-256: `fc9d5f9f43add085c99c2ca59696c0af39e05c80243d6866fda2962ed7ab379b`

## Manual-review artifact

- Review file: `zero_candidate_audit_random100_manual_review_v1.tsv`
- Review SHA-256: `6866e94c8b5349ed223ca2419d1c733ab741ecaa65591f67c237fb3a504852a2`

## Wikidata search outcome

Across all 100 sampled records:

- `NOT_FOUND_AFTER_SEARCH`: **99**
- `FOUND_VARIANT`: **1**

The one identified work-level Wikidata item was:

- **OL1386177W — _Letzte am Schafott_ → Q1214380**
  - status: `FOUND_VARIANT`
  - failure mode: `TITLE_VARIANT_RETRIEVAL_MISS`

## Preliminary scope review

- `INCLUDE`: **60**
- `EXCLUDE_OUT_OF_SCOPE`: **23**
- `UNCERTAIN_SCOPE`: **17**

These scope judgments are preliminary and are intentionally kept separate
from the Wikidata entity-resolution judgment.

## Preliminary eligible-only result

Among the **60** records provisionally judged `INCLUDE`:

- work-level Wikidata item identified: **1/60 (1.7%)**
- no work-level Wikidata item identified after additional manual search:
  **59/60 (98.3%)**

The conservative interpretation is:

> Among 60 records provisionally judged to be in scope, only one
> corresponding work-level Wikidata item was identified through additional
> manual searching. No corresponding item was identified for the remaining
> 59 records.

`NOT_FOUND_AFTER_SEARCH` must not be interpreted as proof that a Wikidata
item does not exist. It records only the outcome of the manual search.
Detailed per-record search provenance was not retained for all 100 records.

## Additional observations

The audit also revealed several kinds of population noise, including:

- clearly out-of-scope nonfiction or bibliographic material;
- short-story collections and other non-novel material;
- juvenile/picture-book cases with uncertain scope;
- malformed or incorrect Open Library author metadata; and
- apparent Open Library date/work mismatches.

These issues should be treated separately from candidate-retrieval error.

## Reproducibility

The sample was frozen before manual inspection. The manual-review TSV,
sample TSV, and this summary should be retained together with their SHA-256
hashes.
