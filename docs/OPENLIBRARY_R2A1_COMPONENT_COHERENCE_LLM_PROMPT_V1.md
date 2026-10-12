# Open Library R2+A1 component coherence review — LLM prompt v1

## Purpose

Assess whether the supplied Open Library Edition records
plausibly represent one bounded bibliographic/editorial
publication family or multiple distinct publication families.

This is a diagnostic assessment, not a project-level
identity decision or a corpus-scope decision.

## Evidence

Use ONLY the supplied Edition metadata:

- edition_key
- edition_title
- edition_subtitle
- publish_date
- publishers
- edition_author_keys
- number_of_pages
- predecessor_author

Do not browse the web.
Do not infer editors, contents, ISBNs, original publication
dates, or contributor roles that are not supplied.

Edition author keys may be inherited from an erroneous
Open Library Work cluster. They do not independently establish
authorship of every Edition.

The Editions have already been grouped by an earlier process.
Do NOT assume that the grouping is correct.

Do NOT use previous routing decisions, component definitions,
human notes, or the number of Editions as proof of identity.

## Coherence classification

Choose one case-level decision:

ONE_PUBLICATION_FAMILY:
The metadata reasonably supports treating all supplied
Editions as manifestations or editions of one bounded
publication or editorial compilation.

MULTIPLE_PUBLICATION_FAMILIES:
The metadata positively indicates two or more materially
different publications, compilations, or editorial units.

INSUFFICIENT_EVIDENCE:
The available metadata cannot support either conclusion.

NOT_ASSESSABLE_SINGLE_EDITION:
Only one Edition is supplied. No cross-Edition coherence
assessment is possible.

Different publication years, publishers, formats, or minor
title variants do not by themselves establish different works.

Identical generic titles do not by themselves establish
the same work.

An omnibus or anthology remains a publication-level unit.
Do not decompose it into its constituent literary texts.

## Proposed internal groups

If the supplied evidence supports a subdivision, propose
publication-level groups using local identifiers G01, G02, etc.

Each proposed group must identify its Edition keys exactly.

Do not put an Edition into multiple groups.

An Edition with insufficient evidence should be placed
in the unresolved Edition list rather than forced into a group.

If there is insufficient evidence to determine even a
provisional grouping, leave the groups empty and mark all
Editions unresolved.

Do not assume the earlier component is one coherent
publication simply because no alternative is obvious.

## Authorship and subject relationship

For each proposed group, classify:

AUTHOR_TEXT:
Evidence supports a publication containing writings by
the stated predecessor author.

ABOUT_AUTHOR:
Evidence supports a publication primarily about that author,
rather than primarily containing the author's writings.

MIXED:
Evidence supports both categories in a materially
mixed publication.

UNKNOWN:
The metadata cannot establish the relationship.

Do not equate an edition_author_key with proof that an
Edition consists of writings by that author.

A title such as "a collection of critical essays" may refer
either to criticism written by the author or to essays
about the author. If the metadata does not distinguish them,
use UNKNOWN and flag the issue.

## Conservative handling

Use insufficient-evidence judgments whenever metadata
does not determine the publication's editorial identity.

Explicitly flag suspected:

- different edited selections
- mixed collections or omnibuses
- author-as-subject versus author-as-writer confusion
- generic-title ambiguity
- missing editorial information
- format differences requiring content verification

A diagnostic flag is not a factual assertion.

## Output requirements

Return structured JSON according to the separately frozen
runner schema.

The result must contain:

- case_id
- coherence_decision
- confidence: HIGH, MEDIUM, or LOW
- proposed_groups
- unresolved_edition_keys
- diagnostic_flags
- concise evidence_note

Each proposed_group must contain:

- local_group_id
- edition_keys
- provisional_label
- authorship_relation
- evidence_note

All supplied Edition keys must be accounted for exactly once,
either in one proposed group or as unresolved.

Use only supplied evidence in notes.
Do not invent new Project W IDs or source entity IDs.
Do not claim to update the existing identity registry.

## Interpretation

This is independent assessment of metadata coherence
CONDITIONAL ON the previously generated Edition grouping.

It is not independent source sampling and does not establish
the correctness of the earlier routing.

The results are provisional and subject to targeted
human bibliographic review.
