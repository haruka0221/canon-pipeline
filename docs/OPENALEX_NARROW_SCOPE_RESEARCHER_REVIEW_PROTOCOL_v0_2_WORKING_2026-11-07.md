# OpenAlex 狭義scope研究者レビュー規約 v0.2 — 暫定作業版

Date: 2026-11-07
Status: `WORKING_PROTOCOL / TENTATIVELY_ACCEPTED_FOR_PILOT / NOT_FORMALLY_ADJUDICATED / NO_SCOPE_RELEASE`
Relation: extends `docs/OPENALEX_SCOPE_REVIEW_PROTOCOL_DRAFT_v0_1.md` and `docs/OPENALEX_SHORT_FICTION_COLLECTION_SCOPE_POLICY_PROPOSAL_v0_2_2026-11-07.md`. Does not overwrite those documents.

## 1. 目的と母集団

This procedure is only for the **primary OpenAlex scholarly-visibility analysis**. The historical English-language edition/circulation population (34,789 historical OL source records; 32,066 active Project W) remains unchanged; historically republished older texts and English translations may belong in that broader frame.

The v0.2 **working candidate principal scope** consists of:

A. One originally English individual novel or novella first published 1880–1950 inclusive, including children's/YA/coauthored novels.

B. An identifiable **original single-author short-fiction collection** first issued as a distinct collection during 1880–1950, whose constituent fictional texts were originally written in English. Its first *collection* edition determines the collection-level date, not the oldest component's first appearance.

Keep an independently tabulated nested comparison restricted to A (`NOVEL_NOVELLA_ONLY`). This v0.2 rule is **tentative**, not a signed-off membership release. No historical Project W identity or OA candidate-pair attribution is changed.

## 2. Unit of review: identify the bibliographic object before its form

Each row in the independent frozen 80-W sample refers to one Project W (not necessarily a validated single conceptual literary work). Verify source OL Work IDs, their linked Editions, creator/editor/translator roles, and whether external first-edition or secondary evidence actually refers to this specific target.

