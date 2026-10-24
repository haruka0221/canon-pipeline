# canon-pipeline

A research pipeline for cross-database bibliographic entity resolution and the study of literary visibility and canon formation.

## Project overview

This repository documents an ongoing doctoral research project investigating how literary works gain, maintain, or lose visibility across different cultural and institutional contexts.

The project focuses on English-language fiction associated with the period 1880–1950. Its initial research population comprises 34,789 Open Library Work records, which are being verified and resolved into distinct literary works.

By connecting bibliographic records and other forms of evidence across multiple databases, the project examines several dimensions of literary visibility:

- Scholarly attention: JSTOR and OpenAlex
- Bibliographic representation and republication: British Library catalogue and Open Library
- Reader reception: Goodreads (UCSD Book Graph)
- Educational visibility: Open Syllabus

Wikidata provides additional linked-data identifiers and metadata for connecting records across sources.

Rather than producing a single ranking of literary value or canonicity, the project aims to map where these different forms of visibility overlap, diverge, or remain independent.

## Research approach

A central component of the project is bibliographic entity resolution: identifying when records from different databases refer to the same literary work.

The pipeline distinguishes source-specific records from project-level literary works and preserves information about matching decisions, unresolved identities, and data provenance.

It also develops and evaluates source-specific methods for retrieving and validating evidence of literary visibility.

The British Library catalogue is being investigated as a source of bibliographic evidence concerning publication history and later editions. This work is currently under methodological development.

## Public pilot dataset

A provisional dataset of 90 literary works is available here:

[Multisource Literary Visibility Pilot (90 Works)](share/multisource_literary_visibility_pilot_90works/)

The dataset includes indicators derived from:

- JSTOR Language & Literature
- OpenAlex
- Open Library
- HathiTrust
- Wikidata

This pilot reflects an earlier stage of the project and is distinct from the broader research framework described above.

The original test set was derived from a doctoral reading-list appendix used by McGrath, Higgins, and Hintze (2018). Before external sharing, 98 matched records were re-audited and eight confirmed false Open Library matches were excluded.

The retained 90 records constitute a provisional subset for methodological comparison, not a definitive list of canonical literary works.

For field definitions, matching procedures, and limitations, see the [pilot dataset README](share/multisource_literary_visibility_pilot_90works/README.md).

## Research workflow and documentation

The development of the pipeline, including data collection, entity resolution, validation, and methodological decisions, is documented in [WORKFLOW.md](WORKFLOW.md).

The repository preserves intermediate results and audit records to make the research process traceable and open to methodological review.

## Data availability and limitations

The publicly shared pilot does not include Goodreads-derived values because of redistribution restrictions associated with the underlying UCSD Book Graph dataset.

Bibliographic record counts, scholarly references, reader ratings, and syllabus appearances measure different forms of visibility. None should be interpreted as a direct or exhaustive measure of literary value, readership, or canonical status.

Some large source datasets and derived files are maintained outside this repository because of storage requirements or redistribution restrictions.

All publicly shared datasets should be treated as provisional unless explicitly identified as finalized releases.

## Reference for the pilot selection

McGrath, Laura, Devin Higgins, and Arend Hintze. “Measuring Modernist Novelty.” *Journal of Cultural Analytics*, vol. 3, no. 1, 2018. https://doi.org/10.22148/16.027.

## Project status

Work in progress. This repository is intended to document the development of research methods and data, support methodological discussion, and facilitate exploratory collaboration.

## Contact

Haruka Tsutsui  
Project Assistant Professor, National Institutes for the Humanities (NIHU), Japan  
PhD Candidate in English Literature, University of Tokyo
Mail: tsutsui@nihu.jp
ORCID: https://orcid.org/0009-0005-3008-7041
