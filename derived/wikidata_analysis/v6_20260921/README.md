# Wikidata v6 Analysis Store

Derived from the frozen Wikidata v6 production resolution:

- source tag: `wikidata-v6-production-20260921`
- source commit: `41e1076`
- source population: 34,789 Open Library Works

## Data grains

### `wikidata_resolution_34789.parquet`

One row per Open Library Work.

- rows: 34,789
- unique target IDs: 34,789
- MATCH: 8,442
- NO_MATCH: 25,989
- AMBIGUOUS: 358

### `wikidata_matches_8442.parquet`

One row per matched Open Library Work.

- rows: 8,442
- unique Open Library Work IDs: 8,442
- distinct matched Wikidata QIDs: 6,852

Multiple Open Library Work records may resolve to the same conceptual
Wikidata work. Therefore this table must not be interpreted as containing
8,442 distinct Wikidata works.

### `wikidata_matches_8442.csv`

Human-readable/shareable representation of the MATCH table.

### `wikidata_analysis.duckdb`

Rebuildable analytical database containing:

- `resolution_all`
- `wikidata_matches`
- `resolution_counts`

The DuckDB file is treated as a rebuildable local analytical artifact,
not the canonical source.

## Analytical unit

For Open Library population-level analysis, use the 8,442 matched
Open Library Work rows.

For Wikidata-item-level enrichment or API/dump retrieval, deduplicate
`selected_qid` first. There are 6,852 distinct QIDs.

Example:

```sql
SELECT DISTINCT selected_qid
FROM wikidata_matches;
````

## Provenance

The build script verifies the SHA256 of the frozen input before creating
any derived files. See `build_summary.json` and `SHA256SUMS.txt`.

Do not edit the derived Parquet/CSV files manually. Rebuild them with:

```bash
python scripts/build_wikidata_analysis_store.py
```

