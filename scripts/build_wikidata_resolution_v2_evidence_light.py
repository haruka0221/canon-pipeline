#!/usr/bin/env python3

import argparse
import bz2
import sqlite3
import time
from datetime import datetime

import orjson

from build_wikidata_resolution_v2_evidence import (
    NORMALIZATION_VERSION,
    SELECTED_PROPS,
    load_targets,
    author_keys_for_wikidata_name,
    normalize_v2,
    en_value,
    en_aliases,
    stated_titles,
    entity_row,
)


def init_db(path):
    con = sqlite3.connect(path)

    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA temp_store=MEMORY")

    con.executescript("""
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT
    );

    -- Frozen Open Library source records.
    -- One row is one OL Work record, NOT necessarily one conceptual work.
    CREATE TABLE IF NOT EXISTS source_targets (
        target_id TEXT PRIMARY KEY,
        raw_title TEXT,
        raw_author TEXT,
        ol_first_publish_year_raw TEXT,
        author_key_v2 TEXT,
        title_key_v2 TEXT
    );

    -- Author-resolution evidence only.
    -- Multiple candidate QIDs are explicitly allowed.
    CREATE TABLE IF NOT EXISTS target_author_matches_v2 (
        target_id TEXT NOT NULL,
        author_key_v2 TEXT NOT NULL,
        author_qid TEXT NOT NULL,
        matched_text TEXT NOT NULL,
        source TEXT NOT NULL,
        PRIMARY KEY (
            target_id,
            author_qid,
            matched_text,
            source
        )
    );

    -- Direct title evidence only.
    -- N:1 and 1:N mappings are explicitly allowed.
    CREATE TABLE IF NOT EXISTS target_title_matches_v2 (
        target_id TEXT NOT NULL,
        title_key_v2 TEXT NOT NULL,
        qid TEXT NOT NULL,
        matched_text TEXT NOT NULL,
        source TEXT NOT NULL,
        PRIMARY KEY (
            target_id,
            qid,
            matched_text,
            source
        )
    );

    -- Detailed Wikidata evidence for entities directly encountered
    -- through author-name or title matching.
    --
    -- QID is external evidence, NOT the project's conceptual-work ID.
    CREATE TABLE IF NOT EXISTS wikidata_entities_v2 (
        qid TEXT PRIMARY KEY,
        label_en TEXT,
        description_en TEXT,
        aliases_en_json TEXT,

        p31_json TEXT,
        p106_json TEXT,
        p50_json TEXT,
        p629_json TEXT,
        p577_json TEXT,
        p1476_json TEXT,
        p407_json TEXT,
        p655_json TEXT,
        p98_json TEXT,
        p747_json TEXT,
        p9745_json TEXT,
        p123_json TEXT,
        p291_json TEXT,

        has_enwiki INTEGER,
        wikidata_modified TEXT,
        wikidata_lastrevid TEXT,

        raw_selected_claims_json TEXT,
        search_text TEXT
    );
    """)

    meta = {
        "normalization_version": NORMALIZATION_VERSION,
        "created_at": datetime.now().astimezone().isoformat(),

        "population_policy":
            "34,789 Open Library Work records are a frozen source "
            "population, not final conceptual works",

        "year_policy":
            "Open Library and Wikidata dates are retained as "
            "source-specific evidence; no date is used here as a "
            "hard identity-resolution filter",

        "qid_policy":
            "Wikidata QIDs are external entity-resolution evidence, "
            "not project conceptual-work IDs",

        "cardinality_policy":
            "many OL targets to one QID and one OL target to many "
            "candidate QIDs are allowed",

        "candidate_policy":
            "this database stores direct author/title evidence only; "
            "author-to-work P50 expansion is performed on demand "
            "against the frozen base index",

        "selected_properties":
            ",".join(SELECTED_PROPS),
    }

    con.executemany(
        "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
        list(meta.items()),
    )

    con.commit()
    return con


