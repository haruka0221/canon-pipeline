from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

PREVIOUS_WORKS = (
    ROOT / "derived/identity/project_works_v2.parquet"
)

PREVIOUS_MAP = (
    ROOT / "derived/identity/work_identity_map_v2.parquet"
)

DECISIONS_V2 = (
    ROOT / "derived/identity/aggregation_decisions_v2.parquet"
)

DECISIONS_V3 = (
    ROOT / "derived/identity/aggregation_decisions_v3.parquet"
)

MEMBERS = (
    ROOT / "derived/identity/aggregation_review_members_v1.parquet"
)

POLICY = ROOT / "docs/AGGREGATION_POLICY.md"

OUT_DIR = ROOT / "derived/identity"

OUT_WORKS_TSV = OUT_DIR / "project_works_v3.tsv"
OUT_WORKS_PARQUET = OUT_DIR / "project_works_v3.parquet"

OUT_MAP_TSV = OUT_DIR / "work_identity_map_v3.tsv"
OUT_MAP_PARQUET = OUT_DIR / "work_identity_map_v3.parquet"

OUT_MANIFEST = (
    OUT_DIR / "project_works_v3_manifest.json"
)

CREATED_AT = "2026-09-27"

EXPECTED_PREVIOUS_WORKS = 31651
EXPECTED_NEW_WORKS = 2
EXPECTED_TOTAL_WORKS = 31653

EXPECTED_PREVIOUS_MAP_ROWS = 43400
EXPECTED_NEW_MAP_ROWS = 9
EXPECTED_TOTAL_MAP_ROWS = 43409

EXPECTED_NEW_CURRENT_TARGETS = 5
EXPECTED_NEW_EXTERNAL_ENTITIES = 4

EXPECTED_TOTAL_CURRENT_TARGET_MEMBERS = 31783
EXPECTED_TOTAL_EXTERNAL_MEMBERS = 11626

EXPECTED_PENDING_UNITS = 1194
EXPECTED_PENDING_CURRENT_TARGETS = 3006
EXPECTED_PENDING_EXTERNAL_ENTITIES = 1774
EXPECTED_PENDING_MEMBER_ENTITIES = 4780

