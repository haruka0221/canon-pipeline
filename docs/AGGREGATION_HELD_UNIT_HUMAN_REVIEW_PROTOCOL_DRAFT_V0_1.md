# Held Aggregation Unit Human Review Protocol — Draft v0.1

Status: DRAFT — NOT FROZEN
Scope: 20 development units from 761 held aggregation units
Purpose: Establish defensible bibliographic identity adjudication criteria.

## 1. Principles

- Open Library Work IDs are source records, not Project W identities.
- Matching titles, authors, dates, or page counts do not alone prove identity.
- Edition publication dates are not conceptual original-publication dates.
- Translations, revisions, collections, omnibus editions, parts, and series
  require explicit consideration.
- Shared Goodreads or Wikidata identities are evidence, not project decisions.
- Identity adjudication must remain separate from corpus scope adjudication.
- Uncertainty must be preserved rather than resolved by guessing.

## 2. Decisions

ONE_WORK:
Sufficient evidence supports representing all relevant OL Work records
as one project conceptual work.

MULTIPLE_WORKS:
Evidence supports two or more distinct conceptual works.
The proposed partition of OL source entities must be recorded.

UNRESOLVED:
Available evidence does not support a defensible partition or merge.

These decisions concern conceptual-work identity, not corpus eligibility.

## 3. Review procedure

1. Compare OL Work titles, author IDs, and historical first-publish fields.
2. Examine all linked Edition records and their distributions.
3. Check whether each OL Work internally mixes different publications
   or intellectual works.
4. Investigate alternate titles, translations, collections, parts,
   revisions, and author attribution.
5. Consult independent bibliographic sources where necessary.
6. Record supporting Edition IDs, source URLs, unresolved questions,
   confidence, and the reasoning behind each decision.
7. Do not register an AI suggestion as a verified human decision.

## 4. Development cases discussed so far

E000005163 — Sherlock Holmes collections
Preliminary disposition: UNRESOLVED.
Reason: Overlapping collections with potentially different contents
and editorial boundaries. Edition-level coherence requires review.

E000022268 — Suddenly at His Residence / The Crooked Wreath
Preliminary disposition: ONE_WORK candidate.
Reason: Evidence for UK/US alternate publication titles.
Outstanding: Independent evidence documentation and additional OL author ID.

E000021061 — The Haunted Bookshop
Preliminary disposition: ONE_WORK candidate.
Reason: Matching author, title, and bibliographic features across two
OL Works, despite differing historical first-publish fields.
Outstanding: Verify the 1926 Edition and independent bibliography.

These are discussion notes, not finalized human adjudications.

## 5. Evaluation safeguards

- Use the 20 development units to refine this protocol.
- Keep the 20 held-out units separate during method development.
- Do not use prior LLM judgments as the human gold standard.
- Preserve the sampling design and distinguish pilot performance
  from estimates for the full 761-unit population.
- Evaluate LLM judgments only after independent assessment.
- Never update project_works_v7 or frozen identity releases in place.
- Any approved identity revision requires a new versioned release.

## 6. Related artifacts

- docs/AGGREGATION_POLICY.md
- docs/IDENTITY_MODEL.md
- derived/identity/aggregation_held_units_sampling_v1/
- derived/identity/aggregation_held_dev_evidence_20260228_v1/
- derived/identity/aggregation_held_dev_review_draft_v1/

## 7. Status

Draft protocol under development.
Three preliminary cases discussed.
No human gold-standard decisions finalized.
No Project W changes authorized.
