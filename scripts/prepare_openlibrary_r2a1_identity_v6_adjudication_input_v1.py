from pathlib import Path
import hashlib
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "derived/identity"

PROJECTS = (
    BASE / "openlibrary_r2a1_split_edition_routing_input_v1"
    / "openlibrary_r2a1_split_edition_routing_projects_v1.tsv"
)
REGISTRY = (
    BASE / "openlibrary_r2a1_split_component_registry_v2"
    / "openlibrary_r2a1_split_component_registry_v2.tsv"
)
UNITS = (
    BASE / "openlibrary_r2a1_identity_v6_planning_input_v1"
    / "publication_unit_candidates_v1.tsv"
)
CANDIDATES = (
    BASE / "openlibrary_r2a1_identity_v6_existing_w_candidates_v1"
    / "candidate_existing_w_summary_v1.tsv"
)
COVERAGE = (
    BASE / "openlibrary_r2a1_identity_v6_migration_coverage_v1"
    / "edition_migration_coverage_v1.tsv"
)
WORKS = BASE / "project_works_v5.tsv"

OUT = BASE / "openlibrary_r2a1_identity_v6_adjudication_input_v1"

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read(p):
    return pd.read_csv(
        p, sep="\t", dtype=str, keep_default_na=False
    )

def check_manifest(manifest_path, file_path, key=None):
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = m["outputs"][key or file_path.name]
    assert sha(file_path) == expected, file_path

