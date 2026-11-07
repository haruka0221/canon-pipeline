# OpenAlex × Goodreads percentile extremes: first-pass scope audit (2026-11-07)

Status: `AI_BIBLIOGRAPHIC_SCREENING_NOT_RESEARCHER_ADJUDICATED`. Source analytical frame: frozen `analysis_v3_ol_goodreads_provisional_comparison_v0_2`; user-provided first/last ten of `academic_vs_goodreads_percentile_contrasts.tsv` (CORE3). This memo does not modify any existing labels, scope, identities, counts, correlations, model results or holdout.

## Descriptive coefficients, before scope filtering

- CORE3 × Open Library editions: 31,160 matched Project W, Spearman 0.405520.
- CORE3 × historical Goodreads ratings: 4,642 matched Project W, Spearman 0.411970.
- CORE3 × historical Goodreads text reviews: 4,642 matched Project W, Spearman 0.431489.
- Goodreads metric coverage within OpenAlex measured population: 4,642/31,713 (14.6375%). Source selection-missingness analysis `analysis_v3_goodreads_selection_missingness_v0_1`.
- The 4,642 are non-random complete cases, not a verified 1880–1950 original-English individual-novel population.

## Extremes: bibliographic scope screening

Codes: `PRELIMINARY_OUT` = clear outside main-scope criterion on public evidence; `POSSIBLE_IN_CHECK_ENTITY` = apparent target-scope original text, but Project W/OL identity and study-wide inclusion are not human adjudicated; `FORM_OR_IDENTITY_REVIEW` = a specific work-boundary question. These are not final Project W scope labels.

### Academic-high / Goodreads-low top ten

| W | R2 query title / author | CORE3 | GR ratings | Preliminary screening | Reason/reference |
|---|---|---:|---:|---|---|
| W000022701 | Don Juan / Azorín | 21 | 4 | PRELIMINARY_OUT | Original Spanish novel, 1922; Museo Reina Sofía catalogue https://ladigitaldelreina.museoreinasofia.es/search/item/4410-don-juan-novela?offset=48 |
| W000031114 | From man to man / Olive Schreiner | 58 | 17 | POSSIBLE_IN_CHECK_ENTITY | Original novel posthumously published 1926, unfinished/editorial-history caution; https://1890s.ca/schreiner_bio/ |
| W000009797 | An Australian girl / Catherine Martin | 14 | 7 | POSSIBLE_IN_CHECK_ENTITY | English original novel, 1890; Australian Dictionary of Biography https://adbonline.anu.edu.au/biography/martin-catherine-edith-7500 |
| W000018126 | It is never too late to mend / Charles Reade | 30 | 17 | PRELIMINARY_OUT | First edition 1856; Princeton Library catalogue https://static-prod.lib.princeton.edu/scsites/parrish/21-Reade.pdf |
| W000031809 | Lalla Rookh / Thomas Moore | 62 | 26 | PRELIMINARY_OUT | Poetic narrative, first published 1817; Poetry Foundation https://www.poetryfoundation.org/poets/thomas-moore |
| W000017790 | A night in Acadie / Kate Chopin | 18 | 13 | PRELIMINARY_OUT | 1897 short-story collection, not an individual novel or novella; https://www.katechopin.org/kate-chopins-short-stories-composition-publication-dates/ |
| W000022915 | Fiction and the reading public / Q. D. Leavis | 28 | 20 | PRELIMINARY_OUT | 1932 work of literary criticism, not a novel; first-edition data https://openlibrary.org/books/OL6279868M/Fiction_and_the_reading_public |
| W000025764 | Workers in the dawn / George Gissing | 25 | 23 | POSSIBLE_IN_CHECK_ENTITY | English novel first published 1880; https://www.simonandschuster.com/books/Workers-in-The-Dawn/George-Gissing/9781911204343 (modern publisher calls it first novel; verify precise original date separately) |
| W000010046 | The Divine Fire / May Sinclair | 13 | 14 | POSSIBLE_IN_CHECK_ENTITY | English novel first published 1904; May Sinclair Society bibliography https://maysinclairsociety.com/works/ |
| W000021745 | Paz en la guerra / Miguel de Unamuno | 36 | 29 | PRELIMINARY_OUT | 1897 original Spanish novel; WorldCat catalogue https://search.worldcat.org/title/Paz-en-la-guerra/oclc/7269995 |

At least 6/10 top-ranked observed examples have clear main-scope exclusions.

### Goodreads-high / academic-low top ten

