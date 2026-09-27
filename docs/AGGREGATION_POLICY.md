# Aggregation Policy

Version: 1
Date: 2026-09-27

## 1. Purpose

This document defines how source-level identity evidence is converted into
project-level conceptual works.

The project distinguishes three different objects:

- `E...` — source entity
- `A...` — identity assertion
- `W...` — project conceptual work

These identifiers represent different levels of the data model and must not
be treated as interchangeable.

The purpose of aggregation is to decide when one or more source entities may
be represented by a single project conceptual work.

Aggregation is a separate step from source matching.

## 2. Source entities (`E...`)

A source entity represents one record in an external source or source layer.

Examples include:

- an Open Library Work,
- a Goodreads work,
- a Wikidata item.

Source entities preserve source provenance. They do not by themselves define
the project's conceptual-work boundaries.

Different source entities may represent:

- the same conceptual work,
- different editions or manifestations of the same work,
- translations,
- adaptations,
- parts of a larger work,
- collections or series,
- genuinely different works,
- or erroneous source records.

Therefore, source entities are not automatically interchangeable.

## 3. Identity assertions (`A...`)

An identity assertion records a source-specific judgment about a pair of
source entities.

In `identity_assertions_v1`, accepted assertions have:

- `identity_type = work`
- `identity_decision = SAME`

A `SAME` assertion means that the source-specific resolution process accepted
the pair as referring to the same work for that matching task.

It does **not** mean that:

- the two source records have identical granularity,
- the external source is necessarily correct,
- all entities connected through `SAME` assertions must automatically be
  merged,
- or a project conceptual work has already been established.

Identity assertions are evidence for aggregation, not aggregation decisions.

## 4. Project conceptual works (`W...`)

A `W...` identifier represents a conceptual work defined by this project.

`W...` identifiers are project-native identifiers. They are not aliases for
Open Library IDs, Goodreads IDs, Wikidata QIDs, or any other external
identifier.

A `W...` identifier is issued only after the project has made an explicit
aggregation decision about which current analysis targets belong to that
conceptual work.

No `W...` identifiers are assigned by `aggregation_review_v1`.

## 5. Current analysis targets

The aggregation process operates on the current Open Library analysis target
set defined in:

`derived/identity/openlibrary_analysis_targets_v1.*`

This release contains 34,789 current Open Library targets.

Historical Open Library source entities remain in the source-entity registry
even when a later target correction removes them from the current analysis
population.

Source-level identity assertions attached to such historical entities are
also preserved. They are not silently deleted or rewritten.

However, assertions whose left Open Library entity is not a current analysis
target do not participate in the current aggregation graph.

## 6. Aggregation review graph

`aggregation_review_v1` constructs a graph from:

1. the 34,789 current Open Library analysis targets; and
2. accepted source-specific `SAME` assertions whose left entity is one of
   those current targets.

The graph contains 16,064 included assertions.

One historical source-level assertion is preserved in
`identity_assertions_v1` but excluded from the current aggregation graph:

`A000009386`

This assertion connects the historical Open Library target `OL15345521W`
with Wikidata `Q208622`.

The historical Open Library entity remains valid as a source entity, but it
is not a current analysis target.

## 7. Provisional aggregation units

Connected components of the current aggregation graph, together with current
targets having no accepted external identity assertion, form provisional
aggregation units.

`aggregation_review_v1` contains 32,847 provisional units.

This number must **not** be interpreted as the number of conceptual works in
the corpus.

A provisional unit is a review structure only.

The field `unit_anchor_entity_id` is the lexically smallest current Open
Library `E...` identifier in that unit.

It is a deterministic release-local anchor. It is not a conceptual-work ID
and must not be treated as a substitute for a `W...` identifier.

## 8. Structural classes

`aggregation_review_v1` assigns each provisional unit one of five structural
classes.

### 8.1 `no_accepted_external_identity`

One current Open Library target has no accepted Goodreads or Wikidata
identity assertion.

Current release:

- 23,295 units
- 23,295 current Open Library targets

This means only that no accepted external identity is currently available.

It does not establish that the Open Library record is unique at the
conceptual-work level.

### 8.2 `single_ol_single_external_source`

One current Open Library target is connected to one external source entity.

Current release:

- 5,090 units
- 5,090 current Open Library targets

This is single-source support for an identity relationship.

It is not independently corroborated by both Goodreads and Wikidata.

### 8.3 `single_ol_cross_source_corroborated`

One current Open Library target is connected to one Goodreads entity and one
Wikidata entity, without an explicit structural conflict.

Current release:

- 3,154 units
- 3,154 current Open Library targets

This provides cross-source corroboration.

