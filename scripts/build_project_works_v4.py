from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

PREVIOUS_WORKS = (
    ROOT / "derived/identity/project_works_v3.parquet"
)

PREVIOUS_MAP = (
    ROOT / "derived/identity/work_identity_map_v3.parquet"
)

DECISIONS_V3 = (
    ROOT / "derived/identity/aggregation_decisions_v3.parquet"
)

DECISIONS_V4 = (
    ROOT / "derived/identity/aggregation_decisions_v4.parquet"
)

MEMBERS = (
    ROOT / "derived/identity/aggregation_review_members_v1.parquet"
)

POLICY = ROOT / "docs/AGGREGATION_POLICY.md"

LLM_REVIEW_DOC = (
    ROOT / "docs/AGGREGATION_LLM_REVIEW.md"
)

ADJUDICATION = (
    ROOT
    / "derived/identity/"
    "aggregation_llm_review_adjudication_v1.parquet"
)

OUT_DIR = ROOT / "derived/identity"

OUT_WORKS_TSV = OUT_DIR / "project_works_v4.tsv"
OUT_WORKS_PARQUET = OUT_DIR / "project_works_v4.parquet"

OUT_MAP_TSV = OUT_DIR / "work_identity_map_v4.tsv"
OUT_MAP_PARQUET = OUT_DIR / "work_identity_map_v4.parquet"

OUT_MANIFEST = (
    OUT_DIR / "project_works_v4_manifest.json"
)

CREATED_AT = "2026-09-27"

EXPECTED_PREVIOUS_WORKS = 31653
EXPECTED_NEW_WORKS = 433
EXPECTED_TOTAL_WORKS = 32086

EXPECTED_PREVIOUS_MAP_ROWS = 43409

EXPECTED_NEW_CURRENT_TARGETS = 923
EXPECTED_TOTAL_CURRENT_TARGETS = 32706

EXPECTED_PENDING_UNITS = 761
EXPECTED_PENDING_CURRENT_TARGETS = 2083

EXPECTED_ALL_CURRENT_TARGETS = 34789

FIRST_NEW_W = 31654
LAST_NEW_W = 32086


def require(path):
    if not path.exists():
        raise FileNotFoundError(path)


def sha256_file(path):
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


def wid(n):
    return f"W{n:09d}"


