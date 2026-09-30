# OpenAlex Scholarly Visibility Matching Method

**Status:** Registry v3 and retrieval-calibration sample v1 frozen; 901-file partial-snapshot profile v1 retained for calibration; OpenAlex 2026-09-23 Works snapshot manifest-verified complete; scanner compatibility smoke test passed; profile v2 runner frozen; complete profile v2 scan pending
**Date:** 2026-09-30
**Current identity baseline:** `project_works_v4`
**Repository:** `haruka0221/canon-pipeline`

## Snapshot checkpoint — 2026-09-30

A replacement OpenAlex Works snapshot was acquired independently from the
official 2026-09-23 release and verified against its own manifest before any
new full-profile execution.

Verified snapshot:

```text
release date                         2026-09-23
entity                               works
format                               jsonl
manifest files                       2,040
verified files                       2,040
missing files                            0
unexpected files                         0
size mismatches                          0
temporary .aria2 files                   0
compressed bytes               659,026,072,445
record count                   476,196,327
updated_date min                     2016-06-24
updated_date max                     2026-09-23
```

Official manifest SHA256:

```text
441a4d047be6e5f21146c30525c3a6fee6a820b171f7fd6b6f0c069cdad9d05e
```

Path-plus-size inventory SHA256:

```text
57959e90573d6ef2adb953fd747ba71854819880f762077f680083476d490fc9
```

The inventory hash is defined as SHA256 over UTF-8 lines sorted by relative
path, with each line encoded as:

```text
<relative_path>\t<byte_size>\n
```

It is an inventory-provenance hash rather than a content checksum.

This snapshot supersedes the incomplete 901-file inventory as the intended
input for the next complete calibration profile, but it does not alter or
overwrite profile v1. The historical profile v1 remains reproducible for its
own partial input snapshot.

The upstream manifest does not provide per-file cryptographic checksums.
Accordingly, manifest completeness verifies path presence and byte length;
gzip and JSONL readability remain separate execution-time checks and must be
exercised by the compatibility smoke test and full profile scan.

Provenance artifacts:

```text
derived/openalex_production/snapshot_provenance_release_20260923_v1/
```

The next execution sequence is:

```text
manifest-verified snapshot
    ->
scanner compatibility smoke test
    ->
complete calibration profile v2
    ->
profile audit
    ->
retrieval-policy evaluation
```

### Scanner compatibility smoke test

Before constructing the complete profile-v2 run, the existing profile-v1
scanner was exercised without changing its matching semantics against five
evenly spaced files from the verified 2026-09-23 snapshot.

Selected files:

```text
updated_date=2016-06-24/part_0000.gz
updated_date=2026-02-09/part_0016.gz
updated_date=2026-08-13/part_0012.gz
updated_date=2026-09-02/part_0035.gz
updated_date=2026-09-23/part_0049.gz
```

The test read 902,053 OpenAlex records. Strict independent re-reading of the
same files found zero UTF-8 errors, zero JSON errors, zero missing OpenAlex
IDs, and zero non-dictionary `abstract_inverted_index` values.

The scanner produced 11,008 logical-query rows, 2,858 title-pattern rows,
246 A1/A2 candidate-query evidence rows, and 61 candidate OpenAlex metadata
rows. Audit checks found no duplicate `(query_id, openalex_work_id)` evidence
keys, no duplicate OpenAlex metadata IDs, no evidence IDs missing metadata,
and the summed query-level A2 count equaled the 246 materialized evidence
rows.

This establishes compatibility of the existing matching implementation with
the 2026-09-23 snapshot. It does not itself constitute the complete profile.

### Complete-profile v2 runner

The profile-v2 runner preserves the profile-v1 matching contract:

```text
openalex_snapshot_title_abstract_token_phrase_v1
```

The core normalization, abstract reconstruction, automaton construction,
pattern matching, and A1/A2/A3 semantics are intentionally unchanged.

Profile v2 instead strengthens execution provenance and snapshot guards. It
requires the frozen 2026-09-23 snapshot characteristics:

```text
files                         2,040
compressed bytes        659,026,072,445
record count            476,196,327
inventory SHA256
57959e90573d6ef2adb953fd747ba71854819880f762077f680083476d490fc9
official manifest SHA256
441a4d047be6e5f21146c30525c3a6fee6a820b171f7fd6b6f0c069cdad9d05e
```

A complete run fails if the observed snapshot contract differs, if a JSON
parse error occurs, or if the complete row count differs from the official
manifest record count.

The v2 manifest additionally records runtime package versions and Git state.
All outputs use separate `*_v2` names; profile-v1 artifacts remain frozen and
unchanged.

**Branch:** `kakenc-integration-20260927`
**Baseline commit at drafting:** `a5c9165` (`Add project works v4`)

## 1. Purpose

This document defines the project architecture for retrieving, attributing, and classifying OpenAlex scholarly records as evidence of scholarly visibility for literary works.

The OpenAlex workflow builds on the project-native identity and aggregation layer established before OpenAlex production.

The current identity checkpoint is:

```text
Open Library current targets                  34,789
│
├── assigned to project conceptual works      32,706
│     └── project conceptual works (W)         32,086
│
└── intentionally unresolved                   2,083
      └── unresolved aggregation units            761
```

For the current OpenAlex matching and calibration stage:

- the 32,086 released project works in `project_works_v4` form the primary W-level matching population;
- the 761 unresolved aggregation units / 2,083 current Open Library targets are processed separately in an unresolved lane;
- this identity-stage population is **not** the same as the future final period/scope population;
- OpenAlex matching must not itself determine final corpus scope.

The main objective is to measure scholarly visibility without collapsing source identity, retrieval, relevance judgment, and analytical aggregation into a single operation.

