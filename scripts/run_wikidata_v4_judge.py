#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI


ALLOWED_DECISIONS = {"MATCH", "NO_MATCH", "AMBIGUOUS"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_ISSUES = {
    "duplicate_work_items",
    "edition_or_translation",
    "edition_without_work_item",
    "adaptation",
    "author_ambiguity",
    "missing_metadata",
    "title_variant",
    "wrong_work",
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def read_jsonl(path):
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def append_jsonl(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def extract_json_object(text):
    cleaned = str(text).replace("```json", "").replace("```", "").strip()

    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    a = cleaned.find("{")
    b = cleaned.rfind("}")
    if a >= 0 and b > a:
        obj = json.loads(cleaned[a:b + 1])
        if isinstance(obj, dict):
            return obj

    raise ValueError("Could not parse one JSON object")


def validate_judgment(obj, candidate_qids):
    decision = str(obj.get("decision", "")).upper().strip()
    if decision not in ALLOWED_DECISIONS:
        raise ValueError(f"invalid decision: {decision}")

    selected = obj.get("selected_qid")
    if selected in ("", "null", "None"):
        selected = None

    alts = obj.get("alternative_qids", []) or []
    if not isinstance(alts, list):
        raise ValueError("alternative_qids must be a list")
    alts = [str(x) for x in alts if str(x).strip()]

    confidence = str(obj.get("confidence", "")).lower().strip()
    if confidence not in ALLOWED_CONFIDENCE:
        raise ValueError(f"invalid confidence: {confidence}")

    issues = obj.get("issue_codes", []) or []
    if not isinstance(issues, list):
        raise ValueError("issue_codes must be a list")
    issues = [str(x).strip() for x in issues if str(x).strip()]

    unknown = [x for x in issues if x not in ALLOWED_ISSUES]
    if unknown:
        raise ValueError(f"unknown issue_codes: {unknown}")

    if decision == "NO_MATCH" and selected is not None:
        raise ValueError("NO_MATCH must have selected_qid=null")

    if decision == "MATCH" and not selected:
        raise ValueError("MATCH requires selected_qid")

    if selected and selected not in candidate_qids:
        raise ValueError(f"selected_qid not supplied: {selected}")

    bad = [q for q in alts if q not in candidate_qids]
    if bad:
        raise ValueError(f"alternative_qids not supplied: {bad}")

    return {
        "decision": decision,
        "selected_qid": selected,
        "alternative_qids": alts,
        "confidence": confidence,
        "issue_codes": issues,
        "reason": str(obj.get("reason", "")).strip(),
    }


def compact_packet(packet):
    candidates = []
    for c in packet.get("candidates", []):
        candidates.append({
            "qid": c["qid"],
            "sources": c.get("sources", []),
            "via": c.get("via", []),
            "title_score": c.get("title_score"),
            "direct_support": c.get("direct_support", 0),
            "direct_author_match": c.get("direct_author_match", False),
            "label": c.get("label", ""),
            "description": c.get("description", ""),
            "aliases": c.get("aliases", [])[:10],
            "stated_titles": c.get("stated_titles", []),
            "publication_dates": c.get("publication_dates", []),
            "instance_of": c.get("instance_of", []),
            "authors": c.get("authors", []),
            "edition_or_translation_of":
                c.get("edition_or_translation_of", []),
            "has_enwiki": c.get("has_enwiki", False),
        })

    return {
        "target": {
            "target_id": packet["target_id"],
            "title": packet["title"],
            "author": packet["author"],
            "year": packet.get("year", ""),
            "author_candidates": packet.get("author_candidates", []),
        },
        "candidates": candidates,
    }


def call_model(client, model, prompt, payload, max_output_tokens=900):
    user = json.dumps(payload, ensure_ascii=False, indent=2)
    last = None

    for attempt in range(6):
        try:
            r = client.responses.create(
                model=model,
                instructions=prompt,
                input=user,
                max_output_tokens=max_output_tokens,
            )
            text = (r.output_text or "").strip()
            if not text:
                raise RuntimeError("Empty model response")
            return text
        except Exception as e:
            last = e
            if attempt == 5:
                raise
            wait = min(60, 5 * (2 ** attempt))
            print(
                f"      model retry {attempt + 1}/6: "
                f"{type(e).__name__}: {e}; waiting {wait}s"
            )
            time.sleep(wait)

    raise RuntimeError(last)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--packets", type=Path, required=True)
    ap.add_argument("--prompt", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--model", default="gpt-5.6-luna")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    prompt = args.prompt.read_text(encoding="utf-8").strip()
    prompt_sha = hashlib.sha256(
        prompt.encode("utf-8")
    ).hexdigest()

    packets = read_jsonl(args.packets)
    if args.limit is not None:
        packets = packets[:args.limit]

    done = {}
    if args.output.exists():
        for x in read_jsonl(args.output):
            done[x["target_id"]] = x

    client = OpenAI()

    for i, packet in enumerate(packets, 1):
        tid = packet["target_id"]

        if tid in done:
            print(f"[{i}/{len(packets)}] SKIP {tid}")
            continue

        payload = compact_packet(packet)
        allowed = {
            c["qid"]
            for c in payload["candidates"]
        }

        print(
            f"[{i}/{len(packets)}] {tid} "
            f"{packet['title']} | candidates={len(allowed)}"
        )

        raw = call_model(
            client,
            args.model,
            prompt,
            payload,
        )

        try:
            judgment = validate_judgment(
                extract_json_object(raw),
                allowed,
            )
        except Exception as e:
            print(f"      validation retry: {e}")
            retry_payload = compact_packet(packet)
            retry_payload["validation_error"] = str(e)
            retry_payload["instruction"] = (
                "Return exactly one valid JSON object using only "
                "supplied candidate QIDs."
            )

            raw = call_model(
                client,
                args.model,
                prompt,
                retry_payload,
            )

            judgment = validate_judgment(
                extract_json_object(raw),
                allowed,
            )

        row = {
            "target_id": tid,
            "title": packet["title"],
            "author": packet["author"],
            "year": packet.get("year", ""),
            "candidate_count": packet.get("candidate_count", 0),
            **judgment,
            "model": args.model,
            "prompt_path": str(args.prompt),
            "prompt_sha256": prompt_sha,
            "judged_at": utc_now(),
            "raw_response": raw,
        }

        append_jsonl(args.output, row)

        print(
            f"      -> {row['decision']} "
            f"{row.get('selected_qid') or ''} "
            f"({row['confidence']})"
        )

    print("saved:", args.output)


if __name__ == "__main__":
    main()
