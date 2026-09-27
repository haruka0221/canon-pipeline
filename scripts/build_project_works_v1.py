from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

DECISIONS = (
    ROOT / "derived/identity/aggregation_decisions_v1.parquet"
)

MEMBERS = (
    ROOT / "derived/identity/aggregation_review_members_v1.parquet"
)

POLICY = (
    ROOT / "docs/AGGREGATION_POLICY.md"
)

OUT_DIR = ROOT / "derived/identity"

OUT_WORKS_TSV = (
    OUT_DIR / "project_works_v1.tsv"
)

OUT_WORKS_PARQUET = (
    OUT_DIR / "project_works_v1.parquet"
)

OUT_MAP_TSV = (
    OUT_DIR / "work_identity_map_v1.tsv"
)

OUT_MAP_PARQUET = (
    OUT_DIR / "work_identity_map_v1.parquet"
)

OUT_MANIFEST = (
    OUT_DIR / "project_works_v1_manifest.json"
)

CREATED_AT = "2026-09-27"

EXPECTED_WORKS = 31539
EXPECTED_MAP_ROWS = 42937
EXPECTED_CURRENT_TARGET_MEMBERS = 31539
EXPECTED_EXTERNAL_MEMBERS = 11398
EXPECTED_PENDING_UNITS = 1308


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


def write_atomic_tsv(
    df: pd.DataFrame,
    path: Path,
) -> None:
    tmp = path.with_name(path.name + ".tmp")

    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    os.replace(tmp, path)


def write_atomic_parquet(
    df: pd.DataFrame,
    path: Path,
) -> None:
    tmp = path.with_name(path.name + ".tmp")

    df.to_parquet(
        tmp,
        index=False,
        engine="pyarrow",
    )

    os.replace(tmp, path)


