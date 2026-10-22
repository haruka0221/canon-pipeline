#!/usr/bin/env python3
"""Continue frozen R2+A1 Luna production after the completed first 1,000.

v0_2: On schema/semantic validation failure, save the rejected API output to an
append-only separate local journal and retry the SAME candidate once. Never
relax validation, fabricate a label, or touch prior 1,012+ valid checkpoints.
If a second response is invalid, stop for inspection instead of silently
skipping or accepting an invalid result. Same frozen model/prompt/schema/input.


Place in canon-pipeline-openalex-a2val/scripts/ alongside the first-1000 runner.

DRY PREPARE (NO API):
    python -B scripts/run_openalex_r2a1_production_continue_v0_1.py --prepare --start-batch 1 --end-batch 9
DRY STATUS (NO API):
    python -B scripts/run_openalex_r2a1_production_continue_v0_1.py --start-batch 1 --end-batch 9
PAID, RESUMABLE:
    python -B scripts/run_openalex_r2a1_production_continue_v0_1.py --execute --start-batch 1 --end-batch 9 --max-new 9000

Each batch has at most 1,000 NEW pair IDs. Batch 0000 is immutable; it is
verified, never re-executed. Preexisting queue and first-1000 config are read
and integrity-checked. The exact development prompt, schema, model and
case_payload from the first-1000 runner are reused without modifications.
LLM labels are provisional target attribution, NOT human-gold/scope/visibility.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from datetime import datetime, timezone

import pandas as pd
import pyarrow.dataset as ds

import run_openalex_r2a1_production_first_1000_v0_1 as first

OUT = first.OUT
TOTAL = first.PRODUCTION_EXPECTED  # 223115
BATCH_SIZE = 1000
MAX_BATCH = (TOTAL - 1) // BATCH_SIZE
FIRST_1000_HASH = "8536688e59f93054bbc40a6cf8bc54e6cefc80b84001b996ad39f0c8c083efc7"
RELEASE = "openalex-r2a1-production-continuation-batches-v0_1"


def digest(path: Path) -> str:
    return first.file_hash(path)


def batchdir(batch_number: int) -> Path:
    return OUT / f"batch_{batch_number:04d}_continuation_v0_1"


def batchpaths(batch_number: int):
    directory = batchdir(batch_number)
    return (directory / "input.parquet", directory / "run_config.json",
            directory / "model_results.jsonl")


def verify_source() -> pd.DataFrame:
    """Require that previously completed 1,000 and its frozen queue survive unchanged."""
    first_batch = first.loaded_batch()  # frozen sample, queue, prompt, schema, BIB hash
    if len(first.saved_results(set(first_batch.baseline_candidate_id))) != 1000:
        raise RuntimeError("FIRST batch does not contain exactly 1,000 accepted saved results")
    if digest(first.RESULTS) != FIRST_1000_HASH:
        raise RuntimeError("FIRST 1000 SHA mismatch: STOP; do not alter baseline data")
    queue = pd.read_parquet(first.QUEUE)
    if len(queue) != TOTAL or not queue.baseline_candidate_id.is_unique:
        raise RuntimeError("Frozen 223,115-pair production queue unexpected")
    if queue.production_queue_ordinal.tolist() != list(range(TOTAL)):
        raise RuntimeError("Frozen production ordinals not consecutive")
    if list(queue.head(1000).baseline_candidate_id) != list(first_batch.baseline_candidate_id):
        raise RuntimeError("Previously completed 1,000 and frozen queue differ")
    return queue


def expected_config(batch_number: int, batch: pd.DataFrame, path: Path) -> dict:
    lo = batch_number * BATCH_SIZE
    hi = min((batch_number + 1) * BATCH_SIZE, TOTAL)
    if len(batch) != hi - lo or batch.production_queue_ordinal.tolist() != list(range(lo, hi)):
        raise RuntimeError("Batch order mismatch")
    return {
        "release": RELEASE,
        "model": first.MODEL,
        "batch_number": batch_number,
        "queue_ordinal_start": lo,
        "queue_ordinal_end_exclusive": hi,
        "count": len(batch),
        "queue_sha256": digest(first.QUEUE),
        "first_1000_config_sha256": digest(first.CFG),
        "first_1000_result_sha256": FIRST_1000_HASH,
        "frozen_sample_manifest_sha256": digest(first.FROZEN / "sampling_manifest_v0_1.json"),
        "source_native_bibliographic_evidence_sha256": digest(first.dev20.BIB),
        "development_prompt_sha256": hashlib.sha256(first.dev20.PROMPT.encode("utf-8")).hexdigest(),
        "development_schema_sha256": hashlib.sha256(json.dumps(first.dev20.SCHEMA, sort_keys=True).encode()).hexdigest(),
        "input_parquet_sha256": digest(path),
        "case_ids_sha256": hashlib.sha256("\n".join(batch.baseline_candidate_id).encode("utf-8")).hexdigest(),
        "execution": "Responses API store=false, sequential, strict json schema, per-result fsync",
        "human_labels_used": False,
        "holdout_predictions_used": False,
    }


def verify_batch(batch_number: int, queue: pd.DataFrame) -> pd.DataFrame:
    inp, cfgpath, _ = batchpaths(batch_number)
    if not inp.is_file() or not cfgpath.is_file():
        raise FileNotFoundError(f"Batch {batch_number:04d} not prepared; run --prepare")
    batch = pd.read_parquet(inp).fillna("")
    lo = batch_number * BATCH_SIZE
    hi = min((batch_number + 1) * BATCH_SIZE, TOTAL)
    if (len(batch) != hi - lo or not batch.baseline_candidate_id.is_unique or
        list(batch.baseline_candidate_id) != list(queue.iloc[lo:hi].baseline_candidate_id) or
        list(batch.project_work_id) != list(queue.iloc[lo:hi].project_work_id) or
        list(batch.openalex_work_id) != list(queue.iloc[lo:hi].openalex_work_id)):
        raise RuntimeError(f"Prepared batch {batch_number:04d} differs from frozen queue")
    cfg = json.loads(cfgpath.read_text(encoding="utf-8"))
    if cfg != expected_config(batch_number, batch, inp):
        raise RuntimeError(f"Prepared batch {batch_number:04d} integrity/config mismatch")
    return batch


def make_input(batch_number: int, queue: pd.DataFrame,
               oa_dataset, bib: pd.DataFrame) -> pd.DataFrame:
    lo = batch_number * BATCH_SIZE
    hi = min((batch_number + 1) * BATCH_SIZE, TOTAL)
    selected = queue.iloc[lo:hi].copy()
    oa_ids = sorted(set(selected.openalex_work_id))
    oa = oa_dataset.to_table(
        columns=["openalex_work_id", "display_name", "abstract", "publication_year", "doi"],
        filter=ds.field("openalex_work_id").isin(oa_ids)).to_pandas()
    if oa.openalex_work_id.duplicated().any() or set(oa.openalex_work_id) != set(oa_ids):
        raise RuntimeError(f"Frozen OA metadata missing/duplicate in batch {batch_number:04d}")
    oa.rename(columns={"display_name": "openalex_title", "abstract": "openalex_abstract",
                       "publication_year": "openalex_publication_year", "doi": "openalex_doi"}, inplace=True)
    selected = selected.merge(oa, on="openalex_work_id", how="left", validate="many_to_one")
    selected = selected.merge(bib, on="project_work_id", how="left", validate="many_to_one", indicator=True)
    if not selected._merge.eq("both").all():
        raise RuntimeError("Some Project W lack frozen bibliographic evidence")
    selected.drop(columns=["_merge"], inplace=True)
    for field in selected.columns:
        if field != "production_queue_ordinal":
            selected[field] = selected[field].fillna("").astype(str)
    if selected.baseline_candidate_id.duplicated().any():
        raise RuntimeError("Batch has repeated candidate IDs")
    for _, row in selected.iterrows():
        payload = first.dev20.case_payload(row)
        doc = payload["openalex_document"]
        if not isinstance(doc["title"], str) or not isinstance(doc["abstract"], str):
            raise RuntimeError("OpenAlex text fields are not strings; blanks are permitted")
    return selected


def prepare(start: int, end: int) -> None:
    queue = verify_source()
    bib = first.read_tsv(first.dev20.BIB, first.BIB_COLS)
    if len(bib) != 32066 or not bib.project_work_id.is_unique:
        raise RuntimeError("Frozen 32,066 W bibliography unexpectedly changed")
    oa_dataset = ds.dataset(str(first.samplemaker.OA), format="parquet")
    for n in range(start, end + 1):
        directory = batchdir(n)
        if directory.exists():
            batch = verify_batch(n, queue)
            print(f"PREPARED ALREADY batch {n:04d}: {len(batch)}; no changes", flush=True)
            continue
        batch = make_input(n, queue, oa_dataset, bib)
        stage = Path(tempfile.mkdtemp(prefix=f".batch_{n:04d}_stage_", dir=OUT))
        try:
            input_path = stage / "input.parquet"
            batch.to_parquet(input_path, index=False)
            config = expected_config(n, batch, input_path)
            (stage / "run_config.json").write_text(
                json.dumps(config, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            if directory.exists():
                raise RuntimeError(f"Concurrent batch preparation: {directory}")
            stage.rename(directory)
            print(f"PREPARED batch {n:04d}: {len(batch)} candidates, no API", flush=True)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    print("DRY PREPARATION COMPLETE: frozen queue and first 1000 untouched", flush=True)


def load_saved(batch_number: int, batch: pd.DataFrame) -> list[dict]:
    _, _, path = batchpaths(batch_number)
    if not path.is_file():
        return []
    keyed = {row.baseline_candidate_id: row for row in batch.itertuples(index=False)}
    seen = set()
    records = []
    with path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            if not line.strip():
                raise RuntimeError(f"Blank checkpoint line {i} in batch {batch_number:04d}")
            item = json.loads(line)
            cid = item.get("baseline_candidate_id")
            if cid not in keyed or cid in seen:
                raise RuntimeError(f"Duplicate/unknown candidate ID in batch {batch_number:04d}, line {i}")
            ref = keyed[cid]
            if (item.get("project_work_id") != ref.project_work_id or
                item.get("openalex_work_id") != ref.openalex_work_id or
                item.get("production_queue_ordinal") != int(ref.production_queue_ordinal)):
                raise RuntimeError("Saved record identity/ordinal differs from frozen batch")
            if (item.get("model") != first.MODEL or
                item.get("judgment") not in first.dev20.ALLOWED_REASONS or
                item.get("reason_code") not in first.dev20.ALLOWED_REASONS[item["judgment"]] or
                item.get("confidence") not in ("HIGH", "MEDIUM", "LOW") or
                item.get("identity_context_adequacy") not in ("SUFFICIENT", "INSUFFICIENT", "CONFLICTING")):
                raise RuntimeError(f"Invalid saved model response in batch {batch_number:04d}")
            seen.add(cid)
            records.append(item)
    return records


def status(start: int, end: int, queue: pd.DataFrame | None = None) -> int:
    if queue is None:
        queue = verify_source()
    total = 0
    for n in range(start, end + 1):
        if batchdir(n).exists():
            batch = verify_batch(n, queue)
            saved = load_saved(n, batch)
            print(f"batch {n:04d}: {len(saved):4d} / {len(batch):4d} saved", flush=True)
            total += len(saved)
        else:
            print(f"batch {n:04d}: NOT PREPARED", flush=True)
    print(f"Continuation total: {total} saved; with frozen first 1000: {total + 1000}", flush=True)
    return total


def validation_issues(label) -> list[str]:
    """Check the original strict schema AND the semantic judgment/reason contract."""
    if not isinstance(label, dict):
        return ["response_not_json_object"]
    issues = []
    expected = set(first.dev20.SCHEMA["required"])
    if set(label) != expected:
        issues.append("incorrect_output_keys")
    judgment = label.get("judgment")
    if judgment not in first.dev20.ALLOWED_REASONS:
        issues.append("invalid_judgment")
    elif label.get("reason_code") not in first.dev20.ALLOWED_REASONS[judgment]:
        issues.append("reason_code_mismatch_for_judgment")
    if label.get("confidence") not in ("HIGH", "MEDIUM", "LOW"):
        issues.append("invalid_confidence")
    if label.get("identity_context_adequacy") not in ("SUFFICIENT", "INSUFFICIENT", "CONFLICTING"):
        issues.append("invalid_identity_context_adequacy")
    if not isinstance(label.get("note"), str) or not label["note"].strip():
        issues.append("empty_or_invalid_note")
    return issues


def record_rejected_response(batch_number: int, row, response, issues: list[str], attempt: int) -> Path:
    """Store invalid model output for audit; NEVER append it to accepted results."""
    journal = batchdir(batch_number) / "model_validation_rejections_v0_2.jsonl"
    usage = getattr(response, "usage", None)
    item = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_id": row["baseline_candidate_id"],
        "project_work_id": row["project_work_id"],
        "openalex_work_id": row["openalex_work_id"],
        "production_queue_ordinal": int(row["production_queue_ordinal"]),
        "batch_number": batch_number,
        "attempt_within_this_invocation": attempt,
        "model": first.MODEL,
        "response_id": getattr(response, "id", None),
        "response_status": getattr(response, "status", None),
        "validation_issues": issues,
        "raw_model_output": getattr(response, "output_text", None),
        "input_tokens": int(usage.input_tokens or 0) if usage else 0,
        "output_tokens": int(usage.output_tokens or 0) if usage else 0,
        "review_status": "REJECTED_NOT_AN_ACCEPTED_ATTRIBUTION",
    }
    with journal.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return journal


def execute(start: int, end: int, limit: int, validation_attempts: int = 2) -> None:
    queue = verify_source()
    for n in range(start, end + 1):
        verify_batch(n, queue)  # fail before the first paid call if not prepared
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY absent; no API calls made")
    from openai import OpenAI
    client = OpenAI(timeout=120.0, max_retries=2)
    # SAME lock file used by the original 1,000-runner.
    lock_path = OUT / ".paid_execution.lock"
    with lock_path.open("a", encoding="utf-8") as lock_fh:
        try:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Production runner already active; will not run concurrently") from exc
        left = limit
        run_in, run_out = 0, 0
        for n in range(start, end + 1):
            batch = verify_batch(n, queue)
            saved = load_saved(n, batch)
            already = {v["baseline_candidate_id"] for v in saved}
            todo = batch.loc[~batch.baseline_candidate_id.isin(already)].head(left)
            print(f"=== BATCH {n:04d}: saved {len(saved)}/{len(batch)}, new this run {len(todo)} ===", flush=True)
            if todo.empty:
                continue
            _, _, results = batchpaths(n)
            for _, row in todo.iterrows():
                try:
                    # Only response-validation failures are retried; API/HTTP failures
                    # remain fail-stop under the original exception policy.
                    for attempt in range(1, validation_attempts + 1):
                        response = client.responses.create(
                            model=first.MODEL,
                            instructions=first.dev20.PROMPT,
                            input=json.dumps(first.dev20.case_payload(row), ensure_ascii=False),
                            text={"format": {"type": "json_schema", "name": "literary_attribution_dev_v0_1",
                                             "schema": first.dev20.SCHEMA, "strict": True}},
                            store=False,
                        )
                        if response.status != "completed" or not response.output_text:
                            raise RuntimeError(f"Incomplete model response: {response.status}")
                        try:
                            label = json.loads(response.output_text)
                            issues = validation_issues(label)
                        except (json.JSONDecodeError, UnicodeError):
                            label = None
                            issues = ["response_not_valid_json"]
                        if not issues:
                            break
                        journal = record_rejected_response(n, row, response, issues, attempt)
                        print(f"VALIDATION REJECTED batch {n:04d} ordinal "
                              f"{int(row['production_queue_ordinal'])}: "
                              f"{','.join(issues)} (attempt {attempt}/{validation_attempts}); "
                              f"logged to {journal.name}", flush=True)
                        if attempt == validation_attempts:
                            raise RuntimeError(
                                f"Model response invalid after {validation_attempts} attempts "
                                f"for {row['baseline_candidate_id']}; "
                                f"reason={','.join(issues)}; audit journal={journal}")
                    usage = response.usage
                    record = {
                        "baseline_candidate_id": row["baseline_candidate_id"],
                        "project_work_id": row["project_work_id"],
                        "openalex_work_id": row["openalex_work_id"],
                        "production_queue_ordinal": int(row["production_queue_ordinal"]),
                        "model": first.MODEL,
                        "response_id": response.id,
                        "input_tokens": int(usage.input_tokens or 0) if usage else 0,
                        "output_tokens": int(usage.output_tokens or 0) if usage else 0,
                        **label,
                    }
                    with results.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                        fh.flush()
                        os.fsync(fh.fileno())
                    already.add(record["baseline_candidate_id"])
                    left -= 1
                    run_in += record["input_tokens"]
                    run_out += record["output_tokens"]
                    if len(already) % 25 == 0 or len(already) == len(batch):
                        print(f"PROGRESS batch {n:04d}: {len(already)}/{len(batch)} saved; budget left: {left}", flush=True)
                except Exception as exc:
                    print("STOP ON API/VALIDATION ERROR:", type(exc).__name__, str(exc)[:250], flush=True)
                    print("Saved responses are on disk; use identical --execute command to resume", flush=True)
                    raise SystemExit(1) from exc
            print(f"BATCH {n:04d} recorded: {len(already)}/{len(batch)}", flush=True)
            if left == 0:
                break
        print(f"PAID INVOCATION COMPLETE: {limit-left} new successes; tokens in/out {run_in}/{run_out}", flush=True)
        status(start, end, queue)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--prepare", action="store_true", help="Prepare batch inputs without API calls")
    g.add_argument("--execute", action="store_true", help="Paid calls, restartable")
    p.add_argument("--start-batch", type=int, default=1)
    p.add_argument("--end-batch", type=int, default=9)
    p.add_argument("--max-new", type=int, default=10)
    p.add_argument("--validation-attempts", type=int, default=2,
                   help="Max model API responses for one candidate when output fails validation (1..3); default 2")
    args = p.parse_args()
    if not 1 <= args.start_batch <= args.end_batch <= MAX_BATCH:
        p.error(f"Batches must satisfy 1 <= start <= end <= {MAX_BATCH}")
    if not 1 <= args.max_new <= 10000:
        p.error("--max-new must be 1..10000; run separate invocations for larger amounts")
    if not 1 <= args.validation_attempts <= 3:
        p.error("--validation-attempts must be 1..3")
    if args.prepare:
        prepare(args.start_batch, args.end_batch)
    elif args.execute:
        execute(args.start_batch, args.end_batch, args.max_new, args.validation_attempts)
    else:
        status(args.start_batch, args.end_batch)


if __name__ == "__main__":
    main()