---

## 2. Fundamental entity distinction

The project uses the term **project work** for the conceptual literary-work entity identified by a project-native `W...` identifier.

Example:

```text
W000012345
```

An OpenAlex `Work`, by contrast, is an OpenAlex scholarly record representing an article, chapter, book, conference contribution, or other scholarly/documentary object.

These are different kinds of entities.

```text
Project W
    = conceptual literary work

OpenAlex Work
    = scholarly/document record
```

Therefore, the OpenAlex workflow is **not** another Goodreads/Wikidata-style work identity-resolution layer.

The following must never be implied:

```text
OpenAlex Work SAME_AS project W
```

Instead, the relevant relationship is:

```text
OpenAlex scholarly Work
          │
          │ scholarly reference /
          │ discussion / analysis
          ▼
project conceptual literary W
```

This distinction must be preserved in column names, decision vocabularies, documentation, and downstream aggregation.

---

## 3. Relationship to the project identity model

The OpenAlex workflow inherits, but does not redefine, the existing project identity layer.

Current identity artifacts include:

```text
derived/identity/project_works_v4.parquet
derived/identity/project_works_v4.tsv

derived/identity/work_identity_map_v4.parquet
derived/identity/work_identity_map_v4.tsv

derived/identity/aggregation_decisions_v4.parquet
derived/identity/aggregation_decisions_v4.tsv
```

The project master literary-work identifier is:

```text
project_work_id = W...
```

External identifiers remain source identifiers.

Examples:

```text
Open Library Work ID
Goodreads Work ID
Wikidata QID
OpenAlex Work ID
```

None of these replaces the project `W` identifier.

OpenAlex evidence must not silently alter `W` membership. If OpenAlex evidence later suggests an identity problem, that evidence may trigger a separate identity-review process, but it must not modify the identity layer implicitly.

---

## 4. Identity, scope, retrieval, attribution, and visibility are separate decisions

The pipeline distinguishes at least five logically different questions.

### 4.1 Project identity

```text
Which source entities belong to the same project conceptual literary work W?
```

This is handled by the identity / aggregation layer.

### 4.2 Project scope

```text
Does the conceptual literary work belong in the final analytical population?
```

This is a separate future scope-resolution layer.

### 4.3 OpenAlex retrieval

```text
Which OpenAlex scholarly records should be retrieved as candidates for a target W?
```

This is handled through versioned query routes and aliases.

### 4.4 Target attribution

```text
Does this OpenAlex scholarly record genuinely refer to the target literary W?
```

This is not identity resolution.

### 4.5 Mention strength / visibility contribution

```text
If attributed to W, does the record substantively analyze W,
briefly mention it, or otherwise contribute to the chosen
scholarly-visibility measure?
```

These decisions must remain separately reproducible.

---

## 5. Definition of target attribution

The principal W-level relevance field is:

```text
target_attribution_decision
```

The value:

```text
ATTRIBUTED
```

means:

> The OpenAlex scholarly work is judged, on the available scholarly-record evidence, to genuinely refer to, discuss, analyze, compare, or otherwise make a scholarly reference to the target project conceptual literary work (`W`).

It does **not** mean that the OpenAlex Work and project `W` are the same entity.

Formally:

```text
ATTRIBUTED != SAME
```

The Goodreads/Wikidata identity vocabulary such as:

```text
SAME
DIFFERENT
AMBIGUOUS
UNRESOLVED
```

must therefore not be reused as the main OpenAlex scholarly-attribution vocabulary.

---

## 6. Current OpenAlex architecture

The v3 design separates target evidence, query provenance, physical query execution, raw hits, candidate aggregation, and visibility judgment.

```text
project W / unresolved OL source target
                │
                ▼
      alias / target registry
                │
                ▼
          query registry
                │
                ▼
      query execution registry
                │
                ▼
     query_id × OpenAlex raw hits
                │
                ▼
 candidate-query evidence bridge
                │
                ▼
     W × OpenAlex Work candidate
                │
                ▼
 document scope / attribution / mention
                │
                ▼
      W-level visibility summary
```

The layers must not be collapsed merely for storage convenience.

---

## 7. Resolved and unresolved target lanes

### 7.1 Resolved W lane

The current W-level OpenAlex calibration population is:

```text
project_works_v4
32,086 project works
```

A resolved target has:

```text
target_lane = resolved_w
project_work_id = W...
```

All retrieval aliases associated with source entities belonging to the project W may be retained as evidence.

### 7.2 Unresolved identity lane

The remaining:

```text
761 unresolved aggregation units
2,083 current Open Library targets
```

must not be forced into `W` entities before OpenAlex retrieval.

These targets are processed in a parallel lane:

```text
target_lane = unresolved_source
project_work_id = NULL
```

The unresolved lane exists to preserve potentially useful OpenAlex candidates during the same scan without prematurely resolving literary-work identity.

OpenAlex evidence from this lane:

- is preserved;
- may later support identity review;
- may later be reassigned after a future project-work release;
- does not contribute to current W-level scholarly visibility.

The status of an unresolved target must never be interpreted as zero visibility.

---

## 8. Alias model

Source-level aliases are retrieval evidence. They are not all assumed to be equally authoritative.

For every retrieval alias, preserve provenance such as:

```text
alias_id
alias_project_source_entity_id
alias_source
alias_source_namespace
alias_source_record_id

alias_domain
alias_value_raw
alias_value_norm

alias_role
alias_quality
alias_quality_reason
alias_provenance

membership_role
membership_basis
```

For project source entities, use the project `E...` identifier explicitly:

```text
alias_project_source_entity_id = E000...
```

Do not overload this field with source-native identifiers such as:

```text
/works/OL...
Q...
```

Instead preserve source-native identifiers separately:

