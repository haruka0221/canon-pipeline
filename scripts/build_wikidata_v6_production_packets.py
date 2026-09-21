#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path


def load_json(s, default=None):
    if default is None:
        default = []
    if s in (None, ""):
        return default
    try:
        return json.loads(s)
    except Exception:
        return default


def text_value(v):
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return str(v.get("value", ""))
    if isinstance(v, list):
        return " | ".join(map(str, v))
    return str(v)


SOURCE_PATTERNS = [
    (
        "translation_of",
        re.compile(
            r"\btranslation\s+of\s+(.+?)(?=(?:[\.;\n]|$))",
            re.I,
        ),
    ),
    (
        "abridged_from",
        re.compile(
            r"\babridged\s+from\s+(.+?)(?=(?:\s+by\b|[\.;\n]|$))",
            re.I,
        ),
    ),
    (
        "adapted_from",
        re.compile(
            r"\badapted\s+from\s+(.+?)(?=(?:\s+by\b|[\.;\n]|$))",
            re.I,
        ),
    ),
    (
        "based_on",
        re.compile(
            r"\bbased\s+on\s+(.+?)(?=(?:\s+with\b|;|\n|$))",
            re.I,
        ),
    ),
]

RESP_PAT = re.compile(
    r"\b("
    r"translat\w*|"
    r"abridg\w*|"
    r"adapt\w*|"
    r"based\s+on|"
    r"version\s+of|"
    r"retold|"
    r"revised|"
    r"edited"
    r")\b",
    re.I,
)


def extract_source_relations(ed):
    found = []

    for field in ["notes", "by_statement", "full_title"]:
        txt = " ".join(text_value(ed.get(field)).split())
        if not txt:
            continue

        for relation, pat in SOURCE_PATTERNS:
            for m in pat.finditer(txt):
                found.append({
                    "relation": relation,
                    "source_work_text":
                        " ".join(m.group(1).split()).rstrip(" .;"),
                    "field": field,
                    "evidence": " ".join(m.group(0).split()),
                })

    return found


def extract_responsibility_notes(ed):
    found = []

    for field in [
        "title",
        "full_title",
        "subtitle",
        "by_statement",
        "notes",
    ]:
        txt = " ".join(text_value(ed.get(field)).split())

        if txt and RESP_PAT.search(txt):
            found.append({
                "field": field,
                "text": txt,
            })

    return found


def dedupe_dicts(rows):
    seen = set()
    out = []

    for r in rows:
        k = json.dumps(
            r,
            ensure_ascii=False,
            sort_keys=True,
        )

        if k not in seen:
            seen.add(k)
            out.append(r)

    return out


def load_edition_evidence(path):
    edition_by_target = {}

    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            x = json.loads(line)
            tid = x["target_id"]
            ed = x["edition"]

            item = edition_by_target.setdefault(
                tid,
                {
                    "selection_scope": x["selection_scope"],
                    "source_relations": [],
                    "work_titles": [],
                    "responsibility_notes": [],
                },
            )

            item["source_relations"].extend(
                extract_source_relations(ed)
            )

            for wt in ed.get("work_titles") or []:
                item["work_titles"].append(str(wt))

            item["responsibility_notes"].extend(
                extract_responsibility_notes(ed)
            )

    for tid, e in edition_by_target.items():
        e["source_relations"] = dedupe_dicts(
            e["source_relations"]
        )[:10]

        e["work_titles"] = list(
            dict.fromkeys(e["work_titles"])
        )[:10]

        e["responsibility_notes"] = dedupe_dicts(
            e["responsibility_notes"]
        )[:10]

    return edition_by_target


