# Open Library Source Population Provenance

Status: authoritative provenance audit
Audit date: 2026-09-28
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

### 2.1 Source-file custody and 2026-09-28 Works dump re-acquisition

The historical population was originally constructed from the Open Library
2026-02-28 Works and Editions snapshot.

The Works dump was first downloaded locally on 2026-03-07 for the historical
population construction. The original local raw Works dump was subsequently
deleted after the derived population artifacts had been created.

On 2026-09-28, the same published Open Library snapshot was re-acquired from
the same Archive.org release for provenance recovery and current source-level
metadata inspection:

```text
source:
https://archive.org/download/ol_dump_2026-02-28/ol_dump_works_2026-02-28.txt.gz

snapshot date:
2026-02-28

re-acquisition date:
2026-09-28

local server path:
/media/hdd1/user/tsutsui/openlibrary/ol_dump_works_2026-02-28.txt.gz

size:
3,920,616,854 bytes

SHA256:
a4714480bd20a7ad41538653d69ed43a012efecfba57cd5194edb2768cfc26ad

gzip integrity check:
passed
```

This is a re-acquisition of the same published 2026-02-28 snapshot, not a new
Open Library snapshot.

No checksum of the original 2026-03-07 local Works dump is known to survive.
Therefore, the re-acquired file can be identified as the same published
snapshot and source artifact, but bit-for-bit identity with the deleted
historical local copy is not independently asserted.

The Editions dump from the same 2026-02-28 snapshot remained preserved on the
analysis server.

The Authors dump was not part of the original population-construction step.
It was acquired later for author-name and author-identity work and should
therefore be documented separately from the Works/Editions population-source
lineage.

### 2.2 2026-09-28 Authors dump re-acquisition

Repository documentation from March 2026 refers to an Open Library Authors
dump named:

```text
raw/ol_dump/ol_dump_authors_2026-02-28.txt.gz
```

and `scripts/build_author_lookup.py` was written to consume that fixed
2026-02-28 Authors snapshot.

During the 2026-09-28 provenance audit, however, the historical local copy of
that file could not be found. A fixed copy of the same published Open Library
2026-02-28 Authors snapshot was therefore re-acquired from Archive.org.

```text
source:
https://archive.org/download/ol_dump_2026-02-28/ol_dump_authors_2026-02-28.txt.gz

snapshot date:
2026-02-28

re-acquisition date:
2026-09-28

local server path:
/media/hdd1/user/tsutsui/openlibrary/ol_dump_authors_2026-02-28.txt.gz

size:
755,365,970 bytes

SHA256:
9e28a45c3db56f7d89eceaa01024865bacc458c84fc83d29044f6897987a363d

gzip integrity check:
passed
```

A separate later file is preserved at:

```text
/media/hdd1/Openlibrary/ol_dump_authors_latest.txt.gz
```

That file is a distinct later Authors dump and must not be treated as the
2026-02-28 source snapshot.

The fixed 2026-02-28 Authors dump is used when source-native author records
need to be aligned with the 2026-02-28 Works and Editions snapshot.

### 2.3 Current-target author source layer v1

On 2026-09-28 the project froze a new source-native author layer for the
34,789 **current** Open Library analysis targets:

```text
release:
openlibrary-author-source-v1

freeze commit:
16d0a29

builder:
scripts/build_openlibrary_author_source_v1.py

builder commit used for the frozen run:
0d77b598b38f9b96c9870fafe8a57a344a8fca7a
```

This layer was created because the current analysis-target release includes
three explicit Open Library target corrections. The historical population
row may therefore retain historical `author_keys` associated with a
superseded source Work. The new layer does not use those historical
`author_keys` or historical `author_name` fields as source truth.

Instead, it reconstructs author evidence through the following path:

```text
openlibrary_analysis_targets_v1
        │
        │ current_ol_work_id
        ▼
fixed Open Library Works dump, 2026-02-28
        │
        │ source-native Work.authors entries
        ▼
Work → Author source-native edges
        │
        ▼
fixed Open Library Authors dump, 2026-02-28
        │
        ├── name
        ├── personal_name
        ├── fuller_name
        └── alternate_names
```

