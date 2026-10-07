# OpenAlex A2 Held-Out Validation Adjudication Guide v1

## Status

Frozen adjudication rubric for the held-out validation of the
`A2_AUTHOR_REVERSAL` marginal retrieval route.

This guide must be frozen before adjudication begins.

The adjudication target is the frozen pre-adjudication candidate release:

- release: `openalex-a2-validation-candidates-v1`
- candidate pairs: 248
- project works: 64
- unique OpenAlex works: 243

The adjudication unit is:

```text
project_work_id × openalex_work_id
```

The same OpenAlex work may therefore receive separate judgments for
different target literary works.

## Purpose

The task is to determine whether each retrieved OpenAlex record
substantively refers to the specific target literary work.

The task is not to judge:

- the scholarly quality of the OpenAlex record;
- the importance of the target literary work;
- whether the OpenAlex record is primarily about the target;
- whether the retrieval route should be accepted automatically;
- whether the frozen A2 policy is good or bad.

Policy action and policy-driving features must remain hidden during
adjudication.

## Allowed judgments

Exactly one of the following three labels must be assigned to every
candidate pair.

### `VALID_TARGET_REFERENCE`

Use when the available OpenAlex title and/or abstract provides sufficient
evidence that the record substantively refers to the target literary work.

A record does not need to be primarily about the target work.

Examples include:

- an article directly about the target novel;
- a comparative study that discusses the target novel;
- a broader author study in which the target novel is explicitly discussed;
- a historical, theoretical, or thematic study that clearly treats the
  target novel as part of its evidence;
- a review, chapter, dissertation, or other scholarly record whose available
  metadata clearly establishes reference to the target work.

### `INVALID_TARGET_REFERENCE`

Use when the available evidence is sufficient to conclude that the match does
not refer to the target literary work.

Examples include:

- a different work with the same or similar title;
- a lexical or generic phrase that happens to match the literary title;
- a reference to a different person with the same or similar author name;
- another work by the target author, where the target literary work itself is
  not being referred to;
- a title/author combination produced by retrieval coincidence rather than a
  substantive reference to the target work.

Do not use `INVALID_TARGET_REFERENCE` merely because the evidence is sparse.
If the available evidence does not permit a reliable decision, use
`UNCERTAIN`.

### `UNCERTAIN`

Use when the available OpenAlex title and abstract do not provide enough
evidence to decide reliably whether the record refers to the target literary
work.

`UNCERTAIN` must remain analytically distinct from
`INVALID_TARGET_REFERENCE`.

It must never be silently recoded as a false positive.

## Judgment principles

### 1. Judge the target work, not merely the author

A record mentioning the target author is not automatically a valid reference
to the target literary work.

There must be sufficient evidence that the specific target work is referred
to.

### 2. Explicit work evidence is sufficient

If the target work is clearly named or otherwise unmistakably identified in
the title or abstract, the candidate may be judged
`VALID_TARGET_REFERENCE`.

### 3. Primary focus is not required

A record may discuss several works or authors.

It remains valid if the target literary work is substantively included.

### 4. Do not infer beyond the available evidence

Do not assume that a record discusses the target work merely because:

- it concerns the same author;
- it concerns the same national literature;
- it concerns the same historical period;
- its topic would make discussion of the target plausible.

If the available evidence is insufficient, use `UNCERTAIN`.

### 5. Do not use retrieval-policy information

The following must not influence adjudication:

- `hit_location`;
- title token count;
- cross-W collision status;
- A1/A2 matching flags;
- whether the frozen policy would assign `ACCEPT` or `REVIEW`;
- calibration outcomes for similar cases.

These are evaluation variables, not adjudication evidence.

### 6. Do not use candidate frequency as evidence

A target work having many retrieved candidates does not make an individual
candidate more or less likely to be valid.

Each candidate pair must be judged on its own evidence.

## Reason codes

Reason codes are explanatory metadata only.

They must not be used as production-policy inputs.

### For valid judgments

- `DIRECT_WORK_REFERENCE`
  - The target literary work is directly and clearly identified.

- `AUTHOR_AND_WORK_CONTEXT`
  - The record is framed more broadly around the author or related context,
    but the available evidence sufficiently establishes discussion of the
    target work.

- `OTHER_VALID`
  - Valid reference not adequately described by the above categories.

### For invalid judgments

- `TITLE_COLLISION_DIFFERENT_WORK`
  - The matching title refers to a different work or object.

- `GENERIC_OR_LEXICAL_MATCH`
  - The literary title functions as an ordinary phrase or coincidental
    lexical match rather than as a reference to the target work.

- `WRONG_WORK_SAME_AUTHOR`
  - The record concerns the target author but a different work.

- `AUTHOR_COLLISION`
  - The author-name evidence refers to another person.

- `OTHER_INVALID`
  - Invalid match not adequately described by the above categories.

### For uncertain judgments

- `INSUFFICIENT_CONTEXT`
  - The available title and abstract are insufficient for a reliable
    attribution decision.

- `OTHER_UNCERTAIN`
  - Uncertain for another reason that should be described in notes.

## Notes field

`human_notes` is optional.

Use it when a short explanation would help later error analysis, especially
for:

- ambiguous title identity;
- unclear author identity;
- records discussing several works;
- unusual publication types;
- cases where the distinction between `INVALID_TARGET_REFERENCE` and
  `UNCERTAIN` is not obvious.

Notes are post-hoc explanatory material only.

## Adjudication procedure

For each candidate:

1. Read the target title and target author.
2. Read the OpenAlex display name.
3. Read the OpenAlex abstract when available.
4. Decide whether the OpenAlex record substantively refers to the specific
   target literary work.
5. Assign exactly one judgment:
   - `VALID_TARGET_REFERENCE`
   - `INVALID_TARGET_REFERENCE`
   - `UNCERTAIN`
6. Assign one compatible reason code.
7. Add a short note only if useful.

Do not inspect the hidden policy-driving features before assigning the
judgment.

## LLM-assisted first pass

An LLM may be used to assist with first-pass adjudication.

The LLM must receive only the blind adjudication fields required for the
semantic decision and must not receive:

- policy action;
- policy condition;
- hit location;
- title token count;
- cross-W collision status;
- calibration labels;
- previous validation judgments that could bias later cases.

LLM output is provisional.

Final validation labels should be human-reviewed before they are frozen.

## Validation analysis after labels are frozen

Only after all judgments have been completed and frozen may the locked A2
policy be overlaid.

The locked policy must not be altered in response to validation outcomes.

Primary reporting:

- pair-level micro performance.

Secondary reporting:

- work-level macro performance;
- `ACCEPT` and `REVIEW` performance separately;
- candidate and project-work counts;
- `UNCERTAIN` reported separately from `INVALID`.

No threshold tuning or work-specific exception may be introduced on the
basis of this validation set.

## Separation of stages

The intended sequence is:

```text
frozen sampling frame
    ↓
frozen held-out sample
    ↓
full OpenAlex scan
    ↓
frozen A2 marginal candidate universe
    ↓
frozen adjudication rubric
    ↓
blind adjudication
    ↓
frozen human labels
    ↓
locked policy overlay
    ↓
validation analysis
```

This ordering is part of the validation design.
