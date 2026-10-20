# Random scope evidence review — works 51–60 (exploratory draft v0.1)

Date: 2026-10-20
Status: EXPLORATORY_EVIDENCE_DRAFT / NOT_ADJUDICATED
Cohort: independently sampled `RANDOM_ACTIVE_80`, review order 51–60, seed `scope-random80-first10-20261020` (SHA256 of seed + unit separator + Project W ID)

## Method and limits

The proposed primary OpenAlex analytical scope is a **single novel or novella originally written in English, first published 1880–1950 inclusive**. Children's/juvenile novels are not excluded merely because of their audience. Individual short stories, collections, essays, memoirs, and other borderline forms are not automatically included. Historical Open Library `Edition-derived min year` is **not** original-work publication evidence. The sources below are external supporting evidence for *proposals*, not automatically authoritative links to a Project W. No Work identities, OpenAlex v2 candidate counts, frozen judgments, or review templates are changed. AI-assisted interpretations have not been researcher-approved.

| Order | Project W | Historical OL Work | Title (short) | OL edition-derived min year | Proposed scope | Principal reason |
|---:|---|---|---|---|---|---|
| 51 | W000018126 | OL39438790W | It Is Never Too Late to Mend | 1882 | OUT_OF_SCOPE_CANDIDATE | Original novel dated 1856 |
| 52 | W000002247 | OL121864W | Double Trouble Squared | 1924 | OUT_OF_SCOPE_CANDIDATE | Published in 1991, not 1924 |
| 53 | W000006556 | OL16552687W | Mr. Dooley in Peace and in War | 1899 | OUT_OF_SCOPE_CANDIDATE | Collection of separately published satirical sketches |
| 54 | W000028099 | OL7605686W | Flying Death | 1942 | UNRESOLVED | 1942 book confirmed, but fictional novel vs exploration-derived narrative insufficiently verified |
| 55 | W000031126 | OL8934210W | Lady Rose and Mrs Memmary | 1937 | IN_SCOPE_CANDIDATE | Publisher calls it a 1937 novel |
| 56 | W000031785 | OL15147003W; OL4321250W | Mr. Popper's Penguins | 1938 | IN_SCOPE_CANDIDATE | 1938 children's novel; two authors |
| 57 | W000027249 | OL7540133W | The Road to Carolina | 1932 | IN_SCOPE_CANDIDATE | 1932 historical novel with narrative character |
| 58 | W000023108 | OL5714150W | Oh, Doctor! | 1923 | IN_SCOPE_CANDIDATE | Contemporary publication titled 'a novel' |
| 59 | W000029901 | OL7794059W | The Proud House | 1932 | IN_SCOPE_CANDIDATE | 1932 immigrant novel, contemporary and book evidence |
| 60 | W000007020 | OL16901966W | Oh, You Tex! | 1920 | IN_SCOPE_CANDIDATE | 1920 English-language western novel; continuous chapters |

**Provisional batch counts: 6 IN_SCOPE_CANDIDATE / 3 OUT_OF_SCOPE_CANDIDATE / 1 UNRESOLVED.** Not researcher-adjudicated and not an estimate for the full corpus.

## Item-level evidence and cautions

### 51 — W000018126 — *It Is Never Too Late to Mend* — Charles Reade

- Historical OL year: 1882; current OL: `OL39438790W`.
- An 1856 publication, *It Is Never Too Late to Mend: A Matter of Fact Romance* by Charles Reade, is recorded in Google Books (New York Public Library source copy). The text is an English novel; the first publication predates 1880.
- Proposal: `OUT_OF_SCOPE_CANDIDATE`, exclusion basis `ORIGINAL_PUBLICATION_BEFORE_1880`.
- Caveat: 1882 may represent a later edition; do not overwrite the historical source year or claim this individual OL edition is validated.
- Evidence: https://books.google.com/books/about/It_is_Never_Too_Late_to_Mend.html?id=8awuAAAAMAAJ

### 52 — W000002247 — *Double Trouble Squared* — Kathryn Lasky