| W | R2 query title / author | CORE3 | GR ratings | Preliminary screening | Reason/reference |
|---|---|---:|---:|---|---|
| W000000972 | The Lincoln Lawyer / Michael Connelly | 0 | 163060 | PRELIMINARY_OUT | 2005 original novel, author site https://www.michaelconnelly.com/writing/thelincolnlawyer/ |
| W000019130 | Caps for sale / Esphyr Slobodkina | 0 | 74269 | PRELIMINARY_OUT | Children's illustrated picture book, not a standalone novel/novella; Open Library catalogue https://openlibrary.org/books/OL6521717M/Caps_for_sale |
| W000012852 | The Sweet Far Thing / Libba Bray | 0 | 57951 | PRELIMINARY_OUT | Original 2007 YA novel; https://books.google.com/books/about/The_Sweet_Far_Thing.html?id=w7gqAAAAYAAJ |
| W000000966 | Dance Upon the Air / Nora Roberts | 0 | 55369 | PRELIMINARY_OUT | Original 2001 novel; publisher https://www.penguinrandomhouse.com/books/317309/dance-upon-the-air-by-nora-roberts/ |
| W000031785 | Mr. Popper's Penguins / Richard Atwater [Florence Atwater also credited] | 0 | 52818 | POSSIBLE_IN_CHECK_ENTITY | Original 1938 children's novel; children’s fiction is not automatically excluded under draft novels/novellas scope; publisher https://www.hachettebookgroup.com/titles/florence-atwater/mr-poppers-penguins/9780316058438/ . R2 display omits Florence Atwater, so audit attribution/OL identity |
| W000007853 | The peach keeper / Sarah Addison Allen | 0 | 50220 | PRELIMINARY_OUT | Original 2011 novel; publisher https://www.penguinrandomhouse.com/books/2357/the-peach-keeper-by-sarah-addison-allen/9780553908138/ |
| W000006495 | The Wind Through the Keyhole / Stephen King | 0 | 48578 | PRELIMINARY_OUT | 2012 original novel; publisher https://www.hachette.co.uk/titles/stephen-king-3/the-wind-through-the-keyhole/9781444731743/ |
| W000026117 | Dragons of Spring Dawning / Margaret Weis | 0 | 44598 | PRELIMINARY_OUT | 1985 novel, coauthored by Tracy Hickman; Google Books bibliography https://books.google.com/books/about/Dragons_of_Spring_Dawning.html?id=YrLNPgAACAAJ |
| W000021003 | Winnie-the-Pooh / The House at Pooh Corner / A. A. Milne | 0 | 41436 | PRELIMINARY_OUT | Combined record representing two first-published collections (1926/1928), not one stand-alone novel/novella; OBNB https://obnb.uk/p10130817-winnie-the-pooh-the-house-at-pooh-corner-the-complete-collection-of-stories |
| W000007937 | Three Men in a Boat / Jerome K. Jerome | 0 | 40154 | POSSIBLE_IN_CHECK_ENTITY | Original 1889, categorized as comic novel by EBSCO; https://www.ebsco.com/research-starters/history/three-men-boat-say-nothing-dog-jerome-k-jerome/ . Zero candidate pairs should trigger retrieval audit, not claim of zero scholarship |

At least 8/10 top-ranked observed examples have clear main-scope exclusions.

## Interpretation and required next analytical action

- The counts 6/10 and 8/10 describe deliberately selected *extreme-ranked examples*. Do not present them as estimates of contamination prevalence among 4,642 matched W, or 32,066 active W.
- The original `academic_minus_public_percentile` ranks are based on the full frozen 4,642 matched set; dropping flagged entries from a displayed top ten is *not* a valid scope-filtered percentile comparison. Recalculate both percentiles within the same newly screened eligible comparison population.
- Do not interpret `CORE3=0` as absence of academic discussion. Query recall, academic document type, W/OA identity, and provenance require separate diagnostics.
- Next: construct a versioned, conservative all-W bibliographic **screening candidate** with original-work year, original language, and stand-alone novel/novella form independently represented. `OL historical edition min year` and Wikidata statements are evidence signals, not definitive original publication or validated scope flags.
- Partition `HIGH_CONFIDENCE_OUT` from `POSSIBLE_IN` and `UNRESOLVED`; audit a stratified sample plus high-impact ranks. Keep formal `IN_SCOPE` restricted to human-approved adjudications. Do not automatically exclude children’s novels unless the project scope explicitly introduces an adult-literature restriction.
- Maintain historical Goodreads metric provenance, untouched crosswalk v1, Project W identity, OpenAlex v3, original v0.2 correlations, holdout and human research decisions.

## Selected book references (MLA 9)

- Leavis, Q. D. *Fiction and the Reading Public*. Chatto & Windus, 1932.
- Moore, Thomas. *Lalla Rookh: An Oriental Romance*. Longman, Hurst, Rees, Orme, and Brown, 1817.
- Reade, Charles. *It Is Never Too Late to Mend: A Matter of Fact Romance*. Richard Bentley, 1856.
- Unamuno, Miguel de. *Paz en la guerra*. Fernando Fe, 1897.
- Martin, Catherine. *An Australian Girl*. Richard Bentley and Son, 1890.
- Sinclair, May. *The Divine Fire*. Constable, 1904.

These references are bibliographic source pointers, not a full validation of the dataset's entity link at each Project W.
