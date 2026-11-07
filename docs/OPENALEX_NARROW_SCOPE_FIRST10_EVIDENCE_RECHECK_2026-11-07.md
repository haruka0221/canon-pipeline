# OpenAlex primary-scope first-ten evidence checkpoint (2026-11-07)

Status: **BIBLIOGRAPHIC_EVIDENCE_RECHECK / NO HUMAN ADJUDICATION / NO SCOPE RELEASE**.

## Two deliberately different populations

1. **Historical broad corpus**: English-language editions/publications appearing 1880–1950, potentially including English translations and reprints of older texts. Fictional form and linkage may require further investigation. Presence in the frozen 32,066 Project W analytical frame does **not** establish strict scope or original English composition.
2. **Narrow OpenAlex primary analysis**: a single novel or novella originally written in English, originally first published 1880–1950 inclusive. Serialized-publication convention and individual short stories still require final protocol. *This is an analysis filter, not the collection scope.* Ineligible for the narrow analysis does not mean erroneous inclusion in the broad corpus.

The existing frozen `derived/scope/random_scope_80_researcher_evidence_sheet_v0_1/random_scope_80_researcher_evidence_sheet_v0_1.tsv` has 80 distinct Project W, 176 source URLs from AI-assisted evidence, and intentionally blank researcher decision fields. **Do not alter that original sheet.**

## First ten of the frozen independent random-80: initial source recheck

These are provisional research-assistant recommendations. **No row is researcher-approved.** The most significant remaining gate for every row is a defensible linkage from the cited bibliographic object to the specific Project W and associated Open Library Work.

