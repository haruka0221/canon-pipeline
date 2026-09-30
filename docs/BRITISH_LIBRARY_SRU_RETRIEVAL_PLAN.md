# British Library Catalogue Retrieval: Research Context, Findings, and Implementation Plan

Date: 2026-09-30\
Project: Doctoral dissertation / `canon-pipeline`\
Status: planning / pilot completed; production retrieval not yet started

---

## 1. Purpose of this document

This document records the current state of the British Library (BL) catalogue work for the dissertation project and is intended as a durable handoff for future implementation.

It consolidates:

- what was learned directly from correspondence with the British Library;
- what was confirmed experimentally through the BL SRU service;
- what the pilot suggests is methodologically possible;
- what remains uncertain;
- how BL evidence should fit into the existing `canon-pipeline` identity / provenance architecture;
- a cautious plan for moving from the pilot to reproducible large-scale retrieval.

This document should be treated as a planning and methodological note, not as a frozen production release. Exact scripts, logs, manifests, hashes, and later production decisions should live in the repository.

---

# 2. Research question and why BL data matter

The dissertation studies multiple, deliberately separate dimensions of literary visibility. British Library catalogue evidence is potentially useful as a bibliographic / circulation-oriented dimension rather than as a measure of readership, sales, scholarly attention, or teaching frequency.

The BL-specific research question is approximately:

> For literary works first published in the dissertation's historical period, how strongly and how persistently do those works remain represented in the British Library catalogue through later editions, republications, and different formats?

The key point is that the historical period defines the **works being followed**, not the publication dates of all BL manifestations that should be retrieved.

For example, a work first published in 1902 may have BL catalogue records for editions published in 1973, 2007, 2018, 2024, etc. Those later records are part of the phenomenon of interest and should not be discarded merely because they fall outside 1880–1950.

Possible BL-derived evidence therefore includes, at minimum:

- presence / absence of matching BL bibliographic records;
- count of matching BL bibliographic records;
- manifestation / publication dates;
- publishers and places of publication;
- ISBNs and other identifiers;
- edition statements;
- print vs online / other carrier distinctions;
- relationships between print and electronic manifestations;
- persistence of republication across time;
- potentially the diversity of publication channels / formats.

These should not automatically be collapsed into a single “edition count.” A BL bibliographic record is not necessarily equivalent to one conceptual edition.

The interpretation should remain cautious:

- BL catalogue representation is not direct evidence of sales;
- it is not direct evidence of readership;
- it is not a complete census of all historical publication or circulation;
- it may nevertheless provide a valuable large-scale bibliographic trace of persistence, republication, and institutional preservation / representation.

---

# 3. What the British Library provided

The BL supplied access details for two search services.

## 3.1 Z39.50 British National Bibliography search

BL description:

- searches the British National Bibliography (BNB);
- MARC21 syntax;
- authenticated service;
- intended for relatively small-scale cataloguing / library use rather than large-scale extraction.

Technical details supplied by BL:

```text
Host: bl.alma.exlibrisgroup.com
Database: 44BL_MAIN
Port: 1921
Syntax: MARC21
```

Authentication credentials were supplied privately by BL and should **not** be committed to the repository, copied into public documentation, or embedded in scripts. Store them only in an ignored local secrets file or environment variables if Z39.50 is used.

## 3.2 SRU BL Catalogue search

BL supplied the following SRU endpoint:

```text
https://eu06.alma.exlibrisgroup.com/view/sru/44BL_MAIN
```

Settings supplied by BL:

```text
Version: 1.2
Metadata schema: marcxml
Search profile: Custom
```

Custom indexes supplied by BL:

```text
Title Index:     alma.title
Author Index:    alma.creator
Subject Index:   alma.subject
ISBN Index:      alma.isbn
ISSN Index:      alma.issn
Record # Index:  alma.source_record_id
Keyword Index:   alma.all_for_ui
```

For the current project, SRU is the more natural route for programmatic experimentation because:

- it is HTTP-based;
- it returns MARCXML;
- it can be called reproducibly from Python;
- the returned records preserve rich bibliographic metadata.

---

# 4. Terms of use / service constraints learned from BL

## 4.1 Z39.50 terms

