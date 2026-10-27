#!/usr/bin/env python3
"""Build the BL production v3 target list from the frozen v2 target frame.

Inputs (sha256 verified):
  derived/bl_calibration/calibration_v2/target_frame_v1.tsv     (34,790 alias rows, Project Works v7)
  derived/bl_calibration/calibration_v2/sample_targets_v1.tsv   (the 270 v2 targets: NOT re-retrieved)
  derived/bl_production/production_v3/author_overrides_v1.tsv   (REPLACE / ADD / NO_AUTHOR)

Output (new; refuses to overwrite):
  derived/bl_production/production_v3/targets_v1.tsv            one row per OL alias to retrieve
  derived/bl_production/production_v3/targets_v1_summary.json

Per alias row:
  target_id           project_work_id (resolved) or ol_entity_id (unresolved lane)
  batch               1-based batch number; 1,000 targets per batch, in target_id order
  query_title         source_title as frozen (quotes kept; the runner builds T2/K1 from it)
  query_authors       ';'-joined surnames/names used for K1/A1 after overrides ('' = no author route)
  author_override     '' | REPLACE | ADD | NO_AUTHOR
  title_has_quote / author_has_quote   -> runner sends the original route as SKIPPED_INVALID_QUERY
                                          and the quote-stripped T2q/K1q/A1q instead
Excluded (counted in the summary): source-light W (NA), identity_suspended (NA), the 270 v2 targets.
No BL request is sent.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CAL = ROOT / "derived" / "bl_calibration" / "calibration_v2"
PROD = ROOT / "derived" / "bl_production" / "production_v3"
P_FRAME, P_SAMPLE, P_OVR = CAL / "target_frame_v1.tsv", CAL / "sample_targets_v1.tsv", PROD / "author_overrides_v1.tsv"
OUT, OUT_J = PROD / "targets_v1.tsv", PROD / "targets_v1_summary.json"
EXPECTED = {
    "target_frame_v1.tsv": "55b8a26625f50b331aabdd5d2a1a0ba8d436aaad7956185b8f02c671094ca9a5",
    "sample_targets_v1.tsv": "71553b94cb2536a98fec22c2c0eb27fa7b48fc3691ce1a6ddb0c2dc2314f3c27",
}
BATCH = 1000


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def read(p):
    return pd.read_csv(p, sep="\t", dtype=str, keep_default_na=False)


def main() -> int:
    if OUT.exists() or OUT_J.exists():
        sys.exit(f"output exists, refusing to overwrite: {PROD}")
    for p in (P_FRAME, P_SAMPLE):
        if sha256(p) != EXPECTED[p.name]:
            sys.exit(f"{p.name}: sha256 mismatch")
    fr, s2, ovr = read(P_FRAME), read(P_SAMPLE), read(P_OVR)

    fr["target_id"] = fr["project_work_id"].where(fr["target_lane"] == "resolved_w", fr["ol_entity_id"])
    v2_targets = set(s2["target_id"])
    excl = {
        "source_light_na": int((fr["measurement_status"] == "NOT_RETRIEVED_SOURCE_LIGHT").sum()),
        "identity_suspended_na": int((fr["measurement_status"] == "NOT_MEASURED_IDENTITY_SUSPENDED").sum()),
        "v2_already_retrieved_aliases": int(fr["target_id"].isin(v2_targets).sum()),
    }
    T = fr[fr["measurement_status"].isin(["TO_RETRIEVE", "TO_RETRIEVE_UNRESOLVED_LANE"]) & ~fr["target_id"].isin(v2_targets)].copy()

    # author overrides
    o = {r.project_work_id: r for r in ovr.itertuples(index=False)}
    def authors(row):
        base = row["query_author_name"] if row["primary_action"] in ("USE_ORDINAL0", "USE_OTHER_ORDINAL") else ""
        r = o.get(row["target_id"])
        if r is None:
            return base, ""
        if r.override_action == "NO_AUTHOR":
            return "", "NO_AUTHOR"
        if r.override_action == "REPLACE":
            return r.override_surnames.replace(";", ";"), "REPLACE"
        if r.override_action == "ADD":
            extra = [x for x in r.override_surnames.split(";") if x and x not in base]
            return ";".join([base] + extra) if base else ";".join(extra), "ADD"
        return base, ""
    aa = T.apply(authors, axis=1, result_type="expand")
    T["query_authors"], T["author_override"] = aa[0], aa[1]
    T["query_title"] = T["source_title"]
    T["title_has_quote"] = T["query_title"].str.contains('"', regex=False)
    T["author_has_quote"] = T["query_authors"].str.contains('"', regex=False)

    # batches by target (not alias): targets in id order, 1,000 per batch
    order = sorted(T["target_id"].unique())
    batch_of = {t: i // BATCH + 1 for i, t in enumerate(order)}
    T["batch"] = T["target_id"].map(batch_of)
    T["n_ol_aliases"] = T.groupby("target_id")["ol_entity_id"].transform("size")
    T = T.sort_values(["batch", "target_id", "ol_entity_id"])

    cols = ["batch", "target_id", "target_lane", "ol_entity_id", "ol_work_id", "n_ol_aliases",
            "query_title", "query_authors", "author_override", "title_has_quote", "author_has_quote", "measurement_status"]
    T[cols].to_csv(OUT, sep="\t", index=False, lineterminator="\n")

    summary = {
        "release": "bl_production_v3_targets_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "identity_version": "project_works_v7",
        "inputs_sha256": {p.name: sha256(p) for p in (P_FRAME, P_SAMPLE, P_OVR)},
        "excluded": excl,
        "alias_rows": int(len(T)),
        "targets": len(order),
        "targets_by_lane": T.drop_duplicates("target_id")["target_lane"].value_counts().to_dict(),
        "batches": len(set(batch_of.values())),
        "batch_size": BATCH,
        "aliases_with_title_quote": int(T["title_has_quote"].sum()),
        "aliases_with_author_quote": int(T["author_has_quote"].sum()),
        "targets_without_author_route": int(T.drop_duplicates("target_id")["query_authors"].eq("").sum()),
        "author_overrides_applied": T.drop_duplicates("target_id")["author_override"].value_counts().to_dict(),
        "output_sha256": sha256(OUT),
        "note": "v2's 270 targets are reused from calibration_v2 (retrieved 2026-10-25) and not re-retrieved. No BL request is sent.",
    }
    OUT_J.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "inputs_sha256"}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
