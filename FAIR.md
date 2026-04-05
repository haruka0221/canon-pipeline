# FAIR.md — canon-pipeline
**FAIR Data Quality Checklist**
Last updated: 2026-04-02
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
- [x] `WORKFLOW.md` — end-to-end pipeline narrative with inputs/outputs/commands (updated 2026-04-02)
- [x] `FAIR.md` — this document (updated 2026-04-02)
- [x] `derived/prov.json` — PROV-DM provenance record for population-dump-v1 release
- [ ] **TODO:** Add `datacite.json` or equivalent structured metadata file at root level

### F3. Metadata clearly includes the identifier of the data it describes
- [x] All TSV files use `work_key` (e.g. `/works/OL37513138W`) as primary key — globally resolvable: `https://openlibrary.org/works/OL37513138W`
- [x] `htid` values resolvable at `https://babel.hathitrust.org/cgi/pt?id={htid}`
- [x] OCLC numbers resolvable at `https://worldcat.org/oclc/{number}`
- [x] Wikidata QIDs resolvable at `https://www.wikidata.org/entity/{qid}`
- [x] OpenAlex work IDs resolvable at `https://openalex.org/works/{id}`

### F4. Data is registered or indexed in a searchable resource
- [ ] **TODO:** Deposit to institutional repository (UTokyo RDUF or equivalent) at dissertation submission
- [ ] **TODO:** Register with re3data.org if data is published independently

---

## A — Accessible

### A1. Data is retrievable by an open, standardised protocol
- [x] GitHub: HTTPS access, no authentication required for public content
- [x] Source APIs (Open Library, OpenAlex, Wikidata SPARQL): open HTTP/REST
- [x] OpenAlex: polite pool access via `mailto` parameter, rate 0.2s interval
- [ ] **TODO:** `data/` directory contents (htrc-fiction_metadata.csv, phd_corpus.csv, jstor_metadata.jsonl) are NOT in GitHub — document retrieval instructions in README

### A1.2. Authentication and authorisation procedures are specified
- [x] WorldCat Entity API: OAuth 2.0 CCG documented in WORKFLOW.md Stage 4c; WSKey stored in `token.sh` (local only, GitHub禁止)
- [x] JSTOR: local file access only (no API auth required)
- [x] Critical Inquiry PDFs: institutional subscription access — derived aggregate data only in repository

### A2. Metadata remains accessible even if data is no longer available
- [x] `WORKFLOW.md`, `FAIR.md`, `derived/prov.json` retained in GitHub regardless of TSV availability

---

## I — Interoperable

### I1. Data uses a formal, accessible, broadly applicable language for knowledge representation
- [x] Primary format: TSV with explicit column headers
- [x] Primary key (`work_key`) uses Open Library URI format — globally resolvable
- [x] OCLC, htid, ISBN-10/13, LCCN, Wikidata QID — all standard bibliographic identifiers

### I2. Data uses vocabularies that follow FAIR principles
- [x] Subject terms: Open Library subject_key format (e.g. `english_fiction`, `novel`)
- [x] Wikidata QIDs link works to a globally used knowledge graph

### I3. Data includes qualified references to other data
- [x] `htrc_ol_dump_match_summary_v2.tsv` — cross-reference OL work_key ↔ HathiTrust htid
- [x] `wikidata_sitelinks_final.tsv` — cross-reference OL work_key ↔ Wikidata QID
- [x] `jstor_mentions.tsv` — derived indicator linking OL work_key to JSTOR counts
- [x] `openalex_snapshot_mentions.tsv` — derived indicator linking OL work_key to OpenAlex counts
- [x] `oa_ci_works_v2.tsv` — OA-indexed Critical Inquiry works (new 2026-04-02)
- [x] `shadow_canon_final.tsv` — non-canonical works with high JSTOR mention counts (new 2026-04-02)

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
| `work_id` | string | OL work identifier (same format as work_key: `/works/OL123W`) | `/works/OL37513138W` |
| `title` | string | Work title | `Ulysses` |
| `author` | string | Author name ⚠️ FORCE_MAP 3件は誤著者名 | `James Joyce` |
| `title_norm` | string | Normalized title (v3 rules) | `ulysses` |
| `last_name` | string | Normalized author last name | `joyce` |
| `canonical` | integer | 0 or 1 | `1` |
| `is_short` | integer | 1 if title_norm < 6 chars | `0` |
| `jstor_mention_count` | integer | **Primary JSTOR indicator** | `443` |
| `via_creators` | integer | Matches via creators_string field | `200` |
| `via_jtitle` | integer | Matches via jstor article title field | `243` |

**`ol_edition_counts.tsv`**:

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `work_key` | string | OL work identifier (`/works/OL123W` — same format as `work_id` in jstor_mentions.tsv) | `/works/OL37513138W` |
| `edition_count` | integer | Number of distinct editions in OL Editions dump | `397` |
| `ocaid` | string | Internet Archive identifier (if available) | `moonandsixpence00maug` |

**`shadow_canon_final.tsv`** (new 2026-04-02):

| Column | Type | Description |
|--------|------|-------------|
| `work_id` | string | OL work identifier |
| `title` | string | Work title |
| `author_name_pop` | string | Author name from population file |
| `first_publish_year` | string | Year from population file |
| `jstor_mention_count` | integer | JSTOR citations |
| `via_creators` | integer | |
| `via_jtitle` | integer | |
| `last_name` | string | Author last name |

⚠️ **shadow_canon_final.tsv には1880-1950スコープ外作品が残存する可能性あり。** 個別引用前に`first_publish_year`を確認すること（Known Limitation #19）。

**`oa_ci_works_v2.tsv`** (new 2026-04-02):

