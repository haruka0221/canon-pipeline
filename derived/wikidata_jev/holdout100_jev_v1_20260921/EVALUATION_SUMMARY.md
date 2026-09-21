# Jev vs GPT-5.6 Luna for Wikidata Literary-Work Resolution

## Experiment

Goal: compare a decision-native model (Jev) with the frozen GPT-5.6 Luna v6
pipeline for resolving Open Library literary works against Wikidata.

Jev model:
- `jev-1.13.0`

Input representation:
- the same `compact_packet()` representation used by GPT-v6

Jev questions:
1. candidate-level `same_work` Noul for every candidate
2. `any_candidate_match` Noul for the candidate set
3. `best_candidate` Choice among supplied candidates

The Jev question specification was frozen after a 15-item exploratory pilot.
The 100-item holdout predictions were then generated without reading the
human-gold annotations or GPT-v6 holdout judgments.

## Frozen holdout

Total holdout:
- 100 targets
- 68 primary evaluation-eligible (`INCLUDE`)
- 32 excluded as out of intended population scope

Within the 68 primary targets:
- Human MATCH: 15
- Human NO_MATCH: 53
- Candidate-positive: 48
- Zero-candidate: 20

Across all 100 packets:
- Jev API calls: 68
- Zero-candidate deterministic retrieval-stage records: 32
- API failures: 0

## GPT-5.6 Luna v6

Primary eligible n = 68:

- TP = 14
- FP = 0
- FN = 1
- TN = 53
- Accuracy = 67/68 = 98.53%
- Precision = 1.000
- Recall = 0.933
- F1 = 0.966

The single false negative was a candidate-retrieval miss:
`Prince Schamyl's Wooing` (OL1492280W), whose gold QID
`Q124092201` was absent from the frozen candidate set.

Conditional on the gold QID being present in the candidate set,
GPT-v6 selected the correct QID in 14/14 cases.

## Jev: candidate selection

Among the 15 human MATCH cases:

- Gold QID present in candidate set: 14
- Gold QID absent from candidate set: 1
- Gold QID ranked #1 by Jev when present: 14/14
- Gold QID ranked within top 2 when present: 14/14

Thus, conditional on successful candidate retrieval, Jev and GPT-v6 both
selected the gold QID in all 14 evaluable MATCH cases.

The retrieval-miss case was again `Prince Schamyl's Wooing`.
Jev returned a low `any_candidate_match` probability (0.05), which is
appropriate given that the true QID was not among the supplied candidates.

## Jev: threshold-free discrimination

For the 48 primary candidate-positive cases, `any_candidate_match` was
evaluated according to the question Jev was actually asked:

- Positive: the gold matching QID is present in the supplied candidate set
  (n = 14)
- Negative: no true matching QID is present in the supplied candidate set
  (n = 34)

Results:

- `any_candidate_match` ROC AUC = 0.9916
- Positive probability range = 0.24–0.98
- Negative probability range = 0.03–0.68

The candidate-level top Noul probabilities also strongly separated MATCH
and NO_MATCH cases, but the absolute probabilities were not perfectly
calibrated as a direct final MATCH/NO_MATCH rule.

No classification threshold was selected on this holdout.

## Interpretation

Jev showed very strong candidate-ranking performance in this sample:
when the correct QID was available, it ranked that QID first in 14/14 cases.

Its typed probabilistic outputs also expose information that is less explicit
in the GPT-v6 pipeline. In the exploratory pilot, GPT-v6 AMBIGUOUS cases often
produced two simultaneously high candidate-level Noul probabilities.

However, Jev probabilities should not be interpreted naively as final
MATCH probabilities. Some true matches received relatively low absolute
probabilities, while one NO_MATCH case received a comparatively high
probability.

GPT-v6, by contrast, directly returns a final MATCH / NO_MATCH / AMBIGUOUS
decision together with a natural-language rationale.

## Representative Jev failure: Dyrendel

Target:
- OL1061650W
- `Dyrendel.`
- Johan Bojer
- target year 1921

Human gold:
- NO_MATCH

Jev:
- `any_candidate_match` = 0.68
- top candidate = Q12714183
- candidate `same_work` probability = 0.64

The supplied compact representation for Q12714183 contained:

- English label: blank
- description: `1921 novel by Johan Bojer`
- author: Johan Bojer
- publication date: 1921
- title score: 0.0

A post-hoc Wikidata revision audit established that Q12714183 is
`Den siste viking`, a different Johan Bojer novel.

A Wikidata revision from 2026-02-14, predating the frozen 2026-08-05
snapshot, already contained:

- Norwegian Bokmål label: `Den siste viking`
- Norwegian Nynorsk label: `Den siste viking`
- Polish label: `Ostatni wiking`
- corresponding Wikipedia sitelinks

Those multilingual titles were not included in the shared compact
representation supplied to either model.

This case therefore illustrates both:
1. a Jev false positive under the shared evidence representation; and
2. information loss caused by an English-centered candidate representation.

The audit was performed only after holdout predictions were frozen and
human gold was revealed.

## Efficiency

Jev holdout run:

- Jev API calls: 68
- Total input tokens: 262,763
- Mean observed latency: 256.2 ms per Jev request
- API failures: 0

These measurements are specific to this run and environment.

## Main takeaway

On this frozen holdout, both GPT-5.6 Luna v6 and Jev-1.13.0 identified
the correct Wikidata item in all 14 cases where the gold QID was present
in the candidate set.

The models differ substantially in interface and evidential behavior:

- GPT-v6 directly produces a final categorical judgment and explanation.
- Jev produces typed probabilistic judgments that make candidate ranking,
  candidate-set confidence, and ambiguity easier to inspect separately.
- Jev requires an explicit downstream decision rule if probabilities are
  to be converted into MATCH / NO_MATCH / AMBIGUOUS labels.
- Candidate retrieval and metadata representation remain important
  bottlenecks independently of the judge model.

Given the small number of gold-positive cases (14 with the true candidate
available), these results should be treated as an initial private-task
evaluation rather than evidence of general superiority of either model.
