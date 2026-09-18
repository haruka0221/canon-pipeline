# Wikidata v6 Fresh Holdout Final Evaluation

## Frozen evaluation

- Human-gold freeze commit: `5c6316e`
- Prediction freeze commit: `c0fdc47`
- Fresh holdout: 100 records
- Primary evaluation population: 68 INCLUDE records
- Out-of-scope records retained in sample: 32
- Model: `gpt-5.6-luna`

## Primary evaluation: INCLUDE records

- N: 68
- Strict accuracy: 67/68 = 98.5294%
- TP: 14
- FP: 0
- FN: 1
- TN: 53
- Precision: 1.0000
- Recall: 0.9333
- F1: 0.9655
- Candidate recall among gold MATCH cases:
  14/15 = 93.3333%

The sole primary error was `Prince Schamyl's Wooing`
(OL1492280W; gold Q124092201), whose correct QID was absent from
the frozen candidate set.

## Sensitivity analysis: all 100 sampled records

- N: 100
- Strict accuracy: 98/100 = 98.0000%
- TP: 24
- FP: 0
- FN: 2
- TN: 74
- Precision: 1.0000
- Recall: 0.9231
- F1: 0.9600
- Candidate recall among gold MATCH cases:
  24/26 = 92.3077%

The two strict errors were:

1. `Rossingon FR Nightingale` (OL8408550W; gold Q1200454)
2. `Prince Schamyl's Wooing` (OL1492280W; gold Q124092201)

In both cases the correct gold QID was absent from the frozen
candidate set. Both Wikidata items predated the 2026-08-05
snapshot, so these are genuine candidate-retrieval misses rather
than post-snapshot Wikidata additions.

No false-positive MATCH predictions were observed.

Among gold MATCH cases for which the correct QID was present in
the frozen candidate set, v6 selected the correct QID in all
observed cases (24/24 overall; 14/14 in the primary population).
This conditional result should be reported separately from
end-to-end accuracy because candidate generation constrains the
judge's available choices.
