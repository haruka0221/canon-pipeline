# Open Library Query-Author Review Guidelines

Last updated: 2026-09-28
Status: CALIBRATION GUIDELINES — not yet a frozen production selection rule

## 1. Purpose

This review evaluates Open Library author evidence for use in OpenAlex
retrieval.

The review question is:

> Is Open Library author ordinal 0 safe and useful as an author
> disambiguator for retrieving scholarly documents about this target
> literary work?

This is a retrieval decision. It is not an attempt to establish a
definitive literary-historical authorship record.

The source-native Open Library author evidence remains unchanged.

## 2. Review population

The frozen Open Library author source contains 34,789 current analysis
targets.

The first-stage audit classified them as:

- 32,704 SINGLE_RESOLVED
- 1 SINGLE_UNRESOLVED
- 354 NO_AUTHOR_ENTRY
- 1,730 MULTI

Human review is currently focused on a stratified sample of 155 MULTI
targets:

- 50 MULTI_BASELINE
- 50 MULTI_LOW
- 50 MULTI_MEDIUM
- all 5 MULTI_HIGH

The first calibration batch contains OAR0001–OAR0020.

## 3. Meaning of ordinal0_retrieval_safe

### YES

Use YES when ordinal 0 is a sufficiently reliable and useful author or
responsibility name for an OpenAlex title+author retrieval query.

YES does not mean:

- ordinal 0 is the only author;
- ordinal 0 is necessarily the original literary author;
- other author edges are incorrect.

Examples that may receive YES include:

- a straightforward literary author;
- a valid co-author;
- a valid editor or compiler when the target itself is an anthology or
  compilation identified through that responsibility;
- one clean author record among duplicate Open Library records for the
  same person.

### NO

Use NO when ordinal 0 should not be used as the OpenAlex author
disambiguator.

Typical reasons include:

- publisher, printer, production company, or editing-service record;
- missing Author record;
- malformed or materially erroneous author string when a better Open
  Library author edge exists;
- illustrator, introducer, translator, editor, or other contributor
  incorrectly occupying ordinal 0 for a target whose relevant literary
  author is represented elsewhere;
- ordinal 0 is otherwise likely to narrow retrieval toward the wrong
  entity or work.

### UNCLEAR

Use UNCLEAR when available evidence is insufficient to determine
whether ordinal 0 is retrieval-safe.

UNCLEAR should be retained rather than forcing a YES or NO decision.

Possible reasons include:

- ambiguous responsibility relationships;
- insufficient bibliographic evidence;
- conflicting source evidence;
- uncertainty about the identity or scope of the target itself.

## 4. recommended_query_author_action

### USE_ORDINAL0

Ordinal 0 is the selected Open Library-derived retrieval author.

### USE_OTHER_ORDINAL

Ordinal 0 is not safe, but one or more other Open Library author edges
provide a better retrieval author.

The selected ordinal(s) must be recorded explicitly.

### USE_MULTIPLE_OL_AUTHORS

More than one Open Library author edge is independently useful for
retrieval.

This does not mean that all names must be placed into one query.
Downstream query-registry construction may create separate
title+author query routes for the selected authors.

### NO_OL_AUTHOR

The available Open Library author edges do not provide a sufficiently
safe author string for retrieval.

This does not imply that the work has no author. It means only that no
Open Library-derived query author is selected under this review.

### UNCLEAR

No production retrieval action should yet be derived from the reviewed
author evidence.

## 5. review_case_types

One or more case types may be recorded.

### straightforward

Ordinal 0 is an ordinary usable retrieval author without a material
authorship complication affecting retrieval.

### duplicate_same_person

Multiple Open Library Author records appear to represent the same
person.

The cleanest useful source-native name may be selected, but source
records remain distinct.

### name_variant_or_error

The ordinal-0 string appears malformed, erroneous, or substantially
inferior to another Open Library representation of the same person.

### translator_editor_adapter

Translation, editing, adaptation, introduction, illustration, or
similar contribution complicates the Work.authors relation.

This label does not automatically imply YES or NO.

### coauthor_collaborator

More than one person has a legitimate creative or bibliographic
responsibility relevant to retrieval.

### anthology_collection

The target is an anthology, collection, compilation, or similar work
where editor/compiler responsibility may legitimately be useful for
retrieval.

### corporate_or_institutional_author

An organization may represent legitimate corporate authorship or
responsibility.

An organizational name is therefore not automatically rejected.

### publisher_or_production_entity

An author edge represents a publisher, printer, production company,
editing service, or comparable entity and is not appropriate as the
literary retrieval author.

### missing_author_record

The Work references an Open Library Author ID for which the frozen
Authors snapshot contains no corresponding record.

### target_or_scope_problem

The target itself raises a separate identity or literary-scope issue.

This flag must not silently alter the source population or identity
layer. Scope resolution remains a separate decision.

### other

A material case not captured above.

## 6. Evidence policy

### PACKET_ONLY

Use when the frozen Open Library evidence is sufficient for the review
decision.

### EXTERNAL_BIBLIOGRAPHIC

Use when the decision depends primarily on independent bibliographic
evidence.

### PACKET_AND_EXTERNAL

Use when both the frozen Open Library evidence and independent
bibliographic evidence materially support the decision.

External evidence should be recorded in `review_evidence_refs`.

External evidence is used to adjudicate the review sample. It does not
replace or rewrite the frozen Open Library source layer.

## 7. Separation of decisions

The following questions must remain separate:

1. What author relationships does Open Library record?
2. Is ordinal 0 safe for OpenAlex retrieval?
3. Which Open Library author name(s), if any, should generate retrieval
   queries?
4. Is the target itself within the literary population or otherwise
   correctly scoped?
5. What is the definitive literary-historical authorship of the work?

The current review directly addresses questions 2 and 3 only.

## 8. Calibration status

Calibration batch OAR0001–OAR0020 produced:

- YES: 13
- NO: 7
- UNCLEAR: 0
- remaining PENDING: 135

Recommended actions in the calibration batch:

- USE_ORDINAL0: 10
- USE_MULTIPLE_OL_AUTHORS: 3
- USE_OTHER_ORDINAL: 3
- NO_OL_AUTHOR: 4

These calibration results inform review consistency but do not yet
constitute the production `query_author_selection_rule_v1`.

The production rule will be considered only after completion and
analysis of the full human-review sample.
