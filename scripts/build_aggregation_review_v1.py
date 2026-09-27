from collections import Counter, defaultdict
from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

ENTITIES = (
    ROOT / "derived/identity/source_entities_v2.parquet"
)

ASSERTIONS = (
    ROOT / "derived/identity/identity_assertions_v1.parquet"
)

TARGETS = (
    ROOT / "derived/identity/openlibrary_analysis_targets_v1.parquet"
)

OUT_DIR = ROOT / "derived/identity"

OUT_UNITS_TSV = (
    OUT_DIR / "aggregation_review_units_v1.tsv"
)

OUT_UNITS_PARQUET = (
    OUT_DIR / "aggregation_review_units_v1.parquet"
)

OUT_MEMBERS_TSV = (
    OUT_DIR / "aggregation_review_members_v1.tsv"
)

OUT_MEMBERS_PARQUET = (
    OUT_DIR / "aggregation_review_members_v1.parquet"
)

OUT_MANIFEST = (
    OUT_DIR / "aggregation_review_v1_manifest.json"
)

CREATED_AT = "2026-09-27"

EXPECTED_CURRENT_TARGETS = 34789
EXPECTED_ASSERTIONS_ALL = 16065
EXPECTED_ASSERTIONS_CURRENT = 16064
EXPECTED_UNITS = 32847
EXPECTED_MEMBERS = 48189


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


def classify(
    current_ol_count: int,
    goodreads_count: int,
    wikidata_count: int,
) -> str:

    if goodreads_count > 1 or wikidata_count > 1:
        return "cross_source_conflict"

    if current_ol_count > 1:
        return "multi_ol_no_explicit_split"

    if (
        current_ol_count == 1
        and goodreads_count == 1
        and wikidata_count == 1
    ):
        return "single_ol_cross_source_corroborated"

    if (
        current_ol_count == 1
        and goodreads_count + wikidata_count == 1
    ):
        return "single_ol_single_external_source"

    raise ValueError(
        "Unexpected connected component shape: "
        f"OL={current_ol_count}, "
        f"GR={goodreads_count}, "
        f"WD={wikidata_count}"
    )