The fixed inputs used by the frozen run were:

```text
current-target artifact:
derived/identity/openlibrary_analysis_targets_v1.parquet

target artifact SHA256:
7200fe0721a2a112da8351aea2561914c71322ccac45764d97c425ef5046ff21

Works dump:
/media/hdd1/user/tsutsui/openlibrary/ol_dump_works_2026-02-28.txt.gz

Works SHA256:
a4714480bd20a7ad41538653d69ed43a012efecfba57cd5194edb2768cfc26ad

Authors dump:
/media/hdd1/user/tsutsui/openlibrary/ol_dump_authors_2026-02-28.txt.gz

Authors SHA256:
9e28a45c3db56f7d89eceaa01024865bacc458c84fc83d29044f6897987a363d
```

The production run was executed in the clean detached worktree:

```text
/home/tsutsui/canon-pipeline-openalex
```

with:

```text
Python executable:
/home/tsutsui/venvs/canon/bin/python3

Python:
3.12.3

pandas:
3.0.5

pyarrow:
25.0.1

builder script SHA256:
943d57f8374ea9174ebd58d12954acb5a097e77394a44eb5f9e81fa34b5cd29c

run started:
2026-09-28T12:36:45.134502+00:00

run finished:
2026-09-28T12:38:40.669160+00:00
```

The frozen output directory is:

```text
derived/openlibrary_author_source_v1/
```

and contains synchronized TSV and Parquet releases for:

```text
openlibrary_current_work_records_v1
openlibrary_current_work_authors_v1
openlibrary_author_records_v1
openlibrary_author_names_v1
openlibrary_missing_authors_v1
```

plus:

```text
openlibrary_author_source_v1_manifest.json
```

The frozen release contains:

```text
current Open Library targets:          34,789
Work → Author edges:                   37,652
unique referenced Author IDs:          16,405
Author records found:                  16,402
Author records missing:                     3
author-name evidence rows:             57,510

targets without author entries:           354
targets with >1 author entry:            1,730

name non-empty:                        16,402
personal_name non-empty:               14,277
fuller_name non-empty:                     82
```

The three unresolved Author references are:

```text
OL1176752W   The Dewy Morn: A Novel
  author ordinal 1 → /authors/OL6789084A

OL36050583W  Jude the Obscure
  author ordinal 0 → /authors/OL6817526A

OL41363589W  Tales of the Fish Patrol
  author ordinal 0 → /authors/OL9258086A
```

All three references are present in the fixed 2026-02-28 Works dump, but
none of the three Author IDs occurs in either the fixed 2026-02-28 Authors
dump or the separately preserved September 2026 `authors_latest` dump.
They are therefore retained as unresolved source references rather than
silently repaired or manually replaced.

The audit also demonstrated why Open Library `Work.authors` must not be
treated as synonymous with a definitive original-author list. For example,
the current Open Library Work for *The Prisoner of Zenda* contains 16 author
edges: Anthony Hope is ordinal 0, alongside 15 additional person or
organization records, including Gary Hoppenstand, Diane Mowat, Alan Marks,
and Smidgen Press. The source `authors` relation itself does not establish
that all of these records represent original literary authorship.
Accordingly, every source-native edge and its ordinal are preserved, while
selection of a retrieval author is a separate downstream decision.

The production run was preceded by an independent pre-freeze run. After
execution-provenance metadata was added to the builder, the production run
was repeated from a clean Git worktree. All ten data outputs (five TSV and
five Parquet files) were byte-for-byte identical between the two runs by
SHA256 comparison.

The pre-freeze audit copy is retained outside the repository at:

```text
/media/hdd1/user/tsutsui/openlibrary/audit/
openlibrary_author_source_v1_prefreeze_20260928/
```

The production execution log is retained locally at:

```text
/home/tsutsui/canon-pipeline-openalex/
logs/openlibrary_author_source_v1_20260928.log
```

The log is intentionally not a repository artifact because `logs/*.log` is
ignored. Machine-readable release provenance, input/output hashes, counts,
and execution metadata are instead preserved in the committed manifest.

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
