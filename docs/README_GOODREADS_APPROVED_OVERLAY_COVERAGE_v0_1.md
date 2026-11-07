# Goodreads approved source-link coverage sensitivity v0.1

Analysis date: 2026-11-07.

## Purpose

Measure the effect of seven approved OL Work-to-Goodreads Work
source links on the frozen 1,797 Project W shared-query-risk cohort.
This is an exploratory source-coverage analysis, not a final
literary-work identity or corpus-scope decision.

## Findings

- Historical crosswalk v1: 0 MATCH, 300 AMBIGUOUS,
  1,497 NO_CANDIDATE among 1,797 risk W.
- Approved overlay: 7 Project W source memberships,
  representing 3 distinct Goodreads Work IDs.
- Rosalynde (GR 1534534): no historical metric carrier rows.
- East Goes West (GR 1035773): 36 ratings, 3 text reviews.
- Chita (GR 1930317): 66 ratings, 13 text reviews.
- None of these Goodreads IDs was already adopted by another
  Project W in the previous v0.2 comparison.
- All observed ratings/reviews are from the historical UCSD
  Goodreads carrier, not current Goodreads statistics.

## Interpretation and limitations

Seven source memberships do not establish seven independent
literary works. The three Goodreads IDs are metric observation
units, not researcher-adjudicated conceptual work identities.

No Goodreads metrics were assigned to individual Project W rows.
No Project W identities were merged, no corpus scope was
adjudicated, and no OpenAlex correlation was recomputed.

The seven reviewed cases form a deliberately selected sample,
not a representative estimate of crosswalk success.

## Reproduction

Run scripts/analyze_openalex_v3_goodreads_approved_overlay_coverage_v0_1.py
with --repo-root pointing to the production analysis worktree.

This script requires historical upstream data that may be
untracked and unavailable in a fresh Git clone.

The result manifest records input and output SHA-256 hashes.
Existing OpenAlex, Goodreads, scope, and holdout data remain
unchanged.
