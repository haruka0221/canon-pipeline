#!/usr/bin/env python3
"""OpenAlex R2+A1 v7 / Luna production: switch only transport to the OpenAI Batch API.

Put alongside the existing production scripts in scripts/.

   # First 100 requests of BATCH 0010; no API on --stage
   python -B scripts/run_openalex_r2a1_production_batch_api_v0_1.py --stage --start-batch 10 --end-batch 10 --max-requests 100
   python -B scripts/run_openalex_r2a1_production_batch_api_v0_1.py --submit
   python -B scripts/run_openalex_r2a1_production_batch_api_v0_1.py --check
   python -B scripts/run_openalex_r2a1_production_batch_api_v0_1.py --collect

After pilot is collected, use --stage --start-batch 10 --end-batch 19 --max-requests 10000, etc.
Each stage is ONE async batch job; it must be collected (or have a final failure
reconciled) before the next stage. Stage only includes unsaved candidate pairs.

DO NOT run the synchronous production runner while an OpenAI Batch job is in
progress. Outputs are saved to the same per-1,000 result directories as v0_2,
with added Batch API provenance fields. Original 10,000 are preserved.

--stage: local computation only, no API. --submit: API upload + creates paid job.
--check: remote job status only. --collect: downloads / validates / imports results.
--status: local metadata only. --reconcile: recover uncertain create status.

The EXACT frozen model, prompt, schema, and case_payload come from the
already-tested synchronous production scripts. No scope/document quality labels
are inferred. No previously submitted / saved candidate is automatically rerun.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone

import run_openalex_r2a1_production_first_1000_v0_1 as first
import run_openalex_r2a1_production_continue_v0_2 as cont

ROOT = first.OUT / "batch_api_v0_1"
JOBS = ROOT / "jobs"
LATEST = ROOT / "latest_job.txt"
MAX_REQUESTS = 10000  # conservative < Batch API 50k/200MB; check model queue limits
MAX_BYTES = 190 * 1024 * 1024  # stop before official 200MB limit
TERMINAL = {"completed", "expired", "cancelled", "failed"}
ACTIVE = {"validating", "in_progress", "finalizing", "cancelling"}
MODEL = first.MODEL
RELEASE = "openalex-r2a1-production-batch-api-v0_1"


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(path: Path) -> str:
    return first.file_hash(path)


def atomic_json(path: Path, obj: dict) -> None:
    tmp = path.with_name(path.name + ".partial")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def atomic_text(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".partial")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def job_dirs():
    if not JOBS.exists():
        return []
    return sorted(p for p in JOBS.iterdir() if p.is_dir() and p.name.startswith("job_"))


def read_job(path: Path) -> dict:
    return json.loads((path / "state.json").read_text(encoding="utf-8"))


def selected_job_dir() -> Path:
    if not LATEST.exists():
        raise RuntimeError("No staged Batch API job; use --stage")
    name = LATEST.read_text(encoding="utf-8").strip()
    if not name.startswith("job_") or Path(name).name != name:
        raise RuntimeError("Invalid latest job reference")
    path = JOBS / name
    if not (path / "state.json").is_file():
        raise RuntimeError(f"Job state missing: {path}")
    return path


def global_lock():
    """Use same nonblocking lock as synchronous runner for local operations."""
    first.OUT.mkdir(parents=True, exist_ok=True)
    path = first.OUT / ".paid_execution.lock"
    fh = path.open("a", encoding="utf-8")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        fh.close()
        raise RuntimeError("Another local production action is running. Do not run concurrently") from exc
    return fh


def validate_staging_environment():
    if not first.QUEUE.exists():
        raise RuntimeError("Frozen production queue is missing")
    return cont.verify_source()


def load_batch(n: int, queue):
    cont.prepare(n, n)  # no API; builds only if missing, otherwise verifies
    batch = cont.verify_batch(n, queue)
    existing = cont.load_saved(n, batch)
    return batch, {item["baseline_candidate_id"] for item in existing}


def body_for_row(row) -> dict:
    # Byte-equivalent semantic request body to the synchronous responses.create.
    return {
        "model": MODEL,
        "instructions": first.dev20.PROMPT,
        "input": json.dumps(first.dev20.case_payload(row), ensure_ascii=False),
        "text": {"format": {"type": "json_schema",
                            "name": "literary_attribution_dev_v0_1",
                            "schema": first.dev20.SCHEMA, "strict": True}},
        "store": False,
    }


def stage(start: int, end: int, max_requests: int):
    if not 1 <= start <= end <= cont.MAX_BATCH:
        raise RuntimeError(f"Expected 1 <= start <= end <= {cont.MAX_BATCH}")
    if not 1 <= max_requests <= MAX_REQUESTS:
        raise RuntimeError(f"max_requests must be between 1 and {MAX_REQUESTS}")
    lock = global_lock()
    try:
        queue = validate_staging_environment()
        ROOT.mkdir(parents=True, exist_ok=True)
        JOBS.mkdir(parents=True, exist_ok=True)
        for p in job_dirs():
            j = read_job(p)
            if j["phase"] not in {"IMPORTED", "CLOSED_WITH_NO_RESULTS"}:
                raise RuntimeError(f"Unfinished Batch API job {p.name}: phase {j['phase']}. Check/collect/reconcile it first")
        number = len(job_dirs()) + 1
        jdir = JOBS / f"job_{number:06d}"
        if jdir.exists():
            raise RuntimeError("Job directory already exists")
        jdir.mkdir(parents=True)
        request_path = jdir / "requests.jsonl"
        picks = []
        counter = 0
        with request_path.open("w", encoding="utf-8") as fh:
            for n in range(start, end + 1):
                batch, accepted = load_batch(n, queue)
                for _, row in batch.iterrows():
                    cid = row["baseline_candidate_id"]
                    if cid in accepted:
                        continue
                    item = {"custom_id": cid, "method": "POST", "url": "/v1/responses",
                            "body": body_for_row(row)}
                    fh.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
                    picks.append((cid, n, int(row["production_queue_ordinal"])))
                    counter += 1
                    if counter >= max_requests:
                        break
                if counter >= max_requests:
                    break
            fh.flush()
            os.fsync(fh.fileno())
        if not picks:
            request_path.unlink()
            jdir.rmdir()
            print(f"No unprocessed candidate pairs in batches {start}..{end}; no job created", flush=True)
            return
        size = request_path.stat().st_size
        if size > MAX_BYTES:
            # Never leave a stage that cannot be uploaded.
            request_path.unlink()
            jdir.rmdir()
            raise RuntimeError(f"Prepared JSONL {size:,} bytes exceeds safety cap; reduce --max-requests")
        manifest = {
            "release": RELEASE, "model": MODEL, "endpoint": "/v1/responses",
            "started_at_utc": stamp(), "batch_range": [start, end],
            "count": len(picks), "bytes": size,
            "request_sha256": sha(request_path),
            "candidate_ids_sha256": hashlib.sha256("\n".join(p[0] for p in picks).encode()).hexdigest(),
            "production_queue_sha256": sha(first.QUEUE),
            "first_1000_results_sha256": cont.FIRST_1000_HASH,
            "development_prompt_sha256": hashlib.sha256(first.dev20.PROMPT.encode()).hexdigest(),
            "development_schema_sha256": hashlib.sha256(json.dumps(first.dev20.SCHEMA, sort_keys=True).encode()).hexdigest(),
            "no_holdout_or_human_gold": True,
            "request_ids": [x[0] for x in picks],
            "batch_numbers": [x[1] for x in picks],
            "queue_ordinals": [x[2] for x in picks],
            "transport_only_change": "OpenAI Batch API, same Responses body as synchronous v0_2",
        }
        atomic_json(jdir / "manifest.json", manifest)
        state = {"phase": "STAGED", "created_at_utc": stamp(), "updated_at_utc": stamp(),
                 "batch_id": None, "input_file_id": None, "job_name": jdir.name, "request_sha256": manifest["request_sha256"],
                 "error": None}
        atomic_json(jdir / "state.json", state)
        atomic_text(LATEST, jdir.name + "\n")
        print(f"STAGED: {jdir.name}  {len(picks)} unsaved requests from batches {start}..{end}; {size:,} bytes", flush=True)
        print("NO API calls. Source prompt, W mapping, holdout, old 10,000 unchanged.", flush=True)
        print(f"Stage dir: {jdir}", flush=True)
    finally:
        lock.close()


def client():
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY absent in this terminal. No API calls made")
    from openai import OpenAI
    return OpenAI(timeout=180.0, max_retries=2)


def save_state(jdir: Path, state: dict):
    state["updated_at_utc"] = stamp()
    atomic_json(jdir / "state.json", state)


def check_input_invariant(jdir: Path):
    mf = json.loads((jdir / "manifest.json").read_text(encoding="utf-8"))
    if sha(jdir / "requests.jsonl") != mf["request_sha256"]:
        raise RuntimeError("Batch API request file mutated")
    if hashlib.sha256(first.dev20.PROMPT.encode()).hexdigest() != mf["development_prompt_sha256"]:
        raise RuntimeError("Frozen prompt no longer matches staged job")
    if mf["development_schema_sha256"] != hashlib.sha256(json.dumps(first.dev20.SCHEMA, sort_keys=True).encode()).hexdigest():
        raise RuntimeError("Frozen structured output schema changed since staging")
    if mf["first_1000_results_sha256"] != cont.FIRST_1000_HASH or mf["model"] != MODEL or mf["production_queue_sha256"] != sha(first.QUEUE):
        raise RuntimeError("Frozen source/model changed since staging")
    return mf


def submit():
    lock = global_lock()
    try:
        jdir = selected_job_dir()
        mf = check_input_invariant(jdir)
        state = read_job(jdir)
        if state["phase"] not in {"STAGED", "UPLOADED"}:
            raise RuntimeError(f"Cannot submit from phase {state['phase']}; --check/--reconcile if uncertain")
        sdk = client()
        if not state["input_file_id"]:
            # Never auto-reupload after uncertain failure.
            state["phase"] = "UPLOADING"
            save_state(jdir, state)
            try:
                with (jdir / "requests.jsonl").open("rb") as fh:
                    fileobj = sdk.files.create(file=fh, purpose="batch")
            except Exception:
                state["error"] = "File upload outcome uncertain; inspect Files API before manually recovering."
                save_state(jdir, state)
                raise
            state["input_file_id"] = fileobj.id
            state["phase"] = "UPLOADED"
            state["error"] = None
            save_state(jdir, state)
            print(f"Uploaded input file: {fileobj.id}", flush=True)
        state["phase"] = "CREATING"
        save_state(jdir, state)
        try:
            batch = sdk.batches.create(
                input_file_id=state["input_file_id"], endpoint="/v1/responses",
                completion_window="24h",
                metadata={"job_tag": jdir.name, "release": "oa-r2a1-batch-v0_1", "request_hash": mf["request_sha256"][:32]},
            )
        except Exception:
            state["error"] = "Batch-create outcome uncertain: do NOT resubmit. Use --reconcile."
            save_state(jdir, state)
            raise
        state["batch_id"] = batch.id
        state["phase"] = "SUBMITTED"
        state["remote_status"] = batch.status
        state["error"] = None
        save_state(jdir, state)
        print(f"SUBMITTED {len(mf['request_ids'])} paid Batch API requests, id={batch.id}, status={batch.status}", flush=True)
        print("Processing is asynchronous; use --check and later --collect. Do NOT use synchronous runner for these IDs.")
    finally:
        lock.close()


def reconcile():
    jdir = selected_job_dir()
    state = read_job(jdir)
    if state["phase"] != "CREATING" or not state.get("input_file_id"):
        raise RuntimeError("--reconcile is only for an uncertain batch create")
    sdk = client()
    matches = []
    # Scan recent batches, including other projects; require exact file+job metadata.
    batches = sdk.batches.list(limit=100)
    for batch in batches.auto_paging_iter():
        meta = batch.metadata or {}
        if batch.input_file_id == state["input_file_id"] and meta.get("job_tag") == jdir.name:
            matches.append(batch)
        if len(matches) > 1:
            break
    if len(matches) != 1:
        raise RuntimeError(f"Reconcile found {len(matches)} matching remote jobs. Do not blindly resubmit. Resolve manually")
    batch = matches[0]
    state["batch_id"] = batch.id
    state["phase"] = "SUBMITTED"
    state["remote_status"] = batch.status
    state["error"] = None
    save_state(jdir, state)
    print(f"RECONCILED job {jdir.name}: {batch.id} status={batch.status}")


def retrieve_remote(jdir: Path, sdk):
    state = read_job(jdir)
    if not state.get("batch_id"):
        raise RuntimeError("No remote job ID yet")
    b = sdk.batches.retrieve(state["batch_id"])
    if b.input_file_id != state["input_file_id"] or b.endpoint != "/v1/responses":
        raise RuntimeError("Remote job does not match uploaded file / endpoint")
    state["remote_status"] = b.status
    state["output_file_id"] = b.output_file_id
    state["error_file_id"] = b.error_file_id
    state["request_counts"] = b.request_counts.model_dump() if b.request_counts else None
    state["usage"] = b.usage.model_dump() if getattr(b, "usage", None) else None
    save_state(jdir, state)
    return b, state


def check():
    jdir = selected_job_dir()
    b, state = retrieve_remote(jdir, client())
    print(f"Batch {b.id}: {b.status} / requests={state.get('request_counts')}", flush=True)
    if b.status in ACTIVE:
        print("Still processing remotely. A tmux session is NOT required while waiting.")
    elif b.status in TERMINAL:
        print("Remote job reached terminal status. Run --collect to archive/import available responses.")


def atomic_download(sdk, file_id: str, target: Path):
    if target.exists():
        return
    tmp = target.with_name(target.name + ".partial")
    response = sdk.files.content(file_id)
    body = response.content
    with tmp.open("wb") as fh:
        fh.write(body)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, target)


def extract_response_text(body: dict) -> str | None:
    # A Batch /v1/responses result contains a full Response JSON object.
    # No guarantee that the output message is the first output element.
    parts = []
    for output in body.get("output") or []:
        if output.get("type") != "message":
            continue
        for part in output.get("content") or []:
            if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                parts.append(part["text"])
    return "".join(parts) if parts else None


def parse_outputs(jdir: Path, mf: dict):
    expected = set(mf["request_ids"])
    if len(expected) != mf["count"] or len(set(mf["queue_ordinals"])) != mf["count"]:
        raise RuntimeError("Staged batch IDs/ordinals are not unique")
    mapping = {cid: (n, ordinal) for cid, n, ordinal in zip(
        mf["request_ids"], mf["batch_numbers"], mf["queue_ordinals"])}
    responses = {}
    rejects = []
    seen = set()
    for path in (jdir / "raw_output.jsonl", jdir / "raw_errors.jsonl"):
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                if not line.strip():
                    raise RuntimeError(f"Blank returned line at {path}:{lineno}")
                x = json.loads(line)
                cid = x.get("custom_id")
                if cid not in expected or cid in seen:
                    raise RuntimeError(f"Unknown/duplicate custom_id in {path}:{lineno}: {cid}")
                seen.add(cid)
                resp = x.get("response") or {}
                code = resp.get("status_code")
                if code != 200 or x.get("error"):
                    rejects.append({"candidate_id": cid, "kind": "request_failure", "status_code": code,
                                    "error": x.get("error"), "request_id": resp.get("request_id")})
                    continue
                body = resp.get("body") or {}
                if body.get("status") != "completed":
                    rejects.append({"candidate_id": cid, "kind": "incomplete_response",
                                    "response_id": body.get("id"), "response_status": body.get("status")})
                    continue
                s = extract_response_text(body)
                try:
                    label = json.loads(s) if s else None
                except (json.JSONDecodeError, TypeError):
                    label = None
                issues = cont.validation_issues(label)
                if issues:
                    rejects.append({"candidate_id": cid, "kind": "model_validation_failure",
                                    "issues": issues, "response_id": body.get("id"), "output_text": s})
                    continue
                n, ordinal = mapping[cid]
                usage = body.get("usage") or {}
                responses[cid] = {
                    "baseline_candidate_id": cid,
                    "project_work_id": None,  # verified and assigned from frozen parquet below
                    "openalex_work_id": None,
                    "production_queue_ordinal": ordinal,
                    "model": MODEL,
                    "response_id": body.get("id"),
                    "input_tokens": int(usage.get("input_tokens") or 0),
                    "output_tokens": int(usage.get("output_tokens") or 0),
                    "processing_mode": "batch_api",
                    **label,
                }
    for cid in expected - seen:
        rejects.append({"candidate_id": cid, "kind": "missing_remote_result"})
    return mapping, responses, sorted(rejects, key=lambda x: x["candidate_id"])


def collect():
    lock = global_lock()
    try:
        jdir = selected_job_dir()
        state = read_job(jdir)
        if state["phase"] == "IMPORTED":
            print("Already imported; no action. Stage another range when needed.")
            return
        if state["phase"] not in {"SUBMITTED", "IMPORTING"}:
            raise RuntimeError(f"Expected SUBMITTED/IMPORTING job, got {state['phase']}")
        mf = check_input_invariant(jdir)
        sdk = client()
        remote, state = retrieve_remote(jdir, sdk)
        if remote.status not in TERMINAL:
            print(f"Remote job {remote.id} still {remote.status}; do not import yet")
            return
        if remote.output_file_id:
            atomic_download(sdk, remote.output_file_id, jdir / "raw_output.jsonl")
        if remote.error_file_id:
            atomic_download(sdk, remote.error_file_id, jdir / "raw_errors.jsonl")
        # Verify all output lines and perform all semantic validation BEFORE appending.
        mapping, accepted, rejects = parse_outputs(jdir, mf)
        state["phase"] = "IMPORTING"
        save_state(jdir, state)
        queue = validate_staging_environment()
        n_import = 0
        by_batch = {}
        for cid, r in accepted.items():
            n = mapping[cid][0]
            by_batch.setdefault(n, []).append(r)
        for n in sorted(by_batch):
            batch = cont.verify_batch(n, queue)
            row_by_id = {r["baseline_candidate_id"]: r for _, r in batch.iterrows()}
            existing = {x["baseline_candidate_id"] for x in cont.load_saved(n, batch)}
            _, _, result_path = cont.batchpaths(n)
            with result_path.open("a", encoding="utf-8") as fh:
                for r in sorted(by_batch[n], key=lambda x: x["production_queue_ordinal"]):
                    cid = r["baseline_candidate_id"]
                    if cid in existing:
                        continue  # re-import after a crash: never duplicate previously imported IDs
                    row = row_by_id[cid]
                    if (row["project_work_id"] != first.dev20.case_payload(row)["candidate_pair"]["project_work_id"]
                            or int(row["production_queue_ordinal"]) != r["production_queue_ordinal"]):
                        raise RuntimeError(f"Prepared identity/ordinal unexpectedly changed: {cid}")
                    r["project_work_id"] = row["project_work_id"]
                    r["openalex_work_id"] = row["openalex_work_id"]
                    r["batch_api_job_id"] = state["batch_id"]
                    fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())
                    existing.add(cid)
                    n_import += 1
            # Re-check the full per-1000 saved result file after import.
            cont.load_saved(n, batch)
        atomic_json(jdir / "unaccepted_audit.json", {
            "job_id": state["batch_id"], "retrieved_status": remote.status,
            "not_accepted_n": len(rejects), "items": rejects,
        })
        outcome = {
            "job_id": state["batch_id"], "remote_status": remote.status,
            "model": MODEL, "requests": mf["count"],
            "accepted_total_this_job": len(accepted), "newly_imported_this_command": n_import,
            "unaccepted": len(rejects), "input_sha256": mf["request_sha256"],
            "output_file_sha256": sha(jdir / "raw_output.jsonl") if (jdir / "raw_output.jsonl").is_file() else None,
            "errors_file_sha256": sha(jdir / "raw_errors.jsonl") if (jdir / "raw_errors.jsonl").is_file() else None,
            "collected_at_utc": stamp(), "input_tokens_accepted": sum(r["input_tokens"] for r in accepted.values()),
            "output_tokens_accepted": sum(r["output_tokens"] for r in accepted.values()),
        }
        atomic_json(jdir / "import_summary.json", outcome)
        state["phase"] = "IMPORTED"
        save_state(jdir, state)
        print(f"COLLECTED / IMPORTED: {len(accepted)}/{mf['count']} accepted, {len(rejects)} unresolved, {n_import} newly written", flush=True)
        print(f"Job: {jdir.name} / batch_id={state['batch_id']} / status={remote.status}", flush=True)
        if rejects:
            print(f"Unaccepted IDs are preserved in {jdir/'unaccepted_audit.json'}; next --stage will include them.", flush=True)
        print("All old results, human gold, and 600 holdout model predictions unchanged.", flush=True)
    finally:
        lock.close()


def status():
    ROOT.mkdir(parents=True, exist_ok=True)
    jobs = job_dirs()
    print(f"Batch API jobs: {len(jobs)}", flush=True)
    for p in jobs[-10:]:
        j = read_job(p)
        mf = json.loads((p / "manifest.json").read_text(encoding="utf-8"))
        info = f"{p.name}: {j['phase']} / remote={j.get('remote_status')} / requested={mf['count']} / id={j.get('batch_id')}"
        if (p / "import_summary.json").exists():
            report = json.loads((p / "import_summary.json").read_text(encoding="utf-8"))
            info += f" / accepted={report['accepted_total_this_job']} / unresolved={report['unaccepted']}"
        print(info, flush=True)
    print("No API calls. For latest remote status: --check")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    commands = ap.add_mutually_exclusive_group(required=True)
    for flag in ("stage", "submit", "check", "collect", "status", "reconcile"):
        commands.add_argument(f"--{flag}", action="store_true")
    ap.add_argument("--start-batch", type=int, default=10)
    ap.add_argument("--end-batch", type=int, default=10)
    ap.add_argument("--max-requests", type=int, default=100,
                    help="Max NEW Batch API requests in staged job; 100 recommended for first pilot")
    args = ap.parse_args()
    if args.stage:
        stage(args.start_batch, args.end_batch, args.max_requests)
    elif args.submit:
        submit()
    elif args.check:
        check()
    elif args.collect:
        collect()
    elif args.reconcile:
        reconcile()
    elif args.status:
        status()


if __name__ == "__main__":
    main()
