# OpenAlex retrieval precision review protocol v1

Status: **Protocol definition for precision-review v1**. This document specifies `review_protocol_version = v1`;
it does not claim a Git freeze or completed adjudication. Starting implementation
commit: `f839adc2f24a67b8dfb9cacc741c0a19ca870825`.

This is a detailed methodological appendix to [WORKFLOW.md](../WORKFLOW.md)
and [OPENALEX_MATCHING_METHOD.md](OPENALEX_MATCHING_METHOD.md). The older method's
conceptual attribution vocabulary is historical context; the v1 judgment table
specified here uses the explicit vocabulary below. Document scope, mention strength,
production retrieval policy and final visibility counting remain separate decisions.

## Purpose and estimand

Primary question: **Does the retrieved title/author evidence actually refer to the
intended project literary work W?**

The review unit is a frozen `(project_work_id, openalex_work_id)` candidate, not a
query ID or provenance row. One OpenAlex record may refer validly to several W.
The 661-row candidate-v3 release contains the two disjoint marginal increments:
409 `ALIAS_EXPANSION` (R3+A2 minus R2+A2) and 252 `A2_AUTHOR_REVERSAL`
(R3+A2 minus R3+A1). These allow marginal target-attribution precision evaluation
for R3 alias expansion and A2 author reversal only. They do not establish R2
absolute precision or R4 precision. The 24 development cases are not precision data.

Explicitly excluded: scholarly-visibility inclusion; OpenAlex document type/scope
policy; mention-strength policy; final visibility counting; R2 absolute precision
inference; R4 precision inference. A bibliographic, primary-text, archival or
non-scholarly record can still be valid for target attribution. Type, topic,
language and fulltext availability are not scope inclusion decisions in this review.

## Primary judgments and work identity

- `VALID_TARGET_REFERENCE`: context semantically links the matched title expression
  to intended W and its associated author/creator. Exact bibliographic wording is
  not required; a substantive discussion is not required for attribution.
- `INVALID_TARGET_REFERENCE`: available evidence establishes false attribution to
  W, including another work/person, lexical title use or unlinked co-occurrence.
- `UNCERTAIN`: available evidence genuinely cannot decide valid versus invalid.
  Record what identity or context information is missing.

Apply all of these rules:

1. An explicit reference to source W remains valid in discussion of an adaptation.
2. Adaptation/derivative-only evidence does not establish source-W reference merely
   from shared title/author.
3. If source versus derivative identity cannot be resolved: `UNCERTAIN`.
4. Collection and component works must be distinguished. A component-only reference
   does not automatically establish a reference to its containing collection.
5. Title variants may be valid where evidence supports the same underlying W.
6. Frozen alias membership supplies project identity context but is not independent
   corroboration or automatic proof of semantic equivalence. Document reliance on
   it, particularly for collection contents or same-title story/drama distinctions.
7. Generic/genre lexical use plus a nearby author name is not a target reference.
8. An unnamed quotation/essay can support attribution only where context sufficiently
   identifies its source as W. Author name and matching subject matter alone do not
   necessarily identify the work.
9. Editor/compiler/translator/contributor roles do not automatically invalidate a
   target reference, but role co-occurrence alone does not establish work identity.
   Distinguish whole-work identity from attribution of a component contribution.

Use project identity evidence to resolve form/collection boundaries where possible;
do not silently revise project identity or treat scanner firing as semantic proof.
Missing abstract alone does not imply `UNCERTAIN`: a sufficiently identifying OA
record title can decide attribution. Inspect all supplied title/abstract context,
including references inside discussions primarily about another work.

## Reason taxonomy and precedence

Exactly one reason code is required, compatible with the primary judgment.

