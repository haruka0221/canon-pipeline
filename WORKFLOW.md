# WORKFLOW.md — canon-pipeline
**DCC Digital Curation Workflow Narrative**
Last updated: 2026-03-07
Status: LIVING DOCUMENT — update on every major change

---

## Overview

This pipeline constructs and validates a population of English-language fiction works (1880–1950) for a doctoral dissertation on canonical inequality in modernist literature. The pipeline is structured in four stages: Collection → Filtering → Validation → Enrichment.

**Repository:** https://github.com/haruka0221/canon-pipeline
**Working environment:** WSL (Ubuntu) on Windows, ~/canon-pipeline
**Primary tools:** Python 3, curl, jq, pandas, rapidfuzz

---

## Stage 1: Population Collection (Dump-Based — Main Study)

### Purpose
Construct the definitive population from the Open Library Works dump,
replacing the Search API approach used in the pilot study.
Motivation: OL Search API returns results ranked by internal relevance score,
which correlates with prior attention — a circular method for studying
attention inequality. The dump provides a complete, unbiased snapshot.

### Inputs
- OL Works dump: `https://openlibrary.org/developers/dumps`
- File: `raw/ol_dump/ol_dump_works_{date}.txt.gz` (.gitignore対象)
- Snapshot date must be recorded in `derived/README_population.txt` and this file

### Filter Criteria
1. `first_publish_year`: 1880–1950
2. `language`: eng (note: language field may be absent at Work level — handling TBD at implementation)
3. `subject_keys`: same exclusion rules as pilot study (see Stage 2 below)

### Processing Method
Stream processing (1 line at a time via `gzip.open` + JSONL):
do NOT load entire dump into memory.

### Outputs
| File | Description |
|------|-------------|
| `derived/ol_dump_population_{date}.tsv` | Official main-study population |
| `derived/README_population.txt` | Snapshot date, filter criteria, record count |

### Commands
```bash
# Confirm disk space before download (expanded dump may reach tens of GB)
df -h ~
# Download (replace date with actual filename from developers/dumps page)
wget -P raw/ol_dump/ https://openlibrary.org/data/ol_dump_works_{date}.txt.gz
# Parse and filter
python3 scripts/build_population_from_dump.py
```

