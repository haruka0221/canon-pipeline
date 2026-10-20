# V4 exploratory bibliographic quality audit

Status: EXPLORATORY; NOT IDENTITY ADJUDICATION
Date: 2026-10-20
Frozen OL Edition snapshot: 2026-02-28

## Scope

438 held historical old-LLM ONE_WORK units;
1,249 OL Works; 40,305 Edition records.

V4 focus groups:
- F1_CONTENT_BOUNDARY: 27
- F2_PUBLICATION_CONTEXT: 20
- F3_AMBIGUOUS_METADATA: 367
- F4_NO_DEFINED_PROMPT: 24

Among the 27 F1 units, 3 belong to the previously
sampled development/held-out set; 24 do not.

## Interpretive cautions

F1 denotes a reason to inspect publication content,
not a judgment that the aggregation unit incorrectly
combines conceptual literary works.

Edition-level heterogeneity does not necessarily imply
identity disagreement between the OL Works in a unit.

Examples from the read-only quality audit:

- E000000220: The Brothers Karamazov.
  Two-volume pagination may represent one novel.

- E000006180: Kidnapped.
  Extended narrative subtitle can resemble a list
  of independent titles.

- E000006533: Peg Woffington.
  OL24773752M lists several separately titled works;
  verify publication contents and OL Work alignment.

- E000006651: Rab and His Friends.
  Editions supply multiple contents entries and
  potentially different collection scopes.

- E000018738: Peter Pan.
  The sampled F1 subtitle is programme wording;
  this signal alone does not establish work identity.
  Other known play/novel distinctions remain relevant.

- E000019492: The Regent's Daughter.
  OL52630896M records subtitle The Black Tulip
  and pagination 319, 253 pages.

- E000019621: Youth, a Narrative and Two Other Stories.
  Two inspected Editions list the same three stories.
  This may support duplicate OL Work records for
  the same collection, not an erroneous union.

- E000019634: Typhoon.
  OL21043182M lists Typhoon, Amy Foster, Falk,
  and To-morrow. Compare the other OL Work before
  drawing any identity conclusion.

- E000007746: Ninety-three.
  Extra pages explicitly describe advertisements.

- E000019179: Cakes and Ale.
  Short leading pagination and translated-title
  metadata are not by themselves evidence of
  multiple conceptual works.

## Methodological restrictions

The v4 detection rules were developed after inspection
of earlier human-assisted held-out and exploratory
examples. These cases do not provide an independent
estimate of v4 precision, recall, or error rate.

F1/F2/F3/F4 are bibliographic review priorities only.
F4 does not establish safety of an automatic merge.

No ONE_WORK/MULTIPLE_WORKS decisions were made.
No Project W records or historical evaluation labels
were modified. Existing v1-v3 artifacts remain frozen.