```text
alias_source_record_id
```

### 8.1 Alias quality

The first v3 implementation should prefer categorical quality states over pseudo-precise numerical scores.

Initial vocabulary:

```text
preferred
usable
restricted
exclude
```

A quality category must be accompanied by an explicit rule or reason.

### 8.2 Alias provenance must survive deduplication

Even when multiple aliases generate an identical normalized query, the alias-level provenance must not be discarded.

---

## 9. Representative retrieval title is not a project canonical title

The current project identity release does not establish one definitive project-level canonical title for every `W`.

Therefore R2 must not describe its selected title simply as the canonical title.

Instead, the selected title is a retrieval-specific representative alias.

Preserve fields such as:

```text
representative_for_r2
representative_alias_id
representative_selection_rule
representative_selection_version
```

The semantics are:

> This alias was selected by a documented retrieval rule as the representative title for this OpenAlex query route.

They are **not**:

> This is the definitive title of the conceptual literary work.

Representative-title selection must therefore be reproducible and versioned.

---

## 10. Author evidence

Author identity evidence and the query author string must remain distinct.

The intended evidence model is:

```text
Open Library Work
        │
        ▼
Work → Author source-native edge
        │
        ▼
Open Library Author source entity
        │
        ▼
source-native author-name evidence
        │
        ▼
explicit query-author selection rule
        │
        ▼
query_author_name
```

The query author name is therefore a **derived retrieval value**, not a replacement for the underlying source-native evidence.

### 10.1 Required author provenance

The v3 registry should be able to preserve fields such as:

```text
author_source
author_source_namespace
author_source_id
author_ordinal

author_name_type
author_name_raw
author_name_source_artifact
author_name_source_snapshot

query_author_name
query_author_norm
query_author_role
query_author_selection_rule
query_author_selection_version
```

### 10.2 Multiple authors

Multiple source-native author relationships must not be silently collapsed to the first author merely because an earlier workflow used a single `author_name` column.

The source relationship and `author_ordinal` should remain recoverable.

The retrieval policy may choose a primary query author, but that choice must be represented as a retrieval rule rather than as source truth.

### 10.3 Frozen Open Library author source layer

The source-native Open Library author layer was frozen on 2026-09-28 as:

```text
release:
openlibrary-author-source-v1

artifact directory:
derived/openlibrary_author_source_v1/

freeze commit:
16d0a29
```

The release is built from the 34,789 current Open Library analysis targets.
It does **not** inherit historical population `author_keys` or `author_name`
values as source truth. Instead, current target IDs are looked up directly
in the fixed 2026-02-28 Open Library Works dump, all source-native
`Work.authors` entries and their ordinals are preserved, and referenced
Author records are then extracted from the fixed 2026-02-28 Authors dump.

The release contains:

```text
current targets                       34,789
Work → Author edges                    37,652
unique referenced Author IDs           16,405
Author records found                   16,402
Author records missing                      3
author-name evidence rows              57,510
targets with no author entries            354
targets with >1 author entry             1,730
```

All 16,402 resolved Author records contain a non-empty `name`.
`personal_name` is present for 14,277 records and `fuller_name` for 82.

Three Work-side Author references have no corresponding Author record in
either the fixed 2026-02-28 Authors dump or the separately preserved later
September 2026 Authors dump. They remain explicit unresolved source
references and are not manually repaired in the source layer.

The audit also shows that Open Library `Work.authors` cannot be interpreted
as a guaranteed list of original literary authors. The current Open Library
record for *The Prisoner of Zenda*, for example, contains 16 author edges:
Anthony Hope is ordinal 0, alongside 15 additional person or organization
records. Therefore all source-native relationships are preserved, while a
retrieval-specific author must be selected separately.

The project-wide Open Library-derived query-author selection rule was
subsequently calibrated and frozen on 2026-09-29 as described below.

### 10.4 Frozen Open Library query-author selection v1

The first production query-author selection release is:

```text
release:
openlibrary-query-author-selection-v1

artifact directory:
derived/openlibrary_query_author_selection_v1/

freeze commit:
3c00110
```

The release was derived from the frozen author-source layer, the query-author
audit, and a stratified manual review of the 1,730 targets with more than one
Open Library `Work.authors` entry.

The MULTI population was divided into heuristic review buckets. The heuristics
were used only to stratify review risk; they are not treated as source truth.
The human-review sample contained 155 targets:

```text
MULTI_BASELINE     50 random
MULTI_LOW          50 random
MULTI_MEDIUM       50 random
MULTI_HIGH          5 all
total             155
```

The review question was whether Open Library author ordinal 0 was safe and
useful as an OpenAlex title+author retrieval disambiguator for the target.
This was explicitly a retrieval decision, not a definitive
literary-historical authorship judgment.

Final human-review results were:

```text
ordinal0_retrieval_safe

YES    145
NO      10
```

By review bucket:

```text
MULTI_BASELINE   50 / 50 YES
MULTI_LOW        48 / 50 YES
MULTI_MEDIUM     47 / 50 YES
MULTI_HIGH        0 /  5 YES
```

Recommended review actions were:

```text
USE_ORDINAL0               123
USE_MULTIPLE_OL_AUTHORS     22
USE_OTHER_ORDINAL            4
NO_OL_AUTHOR                 6
```

The resulting project-wide primary selection rule covers all 34,789 current
Open Library analysis targets:

```text
USE_ORDINAL0         34,424
USE_OTHER_ORDINAL         4
NO_OL_AUTHOR            361
```

The selection basis is preserved explicitly:

```text
AUTO_SINGLE_RESOLVED               32,704
AUTO_MULTI_ORDINAL0_CALIBRATED      1,575
NO_AUTHOR_ENTRY                        354
HUMAN_REVIEW_CONFIRMED_ORDINAL0       145
HUMAN_REVIEW_NO_OL_AUTHOR                6
HUMAN_REVIEW_OVERRIDE                    4
SINGLE_UNRESOLVED                         1
```

For unreviewed MULTI targets, ordinal 0 is used only in the
`MULTI_BASELINE`, `MULTI_LOW`, and `MULTI_MEDIUM` buckets under the
explicit basis `AUTO_MULTI_ORDINAL0_CALIBRATED`. All five
`MULTI_HIGH` targets were reviewed manually.

The raw selected query-author string is the frozen Open Library
`Author.name`. `personal_name`, `fuller_name`, and
`alternate_names` are not substituted in selection v1.

Twenty-two reviewed targets had more than one Open Library author judged useful
for retrieval. Those additional names are retained as calibration evidence
with:

```text
CALIBRATION_EVIDENCE_NOT_AUTOMATIC_PRODUCTION_ROUTE
```

They are not automatically enabled as production query routes, because doing so
only for sampled targets would make retrieval conditions uneven across the
population. They may inform a later uniformly defined R3 author-expansion rule.

The selected query author remains a derived retrieval value. It does not
overwrite the source-native `Work.authors` evidence and must not be presented
as the definitive literary-historical author record.

---

## 11. Query registry

Every logical retrieval query receives a stable `query_id`.

Example:

```text
OAQ000000001
```

A logical query records not only the query string but also why it exists.

Core fields should include:

```text
query_id

target_lane
project_work_id
unresolved_unit_anchor_entity_id

alias_id
alias_project_source_entity_id
alias_source_record_id

query_route
query_form

query_title
query_author

normalized_title
normalized_author

normalized_query_signature
normalization_version

query_registry_version
```

Additional route-specific provenance may be added where required.

---

## 12. Query ID and normalized query signature have different functions

These two identifiers must not be conflated.

```text
query_id
    = provenance-bearing logical query

normalized_query_signature
    = execution-level deduplication key
```

For example:

```text
OAQ000001   W1   R2   alias A   "Ulysses" + "James Joyce"
OAQ000837   W1   R3   alias A   "Ulysses" + "James Joyce"
```

may share one normalized query signature.

Likewise, two different project works may occasionally generate the same normalized retrieval string.

Physical execution may therefore be deduplicated for efficiency, but each logical query remains separately recorded.

The following information must survive execution deduplication:

```text
target
alias
route
query_id
```

---

## 13. Query execution layer

Physical OpenAlex retrieval should be represented separately from logical queries where useful.

A query-execution artifact may contain:

```text
normalized_query_signature
normalization_version

openalex_snapshot
retrieval_source
retrieval_version

execution_status
execution_timestamp

dump_shard
api_parameters
```

where applicable.

Multiple logical `query_id` values may map to one execution signature.

This separation permits efficient full-dump scanning without losing methodological provenance.

### 13.1 Frozen v3 execution-registry implementation

The first v3 execution-registry implementation uses:

```text
normalization rule:
openalex_execution_query_norm_v1
```

with the following conservative operations:

```text
Unicode NFKC
Unicode casefold
collapse consecutive whitespace
strip leading/trailing whitespace
```

The rule intentionally does not apply:

```text
punctuation deletion
apostrophe deletion
hyphen or dash deletion
dash canonicalization
leading-article deletion
diacritic stripping
ASCII transliteration
non-Latin character deletion
```

Calibration compared this rule with both raw exact strings and more aggressive
alternatives. A punctuation-spacing variant would reduce the execution count
by only four additional signatures, while the historical ASCII-oriented
normalization can destroy non-Latin title evidence. The conservative rule was
therefore selected for v1.

The current logical registry contains:

```text
logical queries                    101,710

R2                                  32,493
R3                                  34,428
R4                                  34,789
```

By target lane:

```text
                         R2       R3       R4
resolved_w            31,734   32,354   32,706
unresolved_source        759    2,074    2,083
```

R2 is an identity-anchor retrieval baseline, not a canonical-title or
best-title judgment. R3 uses the frozen primary query author belonging to each
Open Library alias's own source target. Human-reviewed additional authors
remain calibration evidence only. R4 rows remain calibration candidates and
do not imply that all title-only queries will be executed in the final
production policy.

Under `openalex_execution_query_norm_v1`, the logical registry maps to:

```text
physical execution signatures       63,624
title_author                         32,237
title_only                           31,387
logical rows saved by dedup          38,086
```

The physical layer is represented separately through:

```text
openalex_query_execution_map_v3
    query_id -> execution_id / normalized_query_signature

openalex_query_executions_v3
    one row per normalized physical execution signature
```

The current registry contains 2,474 signatures shared by more than one
resolved W and 3 shared by more than one unresolved aggregation unit. Such
collisions are expected and do not imply identity. The largest observed
fan-out is the generic title-only query `Short stories`, shared by 37 resolved
W entities.

The stable semantic execution key is `normalized_query_signature`, computed
from query form, normalized title, and normalized author. Sequential
`execution_id` values are release-local identifiers. All target, alias, route,
and `query_id` provenance remains in the query-to-execution mapping.

---

## 13.2 Frozen retrieval-calibration sample v1

The first fixed population for comparing R2/R3/R4 retrieval behavior is:

```text
release:
openalex-retrieval-calibration-sample-v1

artifact directory:
derived/openalex_production/retrieval_calibration_sample_v1/
```

The sample was frozen before retrieval-policy evaluation so that route or
matching choices are not tuned by repeatedly changing the target population.

Its target population is:

```text
resolved project W                    1,852
unresolved aggregation units           761
target units total                    2,613
```

All logical R2/R3/R4 queries associated with these target units are retained:

```text
logical queries                      11,008
unique physical execution IDs        5,785

R2                                   2,259
R3                                   4,194
R4                                   4,555
```

By target lane:

```text
                         R2       R3       R4
resolved_w             1,500    2,120    2,472
unresolved_source        759    2,074    2,083
```

The resolved-W population is the union of the following predefined cohorts:

```text
baseline_random                  300
multi_alias_all                  547
r2_missing_all                   352
high_r4_collision_all            336
a2_sensitive_random              150
one_token_title_random           100
two_token_title_random           100
```

The exhaustive cohorts retain all qualifying W. Random cohorts are selected
by deterministic SHA256 ranking using:

```text
seed
+ ASCII Unit Separator
+ cohort name
+ ASCII Unit Separator
+ project_work_id
```

with seed:

```text
20260929
```

This avoids dependence on pandas or NumPy random-number implementation
details.

The cohort semantics are:

- `baseline_random`: general resolved-W baseline;
- `multi_alias_all`: every resolved W having more than one current Open
  Library title alias, used especially to measure the incremental effect of
  R3 over R2;
- `r2_missing_all`: every resolved W lacking an R2 title-author query,
  important for rescue-route evaluation;
- `high_r4_collision_all`: every resolved W having at least one R4 execution
  string shared by four or more resolved W;
- `a2_sensitive_random`: a stable sample whose query-author evidence includes
  a simple surname-first comma form suitable for conservative author-order
  reversal testing;
- `one_token_title_random` and `two_token_title_random`: stable samples for
  high-risk short-title calibration.

The union contains more members with a given feature than the nominal random
cohort size when those W enter through another cohort. For example,
`a2_sensitive` feature coverage in the final union is 222 W even though the
dedicated A2-sensitive random cohort contains 150 W.

All 761 unresolved units are retained in parallel for retrieval diagnostics.
They are not W entities and cannot contribute directly to current W-level
visibility.

Freezing this sample does not freeze:

```text
title / abstract matching normalization
A1 author matching
A2 author-order variants
A3 surname-only matching
R2 / R3 / R4 production eligibility
R4 operational thresholds
final visibility judgment policy
```

Those decisions are evaluated against this fixed calibration population.

---

## 13.3 Full retrieval-calibration profile v1

The fixed calibration population was scanned against one fixed OpenAlex
snapshot inventory after the profile implementation passed exact parity
against the earlier five-file smoke scanner.

The snapshot is identified by inventory rather than by filesystem path:

```text
files                                  901
compressed bytes               182,243,772,809
inventory SHA256
4497f9cfc56c6d0495d5ae8c1b884d7efe78503fb90451bb8fd5f5aa6289087c

updated_date min                  2016-06-24
updated_date max                  2025-11-06
records read                     152,044,758
```

A later snapshot-completeness audit showed that the 901-file input
inventory was incomplete relative to the bundled upstream manifest. The
manifest describes 2,236 files, while 1,335 files totaling 443,649,290,060
compressed bytes were absent locally.

Therefore, profile v1 is interpreted as a complete scan of its frozen
901-file local input inventory, not as a complete scan of the upstream
OpenAlex snapshot. Its artifacts remain unchanged and reproducible, but they
are retained for calibration rather than as the final production baseline.

A new complete OpenAlex snapshot must be acquired and scanned independently;
files from a different snapshot release must not be mixed into the 901-file
inventory.

The completeness audit is stored under:

```text
derived/openalex_production/snapshot_provenance_v1/
```

The matching registry used for this run is stored under:

```text
derived/openalex_production/retrieval_match_registry_v1/
```

It maps the frozen 11,008 calibration logical queries to 2,858 normalized
title-match patterns and versioned A1/A2/A3 author-evidence fields.

The profile scanner searches the OpenAlex Work display title plus reconstructed
abstract under the frozen calibration token-phrase contract. This is a
project-defined reproducible snapshot retrieval contract; it is not asserted
to reproduce every field searched by the live OpenAlex API.

The full run records exact counts for every calibration title pattern and
logical query. Candidate-level rows are materialized only for A1/A2-qualified
title-author evidence. R4 title-only candidates are counted but are not
materialized before production eligibility is determined.

Full-profile counts are:

```text
title patterns                         2,858
logical queries                       11,008
OA records with any title hit     11,342,122
A1/A2 candidate-query rows            79,625
A1/A2 OA metadata rows                23,214
```

Integrity checks passed:

```text
title-match pattern IDs unique                         yes
query IDs unique                                       yes
duplicate (query_id, OpenAlex Work) evidence keys        0
duplicate OpenAlex metadata IDs                          0
evidence OpenAlex IDs missing metadata                   0
sum(query a2_hit_count) == evidence rows               yes
```

For resolved W, candidate-set comparisons are:

```text
                         candidates       W
R2 + A1                     11,239       407
R3 + A1                     11,386       429
R2 + A2                     11,329       423
R3 + A2                     11,472       443

R3+A1 minus R2+A1              147        31
R3+A2 minus R2+A2              143        29
R3+A2 minus R3+A1               86        17
```

These differences establish retrieval increment only. They do not establish
precision or accepted scholarly visibility. Candidate-level review remains
necessary before production routing is frozen.

A2-only evidence also exists in the resolved lane. Across query-level evidence,
194 resolved rows and 625 unresolved rows satisfy A2 but not A1. After
candidate aggregation, the resolved R3+A2 candidate set contains 86
`(project_work_id, openalex_work_id)` pairs not present in R3+A1, spanning
17 W.

A3 remains diagnostic. Its much larger hit counts relative to A1/A2 indicate
that surname-only matching cannot be treated as an automatically accepted
uniform production route on the basis of this calibration alone.