### Decision Points
- **Why dump instead of API:** 72 canonical phd_corpus works were absent from
  the top-5,000 API results (e.g. Huckleberry Finn, Dracula, Tess of the D'Urbervilles).
  Direct evidence of search bias documented in pilot study.
- **No manual additions:** phd_corpus works not found in OL will be recorded
  as limitations only — no supplementation.

### Rights / Access
- OL dump data: CC0 (public domain dedication)
- No authentication required; direct download

### Evidence / Logs
- `logs/build_population_from_dump_{date}.log`

---

## Pilot Study: Population Collection (API-Based — Superseded)

### Purpose
Retrieve a large-scale list of fiction works from Open Library (OL) matching the study's temporal and linguistic scope.

### Inputs
- Open Library Search API (`https://openlibrary.org/search.json`)
- Query parameters:
  - `subject=fiction`
  - `first_publish_year=[1880 TO 1950]`
  - `language=eng`
  - `fields=key,title,first_publish_year,author_key,author_name,subject,edition_count`

### Outputs
| File | Description |
|------|-------------|
| `derived/ol_works_population_unique_clean.tsv` | Initial retrieval: 5,000 works (deduplicated) |
| `derived/ol_works_expanded_raw.tsv` | Additional works from offset 5000–14999 |
| `derived/ol_works_expanded_population.tsv` | Merged expanded population (~15,000 works) |

### Commands
```bash
# Initial 5,000 (historical — exact command not recovered)
# Expansion to ~15,000
python3 scripts/expand_population.py
```

### Decision Points
- **Initial limit=5,000:** Set as initial working scope. Post-hoc analysis showed that 72 phd_corpus canonical works were excluded by this limit → expanded to ~15,000.
- **"English" definition:** Works published in English are included regardless of original language (translations such as Chekhov in English are included).
- **OL search sort order:** OL returns results by internal relevance score. The population is NOT a random sample; it is biased toward frequently-edited/well-documented works.

### Rights / Access
- Open Library data is available under CC0 (public domain dedication).
- API access requires a descriptive User-Agent: `HarukaResearch (tsutsui@nihu.jp)`
- No authentication required; rate limiting applied manually (≥0.5s between requests).

### Evidence / Logs
- `logs/expand_population.log`
- `raw/ol_expand/offset_*.json` (API response cache, resumable)

---

## Pilot Study: Population Filtering (API-Based — Superseded)

### Purpose
Remove non-fiction, poetry, drama, and picture books from the OL retrieval using subject_key-based rules.

### Inputs
- `derived/ol_works_population_unique_clean.tsv` (5,000 works)
- `derived/ol_works_expanded_raw.tsv` (expansion works)

### Outputs
| File | Description |
|------|-------------|
| `derived/ol_works_final_population.tsv` | Filtered population: 4,833 works |
| `derived/ol_works_filtered_removed.tsv` | Excluded 167 works |
| `derived/ol_works_augmented_population.tsv` | + 51 phd_corpus supplements = 4,884 works |
| `derived/README_population.txt` | Machine-readable definition of exclusion rules |

### Commands
```bash
python3 scripts/filter_population.py
```

### Exclusion Rules (confirmed, do not change without new audit)
Works are excluded if their `subject_keys` contain **any** of:
```
plays, dramatic_works, scripts, poetry, poems, ballads, stories_in_rhyme,
nonsense_verses, verse, picture_books, literary_criticism, nonfiction,
biography__autobiography
```
AND do **not** contain **any** of:
```
novel, novels, short_stories, literary_fiction, fiction_general,
english_fiction, american_fiction
```

**Keywords explicitly NOT used for exclusion:**
- `drama` — appears on novels set in theatrical contexts (caused false exclusions of Jane Eyre, Martian Chronicles)
- `history_and_criticism` — appears on fiction works
- `fiction` — appears on virtually all works, not discriminative

### Decision Points
- Pre-filter audit (n=200, seed=20260222): 11% NG rate
- Post-filter audit (n=200): 3.5% NG rate; primary residual issue is `first_publish_year` mis-registration, not genre misclassification
- phd_corpus supplement: 51 canonical works confirmed present in OL but excluded by limit=5000 were added directly via work_key lookup

### Rights / Access
- Filtering logic is fully reproducible via `scripts/filter_population.py`
- No external dependencies beyond OL data

### Evidence / Logs
- `derived/ol_works_audit200_seed20260222.tsv`
- `derived/ol_works_audit200_for_review.tsv`
- `derived/ol_works_postfilter_audit100.tsv`

---

## Stage 3: Validation

### 3a. Year Mismatch Audit

**Purpose:** Verify that `first_publish_year` (work-level) is consistent with edition-level `publish_date`.

**Inputs:** 100-work sample from `derived/ol_works_final_population.tsv`
**Outputs:** `derived/year_audit_final.tsv`
**Command:** `python3 scripts/finalize_year_audit.py`

**Result:** matched 98/100, near_match 2/100, mismatch 0/100.
Apparent mismatches were caused by OL returning recent editions first (offset0 bias), not by data errors. Paging to offset50/100 resolved all cases.

**Conclusion:** `first_publish_year` is reliable as population filter criterion. Retrieving earliest edition year requires paging beyond offset0 for works with >50 editions.

---

### 3b. Identifier Coverage Audit

**Purpose:** Measure the availability of external identifiers (OCLC, ISBN, LCCN, ocaid) in OL edition records, to assess feasibility of linking to external databases.

**Inputs:** 100-work sample, editions API (`/works/{key}/editions.json?limit=50`)
**Outputs:** `derived/identifier_audit_offset0.tsv`, `derived/identifier_audit_comparison.tsv`
**Command:** `python3 scripts/audit_identifiers.py`

**Results (work-level, at least one identifier present):**

| Identifier | Coverage |
|---|---|
| ISBN (any) | 96.0% |
| OCLC (any) | 92.0% |
| LCCN | 82.0% |
| Internet Archive (ocaid) | 89.0% |

**Full population OCLC coverage (all 4,833 works):** 92.4% (4,464 works)

---

### 3c. phd_corpus Coverage Audit

**Purpose:** Verify that canonical works (phd_corpus) are present in the OL population.

**Inputs:** `data/phd_corpus.csv` (408 works; 170 in 1880–1950 scope)
**Outputs:** `tmp/phd_missing_ol_search.tsv`

**Results:**
- Exact match: 65/170
- Fuzzy match (rapidfuzz token_sort_ratio ≥ 80): additional 19
- After input error corrections: 72 works found in OL but excluded by limit=5000
- Not in OL at all: 19 works

**Action taken:** 51 unique works added directly via work_key → `derived/phd_supplement_works.tsv`

---

## Stage 4: Enrichment

### 4a. OCLC Bulk Fetch

**Purpose:** Retrieve all OCLC numbers from OL edition records for the full population, to enable matching with external databases.

**Inputs:** `derived/ol_works_final_population.tsv`
**Outputs:** `derived/ol_works_oclc_all.tsv` (28,895 rows; 4,464 works with OCLC)
**Command:** `python3 scripts/fetch_all_editions_oclc.py`
**Cache:** `raw/editions_oclc/*.json` (resumable)
**Rate:** 0.5s per request

---

### 4b. HathiTrust Matching (htrc × OL)

**Purpose:** Match OL population works to HathiTrust digitised volumes via shared OCLC numbers.

**Inputs:**
- `derived/ol_works_oclc_all.tsv`
- `data/htrc-fiction_metadata.csv` (101,948 records; all within 1880–1923)

**Outputs:**
- `derived/htrc_ol_match.tsv` (all matched rows with htrc metadata)
- `derived/htrc_ol_match_summary.tsv` (per work_id summary)
- `derived/htrc_ol_match_with_ol_meta.tsv` (+ OL metadata joined)

**Command:** `python3 scripts/match_htrc_ol.py`

**Results:**

| Metric | Value |
|---|---|
| Raw matches | 995 works (20.6% of population) |
| Clean matches (prob80 ≥ 0.8, non-omnibus, pre-1923) | **885 works** |

**htrc note:** `htid` values enable direct access to HathiTrust full text at `https://babel.hathitrust.org/cgi/pt?id={htid}`. Works with startdate ≤ 1922 are US public domain and allow full-text download.

**Why HathiTrust API direct access failed:** OL edition identifiers reflect modern reprint/POD editions; HathiTrust holds digitised copies of early library holdings. Structural version mismatch → resolved by using pre-matched htrc CSV instead.

---

### 4c. WorldCat Entity API (Author Metadata)

**Purpose:** Retrieve structured author metadata (birth/death dates, name variants, influence networks) via OCLC WorldCat Entity Data API.

**Endpoint:** `GET https://id.oclc.org/worldcat/entity/{entityId}.jsonld`
**Auth:** OAuth 2.0 CCG; scope `publicEntities:read_brief_entities publicEntities:read_references`
**Token expiry:** ~20 minutes (must re-acquire per session)

**Confirmed available (Person entities):** prefLabel (multilingual), altLabel, dateOfBirth, dateOfDeath, placeOfBirth, influencedBy

**Confirmed NOT available (any entity type):** holdingsCount, oclcNumber, externalIdentifier — this API is a Linked Data identity service, not a bibliographic holdings API.

**WorldCat Discovery API (holdings):** Requires institutional subscription beyond current University of Tokyo OCLC agreement. Cannot be self-requested via developer portal. Formal OCLC Research Partnership inquiry is the recommended path.

---

## Stage 5: Planned (Not Yet Implemented)

| Step | Description | API / Source |
|------|-------------|--------------|
| 5a | phd_corpus × OL fuzzy matching → `canonical` flag | rapidfuzz |
| 5b | Academic Citations | OpenAlex API (no auth required) |
| 5c | Classroom Citations | Open Syllabus API (auth TBC) |
| 5d | Bibliographic Presence score | Wikidata SPARQL + OL edition_count |
| 5e | Book Reviews | JSTOR (access TBC) |
| 5f | influencedBy network analysis | WorldCat Entity API |

---

## Release History

| Release ID | Date | Key Artifact | Notes |
|---|---|---|---|
| population-v1 | 2026-02-22 | `ol_works_final_population.tsv` (4,833) | Initial filtered population |
| population-v2 | 2026-03-04 | `ol_works_augmented_population.tsv` (4,884) | + phd_corpus supplement |
| population-v3 | TBD | `ol_works_expanded_population.tsv` (~15,000) | + OL offset expansion |
| population-dump-v1 | TBD | `ol_dump_population_{date}.tsv` | Dump-based main study population (to be created) |

---

## Known Limitations (Cumulative)

1. `first_publish_year` mis-registration ~2.5% (unfilterable)
2. Non-fiction residual contamination ~1% post-filter
3. OL search is relevance-ranked, not random — population skews toward well-documented works
4. OCLC identifier audit covers 100 works only (~2% sample); full-population figures are estimates
5. HathiTrust match covers 885 works (20.6%); non-matched works are not absent from libraries, only undigitised in HathiTrust
6. WorldCat Entity API: holdingsCount structurally unavailable under current WSKey scope
7. WorldCat Discovery API: institutional contract barrier; self-application not possible
8. phd_corpus: 19 works not found in OL at all (see `tmp/phd_missing_ol_search.tsv`)
9. htrc omnibus volumes (collected works) inflate htid_count; not equivalent to single-work importance
10. FAST ID label resolution blocked by network policy in current work environment
11. OL dump coverage: works not registered in OL are treated as non-existent
12. OL dump language field: may be absent at Work level; handling strategy TBD at implementation
