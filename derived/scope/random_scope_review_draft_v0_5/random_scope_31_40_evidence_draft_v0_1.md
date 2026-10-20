# Random Scope Evidence Review — Works 31–40 (Exploratory Draft v0.1)

Date: 2026-10-20
Status: `EXPLORATORY_EVIDENCE_DRAFT / NOT_ADJUDICATED`
Cohort: independent random 80-W sample, review-order ranks 31–40 (the frozen 80-W sample; review ordering uses the previously fixed hash seed `scope-random80-first10-20261020`).

## Method and evidence caution

These notes are AI-assisted bibliographic evidence proposals, **not researcher-confirmed scope decisions**. The matching of external bibliographic items to the particular current Open Library Work records is based primarily on matching title/creator plus edition-year context; direct edition-to-OL-Work linkage was **not independently audited here**. Current OL identifiers and edition-derived minimum years are copied from the researcher's frozen review preview, not reconstructed original publication dates. If evidence is insufficient, leave the relevant field unresolved. These cases cannot be used to estimate scope prevalence until independently reviewed; do not combine purposively chosen cases with the independent random sample.

Scope criterion under consideration: individual novels/novellas **originally written in English**, first published 1880–1950 inclusive, with juvenile novels not automatically excluded. Poetry, nonfiction reference works, and translation-only records do not qualify for this particular OpenAlex primary analysis. Other dissertation analyses retain the broader data.

## Compact case register

| Rank | Project W | OL Work(s) | Query title | OL edition-derived min year | Proposed OpenAlex primary-analysis scope | Principal reason / uncertainty |
|---:|---|---|---|---|---|---|
| 31 | W000021223 | OL485558W | Wildfire | 1916 | `IN_SCOPE_CANDIDATE` | English-language Western novel; serial from 1916; book-year evidence 1916/1917 differs |
| 32 | W000032017 | OL39442957W; OL43998022W | Six to Sixteen | 1887; 1886 | `OUT_OF_SCOPE_CANDIDATE` | Serialized in 1872, book by 1875: pre-1880 original work |
| 33 | W000010698 | OL21165534W | The Holy City, Jerusalem II | 1918 | `OUT_OF_SCOPE_CANDIDATE` | Swedish original 1902; English translation published 1918 |
| 34 | W000002911 | OL13102577W | Blind Alley | 1919 | `IN_SCOPE_CANDIDATE` | English-language novel discussed among new novels in 1919; first-edition bibliographic details may be supplemented |
| 35 | W000014154 | OL28203067W | Come and Get It | 1935 | `IN_SCOPE_CANDIDATE` | 1935 English-language single novel, documented first edition |
| 36 | W000009023 | OL1836073W | To the Hilt | 1937 | `IN_SCOPE_CANDIDATE` | 1937 American title of UK original *Worth Wile*, novel by P. C. Wren; note title variant |
| 37 | W000008851 | OL18141350W | A Guide to the Best Fiction | 1932 | `OUT_OF_SCOPE_CANDIDATE` | Annotated bibliography/reference guide; 1932 expanded edition of 1903 reference work |
| 38 | W000021202 | OL485467W | The Last Trail | 1900 | `IN_SCOPE_CANDIDATE` | 1909 English-language novel; 1900 OL minimum conflicts with independent first-publication evidence |
| 39 | W000011460 | OL2221095W | Gallions Reach | 1917 | `IN_SCOPE_CANDIDATE` | 1927 English-language novel; 1917 OL minimum conflicts with independent first-publication evidence |
| 40 | W000010303 | OL20338199W | Ladders to Fire | 1946 | `IN_SCOPE_CANDIDATE` | 1946 English-language novel, first volume of linked *Cities of the Interior* novel sequence |

Proposed counts: `IN_SCOPE_CANDIDATE` = 7, `OUT_OF_SCOPE_CANDIDATE` = 3, `UNRESOLVED` = 0. These are not final adjudications. Per-field uncertainties remain even when an overall scope proposal is stable.

## Case evidence and outstanding checks