Title-only burden is highly concentrated in short titles:

```text
tokens    patterns    patterns with hit    total title hits
1              290                  284         12,974,198
2              576                  485            532,031
3              586                  463            114,877
4-5            852                  537             25,830
6-10           469                  201              5,211
11+             85                   23                 42
```

Accordingly, this milestone freezes the calibration observations and their
provenance, not a final production decision.

Still not frozen:

```text
R2 / R3 / R4 production routing
R4 title-only eligibility or burden thresholds
A3 surname-only production use
precision judgment for incremental R3 / A2 candidates
document scope
target attribution
mention strength
W-level scholarly-visibility aggregation
```

---

## 14. Raw hit layer

The raw retrieval layer must preserve one row per logical query / OpenAlex hit relationship where practical.

Conceptually:

```text
query_id
normalized_query_signature
openalex_work_id

retrieval_route
retrieval_match_evidence

openalex_snapshot
retrieval_source
retrieval_version
```

At this stage, duplicate hits across aliases or routes should not be silently discarded.

The raw hit layer exists to preserve how an OpenAlex candidate was retrieved.

---

## 15. Candidate aggregation

### 15.1 Resolved W candidate key

For resolved project works, the candidate-level analytical key is:

```text
(project_work_id, openalex_work_id)
```

If one OpenAlex record is retrieved through multiple aliases or routes for the same `W`, the final candidate layer contains one candidate row.

Example:

```text
W1 × OA123
    ← R2 / alias A
    ← R3 / alias A
    ← R3 / alias B
    ← R4 / alias C
```

The candidate row is deduplicated, but all contributing retrieval evidence is preserved through a bridge table or equivalent provenance structure.

Recommended bridge:

```text
openalex_candidate_query_evidence_v3

project_work_id
openalex_work_id
query_id
alias_id
alias_project_source_entity_id
query_route
```

Useful candidate-level summaries may include:

```text
matched_query_count
matched_alias_count
matched_route_count
```

These summaries must remain reproducible from the lower-level evidence table.

### 15.2 Unresolved candidate key

Unresolved units must not be prematurely collapsed to aggregation-unit level.

Until project identity is resolved, retain the source target explicitly.

A safe unresolved candidate basis is:

```text
(alias_project_source_entity_id, openalex_work_id)
```

with:

```text
project_work_id = NULL
unresolved_unit_anchor_entity_id = ...
```

If two unresolved Open Library source targets inside the same aggregation unit retrieve the same OpenAlex record, both source-level candidate relationships remain preserved.

They may be collapsed only after a later explicit identity / aggregation decision warrants doing so.

---

## 16. Cross-W collisions

An OpenAlex scholarly record may validly refer to multiple literary works.

Therefore:

```text
(W1, OA123)
(W2, OA123)
```

may both be valid candidates.

OpenAlex records must **not** be globally assigned to exactly one project literary work.

Cross-W collision is therefore an expected data state, not automatically an error.

Candidate artifacts should preserve or derive:

```text
cross_w_collision_flag
cross_w_collision_count
```

where analytically useful.

Collision rate may also be used as a diagnostic for overly broad query routes.

---

## 17. Retrieval routes

The existing OpenAlex retrieval experiments are retained conceptually, but adapted to the new `W`-based architecture.

### 17.1 R1 — historical / regression route

R1 preserves earlier Open Library-record-centered retrieval behavior for reproducibility and regression comparison.

R1 is not the primary new production architecture.

### 17.2 R2 — representative title + author

R2 uses:

```text
retrieval representative title
+
selected query author
```

for each resolved project `W`.

The representative title and query author must be selected through documented, versioned rules.

R2 must not imply that either string is the definitive project-level title or author representation.

### 17.3 R3 — verified aliases + author evidence

R3 expands retrieval using source aliases associated with the target W.

Multiple Open Library title records attached to one `W` may therefore improve retrieval recall.

Aliases must retain:

```text
source entity
source record
alias role
alias quality
provenance
```

They are not automatically treated as equally strong.

### 17.4 R4 — title-only rescue

R4 permits title-only retrieval where appropriate.

A high title frequency does not by itself make a literary target ineligible for retrieval.

Instead, title-only performance should be assessed using such diagnostics as:

```text
candidate burden
cross-W collision
generic-title collision
accepted-mention precision
review burden
incremental recall
```

Candidate retrieval count and accepted scholarly mention count must remain separate measurements.

R4 policy may vary by query characteristics, but retrieval eligibility must not be determined by Goodreads/Wikidata presence or other visibility-bearing external-source availability.

### 17.5 Future semantic rescue

Character names or work-specific terminology may later support a separate semantic-recall route.

Example:

```text
Heart of Darkness
Conrad
Kurtz
```

Such retrieval should be treated as an extension of scholarly mention detection, not as a mechanism that silently changes project-work identity.

It should therefore receive its own route and validation before production use.

---

## 18. Candidate burden is not scholarly visibility

The number of raw OpenAlex candidates generated by a query is not itself the final visibility count.

The pipeline must distinguish:

```text
retrieved candidate count
```

from:

```text
accepted scholarly attribution / mention count
```

A generic or ambiguous title may generate a large candidate pool but few accepted mentions.

Conversely, a restrictive title-author query may have high precision while missing valid scholarship.

Retrieval statistics are therefore diagnostics for retrieval design, not direct measures of literary visibility.

---

## 19. OpenAlex candidate judgment

The current conceptual decision structure should separate three judgments.

### 19.1 Document scope

```text
document_scope_decision
```

Initial vocabulary:

```text
ELIGIBLE_SECONDARY
INELIGIBLE_NON_SCHOLARLY
UNCLEAR
```