Cross-source corroboration is stronger evidence than a single external
source, but it still does not by itself prove that all source records have
identical conceptual granularity.

### 8.4 `multi_ol_no_explicit_split`

Two or more current Open Library targets are connected through accepted
external identity assertions, while the external-source structure does not
explicitly split them into multiple Goodreads or multiple Wikidata entities.

Current release:

- 1,294 units
- 3,204 current Open Library targets

The absence of an explicit external split must not be interpreted as proof
that all Open Library records represent one conceptual work.

Possible explanations include:

- duplicate Open Library Work records,
- translations,
- parts and wholes,
- collections,
- series or installments,
- different textual versions,
- or external-source overaggregation.

These units require an explicit aggregation rule or review before their
Open Library targets can be merged into one project work.

### 8.5 `cross_source_conflict`

A connected component contains more than one accepted Goodreads entity or
more than one accepted Wikidata entity.

Current release:

- 14 units
- 46 current Open Library targets

These units contain explicit structural disagreement within the accepted
identity graph.

They must not be automatically collapsed into a single project conceptual
work.

They require review before project-work membership is assigned.

## 9. Aggregation decisions

A future aggregation-decision layer should record explicit project decisions
separately from source-level identity assertions.

The initial decision vocabulary is:

- `ONE_WORK`
- `MULTIPLE_WORKS`
- `UNRESOLVED`
- `MANUAL_REVIEW_REQUIRED`

### `ONE_WORK`

The reviewed current Open Library target or targets may be represented by one
project conceptual work.

### `MULTIPLE_WORKS`

The provisional aggregation unit contains more than one project conceptual
work and must be split before project-work IDs are assigned.

### `UNRESOLVED`

Available evidence is insufficient to determine conceptual-work boundaries.

### `MANUAL_REVIEW_REQUIRED`

The unit has been identified as requiring explicit review before an
aggregation decision can be made.

These decisions belong to the project aggregation layer and must not overwrite
the underlying source entities or identity assertions.

## 10. Default treatment by structural class

The structural class determines review priority, not conceptual identity.

The default treatment for version 1 is:

| Structural class | Default treatment |
| --- | --- |
| `no_accepted_external_identity` | do not merge with another current target solely from absence of external evidence |
| `single_ol_single_external_source` | retain as a single-target provisional unit; external identity remains source-specific evidence |
| `single_ol_cross_source_corroborated` | retain as a single-target provisional unit with cross-source support |
| `multi_ol_no_explicit_split` | do not automatically merge multiple current OL targets; aggregation decision required |
| `cross_source_conflict` | manual review required before project-work assignment |

For the three single-target classes, the project may later issue one `W...`
identifier per current target under a separately versioned project-work
release policy.

This must not be interpreted as a claim that Open Library has perfectly
deduplicated conceptual works.

### 10.1 Initial automatic decision policy for v1

For `aggregation_decisions_v1`, the three structural classes containing
exactly one current Open Library target receive:

- `aggregation_decision = ONE_WORK`
- `decision_method = single_current_target_policy`
- `decision_version = v1`
- `review_status = auto_accepted`

The three classes are:

- `no_accepted_external_identity`
- `single_ol_single_external_source`
- `single_ol_cross_source_corroborated`

`ONE_WORK` means that the project may represent that provisional unit as one
project conceptual work in the current release.

It does not claim that Open Library has globally deduplicated all conceptual
works, and it does not prevent a later versioned merge if another provisional
unit is later shown to represent the same conceptual work.

Units classified as:

- `multi_ol_no_explicit_split`
- `cross_source_conflict`

receive:

- `aggregation_decision = MANUAL_REVIEW_REQUIRED`
- `decision_method = structural_review_gate`
- `decision_version = v1`
- `review_status = pending`

No `MULTIPLE_WORKS` or `UNRESOLVED` decisions are assigned automatically in
v1. Those decisions require additional evidence or review.

### 10.2 Strict multi-OL cross-source rule for v2

`aggregation_decisions_v2` adds one conservative automatic aggregation rule
for units previously classified as `multi_ol_no_explicit_split`.

A unit may be changed from `MANUAL_REVIEW_REQUIRED` to `ONE_WORK` only when
all of the following conditions hold:

1. all current Open Library targets have the same title after Unicode NFKC
   normalization, case folding, and removal of non-alphanumeric characters;
2. all current Open Library targets have the same non-empty `author_keys`;
3. all current Open Library targets have the same non-empty historical
   `first_publish_year`;
4. the unit contains exactly one Goodreads entity and exactly one Wikidata
   entity;
5. every current Open Library target has a direct accepted `SAME` assertion
   to that Goodreads entity;
