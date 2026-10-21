# Scope Wikidata bibliographic evidence v0.1 (source evidence; not scope adjudication)

## Purpose

Preserve Wikidata snapshot property **values** for each of the 6,177 Wikidata QIDs already adopted by Project W identity v7. Keep missing Wikidata coverage visible across **all 32,066 active Project W**. This is an independent evidence layer alongside the frozen Open Library bibliographic projection; it does **not** modify either source or decide analytical scope.

## Immutable upstream and snapshot

- Active frame: `derived/scope/scope_evidence_pilot_v1/sampling_frame_v1.tsv`.
- Identity: `derived/identity/work_identity_map_v7.tsv` joined to `derived/identity/source_entities_v3.tsv`, filtered to active Project W and Wikidata item memberships (`accepted_external_identity`).
- Wikidata extraction: `~/research-data/wikidata-source-layer/2026-08-05/wikidata_entities.parquet` from the frozen 2026-08-05 Wikidata dump.
- Source hashes, output hashes, exact counts, and methodological limitations are saved in the generated manifest.

## Output files

1. `scope_wikidata_qid_evidence_v0_1.tsv`: 6,177 Project W/QID rows. Holds the source QID, effective English label, snapshot date, full extracted value arrays for `P31`, `P407`, `P577`, `P629` as JSON strings, counts, parseable positive years from P577, and a boolean showing whether `P407` contains English `Q1860`.
2. `scope_wikidata_project_w_coverage_v0_1.tsv`: exactly 32,066 Project W rows, distinguishing an adopted QID with empty properties from **no adopted QID**. Missing QID is not equivalent to out of scope.
3. `scope_wikidata_bibliographic_evidence_manifest_v0_1.json`: SHA-256 hashes and QC counts.

## Previously observed QC invariants (checked before output)

| Metric | Expected |
|---|---:|
| Active Project W | 32,066 |
| Adopted Wikidata QIDs | 6,177 |
| QIDs with P577 values | 4,473 |
| QIDs with P407 values | 4,893 |
| QIDs with P31 values | 6,120 |
| QIDs with P629 values | 1 |
| QIDs with both P577 and P407 | 3,651 |

## Important interpretive restrictions

- `P577` is a Wikidata publication-date *claim*, not a verified original-first-publication year. The parsed year is only a convenience derivative and cannot replace researcher verification.
- `P407` is a language *claim*, not proof of original composition language. English (`Q1860`) is only one possible value; multiple values are retained.
- `P31` is broad: `Q7725634` means literary work, `Q47461344` written work, and `Q571` book. None alone establishes a *single novel or novella*.
- `P629` typically appears on an **edition/translation item**, pointing to a work. Near-zero P629 among adopted work-level QIDs is not itself a problem.
- The Parquet file retains **flattened property values**, not complete statement objects with rank, qualifiers, or references. Snapshot and QID are source provenance; statement-level citation quality must be evaluated separately if required.
- The 80-work AI exploratory review is **not** a gold standard; do not use its 44/26/10 proposals as researcher-adjudicated truth. This evidence layer does not classify any of the 80 or 32,066 W.
- No modification of frozen OpenAlex outputs, OL corpus, Project W identity, or researcher review templates.

## Reproduction

Install `build_scope_wikidata_bibliographic_evidence_v0_1.py` under `scripts/` and run from the worktree root:

```bash
python -B scripts/build_scope_wikidata_bibliographic_evidence_v0_1.py --dry-run
python -B scripts/build_scope_wikidata_bibliographic_evidence_v0_1.py
```

The second command creates `derived/scope/scope_wikidata_bibliographic_evidence_v0_1/` and refuses to overwrite an existing output directory. Do not rerun the write step over a completed release. The README is intentionally a separately versioned methodology document.

## What remains to do

1. Examine `P31`/`P407` distributions and selected cases for interpretation (without changing adopted QIDs).
2. Compare this new evidence layer to the existing Open Library projection by `project_work_id` in a **separate, non-destructive QC**.
3. Decide a review triage protocol for original publication date, original language, and single novel/novella form; do not automate final scope outcomes from one property.
