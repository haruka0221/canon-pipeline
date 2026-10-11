# OpenAlex R2+A1 Baseline Human Adjudication Guide v1

## Purpose

This review evaluates absolute target-attribution precision for the frozen
PRIMARY 800-pair validation sample of the R2+A1 OpenAlex retrieval baseline.

The review unit is one frozen:

    project_work_id × openalex_work_id

candidate pair.

Primary question:

> Does the supplied OpenAlex record genuinely refer to the intended
> literary work identified by the supplied target title and author?

This review follows the target-attribution semantics and reason taxonomy of:

    docs/OPENALEX_PRECISION_REVIEW_PROTOCOL_V1.md

It does NOT evaluate:

- scholarly-visibility inclusion;
- document type or document scope;
- whether the record is primary or secondary literature;
- substantive analysis versus brief mention;
- final visibility counting.

A primary-text record, bibliography, review, or brief reference may therefore
still be VALID_TARGET_REFERENCE if it genuinely refers to the target work.

## Frozen review population

Review exactly the 800 candidates in the previously frozen PRIMARY pair-level
random sample.

The SECONDARY work-diagnostic sample is not part of this authoritative
baseline-precision adjudication.

## Blinding

The human reviewer must not use, inspect, or infer during adjudication:

- LLM first-pass judgments;
- LLM confidence;
- LLM reason codes;
- primary/secondary sampling diagnostics beyond the fact that this is the
  frozen PRIMARY review set;
- hit location;
- title-token count;
- work candidate volume;
- retrieval-risk features;
- query provenance.

The human packet is constructed without reading the LLM first-pass artifact.

## Evidence available to the reviewer

Use only the supplied frozen review-row evidence:

- target title;
- target author;
- OpenAlex record title;
- OpenAlex abstract;
- publication year/date;
- DOI;
- project_work_id and OpenAlex Work ID as identifiers.

Do not browse the web or use external sources for v1 adjudication.

If the supplied evidence is genuinely insufficient, use UNCERTAIN rather than
filling the gap from outside knowledge.

## Primary judgments

Exactly one:

- VALID_TARGET_REFERENCE
- INVALID_TARGET_REFERENCE
- UNCERTAIN

### VALID_TARGET_REFERENCE

The supplied evidence sufficiently establishes that the OpenAlex record refers
to the intended target literary work.

Substantive discussion is not required.

### INVALID_TARGET_REFERENCE

The supplied evidence establishes that the apparent match does not refer to the
intended literary work.

### UNCERTAIN

The supplied evidence does not reliably establish either validity or invalidity.

Missing abstract alone does not require UNCERTAIN if the OpenAlex record title
sufficiently identifies the target.

## Reason codes

For VALID_TARGET_REFERENCE:

- DIRECT_TARGET_REFERENCE
- VALID_TITLE_VARIANT
- VALID_CONTEXTUAL_REFERENCE

For INVALID_TARGET_REFERENCE:

- TITLE_COLLISION_DIFFERENT_WORK
- GENERIC_OR_LEXICAL_TITLE_USE
- AUTHOR_COLLISION_DIFFERENT_PERSON
- TITLE_AUTHOR_UNLINKED_COOCCURRENCE
- WRONG_WORK_SAME_AUTHOR
- ALIAS_NOT_TARGET_EQUIVALENT
- METADATA_TEXT_ARTIFACT
- OTHER

For UNCERTAIN:

- INSUFFICIENT_CONTEXT
- AMBIGUOUS_TARGET_REFERENCE

Use the precedence rules defined in
OPENALEX_PRECISION_REVIEW_PROTOCOL_V1.md.

## Confidence

Exactly one:

- HIGH
- MEDIUM
- LOW

Confidence describes support for the chosen judgment, not probability that the
candidate is valid.

## Human-review fields

Complete:

- human_target_attribution_judgment
- human_adjudication_confidence
- human_attribution_reason_code
- human_reviewer_note
- human_reviewer_id
- human_adjudicated_at_utc

Use reviewer ID:

    haruka_tsutsui

Use UTC ISO-8601 timestamps:

    YYYY-MM-DDTHH:MM:SSZ

Reviewer notes should be concise but should identify the evidence supporting
the decision, especially for INVALID and UNCERTAIN cases.

## Independence

Each candidate is an independent judgment unit.

Repeated project works, similar abstracts, repeated titles, or similar evidence
patterns do not authorize automatic propagation of one judgment to another.

## Statistical role

The final baseline pair-level target-attribution precision estimate is computed
from these 800 human judgments, not from the LLM first pass.

The separately frozen secondary diagnostic sample must not be pooled
unweighted with these 800 observations to estimate overall pair-level
precision.

No retrieval policy should be retuned until this PRIMARY human adjudication is
complete and frozen.
