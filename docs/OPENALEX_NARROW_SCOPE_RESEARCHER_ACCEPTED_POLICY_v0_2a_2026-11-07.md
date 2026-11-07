# OpenAlex narrow scope v0.2a — researcher-accepted provisional rulebook

Date: 2026-11-07
Status: `RESEARCHER_ACCEPTED_PROVISIONAL_POLICY / NOT_MEMBERSHIP_RELEASED`
Parent: `docs/OPENALEX_NARROW_SCOPE_RESEARCHER_REVIEW_PROTOCOL_v0_2_WORKING_2026-11-07.md`
Dataset: `derived/scope/narrow_v02_researcher_accepted_2026_11_07/random80_researcher_accepted_provisional_v0_1.tsv`
Corpus frame: 34,789 historical Open Library source records; 32,066 active Project W (not modified here).

## 1. Approval provenance

The project researcher accepted the *scope method*, the pilot-15 provisional decisions (3 IN, 3 OUT, 9 UNRESOLVED) and the remaining-65 AI-prepared assessment sheet as a reasonable **provisional review** on 2026-11-07. This is NOT an assertion that they independently opened, verified and signed every edition, title page and cited source. The original 65-row sheet's column `研究者最終判定欄（空欄）` was entirely blank when provided and remains preserved as a source. The 80-row dataset records acceptance status separately from bibliographic verification and analytic release.

All 15 purposively selected protocol stress tests are members of the original fixed independent random sample of 80 Project W. Do **not** add pilot-15 separately to the 80 for denominators.

## 2. Provisional main scope and nested comparator

- **A, novel/novella:** An individual work of narrative prose fiction **originally written in English**, with its first independently evidenced original-language public appearance in **1880–1950 inclusive**. Originally English novels for children/young adults, novels with multiple authors, and novels based on historical events are *not* excluded solely because of audience, coauthorship or historical setting. Record separately original serial appearance, first complete publication, and first book publication. Any boundary-crossing chronological disagreement must be flagged and sensitivity-tested.
- **B, original single-author short-fiction collection:** A distinguishable volume first published **as a particular original collection in 1880–1950 inclusive** whose constituent fiction was originally written in English. Its date is the earliest evidenced *collection* edition with matching contents, not the earliest appearance of a component story. A frame narrative connecting distinct stories can qualify. A story published individually does not automatically qualify because it later entered a collection.
- **Main provisional stratum:** A or B when target Work/Edition, form, original language, and dating have support.
- **Nested comparator:** A only, recorded independently; a collection IN in the main stratum may be OUT in the novel/novella comparator. For the remaining 65 works, novel/novella comparator is currently `NOT_ASSESSED`, not silently inherited.
- Broad historical English-language circulation/translation corpus **remains a different population**: exclusion from narrow scope does not authorize deletion from historical data.

## 3. Bibliographic target and version identity

- Unit of assessment: exact sampled `project_work_id` and its historically/source-linked OL Work(s), not a similarly titled book found elsewhere.
- Check Work → Edition → first-edition/manifestation chain, author/editor/translator roles, title, year, publisher, contents and, when available, source-page evidence.
- Do not merge OL Work IDs solely for similar titles. For retitled novels, record original title, retitle and editions as a documented relation; do not replace a source Work or claim its link is verified without an Edition tie.
- Distinguish metadata/QC contamination (false years, wrong author, catalog misclassified as fiction) from legitimate older-source works or translated editions in the broad corpus.

## 4. Form routing and unresolved conventions

