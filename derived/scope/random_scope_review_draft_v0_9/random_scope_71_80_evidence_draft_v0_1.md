# Independent random scope review: works 71–80 — exploratory bibliographic evidence v0.1

Date: 2026-10-20 (Asia/Tokyo)
Status: **AI-assisted exploratory evidence draft; NOT researcher adjudication**.
Proposed repository location: `derived/scope/random_scope_review_draft_v0_9/random_scope_71_80_evidence_draft_v0_1.md`.

## Scope and provenance

- Population unit: Project W in the independently drawn fixed 80-W sample from 32,066 active Project W; fixed ordering uses `scope-random80-first10-20261020` and SHA-256 of the seed, a separator, and the Project W ID. These are **positions 71–80**, not a new draw.
- Eligibility under the current draft scope: a **single novel or novella originally written in English**, first published in **1880–1950 inclusive**. Children's/juvenile novels are not automatically excluded. Single short stories, story collections, translations of non-English originals, and non-fiction are not eligible.
- Historical `edition-derived year` is the minimum recorded year of linked Open Library Editions; it is **not** independent evidence of original publication. Subject labels and a generic `fiction` tag are not conclusive evidence of form or identity.
- Each classification below is provisional (`IN_SCOPE_CANDIDATE`, `OUT_OF_SCOPE_CANDIDATE`, or `UNRESOLVED`), based on cited public source evidence. Do not copy these values into researcher decision fields without review.
- No changes to OpenAlex v2, identity merges, OL source data, existing templates, or the unrelated identity pilot are proposed.

## Provisional classification summary

| Index | Project W | Short title | Provisional class | Principal basis / exception |
|---:|---|---|---|---|
| 71 | W000026408 | Captain Boycott | IN_SCOPE_CANDIDATE | English-language historical novel, 1946 |
| 72 | W000011140 | His Queen | UNRESOLVED | Evidence for a historical romance and Spanish edition; original English publication and exact OL correspondence insufficiently verified |
| 73 | W000004535 | Humor | OUT_OF_SCOPE_CANDIDATE | Appears to denote a 1927 humorous short-story anthology volume; direct match to this OL Work not proved |
| 74 | W000006667 | Killer's Choice | OUT_OF_SCOPE_CANDIDATE | First published 1957, not 1950 |
| 75 | W000017789 | The Red Lacquer Case | IN_SCOPE_CANDIDATE | 1924 single English mystery novel |
| 76 | W000004344 | A Dog at His Heel | IN_SCOPE_CANDIDATE | 1936 continuous juvenile animal adventure narrative; novel/novella form provisional |
| 77 | W000012835 | Merry Men | OUT_OF_SCOPE_CANDIDATE | 1882 short story or 1887 short-story collection, neither a single novel/novella |
| 78 | W000002690 | The Key of the Field | OUT_OF_SCOPE_CANDIDATE | 1930 independently published **short story**, not novella merely by virtue of its book format |
| 79 | W000007486 | In King Philip's War | IN_SCOPE_CANDIDATE | 1907 English historical juvenile adventure novel |
| 80 | W000023830 | Pretty Sinister | IN_SCOPE_CANDIDATE | 1929 English espionage/crime novel; OL year 1900 anomalous |

**Batch count:** 5 IN / 4 OUT / 1 UNRESOLVED (exploratory only).

## 71 — W000026408 — *Captain Boycott*, Philip Rooney

- Source OL Work: `OL7421528W`; historical edition-derived year **1946**; supplied subject signals: `fiction;fiction_general;large_type_books`.
- The National Library of Ireland catalogue records a later 1966 edition and explicitly states “First published by the Talbot Press 1946.” The *Dictionary of Irish Biography* lists *Captain Boycott* (1946) among Rooney's novels. A contemporaneous *Kirkus* review dated September 1946 describes its historical-fiction narrative set amid Irish agrarian conflict.
- English original and a single sustained historical fictional narrative are well supported. Film adaptation in 1947 is a **subsequent** derivative and not the original source of the novel; NLI separately catalogues a film tie-in as based on Rooney's novel.
- **Proposed:** `IN_SCOPE_CANDIDATE`; original year **1946**.
- Sources:
  - https://catalogue.nli.ie/Record/vtls000094254
  - https://www.dib.ie/biography/rooney-philip-a7796
  - https://www.kirkusreviews.com/book-reviews/a/philip-roony/captain-boycott/
  - https://catalogue.nli.ie/Record/vtls000077995

## 72 — W000011140 — *His Queen*, Bernard Hamilton

