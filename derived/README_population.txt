# Population Definition

## Current authoritative status

The project preserves the historical Open Library release
`population-dump-v1` as a frozen source population.

- Source: Open Library Works + Editions dumps
- Snapshot date: 2026-02-28
- Frozen artifact:
  `derived/ol_dump_population_fiction_2026-02-28.tsv`
- Source-record count: 34,789 Open Library Work records
- SHA256:
  `70630644b8300088a8ba1f46c7a2eaa81cc37a67e251e1068e217fbf86be9ba7`

These 34,789 rows are historical Open Library source records.

They must not be interpreted as:

- 34,789 definitively resolved conceptual literary works;
- 34,789 works proven to have been originally published in 1880–1950;
- the final dissertation analysis population.

For the full reconstruction and provenance audit, see:

`docs/POPULATION_PROVENANCE.md`

For the machine-readable release record, see:

`derived/population_dump_v1_manifest.json`

For the current identity and scope policy, see:

`docs/IDENTITY_MODEL.md`

## Historical construction note

Historical documentation from 2026-03 records an
"inclusion-based fiction filter (18 keys)" producing the 34,789-row
release.

The exact original one-off filtering code and exact historical
18-signal list were not preserved.

A 2026-09-27 reconstruction found a sufficient 17-signal OR rule that
reproduces the frozen 34,789 `work_key` set exactly:

- reconstructed: 34,789
- extra: 0
- missing: 0
- exact set equality: True

The reconstructed 17-signal rule is documented in
`docs/POPULATION_PROVENANCE.md`. It must not be described as the
recovered original historical 18-signal rule.

## Historical year semantics

The historical column name `first_publish_year` does not represent a
resolved conceptual-work original publication year.

In the surviving dump-building implementation it represents the
minimum year parsed from linked Open Library Edition `publish_date`
values used by the historical population workflow.

Future period decisions are therefore handled separately through
versioned year-evidence and scope-resolution layers.

## Historical provenance record

`derived/prov.json` is preserved as the provenance record created in
March 2026.

It contains a simplified historical description of the population
pipeline and is not silently rewritten to incorporate the September
2026 audit.

The later authoritative clarification is:

`docs/POPULATION_PROVENANCE.md`

## Pilot study — superseded

Before the dump-based population was adopted, the project used the Open
Library Search API and produced smaller API-based pilot populations.

Those pilot artifacts are retained as historical research records but
do not define `population-dump-v1`.

## Policy

The frozen 34,789 Open Library rows are never silently deleted or
rewritten when later identity, temporal, or scope resolution changes
the analytical population.

Future flow:

frozen source population
→ identity resolution
→ project-level conceptual works
→ year evidence / temporal resolution
→ scope resolution
→ versioned analysis population
