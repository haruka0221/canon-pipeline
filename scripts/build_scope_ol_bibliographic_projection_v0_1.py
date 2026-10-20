#!/usr/bin/env python3
"""Build a provenance-preserving OL bibliographic *input* for scope review.

This does not decide literary genre, original language, or first original publication
year. It does not modify identity, OpenAlex, or researcher review data.

Run from the canon-pipeline-openalex-a2val repository root:
  python -B scripts/build_scope_ol_bibliographic_projection_v0_1.py --dry-run
  python -B scripts/build_scope_ol_bibliographic_projection_v0_1.py

Outputs (new directory, refuses to overwrite):
  derived/scope/scope_ol_bibliographic_projection_v0_1/
    scope_ol_work_evidence_v0_1.tsv
    scope_project_w_bibliographic_frame_v0_1.tsv
    scope_ol_bibliographic_projection_manifest_v0_1.json
"""

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path

import pandas as pd

ACTIVE_DEFAULT = "derived/scope/scope_evidence_pilot_v1/sampling_frame_v1.tsv"
MAP_DEFAULT = "derived/identity/work_identity_map_v7.tsv"
ENTITIES_DEFAULT = "derived/identity/source_entities_v3.tsv"
OUTPUT_DEFAULT = "derived/scope/scope_ol_bibliographic_projection_v0_1"
EXPECTED_MISSING = {
    "W000014515",  # existing source-light Alcott hold
    "W000031537",  # The Prisoner of Zenda: current OL ID outside historical population
    "W000031538",  # The Good Soldier: current OL ID outside historical population
    "W000031539",  # Dracula: current OL ID outside historical population
}
EXPECTED_UNMATCHED_OL = {"OL245401W", "OL509889W", "OL85892W"}
WORK_RE = re.compile(r"OL\d+W")


def require_columns(df, cols, label):
    absent = sorted(set(cols) - set(df.columns))
    if absent:
        raise ValueError(f"{label} missing columns: {absent}")


def read_tsv(path):
    return pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)


def ol_id(raw):
    match = WORK_RE.search(raw)
    return match.group(0) if match else ""


def unique_nonblank(values):
    return sorted({v.strip() for v in values if v and v.strip()})


