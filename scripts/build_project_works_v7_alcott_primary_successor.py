from pathlib import Path
from collections import Counter
import hashlib
import json
import shutil
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "derived/identity"

W6 = BASE / "project_works_v6.tsv"
M6 = BASE / "work_identity_map_v6.tsv"
MP6 = BASE / "work_identity_map_v6.parquet"

HUMAN = (
    BASE / "openlibrary_r2a1_target_identity_remediation_adjudication_v1"
    / "openlibrary_r2a1_target_identity_remediation_adjudication_v1.tsv"
)
UNITS = (
    BASE / "openlibrary_r2a1_identity_v6_adjudication_input_v1"
    / "publication_unit_adjudication_input_v1.tsv"
)
COVERAGE = (
    BASE / "openlibrary_r2a1_identity_v6_migration_coverage_v1"
    / "edition_migration_coverage_v1.tsv"
)
BRIDGE = (
    BASE / "openlibrary_r2a1_edition_source_bridge_v1"
    / "edition_source_bridge_v1.tsv"
)
SUSPENSIONS = BASE / "project_work_identity_suspensions_v1.tsv"
ENTITIES = BASE / "source_entities_v3.tsv"

POLICY = ROOT / "docs/PROJECT_WORKS_SOURCE_LIGHT_POLICY_V1.md"

W7 = BASE / "project_works_v7.tsv"
WP7 = BASE / "project_works_v7.parquet"
M7 = BASE / "work_identity_map_v7.tsv"
MP7 = BASE / "work_identity_map_v7.parquet"
REL = BASE / "project_work_edition_evidence_v1.tsv"
LEDGER = BASE / "project_work_primary_restorations_v1.tsv"
MANIFEST = BASE / "project_works_v7_manifest.json"

OUTPUTS = [W7, WP7, M7, MP7, REL, LEDGER, MANIFEST]

WID = "W000014515"
OLID = "OL29984W"
UNIT = "CCV1_0048_G01"
VERSION = "openlibrary_r2a1_primary_successor_inheritance_v1"
CREATED_AT = "2026-10-12"


