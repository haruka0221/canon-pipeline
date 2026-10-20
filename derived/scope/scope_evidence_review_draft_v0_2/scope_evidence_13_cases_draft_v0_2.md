# Scope evidence review — initial 13 Project W (draft v0.2)

Date: 2026-10-20  
Status: **EXPLORATORY_EVIDENCE_DRAFT / NOT_ADJUDICATED**  
Applies to: the proposed *primary OpenAlex scholarly-visibility analysis only*.

## Purpose and safeguards

This document consolidates bibliographic observations for the initial 13 purposively selected Project W. It is **not** a researcher-confirmed scope release, an identity repair, an OpenAlex candidate-precision assessment, or an edit to the 159-W pilot's `NOT_REVIEWED` template. The observations were assembled with AI assistance and should be checked against the cited records by the researcher before adjudication.

Working criterion (see `docs/OPENALEX_ANALYSIS_SCOPE_DRAFT_v0_1.md`): an **individual novel or novella first published in 1880–1950 inclusive and originally written in English**. Original-work dates are distinct from dates inferred from linked Open Library Editions; first serial publication and first book publication are recorded separately. Short stories as single works, ambiguous autobiographical fiction, and the treatment of serialization remain to be codified in a formal protocol.

The **current Project W** is the unit being screened, not automatically a unique conceptual literary work. Source links provide evidence of a publication or form; they do **not**, merely by existing, validate every OL Edition–Work link or every OpenAlex candidate. The broader corpus and the frozen integrated OpenAlex v2 are retained unchanged for circulation, edition, reception, and other analyses.

## Preliminary screen — NOT researcher decisions

| Project W | Retrieval title | OA operational candidates v2 | Preliminary screen | Reason / caveat |
|---|---|---:|---|---|
| `W000018534` | Edgar Allan Poe | 9,922 | `OUT_SCOPE_CANDIDATE` | Anthology of different works and genres; not one novel |
| `W000011932` | Steinbeck | 3,913 | `OUT_SCOPE_CANDIDATE` | *Portable Steinbeck* collection with excerpts |
| `W000021772` | Petronius | 2,960 | `OUT_SCOPE_CANDIDATE` | Classical Latin text in twentieth-century translation / collected volume; verify precise OL Edition link |
| `W000025675` | E.K. Means .. | 369 | `OUT_SCOPE_CANDIDATE` | Eight-story collection, not a single novel |
| `W000005521` | Diana | 1 | `IN_SCOPE_CANDIDATE` | University library identifies 1939 work as novel; publisher disagreement to resolve |
| `W000013110` | Sousanna | 0 | `UNRESOLVED` | Modern 2018 title matches author; historical OL Edition-derived 1918 conflicts; direct linkage not verified |
| `W000029988` | Kentucky | 0 | `UNRESOLVED` | Government-agency author, mixed literary/nonliterary subjects; no direct bibliographic resolution |
| `W000001290` | The Waste Land | 2,062 | `OUT_SCOPE_CANDIDATE` | Poem first published 1922, not prose fiction |
| `W000020154` | Pride and prejudice | 2,774 | `OUT_SCOPE_CANDIDATE` | English novel first published 1813; historical OL Edition-derived 1900 is not the work year |
| `W000016806` | Jane Eyre | 1,738 | `OUT_SCOPE_CANDIDATE` | English novel first published 1847; historical OL Edition-derived 1950 is not the work year |
| `W000016985` | Ulysses | 4,445 | `IN_SCOPE_CANDIDATE` | English novel, partially serialized from 1918, first complete book 1922; duplicate candidate sets across 3 W |
| `W000014272` | Heart of Darkness | 1,970 | `IN_SCOPE_CANDIDATE` | English novella, magazine serialization 1899, first collection appearance 1902; duplicate candidate sets across 4 W |
| `W000031539` | Dracula | 2,185 | `IN_SCOPE_CANDIDATE` | English novel first published 1897; current `OL85892W` reflects known earlier target correction |

The seven `OUT_SCOPE_CANDIDATE`, four `IN_SCOPE_CANDIDATE`, and two `UNRESOLVED` labels are **analyst/model proposals**, not human decisions. These 13 W are purposively selected, so these proportions cannot estimate the 32,066-W population. Operational candidate numbers represent frozen retrieval counts, *not* verified target references. Overlapping W groups make summing candidate totals especially hazardous.

## Work-by-work evidence and remaining checks

