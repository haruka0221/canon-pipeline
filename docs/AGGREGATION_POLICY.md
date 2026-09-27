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