The supplied BL Z39.50 terms explicitly state that the service is free and available for non-commercial library / information-science purposes, including academic and scientific research.

The terms also prohibit abusive behavior, including attempts to download the entire database in a way that degrades service.

Important practical implication:

> Academic research use is allowed, but the service must not be treated as an unrestricted bulk-dump endpoint.

## 4.2 What BL said about scale

BL explicitly clarified that:

- both SRU and Z39.50 can search and retrieve records;
- neither service can search tens of thousands of items “at a time”;
- each response is limited in how many records it returns at once;
- BL believed the practical per-response limit to be around 20 records (possibly lower depending on use);
- the services are not designed as large-scale data extraction mechanisms.

BL does **not** provide an open dump of the entire catalogue metadata.

BL sometimes provides custom data extracts to organisations / academics, potentially for a fee.

Examples of extracts BL said it could more normally support:

- all works by a single author;
- a bounded set of records filtered by date;
- a bounded set filtered by format;
- a bounded set filtered by keyword;
- similar limited extracts;
- typically up to a few thousand records.

BL stated that matching a ~35,000-work corpus title-by-title would be unusually labour-intensive for BL staff, likely expensive, and would not provide information that could not in principle be obtained by the researcher through the supplied protocols.

Therefore the working direction is now:

> perform the matching on the project side using SRU, cautiously and sequentially, rather than asking BL staff to perform a title-by-title bulk match.

A smaller, clearly defined custom extract may still be worth discussing later if a suitable subset emerges.

---

# 5. Rate / load considerations

No BL-specific numerical rate limit has yet been confirmed.

A conservative access pattern was discussed for the intended reply to BL:

```text
- sequential requests only;
- no parallel requests;
- approximately 2 seconds between requests as a cautious starting point;
- willingness to slow further if BL prefers.
```

Important:

**The 2-second interval is not an official BL rule.** It is a conservative proposed operating policy pending any further guidance.

Before launching full production retrieval, the project should preserve the latest BL correspondence confirming or modifying the acceptable access pattern.

Even with a fixed delay, large-scale retrieval will generate more requests than the number of literary works because a search with >20 results requires pagination.

Example from the pilot:

```text
84 candidate records
=> approximately 5 SRU requests at maximumRecords=20
```

Therefore production should be resumable, logged, and rate-controlled.

---

# 6. SRU pilot: Heart of Darkness

The main pilot target was Joseph Conrad's *Heart of Darkness*.

## 6.1 Initial title-only search

Query:

```text
alma.title = "Heart of Darkness"
```

Observed result:

```text
283 records
```

This was clearly too broad.

Examples of false / indirect matches included books whose main title was unrelated but which contained “heart of darkness” in a subtitle or table of contents.

Conclusion:

> `alma.title = ...` should be treated as candidate retrieval, not exact work identity.

## 6.2 Testing `==`

Four query forms were compared:

```text
title_phrase
alma.title = "Heart of Darkness"
=> 283 hits

title_exact
alma.title == "Heart of Darkness"
=> 108 hits

title_exact_author_keywords
alma.title == "Heart of Darkness" and alma.creator all "Conrad Joseph"
=> 84 hits

title_exact_author_phrase
alma.title == "Heart of Darkness" and alma.creator = "Conrad, Joseph"
=> 84 hits
```

Important finding:

> `alma.title == "Heart of Darkness"` does **not** behave like a literal equality test against MARC 245$a.

Even after adding the creator condition, the 84 results included:

- anthologies containing the work;
- adaptations;
- an opera based on the novella;
- other records associated with Conrad but not the target manifestation itself.

Therefore the SRU query engine must not be treated as the final identity adjudicator.

## 6.3 Recommended retrieval logic from the pilot

The pilot strongly supports a two-stage architecture:

```text
SRU query
    -> retrieve candidate bibliographic records
    -> parse MARCXML locally
    -> validate title / author / manifestation evidence locally
    -> classify accepted / rejected / ambiguous records
```

This is methodologically preferable to assuming SRU's title / creator indexes implement the project's desired exact matching semantics.

---

# 7. MARC fields confirmed useful in the pilot

The SRU response returned full MARCXML records with useful fields including:

