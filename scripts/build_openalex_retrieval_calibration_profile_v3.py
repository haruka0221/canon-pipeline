from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

D = ROOT / "derived/openalex_production"

M1 = (
    D
    / "retrieval_match_registry_v1/"
      "openalex_retrieval_match_registry_v1.parquet"
)

M2D = (
    D
    / "retrieval_match_registry_v2"
)

M2 = (
    M2D
    / "openalex_retrieval_match_registry_v2.parquet"
)

M2M = (
    M2D
    / "openalex_retrieval_match_registry_v2_manifest.json"
)

M2A = (
    M2D
    / "openalex_retrieval_match_registry_v2_audit_v1.json"
)

P2D = (
    D
    / "retrieval_calibration_profile_v2/"
      "full_inventory_57959e90"
)

P2M = (
    P2D
    / "openalex_retrieval_calibration_profile_v2_manifest.json"
)

Q2 = (
    P2D
    / "openalex_query_profile_counts_v2.parquet"
)

TP2 = (
    P2D
    / "openalex_title_pattern_counts_v2.parquet"
)

EV2 = (
    P2D
    / "openalex_a12_candidate_query_evidence_v2.parquet"
)

OA2 = (
    P2D
    / "openalex_a12_candidate_oa_records_v2.parquet"
)

Q2T = (
    P2D
    / "openalex_query_profile_counts_v2.tsv"
)

TP2T = (
    P2D
    / "openalex_title_pattern_counts_v2.tsv"
)

OUT = (
    D
    / "retrieval_calibration_profile_v3/"
      "full_inventory_57959e90"
)

MAPT = (
    OUT
    / "openalex_retrieval_query_semantic_map_v1_to_v2_v1.tsv"
)

MAPP = (
    OUT
    / "openalex_retrieval_query_semantic_map_v1_to_v2_v1.parquet"
)

Q3T = (
    OUT
    / "openalex_query_profile_counts_v3.tsv"
)

Q3P = (
    OUT
    / "openalex_query_profile_counts_v3.parquet"
)

TP3T = (
    OUT
    / "openalex_title_pattern_counts_v3.tsv"
)

TP3P = (
    OUT
    / "openalex_title_pattern_counts_v3.parquet"
)

EV3P = (
    OUT
    / "openalex_a12_candidate_query_evidence_v3.parquet"
)

OA3P = (
    OUT
    / "openalex_a12_candidate_oa_records_v3.parquet"
)

MAN = (
    OUT
    / "openalex_retrieval_calibration_profile_v3_manifest.json"
)


COUNT_COLS = [
    "title_hit_count",
    "title_in_title_count",
    "title_in_abstract_count",
    "title_in_both_count",
    "a1_hit_count",
    "a2_hit_count",
    "a2_reverse_hit_count",
    "a2_incremental_over_a1_count",
    "a3_hit_count",
    "a3_incremental_over_a2_count",
]

QBASE = [
    "query_id",
    "execution_id",
    "target_lane",
    "project_work_id",
    "unresolved_unit_anchor_entity_id",
    "alias_id",
    "query_route",
    "query_form",
    "query_title",
    "query_author",
    "title_match_norm",
    "title_match_token_count",
    "author_a1_norm",
    "author_a2_reverse_norm",
    "author_a3_anchor",
]

SKEY = [
    "execution_id",
    "target_lane",
    "unresolved_unit_anchor_entity_id",
    "alias_id",
    "alias_project_source_entity_id",
    "query_route",
    "query_form",
    "query_title",
    "query_author",
    "title_match_norm",
    "title_match_token_count",
    "author_a1_norm",
    "author_a2_reverse_norm",
    "author_a3_anchor",
]

PSCAN = [
    "title_hit_count",
    "title_in_title_count",
    "title_in_abstract_count",
    "title_in_both_count",
]

PMETA = [
    "logical_query_rows",
    "resolved_w",
    "unresolved_units",
    "raw_title_variant_count",
    "raw_title_examples",
]

EXPECTED_PATTERN_CHANGES = {
    "the english novel": {
        "logical_query_rows": [42, 40],
        "resolved_w": [14, 12],
    },
    "the golden horseshoe": {
        "logical_query_rows": [12, 5],
        "resolved_w": [4, 1],
    },
    "the short story": {
        "logical_query_rows": [18, 17],
        "resolved_w": [6, 5],
    },
}