6. every current Open Library target has a direct accepted `SAME` assertion
   to that Wikidata entity;
7. every relevant Goodreads assertion has
   `resolution_status_detail = AUTO_MATCH_HIGH`; and
8. every relevant Wikidata assertion has `confidence = high`.

The decision metadata for units accepted by this rule is:

- `aggregation_decision = ONE_WORK`
- `decision_method = multi_ol_exact_metadata_cross_source_rule`
- `decision_version = v2`
- `review_status = auto_accepted`

This rule is an operational project aggregation rule. It does not claim that
the Open Library records have been proven to be duplicate records in every
bibliographic or ontological sense.

Units failing any condition remain under their previous decision.

Existing v1 decisions are preserved historically. In the v2 decision release,
unchanged rows retain the decision version under which their current decision
was originally made.

### 10.3 Direct Open Library identity-evidence rule for v3

`aggregation_decisions_v3` adds a second conservative automatic aggregation
rule for units that remained `MANUAL_REVIEW_REQUIRED` after v2.

A unit may be changed to `ONE_WORK` only when all of the following conditions
hold:

1. it is classified as `multi_ol_no_explicit_split`;
2. all current Open Library targets have the same title after Unicode NFKC
   normalization, case folding, and removal of non-alphanumeric characters;
3. all current Open Library targets have the same non-empty `author_keys`;
4. all current Open Library targets have the same non-empty historical
   `first_publish_year`;
5. the unit contains exactly one Goodreads entity and exactly one Wikidata
   entity;
6. every current Open Library target has a direct accepted `SAME` assertion
   to that Goodreads entity;
7. every current Open Library target has a direct accepted `SAME` assertion
   to that Wikidata entity;
8. every relevant Goodreads assertion has
   `resolution_status_detail = AUTO_MATCH_IDENTITY_EVIDENCE`;
9. every relevant Goodreads assertion records either
   `IDENTITY_OL_DIRECT` or `IDENTITY_OL_REDIRECT_DIRECT` as
   `author_match_quality`, has `review_needed = 0`, and has a full work/book
   title match;
10. every relevant Wikidata assertion has `confidence = high`.

The decision metadata for units accepted by this rule is:

- `aggregation_decision = ONE_WORK`
- `decision_method = multi_ol_identity_evidence_cross_source_rule`
- `decision_version = v3`
- `review_status = auto_accepted`

This rule uses explicit Open Library identity evidence already preserved by the
Goodreads resolution pipeline. It does not infer membership through transitive
closure. A unit lacking a direct accepted assertion from every current Open
Library target to both external entities remains unresolved by this rule.

Existing v1 and v2 decisions remain historically unchanged. In the v3 release,
unchanged rows retain the decision version under which their current decision
was originally made.

## 11. Conditions for issuing `W...` identifiers

A `W...` identifier may be issued only when:

1. the relevant current Open Library target or targets are explicitly included
   in a project aggregation decision;
2. the aggregation decision specifies the conceptual-work boundary;
3. unresolved structural conflicts are not silently collapsed;
4. the decision and its provenance are preserved in a versioned artifact; and
5. the mapping from source entities to the resulting project work is recorded
   separately.

The issuance of a `W...` identifier must therefore be reproducible from a
versioned aggregation policy and decision layer.

## 12. Project-work membership

A future work-identity mapping should explicitly record membership such as:

`E... -> W...`

The mapping expresses a project aggregation decision.

It must not be generated merely by computing the transitive closure of all
`SAME` identity assertions.

A source entity may participate in source-level evidence without being
automatically assigned to a project conceptual work.

## 13. Stable `W...` identifier policy

Once a `W...` identifier has been released, it must never be reused for an
unrelated conceptual work.

Existing released `W...` identifiers must not be renumbered merely because
new evidence is added.

New project works receive new identifiers after the highest previously
released `W...` identifier.

### 13.1 Initial `W` assignment

For the first stable project-work release, only units with:

`aggregation_decision = ONE_WORK`

receive a project-work identifier.

Units with:

`aggregation_decision = MANUAL_REVIEW_REQUIRED`

receive no `W...` identifier until a later versioned aggregation decision
establishes their conceptual-work boundary.

For `project_works_v1`, eligible units are sorted lexically by
`unit_anchor_entity_id` and assigned sequential identifiers beginning with:

`W000000001`

The initial release therefore assigns `W...` identifiers only to the 31,539
auto-accepted `ONE_WORK` units.

This ordering is used only to make the initial assignment deterministic.
After release, existing `W...` identifiers are stable and are never
renumbered because new works are added.

### 13.2 `project_works` registry

The initial project-work registry has the following minimum fields:

