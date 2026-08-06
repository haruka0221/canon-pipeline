# OpenAlex Literary Candidate Classification Prototype

## Overview

This folder contains a diagnostic prototype for identifying scholarly
discussion of literary works in OpenAlex metadata.

The prototype has two related purposes:

1. to test a broad candidate-retrieval method based on literary work
   titles and author names; and
2. to test whether an LLM can distinguish substantive literary
   scholarship, brief scholarly mentions, non-scholarly records, and
   unrelated false matches.

This is a small collaboration prototype rather than a complete
bibliography or a production-ready scholarly-visibility dataset.

The prototype uses OpenAlex record titles, record types, topics, and
reconstructed abstracts. Full publication texts were not consulted.

## Target works

The diagnostic dataset contains three widely canonical literary works
and one deliberately difficult generic-title stress test:

- Joseph Conrad, *Heart of Darkness*
- F. Scott Fitzgerald, *The Great Gatsby*
- James Joyce, *Ulysses*
- Sinclair Lewis, *The Job*

*The Job* was included to examine false matches produced by a short,
generic title and the common surname “Lewis.”

## Candidate retrieval

OpenAlex dump records were treated as candidates when:

- the complete target-work title phrase appeared somewhere in the
  combined OpenAlex title and reconstructed abstract; and
- the target author's surname also appeared in that combined text.

The candidate retrieval step used the complete reconstructed abstract.

Up to 40 candidate records per target work were retained through uniform
reservoir sampling with the fixed random seed `20260713`.

The resulting candidate-pool counts were:

| Target work | Candidate pool | Reservoir sample |
|---|---:|---:|
| Heart of Darkness | 1,005 | 40 |
| The Great Gatsby | 858 | 40 |
| The Job | 161 | 40 |
| Ulysses | 2,194 | 40 |

Candidate-pool counts are broad retrieval results. They are not counts of
relevant scholarly publications.

## Classification labels

Each candidate record is assigned one of five labels:

- `include_substantive`: the metadata shows substantive interpretation,
  analysis, comparison, reception, adaptation, or contextual discussion
  of the target work.
- `include_mention`: a genuine scholarly secondary source uses the work
  as a comparison, example, quotation, or reference, but the supplied
  metadata does not show sustained analysis of the work.
- `exclude_non_scholarly`: the record is connected to the literary work
  but is a primary text, ebook, front matter, event record, personal
  recollection, download page, or another form of non-secondary-
  scholarly material.
- `exclude_unrelated`: the candidate results from an unrelated title,
  phrase, surname collision, or another false match.
- `unclear`: the available metadata is contradictory or insufficient
  for a reliable decision.

For the broad binary classification task:

- `include_substantive` and `include_mention` are treated as included;
- `exclude_non_scholarly` and `exclude_unrelated` are treated as
  excluded.

## Initial diagnostic classification

The original reservoir samples were classified using `gpt-5-mini` and
prompt version:

`literary_visibility_v3_20260804`

During this initial diagnostic stage, candidate retrieval used complete
reconstructed abstracts, but the abstracts stored for classification
were limited to the first 1,200 characters.

Records initially assigned to the boundary categories
`include_mention`, `exclude_non_scholarly`, and `unclear` were manually
inspected. Two Ulysses records were relabelled during this targeted
review.

The initial post-review sample composition was:

| Target work | Sampled | Substantive | Mention | Non-scholarly | Unrelated | Unclear | Included share |
|---|---:|---:|---:|---:|---:|---:|---:|
| Heart of Darkness | 40 | 34 | 2 | 0 | 3 | 1 | 0.923 |
| The Great Gatsby | 40 | 38 | 1 | 1 | 0 | 0 | 0.975 |
| The Job | 40 | 0 | 0 | 0 | 40 | 0 | 0.000 |
| Ulysses | 40 | 31 | 2 | 3 | 4 | 0 | 0.825 |

These figures describe the composition of the sampled candidate records.
They are not visibility rankings, precision estimates, or extrapolated
publication totals.

The 1,200-character limit was subsequently found to hide the retrieval
evidence in some records. The initial sample results are therefore
retained as diagnostic evidence but are not used for the provisional F1
evaluation below.