Use `TARGET_CONFIRMED`, `TARGET_DISPROVED`, or `TARGET_UNRESOLVED` independently of form and dates. `TARGET_DISPROVED` means an externally found source is not evidence for this W; do **not** infer W is out-of-scope. Examples:
- W000004535 `Humor` links to OL15142749W in the original researcher sheet, while the external Overton multi-author anthology is cataloged as OL7098433W (https://openlibrary.org/books/OL6706241M/The_world%27s_one_hundred_best_short_stories_...).
- W000012835 `Merry Men` is linked to OL24123W in that sheet; a clearly documented 1887 collection edition links to *different* OL24137W (https://openlibrary.org/books/OL6980014M/The_merry_men_and_other_tales_and_fables). This **does not** establish which bibliographic object OL24123W denotes.

Neither discrepancy authorizes automatic OL-Work merging, identity editing, or an OUT decision.

## 3. Work form vocabulary and inclusion routing

Record the bibliographically evidenced form before classification. Use these form classes in the pilot:

| reviewer_form_code | v0.2 principal routing |
|---|---|
| `INDIVIDUAL_NOVEL` | Candidate A, if language/year/identity confirm |
| `INDIVIDUAL_NOVELLA` | Candidate A, if language/year/identity confirm |
| `ORIGINAL_SINGLE_AUTHOR_SHORT_FICTION_COLLECTION` | Candidate B, if edition contents and authorial/original collection are evidenced |
| `MIXED_FORM_SINGLE_AUTHOR_COLLECTION` | `UNRESOLVED` for principal set pending an explicit mixed-form convention; optionally investigate separately for sensitivity |
| `RETROSPECTIVE_SELECTED_COLLECTED_WORKS` | Not automatically eligible B; inspect whether a genuinely new authorial collection or merely reprint/editorial aggregation |
| `MULTI_AUTHOR_ANTHOLOGY` | Out of principal B if exact target, form and contributors verified |
| `INDIVIDUAL_SHORT_STORY` | Out of v0.2 principal set; separately maintain possible story-level work for future method |
| `OTHER_NONFICTION`, `CRITICISM`, `CATALOG_REFERENCE`, `WRITING_MANUAL` | Out if specific target and genre confirmed |
| `FILM_NOVELIZATION`, `EPISODIC_SEQUENCE`, `UNRESOLVED_FORM` | Keep pending original prose identity, continuity, copyright/source relationship and explicit method choice |

Page count or approximate word count alone is **not** sufficient to label a novella. Fiction/short-story tags in OL subjects are non-adjudicative clues. A book containing a fictional voice plus historical explanation (e.g. Mr Dooley; Eastman; Saki playlet) is not automatically a pure original short-story collection.

## 4. Publication years and language

Independent evidence fields:
- `first_public_appearance_year`: original language, first serialized installment or first discrete public issue;
- `first_complete_publication_year`: first complete original-language work;
- `first_book_publication_year`: original-language first standalone book;
- `original_collection_first_edition_year`: first edition assembling the original collection with version/contents specified;
- `first_english_manifestation_year`: first English publication, including translations; and
- `first_edition_title`, `alternative_title_and_year`, `version_relation`, `original_language`.

Working **period basis for A**: earliest independently evidenced *original-language public appearance* (including original serialization start), with completion/book years recorded separately. If a boundary is crossed (before 1880/after 1950), flag `PERIOD_BASIS_REVIEW_REQUIRED` and run an eventual sensitivity comparison using first complete publication and first original-language book publication. Earliest available edition **is not** the earliest appearance without explicit source evidence.

Working **period basis for B**: first independently documented issue of the identifiable collection as a *collection*, not first appearance of any component. Component/story first dates remain attached to the relevant components. For a restructured volume (1924 vs 1925 `In Our Time`), record an edition/version relation and do not automatically merge different collection identities.

Translations of non-English originals are excluded only from the narrow original-English set; their first English appearance still matters to the broad circulation/translation analysis. The 1933 original `Better Angel` and the 1951 retitling `Torment` are another reason to distinguish original-work and current-display names.

## 5. Decision workflow — only human verification enters final columns

1. Reviewer personally checks the claimed bibliographic target and every decisive source/identifier, recording what specific claim each URL/title page/edition supports and any conflict.
2. Reviewer logs work form, original-language, publication events and unresolved issues separately. An AI proposal or repository evidence pointer is not evidence of having reviewed the linked object.
3. Reviewer enters `IN_SCOPE`, `OUT_OF_SCOPE`, or `UNRESOLVED` **only** after specific claims and their link to the relevant Project W have been checked. If target identity remains ambiguous, set `UNRESOLVED` and specify `TARGET_UNRESOLVED` rather than inheriting a different Work's form.
4. Keep `NOVEL_NOVELLA_ONLY` and expanded v0.2 routing as separate columns. No forced binary default. Record reviewer name, UTC or local review date, evidence IDs/URLs and notes.
5. Store reviewer decisions in a **separate versioned output** and leave `derived/scope/random_scope_80_researcher_evidence_sheet_v0_1/random_scope_80_researcher_evidence_sheet_v0_1.tsv` (original `NOT_REVIEWED` sheet), all frozen W, OL, OA/LLM, Goodreads and holdout artifacts unchanged.

## 6. Pilot and limits

Use a **purposive 15-item protocol stress-test** before reviewing the fixed sample of 80 uniformly. This diagnostic selection covers target conflicts, translation, original single-author collection, hybrid form, retitling, suspicious dates, and film adaptation. **15 purposively reviewed rows are not a probability sample** and cannot estimate eligibility prevalence. Once the procedure is stable, use it to review *all the original random 80 W in original order*, including the 15 if the protocol has materially changed.

Pilot file:
`derived/scope/narrow_v02_researcher_pilot_2026_11_07/pilot15_reviewer_queue_v0_1.tsv`.

No scope membership is released by this protocol or queue. Even after review, scope classification, OA scholarly-document eligibility, W-identity quality, citation attribution and Goodreads missingness remain separate QC problems.

## 7. Acceptance tests prior to a narrow analytical release

- Each finalized W row has exact bibliographic-target evidence and a documented independent form/language/year rationale (or remains unresolved).
- The 80-W sampling frame and all `NOT_REVIEWED` upstream artifacts remain unmodified.
- Inter-review and intra-review ambiguity policy stable for mixed forms, serial dates, authorial collections, translations, and novelizations.
- No automated `IN_SCOPE` from `P577`, `P407`, OL minimum year, source-alert absence, AI label, OA mentions, or ratings.
- A separate versioned membership dataset explicitly states its inclusion basis and unresolved count; any subsequent OpenAlex v3 JOIN preserves `NA` for unqueried works and never treats Goodreads missing values as zero.

## Source documents

- Original scope protocol v0.1: `docs/OPENALEX_SCOPE_REVIEW_PROTOCOL_DRAFT_v0_1.md`.
- Source classification design: `docs/OPENALEX_SCOPE_SCREENING_DESIGN_DRAFT_v0_1.md`.
- Entire random-80 audit summary: `docs/OPENALEX_NARROW_SCOPE_RANDOM80_V0_2_REVIEW_GATE_2026-11-07.md`.
- Example independent collection evidence: Elizabeth Bowen's `Ann Lee's: & Other Stories` (1926) has OL Work OL724097W in an original 1926 Edition, https://openlibrary.org/books/OL14116676M/Ann_Lee%27s ; the first-edition Stevenson collection is held by the Morgan Library, https://www.themorgan.org/printed-books/78982.
