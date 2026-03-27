# WORKFLOW.md — canon-pipeline
**DCC Digital Curation Workflow Narrative**
Last updated: 2026-03-27
Status: LIVING DOCUMENT — update on every major change

---

## Overview

This pipeline constructs and validates a population of English-language fiction works (1880–1950) for a doctoral dissertation on the formation and transformation of modernist literary studies as a scholarly field. The pipeline is structured in seven stages: Collection → Filtering → Validation → Enrichment → Citations → Analysis → Discourse Analysis.

**Core research question:** How was modernist literary studies made as a scholarly field? The pipeline provides empirical evidence for narratives that critics have previously constructed through impression and authority — mapping the formation of the modernist canon through multiple vectors of scholarly activity.

**Repository:** https://github.com/haruka0221/canon-pipeline
**Working environment:** WSL (Ubuntu 24) on Windows, ~/canon-pipeline
**Primary tools:** Python 3.12, pandas, rapidfuzz, pyahocorasick, pdfplumber
**External data (local only):** OpenAlex works snapshot (620GB, /mnt/d/openalex/works/), JSTOR metadata (6.5GB), Critical Inquiry PDFs (254 files)

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
python3 scripts/build_population_from_dump.py
python3 scripts/build_author_lookup.py
# → output: derived/ol_author_lookup.tsv (607MB — local only, .gitignore対象)
# → output: derived/ol_dump_population_with_author.tsv (34,789 rows)
```

### Decision Points
- **Why dump instead of API:** 72 canonical phd_corpus works were absent from the top-5,000 API results (e.g. Huckleberry Finn, Dracula, Tess of the D'Urbervilles). Direct evidence of search bias documented in pilot study.
- **No manual additions:** phd_corpus works not found in OL will be recorded as limitations only — no supplementation.
- **Authors dump required:** author_keys in population file are OL URIs, not names. Matching against JSTOR/OpenAlex requires last name strings → Authors dump lookup mandatory.

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
- Query parameters: `subject=fiction`, `first_publish_year=[1880 TO 1950]`, `language=eng`

### Outputs
| File | Description |
|------|-------------|
| `derived/ol_works_population_unique_clean.tsv` | Initial retrieval: 5,000 works (deduplicated) |
| `derived/ol_works_expanded_raw.tsv` | Additional works from offset 5000–14999 |
| `derived/ol_works_expanded_population.tsv` | Merged expanded population (~15,000 works) |

### Decision Points
- **Initial limit=5,000:** Post-hoc analysis showed 72 phd_corpus canonical works were excluded → expanded to ~15,000.
- **"English" definition:** Works published in English are included regardless of original language.
- **OL search sort order:** Results biased toward frequently-edited/well-documented works — superseded by dump-based approach.

### Evidence / Logs
- `logs/expand_population.log`
- `raw/ol_expand/offset_*.json` (API response cache)

---

## Pilot Study: Population Filtering (API-Based — Superseded)

### Purpose
Remove non-fiction, poetry, drama, and picture books using subject_key-based rules.

### Outputs
| File | Description |
|------|-------------|
| `derived/ol_works_final_population.tsv` | Filtered population: 34,789 works |
| `derived/ol_works_filtered_removed.tsv` | Excluded 167 works |
| `derived/ol_works_augmented_population.tsv` | + 51 phd_corpus supplements = 4,884 works |

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
- Post-filter audit (n=200): 3.5% NG rate; primary residual issue is `first_publish_year` mis-registration

### Evidence / Logs
- `derived/ol_works_audit200_seed20260222.tsv`
- `derived/ol_works_audit200_for_review.tsv`
- `derived/ol_works_postfilter_audit100.tsv`

---

## Stage 3: Validation

### 3a. Year Mismatch Audit

**Purpose:** Verify that `first_publish_year` (work-level) is consistent with edition-level `publish_date`.

**Result:** matched 98/100, near_match 2/100, mismatch 0/100. Apparent mismatches were caused by OL returning recent editions first (offset0 bias), not by data errors.

**Conclusion:** `first_publish_year` is reliable as population filter criterion.

---

### 3b. Identifier Coverage Audit

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
It is derived from the appendix of McGrath et al.'s quantitative study of modernist literature, which aggregated publicly available PhD reading lists from multiple major university English departments.

- **Meaning:** Works on this list were judged "required reading" for doctoral study in English literature at multiple major universities.
- **Dissertation significance:** hollow canon works (canonical=1, jstor=0) represent a *gap between pedagogical canon and research canon*: works institutionally mandated for doctoral education that are nonetheless absent from the academic literature.
- **Citation required:** Add full bibliographic reference for McGrath et al. to this section when available.

#### Matching approach

Each phd_corpus work is matched against the OL population (34,789 works) to assign `canonical = 1`. Unmatched works are recorded as limitations only — no manual supplementation.

**v1 (deprecated):** Title fuzzy match only (token_sort_ratio ≥ 80)

**v2 (current — 2026-03-11):** Three-condition priority matching

```
Priority 1 (quality=best):
  title score ≥ 80  AND  |publication year difference| ≤ 5  AND  last name match

