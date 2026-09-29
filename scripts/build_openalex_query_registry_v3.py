from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

REGISTRY_DIR = ROOT / "derived/openalex_production/registry_v3"

ALIASES = REGISTRY_DIR / "openalex_aliases_v3.parquet"
ALIAS_MANIFEST = REGISTRY_DIR / "openalex_alias_registry_v3_manifest.json"

R2 = REGISTRY_DIR / "openalex_r2_representative_aliases_v1.parquet"
R2_MANIFEST = REGISTRY_DIR / "openalex_r2_representative_aliases_v1_manifest.json"

QUERY_AUTHORS = (
    ROOT
    / "derived/openlibrary_query_author_selection_v1/"
    "openlibrary_query_author_selection_v1.parquet"
)
QUERY_AUTHOR_MANIFEST = (
    ROOT
    / "derived/openlibrary_query_author_selection_v1/"
    "openlibrary_query_author_selection_v1_manifest.json"
)

OUT_TSV = REGISTRY_DIR / "openalex_queries_v3.tsv"
OUT_PARQUET = REGISTRY_DIR / "openalex_queries_v3.parquet"
OUT_MANIFEST = REGISTRY_DIR / "openalex_query_registry_v3_manifest.json"

RELEASE = "openalex-query-registry-v3"
QUERY_REGISTRY_VERSION = "v3"
CREATED_AT = "2026-09-29"

EXPECTED_R2 = 32493
EXPECTED_R3 = 34428
EXPECTED_R4 = 34789
EXPECTED_TOTAL = EXPECTED_R2 + EXPECTED_R3 + EXPECTED_R4

ROUTE_ORDER = {
    "R2": 0,
    "R3": 1,
    "R4": 2,
}


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
    df.to_csv(tmp, sep="\t", index=False, lineterminator="\n")
    os.replace(tmp, path)


