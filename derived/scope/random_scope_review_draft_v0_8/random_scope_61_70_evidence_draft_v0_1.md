# Random scope evidence review — works 61–70 (exploratory draft v0.1)

Date: 2026-10-20
Status: EXPLORATORY_EVIDENCE_DRAFT / NOT_ADJUDICATED
Cohort: independently sampled `RANDOM_ACTIVE_80`, review order 61–70, seed `scope-random80-first10-20261020` (SHA256 of seed + unit separator + Project W ID)

## Method and limits

The proposed primary OpenAlex analytical scope is a **single novel or novella originally written in English, first published 1880–1950 inclusive**. Children's and juvenile novels are not excluded solely because of intended audience. Collections, literary studies, catalogues, manuals, and translations from non-English originals are outside the primary analysis. Adaptations and novelizations need explicit form and corpus-policy review: the mere fact that the source material is a film does not by itself resolve whether a 1947 prose adaptation is a single novel.

The historical Open Library (OL) `Edition-derived min year` is **not** the conceptual work's original publication year. External records here provide evidence for AI-assisted provisional *proposals*, not researcher-approved adjudications or proof that a specific OL Edition was checked. Preserve bibliographic uncertainty and target-attribution distinctions. No OL identity, frozen evaluation, OpenAlex v2, historical population, or 159-W unreviewed template is edited.

| Order | Project W | Current OL Work | Title | Historical OL min Edition year | Proposed scope | Main reason |
|---:|---|---|---|---:|---|---|
| 61 | W000012944 | OL24309248W | Writers in Crisis | 1942 | OUT_OF_SCOPE_CANDIDATE | Academic literary criticism, not a novel |
| 62 | W000025100 | OL6917856W | The Sin of Harold Diddlebock | 1947 | UNRESOLVED | Film-based 1947 prose publication/novelization; specific edition and novel form insufficiently established |
| 63 | W000002657 | OL1254426W | The Cross of Carl | 1931 | IN_SCOPE_CANDIDATE | Original English novel/allegory, first published 1931 |
| 64 | W000019752 | OL439548W | Finding List of English Prose Fiction | 1903 | OUT_OF_SCOPE_CANDIDATE | Library bibliography/catalogue, not a literary work |
| 65 | W000029623 | OL7766063W | The Life and Death of Cleopatra | 1924 | OUT_OF_SCOPE_CANDIDATE | 1924 English translation of French-language original |
| 66 | W000028664 | OL7664092W | Write the Short Short | 1947 | OUT_OF_SCOPE_CANDIDATE | Creative-writing guide, not a single novel |
| 67 | W000010893 | OL219684W | The Days of Lamb and Coleridge | 1893 | IN_SCOPE_CANDIDATE | Original English historical romance of 1893 |
| 68 | W000011605 | OL22291578W | Front Page Deadline | 1950 | IN_SCOPE_CANDIDATE | 1950 book expressly describes itself as a fictional newspaper-crusade story |
| 69 | W000010146 | OL20110321W | Husband and Foe | 1900 | IN_SCOPE_CANDIDATE | 1900 single romance/fiction title, with stronger original-text confirmation desirable |
| 70 | W000000533 | OL1084976W | Mary | 1906 | OUT_OF_SCOPE_CANDIDATE | Norwegian-language original (1906); English translation (1909) |

**Provisional batch totals: 4 IN_SCOPE_CANDIDATE / 5 OUT_OF_SCOPE_CANDIDATE / 1 UNRESOLVED.** These are exploratory AI proposals, not researcher decisions.

## Item-level evidence and cautions

### 61 — W000012944 — *Writers in Crisis* — Maxwell Geismar

- Historical OL year: 1942; current OL Work `OL24309248W`.
- CiNii Books identifies *Writers in Crisis: The American Novel Between Two Wars* (Houghton Mifflin, 1942; ix + 299 pp.; LCCN 42015988), classifying it as twentieth-century American fiction **history and criticism** and noting discussions of Ring Lardner, Hemingway, Dos Passos, Faulkner, Wolfe, and Steinbeck. This is a critical study, not a novel.
- Proposal: `OUT_OF_SCOPE_CANDIDATE`; basis `LITERARY_CRITICISM_NOT_FICTION`.
- Caveat: do not confuse a book *about* American fiction with a work of fiction. External title/author match supports the interpretation but does not constitute an OL Edition audit.
- Evidence: https://ci.nii.ac.jp/ncid/BA6747502X ; https://www.newyorker.com/magazine/1947/12/27/1947-12-27-057-tny-cards-000026040

### 62 — W000025100 — *The Sin of Harold Diddlebock* — Harry Hershfield