def main():
    if OUT.exists():
        raise SystemExit("STOP: output exists")

    check_manifest(
        PROJECTS.parent /
        "openlibrary_r2a1_split_edition_routing_input_v1_audit.json",
        PROJECTS,
    )
    check_manifest(
        UNITS.parent / "planning_input_manifest_v1.json",
        UNITS,
    )
    check_manifest(
        CANDIDATES.parent / "candidate_match_manifest_v1.json",
        CANDIDATES,
    )
    check_manifest(
        COVERAGE.parent / "migration_coverage_manifest_v1.json",
        COVERAGE,
    )
    check_manifest(
        BASE / "project_works_v5_manifest.json",
        WORKS,
    )

    projects = read(PROJECTS)
    registry = read(REGISTRY)
    units = read(UNITS)
    candidates = read(CANDIDATES)
    coverage = read(COVERAGE)
    works = read(WORKS)

    assert len(projects) == 17
    assert len(units) == 76
    assert len(candidates) == 76
    assert len(coverage) == 508
    assert registry["component_id"].is_unique
    assert units["candidate_unit_id"].is_unique
    assert candidates["candidate_unit_id"].is_unique

    primary = registry[
        registry["human_role_hint"].eq("PRIMARY_SUCCESSOR_HINT")
    ]
    assert len(primary) == 3
    assert primary["project_work_id"].is_unique

    primary_map = dict(zip(
        primary["project_work_id"],
        primary["component_id"],
    ))

    assert set(primary_map) == {
        "W000014515", "W000003030", "W000002404"
    }

    # --------------------------------------------------
    # A. Predecessor-level adjudication input
    # --------------------------------------------------

    bucket_counts = (
        coverage.groupby(["project_work_id", "migration_bucket"])
        .size()
        .unstack(fill_value=0)
    )

    work_status = works.set_index("project_work_id")["status"]

    predecessor_rows = []

    for p in projects.to_dict("records"):
        wid = p["project_work_id"]

        assert work_status[wid] == "active"

        hint = primary_map.get(wid, "")
        group_ids = sorted(
            units.loc[
                units["component_id"].eq(hint),
                "candidate_unit_id",
            ].tolist()
        ) if hint else []

        predecessor_rows.append({
            "predecessor_project_work_id": wid,
            "predecessor_ol_work_id": p["current_ol_work_id"],
            "target_title": p["r2_target_title"],
            "target_author": p["r2_target_author"],
            "human_resolution_decision": "SPLIT",
            "human_resolution_confidence":
                p["resolution_confidence"],
            "human_resolution_plan": p["resolution_plan"],
            "human_resolution_note": p["resolution_note"],
            "primary_successor_hint_component_id": hint,
            "primary_hint_publication_units":
                "|".join(group_ids),
            "edition_count": int(
                (coverage["project_work_id"] == wid).sum()
            ),
            "publication_unit_count": int(
                (units["predecessor_project_work_id"] == wid).sum()
            ),
            "v6_predecessor_action": "NOT_ADJUDICATED",
            "v6_identity_evidence_status": "PENDING_REVIEW",
            "review_note": "",
        })

    predecessors = pd.DataFrame(predecessor_rows).sort_values(
        "predecessor_project_work_id"
    )

    assert len(predecessors) == 17
    assert predecessors["edition_count"].sum() == 508

    # --------------------------------------------------
    # B. Publication-unit-level adjudication input
    # --------------------------------------------------

    unit_table = units.merge(
        candidates[
            [
                "candidate_unit_id",
                "same_author_existing_W_count",
                "same_author_existing_Ws",
            ]
        ],
        on="candidate_unit_id",
        validate="one_to_one",
    )

    unit_table = unit_table.merge(
        registry[
            [
                "component_id",
                "human_role_hint",
                "component_definition",
            ]
        ],
        on="component_id",
        validate="many_to_one",
    )

    unit_table["v6_conceptual_work_relation"] = "NOT_ADJUDICATED"
    unit_table["v6_existing_W_decision"] = "NOT_ADJUDICATED"
    unit_table["v6_new_W_decision"] = "NOT_ADJUDICATED"
    unit_table["v6_review_note"] = ""

    unit_table = unit_table.sort_values(
        [
            "predecessor_project_work_id",
            "component_id",
            "candidate_unit_id",
        ]
    )

    assert len(unit_table) == 76
    assert unit_table["edition_count"].astype(int).sum() == 280

    # Same-author title matches are leads, not SAME assertions.
    assert (
        unit_table["same_author_existing_W_count"]
        .astype(int).gt(0).sum()
    ) == 1

    assert (
        unit_table.loc[
            unit_table["same_author_existing_W_count"].eq("1"),
            "same_author_existing_Ws",
        ].tolist()
        == ["W000030610"]
    )

    # No review decisions have been created.
    assert set(predecessors["v6_predecessor_action"]) == {
        "NOT_ADJUDICATED"
    }
    assert set(unit_table["v6_conceptual_work_relation"]) == {
        "NOT_ADJUDICATED"
    }

    OUT.mkdir(parents=True)

    pp = OUT / "predecessor_adjudication_input_v1.tsv"
    up = OUT / "publication_unit_adjudication_input_v1.tsv"

    predecessors.to_csv(
        pp, sep="\t", index=False, lineterminator="\n"
    )
    unit_table.to_csv(
        up, sep="\t", index=False, lineterminator="\n"
    )

    manifest = {
        "release": "openlibrary-r2a1-identity-v6-adjudication-input-v1",
        "status": "review_input_only",
        "inputs": {
            str(p.relative_to(ROOT)): sha(p)
            for p in [
                PROJECTS, REGISTRY, UNITS,
                CANDIDATES, COVERAGE, WORKS,
            ]
        },
        "outputs": {
            pp.name: sha(pp),
            up.name: sha(up),
        },
        "counts": {
            "predecessors": 17,
            "publication_units": 76,
            "grouped_editions": 280,
            "total_repair_editions": 508,
            "primary_successor_hints": 3,
            "same_author_exact_title_leads": 1,
        },
        "new_identity_decisions": 0,
        "new_project_works": 0,
    }

    (OUT / "adjudication_input_manifest_v1.json").write_text(
        json.dumps(
            manifest, indent=2, ensure_ascii=False, sort_keys=True
        ) + "\n",
        encoding="utf-8",
    )

    print("=== IDENTITY V6 ADJUDICATION INPUT ===")
    print("predecessors:", len(predecessors))
    print("publication units:", len(unit_table))
    print("primary successor hints:", len(primary))
    print("same-author existing W leads:", 1)
    print("new identity decisions:", 0)
    print("new project works:", 0)
    print("output:", OUT)
    print("QC: PASSED")

if __name__ == "__main__":
    main()