Priority 2 (quality=year_only):
  title score ≥ 80  AND  |publication year difference| ≤ 5

Priority 3 (quality=title_only):
  title score ≥ 80 only — last resort when year/author unavailable

FORCE_MAP (manual override):
    "The Prisoner of Zenda" → /works/OL9056552W  (Anthony Hope, 1894)
    "The Good Soldier"      → /works/OL15345521W (Ford Madox Ford, 1915)
    "Dracula"               → /works/OL15062619W (Bram Stoker, 1897)
```

**Script:** `scripts/match_phd_corpus_v2.py`
**Comparison log:** `derived/phd_match_comparison.tsv`

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

#### ⚠️ Scope of verification — what is and is not guaranteed

**Covered:** Correctness of work_key assignments for all 98 canonical works; JSTOR mention counts for canonical works (rescanned with correct author names; see §5a).

**Not covered:** Correctness of work_key assignments for the remaining 34,691 non-canonical works. Individual non-canonical works cited in the dissertation should be manually verified against `derived/ol_dump_population_with_author.tsv`.

#### When re-verification is required

1. phd_corpus is updated (works added, removed, or year range changed)
2. OL dump is replaced with a newer snapshot (work_keys may change)
3. A specific non-canonical work is cited individually in the dissertation
4. Multi-signal agreement analysis (§6b) is run → cross-check that all four indicators reference the same work_key

---

## Stage 4: Enrichment (完了)

### 4a. OCLC Bulk Fetch

**Outputs:** `derived/ol_dump_oclc_all.tsv` (91,449 rows; 30,101 works with OCLC)
**Command:** `python3 scripts/fetch_oclc_from_dump.py`
**Note:** Dump-based approach replaced API-based fetch (API版: ~200時間 → Dump版: ~40分)

---

### 4b. HathiTrust Matching (htrc × OL)

**Inputs:** `derived/ol_dump_oclc_all.tsv` + `data/htrc-fiction_metadata.csv` (101,948 records; all within 1880–1923)

**Results:**

| Metric | Value |
|---|---|
| Raw matches | 6,264 works (18.0% of population) |
| prob80 ≥ 0.8 (clean) | 5,310 works |
| canonical 98件中HT収録 | 38 works（60件は構造的に未収録・1923年以降初出） |

---

### 4c. WorldCat Entity API (Author Metadata)

**Auth:** OAuth 2.0 CCG — WSKey stored in `token.sh` (local only, .gitignore対象・**GitHub絶対禁止**)

**Confirmed NOT available:** holdingsCount — this API is a Linked Data identity service, not a holdings API.
**WorldCat Discovery API:** Requires institutional subscription beyond current OCLC agreement.

---

### 4d. Author Name Lookup (OL Authors Dump)

**Output:** `derived/ol_author_lookup.tsv` (15,068,943 rows — **607MB, local only**)
**Output:** `derived/ol_dump_population_with_author.tsv` (34,789 rows)
**Command:** `python3 scripts/build_author_lookup.py`

**Results:** 母集団への付与率: 34,434/34,789 (99.0%); 著者名なし: 355件 (1.0%)

---

### 4e. Wikidata Sitelink Fetch

**Method:** P648 (Open Library Work ID) property → direct OL↔Wikidata link
**Output:** `derived/wikidata_sitelinks.tsv`

**Results:**

| Metric | Value |
|---|---|
| 実ヒット (sitelink > 0) | 1,338 works (3.8%) |
| sitelink 中央値（ヒットのみ） | 5 |
| sitelink 最大値 | 136 (Nineteen Eighty-Four) |
| canonical 98件中Wikidataあり | **98/98件 (100%)** |

**Note:** qid が NaN の行はWikidata未収録。フィルタ時は `wd['qid'].notna()` を使うこと。

---

## Stage 5: Academic Citations Enrichment (完了)

### 5a. JSTOR Full Scan

**Purpose:** Count academic papers whose titles co-occur with a work title AND author surname in JSTOR metadata.

**Input:** `data/jstor_metadata_2025-07-04.jsonl` (12,380,553 lines — **local only, 6.5GB**)
**Output:** `derived/jstor_mentions.tsv` (30,962 rows)
**Script:** `scripts/jstor_mentions_all.py`
**Runtime:** 621分 (2026-03-10 23:09 〜 2026-03-11 09:30)

#### JSTOR Data Structure (confirmed 2026-03-11)
- Total records: 12,380,553
- `content_type == "article"`: 11,657,976 (94.2%) ← 検索対象はこれのみ
- `abstract` field population: **0.0%** ← abstractフィールドは実質存在しない

#### Indicator Definition (confirmed, do not change)
> **"Number of academic journal articles whose title and/or creators field co-occurs with a work title AND author last name"**

#### Normalization Rules (v3-final — applies to ALL matching scripts)
```python
_LEADING_ART = re.compile(r'^(the|a|an)\s+', re.IGNORECASE)
_DROP_CHARS  = re.compile(r"['\-\u2018\u2019\u201c\u201d]")   # DELETE (not replace)
_NON_ALNUM   = re.compile(r'[^a-z0-9\s]')                     # replace with space
_MULTI_SPC   = re.compile(r'\s+')
# "Howard's End" → "howards end" / "D'Urbervilles" → "durbervilles"
```

**⚠ WARNING:** `scripts/jstor_canonical_test_v2.py` contains a normalization bug. Use v3 only.

#### Post-hoc JSTOR rescan for corrected canonical works (2026-03-11)

Ten canonical works corrected in v2 matching were rescanned with correct author names.

| Work | Correct author | New JSTOR |
|---|---|---|
| The Awakening | Kate Chopin | **32** |
| Jude the Obscure | Hardy, Thomas | **27** |
| The Secret Agent | Conrad, Joseph | **77** |
| The Custom of the Country | Edith Wharton | **12** |
| Tender Is The Night | F. Scott Fitzgerald | **15** |
| Dracula | Bram Stoker | **63** |
| The Good Soldier | Ford Madox Ford | **21** |
| The Prisoner of Zenda | Anthony Hope | **1** |

#### Confirmed canonical indicator values (post-correction — use these in dissertation)

| Metric | Canonical (n=98) | Non-canonical (n=30,874) |
|---|---|---|
| Zero hits | 23 (23.5%) | 27,456 (88.9%) |
| 1 or more hits | 75 (76.5%) | 3,418 (11.1%) |
| Median | **7** | **0** |
| Mean | 18.3 | 2.2 |
| Maximum | 443 (Ulysses) | 10,559 |

#### Output Column Schema
| Column | Type | Description |
|---|---|---|
| `work_id` | string | `/works/OL123W` format |
| `title` | string | Work title |
| `author` | string | Author name string |
| `title_norm` | string | Normalized title (v3 rules) |
| `last_name` | string | Normalized author last name |
| `canonical` | integer | 0 or 1 |
| `is_short` | integer | 1 if title_norm < 6 chars |
| `jstor_mention_count` | integer | **Primary indicator** |
| `via_creators` | integer | Matches via creators_string field |
| `via_jtitle` | integer | Matches via jstor title field |

---

### 5b. OpenAlex Snapshot Scan (completed 2026-03-26)

**Purpose:** Count academic papers mentioning a work in title using the full OpenAlex works snapshot, as a complementary indicator to JSTOR.

**Method:** Switched from API-based approach (abandoned due to persistent HTTP 429 rate limiting) to local snapshot scanning using Aho-Corasick multi-pattern matching.

**Input:** `/mnt/d/openalex/works/updated_date=*/part_*.gz` (620GB, 2,228 files, 901 partitions after deduplication)
**Output:** `derived/openalex_snapshot_mentions.tsv`
**Script:** `scripts/openalex_snapshot_scan.py` (v3, Aho-Corasick)
**Runtime:** 89 minutes (16 workers, 2026-03-26)

#### Why API approach was abandoned
The OpenAlex API consistently returned HTTP 429 errors at scale (~10,000 requests in). Rate limiting persisted for hours even at 1.0s intervals. Snapshot-based local processing is more reliable and reproducible.

#### Matching logic
- Aho-Corasick automaton built from all 33,978 normalized title_norms (≥6 chars)
- For each OpenAlex paper: check if any work title appears in `display_name`
- AND condition: author last name must appear in paper's `authorships` list
- Title-only matching (abstract disabled for consistency with JSTOR indicator)
- `title_norm` minimum length: 6 characters (short titles cause too many false positives)

#### Difference from JSTOR
- OpenAlex covers all disciplines and languages (JSTOR: humanities-heavy, English-dominant)
- OpenAlex `display_name` = paper title only (abstract excluded to match JSTOR scope)
- The two indicators are designed to be complementary, not identical

#### Confirmed indicator values

| Metric | Canonical (n=98) | Non-canonical |
|---|---|---|
| Median | **3.0** | **0** |
| ≥1 hit | 79.6% | — |

#### Cross-validation with JSTOR

Both independent datasets show the same structural pattern:
```
JSTOR:    canonical median 6.5  vs  non-canonical median 0
OpenAlex: canonical median 3.0  vs  non-canonical median 0
```
This convergence confirms the pattern reflects actual scholarly attention structure, not database-specific bias.

#### Output Column Schema
| Column | Type | Description |
|---|---|---|
| `work_key` | string | `/works/OL123W` format |
| `title` | string | Work title |
| `author` | string | Author name string |
| `last_name` | string | Normalized author last name |
| `canonical` | integer | 0 or 1 |
| `oa_count` | integer | **Primary indicator** |
| `via_title` | integer | Matches via display_name field |
| `via_abstract` | integer | Always 0 (abstract matching disabled) |

---

## Stage 6: Analysis

### 6a. Shadow Canon / Hollow Canon Analysis (completed 2026-03-11)

**Script:** `scripts/shadow_hollow_analysis.py` (v2)
**Input:** `derived/jstor_mentions.tsv`
**Outputs:**
- `derived/shadow_canon.tsv` (50 works)
- `derived/hollow_canon.tsv` (23 works)
- `derived/shadow_hollow_summary.txt`

#### Hollow canon (23 works — confirmed)

Definition: canonical=1 AND jstor_mention_count=0

Because canonical status derives from McGrath et al.'s aggregation of PhD reading lists at major universities, hollow canon works are those that **doctoral programs have institutionally mandated as required reading, yet which receive no citation in the academic literature**.

**Dissertation framing:**
> "A disjunction between the pedagogical canon — works deemed essential by doctoral programs — and the research canon — works that actually circulate in academic discourse."

Representative hollow canon works:

| Work | Author | Interpretation |
|---|---|---|
| Tarzan of the Apes | Edgar Rice Burroughs | Mass popularity, zero academic attention — Huyssen's "great divide" in concrete form |
| White Fang | Jack London | Same pattern |
| The Yearling | Marjorie Kinnan Rawlings | Pulitzer Prize winner — prize status does not guarantee academic citation |
| King Coal | Upton Sinclair | Valued in political/social movement contexts, absent from literary scholarship |

#### Shadow canon (50 works — confirmed)

Definition: canonical=0 AND jstor_mention_count ≥ 5, title_norm ≥ 6 chars, author-name-as-title noise excluded.

**Dissertation framing:**
> "Works excluded from the PhD reading lists aggregated by McGrath et al., yet heavily cited in academic literature — evidence of what (and who) canonical selection omitted."

Key findings:

- **H. D. (Hilda Doolittle)** appears twice in top 10: Palimpsest (396 citations), The Hedgehog (381 citations). A female modernist writer receiving substantial academic attention while absent from the doctoral canon. Usable as concrete evidence of gender bias in canonical selection.
- **Finnegans Wake / Joyce (142 citations):** Ulysses is canonical, but this equally major work is not. "Author is canonical, work is excluded" — a distinct structural pattern.
- **The Wave / Evelyn Scott (122 citations):** Confirmed not confused with Virginia Woolf's The Waves — normalization produces "wave" ≠ "waves".
- **Virginia Woolf's non-canonical works** (The Waves 37, Between the Acts 30, The Years 25): four Woolf works are canonical; remaining major works outside the canon despite substantial academic citation.

**Known noise in shadow canon:** Stephen King "The Mist" (1980), Shakespeare, Spenser — outside 1880–1950 scope. See Known Limitation #19.

#### Core quantitative finding (citable in dissertation)
```
JSTOR:
  Canonical median citations:     7    Non-canonical median: 0
  Canonical works with ≥1 hit: 76.5%  Non-canonical: 11.1%

