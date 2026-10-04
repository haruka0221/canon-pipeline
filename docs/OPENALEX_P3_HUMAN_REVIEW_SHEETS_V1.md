# OpenAlex P3 human-review sheets v1

This artifact package renders the 493 P3 candidates from the frozen 661-row
human-review package and the frozen P3 deterministic review inventory. It creates
no human judgments, changes no batch membership, and calculates no precision.

Every candidate remains an independent review unit. The LLM judgment, confidence,
reason and note are displayed only as a reference suggestion. Reviewers must apply
the [frozen OpenAlex review protocol v1](OPENALEX_PRECISION_REVIEW_PROTOCOL_V1.md)
independently. Grouping is a review aid only and does not authorize shared human
judgments.

## Frozen inputs

- `derived/openalex_production/openalex_retrieval_precision_review_human_adjudication_v1/full_profile_57959e90/openalex_retrieval_precision_review_human_adjudication_v1.tsv`
- `derived/openalex_production/p3_deterministic_review_inventory_v1/full_profile_57959e90/openalex_p3_deterministic_review_inventory_v1_candidates.tsv`

The inventory owns the candidate-level stable review order, project-specific
evidence subgroup, complexity class, deterministic risk flags, and all 25 batch
assignments. This generator copies those values and rejects any candidate/source
identity disagreement. It sorts by batch sequence, project work ID, project-specific
evidence subgroup order, and stable candidate review order for display; it does not
reassign a candidate.

## Sheet contents

Each batch Markdown sheet contains candidate and project-work navigation, query and
baseline title/author context, OpenAlex identity and full abstract, exact evidence
signature identifiers and match fields, risk flags, and the pre-existing LLM
suggestion fields. It appends six blank authoritative human fields to each
candidate. The reviewer is identified as `haruka_tsutsui`; the per-candidate human
reviewer ID field remains blank for completion during adjudication.

The raw title/author match forms and hit flags are displayed as supplied. The sheet
does not infer title-author co-location, semantic equivalence, or shared judgments.
Risk flags are navigation prompts only.

## Batch index

The TSV index has one row per frozen batch and includes its sequence, candidate and
project-work counts, project-work IDs, complexity distribution, evidence-subgroup
counts, risk-flag counts, and first/last stable candidate review orders. The Markdown
index reiterates the independent-review requirements and links the frozen protocol.

## Reproduction and audit

Run from the repository root:

```bash
python3 scripts/build_openalex_p3_human_review_sheets_v1.py
```

The generator refuses a nonempty output directory, renders the full package twice
from the frozen inputs, and requires byte-identical output maps before writing. The
audit records source hashes, candidate/batch checks, empty human fields, output
hashes, and the explicit no-precision/no-judgments status. It also checks that the
protected P1/P2, review-package, grouping, inventory and BL source trees remain
unchanged while the package is generated.