def main():
    for p in [
        PREVIOUS_WORKS,
        PREVIOUS_MAP,
        DECISIONS_V3,
        DECISIONS_V4,
        MEMBERS,
        POLICY,
        LLM_REVIEW_DOC,
        ADJUDICATION,
    ]:
        require(p)

    previous_works = pd.read_parquet(
        PREVIOUS_WORKS
    ).fillna("")

    previous_map = pd.read_parquet(
        PREVIOUS_MAP
    ).fillna("")

    d3 = pd.read_parquet(
        DECISIONS_V3
    ).fillna("")

    d4 = pd.read_parquet(
        DECISIONS_V4
    ).fillna("")

    members = pd.read_parquet(
        MEMBERS
    ).fillna("")

    adjudication = pd.read_parquet(
        ADJUDICATION
    ).fillna("")

    # ---------------------------------------------------------
    # Previous release invariants
    # ---------------------------------------------------------

    assert len(previous_works) == EXPECTED_PREVIOUS_WORKS
    assert len(previous_map) == EXPECTED_PREVIOUS_MAP_ROWS

    assert previous_works[
        "project_work_id"
    ].is_unique

    assert previous_map[
        "source_entity_id"
    ].is_unique

    assert (
        previous_works.iloc[-1][
            "project_work_id"
        ]
        == "W000031653"
    )

    # ---------------------------------------------------------
    # Identify only units newly eligible in v4
    # ---------------------------------------------------------

    z = d3[
        [
            "unit_anchor_entity_id",
            "aggregation_decision",
        ]
    ].merge(
        d4[
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
        suffixes=("_v3", "_v4"),
        validate="one_to_one",
    )

    newly_eligible = z[
        z["aggregation_decision_v3"].eq(
            "MANUAL_REVIEW_REQUIRED"
        )
        & z["aggregation_decision_v4"].eq(
            "ONE_WORK"
        )
    ].copy()

    newly_eligible = newly_eligible.sort_values(
        "unit_anchor_entity_id",
        kind="stable",
    ).reset_index(drop=True)

    assert len(newly_eligible) == EXPECTED_NEW_WORKS

    assert int(
        newly_eligible[
            "current_target_count"
        ].sum()
    ) == EXPECTED_NEW_CURRENT_TARGETS

    assert set(
        newly_eligible[
            "decision_version"
        ]
    ) == {"v4"}

    assert set(
        newly_eligible[
            "review_status"
        ]
    ) == {"auto_accepted"}

    assert set(
        newly_eligible[
            "decision_method"
        ]
    ) == {
        "llm_review_strict_external_support_rule"
    }

    accepted_adjudication = adjudication[
        adjudication[
            "final_auto_accept_eligible"
        ].astype(bool)
    ]

    assert set(
        newly_eligible[
            "unit_anchor_entity_id"
        ]
    ) == set(
        accepted_adjudication[
            "unit_anchor_entity_id"
        ]
    )

    # ---------------------------------------------------------
    # Append-only W assignment
    # ---------------------------------------------------------

    new_work_ids = [
        wid(n)
        for n in range(
            FIRST_NEW_W,
            LAST_NEW_W + 1,
        )
    ]

    assert len(new_work_ids) == EXPECTED_NEW_WORKS
    assert new_work_ids[0] == "W000031654"
    assert new_work_ids[-1] == "W000032086"

    new_works = pd.DataFrame(
        {
            "project_work_id": new_work_ids,
            "origin_unit_anchor_entity_id": (
                newly_eligible[
                    "unit_anchor_entity_id"
                ].tolist()
            ),
            "aggregation_decision": "ONE_WORK",
            "aggregation_decision_version": "v4",
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

    # Exact v3 prefix preservation.
    assert works.iloc[
        :EXPECTED_PREVIOUS_WORKS
    ].reset_index(drop=True).equals(
        previous_works.reset_index(drop=True)
    )

    assert len(works) == EXPECTED_TOTAL_WORKS

    assert works[
        "project_work_id"
    ].is_unique

    assert works[
        "origin_unit_anchor_entity_id"
    ].is_unique

    assert (
        works.iloc[-1][
            "project_work_id"
        ]
        == "W000032086"
    )

    # ---------------------------------------------------------
    # Append membership for the 433 newly accepted units
    # ---------------------------------------------------------

    anchor_to_w = dict(
        zip(
            new_works[
                "origin_unit_anchor_entity_id"
            ],
            new_works[
                "project_work_id"
            ],
        )
    )

    new_anchors = set(
        newly_eligible[
            "unit_anchor_entity_id"
        ]
    )

    new_members = members[
        members[
            "unit_anchor_entity_id"
        ].isin(new_anchors)
    ].copy()

    assert set(
        new_members[
            "unit_anchor_entity_id"
        ]
    ) == new_anchors

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
    ] = "aggregation_decisions_v4:ONE_WORK"

    new_map[
        "aggregation_decision_version"
    ] = "v4"

    new_map["created_at"] = CREATED_AT

    role_order = {
        "current_analysis_target": 0,
        "accepted_external_identity": 1,
    }

    new_map["_role_order"] = (
        new_map[
            "membership_role"
        ].map(role_order)
    )

    assert new_map[
        "_role_order"
    ].notna().all()

    new_map = (
        new_map.sort_values(
            [
                "project_work_id",
                "_role_order",
                "source_entity_id",
            ],
            kind="stable",
        )
        .drop(
            columns=["_role_order"]
        )
        .reset_index(drop=True)
    )

    # Newly resolved source entities must not already belong
    # to an earlier project work.
    assert not (
        set(
            new_map[
                "source_entity_id"
            ]
        )
        & set(
            previous_map[
                "source_entity_id"
            ]
        )
    )

    assert new_map[
        "source_entity_id"
    ].is_unique

    new_role_counts = (
        new_map[
            "membership_role"
        ]
        .value_counts()
        .to_dict()
    )

    assert (
        new_role_counts[
            "current_analysis_target"
        ]
        == EXPECTED_NEW_CURRENT_TARGETS
    )

    new_external_entities = (
        new_role_counts.get(
            "accepted_external_identity",
            0,
        )
    )

    work_map = pd.concat(
        [
            previous_map,
            new_map,
        ],
        ignore_index=True,
    )

    # Exact v3 map prefix preservation.
    assert work_map.iloc[
        :EXPECTED_PREVIOUS_MAP_ROWS
    ].reset_index(drop=True).equals(
        previous_map.reset_index(drop=True)
    )

    assert work_map[
        "source_entity_id"
    ].is_unique

    # Every newly created W must contain the same number of
    # current targets recorded by its aggregation decision.
    current_per_w = (
        new_map[
            new_map[
                "membership_role"
            ].eq(
                "current_analysis_target"
            )
        ]
        .groupby(
            "project_work_id"
        )
        .size()
    )

    expected_current_per_w = dict(
        zip(
            new_works[
                "project_work_id"
            ],
            newly_eligible[
                "current_target_count"
            ].astype(int),
        )
    )

    assert (
        current_per_w.to_dict()
        == expected_current_per_w
    )

    # ---------------------------------------------------------
    # Remaining pending units
    # ---------------------------------------------------------

    pending = d4[
        d4[
            "aggregation_decision"
        ].eq(
            "MANUAL_REVIEW_REQUIRED"
        )
    ]

    assert len(pending) == EXPECTED_PENDING_UNITS

    pending_anchors = set(
        pending[
            "unit_anchor_entity_id"
        ]
    )

    pending_members = members[
        members[
            "unit_anchor_entity_id"
        ].isin(
            pending_anchors
        )
    ]

    pending_current = pending_members[
        pending_members[
            "is_current_target"
        ]
    ]

    pending_external = pending_members[
        ~pending_members[
            "is_current_target"
        ]
    ]

    assert (
        len(pending_current)
        == EXPECTED_PENDING_CURRENT_TARGETS
    )

    # Nothing intentionally held may have been assigned.
    assert not (
        set(
            pending_members[
                "entity_id"
            ]
        )
        & set(
            work_map[
                "source_entity_id"
            ]
        )
    )

    # ---------------------------------------------------------
    # Complete accounting of all current OL targets
    # ---------------------------------------------------------

    assigned_current = set(
        work_map.loc[
            work_map[
                "membership_role"
            ].eq(
                "current_analysis_target"
            ),
            "source_entity_id",
        ]
    )

    pending_current_ids = set(
        pending_current[
            "entity_id"
        ]
    )

    assert (
        len(assigned_current)
        == EXPECTED_TOTAL_CURRENT_TARGETS
    )

    assert (
        len(pending_current_ids)
        == EXPECTED_PENDING_CURRENT_TARGETS
    )

    assert not (
        assigned_current
        & pending_current_ids
    )

    assert (
        len(
            assigned_current
            | pending_current_ids
        )
        == EXPECTED_ALL_CURRENT_TARGETS
    )

    assert (
        EXPECTED_TOTAL_CURRENT_TARGETS
        + EXPECTED_PENDING_CURRENT_TARGETS
        == EXPECTED_ALL_CURRENT_TARGETS
    )

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
        "release": "project-works-v4",
        "created_at": CREATED_AT,
        "semantics": {
            "previous_release": "project-works-v3",
            "append_only": (
                "All v3 project-work IDs and membership "
                "rows are preserved exactly. Only the 433 "
                "units newly accepted by aggregation "
                "decisions v4 are appended."
            ),
            "new_w_range": (
                "W000031654-W000032086"
            ),
            "held_units_are_intentionally_unresolved": True,
            "important_note": (
                "The 761 remaining aggregation units are "
                "not assigned project W IDs in this release."
            ),
        },
        "inputs": {
            "previous_project_works": {
                "artifact": (
                    "derived/identity/"
                    "project_works_v3.parquet"
                ),
                "sha256": sha256_file(
                    PREVIOUS_WORKS
                ),
            },
            "previous_work_identity_map": {
                "artifact": (
                    "derived/identity/"
                    "work_identity_map_v3.parquet"
                ),
                "sha256": sha256_file(
                    PREVIOUS_MAP
                ),
            },
            "aggregation_decisions_v3": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_decisions_v3.parquet"
                ),
                "sha256": sha256_file(
                    DECISIONS_V3
                ),
            },
            "aggregation_decisions_v4": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_decisions_v4.parquet"
                ),
                "sha256": sha256_file(
                    DECISIONS_V4
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
            "llm_adjudication": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_llm_review_"
                    "adjudication_v1.parquet"
                ),
                "sha256": sha256_file(
                    ADJUDICATION
                ),
            },
            "aggregation_policy": {
                "artifact": (
                    "docs/AGGREGATION_POLICY.md"
                ),
                "sha256": sha256_file(
                    POLICY
                ),
            },
            "llm_review_methodology": {
                "artifact": (
                    "docs/AGGREGATION_LLM_REVIEW.md"
                ),
                "sha256": sha256_file(
                    LLM_REVIEW_DOC
                ),
            },
        },
        "counts": {
            "previous_project_works": (
                EXPECTED_PREVIOUS_WORKS
            ),
            "new_project_works": (
                EXPECTED_NEW_WORKS
            ),
            "project_works": (
                EXPECTED_TOTAL_WORKS
            ),
            "previous_membership_rows": (
                EXPECTED_PREVIOUS_MAP_ROWS
            ),
            "new_membership_rows": (
                len(new_map)
            ),
            "work_identity_map_rows": (
                len(work_map)
            ),
            "new_current_target_members": (
                EXPECTED_NEW_CURRENT_TARGETS
            ),
            "new_external_members": (
                new_external_entities
            ),
            "current_target_members": (
                EXPECTED_TOTAL_CURRENT_TARGETS
            ),
            "pending_units_without_w_id": (
                EXPECTED_PENDING_UNITS
            ),
            "pending_current_targets": (
                EXPECTED_PENDING_CURRENT_TARGETS
            ),
            "pending_external_entities": (
                len(pending_external)
            ),
            "pending_member_entities": (
                len(pending_members)
            ),
        },
        "id_range": {
            "first": "W000000001",
            "previous_last": "W000031653",
            "first_new": "W000031654",
            "last": "W000032086",
        },
        "outputs": {
            "project_works_tsv": (
                "derived/identity/"
                "project_works_v4.tsv"
            ),
            "project_works_parquet": (
                "derived/identity/"
                "project_works_v4.parquet"
            ),
            "work_identity_map_tsv": (
                "derived/identity/"
                "work_identity_map_v4.tsv"
            ),
            "work_identity_map_parquet": (
                "derived/identity/"
                "work_identity_map_v4.parquet"
            ),
        },
    }

    manifest[
        "outputs"
    ]["project_works_tsv_sha256"] = (
        sha256_file(
            OUT_WORKS_TSV
        )
    )

    manifest[
        "outputs"
    ]["project_works_parquet_sha256"] = (
        sha256_file(
            OUT_WORKS_PARQUET
        )
    )

    manifest[
        "outputs"
    ]["work_identity_map_tsv_sha256"] = (
        sha256_file(
            OUT_MAP_TSV
        )
    )

    manifest[
        "outputs"
    ]["work_identity_map_parquet_sha256"] = (
        sha256_file(
            OUT_MAP_PARQUET
        )
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

    print("=== PROJECT WORKS V4 ===")
    print(
        "previous works:",
        len(previous_works),
    )
    print(
        "new works:",
        len(new_works),
    )
    print(
        "total works:",
        len(works),
    )

    print("\n=== NEW W RANGE ===")
    print(
        new_works.iloc[0][
            "project_work_id"
        ],
        "->",
        new_works.iloc[-1][
            "project_work_id"
        ],
    )

    print("\n=== NEW MEMBERSHIP ===")
    print(
        "rows:",
        len(new_map),
    )
    print(
        new_map[
            "membership_role"
        ]
        .value_counts()
        .to_string()
    )

    print("\n=== TOTAL CURRENT TARGET MEMBERS ===")
    print(
        len(assigned_current)
    )

    print("\n=== REMAINING PENDING ===")
    print(
        "units:",
        len(pending),
    )
    print(
        "current targets:",
        len(pending_current),
    )
    print(
        "external entities:",
        len(pending_external),
    )
    print(
        "member entities:",
        len(pending_members),
    )

    print("\n=== FULL OL ACCOUNTING ===")
    print(
        "assigned:",
        len(assigned_current),
    )
    print(
        "pending:",
        len(pending_current_ids),
    )
    print(
        "total:",
        len(
            assigned_current
            | pending_current_ids
        ),
    )

    print("\n=== OUTPUT SHA256 ===")
    print(
        "project works tsv:",
        sha256_file(
            OUT_WORKS_TSV
        ),
    )
    print(
        "project works parquet:",
        sha256_file(
            OUT_WORKS_PARQUET
        ),
    )
    print(
        "identity map tsv:",
        sha256_file(
            OUT_MAP_TSV
        ),
    )
    print(
        "identity map parquet:",
        sha256_file(
            OUT_MAP_PARQUET
        ),
    )
    print(
        "manifest:",
        sha256_file(
            OUT_MANIFEST
        ),
    )


if __name__ == "__main__":
    main()