OpenAlex:
  Canonical median citations:     3    Non-canonical median: 0
  Canonical works with ≥1 hit: 79.6%
```

---

### 6b. Multi-Signal Agreement Analysis
**Status:** Pending — can now proceed (all four signals available)

```
Vectorise each work: [jstor, openalex, wikidata_sitelinks, hathitrust_htid_count]
→ Spearman correlation matrix between indicators
→ Cluster into 4 types:
   Type A: all indicators high → "true canon"
   Type B: Wikidata high, JSTOR low → popular but academically ignored (e.g. Tarzan)
   Type C: JSTOR high, Wikidata low → academically important, low public profile
   Type D: all indicators low → "forgotten works"
```

---

### 6c. Temporal Analysis (Citation Trends)
**Status:** Pending — requires per-year citation data from OpenAlex API (not available in snapshot)

```
For canonical 98 works:
→ Fetch individual papers via OpenAlex API (cursor pagination)
→ Aggregate by decade → visualise citation waves
→ Expected findings:
   Kate Chopin "The Awakening": spike post-1960s feminism
   Virginia Woolf: spike 1970–80s feminist criticism
   Joseph Conrad: spike 1980s postcolonial criticism
```

**Note:** year_json data is NOT available in the snapshot output — it requires individual API calls with `group_by=publication_year`. This is feasible for 98 canonical works (not 34,789).

---

## Stage 7: Preliminary Study — Critical Discourse Analysis

### Purpose and Research Motivation

Before proceeding to full multi-signal synthesis (§6b), this stage investigates **what drives critical discourse** in literary studies — that is, what actually functions as the generative force of scholarly debate, as opposed to what merely accumulates citations.

The canon-pipeline data (JSTOR, OpenAlex) measures *which works are cited*, but this is a different question from *what drives critics to write*. Stage 7 addresses the latter directly, using a corpus of Critical Inquiry articles (2019–2025) as a proxy for high-stakes critical discourse in the humanities.

**Research motivation (researcher's own framing):** In literary criticism, what drives debate appears to be authoritative interpretive claims more often than documented disparities. Whether this is actually the case — and what the structural patterns of critical argumentation look like — must be established empirically before the canon-pipeline data can be connected to existing literary-critical debates.

This stage directly serves the KCL DH conference paper, which requires a "conceptual terrain" vector (Vector 2) alongside the citation economy (Vector 1, completed) and pedagogical structures (Vector 3, completed via phd_corpus).

### The Four Vectors (KCL Conference Framework)

| Vector | Definition | Data Source | Status |
|---|---|---|---|
| 1. Attention economy | Citation formations | JSTOR + OpenAlex | ✅ Complete |
| 2. Conceptual terrain | Journal discourse | Critical Inquiry PDFs | 🔄 This stage |
| 3. Pedagogical structures | PhD reading lists | phd_corpus (McGrath et al.) | ✅ Complete |
| 4. Evaluative practice | How criticism assigns value at expansion debates | To be defined | ❌ Pending |

### Inputs

- Critical Inquiry PDFs (2019–2025): `C:\Users\tsuts\Desktop\色々使えるデータ\Critical Inquiry\2019-2025\` (254 files)
  - WSL path: `/mnt/c/Users/tsuts/Desktop/色々使えるデータ/Critical Inquiry/2019-2025/`
- `derived/jstor_mentions.tsv` (for cross-validation)
- `derived/openalex_snapshot_mentions.tsv` (for cross-validation)

### Planned Outputs

| File | Description |
|---|---|
| `derived/ci_citations.tsv` | Extracted references from all 254 PDFs |
| `derived/ci_author_freq.tsv` | Most-cited authors/critics in CI 2019–2025 |
| `derived/ci_concept_freq.tsv` | Keyword/concept frequency distribution |
| `derived/ci_intro_patterns.tsv` | Argumentative structure of introductions |

### Analytical Questions

1. **Who is cited?** Which critics, theorists, and literary figures appear most frequently in CI 2019–2025? Does this overlap with JSTOR/OpenAlex citation patterns, or diverge?
2. **What concepts drive debate?** Which terms — "canon", "modernism", "world literature", "postcolonial", "gender", "race", "expansion" — cluster in what configurations?
3. **How do introductions work?** What is the argumentative structure? What gets cited as the position to overcome ("however X argues...", "against X"), and what follows?

### Structural Tension Zones

Of particular interest are cases where novel conceptual vocabularies coexist with traditional citational hubs, or where pedagogically central authors remain peripheral in research routines. These "structural tension zones" (KCL abstract) correspond in the pipeline data to the intersection of hollow canon and shadow canon — cases like H.D., who is heavily cited in research (396 JSTOR hits) yet absent from doctoral reading lists.

### Connection to Key Theoretical Interlocutors

- **Lawrence Rainey, *Institutions of Modernism* (1998):** Modernism was constructed through institutional mechanisms. This dissertation extends that argument to doctoral curricula and academic journals.
- **Franco Moretti, *Distant Reading* (2013):** Most of world literature goes unread. This dissertation provides the English modernism version with multi-signal evidence.
- **Andreas Huyssen, *After the Great Divide* (1986):** The modernism/mass culture divide. The hollow canon (Tarzan, White Fang) is direct evidence for this structural logic.

### HathiTrust Data Capsule (Time-Sensitive: terminates September 2026)

The researcher holds a HathiTrust Research Center Data Capsule account. Priority use cases before termination:
- Temporal analysis of modernist criticism pre-2019 (outside CI coverage)
- Verification of critical movement waves (feminist criticism 1970s, postcolonial criticism 1980s) using longer time series

### Commands (To Be Created)
```bash
pip install pdfplumber --break-system-packages
python scripts/ci_extract_citations.py \
  --input "/mnt/c/Users/tsuts/Desktop/色々使えるデータ/Critical Inquiry/2019-2025/" \
  --output derived/ci_citations.tsv
