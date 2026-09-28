# OpenAlex Scholarly Visibility Matching Method

**Status:** Design adopted for implementation; registry v3 not yet frozen  
**Date:** 2026-09-28  
**Current identity baseline:** `project_works_v4`  
**Repository:** `haruka0221/canon-pipeline`  
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

The first production `query_author_selection_rule` remains intentionally
**unfrozen**. Its selection must be based on an explicit audit of the frozen
source layer rather than on the earlier single-author population columns.
The selected query author will be a derived retrieval value and will not
overwrite or redefine source-native authorship evidence.

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

The following require calibration or coverage audit before production freeze:

### 29.1 Query-author selection rule

The exact preference order among source-native author names remains to be tested.

Candidates include:

```text
name
personal_name
fuller_name
alternate_name
```

The rule should be chosen after checking:

- coverage;
- disagreement rates;
- formatting effects;
- multi-author cases;
- retrieval consequences.

### 29.2 R2 representative-title selection

The final representative-alias rule remains to be specified and versioned.

It must not rely on the historical `canonical` flag as if that flag established project-level title authority.

### 29.3 R4 operational routing policy

Candidate burden, collision, precision, and incremental recall should be evaluated before choosing the final route policy.

### 29.4 Semantic-recall route

Character names and work-specific terminology remain experimental until separately validated.

---

## 30. Immediate implementation sequence

The next implementation steps are:

1. audit author-source coverage for all current Open Library analysis targets;
2. freeze the Open Library author evidence artifacts required by OpenAlex v3;
3. define and version the first query-author selection rule;
4. construct W-based alias registry v3;
5. define the R2 representative-alias rule;
6. construct the logical query registry with stable `query_id`;
7. construct normalized execution signatures;
8. rerun retrieval calibration at W level;
9. evaluate R2 / R3 / R4 candidate burden, collisions, recall, and precision;
10. freeze the production retrieval policy;
11. perform the full OpenAlex scan;
12. adjudicate candidate attribution / mention;
13. aggregate accepted evidence to W-level scholarly visibility;
14. keep unresolved source-target results separate until a later identity release.

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