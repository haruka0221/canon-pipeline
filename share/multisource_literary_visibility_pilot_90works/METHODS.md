# Methods

This pilot brings together several indicators of literary visibility for a
small set of literary works. The indicators are intended for comparison across
sources rather than as definitive measures of literary value or canonicity.

## Work matching

Records are linked at the work level using bibliographic information such as
title, author, and publication year.

Open Library work identifiers are used as the main bibliographic link within
the pilot. Wikidata QIDs are included where a work could be resolved reliably
and provide a useful identifier for comparison with external literary lists.

## JSTOR

The JSTOR indicator is based on research articles associated with
**Language & Literature**.

Candidate articles are retrieved when the normalized literary work title
appears as a phrase in the article title. Because title matching can produce
false positives for short or ambiguous titles, candidates are then classified
as:

- `relevant`: the article title indicates that the literary work itself is
  being discussed;
- `unrelated`: the match refers to something else, or uses the same words only
  generically, metaphorically, or incidentally;
- `unclear`: the article title alone does not provide enough evidence to decide.

The main JSTOR visibility indicator is `jstor_ll_relevant_count`.

The candidate, unclear, and unrelated counts are also retained so that the
effect of relevance filtering remains visible.

## OpenAlex

The pilot includes provisional OpenAlex indicators based on title-and-author
matching, together with a more conservative literary-context count.

These values should be treated as exploratory visibility indicators rather
than exhaustive counts of scholarship.

A separate prototype in this repository explores candidate-level relevance
classification for OpenAlex records.

## Open Library

`openlibrary_edition_count` counts edition records associated with the matched
Open Library work.

It is used as a bibliographic visibility indicator, not as a direct measure of
readership or circulation.

## HathiTrust

`hathitrust_volume_count` records HathiTrust volumes identified by the current
bibliographic matching workflow.

It should be interpreted as a holdings / bibliographic availability indicator,
not as a direct circulation measure.

## Wikidata

`wikidata_qid` gives the Wikidata work identifier where a reliable match was
available.

The QID can be used to connect this pilot with literary lists and other
enrichment sources that also use Wikidata identifiers.

## Status

This is a provisional research dataset intended for methodological testing and
cross-source comparison. Individual records and matching procedures may be
revised as the larger project develops.
