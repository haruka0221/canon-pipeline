# OpenAlex analysis scope: independent random sample, first 10 W (evidence draft v0.1)

Date: 2026-10-20
Status: `EXPLORATORY_EVIDENCE_DRAFT / NOT_ADJUDICATED`
Selection: first ten W drawn using the deterministic review-order hash from the already frozen independent `RANDOM_ACTIVE_80` cohort in `scope_evidence_pilot_v1`. The selection is *not* a new sample.
Scope definition: see `docs/OPENALEX_ANALYSIS_SCOPE_DRAFT_v0_1.md`.

## Provenance and safeguards

- Project W, OL Work IDs, historic OL minimum Edition-derived year, titles, and names below were taken from the read-only pilot preview supplied on 2026-10-20. They are **not** verified original-work first-publication years.
- External links are exploratory bibliographic references, not researcher-signed adjudications. Explicit publication statements, publisher/catalogue records, contemporary reviews, and secondary bookseller descriptions carry different levels of evidentiary weight.
- `IN_SCOPE_CANDIDATE`, `OUT_OF_SCOPE_CANDIDATE`, and `UNRESOLVED` are *AI-supported proposals*, not values to import into `analysis_scope_status_review`. Human status remains `NOT_REVIEWED`.
- The sample is independent of purposive high-risk cases, though one W could in principle belong to other pilot cohorts. Do not pool the first ten or purposive cohorts to claim a measured population scope rate.
- Do **not** change the historical OL population, Project W identity, OpenAlex visibility v2, prior audits, or frozen 159-W review template.

## Summary of provisional hypotheses

| Project W | OL Work | OL Edition-derived min year | Book / short title | Exploratory interpretation | Evidence strength and open question |
|---|---|---:|---|---|---|
| `W000026120` | `OL7342831W` | 1950 | *The Angel* (William J. Blake) | `UNRESOLVED` | Existence of a 1950 edition weakly attested; genre and original year not verified. |
| `W000000835` | `OL1104248W` | 1909 | *One Immortality* (H. Fielding Hall) | `IN_SCOPE_CANDIDATE` | Contemporary review calls it a novel; 1909 first-edition imprint independently supported. |
| `W000019449` | `OL43485292W` | 1892 | *A Master Workman's Oath; or, Coralie the Unfortunate* (Laura Jean Libbey) | `IN_SCOPE_CANDIDATE` | Dated nineteenth-century single love-story publication; clarify novel / separately published story threshold. |
| `W000029814` | `OL7785388W` | 1929 | *The Swamps* (Sigel Roush) | `OUT_OF_SCOPE_CANDIDATE` | Contemporary historical account describes pioneer history, not an individual novel. |
| `W000020394` | `OL44919685W` | 1935 | *Carry Me Back* (Shirley Brander) | `UNRESOLVED` | Insufficient reliable independent bibliographic confirmation of work form and original edition. |
| `W000025443` | `OL7039535W` | 1888 | *A Romance of Toronto* (Annie G. Savigny) | `IN_SCOPE_CANDIDATE` | 1888 title page explicitly states it is a novel; original English text available. |
| `W000013966` | `OL2751843W` | 1920 | *Surface and Depth* (Michael T. Gilmore) | `OUT_OF_SCOPE_CANDIDATE` | Corresponding named book is a 2003 cultural/literary-critical study; direct OL Edition linkage and false-year mechanism remain unresolved. |
| `W000017199` | `OL36949866W` | 1925 | *December the Fourteenth* (Dmitry Merezhkovsky) | `OUT_OF_SCOPE_CANDIDATE` | Contemporary 1923 review expressly identifies translation from Russian; OL 1925 is Edition-derived, not original publication year. |
| `W000025896` | `OL7212406W` | 1947 | *Anchor in the Sea* (Alan Swallow) | `OUT_OF_SCOPE_CANDIDATE` | An edited multi-author anthology of psychological fiction, not one novel. |
| `W000022732` | `OL544757W` | 1949 | *Sing, Morning Star* (Jane Oliver) | `IN_SCOPE_CANDIDATE` | 1949 English printed book and historical-novel classification supported; verify original-language and sole-work status for final review. |

## Per-work evidence and outstanding actions

