# Open Library Source Population Provenance

Status: authoritative provenance audit
Audit date: 2026-09-27
Historical release: `population-dump-v1`

## 1. What the 34,789-row release represents

The historical release

`derived/ol_dump_population_fiction_2026-02-28.tsv`

contains 34,789 Open Library Work source records selected from the
2026-02-28 Open Library dump.

This release is retained as a frozen historical source population.

It must not be described as:

- 34,789 definitively resolved conceptual literary works;
- 34,789 works proven to have been originally published in 1880–1950;
- the final dissertation analysis population.

The Open Library `work_key` remains a source identifier. Project-level
conceptual identity and analytical scope are resolved in later layers.

## 2. Source snapshot

The historical population was derived from the Open Library snapshot
dated 2026-02-28.

Primary dump sources:

- Works dump:
  `raw/ol_dump/ol_dump_works_2026-02-28.txt.gz`
- Editions dump:
  `raw/ol_dump/ol_dump_editions_2026-02-28.txt.gz`

The historical provenance record is preserved in:

`derived/prov.json`

That file is retained as a historical record and is not silently
rewritten to incorporate later audit findings.

## 3. Recoverable historical construction

Git commit `7771e0d` introduced
`scripts/build_population_from_dump.py`.

The surviving script performs the following operations.

### Works-level subject handling

It normalizes Open Library Work subjects and applies the historical
exclusion/protection logic.

### Editions-level language and year handling

For linked Open Library Editions, it:

- detects whether at least one linked edition is marked English;
- parses years from edition `publish_date`;
- records the minimum observed linked-edition year;
- retains records whose minimum observed year is between 1880 and 1950.

The resulting base artifact is:

`derived/ol_dump_population_2026-02-28.tsv`

Audit on 2026-09-27 found:

- parsed records: 2,044,920
- SHA256:
  `1de8541ce871737c37720233ce7ef75079e55040dfe45dc488cd5657f3c80da1`

Historical documentation reported a slightly larger line count because
physical TSV lines and parsed logical records are not identical. Parsed
record counts should be used when describing the population size.

## 4. Historical fiction inclusion step

Git commit `085813c` dated 2026-03-08 records a subsequent:

> inclusion-based fiction filter (18 keys)

and identifies the resulting artifact as:

`derived/ol_dump_population_fiction_2026-02-28.tsv`

with 34,789 records.

The same commit records a 200-record quality audit:

- seed: 20260307
- OK: 189 / 200 (94.5%)
- Uncertain: 6 / 200 (3.0%)
- NG: 5 / 200 (2.5%)

The frozen artifact currently has:

- records: 34,789
- SHA256:
  `70630644b8300088a8ba1f46c7a2eaa81cc37a67e251e1068e217fbf86be9ba7`

## 5. Historical implementation gap

The exact one-off code used for the historical 18-signal inclusion step
was not preserved in the tracked Git history.

The exact original 18-term signal list was also not recovered.

Audit steps performed in September 2026 included:

- inspection of commit `085813c`;
- comparison of historical versions of
  `scripts/build_population_from_dump.py`;
- inspection of surrounding commits;
- search of tracked Git history;
- search of local shell history;
- search of unreachable Git blobs.

No recoverable copy of the original one-off filtering code or exact
18-term list was found.

Therefore, the project must not claim that the exact historical
18-signal implementation has been recovered.

## 6. 2026-09-27 reconstruction audit

The surviving 2,044,920-record base population and the frozen
34,789-record output were compared directly.

A sufficient OR-rule using the following 17 normalized subject signals
reproduces the frozen `work_key` set exactly:

1. `fiction`
2. `juvenile_fiction`
3. `fiction_general`
4. `english_fiction`
5. `short_stories`
6. `romances`
7. `american_fiction`
8. `detective_and_mystery_stories`
9. `science_fiction`
10. `western_stories`
11. `historical_fiction`
12. `dime_novels`
13. `adventure_stories`
14. `love_stories`
15. `war_stories`
16. `novel`
17. `novels`

Verification result:

- reconstructed records: 34,789
- frozen records: 34,789
- extra records: 0
- missing records: 0
- exact `work_key` set equality: True

This 17-signal set is a reconstructed sufficient rule.

It must not be represented as the recovered original historical
18-signal list.

`literary_fiction` is a plausible redundant historical eighteenth
signal because it occurs inside the frozen population and adds no
additional records beyond the reconstructed rule. However, this has not
been independently proven and is not treated as recovered historical
fact.

## 7. Meaning of the historical `first_publish_year` column

The column name `first_publish_year` is historical.

In the surviving dump-building implementation, its value is derived
from the minimum year parsed from linked Open Library Edition
`publish_date` values.

It must therefore be interpreted as historical Open Library
edition-derived year evidence.

It must not automatically be interpreted as:

- the original publication year of the conceptual literary work;
- the first English publication year;
- the publication year of a specific manifestation unless separately
  identified.

Future temporal resolution must preserve source-specific evidence and
distinguish at minimum:

- original work year;
- first English manifestation year;
- manifestation publication year;
- source-reported year.

## 8. Relationship to later enriched population files

The following later artifacts preserve the same frozen Open Library
source-record population while adding source-level information:

- `derived/ol_dump_population_with_canonical.tsv`
- `derived/ol_dump_population_with_author.tsv`

Audit confirmed that their core Open Library source columns correspond
to the frozen 34,789-record population.

The author-enriched population contains 34,789 rows, including 355 rows
without a resolved author name.

## 9. Downstream provenance check

The September 2026 Wikidata production input was reconstructed from the
surviving author-enriched population.

The reconstructed input matched the historical frozen Wikidata
production input SHA256 exactly:

`98c9284dcf381edf2e0e82de19d93ae8c418ba97a72881b43886c2778a2d019d`

This provides an additional downstream check that the surviving frozen
population lineage is consistent with the population used in the
September 2026 production workflow.

## 10. Project policy going forward

`population-dump-v1` is immutable historical source-population
evidence.

Later corrections must not rewrite or delete its source rows.

The forward model is:

```text
frozen source population
    34,789 Open Library Work records
        |
        v
identity resolution
        |
        v
project-level conceptual works
        |
        v
year evidence / temporal resolution
        |
        v
scope resolution
        |
        v
versioned analysis population
```

In particular:

- source identity is distinct from project-level conceptual identity;
- identity resolution is distinct from scope resolution;
- absence from Wikidata, Goodreads, or another external database is not
  evidence of being out of scope;
- later analysis populations must be versioned derived releases;
- historical analyses based directly on the 34,789 rows remain
  historical snapshots and must not be silently recalculated.

## 11. Next implementation steps

After this provenance audit:

1. adopt and verify `docs/IDENTITY_MODEL.md` v0.2;
2. build versioned `work_year_evidence`;
3. define and version `work_scope_resolution`;
4. construct an expanded candidate population to assess false negatives
   created by the historical temporal filtering rule;
5. freeze the primary `period_basis`;
6. only then freeze the final population-dependent OpenAlex production
   target release.