```text
001   BL / Alma record identifier
008   fixed-length metadata including date/language coding
020   ISBN
035   other system / OCLC identifiers where present
100   main personal author
245   title statement
250   edition statement
260   publication information (older practice)
264   production/publication/distribution information
300   physical description
336   content type
337   media type
338   carrier type
490   series statement
500   general notes
505   contents
600   personal-name subject
650   topical subject
651   geographic subject
655   genre/form (when present)
700   added personal contributors
776   additional physical form / related format
AVA   local holdings / availability information in returned BL records
```

The exact field set varies by record and period.

Important empirical finding:

> Genre/form metadata (655) is too sparse to be assumed reliable as the sole way to identify fiction.

In the Heart of Darkness accepted pilot set, most records did not have a usable 655 fiction label. Therefore a BL extract or retrieval strategy that filters to fiction solely using 655 would risk substantial false negatives.

---

# 8. Local validation pilot

The 84 SRU candidates were parsed locally.

A deliberately simple initial acceptance rule was used:

```text
normalized 245$a == "heart of darkness"
AND
normalized 100$a starts with "conrad joseph"
```

Observed classification:

```text
OTHER                       22
EXACT_WORK                  52
TITLE_EXACT_OTHER_AUTHOR    10
```

The label `EXACT_WORK` was a pilot convenience label only. It should not be adopted unchanged as the final production vocabulary because some accepted records include combined editions and other bibliographic complications.

More precise production terminology should distinguish at least:

```text
candidate
accepted_target_manifestation
accepted_target_in_collection
adaptation
related_work
translation
ambiguous
rejected
```

or another explicitly frozen equivalent.

---

# 9. Heart of Darkness accepted-record profile

The 52 pilot-accepted records showed:

```text
Total accepted bibliographic records: 52

Carrier types:
40 volume
12 online resource

Media types:
40 unmediated
12 computer

Language:
52 eng
```

Further exploratory analysis showed:

```text
Records:                 52
Records with ISBN:       51
Distinct ISBN strings:   86
Distinct publication years observed: 27
Observed years:          1971–2024 (not continuous)
```

Approximate MARC 776 relationships in the pilot:

```text
none                     45
has_print_version          4
has_electronic_version     2
other_related_format       1
```

Simple descriptive flags found:

```text
illustrated                 3
large_print                 2
combined_with_other_work    1
```

These figures are exploratory, not yet production metrics.

---

# 10. What the pilot demonstrates conceptually

## 10.1 A BL “record count” is not an edition count

Multiple BL records can exist because of:

- print vs ebook manifestations;
- publisher / year changes;
- format changes;
- ISBN differences;
- large-print editions;
- collected / combined editions;
- cataloguing history;
- potentially duplicated or parallel records.

Therefore:

```text
BL matching bibliographic record count
!=
number of conceptual editions
```

Use terminology such as:

```text
BL matching bibliographic records
BL catalogue manifestations
BL bibliographic presence
```

until a stronger manifestation / edition clustering policy has been validated.

## 10.2 Later publication dates are analytically essential

The pilot made clear that restricting BL records themselves to 1880–1950 would destroy much of the phenomenon of interest.

For a work originally published in the historical period, later reprints and editions are evidence of persistence / continued bibliographic presence.

Therefore distinguish:

```text
work original publication period
vs
BL manifestation publication year
```

This aligns with the wider project rule that event-time semantics must remain explicit.

## 10.3 Presence / absence must not silently become a scope criterion

A work with no BL match must not automatically be treated as:

- outside the dissertation population;
- non-literary;
- a true zero before retrieval quality is evaluated.

BL coverage is itself part of the phenomenon being measured.

---

# 11. Integration with the current canon-pipeline identity architecture

The current project does not treat Open Library Work IDs or any external source ID as the master conceptual work identity.

The current analytical identity unit is project `W`.

At the 2026-09-30 checkpoint:

```text
project_works_v4
32,086 resolved W
32,706 current OL targets assigned to W
2,083 OL targets remain intentionally unresolved
761 unresolved aggregation units
```

BL should therefore be added as another source-specific evidence layer, not as a replacement identity system.

Suggested conceptual relation:

```text
project W
   -> retrieval aliases / author evidence
   -> BL SRU logical query
   -> BL bibliographic candidate records
   -> local target attribution / manifestation classification
   -> BL source evidence
   -> W-level BL visibility summaries
```

