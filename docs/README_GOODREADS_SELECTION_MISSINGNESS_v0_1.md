# Goodreads selection and missingness diagnostic v0.1

Status: exploratory; not a scope or work-identity adjudication.

Input: frozen OpenAlex v3 / Goodreads comparison v0.2,
32,066 Project W. Historical Goodreads UCSD metrics only.

## Results

- OpenAlex measured: 31,713 W; unmeasured: 353 W.
- Goodreads historical ratings observed: 4,642 W
  (14.64% of OA-measured W).
- CORE3=0: Goodreads observed for 2,256/25,461 W (8.86%).
- CORE3>=25: Goodreads observed for 513/828 W (61.96%).
- The matched sample is strongly selected by OA candidate-pair count.
- Shared-query-risk W with observed GR metrics in frozen v0.2: 0/1,797.

## Interpretation

These are Project W units, not independently validated conceptual works.
OpenAlex CORE3 counts are candidate pairs, not verified scholarly citations.
Missing Goodreads data do not mean zero readership.

The association does not establish causality or correct missing-not-at-random
selection. The seven approved OL-to-GR links are intentionally not adopted
in the frozen v0.2 comparison.

No existing input, scope decision, holdout, identity or correlation was changed.

## Reproduction

Run scripts/analyze_openalex_v3_goodreads_selection_missingness_v0_1.py
with --repo-root pointing to the production analysis worktree.
Input/output SHA-256 values are recorded in manifest_v0_1.json.