- Historical OL year: 1947; current OL Work `OL6917856W`.
- The American Film Institute dates the Preston Sturges film *The Sin of Harold Diddlebock* to 1947. A contemporaneous Bart House *Film Hit of the Month* cover listing attributes a 1947 book of this title to Harry Hershfield. Later retail metadata lists Walter B. Gibson together with Hershfield and describes the book as based on the 1947 film.
- These sources establish a film-related *book*, but the exact 1947 prose edition, author/contributor roles, novel-length continuous text, and its relationship to this OL Work have not yet been independently checked.
- Proposal: `UNRESOLVED`, pending identification of the original Bart House edition and whether it is a continuous novelization. A separate analytical policy may be required for English-language film novelizations. Do **not** equate a 1947 film release with a 1947 literary work, and do not exclude every novelization categorically without a stated form rule.
- Evidence: https://catalog.afi.com/Film/25351-THE-SIN-OF-HAROLD-DIDDLEBOCK ; https://www.flickr.com/photos/123537271%40N07/sets/72177720335205482 ; https://www.barnesandnoble.com/w/the-sin-of-harold-diddlebock-walter-b-gibson/1142852622

### 63 — W000002657 — *The Cross of Carl* — Walter Owen

- Historical OL year: 1931; current OL Work `OL1254426W`.
- Edinburgh Napier University's English research blog identifies Walter Owen's *The Cross of Carl: An Allegory* as a novel published in London by Grant Richards in 1931. It was **written in 1917** but withheld from publication until 1931. It recounts an English-language, continuous wartime/supernatural allegorical narrative.
- A first-edition bibliography independently lists 1931 UK and US editions.
- Proposal: `IN_SCOPE_CANDIDATE`; basis `ORIGINAL_ENGLISH_NOVELLA_OR_NOVEL_FIRST_PUBLISHED_1931`.
- Caveat: keep year-of-composition (1917) separate from first publication (1931), and record `ALLEGORICAL_NOVEL` as a form nuance. Do not infer it was published in 1917.
- Evidence: https://blogs.napier.ac.uk/english/walter-owens-hallucinatory-the-cross-of-carl-1931/ ; https://tartaruspress.com/o23.htm

### 64 — W000019752 — *Finding List of English Prose Fiction* — Boston Public Library

- Historical OL year: 1903; current OL Work `OL439548W`.
- The Boston Public Library's *Finding list of English prose fiction in the Public library of the city of Boston* is a library finding list/catalogue. Bibliographic records of Boston Public Library's English prose fiction catalogues independently corroborate the institution's publication of title/collection lists.
- Proposal: `OUT_OF_SCOPE_CANDIDATE`; basis `LIBRARY_CATALOGUE_NOT_NOVEL`.
- Caveat: the term 'fiction' refers to *the books catalogued*, not to the genre of the catalogue itself. Detailed issue/edition dating is separate from form exclusion.
- Evidence: https://onlinebooks.library.upenn.edu/webbin/who/Boston%20Public%20Library ; https://bpl.bibliocommons.com/v2/search?origin=core-catalog-explore&query=%22Catalogs+%E2%80%94+Public+libraries.%22&searchType=subject

### 65 — W000029623 — *The Life and Death of Cleopatra* — Claude Ferval [Marguerite Aimery de Pierrebourg]

- Historical OL year: 1924; current OL Work `OL7766063W`; historical displayed author is an imperfect name variant of Marguerite Aimery de Pierrebourg.
- New York Public Library records the 1924 Garden City, NY, Doubleday, Page & Co. volume under `Claude Ferval [pseud.]`, explicitly naming M. E. Poindexter as translator. WorldCat corroborates the 1924 English translation and contributors. Editions of the French-language *La vie et la mort de Cléopâtre* also appear in bibliographies.
- Proposal: `OUT_OF_SCOPE_CANDIDATE`; basis `NON_ENGLISH_ORIGINAL_TRANSLATED_INTO_ENGLISH`.
- Caveat: the precise form of the French source (fictionalized biography versus biography/history) and precise original date are **not** adjudicated and are not necessary to establish the language exclusion. Pseudonymous author evidence must not silently change Project W identity.
- Evidence: https://www.nypl.org/research/research-catalog/browse/subjects/Cleopatra%2C%20Queen%20of%20Egypt%2C%20-30%20B.C.%20--%20Fiction. ; https://search.worldcat.org/fr/title/2884939

### 66 — W000028664 — *Write the Short Short* — Maren Elwood

- Historical OL year: 1947; current OL Work `OL7664092W`.
- CiNii Books lists a 1947 Boston publication from The Writer (xi, 348 pp.). Bookseller metadata and writing-craft discussions classify it as a **writing guide** on the short-short story, not a novel or collection of authored fiction.
- Proposal: `OUT_OF_SCOPE_CANDIDATE`; basis `WRITING_INSTRUCTION_NOT_NOVEL`.
- Caveat: this form attribution is supported by multiple secondary descriptions rather than a full original scan; it is nevertheless much stronger than inferring genre from the historical subject string `short_stories;short_story`.
- Evidence: https://ci.nii.ac.jp/ncid/BA83265028 ; https://www.ebay.com/itm/195536323914 ; https://www.writersandartists.co.uk/community/discussions/writing-courses-and-books

### 67 — W000010893 — *The Days of Lamb and Coleridge* — Alice Emma Sauerwein Lord