| Judgment | Code | Meaning |
|---|---|---|
| VALID_TARGET_REFERENCE | DIRECT_TARGET_REFERENCE | Explicit title/work and author linkage identifies W. |
| VALID_TARGET_REFERENCE | VALID_TITLE_VARIANT | Supported alternate spelling, abbreviated/expanded title or other equivalent title denotes W. |
| VALID_TARGET_REFERENCE | VALID_CONTEXTUAL_REFERENCE | Context sufficiently identifies W without a direct bibliographic naming formula. |
| INVALID_TARGET_REFERENCE | TITLE_COLLISION_DIFFERENT_WORK | Matched title denotes a distinct work. |
| INVALID_TARGET_REFERENCE | GENERIC_OR_LEXICAL_TITLE_USE | Matched expression is ordinary vocabulary, genre or category rather than W. |
| INVALID_TARGET_REFERENCE | AUTHOR_COLLISION_DIFFERENT_PERSON | Matched name denotes a different person. |
| INVALID_TARGET_REFERENCE | TITLE_AUTHOR_UNLINKED_COOCCURRENCE | Title expression and author occur without a semantic target linkage. |
| INVALID_TARGET_REFERENCE | WRONG_WORK_SAME_AUTHOR | A distinct work by the same author is identified. |
| INVALID_TARGET_REFERENCE | ALIAS_NOT_TARGET_EQUIVALENT | Retrieval alias is established not to denote underlying W. |
| INVALID_TARGET_REFERENCE | METADATA_TEXT_ARTIFACT | A text/metadata artifact causes false attribution. |
| INVALID_TARGET_REFERENCE | OTHER | Established invalidity outside the listed causes; explain in reviewer_note. |
| UNCERTAIN | INSUFFICIENT_CONTEXT | Information is inadequate without an established specific competing identity. |
| UNCERTAIN | AMBIGUOUS_TARGET_REFERENCE | Specific competing work identities remain unresolved. |

Precedence:

- `GENERIC_OR_LEXICAL_TITLE_USE` before generic/unlinked co-occurrence.
- `WRONG_WORK_SAME_AUTHOR` when a distinct work by the same author is identified;
  merely naming another work elsewhere does not suffice.
- `TITLE_AUTHOR_UNLINKED_COOCCURRENCE` when both occur but are not semantically
  linked after more specific causes are excluded.
- `METADATA_TEXT_ARTIFACT` only when an artifact causes false attribution; noisy
  text containing an explicit target reference is not invalid merely because it
  is noisy. Uninterpretable noise without established false attribution is uncertain.
- `AMBIGUOUS_TARGET_REFERENCE` when specific competing work identities remain.
- `INSUFFICIENT_CONTEXT` when information is inadequate but no specific competing
  identity can be established.

Where several valid reasons apply, prefer `VALID_TITLE_VARIANT` if supported
variant equivalence is the material identity issue; otherwise direct linkage uses
`DIRECT_TARGET_REFERENCE`, and indirect identifying context uses
`VALID_CONTEXTUAL_REFERENCE`. For multiple invalid causes not resolved by the
precedence above, select the most directly evidenced cause and explain alternatives
in reviewer_note. Do not invent additional authoritative codes during review.

## Confidence

- `HIGH`: clear support; no material competing interpretation.
- `MEDIUM`: sufficiently supported with bounded non-dispositive qualification.
- `LOW`: chosen judgment only tentatively clears protocol threshold.

Confidence applies to the chosen judgment, including `UNCERTAIN`; it is not
P(reference is valid). A high-confidence uncertain judgment can reflect clear
support for unresolved ambiguity, without choosing a work identity. Unresolved
material competing identity should normally produce `UNCERTAIN` rather than merely
LOW confidence in VALID or INVALID. Missing abstract alone does not lower confidence.
Provenance multiplicity never raises confidence by itself.

## Evidence provenance

Separate substantive evidence use from field visibility:

- `evidence_used_oa_title`
- `evidence_used_oa_abstract`
- `evidence_used_project_provenance`
- `evidence_used_external_check`

Each is a boolean, TRUE only if it substantively contributed to the decision,
not merely because visible. OA title means the record's `display_name`, not a
retrieval query title. Project provenance records supplied work identity/alias/author
context when substantively used to map OA evidence to W. Multiple flags may be TRUE.

