from pathlib import Path
import hashlib
import json
import os
import re
import unicodedata

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

PROJECT_WORKS = ROOT / "derived/identity/project_works_v5.parquet"
WORK_MAP = ROOT / "derived/identity/work_identity_map_v5.parquet"
DECISIONS = ROOT / "derived/identity/aggregation_decisions_v4.parquet"
MEMBERS = ROOT / "derived/identity/aggregation_review_members_v1.parquet"
OL_TARGETS = ROOT / "derived/identity/openlibrary_analysis_targets_v1.parquet"
SOURCE_ENTITIES = ROOT / "derived/identity/source_entities_v2.parquet"

PROJECT_WORKS_MANIFEST = ROOT / "derived/identity/project_works_v5_manifest.json"
DECISIONS_MANIFEST = ROOT / "derived/identity/aggregation_decisions_v4_manifest.json"
OL_TARGETS_MANIFEST = ROOT / "derived/identity/openlibrary_analysis_targets_v1_manifest.json"
SOURCE_ENTITIES_MANIFEST = ROOT / "derived/identity/source_entities_v2_manifest.json"

OUT_DIR = ROOT / "derived/openalex_production/registry_v4"
OUT_TARGETS_TSV = OUT_DIR / "openalex_targets_v4.tsv"
OUT_TARGETS_PARQUET = OUT_DIR / "openalex_targets_v4.parquet"
OUT_ALIASES_TSV = OUT_DIR / "openalex_aliases_v4.tsv"
OUT_ALIASES_PARQUET = OUT_DIR / "openalex_aliases_v4.parquet"
OUT_MANIFEST = OUT_DIR / "openalex_alias_registry_v4_manifest.json"

RELEASE = "openalex-alias-registry-v4"
REGISTRY_VERSION = "v4"
ALIAS_NORMALIZATION_VERSION = "openalex_alias_title_norm_v1"
CREATED_AT = "2026-10-02"

EXPECTED_PROJECT_WORKS = 32082
EXPECTED_RESOLVED_CURRENT_TARGETS = 32706
EXPECTED_UNRESOLVED_UNITS = 761
EXPECTED_UNRESOLVED_CURRENT_TARGETS = 2083
EXPECTED_ALL_CURRENT_TARGETS = 34789
EXPECTED_TARGET_ROWS = EXPECTED_PROJECT_WORKS + EXPECTED_UNRESOLVED_UNITS

_WS_RE = re.compile(r"\s+")


