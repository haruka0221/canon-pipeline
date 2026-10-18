# Restricted files: BL verification pilot v1

The British Library's terms of use for its catalogue records do not allow retrieved bibliographic records to be redistributed to third parties without permission. To comply, the seven files below were removed from the latest version of this public repository. They contain fields of BL records verbatim (MARC field values, or LLM reasons quoting them).

The Git history has not been rewritten. The files remain in earlier commits.

## Removed files

| file | sha256 |
|---|---|
| `records_parsed.tsv` | `7ea6a940e191baa3d86d874280b868aaddcf627fdaf50c909eab7c1c16d58efb` |
| `q1_failure_examples.tsv` | `0cfc3b486192afabadc7d76aafba491f7e9a4a9107caabe1d3a02edffeb4de72` |
| `q1_first_edition_matching.tsv` | `1fb22dc6c3e04eded4a8b47bb3ff88df5fc3d534e84cfa5e4be1e647f75f18d9` |
| `q2_candidates.tsv` | `1c3cc7ffc3d4b66581d3421562c790870b23129a731f902d5769168b04df07fc` |
| `q3_candidates.tsv` | `aee831992ea69fc9c4c00c41b5a67eb59d18bb88745fcbde3dbe212ec1e33805` |
| `q2_llm_output.tsv` | `0954d0c19e39241055c516ee01519468b049dc3ed92927b2cd085da2d706c537` |
| `q3_llm_output.tsv` | `ed1afb3cc5ce2027a82072f6da317931d9dc0a3a6f9669fb31c3b853597b84a6` |

The hashes are the values recorded in `manifest.json`.

## Private copies

Copies of the seven files are kept in a private storage location outside the repository. Their identity with the removed files can be checked against the sha256 values above.

## What was kept

- `manifest.json` is kept unchanged as a frozen record. It still lists these seven files with their hashes.
- Short quotations from BL records in the research write-up (`summary.md`, the human confirmation table `q2_first_edition_review.tsv`, and the analysis addenda in `docs/`) were kept.
- Files that contain only BL record identifiers (`marc_001`) were kept.

## Status

We have asked the British Library how these files should be handled. This note will be updated when we have an answer.
