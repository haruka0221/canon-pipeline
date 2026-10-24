# FAIR Data and Reuse Statement

Project: canon-pipeline  
Status: Living documentation — work in progress  
Last reviewed: 2026-10-24

## Overview

This document describes the data management, accessibility, interoperability, and reuse practices of the `canon-pipeline` research project, following the FAIR (Findable, Accessible, Interoperable, Reusable) Guiding Principles.

The project combines bibliographic records and indicators of literary visibility from multiple sources. Because these sources differ in their data structures, licensing conditions, and methodological limitations, the availability and reuse conditions of individual datasets may vary.

This document describes current practices and areas for improvement. It does not constitute a formal certification of FAIR compliance.

## F — Findable

The project repository is publicly available at:

https://github.com/haruka0221/canon-pipeline

Publicly shared datasets are accompanied by documentation describing their contents, methods, and limitations.

The repository maintains versioned research artifacts, provenance records, and Git commit histories to support the identification and verification of specific research outputs.

Persistent identifiers such as DOIs may be assigned to selected datasets or releases in the future. The GitHub repository URL should not be treated as a substitute for a dataset-specific persistent identifier.

## A — Accessible

Not all source data and intermediate research outputs can be publicly redistributed.

The project distinguishes between:

- Public research outputs: selected datasets, methodological documentation, scripts, and aggregate results made available through GitHub.
- Restricted source data: records obtained from external services that are subject to usage or redistribution conditions.
- Local research data: large source snapshots and intermediate datasets maintained outside the public repository.

### Public datasets

The [Multisource Literary Visibility Pilot (90 Works)](share/multisource_literary_visibility_pilot_90works/) is currently available for methodological comparison.

The pilot contains provisional indicators from JSTOR, OpenAlex, Open Library, HathiTrust, and Wikidata.

### British Library data

British Library catalogue records are used to investigate bibliographic representation, editions, and republication histories.

The project currently keeps retrieved record-level data outside the public repository as a precaution under the applicable service conditions.

The public repository retains selected research documentation, summaries, identifiers, and provenance information where appropriate. Seven record-containing pilot files were removed from the latest public repository tree; these files remain accessible in earlier Git history. See the project's restricted-files record for details.

The BL component remains under methodological development. Its pilot outputs should not be interpreted as final population-level bibliographic visibility measures.

### Other source restrictions

Goodreads-derived data from the UCSD Book Graph are not included in the public 90-work pilot because of redistribution restrictions.

Other externally obtained metadata, full-text materials, and large source snapshots may also be excluded from public distribution.

Public access to project documentation does not imply unrestricted access to the underlying source records.

## I — Interoperable

The project uses bibliographic identifiers and structured crosswalks to connect records across different databases.

A central distinction is maintained between:

- Source entities: records identified within external databases, such as Open Library or Wikidata.
- Project conceptual works: literary works represented by project-specific identifiers (`W`).
- Identity assertions: evidence-based decisions linking or distinguishing source entities.
- Source-specific evidence: bibliographic, scholarly, educational, and reception-related observations attributed to project works.

External database identifiers are preserved as source evidence rather than treated as authoritative project-wide identifiers.

Project identifiers are maintained through versioned identity releases, with unresolved and ambiguous cases retained where appropriate.

Derived data are generally stored in structured formats such as TSV and Parquet, alongside methodological documentation and provenance records.

The project also distinguishes bibliographic relationships between works, editions, translations, and collections rather than treating every record match as evidence of identical works.

## R — Reusable

The project aims to support the interpretation, verification, and reuse of its published methods and research outputs.

Where available, documentation records:

- Source databases and snapshot dates
- Data collection and matching methods
- Dataset schemas and identifiers
- Validation procedures and human review decisions
- Known limitations and unresolved cases
- Version information and provenance

### Interpretation of indicators

The project's indicators capture different forms of visibility and should not be treated as interchangeable measures.

For example:

- Open Library edition records do not directly measure readership or sales.
- British Library bibliographic records do not necessarily correspond one-to-one with distinct editions.
- JSTOR and OpenAlex retrieval results are not automatically verified counts of scholarly discussion.
- The absence of a database match does not necessarily indicate the absence of literary visibility.

### Licensing and redistribution

Source-specific rights and redistribution conditions must be considered separately from the project's own contributions.

No single open licence is assumed to apply to all files in this repository.

Licensing arrangements for original code, documentation, and derived research datasets will be specified as appropriate following review of the relevant source-data conditions.

Materials obtained under restricted access or redistribution terms are not automatically eligible for republication under an open licence.

## Ongoing improvements

The project is continuing to develop:

- Dataset-specific documentation and provenance records
- Explicit descriptions of access and redistribution conditions
- Versioned identity and matching procedures
- Quality assessments of bibliographic and scholarly evidence
- Persistent identifiers and citation information for selected public releases
- Clearer distinctions between provisional outputs and validated research releases

## Reference

Wilkinson, Mark D., et al. “The FAIR Guiding Principles for Scientific Data Management and Stewardship.” *Scientific Data*, vol. 3, 2016, article 160018. https://doi.org/10.1038/sdata.2016.18.
