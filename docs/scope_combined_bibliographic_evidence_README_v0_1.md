# Scope combined bibliographic evidence v0.1 — README

## Purpose

A read-only join of already frozen Open Library and Wikidata **bibliographic evidence**, by the currently active **32,066 Project W IDs**. This is a convenience layer for studying evidence coverage and for designing screening rules. It is **not** a scope-classification table or a newly adjudicated literary corpus.

## Inputs

- `derived/scope/scope_ol_bibliographic_projection_v0_1/scope_project_w_bibliographic_frame_v0_1.tsv` — 32,066 Project W, historically enriched Open Library evidence, including Edition-derived minimum years and native subjects.
- `derived/scope/scope_wikidata_bibliographic_evidence_v0_1/scope_wikidata_project_w_coverage_v0_1.tsv` — 32,066 Project W, showing whether an **adopted** QID exists, and per-property counts.
- `derived/scope/scope_wikidata_bibliographic_evidence_v0_1/scope_wikidata_qid_evidence_v0_1.tsv` — 6,177 adopted QIDs, with snapshot `2026-08-05` source values for P577, P407, P31, P629.

Inputs are read without modification. Their SHA-256 hashes are written to the manifest.

## Output

- `scope_combined_project_w_bibliographic_evidence_v0_1.tsv` — one row per active Project W, preserving original Open Library fields and Wikidata coverage and QID evidence fields, with `bibliographic_source_combination` added.
- `scope_combined_bibliographic_evidence_manifest_v0_1.json` — hashes, exact aggregate counts, source snapshots, constraints and limitations.

The new source-combination field has four possible values: `HISTORICAL_OL_AND_WIKIDATA`, `HISTORICAL_OL_ONLY`, `WIKIDATA_ONLY`, and `NO_HISTORICAL_OL_OR_ADOPTED_WIKIDATA`. These are **data availability** categories, not literary-scope categories.

## Expected cross-source coverage

| Evidence availability | Project W |
| --- | ---: |
| Historical OL and adopted Wikidata QID | 6,177 |
| Historical OL only | 25,885 |
| Adopted Wikidata QID only | 0 |
| Neither | 4 |
| **Total** | **32,066** |

The four without either source are `W000014515`, `W000031537`, `W000031538`, and `W000031539`. Three have current OL Work IDs that were not in the historical source population; one is a source-light hold. None are repaired or dropped.

For 6,177 QIDs, Wikidata P577 is nonempty in 4,473, P407 in 4,893, both in 3,651, P31 in 6,120, and P629 in one. These are statements in the frozen Wikidata extraction, **not** verified original-year/original-language determinations.

## Interpretation and invariants

- Historical Open Library `historical_edition_derived_min_years_json` is **Edition-derived**, not an original publication date.
- Wikidata `wd_p577_values_json` and `wd_p577_parsed_positive_years_json` are a **date statement** and parsed year spellings, not verified original first-publication years.
- Wikidata `wd_p407_values_json` is a source language property, not independently verified original language. `wd_p31_values_json` is a general class signal, not a novel classification.
- `[]` means an explicitly empty attribute array in its source table. Blank Wikidata detail cells mean that **no adopted QID evidence row exists** for this Project W. Use the availability statuses rather than conflating these cases.
- Identity v7, source entities, OL historical data, Wikidata snapshots, OpenAlex integrated v2, the fixed random 80 W review and all researcher-adjudication columns are left untouched.
- The existing random-80 AI draft (44 IN candidates, 26 OUT candidates, 10 unresolved) is a *separate exploratory document*, **not** a source of labels for this table.
- Property arrays are an extracted representation; individual Wikidata claim qualifiers, ranks, and references may not be fully retained. If a decision hinges on them, inspect the frozen raw JSONL and verify independently.

## Execution

Place script in `scripts/build_scope_combined_bibliographic_evidence_v0_1.py` and run in the dedicated analysis worktree:

```bash
cd ~/canon-pipeline-openalex-a2val || exit 1
python -B scripts/build_scope_combined_bibliographic_evidence_v0_1.py --dry-run
python -B scripts/build_scope_combined_bibliographic_evidence_v0_1.py
```

The dry-run creates nothing. A writing run refuses to overwrite an existing output directory. The inputs are validated before any output directory is created. Test against the **actual server inputs** before committing output; no server data is available to the author of this script in this chat.

## Next use

Evaluate agreement and contradictions between *evidence* fields by Project W, always separating (1) original work versus edition, (2) original versus translated language, (3) bibliographic classification, and (4) formal researcher scope judgment. Do not exclude the 25,889 W lacking adopted Wikidata QIDs; bibliographic visibility may correlate with literary visibility.