This determines whether the OpenAlex record qualifies as the type of scholarly secondary contribution relevant to the visibility measure.

### 19.2 Target attribution

```text
target_attribution_decision
```

Initial vocabulary:

```text
ATTRIBUTED
NOT_ATTRIBUTED
UNCLEAR
NOT_APPLICABLE
```

This determines whether the scholarly record genuinely refers to the target literary `W`.

Again:

```text
ATTRIBUTED != identity SAME
```

### 19.3 Mention strength

```text
mention_decision
```

Initial vocabulary:

```text
SUBSTANTIVE
MENTION
NONE
UNCLEAR
NOT_APPLICABLE
```

This distinguishes substantive analytical attention from genuine but limited scholarly mention.

---

## 20. Compatibility with historical visibility labels

Earlier OpenAlex classification used a combined label vocabulary:

```text
include_substantive
include_mention
exclude_non_scholarly
exclude_unrelated
unclear
```

For continuity, `visibility_label` may be retained as a derived compatibility field.

Conceptually:

```text
ELIGIBLE_SECONDARY
+ ATTRIBUTED
+ SUBSTANTIVE
    -> include_substantive
```

```text
ELIGIBLE_SECONDARY
+ ATTRIBUTED
+ MENTION
    -> include_mention
```

```text
INELIGIBLE_NON_SCHOLARLY
    -> exclude_non_scholarly
```

```text
ELIGIBLE_SECONDARY
+ NOT_ATTRIBUTED
    -> exclude_unrelated
```

Cases that cannot be safely mapped remain:

```text
unclear
```

The multi-axis decisions are primary. The combined historical label is derived.

---

## 21. Visibility zero, missingness, and unresolved identity

Zero scholarly visibility must be distinguished from unavailable or unresolved measurement.

Recommended W-level field:

```text
visibility_observation_status
```

Initial vocabulary:

```text
OBSERVED_POSITIVE
OBSERVED_ZERO
NOT_PROCESSED
PROCESSING_ERROR
```

### `OBSERVED_POSITIVE`

The W-level pipeline completed under the specified production policy and at least one accepted contribution was observed.

### `OBSERVED_ZERO`

The W-level pipeline completed under the specified production policy and no accepted contribution was observed.

### `NOT_PROCESSED`

The target has not completed the required production workflow.

### `PROCESSING_ERROR`

The intended workflow failed and the result cannot be interpreted as zero.

For the unresolved identity lane, use a separate state such as:

```text
UNRESOLVED_TARGET_IDENTITY
```

and do not assign W-level visibility values.

Therefore:

```text
unresolved identity != zero visibility
not processed        != zero visibility
retrieval failure    != zero visibility
```

---

## 22. Scope status must not be inferred from OpenAlex

The OpenAlex workflow must not infer corpus scope from scholarly-source presence or absence.

In particular:

```text
no OpenAlex candidate
no accepted OpenAlex mention
```

must not imply:

```text
out of scope
not a literary work
distinct project work
```

Likewise, OpenAlex visibility must not be used as an implicit inclusion criterion for the final literary population.

The current 32,086-W OpenAlex calibration population is an identity-stage working population.

Future final period/scope filtering remains a separate versioned analytical step.

---

## 23. Historical year evidence

The historical Open Library field:

```text
first_publish_year
```

must not be treated as a definitive original conceptual-work publication year.

Where retained for retrieval or diagnostics, its semantics should be represented as historical source evidence, approximately:

```text
ol_min_observed_edition_year
```

It may support:

```text
warning logic
candidate disambiguation
diagnostic analysis
```

but must not function as an unquestioned hard identity key.

Future year evidence should be drawn from the project year-evidence layer when available.

---

## 24. Production manifest

Every production OpenAlex release must freeze the relevant methodological dependencies.

At minimum the manifest should record:

```text
identity_release
identity_map_release
aggregation_decision_release

openalex_snapshot
openalex_snapshot_date_or_max_updated_date
retrieval_source
    dump / api

query_registry_version
normalization_version
retrieval_route_version

representative_selection_version
query_author_selection_version

candidate_aggregation_version
document_scope_decision_version
target_attribution_decision_version
mention_decision_version

scope_release
```

For the present identity-stage run:

```text
identity_release = project_works_v4
identity_map_release = work_identity_map_v4
aggregation_decision_release = aggregation_decisions_v4
scope_release = not_applied
```

The manifest should also preserve SHA256 values for major fixed input and output artifacts where practical.

---

## 25. Registry v2 migration policy

Historical OpenAlex registry v2 was constructed around the frozen 34,789 Open Library targets and a provisional OpenAlex-oriented conceptual grouping.

Registry v3 must not treat the old conceptual group as the project master identity.

The v3 master literary-work unit is:

```text
project_work_id
```

from the released project identity layer.

The v2 conceptual-group fields may be retained only as historical calibration / migration provenance where useful.

Recommended treatment:

| Registry v2 concept | Registry v3 treatment |
|---|---|
| Open Library `work_key` / target ID | source-target / alias provenance |
| raw and normalized title | alias registry |
| historical `first_publish_year` | historical year evidence |
| `canonical` | historical provenance only; not project canonical title |
| author keys | author source relationships |
| resolved/raw author name | historical retrieval provenance; rebuild production query author from versioned source evidence |
| Wikidata title / author evidence | corroborating retrieval evidence |
| legacy retrieval eligibility | historical calibration only |
| title-author production eligibility | recompute under v3 retrieval policy |
| title-only reviewability | recompute under v3 R4 policy |
| provisional conceptual group | historical only |
| title/author variant counts | derived from v3 alias/query registries where needed |

Registry v3 should be generated from the current project identity release rather than produced by renaming or directly mutating registry v2.

---

## 26. Required v3 artifacts