def require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_atomic_tsv(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    df.to_csv(tmp, sep="\t", index=False, lineterminator="\n")
    os.replace(tmp, path)


def write_atomic_parquet(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(tmp, index=False, engine="pyarrow")
    os.replace(tmp, path)


def write_atomic_json(value: dict, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def alias_title_norm(value: str) -> str:
    """Conservative alias-string normalization, not execution normalization."""
    value = unicodedata.normalize("NFKC", str(value or ""))
    value = value.casefold()
    value = _WS_RE.sub(" ", value).strip()
    return value


def alias_id(n: int) -> str:
    return f"OAA{n:09d}"


def as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return series.astype(str).str.lower().isin({"true", "1", "yes"})


def main() -> None:
    for path in [
        PROJECT_WORKS,
        WORK_MAP,
        DECISIONS,
        MEMBERS,
        OL_TARGETS,
        SOURCE_ENTITIES,
        PROJECT_WORKS_MANIFEST,
        DECISIONS_MANIFEST,
        OL_TARGETS_MANIFEST,
        SOURCE_ENTITIES_MANIFEST,
    ]:
        require(path)

    all_works = pd.read_parquet(PROJECT_WORKS).fillna("")

    if len(all_works) != 32089:
        raise RuntimeError(
            f"Expected 32089 historical project-work rows; "
            f"found {len(all_works)}"
        )

    if int(all_works["status"].eq("superseded").sum()) != 7:
        raise RuntimeError(
            "Expected exactly 7 superseded project works in v5"
        )

    works = all_works[
        all_works["status"].eq("active")
    ].copy()

    work_map = pd.read_parquet(WORK_MAP).fillna("")
    decisions = pd.read_parquet(DECISIONS).fillna("")
    members = pd.read_parquet(MEMBERS).fillna("")
    ol_targets = pd.read_parquet(OL_TARGETS).fillna("")
    source_entities = pd.read_parquet(SOURCE_ENTITIES).fillna("")

    project_works_manifest = read_json(PROJECT_WORKS_MANIFEST)
    decisions_manifest = read_json(DECISIONS_MANIFEST)
    ol_targets_manifest = read_json(OL_TARGETS_MANIFEST)
    source_entities_manifest = read_json(SOURCE_ENTITIES_MANIFEST)

    # ---------------------------------------------------------
    # Input invariants
    # ---------------------------------------------------------

    if len(works) != EXPECTED_PROJECT_WORKS:
        raise RuntimeError(
            f"Expected {EXPECTED_PROJECT_WORKS} project works; found {len(works)}"
        )

    if not works["project_work_id"].is_unique:
        raise RuntimeError("active project_works_v5 project_work_id is not unique")

    if len(ol_targets) != EXPECTED_ALL_CURRENT_TARGETS:
        raise RuntimeError(
            f"Expected {EXPECTED_ALL_CURRENT_TARGETS} current OL targets; "
            f"found {len(ol_targets)}"
        )

    for col in ["current_entity_id", "current_ol_work_id"]:
        if not ol_targets[col].is_unique:
            raise RuntimeError(
                f"openlibrary_analysis_targets_v1 {col} is not unique"
            )

    if ol_targets["title"].astype(str).str.strip().eq("").any():
        raise RuntimeError("Current Open Library target with empty title")

    current_map = work_map[
        work_map["membership_role"].eq("current_analysis_target")
    ].copy()

    if len(current_map) != EXPECTED_RESOLVED_CURRENT_TARGETS:
        raise RuntimeError(
            f"Expected {EXPECTED_RESOLVED_CURRENT_TARGETS} resolved current "
            f"targets; found {len(current_map)}"
        )

    if not current_map["source_entity_id"].is_unique:
        raise RuntimeError(
            "Resolved current target appears in more than one project W"
        )

    pending = decisions[
        decisions["aggregation_decision"].eq("MANUAL_REVIEW_REQUIRED")
    ].copy()

    if len(pending) != EXPECTED_UNRESOLVED_UNITS:
        raise RuntimeError(
            f"Expected {EXPECTED_UNRESOLVED_UNITS} unresolved units; "
            f"found {len(pending)}"
        )

    members = members.copy()
    members["is_current_target"] = as_bool(members["is_current_target"])

    pending_current = members[
        members["unit_anchor_entity_id"].isin(
            set(pending["unit_anchor_entity_id"])
        )
        & members["is_current_target"]
    ].copy()

    if len(pending_current) != EXPECTED_UNRESOLVED_CURRENT_TARGETS:
        raise RuntimeError(
            f"Expected {EXPECTED_UNRESOLVED_CURRENT_TARGETS} unresolved "
            f"current targets; found {len(pending_current)}"
        )

    if not pending_current["entity_id"].is_unique:
        raise RuntimeError(
            "Unresolved current target appears in more than one pending unit"
        )

    resolved_entity_ids = set(current_map["source_entity_id"])
    unresolved_entity_ids = set(pending_current["entity_id"])
    all_target_entity_ids = set(ol_targets["current_entity_id"])

    if resolved_entity_ids & unresolved_entity_ids:
        raise RuntimeError("Resolved and unresolved current-target lanes overlap")

    if resolved_entity_ids | unresolved_entity_ids != all_target_entity_ids:
        missing = all_target_entity_ids - (
            resolved_entity_ids | unresolved_entity_ids
        )
        extra = (
            resolved_entity_ids | unresolved_entity_ids
        ) - all_target_entity_ids
        raise RuntimeError(
            f"Current target accounting mismatch; "
            f"missing={len(missing)} extra={len(extra)}"
        )

    # ---------------------------------------------------------
    # Target registry: one row per W plus one per unresolved unit
    # ---------------------------------------------------------

    resolved_counts = (
        current_map.groupby("project_work_id", sort=False)
        .size()
        .rename("current_ol_target_count")
    )

    if set(resolved_counts.index) != set(works["project_work_id"]):
        raise RuntimeError(
            "Every released project W must have at least one current OL target"
        )

    resolved_targets = works[
        [
            "project_work_id",
            "origin_unit_anchor_entity_id",
            "aggregation_decision",
            "aggregation_decision_version",
        ]
    ].copy()

    resolved_targets["target_lane"] = "resolved_w"
    resolved_targets["unresolved_unit_anchor_entity_id"] = ""
    resolved_targets["current_ol_target_count"] = (
        resolved_targets["project_work_id"].map(resolved_counts).astype(int)
    )
    resolved_targets["target_status"] = "identity_resolved"
    resolved_targets["scope_release"] = "not_applied"
    resolved_targets["target_registry_version"] = REGISTRY_VERSION

    unresolved_targets = pending[
        [
            "unit_anchor_entity_id",
            "aggregation_decision",
            "decision_version",
            "current_target_count",
        ]
    ].copy()

    unresolved_targets = unresolved_targets.rename(
        columns={
            "unit_anchor_entity_id": "unresolved_unit_anchor_entity_id",
            "decision_version": "aggregation_decision_version",
            "current_target_count": "current_ol_target_count",
        }
    )
    unresolved_targets["project_work_id"] = ""
    unresolved_targets["origin_unit_anchor_entity_id"] = ""
    unresolved_targets["target_lane"] = "unresolved_source"
    unresolved_targets["target_status"] = "identity_unresolved"
    unresolved_targets["scope_release"] = "not_applied"
    unresolved_targets["target_registry_version"] = REGISTRY_VERSION
    unresolved_targets["current_ol_target_count"] = (
        unresolved_targets["current_ol_target_count"].astype(int)
    )

    target_columns = [
        "target_lane",
        "project_work_id",
        "unresolved_unit_anchor_entity_id",
        "origin_unit_anchor_entity_id",
        "current_ol_target_count",
        "aggregation_decision",
        "aggregation_decision_version",
        "target_status",
        "scope_release",
        "target_registry_version",
    ]

    resolved_targets = resolved_targets[target_columns]
    unresolved_targets = unresolved_targets[target_columns]

    resolved_targets = resolved_targets.sort_values(
        "project_work_id", kind="stable"
    )
    unresolved_targets = unresolved_targets.sort_values(
        "unresolved_unit_anchor_entity_id", kind="stable"
    )

    targets = pd.concat(
        [resolved_targets, unresolved_targets],
        ignore_index=True,
    )

    if len(targets) != EXPECTED_TARGET_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_TARGET_ROWS} target rows; found {len(targets)}"
        )

    if (
        int(targets["current_ol_target_count"].sum())
        != EXPECTED_ALL_CURRENT_TARGETS
    ):
        raise RuntimeError(
            "Target registry does not account for all current OL targets"
        )

    # ---------------------------------------------------------
    # Alias registry: lossless current-OL title evidence
    # ---------------------------------------------------------

    resolved_lookup = current_map.set_index("source_entity_id")[
        [
            "project_work_id",
            "membership_role",
            "membership_basis",
        ]
    ].to_dict("index")

    unresolved_lookup = pending_current.set_index("entity_id")[
        [
            "unit_anchor_entity_id",
            "member_role",
        ]
    ].to_dict("index")

    source_lookup = source_entities.set_index("entity_id")[
        [
            "source",
            "source_namespace",
            "source_id",
            "source_snapshot",
            "source_artifact",
            "provenance_ref",
        ]
    ].to_dict("index")

    alias_rows = []
    ordered_targets = ol_targets.sort_values(
        "current_entity_id", kind="stable"
    )

    for n, row in enumerate(
        ordered_targets.to_dict("records"),
        start=1,
    ):
        entity_id = str(row["current_entity_id"])
        source_row = source_lookup.get(entity_id)

        if source_row is None:
            raise RuntimeError(
                f"Missing source_entities_v2 row for {entity_id}"
            )

        if (
            source_row["source"] != "openlibrary"
            or source_row["source_namespace"] != "work"
        ):
            raise RuntimeError(
                f"Unexpected source identity for {entity_id}: {source_row}"
            )

        if str(source_row["source_id"]) != str(
            row["current_ol_work_id"]
        ):
            raise RuntimeError(
                f"Open Library source ID mismatch for {entity_id}: "
                f"{source_row['source_id']} != {row['current_ol_work_id']}"
            )

        if entity_id in resolved_lookup:
            m = resolved_lookup[entity_id]
            target_lane = "resolved_w"
            project_work_id = str(m["project_work_id"])
            unresolved_anchor = ""
            membership_role = str(m["membership_role"])
            membership_basis = str(m["membership_basis"])
        else:
            m = unresolved_lookup.get(entity_id)
            if m is None:
                raise RuntimeError(
                    f"Current target not assigned to either lane: {entity_id}"
                )
            target_lane = "unresolved_source"
            project_work_id = ""
            unresolved_anchor = str(m["unit_anchor_entity_id"])
            membership_role = str(m["member_role"])
            membership_basis = (
                "aggregation_decisions_v4:MANUAL_REVIEW_REQUIRED"
            )

        raw_title = str(row["title"])
        norm_title = alias_title_norm(raw_title)

        if not norm_title:
            raise RuntimeError(
                f"Empty normalized alias title for {entity_id}"
            )

        alias_rows.append(
            {
                "alias_id": alias_id(n),
                "target_lane": target_lane,
                "project_work_id": project_work_id,
                "unresolved_unit_anchor_entity_id": unresolved_anchor,
                "alias_project_source_entity_id": entity_id,
                "alias_source": str(source_row["source"]),
                "alias_source_namespace": str(
                    source_row["source_namespace"]
                ),
                "alias_source_record_id": str(source_row["source_id"]),
                "alias_source_snapshot": str(
                    source_row["source_snapshot"]
                ),
                "alias_source_artifact": str(
                    source_row["source_artifact"]
                ),
                "alias_provenance_ref": str(
                    source_row["provenance_ref"]
                ),
                "alias_domain": "title",
                "alias_value_raw": raw_title,
                "alias_value_norm": norm_title,
                "alias_normalization_version": (
                    ALIAS_NORMALIZATION_VERSION
                ),
                "alias_role": "openlibrary_work_title",
                "alias_quality": "usable",
                "alias_quality_reason": (
                    "frozen_current_openlibrary_analysis_target_title;"
                    "representative_not_yet_selected"
                ),
                "alias_provenance": (
                    "derived/identity/"
                    "openlibrary_analysis_targets_v1.parquet"
                ),
                "membership_role": membership_role,
                "membership_basis": membership_basis,
                "historical_entity_id": str(
                    row["historical_entity_id"]
                ),
                "historical_ol_work_id": str(
                    row["historical_ol_work_id"]
                ),
                "target_resolution": str(row["target_resolution"]),
                "alias_registry_version": REGISTRY_VERSION,
                "created_at": CREATED_AT,
            }
        )

    aliases = pd.DataFrame(alias_rows)

    if len(aliases) != EXPECTED_ALL_CURRENT_TARGETS:
        raise RuntimeError(
            f"Expected {EXPECTED_ALL_CURRENT_TARGETS} aliases; "
            f"found {len(aliases)}"
        )

    if not aliases["alias_id"].is_unique:
        raise RuntimeError("alias_id is not unique")

    if not aliases["alias_project_source_entity_id"].is_unique:
        raise RuntimeError(
            "v4 OL-title layer should contain one alias per current OL target"
        )

    lane_counts = aliases["target_lane"].value_counts().to_dict()
    expected_lane_counts = {
        "resolved_w": EXPECTED_RESOLVED_CURRENT_TARGETS,
        "unresolved_source": EXPECTED_UNRESOLVED_CURRENT_TARGETS,
    }
    if lane_counts != expected_lane_counts:
        raise RuntimeError(
            f"Unexpected alias lane counts: {lane_counts}"
        )

    if set(aliases["alias_quality"]) != {"usable"}:
        raise RuntimeError(
            "Unexpected alias-quality state in v4 OL-title layer"
        )

    # ---------------------------------------------------------
    # Diagnostics: preserve duplicates/collisions; do not drop
    # ---------------------------------------------------------

    resolved_aliases = aliases[
        aliases["target_lane"].eq("resolved_w")
    ].copy()

    aliases_per_w = (
        resolved_aliases.groupby("project_work_id").size()
    )
    works_with_multiple_ol_aliases = int(
        (aliases_per_w > 1).sum()
    )
    max_ol_aliases_per_w = int(aliases_per_w.max())

    within_w_norm = (
        resolved_aliases.groupby(
            ["project_work_id", "alias_value_norm"]
        )
        .size()
        .rename("n")
    )
    within_w_dup_groups = within_w_norm[
        within_w_norm > 1
    ]
    within_w_duplicate_norm_groups = int(
        len(within_w_dup_groups)
    )
    within_w_alias_rows_in_duplicate_norm_groups = int(
        within_w_dup_groups.sum()
    )

    norm_w_memberships = resolved_aliases[
        ["alias_value_norm", "project_work_id"]
    ].drop_duplicates()
    cross_w_counts = norm_w_memberships.groupby(
        "alias_value_norm"
    )["project_work_id"].nunique()
    cross_w_collision_values = cross_w_counts[
        cross_w_counts > 1
    ]
    cross_w_normalized_title_collision_values = int(
        len(cross_w_collision_values)
    )
    cross_w_normalized_title_collision_w_memberships = int(
        cross_w_collision_values.sum()
    )

    corrected_target_rows = int(
        aliases["target_resolution"]
        .ne("unchanged_frozen_target")
        .sum()
    )

    # ---------------------------------------------------------
    # Write outputs
    # ---------------------------------------------------------

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    write_atomic_tsv(targets, OUT_TARGETS_TSV)
    write_atomic_parquet(targets, OUT_TARGETS_PARQUET)
    write_atomic_tsv(aliases, OUT_ALIASES_TSV)
    write_atomic_parquet(aliases, OUT_ALIASES_PARQUET)

    manifest = {
        "release": RELEASE,
        "created_at": CREATED_AT,
        "status": "frozen_alias_and_target_registry",
        "registry_version": REGISTRY_VERSION,
        "purpose": (
            "Re-express the 34,789 current Open Library retrieval-title "
            "targets against project-native W identity, while preserving "
            "the 761 intentionally unresolved aggregation units in a "
            "separate lane."
        ),
        "semantics": {
            "master_resolved_unit": (
                "project_work_id from project_works_v5"
            ),
            "resolved_lane": (
                "One OpenAlex target row per active project W. "
                "All current Open Library target titles assigned to "
                "that W are retained as separate alias rows."
            ),
            "unresolved_lane": (
                "One target row per aggregation_decisions_v4 "
                "MANUAL_REVIEW_REQUIRED unit, with project_work_id "
                "left null/empty. Its current Open Library titles are "
                "retained as aliases but cannot contribute to current "
                "W-level visibility."
            ),
            "alias_scope_v4": (
                "This v4 alias release retains one title alias "
                "for each current Open Library analysis target. "
                "Goodreads/Wikidata titles are not promoted here; they "
                "remain corroborating evidence until a separate uniform "
                "alias-expansion rule is defined."
            ),
            "alias_quality": (
                "All frozen current Open Library target titles are "
                "marked usable as source title evidence. Retrieval "
                "ambiguity, generic-title burden, and R4 eligibility are "
                "later query/retrieval diagnostics and are not encoded "
                "as alias-quality exclusions."
            ),
            "representative_title": (
                "No R2 representative alias is selected in this release. "
                "That is the next separately versioned milestone."
            ),
            "duplicate_policy": (
                "Alias rows are not deduplicated across source entities, "
                "within W, or across W. Provenance survives normalization "
                "collisions."
            ),
            "query_author_policy": (
                "openlibrary-query-author-selection-v1 is intentionally "
                "not merged into the alias registry. It will be joined "
                "at logical-query creation."
            ),
        },
        "alias_normalization": {
            "version": ALIAS_NORMALIZATION_VERSION,
            "rule": [
                "Unicode NFKC",
                "Unicode casefold",
                "collapse all whitespace runs to one ASCII space",
                "strip leading/trailing whitespace",
                "do not remove punctuation",
                "do not remove leading articles",
            ],
            "note": (
                "This is alias-string normalization for registry "
                "diagnostics. It is not the future "
                "normalized_query_signature execution rule."
            ),
        },
        "source_releases": {
            "identity_release": project_works_manifest.get(
                "release", "project-works-v5"
            ),
            "aggregation_decision_release": (
                decisions_manifest.get(
                    "release", "aggregation-decisions-v4"
                )
            ),
            "openlibrary_target_release": (
                ol_targets_manifest.get(
                    "release", "openlibrary-analysis-targets-v1"
                )
            ),
            "source_entity_release": (
                source_entities_manifest.get(
                    "release", "source-entities-v2"
                )
            ),
            "scope_release": "not_applied",
        },
        "inputs": {
            str(PROJECT_WORKS.relative_to(ROOT)): (
                sha256_file(PROJECT_WORKS)
            ),
            str(WORK_MAP.relative_to(ROOT)): (
                sha256_file(WORK_MAP)
            ),
            str(DECISIONS.relative_to(ROOT)): (
                sha256_file(DECISIONS)
            ),
            str(MEMBERS.relative_to(ROOT)): (
                sha256_file(MEMBERS)
            ),
            str(OL_TARGETS.relative_to(ROOT)): (
                sha256_file(OL_TARGETS)
            ),
            str(SOURCE_ENTITIES.relative_to(ROOT)): (
                sha256_file(SOURCE_ENTITIES)
            ),
        },
        "counts": {
            "target_rows": len(targets),
            "resolved_w_targets": EXPECTED_PROJECT_WORKS,
            "unresolved_unit_targets": EXPECTED_UNRESOLVED_UNITS,
            "alias_rows": len(aliases),
            "resolved_alias_rows": (
                EXPECTED_RESOLVED_CURRENT_TARGETS
            ),
            "unresolved_alias_rows": (
                EXPECTED_UNRESOLVED_CURRENT_TARGETS
            ),
            "empty_raw_titles": int(
                aliases["alias_value_raw"]
                .str.strip()
                .eq("")
                .sum()
            ),
            "empty_normalized_titles": int(
                aliases["alias_value_norm"].eq("").sum()
            ),
            "corrected_historical_target_rows": (
                corrected_target_rows
            ),
            "works_with_multiple_openlibrary_aliases": (
                works_with_multiple_ol_aliases
            ),
            "max_openlibrary_aliases_per_w": (
                max_ol_aliases_per_w
            ),
            "within_w_normalized_duplicate_groups": (
                within_w_duplicate_norm_groups
            ),
            "within_w_alias_rows_in_normalized_duplicate_groups": (
                within_w_alias_rows_in_duplicate_norm_groups
            ),
            "cross_w_normalized_title_collision_values": (
                cross_w_normalized_title_collision_values
            ),
            "cross_w_normalized_title_collision_w_memberships": (
                cross_w_normalized_title_collision_w_memberships
            ),
        },
        "outputs": {
            "targets_tsv": {
                "artifact": str(
                    OUT_TARGETS_TSV.relative_to(ROOT)
                ),
                "sha256": sha256_file(OUT_TARGETS_TSV),
            },
            "targets_parquet": {
                "artifact": str(
                    OUT_TARGETS_PARQUET.relative_to(ROOT)
                ),
                "sha256": sha256_file(
                    OUT_TARGETS_PARQUET
                ),
            },
            "aliases_tsv": {
                "artifact": str(
                    OUT_ALIASES_TSV.relative_to(ROOT)
                ),
                "sha256": sha256_file(OUT_ALIASES_TSV),
            },
            "aliases_parquet": {
                "artifact": str(
                    OUT_ALIASES_PARQUET.relative_to(ROOT)
                ),
                "sha256": sha256_file(
                    OUT_ALIASES_PARQUET
                ),
            },
        },
        "next_step": (
            "define_and_version_r2_representative_alias_rule"
        ),
    }

    write_atomic_json(manifest, OUT_MANIFEST)

    print("=== OPENALEX ALIAS REGISTRY V4 ===")
    print("targets:", len(targets))
    print("  resolved W:", EXPECTED_PROJECT_WORKS)
    print("  unresolved units:", EXPECTED_UNRESOLVED_UNITS)
    print("aliases:", len(aliases))
    print(
        "  resolved aliases:",
        EXPECTED_RESOLVED_CURRENT_TARGETS,
    )
    print(
        "  unresolved aliases:",
        EXPECTED_UNRESOLVED_CURRENT_TARGETS,
    )
    print(
        "works with >1 OL alias:",
        works_with_multiple_ol_aliases,
    )
    print(
        "max OL aliases per W:",
        max_ol_aliases_per_w,
    )
    print(
        "within-W normalized duplicate groups:",
        within_w_duplicate_norm_groups,
    )
    print(
        "cross-W normalized title collision values:",
        cross_w_normalized_title_collision_values,
    )
    print(
        "corrected historical target rows:",
        corrected_target_rows,
    )
    print("\nOutputs:")
    for p in [
        OUT_TARGETS_TSV,
        OUT_TARGETS_PARQUET,
        OUT_ALIASES_TSV,
        OUT_ALIASES_PARQUET,
        OUT_MANIFEST,
    ]:
        print(p.relative_to(ROOT))
    print(
        "\nOpenAlex alias registry v4 build checks passed."
    )


if __name__ == "__main__":
    main()
