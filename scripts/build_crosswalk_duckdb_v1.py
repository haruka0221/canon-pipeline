from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]

DB = ROOT / "derived/crosswalks/canon_crosswalks.duckdb"

GR = ROOT / "derived/crosswalks/goodreads_work_crosswalk_v1.parquet"
GR_RESIDUAL = ROOT / "derived/goodreads_no_author_singleton_full_v13.tsv"
GR_TRIAGE = ROOT / "derived/goodreads_no_author_singleton_full_v13_temporal_triage.tsv"

WD = ROOT / "derived/crosswalks/work_to_wikidata_v2.parquet"


for p in [GR, GR_RESIDUAL, GR_TRIAGE, WD]:
    assert p.exists(), p


def sql_path(p):
    return p.resolve().as_posix().replace("'", "''")


con = duckdb.connect(str(DB))


# ============================================================
# 1. Versioned physical snapshots
#
# TSV / Parquet remain the canonical portable storage.
# These DuckDB tables are reproducible query-layer snapshots.
# ============================================================

con.execute("DROP TABLE IF EXISTS goodreads_work_crosswalk_v1_data")
con.execute(
    f"""
    CREATE TABLE goodreads_work_crosswalk_v1_data AS
    SELECT *
    FROM read_parquet('{sql_path(GR)}')
    """
)

con.execute("DROP TABLE IF EXISTS goodreads_singleton_full_residual_v13_data")
con.execute(
    f"""
    CREATE TABLE goodreads_singleton_full_residual_v13_data AS
    SELECT *
    FROM read_csv(
        '{sql_path(GR_RESIDUAL)}',
        delim = '\t',
        header = true,
        all_varchar = true
    )
    """
)

con.execute("DROP TABLE IF EXISTS goodreads_singleton_full_triage_v13_data")
con.execute(
    f"""
    CREATE TABLE goodreads_singleton_full_triage_v13_data AS
    SELECT *
    FROM read_csv(
        '{sql_path(GR_TRIAGE)}',
        delim = '\t',
        header = true,
        all_varchar = true
    )
    """
)

con.execute("DROP TABLE IF EXISTS wikidata_work_crosswalk_v2_data")
con.execute(
    f"""
    CREATE TABLE wikidata_work_crosswalk_v2_data AS
    SELECT *
    FROM read_parquet('{sql_path(WD)}')
    """
)


# ============================================================
# 2. Registry
# ============================================================

con.execute("DROP TABLE IF EXISTS crosswalk_dataset_registry")

con.execute(
    """
    CREATE TABLE crosswalk_dataset_registry (
        dataset_name VARCHAR,
        version VARCHAR,
        row_count BIGINT,
        source_file VARCHAR,
        role VARCHAR,
        notes VARCHAR
    )
    """
)

registry_rows = [
    (
        "goodreads_work_crosswalk",
        "v1",
        34789,
        "derived/crosswalks/goodreads_work_crosswalk_v1.parquet",
        "canonical crosswalk baseline",
        "Built from Goodreads resolution v13; future retrieval-assisted updates must create a later version rather than overwrite v1.",
    ),
    (
        "goodreads_singleton_full_residual",
        "v13",
        909,
        "derived/goodreads_no_author_singleton_full_v13.tsv",
        "unresolved audit subset",
        "Singleton FULL-title candidates remaining unresolved after Goodreads resolution v13.",
    ),
    (
        "goodreads_singleton_full_triage",
        "v13",
        909,
        "derived/goodreads_no_author_singleton_full_v13_temporal_triage.tsv",
        "unresolved triage subset",
        "Temporal triage is prioritization evidence only and is not a hard identity rule.",
    ),
    (
        "wikidata_work_crosswalk",
        "v2",
        34789,
        "derived/crosswalks/work_to_wikidata_v2.parquet",
        "Wikidata work crosswalk",
        "Existing corrected Wikidata work crosswalk; included for cross-source querying.",
    ),
]

con.executemany(
    """
    INSERT INTO crosswalk_dataset_registry
    VALUES (?, ?, ?, ?, ?, ?)
    """,
    registry_rows,
)


# ============================================================
# 3. Goodreads crosswalk views
# ============================================================

views = [
    "goodreads_crosswalk_v1",
    "goodreads_matches_v1",
    "goodreads_no_matches_v1",
    "goodreads_no_candidate_v1",
    "goodreads_ambiguous_v1",
    "goodreads_provisional_candidates_v1",
    "goodreads_singleton_full_unresolved_v1",
    "goodreads_singleton_full_plausible_v1",
    "goodreads_singleton_full_temporal_conflict_v1",
    "goodreads_singleton_full_year_missing_v1",
    "goodreads_singleton_full_older_manifestation_v1",
    "goodreads_with_wikidata_v1",
]

