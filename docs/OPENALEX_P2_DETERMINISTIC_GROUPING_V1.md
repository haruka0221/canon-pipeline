# OpenAlex P2 deterministic evidence grouping v1

This release is a reproducible grouping and review-support artifact. It assigns no target-attribution judgment, does not calculate precision, and is not an adjudication result. The LLM judgment and reason-code columns are copied only as pre-existing descriptive inputs to deterministic complexity classification; they are non-authoritative.

## Inputs and scope

The standalone generator reads the frozen 661-row review package at `derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_v1/full_profile_57959e90/openalex_retrieval_precision_review_human_adjudication_v1.tsv`. It selects rows whose existing `review_priority` is exactly `P2`. Candidate identity, review order, project work ID, semantic group ID, evidence-signature strings, and LLM descriptive fields are copied from that package. Human adjudication fields must remain empty.

## Evidence signature and subgroup identifier

Within each existing `review_semantic_group_id`, subgroup membership is exact equality of the raw TSV string values, in this fixed order: `title_match_norms`, `author_a1_norms`, `author_a2_reverse_norms`, `any_title_match_in_title`, `any_title_match_in_abstract`, `any_author_a1_hit`, `any_author_a2_reverse_hit`, `hit_location`, `abstract_available`, `provenance_multiplicity`. There is no normalization, type conversion, or semantic interpretation in this grouping step.

For a semantic group ID `g` and signature fields `s1…s10`, the identifier input is the JSON array `[g,s1,…,s10]`, serialized as UTF-8 with Python JSON `ensure_ascii=False` and separators `(',', ':')`. No Unicode normalization is applied. The subgroup ID is `OAPESG1_` plus the first 16 lowercase hexadecimal characters of SHA-256 of those bytes. This canonicalization and field order are constants in the generator.

## Complexity classification

For each semantic group, let `n` be its P2 candidate count, `r` the number of distinct raw LLM reason-code strings, `j` the number of distinct raw LLM judgment strings, and `e` the number of distinct exact evidence signatures. Apply these rules in order:

1. `HETEROGENEOUS` when `n > 8`, `r > 1`, `j > 1`, or `e >= 4`.
2. Otherwise `SIMPLE_HOMOGENEOUS` when `n <= 3` and `e == 1`.
3. Otherwise `MODERATE`.

These labels describe review complexity only. LLM fields are descriptive inputs and are not treated as human-authoritative judgments.

## Regeneration

From the repository root, run:

```sh
python3 scripts/build_openalex_p2_deterministic_grouping_v1.py
```

The generator writes the mapping, manifest, and audit into `derived/openalex_production/p2_deterministic_grouping_v1/full_profile_57959e90/`. Optional `--sheets-dir PATH` writes compact Markdown review sheets; `--compare-sheets-dir PATH` audits per-subgroup candidate membership against an existing sheet directory.
