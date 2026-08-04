# OpenAlex literary-visibility prototype

## Purpose

This diagnostic prototype demonstrates how candidate OpenAlex records
can be linked to literary works and assessed for evidence of scholarly
visibility in OpenAlex metadata.

The classification uses only the OpenAlex record title, record type,
topic, and abstract. Full texts were not consulted.

## Labels

- `include_substantive`: the metadata shows substantive interpretation,
  analysis, comparison, reception, adaptation, or contextual discussion
  of the target work.
- `include_mention`: a genuine scholarly secondary source uses the work
  as a comparison, example, quotation, or reference, without showing
  substantive analysis in the supplied abstract.
- `exclude_non_scholarly`: the record is connected to the work but is a
  primary text, ebook, download page, event record, or other
  non-secondary-scholarly material.
- `exclude_unrelated`: the candidate results from an unrelated title,
  phrase, surname collision, or other false match.
- `unclear`: the available metadata is contradictory or insufficient.

Both `include_substantive` and `include_mention` are retained as broad
scholarly visibility.

## Method

Candidate records were retrieved when the complete target-work title
phrase and author surname both appeared somewhere in the combined
title-and-abstract text of an OpenAlex record.

Up to 40 records per work were selected through uniform reservoir
sampling with the fixed seed `20260713`.

The sampled records were classified using `gpt-5-mini` and prompt
version `literary_visibility_v3_20260804`.

All records initially assigned to the boundary categories
`include_mention`, `exclude_non_scholarly`, and `unclear` were manually
inspected. Two Ulysses records were relabelled after review. The original
LLM label, final label, and review note are preserved in the data.

The proportions below describe the composition of the sampled candidate
records after targeted review. They are not work-level visibility scores,
human-validated precision estimates, or estimated totals of relevant
scholarship.

## How to read the results

The prototype contains three widely canonical works—*Heart of
Darkness*, *The Great Gatsby*, and *Ulysses*—plus *The Job* as a
deliberately difficult generic-title stress test.

`Candidate pool` is the number of records returned by the broad
retrieval step. It is not the number of relevant scholarly publications.

`Included share among decided sample` is calculated as:

`(include_substantive + include_mention) / all decided sampled records`

Records labelled `unclear` are excluded from the denominator. This
proportion evaluates the retrieved candidate sample; it should not be
used to rank the scholarly visibility of the four literary works.

OpenAlex topic labels are retained as diagnostic metadata and are not
used as automatic exclusion criteria.

## Candidate-validation results

| Target work | Candidate pool | Sampled | Substantive | Mention | Non-scholarly | Unrelated | Unclear | Included share among decided sample |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Heart of Darkness | 1005 | 40 | 34 | 2 | 0 | 3 | 1 | 0.923 |
| The Great Gatsby | 858 | 40 | 38 | 1 | 1 | 0 | 0 | 0.975 |
| The Job | 161 | 40 | 0 | 0 | 0 | 40 | 0 | 0.000 |
| Ulysses | 2194 | 40 | 31 | 2 | 3 | 4 | 0 | 0.825 |

## Illustrative examples

| Target work | OpenAlex record | OpenAlex topic | Match evidence | Final label | Why it matters |
|---|---|---|---|---|---|
| Ulysses | [All the Dishevelled Wandering Stars: Astronomical Symbolism in "Ithaca"](https://openalex.org/W2315163088) | Shakespeare, Adaptation, and Literary Criticism | abstract_only | include_substantive | A relevant Ulysses study recovered from the abstract although the target work is absent from the record title and the OpenAlex topic is misleading. |
| Heart of Darkness | [Holroyd’s Man](https://openalex.org/W2501226940) | Medical and Biological Sciences | abstract_only | include_substantive | A broader Conrad study retained because the abstract substantively discusses Heart of Darkness despite its Medical and Biological Sciences topic. |
| Ulysses | [The Da Vinci Code: A Pseudo-Feminist Text](https://openalex.org/W3022167826) | Gothic Literature and Media Analysis | abstract_only | include_mention | A genuine but brief scholarly comparison with Ulysses, retained as broad visibility rather than substantive analysis. |
| The Great Gatsby | [The Great Gatsby — electronic text](https://openalex.org/W7047645099) | Superconducting and THz Device Technology | title_only | exclude_non_scholarly | An electronic edition of the primary text, excluded because it is not scholarly secondary literature. |
| The Job | [Controlled/Living Cationic Polymerization of p-Methoxystyrene in Solution and Aqueous Dispersion Using Tris(pentafluorophenyl)borane as a Lewis Acid: Acetonitrile Does the Job](https://openalex.org/W2015478441) | Synthetic Organic Chemistry Methods | title_only | exclude_unrelated | A chemistry article produced by a generic-title and surname collision, excluded as unrelated. |
| Heart of Darkness | [Into the Jungle: Disentangling Form and Content in Conrad's Heart of Darkness](https://openalex.org/W24554225) | Joseph Conrad and Literature | title_only | unclear | A record with a literary title but an unrelated medical abstract, retained as unclear because the metadata conflict. |

## Files

- `curated_openalex_examples.tsv`: six representative records showing
  successful retrieval, scholarly mentions, non-scholarly records,
  unrelated false matches, and contradictory metadata.
- `work_level_validation_summary.tsv`: work-level results for the full
  reservoir samples.
- `llm_judged_candidate_sample.tsv`: a smaller diagnostic subset with
  metadata, LLM labels, final labels, reasons, and review notes.

This is a diagnostic collaboration prototype, not a complete bibliography
and not a fully human-validated gold-standard dataset.
