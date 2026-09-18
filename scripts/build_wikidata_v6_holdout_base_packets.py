#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pandas as pd

from wikidata_candidate_generator_v2 import build_candidates


DEFAULT_V2 = Path(
    "/media/hdd1/user/tsutsui/wikidata/"
    "wikidata_resolution_v2_evidence_20260805.sqlite"
)
DEFAULT_BASE = Path(
    "/media/hdd1/user/tsutsui/wikidata/"
    "wikidata_local_20260805.sqlite"
)

DEFAULT_RELATION_CACHE = Path(
    "derived/wikidata_production/"
    "judge_v4_random100_20260915/"
    "relation_qid_metadata_from_dump.jsonl"
)


def load_json(s, default=None):
    if default is None:
        default = []
    if s in (None, ""):
        return default
    try:
        x = json.loads(s)
        return x
    except Exception:
        return default


def read_targets(path: Path):
    sep = "\t" if path.suffix.lower() in {".tsv", ".txt"} else ","
    df = pd.read_csv(path, sep=sep, dtype=str).fillna("")

    required = {"target_id", "title", "author"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    if "year" not in df.columns:
        df["year"] = ""

    return df[["target_id", "title", "author", "year"]].to_dict("records")


class Metadata:
    def __init__(
        self,
        base,
        v2,
        relation_cache,
        candidate_supplement,
    ):
        self.base = base
        self.v2 = v2
        self.cache = {}
        self.relation_cache = {}
        self.dump_relation_meta = {}
        self.candidate_supplement = {}

        if candidate_supplement.exists():
            with candidate_supplement.open(
                encoding="utf-8"
            ) as f:
                for line in f:
                    if line.strip():
                        x = json.loads(line)
                        qid = x.get("qid", "")
                        if qid:
                            self.candidate_supplement[qid] = x

        if relation_cache.exists():
            with relation_cache.open(encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    x = json.loads(line)
                    qid = x.get("qid", "")
                    if qid:
                        self.dump_relation_meta[qid] = x

    def get(self, qid):
        if qid in self.cache:
            return self.cache[qid]

        row = self.base.execute("""
            SELECT
                qid,
                label_en,
                description_en,
                aliases_en,
                p31,
                p50,
                p629,
                p577,
                p1476,
                has_enwiki
            FROM entities
            WHERE qid=?
        """, (qid,)).fetchone()

        if row is None:
            sup = self.candidate_supplement.get(qid)

            if sup is None:
                raise KeyError(
                    f"Candidate QID missing from base DB "
                    f"and supplement: {qid}"
                )

            x = {
                "qid": qid,
                "label": sup.get("label_en", ""),
                "description": sup.get(
                    "description_en", ""
                ),
                "aliases": sup.get("aliases_en", []),
                "p31": sup.get("p31", []),
                "p50": sup.get("p50", []),
                "p629": sup.get("p629", []),
                "publication_dates": sup.get(
                    "p577", []
                ),
                "stated_titles": sup.get(
                    "p1476", []
                ),
                "has_enwiki": bool(
                    sup.get("has_enwiki", False)
                ),
            }
        else:
            x = {
                "qid": row[0],
                "label": row[1] or "",
                "description": row[2] or "",
                "aliases": load_json(row[3]),
                "p31": load_json(row[4]),
                "p50": load_json(row[5]),
                "p629": load_json(row[6]),
                "publication_dates": load_json(row[7]),
                "stated_titles": load_json(row[8]),
                "has_enwiki": bool(row[9]),
            }
        self.cache[qid] = x
        return x

    def relation(self, qid):
        if qid in self.relation_cache:
            return self.relation_cache[qid]

        label = ""
        description = ""

        # 1. original base DB
        row = self.base.execute(
            """
            SELECT label_en, description_en
            FROM entities
            WHERE qid=?
            """,
            (qid,),
        ).fetchone()

        if row:
            label = row[0] or ""
            description = row[1] or ""

        # 2. v2 evidence DB
        if not label or not description:
            row = self.v2.execute(
                """
                SELECT label_en, description_en
                FROM wikidata_entities_v2
                WHERE qid=?
                """,
                (qid,),
            ).fetchone()

            if row:
                if not label:
                    label = row[0] or ""
                if not description:
                    description = row[1] or ""

        # 3. targeted metadata extracted from frozen dump
        if not label or not description:
            x = self.dump_relation_meta.get(qid)

            if x:
                if not label:
                    label = x.get("label_en", "") or ""
                if not description:
                    description = x.get("description_en", "") or ""

        result = {
            "qid": qid,
            "label": label,
            "description": description,
        }
        self.relation_cache[qid] = result
        return result

    def label(self, qid):
        return self.relation(qid)["label"]

    def relation_list(self, qids):
        return [self.relation(q) for q in qids]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--v2-db", type=Path, default=DEFAULT_V2)
    ap.add_argument("--base-db", type=Path, default=DEFAULT_BASE)
    ap.add_argument(
        "--relation-cache",
        type=Path,
        default=DEFAULT_RELATION_CACHE,
    )
    ap.add_argument(
        "--candidate-supplement",
        type=Path,
        default=Path(
            "derived/benchmark/holdout/"
            "fresh_random100_v6_20260918/"
            "supplement/candidate_metadata_live_api.jsonl"
        ),
    )
    args = ap.parse_args()

    targets = read_targets(args.input)

    v2 = sqlite3.connect(args.v2_db)
    base = sqlite3.connect(args.base_db)
    meta = Metadata(
        base,
        v2,
        args.relation_cache,
        args.candidate_supplement,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)

    total_candidates = 0
    max_candidates = 0

    with args.output.open("w", encoding="utf-8") as f:
        for i, target in enumerate(targets, 1):
            author_qids, candidates = build_candidates(
                v2,
                base,
                target["target_id"],
                target["title"],
            )

            enriched = []

            for c in candidates:
                m = meta.get(c["qid"])

                enriched.append({
                    "qid": c["qid"],
                    "sources": c.get("sources", []),
                    "via": c.get("via", []),
                    "title_score": c.get("score"),
                    "direct_support": c.get("direct_support", 0),
                    "direct_author_match": c.get(
                        "direct_author_match", False
                    ),
                    "label": m["label"],
                    "description": m["description"],
                    "aliases": m["aliases"],
                    "stated_titles": m["stated_titles"],
                    "publication_dates": m["publication_dates"],
                    "instance_of": meta.relation_list(m["p31"]),
                    "authors": meta.relation_list(m["p50"]),
                    "edition_or_translation_of":
                        meta.relation_list(m["p629"]),
                    "has_enwiki": m["has_enwiki"],
                })

            packet = {
                "target_id": target["target_id"],
                "title": target["title"],
                "author": target["author"],
                "year": target["year"],
                "author_candidate_qids": author_qids,
                "author_candidates": [
                    meta.relation(q)
                    for q in author_qids
                ],
                "candidate_count": len(enriched),
                "candidates": enriched,
            }

            f.write(
                json.dumps(packet, ensure_ascii=False)
                + "\n"
            )

            total_candidates += len(enriched)
            max_candidates = max(max_candidates, len(enriched))

            if i <= 5 or i % 25 == 0 or i == len(targets):
                print(
                    f"[{i}/{len(targets)}] "
                    f"{target['target_id']} "
                    f"candidates={len(enriched)}"
                )

    print("\nDONE")
    print("targets:", len(targets))
    print("total candidates:", total_candidates)
    print("mean candidates:", round(total_candidates / len(targets), 3))
    print("max candidates:", max_candidates)
    print("output:", args.output)


if __name__ == "__main__":
    main()
