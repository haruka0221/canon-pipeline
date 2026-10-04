# OpenAlex P3 deterministic review inventory v1

Status: descriptive inventory and workflow-design aid only. No human judgments are included.

> Grouping is a review aid only and does not authorize shared human judgments.

## Scope and counts

- P3 candidates: 493
- Distinct project works: 51
- Exact raw evidence-pattern signatures: 95
- Project-specific evidence subgroups: 95
- Project works spanning multiple evidence patterns: 21
- Suggested review batches: 25 (maximum 25 candidates)

## Candidate and evidence distributions

### Candidates per project work

`1`: 22, `2`: 6, `3`: 4, `4`: 5, `5`: 2, `6`: 3, `12`: 2, `15`: 1, `19`: 1, `27`: 1, `31`: 1, `42`: 1, `47`: 1, `194`: 1

### LLM judgment suggestions (descriptive only)

`VALID_TARGET_REFERENCE`: 493

### LLM confidence suggestions (descriptive only)

`HIGH`: 488, `MEDIUM`: 5

### LLM reason suggestions (descriptive only)

`DIRECT_TARGET_REFERENCE`: 493

### Increment type

`A2_AUTHOR_REVERSAL`: 242, `ALIAS_EXPANSION`: 251

### Hit location

`ABSTRACT_ONLY`: 300, `TITLE_AND_ABSTRACT`: 105, `TITLE_ONLY`: 88

### Abstract availability

`False`: 61, `True`: 432

### Title hit flag

`False`: 300, `True`: 193

### Abstract hit flag

`False`: 88, `True`: 405

### Author A1 hit flag

`False`: 242, `True`: 251

### Author A2 reverse hit flag

`False`: 251, `True`: 242

### Provenance multiplicity

`MULTIPLE`: 83, `SINGLE`: 410

### Title token count

`1`: 45, `2`: 298, `3`: 61, `4`: 43, `5`: 34, `6`: 6, `9`: 6

## Project-work review-load classes

| Class | Project works |
|---|---:|
| HIGH_REVIEW_LOAD | 10 |
| LOW_REVIEW_LOAD | 26 |
| MODERATE_REVIEW_LOAD | 15 |

Classes use project candidate count and distinct exact evidence patterns only. They do not imply that cases in a group share a correct judgment.

## Deterministic review ordering and batches

Candidates are sorted by project_work_id, then exact raw evidence signature fields in lexicographic order, then frozen review_order and candidate ID. `p3_review_order` assigns 1–493 in that sequence. Reviewers can use the evidence-signature summary to navigate candidate-level records.

Batch packing keeps a project-work block intact where it fits within the 25-candidate capacity; project works larger than 25 are split into sequential candidate-level chunks. These are proposed logistics, not adjudication units.

| Batch | P3 order | Candidates | Project works |
|---|---:|---:|---:|
| P3B01 | 1–20 | 20 | W000001334, W000001998, W000004216, W000006250, W000011243, W000012082, W000012083, W000012521, W000012633 |
| P3B02 | 21–45 | 25 | W000012843 |
| P3B03 | 46–70 | 25 | W000012843 |
| P3B04 | 71–95 | 25 | W000012843 |
| P3B05 | 96–120 | 25 | W000012843 |
| P3B06 | 121–145 | 25 | W000012843 |
| P3B07 | 146–170 | 25 | W000012843 |
| P3B08 | 171–195 | 25 | W000012843 |
| P3B09 | 196–214 | 19 | W000012843 |
| P3B10 | 215–238 | 24 | W000013001, W000013782, W000022646, W000023580, W000024260, W000025627, W000027859, W000029053, W000030303, W000031720, W000031727 |
| P3B11 | 239–263 | 25 | W000031733 |
| P3B12 | 264–280 | 17 | W000031733 |
| P3B13 | 281–305 | 25 | W000031746, W000031752, W000031771, W000031775, W000031792 |
| P3B14 | 306–330 | 25 | W000031804 |
| P3B15 | 331–352 | 22 | W000031804 |
| P3B16 | 353–372 | 20 | W000031833, W000031927, W000031931, W000031939, W000031941 |
| P3B17 | 373–397 | 25 | W000031942 |
| P3B18 | 398–403 | 6 | W000031942 |
| P3B19 | 404–404 | 1 | W000031946 |
| P3B20 | 405–429 | 25 | W000031949 |
| P3B21 | 430–431 | 2 | W000031949 |
| P3B22 | 432–456 | 25 | W000031954, W000031962, W000031967, W000031997 |
| P3B23 | 457–465 | 9 | W000032001, W000032009, W000032024, W000032026, W000032060 |
| P3B24 | 466–487 | 22 | W000032069, W000032070, W000032072 |
| P3B25 | 488–493 | 6 | W000032087, W000032088, W000032089 |

## Deterministic review flags

Flags identify observable review conditions, including title-only matches, unavailable abstracts, short title-token counts, absent aggregate author-hit flags, multiple provenance routes, multiple candidates or patterns per project work, repeated OpenAlex work IDs, repeated raw titles/abstracts, metadata missingness, and available LLM attention/taxonomy flags. A flag is a prompt to inspect the individual row; it is not a target-attribution judgment.

Exact repeated-field cues: 
same_openalex_work_id: 4 groups (4 excess rows); same_raw_display_name: 56 groups (63 excess rows); same_raw_abstract: 44 groups (48 excess rows); same_raw_display_name_and_publication_year: 47 groups (50 excess rows); same_raw_display_name_and_abstract: 43 groups (43 excess rows); same_nonempty_doi: 3 groups (3 excess rows).

The frozen package has aggregate any_author_a1_hit/any_author_a2_reverse_hit booleans but does not encode whether title and author evidence co-occur in the same title/abstract field or sentence. No co-occurrence is inferred; inspect candidate evidence directly.

## Reproduction

Run `python3 scripts/build_openalex_p3_deterministic_review_inventory_v1.py` from the repository root. The generator refuses a nonempty destination. Pass `--output-dir /tmp/<new-directory>` to generate a replay for byte-level reproducibility comparison.
