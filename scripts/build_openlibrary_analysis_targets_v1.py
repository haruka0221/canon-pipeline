from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

FROZEN = (
    Path.home()
    / "canon-pipeline/derived/"
    "ol_dump_population_fiction_2026-02-28.tsv"
)

CORRECTIONS = (
    ROOT
    / "derived/identity/openlibrary_target_corrections_v1.tsv"
)

ENTITIES = (
    ROOT / "derived/identity/source_entities_v2.parquet"
)

OUT_DIR = ROOT / "derived/identity"
OUT_TSV = OUT_DIR / "openlibrary_analysis_targets_v1.tsv"
OUT_PARQUET = OUT_DIR / "openlibrary_analysis_targets_v1.parquet"
OUT_MANIFEST = OUT_DIR / "openlibrary_analysis_targets_v1_manifest.json"

CREATED_AT = "2026-09-27"
EXPECTED_ROWS = 34789


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)


def write_atomic_tsv(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )
    os.replace(tmp, path)


def write_atomic_parquet(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(
        tmp,
        index=False,
        engine="pyarrow",
    )
    os.replace(tmp, path)


def main() -> None:
    for p in [FROZEN, CORRECTIONS, ENTITIES]:
        require(p)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    frozen = pd.read_csv(
        FROZEN,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    corr = pd.read_csv(
        CORRECTIONS,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    ent = pd.read_parquet(
        ENTITIES
    ).fillna("")

    assert len(frozen) == EXPECTED_ROWS
    assert len(corr) == 3

    frozen["historical_ol_work_id"] = (
        frozen["work_key"]
        .str.replace("/works/", "", regex=False)
    )

    assert frozen["historical_ol_work_id"].is_unique

    correction_map = dict(
        zip(
            corr["historical_ol_work_id"],
            corr["corrected_ol_work_id"],
        )
    )

    frozen["current_ol_work_id"] = (
        frozen["historical_ol_work_id"]
        .map(correction_map)
        .fillna(frozen["historical_ol_work_id"])
    )

    frozen["target_resolution"] = (
        frozen["historical_ol_work_id"]
        .map(
            lambda x:
            "corrected_historical_force_map_target"
            if x in correction_map
            else "unchanged_frozen_target"
        )
    )

    assert frozen["current_ol_work_id"].is_unique

    ol_ent = ent[
        (ent["source"] == "openlibrary")
        & (ent["source_namespace"] == "work")
    ][
        [
            "entity_id",
            "source_id",
        ]
    ].copy()

    assert ol_ent["source_id"].is_unique

    e_by_source_id = dict(
        zip(
            ol_ent["source_id"],
            ol_ent["entity_id"],
        )
    )

    frozen["historical_entity_id"] = (
        frozen["historical_ol_work_id"]
        .map(e_by_source_id)
    )

    frozen["current_entity_id"] = (
        frozen["current_ol_work_id"]
        .map(e_by_source_id)
    )

    assert frozen["historical_entity_id"].notna().all()
    assert frozen["current_entity_id"].notna().all()

    assert frozen["historical_entity_id"].is_unique
    assert frozen["current_entity_id"].is_unique

    out = frozen[
        [
            "historical_entity_id",
            "historical_ol_work_id",
            "current_entity_id",
            "current_ol_work_id",
            "target_resolution",
            "title",
            "author_keys",
            "first_publish_year",
        ]
    ].copy()

    assert len(out) == EXPECTED_ROWS

    assert (
        out["target_resolution"]
        .value_counts()
        .to_dict()
        == {
            "unchanged_frozen_target": 34786,
            "corrected_historical_force_map_target": 3,
        }
    )

    write_atomic_tsv(out, OUT_TSV)
    write_atomic_parquet(out, OUT_PARQUET)

    manifest = {
        "release": "openlibrary-analysis-targets-v1",
        "created_at": CREATED_AT,
        "row_count": len(out),
        "semantics": {
            "historical_target": (
                "The Open Library Work selected in the frozen "
                "34,789-row historical population."
            ),
            "current_target": (
                "The Open Library Work used as the current "
                "analysis anchor after explicit target corrections."
            ),
            "important_note": (
                "Historical source entities remain valid registry "
                "entities even when they are no longer current "
                "analysis targets. Source-level identity assertions "
                "attached to them are not silently deleted."
            ),
        },
        "inputs": {
            "frozen_population": {
                "artifact": (
                    "derived/"
                    "ol_dump_population_fiction_2026-02-28.tsv"
                ),
                "sha256": sha256_file(FROZEN),
                "rows": EXPECTED_ROWS,
            },
            "target_corrections": {
                "artifact": (
                    "derived/identity/"
                    "openlibrary_target_corrections_v1.tsv"
                ),
                "sha256": sha256_file(CORRECTIONS),
                "rows": 3,
            },
            "source_entities": {
                "artifact": (
                    "derived/identity/source_entities_v2.parquet"
                ),
                "sha256": sha256_file(ENTITIES),
            },
        },
        "counts": {
            "unchanged_frozen_target": 34786,
            "corrected_historical_force_map_target": 3,
            "current_unique_targets": 34789,
        },
        "outputs": {
            "tsv": (
                "derived/identity/"
                "openlibrary_analysis_targets_v1.tsv"
            ),
            "parquet": (
                "derived/identity/"
                "openlibrary_analysis_targets_v1.parquet"
            ),
        },
    }

    manifest["outputs"]["tsv_sha256"] = sha256_file(OUT_TSV)
    manifest["outputs"]["parquet_sha256"] = sha256_file(OUT_PARQUET)

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

    print("rows:", len(out))
    print("historical unique:", out["historical_entity_id"].nunique())
    print("current unique:", out["current_entity_id"].nunique())

    print("\n=== TARGET RESOLUTION ===")
    print(
        out["target_resolution"]
        .value_counts()
        .to_string()
    )

    print("\n=== CORRECTED TARGETS ===")
    print(
        out[
            out["target_resolution"].eq(
                "corrected_historical_force_map_target"
            )
        ][
            [
                "historical_ol_work_id",
                "current_ol_work_id",
                "historical_entity_id",
                "current_entity_id",
                "title",
            ]
        ].to_string(index=False)
    )

    print("\n=== OUTPUT SHA256 ===")
    print("tsv:", sha256_file(OUT_TSV))
    print("parquet:", sha256_file(OUT_PARQUET))
    print("manifest:", sha256_file(OUT_MANIFEST))


if __name__ == "__main__":
    main()