- Historical OL year: 1893; current OL Work `OL219684W`.
- New York Society Library's 1893/1894 accessions list records `Days of Lamb and Coleridge. A. E. Lord` under books received for 1893. Edition descriptions give the fuller subtitle `A Historical Romance` and describe the novel as a fictionalized account of Lamb and Coleridge.
- Proposal: `IN_SCOPE_CANDIDATE`; basis `ENGLISH_HISTORICAL_ROMANCE_1893`.
- Caveat: the book's treatment of identifiable historical literary figures does not by itself make it nonfiction. A scan of the original title page or a contemporary review would strengthen the evidentiary chain; modern reprint descriptions alone are not sufficient for full adjudication.
- Evidence: https://www.nysoclib.org/sites/default/files/2025-04/annual1894.pdf ; https://www.abebooks.com/9781164038764/Days-Lamb-Coleridge-Historical-Romance-1164038761/plp

### 68 — W000011605 — *Front Page Deadline* — Jack Kofoed [and Hal Leyshon]

- Historical OL year: 1950; current OL Work `OL22291578W`.
- A bibliographic first-edition listing identifies *Front Page Deadline: The Fictional Story of a Pulitzer Prize-Winning Newspaper Crusade* (New York: Merlin Press, 1950) by Jack Kofoed. Other bookseller listings explicitly name **Jack Kofoed and Hal Leyshon** as contributors, requiring separate author-role verification. One catalog describes the item at approximately 326 pp.
- Proposal: `IN_SCOPE_CANDIDATE`; basis `ENGLISH_SINGLE_FICTIONAL_NARRATIVE_1950`, but novel form remains a moderate-confidence inference from its self-described fictional story and physical extent.
- Caveat: whether it is a novelized treatment of a true historical newspaper event, which roles were played by the two named authors, and the first edition's internal structure should be checked before final confirmation. No Project W author correction follows automatically.
- Evidence: https://www.abaa.org/book/866303056 ; https://www.abebooks.com/book-search/author/kofoed-john-christian/ ; https://www.pulpartists.com/Kofoed.html

### 69 — W000010146 — *Husband and Foe* — Effie Adelaide Rowlands

- Historical OL year: 1900; current OL Work `OL20110321W`.
- A specialist Rowlands bibliography records `Husband and Foe`, New York: Street & Smith, **1900**, with a later London Hutchinson edition (1911). A genre-fiction bibliography also lists the title as a 1900 novel/fiction publication.
- Proposal: `IN_SCOPE_CANDIDATE`; basis `ENGLISH_SINGLE_ROMANCE_FICTION_1900`, medium evidence strength.
- Caveat: a direct scanned 1900 title page or contemporary account establishing one continuous novel has not yet been inspected. Do not confuse the 1911 British edition with first publication, and retain genre/form uncertainty in the record.
- Evidence: https://bearalley.blogspot.com/2010/02/effie-adelaide-rowlands.html ; https://www.fictiondb.com/author/effie-adelaide-rowlands~740424.htm

### 70 — W000000533 — *Mary* — Bjørnstjerne Bjørnson

- Historical OL year: 1906; current OL Work `OL1084976W`.
- A Scandinavian bibliography identifies *Mary* as `1906, roman, norsk` (novel, Norwegian). The 1909 English Heinemann title page explicitly states `Translated from the Norwegian by Mary Morison`; a digitization of that 1909 publication is available in Project Gutenberg.
- Proposal: `OUT_OF_SCOPE_CANDIDATE`; basis `NORWEGIAN_ORIGINAL_ENGLISH_TRANSLATION_1909`.
- Caveat: retention for a broader translation/English circulation analysis is valuable; the work should not be deleted from the corpus. The Norwegian original and English manifestation years must remain distinct.
- Evidence: https://www.danskforfatterleksikon.dk/1850tit/0081/sknr81432.htm ; https://www.gutenberg.org/cache/epub/33300/pg33300-images.html ; https://www.finna.fi/Record/kuopio.234714

## Methodological findings and follow-up

- This batch demonstrates multiple *kinds* of scope contamination: academic criticism (61), library catalogue (64), creative-writing manual (66), and literary translation (65, 70). These must be distinguishable from low scholarly visibility and from candidate-match precision.
- A movie tie-in (62) is not equivalent to the movie itself; examine the original 1947 publication and separately decide novelization eligibility. It is currently **UNRESOLVED** rather than an automatic exclusion.
- Published-on date is different from composition date (*The Cross of Carl* was reportedly composed 1917 but published 1931). Work scope is not the same as perfect edition bibliographic dating.
- `Front Page Deadline` (68) has a contributor discrepancy; bibliographic role completeness is separate from scope. `Husband and Foe` (69) is a provisional candidate with weaker source evidence than `Writers in Crisis` (61) or `Mary` (70).
- Prior exploratory totals through positions 1–60: 35 in / 17 out / 8 unresolved. Proposed positions 61–70: 4 in / 5 out / 1 unresolved. Cumulative positions 1–70: **39 in / 22 out / 9 unresolved**. This is a tally of AI-assisted exploratory proposals, **not** a population estimate or researcher-approved adjudication.
- The next fixed random batch is positions 71–80. After 80, stop individual exploration and first assess evidence quality, unresolved cases and review protocol before formal population estimates or automated scope decisions.
