#!/usr/bin/env python3
"""Join frozen OL and Wikidata *evidence* at active Project W granularity.

No scope adjudication, source-entity reconstruction, original publication-year
inference, or OpenAlex remeasurement. Both evidence layers stay unchanged.

From the canon-pipeline-openalex-a2val repository root:
  python -B scripts/build_scope_combined_bibliographic_evidence_v0_1.py --dry-run
  python -B scripts/build_scope_combined_bibliographic_evidence_v0_1.py

The output directory must not exist before a writing run.
"""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

EXPECTED_ACTIVE = 32066
EXPECTED_OL_HISTORICAL = 32062
EXPECTED_NO_OL_HISTORICAL = {
    "W000014515", "W000031537", "W000031538", "W000031539",
}
EXPECTED_WD = 6177
EXPECTED_P577 = 4473
EXPECTED_P407 = 4893
EXPECTED_P31 = 6120
EXPECTED_P629 = 1
EXPECTED_BOTH = 3651

DEFAULT_INPUTS = {
    "ol_project_w_frame": (
        "derived/scope/scope_ol_bibliographic_projection_v0_1/"
        "scope_project_w_bibliographic_frame_v0_1.tsv"
    ),
    "wikidata_coverage": (
        "derived/scope/scope_wikidata_bibliographic_evidence_v0_1/"
        "scope_wikidata_project_w_coverage_v0_1.tsv"
    ),
    "wikidata_qid_evidence": (
        "derived/scope/scope_wikidata_bibliographic_evidence_v0_1/"
        "scope_wikidata_qid_evidence_v0_1.tsv"
    ),
}
DEFAULT_OUT = "derived/scope/scope_combined_bibliographic_evidence_v0_1"
PROPERTIES = ("p577", "p407", "p31", "p629")
JSON_COLUMNS_OL = (
    "current_ol_work_ids_json",
    "historical_matched_ol_work_ids_json",
    "historical_unmatched_ol_work_ids_json",
    "historical_titles_json",
    "historical_authors_json",
    "historical_edition_derived_min_years_json",
    "historical_subject_keys_json",
)
JSON_COLUMNS_WD = (
    "wd_p31_values_json", "wd_p407_values_json", "wd_p577_values_json",
    "wd_p629_values_json", "wd_p577_parsed_positive_years_json",
)
WD_DETAIL_ONLY = (
    "project_work_id", "wikidata_label_en_effective", "identity_membership_role",
    "wikidata_snapshot", *JSON_COLUMNS_WD,
    "wd_p577_unparsed_values_count", "wd_p407_includes_english_q1860",
)


def read_tsv(path):
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)


def require(df, fields, name):
    absent = sorted(set(fields) - set(df.columns))
    if absent:
        raise ValueError(f"{name} missing columns: {absent}")


def unique_work_ids(df, name, expected_count):
    require(df, ("project_work_id",), name)
    assert len(df) == expected_count, (name, len(df), expected_count)
    assert df.project_work_id.is_unique and df.project_work_id.ne("").all(), name


def numerical(series, name, allow_empty=False):
    if allow_empty:
        assert series.str.fullmatch(r"(?:\d+)?").all(), name
        return pd.to_numeric(series.replace("", "0"), errors="raise")
    assert series.str.fullmatch(r"\d+").all(), name
    return pd.to_numeric(series, errors="raise")