def write_atomic_parquet(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(tmp, index=False, engine="pyarrow")
    os.replace(tmp, path)


def write_atomic_json(value: dict, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def query_id(n: int) -> str:
    return f"OAQ{n:09d}"


def target_sort_key(row: dict) -> str:
    if row["target_lane"] == "resolved_w":
        return str(row["project_work_id"])
    return str(row["unresolved_unit_anchor_entity_id"])


def main() -> None:
    for path in [
        ALIASES,
        ALIAS_MANIFEST,
        R2,
        R2_MANIFEST,
        QUERY_AUTHORS,
        QUERY_AUTHOR_MANIFEST,
    ]:
        require(path)

    aliases = pd.read_parquet(ALIASES).fillna("")
    r2 = pd.read_parquet(R2).fillna("")
    qa = pd.read_parquet(QUERY_AUTHORS).fillna("")

    alias_manifest = json.loads(
        ALIAS_MANIFEST.read_text(encoding="utf-8")
    )
    r2_manifest = json.loads(
        R2_MANIFEST.read_text(encoding="utf-8")
    )
    qa_manifest = json.loads(
        QUERY_AUTHOR_MANIFEST.read_text(encoding="utf-8")
    )

    if alias_manifest.get("release") != "openalex-alias-registry-v3":
        raise RuntimeError("Unexpected alias registry release")

    if r2_manifest.get("release") != "openalex-r2-representative-aliases-v1":
        raise RuntimeError("Unexpected R2 representative release")

    if qa_manifest.get("release") != "openlibrary-query-author-selection-v1":
        raise RuntimeError("Unexpected query-author release")

    if not aliases["alias_id"].is_unique:
        raise RuntimeError("alias_id is not unique")

    if not aliases["alias_project_source_entity_id"].is_unique:
        raise RuntimeError(
            "Expected one Open Library title alias per current source entity"
        )

    if not qa["current_entity_id"].is_unique:
        raise RuntimeError(
            "Query-author selection current_entity_id is not unique"
        )

    alias_by_id = aliases.set_index("alias_id")
    qa_by_entity = qa.set_index("current_entity_id")

    rows = []

    # ---------------------------------------------------------
    # R2: one representative alias per target, title + author.
    # Targets with no selected OL query author do not get R2;
    # they remain eligible for R4 title-only calibration.
    # ---------------------------------------------------------

    for rep in r2.to_dict("records"):
        aid = str(rep["representative_alias_id"])

        if aid not in alias_by_id.index:
            raise RuntimeError(f"R2 alias not found: {aid}")

        a = alias_by_id.loc[aid]
        entity_id = str(a["alias_project_source_entity_id"])

        if entity_id not in qa_by_entity.index:
            raise RuntimeError(
                f"R2 alias source entity missing query-author row: {entity_id}"
            )

        q = qa_by_entity.loc[entity_id]

        if not bool(q["query_author_selected"]):
            continue

        rows.append(
            {
                "target_lane": str(a["target_lane"]),
                "project_work_id": str(a["project_work_id"]),
                "unresolved_unit_anchor_entity_id": str(
                    a["unresolved_unit_anchor_entity_id"]
                ),
                "alias_id": aid,
                "alias_project_source_entity_id": entity_id,
                "alias_source_record_id": str(
                    a["alias_source_record_id"]
                ),
                "query_route": "R2",
                "query_form": "title_author",
                "query_title": str(a["alias_value_raw"]),
                "query_author": str(q["query_author_name"]),
                "query_author_source_id": str(
                    q["query_author_source_id"]
                ),
                "query_author_selection_basis": str(
                    q["selection_basis"]
                ),
                "query_author_selection_version": str(
                    q["query_author_selection_version"]
                ),
                "logical_query_status": "calibration_candidate",
                "query_registry_version": QUERY_REGISTRY_VERSION,
                "created_at": CREATED_AT,
            }
        )

    # ---------------------------------------------------------
    # R3: every alias whose own source OL target has a selected
    # primary query author.
    # ---------------------------------------------------------

    for a in aliases.to_dict("records"):
        entity_id = str(a["alias_project_source_entity_id"])

        if entity_id not in qa_by_entity.index:
            raise RuntimeError(
                f"Alias source entity missing query-author row: {entity_id}"
            )

        q = qa_by_entity.loc[entity_id]

        if not bool(q["query_author_selected"]):
            continue

        rows.append(
            {
                "target_lane": str(a["target_lane"]),
                "project_work_id": str(a["project_work_id"]),
                "unresolved_unit_anchor_entity_id": str(
                    a["unresolved_unit_anchor_entity_id"]
                ),
                "alias_id": str(a["alias_id"]),
                "alias_project_source_entity_id": entity_id,
                "alias_source_record_id": str(
                    a["alias_source_record_id"]
                ),
                "query_route": "R3",
                "query_form": "title_author",
                "query_title": str(a["alias_value_raw"]),
                "query_author": str(q["query_author_name"]),
                "query_author_source_id": str(
                    q["query_author_source_id"]
                ),
                "query_author_selection_basis": str(
                    q["selection_basis"]
                ),
                "query_author_selection_version": str(
                    q["query_author_selection_version"]
                ),
                "logical_query_status": "calibration_candidate",
                "query_registry_version": QUERY_REGISTRY_VERSION,
                "created_at": CREATED_AT,
            }
        )

    # ---------------------------------------------------------
    # R4: every alias as title-only rescue candidate.
    # R4 inclusion in the registry does not freeze production
    # eligibility; routing policy is decided after calibration.
    # ---------------------------------------------------------

    for a in aliases.to_dict("records"):
        rows.append(
            {
                "target_lane": str(a["target_lane"]),
                "project_work_id": str(a["project_work_id"]),
                "unresolved_unit_anchor_entity_id": str(
                    a["unresolved_unit_anchor_entity_id"]
                ),
                "alias_id": str(a["alias_id"]),
                "alias_project_source_entity_id": str(
                    a["alias_project_source_entity_id"]
                ),
                "alias_source_record_id": str(
                    a["alias_source_record_id"]
                ),
                "query_route": "R4",
                "query_form": "title_only",
                "query_title": str(a["alias_value_raw"]),
                "query_author": "",
                "query_author_source_id": "",
                "query_author_selection_basis": "",
                "query_author_selection_version": "",
                "logical_query_status": "calibration_candidate",
                "query_registry_version": QUERY_REGISTRY_VERSION,
                "created_at": CREATED_AT,
            }
        )

    out = pd.DataFrame(rows)

    if len(out) != EXPECTED_TOTAL:
        raise RuntimeError(
            f"Expected {EXPECTED_TOTAL} logical queries; found {len(out)}"
        )

    route_counts = out["query_route"].value_counts().to_dict()
    expected_route_counts = {
        "R2": EXPECTED_R2,
        "R3": EXPECTED_R3,
        "R4": EXPECTED_R4,
    }
    if route_counts != expected_route_counts:
        raise RuntimeError(
            f"Unexpected route counts: {route_counts}"
        )

    # ---------------------------------------------------------
    # Stable ID assignment within registry v3
    # ---------------------------------------------------------

    out["_route_order"] = out["query_route"].map(ROUTE_ORDER)
    if out["_route_order"].isna().any():
        raise RuntimeError("Unknown query route")

    out["_target_sort"] = [
        target_sort_key(row)
        for row in out.to_dict("records")
    ]

    out = out.sort_values(
        [
            "_target_sort",
            "_route_order",
            "alias_id",
            "query_form",
            "query_title",
            "query_author",
        ],
        kind="stable",
    ).reset_index(drop=True)

    out.insert(
        0,
        "query_id",
        [query_id(i) for i in range(1, len(out) + 1)],
    )

    out = out.drop(
        columns=["_route_order", "_target_sort"]
    )

    if not out["query_id"].is_unique:
        raise RuntimeError("query_id is not unique")

    logical_key = [
        "target_lane",
        "project_work_id",
        "unresolved_unit_anchor_entity_id",
        "alias_id",
        "query_route",
        "query_form",
        "query_title",
        "query_author",
    ]
    if out.duplicated(logical_key).any():
        raise RuntimeError(
            "Duplicate logical query provenance rows"
        )

    # R2/R3 overlap is intentionally preserved.
    r2_keys = set(
        out.loc[
            out["query_route"].eq("R2"),
            ["alias_id", "query_title", "query_author"],
        ].itertuples(index=False, name=None)
    )
    r3_keys = set(
        out.loc[
            out["query_route"].eq("R3"),
            ["alias_id", "query_title", "query_author"],
        ].itertuples(index=False, name=None)
    )

    r2_r3_exact_overlap = len(r2_keys & r3_keys)

    if r2_r3_exact_overlap != EXPECTED_R2:
        raise RuntimeError(
            "Every R2 logical query should also exist as an R3 "
            f"alias query; overlap={r2_r3_exact_overlap}"
        )

    write_atomic_tsv(out, OUT_TSV)
    write_atomic_parquet(out, OUT_PARQUET)

    manifest = {
        "release": RELEASE,
        "created_at": CREATED_AT,
        "query_registry_version": QUERY_REGISTRY_VERSION,
        "purpose": (
            "Freeze logical OpenAlex calibration queries separately from "
            "physical execution deduplication."
        ),
        "semantics": {
            "query_id": (
                "Stable sequential logical-query identifier within registry "
                "v3. IDs are assigned after deterministic sorting by target, "
                "route, alias, query form, title, and author."
            ),
            "R2": (
                "Representative identity-anchor alias plus its frozen "
                "Open Library-derived primary query author. Targets without "
                "a selected query author do not receive an R2 title-author "
                "query."
            ),
            "R3": (
                "All current Open Library title aliases whose own source "
                "target has a selected primary query author."
            ),
            "R4": (
                "All current Open Library title aliases as title-only "
                "calibration candidates. Presence in the logical registry "
                "does not imply final production routing eligibility."
            ),
            "r2_r3_overlap_policy": (
                "R2 and R3 logical queries are both preserved even where "
                "their raw query strings are identical. Execution-level "
                "deduplication happens in the next registry layer."
            ),
            "scope_release": "not_applied",
        },
        "source_releases": {
            "alias_registry": alias_manifest["release"],
            "representative_aliases": r2_manifest["release"],
            "query_author_selection": qa_manifest["release"],
        },
        "inputs": {
            str(ALIASES.relative_to(ROOT)): sha256_file(ALIASES),
            str(ALIAS_MANIFEST.relative_to(ROOT)): sha256_file(ALIAS_MANIFEST),
            str(R2.relative_to(ROOT)): sha256_file(R2),
            str(R2_MANIFEST.relative_to(ROOT)): sha256_file(R2_MANIFEST),
            str(QUERY_AUTHORS.relative_to(ROOT)): sha256_file(QUERY_AUTHORS),
            str(QUERY_AUTHOR_MANIFEST.relative_to(ROOT)): (
                sha256_file(QUERY_AUTHOR_MANIFEST)
            ),
        },
        "counts": {
            "logical_queries": len(out),
            "by_route": route_counts,
            "r2_r3_exact_logical_string_overlap": r2_r3_exact_overlap,
            "title_author_queries": int(
                out["query_form"].eq("title_author").sum()
            ),
            "title_only_queries": int(
                out["query_form"].eq("title_only").sum()
            ),
        },
        "outputs": {
            "tsv": {
                "artifact": str(OUT_TSV.relative_to(ROOT)),
                "sha256": sha256_file(OUT_TSV),
            },
            "parquet": {
                "artifact": str(OUT_PARQUET.relative_to(ROOT)),
                "sha256": sha256_file(OUT_PARQUET),
            },
        },
        "next_step": (
            "construct_normalized_execution_signatures"
        ),
    }

    write_atomic_json(manifest, OUT_MANIFEST)

    print("=== OPENALEX QUERY REGISTRY V3 ===")
    print(out["query_route"].value_counts().to_string())
    print("logical queries:", len(out))
    print("R2/R3 exact logical-string overlap:", r2_r3_exact_overlap)
    print("\nOutputs:")
    print(OUT_TSV.relative_to(ROOT))
    print(OUT_PARQUET.relative_to(ROOT))
    print(OUT_MANIFEST.relative_to(ROOT))
    print("\nOpenAlex logical query registry v3 checks passed.")


if __name__ == "__main__":
    main()
