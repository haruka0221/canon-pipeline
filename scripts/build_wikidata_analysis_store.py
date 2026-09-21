#!/usr/bin/env python3

import hashlib
import json
import platform
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


EXPECTED_INPUT_SHA256 = (
    "d1c2b08b4f05df8ac738fbcb987f8fcce98576d29585ebab502ccf1b513396f5"
)

INPUT = Path(
    "derived/wikidata_production/full_34789_v6_20260918/"
    "final_resolution_v6_34789.tsv"
)

OUT = Path("derived/wikidata_analysis/v6_20260921")

ALL_PARQUET = OUT / "wikidata_resolution_34789.parquet"
MATCH_PARQUET = OUT / "wikidata_matches_8442.parquet"
MATCH_CSV = OUT / "wikidata_matches_8442.csv"
DUCKDB = OUT / "wikidata_analysis.duckdb"
SUMMARY = OUT / "build_summary.json"
SHA_FILE = OUT / "SHA256SUMS.txt"


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def parse_json_list(value):
    if value is None or pd.isna(value) or value == "":
        return []
    x = json.loads(value)
    if not isinstance(x, list):
        raise ValueError(f"Expected JSON list, got: {value!r}")
    return [str(v) for v in x]


def parse_bool(value):
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"true", "1"}:
        return True
    if s in {"false", "0", ""}:
        return False
    raise ValueError(f"Unexpected boolean value: {value!r}")


