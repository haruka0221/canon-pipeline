# Narrow OpenAlex v0.2 — 15-case researcher protocol pilot

Date: 2026-11-07
Status: `PILOT_QUEUE_CREATED / 0_RESEARCHER_REVIEWS / NO_SCOPE_RELEASE`

## Files and source

- Queue: `pilot15_reviewer_queue_v0_1.tsv` (15 rows, 26 columns, exact unique Project W IDs)
- Pilot protocol: `docs/OPENALEX_NARROW_SCOPE_RESEARCHER_REVIEW_PROTOCOL_v0_2_WORKING_2026-11-07.md`
- Frozen input: `derived/scope/random_scope_80_researcher_evidence_sheet_v0_1/random_scope_80_researcher_evidence_sheet_v0_1.tsv`
- Frozen input Git blob SHA at derivation: `d385cc1ca0ecca4aab10581bea74ceabc454bf49`
- Queue Git blob SHA after writing: `c118ba5232961e5377d57cca07caf39435657e34`

## Selection and QC

The 15 W are purposively selected **from within** the already frozen independent random-80 sample, at original ranks:
`7, 8, 12, 17, 24, 29, 36, 42, 45, 49, 52, 53, 62, 73, 77`.

Selection targets high-information methodological challenges: target identity, translated original, pure vs mixed single-author collections, component vs collection, alternate original titles, later retitlings, impossible OL years, political satire/essays and film novelization. **These 15 are no longer a random subsample for prevalence inference**; they are diagnostic stress tests only. Do not pool them as a separate population estimate.

GitHub read-back verification:
- 15 data rows, 26 columns, 15 unique Project W.
- Original 80-row sample was read unchanged. Pilot Project W IDs, rank and displayed source title were projected from its frozen input.
- Each pilot `review_status` is `NOT_REVIEWED`, and every `researcher_*` field is blank. No AI-generated `IN_SCOPE` or `OUT_OF_SCOPE` decision was inserted.
- Legacy `original_ai_label_DO_NOT_ADOPT` and `original_evidence_urls_UNVERIFIED` are context only; they predate the new short-fiction-collection policy. The new `specific_claim_to_verify` field is a human review prompt, **not a confirmed conclusion**.

## How the reviewer should use the TSV

The queue is intended for a tabular editor. Original identity metadata and source pointers are read-only. The reviewer may fill fields starting with `researcher_`, with supporting claims and evidence URLs, in a *new local or versioned review file*.

Recommended sequence for each W:
1. Inspect exact supplied OL Work(s), linked Edition(s), and the cited external publication (not merely title similarities).
2. Enter a target-link status: `TARGET_CONFIRMED`, `TARGET_DISPROVED`, or `TARGET_UNRESOLVED`. If unresolved, do not inherit form/language/year from the external candidate.
3. Record a bibliographically defensible form code, original composition language, first appearance, first complete original publication, first original-language book and collection-first edition separately.
4. Record `IN_SCOPE`, `OUT_OF_SCOPE`, `UNRESOLVED` **for both** the expanded v0.2 principal group and nested novel+novella comparison, with decisive source URLs and explicit uncertainty.
5. Provide review name/date, notes and review status in an eventual **new** versioned decision artifact. Do not overwrite this original pilot queue or the 80-item upstream sheet.

## Key caution: different Open Library Work ID is not proof of identity

- #73 W000004535 `Humor` has original associated `OL15142749W`, while an identified 1927 Overton-edited multi-author anthology is associated with `OL7098433W`: https://openlibrary.org/books/OL6706241M/The_world%27s_one_hundred_best_short_stories_... .
- #77 W000012835 `Merry Men` has source `OL24123W`, while an 1887 original Stevenson **single-author collection** is associated with `OL24137W`: https://openlibrary.org/books/OL6980014M/The_merry_men_and_other_tales_and_fables .

The collection titles and edition references are separately attested; their relation to the sampled W has **not** been adjudicated. The latter two sources were specifically cross-checked at desk review, and the different OL Work IDs should block any automatic join.

## Publication-grade limits

A completed pilot validates the review *protocol's usability*, not the 32,066-W population eligibility rate. After any revisions to the protocol, the researcher should review the full fixed sample of 80 consistently. The primary OpenAlex v3 corpus remains broad and provisional until a separately versioned, independently reviewed analytical-scope membership layer is produced. OpenAlex candidate-pair validity and scholarly-document eligibility remain separate unresolved questions.