### 31 — W000021223, Zane Grey, *Wildfire*
- Current OL work: `OL485558W`. Historical OL edition-derived min year: **1916**.
- Project Gutenberg Australia records serialization in *The Country Gentleman* starting April 8, 1916, and attributes a 1916 book edition to Harper & Brothers. Zane Grey's West Society instead lists *Wildfire* as a **1917** first edition and a Harper printing code interpreted as November 1916. Google Books holds an edition cataloged Harper & Brothers **1916**. Do not silently resolve 1916 vs 1917 book-edition year.
- The work is an English-language, chaptered Western novel. Both plausible book-year dates and the attested 1916 serial are within 1880–1950.
- Proposal: `IN_SCOPE_CANDIDATE`; `FIRST_BOOK_YEAR_CONFLICT_1916_1917` should remain open separately.
- Sources:
  - https://gutenberg.net.au/ebooks/w00067.html
  - https://zgws.org/the-writings/great-western-series/
  - https://books.google.com/books?id=ZRlFAAAAIAAJ

### 32 — W000032017, Juliana Horatia Ewing, *Six to Sixteen*
- Current OL works: `OL39442957W` and `OL43998022W`; historical OL edition-derived min years: **1887** and **1886**, respectively.
- A scholarly bibliographic reference dates the serialization in *Aunt Judy's Magazine* to January–October **1872**, with London book publication by Bell & Sons in **1875** (a biographical reference cites 1876). All cited original-book possibilities predate 1880.
- Proposal: `OUT_OF_SCOPE_CANDIDATE` (`PERIOD_PRE_1880`); preserve the multiple current OL Work identities and do not merge or reinterpret them here.
- Sources:
  - https://www.researchgate.net/publication/232847684_Empire_Hysteria_and_the_Healthy_Girl_The_Deployment_of_the_Body_in_Juliana_Horatia_Ewing%27sSix_to_Sixteen
  - https://www.biographi.ca/en/bio/5530

### 33 — W000010698, Selma Lagerlöf, *The Holy City: Jerusalem II*
- Current OL work: `OL21165534W`; historical OL edition-derived min year: **1918**.
- Swedish public-library catalog documents *Jerusalem II: I det heliga landet*, Swedish original edition **1902**. Google Books has a **1918** Doubleday, Page English translation titled *The Holy City: Jerusalem II* by Velma Swanston Howard.
- Proposal: `OUT_OF_SCOPE_CANDIDATE` (`ORIGINAL_LANGUAGE_SWEDISH`), irrespective of which early twentieth-century year is assigned to the work. Retain in translation/circulation analyses.
- Sources:
  - https://www.gotabiblioteken.se/ (catalog record for *Jerusalem Del 2 Att längta hem*; notes 1902 original)
  - https://books.google.com/books/about/The_Holy_City.html?id=zeXQdkqosM4C
  - https://www.albertbonniersforlag.se/bocker/153987/jerusalem/

### 34 — W000002911, W. L. George, *Blind Alley*
- Current OL work: `OL13102577W`; historical OL edition-derived min year: **1919**.
- *The New Republic* reviewed a W. L. George book titled *Blind Alley* in May 1919. Contemporary reviews index it among novels, and a First World War fiction list catalogs it as a 1919 work by W. L. George.
- Proposal: `IN_SCOPE_CANDIDATE` (1919 single English-language novel), but **first-edition publisher/physical copy** and direct OL-edition relation can be corroborated if needed. Avoid treating a review headline alone as proof of first-book publication date.
- Sources:
  - https://www.unz.com/print/GeorgeWL-1919/
  - https://www.unz.com/print/NewRepublic-1919may03/
  - https://www.themodernnovel.org/my-lists/world-war-i/

### 35 — W000014154, Edna Ferber, *Come and Get It*
- Current OL work: `OL28203067W`; historical OL edition-derived min year: **1935**.
- WorldCat identifies a **1935 first edition**, Doubleday, Doran & Co., with Ferber as author. The current publisher's page identifies the 1935 original publication and explicitly calls it a novel.
- Proposal: `IN_SCOPE_CANDIDATE` (1935 English-language single novel).
- Sources:
  - https://search.worldcat.org/title/Come-and-get-it/oclc/869930
  - https://www.penguinrandomhouse.com/books/227180/come-and-get-it-by-edna-ferber/

### 36 — W000009023, P. C. Wren, *To the Hilt*
- Current OL work: `OL1836073W`; historical OL edition-derived min year: **1937**.
- A rare-bookseller's description of the signed **1937** John Murray UK first edition, *Worth Wile*, explicitly states the US publication title is *To the Hilt*. A genre bibliographic index lists *Worth Wile* / *To the Hilt* among Wren's novels, dated 1937.
- Proposal: `IN_SCOPE_CANDIDATE` with `TITLE_VARIANT_UK_US`; the book's first-publication title differs from the OL English-language title. The precise US imprint of the first *To the Hilt* edition has not been individually confirmed in this review.
- Sources:
  - https://www.abebooks.co.uk/signed-first-edition/WORTH-WILE-Wren-Percival-Christopher-John/10309111454/bd
  - https://www.fantasticfiction.com/w/p-c-wren/

