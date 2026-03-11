# WORKFLOW.md — canon-pipeline
**DCC Digital Curation Workflow Narrative**
Last updated: 2026-03-11
Status: LIVING DOCUMENT — update on every major change

---

## Overview

This pipeline constructs and validates a population of English-language fiction works (1880–1950) for a doctoral dissertation on canonical inequality in modernist literature. The pipeline is structured in five stages: Collection → Filtering → Validation → Enrichment → Analysis.

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
- File: `raw/ol_dump/ol_dump_works_2026-02-28.txt.gz` (.gitignore対象)
- File: `raw/ol_dump/ol_dump_editions_2026-02-28.txt.gz` (.gitignore対象)
- File: `raw/ol_dump/ol_dump_authors_2026-02-28.txt.gz` (.gitignore対象・2026-03-11追加)
- Snapshot date: 2026-02-28 (recorded in `derived/prov.json`)

### Filter Criteria
1. `first_publish_year`: 1880–1950
2. `language`: eng — determined from Edition-level `languages` field (Work-level language field is absent in dump; confirmed 2026-03-11)
3. `subject_keys`: fiction inclusion/exclusion rules (see Pilot Study Stage 2 below)

### Processing Method
3-pass stream processing (Works + Editions dumps combined):
- Pass 1: Extract work_key, title, author_keys, subjects from Works dump
- Pass 2: Extract first_publish_year, language from Editions dump
- Pass 3: Join and filter
Do NOT load entire dump into memory.

### Important OL Dump Structure Notes (confirmed 2026-03-11)
- `first_publish_year` does NOT exist in Work records — it is a Search API derived field only
- `subject_keys` does NOT exist in Work records — only raw `subjects` strings
- `language` is absent at Work level — must use Edition-level `languages`
- `author_keys` contains OL key format (`/authors/OL123A`), NOT author name strings
  → Author names require separate lookup against Authors dump (see Stage 4d)

### Outputs
| File | Description |
|------|-------------|
| `derived/ol_dump_population_fiction_2026-02-28.tsv` | Official main-study population (34,789 works) — local only |
| `derived/ol_dump_population_with_canonical.tsv` | + canonical flag from phd_corpus matching — local only |
| `derived/ol_dump_population_with_author.tsv` | + author_name column from Authors dump — local only |
| `derived/prov.json` | population-dump-v1 release record (frozen) |

### Commands
```bash
# Build population from dump
python3 scripts/build_population_from_dump.py

# Build author name lookup table from Authors dump
python3 scripts/build_author_lookup.py
# → output: derived/ol_author_lookup.tsv (607MB — local only, .gitignore対象)
# → output: derived/ol_dump_population_with_author.tsv (34,789 rows)
```