def stable_json(values):
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def sha256(path):
    hash_ = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(2**20), b""):
            hash_.update(chunk)
    return hash_.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--active", default=ACTIVE_DEFAULT)
    parser.add_argument("--identity-map", default=MAP_DEFAULT)
    parser.add_argument("--source-entities", default=ENTITIES_DEFAULT)
    parser.add_argument(
        "--historical", default=str(Path.home() / "canon-pipeline/derived/ol_dump_population_with_author.tsv")
    )
    parser.add_argument("--output-dir", default=OUTPUT_DEFAULT)
    parser.add_argument("--dry-run", action="store_true", help="Validate and print QC without writing any files")
    args = parser.parse_args()
    inputs = {
        "active_project_w_frame": Path(args.active),
        "identity_map_v7": Path(args.identity_map),
        "source_entities_v3": Path(args.source_entities),
        "historical_ol_population": Path(args.historical),
    }
    for name, path in inputs.items():
        if not path.is_file():
            raise FileNotFoundError(f"{name}: {path}")

    active = read_tsv(inputs["active_project_w_frame"])
    mapping = read_tsv(inputs["identity_map_v7"])
    entities = read_tsv(inputs["source_entities_v3"])
    historical = read_tsv(inputs["historical_ol_population"])
    require_columns(active, ["project_work_id", "measurement_status", "query_title", "query_author"], "active")
    require_columns(mapping, ["project_work_id", "source_entity_id", "membership_role"], "identity map")
    require_columns(entities, ["entity_id", "source", "source_namespace", "source_id", "entity_type", "source_snapshot", "source_artifact", "provenance_ref"], "source entities")
    require_columns(historical, ["work_key", "title", "author_name", "first_publish_year", "subject_keys_str"], "historical")

    if len(active) != 32066 or active.project_work_id.duplicated().any() or active.project_work_id.eq("").any():
        raise ValueError("Active 32,066-W frozen frame not as expected")
    if entities.entity_id.duplicated().any():
        raise ValueError("Duplicated source entity IDs")
    active_ids = set(active.project_work_id)
    am = mapping.loc[mapping.project_work_id.isin(active_ids)].copy()
    bridge = am.merge(entities, left_on="source_entity_id", right_on="entity_id", how="left", validate="many_to_one", indicator=True)
    if not bridge["_merge"].eq("both").all():
        raise ValueError("Active membership points to unknown source entity")
    ol = bridge.loc[
        bridge.source.eq("openlibrary") & bridge.source_namespace.eq("work") & bridge.entity_type.eq("work")
    ].copy()
    if not ol.membership_role.eq("current_analysis_target").all():
        raise ValueError("Unexpected role among current OL Work memberships")
    ol["ol_work_id"] = ol.source_id.map(ol_id)
    if ol.ol_work_id.eq("").any():
        raise ValueError("Invalid current OL Work IDs")
    if ol.ol_work_id.duplicated().any():
        raise ValueError("One OL Work mapped more than once; review identity before proceeding")

    h = historical.copy()
    h["ol_work_id"] = h.work_key.map(ol_id)
    if h.ol_work_id.eq("").any() or h.ol_work_id.duplicated().any():
        raise ValueError("Invalid or duplicate historical OL Work IDs")
    h = h.rename(columns={
        "work_key": "historical_work_key",
        "title": "historical_title",
        "author_name": "historical_author_name",
        # Historical first_publish_year was generated from edition minimum, not original publication.
        "first_publish_year": "historical_edition_derived_min_year",
        "subject_keys_str": "historical_subject_keys_str",
    })
    selected = [
        "project_work_id", "source_entity_id", "membership_role", "membership_basis",
        "aggregation_decision_version", "ol_work_id", "source_snapshot", "source_artifact", "provenance_ref",
    ]
    require_columns(ol, selected, "current OL membership")
    details = ol[selected].merge(
        h[["ol_work_id", "historical_work_key", "historical_title", "historical_author_name", "historical_edition_derived_min_year", "historical_subject_keys_str"]],
        how="left", on="ol_work_id", validate="one_to_one", indicator=True,
    )
    details["historical_match_status"] = details.pop("_merge").map({
        "both": "HISTORICAL_MATCH", "left_only": "NO_HISTORICAL_MATCH",
    }).astype(str)
    for column in ["historical_work_key", "historical_title", "historical_author_name", "historical_edition_derived_min_year", "historical_subject_keys_str"]:
        details[column] = details[column].fillna("")
    details = details.sort_values(["project_work_id", "ol_work_id"], kind="stable").reset_index(drop=True)

    by_w = {wid: part for wid, part in details.groupby("project_work_id", sort=False)}
    summary_rows = []
    for row in active.itertuples(index=False):
        w = row.project_work_id
        part = by_w.get(w)
        if part is None:
            n_all = n_matched = n_unmatched = 0
            all_ol, matched_ol, unmatched_ol = [], [], []
            titles, authors, years, subjects = [], [], [], []
            status = "NO_CURRENT_OL_WORK"
        else:
            yes = part.loc[part.historical_match_status.eq("HISTORICAL_MATCH")]
            no = part.loc[part.historical_match_status.eq("NO_HISTORICAL_MATCH")]
            n_all, n_matched, n_unmatched = len(part), len(yes), len(no)
            all_ol = sorted(part.ol_work_id.tolist())
            matched_ol = sorted(yes.ol_work_id.tolist())
            unmatched_ol = sorted(no.ol_work_id.tolist())
            titles = unique_nonblank(yes.historical_title.tolist())
            authors = unique_nonblank(yes.historical_author_name.tolist())
            years = unique_nonblank(yes.historical_edition_derived_min_year.tolist())
            subjects = unique_nonblank(
                [term for raw in yes.historical_subject_keys_str for term in raw.split(";")]
            )
            if n_matched == n_all:
                status = "FULL_HISTORICAL_MATCH"
            elif n_matched > 0:
                status = "PARTIAL_HISTORICAL_MATCH"
            else:
                status = "NO_HISTORICAL_MATCH"
        summary_rows.append({
            "project_work_id": w,
            "measurement_status": row.measurement_status,
            "retrieval_query_title": row.query_title,
            "retrieval_query_author": row.query_author,
            "bibliographic_evidence_status": status,
            "current_ol_work_count": n_all,
            "historical_matched_ol_work_count": n_matched,
            "historical_unmatched_ol_work_count": n_unmatched,
            "current_ol_work_ids_json": stable_json(all_ol),
            "historical_matched_ol_work_ids_json": stable_json(matched_ol),
            "historical_unmatched_ol_work_ids_json": stable_json(unmatched_ol),
            "historical_titles_json": stable_json(titles),
            "historical_authors_json": stable_json(authors),
            "historical_edition_derived_min_years_json": stable_json(years),
            "historical_subject_keys_json": stable_json(subjects),
        })
    summary = pd.DataFrame(summary_rows)
    assert len(summary) == 32066 and summary.project_work_id.is_unique
    matched = details.historical_match_status.eq("HISTORICAL_MATCH")
    missing = set(summary.loc[summary.historical_matched_ol_work_count.eq(0), "project_work_id"])
    unmatched_ol = set(details.loc[~matched, "ol_work_id"])

    checks = {
        "active_project_w": len(active),
        "ol_work_memberships": len(details),
        "historically_matched_ol_works": int(matched.sum()),
        "historically_unmatched_ol_works": int((~matched).sum()),
        "project_w_with_historical_match": int(summary.historical_matched_ol_work_count.gt(0).sum()),
        "project_w_without_historical_match": int(summary.historical_matched_ol_work_count.eq(0).sum()),
        "project_w_with_2plus_historical_ol": int(summary.historical_matched_ol_work_count.ge(2).sum()),
        "project_w_with_1_historical_ol": int(summary.historical_matched_ol_work_count.eq(1).sum()),
        "project_w_without_current_ol": int(summary.current_ol_work_count.eq(0).sum()),
    }
    expected = {
        "active_project_w": 32066,
        "ol_work_memberships": 32689,
        "historically_matched_ol_works": 32686,
        "historically_unmatched_ol_works": 3,
        "project_w_with_historical_match": 32062,
        "project_w_without_historical_match": 4,
        "project_w_with_2plus_historical_ol": 550,
        "project_w_with_1_historical_ol": 31512,
        "project_w_without_current_ol": 1,
    }
    if checks != expected or missing != EXPECTED_MISSING or unmatched_ol != EXPECTED_UNMATCHED_OL:
        raise ValueError(f"Projection QC differs from frozen read-only inspection!\nActual counts {checks}\nMissing W {sorted(missing)}\nMissing OL {sorted(unmatched_ol)}")

    print("=== SCOPE OL BIBLIOGRAPHIC PROJECTION QC ===")
    for key, value in checks.items():
        print(f"{key}: {value}")
    print("W without historical match:", ", ".join(sorted(missing)))
    print("Current OL IDs absent from historical population:", ", ".join(sorted(unmatched_ol)))
    print("No scope classifications or original-publication-year inferences were made.")
    if args.dry_run:
        print("DRY-RUN VERIFIED — no files written.")
        return

    out = Path(args.output_dir)
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite existing output directory: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": "v0_1",
        "purpose": "Provenance-preserving current Project W to historical OL Work projection for later scope screening",
        "classification_performed": False,
        "original_publication_year_inferred": False,
        "historical_first_publish_year_definition": "minimum linked OL Edition-derived year (not original publication year)",
        "input_files": {label: {"path": str(path), "sha256": sha256(path)} for label, path in inputs.items()},
        "counts": checks,
        "expected_w_without_historical_match": sorted(missing),
        "expected_current_ol_work_ids_without_historical_match": sorted(unmatched_ol),
        "note": "OL Current Work identities remain distinct from historical source rows; no backfill or identity repair is attempted.",
    }
    # Write in an isolated temporary directory, then atomically move it into place.
    with tempfile.TemporaryDirectory(prefix=".scope_ol_projection_staging_", dir=out.parent) as tmp:
        tempdir = Path(tmp)
        details.to_csv(tempdir / "scope_ol_work_evidence_v0_1.tsv", sep="\t", index=False, lineterminator="\n")
        summary.to_csv(tempdir / "scope_project_w_bibliographic_frame_v0_1.tsv", sep="\t", index=False, lineterminator="\n")
        (tempdir / "scope_ol_bibliographic_projection_manifest_v0_1.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        # Out doesn't exist, so rename of complete staging directory is non-destructive.
        tempdir.rename(out)
    print("WROTE:", out)
    print("OL Work rows:", len(details), "Project W rows:", len(summary))


if __name__ == "__main__":
    main()