### 01 — W000018534, Edgar Allan Poe
- Current OL target: `OL41035W`; historical Edition-derived minimum: **1945**.
- **Observed:** OL Work displays a 1945 Viking Portable Library edition and a descriptive contents list including fiction, poetry, letters, and criticism. A later edition explicitly identifies the original 1945 publication. This is a multi-work anthology, not a single novel.
- **Proposed form:** `MULTI_WORK_ANTHOLOGY` / `OUT_SCOPE_CANDIDATE`.
- **Remaining check:** Preserve distinction between the *portable collection* and the individual tales discussed by OA records. Do not infer that all 9,922 OA candidates refer to this anthology.
- **Evidence:** `S01`.

### 02 — W000011932, Steinbeck
- Current OL target: `OL23183W`; historical Edition-derived minimum: **1943**.
- **Observed:** OL's *The Portable Steinbeck* edition details excerpts from *The Long Valley*, *The Pastures of Heaven*, *Tortilla Flat*, *In Dubious Battle*, and other works. The OL Work dates to 1943; a documented later revised edition dates to 1946.
- **Proposed form:** `MULTI_WORK_ANTHOLOGY` / `OUT_SCOPE_CANDIDATE`.
- **Remaining check:** Distinguish publication manifestations; do not relabel individual Steinbeck novels as the collection or infer OA precision from the collection's record.
- **Evidence:** `S02`.

### 03 — W000021772, Petronius
- Current OL target: `OL503904W`; historical Edition-derived minimum: **1913**.
- **Observed:** Perseus and CiNii record a 1913 Loeb Classical Library volume with Petronius's Latin *Satyricon* and English translation, alongside Seneca's *Apocolocyntosis*. This is evidence for a twentieth-century translation/collection, not an English original work from 1913.
- **Proposed form:** `CLASSICAL_TEXT_TRANSLATION_COLLECTION` / `OUT_SCOPE_CANDIDATE`.
- **Remaining check:** Directly verify which precise 1913 Edition is attached to `OL503904W`. Do not treat the external Loeb record as proof of OL Edition membership without a link.
- **Evidence:** `S03`, `S04`.

### 04 — W000025675, E.K. Means ..
- Current OL target: `OL7135516W`; historical Edition-derived minimum: **1918**.
- **Observed:** Project Gutenberg's text and table of contents describe eight named stories under the book title *E. K. Means: Is This a Title? It Is Not...*. An author name as title does not imply this is a biographical monograph.
- **Proposed form:** `SHORT_STORY_COLLECTION` / `OUT_SCOPE_CANDIDATE` under the proposed single-novel-or-novella rule.
- **Remaining check:** If the dissertation later elects to analyze story collections, retain as an eligible record for that separate population.
- **Evidence:** `S05`.

### 05 — W000005521, Diana
- Current OL target: `OL154593W`; historical Edition-derived minimum: **1939**.
- **Observed:** OL identifies *Diana: A Strange Autobiography* by Diana Frederics as a 1939 English publication. The University of Toronto library expressly describes it as a novel and discusses its later reprints.
- **Proposed form:** `AUTOBIOGRAPHICAL_NOVEL` / `IN_SCOPE_CANDIDATE`.
- **Remaining check:** The University of Toronto exhibition says *Citadel Press* for 1939, whereas a Google Books bibliographic entry says *Dial Press*. Do not choose a definitive first-edition imprint without resolving this difference. The fiction/nonfiction status should be researcher-reviewed, not inferred from the word “Autobiography” alone.
- **Evidence:** `S06`, `S07`, `S08`.

### 06 — W000013110, Sousanna
- Current OL target: `OL24793711W`; historical Edition-derived minimum: **1918**.
- **Observed:** Publisher/author information, Kirkus and Google Books identify *Sousanna: The Lost Daughter* by Sousanna Stratmann as a novel from **2018**. The author’s own biography places her birth in 1953, incompatible with authorship of an edition published in 1918.
- **Proposed category:** `YEAR_CONFLICT_AND_OL_LINKAGE_UNRESOLVED`; **no scope decision**.
- **Remaining check:** Check the actual OL Edition IDs/dates associated with `OL24793711W` against the modern book's ISBNs (9780990497752 / 9780990497783). If they match, diagnose provenance of the apparent 1918 date. Do **not** silently change the frozen historical source or assume current bibliographic identity has been fully validated.
- **Evidence:** `S09`, `S10`, `S11`. Historical 1918 value comes from frozen pipeline metadata, not external validation.

