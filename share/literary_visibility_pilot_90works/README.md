# Provisional Literary Visibility Pilot Dataset

Last updated: 2026-08-03

## Overview

This directory contains a provisional pilot dataset of 90 literary works used to test a multidimensional approach to literary visibility and canonicity.

The source selection metadata derives from a doctoral reading-list appendix containing 142 works. Before external sharing, 98 records in the current working subset were re-audited. Eight confirmed false Open Library matches were excluded, leaving 90 records in this provisional sharing dataset.

The retained records should not be interpreted as an exhaustive or definitive list of canonical literature.

## Files

- `literary_visibility_pilot_90works.csv`: provisional 90-work dataset
- `README.md`: documentation, field definitions, source information, and limitations

## Bibliographic structure

The dataset preserves selection-list metadata and matched-work metadata in separate columns.

This distinction is intentional because the source list and Open Library occasionally differ in author spelling, title form, or publication year. The dataset does not automatically assume that either source is correct in every case.

## Indicators included

- JSTOR Language & Literature title-based count
- provisional OpenAlex title-and-author count
- conservative OpenAlex literary-terms count
- Open Library edition count
- HathiTrust matched-volume count
- Wikidata QID where resolved

## Column definitions

| Column | Description |
|---|---|
| `selection_title` | Title recorded in the source doctoral reading-list appendix |
| `selection_author` | Author recorded in the source appendix |
| `selection_year` | Publication year recorded in the source appendix |
| `matched_title` | Title of the matched Open Library work record |
| `matched_author` | Author associated with the matched Open Library work record |
| `openlibrary_record_year` | Year associated with the matched Open Library record; this may differ from the original publication year |
| `openlibrary_work_key` | Open Library work identifier used as the primary bibliographic link in this pilot |
| `jstor_language_literature_title_count` | Number of title-based matches in the JSTOR Language & Literature metadata used for this pilot |
| `openalex_title_author_count` | Provisional OpenAlex count based on title-and-author matching |
| `openalex_literary_terms_count` | More conservative OpenAlex count restricted to records containing literary-context terms |
| `openalex_status` | Recommended interpretation status for the OpenAlex count |
| `openalex_risk_flags` | Pipe-separated diagnostic flags describing matching risks or review conditions |
| `openlibrary_edition_count` | Number of Open Library edition records associated with the matched work |
| `hathitrust_volume_count` | Number of HathiTrust volume records matched by the current workflow |
| `wikidata_qid` | Wikidata work identifier where resolved |
| `metadata_flags` | Semicolon-separated notes concerning title, author, year, OpenAlex, or Wikidata discrepancies |
| `bibliographic_note` | Human-readable explanation of selected bibliographic discrepancies |

## OpenAlex status values

| Status | Interpretation |
|---|---|
| `use_title_author` | The title-and-author count is the recommended provisional OpenAlex value |
| `use_with_warning_short_title` | The count is retained, but the title is short or generic and requires caution |
| `use_with_warning_risky_author` | The count is retained, but the author name creates an elevated matching risk |
| `zero_title_author` | No OpenAlex records remained after the title-and-author matching stage |

The OpenAlex status and risk flags should remain attached to their corresponding values in any reuse or analysis.

## Source of the selection metadata

The source selection metadata was derived from the appendix to:

McGrath, Laura, Devin Higgins, and Arend Hintze. “Measuring Modernist Novelty.” *Journal of Cultural Analytics*, vol. 3, no. 1, 2018, https://doi.org/10.22148/16.027.

## Important limitations

- This is a provisional pilot dataset, not a formal research-data release.
- JSTOR and OpenAlex counts are visibility indicators, not exhaustive counts of scholarship about each literary work.
- OpenAlex status and risk flags should not be removed from the corresponding values.
- Open Library record years may reflect record-level or edition-level metadata rather than the original publication year.
- HathiTrust values represent volumes matched by the current workflow and should not be interpreted as complete global holdings counts.
- A blank `wikidata_qid` means that the match remains unresolved in this pilot; it does not prove that no Wikidata item exists.
- Goodreads-derived values are not included because the underlying UCSD Book Graph data has redistribution restrictions.
- Some retained records preserve unresolved differences between the source selection metadata and the matched bibliographic record.

## Project context

This pilot is a small public output from the larger `canon-pipeline` project, which examines approximately 35,000 English-language fiction works first published between 1880 and 1950 across multiple dimensions of literary visibility.

For the full research workflow and audit history, see [`../../WORKFLOW.md`](../../WORKFLOW.md).