EXPECTED_NEW_ANCHORS = [
    "E000016422",
    "E000018958",
]


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
        DECISIONS_V2,
        DECISIONS_V3,
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

    d2 = pd.read_parquet(
        DECISIONS_V2
    ).fillna("")

    d3 = pd.read_parquet(
        DECISIONS_V3
    ).fillna("")

    members = pd.read_parquet(
        MEMBERS
    ).fillna("")

    assert len(previous_works) == EXPECTED_PREVIOUS_WORKS
    assert len(previous_map) == EXPECTED_PREVIOUS_MAP_ROWS

    assert previous_works["project_work_id"].is_unique
    assert previous_map["source_entity_id"].is_unique

    # ---------------------------------------------------------
    # Identify only units newly eligible in v3
    # ---------------------------------------------------------

    z = d2[
        [
            "unit_anchor_entity_id",
            "aggregation_decision",
        ]
    ].merge(
        d3[
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
        suffixes=("_v2", "_v3"),
        validate="one_to_one",
    )

    newly_eligible = z[
        z["aggregation_decision_v2"].eq(
            "MANUAL_REVIEW_REQUIRED"
        )
        & z["aggregation_decision_v3"].eq(
            "ONE_WORK"
        )
    ].copy()

    newly_eligible = newly_eligible.sort_values(
        "unit_anchor_entity_id",
        kind="stable",
    ).reset_index(drop=True)

    assert len(newly_eligible) == EXPECTED_NEW_WORKS

    assert (
        newly_eligible["unit_anchor_entity_id"].tolist()
        == EXPECTED_NEW_ANCHORS
    )

    assert set(
        newly_eligible["decision_method"]
    ) == {
        "multi_ol_identity_evidence_cross_source_rule"
    }

    assert set(
        newly_eligible["decision_version"]
    ) == {"v3"}

    assert int(
        newly_eligible["current_target_count"].sum()
    ) == EXPECTED_NEW_CURRENT_TARGETS

    # ---------------------------------------------------------
    # Append-only W assignment
    # ---------------------------------------------------------

    assert (
        previous_works.iloc[-1]["project_work_id"]
        == "W000031651"
    )

    new_work_ids = [
        "W000031652",
        "W000031653",
    ]

    new_works = pd.DataFrame(
        {
            "project_work_id": new_work_ids,
            "origin_unit_anchor_entity_id": (
                newly_eligible[
                    "unit_anchor_entity_id"
                ].tolist()
            ),
            "aggregation_decision": "ONE_WORK",
            "aggregation_decision_version": "v3",
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

    assert works.iloc[
        :EXPECTED_PREVIOUS_WORKS
    ].reset_index(drop=True).equals(
        previous_works.reset_index(drop=True)
    )

    # ---------------------------------------------------------
    # Append membership
    # ---------------------------------------------------------

    anchor_to_w = dict(
        zip(
            new_works[
                "origin_unit_anchor_entity_id"
            ],
            new_works["project_work_id"],
        )
    )

    new_members = members[
        members["unit_anchor_entity_id"].isin(
            set(EXPECTED_NEW_ANCHORS)
        )
    ].copy()

    assert len(new_members) == EXPECTED_NEW_MAP_ROWS

    new_members[
        "project_work_id"
    ] = new_members[
        "unit_anchor_entity_id"
    ].map(anchor_to_w)

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
    ] = "aggregation_decisions_v3:ONE_WORK"

    new_map[
        "aggregation_decision_version"
    ] = "v3"

    new_map["created_at"] = CREATED_AT

    role_order = {
        "current_analysis_target": 0,
        "accepted_external_identity": 1,
    }

    new_map["_role_order"] = (
        new_map["membership_role"].map(role_order)
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

    assert works.iloc[-1]["project_work_id"] == "W000031653"

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

    new_current_per_w = (
        new_map[
            new_map["membership_role"].eq(
                "current_analysis_target"
            )
        ]
        .groupby("project_work_id")
        .size()
    )

    assert (
        new_current_per_w.to_dict()
        == {
            "W000031652": 3,
            "W000031653": 2,
        }
    )

    new_external_per_w = (
        new_map[
            new_map["membership_role"].eq(
                "accepted_external_identity"
            )
        ]
        .groupby("project_work_id")
        .size()
    )

    assert new_external_per_w.eq(2).all()

    # ---------------------------------------------------------
    # Remaining pending
    # ---------------------------------------------------------

    pending = d3[
        d3["aggregation_decision"].eq(
            "MANUAL_REVIEW_REQUIRED"
        )
    ]

    assert len(pending) == EXPECTED_PENDING_UNITS

    pending_anchors = set(
        pending["unit_anchor_entity_id"]
    )

    pending_members = members[
        members["unit_anchor_entity_id"].isin(
            pending_anchors
        )
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

    # Explicit near-miss preservation.
    pending_anchor_set = set(
        pending["unit_anchor_entity_id"]
    )

    for anchor in [
        "E000000508",
        "E000003313",
        "E000008831",
        "E000009616",
    ]:
        assert anchor in pending_anchor_set

    # ---------------------------------------------------------
    # Write outputs
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
        "release": "project-works-v3",
        "created_at": CREATED_AT,
        "semantics": {
            "previous_release": "project-works-v2",
            "append_only": (
                "All v2 W IDs and membership rows are "
                "preserved exactly; only two newly eligible "
                "v3 units are appended."
            ),
            "new_assignment": (
                "E000016422 and E000018958 receive "
                "W000031652 and W000031653 respectively."
            ),
        },
        "inputs": {
            "previous_project_works": {
                "artifact": (
                    "derived/identity/project_works_v2.parquet"
                ),
                "sha256": sha256_file(PREVIOUS_WORKS),
            },
            "previous_work_identity_map": {
                "artifact": (
                    "derived/identity/work_identity_map_v2.parquet"
                ),
                "sha256": sha256_file(PREVIOUS_MAP),
            },
            "aggregation_decisions_v2": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_decisions_v2.parquet"
                ),
                "sha256": sha256_file(DECISIONS_V2),
            },
            "aggregation_decisions_v3": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_decisions_v3.parquet"
                ),
                "sha256": sha256_file(DECISIONS_V3),
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
            "previous_last": "W000031651",
            "first_new": "W000031652",
            "last": "W000031653",
        },
        "outputs": {
            "project_works_tsv": (
                "derived/identity/project_works_v3.tsv"
            ),
            "project_works_parquet": (
                "derived/identity/project_works_v3.parquet"
            ),
            "work_identity_map_tsv": (
                "derived/identity/work_identity_map_v3.tsv"
            ),
            "work_identity_map_parquet": (
                "derived/identity/work_identity_map_v3.parquet"
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

    print("=== PROJECT WORKS V3 ===")
    print("previous works:", len(previous_works))
    print("new works:", len(new_works))
    print("total works:", len(works))

    print("\n=== NEW W ASSIGNMENTS ===")
    print(
        new_works[
            [
                "project_work_id",
                "origin_unit_anchor_entity_id",
            ]
        ].to_string(index=False)
    )

    print("\n=== NEW MEMBERSHIP ===")
    print("rows:", len(new_map))
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
