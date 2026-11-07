# Proposal: treating original single-author short-fiction collections in OpenAlex scope v0.2

Date: 2026-11-07
Status: `DISCUSSION_DRAFT / NOT_ADOPTED / NOT_RESEARCHER_ADJUDICATED / NO_DATA_CHANGE`.

## Why revisit

The primary OpenAlex scope proposal dated 2026-10-20 limited the scholarly-visibility analysis to individual originally English novels/novellas first published 1880–1950. That excludes James Joyce's *Dubliners* even though it is a central published unit of literary reception and scholarship. This note explores broadening that narrow literary form restriction, *without altering the historical broad Open Library corpus or existing frozen OpenAlex analysis.*

## Proposed analysis design (NOT a final decision)

- Candidate principal set: English-original prose fiction first published as an original work or identifiable single-author collection during 1880–1950; include (a) individual novel, (b) novella/short novel, and (c) original single-author short-fiction collection first issued as such during the period. The year of a collection means the earliest verified *edition with that collection's contents and identity*, not the year of its earliest contained story.
- Preserve separate form labels `INDIVIDUAL_NOVEL`, `INDIVIDUAL_NOVELLA`, `ORIGINAL_SINGLE_AUTHOR_SHORT_FICTION_COLLECTION`, `MIXED_FORM_SINGLE_AUTHOR_COLLECTION`, `INDIVIDUAL_SHORT_STORY`, `MULTI_AUTHOR_ANTHOLOGY`, `RETROSPECTIVE_SELECTED_OR_COLLECTED_WORKS`, `OTHER_NONFICTION`, `UNRESOLVED_FORM`.
- Keep the 2026-10-20 novel+novella population as a prespecified nested comparator (`NOVEL_NOVELLA_ONLY`), so conclusions can be assessed with and without newly considered collections.
- A volume must be a distinguishable collection in its own right, not just a later reprint, modern *Collected Works*, anthology of multiple authors, or a catalogue heading for an individual short story. Later posthumous collections and retrospective anthologies require their own rules and should not be automatically included.
- No automatic IN/OUT statuses from `fiction` subjects, single-author catalogue fields, page count, title keywords, or OpenAlex counts. The inclusion of individual short stories remains a distinct unresolved question; do not automatically import every component when its collection qualifies.
- Individual works and collections may both have separately analyzed scholarly attention. If a paper on "The Dead" does not literally mention *Dubliners*, the collection query may miss it; conversely a *Dubliners* paper may discuss several stories. Record `COLLECTION_CONTAINS_STORY` and `PAPER_DISCUSSSES_COLLECTION` versus `PAPER_DISCUSSSES_COMPONENT` relationships, and never add their raw counts without a deduplication/attribution rule.

## Publication-year convention for collections

Record:
1. `collection_first_edition_year`: first evidenced original publication of the collection, with contents/version tied to an edition.
2. `component_first_appearance_year(s)`: earliest public appearance of *each* included work (optionally later for complete source coverage).
3. `collection_version_id / content_signature`: identity of the contents/organization to discriminate materially different collected works under similar titles.
4. `original_language` of collection's component texts, separately from edition language, and evidence for the work/collection identity.
5. `first_english_edition_year` for translated collections, separate from original publication.
6. `review_status`, `source_evidence`, `reviewer`, `review_date`: explicit nonautomatic human decision provenance.

For an original new collection, use the collection year for the *collection-level* analysis, not the earliest story date. If the original collection first appears before 1880 but is reissued in 1880–1950, do not reclassify it as a newly created collection. If individual stories were first published before 1880 but a genuinely new authorial collection was issued during the window, decide its collection membership as a distinct publication object and retain constituent dates separately.

## Bibliographic stress tests (source citations)

