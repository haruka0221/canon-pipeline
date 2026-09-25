#!/usr/bin/env python3

import json
import re
import time
from pathlib import Path

import pandas as pd
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]

MODEL = "gpt-5.6-luna"

INPUT = ROOT / "derived/goodreads_llm_review_pilot50_v3.tsv"
PROMPT_FILE = ROOT / "prompts/goodreads_identity_review_v3.txt"
OUTPUT = ROOT / "derived/goodreads_llm_review_pilot50_v3_results.tsv"

client = OpenAI()

ALLOWED_DECISIONS = {
    "MATCH",
    "NO_MATCH",
    "RELATED_NOT_SAME_WORK",
    "AMBIGUOUS",
}

ALLOWED_CONFIDENCE = {
    "HIGH",
    "MEDIUM",
    "LOW",
}

stats = {
    "api_calls": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "api_errors": 0,
    "invalid_json": 0,
    "empty_outputs": 0,
}


def extract_json(text):
    text = (text or "").strip()

    # tolerate accidental markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # first try whole response
    try:
        obj = json.loads(text)
    except Exception:
        # fallback: extract first JSON object
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            raise ValueError("No JSON object found")
        obj = json.loads(m.group(0))

    decision = str(obj.get("decision", "")).strip()
    confidence = str(obj.get("confidence", "")).strip()
    reason = str(obj.get("reason", "")).strip()

    if decision not in ALLOWED_DECISIONS:
        raise ValueError(f"invalid decision: {decision!r}")

    if confidence not in ALLOWED_CONFIDENCE:
        raise ValueError(f"invalid confidence: {confidence!r}")

    if not reason:
        raise ValueError("empty reason")

    return {
        "decision": decision,
        "confidence": confidence,
        "reason": reason,
    }


def call_luna(prompt):
    last_error = None

    # retry only for API/empty/invalid-output failures
    for attempt in range(3):
        try:
            response = client.responses.create(
                model=MODEL,
                input=prompt,
                reasoning={"effort": "medium"},
                max_output_tokens=1024,
            )

            stats["api_calls"] += 1

            if getattr(response, "usage", None):
                stats["input_tokens"] += (
                    getattr(response.usage, "input_tokens", 0) or 0
                )
                stats["output_tokens"] += (
                    getattr(response.usage, "output_tokens", 0) or 0
                )

            text = (response.output_text or "").strip()

            if not text:
                stats["empty_outputs"] += 1
                last_error = "empty output"
                print("    [empty output; retry]")
                time.sleep(2)
                continue

            try:
                return extract_json(text), text
            except Exception as e:
                stats["invalid_json"] += 1
                last_error = f"invalid output: {e}; raw={text[:500]!r}"
                print(f"    [invalid JSON; retry: {e}]")
                time.sleep(2)
                continue

        except Exception as e:
            stats["api_errors"] += 1
            last_error = repr(e)
            print(f"    [API error; retry: {e}]")
            time.sleep(3 + attempt * 2)

    raise RuntimeError(last_error or "unknown API failure")


def make_case_prompt(base_prompt, row):
    case = {
        "open_library": {
            "work_key": row["ol_work_key"],
            "title": row["ol_title"],
            "author": row["ol_author_name"],
            "first_publish_year": row["ol_first_publish_year"],
        },
        "goodreads": {
            "work_id": row["goodreads_work_id"],
            "title_match_type": row["title_match_type"],
            "original_title": row["gr_original_title"],
            "original_publication_year":
                row["gr_original_publication_year"],
            "matched_book_titles": row["matched_book_titles"],
            "contributors": row["goodreads_contributors"],
        },
    }

    return (
        base_prompt
        + "\n\nCASE TO REVIEW:\n"
        + json.dumps(case, ensure_ascii=False, indent=2)
    )


def save(df):
    df.to_csv(
        OUTPUT,
        sep="\t",
        index=False,
    )


def main():
    base_prompt = PROMPT_FILE.read_text(encoding="utf-8")

    source = pd.read_csv(
        INPUT,
        sep="\t",
        dtype=str,
    ).fillna("")

    # Resume from prior output if present.
    if OUTPUT.exists():
        old = pd.read_csv(
            OUTPUT,
            sep="\t",
            dtype=str,
        ).fillna("")

        old_by_key = {
            r["ol_work_key"]: r
            for _, r in old.iterrows()
            if r.get("review_decision", "")
        }

        for i, row in source.iterrows():
            wk = row["ol_work_key"]

            if wk in old_by_key:
                prev = old_by_key[wk]
                source.at[i, "review_decision"] = (
                    prev["review_decision"]
                )
                source.at[i, "review_confidence"] = (
                    prev["review_confidence"]
                )
                source.at[i, "review_reason"] = (
                    prev["review_reason"]
                )

        print(
            "resuming completed:",
            sum(source["review_decision"] != ""),
        )

    total = len(source)

    for i, row in source.iterrows():
        if row["review_decision"]:
            continue

        print(
            f"[{i + 1}/{total}] "
            f"{row['ol_title']} | "
            f"{row['ol_author_name']}"
        )

        prompt = make_case_prompt(base_prompt, row)

        try:
            result, raw = call_luna(prompt)

            source.at[i, "review_decision"] = (
                result["decision"]
            )
            source.at[i, "review_confidence"] = (
                result["confidence"]
            )
            source.at[i, "review_reason"] = (
                result["reason"]
            )

            print(
                f"    {result['decision']} / "
                f"{result['confidence']} / "
                f"{result['reason']}"
            )

        except Exception as e:
            print(f"    FAILED: {e}")

        # Save after every case.
        save(source)
        time.sleep(0.2)

    print("\n=== SUMMARY ===")

    done = source[source["review_decision"] != ""]

    if len(done):
        print(
            done["review_decision"]
            .value_counts()
            .to_string()
        )

        print("\nconfidence:")
        print(
            done["review_confidence"]
            .value_counts()
            .to_string()
        )

    print("\ncompleted:", len(done), "/", total)
    print("api_calls:", stats["api_calls"])
    print("input_tokens:", stats["input_tokens"])
    print("output_tokens:", stats["output_tokens"])
    print("api_errors:", stats["api_errors"])
    print("invalid_json:", stats["invalid_json"])
    print("empty_outputs:", stats["empty_outputs"])
    print("output:", OUTPUT)


if __name__ == "__main__":
    main()
