#!/usr/bin/env python3

import json
import re
import sqlite3
from collections import Counter
from statistics import mean, median

import numpy as np
import pandas as pd

from analyze_wikidata_v2_topk import (
    add,
    load_json,
    entity_titles,
    similarity,
)
from build_wikidata_resolution_v2_evidence import normalize_v2


V2_DB = "/media/hdd1/user/tsutsui/wikidata/wikidata_resolution_v2_evidence_20260805.sqlite"
BASE_DB = "/media/hdd1/user/tsutsui/wikidata/wikidata_local_20260805.sqlite"
BENCH = "derived/benchmark/judgments/adjudication/wikidata_benchmark_adjudicated_final_130.csv"

AUTHOR_FUZZY_K = 5
DIRECT_CAPS = [1, 3, 5, 10, 20]


def qids_from_text(s):
    return re.findall(r"Q\d+", s or "")


def gold_set(row):
    out = set()

    if row["gold_selected_qid"]:
        out.add(row["gold_selected_qid"])

    out.update(qids_from_text(row["gold_alternative_qids"]))

    return out


def get_entity_p50(v2, base, qid):
    row = base.execute(
        "SELECT p50 FROM entities WHERE qid=?",
        (qid,),
    ).fetchone()

    if row:
        return set(load_json(row[0]))

    row = v2.execute(
        "SELECT p50_json FROM wikidata_entities_v2 WHERE qid=?",
        (qid,),
    ).fetchone()

    if row:
        return set(load_json(row[0]))

    return set()


def direct_candidates_ranked(v2, base, target_id):
    author_qids = {
        r[0]
        for r in v2.execute("""
            SELECT DISTINCT author_qid
            FROM target_author_matches_v2
            WHERE target_id=?
        """, (target_id,))
    }

    # Aggregate raw direct-title items to conceptual candidates.
    support = Counter()

    rows = v2.execute("""
        SELECT
            t.qid,
            e.p629_json,
            e.p9745_json
        FROM target_title_matches_v2 t
        LEFT JOIN wikidata_entities_v2 e
          ON e.qid=t.qid
        WHERE t.target_id=?
    """, (target_id,)).fetchall()

    for qid, p629_json, p9745_json in rows:
        related = []
        related.extend(load_json(p629_json))
        related.extend(load_json(p9745_json))

        related = list(dict.fromkeys(
            x for x in related if x
        ))

        if related:
            for parent in related:
                support[parent] += 1
        else:
            support[qid] += 1

    ranked = []

    for qid, n_support in support.items():
        p50 = get_entity_p50(v2, base, qid)
        author_match = bool(author_qids & p50)

        ranked.append(
            (author_match, n_support, qid)
        )

    ranked.sort(
        key=lambda x: (
            -int(x[0]),
            -x[1],
            x[2],
        )
    )

    return ranked


def candidates_for_target(v2, base, target_id, title, direct_cap):
    candidates = set()

    # ------------------------------------------------------------
    # Direct title route:
    # conceptual aggregation first, then hard cap.
    # Ranking:
    #   1. author P50 compatibility
    #   2. manifestation support count
    #   3. QID only as deterministic tie-break
    # ------------------------------------------------------------
    ranked_direct = direct_candidates_ranked(
        v2, base, target_id
    )

    for author_match, support, qid in ranked_direct[:direct_cap]:
        add(candidates, qid)

    # ------------------------------------------------------------
    # Author -> P50 route:
    # frozen K=5.
    # This is copied from the current benchmark logic.
    # ------------------------------------------------------------
    author_qids = [
        r[0]
        for r in v2.execute("""
            SELECT DISTINCT author_qid
            FROM target_author_matches_v2
            WHERE target_id=?
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
              ON e.qid=p.item_qid
            WHERE p.author_qid=?
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

        # Exact title matches: always retain, but aggregate editions.
        for exact, score, qid, parents in scored:
            if not exact:
                continue

            if parents:
                for parent in parents:
                    add(candidates, parent)
            else:
                add(candidates, qid)

        # Frozen hard top-5 fuzzy shortlist.
        ranked = sorted(
            scored,
            key=lambda x: (-x[1], x[2]),
        )

        for exact, score, qid, parents in ranked[:AUTHOR_FUZZY_K]:
            if parents:
                for parent in parents:
                    add(candidates, parent)
            else:
                add(candidates, qid)

    return candidates


def evaluate_cap(v2, base, df, cap):
    positive = df[df["gold_decision"].isin(["MATCH", "AMBIGUOUS"])]

    primary_hits = 0
    set_hits = 0
    counts = []
    misses = []

    for _, r in df.iterrows():
        candidates = candidates_for_target(
            v2,
            base,
            r["target_id"],
            r["title"],
            cap,
        )

        counts.append(len(candidates))

        if r["gold_decision"] not in ("MATCH", "AMBIGUOUS"):
            continue

        gold_primary = r["gold_selected_qid"]
        gold_all = gold_set(r)

        if gold_primary in candidates:
            primary_hits += 1

        if gold_all & candidates:
            set_hits += 1
        else:
            misses.append(
                (
                    r["target_id"],
                    r["title"],
                    r["author"],
                    sorted(gold_all),
                    len(candidates),
                )
            )

    n_pos = len(positive)

    return {
        "cap": cap,
        "primary_hits": primary_hits,
        "set_hits": set_hits,
        "n_pos": n_pos,
        "primary_recall": primary_hits / n_pos,
        "set_recall": set_hits / n_pos,
        "mean_candidates": mean(counts),
        "median_candidates": median(counts),
        "p90_candidates": float(np.percentile(counts, 90)),
        "p95_candidates": float(np.percentile(counts, 95)),
        "p99_candidates": float(np.percentile(counts, 99)),
        "max_candidates": max(counts),
        "misses": misses,
    }


def main():
    v2 = sqlite3.connect(V2_DB)
    base = sqlite3.connect(BASE_DB)

    df = pd.read_csv(BENCH, dtype=str).fillna("")

    results = []

    for cap in DIRECT_CAPS:
        x = evaluate_cap(v2, base, df, cap)
        results.append(x)

        print(f"\nDIRECT CAP = {cap}")
        print(
            f"primary recall: "
            f"{x['primary_hits']}/{x['n_pos']} = "
            f"{x['primary_recall']:.3f}"
        )
        print(
            f"set-aware recall: "
            f"{x['set_hits']}/{x['n_pos']} = "
            f"{x['set_recall']:.3f}"
        )
        print(
            "candidate count:"
            f" median={x['median_candidates']:.1f}"
            f" | p95={x['p95_candidates']:.1f}"
            f" | max={x['max_candidates']}"
        )

        if x["misses"]:
            print("MISSES:")
            for m in x["misses"]:
                print(" ", m)

    print("\nSUMMARY")

    summary = pd.DataFrame([
        {
            "direct_cap": x["cap"],
            "primary_recall": x["primary_recall"],
            "set_recall": x["set_recall"],
            "mean_candidates": x["mean_candidates"],
            "median_candidates": x["median_candidates"],
            "p90_candidates": x["p90_candidates"],
            "p95_candidates": x["p95_candidates"],
            "p99_candidates": x["p99_candidates"],
            "max_candidates": x["max_candidates"],
        }
        for x in results
    ])

    print(summary.to_string(index=False, float_format=lambda x: f"{x:.3f}"))


if __name__ == "__main__":
    main()