def main() -> None:
    for p in [
        ENTITIES,
        ASSERTIONS,
        TARGETS,
    ]:
        require(p)

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    ent = pd.read_parquet(
        ENTITIES
    ).fillna("")

    assertions = pd.read_parquet(
        ASSERTIONS
    ).fillna("")

    targets = pd.read_parquet(
        TARGETS
    ).fillna("")

    assert len(targets) == EXPECTED_CURRENT_TARGETS
    assert len(assertions) == EXPECTED_ASSERTIONS_ALL

    assert ent["entity_id"].is_unique
    assert targets["current_entity_id"].is_unique

    current_targets = set(
        targets["current_entity_id"]
    )

    meta = ent.set_index("entity_id")[
        [
            "source",
            "source_namespace",
            "source_id",
        ]
    ].to_dict("index")

    # ---------------------------------------------------------
    # Current aggregation graph
    #
    # Source-level assertions remain preserved in
    # identity_assertions_v1, but only assertions whose
    # left OL entity is a current analysis target participate
    # in this release's aggregation review graph.
    # ---------------------------------------------------------

    current_assertions = assertions[
        assertions["left_entity_id"].isin(
            current_targets
        )
    ].copy()

    excluded_assertions = assertions[
        ~assertions["left_entity_id"].isin(
            current_targets
        )
    ].copy()

    assert len(current_assertions) == EXPECTED_ASSERTIONS_CURRENT

    assert len(excluded_assertions) == 1

    assert (
        excluded_assertions.iloc[0]["assertion_id"]
        == "A000009386"
    )

    # ---------------------------------------------------------
    # Union-find
    # ---------------------------------------------------------

    parent = {}
    rank = {}

    def add(x):
        if x not in parent:
            parent[x] = x
            rank[x] = 0

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        add(x)
        add(y)

        rx = find(x)
        ry = find(y)

        if rx == ry:
            return

        if rank[rx] < rank[ry]:
            rx, ry = ry, rx

        parent[ry] = rx

        if rank[rx] == rank[ry]:
            rank[rx] += 1

    for r in current_assertions.itertuples(
        index=False
    ):
        union(
            r.left_entity_id,
            r.right_entity_id,
        )

    components = defaultdict(set)

    for entity_id in parent:
        components[find(entity_id)].add(
            entity_id
        )

    # assertion IDs per graph component
    component_assertions = defaultdict(list)

    for r in current_assertions.itertuples(
        index=False
    ):
        root = find(r.left_entity_id)

        assert (
            find(r.right_entity_id)
            == root
        )

        component_assertions[root].append(
            r.assertion_id
        )

    # ---------------------------------------------------------
    # Build connected units
    # ---------------------------------------------------------

    unit_rows = []
    member_rows = []

    source_order = {
        "openlibrary": 0,
        "goodreads": 1,
        "wikidata": 2,
    }

    for root, nodes in components.items():
        current_ol = sorted(
            x
            for x in nodes
            if x in current_targets
        )

        assert current_ol

        goodreads = sorted(
            x
            for x in nodes
            if meta[x]["source"] == "goodreads"
        )

        wikidata = sorted(
            x
            for x in nodes
            if meta[x]["source"] == "wikidata"
        )

        # No non-current OL source entity should enter the
        # current graph because the left side was filtered
        # before union-find.
        all_ol = sorted(
            x
            for x in nodes
            if meta[x]["source"] == "openlibrary"
        )

        assert all_ol == current_ol

        cls = classify(
            len(current_ol),
            len(goodreads),
            len(wikidata),
        )

        anchor = min(current_ol)

        assertion_ids = sorted(
            component_assertions[root]
        )

        unit_rows.append(
            {
                "unit_anchor_entity_id": anchor,
                "structural_class": cls,
                "current_target_count": (
                    len(current_ol)
                ),
                "goodreads_entity_count": (
                    len(goodreads)
                ),
                "wikidata_entity_count": (
                    len(wikidata)
                ),
                "assertion_count": (
                    len(assertion_ids)
                ),
                "member_entity_count": (
                    len(nodes)
                ),
                "assertion_ids": json.dumps(
                    assertion_ids,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "created_at": CREATED_AT,
            }
        )

        for entity_id in sorted(
            nodes,
            key=lambda x: (
                source_order[
                    meta[x]["source"]
                ],
                meta[x]["source_id"],
                x,
            ),
        ):
            m = meta[entity_id]

            is_current = (
                entity_id in current_targets
            )

            role = (
                "current_analysis_target"
                if is_current
                else "accepted_external_identity"
            )

            member_rows.append(
                {
                    "unit_anchor_entity_id": anchor,
                    "entity_id": entity_id,
                    "source": m["source"],
                    "source_namespace": (
                        m["source_namespace"]
                    ),
                    "source_id": m["source_id"],
                    "member_role": role,
                    "is_current_target": is_current,
                    "created_at": CREATED_AT,
                }
            )

    # ---------------------------------------------------------
    # Add current targets with no accepted external assertion
    # as singleton provisional units.
    # ---------------------------------------------------------

    covered_targets = set(
        current_assertions[
            "left_entity_id"
        ]
    )

    unmatched_targets = sorted(
        current_targets - covered_targets
    )

    assert len(unmatched_targets) == 23295

    for entity_id in unmatched_targets:
        m = meta[entity_id]

        assert m["source"] == "openlibrary"

        unit_rows.append(
            {
                "unit_anchor_entity_id": entity_id,
                "structural_class": (
                    "no_accepted_external_identity"
                ),
                "current_target_count": 1,
                "goodreads_entity_count": 0,
                "wikidata_entity_count": 0,
                "assertion_count": 0,
                "member_entity_count": 1,
                "assertion_ids": "[]",
                "created_at": CREATED_AT,
            }
        )

        member_rows.append(
            {
                "unit_anchor_entity_id": entity_id,
                "entity_id": entity_id,
                "source": m["source"],
                "source_namespace": (
                    m["source_namespace"]
                ),
                "source_id": m["source_id"],
                "member_role": (
                    "current_analysis_target"
                ),
                "is_current_target": True,
                "created_at": CREATED_AT,
            }
        )

    units = pd.DataFrame(unit_rows)

    members = pd.DataFrame(member_rows)

    # ---------------------------------------------------------
    # Deterministic ordering
    # ---------------------------------------------------------

    units = units.sort_values(
        [
            "unit_anchor_entity_id",
        ],
        kind="stable",
    ).reset_index(drop=True)

    members["_source_order"] = (
        members["source"]
        .map(source_order)
    )

    members = members.sort_values(
        [
            "unit_anchor_entity_id",
            "_source_order",
            "source_id",
            "entity_id",
        ],
        kind="stable",
    ).drop(
        columns=["_source_order"]
    ).reset_index(drop=True)

    # ---------------------------------------------------------
    # Validation
    # ---------------------------------------------------------

    assert len(units) == EXPECTED_UNITS
    assert len(members) == EXPECTED_MEMBERS

    assert units[
        "unit_anchor_entity_id"
    ].is_unique

    assert members["entity_id"].is_unique

    assert set(
        units["unit_anchor_entity_id"]
    ).issubset(current_targets)

    current_member_rows = members[
        members["is_current_target"]
    ]

    assert len(current_member_rows) == EXPECTED_CURRENT_TARGETS

    assert set(
        current_member_rows["entity_id"]
    ) == current_targets

    # No historical/non-current OL entity leaks into membership.
    ol_members = members[
        members["source"].eq("openlibrary")
    ]

    assert set(
        ol_members["entity_id"]
    ) == current_targets

    component_counts = (
        units["structural_class"]
        .value_counts()
        .to_dict()
    )

    expected_component_counts = {
        "no_accepted_external_identity": 23295,
        "single_ol_single_external_source": 5090,
        "single_ol_cross_source_corroborated": 3154,
        "multi_ol_no_explicit_split": 1294,
        "cross_source_conflict": 14,
    }

    assert component_counts == expected_component_counts

    target_counts = (
        units.groupby(
            "structural_class"
        )["current_target_count"]
        .sum()
        .to_dict()
    )

    expected_target_counts = {
        "no_accepted_external_identity": 23295,
        "single_ol_single_external_source": 5090,
        "single_ol_cross_source_corroborated": 3154,
        "multi_ol_no_explicit_split": 3204,
        "cross_source_conflict": 46,
    }

    assert target_counts == expected_target_counts

    assert (
        units["current_target_count"].sum()
        == EXPECTED_CURRENT_TARGETS
    )

    assert (
        units["assertion_count"].sum()
        == EXPECTED_ASSERTIONS_CURRENT
    )

    assert (
        members[
            "member_role"
        ].value_counts().to_dict()
        == {
            "current_analysis_target": 34789,
            "accepted_external_identity": 13400,
        }
    )

    # ---------------------------------------------------------
    # Write release
    # ---------------------------------------------------------

    write_atomic_tsv(
        units,
        OUT_UNITS_TSV,
    )

    write_atomic_parquet(
        units,
        OUT_UNITS_PARQUET,
    )

    write_atomic_tsv(
        members,
        OUT_MEMBERS_TSV,
    )

    write_atomic_parquet(
        members,
        OUT_MEMBERS_PARQUET,
    )

    manifest = {
        "release": "aggregation-review-v1",
        "created_at": CREATED_AT,
        "semantics": {
            "unit_definition": (
                "A provisional aggregation unit formed from "
                "current Open Library analysis targets and "
                "accepted source-specific SAME assertions."
            ),
            "unit_anchor_entity_id": (
                "The lexically smallest current Open Library "
                "entity_id in the unit. It is a deterministic "
                "release-local anchor and is not a conceptual "
                "work identifier."
            ),
            "important_note": (
                "These units are not project conceptual works. "
                "No W identifiers are assigned in this release, "
                "and connected components must not be interpreted "
                "as validated conceptual-work counts."
            ),
            "assertion_projection": (
                "Only identity assertions whose left_entity_id "
                "is a current Open Library analysis target are "
                "included in the aggregation graph. Historical "
                "source-level assertions remain preserved in "
                "identity_assertions_v1."
            ),
        },
        "inputs": {
            "source_entities": {
                "artifact": (
                    "derived/identity/"
                    "source_entities_v2.parquet"
                ),
                "sha256": sha256_file(
                    ENTITIES
                ),
            },
            "identity_assertions": {
                "artifact": (
                    "derived/identity/"
                    "identity_assertions_v1.parquet"
                ),
                "sha256": sha256_file(
                    ASSERTIONS
                ),
                "all_assertions": (
                    EXPECTED_ASSERTIONS_ALL
                ),
                "included_current_target_assertions": (
                    EXPECTED_ASSERTIONS_CURRENT
                ),
                "excluded_assertion_ids": [
                    "A000009386"
                ],
            },
            "analysis_targets": {
                "artifact": (
                    "derived/identity/"
                    "openlibrary_analysis_targets_v1.parquet"
                ),
                "sha256": sha256_file(
                    TARGETS
                ),
                "current_targets": (
                    EXPECTED_CURRENT_TARGETS
                ),
            },
        },
        "counts": {
            "provisional_units": (
                EXPECTED_UNITS
            ),
            "membership_rows": (
                EXPECTED_MEMBERS
            ),
            "current_analysis_targets": (
                EXPECTED_CURRENT_TARGETS
            ),
            "accepted_external_entities_in_units": (
                13400
            ),
            "structural_class_units": (
                expected_component_counts
            ),
            "structural_class_current_targets": (
                expected_target_counts
            ),
        },
        "outputs": {
            "units_tsv": (
                "derived/identity/"
                "aggregation_review_units_v1.tsv"
            ),
            "units_parquet": (
                "derived/identity/"
                "aggregation_review_units_v1.parquet"
            ),
            "members_tsv": (
                "derived/identity/"
                "aggregation_review_members_v1.tsv"
            ),
            "members_parquet": (
                "derived/identity/"
                "aggregation_review_members_v1.parquet"
            ),
        },
    }

    manifest["outputs"]["units_tsv_sha256"] = (
        sha256_file(OUT_UNITS_TSV)
    )

    manifest[
        "outputs"
    ]["units_parquet_sha256"] = (
        sha256_file(OUT_UNITS_PARQUET)
    )

    manifest["outputs"]["members_tsv_sha256"] = (
        sha256_file(OUT_MEMBERS_TSV)
    )

    manifest[
        "outputs"
    ]["members_parquet_sha256"] = (
        sha256_file(OUT_MEMBERS_PARQUET)
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

    print("=== AGGREGATION REVIEW V1 ===")
    print("units:", len(units))
    print("members:", len(members))

    print("\n=== UNIT COUNTS ===")
    print(
        units["structural_class"]
        .value_counts()
        .to_string()
    )

    print("\n=== CURRENT TARGET COUNTS ===")
    print(
        units.groupby(
            "structural_class"
        )["current_target_count"]
        .sum()
        .sort_values(
            ascending=False
        )
        .to_string()
    )

    print("\n=== MEMBER ROLES ===")
    print(
        members["member_role"]
        .value_counts()
        .to_string()
    )

    print("\n=== ASSERTION PROJECTION ===")
    print(
        "included:",
        len(current_assertions),
    )
    print(
        "excluded:",
        len(excluded_assertions),
    )
    print(
        "excluded IDs:",
        ",".join(
            excluded_assertions[
                "assertion_id"
            ].tolist()
        ),
    )

    print("\n=== OUTPUT SHA256 ===")
    print(
        "units tsv:",
        sha256_file(OUT_UNITS_TSV),
    )
    print(
        "units parquet:",
        sha256_file(OUT_UNITS_PARQUET),
    )
    print(
        "members tsv:",
        sha256_file(OUT_MEMBERS_TSV),
    )
    print(
        "members parquet:",
        sha256_file(OUT_MEMBERS_PARQUET),
    )
    print(
        "manifest:",
        sha256_file(OUT_MANIFEST),
    )


if __name__ == "__main__":
    main()