def check_json_arrays(df, cols, name):
    for col in cols:
        for i, cell in enumerate(df[col]):
            try:
                arr = json.loads(cell)
            except (json.JSONDecodeError, TypeError) as ex:
                raise ValueError(f"{name}: {col}, row {i + 1}: invalid JSON") from ex
            if not isinstance(arr, list):
                raise ValueError(f"{name}: {col}, row {i + 1}: expected list")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build(ol, coverage, evidence):
    unique_work_ids(ol, "Open Library Project W frame", EXPECTED_ACTIVE)
    unique_work_ids(coverage, "Wikidata coverage", EXPECTED_ACTIVE)
    unique_work_ids(evidence, "Wikidata QID evidence", EXPECTED_WD)
    require(ol, ("bibliographic_evidence_status", "historical_matched_ol_work_count",
                 "historical_unmatched_ol_work_count", *JSON_COLUMNS_OL), "Open Library")
    require(coverage, ("wikidata_qid", "wikidata_evidence_status",
                       *(f"wd_{p}_count" for p in PROPERTIES)), "Wikidata coverage")
    require(evidence, ("wikidata_qid", *(f"wd_{p}_count" for p in PROPERTIES),
                       *WD_DETAIL_ONLY), "Wikidata evidence")
    assert evidence.wikidata_qid.is_unique and evidence.wikidata_qid.ne("").all()
    assert set(ol.project_work_id) == set(coverage.project_work_id)

    ol_status = ol.bibliographic_evidence_status.eq("FULL_HISTORICAL_MATCH")
    assert int(ol_status.sum()) == EXPECTED_OL_HISTORICAL
    actual_no_ol = set(ol.loc[~ol_status, "project_work_id"])
    assert actual_no_ol == EXPECTED_NO_OL_HISTORICAL, actual_no_ol

    # The QID coverage index is a frozen all-W projection. Verify its QIDs and
    # counts against the actual QID-evidence rows before using either dataset.
    linked = coverage.loc[coverage.wikidata_qid.ne("")].copy()
    assert len(linked) == EXPECTED_WD
    assert linked.wikidata_qid.is_unique
    assert set(linked.project_work_id) == set(evidence.project_work_id)
    unlinked = coverage.loc[coverage.wikidata_qid.eq("")]
    assert len(unlinked) == EXPECTED_ACTIVE - EXPECTED_WD
    assert unlinked.wikidata_evidence_status.eq("NO_ADOPTED_WIKIDATA_QID").all()
    assert linked.wikidata_evidence_status.eq("ADOPTED_QID_IN_FROZEN_PARQUET").all()
    assert not (linked.project_work_id.isin(EXPECTED_NO_OL_HISTORICAL)).any()
    for prop in PROPERTIES:
        col = f"wd_{prop}_count"
        assert unlinked[col].eq("").all(), f"Nonblank {col} for no-QID W"
    qc = linked[["project_work_id", "wikidata_qid", *(f"wd_{p}_count" for p in PROPERTIES)]].merge(
        evidence[["project_work_id", "wikidata_qid", *(f"wd_{p}_count" for p in PROPERTIES)]],
        on="project_work_id", how="outer", validate="one_to_one", indicator=True,
        suffixes=("_coverage", "_evidence"),
    )
    assert qc._merge.eq("both").all()
    for col in ("wikidata_qid", *(f"wd_{p}_count" for p in PROPERTIES)):
        assert qc[f"{col}_coverage"].equals(qc[f"{col}_evidence"]), col

    check_json_arrays(ol, JSON_COLUMNS_OL, "Open Library")
    check_json_arrays(evidence, JSON_COLUMNS_WD, "Wikidata")
    for prop in PROPERTIES:
        col = f"wd_{prop}_count"
        sizes = evidence[f"wd_{prop}_values_json"].map(lambda s: len(json.loads(s)))
        assert (sizes == numerical(evidence[col], col)).all(), col

    joined = ol.merge(coverage, on="project_work_id", how="left", validate="one_to_one", indicator=True)
    assert joined._merge.eq("both").all()
    joined.drop(columns="_merge", inplace=True)
    joined = joined.merge(evidence[list(WD_DETAIL_ONLY)], on="project_work_id", how="left",
                          validate="one_to_one", indicator=True)
    matched_evidence = joined._merge.eq("both")
    assert int(matched_evidence.sum()) == EXPECTED_WD
    assert (matched_evidence == joined.wikidata_qid.ne("")).all()
    joined.drop(columns="_merge", inplace=True)
    joined.fillna("", inplace=True)

    has_ol = joined.bibliographic_evidence_status.eq("FULL_HISTORICAL_MATCH")
    has_wd = joined.wikidata_qid.ne("")
    joined["bibliographic_source_combination"] = "NO_HISTORICAL_OL_OR_ADOPTED_WIKIDATA"
    joined.loc[has_ol & ~has_wd, "bibliographic_source_combination"] = "HISTORICAL_OL_ONLY"
    joined.loc[has_ol & has_wd, "bibliographic_source_combination"] = "HISTORICAL_OL_AND_WIKIDATA"
    joined.loc[~has_ol & has_wd, "bibliographic_source_combination"] = "WIKIDATA_ONLY"

    counts = numerical(joined.loc[has_wd, "wd_p577_count"], "P577 count")
    langs = numerical(joined.loc[has_wd, "wd_p407_count"], "P407 count")
    types = numerical(joined.loc[has_wd, "wd_p31_count"], "P31 count")
    editions = numerical(joined.loc[has_wd, "wd_p629_count"], "P629 count")
    report = {
        "active_project_w": len(joined),
        "historical_ol_w": int(has_ol.sum()),
        "no_historical_ol_w": int((~has_ol).sum()),
        "wikidata_qid_w": int(has_wd.sum()),
        "no_adopted_wikidata_w": int((~has_wd).sum()),
        "ol_and_wikidata_w": int((has_ol & has_wd).sum()),
        "ol_only_w": int((has_ol & ~has_wd).sum()),
        "wikidata_only_w": int((~has_ol & has_wd).sum()),
        "neither_w": int((~has_ol & ~has_wd).sum()),
        "wd_p577_nonempty": int((counts > 0).sum()),
        "wd_p407_nonempty": int((langs > 0).sum()),
        "wd_p31_nonempty": int((types > 0).sum()),
        "wd_p629_nonempty": int((editions > 0).sum()),
        "wd_p577_and_p407_nonempty": int(((counts > 0) & (langs > 0)).sum()),
    }
    assert report["no_historical_ol_w"] == len(EXPECTED_NO_OL_HISTORICAL)
    assert report["wd_p577_nonempty"] == EXPECTED_P577
    assert report["wd_p407_nonempty"] == EXPECTED_P407
    assert report["wd_p31_nonempty"] == EXPECTED_P31
    assert report["wd_p629_nonempty"] == EXPECTED_P629
    assert report["wd_p577_and_p407_nonempty"] == EXPECTED_BOTH
    assert report["ol_and_wikidata_w"] == EXPECTED_WD
    assert report["ol_only_w"] == EXPECTED_OL_HISTORICAL - EXPECTED_WD
    assert report["neither_w"] == 4 and report["wikidata_only_w"] == 0
    joined.sort_values("project_work_id", inplace=True)
    joined.reset_index(drop=True, inplace=True)
    assert joined.project_work_id.is_unique
    return joined, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--ol-frame", type=Path, default=None)
    parser.add_argument("--wd-coverage", type=Path, default=None)
    parser.add_argument("--wd-evidence", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path(DEFAULT_OUT))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    overrides = {
        "ol_project_w_frame": args.ol_frame,
        "wikidata_coverage": args.wd_coverage,
        "wikidata_qid_evidence": args.wd_evidence,
    }
    paths = {
        label: (path if path.is_absolute() else repo / path).resolve()
        for label, path in (
            (label, overrides[label] or Path(DEFAULT_INPUTS[label]))
            for label in DEFAULT_INPUTS
        )
    }
    outdir = args.output_dir if args.output_dir.is_absolute() else repo / args.output_dir
    if not args.dry_run and outdir.exists():
        raise FileExistsError(f"Output exists, refusing overwrite: {outdir}")
    ol, coverage, evidence = (read_tsv(paths[name]) for name in DEFAULT_INPUTS)
    joint, counts = build(ol, coverage, evidence)
    print("=== COMBINED SCOPE BIBLIOGRAPHIC EVIDENCE QC ===")
    for key, value in counts.items():
        print(f"{key}: {value}")
    print("Source-native OL and Wikidata attributes retained; NO scope or original-year inference.")
    if args.dry_run:
        print("DRY-RUN VERIFIED — no files written.")
        return
    # Validation must complete before this directory is created. No overwrite.
    outdir.mkdir(parents=True, exist_ok=False)
    output = outdir / "scope_combined_project_w_bibliographic_evidence_v0_1.tsv"
    manifest_path = outdir / "scope_combined_bibliographic_evidence_manifest_v0_1.json"
    joint.to_csv(output, sep="\t", index=False, lineterminator="\n")
    manifest = {
        "release": "scope_combined_bibliographic_evidence_v0_1",
        "unit": "active Project W",
        "source_snapshots": {"historical_open_library": "2026-02-28", "wikidata": "2026-08-05"},
        "counts": counts,
        "known_without_either_source": sorted(EXPECTED_NO_OL_HISTORICAL),
        "inputs": {
            label: {"path": str(path), "sha256": sha256(path)}
            for label, path in paths.items()
        },
        "outputs": {output.name: {"rows": len(joint), "sha256": sha256(output)}},
        "method": (
            "Lossless one-to-one Project W join of the OL bibliographic frame, Wikidata "
            "all-W coverage, and adopted-QID evidence; unlinked QID detail fields left blank."
        ),
        "limitations": [
            "OL edition-derived minimum years are not verified first original publication years.",
            "Wikidata P577/P407/P31/P629 arrays are source-native, not adjudicated original dates/languages/genres.",
            "The extraction of Wikidata statements may omit claim qualifiers, ranks, and reference details.",
            "Empty Wikidata details with no adopted QID differ from [] for linked QIDs with absent properties.",
            "No scope classification or researcher adjudication was added.",
            "Source W identities and OpenAlex candidate counts were not modified.",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"WROTE: {outdir}")
    print(f"Combined Project W rows: {len(joint)}")


if __name__ == "__main__":
    main()
