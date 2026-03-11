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

### 3c. phd_corpus Coverage Audit

**Purpose:** Verify that canonical works (phd_corpus) are present in the OL population.

**Inputs:** `data/phd_corpus_1880_1950_cleaned.csv` (142 works after cleaning)
**Outputs:** `derived/phd_corpus_not_matched.tsv`
**Script:** `scripts/match_phd_corpus.py` (rapidfuzz token_sort_ratio ≥ 80)

**Results:**
- Matched: 98/142 works → `canonical = 1` flag in population file
- Not matched: 44 works → recorded as limitation only (no manual supplementation)
- canonical 98件全件がWikidataに存在することを別途確認（§4e参照）

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
> **「学術論文タイトルおよびcreators欄に作品名・著者名が共起する論文件数」**
>
> ~~「論文のtitle・abstract・全文に作品名が含まれる件数」~~ (abstractが存在しないため修正)

#### Normalization Rules (v3-final — applies to ALL matching scripts)
```python
_LEADING_ART = re.compile(r'^(the|a|an)\s+', re.IGNORECASE)
_DROP_CHARS  = re.compile(r"['\-\u2018\u2019\u201c\u201d]")   # DELETE (not replace)
_NON_ALNUM   = re.compile(r'[^a-z0-9\s]')                     # replace with space
_MULTI_SPC   = re.compile(r'\s+')

# Examples:
# "Howard's End"      → "howards end"    (v2 bug was: "howard s end")
# "D'Urbervilles"     → "durbervilles"   (v2 bug was: "d urbervilles")
# "Nineteen Eighty-Four" → "nineteen eightyfour"
```

**⚠ WARNING:** `scripts/jstor_canonical_test_v2.py` contains the normalization bug above. Use v3 only.

#### Filtering Decision Points
- `content_type != "article"` → skip (6.9% of records)
- `last_name` empty (author unknown) → title-only match only (355 works, 1.0%)
- `title_norm` duplicate → deduplicated to 30,962 index entries (from 34,789)

#### Results

| Metric | All works (30,962) | Canonical (98) |
|---|---|---|
| 総マッチ件数 | 70,348 | — |
| ゼロヒット | 27,481 (88.8%) | 28 (28.6%) |
| 1件以上 | 3,481 (11.2%) | 70 (71.4%) |
| 5件以上 | 845 (2.7%) | 55 (56.1%) |
| 中央値 | 0 | 6 |
| 最大値 | — | 443 (Ulysses) |

**Core finding:** canonical works receive dramatically more academic attention than non-canonical works. This quantitative evidence of attention inequality is a key dissertation finding.

#### Output Column Schema
| Column | Type | Description |
|---|---|---|
| `work_key` | string | `/works/OL123W` format |
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

**Endpoint:** `GET https://api.openalex.org/works?filter=title.search:"作品名" 著者姓&mailto=tsutsui@nihu.jp`
**Auth:** None required. Use `mailto` param for polite pool (10 req/sec).
**Rate:** 0.2s interval (confirmed safe in testing)

#### Why OpenAlex Concepts/Topics approach was abandoned (confirmed 2026-03-11)
- **Concepts API** (`filter=wikidata_id:Q208460`): `count: 0` for all tested works including Nineteen Eighty-Four. OpenAlex does not register individual novels as Concepts.
- **Topics:** Granularity is "James Joyce" or "Modernist Literature" level — no per-title Topics exist.
- **Conclusion:** QID-based approach is structurally impossible. title.search is the only viable method.

#### Difference from JSTOR
- OpenAlex searches **title + abstract** (JSTOR: title only)
- OpenAlex covers all disciplines (JSTOR: humanities-heavy)
- → OpenAlex counts are generally higher; the two indicators are complementary

#### Canonical 142-work test results (2026-03-11)
**Output:** `derived/openalex_works_test.tsv`

| Metric | title only | title AND author |
|---|---|---|
| 総カウント | 854,332 | 4,350 |
| ゼロヒット | 15 (10.6%) | 56 (39.4%) |
| 1件以上 | 127 (89.4%) | 86 (60.6%) |
| 10件以上 | 103 (72.5%) | 59 (41.5%) |
| 最大値 | 343,243 | 530 (Ulysses) |

#### Next step: Full population scan (34,789 works)
**Script to create:** `scripts/openalex_mentions_all.py`
**Input:** `derived/ol_dump_population_with_author.tsv`
**Output:** `derived/openalex_mentions.tsv`
**Estimated runtime:** ~4 hours (nohup推奨)
**Important:** Include checkpoint saves every 1,000 works (lesson from JSTOR scan failure)
**Important:** Include HTTP 429 retry with exponential backoff

#### Output Column Schema (openalex_works_test.tsv)
| Column | Type | Description |
|---|---|---|
| `work_key` | string | `/works/OL123W` format |
| `title` | string | Work title |
| `author` | string | Author name string |
| `last_name` | string | Normalized author last name |
| `oa_count_title` | integer | title-only count (reference, noisy) |
| `oa_count_author` | integer | title AND author count (**primary indicator**) |

---

## Stage 6: Analysis (Next Phase)

### 6a. Shadow Canon / Hollow Canon Analysis
**Status:** Not yet implemented — can start immediately with existing data

```
shadow canon: canonical=0 AND jstor_mention_count high
→ "works that should have entered the canon but did not"
→ test: are female/minority authors overrepresented here?

hollow canon: canonical=1 AND jstor_mention_count=0
→ "works in the canon but academically ignored"
→ question: why did they achieve canonical status?
```

**Script to create:** `scripts/shadow_hollow_analysis.py`
**Input:** `derived/jstor_mentions.tsv`

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
**Status:** Pending OpenAlex canonical detail fetch

```
For canonical 98 works:
→ fetch all individual papers (cursor pagination, per_page=200)
→ fields: publication_year, cited_by_count, primary_topic
→ aggregate by decade → visualise citation waves
→ expected findings:
   Kate Chopin "The Awakening": spike post-1960s feminism
   Virginia Woolf: spike 1970–80s feminist criticism
   Joseph Conrad: spike 1980s postcolonial criticism
```

**Script to create:** `scripts/openalex_canonical_papers.py`
**Output:** `derived/openalex_canonical_papers.tsv`

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