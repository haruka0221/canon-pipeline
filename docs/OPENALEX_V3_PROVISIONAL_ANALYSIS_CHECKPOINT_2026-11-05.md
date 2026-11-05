# OpenAlex v3 attribution and provisional visibility — checkpoint (2026-11-05)

Status: **analysis checkpoint; NOT validated scholarly-visibility release**.

## Preserved evidence and measured results

- Frozen R2+A1 LLM production queue: 223,115 candidate Project W × OpenAlex Work pairs, batches 0000–0223 complete, verified using continuation-status and independent read-only integrity scan.
- Model judgments (provisional, not human gold): 170,791 VALID_TARGET_REFERENCE (76.55%), 42,351 INVALID_TARGET_REFERENCE (18.98%), 9,973 UNCERTAIN (4.47%).
- Integrated v2 operational inclusions: 226,221 W×OA pairs. Non-destructive integrated v3: 173,897 included candidate pairs (170,791 model VALID + 3,106 v2 inclusions with no new production-model judgment). All original dispositions remain in the v3 pair table.
- Active Project W: 32,066. v3 works with ≥1 provisionally included pair: 6,816. R2/R3 not queried: 352; source-light Alcott successor unremeasured: one work, preserved as NA.
- Of 173,897 included pairs, 129,628 unique OpenAlex IDs; 24,001 OpenAlex IDs are associated with multiple Project W, creating 68,270 pairs on shared OA IDs (39.3%). Multi-work discussion is possible: not a false-positive estimate.

## Document types (from OpenAlex snapshot, 100% linked)

- article: 103,547 pairs
- dissertation: 22,315
- book-chapter: 20,862
- book: 9,617
- other: 6,737
- book-review: 3,377
- all other types together: 7,442
- article+dissertation+book-chapter: 146,724 (84.4%) of all v3 pairs

OpenAlex document types are not verified scholarly-eligibility classifications. Book (possibly primary works), book-review (may be relevant for reception), conference-paper, preprint, report, editorial and other types warrant separate interpretation. Do not call the 146,724 count a validated citation total.

## Identity/query overlap findings

- Exact normalized R2 title+author query shared by multiple Project W: 833 groups / 1,799 Project W.
- Ulysses (James Joyce), 3 W: 13,202 original included pairs, union 4,423 distinct OA IDs, 8,779 repeated placements.
- Heart of Darkness (Joseph Conrad), 4 W: 5,851 repeated placements. One OL record may be a multi-work publication; do not infer SAME work automatically.
- Top-two grouping sensitivity, NOT a researcher identity adjudication:
  - v3 as-is: 173,897 pairs, top10 share 16.1%, top100 share 48.9%;
  - hypothetical Ulysses union: 165,118, 13.9%, 46.5%;
  - hypothetical both group unions: 159,267, 13.5%, 45.1%.
- Other 831 shared title+author query groups remain unadjudicated. A work appearing in several publications, a common-title coincidence, a collection, and duplicate OL Works require distinguishing relations. No changes to Project W identities from these signals.

## Corpus and scholarly-scope limitations

- Primary analytical target as drafted: original English-language novels/novellas first published 1880–1950 (inclusive); short stories and serialized date rules unresolved.
- Historical OL linked Edition minimum year is NOT original publication year, and cannot confirm scope.
- Wikidata source-native language/form/year evidence is not yet researcher adjudicated.
- Frozen independent random 80-W scope draft is AI-supported evidence but not a human-validated inclusion frame; no AI IN_SCOPE_CANDIDATE is promoted to IN_SCOPE.
- Work identity, corpus scope, work-document attribution, document scholarly suitability, OpenAlex record/content duplication, and inter-database metric correspondence are separate steps.
- The 600-case held-out evaluation and the original human labels must not be modified or joined into production predictions.

## Next analytical steps (do not block first distributions on full manual review)

1. Reproducibly join per-W v3 counts, OpenAlex document type lenses, and all-W OL/Wikidata bibliographic evidence without scope decisions. Compare all types, article/chapter/dissertation, and an explicitly broader, sensitive type lens.
2. Compute distributions, rankings, and top-N concentration for each lens in as-retrieved and hypothetical top-two grouping views.
3. Establish a genuine bibliographic identity correspondence before Goodreads / OL edition-count comparisons; do not cross-join by title+author alone or count repeated OL editions from duplicate W groups.
4. Run targeted checks on top-ranked W and high-overlap clusters; record dispositions without rewriting frozen datasets.
5. Separate original-work publication year and form/language human scope review from the automated retrieval.
6. Create independently versioned *analytical-scope* and *scholarly-source suitability* layers, with missing and unresolved status preserved.

## Artifacts / provenance

- `scripts/build_openalex_r2a1_visibility_v3_provisional.py`
- `scripts/analyze_openalex_visibility_v3_provisional_v0_1.py`
- `scripts/audit_openalex_shared_r2_query_identity_risk_v0_1.py`
- `scripts/analyze_openalex_v3_top2_identity_sensitivity_v0_1.py`
- `scripts/analyze_openalex_v3_document_types_v0_1.py`
- `scripts/analyze_openalex_v3_visibility_lenses_scope_bridge_v0_1.py`
- `docs/OPENALEX_ANALYSIS_SCOPE_DRAFT_v0_1.md`
- `docs/OPENALEX_SCOPE_SCREENING_DESIGN_DRAFT_v0_1.md`

Each analyzer has a new non-overwriting output directory and a SHA-256 input/output manifest. Production inference is not called again. The original v2, v3, project identity, human-gold, and sealed holdout records are not modified.
