#!/usr/bin/env python3
"""Select the 30 S2 targets for the UK first-edition ground-truth table.

Inputs (read-only, frozen at commit ecf1a4d):
  derived/bl_calibration/calibration_v2/sample_targets_v1.tsv
  derived/bl_calibration/calibration_v2/sample_aliases_v1.tsv

Output (new; refuses to overwrite):
  derived/bl_calibration/calibration_v2/first_edition_targets_v1.tsv

Design: 30 W drawn from S2 only, 8 / 8 / 7 / 7 from the strata
ed_1 / ed_2_5 / ed_6_20 / ed_21_plus (seed 20261021). The table carries
the OL title(s) and query author of each W and EMPTY columns for the
human to fill from non-BL sources (year, publisher, place, evidence,
confidence) BEFORE any BL request. A W whose first edition cannot be
established is kept with status NO_EVIDENCE; it is not replaced.

No request is sent to the British Library.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "derived" / "bl_calibration" / "calibration_v2"
P_T = DIR / "sample_targets_v1.tsv"
P_A = DIR / "sample_aliases_v1.tsv"
OUT = DIR / "first_edition_targets_v1.tsv"

SEED = 20261021
QUOTA = {"ed_1": 8, "ed_2_5": 8, "ed_6_20": 7, "ed_21_plus": 7}
EXPECTED_SHA = {
    P_T.name: "71553b94cb2536a98fec22c2c0eb27fa7b48fc3691ce1a6ddb0c2dc2314f3c27",
    P_A.name: "a8a88e20185e7a7f5ff4861b6d734653a989a30c201be5900b4b19699832e5f5",
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if OUT.exists():
        print(f"output exists, refusing to overwrite: {OUT}", file=sys.stderr)
        return 1
    for p in (P_T, P_A):
        got = sha256(p)
        if got != EXPECTED_SHA[p.name]:
            print(f"{p.name} sha256 mismatch: {got}", file=sys.stderr)
            return 1

    t = pd.read_csv(P_T, sep="\t", dtype=str, keep_default_na=False)
    a = pd.read_csv(P_A, sep="\t", dtype=str, keep_default_na=False)
    s2 = t[t["stratum"] == "S2"].sort_values("target_id").reset_index(drop=True)

    rng = np.random.default_rng(SEED)
    parts = []
    for stratum, n in QUOTA.items():
        cand = s2[s2["edition_stratum"] == stratum].reset_index(drop=True)
        if len(cand) < n:
            print(f"{stratum}: only {len(cand)} S2 targets", file=sys.stderr)
            return 1
        parts.append(cand.iloc[rng.choice(len(cand), size=n, replace=False)])
    sel = pd.concat(parts, ignore_index=True)

    ga = a.groupby("target_id")
    titles = ga["source_title"].agg(lambda s: " | ".join(dict.fromkeys(s)))
    authors = ga["query_author_name"].agg(lambda s: " | ".join(dict.fromkeys(x for x in s if x)))
    olids = ga["ol_work_id"].agg(lambda s: " | ".join(s))

    out = pd.DataFrame({
        "fe_id": [f"FE2_{i:02d}" for i in range(1, len(sel) + 1)],
        "sample_id": sel["sample_id"].values,
        "project_work_id": sel["target_id"].values,
        "edition_stratum": sel["edition_stratum"].values,
        "edition_count_max": sel["edition_count_max"].values,
        "ol_work_ids": sel["target_id"].map(olids).values,
        "ol_titles": sel["target_id"].map(titles).values,
        "query_author": sel["target_id"].map(authors).values,
        # ---- to be filled by hand from non-BL sources, before any BL request
        "uk_first_edition_year": "",
        "uk_first_edition_publisher": "",
        "uk_first_edition_place": "",
        "earlier_non_uk_edition": "",
        "evidence_sources": "",
        "evidence_confidence": "",     # high / medium / low
        "notes": "",
        "status": "PENDING",            # PENDING -> ESTABLISHED / NO_EVIDENCE
    })
    out.to_csv(OUT, sep="\t", index=False, lineterminator="\n")
    print(out[["fe_id", "project_work_id", "edition_stratum", "edition_count_max",
               "ol_titles", "query_author"]].to_string(index=False))
    print("\nwritten:", OUT.relative_to(ROOT), "sha256", sha256(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