class Metadata:
    def __init__(
        self,
        base,
        v2,
        candidate_supplement,
        relation_caches,
    ):
        self.base = base
        self.v2 = v2
        self.candidate_supplement = {}
        self.relation_dump_meta = {}
        self.entity_cache = {}
        self.relation_cache = {}

        with candidate_supplement.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                x = json.loads(line)
                qid = x.get("qid", "")
                if qid:
                    self.candidate_supplement[qid] = x

        # Multiple caches are merged conservatively:
        # later files fill blanks but do not erase existing values.
        for path in relation_caches:
            if not path.exists():
                raise FileNotFoundError(path)

            with path.open(encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue

                    x = json.loads(line)
                    qid = x.get("qid", "")
                    if not qid:
                        continue

                    cur = self.relation_dump_meta.setdefault(
                        qid,
                        {
                            "qid": qid,
                            "label_en": "",
                            "description_en": "",
                        },
                    )

                    if not cur["label_en"]:
                        cur["label_en"] = (
                            x.get("label_en", "") or ""
                        )

                    if not cur["description_en"]:
                        cur["description_en"] = (
                            x.get("description_en", "") or ""
                        )

    def get_candidate(self, qid):
        if qid in self.entity_cache:
            return self.entity_cache[qid]

        row = self.base.execute(
            """
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
            """,
            (qid,),
        ).fetchone()

        if row is not None:
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
        else:
            sup = self.candidate_supplement.get(qid)

            if sup is None:
                raise KeyError(
                    "Candidate missing from both base DB and "
                    f"candidate supplement: {qid}"
                )

            x = {
                "qid": qid,
                "label": sup.get("label_en", "") or "",
                "description":
                    sup.get("description_en", "") or "",
                "aliases": sup.get("aliases_en", []) or [],
                "p31": sup.get("p31", []) or [],
                "p50": sup.get("p50", []) or [],
                "p629": sup.get("p629", []) or [],
                "publication_dates":
                    sup.get("p577", []) or [],
                "stated_titles":
                    sup.get("p1476", []) or [],
                "has_enwiki":
                    bool(sup.get("has_enwiki", False)),
            }

        self.entity_cache[qid] = x
        return x

    def relation(self, qid):
        if qid in self.relation_cache:
            return self.relation_cache[qid]

        label = ""
        description = ""

        # 1. frozen base DB
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

        # 2. clean v2 evidence DB
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

        # 3. frozen-dump relation supplements
        if not label or not description:
            x = self.relation_dump_meta.get(qid)

            if x:
                if not label:
                    label = x.get("label_en", "") or ""
                if not description:
                    description = (
                        x.get("description_en", "") or ""
                    )

        result = {
            "qid": qid,
            "label": label,
            "description": description,
        }

        self.relation_cache[qid] = result
        return result

    def relation_list(self, qids):
        return [
            self.relation(q)
            for q in qids
            if isinstance(q, str) and q.startswith("Q")
        ]

    def via_title_evidence(self, qid):
        """
        Return frozen title-bearing metadata for a provenance/via QID.

        This does not create a new candidate. It only preserves title
        evidence that was already used during candidate generation.
        """
        row = self.base.execute(
            """
            SELECT label_en, description_en, aliases_en, p1476
            FROM entities
            WHERE qid=?
            """,
            (qid,),
        ).fetchone()

        if row:
            label = row[0] or ""
            description = row[1] or ""
            aliases = load_json(row[2])
            stated_titles = load_json(row[3])
        else:
            row = self.v2.execute(
                """
                SELECT
                    label_en,
                    description_en,
                    aliases_en_json,
                    p1476_json
                FROM wikidata_entities_v2
                WHERE qid=?
                """,
                (qid,),
            ).fetchone()

            if not row:
                return None

            label = row[0] or ""
            description = row[1] or ""
            aliases = load_json(row[2])
            stated_titles = load_json(row[3])

        # Only retain provenance items carrying actual title identity evidence.
        if not label.strip() and not aliases and not stated_titles:
            return None

        return {
            "qid": qid,
            "label": label,
            "description": description,
            "aliases": aliases,
            "stated_titles": stated_titles,
        }


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--shortlists",
        type=Path,
        required=True,
    )
    ap.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    ap.add_argument(
        "--base-db",
        type=Path,
        required=True,
    )
    ap.add_argument(
        "--v2-db",
        type=Path,
        required=True,
    )
    ap.add_argument(
        "--candidate-supplement",
        type=Path,
        required=True,
    )
    ap.add_argument(
        "--relation-cache",
        type=Path,
        action="append",
        default=[],
    )
    ap.add_argument(
        "--edition-evidence",
        type=Path,
        required=True,
    )

    args = ap.parse_args()

    base = sqlite3.connect(args.base_db)
    v2 = sqlite3.connect(args.v2_db)

    meta = Metadata(
        base=base,
        v2=v2,
        candidate_supplement=args.candidate_supplement,
        relation_caches=args.relation_cache,
    )

    edition_by_target = load_edition_evidence(
        args.edition_evidence
    )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    n_targets = 0
    total_candidates = 0
    max_candidates = 0
    with_edition_evidence = 0
    with_source_relation = 0

    with args.shortlists.open(encoding="utf-8") as src, \
         args.output.open("w", encoding="utf-8") as dst:

        for line in src:
            if not line.strip():
                continue

            p = json.loads(line)

            candidates = p.get("candidates", [])

            # Production judge only receives targets with >=1 candidate.
            # Zero-candidate targets are handled separately and are not
            # sent to the LLM judge.
            if not candidates:
                continue

            expected = int(
                p.get("candidate_count", len(candidates))
            )

            if expected != len(candidates):
                raise ValueError(
                    f"{p['target_id']}: candidate_count "
                    f"{expected} != {len(candidates)}"
                )

            enriched = []

            # Preserve shortlist order exactly.
            for c in candidates:
                qid = c["qid"]
                m = meta.get_candidate(qid)

                item = {
                    "qid": qid,
                    "sources": c.get("sources", []),
                    "via": c.get("via", []),
                    "title_score": c.get("score"),
                    "direct_support":
                        c.get("direct_support", 0),
                    "direct_author_match":
                        c.get(
                            "direct_author_match",
                            False,
                        ),
                    "label": m["label"],
                    "description": m["description"],
                    "aliases": m["aliases"],
                    "stated_titles":
                        m["stated_titles"],
                    "publication_dates":
                        m["publication_dates"],
                    "instance_of":
                        meta.relation_list(m["p31"]),
                    "authors":
                        meta.relation_list(m["p50"]),
                    "edition_or_translation_of":
                        meta.relation_list(m["p629"]),
                    "has_enwiki": m["has_enwiki"],
                }

                # Preserve provenance title evidence only when the
                # conceptual candidate itself has no identity metadata,
                # but candidate generation used direct/exact title evidence.
                candidate_identity_blank = (
                    not str(m["label"]).strip()
                    and not str(m["description"]).strip()
                    and not m["aliases"]
                    and not m["stated_titles"]
                )

                sources = c.get("sources", [])
                direct_or_exact = (
                    any(
                        s.startswith("direct_title:")
                        for s in sources
                    )
                    or "author_p50_exact" in sources
                )

                if candidate_identity_blank and direct_or_exact:
                    author_qids = set(
                        p.get("author_candidate_qids", [])
                    )

                    via_evidence = []

                    for via_qid in c.get("via", []):
                        # Do not treat candidate itself or author entity
                        # metadata as title provenance.
                        if via_qid == qid or via_qid in author_qids:
                            continue

                        ev = meta.via_title_evidence(via_qid)
                        if ev:
                            via_evidence.append(ev)

                    if via_evidence:
                        item["via_title_evidence"] = via_evidence

                enriched.append(item)

            packet = {
                "target_id": p["target_id"],
                "title": p["title"],
                "author": p["author"],
                "year": p.get("year", ""),
                "author_candidate_qids":
                    p.get("author_candidate_qids", []),
                "author_candidates": [
                    meta.relation(q)
                    for q in p.get(
                        "author_candidate_qids",
                        [],
                    )
                ],
                "candidate_count": len(enriched),
                "candidates": enriched,
            }

            e = edition_by_target.get(p["target_id"])

            if e:
                has_useful = bool(
                    e["source_relations"]
                    or e["work_titles"]
                    or e["responsibility_notes"]
                )

                if has_useful:
                    packet[
                        "openlibrary_edition_evidence"
                    ] = e
                    with_edition_evidence += 1

                if e["source_relations"]:
                    with_source_relation += 1

            dst.write(
                json.dumps(
                    packet,
                    ensure_ascii=False,
                )
                + "\n"
            )

            n_targets += 1
            total_candidates += len(enriched)
            max_candidates = max(
                max_candidates,
                len(enriched),
            )

            if n_targets % 1000 == 0:
                print(
                    f"[{n_targets}] "
                    f"candidates={total_candidates}"
                )

    base.close()
    v2.close()

    print("\nDONE")
    print("targets:", n_targets)
    print("total candidates:", total_candidates)
    print(
        "mean candidates:",
        round(total_candidates / n_targets, 3),
    )
    print("max candidates:", max_candidates)
    print(
        "with edition evidence:",
        with_edition_evidence,
    )
    print(
        "with explicit source relation:",
        with_source_relation,
    )
    print("output:", args.output)


if __name__ == "__main__":
    main()