For unresolved Open Library targets, preserve a parallel diagnostic lane rather than forcing them into W-level BL visibility.

Suggested semantics:

```text
target_lane = resolved_w | unresolved_source
project_work_id = W... | NULL
```

Do not allow unresolved-source BL evidence to contribute automatically to resolved W-level metrics.

---

# 12. Important project-design consequence: retrieval should be W-aware

The historical Open Library population contains 34,789 current targets, but these are source records, not necessarily 34,789 conceptual literary works.

A naive BL production run of exactly one query per OL record would therefore risk:

- redundant queries for multiple OL records belonging to one W;
- duplicate BL evidence assigned multiple times to the same conceptual work;
- inflated W-level bibliographic visibility;
- inconsistent treatment of unresolved aggregation units.

Recommended direction:

1. build BL retrieval targets from the current project identity release;
2. preserve all OL-derived title aliases attached to each W;
3. deduplicate semantically identical physical BL queries;
4. retain logical query provenance separately from physical execution;
5. merge candidate BL records at the W level only after local attribution.

This mirrors the useful logical-query / physical-execution distinction already established for OpenAlex, without assuming that the exact OpenAlex routes or author policy should be reused unchanged for BL.

Important:

> OpenAlex's frozen query-author selection was designed for OpenAlex retrieval. It should not automatically become the BL author policy without BL-specific calibration.

---

# 13. Proposed BL data model

A source-level BL layer should preserve record-level evidence before aggregation.

## 13.1 Suggested logical query table

Possible fields:

```text
bl_query_id
project_work_id
target_lane
source_alias_id
query_title_raw
query_title_norm
query_author_raw
query_author_norm
query_route
query_string
query_policy_version
created_at
```

## 13.2 Suggested physical execution table

```text
bl_execution_id
normalized_query_signature
query_string
start_record
maximum_records
request_timestamp
http_status
response_record_count
reported_total_records
retry_count
elapsed_ms
raw_response_path
```

## 13.3 Suggested BL bibliographic record table

```text
bl_record_id
marc_001
marc_008
main_title_245a
subtitle_245b
responsibility_245c
main_author_100a
main_author_dates_100d
edition_250
publication_260
publication_264
isbn_020
physical_300
content_336
media_337
carrier_338
notes_500
contents_505
subjects_650
genre_655
contributors_700
related_format_776
raw_marcxml_path
retrieved_at
```

Do not flatten away repeated MARC subfields if they will be analytically useful. For a durable production design, a normalized MARC representation or raw-record archive should remain available alongside any convenient flat table.

## 13.4 Suggested candidate-attribution table

```text
project_work_id
bl_record_id
bl_query_id
title_match_class
author_match_class
manifestation_relation_class
decision
confidence
rule_version
review_status
review_notes
```

This separates retrieval from acceptance.

---

# 14. Candidate-generation strategy to calibrate

The Heart of Darkness pilot suggests a conservative first production candidate route such as:

```text
alma.title == <title alias>
AND
alma.creator <non-exact author query>
```

but this should not be frozen yet.

Need BL-specific calibration across diverse works:

- long distinctive titles;
- short / generic titles;
- works with subtitles;
- works with author-name variants;
- pseudonyms;
- multi-author / editor-heavy records;
- collections;
- translations;
- posthumous republications;
- works with sparse or absent creator indexing;
- obscure works with zero or few candidates.

Compare at least:

```text
alma.title = title
alma.title == title
alma.title == title AND alma.creator all author
alma.title == title AND alma.creator = author phrase
```

Potentially test title-only rescue for works where author indexing fails, but short-title burden must be audited before any uniform production use.

---

# 15. Local matching / classification strategy to develop

Do not rely on SRU result counts directly.

The production pipeline should parse MARC and classify each candidate.

At minimum evaluate:

## 15.1 Title evidence

- 245$a exact normalized match;
- 245$a + 245$b relationship;
- alternate / uniform titles where available;
- collection / anthology title evidence;
- title contained only in 505 contents;
- title occurring only in notes or unrelated fields.

## 15.2 Author evidence