| `work_form` | v0.2a main-scope route |
|---|---|
| `INDIVIDUAL_NOVEL`, `INDIVIDUAL_NOVELLA` | IN only after evidence for original English, period, target and fiction |
| `ORIGINAL_SINGLE_AUTHOR_SHORT_FICTION_COLLECTION` | IN on identical prerequisites at collection level; framed collections allowed |
| `MIXED_FORM_SINGLE_AUTHOR_COLLECTION` | UNRESOLVED; preserve as sensitivity stratum |
| `EPISODIC_SEQUENCE`, uncertain single story/novella, testimony versus fiction | UNRESOLVED until explicit form/length/fiction criterion and source check |
| `FILM_NOVELIZATION` | UNRESOLVED for policy on derivative prose fiction and book/film identity |
| `INDIVIDUAL_SHORT_STORY` | OUT under this v0.2 main policy (not automatically novella even in standalone booklet) |
| `MULTI_AUTHOR_ANTHOLOGY`, secondary edited/retrospective collections | OUT if exact target and editorial identity confirmed; otherwise UNRESOLVED |
| `OTHER_NONFICTION`, `CRITICISM`, `CATALOG_REFERENCE`, `WRITING_MANUAL` | OUT if identity confirmed |
| Translation from non-English original, or originally published outside 1880–1950 | OUT of narrow main set when original-language and chronology are evidenced; retain broad source record |

A conditional phrase in the submitted 65-case sheet (`POSSIBLE_IN`, `IN（要承認）`, `OUT（境界・要承認）`, etc.) is always mapped conservatively to `UNRESOLVED` in the unified *provisional* dataset. Never silently discard the exact input phrase: `original_ai_assessment_verbatim` stores it.

## 5. Evidence, provenance and release boundary

- `researcher_accepted_assessment_v02`: 41 `IN_SCOPE`, 19 `OUT_OF_SCOPE`, 20 `UNRESOLVED`; descriptive bookkeeping **only**, not a validated population rate.
- `reviewer_acceptance_status`: 15 pilot cases accepted in discussion; other 65 accepted *as a batch provisional assessment*. These have different review provenance.
- `source_review_provenance`: prior AI document/API/web checks (`OL_API`, `OL_API+WEB` etc.) and chat-checked primary edition links are explicitly different kinds of evidence. They are not interchangeable with `source_claims_independently_human_verified`.
- `release_status`: all 80 `HOLD_NOT_RELEASED`. The 65-row reviewer's formerly blank *final* column has not been retroactively represented as 65 individually signed source verifications.
- Before any scope membership release, confirm cited claims against the sampled Work/Edition (or keep unresolved), approve distinct `NOVEL_NOVELLA_ONLY` statuses for all, version a per-claim evidence registry, and run QC on all 80 rows.
- Existing researcher draft, frozen OL source, OpenAlex v3 measures, Goodreads and LLM matching outputs remain immutable.

## 6. Special cases that must remain visible

- Sample #12 `W000013111`: original framed single-author story collection, 1887; main IN, novel-only OUT.
- #24 `W000006125`: OL `OL16031380W` + Edition `OL24933847M` refer to the whole five-story volume, 1932; main IN, novel-only OUT.
- #29 `W000025937`: original Bowen short-story collection 1926; main IN, novel-only OUT.
- #17 Saki, #42 Eastman and #53 Dunne: mixed fiction/playlet, stories/exposition and fictional persona/satirical columns, respectively. Remain UNRESOLVED.
- #36 `Worth Wile` / `To the Hilt` and #45 `Better Angel` / `Torment`: title relationship ≠ verified target Work/Edition chain; remain UNRESOLVED.
- #73 `Humor` and #77 `Merry Men`: do not borrow evidence from a distinct OL Work.
- Remaining-65 conditional cases: ranks 4, 5, 16, 22, 28, 40, 54, 63, 68, 72, 78 are all UNRESOLVED pending explicitly described checks.

## 7. Bibliographic examples (MLA 9)

- Emory, A. M. *Told at Tuxedo*. G. P. Putnam's Sons, 1887. https://archive.org/details/toldattuxedo00emoriala
- Sherman, Harold M. *Interference and Other Football Stories*. Goldsmith Publishing Company, 1932. https://openlibrary.org/books/OL24933847M/Interference
- Bowen, Elizabeth. *Ann Lee's: & Other Stories*. Sidgwick & Jackson, 1926. https://openlibrary.org/books/OL14116676M/Ann_Lee%27s

See each data row's source and unresolved-note columns. This working rulebook supersedes none of the older draft documents.