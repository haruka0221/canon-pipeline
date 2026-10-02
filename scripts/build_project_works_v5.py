from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

PREVIOUS_WORKS = (
    ROOT / "derived/identity/project_works_v4.parquet"
)

PREVIOUS_MAP = (
    ROOT / "derived/identity/work_identity_map_v4.parquet"
)

PREVIOUS_MANIFEST = (
    ROOT / "derived/identity/project_works_v4_manifest.json"
)

MERGE_REVIEW = (
    ROOT / "derived/identity/project_work_merge_review_v1.tsv"
)

MERGE_REVIEW_MANIFEST = (
    ROOT
    / "derived/identity/"
    "project_work_merge_review_v1_manifest.json"
)

OUT_DIR = ROOT / "derived/identity"

OUT_LINEAGE_TSV = (
    OUT_DIR / "project_work_lineage_v1.tsv"
)

OUT_LINEAGE_PARQUET = (
    OUT_DIR / "project_work_lineage_v1.parquet"
)

OUT_LINEAGE_MANIFEST = (
    OUT_DIR / "project_work_lineage_v1_manifest.json"
)

OUT_WORKS_TSV = (
    OUT_DIR / "project_works_v5.tsv"
)

OUT_WORKS_PARQUET = (
    OUT_DIR / "project_works_v5.parquet"
)

OUT_MAP_TSV = (
    OUT_DIR / "work_identity_map_v5.tsv"
)

OUT_MAP_PARQUET = (
    OUT_DIR / "work_identity_map_v5.parquet"
)

OUT_MANIFEST = (
    OUT_DIR / "project_works_v5_manifest.json"
)


CREATED_AT = "2026-10-01"

RELEASE = "project-works-v5"
LINEAGE_RELEASE = "project-work-lineage-v1"
DECISION_VERSION = "merge_review_v1"

EXPECTED_PREVIOUS_WORKS = 32086
EXPECTED_PREVIOUS_MAP = 44905

EXPECTED_REVIEW_GROUPS = 3
EXPECTED_PREDECESSORS = 7
EXPECTED_SUCCESSORS = 3

EXPECTED_TOTAL_WORK_ROWS = 32089
EXPECTED_ACTIVE_WORKS = 32082
EXPECTED_SUPERSEDED_WORKS = 7

EXPECTED_CURRENT_TARGETS = 32706
EXPECTED_EXTERNAL_IDENTITIES = 12199
EXPECTED_MAP_ROWS = 44905

FIRST_SUCCESSOR_W = 32087
LAST_SUCCESSOR_W = 32089


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


def read_json(path):
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def write_atomic_tsv(df, path):
    tmp = path.with_name(
        path.name + ".tmp"
    )

    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    os.replace(tmp, path)


def write_atomic_parquet(df, path):
    tmp = path.with_name(
        path.name + ".tmp"
    )

    df.to_parquet(
        tmp,
        index=False,
        engine="pyarrow",
    )

    os.replace(tmp, path)


def write_atomic_json(value, path):
    tmp = path.with_name(
        path.name + ".tmp"
    )

    tmp.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    os.replace(tmp, path)


def git(*args):
    return subprocess.check_output(
        ["git", *args],
        cwd=ROOT,
        text=True,
    ).strip()


def wid(n):
    return f"W{n:09d}"


