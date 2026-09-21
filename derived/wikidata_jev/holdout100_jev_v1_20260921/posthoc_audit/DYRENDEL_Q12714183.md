# Post-hoc audit: Dyrendel / Q12714183

Target:
- OL1061650W
- Dyrendel.
- Johan Bojer
- target year: 1921

Human gold:
- NO_MATCH
- No corresponding Wikidata work item identified for Dyrendel/Dyrendal.

Jev result:
- any_candidate_match: 0.68
- top candidate: Q12714183
- candidate same_work probability: 0.64

Evidence supplied to Jev for Q12714183:
- English label: blank
- description: "1921 novel by Johan Bojer"
- author: Johan Bojer
- publication date: 1921
- title_score: 0.0

Post-hoc Wikidata revision audit:
- revision ID: 2463478153
- revision timestamp: 2026-02-14T19:41:15Z
- nb label: Den siste viking
- nn label: Den siste viking
- pl label: Ostatni wiking
- nnwiki: Den siste viking
- nowiki: Den siste viking
- plwiki: Ostatni wiking

Interpretation:
Q12714183 represents Den siste viking, not Dyrendel. The frozen
candidate representation supplied to both models omitted these
non-English labels/sitelink titles. Thus this is a Jev false positive
under the shared compact evidence representation, while also exposing
an information-loss limitation in that representation.

This audit was performed after unblinding the holdout and must not be
treated as information available to the frozen Jev prediction run.