def sql_path(path):
    return str(path.resolve()).replace("'", "''")


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    actual_sha = sha256_file(INPUT)
    print("input SHA256:", actual_sha)

    if actual_sha != EXPECTED_INPUT_SHA256:
        raise RuntimeError(
            "Frozen input SHA mismatch.\n"
            f"expected: {EXPECTED_INPUT_SHA256}\n"
            f"actual:   {actual_sha}"
        )

    # Read everything as text first so no identifiers are coerced.
    df = pd.read_csv(
        INPUT,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    if len(df) != 34789:
        raise RuntimeError(f"Expected 34789 rows, got {len(df)}")

    if df["target_id"].duplicated().any():
        raise RuntimeError("Duplicate target_id found")

    # Typed analytical representation.
    df["year"] = pd.to_numeric(df["year"], errors="raise").astype("int16")
    df["candidate_count"] = (
        pd.to_numeric(df["candidate_count"], errors="raise")
        .astype("int32")
    )

    df["alternative_qids"] = df["alternative_qids"].map(parse_json_list)
    df["issue_codes"] = df["issue_codes"].map(parse_json_list)
    df["context_safe_fallback"] = (
        df["context_safe_fallback"].map(parse_bool)
    )

    # Optional scalar values become null in Parquet/DuckDB.
    nullable_string_cols = [
        "selected_qid",
        "confidence",
        "reason",
        "model",
        "prompt_sha256",
    ]

    for col in nullable_string_cols:
        df[col] = df[col].map(lambda x: None if x == "" else x)

    decision_counts = df["decision"].value_counts().to_dict()
    stage_counts = df["resolution_stage"].value_counts().to_dict()

    expected_decisions = {
        "NO_MATCH": 25989,
        "MATCH": 8442,
        "AMBIGUOUS": 358,
    }
    expected_stages = {
        "llm_judge": 24015,
        "candidate_retrieval": 10774,
    }

    if decision_counts != expected_decisions:
        raise RuntimeError(
            f"Unexpected decision counts: {decision_counts}"
        )

    if stage_counts != expected_stages:
        raise RuntimeError(
            f"Unexpected stage counts: {stage_counts}"
        )

    matches = df[df["decision"] == "MATCH"].copy()

    if len(matches) != 8442:
        raise RuntimeError(f"Expected 8442 MATCH rows, got {len(matches)}")

    if matches["selected_qid"].isna().any():
        raise RuntimeError("MATCH row with missing selected_qid")

    if not matches["selected_qid"].str.match(r"^Q[0-9]+$").all():
        raise RuntimeError("Invalid selected_qid in MATCH rows")

    # Explicit stable Parquet schema.
    schema = pa.schema([
        ("target_id", pa.string()),
        ("title", pa.string()),
        ("author", pa.string()),
        ("year", pa.int16()),
        ("candidate_count", pa.int32()),
        ("decision", pa.string()),
        ("selected_qid", pa.string()),
        ("alternative_qids", pa.list_(pa.string())),
        ("confidence", pa.string()),
        ("issue_codes", pa.list_(pa.string())),
        ("reason", pa.string()),
        ("resolution_stage", pa.string()),
        ("decision_source", pa.string()),
        ("model", pa.string()),
        ("prompt_sha256", pa.string()),
        ("context_safe_fallback", pa.bool_()),
    ])

    all_table = pa.Table.from_pandas(
        df,
        schema=schema,
        preserve_index=False,
    )
    match_table = pa.Table.from_pandas(
        matches,
        schema=schema,
        preserve_index=False,
    )

    pq.write_table(
        all_table,
        ALL_PARQUET,
        compression="zstd",
        use_dictionary=True,
    )
    pq.write_table(
        match_table,
        MATCH_PARQUET,
        compression="zstd",
        use_dictionary=True,
    )

    # Human-readable/shareable CSV.
    csv_df = matches.copy()
    for col in ["alternative_qids", "issue_codes"]:
        csv_df[col] = csv_df[col].map(
            lambda x: json.dumps(x, ensure_ascii=False)
        )

    csv_df.to_csv(
        MATCH_CSV,
        index=False,
        encoding="utf-8",
        lineterminator="\n",
    )

    # Clean rebuild of DuckDB analytical store.
    if DUCKDB.exists():
        DUCKDB.unlink()

    con = duckdb.connect(str(DUCKDB))

    con.execute(
        f"""
        CREATE TABLE resolution_all AS
        SELECT * FROM read_parquet('{sql_path(ALL_PARQUET)}')
        """
    )

    con.execute(
        f"""
        CREATE TABLE wikidata_matches AS
        SELECT * FROM read_parquet('{sql_path(MATCH_PARQUET)}')
        """
    )

    con.execute(
        "CREATE INDEX idx_resolution_target "
        "ON resolution_all(target_id)"
    )
    con.execute(
        "CREATE INDEX idx_matches_target "
        "ON wikidata_matches(target_id)"
    )
    con.execute(
        "CREATE INDEX idx_matches_qid "
        "ON wikidata_matches(selected_qid)"
    )

    con.execute("""
        CREATE VIEW resolution_counts AS
        SELECT
            decision,
            resolution_stage,
            COUNT(*) AS n
        FROM resolution_all
        GROUP BY decision, resolution_stage
        ORDER BY decision, resolution_stage
    """)

    duck_all = con.execute(
        "SELECT COUNT(*) FROM resolution_all"
    ).fetchone()[0]

    duck_match = con.execute(
        "SELECT COUNT(*) FROM wikidata_matches"
    ).fetchone()[0]

    duck_unique_targets = con.execute(
        "SELECT COUNT(DISTINCT target_id) FROM resolution_all"
    ).fetchone()[0]

    unique_matched_qids = con.execute(
        "SELECT COUNT(DISTINCT selected_qid) FROM wikidata_matches"
    ).fetchone()[0]

    con.close()

    if duck_all != 34789:
        raise RuntimeError(f"DuckDB all count wrong: {duck_all}")

    if duck_match != 8442:
        raise RuntimeError(f"DuckDB match count wrong: {duck_match}")

    if duck_unique_targets != 34789:
        raise RuntimeError(
            f"DuckDB unique target count wrong: {duck_unique_targets}"
        )

    summary = {
        "input": {
            "path": str(INPUT),
            "sha256": actual_sha,
            "frozen_tag": "wikidata-v6-production-20260921",
            "frozen_commit": "41e1076",
        },
        "rows": {
            "resolution_all": len(df),
            "wikidata_matches": len(matches),
            "unique_matched_qids": unique_matched_qids,
        },
        "decision_counts": decision_counts,
        "resolution_stage_counts": stage_counts,
        "year_range": {
            "min": int(df["year"].min()),
            "max": int(df["year"].max()),
        },
        "representation": {
            "parquet_list_columns": [
                "alternative_qids",
                "issue_codes",
            ],
            "optional_empty_strings_normalized_to_null": (
                nullable_string_cols
            ),
            "parquet_compression": "zstd",
            "csv_scope": "MATCH rows only",
            "duckdb_tables": [
                "resolution_all",
                "wikidata_matches",
            ],
            "duckdb_views": [
                "resolution_counts",
            ],
        },
        "software": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "pyarrow": pa.__version__,
            "duckdb": duckdb.__version__,
        },
    }

    SUMMARY.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # Manifest hashes the generated deliverables + build script.
    manifest_paths = [
        ALL_PARQUET,
        MATCH_PARQUET,
        MATCH_CSV,
        DUCKDB,
        SUMMARY,
        Path("scripts/build_wikidata_analysis_store.py"),
    ]

    with SHA_FILE.open("w", encoding="utf-8") as f:
        for path in manifest_paths:
            f.write(f"{sha256_file(path)}  {path}\n")

    print("\n=== BUILD COMPLETE ===")
    print("all rows:", len(df))
    print("MATCH rows:", len(matches))
    print("unique matched QIDs:", unique_matched_qids)
    print("decision counts:", decision_counts)
    print("stage counts:", stage_counts)

    print("\n=== OUTPUTS ===")
    for p in [
        ALL_PARQUET,
        MATCH_PARQUET,
        MATCH_CSV,
        DUCKDB,
        SUMMARY,
        SHA_FILE,
    ]:
        print(p)

    print("\n=== SHA256 ===")
    print(SHA_FILE.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main()
