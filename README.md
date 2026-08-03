# canon-pipeline

A research pipeline for cross-database bibliographic entity resolution and the study of literary visibility and canonicity.

This repository documents an ongoing doctoral research project examining approximately 35,000 English-language fiction works first published between 1880 and 1950. The project connects bibliographic records with multiple indicators of literary visibility, including scholarly attention, bibliographic circulation, research-library representation, reader reception, and linked-data visibility.

Rather than producing a single ranking of literary value or canonicity, the project examines where different forms of visibility align, overlap, or diverge.

## Public pilot dataset

A provisional dataset of 90 literary works is available here:

[`share/literary_visibility_pilot_90works/`](share/literary_visibility_pilot_90works/)

The pilot currently includes indicators derived from:

- JSTOR Language & Literature
- OpenAlex
- Open Library
- HathiTrust
- Wikidata

The source test set was derived from a doctoral reading-list appendix. Before external sharing, 98 matched records were re-audited and eight confirmed false Open Library matches were excluded. The retained 90 records form a provisional sharing subset rather than a definitive list of canonical literature.

For field definitions, matching notes, and limitations, see the README inside the pilot-data folder.

## Research workflow

The full working record of data collection, entity resolution, validation, enrichment, and audit decisions is documented in [`WORKFLOW.md`](WORKFLOW.md).

This is a living research repository. Methods, counts, and record links may change following further bibliographic verification.

## Data and reuse notes

The publicly shared pilot does not include Goodreads-derived values because the underlying UCSD Book Graph data has redistribution restrictions.

JSTOR and OpenAlex values should be treated as visibility indicators rather than exhaustive counts of scholarship about each literary work. OpenAlex status and risk flags should remain attached to the corresponding values.

Some large source datasets and derived files are stored locally and are not included in this repository because of file size or redistribution restrictions.

## Source of the pilot selection

McGrath, Laura, Devin Higgins, and Arend Hintze. “Measuring Modernist Novelty.” *Journal of Cultural Analytics*, vol. 3, no. 1, 2018, doi:10.22148/16.027.

## Project status

Work in progress. The public files are intended to support methodological discussion and exploratory collaboration, not to serve as a final research-data release.

## Contact

Haruka Tsutsui  
National Institutes for the Humanities, Japan  
PhD candidate, University of Tokyo
