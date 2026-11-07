# All-W bibliographic source signals and review priority v0.1

Status: exploratory, non-adjudicative scope diagnostics.

## Population

32,066 active Project W.

## Findings

- OpenAlex measured: 31,713 W
- Historical Goodreads ratings observed: 4,642 W
- Shared-query-risk W: 1,797
- Wikidata QID coverage: 6,177 W
- Mixed-period date signals: 620 W
- No date evidence: 4 W
- Only 1880–1950 date signals: 31,442 W
- Frozen independent random sample: 80 W
- Researcher scope decisions created: 0

## Outputs

- All-W bibliographic source-signal table
- Top-400 review-priority queue
- Fixed random-80 source-signal table
- Summary and SHA-256 manifest

## Limitations

Open Library dates are edition-derived, not verified original
publication years.

Wikidata P577, P407 and P31 are evidence signals, not independent
verification of original year, language or novel/novella form.

Priority score zero does not establish eligibility.

No Project W identities, final scope decisions, OpenAlex counts,
Goodreads matches, holdout records or correlations were changed.

## Reproduction

Run scripts/build_openalex_all_w_scope_screening_signals_v0_1.py
with --repo-root pointing to the production analysis worktree.
