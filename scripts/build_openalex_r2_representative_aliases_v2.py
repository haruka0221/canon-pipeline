from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

PROJECT_WORKS = ROOT / "derived/identity/project_works_v5.parquet"
DECISIONS = ROOT / "derived/identity/aggregation_decisions_v4.parquet"

REGISTRY_DIR = ROOT / "derived/openalex_production/registry_v4"
TARGETS = REGISTRY_DIR / "openalex_targets_v4.parquet"
ALIASES = REGISTRY_DIR / "openalex_aliases_v4.parquet"
ALIAS_MANIFEST = REGISTRY_DIR / "openalex_alias_registry_v4_manifest.json"

OUT_TSV = REGISTRY_DIR / "openalex_r2_representative_aliases_v2.tsv"
OUT_PARQUET = REGISTRY_DIR / "openalex_r2_representative_aliases_v2.parquet"
OUT_MANIFEST = REGISTRY_DIR / "openalex_r2_representative_aliases_v2_manifest.json"

RELEASE = "openalex-r2-representative-aliases-v2"
RULE = "deterministic_identity_representative_alias"
RULE_VERSION = "v2"
CREATED_AT = "2026-10-02"

EXPECTED_RESOLVED_W = 32082
EXPECTED_UNRESOLVED_UNITS = 761
EXPECTED_ROWS = EXPECTED_RESOLVED_W + EXPECTED_UNRESOLVED_UNITS


