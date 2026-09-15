#!/usr/bin/env python3

import json
import sqlite3
from difflib import SequenceMatcher

import pandas as pd

from build_wikidata_resolution_v2_evidence import normalize_v2


V2_DB = "/media/hdd1/user/tsutsui/wikidata/wikidata_resolution_v2_evidence_20260805.sqlite"
BASE_DB = "/media/hdd1/user/tsutsui/wikidata/wikidata_local_20260805.sqlite"
BENCH = "derived/benchmark/judgments/adjudication/wikidata_benchmark_adjudicated_final_130.csv"

KS = [5, 10, 20, 30, 50]


def load_json(s):
    if not s:
        return []
    try:
        x = json.loads(s)
        return x if isinstance(x, list) else []
    except Exception:
        return []


def entity_titles(label, aliases_json, p1476_json):
    vals = []

    if label:
        vals.append(label)

    vals.extend(
        x for x in load_json(aliases_json)
        if isinstance(x, str) and x
    )

    for x in load_json(p1476_json):
        if isinstance(x, dict) and x.get("text"):
            vals.append(x["text"])

    return list(dict.fromkeys(vals))


def similarity(a, b):
    return SequenceMatcher(
        None,
        normalize_v2(a),
        normalize_v2(b),
    ).ratio()


def gold_set(primary, alternatives):
    out = set()

    if primary:
        out.add(primary.strip())

    for x in str(alternatives or "").split(";"):
        x = x.strip()
        if x:
            out.add(x)

    return out


def add(store, qid):
    if qid:
        store.add(qid)


def candidates_for_target(v2, base, target_id, title, k):
    candidates = set()

    # ------------------------------------------------------------
    # Direct title matches: always keep.
    # Also retain related parent/original-work QIDs as evidence.
    # ------------------------------------------------------------
    rows = v2.execute("""
        SELECT
            t.qid,
            e.p629_json,
            e.p9745_json
        FROM target_title_matches_v2 t
        LEFT JOIN wikidata_entities_v2 e
          ON e.qid = t.qid
        WHERE t.target_id = ?
    """, (target_id,)).fetchall()

    for qid, p629_json, p9745_json in rows:
        # For candidate shortlisting, aggregate manifestations /
        # translations to their related work-level entity.
        # The child QID itself remains preserved in the v2 evidence DB.
        related = []

        related.extend(load_json(p629_json))
        related.extend(load_json(p9745_json))

        related = list(
            dict.fromkeys(
                x for x in related if x
            )
        )

        if related:
            for x in related:
                add(candidates, x)
        else:
            # No work-level relation is available, so retain the
            # directly title-matched entity as an unresolved candidate.
            add(candidates, qid)

    # ------------------------------------------------------------
    # Author candidates -> works by P50.
    #
    # Exact title matches are ALWAYS retained.
    # Fuzzy candidates are hard top-K per author QID.
    # No tie expansion at the cutoff.
    # ------------------------------------------------------------
    author_qids = [
        r[0]
        for r in v2.execute("""
            SELECT DISTINCT author_qid
            FROM target_author_matches_v2
            WHERE target_id = ?
        """, (target_id,))
    ]

    for author_qid in author_qids:
        rows = base.execute("""
            SELECT
                e.qid,
                e.label_en,
                e.aliases_en,
                e.p1476,
                e.p629
            FROM p50_edges p
            JOIN entities e
              ON e.qid = p.item_qid
            WHERE p.author_qid = ?
        """, (author_qid,)).fetchall()

        scored = []

        for qid, label, aliases_json, p1476_json, p629_json in rows:
            titles = entity_titles(
                label,
                aliases_json,
                p1476_json,
            )

            score = max(
                (similarity(title, x) for x in titles),
                default=0.0,
            )

            exact = any(
                normalize_v2(title) == normalize_v2(x)
                for x in titles
            )

            parents = load_json(p629_json)

            scored.append(
                (exact, score, qid, parents)
            )

        # Exact matches are not subject to K.
        # For conceptual-work shortlisting, aggregate editions /
        # manifestations to their P629 parent when available.
        # The child edition remains preserved in the evidence DB.
        for exact, score, qid, parents in scored:
            if not exact:
                continue

            if parents:
                for parent in parents:
                    add(candidates, parent)
            else:
                add(candidates, qid)

        # Hard top-K fuzzy shortlist.
        ranked = sorted(
            scored,
            key=lambda x: (-x[1], x[2]),
        )

        for exact, score, qid, parents in ranked[:k]:
            # Same conceptual-work aggregation for fuzzy candidates.
            if parents:
                for parent in parents:
                    add(candidates, parent)
            else:
                add(candidates, qid)

    return candidates


def main():
    v2 = sqlite3.connect(V2_DB)
    base = sqlite3.connect(BASE_DB)

    df = pd.read_csv(
        BENCH,
        dtype=str,
    ).fillna("")

    positives = df[
        df["gold_decision"].isin(["MATCH", "AMBIGUOUS"])
    ].copy()

    summary = []

    for k in KS:
        rows = []

        for _, r in df.iterrows():
            candidates = candidates_for_target(
                v2,
                base,
                r["target_id"],
                r["title"],
                k,
            )

            gset = gold_set(
                r["gold_selected_qid"],
                r["gold_alternative_qids"],
            )

            positive = r["gold_decision"] in {
                "MATCH",
                "AMBIGUOUS",
            }

            rows.append({
                "target_id": r["target_id"],
                "title": r["title"],
                "author": r["author"],
                "positive": positive,
                "candidate_count": len(candidates),
                "primary_hit":
                    r["gold_selected_qid"] in candidates
                    if positive else None,
                "set_hit":
                    bool(gset & candidates)
                    if positive else None,
            })

        x = pd.DataFrame(rows)
        xp = x[x["positive"]].copy()

        primary_hits = xp["primary_hit"].eq(True).sum()
        set_hits = xp["set_hit"].eq(True).sum()

        summary.append({
            "K": k,
            "primary_recall":
                primary_hits / len(xp),
            "set_recall":
                set_hits / len(xp),
            "mean_candidates":
                x["candidate_count"].mean(),
            "median_candidates":
                x["candidate_count"].median(),
            "p90_candidates":
                x["candidate_count"].quantile(.90),
            "p95_candidates":
                x["candidate_count"].quantile(.95),
            "p99_candidates":
                x["candidate_count"].quantile(.99),
            "max_candidates":
                x["candidate_count"].max(),
        })

        misses = xp[
            ~xp["set_hit"].eq(True)
        ]

        print("\nK =", k)
        print(
            "set-aware recall:",
            f"{set_hits}/{len(xp)}",
            f"= {set_hits/len(xp):.3f}",
        )
        print(
            "candidate count:",
            "median =", x["candidate_count"].median(),
            "| p95 =", x["candidate_count"].quantile(.95),
            "| max =", x["candidate_count"].max(),
        )

        if len(misses):
            print("MISSES:")
            print(
                misses[
                    [
                        "target_id",
                        "title",
                        "author",
                        "candidate_count",
                    ]
                ].to_string(index=False)
            )

    print("\nSUMMARY")
    print(
        pd.DataFrame(summary).to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}",
        )
    )


if __name__ == "__main__":
    main()
