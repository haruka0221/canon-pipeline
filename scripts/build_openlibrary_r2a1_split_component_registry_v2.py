#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

V1 = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_component_registry_v1"
    / "openlibrary_r2a1_split_component_registry_v1.tsv"
)

HUMAN = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_human_audit_adjudication_v1"
    / "openlibrary_r2a1_split_edition_human_audit_adjudication_v1.tsv"
)

ROUTING_INPUT = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_routing_input_v1"
    / "openlibrary_r2a1_split_edition_routing_input_v1.tsv"
)

OUT_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_component_registry_v2"
)

OUT_REGISTRY = (
    OUT_DIR
    / "openlibrary_r2a1_split_component_registry_v2.tsv"
)

OUT_CHANGES = (
    OUT_DIR
    / "openlibrary_r2a1_split_component_registry_v2_changes.tsv"
)

OUT_AFFECTED = (
    OUT_DIR
    / "openlibrary_r2a1_split_component_registry_v2_affected_projects.tsv"
)

OUT_AUDIT = (
    OUT_DIR
    / "openlibrary_r2a1_split_component_registry_v2_audit.json"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openlibrary_r2a1_split_component_registry_v2_manifest.json"
)


RELEASE = (
    "openlibrary-r2a1-split-component-registry-v2"
)

CREATED_AT = "2026-10-11"

V1_FREEZE_COMMIT = (
    "83cfef1121a61de39b52cf5c91e7c0dd4ad4e7f0"
)

HUMAN_FREEZE_COMMIT = (
    "655d2e521487d4cf8e34c435ac419a86a9a353be"
)

COMPARISON_FREEZE_COMMIT = (
    "e0e88e5e29346f49e38a4b79ea830e485c141c3e"
)

EXPECTED_V1 = 82
EXPECTED_V2 = 88
EXPECTED_ISSUES = 6
EXPECTED_AFFECTED_PROJECTS = 6
EXPECTED_AFFECTED_EDITIONS = 191


