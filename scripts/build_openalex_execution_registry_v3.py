from pathlib import Path
import hashlib
import json
import os
import unicodedata
import re

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

REGISTRY_DIR = ROOT / "derived/openalex_production/registry_v3"

QUERIES = REGISTRY_DIR / "openalex_queries_v3.parquet"
QUERY_MANIFEST = (
    REGISTRY_DIR / "openalex_query_registry_v3_manifest.json"
)

OUT_MAP_TSV = (
    REGISTRY_DIR / "openalex_query_execution_map_v3.tsv"
)
OUT_MAP_PARQUET = (
    REGISTRY_DIR / "openalex_query_execution_map_v3.parquet"
)

OUT_EXEC_TSV = (
    REGISTRY_DIR / "openalex_query_executions_v3.tsv"
)
OUT_EXEC_PARQUET = (
    REGISTRY_DIR / "openalex_query_executions_v3.parquet"
)

OUT_MANIFEST = (
    REGISTRY_DIR / "openalex_execution_registry_v3_manifest.json"
)

RELEASE = "openalex-execution-registry-v3"
EXECUTION_REGISTRY_VERSION = "v3"

NORMALIZATION_RULE = "openalex_execution_query_norm"
NORMALIZATION_VERSION = "v1"

CREATED_AT = "2026-09-29"

EXPECTED_LOGICAL_QUERIES = 101710
EXPECTED_EXECUTIONS = 63624

EXPECTED_BY_FORM = {
    "title_author": 32237,
    "title_only": 31387,
}

_WS_RE = re.compile(r"\s+")


def require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_atomic_tsv(df: pd.DataFrame, path: Path) -> None:
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


def write_atomic_json(
    value: dict,
    path: Path,
) -> None:
    tmp = path.with_name(path.name + ".tmp")
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


def normalize_query_component(value: str) -> str:
    """
    Conservative OpenAlex execution normalization v1.

    Semantics:
      1. Unicode NFKC
      2. Unicode casefold
      3. collapse consecutive whitespace
      4. strip leading/trailing whitespace

    Intentionally NOT performed:
      - punctuation deletion
      - apostrophe deletion
      - hyphen/dash deletion or canonicalization
      - leading-article deletion
      - diacritic stripping
      - ASCII transliteration
      - non-Latin character deletion
    """
    value = unicodedata.normalize(
        "NFKC",
        str(value or ""),
    )
    value = value.casefold()
    value = _WS_RE.sub(" ", value).strip()
    return value


def signature_payload(
    query_form: str,
    normalized_title: str,
    normalized_author: str,
) -> str:
    """
    Human-inspectable canonical signature payload.

    Unit Separator is used so component boundaries are
    unambiguous.
    """
    return (
        str(query_form)
        + "\x1f"
        + str(normalized_title)
        + "\x1f"
        + str(normalized_author)
    )


