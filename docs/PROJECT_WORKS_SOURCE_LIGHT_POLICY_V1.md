# Source-light Project Works policy v1

## Purpose

A project conceptual Work may be supported by Edition-level
bibliographic evidence without having an accepted source Work
identity member.

This is particularly necessary when a source Open Library Work
was human-adjudicated as an overaggregated cluster.

## Rules

1. Do not reuse a known overaggregated source Work as a SAME
   member of its primary successor.
2. An existing W ID may be restored for a primary successor
   only if a frozen human adjudication explicitly authorizes
   that inheritance.
3. Store Edition-to-Project-Work relations separately from
   the SAME-based work_identity_map.
4. Human-confirmed component routing is not automatically
   equivalent to a fully adjudicated EDITION_OF assertion.
5. LLM-only Edition routing remains provisional.
6. Maintain an explicit exception registry for active Works
   that have no current work_identity_map membership.
7. Historical source records, W IDs, and prior releases
   remain immutable.
8. Identity resolution does not imply corpus-scope eligibility.

## Downstream caution

A source-light active W is not recoverable by joining only
through work_identity_map. Downstream analysis must explicitly
account for the source-light exception and Edition evidence.

Do not automatically switch the frozen analysis population
or visibility pipelines to this provisional new representation.
