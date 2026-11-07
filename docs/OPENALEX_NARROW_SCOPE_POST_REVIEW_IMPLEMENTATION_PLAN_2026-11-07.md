# OpenAlex narrow scope — post-review implementation design, 2026-11-07

Status: `DESIGN_ONLY / NO_WIDE_CORPUS_RELEASE / FROZEN_INPUTS_UNCHANGED`
Policy: `docs/OPENALEX_NARROW_SCOPE_RESEARCHER_ACCEPTED_POLICY_v0_2a_2026-11-07.md`
Provisional random-80 ledger: `derived/scope/narrow_v02_researcher_accepted_2026_11_07/random80_researcher_accepted_provisional_v0_1.tsv`

## 1. This checkpoint

- Source sampling frame: original **80 fixed randomly selected Project W**, not 95.
- Pilot stress-test subset: 15 W within those 80 (3 IN, 3 OUT, 9 UNRESOLVED).
- Remaining 65 researcher-accepted provisional AI assessments: 38 IN, 16 OUT, 11 UNRESOLVED under conservative normalization; 11 includes `POSSIBLE`, `要承認`, and `境界` cases.
- Together: 41 IN, 19 OUT, 20 UNRESOLVED. No eligibility percentage, confidence interval, population size estimate or literary-visibility claim is justified from these book-keeping counts, because source-by-source independent researcher verification and all nested-comparator decisions are incomplete.

## 2. Two different artefacts: audit vs membership

1. Immutable inputs: original 80 source, pilot queue, original researcher sheet and frozen OpenAlex v3, OL, WD, Goodreads, LLM outputs.
2. Current *audit* dataset: 80 rows and acceptance provenance + source pointers, no `final_researcher_decision` asserted for remaining 65.
3. Future *membership* dataset (not created): unique `project_work_id`, exact target OL W/Edition evidence, versioned original-year and original-language evidence, `IN_SCOPE/OUT_OF_SCOPE/UNRESOLVED`, nested novel-only comparator, reviewer provenance, independent claim/URL verification, QC flags, decision revision history and release date.

## 3. Full 32,066-W classification workflow

Stage 0 — freeze the source snapshot and sampling frame. Record input sha, relevant ref, W→OL list, historical editions, current OL records and WD crosswalk; no in-place corrections of bad OL edition years.

Stage 1 — extract evidence as assertions (not decisions). For each Project W create bibliographic candidates with: original and alternate titles; author/editor/translator; original language; work form; first *public*, complete, book, and *collection* publication event dates; edition IDs, provenance URLs, scan/authority IDs, content signatures, and confidence/retrieval version.

Stage 2 — high-recall screening, preserving uncertainty. Assign `ELIGIBLE_CANDIDATE`, `EXCLUDED_CANDIDATE`, `FORM_OR_IDENTITY_UNRESOLVED`, and `INSUFFICIENT_EVIDENCE`. Do not infer eligibility from OL subject `fiction`, WD publication year alone, edition count, English-language catalog entry, scholarly mention count or lack of sources. Route mixed forms, title-mismatch, non-English originals, pre/post-boundary reprints and short-story/novella uncertainty to explicit QC queues.

Stage 3 — human-review gate and audit. Complete source/identity verification for the fixed random-80 audit with a consistent rulebook and nested comparator; preserve unresolved labels. Separately select *additional stratified high-risk review cases* (not added to random-80 prevalence denominator) to test false positives/negatives in all screening strata, especially candidates automatically excluded. Revise policy/version if recurring contradictions appear; keep audit labels synchronized to policy version.

Stage 4 — classify the larger frame with uncertainty. Automate only source-supported rules; maintain explicit `UNKNOWN`, human confirmation status, and a reproducible exception queue. Broad corpus records are never deleted because of narrow-scope exclusion. Use precision/recall estimates from appropriately verified independent audit samples and report uncertainty; do not make confident population-wide rates from unverified pilot counts.

Stage 5 — separate research measures from scope membership. Join a *released* membership table to frozen OpenAlex v3 on validated Project W key, without changing OA candidate-pair attribution, conflating mentions with citations, filling not-queried `NA` with zero, or turning missing Goodreads data into zero. Preserve original vs retitled query variants, collection/component relationships, and deduplicate at cited scholarly-document level before any aggregate.

Stage 6 — sensitivity and reproducibility. Report: (a) main v0.2 collection-inclusive scope, (b) nested novel+novella scope, (c) excluded mixed forms vs a separate sensitivity stratum, (d) uncertain/boundary year cases, (e) missing and unresolved rate. Track all policy/membership revisions and measure how results change.

## 4. Next work tickets (ordered, no blind IN/OUT auto-fill)

1. **Bibliographic QA:** complete exact Edition/Work verification for the 20 UNRESOLVED and sample metadata anomalies, including 11 conditional cases among remaining 65.
2. **Audit completion:** review source claims for all 80, especially source-only AI claims, and record nested comparator statuses for remaining 65; submit the resulting separate human-sign-off ledger.
3. **All-W source extraction:** run provenance-rich work/edition extraction over 32,066 W with a separate exception log; no automated narrow-scope release from subject tags.
4. **Classifier evaluation:** prespecify the screening feature set, assess false negatives on sampled `EXCLUDED_CANDIDATE` Works, measure agreement and uncertainty against the reviewed random-80; increase sample if precision demands.
5. **OA joins:** only after membership release, join versioned scope flags to frozen OA v3 and report separate novel-only sensitivity.

## 5. Tests before a scope release

- 80 unique ranks from 1 through 80, 80 unique W, identical to original frozen sample.
- Pilot subset 15 + remaining 65 exactly partition the 80.
- Full evidence-link chain or explicit UNRESOLVED reason per reviewed row.
- No AI-proposed status is mislabeled individually checked by a researcher; current accepted-batch state remains explicit.
- `novel_novella_only_assessment` known or unresolved for all cases; never auto-fill from main classification.
- Original-language/first appearance/collection-year events present when used for inclusion.
- 32,066-W frame join one-to-one, all W retained, exclusions stored as flags not deletions.
- OpenAlex `NA`/not queried vs verified zero and Goodreads missingness preserved.
- GitHub revision/version and source SHAs recorded in analysis log.