#!/usr/bin/env python3

import argparse
import bz2
import csv
import re
import sqlite3
import time
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import orjson


NORMALIZATION_VERSION = "v2_nfkd_drop_combining_marks_20260914"

# Preserve the original Wikidata statements for these properties.
# Convenience decoded columns are also stored separately.
SELECTED_PROPS = [
    "P31",    # instance of
    "P106",   # occupation
    "P50",    # author
    "P629",   # edition/version/translation of
    "P577",   # publication date
    "P1476",  # title
    "P407",   # language of work or name
    "P655",   # translator
    "P98",    # editor
    "P747",   # has version, edition or translation
    "P9745",  # translation of
    "P123",   # publisher
    "P291",   # place of publication
]


# ----------------------------------------------------------------------
# Normalization
# ----------------------------------------------------------------------

def normalize_author(raw):
    if raw is None:
        return ""

    s = str(raw).strip()

    if "," in s:
        last, first = s.split(",", 1)
        last = last.strip()
        first = first.strip()

        if first.lower().endswith(last.lower()):
            return first

        return f"{first} {last}"

    return s


def normalize_v2(raw):
    """
    Minimal correction of v1:
    after NFKD, combining marks are deleted rather than replaced
    by spaces.

    Émile   -> emile
    Mühlbach -> muhlbach
    Arsène  -> arsene
    """
    s = str(raw or "").strip()

    s = re.sub(
        r"^textplus\s*[-:]\s*",
        "",
        s,
        flags=re.I,
    )

    s = unicodedata.normalize("NFKD", s)

    s = "".join(
        ch
        for ch in s
        if not unicodedata.combining(ch)
    )

    s = s.lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)

    return s.strip()


def author_keys_for_wikidata_name(value):
    if not value:
        return set()

    return {
        normalize_v2(value),
        normalize_v2(normalize_author(value)),
    } - {""}


# ----------------------------------------------------------------------
# Source targets
# ----------------------------------------------------------------------

def load_targets(path):
    rows = []
    author_key_to_targets = defaultdict(list)
    title_key_to_targets = defaultdict(list)

    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")

        for row in reader:
            target_id = (
                row.get("target_id", "").strip()
                or row.get("work_key", "").strip().removeprefix("/works/")
            )

            title = row.get("title", "").strip()

            author = (
                row.get("author", "").strip()
                or row.get("author_name", "").strip()
            )

            # IMPORTANT:
            # This is retained only as Open Library source evidence.
            # It is NOT used for identity resolution or rejection.
            ol_year = (
                row.get("year", "").strip()
                or row.get("first_publish_year", "").strip()
            )

            author_key = (
                normalize_v2(normalize_author(author))
                if author
                else ""
            )

            title_key = normalize_v2(title)

            rows.append((
                target_id,
                title,
                author,
                ol_year,
                author_key,
                title_key,
            ))

            if author_key:
                author_key_to_targets[author_key].append(target_id)

            if title_key:
                title_key_to_targets[title_key].append(target_id)

    return rows, author_key_to_targets, title_key_to_targets


# ----------------------------------------------------------------------
# Wikidata helpers
# ----------------------------------------------------------------------

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
            value = claim["mainsnak"]["datavalue"]["value"]

            qid = (
                value.get("id")
                if isinstance(value, dict)
                else None
            )

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
            value = (
                claim["mainsnak"]["datavalue"]["value"]["time"]
                .lstrip("+")
            )

            if value not in seen:
                seen.add(value)
                out.append(value)

        except Exception:
            pass

    return out


def stated_titles(ent):
    out = []
    seen = set()

    for claim in ent.get("claims", {}).get("P1476", []):
        try:
            value = claim["mainsnak"]["datavalue"]["value"]

            if isinstance(value, dict) and value.get("text"):
                key = (
                    value["text"],
                    value.get("language", ""),
                )

                if key not in seen:
                    seen.add(key)

                    out.append({
                        "text": value["text"],
                        "language": value.get("language", ""),
                    })

        except Exception:
            pass

    return out


def selected_raw_claims(ent):
    claims = ent.get("claims", {})

    return {
        prop: claims[prop]
        for prop in SELECTED_PROPS
        if prop in claims
    }


def dumps(x):
    return orjson.dumps(x).decode("utf-8")


def entity_row(ent, label_en, aliases):
    qid = ent.get("id", "")
    description_en = en_value(ent.get("descriptions", {}))

    p1476 = stated_titles(ent)

    search_text = " | ".join(
        x
        for x in [
            label_en,
            description_en,
            *aliases,
            *[
                x["text"]
                for x in p1476
                if x.get("text")
            ],
        ]
        if x
    )

    return (
        qid,
        label_en,
        description_en,
        dumps(aliases),

        dumps(claim_item_ids(ent, "P31")),
        dumps(claim_item_ids(ent, "P106")),
        dumps(claim_item_ids(ent, "P50")),
        dumps(claim_item_ids(ent, "P629")),
        dumps(claim_dates(ent)),
        dumps(p1476),
        dumps(claim_item_ids(ent, "P407")),
        dumps(claim_item_ids(ent, "P655")),
        dumps(claim_item_ids(ent, "P98")),
        dumps(claim_item_ids(ent, "P747")),
        dumps(claim_item_ids(ent, "P9745")),
        dumps(claim_item_ids(ent, "P123")),
        dumps(claim_item_ids(ent, "P291")),

        int("enwiki" in ent.get("sitelinks", {})),
        str(ent.get("modified", "") or ""),
        str(ent.get("lastrevid", "") or ""),

        # Keeps rank / qualifiers / references for later interpretation.
        dumps(selected_raw_claims(ent)),

        search_text,
    )


