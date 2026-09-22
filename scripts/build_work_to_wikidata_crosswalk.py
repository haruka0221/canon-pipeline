import json
from pathlib import Path
import duckdb

DB = Path("derived/wikidata_analysis/v6_20260921/wikidata_analysis.duckdb")
OUTDIR = Path("derived/crosswalks")
OUT = OUTDIR / "work_to_wikidata.parquet"
SUMMARY = OUTDIR / "work_to_wikidata_summary.json"

OUTDIR.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(str(DB), read_only=True)

stats = con.execute("""
SELECT
    count(*) AS n_rows,
    count(DISTINCT target_id) AS n_unique_targets,
    count(*) FILTER (WHERE target_id IS NULL) AS null_targets,
    count(*) FILTER (WHERE decision = 'MATCH') AS n_match,
    count(*) FILTER (WHERE decision = 'AMBIGUOUS') AS n_ambiguous,
    count(*) FILTER (WHERE decision = 'NO_MATCH') AS n_no_match
FROM resolution_all
""").fetchone()

(
    n_rows,
    n_unique_targets,
    null_targets,
    n_match,
    n_ambiguous,
    n_no_match,
) = stats

if n_rows != 34789:
    raise ValueError(f"Expected 34789 rows, got {n_rows}")

if n_unique_targets != n_rows:
    raise ValueError(
        f"target_id is not unique: {n_unique_targets} unique / {n_rows} rows"
    )

if null_targets:
    raise ValueError(f"Found {null_targets} null target_ids")

con.execute("""
COPY (
    SELECT
        target_id AS ol_work_id,
        CASE
            WHEN decision = 'MATCH' THEN selected_qid
            ELSE NULL
        END AS wikidata_qid,
        decision,
        confidence,
        resolution_stage,
        decision_source,
        context_safe_fallback
    FROM resolution_all
    ORDER BY target_id
)
TO ?
(FORMAT PARQUET, COMPRESSION ZSTD)
""", [str(OUT)])

check = con.execute("""
SELECT
    count(*) AS rows,
    count(DISTINCT ol_work_id) AS unique_ol_work_ids,
    count(*) FILTER (
        WHERE decision = 'MATCH'
          AND wikidata_qid IS NOT NULL
    ) AS resolved_matches,
    count(*) FILTER (
        WHERE decision <> 'MATCH'
          AND wikidata_qid IS NOT NULL
    ) AS invalid_nonmatch_qids
FROM read_parquet(?)
""", [str(OUT)]).fetchone()

rows, unique_ids, resolved_matches, invalid_nonmatch_qids = check

if rows != 34789:
    raise ValueError(f"Output row mismatch: {rows}")

if unique_ids != 34789:
    raise ValueError(f"Output ID uniqueness problem: {unique_ids}")

if resolved_matches != n_match:
    raise ValueError(
        f"Expected {n_match} resolved MATCH rows, got {resolved_matches}"
    )

if invalid_nonmatch_qids != 0:
    raise ValueError(
        f"{invalid_nonmatch_qids} non-MATCH rows unexpectedly have QIDs"
    )

report = {
    "source_database": str(DB),
    "source_table": "resolution_all",
    "output": str(OUT),
    "rows": rows,
    "unique_ol_work_ids": unique_ids,
    "match": n_match,
    "ambiguous": n_ambiguous,
    "no_match": n_no_match,
    "resolved_wikidata_qids": resolved_matches,
    "rule": "wikidata_qid is populated only when decision == MATCH",
}

SUMMARY.write_text(
    json.dumps(report, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print("DONE")
print("rows:", rows)
print("MATCH:", n_match)
print("AMBIGUOUS:", n_ambiguous)
print("NO_MATCH:", n_no_match)
print("parquet:", OUT)
print("summary:", SUMMARY)