```text
project_work_id
origin_unit_anchor_entity_id
aggregation_decision
aggregation_decision_version
status
created_at
```

For the initial release:

```text
aggregation_decision = ONE_WORK
aggregation_decision_version = v1
status = active
```

`origin_unit_anchor_entity_id` records the provisional aggregation unit from
which the project work was initially created. It is provenance, not the
identity of the project work itself.

### 13.3 `work_identity_map`

Project-work membership is stored separately from the project-work registry.

The initial mapping has the following minimum fields:

```text
project_work_id
source_entity_id
membership_role
membership_basis
aggregation_decision_version
created_at
```

For `project_works_v1`, all source entities belonging to an accepted
`ONE_WORK` aggregation unit may be mapped to the corresponding `W...`
identifier.

`membership_role` preserves whether the entity entered the aggregation unit
as:

```text
current_analysis_target
accepted_external_identity
```

`membership_basis` records the aggregation decision that authorized the
mapping.

Source-level `SAME` assertions remain independently preserved and are not
replaced by this mapping.

### 13.4 Project-work lineage

Changes to an already released project-work boundary are represented in a
separate versioned lineage table rather than by rewriting historical
releases.

The minimum lineage schema is:

```text
event_type
predecessor_project_work_id
successor_project_work_id
decision_version
reason
created_at
```

Allowed initial `event_type` values are:

```text
MERGE
SPLIT
SUPERSEDE
```

A merge is represented by multiple predecessor-to-successor rows when
necessary.

A split is represented by multiple predecessor-to-successor rows when
necessary.

Historical `project_works` and `work_identity_map` releases remain unchanged.
The current release may mark an earlier project work as superseded, but its
identifier and historical membership are preserved.

No lineage rows are required for `project_works_v1`, because it is the first
project-work release.

### 13.5 Subsequent project-work releases

A later project-work release must preserve every previously released
`project_work_id`.

When a later aggregation-decision release makes additional units eligible for
project-work assignment:

1. existing project-work registry rows are retained unchanged;
2. existing work-identity membership rows are retained unchanged;
3. newly eligible units are sorted deterministically by
   `unit_anchor_entity_id`;
4. new `W...` identifiers are appended after the highest previously released
   identifier; and
5. new membership rows record the aggregation-decision version that authorized
   them.

For `project_works_v2`, the 31,539 project works from v1 are preserved and the
112 units newly accepted by `aggregation_decisions_v2` receive:

`W000031540` through `W000031651`.

Historical v1 membership continues to cite
`aggregation_decisions_v1:ONE_WORK`; newly added v2 membership cites
`aggregation_decisions_v2:ONE_WORK`.

For `project_works_v3`, all 31,651 previously released project works and all
43,400 previously released membership rows are preserved unchanged. The two
units newly accepted by `aggregation_decisions_v3` receive:

`W000031652` and `W000031653`.

Their new membership rows cite `aggregation_decisions_v3:ONE_WORK`.

## 14. Later merge of project works

If later evidence shows that two previously released project works should be
treated as one conceptual work:

- do not silently rewrite historical releases;
- preserve both historical `W...` identifiers and their earlier mappings;
- record a new versioned aggregation decision;
- designate the current surviving or successor project-work representation
  explicitly;
- preserve provenance explaining the merge.

A merge must therefore be representable historically rather than appearing
as though the earlier project works never existed.

## 15. Later split of a project work

If later evidence shows that one previously released project work contains
multiple conceptual works:

- do not silently repurpose the existing `W...` identifier;
- preserve the historical release and its earlier membership;
- issue new `W...` identifiers for newly distinguished conceptual works as
  required;
- record a new versioned aggregation decision explaining the split;
- preserve the relationship between the superseded aggregation and its
  successor works.

The exact machine-readable merge/split schema should be defined before the
first stable `project_works` release.

## 16. Separation from scope

Conceptual-work aggregation and corpus scope are separate decisions.

A source entity or project work may be successfully resolved without being
in scope for the dissertation corpus.

Likewise, lack of Goodreads or Wikidata coverage must not by itself make a
work out of scope.

Period, language, genre, and other corpus-selection rules belong to the
scope-resolution layer rather than the identity or aggregation layer.

## 17. Current implementation sequence

The current implementation order is:

1. frozen historical Open Library source population;
2. source-entity registry;
3. source-specific identity assertions;
4. current Open Library analysis targets;
5. provisional aggregation review;
6. versioned aggregation decisions;
7. project conceptual works (`W...`);
8. source-entity-to-project-work membership;
9. year evidence and other work-level evidence;
10. versioned scope resolution.

This ordering keeps source evidence, identity judgments, conceptual
aggregation, and corpus selection auditable and independently revisable.