# ----------------------------------------------------------------------
# Database
# ----------------------------------------------------------------------

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

    -- The frozen OL source population.
    -- No claim is made here that one row equals one conceptual work.
    CREATE TABLE IF NOT EXISTS source_targets (
        target_id TEXT PRIMARY KEY,
        raw_title TEXT,
        raw_author TEXT,
        ol_first_publish_year_raw TEXT,
        author_key_v2 TEXT,
        title_key_v2 TEXT
    );

    -- Source-target author evidence.
    -- One target may have multiple candidate author QIDs.
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

    -- Direct title evidence.
    -- One target may map to many QIDs; many targets may map to one QID.
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

    -- Metadata for directly matched Wikidata entities.
    -- QIDs remain external entity-resolution evidence, not project work IDs.
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

    -- Candidate evidence only.
    -- This table does NOT assert that qid is the conceptual work.
    CREATE TABLE IF NOT EXISTS target_qid_evidence_v2 (
        target_id TEXT NOT NULL,
        qid TEXT NOT NULL,
        evidence_type TEXT NOT NULL,
        via_qid TEXT NOT NULL DEFAULT '',
        matched_text TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (
            target_id,
            qid,
            evidence_type,
            via_qid,
            matched_text,
            source
        )
    );
    """)

    meta = {
        "normalization_version": NORMALIZATION_VERSION,
        "created_at": datetime.now().astimezone().isoformat(),
        "year_policy":
            "OL year retained as source evidence only; "
            "not used as identity-resolution filter",
        "qid_policy":
            "Wikidata QIDs are entity-resolution evidence, "
            "not project conceptual-work IDs",
        "cardinality_policy":
            "many OL targets to one QID and one target to many QIDs allowed",
        "selected_properties": ",".join(SELECTED_PROPS),
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


def build_candidate_evidence(con, base_db):
    """
    Materialize evidence only.

    title_exact_v2:
        target title directly matched a Wikidata item.

    author_p50_v2:
        target author matched a Wikidata author entity and the existing
        frozen local Wikidata index contains P50(author -> item).

    Neither evidence type is treated as a final match.
    """

    print("Building target-QID evidence...", flush=True)

    con.execute("""
        INSERT OR IGNORE INTO target_qid_evidence_v2 (
            target_id,
            qid,
            evidence_type,
            via_qid,
            matched_text,
            source
        )
        SELECT
            target_id,
            qid,
            'title_exact_v2',
            '',
            matched_text,
            source
        FROM target_title_matches_v2
    """)

    con.commit()

    if not base_db:
        return

    con.execute("ATTACH DATABASE ? AS base", (base_db,))

    con.execute("""
        INSERT OR IGNORE INTO target_qid_evidence_v2 (
            target_id,
            qid,
            evidence_type,
            via_qid,
            matched_text,
            source
        )
        SELECT
            a.target_id,
            p.item_qid,
            'author_p50_v2',
            a.author_qid,
            a.matched_text,
            a.source
        FROM target_author_matches_v2 AS a
        JOIN base.p50_edges AS p
          ON p.author_qid = a.author_qid
    """)

    con.commit()
    con.execute("DETACH DATABASE base")


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()

    ap.add_argument("--dump", required=True)
    ap.add_argument("--population", required=True)
    ap.add_argument("--db", required=True)

    ap.add_argument(
        "--base-db",
        default="",
        help=(
            "Existing frozen local Wikidata DB containing p50_edges. "
            "Read-only source for author->work candidate evidence."
        ),
    )

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

    # qid -> entity row
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
            # Author identity evidence
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
            # Direct title evidence
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

            # Keep detailed source evidence only for entities that
            # directly match a target author or title in this pass.
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

    CREATE INDEX IF NOT EXISTS idx_author_match_target_v2
        ON target_author_matches_v2(target_id);

    CREATE INDEX IF NOT EXISTS idx_author_match_key_v2
        ON target_author_matches_v2(author_key_v2);

    CREATE INDEX IF NOT EXISTS idx_author_match_qid_v2
        ON target_author_matches_v2(author_qid);

    CREATE INDEX IF NOT EXISTS idx_title_match_target_v2
        ON target_title_matches_v2(target_id);

    CREATE INDEX IF NOT EXISTS idx_title_match_key_v2
        ON target_title_matches_v2(title_key_v2);

    CREATE INDEX IF NOT EXISTS idx_title_match_qid_v2
        ON target_title_matches_v2(qid);

    CREATE INDEX IF NOT EXISTS idx_evidence_target_v2
        ON target_qid_evidence_v2(target_id);

    CREATE INDEX IF NOT EXISTS idx_evidence_qid_v2
        ON target_qid_evidence_v2(qid);
    """)

    con.commit()

    build_candidate_evidence(
        con,
        args.base_db,
    )

    print("\nFINAL COUNTS")

    for table in [
        "source_targets",
        "target_author_matches_v2",
        "target_title_matches_v2",
        "wikidata_entities_v2",
        "target_qid_evidence_v2",
    ]:
        n = con.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]

        print(f"{table}: {n:,}")

    targets_with_evidence = con.execute("""
        SELECT COUNT(DISTINCT target_id)
        FROM target_qid_evidence_v2
    """).fetchone()[0]

    print(
        "targets with any QID evidence:",
        f"{targets_with_evidence:,}",
    )

    print("database:", args.db)
    print("bad JSON lines:", bad_json)
    print("done")


if __name__ == "__main__":
    main()
