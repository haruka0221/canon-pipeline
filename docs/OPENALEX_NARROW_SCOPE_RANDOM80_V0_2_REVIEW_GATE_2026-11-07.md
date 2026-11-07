# Narrow OpenAlex literary-scope review: random-80 exploratory evidence checkpoint

Date: 2026-11-07
Status: `ALL_80_SOURCE_DRAFTS_REVISITED / V0_2_WORKING_POLICY / ZERO_RESEARCHER_ADJUDICATION / NO_SCOPE_RELEASE`

## What is completed

The entire original fixed independent random sample of 80 Project W units has **AI-assisted exploratory bibliographic evidence** from October 2026; an updated sequence of *review/checkpoint notes* reinterprets its 1–80 positions under the tentatively discussed November 2026 scope v0.2. This is not an independently human-validated sample and must not be used to claim eligible-corpus fractions.

The original baseline October 20 scope was individual original-English novels/novellas, first published 1880–1950. The **proposed** new principal scope additionally considers identifiable original *single-author short-fiction collections* first issued as collections in that period, while preserving a nested novel/novella-only comparator. The user gave tentative support for the expansion, not an instruction to classify mixed-form and target-ambiguous cases automatically. Short stories as *components* are not automatically admitted because a collection is.

The historical **broad** corpus contains English-language publication/edition records in 1880–1950 and may appropriately include translations and later editions. It is **not** a validated narrow literary-scope population. A narrow exclusion does not mean a source must be deleted. False metadata years and nonfiction library catalogs are separate broad-source QC problems.

### Full v0.2 checkpoint trail

- Ranks 1–10: `docs/OPENALEX_NARROW_SCOPE_FIRST10_EVIDENCE_RECHECK_2026-11-07.md`
- Ranks 11–20: `docs/OPENALEX_NARROW_SCOPE_RANDOM11_20_EVIDENCE_RECHECK_2026-11-07.md`
- Ranks 21–30: `docs/OPENALEX_NARROW_SCOPE_RANDOM21_30_EVIDENCE_RECHECK_2026-11-07.md`
- Ranks 31–40 and earlier collection re-evaluations: `docs/OPENALEX_NARROW_SCOPE_RANDOM31_40_AND_COLLECTION_RULE_RECHECK_2026-11-07.md`
- Ranks 41–50: `docs/OPENALEX_NARROW_SCOPE_RANDOM41_50_COLLECTION_POLICY_RECHECK_2026-11-07.md`
- Ranks 51–60: `docs/OPENALEX_NARROW_SCOPE_RANDOM51_60_COLLECTION_POLICY_RECHECK_2026-11-07.md`
- Ranks 61–80: `docs/OPENALEX_NARROW_SCOPE_RANDOM61_80_COLLECTION_POLICY_RECHECK_2026-11-07.md`
- Source policy proposal: `docs/OPENALEX_SHORT_FICTION_COLLECTION_SCOPE_POLICY_PROPOSAL_v0_2_2026-11-07.md`

Canonical EXISTING researcher evidence sheet, not modified:
`derived/scope/random_scope_80_researcher_evidence_sheet_v0_1/random_scope_80_researcher_evidence_sheet_v0_1.tsv`.

This v0.1 sheet already includes 80 distinct W, historical OL evidence, Wikidata evidence, AI/source URLs, diagnostic flags and many `reviewer_*` fields intentionally blank. Create a separate later human-decision artifact; never copy AI's `IN_SCOPE_CANDIDATE` into formal `IN_SCOPE`.

## Critical questions for the researcher

**Priority A: define stable form policy, before populating IN/OUT**

- If a single-author collection includes an occasional dramatic playlet or a nonfiction essay, should it qualify for the expanded principal stratum? Suggested option: keep `ORIGINAL_SINGLE_AUTHOR_SHORT_FICTION_COLLECTION` as the clear main group, and put `MIXED_FORM_SINGLE_AUTHOR_COLLECTION` into a separately reported sensitivity set or `UNRESOLVED` rather than admitting it silently.
- Separate an **individual short story**, an **original organized single-author collection**, an **edited multi-author anthology**, a **posthumous/recompiled collected-works edition**, and a **single novel** in all review fields.
- Scope decisions concern the **specific W/OL work entity under review**, not just a generally similar titled published book.

**Priority B: high-information source-target anomalies to inspect first**

