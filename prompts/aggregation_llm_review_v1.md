# Aggregation review v1

You are reviewing groups of Open Library Work records for a literary-history
research dataset.

The task is NOT to decide whether each external database record is correct in
general. The task is to decide how the CURRENT OPEN LIBRARY TARGETS in one
review unit should be represented as project conceptual works.

Use only the evidence supplied in the input packet.

## Possible decisions

### ONE_WORK

Use when all current Open Library targets in the unit represent the same
underlying conceptual literary work.

Typical evidence includes:
- duplicate Open Library Work records;
- capitalization or punctuation variants;
- catalog records that clearly refer to the same underlying work;
- convergence on the same external work entities, when the source assertions
  are sufficiently strong.

### MULTIPLE_WORKS

Use when the current Open Library targets clearly contain two or more distinct
conceptual works.

Return an explicit partition of the Open Library entity IDs.

Examples include:
- an individual work versus a collection or omnibus containing it;
- different works with similar or identical titles;
- an individual volume versus a whole series;
- clearly distinct constituent works;
- records that have been incorrectly joined through an external entity.

### UNRESOLVED

Use when the supplied evidence is insufficient to make a safe conceptual-work
partition.

Prefer UNRESOLVED over guessing.

Cases involving translations, adaptations, substantially revised versions,
part/whole relations, collections, omnibus editions, series/volume relations,
or unclear authorship should not be collapsed automatically unless the
provided evidence makes the identity relation clear.

## Important constraints

- Do not infer identity solely through transitive closure.
- A -> X and B -> X does not by itself prove A = B.
- Goodreads and Wikidata can themselves over-aggregate or contain errors.
- `first_publish_year` is historical Open Library-derived evidence, not a
  guaranteed conceptual original-publication year.
- Different Open Library Work IDs are not by themselves evidence of distinct
  works.
- Shared title alone is weak evidence.
- Coauthorship or variation in author attribution does not by itself prove that
  two records are different works.
- Do not use outside knowledge unless it is explicitly present in the packet.
- High confidence requires evidence that is directly represented in the
  packet.

## Relation flags

Use zero or more of:

- duplicate_record
- title_variant
- authorship_variant
- collection_or_omnibus
- part_whole
- series_or_volume
- translation
- adaptation
- revised_version
- external_source_overmerge
- external_source_conflict
- uncertain_relation

## Required output

Return JSON only, with exactly these top-level fields:

{
  "unit_anchor_entity_id": "...",
  "decision": "ONE_WORK | MULTIPLE_WORKS | UNRESOLVED",
  "clusters": [
    ["E..."]
  ],
  "relation_flags": [],
  "confidence": "high | medium | low",
  "evidence_summary": "...",
  "needs_human_review": true
}

Rules for `clusters`:

- ONE_WORK: exactly one cluster containing every current OL entity ID.
- MULTIPLE_WORKS: two or more non-overlapping clusters whose union contains
  every current OL entity ID exactly once.
- UNRESOLVED: return each current OL entity ID as its own singleton cluster
  unless a subset can already be grouped safely.

`evidence_summary` should be concise and refer to evidence contained in the
packet, not external knowledge.

Set `needs_human_review` to false only when confidence is high and the
conceptual-work partition is directly supported by the supplied evidence.
