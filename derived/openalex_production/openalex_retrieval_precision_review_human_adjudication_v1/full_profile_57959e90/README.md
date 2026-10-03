# OpenAlex human target-attribution adjudication review package v1

Status: **UNADJUDICATED HUMAN REVIEW TEMPLATE**. This package contains no human
judgment and is not an authoritative result until completed, validated, and released
through a separate final-adjudication process. It does not calculate precision.

## Mandatory review rule

The `llm_*` fields are non-authoritative suggestions only. A human reviewer must
independently apply `docs/OPENALEX_PRECISION_REVIEW_PROTOCOL_V1.md`
(`review_protocol_version = v1`). The final human judgment must not be copied
automatically from LLM output. Review the supplied project/retrieval evidence and
OpenAlex record evidence before entering any human field.

The primary question is target attribution only: **does the retrieved title/author
evidence actually refer to the intended project literary work?** Do not judge
document scope, literary-visibility inclusion, or mention policy. Those are separate
decisions. `UNCERTAIN` is valid when the available evidence genuinely cannot
distinguish alternatives.

`review_semantic_group_id` is an analysis aid, not a project work, judgment unit, or
license to propagate one candidate's judgment to another. Each candidate must be
reviewed independently. Rows from the same semantic group are adjacent within each
priority to make comparison easier.

## Review order

Work in ascending `review_order`.

- P1: LLM `UNCERTAIN` and LLM `INVALID_TARGET_REFERENCE`; within each semantic
  group, uncertain suggestions appear before invalid suggestions.
- P2: LLM `VALID_TARGET_REFERENCE` with `VALID_CONTEXTUAL_REFERENCE` or
  `VALID_TITLE_VARIANT`.
- P3: remaining LLM `VALID_TARGET_REFERENCE` rows with
  `DIRECT_TARGET_REFERENCE`.

Priority is a workflow aid derived from provisional LLM labels; it is not evidence
of correctness or a precision result.

## Human fields and protocol-v1 vocabularies

Every `human_*` field is intentionally empty in this package. Populate it only by
manual review.

Allowed `human_target_attribution_judgment` values:

- `VALID_TARGET_REFERENCE`
- `INVALID_TARGET_REFERENCE`
- `UNCERTAIN`

Allowed `human_adjudication_confidence` values: `HIGH`, `MEDIUM`, `LOW`.

Allowed `human_attribution_reason_code` values and compatibility:

- VALID: `DIRECT_TARGET_REFERENCE`, `VALID_TITLE_VARIANT`,
  `VALID_CONTEXTUAL_REFERENCE`
- INVALID: `TITLE_COLLISION_DIFFERENT_WORK`, `GENERIC_OR_LEXICAL_TITLE_USE`,
  `AUTHOR_COLLISION_DIFFERENT_PERSON`, `TITLE_AUTHOR_UNLINKED_COOCCURRENCE`,
  `WRONG_WORK_SAME_AUTHOR`, `ALIAS_NOT_TARGET_EQUIVALENT`,
  `METADATA_TEXT_ARTIFACT`, `OTHER`
- UNCERTAIN: `INSUFFICIENT_CONTEXT`, `AMBIGUOUS_TARGET_REFERENCE`

When filled, human evidence-use fields use `True` or `False`. If external evidence
is used, record both a resolvable reference and a concise note. `OTHER` requires a
reviewer note. Record a stable reviewer identifier and an RFC 3339 UTC adjudication
timestamp. The eventual authoritative output must pass the protocol-v1 schema and
the repository's authoritative Python validator; this empty interface is not itself
a completed judgment table.