- Historical OL year: 1924; current OL: `OL121864W`.
- OL's own 1991 edition (`OL7363694M`) is labelled *Double Trouble Squared: A Starbuck Family Adventure, Book One*, published 15 November 1991, by Kathryn Lasky; a copyright-registration-derived index independently lists 1991 publication/creation in 1990.
- The work is an English children's novel, but after 1950. OL's 'first published 1924' field conflicts sharply with edition/copyright evidence.
- Proposal: `OUT_OF_SCOPE_CANDIDATE`, basis `ORIGINAL_PUBLICATION_AFTER_1950`; `YEAR_CONFLICT_CANDIDATE` as separate metadata issue.
- Caveat: do not silently change the historical OL data or presume the mechanism by which 1924 entered the record.
- Evidence: https://openlibrary.org/books/OL7363694M/Double_Trouble_Squared ; https://www.copyrightencyclopedia.com/double-trouble-fading-away-you-are-my-love-part-2/

### 53 — W000006556 — *Mr. Dooley in Peace and in War* — Finley Peter Dunne

- Historical OL year: 1899; current OL: `OL16552687W`.
- Publisher/catalog context dates the collection to 1898, while some secondary sources state 1899. Its contents are individually titled humorous and political newspaper sketches (e.g., 'On War Preparations,' 'On the Philippines,' 'On Golf'), not chapters of one novel.
- Proposal: `OUT_OF_SCOPE_CANDIDATE`, basis `MULTI_PIECE_SKETCH_COLLECTION`.
- Caveat: precise first-book year (1898 or 1899) remains separable from the form decision and does not affect this exclusion.
- Evidence: https://bibliovault.org/BV.browse_title.epl?SortChar=M&page=27 ; https://www.bokrobot.com/read/dunne-finley-peter-mr-dooley-in-peace-and-in-war/

### 54 — W000028099 — *Flying Death: A Manga Story* — Richard C. Gill

- Historical OL year: 1942; current OL: `OL7605686W`.
- An identifiable 1942 first edition from New York: Henry Holt & Co., approximately 238 pp., appears in rare-book catalogues. A dealer describes the narrative of a young explorer seeking a medicinal drug in South America. This is compatible with an adventure story, but does not alone establish whether it is fully fictional rather than a narrative based on the author's exploratory experience.
- Proposal: `UNRESOLVED` pending stronger independent genre/form evidence (e.g., contemporary review, jacket text/foreword, library genre note or opening text).
- Caveat: a *different*, modern book titled *The Flying Death* by Matt O'Hara is unrelated. Avoid title-only matching. `Manga` in the subtitle must not be mistaken for Japanese comics.
- Evidence: https://www.abebooks.com/first-edition/Flying-Death-Manga-Story-Gill-Richard/31947308446/bd ; https://www.abebooks.com/book-search/title/manga/author/gill-richard/

### 55 — W000031126 — *Lady Rose and Mrs Memmary* — Ruby Ferguson

- Historical OL year: 1937; current OL: `OL8934210W`.
- Publisher Persephone Books explicitly calls it a 1937 novel and describes a sustained single narrative about Lady Rose. Original language is English.
- Proposal: `IN_SCOPE_CANDIDATE`, basis `ENGLISH_SINGLE_NOVEL_FIRST_PUBLISHED_1937`.
- Evidence: https://persephonebooks.co.uk/collections/grey-books/products/lady-rose-and-mrs-memmary ; https://persephonebooks.co.uk/pages/titles-by-publication-date

### 56 — W000031785 — *Mr. Popper's Penguins* — Richard AND Florence Atwater

- Historical OL year: 1938; current OL targets: `OL15147003W`, `OL4321250W`.
- Original publisher Hachette/Little, Brown identifies it as first published in 1938, a single children's novel, jointly by Richard and Florence Atwater. WorldCat also catalogs an English 1938 Boston edition naming both authors.
- Proposal: `IN_SCOPE_CANDIDATE`, basis `ENGLISH_SINGLE_CHILDRENS_NOVEL_FIRST_PUBLISHED_1938`.
- Caveat: the historical population's single displayed author 'Richard Atwater' omits Florence. Record this as author-evidence incompleteness, not an identity repair.
- Evidence: https://www.hachettebookgroup.com/titles/florence-atwater/mr-poppers-penguins/9780316058438/ ; https://search.worldcat.org/title/Mr.-Popper%27s-penguins/oclc/8338221

### 57 — W000027249 — *The Road to Carolina* — Marjorie Hill Allee

