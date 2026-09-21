# Wikidata v6 Production Freeze — 2026-09-21

## Population

- Open Library works: 34,789
- Population snapshot: 2026-02-28
- Frozen Wikidata dump: 2026-08-05

## Candidate retrieval

- Targets with >=1 candidate: 24,015
- Targets with zero candidates: 10,774
- Unique candidate QIDs: 71,957
- Zero-candidate records are treated as retrieval-stage NO_MATCH only.
- This does not assert that no corresponding Wikidata work item exists.

## LLM judgment

Model: `gpt-5.6-luna`

Judged targets: 24,015

- MATCH: 8,442
- NO_MATCH: 15,215
- AMBIGUOUS: 358

Confidence:

- high: 23,403
- medium: 549
- low: 63

No failed production judgments remained.

## Context-window fallback

Exactly one target required the context-safe fallback:

- OL2877017W — *Dawn breaks the heart* — William Davey

The candidate set and candidate order were unchanged.
The complete P50 author lists were inspected deterministically before
only target-relevant author relations and full-list membership/count
facts were passed to the judge.

Final decision for this target: NO_MATCH (high).

All other 24,014 judged targets used the ordinary full compact packet.

## Final 34,789-work resolution

- MATCH: 8,442
- NO_MATCH: 25,989
  - LLM-judged NO_MATCH: 15,215
  - zero-candidate retrieval-stage NO_MATCH: 10,774
- AMBIGUOUS: 358

`resolution_stage` distinguishes LLM judgments from deterministic
zero-candidate retrieval outcomes.

## Frozen holdout

The v6 decision procedure was evaluated on the prediction-blind frozen
holdout before production.

Primary eligible n=68:

- accuracy: 67/68 = 98.5294%
- TP=14, FP=0, FN=1, TN=53
- precision=1.0
- recall=0.9333
- F1=0.9655

All 100 records:

- accuracy: 98/100 = 0.98
- TP=24, FP=0, FN=2, TN=74
- precision=1.0
- recall=0.9231
- F1=0.9600

The two errors were candidate-retrieval misses rather than errors among
cases where the gold QID was present in the candidate set.

## Reproducibility note

The production runner was patched during execution to:
1. continue after repeated malformed model JSON rather than terminate;
2. avoid repeated identical requests after a context-window error; and
3. use the documented context-safe fallback for an actual overflow.

These changes did not alter previously saved judgments.
Only one final judgment used the context-safe fallback.

The final result files should be treated as frozen and not edited in place.