| Literary object | Source-supported publication/form facts | Consequence under the candidate rule |
|---|---|---|
| James Joyce, *Dubliners* | Grant Richards published a fifteen-story volume in 1914; the author wrote components before that volume was published. [James Joyce Centre](https://jamesjoyce.ie/timeline/); [Morgan Library](https://www.themorgan.org/exhibitions/online/ulysses/dubliners); [Dublin City Council](https://www.dublincity.ie/library/blog/james-joyces-dubliners-advertised). | Collection-level `POSSIBLE_IN`, year 1914; *The Dead* and other component stories remain separate works. |
| Katherine Mansfield, *The Garden Party and Other Stories* | Library of Congress preserves an A. A. Knopf 1922 English edition with a multi-story contents list; a separate 1922 Constable printing also attested. [LOC](https://www.loc.gov/item/22011444); [1922 Constable digitization](https://en.wikisource.org/wiki/The_Garden_Party,_and_Other_Stories). | Collection-level `POSSIBLE_IN`, year 1922; individual component first appearances separate. |
| Virginia Woolf, *Monday or Tuesday* | Published in 1921 as eight stories, including "Kew Gardens" and "The Mark on the Wall" first published in 1917. [Yale Modernism Lab](https://campuspress.yale.edu/modernismlab/monday-or-tuesday/). | Collection-level `POSSIBLE_IN`, year 1921, not 1917. |
| Joseph Conrad, *Tales of Unrest* | Collection of five tales issued in 1898; most components appeared earlier separately. [Rare-book first-edition description](https://www.abaa.org/book/1614673573); [Gutenberg](https://www.gutenberg.org/ebooks/1202). | Collection-level `POSSIBLE_IN`, year 1898; story-level first appearances remain distinct. |
| Ernest Hemingway, *in our time* and *In Our Time* | A 1924 Paris edition assembled vignettes; the Boni & Liveright 1925 New York edition contained a substantially different expanded arrangement with stories. [Hemingway Society](https://hemingwaysociety.org/100-years-three-stories-and-ten-poems-1923-and-our-time-1924); [Yale Open Courses](https://oyc.yale.edu/american-studies/amst-246/lecture-2). | `VERSION_RELATIONSHIP_REVIEW`: record at least 1924 and 1925 editions/content structures, don't presume identical conceptual collections or silently merge distinct W. |
| Saki, *Reginald in Russia and Other Sketches* | Methuen 1910 collection has numerous stories and a table of contents including a component labeled "A Playlet". [Original 1910 edition transcription](https://www.gutenberg.org/files/1870/1870-h/1870-h.htm). | `MIXED_FORM_SINGLE_AUTHOR_COLLECTION_REVIEW` pending rule for mostly fiction collections with a drama/playlet item. Prior narrow-scope `LIKELY_OUT_COLLECTION` must be revisited, not automatically reversed. |
| Elizabeth Bowen, *Ann Lee's: & Other Stories* | 1926 Sidgwick & Jackson edition's contents identify 11 stories; OL 1926 Edition OL14116676M corresponds to OL Work OL724097W. [Google Books](https://books.google.com/books/about/Ann_Lee_s.html?id=rNMvD3QJQ28C); [OL edition](https://openlibrary.org/books/OL14116676M/Ann_Lee%27s). | Collection-level `POSSIBLE_IN`; prior novel-only `LIKELY_OUT_COLLECTION` is not an error under old rules but will need reevaluation IF the new rule is adopted. |

## Pending research choices / no change made

1. Does `original single-author short-fiction collection` mean only volumes released under the author's direction during their lifetime, or also first-published posthumously with a demonstrably author-organized manuscript? Default for a stable initial category: lifetime authorial volumes, separately flag posthumous/retrospective cases.
2. Should a single-author collection containing a few playlets, essays, prose poems, or nonfiction sketches enter the main form group? Recommend a separate `MIXED_FORM` stratum rather than declaring it a pure short-story collection automatically.
3. How should materially reconstituted 1924 and 1925 collections be linked? Record edition/content relationship, do not auto-union or count scholarly documents twice.
4. For serially issued individual novels, keep the 2026-10-20 period-basis review open; **do not** apply the collection-first-publication rule to novel serialization without a separate decision.
5. After user approval, amend the primary-scope design draft in a separate versioned document and only then amend researcher review instructions. Reevaluate previous first 30 **candidate** calls for `COLLECTION` cases. No official scope status issued.

## Books cited (MLA 9)

- Bowen, Elizabeth. *Ann Lee's: & Other Stories*. Sidgwick & Jackson, 1926.
- Conrad, Joseph. *Tales of Unrest*. T. Fisher Unwin, 1898.
- Hemingway, Ernest. *In Our Time*. Boni & Liveright, 1925.
- Joyce, James. *Dubliners*. Grant Richards, 1914.
- Mansfield, Katherine. *The Garden Party, and Other Stories*. A. A. Knopf, 1922.
- Saki. *Reginald in Russia, and Other Sketches*. Methuen, 1910.
