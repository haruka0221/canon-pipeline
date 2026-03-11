# FAIR.md — canon-pipeline
**FAIR Data Quality Checklist**
Last updated: 2026-03-11
Status: LIVING DOCUMENT — update on every major change

FAIR = Findable · Accessible · Interoperable · Reusable
Emphasis: machine-actionable aspects ("enhancing the ability of machines to automatically find and use the data").

---

## F — Findable

### F1. Data has a globally unique, persistent identifier
- [x] GitHub repository: `https://github.com/haruka0221/canon-pipeline`
- [ ] **TODO:** Assign DOI via Zenodo at first public release
- [ ] **TODO:** Each frozen release should have a git tag (e.g. `v1.0-population`)

### F2. Data is described with rich metadata
- [x] `derived/README_population.txt` — machine-readable definition of population scope, exclusion rules, known limitations
- [x] `WORKFLOW.md` — end-to-end pipeline narrative with inputs/outputs/commands (updated 2026-03-11)
- [x] `derived/prov.json` — PROV-DM provenance record for population-dump-v1 release
- [ ] **TODO:** Add `datacite.json` or equivalent structured metadata file at root level

### F3. Metadata clearly includes the identifier of the data it describes
- [x] All TSV files use `work_key` (e.g. `/works/OL37513138W`) as the primary key — globally resolvable URI: `https://openlibrary.org/works/OL37513138W`
- [x] `htid` values are resolvable at `https://babel.hathitrust.org/cgi/pt?id={htid}`
- [x] OCLC numbers are resolvable at `https://worldcat.org/oclc/{number}`
- [x] Wikidata QIDs are resolvable at `https://www.wikidata.org/entity/{qid}`

### F4. Data is registered or indexed in a searchable resource
- [ ] **TODO:** Deposit to institutional repository (UTokyo RDUF or equivalent) at dissertation submission
- [ ] **TODO:** Register with re3data.org if data is published independently

---

## A — Accessible

### A1. Data is retrievable by an open, standardised protocol
- [x] GitHub: HTTPS access, no authentication required for public content
- [x] Source APIs (Open Library, OpenAlex, Wikidata SPARQL): open HTTP/REST, no authentication required
- [x] OpenAlex: polite pool access via `mailto` parameter (`mailto=tsutsui@nihu.jp`), rate 0.2s interval
- [ ] **TODO:** `data/` directory contents (htrc-fiction_metadata.csv, phd_corpus.csv, jstor_metadata.jsonl) are NOT in GitHub — document retrieval instructions in README

### A1.1. Protocol is open, free, and universally implementable
- [x] All source data retrieved via standard HTTP GET with JSON/TSV responses

### A1.2. Authentication and authorisation procedures are specified
- [x] WorldCat Entity API: OAuth 2.0 CCG documented in WORKFLOW.md Stage 4c; WSKey stored in `token.sh` (local only)
- [x] Open Library: User-Agent policy documented (`HarukaResearch (tsutsui@nihu.jp)`)
- [x] OpenAlex: no auth required; `mailto` param used for polite pool
- [x] JSTOR: local file access only (no API auth required)
- [ ] **TODO:** Document WSKey storage policy in README

### A2. Metadata remains accessible even if data is no longer available
- [x] `WORKFLOW.md`, `FAIR.md`, `derived/prov.json` retained in GitHub regardless of TSV availability
- [ ] **TODO:** Ensure README describes how to reconstruct pipeline from scripts alone

---

## I — Interoperable

### I1. Data uses a formal, accessible, broadly applicable language for knowledge representation
- [x] Primary format: TSV (tab-separated values) with explicit column headers
- [x] Primary key (`work_key`) uses Open Library URI format — a de facto standard for book identity
- [x] OCLC numbers, htid, ISBN-10/13, LCCN, Wikidata QID — all standard bibliographic/linked-data identifiers

### I2. Data uses vocabularies that follow FAIR principles
- [x] Subject terms: Open Library subject_key format (e.g. `english_fiction`, `novel`)
- [x] Wikidata QIDs link works to a globally used knowledge graph
- [ ] **TODO:** Map OL subject_keys to FAST or LCSH where possible for cross-dataset interoperability

### I3. Data includes qualified references to other data
- [x] `htrc_ol_dump_match_summary.tsv` — cross-reference between OL work_key and HathiTrust htid via OCLC
- [x] `wikidata_sitelinks.tsv` — cross-reference between OL work_key and Wikidata QID
- [x] `jstor_mentions.tsv` — derived indicator linking OL work_key to JSTOR academic paper counts
- [x] `openalex_works_test.tsv` — derived indicator linking OL work_key to OpenAlex paper counts

### Column Schema (machine-readable definitions)

**`ol_dump_population_with_author.tsv`** (主要母集団ファイル・local only):

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `work_key` | string (URI path) | OL work identifier | `/works/OL37513138W` |
| `title` | string | Work title as registered in OL | `The Adventures of Huckleberry Finn` |
| `first_publish_year` | integer | Year of first publication (Edition-derived) | `1884` |
| `author_keys` | string (URI) | OL author identifier(s) | `/authors/OL18319A` |
| `subject_keys_str` | string (semicolon-separated) | OL subject/genre tags | `american_fiction;novel` |
| `canonical` | integer | 1 if in phd_corpus matched set, else 0 | `1` |
| `author_name` | string | Author name from OL Authors dump | `Mark Twain` |

