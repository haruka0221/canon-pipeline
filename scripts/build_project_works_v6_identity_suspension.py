from pathlib import Path
import hashlib
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "derived/identity"

WORKS = BASE / "project_works_v5.tsv"
MAP = BASE / "work_identity_map_v5.tsv"
V5_MANIFEST = BASE / "project_works_v5_manifest.json"

HUMAN = (
    BASE / "openlibrary_r2a1_target_identity_remediation_adjudication_v1"
    / "openlibrary_r2a1_target_identity_remediation_adjudication_v1.tsv"
)
HUMAN_MANIFEST = HUMAN.parent / (
    "openlibrary_r2a1_target_identity_remediation_adjudication_v1_manifest.json"
)

BRIDGE = (
    BASE / "openlibrary_r2a1_edition_source_bridge_v1"
    / "edition_source_bridge_v1.tsv"
)
BRIDGE_MANIFEST = BRIDGE.parent / "edition_source_bridge_manifest_v1.json"

OUT_WORKS = BASE / "project_works_v6.tsv"
OUT_WORKS_PQ = BASE / "project_works_v6.parquet"
OUT_MAP = BASE / "work_identity_map_v6.tsv"
OUT_MAP_PQ = BASE / "work_identity_map_v6.parquet"
OUT_LEDGER = BASE / "project_work_identity_suspensions_v1.tsv"
OUT_MANIFEST = BASE / "project_works_v6_manifest.json"

OUTPUTS = [
    OUT_WORKS, OUT_WORKS_PQ,
    OUT_MAP, OUT_MAP_PQ,
    OUT_LEDGER, OUT_MANIFEST,
]

VERSION = "openlibrary_r2a1_split_identity_suspension_v1"
CREATED_AT = "2026-10-12"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return pd.read_csv(
        p, sep="\t", dtype=str, keep_default_na=False
    )


def verify():
    v5 = json.loads(V5_MANIFEST.read_text())
    hm = json.loads(HUMAN_MANIFEST.read_text())
    bm = json.loads(BRIDGE_MANIFEST.read_text())

    assert sha(WORKS) == v5["outputs"][WORKS.name]
    assert sha(MAP) == v5["outputs"][MAP.name]
    assert sha(HUMAN) == hm["outputs"][str(HUMAN.relative_to(ROOT))]
    assert sha(BRIDGE) == bm["outputs"][BRIDGE.name]


