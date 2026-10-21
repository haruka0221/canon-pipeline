# Random-80 researcher evidence sheet — v0.1

**Status:** `NOT_REVIEWED / NOT_ADJUDICATED`. This is a researcher-facing convenience sheet, not a scoped corpus or finalized classification.

## Purpose and provenance

The fixed random sample contains 80 distinct active Project W among 32,066 W. This new, independent derived sheet joins three **existing, frozen** sources by `project_work_id`:

- `derived/scope/random_scope_review_draft_v0_10/random_scope_80_ai_exploratory_register_v0_1.tsv` (80 W; AI hypotheses and 176 cited URLs).
- `derived/scope/scope_combined_bibliographic_evidence_v0_1/scope_combined_project_w_bibliographic_evidence_v0_1.tsv` (32,066 W; historical Open Library Edition-derived years, Wikidata snapshot P577/P407/P31/P629 values, original provenance fields).
- `derived/scope/scope_evidence_pilot_v1/scope_evidence_review_template_v1.tsv` (frozen random-80 membership; exact review order confirmed with `scope-random80-first10-20261020`).

The generator uses `--dry-run`, checks all 80 IDs and their order, and refuses to overwrite an existing output directory. A manifest records hashes and counts. No original identity, OpenAlex, frozen sample, or exploratory evidence is modified.

## Diagnostic signals — NOT scope decisions

The independent Boolean columns `diagnostic_ol_*` and `diagnostic_wd_*` reproduce the following exploratory cues:

- `diagnostic_ol_any`: prior broad signal from OL subject (`short_stor`, `short_story`, `bibliograph`, `catalog`, or selected criticism keys) or a limited title phrase.
- `diagnostic_wd_p407_without_english`: a nonempty P407 array lacking English Q1860. This flags a language statement and **does not prove original language**.
- `diagnostic_wd_p577_all_years_outside_1880_1950`: every parseable P577 year is outside 1880–1950. P577 is **not a verified original first-publication year**.
- `diagnostic_wd_minus_ol_min_year`: a difference between *one* P577 year and the lowest OL Edition-derived year, when both exist. This is a data-comparison field, **not** a scope decision.
- `diagnostic_ol_or_wd_any`: union of the original broad OL signal and the two WD warning cues.

Earlier read-only QC of the 80 W found OL cues in 10/26 AI-OUT works, and WD additional cues in five distinct AI-OUT works (11 *Atómstöðin*, 14 *Pathetic Symphony*, 32 *Six to Sixteen*, 51 *It Is Never Too Late to Mend*, 74 *Killer's Choice*), together 15/26. Eleven AI-OUT cases remained without these automatic cues. The other 44 AI-IN works had no such cues, and one of 10 AI-unresolved cases had an OL cue. **These are agreement tallies against AI proposals, not validated sensitivity, specificity, or prevalence.** Some cues may describe a novel's reception rather than its genre.

The remaining eleven AI-OUT W include six source-language/translation questions (8, 15, 33, 43, 65, 70), one year issue (52), and four work-form issues (4, 29, 53, 78). Categories are drawn from prior exploratory notes and must be verified independently.

## Human review procedure

All `reviewer_*` columns are intentionally **blank** and `review_status` is `NOT_REVIEWED` for all 80 W, including the previously drafted first 10. The current 80-W sheet **does not merge or overwrite** the older first-10 reviewer template. It uses the more recent 80-W AI register; older drafts are retained separately for audit.

For each W, confirm the **specific bibliographic target**, distinguish original from translated language, and record publication dates separately: first public appearance (including serialization), first complete publication, first book edition, and first English manifestation. Record whether the form is individual novel, novella, short story, collection, critical book, etc., with independent source links and exactly what each supports. If evidence remains contradictory or insufficient, leave the result unresolved. Only the researcher can enter `reviewer_analysis_scope_status` and change `review_status` after explicitly checking sources.

Do not infer scope from OL subjects, an OL Edition-derived minimum, Wikidata P577/P407/P31 alone, OpenAlex candidate counts, or QID existence. Do not exclude source-light/non-Wikidata works. Do not estimate population proportions from 44/80 AI proposals. Sample-level estimators are appropriate only after independent review and with unresolved cases and sampling uncertainty made explicit.

## Execution

Save script as `scripts/build_random_scope_80_researcher_evidence_sheet_v0_1.py` in the analysis worktree:

```bash
cd ~/canon-pipeline-openalex-a2val || exit 1
python -B scripts/build_random_scope_80_researcher_evidence_sheet_v0_1.py --dry-run
python -B scripts/build_random_scope_80_researcher_evidence_sheet_v0_1.py
```

Output directory: `derived/scope/random_scope_80_researcher_evidence_sheet_v0_1/` (new, must not exist). Two outputs are the 80-row TSV and manifest JSON. The full human reviewer sheet should be maintained as **a subsequent version** when review actually begins; never rerun the builder over edited researcher judgments.

The script was syntax-checked and tested with synthetic 32,066-W input; actual source compatibility and counts must be verified on the server with `--dry-run` before committing.
