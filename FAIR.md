# FAIR.md — canon-pipeline
**FAIR Data Quality Checklist**
Last updated: 2026-03-04
Status: LIVING DOCUMENT — update on every major change

FAIR = Findable · Accessible · Interoperable · Reusable
Emphasis: machine-actionable aspects ("enhancing the ability of machines to automatically find and use the data").

---

## F — Findable

### F1. Data has a globally unique, persistent identifier
- [x] GitHub repository: `https://github.com/haruka0221/canon-pipeline`
- [ ] **TODO:** Assign DOI via Zenodo at first public release (population-v1 or population-v3)
- [ ] **TODO:** Each frozen release should have a git tag (e.g. `v1.0-population`)

### F2. Data is described with rich metadata
- [x] `derived/README_population.txt` — machine-readable definition of population scope, exclusion rules, known limitations
- [x] `WORKFLOW.md` — end-to-end pipeline narrative with inputs/outputs/commands
- [ ] **TODO:** Add `datacite.json` or equivalent structured metadata file at root level

### F3. Metadata clearly includes the identifier of the data it describes
- [x] All TSV files use `work_key` (e.g. `/works/OL37513138W`) as the primary key — this is a globally resolvable URI: `https://openlibrary.org/works/OL37513138W`
- [x] `htid` values are resolvable at `https://babel.hathitrust.org/cgi/pt?id={htid}`
- [x] OCLC numbers are resolvable at `https://worldcat.org/oclc/{number}`

### F4. Data is registered or indexed in a searchable resource
- [ ] **TODO:** Deposit to institutional repository (UTokyo RDUF or equivalent) at dissertation submission
- [ ] **TODO:** Register with re3data.org if data is published independently

---

## A — Accessible

### A1. Data is retrievable by an open, standardised protocol
- [x] GitHub: HTTPS access, no authentication required for public content
- [x] Source APIs (Open Library, HathiTrust Bib API): open HTTP/REST, no authentication required
- [ ] **TODO:** `data/` directory (htrc-fiction_metadata.csv, phd_corpus.csv) is NOT in GitHub — document retrieval instructions in README

### A1.1. Protocol is open, free, and universally implementable
- [x] All source data retrieved via standard HTTP GET with JSON/TSV responses

### A1.2. Authentication and authorisation procedures are specified
- [x] WorldCat Entity API: OAuth 2.0 CCG documented in WORKFLOW.md Stage 4c
- [x] Open Library: User-Agent policy documented (`HarukaResearch (tsutsui@nihu.jp)`)
- [ ] **TODO:** Document WSKey storage policy (not in repository; stored separately)

### A2. Metadata remains accessible even if data is no longer available
- [ ] **TODO:** Ensure README and WORKFLOW.md are retained in repository even if large TSV files are removed

---

## I — Interoperable

### I1. Data uses a formal, accessible, broadly applicable language for knowledge representation
- [x] Primary format: TSV (tab-separated values) with explicit column headers
- [x] Primary key (`work_key`) uses Open Library URI format — a de facto standard for book identity
- [x] OCLC numbers, htid, ISBN-10/13, LCCN — all standard bibliographic identifiers

### I2. Data uses vocabularies that follow FAIR principles
- [x] Subject terms: Open Library subject_key format (e.g. `english_fiction`, `novel`)
- [x] Genre/subject from WorldCat Entity API: FAST IDs (`http://id.worldcat.org/fast/{id}`)
- [ ] **TODO:** Map OL subject_keys to FAST or LCSH where possible for cross-dataset interoperability

### I3. Data includes qualified references to other data
- [x] `htrc_ol_match.tsv` — cross-reference between OL work_key and HathiTrust htid via OCLC
- [x] `phd_supplement_works.tsv` — cross-reference between phd_corpus titles and OL work_key
- [x] WorldCat Entity API: `creator` field links Work entities to Person entities via URI

### Column Schema (machine-readable definitions)

**`ol_works_final_population.tsv` / `ol_works_augmented_population.tsv`:**

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `work_key` | string (URI path) | OL work identifier | `/works/OL37513138W` |
| `title` | string | Work title as registered in OL | `The Adventures of Huckleberry Finn` |
| `first_publish_year` | integer | Year of first publication per OL | `1884` |
| `author_keys` | string (pipe-separated URIs) | OL author identifiers | `/authors/OL18319A` |
| `author_names` | string (pipe-separated) | Author display names | `Mark Twain` |
| `subject_keys` | string (pipe-separated) | OL subject/genre tags | `american_fiction\|novel` |
| `edition_count` | integer | Number of editions in OL | `312` |
| `source` | string | Data provenance tag | `ol_expand_offset5000` |

**`htrc_ol_match_with_ol_meta.tsv`:**

| Column | Type | Description |
|--------|------|-------------|
| `work_id` | string | OL work key (without /works/ prefix) |
| `htid` | string | HathiTrust volume ID |
| `oclc` | string | Shared OCLC number used for matching |
| `title_htrc` | string | Title as in HathiTrust record |
| `prob80_max` | float | Max fiction probability score (htrc) |
| `htid_count` | integer | Number of HathiTrust volumes matched |

---

## R — Reusable

### R1. Data is described with accurate and relevant attributes
- [x] Exclusion rules fully documented in `derived/README_population.txt` and WORKFLOW.md
- [x] Known limitations enumerated in WORKFLOW.md (10 items)
- [x] Audit results (pre/post-filter, year mismatch, identifier coverage) retained as evidence

### R1.1. Data is released with a clear and accessible data usage licence
- [ ] **TODO:** Add `LICENSE` file to repository root
- Recommended: CC BY 4.0 for derived data; note that source data (OL) is CC0

### R1.2. Data is associated with detailed provenance
- [ ] **TODO:** Create `prov.json` at population-v1 release freeze (WORKFLOW.md Stage → Release)
- [x] `source` column in all derived TSVs records which pipeline stage generated each row
- [x] Git commit history provides coarse-grained provenance

### R1.3. Data meets domain-relevant community standards
- [x] Bibliographic identifiers (OCLC, ISBN, LCCN) follow library community standards
- [x] Work-level aggregation follows the FRBR Work/Expression/Manifestation model (implicit)
- [ ] **TODO:** Consider Schema.org `Book` type annotation for metadata export

---

## Priority Actions (TODO Summary)

| Priority | Action | Timing |
|---|---|---|
| 🔴 High | Add `LICENSE` (CC BY 4.0) to repository root | Before any external sharing |
| 🔴 High | Document `data/` retrieval instructions in README | Before next session handover |
| 🟡 Medium | Create `prov.json` at population-v3 freeze | After ~15,000 expansion completes |
| 🟡 Medium | Assign git tag `v1.0-population` at freeze | After ~15,000 expansion completes |
| 🟡 Medium | Add `datacite.json` structured metadata | Before dissertation submission |
| 🟢 Low | Map OL subject_keys to FAST/LCSH | Analysis phase |
| 🟢 Low | Register DOI via Zenodo | At public data release |
| 🟢 Low | Deposit to UTokyo institutional repository | At dissertation submission |
