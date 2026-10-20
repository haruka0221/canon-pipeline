# Exploratory bibliographic inspection notes — 2026-10-20

Status: EXPLORATORY; NOT IDENTITY ADJUDICATION

## Scope and provenance

The historical LLM assigned ONE_WORK to 438 held aggregation units.
The v1 screen examined 1,249 OL Works and 40,305 Editions.
The v2 enrichment recovered raw bibliographic fields from the frozen
Open Library Editions dump dated 2026-02-28.

The v3 queue contains 438 units:
- T1_CONTENT_CLUE: 75
- T2_SCOPE_OR_PAGINATION: 61
- T3_GENERAL_METADATA_VARIATION: 236
- T4_NO_DEFINED_PROMPT: 66

Combined v1/v2 signal coverage: 372/438.
No defined signal in either screen: 66/438.

An exploratory display of 13 previously unsampled units was followed
by targeted read-only inspection of 14 Edition records in seven units.
These were not randomly sampled evaluation cases. Their results must
not be used to estimate population-level precision or recall.

## Bibliographic observations requiring attention

E000006533 — Peg Woffington
- OL58162477M: Peg Woffington, pagination 255, 32 p.;
  notes identify advertisements.
- OL24773752M: subtitle enumerates The Knightsbridge Mystery
  and several other separately titled stories.
- Materially different publication contents are plausible.
  Verify title page and contents before any identity decision.

E000006651 — Rab and His Friends
- OL26312932M: title refers to other stories of dogs; 58 pages.
- OL6942418M and OL7024530M: 299 pages and contents listing
  Rab and His Friends alongside multiple other titled pieces.
- Verify exact constituent-work and collection boundaries.

E000016222 — The War of the Worlds
- OL3392127M includes the novel and additional interpretations.
- OL5906325M contains a Bound with note for The Time Machine.
- OL5906034M describes two separately issued books in a slipcase.
- Distinguish text-plus-commentary, physical binding, and
  publisher-issued joint editions.

E000000892 — For My Great Folly
- OL14994025M has a Bound with note for The Moneyman.
- OL18553090M is a translated two-volume publication.
- Binding and translated-volume segmentation alone are not
  sufficient evidence for multiple conceptual works.

## Examples of overly broad pagination prompts

E000007746 — Ninety-three
- OL58202932M: 187, 4 p.; four pages explicitly identified
  as advertisements. Not evidence of a second literary work.

E000019179 — Cakes and Ale
- OL23115054M: 8, 272 p., with translation metadata.
- No independent constituent work is established by pagination.

E000006533 — Peg Woffington
- OL58162477M: 255, 32 p.; advertising material noted.
- The separate OL24773752M subtitle is a stronger content clue.

## Editorial and archival granularity

E000021402 — The Wild Palms
- OL42892051M has a collected-works title but no verified
  second constituent novel in the inspected record.
- OL2549019M is a two-volume manuscript and publishing
  materials edition with detailed contents.
- Distinguish textual-work identity from archival
  publication-unit differences before adjudicating.

## Methodological limitations

1. No new ONE_WORK, MULTIPLE_WORKS, or UNRESOLVED decisions
   have been made in this exploratory inspection.
2. A positive bibliographic prompt is not proof of a bad merge.
3. A missing prompt is not evidence that merging is safe.
4. Edition-level source IDs must remain attached to claims.
5. The v3 tiers contain known false-positive mechanisms and
   should remain versioned and unchanged before v4 refinement.
6. v1-v3 were designed after historical held-out outcomes
   became visible; no independent classification performance
   can be claimed from retrospective examples.
7. Previous frozen held-out judgments and Project W releases
   remain unchanged.
8. Existing manifests record build-time local statuses;
   version-controlling the files does not rewrite those fields.