| Column | Type | Description |
|--------|------|-------------|
| `oa_id` | string | OpenAlex work ID |
| `title` | string | Article title |
| `year` | string | Publication year |
| `ref_count` | integer | Count of referenced works |
| `referenced_work_ids` | string (pipe-separated) | OpenAlex IDs of referenced works |

⚠️ **2023年=1件・2024年=0件は欠落（スナップショットの分散による）。referenced_works充填率27%。**

**`temporal_citations_api.tsv`** (new 2026-04-02):

| Column | Type | Description |
|--------|------|-------------|
| `work_id` | string | OL work identifier |
| `title` | string | Work title |
| `oa_title` | string | Best-match OA title |
| `pub_year` | string | Publication year (from OA) |
| `jstor` | integer | JSTOR mention count |
| `counts_by_year` | JSON string | OA citation counts by year (直近10年分のみ) |

⚠️ **counts_by_yearは直近10年分のみ。** 歴史的分析には使用不可。

**`ci_articles.tsv`**:

| Column | Type | Description |
|--------|------|-------------|
| `filename` | string | PDF filename |
| `n_pages` | integer | Page count |
| `title_extracted` | string | **全件空（取得失敗）** |
| `year_extracted` | string | Year from PDF metadata |
| `year_hint` | string | Year from filename |
| `n_footnotes` | integer | Footnote count |
| `intro_text` | string | Introduction text |

**`ci_footnotes.tsv`** (信頼できる著者頻度分析のソース):

| Column | Type | Description |
|--------|------|-------------|
| `filename` | string | Source PDF filename |
| `footnote_text` | string | Footnote content |

---

## R — Reusable

### R1. Data is described with accurate and relevant attributes
- [x] Exclusion rules fully documented in WORKFLOW.md
- [x] Known limitations enumerated in WORKFLOW.md (30 items as of 2026-04-02)
- [x] Audit results retained as evidence
- [x] Normalization rules (v3-final) fully specified — reproducible by any implementation
- [x] Hollow canon edition counts: all 23 works confirmed, missing=0 (2026-04-02)

### R1.1. Data is released with a clear and accessible data usage licence
- [ ] **TODO (HIGH PRIORITY):** Add `LICENSE` file to repository root
- Recommended: CC BY 4.0 for derived data; OL source data is CC0; JSTOR-derived counts are transformative

### R1.2. Data is associated with detailed provenance
- [x] `derived/prov.json` — PROV-DM provenance record for population-dump-v1 (frozen)
- [x] Git commit history provides coarse-grained provenance
- [x] Release History in WORKFLOW.md documents 7 releases (as of 2026-04-02)
- [ ] **TODO (TIMING 3):** Create `prov.json` for stage7-phase1-v1 when KCL paper data is frozen

### R1.3. Data meets domain-relevant community standards
- [x] Bibliographic identifiers follow library community standards
- [x] Wikidata QIDs follow Linked Open Data standards

### R1.4. Indicator Definitions and Reuse Conditions

**JSTOR `jstor_mention_count`:**
> Counts JSTOR article records where the normalized work title appears in the article title AND the normalized author last name appears in the creators field or article title. **Abstract and full text are NOT searched** (abstract field is 0.0% populated). This is a title-co-occurrence count, not a full-text mention count. Normalization: v3-final rules (see WORKFLOW.md §5a).

**OpenAlex `oa_count` (snapshot scan):**
> Counts OpenAlex Works records where the work title appears in `display_name` AND the author last name appears in `authorships`. Title minimum length: 6 characters. Covers all disciplines. Source: OpenAlex works snapshot 620GB (2025).

**OL `edition_count`:**
> Count of distinct editions registered in Open Library Editions dump (snapshot: 2026-02-28). Proxy for commercial publishing market persistence. Does not include editions not registered in OL (undercount possible). All 34,789 population works have edition_count ≥ 1.

**HathiTrust `htid_count`:**
> Count of HathiTrust volumes matched to each OL work via OCLC (v1) and title fuzzy match (v2 supplement). Works published 1924 or later are structurally absent due to copyright restrictions — their htid=0 is institutional, not indicative of low circulation. See Known Limitation #26 for bias implications.

**CI discourse indicators:**
> Author frequency counts derived from `ci_footnotes.tsv` (8,941 footnotes from 254 Critical Inquiry PDFs, 2019–2025). KEY_SCHOLARS intro_text scan is unreliable and should not be used — use footnote direct extraction only. See Known Limitation #28.

---

## Priority Actions (TODO Summary)

| Priority | Action | Timing |
|---|---|---|
| 🔴 High | Add `LICENSE` (CC BY 4.0) to repository root | Before any external sharing |
| 🔴 High | Document `data/` retrieval instructions in README | Before next session handover |
| 🟡 Medium | WORKFLOW.md: git tag `stage7-phase1-v1` on current commit | Now |
| 🟡 Medium | Create `prov.json` for stage7-phase1-v1 | When KCL paper data frozen (Timing 3) |
| 🟡 Medium | CI×OA交差検証: OA APIでfilter=ISSN+year+著者姓で再試行 | Next session |
| 🟡 Medium | Shadow canon著者属性分析（性別・人種）| 第3章執筆前 |
| 🟡 Medium | HathiTrust Data Capsule: PMLA decade別頻度集計 | 2026年9月期限 |
| 🟡 Medium | Add `datacite.json` structured metadata | Before dissertation submission |
| 🟢 Low | Map OL subject_keys to FAST/LCSH | Analysis phase |
| 🟢 Low | Register DOI via Zenodo | At public data release |
| 🟢 Low | Deposit to UTokyo institutional repository | At dissertation submission |