### 1. W000026120 — *The Angel* (William J. Blake)

Historic OL Work: https://openlibrary.org/works/OL7342831W
A 1950 Doubleday book under this title/author is seen in secondary marketplace descriptions. This **does not** establish that the associated OL Work represents an English-language novel first published in 1950.

Evidence/source: secondary sales listing (low weight), https://www.etsy.com/uk/market/rare_first_editions_books
Next evidence: publisher catalogue, 1950 title page, contemporary review, or library catalogue with content classification.
Proposal: `UNRESOLVED`.

### 2. W000000835 — *One Immortality* (H. Fielding Hall)

Historic OL Work: https://openlibrary.org/works/OL1104248W
A 1909 Macmillan title page survives in a scanned copy. A 27 March 1909 review in *Auckland Star* explicitly calls it a novel; contemporary notices also describe its narrative of a journey and romance. Original English authorship appears consistent with the bibliographic record, though the author pseudonym/name variant should be recorded, not used to change identity.

Evidence:
- 1909 book scan / title page: https://commons.wikimedia.org/wiki/File:One_immortality_(IA_oneimmortalityfi00fieliala).pdf
- Contemporary review: https://paperspast.natlib.govt.nz/newspapers/AS19090327.2.96
- Publisher and copy catalogue: https://static-prod.lib.princeton.edu/scsites/Bliss/_Main_Catalogue/Bliss_box02_D_G.pdf

Proposal: `IN_SCOPE_CANDIDATE`. Human review: confirm identity/edition, original language, and work form.

### 3. W000019449 — *A Master Workman's Oath; or, Coralie the Unfortunate* (Laura Jean Libbey)

Historic OL Work: https://openlibrary.org/works/OL43485292W
A dated 1892 published love story exists under this author and title. It is a single named publication rather than a manifest anthology, but novel/short-story boundary needs an explicit form judgment using bibliographic or text evidence.

Evidence:
- UPenn Online Books Page listing: https://onlinebooks.library.upenn.edu/webbin/book/lookupname?key=Libbey%2C+Laura+Jean%2C+1862-1924
- Period fiction bibliography: https://assets.cengage.com/gale/psm/1000000A.pdf
- Publisher and date (digitized edition): https://play.google.com/store/books/details?id=cTVxv77e-h0C

Proposal: `IN_SCOPE_CANDIDATE`, with form threshold still open.

### 4. W000029814 — *The Swamps* (Sigel Roush)

Historic OL Work: https://openlibrary.org/works/OL7785388W
The title is represented as an account of pioneer settlement in the American Midwest, rather than a single invented novel. Contemporary Ohio historical commentary refers to it as pioneer history. Some scenes may use narrative techniques; that alone does not make the entire book an original novel.

Evidence:
- *Ohio Archaeological and Historical Quarterly*, historical description: https://resources.ohiohistory.org/ohj/search/display.php?ipp=20&page=57&pages=197-239&searchterm=burton&vol=45
- 1929 publisher promotional description (secondary reproduced): https://upload.wikimedia.org/wikipedia/commons/a/ae/Other_states_%28IA_otherstates01linc_1%29.pdf

Proposal: `OUT_OF_SCOPE_CANDIDATE` for work form; verify original book's front matter if available.

### 5. W000020394 — *Carry Me Back* (Shirley Brander)

Historic OL Work: https://openlibrary.org/works/OL44919685W
Historic data show 1935, `american_fiction` and other fiction subjects, but none alone establishes original first publication or single-novel form. The author name may be a pseudonym; that is a separate author-evidence issue.

Evidence: historic OL source record supplied in pilot; no sufficiently strong independent source secured in this draft.
Next evidence: contemporary 1935 publication announcement, national bibliography entry, or digitized first edition.
Proposal: `UNRESOLVED`.

### 6. W000025443 — *A Romance of Toronto (Founded on Fact)* (Annie G. Savigny)

Historic OL Work: https://openlibrary.org/works/OL7039535W
The digitized 1888 title page explicitly labels the book a novel, names Annie Gregg Savigny, and gives Toronto: William Briggs, 1888. The Canadiana metadata independently gives author, publication information, and language English. `Founded on fact` is not by itself disqualifying fiction evidence.