- 100$a main author;
- dates in 100$d;
- relevant 700 added entries;
- editor vs author roles;
- pseudonym / authority variation;
- missing main-author field.

## 15.3 Manifestation relation

Distinguish at least:

- standalone target work manifestation;
- target work combined with other works;
- anthology / collection containing target;
- translation;
- adaptation;
- criticism / secondary work;
- title phrase reused but unrelated;
- ambiguous.

The final dissertation metric may choose to count some classes and exclude others, but the source-level classification should retain the distinctions.

---

# 16. Normalization policy

Do not over-normalize by default.

A reasonable initial BL matching normalization can begin conservatively with:

```text
Unicode NFKC or equivalent normalization
casefold / lowercase
collapse whitespace
strip outer whitespace
controlled punctuation handling
```

Be cautious about:

- removing articles;
- deleting all punctuation;
- stripping diacritics;
- conflating translations;
- treating subtitle variants as exact identity;
- aggressive token sorting.

The Heart of Darkness pilot used a more aggressive punctuation-stripping normalization for exploration. That was useful for pilot classification but should not automatically become the frozen production rule.

---

# 17. Pagination and resumability

BL indicated an approximately 20-record response limit.

Production retrieval must therefore support:

```text
startRecord
maximumRecords
```

and continue until all reported records have been retrieved or an explicit safety cap / routing decision applies.

Every request should be independently resumable.

Recommended state tracking:

```text
PENDING
IN_PROGRESS
COMPLETE
FAILED_RETRYABLE
FAILED_FINAL
SKIPPED_POLICY
```

Do not rerun completed physical requests unnecessarily.

Store enough state that the process can stop and resume after:

- network failure;
- user interruption;
- machine restart;
- rate adjustment;
- BL service error.

---

# 18. Raw-data preservation

For reproducibility, preserve raw SRU responses or raw MARCXML records for all materialized candidate records, subject to the BL terms and project storage policy.

At minimum record:

```text
retrieval timestamp
endpoint
query string
startRecord
maximumRecords
reported numberOfRecords
HTTP status
raw response hash / path
parser version
```

If raw responses are large, consider one file per physical execution or one compressed JSONL/XML archive per run chunk with an index.

Do not rely only on flattened CSV output.

---

# 19. Rate-controlled production implementation

Suggested first implementation principles:

```text
concurrency = 1
request interval = approximately 2 seconds initially
retry with backoff for transient errors
no uncontrolled parallelism
no recursive immediate retry loops
explicit User-Agent if appropriate
checkpoint frequently
```

Again, the 2-second interval is a proposed conservative local policy, not a confirmed BL SLA or rule.

If BL later supplies a different preferred interval, preserve that correspondence and freeze the production rate policy accordingly.

Potential retry policy to calibrate:

```text
HTTP/network transient error
-> wait longer than normal interval
-> bounded retry count
-> log failure
-> continue without losing completed state
```

Never retry parse or logic errors blindly as if they were network failures.

---

# 20. Pilot expansion before production

Do not go directly from one famous Conrad work to the full population.

Create a BL calibration sample that deliberately includes difficult cases.

Suggested sample strata:

```text
famous / high-republication works
mid-visibility works
obscure works
short titles
generic titles
long distinctive titles
multi-author works
collections
works with known translations
works with title collisions
works with corrected OL identity history
works with multiple OL aliases per W
unresolved-source units
```

Manually review enough candidates to estimate:

- candidate precision by query route;
- false positives from title indexes;
- author-index failure patterns;
- usefulness of 100 vs 700;
- prevalence of manifestation duplication;
- effectiveness of title normalization;
- zero-result reliability;
- short-title burden.

Freeze the calibration input before tuning production policy.

---

# 21. Proposed source-specific BL metrics

Do not choose a single final metric prematurely.

Potential W-level summaries include:

```text
bl_record_count_accepted
bl_record_count_print
bl_record_count_online
bl_distinct_isbn_count
bl_distinct_publication_year_count
bl_first_manifestation_year_observed
bl_last_manifestation_year_observed
bl_republication_span_years
bl_distinct_publisher_count
bl_explicit_edition_statement_count
bl_combined_work_record_count
bl_translation_record_count
bl_format_diversity_count
```

Some of these require further normalization / clustering before they are methodologically defensible.