def require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def main() -> None:
    for path in [
        PROJECT_WORKS,
        DECISIONS,
        TARGETS,
        ALIASES,
        ALIAS_MANIFEST,
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

    merge_successors = works[
        works["origin_unit_anchor_entity_id"].eq("")
    ]["project_work_id"].tolist()

    if set(merge_successors) != {
        "W000032087",
        "W000032088",
        "W000032089",
    }:
        raise RuntimeError(
            "Unexpected active project works without origin-unit anchors: "
            f"{merge_successors}"
        )

    decisions = pd.read_parquet(DECISIONS).fillna("")
    targets = pd.read_parquet(TARGETS).fillna("")
    aliases = pd.read_parquet(ALIASES).fillna("")
    alias_manifest = json.loads(
        ALIAS_MANIFEST.read_text(encoding="utf-8")
    )

    if alias_manifest.get("release") != "openalex-alias-registry-v4":
        raise RuntimeError(
            "Unexpected alias-registry release: "
            f"{alias_manifest.get('release')}"
        )

    if len(works) != EXPECTED_RESOLVED_W:
        raise RuntimeError(
            f"Expected {EXPECTED_RESOLVED_W} project works; found {len(works)}"
        )

    pending = decisions[
        decisions["aggregation_decision"].eq("MANUAL_REVIEW_REQUIRED")
    ].copy()

    if len(pending) != EXPECTED_UNRESOLVED_UNITS:
        raise RuntimeError(
            f"Expected {EXPECTED_UNRESOLVED_UNITS} unresolved units; "
            f"found {len(pending)}"
        )

    if len(targets) != EXPECTED_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_ROWS} target rows; found {len(targets)}"
        )

    if not aliases["alias_id"].is_unique:
        raise RuntimeError("Alias registry alias_id is not unique")

    alias_by_entity = aliases.set_index(
        "alias_project_source_entity_id"
    )

    if not alias_by_entity.index.is_unique:
        raise RuntimeError(
            "Alias registry must have one OL-title alias per current entity "
            "for representative selection v1"
        )

    rows = []

    # ---------------------------------------------------------
    # Resolved W lane.
    #
    # Ordinary active W:
    #   representative = historical origin-unit anchor alias.
    #
    # Merge-successor W:
    #   origin_unit_anchor_entity_id is intentionally empty;
    #   select the lexicographically smallest current Open
    #   Library source-entity alias belonging to that W.
    #
    # This is deterministic identity structure, not a
    # canonical-title or best-title judgment.
    # ---------------------------------------------------------

    for row in works.sort_values(
        "project_work_id", kind="stable"
    ).to_dict("records"):

        project_work_id = str(
            row["project_work_id"]
        )

        origin_anchor = str(
            row["origin_unit_anchor_entity_id"]
        )

        if origin_anchor:
            representative_entity_id = (
                origin_anchor
            )

            representative_basis = (
                "project_works_v5."
                "origin_unit_anchor_entity_id"
            )

        else:
            candidates = aliases[
                aliases["target_lane"].eq(
                    "resolved_w"
                )
                & aliases["project_work_id"].eq(
                    project_work_id
                )
            ].copy()

            if len(candidates) < 2:
                raise RuntimeError(
                    "Merge-successor W expected >=2 "
                    "current aliases: "
                    f"{project_work_id} "
                    f"found={len(candidates)}"
                )

            representative_entity_id = min(
                candidates[
                    "alias_project_source_entity_id"
                ].astype(str)
            )

            representative_basis = (
                "merge_successor_"
                "lexicographically_smallest_"
                "current_source_entity"
            )

        if (
            representative_entity_id
            not in alias_by_entity.index
        ):
            raise RuntimeError(
                "Resolved representative source entity "
                "missing from alias registry: "
                f"{project_work_id} "
                f"{representative_entity_id}"
            )

        a = alias_by_entity.loc[
            representative_entity_id
        ]

        if str(a["target_lane"]) != "resolved_w":
            raise RuntimeError(
                "Resolved representative points to "
                "non-resolved alias: "
                f"{project_work_id} "
                f"{representative_entity_id}"
            )

        if (
            str(a["project_work_id"])
            != project_work_id
        ):
            raise RuntimeError(
                "Resolved representative alias belongs "
                "to different W: "
                f"{project_work_id} "
                f"{representative_entity_id} "
                f"{a['project_work_id']}"
            )

        rows.append(
            {
                "target_lane":
                    "resolved_w",

                "project_work_id":
                    project_work_id,

                "unresolved_unit_anchor_entity_id":
                    "",

                "representative_alias_id":
                    str(a["alias_id"]),

                "representative_alias_project_source_entity_id":
                    representative_entity_id,

                "representative_alias_source_record_id":
                    str(
                        a[
                            "alias_source_record_id"
                        ]
                    ),

                "representative_title_raw":
                    str(
                        a[
                            "alias_value_raw"
                        ]
                    ),

                "representative_title_norm":
                    str(
                        a[
                            "alias_value_norm"
                        ]
                    ),

                "representative_alias_role":
                    str(a["alias_role"]),

                "representative_alias_quality":
                    str(
                        a[
                            "alias_quality"
                        ]
                    ),

                "representative_selection_rule":
                    RULE,

                "representative_selection_version":
                    RULE_VERSION,

                "representative_selection_basis":
                    representative_basis,

                "representative_for_r2":
                    True,

                "created_at":
                    CREATED_AT,
            }
        )

    # ---------------------------------------------------------
    # Unresolved lane:
    # representative alias = unresolved unit anchor
    # ---------------------------------------------------------

    for row in pending.sort_values(
        "unit_anchor_entity_id", kind="stable"
    ).to_dict("records"):
        anchor = str(row["unit_anchor_entity_id"])

        if anchor not in alias_by_entity.index:
            raise RuntimeError(
                f"Unresolved unit anchor missing from alias registry: {anchor}"
            )

        a = alias_by_entity.loc[anchor]

        if str(a["target_lane"]) != "unresolved_source":
            raise RuntimeError(
                f"Unresolved anchor points to non-unresolved alias: {anchor}"
            )

        if str(a["unresolved_unit_anchor_entity_id"]) != anchor:
            raise RuntimeError(
                f"Unresolved representative alias belongs to different unit: "
                f"{anchor} {a['unresolved_unit_anchor_entity_id']}"
            )

        rows.append(
            {
                "target_lane": "unresolved_source",
                "project_work_id": "",
                "unresolved_unit_anchor_entity_id": anchor,
                "representative_alias_id": str(a["alias_id"]),
                "representative_alias_project_source_entity_id": anchor,
                "representative_alias_source_record_id": str(
                    a["alias_source_record_id"]
                ),
                "representative_title_raw": str(a["alias_value_raw"]),
                "representative_title_norm": str(a["alias_value_norm"]),
                "representative_alias_role": str(a["alias_role"]),
                "representative_alias_quality": str(a["alias_quality"]),
                "representative_selection_rule": RULE,
                "representative_selection_version": RULE_VERSION,
                "representative_selection_basis": (
                    "aggregation_decisions_v4.unit_anchor_entity_id"
                ),
                "representative_for_r2": True,
                "created_at": CREATED_AT,
            }
        )

    out = pd.DataFrame(rows)

    if len(out) != EXPECTED_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_ROWS} representative rows; found {len(out)}"
        )

    lane_counts = out["target_lane"].value_counts().to_dict()
    expected_lane_counts = {
        "resolved_w": EXPECTED_RESOLVED_W,
        "unresolved_source": EXPECTED_UNRESOLVED_UNITS,
    }
    if lane_counts != expected_lane_counts:
        raise RuntimeError(
            f"Unexpected representative lane counts: {lane_counts}"
        )

    if not out["representative_alias_id"].is_unique:
        raise RuntimeError(
            "Representative alias is reused across target units"
        )

    if not out["representative_for_r2"].all():
        raise RuntimeError(
            "Representative output contains non-R2 row"
        )

    if set(out["representative_alias_quality"]) != {"usable"}:
        raise RuntimeError(
            "R2 representative selection contains non-usable alias"
        )

    # Exact one-per-target checks.
    if (
        out[out["target_lane"].eq("resolved_w")]
        ["project_work_id"]
        .nunique()
        != EXPECTED_RESOLVED_W
    ):
        raise RuntimeError(
            "Resolved representative selection is not one-per-W"
        )

    if (
        out[out["target_lane"].eq("unresolved_source")]
        ["unresolved_unit_anchor_entity_id"]
        .nunique()
        != EXPECTED_UNRESOLVED_UNITS
    ):
        raise RuntimeError(
            "Unresolved representative selection is not one-per-unit"
        )

    write_atomic_tsv(out, OUT_TSV)
    write_atomic_parquet(out, OUT_PARQUET)

    manifest = {
        "release": RELEASE,
        "created_at": CREATED_AT,
        "representative_selection_rule": RULE,
        "representative_selection_version": RULE_VERSION,
        "purpose": (
            "Freeze a deterministic R2 representative retrieval-title "
            "selection without treating the selected title as the canonical "
            "title of the literary work."
        ),
        "semantics": {
            "resolved_w_rule": (
                "For an ordinary active project_work_id in project_works_v5, "
                "select the Open Library alias identified by "
                "origin_unit_anchor_entity_id. For a merge-successor W whose "
                "origin_unit_anchor_entity_id is intentionally empty, select "
                "the lexicographically smallest current Open Library source "
                "entity assigned to that successor."
            ),
            "unresolved_rule": (
                "For each MANUAL_REVIEW_REQUIRED unresolved aggregation unit, "
                "select the Open Library title alias whose source entity equals "
                "unit_anchor_entity_id. This supports parallel retrieval but "
                "does not create or imply a project_work_id."
            ),
            "why_anchor_based": (
                "R2 is a stable identity-structural baseline, not an optimized "
                "best-title heuristic. Retrieval improvement from additional "
                "aliases is evaluated separately through R3."
            ),
            "not_canonical_title": True,
            "scope_release": "not_applied",
        },
        "source_releases": {
            "alias_registry": alias_manifest["release"],
            "identity_release": "project-works-v5",
            "aggregation_decision_release": "aggregation-decisions-v4",
        },
        "inputs": {
            str(PROJECT_WORKS.relative_to(ROOT)): sha256_file(PROJECT_WORKS),
            str(DECISIONS.relative_to(ROOT)): sha256_file(DECISIONS),
            str(TARGETS.relative_to(ROOT)): sha256_file(TARGETS),
            str(ALIASES.relative_to(ROOT)): sha256_file(ALIASES),
            str(ALIAS_MANIFEST.relative_to(ROOT)): sha256_file(ALIAS_MANIFEST),
        },
        "counts": {
            "rows": len(out),
            "resolved_w": EXPECTED_RESOLVED_W,
            "unresolved_units": EXPECTED_UNRESOLVED_UNITS,
            "unique_representative_aliases": int(
                out["representative_alias_id"].nunique()
            ),
        },
        "outputs": {
            "tsv": {
                "artifact": str(OUT_TSV.relative_to(ROOT)),
                "sha256": sha256_file(OUT_TSV),
            },
            "parquet": {
                "artifact": str(OUT_PARQUET.relative_to(ROOT)),
                "sha256": sha256_file(OUT_PARQUET),
            },
        },
        "next_step": (
            "build_logical_query_registry_with_stable_query_id"
        ),
    }

    write_atomic_json(manifest, OUT_MANIFEST)

    print("=== OPENALEX R2 REPRESENTATIVE ALIASES V2 ===")
    print("rows:", len(out))
    print("resolved W:", EXPECTED_RESOLVED_W)
    print("unresolved units:", EXPECTED_UNRESOLVED_UNITS)
    print("rule:", RULE, RULE_VERSION)
    print("\nOutputs:")
    print(OUT_TSV.relative_to(ROOT))
    print(OUT_PARQUET.relative_to(ROOT))
    print(OUT_MANIFEST.relative_to(ROOT))
    print(
        "\nOpenAlex R2 representative-alias selection v2 checks passed."
    )


if __name__ == "__main__":
    main()
