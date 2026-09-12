# Wikidata Production Resolver: Final v3 Unseen Holdout Evaluation

Date: 2026-09-12

## Evaluation status

This file records the final evaluation of the frozen v3 Wikidata work-level
resolver on the untouched second half (review orders 51–100) of a fixed-seed
random sample from the Open Library population.

The first 50 reviewed records had already been used diagnostically to formulate
the v3 work-identity and granularity policy. They are therefore not part of this
final untouched evaluation.

Human review was performed without showing the v3 predictions. Live Wikidata
and external bibliographic evidence could be consulted, and LLM assistance was
used during manual verification. The gold procedure should therefore be
described as:

> prediction-blind manual verification with LLM-assisted review

rather than as purely human-only annotation.

## Frozen artifacts

```text
target input
derived/benchmark/holdout/unseen_random50_review51_100_seed20260912.tsv
SHA256 1380a1f369ae92818f0762cf7e03e6470e851a9e3b3092ca458970f77d2859dc

judge prompt
prompts/wikidata_judge_v3.txt
SHA256 e72640f4af84d86cf3f71efbdba06e5972b6882ab2d53ee7c1a33b1a551ab2ca

resolver
scripts/wikidata_resolver_production.py
SHA256 a57041f928e5f72fb8fc23603b9b1c7cbb0032bd554c5aa7f5e4501c6a662993

Stage 2 packets
derived/benchmark/holdout/random50_v3_final/stage2_packets.jsonl
SHA256 5dd4a0c10107a418acaf332cb4405dca2c6df024e72380555f8aeaf28d2643e1

frozen judgments
derived/benchmark/holdout/random50_v3_final/judgments.jsonl
SHA256 0a2b6a4d58e7439fa656502cb2ae97c3191ccfed160d8b8af29fbd4693b1ac03

frozen results
derived/benchmark/holdout/random50_v3_final/results.tsv
SHA256 83baca18a761ddcb44852b1d4f0eb80c540d63ccf38a4d97db4828b0df6c75e5

completed manual gold
derived/benchmark/holdout/random50_v3_final/human_gold/random50_human_blind_51_100.tsv
SHA256 c4aa43c60f5840d69adb28338474f7e5ae6de4a235d1981b6b92496dc5a84470
```

## Final results

```text
Annotated: 50

Gold decisions:
NO_MATCH    38
MATCH       12
AMBIGUOUS    0

Exact 3-way decision agreement:
48 / 50 = 0.960

Binary MATCH/AMBIGUOUS vs NO_MATCH:
TP = 11
FN = 1
FP = 0
TN = 38

Precision   = 1.000
Recall      = 0.917
F1          = 0.957
Specificity = 1.000

Primary-QID accuracy, gold-positive only:
11 / 12 = 0.917

Set-aware Top-1 accuracy, gold-positive only:
11 / 12 = 0.917
```

The preferred work-level QID was present in the candidate set for all 12
gold-positive records:

```text
positive candidate recall = 12 / 12 = 1.000
```

## Disagreement 1: Under Milk Wood

Target:

```text
Under Milk Wood / Dylan Thomas
```

Gold:

```text
MATCH Q2497140
```

Prediction:

```text
AMBIGUOUS Q2497140
alternatives: Q20601952; Q20601957
```

Prediction reason:

> All three candidates are work-level items with the exact title Under Milk
> Wood and author Dylan Thomas, and none is linked as an edition or translation.
> Q2497140 is preferred because it has a clear description and English
> Wikipedia link, but Q20601952 and Q20601957 remain plausible duplicate work
> representations.

Manual inspection supported Q2497140 as the work-level item. Q20601952 and
Q20601957 were associated with more specific BBC/CD manifestations despite
being broadly typed as `literary work`.

Error class:

```text
ambiguity calibration
manifestation granularity
```

This is not a candidate-retrieval failure because the preferred QID was both
retrieved and selected.

## Disagreement 2: The Flower and Market Girls of Paris

Target:

```text
The flower and market girls of Paris / Emile Zola
```

Gold:

```text
MATCH Q338034
```

Prediction:

```text
NO_MATCH
```

Prediction reason:

> None of the supplied candidates has the target title or an affirmative title
> relation to “The flower and market girls of Paris.” Although Q338034 concerns
> Parisian markets and has the correct author, thematic similarity alone is
> insufficient to identify it as the target work.

Q338034 is Émile Zola's *Le Ventre de Paris*. The target is an English
translation title of that underlying work. The correct QID was therefore
present in the candidate packet, but the packet lacked explicit evidence
connecting the translated English title to the French work title.

Error class:

```text
translated-title normalization
evidence enrichment
```

This is not a candidate-retrieval failure.

## Interpretation

The v3 resolver was conservative on this final holdout. It produced no false
positive matches and one false negative. The two exact-decision disagreements
arose after candidate retrieval rather than from failure to retrieve the
preferred work-level entity.

The first disagreement concerns how Wikidata models multiple same-title,
same-author entities across work and manifestation levels. The second concerns
cross-lingual or translated-title evidence that is not explicitly represented
in the candidate packet.

The final result should be reported as `48/50 (96.0%)`, not only as a
percentage. The sample contains only 12 gold-positive cases and no gold
`AMBIGUOUS` cases, so positive-case and ambiguity estimates remain limited.

The v3 prompt is frozen after this evaluation. These two cases remain genuine
final-holdout errors and should not be used to retroactively revise the reported
v3 result.

## Relation to the earlier unseen diagnostic sample

The preceding 50 reviewed records were evaluated with v2 and yielded:

```text
exact decision agreement = 47 / 50 = 0.940

TP = 14
FN = 1
FP = 2
TN = 33

Precision   = 0.875
Recall      = 0.933
F1          = 0.903
Specificity = 0.943

Primary-QID accuracy, gold-positive only = 14 / 15 = 0.933
Set-aware Top-1, gold-positive only      = 14 / 15 = 0.933
```

Those three disagreements were used to formulate the explicit v3
work-identity/granularity policy. Consequently, the first 50 records are a
diagnostic/development sample, while review orders 51–100 form the final
untouched v3 holdout.

The v2 and v3 percentages should therefore not be presented as a paired
statistical improvement on the same test set. A suitable description is:

> Error analysis on an initial unseen sample of 50 records led to an explicit
> work-identity and granularity policy. The revised resolver was then frozen
> and evaluated on a separate untouched sample of 50 records, achieving 48/50
> exact decision agreement (96.0%).
