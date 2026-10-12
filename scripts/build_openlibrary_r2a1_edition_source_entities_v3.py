from pathlib import Path
import hashlib
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "derived/identity"

V2 = BASE / "source_entities_v2.tsv"
V2_MANIFEST = BASE / "source_entities_v2_manifest.json"

DIAG_DIR = BASE / "openlibrary_r2a1_target_identity_diagnostic_v1"
DIAG = DIAG_DIR / "openlibrary_r2a1_target_identity_current_api_editions_v1.tsv"
DIAG_MANIFEST = DIAG_DIR / "openlibrary_r2a1_target_identity_diagnostic_v1_manifest.json"

COV_DIR = BASE / "openlibrary_r2a1_identity_v6_migration_coverage_v1"
COV = COV_DIR / "edition_migration_coverage_v1.tsv"
COV_MANIFEST = COV_DIR / "migration_coverage_manifest_v1.json"

WORK_MAP = BASE / "work_identity_map_v5.tsv"

OUT_TSV = BASE / "source_entities_v3.tsv"
OUT_PARQUET = BASE / "source_entities_v3.parquet"
OUT_MANIFEST = BASE / "source_entities_v3_manifest.json"

BRIDGE_DIR = BASE / "openlibrary_r2a1_edition_source_bridge_v1"
BRIDGE = BRIDGE_DIR / "edition_source_bridge_v1.tsv"
BRIDGE_MANIFEST = BRIDGE_DIR / "edition_source_bridge_manifest_v1.json"

CREATED_AT = "2026-10-12"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(path):
    return pd.read_csv(
        path, sep="\t", dtype=str, keep_default_na=False
    )

def dump(path, obj):
    path.write_text(
        json.dumps(
            obj, indent=2, ensure_ascii=False, sort_keys=True
        ) + "\n",
        encoding="utf-8",
    )

