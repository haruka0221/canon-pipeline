# Population Definition

## Main Study (Dump-Based)
- Source: Open Library Works Dump
- Snapshot date: 2026-02-28
- Download URL: https://archive.org/download/ol_dump_2026-02-28/ol_dump_works_2026-02-28.txt.gz
- Local file: raw/ol_dump/ol_dump_works_2026-02-28.txt.gz
- Filter criteria:
  - first_publish_year: 1880–1950
  - language: eng (handling TBD at implementation)
  - subject_keys: exclusion rules (see WORKFLOW.md Stage 2)
- Population file: derived/ol_dump_population_2026-02-28.tsv (to be created)

## Pilot Study (API-Based, Superseded)
- Source: Open Library Search API
- Retrieved: 2026-02-22 to 2026-03-04
- Population file: derived/ol_works_augmented_population.tsv (4,884 works)

## Fiction Filter (Inclusion-Based)
- Filter: subject_keys must contain at least one of 18 fiction signals
- Fiction population file: derived/ol_dump_population_fiction_2026-02-28.tsv
- Fiction population size: 34,789 works

## Quality Audit (fiction population)
- Sample: 200 works, seed=20260307
- OK: 189 (94.5%)
- Uncertain: 6 (3.0%)
- NG: 5 (2.5%)
- Audit file: derived/ol_dump_fiction_audit200_seed20260307.tsv
- NG residual cause: subject inconsistency (bibliography/criticism tagged with fiction keys)