def sha256_file(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def atomic_tsv(df, path):
    tmp = path.with_name(
        path.name + ".tmp"
    )

    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    os.replace(
        tmp,
        path,
    )


def atomic_json(obj, path):
    tmp = path.with_name(
        path.name + ".tmp"
    )

    tmp.write_text(
        json.dumps(
            obj,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    os.replace(
        tmp,
        path,
    )


def main():

    for p in [
        V1,
        HUMAN,
        ROUTING_INPUT,
    ]:
        if not p.exists():
            raise FileNotFoundError(p)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory already exists: {OUT_DIR}"
        )

    v1 = pd.read_csv(
        V1,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    human = pd.read_csv(
        HUMAN,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    routing = pd.read_csv(
        ROUTING_INPUT,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    assert len(v1) == EXPECTED_V1
    assert v1["component_id"].is_unique

    issues = human.loc[
        human[
            "human_routing_decision"
        ].eq(
            "REGISTRY_ISSUE"
        )
    ].copy()

    assert len(issues) == EXPECTED_ISSUES

    expected_cases = {
        "SERH0004": "W000014024",
        "SERH0012": "W000030498",
        "SERH0019": "W000003023",
        "SERH0048": "W000005682",
        "SERH0084": "W000021761",
        "SERH0112": "W000005423",
    }

    observed_cases = dict(
        zip(
            issues["audit_case_id"],
            issues["project_work_id"],
        )
    )

    assert observed_cases == expected_cases

    assert set(
        issues[
            "human_confidence"
        ]
    ) == {"MEDIUM"}

    # --------------------------------------------------------
    # Carry forward v1 unchanged by default.
    # --------------------------------------------------------

    v2 = v1.copy()

    v2[
        "registry_version"
    ] = "v2"

    v2[
        "registry_change_type"
    ] = "CARRY_FORWARD"

    v2[
        "registry_change_basis_case_id"
    ] = ""

    v2[
        "registry_change_confidence"
    ] = ""

    v2[
        "registry_change_note"
    ] = ""

    changes = []

    def project_template(pid):
        z = v1.loc[
            v1[
                "project_work_id"
            ].eq(pid)
        ]

        assert not z.empty

        return z.iloc[0]

    def add_component(
        pid,
        local_id,
        label,
        role,
        definition,
        case_id,
        note,
    ):
        nonlocal v2

        base = project_template(pid)

        cid = (
            f"{pid}_{local_id}"
        )

        assert cid not in set(
            v2[
                "component_id"
            ]
        )

        row = {
            "remediation_priority_rank":
                base[
                    "remediation_priority_rank"
                ],

            "project_work_id":
                pid,

            "r2_target_title":
                base[
                    "r2_target_title"
                ],

            "r2_target_author":
                base[
                    "r2_target_author"
                ],

            "component_id":
                cid,

            "component_local_id":
                local_id,

            "component_label":
                label,

            "human_role_hint":
                role,

            "component_definition":
                definition,

            "human_resolution_confidence":
                "MEDIUM",

            # Keep the original project-level v1 plan
            # as provenance; v2-specific amendment is
            # recorded in the registry_change_* fields.
            "human_resolution_plan":
                base[
                    "human_resolution_plan"
                ],

            "registry_version":
                "v2",

            "registry_change_type":
                "ADD_COMPONENT",

            "registry_change_basis_case_id":
                case_id,

            "registry_change_confidence":
                "MEDIUM",

            "registry_change_note":
                note,
        }

        v2 = pd.concat(
            [
                v2,
                pd.DataFrame(
                    [row]
                ),
            ],
            ignore_index=True,
        )

        changes.append({
            "change_type":
                "ADD_COMPONENT",

            "project_work_id":
                pid,

            "component_id":
                cid,

            "basis_case_id":
                case_id,

            "change_confidence":
                "MEDIUM",

            "old_value":
                "",

            "new_value":
                definition,

            "change_note":
                note,
        })

    # --------------------------------------------------------
    # 1. Henry James: Selected Letters.
    # --------------------------------------------------------

    add_component(
        "W000014024",
        "C09",
        "Selected Letters",
        "SUCCESSOR",
        (
            "Selected Letters and equivalent bounded "
            "Henry James letter selections distinct from "
            "Letters to A.C. Benson and Auguste Monod "
            "and from A Life in Letters."
        ),
        "SERH0004",
        (
            "Human audit identified the Belknap 1990 "
            "Selected Letters edition as a distinct "
            "letters selection not represented in v1."
        ),
    )

    # --------------------------------------------------------
    # 2. D. H. Lawrence: mixed poetry/non-fiction selection.
    # --------------------------------------------------------

    add_component(
        "W000030498",
        "C07",
        "Selected poetry and non-fictional prose",
        "SUCCESSOR",
        (
            "The Routledge selection explicitly titled "
            "selected poetry and non-fictional prose, "
            "including its clear manifestations. Treat "
            "the mixed publication as one component; "
            "do not split it between poetry and criticism."
        ),
        "SERH0012",
        (
            "Human audit found a mixed poetry/non-fiction "
            "selection not represented by either the "
            "poetry or criticism components."
        ),
    )

    # --------------------------------------------------------
    # 3. Matthew Arnold: keep Everyman's C02 narrow and add
    # a distinct Penguin Poems selection.
    # --------------------------------------------------------

    add_component(
        "W000003023",
        "C04",
        "Poems — Penguin selection",
        "SUCCESSOR",
        (
            "The Penguin Poems selection represented by "
            "the 1985 Penguin edition and clear "
            "manifestations of that publication. This is "
            "kept distinct from the Everyman's lineage "
            "represented by C02."
        ),
        "SERH0019",
        (
            "Conservative remediation: add a distinct "
            "Penguin component rather than broadening "
            "the Everyman's-specific C02 without evidence "
            "that the selections are the same."
        ),
    )

    # --------------------------------------------------------
    # 4. Rimbaud: correct C04 and add Arabic poetry edition.
    # --------------------------------------------------------

    rimbaud_c04 = (
        v2[
            "component_id"
        ].eq(
            "W000005682_C04"
        )
    )

    assert rimbaud_c04.sum() == 1

    old_def = (
        v2.loc[
            rimbaud_c04,
            "component_definition",
        ].iloc[0]
    )

    new_def = (
        "Critical or biographical studies such as "
        "une étude and Leben und Dichtung. This "
        "component does not include editions or "
        "translations of Rimbaud's poetry."
    )

    v2.loc[
        rimbaud_c04,
        "component_definition",
    ] = new_def

    v2.loc[
        rimbaud_c04,
        "registry_change_type",
    ] = "MODIFY_DEFINITION"

    v2.loc[
        rimbaud_c04,
        "registry_change_basis_case_id",
    ] = "SERH0048"

    v2.loc[
        rimbaud_c04,
        "registry_change_confidence",
    ] = "MEDIUM"

    v2.loc[
        rimbaud_c04,
        "registry_change_note",
    ] = (
        "Remove Al Athar Al-Shi'rya from the secondary-"
        "study definition after human review identified "
        "it as a poetry edition/translation."
    )

    changes.append({
        "change_type":
            "MODIFY_DEFINITION",

        "project_work_id":
            "W000005682",

        "component_id":
            "W000005682_C04",

        "basis_case_id":
            "SERH0048",

        "change_confidence":
            "MEDIUM",

        "old_value":
            old_def,

        "new_value":
            new_def,

        "change_note":
            (
                "Human audit found that Al Athar "
                "Al-Shi'rya should not be treated as "
                "secondary scholarship."
            ),
    })

    add_component(
        "W000005682",
        "C05",
        "Al Athar Al-Shi'rya — Arabic poetry edition",
        "SUCCESSOR",
        (
            "The UNESCO Arabic poetry edition titled "
            "Al Athar Al-Shi'rya and clear manifestations "
            "of that publication. Do not infer from the "
            "available metadata alone that it is identical "
            "to the complete-works or selected-works "
            "components."
        ),
        "SERH0048",
        (
            "Conservative remediation: represent the "
            "Arabic poetry edition separately rather "
            "than forcing it into C01 or C02."
        ),
    )

    # --------------------------------------------------------
    # 5. Robert Graves: 1938 Collected Poems.
    # --------------------------------------------------------

    add_component(
        "W000021761",
        "C07",
        "Collected Poems (1938)",
        "SUCCESSOR",
        (
            "The 1938 Random House Collected Poems and "
            "clear manifestations of that collection, "
            "distinct from Collected Poems 1914-1947 "
            "and from later collected/complete-poems "
            "collections."
        ),
        "SERH0084",
        (
            "Human audit identified the 1938 collection "
            "as absent from the v1 component registry."
        ),
    )

    # --------------------------------------------------------
    # 6. Stevenson: mixed Caedmon audio publication.
    # --------------------------------------------------------

    add_component(
        "W000005423",
        "C07",
        "His Poetry, Prose and the Story of His Life — audio",
        "DETACH",
        (
            "The Caedmon audio publication His Poetry, "
            "Prose and the Story of His Life. Treat the "
            "mixed audio publication as one component; "
            "do not split it into constituent poetry, "
            "prose, or biographical material."
        ),
        "SERH0112",
        (
            "Human audit identified a mixed non-print "
            "publication not represented by the poetry "
            "or prose components; detach it from the "
            "erroneous predecessor poetry grouping."
        ),
    )

    # --------------------------------------------------------
    # QC.
    # --------------------------------------------------------

    assert len(v2) == EXPECTED_V2
    assert v2["component_id"].is_unique

    assert len(changes) == 7

    added = v2.loc[
        v2[
            "registry_change_type"
        ].eq(
            "ADD_COMPONENT"
        )
    ]

    modified = v2.loc[
        v2[
            "registry_change_type"
        ].eq(
            "MODIFY_DEFINITION"
        )
    ]

    assert len(added) == 6
    assert len(modified) == 1

    affected_projects = sorted(
        set(
            issues[
                "project_work_id"
            ]
        )
    )

    assert (
        len(
            affected_projects
        )
        == EXPECTED_AFFECTED_PROJECTS
    )

    affected = (
        routing.loc[
            routing[
                "project_work_id"
            ].isin(
                affected_projects
            )
        ]
        .groupby(
            [
                "remediation_priority_rank",
                "project_work_id",
                "r2_target_title",
                "r2_target_author",
            ],
            as_index=False,
        )
        .size()
        .rename(
            columns={
                "size":
                    "edition_rows_to_reroute"
            }
        )
    )

    affected[
        "remediation_priority_rank"
    ] = pd.to_numeric(
        affected[
            "remediation_priority_rank"
        ]
    )

    affected = affected.sort_values(
        "remediation_priority_rank",
        kind="stable",
    ).reset_index(
        drop=True
    )

    assert int(
        affected[
            "edition_rows_to_reroute"
        ].sum()
    ) == EXPECTED_AFFECTED_EDITIONS

    # Stable ordering.
    v2[
        "_rank"
    ] = pd.to_numeric(
        v2[
            "remediation_priority_rank"
        ]
    )

    v2[
        "_local_num"
    ] = (
        v2[
            "component_local_id"
        ]
        .str.replace(
            "C",
            "",
            regex=False,
        )
        .astype(int)
    )

    v2 = (
        v2.sort_values(
            [
                "_rank",
                "project_work_id",
                "_local_num",
            ],
            kind="stable",
        )
        .drop(
            columns=[
                "_rank",
                "_local_num",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    changes_df = pd.DataFrame(
        changes
    )

    OUT_DIR.mkdir(
        parents=True,
    )

    atomic_tsv(
        v2,
        OUT_REGISTRY,
    )

    atomic_tsv(
        changes_df,
        OUT_CHANGES,
    )

    atomic_tsv(
        affected,
        OUT_AFFECTED,
    )

    audit = {
        "release":
            RELEASE,

        "audit_status":
            "PASSED",

        "v1_components":
            len(v1),

        "v2_components":
            len(v2),

        "added_components":
            len(added),

        "modified_definitions":
            len(modified),

        "registry_issue_cases":
            len(issues),

        "affected_project_works":
            len(
                affected_projects
            ),

        "affected_edition_rows_to_reroute":
            int(
                affected[
                    "edition_rows_to_reroute"
                ].sum()
            ),

        "all_v1_component_ids_preserved":
            set(
                v1[
                    "component_id"
                ]
            ).issubset(
                set(
                    v2[
                        "component_id"
                    ]
                )
            ),

        "component_ids_unique":
            bool(
                v2[
                    "component_id"
                ].is_unique
            ),
    }

    atomic_json(
        audit,
        OUT_AUDIT,
    )

    manifest = {
        "release":
            RELEASE,

        "status":
            "human_defined_routing_component_registry",

        "created_at":
            CREATED_AT,

        "v1_freeze_commit":
            V1_FREEZE_COMMIT,

        "human_freeze_commit":
            HUMAN_FREEZE_COMMIT,

        "comparison_freeze_commit":
            COMPARISON_FREEZE_COMMIT,

        "semantics": [
            (
                "Registry v2 remediates only the six "
                "REGISTRY_ISSUE cases found in the frozen "
                "human audit."
            ),
            (
                "All v1 component IDs are preserved."
            ),
            (
                "Six new components are added; one existing "
                "Rimbaud component definition is corrected."
            ),
            (
                "Arnold's Penguin Poems edition is kept "
                "separate from the Everyman's component "
                "rather than broadening identity without "
                "evidence."
            ),
            (
                "Rimbaud's Arabic poetry edition is kept "
                "as a distinct component rather than being "
                "forced into complete-works or selected-"
                "works identity."
            ),
            (
                "The affected six project works must be "
                "rerouted in full against registry v2; "
                "individual issue rows are not patched "
                "in isolation."
            ),
            (
                "No project-work IDs, source-entity IDs, "
                "lineage, or scope decisions are created "
                "by this registry release."
            ),
        ],

        "inputs": {
            str(
                V1.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    V1
                ),

            str(
                HUMAN.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    HUMAN
                ),

            str(
                ROUTING_INPUT.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    ROUTING_INPUT
                ),

            str(
                Path(__file__).relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    Path(__file__)
                ),
        },

        "outputs": {
            OUT_REGISTRY.name:
                sha256_file(
                    OUT_REGISTRY
                ),

            OUT_CHANGES.name:
                sha256_file(
                    OUT_CHANGES
                ),

            OUT_AFFECTED.name:
                sha256_file(
                    OUT_AFFECTED
                ),

            OUT_AUDIT.name:
                sha256_file(
                    OUT_AUDIT
                ),
        },
    }

    atomic_json(
        manifest,
        OUT_MANIFEST,
    )

    print(
        "=== SPLIT COMPONENT REGISTRY V2 ==="
    )

    print(
        "v1 components:",
        len(v1),
    )

    print(
        "v2 components:",
        len(v2),
    )

    print(
        "added components:",
        len(added),
    )

    print(
        "modified definitions:",
        len(modified),
    )

    print()
    print(
        "=== CHANGES ==="
    )

    print(
        changes_df[
            [
                "change_type",
                "project_work_id",
                "component_id",
                "basis_case_id",
                "change_note",
            ]
        ].to_string(
            index=False
        )
    )

    print()
    print(
        "=== AFFECTED PROJECTS ==="
    )

    print(
        affected.to_string(
            index=False
        )
    )

    print()
    print(
        "affected edition rows:",
        int(
            affected[
                "edition_rows_to_reroute"
            ].sum()
        ),
    )

    print()
    print(
        "QC STATUS: PASSED"
    )


if __name__ == "__main__":
    main()
