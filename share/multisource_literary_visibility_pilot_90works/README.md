# Multisource Literary Visibility Pilot (90 Works)

Last updated: 2026-08-09

## Overview

This directory contains a provisional pilot dataset of 90 literary works used
to explore literary visibility across multiple sources.

The selection derives from the doctoral reading-list appendix used by McGrath,
Higgins, and Hintze (2018). Records in the working subset were re-audited
before external sharing, and confirmed false bibliographic matches were
excluded.

The resulting dataset should not be interpreted as an exhaustive or definitive
list of canonical literature. Its purpose is to test how different indicators
of literary visibility align or diverge across the same set of works.

## Files

- `literary_visibility_pilot_90works.csv`: 90-work multisource pilot dataset
- `README.md`: dataset overview and column definitions
- `METHODS.md`: short description of matching and indicator construction

## Indicators included

The current pilot includes indicators from:

- JSTOR Language & Literature
- OpenAlex
- Open Library
- HathiTrust
- Wikidata

These indicators capture different aspects of visibility and should not be
treated as interchangeable measures of literary value or canonicity.

## JSTOR indicator

For JSTOR, research-article titles in **Language & Literature** are first
matched against literary work titles. Candidate matches are then filtered for
relevance in order to reduce false matches caused by ambiguous titles.

The main JSTOR indicator is:

- `jstor_ll_relevant_count`: candidate article titles classified as referring
  to the target literary work

The candidate, unclear, and unrelated counts are also included for
transparency.

See `METHODS.md` for a short description of the procedure.

## Bibliographic structure

The dataset preserves the original selection metadata and the matched
bibliographic metadata in separate columns.

This distinction is intentional because the source list and bibliographic
records may differ in title form, author spelling, or publication year.

## Column definitions

| Column | Description |
| --- | --- |
| `selection_title` | Title recorded in the source reading-list appendix |
| `selection_author` | Author recorded in the source appendix |
| `selection_year` | Publication year recorded in the source appendix |
| `matched_title` | Title of the matched Open Library work record |
| `matched_author` | Author associated with the matched Open Library work record |
| `openlibrary_record_year` | Year associated with the matched Open Library record |
| `openlibrary_work_key` | Open Library work identifier used as the main bibliographic link |
| `openalex_title_author_count` | Provisional OpenAlex title-and-author visibility count |
| `openalex_literary_terms_count` | More conservative OpenAlex count using literary-context terms |
| `openalex_status` | Interpretation status for the provisional OpenAlex value |
| `openalex_risk_flags` | Diagnostic flags associated with OpenAlex matching |
| `openlibrary_edition_count` | Number of Open Library edition records associated with the matched work |
| `hathitrust_volume_count` | Number of HathiTrust volumes matched by the current workflow |
| `wikidata_qid` | Wikidata work identifier where resolved |
| `metadata_flags` | Diagnostic notes concerning bibliographic or source matching |
| `bibliographic_note` | Human-readable note on selected bibliographic discrepancies |
| `jstor_ll_candidate_count` | JSTOR Language & Literature research-article title candidates before relevance filtering |
| `jstor_ll_relevant_count` | Candidate titles classified as referring to the target literary work |
| `jstor_ll_unclear_count` | Candidate titles for which the article title alone is insufficient to determine relevance |
| `jstor_ll_unrelated_count` | Candidate titles classified as unrelated to the target literary work |

## OpenAlex status values

| Status | Interpretation |
| --- | --- |
| `use_title_author` | Title-and-author count retained as the provisional OpenAlex value |
| `use_with_warning_short_title` | Count retained, but the title is short or generic |
| `use_with_warning_risky_author` | Count retained, but the author name creates elevated matching risk |
| `zero_title_author` | No records remained after the title-and-author matching stage |

OpenAlex values remain provisional and are included primarily for exploratory
cross-source comparison.

## Source of the selection metadata

The selection metadata was derived from the appendix to:

McGrath, Laura, Devin Higgins, and Arend Hintze. “Measuring Modernist Novelty.”
*Journal of Cultural Analytics*, vol. 3, no. 1, 2018.
https://doi.org/10.22148/16.027

## Important limitations

- This is a provisional pilot dataset, not a formal research-data release.
- JSTOR and OpenAlex values are visibility indicators, not exhaustive counts of
  scholarship about each work.
- Open Library edition counts are bibliographic indicators rather than direct
  measures of circulation or readership.
- HathiTrust values represent volumes identified by the current matching
  workflow and should not be interpreted as complete global holdings counts.
- A blank `wikidata_qid` indicates that the work remains unresolved in this
  pilot; it does not imply that no Wikidata item exists.
- Goodreads-derived values are not included because the underlying UCSD Book
  Graph data has redistribution restrictions.
- Some records retain unresolved differences between the source selection
  metadata and matched bibliographic records.

## Project context

This pilot is a small public output from a larger project examining literary
visibility across multiple bibliographic, scholarly, and cultural sources.
