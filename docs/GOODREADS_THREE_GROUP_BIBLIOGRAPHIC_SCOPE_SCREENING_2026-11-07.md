# Three Goodreads groups: rapid bibliographic scope screening (2026-11-07)

Status: `AI_RESEARCH_SCREENING_ONLY — NOT_RESEARCHER_ADJUDICATED`.
This memo records a pragmatic recommendation so that the wider OpenAlex/Goodreads analysis need not wait for further manual review. It does NOT amend any upstream input, scope label, human-approved identity review, or existing analysis result.

## Proposed work-level screening dispositions

| Group | Source Project W IDs | Proposed disposition | Evidence and justification |
|---|---|---|---|
| Rosalynde | W000000884; W000005820; W000009109 | `SCREEN_OUT_PRE_1880_ORIGINAL` | The original work by Thomas Lodge bears a 1590 printed title page; an Open Library record for OL1109103W includes a 1907 revised edition based on the 1590 work. Later edition dates do not qualify the original work for the 1880–1950 period. |
| East Goes West | W000010194; W000016944 | `SCREEN_IN_ENGLISH_NOVEL_1937` | LTI Korea explicitly calls the original an English-language novel first published in 1937; its catalogue records Charles Scribner's Sons as the 1937 publisher. 1997 is a subsequent edition and not the original year. |
| Chita | W000006832; W000030926 | `SCREEN_IN_ENGLISH_NOVELLA_1888_1889` | First serialized in 1888 and first issued as a book by Harper & Brothers in 1889; an Oxford Academic scholarly chapter identifies Chita as a novella. Japanese bibliographic metadata marks the original language as English. Inclusion is conditional upon the stated project rule that both novels and novellas qualify; do not treat the unsupported Goodreads 1886 year as authoritative. |

These are group-level bibliographic recommendations, not seven independently adjudicated Project W inclusion flags.

## Evidence

- Lodge 1590 original title page: https://internetshakespeare.uvic.ca/doc/Rosalind_M/complete/index.html
- Open Library, OL1109103W (1907 edition based on the 1590 work): https://openlibrary.org/works/OL1109103W/Rosalynde
- LTI Korea original work (1937 English novel): https://library.ltikorea.or.kr/originalworks/100883
- LTI Korea publication metadata (1937, Charles Scribner's Sons, original language English): https://library.ltikorea.or.kr/translatedbooks/23206
- Chita 1888 serial appearance and 1889 first book: https://www.rookebooks.com/1889-chita-a-memory-of-the-last-island
- Mary Gallagher, scholarly chapter classifying Chita as a novella: https://doi.org/10.5949/UPO9781846317200.002
- CiNii Books, original language English, Chita originally Harper 1889: https://ci.nii.ac.jp/ncid/BD14128493

## Original works (MLA 9)

- Lodge, Thomas. *Rosalynde: Euphues Golden Legacie*. Printed by Thomas Orwin for T. G. and John Busbie, 1590.
- Kang, Younghill. *East Goes West: The Making of an Oriental Yankee*. Charles Scribner's Sons, 1937.
- Hearn, Lafcadio. *Chita: A Memory of Last Island*. Harper & Brothers, 1889.

## Practical closure and limitations

1. Preserve the seven researcher-approved OL Work-to-Goodreads Work source links and the frozen v0.1/v0.2 analysis releases.
2. Do not merge the seven Project W IDs into three. Goodreads Work ID convergence alone does not demonstrate Project W identity equivalence.
3. Do not duplicate ratings/reviews across Project W. The historic UCSD observations remain 36 ratings/3 reviews for East Goes West, 66/13 for Chita, and missing for Rosalynde.
4. Do not change the final corpus, individual W scope statuses, OpenAlex measures, or complete-case correlations based on this screening note.
5. Publicly indexed OL records independently inspected for OL1109103W and OL859610W; exact current pages for OL15823995W, OL18432732W, OL20153236W, OL3541275W, and OL16772696W were not independently verified in this pass. Their already-approved source-level OL→GR matches remain as approved, with no additional claim of independent OL bibliographic verification.
6. Resume the main analysis. Reopen these three groups only if a later downstream workflow truly requires final W-level inclusion/identity adjudication or a record-specific contradiction surfaces.

Reference analysis commit: `7b0b320472ac3f624a1b0479d644b19eb5989873`.
