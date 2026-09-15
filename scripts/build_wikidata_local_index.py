#!/usr/bin/env python3

import argparse
import bz2
import sqlite3
import time
from pathlib import Path

import orjson

from wikidata_resolver_production import normalize_author, normalize_title


def load_keys(path):
    return {
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def en_value(mapping):
    x = mapping.get("en")
    return x.get("value", "") if isinstance(x, dict) else ""


def en_aliases(ent):
    return [
        x.get("value", "")
        for x in ent.get("aliases", {}).get("en", [])
        if x.get("value")
    ]


def claim_item_ids(ent, prop):
    out = []
    seen = set()
    for claim in ent.get("claims", {}).get(prop, []):
        try:
            v = claim["mainsnak"]["datavalue"]["value"]
            qid = v.get("id") if isinstance(v, dict) else None
            if qid and qid not in seen:
                seen.add(qid)
                out.append(qid)
        except Exception:
            pass
    return out


def claim_dates(ent):
    out = []
    seen = set()
    for claim in ent.get("claims", {}).get("P577", []):
        try:
            v = claim["mainsnak"]["datavalue"]["value"]["time"].lstrip("+")
            if v not in seen:
                seen.add(v)
                out.append(v)
        except Exception:
            pass
    return out


def stated_titles(ent):
    out = []
    seen = set()
    for claim in ent.get("claims", {}).get("P1476", []):
        try:
            v = claim["mainsnak"]["datavalue"]["value"]
            if isinstance(v, dict) and v.get("text"):
                key = (v["text"], v.get("language", ""))
                if key not in seen:
                    seen.add(key)
                    out.append({
                        "text": v["text"],
                        "language": v.get("language", ""),
                    })
        except Exception:
            pass
    return out


def dumps(x):
    return orjson.dumps(x).decode("utf-8")


def author_keys_for_name(s):
    if not s:
        return set()
    return {
        normalize_title(s),
        normalize_title(normalize_author(s)),
    } - {""}


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

    CREATE TABLE IF NOT EXISTS people (
        qid TEXT PRIMARY KEY,
        label_en TEXT,
        description_en TEXT,
        aliases_en TEXT,
        names_text TEXT
    );

    CREATE TABLE IF NOT EXISTS p50_edges (
        author_qid TEXT NOT NULL,
        item_qid TEXT NOT NULL,
        PRIMARY KEY (author_qid, item_qid)
    ) WITHOUT ROWID;

    CREATE TABLE IF NOT EXISTS entities (
        qid TEXT PRIMARY KEY,
        label_en TEXT,
        description_en TEXT,
        aliases_en TEXT,
        p31 TEXT,
        p50 TEXT,
        p629 TEXT,
        p577 TEXT,
        p1476 TEXT,
        has_enwiki INTEGER,
        search_text TEXT
    );

    CREATE TABLE IF NOT EXISTS target_author_matches (
        author_key TEXT NOT NULL,
        qid TEXT NOT NULL,
        matched_text TEXT,
        source TEXT,
        PRIMARY KEY (author_key, qid)
    ) WITHOUT ROWID;

    CREATE TABLE IF NOT EXISTS target_title_matches (
        title_key TEXT NOT NULL,
        qid TEXT NOT NULL,
        matched_text TEXT,
        source TEXT,
        PRIMARY KEY (title_key, qid)
    ) WITHOUT ROWID;
    """)
    con.commit()
    return con


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True, type=Path)
    ap.add_argument("--author-keys", required=True, type=Path)
    ap.add_argument("--title-keys", required=True, type=Path)
    ap.add_argument("--db", required=True, type=Path)
    ap.add_argument("--progress-every", type=int, default=250000)
    args = ap.parse_args()

    author_keys = load_keys(args.author_keys)
    title_keys = load_keys(args.title_keys)

    args.db.parent.mkdir(parents=True, exist_ok=True)
    con = init_db(args.db)

    con.execute(
        "INSERT OR REPLACE INTO meta VALUES (?,?)",
        ("source_dump", str(args.dump))
    )
    con.execute(
        "INSERT OR REPLACE INTO meta VALUES (?,?)",
        ("author_key_count", str(len(author_keys)))
    )
    con.execute(
        "INSERT OR REPLACE INTO meta VALUES (?,?)",
        ("title_key_count", str(len(title_keys)))
    )
    con.commit()

    people_batch = []
    edge_batch = []
    entity_batch = []
    author_match_batch = []
    title_match_batch = []

    def flush():
        nonlocal people_batch, edge_batch, entity_batch
        nonlocal author_match_batch, title_match_batch

        if people_batch:
            con.executemany(
                "INSERT OR REPLACE INTO people VALUES (?,?,?,?,?)",
                people_batch
            )
        if edge_batch:
            con.executemany(
                "INSERT OR IGNORE INTO p50_edges VALUES (?,?)",
                edge_batch
            )
        if entity_batch:
            con.executemany(
                "INSERT OR REPLACE INTO entities VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                entity_batch
            )
        if author_match_batch:
            con.executemany(
                "INSERT OR IGNORE INTO target_author_matches VALUES (?,?,?,?)",
                author_match_batch
            )
        if title_match_batch:
            con.executemany(
                "INSERT OR IGNORE INTO target_title_matches VALUES (?,?,?,?)",
                title_match_batch
            )

        con.commit()

        people_batch = []
        edge_batch = []
        entity_batch = []
        author_match_batch = []
        title_match_batch = []

    start = time.time()
    n = 0
    bad = 0

    with bz2.open(args.dump, "rb") as f:
        for raw in f:
            line = raw.strip()

            if not line or line in (b"[", b"]"):
                continue

            if line.endswith(b","):
                line = line[:-1]

            try:
                ent = orjson.loads(line)
            except Exception:
                bad += 1
                continue

            qid = ent.get("id", "")
            if not qid.startswith("Q"):
                continue

            n += 1

            label_en = en_value(ent.get("labels", {}))
            description_en = en_value(ent.get("descriptions", {}))
            aliases = en_aliases(ent)

            p31 = claim_item_ids(ent, "P31")
            p50 = claim_item_ids(ent, "P50")
            p629 = claim_item_ids(ent, "P629")

            is_human = "Q5" in p31

            # ----------------------------------------------------------
            # Person index: local replacement for author name search
            # ----------------------------------------------------------
            if is_human:
                hits = {}
                for source, value in (
                    [("label_en", label_en)]
                    + [("alias_en", x) for x in aliases]
                ):
                    for key in author_keys_for_name(value):
                        if key in author_keys and key not in hits:
                            hits[key] = (value, source)

                # Persist only people relevant to the target author set.
                if hits:
                    names = [x for x in [label_en, *aliases] if x]
                    people_batch.append((
                        qid,
                        label_en,
                        description_en,
                        dumps(aliases),
                        " | ".join(names),
                    ))

                    for key, (value, source) in hits.items():
                        author_match_batch.append(
                            (key, qid, value, source)
                        )

            # ----------------------------------------------------------
            # P50 edge index
            # ----------------------------------------------------------
            for author_qid in p50:
                edge_batch.append((author_qid, qid))

            # ----------------------------------------------------------
            # Target-title exact matches
            # ----------------------------------------------------------
            title_hits = {}

            for source, value in (
                [("label_en", label_en)]
                + [("alias_en", x) for x in aliases]
            ):
                key = normalize_title(value)
                if key in title_keys and key not in title_hits:
                    title_hits[key] = (value, source)

            p1476 = stated_titles(ent)
            for x in p1476:
                value = x["text"]
                key = normalize_title(value)
                if key in title_keys and key not in title_hits:
                    title_hits[key] = (
                        value,
                        "P1476:" + x.get("language", "")
                    )

            for key, (value, source) in title_hits.items():
                title_match_batch.append(
                    (key, qid, value, source)
                )

            # Keep metadata for all P50-bearing items and all direct title hits.
            if p50 or title_hits:
                dates = claim_dates(ent)
                search_values = [
                    label_en,
                    *aliases,
                    *[x["text"] for x in p1476],
                ]

                entity_batch.append((
                    qid,
                    label_en,
                    description_en,
                    dumps(aliases),
                    dumps(p31),
                    dumps(p50),
                    dumps(p629),
                    dumps(dates),
                    dumps(p1476),
                    int("enwiki" in ent.get("sitelinks", {})),
                    " | ".join(x for x in search_values if x),
                ))

            if n % 5000 == 0:
                flush()

            if n % args.progress_every == 0:
                elapsed = time.time() - start
                rate = n / elapsed if elapsed else 0
                print(
                    f"entities={n:,}  "
                    f"rate={rate:,.0f}/s  "
                    f"elapsed={elapsed/3600:.2f}h  "
                    f"bad={bad:,}",
                    flush=True,
                )

    flush()

    print("Building indexes...", flush=True)

    con.executescript("""
    CREATE INDEX IF NOT EXISTS idx_p50_author
        ON p50_edges(author_qid);

    CREATE INDEX IF NOT EXISTS idx_p50_item
        ON p50_edges(item_qid);

    CREATE INDEX IF NOT EXISTS idx_author_match_key
        ON target_author_matches(author_key);

    CREATE INDEX IF NOT EXISTS idx_title_match_key
        ON target_title_matches(title_key);

    DROP TABLE IF EXISTS people_fts;
    CREATE VIRTUAL TABLE people_fts
        USING fts5(
            qid UNINDEXED,
            names,
            tokenize='unicode61 remove_diacritics 2'
        );

    INSERT INTO people_fts(qid, names)
        SELECT qid, names_text FROM people;

    DROP TABLE IF EXISTS works_fts;
    CREATE VIRTUAL TABLE works_fts
        USING fts5(
            qid UNINDEXED,
            titles,
            tokenize='unicode61 remove_diacritics 2'
        );

    INSERT INTO works_fts(qid, titles)
        SELECT qid, search_text FROM entities;

    ANALYZE;
    """)
    con.commit()

    print("\nFINAL COUNTS")
    for table in [
        "people",
        "p50_edges",
        "entities",
        "target_author_matches",
        "target_title_matches",
    ]:
        count = con.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]
        print(f"{table}: {count:,}")

    print("database:", args.db)
    print("bad JSON lines:", bad)
    print("done")


if __name__ == "__main__":
    main()