def main():
    if any(p.exists() for p in OUTPUTS):
        raise SystemExit("STOP: v6 outputs already exist")

    verify()

    works = read(WORKS)
    mapping = read(MAP)
    human = read(HUMAN)
    bridge = read(BRIDGE)

    assert len(works) == 32089
    assert len(mapping) == 44905
    assert len(bridge) == 508

    assert works["project_work_id"].is_unique
    assert mapping["source_entity_id"].is_unique
    assert bridge["edition_key"].is_unique

    # Only previously accepted human SPLIT decisions.
    split = human[
        human["resolution_decision"].eq("SPLIT")
    ].copy()

    assert len(split) == 17
    assert split["project_work_id"].is_unique

    affected_w = set(split["project_work_id"])
    assert affected_w == set(
        bridge["predecessor_project_work_id"]
    )

    affected = mapping[
        mapping["project_work_id"].isin(affected_w)
    ].copy()

    assert len(affected) == 17
    assert affected["project_work_id"].is_unique
    assert set(affected["project_work_id"]) == affected_w
    assert set(affected["membership_role"]) == {
        "current_analysis_target"
    }

    # Each old W currently has exactly one OL Work member.
    by_w = affected.set_index("project_work_id")
    human_by_w = split.set_index("project_work_id")

    bridge_source = (
        bridge.groupby("predecessor_project_work_id")
        ["predecessor_work_entity_id"]
        .agg(lambda x: set(x))
    )

    assert set(bridge_source.index) == affected_w

    ledger_rows = []

    for wid in sorted(affected_w):
        old = by_w.loc[wid]
        h = human_by_w.loc[wid]

        assert bridge_source[wid] == {
            old["source_entity_id"]
        }

        assert h["resolution_decision"] == "SPLIT"

        ledger_rows.append({
            "project_work_id": wid,
            "suspended_source_entity_id":
                old["source_entity_id"],
            "previous_membership_role":
                old["membership_role"],
            "previous_membership_basis":
                old["membership_basis"],
            "human_resolution_decision": "SPLIT",
            "human_resolution_confidence":
                h["resolution_confidence"],
            "human_resolution_plan":
                h["resolution_plan"],
            "v6_action":
                "SUSPEND_OVERAGGREGATED_SOURCE_MEMBERSHIP",
            "decision_version": VERSION,
            "successor_identity_status":
                "PENDING_ADJUDICATION",
        })

    ledger = pd.DataFrame(ledger_rows)

    # Preserve all W IDs; change only affected statuses.
    new_works = works.copy()

    mask = new_works["project_work_id"].isin(affected_w)

    assert mask.sum() == 17
    assert set(new_works.loc[mask, "status"]) == {"active"}

    new_works.loc[mask, "status"] = "identity_suspended"

    assert len(new_works) == 32089
    assert new_works["project_work_id"].is_unique

    expected_statuses = {
        "active": 32065,
        "superseded": 7,
        "identity_suspended": 17,
    }

    assert new_works["status"].value_counts().to_dict() == (
        expected_statuses
    )

    cols = [x for x in works.columns if x != "status"]

    pd.testing.assert_frame_equal(
        new_works[cols], works[cols]
    )

    # Current-state identity map excludes only the 17
    # invalid source memberships. v5 remains preserved.
    new_map = mapping[
        ~mapping["project_work_id"].isin(affected_w)
    ].copy().reset_index(drop=True)

    assert len(new_map) == 44888
    assert new_map["source_entity_id"].is_unique

    pd.testing.assert_frame_equal(
        new_map,
        mapping[
            ~mapping["project_work_id"].isin(affected_w)
        ].reset_index(drop=True),
    )

    assert not (
        set(new_map["source_entity_id"])
        & set(ledger["suspended_source_entity_id"])
    )

    active = set(
        new_works.loc[
            new_works["status"].eq("active"),
            "project_work_id",
        ]
    )

    assert set(new_map["project_work_id"]) == active

    current = new_map[
        new_map["membership_role"].eq(
            "current_analysis_target"
        )
    ]

    assert len(current) == 32689
    assert set(current["project_work_id"]) == active

    # Historical map can be reconstructed exactly by
    # reinserting the archived rows at their old positions.
    assert set(mapping["source_entity_id"]) == (
        set(new_map["source_entity_id"])
        | set(ledger["suspended_source_entity_id"])
    )

    # No scope decisions and no successor W IDs.
    new_works.to_csv(
        OUT_WORKS, sep="\t", index=False, lineterminator="\n"
    )
    new_works.to_parquet(OUT_WORKS_PQ, index=False)

    new_map.to_csv(
        OUT_MAP, sep="\t", index=False, lineterminator="\n"
    )
    new_map.to_parquet(OUT_MAP_PQ, index=False)

    ledger.to_csv(
        OUT_LEDGER, sep="\t", index=False, lineterminator="\n"
    )

    manifest = {
        "release": "project-works-v6",
        "release_type": "identity_suspension_phase",
        "decision_version": VERSION,
        "created_at": CREATED_AT,
        "inputs": {
            str(p.relative_to(ROOT)): sha(p)
            for p in [
                WORKS, MAP, V5_MANIFEST,
                HUMAN, HUMAN_MANIFEST,
                BRIDGE, BRIDGE_MANIFEST,
            ]
        },
        "outputs": {
            p.name: sha(p)
            for p in [
                OUT_WORKS, OUT_WORKS_PQ,
                OUT_MAP, OUT_MAP_PQ,
                OUT_LEDGER,
            ]
        },
        "counts": {
            "total_project_works": 32089,
            "active_project_works": 32065,
            "superseded_project_works": 7,
            "identity_suspended_works": 17,
            "current_membership_rows": 44888,
            "suspended_memberships": 17,
            "new_project_works": 0,
            "new_identity_assertions": 0,
            "scope_decisions": 0,
        },
        "semantics": {
            "identity_suspended":
                "Known overaggregated source identity; "
                "successor conceptual identity pending.",
            "source_history":
                "All v5 records and source entities are retained.",
            "primary_successor_hints":
                "Preserved in frozen review evidence; "
                "no automatic W inheritance.",
            "analysis_warning":
                "This is an interim identity release. "
                "The 17 suspended historical targets "
                "require explicit handling in downstream views.",
        },
    }

    OUT_MANIFEST.write_text(
        json.dumps(
            manifest, ensure_ascii=False,
            indent=2, sort_keys=True
        ) + "\n",
        encoding="utf-8",
    )

    print("=== PROJECT WORKS V6: IDENTITY SUSPENSION ===")
    print("total W:", len(new_works))
    print("active W:", len(active))
    print("identity suspended:", len(affected_w))
    print("current membership rows:", len(new_map))
    print("archived membership rows:", len(ledger))
    print("new W:", 0)
    print("scope decisions:", 0)
    print("QC: PASSED")


if __name__ == "__main__":
    main()