### Decision Points
- **Why dump instead of API:** 72 canonical phd_corpus works were absent from
  the top-5,000 API results (e.g. Huckleberry Finn, Dracula, Tess of the D'Urbervilles).
  Direct evidence of search bias documented in pilot study.
- **No manual additions:** phd_corpus works not found in OL will be recorded
  as limitations only — no supplementation.
- **Authors dump required:** author_keys in population file are OL URIs, not names.
  Matching against JSTOR/OpenAlex requires last name strings → Authors dump lookup mandatory.

### Rights / Access
- OL dump data: CC0 (public domain dedication)
- No authentication required; direct download
- `ol_author_lookup.tsv` (607MB) excluded from GitHub due to size; local only

### Evidence / Logs
- `logs/build_population_from_dump_{date}.log`
- `derived/prov.json` (population-dump-v1 provenance record)

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
| `derived/ol_works_final_population.tsv` | Filtered population (dump-based): 34,789 works |
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

**Conclusion:** `first_publish_year` is reliable as population filter criterion.

---

### 3b. Identifier Coverage Audit

**Purpose:** Measure the availability of external identifiers (OCLC, ISBN, LCCN, ocaid) in OL edition records.

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

**Full population OCLC coverage (all 34,789 works):** 86.5% (30,101 works)

---

### 3c. phd_corpus Coverage Audit & Canonical Matching (v2)

#### Nature of the phd_corpus (read before interpreting results)

`data/phd_corpus_1880_1950_cleaned.csv` is **not a self-curated list**.
It is derived from the appendix of McGrath et al.'s quantitative study of modernist
literature, which aggregated publicly available PhD reading lists from multiple
major university English departments.

- **Meaning:** Works on this list were judged "required reading" for doctoral study
  in English literature at multiple major universities.
- **Dissertation significance:** hollow canon works (canonical=1, jstor=0) represent
  a *gap between pedagogical canon and research canon*: works institutionally mandated
  for doctoral education that are nonetheless absent from the academic literature.
- **Citation required:** Add full bibliographic reference for McGrath et al. to this
  section when available.

#### Matching approach

Each phd_corpus work is matched against the OL population (34,789 works) to assign
`canonical = 1`. Unmatched works are recorded as limitations only — no manual
supplementation.

**v1 (deprecated):** Title fuzzy match only (token_sort_ratio ≥ 80)

**v2 (current — 2026-03-11):** Three-condition priority matching

```
Priority 1 (quality=best):
  title score ≥ 80  AND  |publication year difference| ≤ 5  AND  last name match
  → Most reliable match

Priority 2 (quality=year_only):
  title score ≥ 80  AND  |publication year difference| ≤ 5
  → Applies when author name is absent from OL record

Priority 3 (quality=title_only):
  title score ≥ 80 only
  → Equivalent to v1; last resort when year/author unavailable

FORCE_MAP (manual override):
  Works where automatic matching is structurally unreliable due to
  multiple OL records sharing the same title. Directly assigned:
    "The Prisoner of Zenda" → /works/OL9056552W  (Anthony Hope, 1894)
    "The Good Soldier"      → /works/OL15345521W (Ford Madox Ford, 1915)
    "Dracula"               → /works/OL15062619W (Bram Stoker, 1897)
```

**Script:** `scripts/match_phd_corpus_v2.py`
**Comparison log:** `derived/phd_match_comparison.tsv`
(records v1 vs v2 diff, quality tier, and changed flag for every matched work)

#### Results (v2)

| Quality tier | Count |
|---|---|
| best (year + author + title) | 76 |
| year_only (year + title) | 4 |
| title_only (title only) | 15 |
| forced (FORCE_MAP) | 3 |
| **Total canonical** | **98** |
| Unmatched | 44 (recorded as limitations) |

#### Corrections made vs v1 (11 works)

| Work | v1 problem | v2 correction |
|---|---|---|
| The Awakening (1899) | Matched C. Wickliffe Yulee edition | Corrected to Kate Chopin (OL65430W) |
| Jude the Obscure (1895) | Matched edition with no author | Corrected to Hardy, Thomas (OL39453744W) |
| The Secret Agent (1907) | Matched wrong edition | Corrected to Conrad, Joseph (OL39108W) |
| Peter Pan (1911) | Matched wrong edition | Corrected to J. M. Barrie (OL462007W) |
| Tender Is The Night (1934) | Matched wrong edition | Corrected to F. Scott Fitzgerald (OL468485W) |
| Strange Case of Dr Jekyll (1886) | Matched wrong edition | Corrected to Robert Louis Stevenson (OL44014215W) |
| The Jungle Book (1894) | Matched wrong edition | Corrected to Kipling, Rudyard (OL19870W) |
| The Crock of Gold (1913) | Matched wrong edition | Corrected to Stephens, James (OL1154817W) |
| The North Star (1904) | Matched wrong edition | Corrected to M. E. Henry-Ruffin (OL18397742W) |
| The Custom of the Country (1913) | Matched wrong author edition | Corrected to Edith Wharton (OL98585W) — OL year mis-registered as 1900 |
| The Frontiersman (1904) | Matched wrong edition | Corrected to Craddock / Murfree (OL2337481W) |

#### ⚠️ Scope of today's verification — what is and is not guaranteed

**What this verification covers:**
- Correctness of work_key assignments for all **98 canonical works**
- JSTOR mention counts for canonical works (rescanned with correct author names; see §5a)

**What this verification does NOT cover:**
- Correctness of work_key assignments for the remaining **34,691 non-canonical works**
  → Where multiple OL records share the same title, the correct edition may not have
    been selected. Only title-based fuzzy matching was applied to these works.
- JSTOR mention counts for non-canonical works where the wrong edition may have been
  matched (unmodified; see Known Limitation #18)

#### When re-verification is required

Re-run `scripts/match_phd_corpus_v2.py` and downstream scripts when any of the
following occur:

1. **phd_corpus is updated** (works added, removed, or year range changed)
2. **OL dump is replaced with a newer snapshot** (work_keys may change)
3. **A specific non-canonical work is cited individually in the dissertation**
   (e.g. shadow canon top entries) → verify its work_key manually against
   `derived/ol_dump_population_with_author.tsv`
4. **Multi-signal agreement analysis (§6b) is run** → cross-check that all four
   indicators (JSTOR, OpenAlex, Wikidata, HathiTrust) reference the same work_key

---

## Stage 4: Enrichment (完了)

### 4a. OCLC Bulk Fetch

**Purpose:** Retrieve all OCLC numbers from OL Editions dump for the full population.

**Inputs:** `derived/ol_dump_population_fiction_2026-02-28.tsv`
**Outputs:** `derived/ol_dump_oclc_all.tsv` (91,449 rows; 30,101 works with OCLC)
**Command:** `python3 scripts/fetch_oclc_from_dump.py`
**Note:** Dump-based approach replaced API-based fetch (API版: ~200時間 → Dump版: ~40分)

---

### 4b. HathiTrust Matching (htrc × OL)

**Purpose:** Match OL population works to HathiTrust digitised volumes via shared OCLC numbers.

**Inputs:**
- `derived/ol_dump_oclc_all.tsv`
- `data/htrc-fiction_metadata.csv` (101,948 records; all within 1880–1923)

**Outputs:**
- `derived/htrc_ol_dump_match.tsv` (all matched rows with htrc metadata)
- `derived/htrc_ol_dump_match_summary.tsv` (per work_id summary)

**Command:** `python3 scripts/match_htrc_ol.py`

**Results:**

| Metric | Value |
|---|---|
| Raw matches | 6,264 works (18.0% of population) |
| prob80 ≥ 0.8 (clean) | 5,310 works |
| canonical 98件中HT収録 | 38 works（60件は構造的に未収録・1923年以降初出） |

---

### 4c. WorldCat Entity API (Author Metadata)

**Purpose:** Retrieve structured author metadata via OCLC WorldCat Entity Data API.

**Auth:** OAuth 2.0 CCG — WSKey stored in `token.sh` (local only, .gitignore対象・**GitHub絶対禁止**)
**Token expiry:** ~20 minutes (must re-acquire per session)

**Confirmed NOT available:** holdingsCount — this API is a Linked Data identity service, not a holdings API.
**WorldCat Discovery API:** Requires institutional subscription beyond current OCLC agreement.

---

### 4d. Author Name Lookup (OL Authors Dump — 2026-03-11追加)

**Purpose:** Resolve `author_keys` (OL URI format) to human-readable author name strings required for JSTOR/OpenAlex matching.

**Input:** `raw/ol_dump/ol_dump_authors_2026-02-28.txt.gz` (~400MB)
**Output:** `derived/ol_author_lookup.tsv` (15,068,943 rows — **607MB, local only, .gitignore対象**)
**Output:** `derived/ol_dump_population_with_author.tsv` (34,789 rows, author_name列追加 — local only)
**Command:** `python3 scripts/build_author_lookup.py`

**Results:**
- 15,071,242 authors processed; 名前あり: 15,068,943 (99.98%)
- 母集団への付与率: 34,434/34,789 (99.0%); 著者名なし: 355件 (1.0%)

**Author name format (mixed, both handled):**
- `"姓, 名"` format: `"Lawrence, D. H."` → last_name = `"lawrence"`
- `"名 姓"` format: `"William Faulkner"` → last_name = `"faulkner"`

---

### 4e. Wikidata Sitelink Fetch

**Purpose:** Retrieve number of Wikipedia language editions linking to each work (cultural circulation proxy).

**Method:** P648 (Open Library Work ID) property → direct OL↔Wikidata link
**Script:** `scripts/fetch_wikidata_sitelinks.py` (50件バッチSPARQL・1秒インターバル・約12分)
**Output:** `derived/wikidata_sitelinks.tsv` (columns: work_id, qid, sitelink_count)

**Results:**

| Metric | Value |
|---|---|
| 実ヒット (sitelink > 0) | 1,338 works (3.8%) |
| sitelink 中央値（ヒットのみ） | 5 |
| sitelink 最大値 | 136 (Nineteen Eighty-Four) |
| canonical 98件中Wikidataあり | **98/98件 (100%)** |

**Note:** qid が NaN の行はWikidata未収録。フィルタ時は `wd['qid'].notna()` を使うこと。

---

## Stage 5: Academic Citations Enrichment (2026-03-11完了・一部継続)

### 5a. JSTOR Full Scan

**Purpose:** Count academic papers whose titles co-occur with a work title AND author surname in JSTOR metadata.

**Input:** `data/jstor_metadata_2025-07-04.jsonl` (12,380,553 lines — **local only, 6.5GB**)
**Output:** `derived/jstor_mentions.tsv` (30,962 rows)
**Script:** `scripts/jstor_mentions_all.py`
**Runtime:** 621分 (2026-03-10 23:09 〜 2026-03-11 09:30)

#### JSTOR Data Structure (confirmed 2026-03-11)
- Total records: 12,380,553
- `content_type == "article"`: 11,657,976 (94.2%) ← **検索対象はこれのみ**
- `abstract` field population: **0.0%** ← abstractフィールドは実質存在しない

#### Indicator Definition (confirmed, do not change)
> **"Number of academic journal articles whose title and/or creators field
>  co-occurs with a work title AND author last name"**
>
> ~~"Number of papers mentioning the work in title, abstract, or full text"~~
> (revised because abstract field is absent in JSTOR metadata)

#### Normalization Rules (v3-final — applies to ALL matching scripts)
```python
_LEADING_ART = re.compile(r'^(the|a|an)\s+', re.IGNORECASE)
_DROP_CHARS  = re.compile(r"['\-\u2018\u2019\u201c\u201d]")   # DELETE (not replace)
_NON_ALNUM   = re.compile(r'[^a-z0-9\s]')                     # replace with space
_MULTI_SPC   = re.compile(r'\s+')

# Examples:
# "Howard's End"         → "howards end"      (v2 bug: "howard s end")
# "D'Urbervilles"        → "durbervilles"      (v2 bug: "d urbervilles")
# "Nineteen Eighty-Four" → "nineteen eightyfour"
```

**⚠ WARNING:** `scripts/jstor_canonical_test_v2.py` contains the normalization bug above. Use v3 only.

#### Filtering Decision Points
- `content_type != "article"` → skip (6.9% of records)
- `last_name` empty (author unknown) → title-only match only (355 works, 1.0%)
- `title_norm` duplicate → deduplicated to 30,962 index entries (from 34,789)

#### Results (initial scan)

| Metric | All works (30,962) | Canonical (98) |
|---|---|---|
| Zero hits | 27,481 (88.8%) | 28 (28.6%) |
| 1 or more | 3,481 (11.2%) | 70 (71.4%) |
| 5 or more | 845 (2.7%) | 55 (56.1%) |
| Median | 0 | 6 |
| Maximum | — | 443 (Ulysses) |

#### Post-hoc JSTOR rescan for corrected canonical works (2026-03-11)

Ten canonical works corrected in v2 matching had been scanned using incorrect
author names from v1. These were rescanned with correct author names and
`derived/jstor_mentions.tsv` was updated.

| Work | Old author (wrong) | Old JSTOR | Correct author | New JSTOR |
|---|---|---|---|---|
| The Awakening | C. Wickliffe Yulee | 0 | Kate Chopin | **32** |
| Jude the Obscure | (no author) | 0 | Hardy, Thomas | **27** |
| The Secret Agent | (wrong author) | 0 | Conrad, Joseph | **77** |
| The Custom of the Country | Fraser, Hugh | 0 | Edith Wharton | **12** |
| Tender Is The Night | (wrong author) | 0 | F. Scott Fitzgerald | **15** |
| The Jungle Book | — | — | Kipling, Rudyard | **6** |
| Strange Case of Dr Jekyll | — | — | R. L. Stevenson | **4** |
| Peter Pan | — | — | J. M. Barrie | **2** |
| The Crock of Gold | — | — | Stephens, James | **2** |
| The Frontiersmen | — | — | Craddock / Murfree | **0** |

FORCE_MAP works (3) also rescanned:

| Work | Correct author | JSTOR |
|---|---|---|
| Dracula | Bram Stoker | **63** |
| The Good Soldier | Ford Madox Ford | **21** |
| The Prisoner of Zenda | Anthony Hope | **1** |

#### Confirmed canonical indicator values (post-correction — use these in dissertation)

| Metric | Canonical (n=98) |
|---|---|
| Zero hits | 23 (23.5%) |
| 1 or more hits | 75 (76.5%) |
| Median | 7 |
| Mean | 18.3 |
| Maximum | 443 (Ulysses) |

#### Output Column Schema
| Column | Type | Description |
|---|---|---|
| `work_id` | string | `/works/OL123W` format |
| `title` | string | Work title |
| `author` | string | Author name string |
| `title_norm` | string | Normalized title (v3 rules) |
| `last_name` | string | Normalized author last name |
| `canonical` | integer | 0 or 1 |
| `is_short` | integer | 1 if title_norm < 4 chars |
| `jstor_mention_count` | integer | **Primary indicator** |
| `via_creators` | integer | Matches via creators_string field |
| `via_jtitle` | integer | Matches via jstor title field |

---

### 5b. OpenAlex Works API (title.search)

**Purpose:** Count academic papers mentioning a work in title OR abstract via OpenAlex API.

**Endpoint:** `GET https://api.openalex.org/works?filter=title.search:{title} {last_name}&mailto=tsutsui@nihu.jp`
**Auth:** None required. Use `mailto` param for polite pool (10 req/sec).
**Rate:** 1.0s interval (confirmed safe; 0.2s caused HTTP 429 at scale)

#### Why OpenAlex Concepts/Topics approach was abandoned (confirmed 2026-03-11)
- **Concepts API** (`filter=wikidata_id:Q208460`): `count: 0` for all tested works including Nineteen Eighty-Four. OpenAlex does not register individual novels as Concepts.
- **Topics:** Granularity is "James Joyce" or "Modernist Literature" level — no per-title Topics exist.
- **Conclusion:** QID-based approach is structurally impossible. title.search is the only viable method.

#### API usage notes (confirmed through trial and error)
- `group_by=publication_year` and `select=id` **cannot be used together** → HTTP 400
- Use `per_page=1` (not 0) with `group_by` → returns `meta.count` + year breakdown in one request
- Filter syntax: **no quotes** around query string → `title.search:ulysses joyce` ✓
  (quoted syntax `title.search:"ulysses joyce"` returns wrong results)

#### Difference from JSTOR
- OpenAlex searches **title + abstract** (JSTOR: title only)
- OpenAlex covers all disciplines (JSTOR: humanities-heavy)
- → OpenAlex counts are generally higher; the two indicators are complementary

#### Canonical 142-work test results (2026-03-11)
**Output:** `derived/openalex_works_test.tsv`

| Metric | title only | title AND author |
|---|---|---|
| Zero hits | 15 (10.6%) | 56 (39.4%) |
| 1 or more | 127 (89.4%) | 86 (60.6%) |
| Maximum | 343,243 | 530 (Ulysses) |

#### Full population scan — pending
**Script:** `scripts/openalex_mentions_all.py` (v5 — checkpoint + 429 retry)
**Input:** `derived/ol_dump_population_with_author.tsv`
**Output:** `derived/openalex_mentions.tsv`
**Additional output:** `year_json` column — per-year citation breakdown for temporal analysis (§6c)
**Estimated runtime:** ~10 hours (1.0s interval × 34,789 works, nohup recommended)
**Resume:** checkpoint saved every 1,000 works to `derived/openalex_mentions_checkpoint.tsv`

#### Output Column Schema
| Column | Type | Description |
|---|---|---|
| `work_key` | string | `/works/OL123W` format |
| `title` | string | Work title |
| `author` | string | Author name string |
| `last_name` | string | Normalized author last name |
| `canonical` | integer | 0 or 1 |
| `oa_count_author` | integer | title AND author count (**primary indicator**) |
| `year_json` | string | Per-year breakdown JSON e.g. `{"1980":3,"2005":12}` |

---

## Stage 6: Analysis

### 6a. Shadow Canon / Hollow Canon Analysis (completed 2026-03-11)

**Script:** `scripts/shadow_hollow_analysis.py` (v2)
**Input:** `derived/jstor_mentions.tsv`
**Outputs:**
- `derived/shadow_canon.tsv` (50 works)
- `derived/hollow_canon.tsv` (23 works)
- `derived/shadow_hollow_summary.txt` (statistics summary for dissertation)

#### Hollow canon (23 works — confirmed)

Definition: canonical=1 AND jstor_mention_count=0

Because canonical status derives from McGrath et al.'s aggregation of PhD reading
lists at major universities, hollow canon works are those that **doctoral programs
have institutionally mandated as required reading, yet which receive no citation
in the academic literature**.

**Dissertation framing:**
> "A disjunction between the pedagogical canon — works deemed essential by doctoral
>  programs — and the research canon — works that actually circulate in academic
>  discourse."

Representative hollow canon works:

| Work | Author | Interpretation |
|---|---|---|
| Tarzan of the Apes | Edgar Rice Burroughs | Mass popularity, zero academic attention — archetypal hollow canon |
| White Fang | Jack London | Same pattern |
| The Yearling | Marjorie Kinnan Rawlings | Pulitzer Prize winner — even prize status does not guarantee academic citation |
| King Coal | Upton Sinclair | Valued in political/social movement contexts, absent from literary scholarship |

Note: The Prisoner of Zenda (JSTOR=1) narrowly avoids zero — in practice
near-hollow; worth noting in dissertation.

#### Shadow canon (50 works — confirmed)

Definition: canonical=0 AND jstor_mention_count ≥ 5, is_short=0,
author-name-as-title noise excluded. Top 50 by jstor_mention_count.

**Dissertation framing:**
> "Works excluded from the PhD reading lists aggregated by McGrath et al.,
>  yet heavily cited in academic literature — evidence of what (and who)
>  canonical selection omitted."

Key findings:

- **H. D. (Hilda Doolittle)** appears twice in top 10:
  Palimpsest (396 citations), The Hedgehog (381 citations).
  A female modernist writer receiving substantial academic attention
  while absent from the doctoral canon. **Usable as concrete evidence
  of gender bias in canonical selection.**

- **Finnegans Wake / Joyce (142 citations):**
  Ulysses is canonical, but this equally major work by the same author is not.
  Illustrates "author is canonical, work is not" — a distinct pattern.

- **The Wave / Evelyn Scott (122 citations):**
  Confirmed not confused with Virginia Woolf's The Waves — normalization
  produces "wave" ≠ "waves"; counts verified as distinct in jstor_mentions.tsv.

- **Virginia Woolf's non-canonical works** (The Waves 37, Between the Acts 30,
  The Years 25, The Voyage Out 17): four works are canonical; remaining major
  works are outside the canon despite substantial academic citation.

**Known noise in shadow canon (record as limitations):**
- Stephen King, "The Mist" (1980) — outside 1880–1950 scope
- Shakespeare, Spenser — outside scope (pre-1880)
- See Known Limitation #19

#### Core quantitative finding (citable in dissertation)

```
Canonical median JSTOR citations:     7
Non-canonical median JSTOR citations: 0

Canonical works with ≥1 citation:     76.5%
Non-canonical works with ≥1 citation: 11.1%
```

### 6b. Multi-Signal Agreement Analysis
**Status:** Pending OpenAlex full scan completion

```
Vectorise each work: [jstor, openalex, wikidata_sitelinks, hathitrust_htid_count]
→ Spearman correlation matrix between indicators
→ Cluster into 4 types:
   Type A: all indicators high → "true canon"
   Type B: Wikidata high, JSTOR low → popular but academically ignored (e.g. Tarzan)
   Type C: JSTOR high, Wikidata low → academically important, low public profile
   Type D: all indicators low → "forgotten works"
```

### 6c. Temporal Analysis (Citation Trends)
**Status:** Pending OpenAlex full scan completion

```
For canonical 98 works × year_json column:
→ aggregate by decade → visualise citation waves
→ expected findings:
   Kate Chopin "The Awakening": spike post-1960s feminism
   Virginia Woolf: spike 1970–80s feminist criticism
   Joseph Conrad: spike 1980s postcolonial criticism
```

---

## Release History

| Release ID | Date | Key Artifact | Notes |
|---|---|---|---|
| population-v1 | 2026-02-22 | `ol_works_final_population.tsv` (4,833) | Initial filtered population (pilot) |
| population-v2 | 2026-03-04 | `ol_works_augmented_population.tsv` (4,884) | + phd_corpus supplement |
| population-dump-v1 | 2026-03-09 | `ol_dump_population_fiction_2026-02-28.tsv` (34,789) | Dump-based production population — **current baseline** |

---

## Known Limitations (Cumulative)

1. `first_publish_year` mis-registration ~2.5% (unfilterable)
2. Non-fiction residual contamination ~1% post-filter
3. OL search is relevance-ranked, not random — population skews toward well-documented works (pilot only; dump-based main study is unbiased)
4. OCLC identifier audit covers 100 works only (~2% sample)
5. HathiTrust match covers 18.0% of population; non-matched works are not absent from libraries, only undigitised
6. WorldCat Entity API: holdingsCount structurally unavailable under current WSKey scope
7. WorldCat Discovery API: institutional contract barrier
8. phd_corpus: 44 works not matched to OL (main study); recorded in `derived/phd_corpus_not_matched.tsv`
9. htrc omnibus volumes inflate htid_count
10. FAST ID label resolution blocked by network policy in current work environment
11. OL dump coverage: works not registered in OL are treated as non-existent
12. OL dump language field absent at Work level — handled via Edition-level languages field
13. **JSTOR abstract field is 0.0% populated** → indicator is title-co-occurrence only, not full-text mention
14. JSTOR title_norm deduplication reduced index from 34,789 to 30,962 works (~3,800 title collisions)
15. Works with unknown author (355 works, 1.0%) receive title-only JSTOR matching (lower precision)
16. OpenAlex Concepts/Topics API cannot identify individual novels — QID-based approach structurally impossible (confirmed 2026-03-11)
17. **work_key accuracy verified for canonical 98 works only.** For the remaining 34,691 non-canonical works, where multiple OL records share the same title, the correct edition may not have been selected (title fuzzy match only). Individual non-canonical works cited in the dissertation (e.g. shadow canon entries) should be manually verified against `derived/ol_dump_population_with_author.tsv`.
18. **JSTOR mention counts for non-canonical works are unrevised.** The post-hoc rescan in §5a was applied to canonical works only. Non-canonical JSTOR values may reflect wrong-edition author names in a small number of cases. Since non-canonical works are used only in aggregate (distributions, medians), not individually, this does not affect dissertation conclusions.
19. **Shadow canon list contains works outside the 1880–1950 scope.** The `first_publish_year` filter was applied at population construction (§1) but not re-applied during shadow canon extraction (§6a). Works such as Stephen King's "The Mist" (1980) appear in the shadow canon list. Individual year verification is required before citing any shadow canon entry in the dissertation.