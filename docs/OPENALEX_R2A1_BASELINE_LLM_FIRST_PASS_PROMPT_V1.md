# OpenAlex R2+A1 Baseline Validation LLM First-Pass Prompt v1

You are performing a provisional blind target-attribution adjudication
of OpenAlex retrieval candidates for literary works.

This task evaluates RETRIEVAL TARGET ATTRIBUTION ONLY.

Primary question:

Does the supplied OpenAlex record genuinely refer to the specific
target literary work identified by `target_title` and `target_author`?

Use only the information supplied for the candidate.

Especially use:

- `target_title`
- `target_author`
- `openalex_display_name`
- `openalex_abstract`
- publication metadata when useful

Do not browse the web.
Do not use outside knowledge to fill gaps.
Do not infer validity merely because the record concerns the same author,
period, national literature, genre, topic, or related work.

Do not classify scholarly visibility, document scope, or mention strength.

In particular:

- a bibliographic record can still be a valid target reference;
- a primary-text record can still be valid for target attribution;
- a review can still be valid for target attribution;
- a non-scholarly record can still be valid for target attribution;
- a brief mention can still be valid for target attribution;
- substantive discussion is NOT required for target attribution.

Those document-scope and visibility decisions belong to a later stage.

## Primary judgments

Assign exactly one:

### VALID_TARGET_REFERENCE

Use when the supplied evidence sufficiently establishes that the
OpenAlex record refers to the intended literary work.

Exact bibliographic wording is not required.

An explicit reference to the source work remains valid when the
OpenAlex record primarily discusses an adaptation, another work,
another author, or a broader topic, provided that the supplied evidence
actually identifies the target work.

### INVALID_TARGET_REFERENCE

Use when the supplied evidence establishes that the apparent match
does not refer to the intended literary work.

Examples include:

- an ordinary lexical use of the title expression;
- a different work with the same or similar title;
- a different work by the same author;
- a different person sharing the author name;
- title and author appearing independently without semantic linkage;
- a metadata/text artifact producing a false match.

### UNCERTAIN

Use when the supplied evidence genuinely cannot establish either
validity or invalidity.

Do not convert missing evidence into INVALID.

Missing abstract alone does not imply UNCERTAIN if the OpenAlex title
itself sufficiently identifies the target.

## Work-identity rules

1. An explicit reference to the source literary work remains VALID in
   discussion of an adaptation.

2. Evidence referring only to an adaptation or derivative does not by
   itself establish a reference to the source work merely because title
   or author strings overlap.

3. If source versus derivative identity cannot be resolved, use
   UNCERTAIN.

4. Distinguish collections from component works. A reference to one
   component does not automatically establish reference to the whole
   collection.

5. Supported spelling, abbreviated-title, expanded-title, translation,
   or other title variants may be VALID when the supplied evidence
   sufficiently identifies the same underlying work.

6. Generic or genre-like lexical use plus a nearby author name is not
   sufficient.

7. An unnamed quotation or passage may support VALID attribution only
   when the supplied context sufficiently identifies its source as the
   target work.

8. Editor, compiler, translator, or contributor roles neither
   automatically establish nor automatically invalidate work identity.

## Reason taxonomy

Exactly one reason code must be used and must be compatible with the
primary judgment.

For VALID_TARGET_REFERENCE:

- DIRECT_TARGET_REFERENCE
  Explicit title/work and author linkage identifies the target.

- VALID_TITLE_VARIANT
  A supported alternate spelling, shortened/expanded title, translation,
  or equivalent title denotes the target.

- VALID_CONTEXTUAL_REFERENCE
  Context sufficiently identifies the target without a direct
  bibliographic naming formula.

For INVALID_TARGET_REFERENCE:

- TITLE_COLLISION_DIFFERENT_WORK
  The matching title denotes a distinct work.

- GENERIC_OR_LEXICAL_TITLE_USE
  The matching expression is ordinary vocabulary, a generic expression,
  genre/category language, or otherwise lexical rather than the target.

- AUTHOR_COLLISION_DIFFERENT_PERSON
  The matching author name denotes a different person.

- TITLE_AUTHOR_UNLINKED_COOCCURRENCE
  The title expression and author both occur, but the supplied evidence
  does not semantically link them as the target work.

- WRONG_WORK_SAME_AUTHOR
  A distinct work by the same author is identified.

- ALIAS_NOT_TARGET_EQUIVALENT
  The supplied target/title relationship is established not to denote
  the same underlying work.

- METADATA_TEXT_ARTIFACT
  A metadata or text artifact causes the apparent match.

- OTHER
  Invalidity is established for another reason. Explain briefly.

For UNCERTAIN:

- INSUFFICIENT_CONTEXT
  Information is inadequate and no specific competing identity can be
  established.

- AMBIGUOUS_TARGET_REFERENCE
  Specific competing work identities remain unresolved.

## Reason precedence

When applicable:

- prefer GENERIC_OR_LEXICAL_TITLE_USE over generic unlinked co-occurrence;
- use WRONG_WORK_SAME_AUTHOR only when a distinct work by that same
  author is actually identified;
- use TITLE_AUTHOR_UNLINKED_COOCCURRENCE when title and author both occur
  without semantic linkage after more specific causes are excluded;
- use METADATA_TEXT_ARTIFACT only when an artifact itself causes the
  false attribution;
- use AMBIGUOUS_TARGET_REFERENCE when specific competing identities
  remain unresolved;
- use INSUFFICIENT_CONTEXT when evidence is inadequate without an
  identifiable competing work.

For valid cases:

- prefer VALID_TITLE_VARIANT when title equivalence is the material issue;
- otherwise use DIRECT_TARGET_REFERENCE for direct identifying linkage;
- use VALID_CONTEXTUAL_REFERENCE for indirect but sufficient context.

## Confidence

Assign one:

- HIGH
- MEDIUM
- LOW

Confidence describes support for the chosen judgment.
It is not a probability that the candidate is valid.

A high-confidence UNCERTAIN judgment is possible when the evidence
clearly establishes unresolved ambiguity.

## Output

Return exactly one structured result containing:

- `baseline_candidate_id`
- `llm_first_pass_judgment`
- `llm_first_pass_reason_code`
- `llm_first_pass_confidence`
- `llm_first_pass_note`

The note must be concise and identify the supplied textual evidence that
supports the decision.

Do not output or infer a final human judgment.

This is a provisional LLM first pass only.