def insert_source_targets(con, rows):
    con.executemany("""
        INSERT OR REPLACE INTO source_targets (
            target_id,
            raw_title,
            raw_author,
            ol_first_publish_year_raw,
            author_key_v2,
            title_key_v2
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, rows)

    con.commit()


def flush(
    con,
    author_matches,
    title_matches,
    entity_rows,
):
    if author_matches:
        con.executemany("""
            INSERT OR IGNORE INTO target_author_matches_v2 (
                target_id,
                author_key_v2,
                author_qid,
                matched_text,
                source
            )
            VALUES (?, ?, ?, ?, ?)
        """, author_matches)

    if title_matches:
        con.executemany("""
            INSERT OR IGNORE INTO target_title_matches_v2 (
                target_id,
                title_key_v2,
                qid,
                matched_text,
                source
            )
            VALUES (?, ?, ?, ?, ?)
        """, title_matches)

    if entity_rows:
        con.executemany("""
            INSERT OR REPLACE INTO wikidata_entities_v2 (
                qid,
                label_en,
                description_en,
                aliases_en_json,

                p31_json,
                p106_json,
                p50_json,
                p629_json,
                p577_json,
                p1476_json,
                p407_json,
                p655_json,
                p98_json,
                p747_json,
                p9745_json,
                p123_json,
                p291_json,

                has_enwiki,
                wikidata_modified,
                wikidata_lastrevid,

                raw_selected_claims_json,
                search_text
            )
            VALUES (
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?
            )
        """, entity_rows)

    con.commit()


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument("--dump", required=True)
    ap.add_argument("--population", required=True)
    ap.add_argument("--db", required=True)

    ap.add_argument(
        "--progress-every",
        type=int,
        default=250000,
    )

    args = ap.parse_args()

    (
        source_rows,
        author_key_to_targets,
        title_key_to_targets,
    ) = load_targets(args.population)

    author_keys = set(author_key_to_targets)
    title_keys = set(title_key_to_targets)

    print("source targets:", len(source_rows))
    print("unique author keys v2:", len(author_keys))
    print("unique title keys v2:", len(title_keys))

    con = init_db(args.db)
    insert_source_targets(con, source_rows)

    author_match_batch = []
    title_match_batch = []

    # One row per directly matched Wikidata QID.
    entity_batch = {}

    n_entities = 0
    bad_json = 0
    started = time.time()

    with bz2.open(args.dump, "rb") as f:
        for raw in f:
            raw = raw.strip()

            if not raw or raw in {b"[", b"]"}:
                continue

            if raw.endswith(b","):
                raw = raw[:-1]

            try:
                ent = orjson.loads(raw)
            except Exception:
                bad_json += 1
                continue

            n_entities += 1

            qid = ent.get("id", "")
            if not qid:
                continue

            label_en = en_value(ent.get("labels", {}))
            aliases = en_aliases(ent)

            entity_matched = False

            # ----------------------------------------------------------
            # AUTHOR EVIDENCE
            # ----------------------------------------------------------
            #
            # Exact equality after normalization v2.
            # Do not force Q5 here:
            # pseudonyms, collective authors, etc. may need review later.
            # P31/P106/description are retained for later discrimination.
            # ----------------------------------------------------------

            author_hits = {}

            for source, value in (
                [("label_en", label_en)]
                + [("alias_en", x) for x in aliases]
            ):
                for key in author_keys_for_wikidata_name(value):
                    if (
                        key in author_keys
                        and key not in author_hits
                    ):
                        author_hits[key] = (value, source)

            for key, (value, source) in author_hits.items():
                for target_id in author_key_to_targets[key]:
                    author_match_batch.append((
                        target_id,
                        key,
                        qid,
                        value,
                        source,
                    ))

                entity_matched = True

            # ----------------------------------------------------------
            # TITLE EVIDENCE
            # ----------------------------------------------------------

            title_hits = {}

            for source, value in (
                [("label_en", label_en)]
                + [("alias_en", x) for x in aliases]
            ):
                key = normalize_v2(value)

                if (
                    key in title_keys
                    and key not in title_hits
                ):
                    title_hits[key] = (value, source)

            p1476 = stated_titles(ent)

            for x in p1476:
                value = x["text"]
                key = normalize_v2(value)

                if (
                    key in title_keys
                    and key not in title_hits
                ):
                    title_hits[key] = (
                        value,
                        "P1476:" + x.get("language", ""),
                    )

            for key, (value, source) in title_hits.items():
                for target_id in title_key_to_targets[key]:
                    title_match_batch.append((
                        target_id,
                        key,
                        qid,
                        value,
                        source,
                    ))

                entity_matched = True

            # Keep detailed evidence only for directly matched entities.
            if entity_matched:
                entity_batch[qid] = entity_row(
                    ent,
                    label_en,
                    aliases,
                )

            if n_entities % 10000 == 0:
                flush(
                    con,
                    author_match_batch,
                    title_match_batch,
                    list(entity_batch.values()),
                )

                author_match_batch.clear()
                title_match_batch.clear()
                entity_batch.clear()

            if (
                args.progress_every
                and n_entities % args.progress_every == 0
            ):
                elapsed = time.time() - started
                rate = n_entities / elapsed if elapsed else 0

                print(
                    f"entities={n_entities:,}  "
                    f"rate={rate:,.0f}/s  "
                    f"elapsed={elapsed/3600:.2f}h  "
                    f"bad={bad_json}",
                    flush=True,
                )

    flush(
        con,
        author_match_batch,
        title_match_batch,
        list(entity_batch.values()),
    )

    print("Building indexes...", flush=True)

    con.executescript("""
    CREATE INDEX IF NOT EXISTS idx_source_author_v2
        ON source_targets(author_key_v2);

    CREATE INDEX IF NOT EXISTS idx_source_title_v2
        ON source_targets(title_key_v2);

    CREATE INDEX IF NOT EXISTS idx_author_target_v2
        ON target_author_matches_v2(target_id);

    CREATE INDEX IF NOT EXISTS idx_author_key_v2
        ON target_author_matches_v2(author_key_v2);

    CREATE INDEX IF NOT EXISTS idx_author_qid_v2
        ON target_author_matches_v2(author_qid);

    CREATE INDEX IF NOT EXISTS idx_title_target_v2
        ON target_title_matches_v2(target_id);

    CREATE INDEX IF NOT EXISTS idx_title_key_v2
        ON target_title_matches_v2(title_key_v2);

    CREATE INDEX IF NOT EXISTS idx_title_qid_v2
        ON target_title_matches_v2(qid);
    """)

    con.commit()

    print("\nFINAL COUNTS")

    for table in [
        "source_targets",
        "target_author_matches_v2",
        "target_title_matches_v2",
        "wikidata_entities_v2",
    ]:
        n = con.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]

        print(f"{table}: {n:,}")

    author_targets = con.execute("""
        SELECT COUNT(DISTINCT target_id)
        FROM target_author_matches_v2
    """).fetchone()[0]

    title_targets = con.execute("""
        SELECT COUNT(DISTINCT target_id)
        FROM target_title_matches_v2
    """).fetchone()[0]

    either_targets = con.execute("""
        SELECT COUNT(*)
        FROM source_targets s
        WHERE EXISTS (
            SELECT 1
            FROM target_author_matches_v2 a
            WHERE a.target_id = s.target_id
        )
        OR EXISTS (
            SELECT 1
            FROM target_title_matches_v2 t
            WHERE t.target_id = s.target_id
        )
    """).fetchone()[0]

    print("targets with direct author evidence:", f"{author_targets:,}")
    print("targets with direct title evidence:", f"{title_targets:,}")
    print("targets with either direct evidence:", f"{either_targets:,}")

    print("database:", args.db)
    print("bad JSON lines:", bad_json)
    print("done")


if __name__ == "__main__":
    main()
