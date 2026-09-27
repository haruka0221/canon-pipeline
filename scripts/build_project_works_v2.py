from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

PREVIOUS_WORKS = (
    ROOT / "derived/identity/project_works_v1.parquet"
)

PREVIOUS_MAP = (
    ROOT / "derived/identity/work_identity_map_v1.parquet"
)

DECISIONS_V1 = (
    ROOT / "derived/identity/aggregation_decisions_v1.parquet"
)

DECISIONS_V2 = (
    ROOT / "derived/identity/aggregation_decisions_v2.parquet"
)

MEMBERS = (
    ROOT / "derived/identity/aggregation_review_members_v1.parquet"
)

POLICY = (
    ROOT / "docs/AGGREGATION_POLICY.md"
)

OUT_DIR = ROOT / "derived/identity"

OUT_WORKS_TSV = (
    OUT_DIR / "project_works_v2.tsv"
)

OUT_WORKS_PARQUET = (
    OUT_DIR / "project_works_v2.parquet"
)

OUT_MAP_TSV = (
    OUT_DIR / "work_identity_map_v2.tsv"
)

OUT_MAP_PARQUET = (
    OUT_DIR / "work_identity_map_v2.parquet"
)

OUT_MANIFEST = (
    OUT_DIR / "project_works_v2_manifest.json"
)

CREATED_AT = "2026-09-27"

EXPECTED_PREVIOUS_WORKS = 31539
EXPECTED_NEW_WORKS = 112
EXPECTED_TOTAL_WORKS = 31651

EXPECTED_PREVIOUS_MAP_ROWS = 42937
EXPECTED_NEW_MAP_ROWS = 463
EXPECTED_TOTAL_MAP_ROWS = 43400

EXPECTED_NEW_CURRENT_TARGETS = 239
EXPECTED_NEW_EXTERNAL_ENTITIES = 224

EXPECTED_TOTAL_CURRENT_TARGET_MEMBERS = 31778
EXPECTED_TOTAL_EXTERNAL_MEMBERS = 11622

EXPECTED_PENDING_UNITS = 1196
EXPECTED_PENDING_CURRENT_TARGETS = 3011
EXPECTED_PENDING_EXTERNAL_ENTITIES = 1778
EXPECTED_PENDING_MEMBER_ENTITIES = 4789


def require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def write_atomic_tsv(df, path):
    tmp = path.with_name(path.name + ".tmp")

    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    os.replace(tmp, path)


def write_atomic_parquet(df, path):
    tmp = path.with_name(path.name + ".tmp")

    df.to_parquet(
        tmp,
        index=False,
        engine="pyarrow",
    )

    os.replace(tmp, path)