| Random rank / W | Question | Why it matters |
|---|---|---|
| 7 / W000013966 *Surface and Depth* | 2003 literary criticism vs OL historical minimum 1920 | wrong Work identity or source-year provenance cannot be solved by declaring a 1920 English novel |
| 12 / W000013111 *Told at Tuxedo* | a "series of stories" vs original single-author collection | previously novel-only OUT may become possible IN under v0.2 |
| 17 / W000016912 *Reginald in Russia* | prose stories + playlet | example for mixed-form category; not automatic OUT or IN |
| 24 / W000006125 *Interference* | 1932 collection vs individual contained story | Work-vs-component identity; count academic mentions at the right level |
| 29 / W000025937 *Ann Lee's* | original 1926 single-author stories collection | strong v0.2 candidate, was novel-only OUT |
| 36 / W000009023 *To the Hilt* | British first title *Worth Wile* vs American retitle | original-year record and OpenAlex query recall |
| 39 / W000011460 *Gallions Reach* | historical OL date 1917 vs original edition 1927 | possible OL source-year contamination |
| 42 / W000022733 *Red Hunters and the Animal People* | indigenous folklore tales + descriptive chapter | mixed-form category; avoid treating indigenous storytelling as categorically nonfiction |
| 45 / W000029824 *Torment* | original 1933 *Better Angel* vs retitle 1951 | query title versus first original work; original 1933 can qualify |
| 49 / W000026024 *Ginger* | previously serialized episodes/character sketches in 1916 collection | form may be cohesive novel, short fiction collection or sketches |
| 52 / W000002247 *Double Trouble Squared* | 1991 novel, historical OL 1924 | verify OL Edition/year error source; neither date is a verified 1924 original |
| 53 / W000006556 *Mr. Dooley in Peace and in War* | satirical newspaper columns, repeated fictional character | main fiction collection vs mixed literary essays |
| 56 / W000031785 *Mr. Popper's Penguins* | dual authors, multiple OL Works | a coauthored novel remains eligible; author display incomplete |
| 62 / W000025100 *The Sin of Harold Diddlebock* | adaptation of 1947 film vs an original standalone English novelization | confirm prose work & publication; explicit treatment of tie-ins |
| 73 / W000004535 *Humor* | identified multi-author anthology belongs to a **different** OL Work | high risk false-target mapping; do not trust attractive same-title match |
| 77 / W000012835 *The Merry Men* | 1882 individual story vs original 1887 Stevenson collection | 1887 collection can qualify under v0.2 **only if W denotes it** |
| 78 / W000002690 *The Key of the Field* | 1930 short story independently issued as pamphlet | separate book-format from novel/novella form |
| 80 / W000023830 *Pretty Sinister* | historical OL min 1900 vs evidence for original 1929 | scope conclusion & provenance issue must not be conflated |

For #77, an 1887 first-edition collection is cataloged by Morgan Library: https://www.themorgan.org/printed-books/78982 and the work chronology identifies the 1882 component: https://robert-louis-stevenson.org/works-chronology/ .

**Priority C: minimum evidence for each formal decision**

1. A checkable institutional catalogue, original title page/contents, archival document, contemporary review, publisher first-edition record, or specialist bibliography whose **claim** supports the specific W/Edition relationship. Preserve each URL and claim, including uncertainty.
2. Separate `original_language`, `work_form`, `first_public_appearance_year`, `first_complete_publication_year`, `first_book_publication_year`, `original_collection_first_edition_year`, and `first_english_manifestation_year`; do not equate them with OL Edition minima or WD P577.
3. Explicitly record author/editor/translator roles, version/retitling relationships, components, and uncertain bibliographic identity.
4. Only the researcher can set a final `reviewer_analysis_scope_status` and `review_status`. Missing evidence remains `UNRESOLVED`.
5. Do not infer original-English first publication from contemporary publication *in English*, nor automatically exclude translated and reprinted works from the separately defined broad frame.

## Suggested practical review cadence

- Agree on the short-fiction collection / mixed-form policy. Keep the novel+novella comparator.
- Human-review a 10–15-work **mixed, high-information pilot** from the priority table, recording explicit exact source claims and target links. These cases are *purposive tests of the protocol only*, not a population estimate.
- Then independently human-review all 80 originally sampled W with the SAME stable policy and preserve unresolved judgments. Only the reviewed 80 support sample-level prevalence/uncertainty estimates; purposive examples may not be pooled.
- Build a separate versioned, one-row-per-Project-W `narrow_scope_decisions` layer and a publication/form evidence registry. Preserve all broad W and frozen OA v3 measures; compute later scoped comparisons only after sufficient verified inclusion evidence.
- Do not presume existing missing Goodreads means zero, or provisional OpenAlex CORE3 pair counts mean verified citations. Scope and OA attribution remain independent QC.

## No work claimed

This checkpoint does NOT certify that all external URLs are reachable, that the exact Work/Edition links are validated, that the 80 original researcher fields are completed, or that the 32,066-W narrow analytic population has been identified. All are distinct follow-up tasks.