def main() -> None:
    for p in [
        DECISIONS,
        MEMBERS,
        POLICY,
    ]:
        require(p)

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    decisions = pd.read_parquet(
        DECISIONS
    ).fillna("")

    members = pd.read_parquet(
        MEMBERS
    ).fillna("")

    assert decisions[
        "unit_anchor_entity_id"
    ].is_unique

    assert members["entity_id"].is_unique

    eligible = decisions[
        decisions["aggregation_decision"].eq(
            "ONE_WORK"
        )
    ].copy()

    pending = decisions[
        decisions["aggregation_decision"].eq(
            "MANUAL_REVIEW_REQUIRED"
        )
    ].copy()

    assert len(eligible) == EXPECTED_WORKS
    assert len(pending) == EXPECTED_PENDING_UNITS

    assert eligible[
        "current_target_count"
    ].eq(1).all()

    # ---------------------------------------------------------
    # Stable initial W assignment
    # ---------------------------------------------------------

    eligible = eligible.sort_values(
        "unit_anchor_entity_id",
        kind="stable",
    ).reset_index(drop=True)

    eligible.insert(
        0,
        "project_work_id",
        [
            f"W{i:09d}"
            for i in range(
                1,
                len(eligible) + 1,
            )
        ],
    )

    works = eligible[
        [
            "project_work_id",
            "unit_anchor_entity_id",
            "aggregation_decision",
            "decision_version",
        ]
    ].copy()

    works = works.rename(
        columns={
            "unit_anchor_entity_id":
                "origin_unit_anchor_entity_id",
            "decision_version":
                "aggregation_decision_version",
        }
    )

    works["status"] = "active"
    works["created_at"] = CREATED_AT

    works = works[
        [
            "project_work_id",
            "origin_unit_anchor_entity_id",
            "aggregation_decision",
            "aggregation_decision_version",
            "status",
            "created_at",
        ]
    ]

    # ---------------------------------------------------------
    # Project-work membership
    # ---------------------------------------------------------

    anchor_to_work = dict(
        zip(
            works[
                "origin_unit_anchor_entity_id"
            ],
            works["project_work_id"],
        )
    )

    eligible_anchors = set(
        anchor_to_work
    )

    mapped_members = members[
        members[
            "unit_anchor_entity_id"
        ].isin(eligible_anchors)
    ].copy()

    mapped_members[
        "project_work_id"
    ] = mapped_members[
        "unit_anchor_entity_id"
    ].map(anchor_to_work)

    assert mapped_members[
        "project_work_id"
    ].notna().all()

    work_map = mapped_members[
        [
            "project_work_id",
            "entity_id",
            "member_role",
        ]
    ].copy()

    work_map = work_map.rename(
        columns={
            "entity_id": "source_entity_id",
            "member_role": "membership_role",
        }
    )

    work_map[
        "membership_basis"
    ] = "aggregation_decisions_v1:ONE_WORK"

    work_map[
        "aggregation_decision_version"
    ] = "v1"

    work_map["created_at"] = CREATED_AT

    role_order = {
        "current_analysis_target": 0,
        "accepted_external_identity": 1,
    }

    work_map["_role_order"] = (
        work_map["membership_role"]
        .map(role_order)
    )

    assert work_map["_role_order"].notna().all()

    work_map = work_map.sort_values(
        [
            "project_work_id",
            "_role_order",
            "source_entity_id",
        ],
        kind="stable",
    ).drop(
        columns=["_role_order"]
    ).reset_index(drop=True)

    # ---------------------------------------------------------
    # Validation
    # ---------------------------------------------------------

    assert len(works) == EXPECTED_WORKS
    assert len(work_map) == EXPECTED_MAP_ROWS

    assert works["project_work_id"].is_unique

    assert works[
        "origin_unit_anchor_entity_id"
    ].is_unique

    assert work_map[
        "source_entity_id"
    ].is_unique

    assert (
        works.iloc[0]["project_work_id"]
        == "W000000001"
    )

    assert (
        works.iloc[-1]["project_work_id"]
        == "W000031539"
    )

    assert set(
        works["aggregation_decision"]
    ) == {"ONE_WORK"}

    assert set(
        works["aggregation_decision_version"]
    ) == {"v1"}

    assert set(
        works["status"]
    ) == {"active"}

    role_counts = (
        work_map["membership_role"]
        .value_counts()
        .to_dict()
    )

    assert role_counts == {
        "current_analysis_target":
            EXPECTED_CURRENT_TARGET_MEMBERS,
        "accepted_external_identity":
            EXPECTED_EXTERNAL_MEMBERS,
    }

    assert set(
        work_map["project_work_id"]
    ) == set(
        works["project_work_id"]
    )

    # Each initial project work must contain exactly one
    # current analysis target.
    current_counts = (
        work_map[
            work_map["membership_role"].eq(
                "current_analysis_target"
            )
        ]
        .groupby("project_work_id")
        .size()
    )

    assert len(current_counts) == EXPECTED_WORKS
    assert current_counts.eq(1).all()

    # Pending units must receive no W identifier and no
    # source-entity membership in this release.
    pending_anchors = set(
        pending["unit_anchor_entity_id"]
    )

    assert not (
        pending_anchors
        & set(
            works[
                "origin_unit_anchor_entity_id"
            ]
        )
    )

    pending_entities = set(
        members.loc[
            members[
                "unit_anchor_entity_id"
            ].isin(pending_anchors),
            "entity_id",
        ]
    )

    assert not (
        pending_entities
        & set(
            work_map["source_entity_id"]
        )
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
        "release": "project-works-v1",
        "created_at": CREATED_AT,
        "semantics": {
            "project_work": (
                "A project-native conceptual work created "
                "only from a versioned aggregation decision."
            ),
            "initial_assignment": (
                "Only aggregation_decisions_v1 rows with "
                "aggregation_decision=ONE_WORK receive W IDs."
            ),
            "w_id_policy": (
                "Eligible units are sorted lexically by "
                "unit_anchor_entity_id and assigned W IDs "
                "sequentially from W000000001. Released W IDs "
                "must never be renumbered or reused."
            ),
            "membership": (
                "work_identity_map_v1 records project-level "
                "membership separately from source-level "
                "identity assertions."
            ),
            "pending_units": (
                "MANUAL_REVIEW_REQUIRED units receive no W ID "
                "and no work-identity membership in v1."
            ),
            "lineage": (
                "No project-work lineage rows are required "
                "for this first project-work release."
            ),
        },
        "inputs": {
            "aggregation_decisions": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_decisions_v1.parquet"
                ),
                "sha256": sha256_file(
                    DECISIONS
                ),
            },
            "aggregation_review_members": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_review_members_v1.parquet"
                ),
                "sha256": sha256_file(
                    MEMBERS
                ),
            },
            "aggregation_policy": {
                "artifact": (
                    "docs/AGGREGATION_POLICY.md"
                ),
                "sha256": sha256_file(
                    POLICY
                ),
                "version": "1",
            },
        },
        "counts": {
            "project_works": EXPECTED_WORKS,
            "work_identity_map_rows": (
                EXPECTED_MAP_ROWS
            ),
            "current_analysis_target_members": (
                EXPECTED_CURRENT_TARGET_MEMBERS
            ),
            "accepted_external_identity_members": (
                EXPECTED_EXTERNAL_MEMBERS
            ),
            "pending_units_without_w_id": (
                EXPECTED_PENDING_UNITS
            ),
        },
        "id_range": {
            "first": "W000000001",
            "last": "W000031539",
        },
        "outputs": {
            "project_works_tsv": (
                "derived/identity/"
                "project_works_v1.tsv"
            ),
            "project_works_parquet": (
                "derived/identity/"
                "project_works_v1.parquet"
            ),
            "work_identity_map_tsv": (
                "derived/identity/"
                "work_identity_map_v1.tsv"
            ),
            "work_identity_map_parquet": (
                "derived/identity/"
                "work_identity_map_v1.parquet"
            ),
        },
    }

    manifest[
        "outputs"
    ]["project_works_tsv_sha256"] = (
        sha256_file(OUT_WORKS_TSV)
    )

    manifest[
        "outputs"
    ]["project_works_parquet_sha256"] = (
        sha256_file(OUT_WORKS_PARQUET)
    )

    manifest[
        "outputs"
    ]["work_identity_map_tsv_sha256"] = (
        sha256_file(OUT_MAP_TSV)
    )

    manifest[
        "outputs"
    ]["work_identity_map_parquet_sha256"] = (
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

    os.replace(
        tmp,
        OUT_MANIFEST,
    )

    print("=== PROJECT WORKS V1 ===")
    print("project works:", len(works))
    print(
        "first W:",
        works.iloc[0]["project_work_id"],
    )
    print(
        "last W:",
        works.iloc[-1]["project_work_id"],
    )

    print("\n=== WORK IDENTITY MAP ===")
    print("rows:", len(work_map))
    print(
        work_map["membership_role"]
        .value_counts()
        .to_string()
    )

    print("\n=== PENDING ===")
    print(
        "units without W ID:",
        len(pending),
    )
    print(
        "pending source entities excluded:",
        len(pending_entities),
    )

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
