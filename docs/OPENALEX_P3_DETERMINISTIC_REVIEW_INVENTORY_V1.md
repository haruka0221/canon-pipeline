# OpenAlex P3 deterministic review inventory v1

## Purpose and limits

This release is a deterministic descriptive inventory for designing the P3 human-review workflow. It creates no human judgments and calculates no precision or performance metric. LLM fields are retained as pre-existing descriptive inputs and are not human-authoritative. Candidate rows remain the independent review units.

**Grouping is a review aid only and does not authorize shared human judgments.** Similar evidence, shared project work, or a repeated OpenAlex record never licenses copying one candidate's human judgment to another candidate.

## Frozen source and scope

The sole candidate source is the 661-row frozen review package at `derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_v1/full_profile_57959e90/openalex_retrieval_precision_review_human_adjudication_v1.tsv`. The generator selects only rows whose frozen `review_priority` is `P3`; it copies every source cell unchanged into the candidate mapping and appends inventory fields. The audit compares all 74 source columns for every P3 candidate. No P1/P2 adjudication package or outcome is used to determine P3 judgments.

## Evidence signature and stable IDs

The exact evidence signature fields and order are the same as P2: `title_match_norms`, `author_a1_norms`, `author_a2_reverse_norms`, `any_title_match_in_title`, `any_title_match_in_abstract`, `any_author_a1_hit`, `any_author_a2_reverse_hit`, `hit_location`, `abstract_available`, and `provenance_multiplicity`. Values are the raw TSV strings, including empty strings and lexical boolean spellings. Signature construction applies no normalization or semantic interpretation.

For signature ID, serialize the ten strings as a UTF-8 JSON array with Python-compatible compact separators `(',', ':')` and `ensure_ascii=False`, then use `OAP3ES1_` plus the first 16 lowercase hexadecimal characters of SHA-256. A project-specific subgroup ID uses the same procedure on `[project_work_id, ...ten raw signature strings...]`, with prefix `OAP3WES1_`. Truncated digest collisions are checked and rejected.

## Candidate-level review order

The proposed stable order sorts candidates by `project_work_id` ascending, then the exact ten raw signature values in their declared field order using string lexicographic ordering, then frozen `review_order` as an integer, then `review_candidate_id`. `p3_review_order` is the resulting sequence 1–493. The original frozen `review_order` remains in its original source column.

## Project-work complexity classes

These are structural workload descriptions based only on candidate and exact signature counts within a project work:

- `HIGH_REVIEW_LOAD`: more than 8 P3 candidates, or at least 4 project-specific evidence patterns.
- `LOW_REVIEW_LOAD`: at most 3 candidates and exactly 1 evidence pattern.
- `MODERATE_REVIEW_LOAD`: all other cases.

The labels help plan inspection time. They do not classify target attribution or authorize a shared judgment.

## Suggested batch boundaries

The default batch capacity is 25 candidates. Project-work blocks stay together when they fit in the remaining capacity. A project work larger than 25 candidates is split into consecutive candidate-level chunks of at most 25, following the stable review order. Batch boundaries are logistical only; reviewers still adjudicate each candidate independently. The candidate mapping records the proposed order and batch ID; the plan and project summary record boundaries and work coverage.

## Deterministic review flags and duplicate cues

Candidate-level flags cover title-only evidence, unavailable abstracts, absent aggregate author-hit flags, one- or two-token title-match patterns from the frozen `title_token_count`, multiple provenance routes, project works with multiple candidates or evidence patterns, exact repeated OpenAlex work IDs, repeated raw display names/abstracts, selected missing metadata, and supplied LLM attention/taxonomy flags. These flags identify records to inspect; they are not judgments.

The source records aggregate author-hit booleans but do not encode whether title and author evidence occur in the same title/abstract field or sentence. The inventory does not infer that relationship. Repeated exact values (OpenAlex ID, display name, abstract, DOI, or selected exact pairs) are listed as review cues. No fuzzy or semantic near-duplicate detection is performed; repeated titles or abstracts alone do not establish duplicate works.

## Outputs and regeneration

The release directory contains a candidate mapping TSV, project-work summary TSV, evidence-signature summary TSV, audit JSON, manifest JSON, and Markdown review plan. From the repository root:

```sh
python3 scripts/build_openalex_p3_deterministic_review_inventory_v1.py
```

The generator refuses a nonempty destination and performs a byte-level replay into a temporary directory. To independently replay into a new location:

```sh
python3 scripts/build_openalex_p3_deterministic_review_inventory_v1.py --output-dir /tmp/openalex_p3_inventory_replay
```