**`jstor_mentions.tsv`**:

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `work_key` | string | OL work identifier | `/works/OL37513138W` |
| `title` | string | Work title | `Ulysses` |
| `author` | string | Author name string | `James Joyce` |
| `title_norm` | string | Normalized title (v3 rules) | `ulysses` |
| `last_name` | string | Normalized author last name | `joyce` |
| `canonical` | integer | 0 or 1 | `1` |
| `is_short` | integer | 1 if title_norm < 4 chars | `0` |
| `jstor_mention_count` | integer | **Primary JSTOR indicator** — count of JSTOR article titles co-occurring with author surname | `443` |
| `via_creators` | integer | Matches via creators_string field | `200` |
| `via_jtitle` | integer | Matches via jstor article title field | `243` |

**`openalex_works_test.tsv`** (canonical 142件テスト・GitHub管理):

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `work_key` | string | OL work identifier | `/works/OL37513138W` |
| `title` | string | Work title | `Ulysses` |
| `author` | string | Author name string | `James Joyce` |
| `last_name` | string | Normalized author last name | `joyce` |
| `oa_count_title` | integer | title-only count (reference, noisy) | `7752` |
| `oa_count_author` | integer | **Primary OA indicator** — title AND author count | `530` |

**`wikidata_sitelinks.tsv`**:

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `work_id` | string | OL work key (without /works/ prefix) | `OL37513138W` |
| `qid` | string | Wikidata entity identifier | `Q18479` |
| `sitelink_count` | integer | Number of Wikipedia language editions | `136` |

**`htrc_ol_dump_match_summary.tsv`**:

| Column | Type | Description |
|--------|------|-------------|
| `work_id` | string | OL work key (without /works/ prefix) |
| `htid` | string | HathiTrust volume ID |
| `oclc` | string | Shared OCLC number used for matching |
| `prob80_max` | float | Max fiction probability score (htrc) |
| `htid_count` | integer | Number of HathiTrust volumes matched |

---

## R — Reusable

### R1. Data is described with accurate and relevant attributes
- [x] Exclusion rules fully documented in `derived/README_population.txt` and WORKFLOW.md
- [x] Known limitations enumerated in WORKFLOW.md (16 items as of 2026-03-11)
- [x] Audit results (pre/post-filter, year mismatch, identifier coverage) retained as evidence
- [x] Normalization rules (v3-final) fully specified in WORKFLOW.md Stage 5a — reproducible by any implementation

### R1.1. Data is released with a clear and accessible data usage licence
- [ ] **TODO:** Add `LICENSE` file to repository root
- Recommended: CC BY 4.0 for derived data; OL source data is CC0; JSTOR-derived counts are transformative (counts only, no text reproduced)

### R1.2. Data is associated with detailed provenance
- [x] `derived/prov.json` — PROV-DM provenance record for population-dump-v1 (frozen)
- [x] Git commit history provides coarse-grained provenance for all script changes
- [x] `jstor_mentions.tsv` and `openalex_works_test.tsv` are GitHub-managed with commit-level traceability

### R1.3. Data meets domain-relevant community standards
- [x] Bibliographic identifiers (OCLC, ISBN, LCCN) follow library community standards
- [x] Work-level aggregation follows the FRBR Work/Expression/Manifestation model (implicit)
- [x] Wikidata QIDs follow Linked Open Data community standards
- [ ] **TODO:** Consider Schema.org `Book` type annotation for metadata export

### R1.4. Indicator Definitions and Reuse Conditions

**JSTOR `jstor_mention_count`:**
> Counts JSTOR article records (content_type="article") where the normalized work title appears in the article title AND the normalized author last name appears in the creators field or article title. **Abstract and full text are NOT searched** (abstract field is 0.0% populated in this dataset). Reusers should note this is a title-co-occurrence count, not a full-text mention count.

**OpenAlex `oa_count_author`:**
> Counts OpenAlex Works records where the work title appears in the paper title OR abstract AND the author last name appears in the same fields. Covers all disciplines. Source: OpenAlex API `title.search` filter as of 2026-03-11.

**Wikidata `sitelink_count`:**
> Number of Wikipedia language editions that have a page for the work, retrieved via SPARQL P648 (Open Library Work ID). Reflects Wikipedia editorial activity and has known language/regional biases.

---

## Priority Actions (TODO Summary)

| Priority | Action | Timing |
|---|---|---|
| 🔴 High | Add `LICENSE` (CC BY 4.0) to repository root | Before any external sharing |
| 🔴 High | Document `data/` retrieval instructions in README | Before next session handover |
| 🟡 Medium | Complete OpenAlex full scan (34,789 works) | Next session |
| 🟡 Medium | Create `prov.json` for citations-v1 release after all indicators complete | After OpenAlex full scan |
| 🟡 Medium | Add `datacite.json` structured metadata | Before dissertation submission |
| 🟢 Low | Map OL subject_keys to FAST/LCSH | Analysis phase |
| 🟢 Low | Register DOI via Zenodo | At public data release |
| 🟢 Low | Deposit to UTokyo institutional repository | At dissertation submission |