The exact file names may be adjusted during implementation, but the logical release should contain at least the following layers.

```text
derived/openalex_production/registry_v3/
    openalex_targets_v3.*
    openalex_aliases_v3.*
    openalex_queries_v3.*
    registry_manifest_v3.json
```

Retrieval output should preserve separate evidence layers, for example:

```text
openalex_query_executions_v3.*
openalex_query_hits_v3.*
openalex_candidate_query_evidence_v3.*
openalex_candidates_v3.*
```

Judgment output should preserve candidate-level decisions separately from W-level summaries.

---

## 27. Reproducibility requirements

A production result must be reproducible from:

```text
identity release
source evidence
alias-selection rules
representative-selection rules
author-selection rules
query registry
normalization logic
OpenAlex snapshot / retrieval source
candidate aggregation rules
judgment method
judgment version
```

No important transformation should rely solely on an undocumented in-memory choice.

Where a string is selected from several possible source values, the selected value and selection rule should both be recoverable.

---

## 28. Current decisions frozen by this design

The following design principles are adopted for registry v3 implementation:

1. `W` is the resolved literary-work analytical unit.
2. OpenAlex `Work` is a scholarly-document entity, not a literary-work identity entity.
3. OpenAlex relevance uses `target_attribution_decision`, not project identity vocabulary.
4. Retrieval aliases preserve source provenance and are not automatically equal in quality.
5. R2 representative title selection is a versioned retrieval decision, not project canonical-title assignment.
6. Query author selection is a versioned retrieval decision derived from source-native author evidence.
7. `query_id` represents logical query provenance.
8. `normalized_query_signature` represents execution-level deduplication.
9. Physical query deduplication must not destroy W / alias / route provenance.
10. Candidate deduplication for resolved works occurs at `(project_work_id, openalex_work_id)`.
11. One OpenAlex Work may remain a candidate for multiple project `W` entities.
12. Cross-W collisions are preserved.
13. R4 title frequency is a retrieval-burden / precision diagnostic, not a target-exclusion criterion by itself.
14. Retrieved candidate count and accepted scholarly mention count are different quantities.
15. The 761 unresolved units are processed in a parallel source-target lane with `project_work_id = NULL`.
16. Unresolved source targets do not contribute to current W-level visibility.
17. Unresolved identity is not equivalent to zero scholarly visibility.
18. OpenAlex absence does not determine project identity or final scope.
19. Production releases freeze identity, OpenAlex snapshot, query, normalization, aggregation, and judgment versions in a manifest.
20. Registry v3 is rebuilt from the project identity release rather than treating registry v2 conceptual groups as project identity.

---

## 29. Items intentionally not yet frozen

The following still require calibration or coverage audit before production
retrieval freeze. Query-author selection is no longer in this list:
`openlibrary-query-author-selection-v1` was frozen on 2026-09-29.

### 29.1 R2 representative-title selection

A deterministic R2 baseline has now been versioned as
`openalex-r2-representative-aliases-v1`.

For resolved W, it selects the alias corresponding to
`project_works_v4.origin_unit_anchor_entity_id`; for unresolved units, it
selects the unit-anchor alias. This is an identity-structural retrieval
baseline, not a best-title or canonical-title judgment.

Whether this baseline is retained unchanged in the final production retrieval
policy remains subject to R2/R3/R4 retrieval calibration. The historical
`canonical` flag is not treated as project-level title authority.

### 29.2 R4 operational routing policy

Candidate burden, collision, precision, and incremental recall should be evaluated before choosing the final route policy.

### 29.3 Semantic-recall route

Character names and work-specific terminology remain experimental until separately validated.

---

## 30. Immediate implementation sequence

Completed OpenAlex v3 preparation and registry milestones are:

1. author-source coverage audited for all 34,789 current Open Library targets;
2. `openlibrary-author-source-v1` frozen;
3. MULTI author-risk audit and 155-target stratified human review completed;
4. `openlibrary-query-author-selection-v1` frozen in commit `3c00110`;
5. W-based Open Library title alias registry v3 constructed;
6. deterministic R2 representative-alias baseline v1 constructed;
7. logical query registry v3 constructed with stable `query_id`;
8. `openalex_execution_query_norm_v1` calibrated and the query-to-execution
   registry constructed, reducing 101,710 logical queries to 63,624 physical
   execution signatures without collapsing logical provenance.

The next implementation steps are:

1. define and calibrate the snapshot scholarly-text matching contract against
   the frozen retrieval-calibration sample v1;
2. compare A1 full-name, A2 conservative author-order-variant, and
   experimental A3 surname-anchor evidence;
3. scan the fixed OpenAlex snapshot once for title / abstract retrieval
   evidence while retaining query-level provenance;
4. evaluate R2 / R3 / R4 candidate burden, cross-target collisions,
   incremental recall, precision, and review burden;
5. determine whether any uniform author expansion beyond the frozen primary
   query author is warranted;
6. freeze the production retrieval-routing policy, including R4 eligibility;
7. perform the full OpenAlex production scan under the frozen policy;
8. preserve query-hit and candidate-query evidence separately;
9. adjudicate document scope, target attribution, and mention strength;
10. aggregate accepted evidence to W-level scholarly visibility;
11. keep unresolved source-target results separate until a later identity release.

---

## 31. Current baseline

At the time this design document was drafted, the current identity release is:

```text
project_works_v4
```

with:

```text
project works                         32,086
current OL targets assigned to W      32,706
current OL targets unresolved          2,083
unresolved aggregation units             761
highest project work ID          W000032086
```

The remaining unresolved units are intentional and must not be silently resolved merely to simplify OpenAlex processing.

Future changes to this method must be versioned and should preserve the ability to reconstruct results produced under earlier releases.