def main():
    for p in [
        PREVIOUS_WORKS,
        PREVIOUS_MAP,
        DECISIONS_V1,
        DECISIONS_V2,
        MEMBERS,
        POLICY,
    ]:
        require(p)

    previous_works = pd.read_parquet(
        PREVIOUS_WORKS
    ).fillna("")

    previous_map = pd.read_parquet(
        PREVIOUS_MAP
    ).fillna("")

    d1 = pd.read_parquet(
        DECISIONS_V1
    ).fillna("")

    d2 = pd.read_parquet(
        DECISIONS_V2
    ).fillna("")

    members = pd.read_parquet(
        MEMBERS
    ).fillna("")

    assert len(previous_works) == EXPECTED_PREVIOUS_WORKS
    assert len(previous_map) == EXPECTED_PREVIOUS_MAP_ROWS

    assert previous_works["project_work_id"].is_unique
    assert previous_map["source_entity_id"].is_unique

    # ---------------------------------------------------------
    # Identify only units newly eligible in v2
    # ---------------------------------------------------------

    z = d1[
        [
            "unit_anchor_entity_id",
            "aggregation_decision",
        ]
    ].merge(
        d2[
            [
                "unit_anchor_entity_id",
                "aggregation_decision",
                "decision_method",
                "decision_version",
                "review_status",
                "current_target_count",
            ]
        ],
        on="unit_anchor_entity_id",
        suffixes=("_v1", "_v2"),
        validate="one_to_one",
    )

    newly_eligible = z[
        z["aggregation_decision_v1"].eq(
            "MANUAL_REVIEW_REQUIRED"
        )
        & z["aggregation_decision_v2"].eq(
            "ONE_WORK"
        )
    ].copy()

    newly_eligible = newly_eligible.sort_values(
        "unit_anchor_entity_id",
        kind="stable",
    ).reset_index(drop=True)

    assert len(newly_eligible) == EXPECTED_NEW_WORKS

    assert set(
        newly_eligible["decision_method"]
    ) == {
        "multi_ol_exact_metadata_cross_source_rule"
    }

    assert set(
        newly_eligible["decision_version"]
    ) == {"v2"}

    assert int(
        newly_eligible[
            "current_target_count"
        ].sum()
    ) == EXPECTED_NEW_CURRENT_TARGETS

    # ---------------------------------------------------------
    # Append-only W assignment
    # ---------------------------------------------------------

    assert (
        previous_works.iloc[-1]["project_work_id"]
        == "W000031539"
    )

    new_work_ids = [
        f"W{i:09d}"
        for i in range(
            31540,
            31652,
        )
    ]

    assert len(new_work_ids) == EXPECTED_NEW_WORKS
    assert new_work_ids[0] == "W000031540"
    assert new_work_ids[-1] == "W000031651"

    new_works = pd.DataFrame(
        {
            "project_work_id": new_work_ids,
            "origin_unit_anchor_entity_id": (
                newly_eligible[
                    "unit_anchor_entity_id"
                ].tolist()
            ),
            "aggregation_decision": "ONE_WORK",
            "aggregation_decision_version": "v2",
            "status": "active",
            "created_at": CREATED_AT,
        }
    )

    works = pd.concat(
        [
            previous_works,
            new_works,
        ],
        ignore_index=True,
    )

    # v1 must remain an exact logical prefix.
    assert works.iloc[
        :EXPECTED_PREVIOUS_WORKS
    ].reset_index(drop=True).equals(
        previous_works.reset_index(drop=True)
    )

    # ---------------------------------------------------------
    # New membership rows
    # ---------------------------------------------------------

    anchor_to_new_w = dict(
        zip(
            new_works[
                "origin_unit_anchor_entity_id"
            ],
            new_works["project_work_id"],
        )
    )

    new_anchors = set(anchor_to_new_w)

    new_members = members[
        members[
            "unit_anchor_entity_id"
        ].isin(new_anchors)
    ].copy()

    assert len(new_members) == EXPECTED_NEW_MAP_ROWS

    new_members[
        "project_work_id"
    ] = new_members[
        "unit_anchor_entity_id"
    ].map(anchor_to_new_w)

    assert new_members[
        "project_work_id"
    ].notna().all()

    new_map = new_members[
        [
            "project_work_id",
            "entity_id",
            "member_role",
        ]
    ].copy()

    new_map = new_map.rename(
        columns={
            "entity_id": "source_entity_id",
            "member_role": "membership_role",
        }
    )

    new_map[
        "membership_basis"
    ] = "aggregation_decisions_v2:ONE_WORK"

    new_map[
        "aggregation_decision_version"
    ] = "v2"

    new_map["created_at"] = CREATED_AT

    role_order = {
        "current_analysis_target": 0,
        "accepted_external_identity": 1,
    }

    new_map["_role_order"] = (
        new_map["membership_role"]
        .map(role_order)
    )

    assert new_map["_role_order"].notna().all()

    new_map = new_map.sort_values(
        [
            "project_work_id",
            "_role_order",
            "source_entity_id",
        ],
        kind="stable",
    ).drop(
        columns=["_role_order"]
    ).reset_index(drop=True)

    # No v2 entity may already belong to a v1 W.
    assert not (
        set(new_map["source_entity_id"])
        & set(previous_map["source_entity_id"])
    )

    work_map = pd.concat(
        [
            previous_map,
            new_map,
        ],
        ignore_index=True,
    )

    # v1 membership remains an exact logical prefix.
    assert work_map.iloc[
        :EXPECTED_PREVIOUS_MAP_ROWS
    ].reset_index(drop=True).equals(
        previous_map.reset_index(drop=True)
    )

    # ---------------------------------------------------------
    # Validation
    # ---------------------------------------------------------

    assert len(works) == EXPECTED_TOTAL_WORKS
    assert len(work_map) == EXPECTED_TOTAL_MAP_ROWS

    assert works["project_work_id"].is_unique
    assert works[
        "origin_unit_anchor_entity_id"
    ].is_unique

    assert work_map[
        "source_entity_id"
    ].is_unique

    assert works.iloc[0]["project_work_id"] == "W000000001"
    assert works.iloc[-1]["project_work_id"] == "W000031651"

    assert set(
        new_works["aggregation_decision_version"]
    ) == {"v2"}

    new_role_counts = (
        new_map["membership_role"]
        .value_counts()
        .to_dict()
    )

    assert new_role_counts == {
        "current_analysis_target":
            EXPECTED_NEW_CURRENT_TARGETS,
        "accepted_external_identity":
            EXPECTED_NEW_EXTERNAL_ENTITIES,
    }

    total_role_counts = (
        work_map["membership_role"]
        .value_counts()
        .to_dict()
    )

    assert total_role_counts == {
        "current_analysis_target":
            EXPECTED_TOTAL_CURRENT_TARGET_MEMBERS,
        "accepted_external_identity":
            EXPECTED_TOTAL_EXTERNAL_MEMBERS,
    }

    # Each newly created W contains 2–4 current OL targets.
    new_current = new_map[
        new_map["membership_role"].eq(
            "current_analysis_target"
        )
    ]

    new_current_per_w = (
        new_current
        .groupby("project_work_id")
        .size()
    )

    assert (
        new_current_per_w
        .value_counts()
        .sort_index()
        .to_dict()
        == {
            2: 99,
            3: 11,
            4: 2,
        }
    )

    # Each newly created W has exactly one GR and one WD
    # external member, hence exactly two external entities.
    new_external_per_w = (
        new_map[
            new_map["membership_role"].eq(
                "accepted_external_identity"
            )
        ]
        .groupby("project_work_id")
        .size()
    )

    assert len(new_external_per_w) == EXPECTED_NEW_WORKS
    assert new_external_per_w.eq(2).all()

    # ---------------------------------------------------------
    # Pending after v2
    # ---------------------------------------------------------

    pending = d2[
        d2["aggregation_decision"].eq(
            "MANUAL_REVIEW_REQUIRED"
        )
    ]

    assert len(pending) == EXPECTED_PENDING_UNITS

    pending_anchors = set(
        pending["unit_anchor_entity_id"]
    )

    pending_members = members[
        members[
            "unit_anchor_entity_id"
        ].isin(pending_anchors)
    ]

    pending_current = pending_members[
        pending_members["is_current_target"]
    ]

    pending_external = pending_members[
        ~pending_members["is_current_target"]
    ]

    assert len(pending_members) == EXPECTED_PENDING_MEMBER_ENTITIES
    assert len(pending_current) == EXPECTED_PENDING_CURRENT_TARGETS
    assert len(pending_external) == EXPECTED_PENDING_EXTERNAL_ENTITIES

    assert not (
        set(pending_members["entity_id"])
        & set(work_map["source_entity_id"])
    )

    # All current OL targets remain fully accounted for.
    assigned_current = set(
        work_map.loc[
            work_map["membership_role"].eq(
                "current_analysis_target"
            ),
            "source_entity_id",
        ]
    )

    pending_current_ids = set(
        pending_current["entity_id"]
    )

    assert len(assigned_current) == EXPECTED_TOTAL_CURRENT_TARGET_MEMBERS
    assert len(pending_current_ids) == EXPECTED_PENDING_CURRENT_TARGETS

    assert not (
        assigned_current
        & pending_current_ids
    )

    assert (
        len(
            assigned_current
            | pending_current_ids
        )
        == 34789
    )

    # ---------------------------------------------------------
    # Write release
    # ---------------------------------------------------------

    write_atomic_tsv(
        works,
        OUT_WORKS_TSV,
    )

    write_atomic_parquet(
        works,
        OUT_WORKS_PARQUET,
    )

    write_atomic_tsv(
        work_map,
        OUT_MAP_TSV,
    )

    write_atomic_parquet(
        work_map,
        OUT_MAP_PARQUET,
    )

    manifest = {
        "release": "project-works-v2",
        "created_at": CREATED_AT,
        "semantics": {
            "previous_release": "project-works-v1",
            "append_only": (
                "All v1 W IDs and membership rows are preserved. "
                "Only newly eligible v2 aggregation units are appended."
            ),
            "new_assignment": (
                "112 units promoted by aggregation_decisions_v2 "
                "receive W000031540 through W000031651."
            ),
            "pending": (
                "Remaining MANUAL_REVIEW_REQUIRED units receive "
                "no W ID or membership."
            ),
        },
        "inputs": {
            "previous_project_works": {
                "artifact": (
                    "derived/identity/project_works_v1.parquet"
                ),
                "sha256": sha256_file(PREVIOUS_WORKS),
            },
            "previous_work_identity_map": {
                "artifact": (
                    "derived/identity/work_identity_map_v1.parquet"
                ),
                "sha256": sha256_file(PREVIOUS_MAP),
            },
            "aggregation_decisions_v1": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_decisions_v1.parquet"
                ),
                "sha256": sha256_file(DECISIONS_V1),
            },
            "aggregation_decisions_v2": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_decisions_v2.parquet"
                ),
                "sha256": sha256_file(DECISIONS_V2),
            },
            "aggregation_review_members": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_review_members_v1.parquet"
                ),
                "sha256": sha256_file(MEMBERS),
            },
            "aggregation_policy": {
                "artifact": "docs/AGGREGATION_POLICY.md",
                "sha256": sha256_file(POLICY),
                "version": "1",
            },
        },
        "counts": {
            "previous_project_works": EXPECTED_PREVIOUS_WORKS,
            "new_project_works": EXPECTED_NEW_WORKS,
            "project_works": EXPECTED_TOTAL_WORKS,
            "previous_membership_rows": EXPECTED_PREVIOUS_MAP_ROWS,
            "new_membership_rows": EXPECTED_NEW_MAP_ROWS,
            "work_identity_map_rows": EXPECTED_TOTAL_MAP_ROWS,
            "new_current_target_members": EXPECTED_NEW_CURRENT_TARGETS,
            "new_external_members": EXPECTED_NEW_EXTERNAL_ENTITIES,
            "current_target_members": EXPECTED_TOTAL_CURRENT_TARGET_MEMBERS,
            "external_members": EXPECTED_TOTAL_EXTERNAL_MEMBERS,
            "pending_units_without_w_id": EXPECTED_PENDING_UNITS,
            "pending_current_targets": EXPECTED_PENDING_CURRENT_TARGETS,
        },
        "id_range": {
            "first": "W000000001",
            "previous_last": "W000031539",
            "first_new": "W000031540",
            "last": "W000031651",
        },
        "outputs": {
            "project_works_tsv": (
                "derived/identity/project_works_v2.tsv"
            ),
            "project_works_parquet": (
                "derived/identity/project_works_v2.parquet"
            ),
            "work_identity_map_tsv": (
                "derived/identity/work_identity_map_v2.tsv"
            ),
            "work_identity_map_parquet": (
                "derived/identity/work_identity_map_v2.parquet"
            ),
        },
    }

    manifest["outputs"]["project_works_tsv_sha256"] = (
        sha256_file(OUT_WORKS_TSV)
    )

    manifest["outputs"]["project_works_parquet_sha256"] = (
        sha256_file(OUT_WORKS_PARQUET)
    )

    manifest["outputs"]["work_identity_map_tsv_sha256"] = (
        sha256_file(OUT_MAP_TSV)
    )

    manifest["outputs"]["work_identity_map_parquet_sha256"] = (
        sha256_file(OUT_MAP_PARQUET)
    )

    tmp = OUT_MANIFEST.with_name(
        OUT_MANIFEST.name + ".tmp"
    )

    tmp.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    os.replace(tmp, OUT_MANIFEST)

    print("=== PROJECT WORKS V2 ===")
    print("previous works:", len(previous_works))
    print("new works:", len(new_works))
    print("total works:", len(works))
    print("first new W:", new_works.iloc[0]["project_work_id"])
    print("last W:", works.iloc[-1]["project_work_id"])

    print("\n=== NEW MEMBERSHIP ===")
    print("new rows:", len(new_map))
    print(
        new_map["membership_role"]
        .value_counts()
        .to_string()
    )

    print("\n=== TOTAL MEMBERSHIP ===")
    print("rows:", len(work_map))
    print(
        work_map["membership_role"]
        .value_counts()
        .to_string()
    )

    print("\n=== NEW W CURRENT-TARGET COUNTS ===")
    print(
        new_current_per_w
        .value_counts()
        .sort_index()
        .to_string()
    )

    print("\n=== REMAINING PENDING ===")
    print("units:", len(pending))
    print("current targets:", len(pending_current))
    print("external entities:", len(pending_external))
    print("member entities:", len(pending_members))

    print("\n=== OUTPUT SHA256 ===")
    print(
        "project works tsv:",
        sha256_file(OUT_WORKS_TSV),
    )
    print(
        "project works parquet:",
        sha256_file(OUT_WORKS_PARQUET),
    )
    print(
        "identity map tsv:",
        sha256_file(OUT_MAP_TSV),
    )
    print(
        "identity map parquet:",
        sha256_file(OUT_MAP_PARQUET),
    )
    print(
        "manifest:",
        sha256_file(OUT_MANIFEST),
    )


if __name__ == "__main__":
    main()