for v in views:
    con.execute(f"DROP VIEW IF EXISTS {v}")


con.execute(
    """
    CREATE VIEW goodreads_crosswalk_v1 AS
    SELECT *
    FROM goodreads_work_crosswalk_v1_data
    """
)

con.execute(
    """
    CREATE VIEW goodreads_matches_v1 AS
    SELECT *
    FROM goodreads_crosswalk_v1
    WHERE crosswalk_decision = 'MATCH'
    """
)

con.execute(
    """
    CREATE VIEW goodreads_no_matches_v1 AS
    SELECT *
    FROM goodreads_crosswalk_v1
    WHERE crosswalk_decision = 'NO_MATCH'
    """
)

con.execute(
    """
    CREATE VIEW goodreads_no_candidate_v1 AS
    SELECT *
    FROM goodreads_crosswalk_v1
    WHERE crosswalk_decision = 'NO_CANDIDATE'
    """
)

con.execute(
    """
    CREATE VIEW goodreads_ambiguous_v1 AS
    SELECT *
    FROM goodreads_crosswalk_v1
    WHERE crosswalk_decision = 'AMBIGUOUS'
    """
)

con.execute(
    """
    CREATE VIEW goodreads_provisional_candidates_v1 AS
    SELECT *
    FROM goodreads_crosswalk_v1
    WHERE crosswalk_decision = 'AMBIGUOUS'
      AND candidate_goodreads_work_id IS NOT NULL
      AND candidate_goodreads_work_id <> ''
    """
)


# ============================================================
# 4. 909-row unresolved singleton-FULL queue
# ============================================================

con.execute(
    """
    CREATE VIEW goodreads_singleton_full_unresolved_v1 AS
    SELECT
        -- ----------------------------------------------------
        -- Canonical crosswalk state
        -- ----------------------------------------------------
        g.source_record_id,
        g.ol_work_key,
        g.source_title,
        g.source_author_name,
        g.source_author_keys,
        g.source_first_publish_year,
        g.scope_flag,

        g.crosswalk_decision,
        g.processing_status,
        g.resolution_status_detail,
        g.goodreads_candidate_count,
        g.goodreads_strongest_title_evidence,

        -- Accepted Goodreads identity.
        -- This is blank for the unresolved 909-row queue.
        g.goodreads_work_id
            AS accepted_goodreads_work_id,

        g.review_needed,

        -- ----------------------------------------------------
        -- Additional OL evidence retained for review
        -- ----------------------------------------------------
        t.subject_keys_str,
        t.canonical,

        -- ----------------------------------------------------
        -- Unresolved singleton-FULL candidate evidence
        --
        -- These fields describe a candidate only.
        -- They must not be interpreted as an accepted match.
        -- ----------------------------------------------------
        t.goodreads_work_id
            AS unresolved_candidate_goodreads_work_id,

        t.title_match_type
            AS unresolved_candidate_title_match_type,

        t.gr_original_title
            AS unresolved_candidate_original_title,

        t.gr_original_publication_year
            AS unresolved_candidate_original_publication_year,

        t.matched_book_titles
            AS unresolved_candidate_matched_book_titles,

        t.goodreads_contributors
            AS unresolved_candidate_contributors,

        t.source_batch
            AS unresolved_candidate_source_batch,

        -- ----------------------------------------------------
        -- Temporal triage evidence
        -- ----------------------------------------------------
        t.ol_year_num,
        t.gr_year_num,
        t.signed_year_diff,
        t.temporal_triage

    FROM goodreads_crosswalk_v1 AS g
    JOIN goodreads_singleton_full_triage_v13_data AS t
      ON g.ol_work_key = t.work_key
    WHERE g.crosswalk_decision = 'AMBIGUOUS'
    """
)

con.execute(
    """
    CREATE VIEW goodreads_singleton_full_plausible_v1 AS
    SELECT *
    FROM goodreads_singleton_full_unresolved_v1
    WHERE temporal_triage = 'TEMPORALLY_PLAUSIBLE_UNRESOLVED'
    """
)

con.execute(
    """
    CREATE VIEW goodreads_singleton_full_temporal_conflict_v1 AS
    SELECT *
    FROM goodreads_singleton_full_unresolved_v1
    WHERE temporal_triage = 'TEMPORAL_CONFLICT_GR_MUCH_NEWER'
    """
)

con.execute(
    """
    CREATE VIEW goodreads_singleton_full_year_missing_v1 AS
    SELECT *
    FROM goodreads_singleton_full_unresolved_v1
    WHERE temporal_triage = 'YEAR_MISSING'
    """
)

