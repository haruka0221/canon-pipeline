#!/usr/bin/env python3
"""Build the BL calibration v2 target frame from Project Works v7.

Inputs (read-only, all at the frozen v7 state of the repository):
  derived/identity/project_works_v7.tsv
  derived/identity/work_identity_map_v7.tsv
  derived/identity/source_entities_v3.tsv
  derived/identity/project_work_identity_suspensions_v1.tsv
  derived/openlibrary_query_author_selection_v1/openlibrary_query_author_selection_v1.tsv
  derived/bl_calibration/verification_pilot_v1/bl_verification_pilot_v1_sample.tsv

Output (new, versioned; nothing existing is modified):
  derived/bl_calibration/calibration_v2/target_frame_v1.tsv
  derived/bl_calibration/calibration_v2/target_frame_v1_summary.json

One row per Open Library alias (current OL target). A project W with several
OL aliases has several rows. The frame is the population the v2 sample is
drawn from; it is not the sample and it sends no request to the BL.

Lanes:
  resolved_w          OL alias mapped to an active W (current_analysis_target)
  identity_suspended  OL alias whose membership was removed in v6 (16 W + 1
                      restored Alcott predecessor); NOT measured
  unresolved_source   OL alias in no W (unresolved aggregation units)
Plus one alias-less row for the source-light W000014515 (NA, not zero).
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
ID = ROOT / "derived" / "identity"
P_WORKS = ID / "project_works_v7.tsv"
P_MAP = ID / "work_identity_map_v7.tsv"
P_ENT = ID / "source_entities_v3.tsv"
P_SUSP = ID / "project_work_identity_suspensions_v1.tsv"
P_AUTH = (ROOT / "derived" / "openlibrary_query_author_selection_v1"
          / "openlibrary_query_author_selection_v1.tsv")
P_V1 = (ROOT / "derived" / "bl_calibration" / "verification_pilot_v1"
        / "bl_verification_pilot_v1_sample.tsv")
OUT_DIR = ROOT / "derived" / "bl_calibration" / "calibration_v2"
OUT_TSV = OUT_DIR / "target_frame_v1.tsv"
OUT_JSON = OUT_DIR / "target_frame_v1_summary.json"

EXPECTED = {
    "w_rows": 32089, "w_active": 32066, "w_suspended": 16, "w_superseded": 7,
    "map_current_targets": 32689, "ol_targets": 34789,
}
SOURCE_LIGHT_W = "W000014515"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read(p: Path) -> pd.DataFrame:
    return pd.read_csv(p, sep="\t", dtype=str, keep_default_na=False)


def main() -> int:
    for p in (P_WORKS, P_MAP, P_ENT, P_SUSP, P_AUTH, P_V1):
        if not p.exists():
            print(f"missing input: {p}", file=sys.stderr)
            return 1
    if OUT_TSV.exists() or OUT_JSON.exists():
        print(f"output exists, refusing to overwrite: {OUT_DIR}", file=sys.stderr)
        return 1

    works = read(P_WORKS)
    wmap = read(P_MAP)
    ents = read(P_ENT)
    susp = read(P_SUSP)
    auth = read(P_AUTH)
    v1 = read(P_V1)

    # --- invariants of the frozen v7 state -------------------------------
    st = works["status"].value_counts()
    checks = {
        "w_rows": len(works),
        "w_active": int(st.get("active", 0)),
        "w_suspended": int(st.get("identity_suspended", 0)),
        "w_superseded": int(st.get("superseded", 0)),
        "map_current_targets": int((wmap["membership_role"] == "current_analysis_target").sum()),
        "ol_targets": len(auth),
    }
    bad = {k: (checks[k], v) for k, v in EXPECTED.items() if checks[k] != v}
    if bad:
        print("v7 invariants failed (got, expected):", bad, file=sys.stderr)
        return 1

    # --- OL entity -> W (active and suspended) ----------------------------
    cur = wmap[wmap["membership_role"] == "current_analysis_target"][
        ["project_work_id", "source_entity_id"]]
    assert cur["source_entity_id"].is_unique, "an OL entity maps to >1 W"
    e2w = dict(zip(cur["source_entity_id"], cur["project_work_id"]))
    w_status = dict(zip(works["project_work_id"], works["status"]))

    # suspensions: find the entity-id column without assuming its name
    ent_cols = [c for c in susp.columns if c.endswith("entity_id")]
    w_cols = [c for c in susp.columns if c == "project_work_id"]
    if not ent_cols or not w_cols:
        print("suspensions file: columns are", list(susp.columns), file=sys.stderr)
        return 1
    susp_e2w = dict(zip(susp[ent_cols[0]], susp["project_work_id"]))

    # OL work id -> entity id (source_entities_v3, Open Library rows only)
    ol_ent = ents[ents["source"].str.lower().str.contains("open")]
    ol2e = dict(zip(ol_ent["source_id"], ol_ent["entity_id"]))

    # v1 sample membership
    v1_w = {w: s for w, s in zip(v1["project_work_id"], v1["sample_id"]) if w}
    v1_u = {e: s for e, s in zip(v1["unresolved_unit_anchor_entity_id"], v1["sample_id"]) if e}

    rows = []
    unmatched_entity = 0
    for r in auth.itertuples(index=False):
        eid = r.current_entity_id
        if eid not in ol2e.values():
            unmatched_entity += 1
        w = e2w.get(eid)
        if w is not None:
            lane, status, ms = "resolved_w", w_status[w], "TO_RETRIEVE"
        elif eid in susp_e2w:
            w, lane = susp_e2w[eid], "identity_suspended"
            status, ms = w_status.get(w, ""), "NOT_MEASURED_IDENTITY_SUSPENDED"
        else:
            w, lane, status, ms = "", "unresolved_source", "", "TO_RETRIEVE_UNRESOLVED_LANE"
        rows.append({
            "project_work_id": w,
            "target_lane": lane,
            "w_status": status,
            "measurement_status": ms,
            "ol_entity_id": eid,
            "ol_work_id": r.current_ol_work_id,
            "source_title": r.source_title,
            "primary_action": r.primary_action,
            "query_author_name": r.query_author_name,
            "query_author_selected": r.query_author_selected,
            "v1_sample_id": v1_w.get(w, "") or v1_u.get(eid, ""),
        })

    # source-light W: active, no OL alias -> NA, not zero
    rows.append({
        "project_work_id": SOURCE_LIGHT_W, "target_lane": "resolved_w",
        "w_status": w_status[SOURCE_LIGHT_W],
        "measurement_status": "NOT_RETRIEVED_SOURCE_LIGHT",
        "ol_entity_id": "", "ol_work_id": "", "source_title": "",
        "primary_action": "", "query_author_name": "",
        "query_author_selected": "", "v1_sample_id": v1_w.get(SOURCE_LIGHT_W, ""),
    })

    df = pd.DataFrame(rows)
    n_alias = df[df["target_lane"] == "resolved_w"].groupby("project_work_id")["ol_entity_id"].transform("size")
    df["n_ol_aliases_for_w"] = n_alias.fillna(1).astype(int)

    # active W with no row at all (should be none)
    active = set(works.loc[works["status"] == "active", "project_work_id"])
    covered = set(df.loc[df["target_lane"] == "resolved_w", "project_work_id"])
    missing_active = sorted(active - covered)

    OUT_DIR.mkdir(parents=True, exist_ok=False)
    df.to_csv(OUT_TSV, sep="\t", index=False, lineterminator="\n")

    summary = {
        "release": "bl_calibration_v2_target_frame_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "identity_version": "project_works_v7",
        "inputs": {str(p.relative_to(ROOT)): sha256(p)
                   for p in (P_WORKS, P_MAP, P_ENT, P_SUSP, P_AUTH, P_V1)},
        "v7_invariants": checks,
        "rows": len(df),
        "rows_by_lane": df["target_lane"].value_counts().to_dict(),
        "rows_by_measurement_status": df["measurement_status"].value_counts().to_dict(),
        "resolved_w_distinct": int(df.loc[df["target_lane"] == "resolved_w", "project_work_id"].nunique()),
        "resolved_w_multi_alias": int((df[df["target_lane"] == "resolved_w"]
                                       .drop_duplicates("project_work_id")["n_ol_aliases_for_w"] > 1).sum()),
        "unresolved_ol_aliases": int((df["target_lane"] == "unresolved_source").sum()),
        "primary_action_resolved_w": df.loc[df["target_lane"] == "resolved_w", "primary_action"]
                                       .value_counts().to_dict(),
        "v1_sample_rows_located": int((df["v1_sample_id"] != "").sum()),
        "active_w_without_row": missing_active,
        "auth_entities_not_in_source_entities_v3": unmatched_entity,
        "output_sha256": sha256(OUT_TSV),
        "note": ("Frame only; the v2 sample is drawn by a separate script. "
                 "Unresolved aliases are not yet grouped into aggregation units."),
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "inputs"},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
