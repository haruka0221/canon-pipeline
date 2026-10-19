# Held Aggregation Unit Human Review Protocol — Draft v0.2

Status: DRAFT — NOT FROZEN
Date: 2026-10-19
Basis: 20 AI-assisted development case reviews
Human gold labels: 0
Held-out evaluation cases: NOT REVIEWED

## 1. Purpose

Evaluate whether multiple Open Library source Work records
refer to the same project conceptual work.

The review must distinguish:

1. Conceptual-work identity
2. Edition coverage and bibliographic granularity
3. Evidence sufficiency and source quality
4. Research corpus eligibility (scope)

This protocol supplements, but does not supersede:

- docs/AGGREGATION_POLICY.md
- docs/IDENTITY_MODEL.md

The E / A / W distinction remains unchanged.

## 2. Primary conceptual-work decisions

### ONE_WORK

Evidence sufficiently supports treating all relevant
source Work records as referring to one conceptual work.

Different publication titles, publishers, translations,
formats, publication dates, or contributor roles do not
automatically imply different conceptual works.

However, individual Edition coverage must still be examined.

### MULTIPLE_WORKS

Evidence establishes the presence of more than one
distinct conceptual work, such as:

- a prose story and its dramatic adaptation;
- a collection and a constituent literary work;
- otherwise demonstrably distinct intellectual works.

Record whether a clean partition of source Work entities
is possible.

MULTIPLE_WORKS must not authorize automatic splitting
if one source Work already mixes heterogeneous Editions.

### UNRESOLVED

The available evidence is insufficient to establish
defensible conceptual-work boundaries.

Record the reason for uncertainty. Examples include:

- missing or contradictory contents evidence;
- unclear part-whole boundaries;
- unresolved adaptation or abridgment status;
- source Work internal heterogeneity.

UNRESOLVED must not be used merely because individual
Edition dates, pagination, or other metadata contain errors.

## 3. Independent review dimensions

For every unit, examine and record separately:

### A. Identity evidence

- Titles and independently attested alternate titles
- Authors and their bibliographic identities
- Independent catalogues and publisher records
- Edition titles, publication history, and contents
- Whether all source records refer to the same work

### B. Granularity and Edition coverage

Check for:

- complete work versus part or volume;
- original versus translation;
- full text versus abridgment;
- collection versus constituent work;
- dramatization or other adaptation;
- audiobook segment versus complete recording;
- collected-works series volume versus anthology.

Being related to the same original work does not prove
that Edition-level textual coverage is identical.

### C. Source-data quality

Record anomalies separately from identity judgments:

- inaccurate source-reported publication year;
- missing or misleading title;
- duplicated or incorrectly assigned author ID;
- contributor incorrectly entered as an author;
- inconsistent page count;
- heterogeneous Editions inside a single OL Work.

The historical OL first-publish field is not a verified
conceptual original-publication year.

### D. Scope

Do not conflate conceptual identity with:

- original publication period;
- first English publication period;
- original language;
- translation status;
- literary genre.

Scope decisions require a separate policy and artifact.

## 4. Source Work internal heterogeneity

If one Open Library Work contains Editions representing
different conceptual works or publication units:

1. Identify the conflicting Edition IDs.
2. Record each evidenced content type.
3. Do not force a source Work-level partition.
4. Record that Edition-level reassignment is required.
5. Keep the project aggregation decision unresolved
   operationally until a separate versioned action
   has been approved.

Evidence for multiple conceptual works and feasibility
of a clean source-record partition are separate questions.

## 5. Provisional relationship and issue flags

The following are descriptive review flags, not new
project entity types or approved automated operations:

- duplicate_source_work
- alternate_publication_title
- distinct_translations
- part_whole_granularity
- collection_contains_work
- adaptation
- editorial_abridgment
- audio_part_whole
- contributor_role_anomaly
- author_id_discrepancy
- source_work_internal_heterogeneity
- edition_metadata_error
- insufficient_bibliographic_evidence

More than one flag may apply to a case.

## 6. Evidence requirements

Every eventual human adjudication should record:

- reviewed source Work IDs;
- relevant Edition IDs;
- bibliographic sources and stable URLs where available;
- what each source establishes;
- unresolved questions;
- conceptual-work decision and confidence;
- reviewer and review date;
- whether AI assistance was consulted.

A URL in a note is not proof that the linked source
supports the accompanying claim.

Incomplete evidence is preferable to invented certainty.

## 7. Human review and independence

Development sample:
AI-assisted findings may inform protocol development.
A researcher must explicitly verify and record any
subsequent HUMAN_VERIFIED judgment.

A judgment informed by AI proposals must not be described
as independent or blind human annotation.

Held-out evaluation sample:
Freeze the review protocol before evaluation.
Do not consult the previous LLM decisions while labeling.
Record the reviewer's evidence and decisions separately.
Compare with the previous LLM decisions only afterward.

No current development note is a human gold label.

## 8. Evaluation safeguards

- The 20 development units are for method development.
- The 20 held-out units remain untouched.
- Neither sample automatically estimates the full
  761-unit population.
- Preserve all source evidence and its provenance.
- Do not overwrite frozen Project W or identity releases.
- Do not convert review flags into automatic SAME links.
- Future identity corrections need separate, versioned
  decisions and release-level verification.

## 9. Development cases motivating v0.2

E000005779:
Collection versus constituent story.

E000005348:
Two-part original, translated and abridged parts.

E000004501:
Selected and edited portions of Gulliver's Travels.

E000034716:
Prose narrative, dramatization, and collection
mixed inside a source Work.

E000001231:
Audiobook Part 1 versus the full novel.

E000033606:
24-story and 42-story collection boundaries
with Editions crossing OL Work boundaries.

E000009675:
Different OL Author IDs despite strong independent
bibliographic support for the same author and novel.

These are AI-assisted observations, not human gold labels.

## 10. Current status

20 development units have preliminary review notes.

Preliminary AI categories:
- ONE_WORK: 12
- MULTIPLE_WORKS: 2
- UNRESOLVED: 6

Human decisions: 0

Three early units lack explicit source URLs
in the current review worksheet:
- E000005163
- E000022268
- E000021061

External-source verification remains a separate task.

This protocol is a draft and does not modify Project W.