def signature_hash(payload: str) -> str:
    """
    Stable execution signature identifier.

    Full SHA256 is retained to make accidental collisions
    practically irrelevant.
    """
    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def main() -> None:
    for path in [
        QUERIES,
        QUERY_MANIFEST,
    ]:
        require(path)

    q = pd.read_parquet(QUERIES).fillna("")

    query_manifest = json.loads(
        QUERY_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    if (
        query_manifest.get("release")
        != "openalex-query-registry-v3"
    ):
        raise RuntimeError(
            "Unexpected logical query registry release"
        )

    # ---------------------------------------------------------
    # Logical-query input invariants
    # ---------------------------------------------------------

    if len(q) != EXPECTED_LOGICAL_QUERIES:
        raise RuntimeError(
            f"Expected {EXPECTED_LOGICAL_QUERIES} logical "
            f"queries; found {len(q)}"
        )

    if not q["query_id"].is_unique:
        raise RuntimeError(
            "query_id is not unique"
        )

    if q["query_form"].eq("").any():
        raise RuntimeError(
            "Logical query with empty query_form"
        )

    if q["query_title"].eq("").any():
        raise RuntimeError(
            "Logical query with empty query_title"
        )

    expected_forms = {
        "title_author",
        "title_only",
    }

    if set(q["query_form"]) != expected_forms:
        raise RuntimeError(
            "Unexpected query_form values: "
            f"{sorted(set(q['query_form']))}"
        )

    title_author = q[
        q["query_form"].eq("title_author")
    ]

    if title_author["query_author"].eq("").any():
        raise RuntimeError(
            "title_author query with empty query_author"
        )

    title_only = q[
        q["query_form"].eq("title_only")
    ]

    if title_only["query_author"].ne("").any():
        raise RuntimeError(
            "title_only query unexpectedly has query_author"
        )

    # ---------------------------------------------------------
    # Normalize logical queries
    # ---------------------------------------------------------

    q = q.copy()

    q["normalized_title"] = (
        q["query_title"]
        .map(normalize_query_component)
    )

    q["normalized_author"] = (
        q["query_author"]
        .map(normalize_query_component)
    )

    if q["normalized_title"].eq("").any():
        raise RuntimeError(
            "Normalization produced empty title"
        )

    if (
        q.loc[
            q["query_form"].eq("title_author"),
            "normalized_author",
        ]
        .eq("")
        .any()
    ):
        raise RuntimeError(
            "Normalization produced empty author "
            "for title_author query"
        )

    if (
        q.loc[
            q["query_form"].eq("title_only"),
            "normalized_author",
        ]
        .ne("")
        .any()
    ):
        raise RuntimeError(
            "title_only normalized_author is non-empty"
        )

    q["normalized_query_signature_payload"] = [
        signature_payload(form, title, author)
        for form, title, author in zip(
            q["query_form"],
            q["normalized_title"],
            q["normalized_author"],
        )
    ]

    q["normalized_query_signature"] = (
        q[
            "normalized_query_signature_payload"
        ]
        .map(signature_hash)
    )

    q["normalization_rule"] = NORMALIZATION_RULE
    q["normalization_version"] = (
        NORMALIZATION_VERSION
    )

    # SHA256 collision/inconsistency guard.
    signature_check = (
        q.groupby(
            "normalized_query_signature"
        )[
            "normalized_query_signature_payload"
        ]
        .nunique()
    )

    if (signature_check > 1).any():
        raise RuntimeError(
            "SHA256 signature collision or inconsistent "
            "signature construction detected"
        )

    # ---------------------------------------------------------
    # Query → execution mapping
    # ---------------------------------------------------------

    map_columns = [
        "query_id",
        "target_lane",
        "project_work_id",
        "unresolved_unit_anchor_entity_id",
        "alias_id",
        "alias_project_source_entity_id",
        "query_route",
        "query_form",
        "query_title",
        "query_author",
        "normalized_title",
        "normalized_author",
        "normalized_query_signature",
        "normalization_rule",
        "normalization_version",
    ]

    execution_map = (
        q[map_columns]
        .sort_values(
            "query_id",
            kind="stable",
        )
        .reset_index(drop=True)
    )

    if len(execution_map) != EXPECTED_LOGICAL_QUERIES:
        raise RuntimeError(
            "Execution map row count mismatch"
        )

    if not execution_map["query_id"].is_unique:
        raise RuntimeError(
            "Execution map query_id is not unique"
        )

    # ---------------------------------------------------------
    # Physical execution registry
    # ---------------------------------------------------------

    group_cols = [
        "normalized_query_signature",
        "normalized_query_signature_payload",
        "query_form",
        "normalized_title",
        "normalized_author",
    ]

    grouped = q.groupby(
        group_cols,
        sort=False,
        dropna=False,
    )

    executions = grouped.agg(
        logical_query_count=(
            "query_id",
            "size",
        ),
        distinct_target_lane_count=(
            "target_lane",
            "nunique",
        ),
        distinct_resolved_w_count=(
            "project_work_id",
            lambda s: s[s.ne("")].nunique(),
        ),
        distinct_unresolved_unit_count=(
            "unresolved_unit_anchor_entity_id",
            lambda s: s[s.ne("")].nunique(),
        ),
        distinct_source_target_count=(
            "alias_project_source_entity_id",
            "nunique",
        ),
        distinct_alias_count=(
            "alias_id",
            "nunique",
        ),
        distinct_route_count=(
            "query_route",
            "nunique",
        ),
    ).reset_index()

    # Deterministic physical execution ID.
    executions = executions.sort_values(
        [
            "query_form",
            "normalized_title",
            "normalized_author",
            "normalized_query_signature",
        ],
        kind="stable",
    ).reset_index(drop=True)

    executions.insert(
        0,
        "execution_id",
        [
            f"OAE{i:09d}"
            for i in range(
                1,
                len(executions) + 1,
            )
        ],
    )

    executions["normalization_rule"] = (
        NORMALIZATION_RULE
    )
    executions["normalization_version"] = (
        NORMALIZATION_VERSION
    )
    executions["execution_status"] = (
        "not_executed"
    )
    executions["execution_registry_version"] = (
        EXECUTION_REGISTRY_VERSION
    )
    executions["created_at"] = CREATED_AT

    if len(executions) != EXPECTED_EXECUTIONS:
        raise RuntimeError(
            f"Expected {EXPECTED_EXECUTIONS} physical "
            f"execution signatures; found {len(executions)}"
        )

    if not executions[
        "normalized_query_signature"
    ].is_unique:
        raise RuntimeError(
            "normalized_query_signature not unique "
            "in execution registry"
        )

    if not executions["execution_id"].is_unique:
        raise RuntimeError(
            "execution_id is not unique"
        )

    by_form = (
        executions["query_form"]
        .value_counts()
        .to_dict()
    )

    if by_form != EXPECTED_BY_FORM:
        raise RuntimeError(
            f"Unexpected execution counts by form: "
            f"{by_form}"
        )

    # ---------------------------------------------------------
    # Add execution_id to mapping
    # ---------------------------------------------------------

    execution_id_lookup = (
        executions.set_index(
            "normalized_query_signature"
        )["execution_id"]
    )

    execution_map.insert(
        1,
        "execution_id",
        execution_map[
            "normalized_query_signature"
        ].map(execution_id_lookup),
    )

    if execution_map["execution_id"].isna().any():
        raise RuntimeError(
            "Logical query failed to map to execution"
        )

    # ---------------------------------------------------------
    # Diagnostics
    # ---------------------------------------------------------

    lane_route = pd.crosstab(
        q["target_lane"],
        q["query_route"],
    )

    multi_logical_executions = int(
        (
            executions["logical_query_count"] > 1
        ).sum()
    )

    cross_w_execution_signatures = int(
        (
            executions[
                "distinct_resolved_w_count"
            ]
            > 1
        ).sum()
    )

    cross_unresolved_execution_signatures = int(
        (
            executions[
                "distinct_unresolved_unit_count"
            ]
            > 1
        ).sum()
    )

    max_logical_queries_per_execution = int(
        executions[
            "logical_query_count"
        ].max()
    )

    # ---------------------------------------------------------
    # Write outputs
    # ---------------------------------------------------------

    REGISTRY_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_atomic_tsv(
        execution_map,
        OUT_MAP_TSV,
    )
    write_atomic_parquet(
        execution_map,
        OUT_MAP_PARQUET,
    )

    write_atomic_tsv(
        executions,
        OUT_EXEC_TSV,
    )
    write_atomic_parquet(
        executions,
        OUT_EXEC_PARQUET,
    )

    manifest = {
        "release": RELEASE,
        "created_at": CREATED_AT,
        "status": "execution_registry_built",
        "execution_registry_version": (
            EXECUTION_REGISTRY_VERSION
        ),
        "normalization": {
            "rule": NORMALIZATION_RULE,
            "version": NORMALIZATION_VERSION,
            "steps": [
                "Unicode NFKC",
                "Unicode casefold",
                "collapse consecutive whitespace",
                "strip leading/trailing whitespace",
            ],
            "intentionally_not_applied": [
                "punctuation deletion",
                "apostrophe deletion",
                "hyphen or dash deletion",
                "dash canonicalization",
                "leading article deletion",
                "diacritic stripping",
                "ASCII transliteration",
                "non-Latin character deletion",
            ],
        },
        "semantics": {
            "query_id": (
                "Logical retrieval-provenance unit."
            ),
            "execution_id": (
                "Deterministic sequential identifier "
                "for one physical execution row within "
                "this v3 execution registry."
            ),
            "normalized_query_signature": (
                "SHA256 of query_form, normalized title, "
                "and normalized author separated by "
                "ASCII Unit Separator. Used only for "
                "physical execution deduplication; it "
                "does not imply literary-work identity."
            ),
            "cross_target_deduplication": (
                "One physical execution may serve logical "
                "queries from multiple project works, "
                "unresolved units, aliases, or retrieval "
                "routes. All logical provenance remains "
                "in openalex_query_execution_map_v3."
            ),
            "scope_release": "not_applied",
            "r4_policy": (
                "R4 rows remain calibration candidates; "
                "their presence in this registry does not "
                "freeze title-only production execution."
            ),
        },
        "source_releases": {
            "logical_query_registry": (
                query_manifest["release"]
            ),
        },
        "inputs": {
            str(
                QUERIES.relative_to(ROOT)
            ): sha256_file(QUERIES),
            str(
                QUERY_MANIFEST.relative_to(ROOT)
            ): sha256_file(QUERY_MANIFEST),
        },
        "counts": {
            "logical_queries": len(q),
            "physical_execution_signatures": (
                len(executions)
            ),
            "logical_rows_saved_by_execution_dedup": (
                len(q) - len(executions)
            ),
            "execution_signatures_by_query_form": (
                by_form
            ),
            "multi_logical_execution_signatures": (
                multi_logical_executions
            ),
            "cross_w_execution_signatures": (
                cross_w_execution_signatures
            ),
            "cross_unresolved_unit_execution_signatures": (
                cross_unresolved_execution_signatures
            ),
            "max_logical_queries_per_execution": (
                max_logical_queries_per_execution
            ),
            "target_lane_by_query_route": {
                str(lane): {
                    str(route): int(
                        lane_route.loc[
                            lane,
                            route,
                        ]
                    )
                    for route in lane_route.columns
                }
                for lane in lane_route.index
            },
        },
        "outputs": {
            "query_execution_map_tsv": {
                "artifact": str(
                    OUT_MAP_TSV.relative_to(ROOT)
                ),
                "sha256": sha256_file(
                    OUT_MAP_TSV
                ),
            },
            "query_execution_map_parquet": {
                "artifact": str(
                    OUT_MAP_PARQUET.relative_to(ROOT)
                ),
                "sha256": sha256_file(
                    OUT_MAP_PARQUET
                ),
            },
            "executions_tsv": {
                "artifact": str(
                    OUT_EXEC_TSV.relative_to(ROOT)
                ),
                "sha256": sha256_file(
                    OUT_EXEC_TSV
                ),
            },
            "executions_parquet": {
                "artifact": str(
                    OUT_EXEC_PARQUET.relative_to(ROOT)
                ),
                "sha256": sha256_file(
                    OUT_EXEC_PARQUET
                ),
            },
        },
        "next_step": (
            "rerun_w_level_retrieval_calibration_and_"
            "evaluate_r2_r3_r4"
        ),
    }

    write_atomic_json(
        manifest,
        OUT_MANIFEST,
    )

    print(
        "=== OPENALEX EXECUTION REGISTRY V3 ==="
    )
    print(
        "logical queries:",
        len(q),
    )
    print(
        "physical executions:",
        len(executions),
    )
    print(
        "saved by execution dedup:",
        len(q) - len(executions),
    )

    print("\nExecutions by query form:")
    print(
        executions[
            "query_form"
        ]
        .value_counts()
        .to_string()
    )

    print("\nTarget lane × query route:")
    print(
        lane_route.to_string()
    )

    print(
        "\nmulti-logical execution signatures:",
        multi_logical_executions,
    )
    print(
        "cross-W execution signatures:",
        cross_w_execution_signatures,
    )
    print(
        "cross-unresolved-unit execution signatures:",
        cross_unresolved_execution_signatures,
    )
    print(
        "max logical queries per execution:",
        max_logical_queries_per_execution,
    )

    print("\nOutputs:")
    for path in [
        OUT_MAP_TSV,
        OUT_MAP_PARQUET,
        OUT_EXEC_TSV,
        OUT_EXEC_PARQUET,
        OUT_MANIFEST,
    ]:
        print(path.relative_to(ROOT))

    print(
        "\nOpenAlex execution registry v3 "
        "checks passed."
    )


if __name__ == "__main__":
    main()
