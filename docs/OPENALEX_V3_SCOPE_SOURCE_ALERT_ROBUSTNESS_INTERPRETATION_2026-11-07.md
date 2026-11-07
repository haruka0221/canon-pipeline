# OpenAlex v3 / Goodreads scope-source-alert sensitivity: interpretation checkpoint

Date: 2026-11-07
Status: EXPLORATORY / NON-ADJUDICATED / FROZEN INPUTS UNCHANGED

Source artifacts:
- `derived/openalex_production/analysis_v3_scope_source_alert_robustness_v0_1/cohort_comparison_v0_1.tsv`
- `derived/openalex_production/analysis_v3_scope_source_alert_robustness_v0_1/correlations_by_source_alert_cohort_v0_1.tsv`
- `derived/openalex_production/analysis_v3_scope_source_alert_robustness_v0_1/percentile_extremes_recomputed_by_cohort_v0_1.tsv`
- `derived/openalex_production/analysis_v3_scope_source_alert_robustness_v0_1/goodreads_observation_by_bibliographic_source_alert_v0_1.tsv`
- `docs/OPENALEX_GOODREADS_PERCENTILE_EXTREMES_SCOPE_AUDIT_2026-11-07.md` (independent-source preliminary book evidence)

## Confirmed technical results

The existing frozen v0.2 complete-case correlations were reproduced exactly. Python-only (without SciPy) Spearman computation uses average ranks followed by Pearson on ranks; SHA-256 results were verified and pushed in commit `39c86e15`.

| Scenario | All W | OA measured W | OA+historical GR observed W | CORE3 pair sum | CORE3 × GR ratings Spearman rho | GR observation among OA measured |
|---|---:|---:|---:|---:|---:|---:|
| BASELINE_ALL_W | 32,066 | 31,713 | 4,642 | 146,724 | 0.411970 | 14.64% |
| NO_SHARED_QUERY_AND_SINGLE_OL | 29,718 | 29,366 | 4,293 | 117,505 | 0.405055 | 14.62% |
| NO_SOURCE_ALERTS | 27,792 | 27,451 | 3,791 | 58,759 | 0.354431 | 13.81% |
| NO_SOURCE_ALERTS_PLUS_WD_WINDOW_ENGLISH | 2,167 | 2,166 | 1,348 | 39,111 | 0.349465 | 62.23% |

The `NO_SOURCE_ALERTS` group retains 86.6% of OA-measured W but just 40.0% of CORE3 candidate pairs. Its CORE3 p90 is 1 versus 2 in the baseline. This may reflect how bibliographic/identity signals coincide with scholarly visibility and source coverage; selecting without an explicit CORE3 threshold does NOT eliminate all such dependence. It must not be claimed that removing out-of-scope works causes the coefficient drop.

The WD-window-English group represents only 2,167/32,066 active W. Its source completeness is strongly associated with GR availability (62.2% vs 14.6% baseline), and its CORE3 p90 is 34 vs 2 baseline. This is a highly selected documentation-rich stratum, not an independently verified scope population.

## Ranking comparisons (top ten each direction)

Top-ten intersection with baseline:

| Scenario | Academic-over-public common with baseline /10 | Public-over-academic common with baseline /10 |
|---|---:|---:|
| NO_SHARED_QUERY_AND_SINGLE_OL | 9 | 9 |
| NO_SOURCE_ALERTS | 6 | 3 |
| NO_SOURCE_ALERTS_PLUS_WD_WINDOW_ENGLISH | 2 | 1 |

Percentiles were recomputed *within each matched analysis cohort*, so this comparison represents both membership changes and rescaling. None of the rankings is a validated ranking of eligible original-English 1880–1950 novels/novellas.

## Concrete false negatives of source-alert screening

The source-alert filtering is **not an adequate literary-scope filter**:

- `W000022701` Azorín, *Don Juan* (original Spanish): still academic-over-public #1 in `NO_SOURCE_ALERTS`.
- `W000022915` Q. D. Leavis, *Fiction and the Reading Public* (literary criticism, not an individual novel): still academic-over-public #5 in `NO_SOURCE_ALERTS`.
- `W000007853` Sarah Addison Allen, *The Peach Keeper* (original 2011): still public-over-academic #2 in `NO_SOURCE_ALERTS`.
- `W000019130` Esphyr Slobodkina, *Caps for Sale* (illustrated picture book): public-over-academic #1 in both `NO_SOURCE_ALERTS` and the stricter `NO_SOURCE_ALERTS_PLUS_WD_WINDOW_ENGLISH`.
- `W000016805` Edwin Lefèvre, *Reminiscences of a Stock Operator* appears at #10 public-over-academic in the WD stratum; review as a nonfiction/memoir-style narrative rather than automatically assuming a novel (no formal book-form adjudication made here).

For bibliographic source references and preliminary determinations supporting the first four, see `docs/OPENALEX_GOODREADS_PERCENTILE_EXTREMES_SCOPE_AUDIT_2026-11-07.md`. The fifth is flagged for independent work-form verification, not confirmed out-of-scope in this memo.

These are selected extreme cases, NOT a prevalence estimate among all 32,066 W or the 4,642 complete cases.

## Additional interpretive issue

In the rankings, all top-ten `PUBLIC_OVER_ACADEMIC` records across the four cohorts have `OA_CORE3=0`. This is an operational candidate count, not confirmed absence of scholarship. The zero-heavy distribution and tied rankings make the particular retrieval protocol a crucial limitation. Avoid calling these cases academically neglected until recall and relevant-document suitability are checked.

## Decision for subsequent work

1. Archive the four-scenario sensitivity as evidence of sample dependence, **not** as a scope correction; do not promote `NO_SOURCE_ALERTS` or the WD subset to `IN_SCOPE`.
2. Prioritize a defined, human-audited scope protocol using the *already frozen independent random 80 W* (and separately labeled purposive extreme cases); preserve independent sampling and unresolved items. A finite validation audit of the filter's false negatives is needed before using it to exclude records.
3. In parallel, proceed with as-retrieved, explicitly provisional full-W OpenAlex distributions, concentration, document-type lenses and identity-overlap sensitivity. No need to hold all distributional analysis hostage to scope adjudication.
4. Treat statistical links between academic attention and reader-facing metrics as *descriptive within observed cross-database subsets*. Goodreads observed values are historical UCSD carrier observations, and the 4,642-W matched group is severely nonrandom.
5. Do not alter work identities, scope decisions, frozen OpenAlex v2/v3 pair counts, Goodreads overlay, historical Goodreads counts, sealed validation samples or earlier correlations.

Summary: All investigated cohorts retain positive rank associations, but magnitudes and high-contrast exemplars are sensitive to data construction. The unresolved construct-validity and coverage problems are substantive methodological findings, not resolved by source-alert filtering.