def main():
    outputs = [OUT_TSV, OUT_PARQUET, OUT_MANIFEST, BRIDGE_DIR]
    if any(p.exists() for p in outputs):
        raise SystemExit("STOP: some outputs already exist")

    vm = json.loads(V2_MANIFEST.read_text())
    dm = json.loads(DIAG_MANIFEST.read_text())
    cm = json.loads(COV_MANIFEST.read_text())

    assert sha(V2) == vm["outputs"]["tsv_sha256"]
    assert sha(DIAG) == dm["outputs"][str(DIAG.relative_to(ROOT))]
    assert sha(COV) == cm["outputs"][COV.name]

    previous = load(V2)
    diagnostic = load(DIAG)
    coverage = load(COV)
    mapping = load(WORK_MAP)

    assert len(previous) == 48655
    assert len(diagnostic) == 650
    assert len(coverage) == 508
    assert coverage["edition_key"].is_unique
    assert previous["entity_id"].is_unique
    assert mapping["source_entity_id"].is_unique

    expected_columns = [
        "entity_id",
        "source",
        "source_namespace",
        "source_id",
        "entity_type",
        "source_snapshot",
        "source_artifact",
        "provenance_ref",
        "created_at",
    ]
    assert list(previous.columns) == expected_columns

    edition_ids = set(coverage["edition_key"])

    diagnostic = diagnostic[
        diagnostic["edition_key"].isin(edition_ids)
    ].copy()

    assert len(diagnostic) == 508
    assert diagnostic["edition_key"].is_unique
    assert set(diagnostic["edition_key"]) == edition_ids

    snapshot = dm["retrieved_at_utc"]

    assert set(diagnostic["retrieved_at_utc"]) == {snapshot}
    assert previous.iloc[-1]["entity_id"] == "E000048655"

    old_natural_keys = set(zip(
        previous["source"],
        previous["source_namespace"],
        previous["source_id"],
    ))

    for eid in edition_ids:
        assert ("openlibrary", "edition", eid) not in old_natural_keys

    source_artifact = str(DIAG.relative_to(ROOT))
    provenance_ref = str(DIAG_MANIFEST.relative_to(ROOT))

    new_rows = []

    for number, eid in enumerate(
        sorted(edition_ids), start=48656
    ):
        new_rows.append({
            "entity_id": f"E{number:09d}",
            "source": "openlibrary",
            "source_namespace": "edition",
            "source_id": eid,
            "entity_type": "edition",
            "source_snapshot": snapshot,
            "source_artifact": source_artifact,
            "provenance_ref": provenance_ref,
            "created_at": CREATED_AT,
        })

    added = pd.DataFrame(new_rows, columns=expected_columns)

    all_entities = pd.concat(
        [previous, added], ignore_index=True
    )

    assert len(added) == 508
    assert len(all_entities) == 49163
    assert all_entities["entity_id"].is_unique
    assert all_entities.iloc[-1]["entity_id"] == "E000049163"

    natural_keys = list(zip(
        all_entities["source"],
        all_entities["source_namespace"],
        all_entities["source_id"],
    ))
    assert len(natural_keys) == len(set(natural_keys))

    pd.testing.assert_frame_equal(
        all_entities.iloc[:len(previous)].reset_index(drop=True),
        previous.reset_index(drop=True),
    )

    # Build an evidence bridge, not a conceptual identity map.
    old_work_entities = previous[
        (previous["source"] == "openlibrary")
        & (previous["source_namespace"] == "work")
    ].set_index("entity_id")

    predecessor_ids = set(coverage["project_work_id"])
    assert len(predecessor_ids) == 17

    predecessor_members = mapping[
        mapping["project_work_id"].isin(predecessor_ids)
    ]

    assert len(predecessor_members) == 17
    assert predecessor_members["project_work_id"].is_unique

    source_work_by_project = dict(zip(
        predecessor_members["project_work_id"],
        predecessor_members["source_entity_id"],
    ))

    edition_entity_by_id = dict(zip(
        added["source_id"], added["entity_id"]
    ))

    diagnostic_by_id = diagnostic.set_index("edition_key")

    bridge_rows = []

    for r in coverage.to_dict("records"):
        eid = r["edition_key"]
        wid = r["project_work_id"]
        ol_id = r["current_ol_work_id"]

        d = diagnostic_by_id.loc[eid]

        assert d["current_ol_work_id"] == ol_id
        assert d["project_work_id"] == wid

        for field in [
            "edition_title",
            "edition_subtitle",
            "publish_date",
            "publishers",
        ]:
            assert d[field] == r[field], (eid, field)

        work_entity_id = source_work_by_project[wid]
        assert work_entity_id in old_work_entities.index
        assert old_work_entities.loc[
            work_entity_id, "source_id"
        ] == ol_id

        bridge_rows.append({
            "edition_entity_id": edition_entity_by_id[eid],
            "edition_key": eid,
            "predecessor_work_entity_id": work_entity_id,
            "predecessor_ol_work_id": ol_id,
            "predecessor_project_work_id": wid,
            "source_relation": "OL_API_EDITION_LISTED_UNDER_WORK",
            "source_snapshot": snapshot,
            "candidate_unit_id": r["candidate_unit_id"],
            "migration_bucket": r["migration_bucket"],
            "final_routing_decision": r["final_routing_decision"],
            "final_provenance": r["final_provenance"],
            "conceptual_identity_decision": "NOT_ADJUDICATED",
        })

    bridge = pd.DataFrame(bridge_rows).sort_values(
        "edition_key"
    )

    assert len(bridge) == 508
    assert bridge["edition_entity_id"].is_unique
    assert bridge["edition_key"].is_unique
    assert bridge["predecessor_ol_work_id"].nunique() == 17

    expected_buckets = {
        "PROVISIONAL_PUBLICATION_GROUP": 280,
        "COHERENCE_UNRESOLVED": 91,
        "ROUTING_UNRESOLVED": 104,
        "DETACH_PENDING_IDENTITY": 28,
        "APPARATUS_PENDING_SCOPE": 5,
    }

    assert bridge["migration_bucket"].value_counts().to_dict() == (
        expected_buckets
    )

    # All QC is complete before writing anything.
    all_entities.to_csv(
        OUT_TSV, sep="\t", index=False, lineterminator="\n"
    )
    all_entities.to_parquet(
        OUT_PARQUET, index=False
    )

    BRIDGE_DIR.mkdir(parents=True)
    bridge.to_csv(
        BRIDGE, sep="\t", index=False, lineterminator="\n"
    )

    dump(OUT_MANIFEST, {
        "release": "source-entities-v3",
        "created_at": CREATED_AT,
        "previous_release": "source-entities-v2",
        "inputs": {
            str(V2.relative_to(ROOT)): sha(V2),
            source_artifact: sha(DIAG),
            str(COV.relative_to(ROOT)): sha(COV),
        },
        "outputs": {
            OUT_TSV.name: sha(OUT_TSV),
            OUT_PARQUET.name: sha(OUT_PARQUET),
        },
        "counts": {
            "previous_entities": 48655,
            "new_edition_entities": 508,
            "total_entities": 49163,
        },
        "appended_entity_id_range": [
            "E000048656", "E000049163"
        ],
        "source_snapshot": snapshot,
        "semantics": (
            "Open Library Edition source records only. "
            "No SAME identity assertion or conceptual work "
            "membership is implied."
        ),
    })

    dump(BRIDGE_MANIFEST, {
        "release": "openlibrary-r2a1-edition-source-bridge-v1",
        "inputs": {
            str(OUT_TSV.relative_to(ROOT)): sha(OUT_TSV),
            str(COV.relative_to(ROOT)): sha(COV),
            str(WORK_MAP.relative_to(ROOT)): sha(WORK_MAP),
        },
        "outputs": {BRIDGE.name: sha(BRIDGE)},
        "counts": {
            "edition_rows": 508,
            "predecessor_ol_works": 17,
            "migration_buckets": expected_buckets,
        },
        "semantics": (
            "Source-native OL Edition-to-Work relation and "
            "provisional migration evidence only; not a "
            "project-work identity membership map."
        ),
        "identity_decisions_created": 0,
        "project_works_created": 0,
    })

    print("=== SOURCE ENTITIES V3 ===")
    print("previous entities:", len(previous))
    print("new Edition entities:", len(added))
    print("total entities:", len(all_entities))
    print("new E ID range: E000048656–E000049163")
    print("source snapshot:", snapshot)

    print("\n=== EDITION SOURCE BRIDGE ===")
    print("bridge rows:", len(bridge))
    print("predecessor OL Works:",
          bridge["predecessor_ol_work_id"].nunique())
    print(bridge["migration_bucket"].value_counts().to_string())

    print("\nidentity decisions created: 0")
    print("project works created: 0")
    print("QC: PASSED")

if __name__ == "__main__":
    main()
