from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

V1_PARQUET = ROOT / "derived/identity/source_entities_v1.parquet"
V1_TSV = ROOT / "derived/identity/source_entities_v1.tsv"

CORRECTIONS = (
    ROOT
    / "derived/identity/openlibrary_target_corrections_v1.tsv"
)

OUT_DIR = ROOT / "derived/identity"
OUT_TSV = OUT_DIR / "source_entities_v2.tsv"
OUT_PARQUET = OUT_DIR / "source_entities_v2.parquet"
OUT_MANIFEST = OUT_DIR / "source_entities_v2_manifest.json"

CREATED_AT = "2026-09-27"

EXPECTED_V1_ROWS = 48652
EXPECTED_OUT_ROWS = 48655

SOURCE_ARTIFACTS = {
    "OL245401W": (
        ROOT / "derived/phd_supplement_works.tsv"
    ),
    "OL509889W": (
        ROOT / "derived/ol_works_population_unique_clean.tsv"
    ),
    "OL85892W": (
        ROOT / "derived/ol_works_population_unique_clean.tsv"
    ),
}


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


def verify_source_artifact(
    ol_id: str,
    artifact: Path,
    expected_author: str,
) -> None:
    require(artifact)

    df = pd.read_csv(
        artifact,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    if "work_key" not in df.columns:
        raise AssertionError(
            f"{artifact}: no work_key column"
        )

    target = "/works/" + ol_id
    z = df[df["work_key"].eq(target)].copy()

    assert len(z) == 1, (
        ol_id,
        artifact,
        len(z),
    )

    if "author_names" in z.columns:
        actual = z.iloc[0]["author_names"]
        assert expected_author in actual, (
            ol_id,
            expected_author,
            actual,
        )


def main() -> None:
    require(V1_PARQUET)
    require(V1_TSV)
    require(CORRECTIONS)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    v1 = pd.read_parquet(
        V1_PARQUET
    ).fillna("")

    assert len(v1) == EXPECTED_V1_ROWS
    assert v1["entity_id"].is_unique
    assert v1.iloc[0]["entity_id"] == "E000000001"
    assert v1.iloc[-1]["entity_id"] == "E000048652"

    expected_columns = [
        "entity_id",
        "source",
        "source_namespace",
        "source_id",
        "entity_type",
        "source_snapshot",
        "source_artifact",
        "provenance_ref",
        "created_at",
    ]

    assert list(v1.columns) == expected_columns

    corr = pd.read_csv(
        CORRECTIONS,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    assert len(corr) == 3
    assert corr["historical_ol_work_id"].is_unique
    assert corr["corrected_ol_work_id"].is_unique

    expected_targets = {
        "OL245401W",
        "OL509889W",
        "OL85892W",
    }

    assert (
        set(corr["corrected_ol_work_id"])
        == expected_targets
    )

    existing_keys = set(
        zip(
            v1["source"],
            v1["source_namespace"],
            v1["source_id"],
        )
    )

    new_rows = []

    corr_by_target = corr.set_index(
        "corrected_ol_work_id"
    )

    for i, ol_id in enumerate(
        sorted(expected_targets),
        start=48653,
    ):
        natural_key = (
            "openlibrary",
            "work",
            ol_id,
        )

        assert natural_key not in existing_keys

        cr = corr_by_target.loc[ol_id]

        artifact = SOURCE_ARTIFACTS[ol_id]

        verify_source_artifact(
            ol_id,
            artifact,
            cr["corrected_author_name"],
        )

        new_rows.append(
            {
                "entity_id": f"E{i:09d}",
                "source": "openlibrary",
                "source_namespace": "work",
                "source_id": ol_id,
                "entity_type": "work",

                # These rows are not from the frozen
                # 2026-02-28 Works Dump population.
                # Historical project artifacts establish
                # the OL entities, but an exact source
                # snapshot date is not preserved.
                "source_snapshot": "",

                "source_artifact": str(
                    artifact.relative_to(ROOT)
                ),

                "provenance_ref": (
                    "derived/identity/"
                    "openlibrary_target_corrections_v1.tsv"
                ),

                "created_at": CREATED_AT,
            }
        )

    added = pd.DataFrame(
        new_rows,
        columns=expected_columns,
    )

    out = pd.concat(
        [v1, added],
        ignore_index=True,
    )

    assert len(out) == EXPECTED_OUT_ROWS
    assert out["entity_id"].is_unique

    natural_keys = list(
        zip(
            out["source"],
            out["source_namespace"],
            out["source_id"],
        )
    )

    assert len(natural_keys) == len(set(natural_keys))

    # v1 rows must survive unchanged and in the same order.
    pd.testing.assert_frame_equal(
        out.iloc[:EXPECTED_V1_ROWS]
        .reset_index(drop=True),
        v1.reset_index(drop=True),
        check_dtype=False,
    )

    assert (
        out.iloc[EXPECTED_V1_ROWS:]["entity_id"].tolist()
        == [
            "E000048653",
            "E000048654",
            "E000048655",
        ]
    )

    assert (
        out.iloc[EXPECTED_V1_ROWS:]["source_id"].tolist()
        == [
            "OL245401W",
            "OL509889W",
            "OL85892W",
        ]
    )

    write_atomic_tsv(out, OUT_TSV)
    write_atomic_parquet(out, OUT_PARQUET)

    source_counts = (
        out["source"]
        .value_counts()
        .sort_index()
        .to_dict()
    )

    manifest = {
        "release": "source-entities-v2",
        "created_at": CREATED_AT,
        "row_count": len(out),
        "previous_release": {
            "release": "source-entities-v1",
            "row_count": len(v1),
            "artifact": (
                "derived/identity/"
                "source_entities_v1.parquet"
            ),
            "sha256": sha256_file(V1_PARQUET),
        },
        "append": {
            "row_count": len(added),
            "entity_ids": added["entity_id"].tolist(),
            "source_ids": added["source_id"].tolist(),
            "policy": (
                "Preserve all released v1 E IDs and append "
                "new natural keys after the previous maximum "
                "E ID. New keys within this append batch are "
                "ordered lexically by source_id."
            ),
        },
        "source_counts": source_counts,
        "openlibrary_target_correction": {
            "artifact": (
                "derived/identity/"
                "openlibrary_target_corrections_v1.tsv"
            ),
            "sha256": sha256_file(CORRECTIONS),
            "correction_date": "2026-05-28",
            "notes": (
                "Three corrected Open Library Work targets "
                "replace historical project target-selection "
                "errors. They do not replace or mutate the "
                "historical Open Library entities already "
                "registered in v1."
            ),
        },
        "appended_source_provenance": {
            ol_id: {
                "source_snapshot": "",
                "source_artifact": str(
                    SOURCE_ARTIFACTS[ol_id]
                    .relative_to(ROOT)
                ),
                "source_artifact_sha256": sha256_file(
                    SOURCE_ARTIFACTS[ol_id]
                ),
                "provenance_note": (
                    "Historical Open Library API-era project "
                    "artifact. Exact row-level source snapshot "
                    "date is not preserved; do not interpret "
                    "this entity as originating from the "
                    "2026-02-28 Works Dump snapshot."
                ),
            }
            for ol_id in sorted(expected_targets)
        },
        "outputs": {
            "tsv": (
                "derived/identity/"
                "source_entities_v2.tsv"
            ),
            "parquet": (
                "derived/identity/"
                "source_entities_v2.parquet"
            ),
        },
    }

    manifest["outputs"]["tsv_sha256"] = sha256_file(
        OUT_TSV
    )
    manifest["outputs"]["parquet_sha256"] = sha256_file(
        OUT_PARQUET
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

    print("rows:", len(out))
    print("appended:", len(added))
    print("first entity:", out.iloc[0]["entity_id"])
    print("last entity:", out.iloc[-1]["entity_id"])

    print("\n=== APPENDED ENTITIES ===")
    print(
        added[
            [
                "entity_id",
                "source_id",
                "source_snapshot",
                "source_artifact",
            ]
        ].to_string(index=False)
    )

    print("\n=== SOURCE COUNTS ===")
    for source, count in source_counts.items():
        print(source, count)

    print("\n=== OUTPUT SHA256 ===")
    print("tsv:", sha256_file(OUT_TSV))
    print("parquet:", sha256_file(OUT_PARQUET))
    print("manifest:", sha256_file(OUT_MANIFEST))


if __name__ == "__main__":
    main()
