#!/usr/bin/env python3
"""Draw the BL calibration v2 sample from the frozen target frame.

Inputs (read-only):
  derived/bl_calibration/calibration_v2/target_frame_v1.tsv
  derived/ol_edition_counts.tsv            (work_key = /works/OL...W, edition_count)

Outputs (new, versioned; refuses to overwrite):
  derived/bl_calibration/calibration_v2/sample_targets_v1.tsv   one row per target
  derived/bl_calibration/calibration_v2/sample_aliases_v1.tsv   one row per OL alias of a sampled target
  derived/bl_calibration/calibration_v2/sample_v1_summary.json

Design (protocol draft, 2026-10-21):
  S1  150 W, simple random draw from active W with retrievable aliases
  S2  100 W, 25 per edition-count stratum (1 / 2-5 / 6-20 / 21+), drawn
      from W not already in S1
  S3  the 21 pilot v1 targets (19 W + 2 unresolved units); a v1 target
      that also falls in S1/S2 keeps that stratum and is flagged v1_retest
  Early budget check: the first 30 S1 targets (s1_early_order 1..30) are
      retrieved first; the per-target request count from them decides
      whether S2 is cut to 15 per stratum (protocol section 7).

Edition count per W, for stratification ONLY: the maximum over the W's OL
aliases (not the sum: aliases of one W can share editions). A W whose
aliases have no edition-count row is eligible for S1, not S2.

No request is sent to the British Library.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "derived" / "bl_calibration" / "calibration_v2"
P_FRAME = DIR / "target_frame_v1.tsv"
P_EDC = ROOT / "derived" / "ol_edition_counts.tsv"
OUT_T = DIR / "sample_targets_v1.tsv"
OUT_A = DIR / "sample_aliases_v1.tsv"
OUT_J = DIR / "sample_v1_summary.json"

SEED = 20261021
N_S1 = 150
N_S2_PER_STRATUM = 25
N_EARLY = 30
STRATA = [("ed_1", 1, 1), ("ed_2_5", 2, 5), ("ed_6_20", 6, 20), ("ed_21_plus", 21, 10**9)]
EXPECTED_FRAME_SHA = "55b8a26625f50b331aabdd5d2a1a0ba8d436aaad7956185b8f02c671094ca9a5"
EXPECTED_V1_TARGETS = 21


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stratum_of(n: float) -> str:
    if pd.isna(n):
        return ""
    for name, lo, hi in STRATA:
        if lo <= n <= hi:
            return name
    return "ed_0"


def main() -> int:
    for p in (P_FRAME, P_EDC):
        if not p.exists():
            print(f"missing input: {p}", file=sys.stderr)
            return 1
    for p in (OUT_T, OUT_A, OUT_J):
        if p.exists():
            print(f"output exists, refusing to overwrite: {p}", file=sys.stderr)
            return 1
    frame_sha = sha256(P_FRAME)
    if frame_sha != EXPECTED_FRAME_SHA:
        print(f"target_frame_v1.tsv sha256 mismatch: {frame_sha}", file=sys.stderr)
        return 1

    fr = pd.read_csv(P_FRAME, sep="\t", dtype=str, keep_default_na=False)
    edc = pd.read_csv(P_EDC, sep="\t", dtype={"work_key": str, "edition_count": "Int64"},
                      usecols=["work_key", "edition_count"])
    edc["ol_work_id"] = edc["work_key"].str.replace("/works/", "", regex=False)
    fr = fr.merge(edc[["ol_work_id", "edition_count"]], on="ol_work_id", how="left")

    # ---- target table: one row per W (resolved) or per OL alias (unresolved)
    res = fr[(fr["target_lane"] == "resolved_w") & (fr["measurement_status"] == "TO_RETRIEVE")]
    g = res.groupby("project_work_id")
    targets = pd.DataFrame({
        "target_id": g.size().index,
        "target_lane": "resolved_w",
        "n_ol_aliases": g.size().values,
        "edition_count_max": g["edition_count"].max().values,
        "edition_count_sum": g["edition_count"].sum(min_count=1).values,
        "v1_sample_id": g["v1_sample_id"].agg(lambda s: next((x for x in s if x), "")).values,
    })
    unres = fr[fr["target_lane"] == "unresolved_source"].copy()
    unres_t = pd.DataFrame({
        "target_id": unres["ol_entity_id"].values,
        "target_lane": "unresolved_source",
        "n_ol_aliases": 1,
        "edition_count_max": unres["edition_count"].values,
        "edition_count_sum": unres["edition_count"].values,
        "v1_sample_id": unres["v1_sample_id"].values,
    })
    targets = pd.concat([targets, unres_t], ignore_index=True)
    targets["edition_stratum"] = targets["edition_count_max"].map(stratum_of)

    n_active = int((targets["target_lane"] == "resolved_w").sum())
    v1_ids = sorted(set(targets.loc[targets["v1_sample_id"] != "", "v1_sample_id"]))
    if len(v1_ids) != EXPECTED_V1_TARGETS:
        print(f"expected {EXPECTED_V1_TARGETS} v1 targets, found {len(v1_ids)}", file=sys.stderr)
        return 1

    # ---- draws (seeded, order-independent: targets sorted by id first)
    rng = np.random.default_rng(SEED)
    pool = targets[targets["target_lane"] == "resolved_w"].sort_values("target_id").reset_index(drop=True)
    s1_idx = rng.choice(len(pool), size=N_S1, replace=False)
    s1 = pool.iloc[s1_idx].copy()
    s1["stratum"] = "S1"
    early = rng.permutation(N_S1)[:N_EARLY]
    s1["s1_early_order"] = 0
    s1.iloc[early, s1.columns.get_loc("s1_early_order")] = np.arange(1, N_EARLY + 1)

    rest = pool[~pool["target_id"].isin(s1["target_id"])]
    s2_parts = []
    for name, _, _ in STRATA:
        cand = rest[rest["edition_stratum"] == name].reset_index(drop=True)
        if len(cand) < N_S2_PER_STRATUM:
            print(f"stratum {name}: only {len(cand)} candidates", file=sys.stderr)
            return 1
        pick = cand.iloc[rng.choice(len(cand), size=N_S2_PER_STRATUM, replace=False)].copy()
        s2_parts.append(pick)
    s2 = pd.concat(s2_parts, ignore_index=True)
    s2["stratum"] = "S2"
    s2["s1_early_order"] = 0

    drawn = pd.concat([s1, s2], ignore_index=True)
    s3 = targets[(targets["v1_sample_id"] != "") & ~targets["target_id"].isin(drawn["target_id"])].copy()
    s3["stratum"] = "S3"
    s3["s1_early_order"] = 0
    sample = pd.concat([drawn, s3], ignore_index=True)
    sample["v1_retest"] = sample["v1_sample_id"] != ""
    sample["sample_id"] = [f"BLC2_{i:03d}" for i in range(1, len(sample) + 1)]

    cols = ["sample_id", "stratum", "target_lane", "target_id", "n_ol_aliases",
            "edition_count_max", "edition_count_sum", "edition_stratum",
            "v1_retest", "v1_sample_id", "s1_early_order"]
    sample = sample[cols]
    assert sample["target_id"].is_unique

    # ---- alias table for query building
    key = fr["project_work_id"].where(fr["target_lane"] == "resolved_w", fr["ol_entity_id"])
    fr = fr.assign(target_id=key)
    aliases = fr[fr["target_id"].isin(sample["target_id"])].merge(
        sample[["sample_id", "stratum", "target_id"]], on="target_id", how="left")
    acols = ["sample_id", "stratum", "target_id", "target_lane", "ol_entity_id", "ol_work_id",
             "source_title", "primary_action", "query_author_name", "edition_count",
             "n_ol_aliases_for_w", "measurement_status"]
    aliases = aliases[acols].sort_values(["sample_id", "ol_entity_id"])

    sample.to_csv(OUT_T, sep="\t", index=False, lineterminator="\n")
    aliases.to_csv(OUT_A, sep="\t", index=False, lineterminator="\n")

    summary = {
        "release": "bl_calibration_v2_sample_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "inputs": {"target_frame_v1.tsv": frame_sha, "ol_edition_counts.tsv": sha256(P_EDC)},
        "population_active_w": n_active,
        "population_unresolved_aliases": int(len(unres_t)),
        "active_w_without_edition_count": int(pool["edition_count_max"].isna().sum()),
        "population_by_edition_stratum": pool["edition_stratum"].value_counts().to_dict(),
        "sample_rows": int(len(sample)),
        "sample_by_stratum": sample["stratum"].value_counts().to_dict(),
        "s2_by_edition_stratum": s2["edition_stratum"].value_counts().to_dict(),
        "v1_retest_total": int(sample["v1_retest"].sum()),
        "v1_retest_by_stratum": sample[sample["v1_retest"]]["stratum"].value_counts().to_dict(),
        "s1_early_check_targets": N_EARLY,
        "alias_rows": int(len(aliases)),
        "alias_primary_action": aliases["primary_action"].value_counts().to_dict(),
        "outputs": {OUT_T.name: sha256(OUT_T), OUT_A.name: sha256(OUT_A)},
        "note": ("Frozen before any BL request. Edition count is a stratification "
                 "variable only (max over aliases, not sum)."),
    }
    OUT_J.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "inputs"}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