- Historical OL year: 1932; current OL: `OL7540133W`.
- Indiana authors bibliography lists publication Boston 1932; a first-edition catalog identifies Houghton Mifflin and calls it a Civil War/Underground Railroad historical novel, and another bookseller describes a continuous story involving a young man and Quaker abolitionist.
- Proposal: `IN_SCOPE_CANDIDATE`, basis `ENGLISH_SINGLE_HISTORICAL_NOVEL_1932`, medium evidence strength due to reliance on antiquarian genre description rather than a scanned original text.
- Children's/juvenile marketing is not by itself an exclusion criterion.
- Evidence: https://webapp-devel.dlib.indiana.edu/inauthors/view?docId=encyclopedia%2FVAA5365-02.xml%3Bchunk.id%3Dd1e1275%3Btoc.depth%3D1%3Btoc.id%3Dd1e1275%3Bbrand%3Dia-books%3Bdoc.view%3Ddocview%3Bquery%3D%2F1000&hit.rank= ; https://www.yesterdaysgallery.com/pages/books/37389/marjorie-hill-allee/the-road-to-carolina

### 58 — W000023108 — *Oh, Doctor!* — Harry Leon Wilson

- Historical OL year: 1923; current OL: `OL5714150W`.
- University of Pennsylvania's Online Books Page lists *Oh, doctor! a novel*, Cosmopolitan Book Corporation, 1923, with linked page images; contemporary bibliographies list the book in the same period.
- Proposal: `IN_SCOPE_CANDIDATE`, basis `ENGLISH_SINGLE_NOVEL_1923`.
- Evidence: https://onlinebooks.library.upenn.edu/webbin/book//lookupname?key=Wilson%2C+Harry+Leon%2C+1867-1939

### 59 — W000029901 — *The Proud House* — Annette Esty

- Historical OL year: 1932; current OL: `OL7794059W`.
- A 1932 Harper & Brothers first edition is catalogued; a historical Polish-language notice calls it a novel describing Polish-American immigrant life, and bibliographic records place its publication in 1932.
- Proposal: `IN_SCOPE_CANDIDATE`, basis `ENGLISH_SINGLE_NOVEL_1932`, supported by the combination of contemporary press and first-edition cataloguing.
- Caveat: a detailed narrative summary should not be inferred beyond the source; an individual OL edition match is not adjudicated.
- Evidence: https://www.abebooks.com/servlet/SearchResults?bsi=30&ds=30&dym=off&pt=book+music&rollup=off&sortby=17&vci=59065164 ; https://www.unz.com/print/1932/Articles/ ; https://www.gutenberg.org/cache/epub/11819/pg11819.html

### 60 — W000007020 — *Oh, You Tex!* — William MacLeod Raine

- Historical OL year: 1920; current OL: `OL16901966W`.
- Project Gutenberg reproduces a 1920 Houghton Mifflin title page, an original English text, and a table of contents of continuous chapters. Copyright notices include 1919 (Story-Press Corporation) and 1920 (William MacLeod Raine); whether an earlier periodical serialization occurred does not affect 1880–1950 eligibility, though it should be recorded separately if verified.
- Proposal: `IN_SCOPE_CANDIDATE`, basis `ENGLISH_SINGLE_WESTERN_NOVEL_1920`.
- Evidence: https://www.gutenberg.org/cache/epub/22328/pg22328-images.html

## Interpretation and follow-up

- Provisional totals for the full random sequence after this batch, assuming prior draft totals stand: positions 1–50 = 29 in / 14 out / 7 unresolved; 51–60 = 6 in / 3 out / 1 unresolved; positions 1–60 = **35 in / 17 out / 8 unresolved**. These are AI-assisted exploratory labels, **not** estimates or adjudicated labels.
- Strong methodological warning: *Double Trouble Squared* is a post-1950 work with a pre-1950 historical OL Work year; *It Is Never Too Late to Mend* has the opposite direction of scope contamination. Neither error can be fixed by simply filtering edition-derived years.
- Distinguish work scope, metadata-year conflicts, author completeness (Atwater coauthorship), and work–edition identity. None authorizes changing frozen records.
- Before a thesis quantitative estimate, researcher review and documented uncertainty handling remain necessary. No scope release is produced here.