- Source OL Work: `OL22124651W`; historical edition-derived year **1927**; subject signal `fiction`.
- Open Library's Bernard Hamilton author listing identifies a work titled *His queen: a romance* and associates it with a 1927 first-publication label. This alone does not establish a securely checked original-English title page/edition.
- Spanish-language records document *Su Reina (His Queen)* by Bernard Hamilton. A Spanish academic discussion calls *Su reina* a popular/historical novel, with a plot involving Isabella of Castile and Columbus, and gives Barcelona 1927; a Spanish governmental bibliographic listing includes a Barcelona **1929** printing. These years may refer to different **Spanish editions**. The observed secondary-source dates should not be silently collapsed into the date of an English original.
- The novel form seems plausible; **English original publication, original publication year, and the linkage between the English-title OL Work and the specific Spanish book** still need firmer independent bibliographic evidence. Do not conflate this early twentieth-century fiction writer with the later medieval historian of the same name whose works also appear in the OL author listing.
- **Proposed:** `UNRESOLVED` (targeted check: 1927 English edition/publisher/title page and original language).
- Sources:
  - https://openlibrary.org/authors/OL28721A/Bernard_Hamilton
  - https://studylib.es/doc/8772591/imprimir-este-art%C3%ADculo---revistas-cient%C3%ADficas-de-la-uned
  - https://www.boe.es/gazeta/dias/1936/08/04/pdfs/GMD-1936-217.pdf (Spanish bibliographic notice of 1929 printing; not independently inspected page image)

## 73 — W000004535 — *Humor*, author missing

- Source OL Work: `OL15142749W`; historical edition-derived year **1927**; supplied subject signals `adventure_stories;humorous_stories;short_stories`; no representative author.
- There is a closely matching 1927 work: Grant Martin Overton (editor), *The World's One Hundred Best Short Stories*, in ten volumes (Funk & Wagnalls), **vol. 10: Humor**. Google Books displays that volume's table of contents with separate stories by Booth Tarkington, P. G. Wodehouse, Émile Zola, etc. Open Library's corresponding full-set Edition record explicitly lists `v. 10. Humor`, and its other volumes include `Adventure` (consistent with the source subject mixture).
- **IMPORTANT identity limit:** the externally found OL full-set Work is `OL7098433W`, **not** the supplied `OL15142749W`. We have not independently fetched or matched the edition(s) linked to `OL15142749W`. This is a highly plausible bibliographic identification, not a validated OL-to-OL identity mapping; the blank-author and `short_stories` evidence independently weighs against a single novel.
- **Proposed:** `OUT_OF_SCOPE_CANDIDATE` (story collection/anthology), **with exact Work linkage flagged for review**. Do not merge OL Works on this evidence.
- Sources:
  - https://books.google.com/books/about/The_World_s_One_Hundred_Best_Short_Stori.html?id=9rsOAQAAIAAJ
  - https://openlibrary.org/books/OL6706241M/The_world%27s_one_hundred_best_short_stories_...

## 74 — W000006667 — *Killer's Choice*, Ed McBain

- Source OL Work: `OL167081W`; historical edition-derived year **1950**; 87th Precinct detective-fiction subjects.
- Bibliographies list *Killer's Choice* (87th Precinct #5) as first published in **1957** by Perma Books (New York). A detailed author bibliography and reader-facing edition records concur. This is a single English-language detective novel but **outside the 1880–1950 original-publication window**.
- Source year 1950 is in conflict with first-publication evidence. The source of the earlier metadata year should be checked separately if needed for historical-data QC; do not edit original historical data.
- **Proposed:** `OUT_OF_SCOPE_CANDIDATE` — original first publication **1957**.
- Sources:
  - https://www.kaliber38.de/autoren/ed_mcbain/ed_mcbain.htm
  - https://www.goodreads.com/book/show/1158273.Killer_s_Choice
  - https://bearalley.blogspot.com/2016/10/ed-mcbain-cover-gallery.html

## 75 — W000017789 — *The Red Lacquer Case*, Patricia Wentworth

- Source OL Work: `OL3901452W`; historical edition-derived year **1924**.
- A digitized full novel identifies Wentworth and `Date of first publication: 1924`; chapters comprise a continuous detective plot. Specialist first-edition bibliography gives **June 1924, London: Melrose**. The digitized text's stated original publisher is **Hodder & Stoughton**, conflicting with the specialist first-edition bibliography, so do not select a first publisher without checking a 1924 copy.
- The conflicting publisher detail does **not** change the 1924 scope decision.
- **Proposed:** `IN_SCOPE_CANDIDATE` — original year **1924**, English mystery novel; first-publisher discrepancy noted.
- Sources:
  - https://www.fadedpage.com/books/20210716/html.php
  - https://www.classiccrimefiction.com/wentworthbib.htm

## 76 — W000004344 — *A Dog at His Heel*, Charles J. Finger