### 07 — W000029988, Kentucky
- Current OL target: `OL7840036W`; historical Edition-derived minimum: **1929**.
- **Observed in frozen metadata only:** Title *Kentucky* and the government-office author “Kentucky. Bureau of Agriculture, Labor and Statistics”; broad subject tags combine French literary terms with history, resources, politics, and industries.
- **Proposed category:** `BIBLIOGRAPHIC_ENTITY_UNRESOLVED`; **no scope decision**.
- **Remaining check:** Inspect current OL Work JSON and linked Edition identifiers; compare publisher, series, title-page title, source MARC records and authorship before assigning a form or publication year. No externally verified record is presently being asserted to match this exact Work.
- **Evidence:** `PILOT` only (historical 159-W scope pilot metadata).

### 08 — W000001290, The Waste Land
- Current OL target: `OL1142292W`; historical Edition-derived minimum: **1922**.
- **Observed:** Eliot's *The Waste Land* is a poem first published in *The Criterion* in October 1922 and subsequently issued as a book in 1922.
- **Proposed form:** `POEM` / `OUT_SCOPE_CANDIDATE`, because the working OpenAlex corpus is for novels/novellas, not all literary forms.
- **Evidence:** `S12`.

### 09 — W000020154, Pride and prejudice
- Current OL target: `OL44675271W`; historical Edition-derived minimum: **1900**.
- **Observed:** Jane Austen's House preserves/catalogues first-edition evidence dated January **1813**. A later Edition date in the OL historical source does not move the original novel's publication to 1900.
- **Proposed form/year:** `NOVEL`, original publication **1813** / `OUT_SCOPE_CANDIDATE` on original-work period.
- **Evidence:** `S13`.

### 10 — W000016806, Jane Eyre
- Current OL target: `OL34726252W`; historical Edition-derived minimum: **1950**.
- **Observed:** British Library's manuscripts catalogue identifies the autograph manuscript and the first three-volume publication on **16 October 1847**.
- **Proposed form/year:** `NOVEL`, original publication **1847** / `OUT_SCOPE_CANDIDATE` on original-work period.
- **Evidence:** `S14`.

### 11 — W000016985, Ulysses
- Current OL target: `OL35695219W`; historical Edition-derived minimum: **1922**.
- **Observed:** Episodes of Joyce's English novel were printed in *The Little Review* beginning **1918** (incomplete serialization). The first complete book was published in Paris on **2 February 1922**.
- **Proposed form/year:** `NOVEL`, first serial **1918**, complete book **1922** / `IN_SCOPE_CANDIDATE`.
- **Separate issue:** Prior OA QC found three W with exactly matching 4,445-item OA candidate sets (`W000016985`, `W000017666`, `W000030950`). This is an overlap diagnostic, not permission to merge identity or triple-count target references.
- **Evidence:** `S15`, `S16`, plus frozen prior OA QC.

### 12 — W000014272, Heart of Darkness
- Current OL target: `OL29000391W`; historical Edition-derived minimum: **1899**.
- **Observed:** Conrad's English novella was serialized in *Blackwood's Edinburgh Magazine* February–April **1899** and collected in *Youth: A Narrative, and Two Other Stories* in **1902**. A novella remains an individual work despite a collection publication manifestation.
- **Proposed form/year:** `NOVELLA`, first serial **1899**, first collection **1902** / `IN_SCOPE_CANDIDATE` under the draft novella-inclusive rule.
- **Separate issue:** Prior OA QC found four W with the same 1,970-item candidate set (`W000014272`, `W000014830`, `W000017583`, `W000030652`); no identity change follows automatically.
- **Evidence:** `S17`, plus frozen prior OA QC.

### 13 — W000031539, Dracula
- Current OL target: `OL85892W`; current target corrected in the existing frozen OL identity release; **historical enriched population does not join directly to the current target**.
- **Observed:** The British Library identifies the first edition of Bram Stoker's English novel as published on **16 May 1897** by Archibald Constable and Company, London.
- **Proposed form/year:** `NOVEL`, first book **1897** / `IN_SCOPE_CANDIDATE`.
- **Remaining check:** Preserve historical/current OL ID provenance; do not “fix” the source records or overwrite the earlier accepted target correction.
- **Evidence:** `S18` and frozen prior target-correction provenance.

## Evidence source register