python scripts/ci_discourse_analysis.py
```

### Rights / Access
- Critical Inquiry PDFs: licensed access via institutional subscription. Cannot be shared or included in the public repository. Only derived aggregate data (frequencies, patterns) will be committed.
- HathiTrust Data Capsule: analysis must remain within the capsule; only aggregate outputs may be exported.

### Evidence / Logs
- `logs/ci_extract_{date}.log`
- `logs/ci_discourse_{date}.log`

---

## Release History

| Release ID | Date | Key Artifact | Notes |
|---|---|---|---|
| population-v1 | 2026-02-22 | `ol_works_final_population.tsv` (4,833) | Initial filtered population (pilot) |
| population-v2 | 2026-03-04 | `ol_works_augmented_population.tsv` (4,884) | + phd_corpus supplement |
| population-dump-v1 | 2026-03-09 | `ol_dump_population_fiction_2026-02-28.tsv` (34,789) | Dump-based production population — **current baseline** |
| citations-v1 | 2026-03-27 | `jstor_mentions.tsv` + `openalex_snapshot_mentions.tsv` | Both citation indicators complete |

---

## Known Limitations (Cumulative)

1. `first_publish_year` mis-registration ~2.5% (unfilterable)
2. Non-fiction residual contamination ~1% post-filter
3. OL search is relevance-ranked, not random — pilot study population biased (dump-based main study is unbiased)
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
17. **work_key accuracy verified for canonical 98 works only.** For the remaining 34,691 non-canonical works, where multiple OL records share the same title, the correct edition may not have been selected. Individual non-canonical works cited in the dissertation should be manually verified against `derived/ol_dump_population_with_author.tsv`.
18. **JSTOR mention counts for non-canonical works are unrevised.** The post-hoc rescan (§5a) was applied to canonical works only. Since non-canonical works are used only in aggregate, this does not affect dissertation conclusions.
19. **Shadow canon list contains works outside the 1880–1950 scope.** `first_publish_year` filter was not re-applied during shadow canon extraction. Works such as Stephen King's "The Mist" (1980) appear in the list. Individual year verification required before citing any shadow canon entry.
20. **OpenAlex snapshot scan uses title-only matching** (abstract disabled). This ensures consistency with JSTOR but means the OpenAlex indicator does not capture works mentioned only in abstracts. The two indicators are complementary in scope, not directly comparable in absolute counts.