### 37 — W000008851, Ernest A. Baker, *A Guide to the Best Fiction*
- Current OL work: `OL18141350W`; historical OL edition-derived min year: **1932**.
- The National Library of Ireland catalogs the **1932** *A Guide to the Best Fiction, English and American* by Baker and James Packman as a *new and enlarged edition*, classifies it `Fiction -- Bibliography`, and describes author-by-author annotation and indexes. CiNii records an earlier **1903** first edition under the original title *A Descriptive Guide to the Best Fiction*; a digitized 1903 title page agrees.
- Proposal: `OUT_OF_SCOPE_CANDIDATE` (`REFERENCE_BIBLIOGRAPHY_NOT_NOVEL`); original reference-book publication year is not a novel publication year.
- Sources:
  - https://catalogue.nli.ie/Record/vtls000401456
  - https://ci.nii.ac.jp/ncid/BA73984855
  - https://upload.wikimedia.org/wikipedia/commons/9/9e/A_descriptive_guide_to_the_best_fiction%2C_British_and_American_%28IA_descriptiveguide00bakeiala%29.pdf

### 38 — W000021202, Zane Grey, *The Last Trail*
- Current OL work: `OL485467W`; historical OL edition-derived min year: **1900**.
- Bibliographic descriptions give original publication as **1909**; Zane Grey's West Society separately records 1909 and a rare-book edition guide describes a 1909 A. L. Burt edition. *The Last Trail* is a single English-language historical/frontier novel.
- Proposal: `IN_SCOPE_CANDIDATE`; retain `OL_EDITION_MIN_YEAR_CONFLICT_1900_VS_1909` as a bibliographic QA flag rather than changing frozen historical source data.
- Sources:
  - https://zgws.org/the-writings/
  - https://www.nocloo.com/zane-grey-first-edition-books-identification-guide/
  - https://books.google.com/books?id=T7VfRlprX4QC

### 39 — W000011460, H. M. Tomlinson, *Gallions Reach*
- Current OL work: `OL2221095W`; historical OL edition-derived min year: **1917**.
- Publisher Bloomsbury explicitly states that Tomlinson's novel was first published in **1927**. CiNii catalogs a **1927** Heinemann book, and *The Spectator* reviewed the work in September 1927.
- Proposal: `IN_SCOPE_CANDIDATE`; retain `OL_EDITION_MIN_YEAR_CONFLICT_1917_VS_1927` for later source-level investigation without modifying prior OL artifacts.
- Sources:
  - https://www.bloomsbury.com/uk/gallions-reach-9781448214303/
  - https://ci.nii.ac.jp/ncid/BA36207343
  - https://archive.spectator.co.uk/article/3rd-september-1927/26/fiction

### 40 — W000010303, Anaïs Nin, *Ladders to Fire*
- Current OL work: `OL20338199W`; historical OL edition-derived min year: **1946**.
- Bibliography from the 1995 Swallow reprint states first publication **1946**, E. P. Dutton. Ohio University Press explicitly describes *Ladders to Fire* as the first book of a five-novel continuous sequence, *Cities of the Interior*, with volumes also individually published. This **does not mean the OL Work is an anthology of five novels**.
- Proposal: `IN_SCOPE_CANDIDATE` (individual 1946 English-language novel); note `LINKED_NOVEL_SEQUENCE` for later literary analysis.
- Sources:
  - https://ci.nii.ac.jp/ncid/BA50685888
  - https://www.ohioswallow.com/9780804011556/ladders-to-fire/
  - https://www.ohioswallow.com/9780804006668/cities-of-the-interior/

## Review completion and preservation

- Preserve `derived/scope/scope_evidence_pilot_v1/` (159-W `NOT_REVIEWED` template) unchanged.
- Do not mark any of these entries as researcher-confirmed without an explicit review action and an auditable evidence status.
- Do not change OpenAlex integrated visibility v2, Project W identities, held-out evaluations, or closed Open Library Edition audits.
- Review priority, if needed: original book publication dates of *Wildfire*; OL-linked anomalies for *The Last Trail* and *Gallions Reach*; original publication/imprint for *Blind Alley*; current OL Work edition linkage for all ten as part of later systematic review.
- Independently sampled cases should be analyzed as a sample **only after** a standardized evidence-review protocol is actually applied and reviewer status is recorded.
