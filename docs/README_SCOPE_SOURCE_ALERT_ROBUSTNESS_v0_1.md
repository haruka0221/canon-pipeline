# OpenAlex v3 scope-source-alert robustness v0.1

Status: exploratory, not researcher-adjudicated scope.

Frozen v0.2 correlations were successfully reproduced before
running sensitivity analysis.

## CORE3 vs historical Goodreads ratings (Spearman)

| Scenario | Matched W | rho |
|---|---:|---:|
| BASELINE_ALL_W | 4642 | 0.411970 |
| NO_SHARED_QUERY_AND_SINGLE_OL | 4293 | 0.405055 |
| NO_SOURCE_ALERTS | 3791 | 0.354431 |
| NO_SOURCE_ALERTS_PLUS_WD_WINDOW_ENGLISH | 1348 | 0.349465 |

The selection criteria use bibliographic source signals rather
than the review-priority score, which includes OpenAlex counts.

These cohorts do NOT establish literary scope eligibility.
Wikidata availability is strongly selected, Goodreads coverage
is nonrandom, and OpenAlex counts remain provisional candidate
document pairs.

The output includes scenario-specific correlations, recomputed
percentile extremes, Goodreads observation-rate comparisons,
summary statistics and a SHA-256 manifest.

No existing scope decisions, source identities, human judgments,
OpenAlex attribution data or frozen correlations were modified.