The raw source-level record table should be retained even if the dissertation ultimately uses only a small subset of these metrics.

---

# 22. Publisher and ISBN cautions discovered in the pilot

The exploratory Heart of Darkness script initially concatenated 260/264 subfields before trying to infer the publisher. This produced messy strings such as combined place / publisher / distributor values.

Production code should parse publication fields structurally:

```text
260/264 $a = place
260/264 $b = publisher / distributor
260/264 $c = date
```

Do not infer publisher from a flattened human-readable publication string when the original MARC subfields are available.

Similarly, one MARC record may contain multiple 020 fields / ISBNs.

Therefore:

```text
BL record count != ISBN count
```

and one record should preserve all ISBN values rather than selecting the first one silently.

---

# 23. Fiction filtering caution

Do not use a single BL genre/form field as a hidden corpus filter.

The pilot indicated sparse 655 coverage even among plausible Heart of Darkness manifestations.

The dissertation population is already defined outside BL. BL should be queried as a visibility / bibliographic evidence source for that population.

This is methodologically preferable to rebuilding the dissertation corpus from BL's own genre coverage, which could introduce source-dependent selection bias.

---

# 24. Relationship to project scope and original publication year

The wider project already distinguishes identity from scope and distinguishes original-work year from manifestation publication year.

BL makes that distinction especially important.

For BL evidence:

```text
project scope variable:
    original_work_year / final scope policy

BL event variable:
    manifestation_publish_year
```

Do not use a BL manifestation's 2018 publication date to infer that the conceptual work is a 2018 work.

Conversely, do not discard the 2018 manifestation merely because the project work first appeared in 1902.

---

# 25. Security / credentials

Do not commit BL credentials.

Recommended pattern:

```text
.env                 # ignored
.env.example         # variable names only, no secrets
```

Possible environment variables if Z39.50 is used later:

```text
BL_Z3950_HOST
BL_Z3950_DATABASE
BL_Z3950_PORT
BL_Z3950_USERNAME
BL_Z3950_PASSWORD
BL_SRU_URL
```

The SRU endpoint itself is not a secret, but keeping all service configuration centralized is still useful.

---

# 26. Suggested repository location

If BL becomes a substantial source, create a dedicated method document rather than burying it in a generic notebook.

Suggested paths:

```text
docs/BRITISH_LIBRARY_RETRIEVAL.md
scripts/bl/
derived/bl_calibration/
derived/bl_production/
```

Possible internal structure:

```text
scripts/bl/
    build_bl_query_registry.py
    run_bl_sru_queries.py
    parse_bl_marcxml.py
    build_bl_candidates.py
    classify_bl_candidates.py
    summarize_bl_visibility.py
```

Do not freeze these names until the implementation is actually created.

---

# 27. Suggested milestone sequence

## Milestone A: correspondence / service-policy freeze

- preserve the relevant BL correspondence locally;
- record the allowed / recommended access pattern;
- record the date of the policy observation;
- do not expose credentials.

## Milestone B: BL calibration target set

- derive a stratified sample from current W / unresolved architecture;
- freeze the sample before policy tuning;
- include difficult title / author cases.

## Milestone C: query-route calibration

- compare title / author query variants;
- collect complete paginated candidates;
- manually review a stratified candidate sample;
- estimate false-positive / false-negative patterns.

## Milestone D: local attribution policy

Freeze:

- title normalization;
- author normalization;
- 100 / 700 use;
- standalone vs collection policy;
- translation policy;
- adaptation policy;
- ambiguous-review policy.

## Milestone E: production query registry

- build W-aware logical queries;
- include unresolved-source lane separately;
- deduplicate physical execution signatures;
- preserve alias provenance.

## Milestone F: rate-controlled production retrieval

- sequential requests;
- checkpointed execution;
- full pagination;
- raw-response provenance;
- bounded retries.

## Milestone G: candidate attribution and audit

- apply frozen policy;
- preserve raw and derived evidence;
- audit duplicate BL record assignment across W;
- audit zero-result works;
- audit short-title / generic-title works.

## Milestone H: BL visibility release

Create versioned source-level and W-level artifacts with:

- input project-work release;
- BL observation date;
- query-policy version;
- match-policy version;
- row counts;
- hashes;
- known limitations;
- relevant Git commit.