def sha(path):
    h = hashlib.sha256()

    with Path(path).open("rb") as f:
        for block in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(block)

    return h.hexdigest()


def pq(path):
    return pd.read_parquet(
        path
    ).fillna("")


def js(path):
    return json.loads(
        Path(path).read_text(
            encoding="utf-8"
        )
    )


def rel(path):
    return str(
        Path(path).relative_to(ROOT)
    )


def skey(row):
    return tuple(
        str(row[col])
        for col in SKEY
    )


def write_tsv(df, path):
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


def write_parquet(df, path):
    tmp = path.with_name(
        path.name + ".tmp"
    )

    df.to_parquet(
        tmp,
        index=False,
        engine="pyarrow",
    )

    os.replace(
        tmp,
        path,
    )


def write_json(value, path):
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

    os.replace(
        tmp,
        path,
    )


def main():
    inputs = [
        M1,
        M2,
        M2M,
        M2A,
        P2M,
        Q2,
        TP2,
        EV2,
        OA2,
        Q2T,
        TP2T,
    ]

    for path in inputs:
        if not path.exists():
            raise FileNotFoundError(
                path
            )

    if subprocess.check_output(
        [
            "git",
            "status",
            "--porcelain",
        ],
        cwd=ROOT,
        text=True,
    ).strip():
        raise RuntimeError(
            "worktree must be clean before profile-v3 build"
        )

    if OUT.exists():
        raise RuntimeError(
            f"output exists: {OUT}"
        )

    m2_manifest = js(
        M2M
    )

    m2_audit = js(
        M2A
    )

    p2_manifest = js(
        P2M
    )

    assert (
        m2_manifest["release"]
        == "openalex-retrieval-match-registry-v2"
    )

    assert (
        m2_audit["audit_status"]
        == "PASSED"
    )

    assert (
        m2_audit[
            "reuse_contract"
        ][
            "every_v2_query_has_exactly_one_v1_semantic_equivalent"
        ]
    )

    assert (
        m2_audit[
            "reuse_contract"
        ][
            "snapshot_rescan_required"
        ]
        is False
    )

    assert (
        p2_manifest["release"]
        == "openalex-retrieval-calibration-profile-v2"
    )

    assert (
        p2_manifest[
            "matching_contract_version"
        ]
        == "openalex_snapshot_title_abstract_token_phrase_v1"
    )

    local_profile_outputs = {
        "queries_parquet":
            Q2,
        "patterns_parquet":
            TP2,
        "a12_evidence":
            EV2,
        "a12_records":
            OA2,
        "queries_tsv":
            Q2T,
        "patterns_tsv":
            TP2T,
    }

    for name, path in (
        local_profile_outputs.items()
    ):
        expected = (
            p2_manifest[
                "outputs"
            ][name]["sha256"]
        )

        if sha(path) != expected:
            raise RuntimeError(
                "profile-v2 mirror hash "
                f"mismatch: {name}"
            )

    m1 = pq(
        M1
    )

    m2 = pq(
        M2
    )

    q2 = pq(
        Q2
    )

    tp2 = pq(
        TP2
    )

    ev2 = pq(
        EV2
    )

    oa2 = pq(
        OA2
    )

    assert (
        len(m1),
        len(m2),
        len(q2),
        len(tp2),
        len(ev2),
        len(oa2),
    ) == (
        11008,
        10998,
        11008,
        2858,
        251905,
        73931,
    )

    # --------------------------------------------------------
    # Cross-release scanner-semantic mapping.
    # query_id is intentionally NOT used as the join key.
    # --------------------------------------------------------

    old = {}
    new = {}

    for row in m1.to_dict(
        "records"
    ):
        key = skey(
            row
        )

        assert key not in old

        old[key] = row

    for row in m2.to_dict(
        "records"
    ):
        key = skey(
            row
        )

        assert key not in new

        new[key] = row

    map_rows = []

    for key, new_row in (
        new.items()
    ):
        assert key in old

        old_row = old[
            key
        ]

        old_qid = str(
            old_row[
                "query_id"
            ]
        )

        new_qid = str(
            new_row[
                "query_id"
            ]
        )

        map_rows.append({
            "old_query_id":
                old_qid,

            "new_query_id":
                new_qid,

            "old_project_work_id":
                str(
                    old_row[
                        "project_work_id"
                    ]
                ),

            "new_project_work_id":
                str(
                    new_row[
                        "project_work_id"
                    ]
                ),

            "query_id_changed":
                old_qid
                != new_qid,

            "project_work_id_changed":
                str(
                    old_row[
                        "project_work_id"
                    ]
                )
                != str(
                    new_row[
                        "project_work_id"
                    ]
                ),

            **{
                col:
                    new_row[col]
                for col in SKEY
            },
        })

    mapping = (
        pd.DataFrame(
            map_rows
        )
        .sort_values(
            "new_query_id",
            kind="stable",
        )
        .reset_index(
            drop=True
        )
    )

    assert len(
        mapping
    ) == 10998

    assert int(
        (
            ~mapping[
                "query_id_changed"
            ]
        ).sum()
    ) == 4973

    assert int(
        mapping[
            "query_id_changed"
        ].sum()
    ) == 6025

    assert int(
        mapping[
            "project_work_id_changed"
        ].sum()
    ) == 17

    dropped_keys = (
        set(old)
        - set(new)
    )

    assert len(
        dropped_keys
    ) == 10

    # --------------------------------------------------------
    # Query-profile exact counts.
    # --------------------------------------------------------

    assert q2[
        "query_id"
    ].is_unique

    assert set(
        q2[
            "query_id"
        ]
    ) == set(
        m1[
            "query_id"
        ]
    )

    q2i = q2.set_index(
        "query_id",
        drop=False,
    )

    q3_rows = []

    for new_row in (
        m2.sort_values(
            "query_id",
            kind="stable",
        )
        .to_dict(
            "records"
        )
    ):
        old_row = old[
            skey(
                new_row
            )
        ]

        old_qid = str(
            old_row[
                "query_id"
            ]
        )

        src = q2i.loc[
            old_qid
        ]

        for col in QBASE:
            if (
                col
                == "title_match_token_count"
            ):
                assert int(
                    src[col]
                ) == int(
                    old_row[col]
                )

            else:
                assert str(
                    src[col]
                ) == str(
                    old_row[col]
                )

        out = {
            col:
                new_row[col]
            for col in QBASE
        }

        out[
            "title_match_token_count"
        ] = int(
            out[
                "title_match_token_count"
            ]
        )

        out.update({
            col:
                int(
                    src[col]
                )
            for col in COUNT_COLS
        })

        q3_rows.append(
            out
        )

    q3 = pd.DataFrame(
        q3_rows,
        columns=(
            QBASE
            + COUNT_COLS
        ),
    )

    assert len(
        q3
    ) == 10998

    assert q3[
        "query_id"
    ].is_unique

    # --------------------------------------------------------
    # Title-pattern scan counts + v2 registry metadata.
    # --------------------------------------------------------

    assert tp2[
        "title_match_norm"
    ].is_unique

    tp2i = tp2.set_index(
        "title_match_norm",
        drop=False,
    )

    tp3_rows = []

    for pattern, group in (
        m2.groupby(
            "title_match_norm",
            sort=True,
        )
    ):
        assert (
            pattern
            in tp2i.index
        )

        src = tp2i.loc[
            pattern
        ]

        raw_titles = sorted(
            set(
                group[
                    "query_title"
                ].astype(str)
            )
        )

        out = {
            "title_match_norm":
                pattern,

            "title_match_token_count":
                len(
                    pattern.split()
                ),

            "logical_query_rows":
                len(
                    group
                ),

            "resolved_w":
                group.loc[
                    group[
                        "project_work_id"
                    ].ne(""),
                    "project_work_id",
                ].nunique(),

            "unresolved_units":
                group.loc[
                    group[
                        "unresolved_unit_anchor_entity_id"
                    ].ne(""),
                    "unresolved_unit_anchor_entity_id",
                ].nunique(),

            "raw_title_variant_count":
                len(
                    raw_titles
                ),

            "raw_title_examples":
                " || ".join(
                    raw_titles[:10]
                ),
        }

        out.update({
            col:
                int(
                    src[col]
                )
            for col in PSCAN
        })

        tp3_rows.append(
            out
        )

    tp3 = pd.DataFrame(
        tp3_rows
    )

    assert len(
        tp3
    ) == 2858

    tp3i = tp3.set_index(
        "title_match_norm",
        drop=False,
    )

    changes = {}

    for pattern in tp3[
        "title_match_norm"
    ]:
        before = tp2i.loc[
            pattern
        ]

        after = tp3i.loc[
            pattern
        ]

        diff = {}

        for col in PMETA:
            if str(
                before[col]
            ) != str(
                after[col]
            ):
                a = before[
                    col
                ]

                b = after[
                    col
                ]

                if hasattr(
                    a,
                    "item",
                ):
                    a = a.item()

                if hasattr(
                    b,
                    "item",
                ):
                    b = b.item()

                diff[col] = [
                    a,
                    b,
                ]

        if diff:
            changes[
                pattern
            ] = diff

    assert (
        changes
        == EXPECTED_PATTERN_CHANGES
    ), changes

    # --------------------------------------------------------
    # A1/A2 candidate evidence reprojection.
    # --------------------------------------------------------

    ev = ev2.copy()

    ev[
        "_source_row_order"
    ] = range(
        len(ev)
    )

    map_for_merge = mapping[
        [
            "old_query_id",
            "new_query_id",
            "old_project_work_id",
            "new_project_work_id",
            "execution_id",
            "target_lane",
            "unresolved_unit_anchor_entity_id",
            "alias_id",
            "alias_project_source_entity_id",
            "query_route",
        ]
    ]

    evidence = ev.merge(
        map_for_merge,
        left_on="query_id",
        right_on="old_query_id",
        how="inner",
        validate="many_to_one",
        suffixes=(
            "",
            "_mapped",
        ),
        sort=False,
    )

    assert len(
        evidence
    ) == 251887

    assert (
        len(ev2)
        - len(evidence)
    ) == 18

    assert (
        evidence[
            "project_work_id"
        ].astype(str)
        == evidence[
            "old_project_work_id"
        ].astype(str)
    ).all()

    for col in [
        "execution_id",
        "target_lane",
        "unresolved_unit_anchor_entity_id",
        "alias_id",
        "alias_project_source_entity_id",
        "query_route",
    ]:
        assert (
            evidence[
                col
            ].astype(str)
            == evidence[
                col
                + "_mapped"
            ].astype(str)
        ).all(), col

    changed_evidence_w = int(
        (
            evidence[
                "old_project_work_id"
            ].astype(str)
            != evidence[
                "new_project_work_id"
            ].astype(str)
        ).sum()
    )

    assert (
        changed_evidence_w
        == 34
    )

    evidence_columns = list(
        ev2.columns
    )

    evidence[
        "query_id"
    ] = evidence[
        "new_query_id"
    ]

    evidence[
        "project_work_id"
    ] = evidence[
        "new_project_work_id"
    ]

    ev3 = (
        evidence
        .sort_values(
            "_source_row_order",
            kind="stable",
        )[
            evidence_columns
        ]
        .reset_index(
            drop=True
        )
    )

    assert not ev3[
        [
            "query_id",
            "openalex_work_id",
        ]
    ].duplicated().any()

    # --------------------------------------------------------
    # OA metadata records remain fully referenced.
    # --------------------------------------------------------

    assert oa2[
        "openalex_work_id"
    ].is_unique

    assert set(
        ev3[
            "openalex_work_id"
        ]
    ) == set(
        oa2[
            "openalex_work_id"
        ]
    )

    # --------------------------------------------------------
    # Write artifacts.
    # --------------------------------------------------------

    OUT.mkdir(
        parents=True,
        exist_ok=False,
    )

    write_tsv(
        mapping,
        MAPT,
    )

    write_parquet(
        mapping,
        MAPP,
    )

    write_tsv(
        q3,
        Q3T,
    )

    write_parquet(
        q3,
        Q3P,
    )

    write_tsv(
        tp3,
        TP3T,
    )

    write_parquet(
        tp3,
        TP3P,
    )

    write_parquet(
        ev3,
        EV3P,
    )

    tmp = OA3P.with_name(
        OA3P.name + ".tmp"
    )

    shutil.copyfile(
        OA2,
        tmp,
    )

    os.replace(
        tmp,
        OA3P,
    )

    dropped = []

    for key in sorted(
        dropped_keys
    ):
        row = old[
            key
        ]

        dropped.append({
            col:
                str(
                    row[col]
                )
            for col in [
                "query_id",
                "project_work_id",
                "execution_id",
                "query_route",
                "query_title",
                "query_author",
            ]
        })

    outputs = {
        "semantic_query_map_tsv":
            MAPT,

        "semantic_query_map_parquet":
            MAPP,

        "queries_tsv":
            Q3T,

        "queries_parquet":
            Q3P,

        "patterns_tsv":
            TP3T,

        "patterns_parquet":
            TP3P,

        "a12_evidence":
            EV3P,

        "a12_records":
            OA3P,
    }

    manifest = {
        "release":
            "openalex-retrieval-calibration-profile-v3",

        "version":
            "v3",

        "created_at":
            "2026-10-02",

        "status":
            "full_profile_reprojected",

        "derivation":
            "deterministic_reprojection_from_full_profile_v2",

        "builder_git_commit":
            subprocess.check_output(
                [
                    "git",
                    "rev-parse",
                    "HEAD",
                ],
                cwd=ROOT,
                text=True,
            ).strip(),

        "matching_contract_version":
            p2_manifest[
                "matching_contract_version"
            ],

        "snapshot":
            p2_manifest[
                "snapshot"
            ],

        "source_releases": {
            "profile_v2":
                p2_manifest[
                    "release"
                ],

            "match_registry_v1":
                "openalex-retrieval-match-registry-v1",

            "match_registry_v2":
                m2_manifest[
                    "release"
                ],

            "match_registry_v2_audit":
                m2_audit[
                    "audit_release"
                ],
        },

        "reprojection_contract": {
            "cross_release_query_join":
                "scanner-facing semantic identity; never literal query_id",

            "semantic_map_cardinality":
                "1:1",

            "snapshot_rescan_required":
                False,

            "query_scan_counts":
                "copied from unique match-registry-v1 semantic equivalent",

            "title_pattern_scan_counts":
                "copied by identical title_match_norm",

            "title_pattern_registry_metadata":
                "recomputed from match registry v2",

            "a12_candidate_evidence":
                "retained rows rekeyed to match-registry-v2 query_id/project_work_id",

            "oa_candidate_records":
                "all source OA metadata rows remain referenced; copied byte-for-byte",
        },

        "counts": {
            "source_logical_queries":
                11008,

            "logical_queries":
                10998,

            "dropped_source_query_rows":
                10,

            "semantic_query_map_rows":
                10998,

            "semantic_query_map_same_query_id":
                4973,

            "semantic_query_map_changed_query_id":
                6025,

            "semantic_query_map_changed_project_w":
                17,

            "title_patterns":
                2858,

            "title_patterns_with_registry_metadata_change":
                3,

            "source_a12_candidate_query_rows":
                251905,

            "a12_candidate_query_rows":
                251887,

            "dropped_a12_candidate_query_rows":
                18,

            "a12_candidate_rows_changed_project_w":
                34,

            "a12_oa_record_rows":
                73931,
        },

        "title_pattern_metadata_changes":
            changes,

        "dropped_source_queries":
            dropped,

        "inputs": {
            rel(path):
                sha(
                    path
                )
            for path in inputs
        },

        "outputs": {
            name: {
                "artifact":
                    rel(path),

                "sha256":
                    sha(
                        path
                    ),
            }
            for name, path
            in outputs.items()
        },
    }

    write_json(
        manifest,
        MAN,
    )

    print(
        "=== OPENALEX RETRIEVAL CALIBRATION PROFILE V3 ==="
    )

    print(
        "semantic query map:",
        len(mapping),
    )

    print(
        "logical queries: 11008 ->",
        len(q3),
    )

    print(
        "dropped old queries:",
        len(dropped_keys),
    )

    print(
        "changed query IDs:",
        int(
            mapping[
                "query_id_changed"
            ].sum()
        ),
    )

    print(
        "changed project-W query rows:",
        int(
            mapping[
                "project_work_id_changed"
            ].sum()
        ),
    )

    print(
        "title patterns:",
        len(tp3),
    )

    print(
        "pattern metadata changed:",
        len(changes),
    )

    print(
        "A1/A2 evidence: 251905 ->",
        len(ev3),
    )

    print(
        "dropped evidence rows:",
        len(ev2)
        - len(ev3),
    )

    print(
        "evidence rows changing project W:",
        changed_evidence_w,
    )

    print(
        "OA records: 73931 ->",
        len(oa2),
    )

    print(
        "snapshot rescan required: False"
    )

    print(
        "\nOpenAlex retrieval calibration profile v3 "
        "reprojection checks passed."
    )


if __name__ == "__main__":
    main()