def main():
    inputs = [
        PREVIOUS_WORKS,
        PREVIOUS_MAP,
        PREVIOUS_MANIFEST,
        MERGE_REVIEW,
        MERGE_REVIEW_MANIFEST,
    ]

    outputs = [
        OUT_LINEAGE_TSV,
        OUT_LINEAGE_PARQUET,
        OUT_LINEAGE_MANIFEST,
        OUT_WORKS_TSV,
        OUT_WORKS_PARQUET,
        OUT_MAP_TSV,
        OUT_MAP_PARQUET,
        OUT_MANIFEST,
    ]

    for path in inputs:
        require(path)

    existing_outputs = [
        path
        for path in outputs
        if path.exists()
    ]

    if existing_outputs:
        raise RuntimeError(
            "Refusing to overwrite existing outputs: "
            + ", ".join(
                str(p.relative_to(ROOT))
                for p in existing_outputs
            )
        )

    # --------------------------------------------------------
    # Runtime provenance before creating outputs.
    # --------------------------------------------------------

    git_commit = git(
        "rev-parse",
        "HEAD",
    )

    git_dirty = bool(
        git(
            "status",
            "--porcelain",
        )
    )

    if git_dirty:
        raise RuntimeError(
            "Repository must be clean before v5 build"
        )

    execution = {
        "git_commit":
            git_commit,
        "git_dirty":
            False,
        "python_version":
            subprocess.check_output(
                [
                    "python",
                    "-c",
                    (
                        "import sys; "
                        "print(sys.version.split()[0])"
                    ),
                ],
                text=True,
            ).strip(),
        "pandas_version":
            pd.__version__,
        "run_started_at_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),
    }

    # --------------------------------------------------------
    # Read frozen inputs.
    # --------------------------------------------------------

    previous_works = pd.read_parquet(
        PREVIOUS_WORKS
    ).fillna("")

    previous_map = pd.read_parquet(
        PREVIOUS_MAP
    ).fillna("")

    review = pd.read_csv(
        MERGE_REVIEW,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    previous_manifest = read_json(
        PREVIOUS_MANIFEST
    )

    review_manifest = read_json(
        MERGE_REVIEW_MANIFEST
    )

    # --------------------------------------------------------
    # Frozen input invariants.
    # --------------------------------------------------------

    assert len(
        previous_works
    ) == EXPECTED_PREVIOUS_WORKS

    assert previous_works[
        "project_work_id"
    ].is_unique

    assert set(
        previous_works["status"]
    ) == {"active"}

    assert (
        previous_works.iloc[-1][
            "project_work_id"
        ]
        == "W000032086"
    )

    assert len(
        previous_map
    ) == EXPECTED_PREVIOUS_MAP

    assert previous_map[
        "source_entity_id"
    ].is_unique

    role_counts = (
        previous_map[
            "membership_role"
        ]
        .value_counts()
        .to_dict()
    )

    assert (
        role_counts[
            "current_analysis_target"
        ]
        == EXPECTED_CURRENT_TARGETS
    )

    assert (
        role_counts[
            "accepted_external_identity"
        ]
        == EXPECTED_EXTERNAL_IDENTITIES
    )

    assert len(
        review
    ) == EXPECTED_REVIEW_GROUPS

    assert review[
        "review_group_id"
    ].is_unique

    assert set(
        review["decision"]
    ) == {"MERGE"}

    assert set(
        review["confidence"]
    ) == {"high"}

    assert set(
        review["decision_version"]
    ) == {DECISION_VERSION}

    assert set(
        review["scope_decision"]
    ) == {"NOT_EVALUATED"}

    assert (
        review_manifest[
            "output"
        ][
            "sha256"
        ]
        == sha256_file(
            MERGE_REVIEW
        )
    )

    # --------------------------------------------------------
    # Deterministic successor assignment.
    # --------------------------------------------------------

    review = (
        review.sort_values(
            "review_group_id",
            kind="stable",
        )
        .reset_index(
            drop=True
        )
    )

    successor_ids = [
        wid(n)
        for n in range(
            FIRST_SUCCESSOR_W,
            LAST_SUCCESSOR_W + 1,
        )
    ]

    assert len(
        successor_ids
    ) == EXPECTED_SUCCESSORS

    assert successor_ids == [
        "W000032087",
        "W000032088",
        "W000032089",
    ]

    existing_w = set(
        previous_works[
            "project_work_id"
        ]
    )

    assert not (
        set(successor_ids)
        & existing_w
    )

    review[
        "successor_project_work_id"
    ] = successor_ids

    predecessor_to_successor = {}
    predecessor_to_group = {}

    lineage_rows = []

    for row in review.to_dict(
        "records"
    ):
        predecessors = [
            x
            for x in row[
                "predecessor_project_work_ids"
            ].split("|")
            if x
        ]

        if len(predecessors) < 2:
            raise RuntimeError(
                "Merge group must contain "
                "at least two predecessors"
            )

        successor = row[
            "successor_project_work_id"
        ]

        for predecessor in predecessors:
            if predecessor not in existing_w:
                raise RuntimeError(
                    "Unknown predecessor W: "
                    f"{predecessor}"
                )

            if (
                predecessor
                in predecessor_to_successor
            ):
                raise RuntimeError(
                    "Predecessor appears in "
                    "multiple merge groups: "
                    f"{predecessor}"
                )

            predecessor_to_successor[
                predecessor
            ] = successor

            predecessor_to_group[
                predecessor
            ] = row[
                "review_group_id"
            ]

            lineage_rows.append(
                {
                    "event_type":
                        "MERGE",

                    "predecessor_project_work_id":
                        predecessor,

                    "successor_project_work_id":
                        successor,

                    "decision_version":
                        DECISION_VERSION,

                    "reason":
                        (
                            "high_confidence_"
                            "duplicate_project_work_"
                            "merge"
                        ),

                    "created_at":
                        CREATED_AT,

                    "review_group_id":
                        row[
                            "review_group_id"
                        ],
                }
            )

    assert len(
        predecessor_to_successor
    ) == EXPECTED_PREDECESSORS

    assert len(
        lineage_rows
    ) == EXPECTED_PREDECESSORS

    predecessor_ids = set(
        predecessor_to_successor
    )

    # --------------------------------------------------------
    # Every predecessor must be a v1 singleton project work
    # with exactly one current OL membership and no external
    # identity membership.
    # --------------------------------------------------------

    pworks = previous_works[
        previous_works[
            "project_work_id"
        ].isin(
            predecessor_ids
        )
    ].copy()

    assert len(
        pworks
    ) == EXPECTED_PREDECESSORS

    assert set(
        pworks[
            "aggregation_decision_version"
        ]
    ) == {"v1"}

    assert set(
        pworks["status"]
    ) == {"active"}

    affected_map = previous_map[
        previous_map[
            "project_work_id"
        ].isin(
            predecessor_ids
        )
    ].copy()

    assert len(
        affected_map
    ) == EXPECTED_PREDECESSORS

    assert set(
        affected_map[
            "membership_role"
        ]
    ) == {
        "current_analysis_target"
    }

    assert affected_map[
        "source_entity_id"
    ].is_unique

    affected_counts = (
        affected_map.groupby(
            "project_work_id"
        )
        .size()
        .to_dict()
    )

    assert set(
        affected_counts
    ) == predecessor_ids

    assert set(
        affected_counts.values()
    ) == {1}

    # --------------------------------------------------------
    # Project-work lineage v1.
    # --------------------------------------------------------

    lineage = pd.DataFrame(
        lineage_rows,
        columns=[
            "event_type",
            "predecessor_project_work_id",
            "successor_project_work_id",
            "decision_version",
            "reason",
            "created_at",
            "review_group_id",
        ],
    )

    lineage = (
        lineage.sort_values(
            [
                "successor_project_work_id",
                "predecessor_project_work_id",
            ],
            kind="stable",
        )
        .reset_index(
            drop=True
        )
    )

    assert lineage[
        "predecessor_project_work_id"
    ].is_unique

    assert set(
        lineage[
            "successor_project_work_id"
        ]
    ) == set(
        successor_ids
    )

    # --------------------------------------------------------
    # project_works_v5:
    # preserve all historical W IDs;
    # mark seven predecessors superseded;
    # append three successor W IDs.
    # --------------------------------------------------------

    works = previous_works.copy()

    works.loc[
        works[
            "project_work_id"
        ].isin(
            predecessor_ids
        ),
        "status",
    ] = "superseded"

    new_work_rows = []

    for row in review.to_dict(
        "records"
    ):
        new_work_rows.append(
            {
                "project_work_id":
                    row[
                        "successor_project_work_id"
                    ],

                # A merge successor does not originate
                # from one provisional aggregation-unit
                # anchor.
                "origin_unit_anchor_entity_id":
                    "",

                "aggregation_decision":
                    "ONE_WORK",

                "aggregation_decision_version":
                    DECISION_VERSION,

                "status":
                    "active",

                "created_at":
                    CREATED_AT,
            }
        )

    new_works = pd.DataFrame(
        new_work_rows,
        columns=list(
            previous_works.columns
        ),
    )

    works = pd.concat(
        [
            works,
            new_works,
        ],
        ignore_index=True,
    )

    assert len(
        works
    ) == EXPECTED_TOTAL_WORK_ROWS

    assert works[
        "project_work_id"
    ].is_unique

    assert (
        works.iloc[-1][
            "project_work_id"
        ]
        == "W000032089"
    )

    assert int(
        works[
            "status"
        ].eq(
            "active"
        ).sum()
    ) == EXPECTED_ACTIVE_WORKS

    assert int(
        works[
            "status"
        ].eq(
            "superseded"
        ).sum()
    ) == EXPECTED_SUPERSEDED_WORKS

    assert set(
        works.loc[
            works[
                "status"
            ].eq(
                "superseded"
            ),
            "project_work_id",
        ]
    ) == predecessor_ids

    # Except for status on the seven predecessors,
    # every v4 project-work field is preserved.
    compare_cols = [
        c
        for c in previous_works.columns
        if c != "status"
    ]

    assert (
        works.iloc[
            :EXPECTED_PREVIOUS_WORKS
        ][
            compare_cols
        ]
        .reset_index(
            drop=True
        )
        .equals(
            previous_works[
                compare_cols
            ].reset_index(
                drop=True
            )
        )
    )

    # --------------------------------------------------------
    # work_identity_map_v5:
    # current-state mapping. The seven affected source
    # entities move from predecessor W to successor W.
    # No source entity is duplicated and row count is stable.
    # --------------------------------------------------------

    work_map = previous_map.copy()

    affected_index = (
        work_map[
            "project_work_id"
        ].isin(
            predecessor_ids
        )
    )

    for idx in work_map.index[
        affected_index
    ]:
        predecessor = work_map.at[
            idx,
            "project_work_id",
        ]

        successor = (
            predecessor_to_successor[
                predecessor
            ]
        )

        work_map.at[
            idx,
            "project_work_id",
        ] = successor

        work_map.at[
            idx,
            "membership_basis",
        ] = (
            "project_work_merge_review_v1:"
            "MERGE"
        )

        work_map.at[
            idx,
            "aggregation_decision_version",
        ] = DECISION_VERSION

        work_map.at[
            idx,
            "created_at",
        ] = CREATED_AT

    assert len(
        work_map
    ) == EXPECTED_MAP_ROWS

    assert work_map[
        "source_entity_id"
    ].is_unique

    new_role_counts = (
        work_map[
            "membership_role"
        ]
        .value_counts()
        .to_dict()
    )

    assert (
        new_role_counts[
            "current_analysis_target"
        ]
        == EXPECTED_CURRENT_TARGETS
    )

    assert (
        new_role_counts[
            "accepted_external_identity"
        ]
        == EXPECTED_EXTERNAL_IDENTITIES
    )

    # No current mapping may point to a superseded W.
    assert not set(
        work_map[
            "project_work_id"
        ]
    ) & predecessor_ids

    active_w = set(
        works.loc[
            works[
                "status"
            ].eq(
                "active"
            ),
            "project_work_id",
        ]
    )

    map_w = set(
        work_map[
            "project_work_id"
        ]
    )

    assert map_w == active_w

    assert len(
        map_w
    ) == EXPECTED_ACTIVE_WORKS

    # Every active W has >=1 current OL target.
    current_map = work_map[
        work_map[
            "membership_role"
        ].eq(
            "current_analysis_target"
        )
    ]

    current_w = set(
        current_map[
            "project_work_id"
        ]
    )

    assert current_w == active_w

    # Successors have exactly 3 / 2 / 2 current OL targets.
    successor_counts = (
        current_map[
            current_map[
                "project_work_id"
            ].isin(
                successor_ids
            )
        ]
        .groupby(
            "project_work_id"
        )
        .size()
        .to_dict()
    )

    assert successor_counts == {
        "W000032087": 3,
        "W000032088": 2,
        "W000032089": 2,
    }

    # All unaffected map rows remain identical.
    unaffected = ~previous_map[
        "project_work_id"
    ].isin(
        predecessor_ids
    )

    assert (
        work_map.loc[
            unaffected
        ]
        .reset_index(
            drop=True
        )
        .equals(
            previous_map.loc[
                unaffected
            ]
            .reset_index(
                drop=True
            )
        )
    )

    # --------------------------------------------------------
    # Write lineage and v5 outputs.
    # --------------------------------------------------------

    write_atomic_tsv(
        lineage,
        OUT_LINEAGE_TSV,
    )

    write_atomic_parquet(
        lineage,
        OUT_LINEAGE_PARQUET,
    )

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

    execution[
        "run_finished_at_utc"
    ] = datetime.now(
        timezone.utc
    ).isoformat()

    # --------------------------------------------------------
    # Lineage manifest.
    # --------------------------------------------------------

    lineage_manifest = {
        "release":
            LINEAGE_RELEASE,

        "created_at":
            CREATED_AT,

        "execution":
            execution,

        "semantics": {
            "event_type":
                "MERGE",

            "historical_policy":
                (
                    "Historical project-work releases "
                    "remain unchanged. Each predecessor "
                    "W is preserved and linked to a new "
                    "successor W."
                ),

            "successor_policy":
                (
                    "A new successor W is issued for "
                    "each merge group rather than "
                    "repurposing a predecessor W."
                ),

            "scope":
                (
                    "Conceptual-work identity only; "
                    "corpus scope is not evaluated."
                ),
        },

        "counts": {
            "lineage_rows":
                len(lineage),

            "merge_groups":
                EXPECTED_REVIEW_GROUPS,

            "predecessor_works":
                EXPECTED_PREDECESSORS,

            "successor_works":
                EXPECTED_SUCCESSORS,
        },

        "inputs": {
            str(
                MERGE_REVIEW.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    MERGE_REVIEW
                ),

            str(
                MERGE_REVIEW_MANIFEST.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    MERGE_REVIEW_MANIFEST
                ),

            str(
                PREVIOUS_WORKS.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    PREVIOUS_WORKS
                ),

            str(
                PREVIOUS_MAP.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    PREVIOUS_MAP
                ),
        },

        "outputs": {
            OUT_LINEAGE_TSV.name:
                sha256_file(
                    OUT_LINEAGE_TSV
                ),

            OUT_LINEAGE_PARQUET.name:
                sha256_file(
                    OUT_LINEAGE_PARQUET
                ),
        },
    }

    write_atomic_json(
        lineage_manifest,
        OUT_LINEAGE_MANIFEST,
    )

    # --------------------------------------------------------
    # project_works_v5 manifest.
    # --------------------------------------------------------

    manifest = {
        "release":
            RELEASE,

        "created_at":
            CREATED_AT,

        "execution":
            execution,

        "semantics": {
            "previous_release":
                "project-works-v4",

            "historical_id_policy":
                (
                    "All 32,086 previously released "
                    "project_work_id values are retained. "
                    "The seven merge predecessors are "
                    "marked superseded, not deleted or "
                    "renumbered."
                ),

            "successor_policy":
                (
                    "Three new successor project works "
                    "W000032087-W000032089 represent "
                    "the accepted merge groups."
                ),

            "work_identity_map_v5":
                (
                    "Current-state membership map. "
                    "The seven affected source entities "
                    "are reassigned from predecessor W "
                    "IDs to their successor W IDs. "
                    "Historical v4 membership remains "
                    "preserved in work_identity_map_v4."
                ),

            "scope_release":
                "not_applied",
        },

        "counts": {
            "project_work_rows":
                len(works),

            "active_project_works":
                EXPECTED_ACTIVE_WORKS,

            "superseded_project_works":
                EXPECTED_SUPERSEDED_WORKS,

            "new_successor_project_works":
                EXPECTED_SUCCESSORS,

            "work_identity_map_rows":
                len(work_map),

            "unique_source_entities":
                work_map[
                    "source_entity_id"
                ].nunique(),

            "current_analysis_targets":
                EXPECTED_CURRENT_TARGETS,

            "accepted_external_identities":
                EXPECTED_EXTERNAL_IDENTITIES,

            "successor_current_target_counts":
                successor_counts,
        },

        "inputs": {
            str(
                PREVIOUS_WORKS.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    PREVIOUS_WORKS
                ),

            str(
                PREVIOUS_MAP.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    PREVIOUS_MAP
                ),

            str(
                PREVIOUS_MANIFEST.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    PREVIOUS_MANIFEST
                ),

            str(
                MERGE_REVIEW.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    MERGE_REVIEW
                ),

            str(
                MERGE_REVIEW_MANIFEST.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    MERGE_REVIEW_MANIFEST
                ),

            str(
                OUT_LINEAGE_MANIFEST.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    OUT_LINEAGE_MANIFEST
                ),
        },

        "outputs": {
            OUT_WORKS_TSV.name:
                sha256_file(
                    OUT_WORKS_TSV
                ),

            OUT_WORKS_PARQUET.name:
                sha256_file(
                    OUT_WORKS_PARQUET
                ),

            OUT_MAP_TSV.name:
                sha256_file(
                    OUT_MAP_TSV
                ),

            OUT_MAP_PARQUET.name:
                sha256_file(
                    OUT_MAP_PARQUET
                ),
        },
    }

    write_atomic_json(
        manifest,
        OUT_MANIFEST,
    )

    print(
        "=== PROJECT WORKS V5 ==="
    )

    print(
        "previous W:",
        EXPECTED_PREVIOUS_WORKS,
    )

    print(
        "new successors:",
        EXPECTED_SUCCESSORS,
    )

    print(
        "total W rows:",
        len(works),
    )

    print(
        "active W:",
        int(
            works[
                "status"
            ].eq(
                "active"
            ).sum()
        ),
    )

    print(
        "superseded W:",
        int(
            works[
                "status"
            ].eq(
                "superseded"
            ).sum()
        ),
    )

    print()
    print(
        "map rows:",
        len(work_map),
    )

    print(
        "current targets:",
        int(
            work_map[
                "membership_role"
            ].eq(
                "current_analysis_target"
            ).sum()
        ),
    )

    print(
        "external identities:",
        int(
            work_map[
                "membership_role"
            ].eq(
                "accepted_external_identity"
            ).sum()
        ),
    )

    print()
    print(
        "successor target counts:",
        successor_counts,
    )

    print()
    print(
        "lineage:",
        OUT_LINEAGE_TSV,
    )

    print(
        "project works:",
        OUT_WORKS_TSV,
    )

    print(
        "work map:",
        OUT_MAP_TSV,
    )

    print(
        "manifest:",
        OUT_MANIFEST,
    )


if __name__ == "__main__":
    main()