- Source OL Work: `OL1503363W`; historical edition-derived year **1936**.
- Contemporary 1938 review describes an extended, continuous adventure narrative following Jock, an Australian sheepdog, and his owner through South Africa, Argentina and elsewhere. Antiquarian descriptions show a 1936 Winston first edition with subtitle *The Story of Jock, an Australian Sheep Dog, and What Befell Him and His Companions on a Great Drive* (about 300 pages).
- This looks like **one juvenile fictional narrative**, rather than a separate-story anthology; juvenile fiction is eligible under the current scope. The term `novel` is not explicitly established in the review: retain a lower-confidence form flag rather than claiming fully adjudicated novel form.
- **Proposed:** `IN_SCOPE_CANDIDATE` — English, 1936, sustained juvenile fictional narrative, form confirmation desirable.
- Sources:
  - https://paperspast.natlib.govt.nz/periodicals/RADREC19380204.2.36
  - https://www.abebooks.co.uk/Dog-Heel-Finger-Charles-John-Winston/22859587444/bd
  - https://archives-manuscripts.dartmouth.edu/agents/people/2161

## 77 — W000012835 — *Merry Men*, Robert Louis Stevenson

- Source OL Work: `OL24123W`; historical edition-derived year **1887**; subjects `nouvelles;short_stories`.
- The titular short story *The Merry Men* appeared in *Cornhill Magazine* in **1882**; an **1887** collection *The Merry Men and Other Tales and Fables* includes six different stories. Library of Congress preserves the 1887 collection and its contents.
- Depending on the exact supplied OL Work-to-Edition mapping, this could denote an individual **short story** or an **anthology**; **neither is a single novel/novella** under the current scope. The specific bibliographic referent should be documented separately for corpus identity work, not repaired here.
- **Proposed:** `OUT_OF_SCOPE_CANDIDATE` — form exclusion.
- Sources:
  - https://robert-louis-stevenson.org/works/the-merry-men-1887/
  - https://robert-louis-stevenson.org/works-chronology/
  - https://www.loc.gov/item/20015593/

## 78 — W000002690 — *The Key of the Field*, T. F. Powys

- Source OL Work: `OL1258105W`; historical edition-derived year **1930**.
- CiNii and Eton College Library document a standalone **1930** Furnival Books no. 1 publication, roughly **39–40 pages**. Eton's genre field explicitly says **Short stories**; Harry Ransom Center's archival inventory identifies *The key of the field (story)*; a specialist Powys catalogue describes it as a story subsequently collected in *Bottle's Path* (1946).
- Important analytical distinction: a story's independent book publication **does not** establish that it is a novella. Evidence currently supports classifying it as a **short story**, not the novel/novella scope.
- **Proposed:** `OUT_OF_SCOPE_CANDIDATE` — form exclusion; consider policy review if researcher later elects to include individually published long short stories.
- Sources:
  - https://ci.nii.ac.jp/ncid/BA35787496
  - https://catalog.etoncollege.com/B24782
  - https://www.fadedpage.com/showbook.php?pid=20191150
  - https://norman.hrc.utexas.edu/fasearch/pdf/00986.pdf (archival catalogue, search-indexed transcript)

## 79 — W000007486 — *In King Philip's War*, Frederick A. Ober

- Source OL Work: `OL17671097W`; historical edition-derived year **1907**.
- Library of Congress preserves a circa **1907** New York A. L. Burt printing titled *In King Philip's War: A Story of Two Boys Captured by the Great Sachem*; **355 pages**, English, expressly catalogued under King Philip's War — Fiction. The extended historical adventure narrative is consistent with a single juvenile novel.
- **Proposed:** `IN_SCOPE_CANDIDATE` — English historical juvenile novel, **1907**.
- Source:
  - https://www.loc.gov/item/07008217/

## 80 — W000023830 — *Pretty Sinister*, Francis Beeding

- Source OL Work: `OL6342778W`; historical edition-derived year **1900**; subject signal `fiction;intelligence_service`.
- Google Books describes the **1929** Little, Brown original copy as **317 pages**, with chapter contents and a continuous spy/crime narrative; a specialist first-edition bibliography lists **1929** London Hodder & Stoughton. Thus the OL-derived **1900** is inconsistent with an actual 1929 first printing.
- Francis Beeding is a joint English-language literary pseudonym; publisher-year variation (UK and US printings) does not imply separate novels.
- **Proposed:** `IN_SCOPE_CANDIDATE` — **1929** English single suspense novel. Flag 1900 for historical-year QC, without changing underlying source.
- Sources:
  - https://books.google.com/books?id=zrM0AAAAMAAJ
  - https://www.classiccrimefiction.com/beedingbib.htm

## Next analytical step (not an automatic decision)

1. Present this evidence to the researcher for optional adjudication; leave the frozen sample/template untouched.
2. After saving all eight ten-work exploratory files, separately aggregate proposed statuses, source strengths, error modes, and identity exceptions. Do not estimate the eligible population fraction from unadjudicated suggestions.
3. Prioritize methods for separating first-original-publication dates from linked OL Edition minima; identify anthologies, individual short stories, non-fiction and translations; retain juvenile novels according to current scope.
4. In the separate researcher decision template, make ambiguity in **novella vs short story** operationally explicit before any population extrapolation.