Evidence:
- Digitized 1888 title page: https://www.gutenberg.org/cache/epub/35927/pg35927-images.html
- Canadiana catalogue/scanned copy: https://www.canadiana.ca/view/oocihm.13188/178
- Dictionary of Canadian Biography: https://www.biographi.ca/en/bio/ryan_anne_gregg_13E.html

Proposal: `IN_SCOPE_CANDIDATE`.

### 7. W000013966 — *Surface and Depth* (Michael T. Gilmore)

Historic OL Work: https://openlibrary.org/works/OL2751843W
Michael T. Gilmore's *Surface and Depth: The Quest for Legibility in American Culture* is a 2003 critical study, not a 1920 novel. The historical OL min Edition-derived year of 1920 is inconsistent with the independent publication evidence. Its cause (misdated Edition, bad cluster, or historical source contamination) is **not adjudicated** here.

Evidence:
- Publisher / ISBN / 2003 listing: https://www.dymocks.com.au/surface-and-depth-by-michael-t-gilmore-9780195157765
- Scholarly publisher bio confirming the 2003 title: https://academic.oup.com/chicago-scholarship-online/book/14393/chapter-abstract/168353094

Proposal: `OUT_OF_SCOPE_CANDIDATE`, with `YEAR_EVIDENCE_CONFLICT` diagnostic. Do not repair OL identities or Editions.

### 8. W000017199 — *December the Fourteenth* (Dmitry Merezhkovsky)

Historic OL Work: https://openlibrary.org/works/OL36949866W
The book was translated from Russian by Nathalie A. Duddington. A contemporary July 1923 review describes the work as a translation; an early English edition is reported for 1923, with a 1930 later edition catalogued by the Russian State Library. Thus an English Edition dated 1925 cannot establish English-original authorship.

Evidence:
- Contemporary review: https://paperspast.natlib.govt.nz/newspapers/PBH19230721.2.116
- 1923 English edition listing: https://www.rookebooks.com/1923-december-the-fourteenth
- Later translated edition in national library catalogue: https://search.rsl.ru/ru/record/01009216843

Proposal: `OUT_OF_SCOPE_CANDIDATE` due to original language. The original Russian first-publication date remains unassigned in this draft.

### 9. W000025896 — *Anchor in the Sea* (Alan Swallow)

Historic OL Work: https://openlibrary.org/works/OL7212406W
The book is an anthology of psychological fiction edited by Alan Swallow and published in 1947. A NYPL essay independently identifies at least one included Jean Garrigue story; therefore `Alan Swallow` should not simply be taken as the author of a single fictional work.

Evidence:
- NYPL research blog: https://www.nypl.org/blog/2023/05/02/planning-jean-garrigue-reader
- OL author/work display with full title: https://openlibrary.org/authors/OL2073114A/Alan_Swallow

Proposal: `OUT_OF_SCOPE_CANDIDATE` for multi-work form.

### 10. W000022732 — *Sing, Morning Star* (Jane Oliver)

Historic OL Work: https://openlibrary.org/works/OL544757W
WorldCat catalogues an English-language 1949 Collins publication by Jane Oliver; British national bibliography metadata for the 1973 reprint explicitly state it was originally published in London in 1949. The work is described in period/reception sources as historical fiction. This is an encouraging positive scope case, but a final decision should still verify the original language and single-work form.

Evidence:
- WorldCat 1949: https://search.worldcat.org/title/6364375
- British national bibliography with original-publication note: https://obnb.uk/p10555681-sing-morning-star
- Open Library author works listing: https://openlibrary.org/authors/OL38742A/Jane_Oliver

Proposal: `IN_SCOPE_CANDIDATE`.

## Next step and decision boundary

1. Preserve this as a **source-backed, non-adjudicative draft**. Never automatically migrate its proposed statuses into the frozen 159-row template.
2. For the two unresolved cases, try one high-value bibliographic query each; if evidence remains missing, record `UNRESOLVED` rather than prolonging the search indefinitely.
3. Have the researcher review the ten cases and approve the evidence rulebook. Formal adjudication, if undertaken, belongs in a separate new, versioned artifact.
4. Only then proceed to the remaining 70 independent random W with the same documented rubric. A ten-W pilot is too small to report a stable population in-scope percentage.