`external_check_reference` and `external_check_note` must both be nonblank if
`evidence_used_external_check` is true. Record a resolvable citation/URL or artifact
reference and the finding's contribution. They must be blank when the flag is false.
An uncertain judgment based on missing evidence need not assert any evidence-used
flag without a substantive contribution. Reviewer notes must not copy long texts.

LLM evidence, if produced later, must have a separate versioned artifact with
model/prompt/input provenance and explicitly provisional suggestion fields. It must
not share authoritative judgment columns as if it were final adjudication, be copied
into the final table automatically, or be treated as human adjudication. The earlier
24-case provisional LLM judgments are not repository data in this release.

## Semantic review groups

The analysis-aid key is exactly:

```text
(increment_type, project_work_id, title_match_norms,
 author_a1_norms, author_a2_reverse_norms)
```

`review_semantic_group_id` is `OAPRSG1_` plus the first 16 lowercase hexadecimal
characters of SHA256 over canonical JSON UTF-8 bytes. Serialization uses a JSON
**object** with the five named fields and exact source string values, including
empty strings: Python `json.dumps(obj, ensure_ascii=False, sort_keys=True,
separators=(',', ':'), allow_nan=False)`. No extra normalization, array sorting,
provenance IDs or delimiter splitting is applied. Key order in the object is
lexicographic from `sort_keys=True`; digest-prefix collisions are explicitly rejected.

`r3_query_ids`, `r3_execution_ids`, `r3_alias_ids`, `r3_evidence_rows` are attached
provenance, not key fields or independent corroboration. A semantic group is not W
and is not a judgment unit; do not propagate one candidate judgment to all members.
The current release's 65 groups and K_RAW/K_NORMALIZED partition equivalence are
release-specific audit findings, not ontological rules.

## Review view v1 and development inputs

Frozen source: `derived/openalex_production/retrieval_precision_review_candidates_v3/`
`full_profile_57959e90/openalex_retrieval_precision_review_candidates_v3.tsv`.
SHA256: `38dda4e170ff8f1f90101f0246edc627401666f24dac5d588336f429194483fa`.

The builder uses stdlib `csv.DictReader(delimiter='\t', strict=True)` and opens
with `newline=''` to preserve quoted fields and embedded abstract newlines. All 33
source columns, order, values and blank cells are preserved; eight aids are appended:

| Aid | Deterministic definition |
|---|---|
| review_semantic_group_id | Digest of the exact semantic key above. |
| title_token_count | Whitespace token count of the single normalized title evidence string. |
| title_token_bucket | `1`, `2`, or `3+`. |
| hit_location | Source booleans yield TITLE_ONLY, ABSTRACT_ONLY, TITLE_AND_ABSTRACT or NEITHER. |
| abstract_available | Abstract contains at least one non-whitespace character. |
| provenance_multiplicity | SINGLE for one evidence row; MULTIPLE for more than one. |
| semantic_group_candidate_count | Candidate count in that semantic group. |
| semantic_group_volume_bucket | SMALL: 1–2; MEDIUM: 3–20; LARGE: >20. |

Multi-title normalized predicates are rejected rather than assigned an undocumented
scalar token count. This release has none. The review view contains no judgments.
Parquet stores all 41 cells as UTF-8 strings, including derived scalar lexemes;
this deliberately preserves original year spellings and blanks with exact TSV
cell parity. `True`/`False` aid lexemes represent booleans, not nulls. An authoritative
judgment table has native boolean semantics as specified separately below.

The versioned development-input TSV is a byte-exact copy of the existing 24-case
input set, SHA256 `0040da4263e8e5fcc26e44bab0471f0cf2575e34ded628d5ee2736fba2888b30`.
Its original 32 fields and selected order are retained; it includes no judgments.
Semantic group IDs are available by joining the review view on review_candidate_id.
There are 12 cases per mechanism, 8 alias W and 9 A2 W, with a maximum of two cases
per W and two A2 In Parenthesis cases. **Protocol-development use only; not a
statistical sample; not gold/holdout data; not used for precision estimation.**

