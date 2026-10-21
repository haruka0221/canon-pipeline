#!/usr/bin/env python3
"""Project-W-indexed Wikidata bibliographic *evidence* from frozen local sources.

Non-destructive: no changes to OL projection, identity v7, OpenAlex, or review tables.
Outputs are explicitly NOT scope decisions or verified original-publication years.

Usage:
    python -B scripts/build_scope_wikidata_bibliographic_evidence_v0_1.py --dry-run
    python -B scripts/build_scope_wikidata_bibliographic_evidence_v0_1.py

Output directory must not already exist (or contain files); no overwrite.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SNAPSHOT = "2026-08-05"
EXPECTED_ACTIVE = 32066
EXPECTED_ADOPTED = 6177
EXPECTED_WD_P577 = 4473
EXPECTED_WD_P407 = 4893
EXPECTED_WD_P31 = 6120
EXPECTED_WD_P629 = 1
EXPECTED_BOTH = 3651
FIELDS = ("P31", "P407", "P577", "P629")
YEAR_PATTERN = re.compile(r"^\+([0-9]{4,})-[0-9]{2}-[0-9]{2}T")


def load_tsv(p: Path) -> pd.DataFrame:
    if not p.is_file():
        raise FileNotFoundError(p)
    return pd.read_csv(p, sep="\t", dtype=str, keep_default_na=False)


def as_values(x: Any) -> list[str]:
    """Preserve order and all nonblank property values; never choose a preferred value."""
    if isinstance(x, np.ndarray):
        arr = x.tolist()
    elif isinstance(x, (tuple, list)):
        arr = list(x)
    elif x is None:
        arr = []
    elif isinstance(x, str):
        arr = [x] if x.strip() else []
    else:
        raise ValueError(f"Unexpected property value type: {type(x).__name__}")
    if not all(isinstance(v, str) for v in arr if v is not None):
        raise ValueError("Expected string-valued Wikidata properties")
    return [v for v in arr if v is not None and v.strip()]


def json_array(items: list) -> str:
    return json.dumps(items, ensure_ascii=False, separators=(",", ":"))


def wd_positive_years(raw_dates: list[str]) -> list[int]:
    """Parse only positive Wikidata year spellings (not verified first-publication years)."""
    out = []
    for value in raw_dates:
        m = YEAR_PATTERN.match(value)
        if m:
            out.append(int(m.group(1)))
    return out


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def build(active: pd.DataFrame, mapping: pd.DataFrame,
          sources: pd.DataFrame, entities: pd.DataFrame):
    assert len(active) == EXPECTED_ACTIVE, f"active={len(active)}"
    assert active.project_work_id.is_unique
    assert sources.entity_id.is_unique
    assert entities.qid.is_unique

    active_ids = set(active.project_work_id)
    membership = mapping.loc[
        mapping.project_work_id.isin(active_ids),
        ["project_work_id", "source_entity_id", "membership_role"],
    ]
    bridge = membership.merge(
        sources[["entity_id", "source", "source_namespace", "source_id", "source_snapshot"]],
        left_on="source_entity_id", right_on="entity_id",
        how="left", validate="many_to_one", indicator=True,
    )
    assert bridge["_merge"].eq("both").all(), "Missing source entities"
    wd = bridge.loc[
        bridge.source.eq("wikidata") & bridge.source_namespace.eq("item"),
        ["project_work_id", "source_id", "source_snapshot", "membership_role"],
    ].copy().rename(columns={"source_id": "wikidata_qid"})
    assert len(wd) == EXPECTED_ADOPTED, f"Wikidata memberships={len(wd)}"
    assert wd.project_work_id.is_unique and wd.wikidata_qid.is_unique
    assert wd.membership_role.eq("accepted_external_identity").all()
    assert wd.source_snapshot.eq(SNAPSHOT).all(), "Unexpected identity source snapshot"

    selected = ["qid", "label_en_effective", "source_snapshot"] + list(FIELDS)
    missing = [col for col in selected if col not in entities.columns]
    if missing:
        raise ValueError(f"Missing Parquet columns: {missing}")
    joined = wd.merge(
        entities[selected], left_on="wikidata_qid", right_on="qid",
        how="left", validate="one_to_one", indicator=True,
        suffixes=("_identity", "_parquet"),
    )
    assert len(joined) == EXPECTED_ADOPTED
    assert joined["_merge"].eq("both").all(), "Some adopted QIDs absent from Parquet"
    assert joined["source_snapshot_parquet"].eq(SNAPSHOT).all(), "Parquet snapshot mismatch"

    # Flatten only existing projection values. These arrays are an extraction of
    # values, NOT Wikidata statement JSON: rank, qualifiers, references absent.
    out = pd.DataFrame({
        "project_work_id": joined.project_work_id,
        "wikidata_qid": joined.wikidata_qid,
        "wikidata_label_en_effective": joined.label_en_effective.fillna("").astype(str),
        "identity_membership_role": joined.membership_role,
        "wikidata_snapshot": SNAPSHOT,
    })
    for prop in FIELDS:
        arrays = joined[prop].map(as_values)
        lname = prop.lower()
        out[f"wd_{lname}_values_json"] = arrays.map(json_array)
        out[f"wd_{lname}_count"] = arrays.map(len)
    raw_date_lists = joined["P577"].map(as_values)
    out["wd_p577_parsed_positive_years_json"] = raw_date_lists.map(
        lambda values: json_array(wd_positive_years(values))
    )
    out["wd_p577_unparsed_values_count"] = raw_date_lists.map(
        lambda values: len(values) - len(wd_positive_years(values))
    )
    out["wd_p407_includes_english_q1860"] = joined["P407"].map(
        lambda value: "Q1860" in as_values(value)
    )
    out = out.sort_values("project_work_id").reset_index(drop=True)

    counts = {
        "active_project_w": EXPECTED_ACTIVE,
        "adopted_wikidata_qids": len(out),
        "wikidata_p577_nonempty": int(out.wd_p577_count.gt(0).sum()),
        "wikidata_p407_nonempty": int(out.wd_p407_count.gt(0).sum()),
        "wikidata_p31_nonempty": int(out.wd_p31_count.gt(0).sum()),
        "wikidata_p629_nonempty": int(out.wd_p629_count.gt(0).sum()),
        "wikidata_p577_and_p407_nonempty": int(
            (out.wd_p577_count.gt(0) & out.wd_p407_count.gt(0)).sum()
        ),
        "active_w_without_adopted_wikidata": EXPECTED_ACTIVE - len(out),
    }
    assert counts["wikidata_p577_nonempty"] == EXPECTED_WD_P577, counts
    assert counts["wikidata_p407_nonempty"] == EXPECTED_WD_P407, counts
    assert counts["wikidata_p31_nonempty"] == EXPECTED_WD_P31, counts
    assert counts["wikidata_p629_nonempty"] == EXPECTED_WD_P629, counts
    assert counts["wikidata_p577_and_p407_nonempty"] == EXPECTED_BOTH, counts
    assert out.project_work_id.is_unique
    assert out.wikidata_qid.is_unique

    # All-active coverage index maintains source-light/missing Wikidata works.
    coverage = active[["project_work_id"]].merge(
        out[["project_work_id", "wikidata_qid", "wd_p577_count", "wd_p407_count",
             "wd_p31_count", "wd_p629_count"]],
        on="project_work_id", how="left", validate="one_to_one", indicator=True,
    )
    coverage["wikidata_evidence_status"] = coverage["_merge"].map({
        "both": "ADOPTED_QID_IN_FROZEN_PARQUET",
        "left_only": "NO_ADOPTED_WIKIDATA_QID",
    }).astype(str)
    coverage.drop(columns=["_merge"], inplace=True)
    coverage.fillna({"wikidata_qid": ""}, inplace=True)
    # Empty count means no adopted QID, which differs from a recorded 0 count.
    for col in ["wd_p577_count", "wd_p407_count", "wd_p31_count", "wd_p629_count"]:
        coverage[col] = coverage[col].map(lambda x: "" if pd.isna(x) else str(int(x)))
    coverage.sort_values("project_work_id", inplace=True)
    assert len(coverage) == EXPECTED_ACTIVE
    assert coverage.project_work_id.is_unique
    assert int(coverage.wikidata_qid.ne("").sum()) == EXPECTED_ADOPTED
    return out, coverage, counts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="QC only: write nothing")
    ap.add_argument("--repo", type=Path, default=Path("."))
    ap.add_argument("--source-parquet", type=Path, default=Path.home() /
        "research-data/wikidata-source-layer/2026-08-05/wikidata_entities.parquet")
    ap.add_argument("--output-dir", type=Path, default=Path(
        "derived/scope/scope_wikidata_bibliographic_evidence_v0_1"))
    args = ap.parse_args()
    repo = args.repo.resolve()
    paths = {
        "active_frame": repo / "derived/scope/scope_evidence_pilot_v1/sampling_frame_v1.tsv",
        "identity_map_v7": repo / "derived/identity/work_identity_map_v7.tsv",
        "source_entities_v3": repo / "derived/identity/source_entities_v3.tsv",
        "wikidata_entities_parquet": args.source_parquet.expanduser().resolve(),
    }
    # Check before anything can be written.
    dest = args.output_dir if args.output_dir.is_absolute() else repo / args.output_dir
    if not args.dry_run and dest.exists():
        raise FileExistsError(f"Output already exists; refusing overwrite: {dest}")
    for p in paths.values():
        if not p.is_file():
            raise FileNotFoundError(p)
    active = load_tsv(paths["active_frame"])
    mapping = load_tsv(paths["identity_map_v7"])
    sources = load_tsv(paths["source_entities_v3"])
    entities = pd.read_parquet(paths["wikidata_entities_parquet"], columns=[
        "qid", "label_en_effective", "source_snapshot", *FIELDS])
    details, coverage, counts = build(active, mapping, sources, entities)
    print("=== SCOPE WIKIDATA BIBLIOGRAPHIC EVIDENCE QC ===")
    for key, count in counts.items():
        print(f"{key}: {count}")
    print("Property arrays are retained as Wikidata snapshot evidence, not validated")
    print("original dates/languages, and not scope classifications.")
    if args.dry_run:
        print("DRY-RUN VERIFIED — no files written.")
        return

    # All validations have passed; refuse replacement of prior outputs.
    dest.mkdir(parents=True, exist_ok=False)
    path_detail = dest / "scope_wikidata_qid_evidence_v0_1.tsv"
    path_cov = dest / "scope_wikidata_project_w_coverage_v0_1.tsv"
    path_manifest = dest / "scope_wikidata_bibliographic_evidence_manifest_v0_1.json"
    details.to_csv(path_detail, sep="\t", index=False, lineterminator="\n")
    coverage.to_csv(path_cov, sep="\t", index=False, lineterminator="\n")
    manifest = {
        "release": "scope_wikidata_bibliographic_evidence_v0_1",
        "snapshot": SNAPSHOT,
        "source_kind": "frozen Wikidata property-value projection via adopted identity v7 QIDs",
        "counts": counts,
        "inputs": {k: {"path": str(v), "sha256": sha256_file(v)} for k, v in paths.items()},
        "outputs": {p.name: {"rows": n, "sha256": sha256_file(p)} for p, n in
                    [(path_detail, len(details)), (path_cov, len(coverage))]},
        "interpretation_limits": [
            "QIDs are adopted identity matches, not independent bibliographic verification.",
            "P577 values are publication date evidence, not verified original publication years.",
            "P407 values are language statements, not verified original languages.",
            "P31 is entity type, not proof of an individual novel/novella.",
            "P629 usually links edition/translation item to its work and need not be present on work items.",
            "Frozen parquet arrays are value projections: statement ranks, qualifiers, and references are not retained here.",
            "Missing adopted Wikidata QID is not an out-of-scope decision.",
            "No changes to existing identity, historical OL projection, OpenAlex data, or researcher adjudications.",
        ],
    }
    path_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE: {dest}")
    print(f"Evidence rows: {len(details)} | all-W coverage rows: {len(coverage)}")


if __name__ == "__main__":
    main()