def read(path):
    return pd.read_csv(
        path, sep="\t", dtype=str, keep_default_na=False
    )


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if any(p.exists() for p in OUTPUTS):
        raise SystemExit("STOP: v7 outputs already exist")

    vm = json.loads(
        (BASE / "project_works_v6_manifest.json").read_text()
    )
    assert sha(W6) == vm["outputs"][W6.name]
    assert sha(M6) == vm["outputs"][M6.name]
    assert sha(MP6) == vm["outputs"][MP6.name]

    works = read(W6)
    mapping = read(M6)
    human = read(HUMAN)
    units = read(UNITS)
    coverage = read(COVERAGE)
    bridge = read(BRIDGE)
    suspensions = read(SUSPENSIONS)
    entities = read(ENTITIES)

    assert POLICY.exists()
    assert len(works) == 32089
    assert len(mapping) == 44888
    assert len(bridge) == len(coverage) == 508

    h = human[human["project_work_id"].eq(WID)]
    u = units[units["candidate_unit_id"].eq(UNIT)]
    s = suspensions[
        suspensions["project_work_id"].eq(WID)
    ]

    assert len(h) == len(u) == len(s) == 1

    h = h.iloc[0]
    u = u.iloc[0]
    s = s.iloc[0]

    assert h["resolution_decision"] == "SPLIT"
    assert h["resolution_confidence"] == "HIGH"
    assert h["current_ol_work_ids"] == OLID
    assert h["resolution_plan"].startswith(
        "Primary successor inherits the current ID:"
    )
    assert "Ednah D. Cheney" in h["resolution_plan"]

    assert u["predecessor_project_work_id"] == WID
    assert u["predecessor_ol_work_id"] == OLID
    assert u["coherence_decision"] == "ONE_PUBLICATION_FAMILY"
    assert u["human_role_hint"] == "PRIMARY_SUCCESSOR_HINT"
    assert u["edition_count"] == "70"

    assert s["suspended_source_entity_id"]
    assert WID not in set(mapping["project_work_id"])

    all_alcott = coverage[
        coverage["project_work_id"].eq(WID)
    ].copy()

    core = all_alcott[
        all_alcott["candidate_unit_id"].eq(UNIT)
    ].copy()

    other = all_alcott[
        ~all_alcott["candidate_unit_id"].eq(UNIT)
    ].copy()

    assert len(all_alcott) == 79
    assert len(core) == 70
    assert len(other) == 9

    assert core["final_provenance"].value_counts().to_dict() == {
        "llm_v1_unreviewed": 68,
        "human_direct_adjudication": 2,
    }

    assert other["migration_bucket"].value_counts().to_dict() == {
        "DETACH_PENDING_IDENTITY": 7,
        "ROUTING_UNRESOLVED": 2,
    }

    assert set(core["edition_key"]) == set(
        u["edition_keys"].split("|")
    )

    # Link Edition source entities to the conceptual W
    # as provenance-qualified relational evidence.
    source_rows = bridge[
        bridge["predecessor_project_work_id"].eq(WID)
    ][
        ["edition_key", "edition_entity_id",
         "predecessor_work_entity_id"]
    ]

    core = core.merge(
        source_rows,
        on="edition_key",
        how="left",
        validate="one_to_one",
    )

    assert core["edition_entity_id"].notna().all()
    assert set(core["predecessor_work_entity_id"]) == {
        s["suspended_source_entity_id"]
    }

    entity_map = entities.set_index("entity_id")
    for r in core.to_dict("records"):
        eid = r["edition_entity_id"]
        assert entity_map.loc[eid, "source"] == "openlibrary"
        assert entity_map.loc[
            eid, "source_namespace"
        ] == "edition"
        assert entity_map.loc[eid, "source_id"] == r["edition_key"]

    relation_rows = []

    for r in core.to_dict("records"):
        provenance = r["final_provenance"]
        review = (
            "HUMAN_CONFIRMED_COMPONENT_ROUTING"
            if provenance == "human_direct_adjudication"
            else "LLM_ROUTING_UNREVIEWED"
        )

        relation_rows.append({
            "project_work_id": WID,
            "candidate_unit_id": UNIT,
            "edition_entity_id": r["edition_entity_id"],
            "edition_key": r["edition_key"],
            "proposed_relation": "EDITION_OF",
            "relation_assertion_status":
                "PROVISIONAL_NOT_FORMALLY_ADJUDICATED",
            "routing_review_status": review,
            "routing_provenance": provenance,
            "evidence_edition_title": r["edition_title"],
            "evidence_edition_subtitle": r["edition_subtitle"],
            "decision_version": VERSION,
        })

    relations = pd.DataFrame(relation_rows).sort_values(
        "edition_key"
    )

    assert len(relations) == 70
    assert relations["edition_entity_id"].is_unique
    assert relations["edition_key"].is_unique

    # The conceptual W inherits its ID on the authority
    # of the frozen human resolution plan.
    restored = works.copy()
    mask = restored["project_work_id"].eq(WID)

    assert mask.sum() == 1
    assert restored.loc[mask, "status"].iloc[0] == (
        "identity_suspended"
    )

    restored.loc[mask, "status"] = "active"

    # The previous source Work anchor was overaggregated.
    # Historical evidence remains in previous releases.
    restored.loc[
        mask, "origin_unit_anchor_entity_id"
    ] = ""
    restored.loc[
        mask, "aggregation_decision_version"
    ] = VERSION

    assert len(restored) == 32089
    assert restored["project_work_id"].is_unique

    assert restored["status"].value_counts().to_dict() == {
        "active": 32066,
        "identity_suspended": 16,
        "superseded": 7,
    }

    # This is the single documented source-light
    # active W. The 16 other suspended Ws remain excluded.
    active = set(
        restored.loc[
            restored["status"].eq("active"),
            "project_work_id",
        ]
    )
    mapped = set(mapping["project_work_id"])

    assert active - mapped == {WID}
    assert mapped - active == set()

    old_remaining = works[
        ~works["project_work_id"].eq(WID)
    ].reset_index(drop=True)
    new_remaining = restored[
        ~restored["project_work_id"].eq(WID)
    ].reset_index(drop=True)

    pd.testing.assert_frame_equal(
        old_remaining, new_remaining
    )

    ledger = pd.DataFrame([{
        "project_work_id": WID,
        "former_ol_work_id": OLID,
        "prior_suspended_entity_id":
            s["suspended_source_entity_id"],
        "primary_candidate_unit_id": UNIT,
        "action": "RESTORE_EXISTING_ID_AS_PRIMARY_SUCCESSOR",
        "authority": "FROZEN_HUMAN_SPLIT_RESOLUTION_PLAN",
        "supporting_edition_count": 70,
        "human_routed_editions": 2,
        "llm_only_routed_editions": 68,
        "unassigned_other_editions": 9,
        "source_work_same_membership": "NOT_RESTORED",
        "corpus_scope": "NOT_ADJUDICATED",
        "decision_version": VERSION,
        "created_at": CREATED_AT,
    }])

    restored.to_csv(
        W7, sep="\t", index=False, lineterminator="\n"
    )
    restored.to_parquet(WP7, index=False)

    # Keep the source-work identity map byte-for-byte
    # unchanged. Edition relations live separately.
    shutil.copyfile(M6, M7)
    shutil.copyfile(MP6, MP7)

    relations.to_csv(
        REL, sep="\t", index=False, lineterminator="\n"
    )
    ledger.to_csv(
        LEDGER, sep="\t", index=False, lineterminator="\n"
    )

    manifest = {
        "release": "project-works-v7",
        "release_type":
            "primary_successor_identity_restoration",
        "decision_version": VERSION,
        "inputs": {
            str(p.relative_to(ROOT)): sha(p)
            for p in [
                W6, M6, MP6, HUMAN, UNITS,
                COVERAGE, BRIDGE, SUSPENSIONS,
                ENTITIES, POLICY,
            ]
        },
        "outputs": {
            p.name: sha(p)
            for p in [W7, WP7, M7, MP7, REL, LEDGER]
        },
        "counts": {
            "total_works": 32089,
            "active_works": 32066,
            "identity_suspended_works": 16,
            "superseded_works": 7,
            "source_light_active_works": 1,
            "work_identity_map_rows": 44888,
            "provisional_edition_relations": 70,
            "human_routed_edition_evidence": 2,
            "llm_only_edition_evidence": 68,
            "new_w_ids": 0,
            "new_same_assertions": 0,
            "new_scope_decisions": 0,
        },
        "source_light_exceptions": [WID],
        "semantics": {
            "conceptual_work_basis":
                "Previously frozen human primary-successor "
                "inheritance decision",
            "edition_relations":
                "Provenance-qualified provisional EDITION_OF "
                "evidence, not automatic SAME identity",
            "original_ol_work":
                "Retained as overaggregated source record; "
                "no SAME membership restored",
            "downstream":
                "Do not automatically switch analysis views. "
                "Source-light active Ws require explicit support.",
        },
    }

    MANIFEST.write_text(
        json.dumps(
            manifest, ensure_ascii=False,
            indent=2, sort_keys=True
        ) + "\n",
        encoding="utf-8",
    )

    print("=== PROJECT WORKS V7: ALCOTT RESTORATION ===")
    print("restored W:", WID)
    print("active W:", len(active))
    print("identity suspended:", 16)
    print("source-light active W:", 1)
    print("work identity map:", len(mapping), "(unchanged)")
    print("provisional Edition relations:", len(relations))
    print("human-routed evidence:", 2)
    print("LLM-only evidence:", 68)
    print("new W IDs:", 0)
    print("new SAME assertions:", 0)
    print("new scope decisions:", 0)
    print("QC: PASSED")


if __name__ == "__main__":
    main()