## Full-abstract internal evaluation

A separate set of 30 records was selected from the reservoir samples for
a provisional internal evaluation:

| Target work | Evaluation records |
|---|---:|
| Heart of Darkness | 8 |
| The Great Gatsby | 8 |
| Ulysses | 8 |
| The Job | 6 |
| Total | 30 |

Records previously used as discussed or illustrative examples were
excluded before sampling. The evaluation sample used the fixed random
seed `20260805`.

For this evaluation, both the human reviewer and the LLM classifier were
provided with the complete reconstructed OpenAlex abstracts.

The LLM classification used `gpt-5-mini` and prompt version:

`literary_visibility_v3_fullabstract_20260806`

The human-reviewed binary evaluation produced the following confusion
matrix:

| | Human include | Human exclude |
|---|---:|---:|
| LLM include | 22 | 2 |
| LLM exclude | 0 | 6 |

The resulting metrics were:

| Metric | Result |
|---|---:|
| Precision | 0.917 |
| Recall | 1.000 |
| F1 | 0.957 |
| Accuracy | 0.933 |
| Specificity | 0.750 |
| Exact five-label agreement | 0.833 |

The classifier retained all 22 records judged relevant by the human
reviewer.

The two binary false positives were:

- a preliminary-material record associated with a scholarly volume; and
- a personal recollection concerning James Joyce.

Both records were related to the target work or author, but were judged
not to constitute scholarly secondary literature.

## Interpretation

The provisional evaluation suggests that the classifier performs well
at retaining potentially relevant records in this small sample.

Its principal difficulty is not identifying the literary connection,
but distinguishing secondary scholarship from related non-scholarly
materials such as front matter and personal recollections.

The evaluation measures classification of records that had already been
retrieved as candidates. It does not measure whether the retrieval
method finds all relevant OpenAlex records.

In particular, the reported recall of `1.000` is classification recall
within the 30-record evaluation sample. It is not retrieval recall for
OpenAlex as a whole.

## Illustrative examples

The curated examples show several characteristic cases:

- relevant literary scholarship recovered from an abstract even when
  the OpenAlex topic is misleading;
- brief but genuine scholarly comparison with a target work;
- electronic editions and other non-secondary-scholarly records;
- false matches produced by generic titles and common surnames; and
- contradictory OpenAlex metadata requiring an `unclear` decision.

OpenAlex topic labels are retained as diagnostic metadata and are not
used as automatic exclusion criteria.

## Files

### Main diagnostic files

- `curated_openalex_examples.tsv`

  Six representative records illustrating successful retrieval,
  scholarly mentions, non-scholarly records, unrelated matches, and
  contradictory metadata.

- `llm_judged_candidate_sample.tsv`

  A diagnostic subset containing OpenAlex metadata, the original LLM
  labels, reviewed labels, classification reasons, and review notes.

- `work_level_validation_summary.tsv`

  Work-level summaries of the original 40-record reservoir samples.

### Evaluation files

- `evaluation/provisional_internal_evaluation_30.tsv`

  Record-level comparison between the human labels and the full-abstract
  LLM labels. Complete abstracts are not redistributed in this file.

- `evaluation/provisional_internal_evaluation_summary.json`

  Machine-readable summary of the confusion matrix and evaluation
  metrics.

## Limitations

This evaluation is provisional and internal.

The principal limitations are:

- the evaluation contains only 30 records;
- it covers only four literary works;
- the same four works were used during prototype development;
- the human labels were produced by one reviewer;
- classification is based on OpenAlex metadata rather than publication
  full text;
- OpenAlex abstract availability and metadata quality vary substantially;
  and
- retrieval recall has not yet been evaluated.

The results should therefore not be interpreted as an independent
external benchmark, a complete bibliography, or a general estimate of
performance across literary studies.

## Status

The prototype is suitable for methodological discussion and small-scale
collaborative exploration.

Before production use, the method would require a larger independently
reviewed evaluation set, broader coverage of literary works, explicit
retrieval-recall testing, and further refinement of the distinction
between secondary scholarship and related non-scholarly records.
