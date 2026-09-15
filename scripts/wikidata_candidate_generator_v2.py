#!/usr/bin/env python3

import json
from collections import Counter, defaultdict
from difflib import SequenceMatcher

from build_wikidata_resolution_v2_evidence import normalize_v2


# Frozen after development on the adjudicated 130-item benchmark.
DIRECT_CAP = 5
AUTHOR_FUZZY_K = 5

# Candidate packets should not duplicate thousands of manifestation QIDs.
# Full provenance remains preserved in the v2 evidence database.
MAX_VIA_EXAMPLES = 10


def load_json(s):
    if not s:
        return []
    try:
        x = json.loads(s)
        return x if isinstance(x, list) else []
    except Exception:
        return []


def entity_titles(label, aliases_json, p1476_json):
    out = []

    if label:
        out.append(label)

    for x in load_json(aliases_json):
        if isinstance(x, str) and x:
            out.append(x)

    for x in load_json(p1476_json):
        if isinstance(x, dict):
            text = x.get("text")
            if text:
                out.append(text)
        elif isinstance(x, str) and x:
            out.append(x)

    return list(dict.fromkeys(out))


def similarity(a, b):
    na = normalize_v2(a or "")
    nb = normalize_v2(b or "")

    if not na or not nb:
        return 0.0

    return SequenceMatcher(None, na, nb).ratio()


def entity_p50(v2, base, qid):
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


def conceptual_qids(qid, p629_json=None, p9745_json=None):
    """
    Candidate-level aggregation only.

    If an item explicitly points to a parent/original work, use that
    work-level QID as the candidate. Otherwise retain the item itself.

    The child item is NOT deleted from the evidence database.
    """
    related = []

    related.extend(load_json(p629_json))
    related.extend(load_json(p9745_json))

    related = list(dict.fromkeys(
        x for x in related if x
    ))

    return related if related else [qid]


def add_candidate(
    store,
    qid,
    source,
    score=None,
    via=None,
    direct_support=0,
    direct_author_match=False,
):
    if not qid:
        return

    if qid not in store:
        store[qid] = {
            "qid": qid,
            "sources": set(),
            "score": None,
            "via": set(),
            "direct_support": 0,
            "direct_author_match": False,
        }

    x = store[qid]
    x["sources"].add(source)

    if score is not None:
        if x["score"] is None or score > x["score"]:
            x["score"] = score

    if via:
        if isinstance(via, (list, tuple, set)):
            for v in via:
                if len(x["via"]) >= MAX_VIA_EXAMPLES:
                    break
                if v:
                    x["via"].add(v)
        elif len(x["via"]) < MAX_VIA_EXAMPLES:
            x["via"].add(via)

    x["direct_support"] = max(
        x["direct_support"],
        int(direct_support or 0),
    )

    if direct_author_match:
        x["direct_author_match"] = True


def build_candidates(
    v2,
    base,
    target_id,
    title,
    direct_cap=DIRECT_CAP,
    author_fuzzy_k=AUTHOR_FUZZY_K,
):
    candidates = {}

    # ------------------------------------------------------------
    # Resolve author-name evidence first because it is also used
    # to rank direct-title candidates.
    # ------------------------------------------------------------
    author_qids = [
        r[0]
        for r in v2.execute("""
            SELECT DISTINCT author_qid
            FROM target_author_matches_v2
            WHERE target_id=?
        """, (target_id,))
    ]

    author_qid_set = set(author_qids)

    # ------------------------------------------------------------
    # 1. Direct-title route
    #
    # Raw manifestations/translations remain in the evidence DB.
    # Candidate shortlist is aggregated to conceptual-work QIDs.
    #
    # Frozen ranking:
    #   1. P50 compatibility with resolved author candidates
    #   2. manifestation/direct-evidence support count
    #   3. QID as deterministic tie-break
    #
    # Hard cap = 5.
    # ------------------------------------------------------------
    support = Counter()
    via = defaultdict(set)
    source_map = defaultdict(set)

    rows = v2.execute("""
        SELECT
            t.qid,
            t.source,
            e.p629_json,
            e.p9745_json
        FROM target_title_matches_v2 t
        LEFT JOIN wikidata_entities_v2 e
          ON e.qid=t.qid
        WHERE t.target_id=?
    """, (target_id,)).fetchall()

    for qid, source, p629_json, p9745_json in rows:
        cqids = conceptual_qids(
            qid,
            p629_json,
            p9745_json,
        )

        for cqid in cqids:
            support[cqid] += 1
            via[cqid].add(qid)
            source_map[cqid].add(
                "direct_title:" + str(source)
            )

    ranked_direct = []

    for qid, n_support in support.items():
        p50 = entity_p50(v2, base, qid)
        author_match = bool(author_qid_set & p50)

        ranked_direct.append(
            (author_match, n_support, qid)
        )

    ranked_direct.sort(
        key=lambda x: (
            -int(x[0]),
            -x[1],
            x[2],
        )
    )

    for author_match, n_support, qid in ranked_direct[:direct_cap]:
        for source in sorted(source_map[qid]):
            add_candidate(
                candidates,
                qid,
                source,
                score=1.0,
                via=sorted(via[qid])[:MAX_VIA_EXAMPLES],
                direct_support=n_support,
                direct_author_match=author_match,
            )

    # ------------------------------------------------------------
    # 2. Author -> P50 route
    #
    # Exact normalized-title matches are retained.
    # Fuzzy shortlist is hard top-5 PER AUTHOR QID.
    # No tie expansion.
    #
    # Manifestations are aggregated to P629 parents when available.
    # ------------------------------------------------------------
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

        # Exact matches are not subject to fuzzy K.
        for exact, score, qid, parents in scored:
            if not exact:
                continue

            cqids = parents if parents else [qid]

            for cqid in cqids:
                add_candidate(
                    candidates,
                    cqid,
                    "author_p50_exact",
                    score=score,
                    via=[author_qid, qid],
                )

        # Frozen hard top-5 fuzzy shortlist per author candidate.
        ranked = sorted(
            scored,
            key=lambda x: (-x[1], x[2]),
        )

        for exact, score, qid, parents in ranked[:author_fuzzy_k]:
            cqids = parents if parents else [qid]

            for cqid in cqids:
                add_candidate(
                    candidates,
                    cqid,
                    "author_p50_fuzzy",
                    score=score,
                    via=[author_qid, qid],
                )

    # ------------------------------------------------------------
    # Deterministic output.
    # Full raw evidence stays in SQLite; this is only the judge
    # candidate shortlist.
    # ------------------------------------------------------------
    out = []

    for x in candidates.values():
        out.append({
            "qid": x["qid"],
            "sources": sorted(x["sources"]),
            "score": x["score"],
            "via": sorted(x["via"]),
            "direct_support": x["direct_support"],
            "direct_author_match": x["direct_author_match"],
        })

    out.sort(
        key=lambda x: (
            -int(x["direct_author_match"]),
            -(x["score"] if x["score"] is not None else -1),
            -x["direct_support"],
            x["qid"],
        )
    )

    return author_qids, out
