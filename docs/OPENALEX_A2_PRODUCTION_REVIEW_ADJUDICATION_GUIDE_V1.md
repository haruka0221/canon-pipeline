# OpenAlex A2 Production Review Adjudication Guide v1

## Scope

This guide applies only to the 48 `NEW_PRODUCTION` candidates that were
routed to `REVIEW` by the already-frozen A2 production routing policy.

The routing policy must not be altered on the basis of these adjudications.

## Unit of adjudication

One candidate is one:

`project_work_id × openalex_work_id`

pair.

## Question

Does the supplied OpenAlex record substantively refer to the target literary
work identified by the supplied target title and author?

Only the supplied target identity context, OpenAlex display name, and
OpenAlex abstract/metadata should be used for the blind adjudication.

Do not use hidden production-policy features.

## Judgments

### VALID_TARGET_REFERENCE

Use when the supplied title/abstract gives sufficient evidence that the
OpenAlex record substantively refers to the target literary work.

The target work need not be the primary focus of the OpenAlex record.

Comparative criticism, broader author studies, thematic discussions,
reviews, and similar records are valid if the target work is clearly
established.

### INVALID_TARGET_REFERENCE

Use when there is sufficient evidence that the match does not refer to the
target literary work.

Examples include:

- a different work with the same title;
- a generic or lexical phrase match;
- a different work by the same author;
- an author-name collision;
- another clearly non-target referent.

### UNCERTAIN

Use when the supplied title/abstract is insufficient to establish either a
valid or invalid target reference.

`UNCERTAIN` is distinct from `INVALID_TARGET_REFERENCE`.

## Reason codes

For `VALID_TARGET_REFERENCE`:

- `DIRECT_WORK_REFERENCE`
- `AUTHOR_AND_WORK_CONTEXT`
- `OTHER_VALID`

For `INVALID_TARGET_REFERENCE`:

- `TITLE_COLLISION_DIFFERENT_WORK`
- `GENERIC_OR_LEXICAL_MATCH`
- `WRONG_WORK_SAME_AUTHOR`
- `AUTHOR_COLLISION`
- `OTHER_INVALID`

For `UNCERTAIN`:

- `INSUFFICIENT_CONTEXT`
- `OTHER_UNCERTAIN`

## Blinding

The adjudicator must not use:

- `policy_action`;
- `hit_location`;
- title-token thresholds;
- cross-work collision features;
- A1/A2 matching diagnostics;
- candidate frequency;
- calibration or held-out outcomes.

Human reason codes are explanatory outcomes only and must never become
production-policy inputs.

## Reporting

After adjudication:

- keep `UNCERTAIN` separate from `INVALID`;
- retain candidate-level provenance;
- distinguish production-review labels from calibration and held-out labels;
- do not retune the frozen A2 policy from these production-review results.