| ID | Provider / resource | URL | What this supports (and does not support) |
|---|---|---|---|
| S01 | Open Library, *Edgar Allan Poe* (`OL41035W`) | https://openlibrary.org/works/OL41035W | Anthology, multiple genres, OL editions including 1945 |
| S02 | Open Library, *The Portable Steinbeck* (`OL18343133M`) | https://openlibrary.org/books/OL18343133M/The_Portable_Steinbeck | Multi-work contents and revised edition, Work link `OL23183W` |
| S03 | Perseus Catalog, Petronius *Satyricon* | https://catalog.perseus.tufts.edu/catalog/urn%3Acts%3AlatinLit%3Aphi0972.phi001.perseus-lat1 | Latin text in 1913 Loeb volume |
| S04 | CiNii Books, *Petronius / Apocolocyntosis* | https://ci.nii.ac.jp/ncid/BA55744033 | Bilingual classical volume published 1913; not OL Work membership |
| S05 | Project Gutenberg no. 59121, *E. K. Means* | https://www.gutenberg.org/ebooks/59121 | Original book title and 8-story contents |
| S06 | Open Library, *Diana* (`OL154593W`) | https://openlibrary.org/works/OL154593W | OL Work and 1939 English edition |
| S07 | University of Toronto Libraries exhibition, item 49 | https://features.library.utoronto.ca/rbsc-70-digital-exhibition/70-rare-books-special-collections-archives-a-digital-anniversary-exhibition/case-seven-items-46-57/ | Explicit literary classification as a novel and publication history |
| S08 | Google Books, *Diana: A Strange Autobiography* | https://books.google.co.uk/books?id=bUgiAQAAIAAJ | Publisher-name disagreement to resolve; corroborates 1939 |
| S09 | Google Books, *Sousanna: The Lost Daughter* | https://books.google.com/books?id=z7lTuQEACAAJ | 2018 book, title, publisher and author |
| S10 | Kirkus, *Sousanna* | https://www.kirkusreviews.com/book-reviews/sousanna-stratmann/sousanna/ | 2018 independent review of the novel |
| S11 | Author site, *Sousanna* biography | https://sousanna.net/about/ | Biographical chronological context, not direct OL record verification |
| S12 | Academy of American Poets, *The Waste Land* | https://poets.org/poem/waste-land/print | Genre and 1922 sequence of publications |
| S13 | Jane Austen's House, *Pride and Prejudice* | https://janeaustens.house/jane-austen/novels/pride-and-prejudice/ | 1813 first edition of the novel |
| S14 | British Library MS catalogue, *Jane Eyre* | https://searcharchives.bl.uk/catalog/036-002056383 | First publication in 1847 / manuscript provenance |
| S15 | Oxford University Press, Clare Hutton, *Serial Encounters* | https://academic.oup.com/book/34966 | Partial serial publication from 1918 and full book 1922 |
| S16 | Morgan Library & Museum, *Publishing Ulysses* | https://www.themorgan.org/exhibitions/online/ulysses/publishing-ulysses | First full book on 2 February 1922 |
| S17 | *At the Circulating Library*, Troy J. Bassett, *Youth* | https://www.victorianresearch.org/atcl/show_title.php?aid=2597&tid=7921 | *Heart of Darkness* 1899 serial; *Youth* 1902 collection |
| S18 | British Library, first edition of *Dracula* | https://www.britishlibrary.cn/en/works/dracula/ | Original novel first edition on 16 May 1897 |

## Remaining protocol decisions / stop conditions

1. **Human adjudication is not implied by this document.** The researcher should confirm the exact OL Work–Edition bibliographic linkage and source interpretations; only then may a separate versioned adjudication release be created.
2. **Do not let the exploratory 13-W case mix determine a population error rate.** Use the separately marked independent 80-W sample for distributional assessment, with the sampling design declared.
3. **Scope ≠ OpenAlex precision.** Classifying a Project W as a collection does not prove its individual OA hits false; classifying a novel as in-scope does not prove its candidate hits correct.
4. **No destructive operations.** No edits to integrated OpenAlex v2, Project W identity, historical OL population, frozen evaluations, or concluded Edition audits. Do not stage the unrelated untracked `derived/identity/openlibrary_r2a1_split_identity_review_pilot_v1/` directory.
5. **Next step:** Researcher reviews these 13 entries, specifically `Sousanna`, `Kentucky`, and the first-edition imprint for `Diana`. Only after the review rules are stable begin the independent 80-W sample. 