con.execute(
    """
    CREATE VIEW goodreads_singleton_full_older_manifestation_v1 AS
    SELECT *
    FROM goodreads_singleton_full_unresolved_v1
    WHERE temporal_triage = 'POSSIBLE_OLDER_WORK_MANIFESTATION'
    """
)


# ============================================================
# 5. Cross-source Goodreads + Wikidata view
# ============================================================

con.execute(
    """
    CREATE VIEW goodreads_with_wikidata_v1 AS
    SELECT
        g.*,
        w.wikidata_qid,
        w.decision AS wikidata_crosswalk_decision,
        w.confidence AS wikidata_crosswalk_confidence,
        w.resolution_stage AS wikidata_resolution_stage,
        w.correction_applied AS wikidata_correction_applied,
        w.correction_type AS wikidata_correction_type
    FROM goodreads_crosswalk_v1 AS g
    LEFT JOIN wikidata_work_crosswalk_v2_data AS w
      ON g.ol_work_id = w.ol_work_id
    """
)


# ============================================================
# 6. Integrity audit
# ============================================================

def count(q):
    return con.execute(q).fetchone()[0]


assert count(
    "SELECT COUNT(*) FROM goodreads_crosswalk_v1"
) == 34789

assert count(
    "SELECT COUNT(*) FROM goodreads_matches_v1"
) == 7624

assert count(
    "SELECT COUNT(*) FROM goodreads_no_matches_v1"
) == 15

assert count(
    "SELECT COUNT(*) FROM goodreads_no_candidate_v1"
) == 22465

assert count(
    "SELECT COUNT(*) FROM goodreads_ambiguous_v1"
) == 4685

assert count(
    "SELECT COUNT(*) FROM goodreads_provisional_candidates_v1"
) == 592

assert count(
    "SELECT COUNT(*) FROM goodreads_singleton_full_unresolved_v1"
) == 909

assert count(
    "SELECT COUNT(*) FROM goodreads_singleton_full_plausible_v1"
) == 227

assert count(
    "SELECT COUNT(*) FROM goodreads_singleton_full_temporal_conflict_v1"
) == 584

assert count(
    "SELECT COUNT(*) FROM goodreads_singleton_full_year_missing_v1"
) == 73

assert count(
    "SELECT COUNT(*) FROM goodreads_singleton_full_older_manifestation_v1"
) == 25

assert count(
    "SELECT COUNT(*) FROM goodreads_with_wikidata_v1"
) == 34789

assert count(
    """
    SELECT COUNT(*)
    FROM goodreads_crosswalk_v1
    WHERE crosswalk_decision = 'MATCH'
      AND (
          goodreads_work_id IS NULL
          OR goodreads_work_id = ''
      )
    """
) == 0

assert count(
    """
    SELECT COUNT(*)
    FROM goodreads_crosswalk_v1
    WHERE crosswalk_decision <> 'MATCH'
      AND goodreads_work_id IS NOT NULL
      AND goodreads_work_id <> ''
    """
) == 0


print("=== DUCKDB CROSSWALK LAYER V1 ===")
print("database:", DB)

print("\nGoodreads crosswalk:", count(
    "SELECT COUNT(*) FROM goodreads_crosswalk_v1"
))
print("  MATCH:", count(
    "SELECT COUNT(*) FROM goodreads_matches_v1"
))
print("  NO_MATCH:", count(
    "SELECT COUNT(*) FROM goodreads_no_matches_v1"
))
print("  NO_CANDIDATE:", count(
    "SELECT COUNT(*) FROM goodreads_no_candidate_v1"
))
print("  AMBIGUOUS:", count(
    "SELECT COUNT(*) FROM goodreads_ambiguous_v1"
))
print("  provisional candidates:", count(
    "SELECT COUNT(*) FROM goodreads_provisional_candidates_v1"
))

print("\nSingleton FULL unresolved:", count(
    "SELECT COUNT(*) FROM goodreads_singleton_full_unresolved_v1"
))
print("  plausible:", count(
    "SELECT COUNT(*) FROM goodreads_singleton_full_plausible_v1"
))
print("  temporal conflict:", count(
    "SELECT COUNT(*) FROM goodreads_singleton_full_temporal_conflict_v1"
))
print("  year missing:", count(
    "SELECT COUNT(*) FROM goodreads_singleton_full_year_missing_v1"
))
print("  older manifestation:", count(
    "SELECT COUNT(*) FROM goodreads_singleton_full_older_manifestation_v1"
))

print("\nGoodreads + Wikidata joined rows:", count(
    "SELECT COUNT(*) FROM goodreads_with_wikidata_v1"
))

print("\nALL DUCKDB AUDITS: PASS")

con.close()
