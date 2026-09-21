#!/usr/bin/env python3

import json
from collections import Counter
from pathlib import Path

import pandas as pd


ROOT = Path("derived/wikidata_production")
OUT = ROOT / "full_34789_v6_20260918"

POP = ROOT / "population_34789_2026-02-28.tsv"
SHORT = OUT / "candidate_shortlists_items_only.jsonl"
JUDG = OUT / "judgments_v6_production.jsonl"

OUT_TSV = OUT / "final_resolution_v6_34789.tsv"
OUT_JSONL = OUT / "final_resolution_v6_34789.jsonl"
OUT_SUMMARY = OUT / "final_resolution_v6_34789_summary.json"


def main():
    pop = pd.read_csv(POP, sep="\t", dtype=str).fillna("")

    if len(pop) != 34789:
        raise RuntimeError(f"population rows != 34789: {len(pop)}")

    if pop["target_id"].duplicated().any():
        raise RuntimeError("duplicate target_id in population")

    short = {}
    with SHORT.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            x = json.loads(line)
            tid = x["target_id"]
            if tid in short:
                raise RuntimeError(f"duplicate shortlist target: {tid}")
            short[tid] = x

    if len(short) != 34789:
        raise RuntimeError(f"shortlist rows != 34789: {len(short)}")

    judg = {}
    with JUDG.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            x = json.loads(line)
            tid = x["target_id"]
            if tid in judg:
                raise RuntimeError(f"duplicate judgment target: {tid}")
            judg[tid] = x

    if len(judg) != 24015:
        raise RuntimeError(f"judgment rows != 24015: {len(judg)}")

    rows = []

    for _, r in pop.iterrows():
        tid = r["target_id"]
        s = short.get(tid)

        if s is None:
            raise RuntimeError(f"missing shortlist: {tid}")

        candidates = s.get("candidates", [])
        n = len(candidates)

        if n == 0:
            if tid in judg:
                raise RuntimeError(
                    f"zero-candidate target unexpectedly judged: {tid}"
                )

            out = {
                "target_id": tid,
                "title": r["title"],
                "author": r["author"],
                "year": r["year"],
                "candidate_count": 0,
                "decision": "NO_MATCH",
                "selected_qid": "",
                "alternative_qids": [],
                "confidence": "",
                "issue_codes": ["no_candidate_retrieved"],
                "reason": "",
                "resolution_stage": "candidate_retrieval",
                "decision_source": "deterministic_no_candidate",
                "model": "",
                "prompt_sha256": "",
                "context_safe_fallback": False,
            }

        else:
            j = judg.get(tid)
            if j is None:
                raise RuntimeError(
                    f"candidate>0 target missing judgment: {tid}"
                )

            candidate_qids = {
                c["qid"] for c in candidates
            }

            selected = j.get("selected_qid")

            if selected and selected not in candidate_qids:
                raise RuntimeError(
                    f"selected QID outside candidates: {tid} {selected}"
                )

            out = {
                "target_id": tid,
                "title": r["title"],
                "author": r["author"],
                "year": r["year"],
                "candidate_count": n,
                "decision": j["decision"],
                "selected_qid": selected or "",
                "alternative_qids":
                    j.get("alternative_qids", []) or [],
                "confidence": j.get("confidence", ""),
                "issue_codes":
                    j.get("issue_codes", []) or [],
                "reason": j.get("reason", ""),
                "resolution_stage": "llm_judge",
                "decision_source": "gpt-5.6-luna_v6",
                "model": j.get("model", ""),
                "prompt_sha256":
                    j.get("prompt_sha256", ""),
                "context_safe_fallback":
                    bool(j.get("context_safe_fallback", False)),
            }

        rows.append(out)

    if len(rows) != 34789:
        raise RuntimeError(len(rows))

    ids = [x["target_id"] for x in rows]

    if len(set(ids)) != 34789:
        raise RuntimeError("duplicate final target IDs")

    stage_counts = Counter(
        x["resolution_stage"] for x in rows
    )

    decision_counts = Counter(
        x["decision"] for x in rows
    )

    judged_decisions = Counter(
        x["decision"]
        for x in rows
        if x["resolution_stage"] == "llm_judge"
    )

    selected_n = sum(
        bool(x["selected_qid"]) for x in rows
    )

    fallback_n = sum(
        x["context_safe_fallback"] for x in rows
    )

    summary = {
        "population_rows": len(rows),
        "resolution_stage_counts": dict(stage_counts),
        "overall_decision_counts": dict(decision_counts),
        "llm_judge_decision_counts": dict(judged_decisions),
        "selected_qid_rows": selected_n,
        "context_safe_fallback_rows": fallback_n,
        "zero_candidate_policy": (
            "NO_MATCH at candidate_retrieval stage; "
            "does not assert absence of a Wikidata work item"
        ),
    }

    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for x in rows:
            f.write(
                json.dumps(x, ensure_ascii=False) + "\n"
            )

    df = pd.DataFrame(rows)

    for col in ["alternative_qids", "issue_codes"]:
        df[col] = df[col].map(
            lambda x: json.dumps(x, ensure_ascii=False)
        )

    df.to_csv(
        OUT_TSV,
        sep="\t",
        index=False,
    )

    OUT_SUMMARY.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