Selection was deterministic and did not inspect semantic correctness: separately by
mechanism, maximize newly covered title-token, hit-location, abstract-availability,
provenance-multiplicity and group-volume categories plus a new-W indicator; then
prefer a new W; then ascending SHA256 of
`openalex_precision_review_development_v0|` + review_candidate_id. Once all available
categories and at least 8 W are covered, fill by hash order subject to max 2/W.
The preserved input artifact is the selected record; rebuilding the review view
validates its fields against source-derived values, not the selection itself.

Reproduction using an existing environment with PyArrow (no package installation):

```bash
/home/haruka221/canon-pipeline/.venv/bin/python scripts/build_openalex_precision_review_view_v1.py
```

The builder refuses an existing output directory. To verify replay, pass a new
`--output-dir /tmp/<new-directory>`. TSV and Parquet bytes are deterministic with
fixed builder/dependency/runtime versions. Manifest/audit capture build Git state,
so provenance JSON may change between unstaged and later committed executions.
Manifests bind source, protocol, schema, builder and development-input hashes.
Audit hashes are recorded externally rather than cyclically inside the manifest;
the audit binds the manifest and each data output.

## Authoritative judgment schema v1

Machine-readable contract:
`derived/openalex_production/precision_review_protocol_v1/`
`openalex_precision_review_judgment_schema_v1.json`.
It specifies a JSON array representing the eventual table's 18 columns, JSON-native
booleans and per-row conditional reason/external-check constraints. TSV transports
booleans as `True`/`False`, strings as UTF-8 and missing optional text as empty strings.
No authoritative table is populated now, including no empty 661-row template.

The final release must pass all of these invariants:

- exactly 661 rows and 661 unique review_candidate_id;
- exact candidate-ID set equality with frozen candidate v3;
- exact `(project_work_id, openalex_work_id)` pair equality, including each ID's mapping;
- exact increment type and recomputed semantic-group ID for each candidate;
- controlled vocabulary and reason-code/primary-judgment compatibility;
- review_protocol_version fixed to `v1`;
- external_check_reference/note required if external evidence was used;
- nonblank reviewer_id, UTC adjudicated_at_utc, and a reviewer note for OTHER.

The schema carries cross-table constraints as documented metadata; these require
an executable candidate join, not JSON Schema alone. The companion
`scripts/validate_openalex_precision_review_judgments_v1.py` validates eventual
TSV data against the frozen universe without writing files. Its example syntax:

```bash
python3 scripts/validate_openalex_precision_review_judgments_v1.py /path/to/final_judgments_v1.tsv
```

### Structural schema and authoritative release gate

JSON Schema defines structural and controlled-vocabulary validity: the property
set, required values, controlled vocabularies, cross-field conditional constraints,
and timestamp lexical shape. It is not sufficient for final-release acceptance.

Every final/frozen v1 judgment artifact MUST additionally pass
`scripts/validate_openalex_precision_review_judgments_v1.py`.
That Python validator is the authoritative release gate. Schema-only success MUST
NOT be reported as successful final-release validation or justify calling a judgment
release valid or frozen.

Timestamp transport is UTC ISO-8601 with literal Z:
`YYYY-MM-DDTHH:MM:SS[.fraction]Z`. The schema checks lexical shape and component
ranges (month 01–12, day 01–31, hour 00–23, minute/second 00–59). It intentionally
omits `format: date-time` and does not encode leap-year or month-day validity.
The authoritative validator checks Gregorian calendar validity with
`datetime.fromisoformat` and verifies UTC. For example, structurally shaped
`2026-02-30T00:00:00Z` is rejected by the validator; `2028-02-29T00:00:00Z` is accepted.

No production judgments, precision estimates, scope policies or visibility totals
are created by the protocol implementation or review-view audit.