| Rank / Project W | Bibliographic object | Initial *narrow* recommendation (NOT final) | What the cited source supports; outstanding issue |
|---|---|---|---|
| 1 W000026120 | William James Blake, *The Angel* | POSSIBLE_IN | Google Books lists the 1950 Doubleday novel, 438 pp. Original-language and target OL7342831W link still to be confirmed. [Google Books](https://books.google.com/books/about/The_Angel.html?id=_PdJAAAAMAAJ) |
| 2 W000000835 | H. Fielding, *One Immortality* | POSSIBLE_IN | An *Auckland Star* contemporary notice (27 March 1909) calls Fielding Hall's book a new novel; first full original publication and OL1104248W link still to be confirmed. [National Library of New Zealand](https://paperspast.natlib.govt.nz/newspapers/AS19090327.2.96) |
| 3 W000019449 | Laura Jean Libbey, *A Master Workman's Oath* | POSSIBLE_IN_FORM_REVIEW | Google Play Books lists a 223-page 1892 Norman L. Munro edition. Scholarly biographical bibliography lists it among Libbey's novels; check serial/original first appearance, alternate publisher records and OL43485292W. [Google Play](https://play.google.com/store/books/details?id=cTVxv77e-h0C), [biographical bibliography](https://www.encyclopedia.com/women/encyclopedias-almanacs-transcripts-and-maps/libbey-laura-jean-1862-1925) |
| 4 W000029814 | Sigel Roush, *The Swamps* | LIKELY_OUT_FORM | A first-edition bookseller's catalogue characterizes the 1929 volume as interconnected rural/pioneer sketches, mainly factual, not a single novel. Check the original foreword/contents and OL7785388W. [Antiquarian catalogue](https://www.eilenbergerrarebooks.com/uploads/1/1/3/8/113860767/erb_catalog_3._spring_miscellany.pdf) (source cited from earlier AI evidence; primary image/contents not reverified here) |
| 5 W000020394 | Shirley Brander, *Carry Me Back* | UNRESOLVED | Prior AI evidence confirmed a pseudonym but did not establish a work-specific 1935 original-language novel record. Do not assume eligibility or exclusion; verify OL44919685W. [Library of Virginia](https://www.lva.virginia.gov/collections/dvb/bio/dowdey-clifford-shirley) |
| 6 W000025443 | Annie G. Savigny, *A Romance of Toronto* | POSSIBLE_IN_STRONG_FORM_YEAR | Digitized 1888 title page explicitly identifies an English-language novel and Toronto/William Briggs imprint. Still check this is the target of OL7039535W and whether any earlier serialization changes the year convention. [Project Gutenberg original imprint transcription](https://www.gutenberg.org/cache/epub/35927/pg35927-images.html) |
| 7 W000013966 | Michael T. Gilmore, *Surface and Depth* | UNRESOLVED_TARGET_IDENTITY | Oxford University Press identifies a 2003 scholarly study (literary criticism), while the associated OL historical minimum is *1920*. The book would be OUT for narrow analysis *if* this is actually the target; the date discrepancy prevents adjudication without tracing OL2751843W. [Oxford UP](https://academic.oup.com/book/3990) |
| 8 W000017199 | Dmitry S. Merezhkovsky, *December the Fourteenth* | LIKELY_OUT_ORIGINAL_LANGUAGE | A first-English-edition bookseller record identifies 1923 Jonathan Cape translation by Nathalie A. Duddington; Russian State Library also catalogs a later English edition as translated from Russian. Confirm OL36949866W target and original Russian publication. [1923 English edition](https://www.abebooks.com/December-Fourteenth-Merezhkovsky-Dmitri-S-Jonathan/22706437109/bd), [RSL catalog](https://search.rsl.ru/ru/record/01009216843) |
| 9 W000025896 | Alan Swallow (editor), *Anchor in the Sea* | LIKELY_OUT_FORM | Open Library author bibliography calls it a 1947 anthology of psychological fiction, not a single novel. Confirm OL7212406W record and editor's role. [Open Library](https://openlibrary.org/authors/OL2073114A/Alan_Swallow) |
| 10 W000022732 | Jane Oliver, *Sing, Morning Star* | POSSIBLE_IN_FORM_REVIEW | WorldCat catalogs Collins, London, 1949, English. OBNB confirms that a 1973 edition refers back to Collins 1949. Need source proving it is an individual novel and target correspondence OL544757W. [WorldCat](https://search.worldcat.org/title/6364375), [OBNB](https://obnb.uk/p10555681-sing-morning-star) |

Caveats:
- A publisher's catalog entry, Google Books, or a modern bookseller's description is not itself a validated original-publication history.
- An Open Library Work association based on the existing identity registry is not independent bibliographic proof that the inspected edition corresponds to the W conceptual target.
- Apparent inclusion in the broad English-edition historical population may be appropriate for reprints and translations; **narrow exclusion alone is not a broad-corpus error**.
- None of the entries above changes `review_status`, `reviewer_analysis_scope_status`, or any AI, OA, OL, Goodreads, holdout, or identity data.

## Immediate review procedure

Use the *existing* 80-W sheet (not a recreated worksheet), beginning with these first ten. For each, verify the OL target first and log evidence of (a) original-language status, (b) a single novel/novella rather than collection/criticism, (c) original first-publication date with serial/complete/book distinctions where necessary. Record outcomes as `IN_SCOPE`, `OUT_OF_SCOPE`, or `UNRESOLVED` **only with researcher review**; keep the broad historical frame unchanged. If an exact W link cannot be defended, keep `UNRESOLVED_TARGET`.

No statistical estimate of out-of-scope prevalence is justified by these ten or by the original 44/26/10 AI proposal split. A narrow OpenAlex analysis release should be a separately versioned, researcher-approved membership layer joined back to the frozen OpenAlex v3 W counts—not a data deletion, an automated source-alert filter or a subset labeled from Wikidata statements alone.

## Selected verified bibliographic records (MLA 9)

- Blake, William James. *The Angel: A Novel Based on the Life of Alexander I of Russia*. Doubleday, 1950.
- Libbey, Laura Jean. *A Master Workman's Oath; or, Coralie the Unfortunate*. Norman L. Munro, 1892. (An additional bibliographic source lists a J. S. Ogilvie 1892 edition; publisher/sequence unresolved.)
- Savigny, Annie G. *A Romance of Toronto (Founded on Fact): A Novel*. William Briggs, 1888.
- Gilmore, Michael T. *Surface and Depth: The Quest for Legibility in American Culture*. Oxford UP, 2003.
- Merezhkovsky, Dmitry S. *December the Fourteenth*. Translated by Nathalie A. Duddington, Jonathan Cape, 1923. (First English edition identified in bookseller listing; further edition confirmation needed.)