---

# 28. Immediate next actions

The recommended next actions are:

1. **Do not start the 35k-scale run yet.**
2. Preserve the final BL correspondence about self-service SRU use / rate expectations.
3. Add this BL work to the repository as a dedicated method / planning document.
4. Inspect the current project W + alias artifacts and design a BL calibration sample.
5. Expand the SRU pilot beyond Heart of Darkness.
6. Build a minimal reusable SRU client with:
   - sequential requests;
   - explicit delay;
   - pagination;
   - retry/backoff;
   - raw-response preservation;
   - checkpoint / resume.
7. Freeze a small BL calibration release before tuning matching rules.
8. Only after calibration, construct the W-aware production query registry.

---

# 29. Questions still unresolved

The following questions are not yet settled and should not be silently assumed:

1. What BL-specific request interval does BL prefer for sustained research retrieval?
2. Which SRU query route provides the best recall / precision trade-off across the dissertation population?
3. How often does `alma.creator` fail for legitimate target manifestations?
4. How should 700 contributor evidence be used?
5. How should collections containing the target work be counted?
6. How should translations be treated in the BL visibility measure?
7. How should adaptations be treated?
8. Should print and ebook records count separately in the primary metric?
9. How should likely duplicate / parallel catalogue records be clustered?
10. Which BL-derived metrics will enter the dissertation's final literary-visibility analysis?
11. How should zero-result works be audited before interpreting them as zero BL visibility?
12. What observation date / snapshot semantics should be attached to a live-catalogue SRU retrieval campaign that runs over multiple days?

---

# 30. Core methodological rules to preserve

The following rules should survive future implementation changes:

```text
1. BL record identity is not project literary-work identity.

2. Retrieval is not acceptance.

3. SRU hit count is not the final visibility count.

4. BL bibliographic record count is not automatically edition count.

5. Later manifestations of historical works are analytically relevant.

6. BL source absence must not become a hidden project-scope criterion.

7. Resolve / aggregate at the project W layer, not by blindly treating OL records as independent works.

8. Preserve unresolved-source evidence separately from resolved W visibility.

9. Preserve raw MARC provenance before aggregation.

10. Freeze calibration and production policies explicitly and version them forward.

11. Do not commit credentials.

12. Do not launch large-scale retrieval before service-policy confirmation, calibration, resumability, and audit infrastructure are in place.
```

---

# 31. Compact handoff

The British Library provided authenticated Z39.50 access to BNB and an SRU 1.2 endpoint for the BL catalogue returning MARCXML. BL confirmed that SRU/Z39.50 can be used to search and retrieve records but are not intended for tens-of-thousands-at-once extraction; responses are limited to roughly 20 records and require pagination. BL does not provide an open full-catalogue dump. Staff can sometimes prepare limited custom extracts of up to a few thousand records, potentially for a fee, but a title-by-title match of the dissertation's ~35k-work corpus would be labour-intensive and likely expensive; BL therefore indicated that the same information can instead be obtained by the researcher through individual SRU/Z39.50 searches. A conservative self-service plan is sequential, non-parallel SRU access with a delay (approximately two seconds was proposed locally, but is not an official BL limit) and full resumability / logging.

The Heart of Darkness pilot showed that Alma query operators do not provide project-level exact matching. `alma.title = "Heart of Darkness"` returned 283 hits; `alma.title == "Heart of Darkness"` returned 108; adding Conrad creator evidence reduced this to 84, but still included anthologies, adaptations, and related records. Local MARC parsing using 245$a and 100$a produced an exploratory 52-record accepted set, consisting of 40 print volumes and 12 online resources, all English. These 52 records contained 86 distinct ISBN strings and publication years spanning 1971–2024. Therefore SRU should be used for candidate generation, followed by local MARC-based attribution and manifestation classification. A BL record count must not be called an edition count without further clustering.

BL should be integrated into the existing `canon-pipeline` as a source-specific bibliographic-evidence layer attached to project W, with unresolved-source targets retained in a separate lane. Production retrieval should be W-aware, alias-aware, provenance-preserving, physically deduplicated, paginated, rate-controlled, checkpointed, and calibrated on a diverse frozen sample before the full run.
