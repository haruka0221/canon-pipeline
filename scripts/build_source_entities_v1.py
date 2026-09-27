from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

GR_CROSSWALK = (
    ROOT / "derived/crosswalks/goodreads_work_crosswalk_v1.tsv"
)
GR_SUMMARY = (
    ROOT / "derived/crosswalks/goodreads_work_crosswalk_v1_summary.json"
)

WD_CROSSWALK = (
    ROOT / "derived/crosswalks/work_to_wikidata_v2.parquet"
)
WD_SUMMARY = (
    ROOT / "derived/crosswalks/work_to_wikidata_v2_summary.json"
)

OUT_DIR = ROOT / "derived/identity"
OUT_TSV = OUT_DIR / "source_entities_v1.tsv"
OUT_PARQUET = OUT_DIR / "source_entities_v1.parquet"
OUT_MANIFEST = OUT_DIR / "source_entities_v1_manifest.json"

EXPECTED_OL_SHA256 = (
    "70630644b8300088a8ba1f46c7a2eaa81cc37a67e251e1068e217fbf86be9ba7"
)

RELEASE_ID = "source-entities-v1"
RELEASE_CREATED_AT = "2026-09-27"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)


def build_openlibrary(path: Path) -> pd.DataFrame:
    actual_sha = sha256_file(path)
    assert actual_sha == EXPECTED_OL_SHA256, {
        "expected": EXPECTED_OL_SHA256,
        "actual": actual_sha,
        "path": str(path),
    }

    df = pd.read_csv(
        path,
        sep="\t",
        dtype=str,
    ).fillna("")

    assert len(df) == 34789
    assert df["work_key"].is_unique
    assert df["work_key"].str.startswith("/works/").all()

    source_ids = (
        df["work_key"]
        .str.replace("/works/", "", regex=False)
    )

    assert source_ids.ne("").all()
    assert source_ids.is_unique

    return pd.DataFrame({
        "source": "openlibrary",
        "source_namespace": "work",
        "source_id": source_ids,
        "entity_type": "work",
        "source_snapshot": "2026-02-28",
        "source_artifact": (
            "derived/ol_dump_population_fiction_2026-02-28.tsv"
        ),
        "provenance_ref": (
            "derived/population_dump_v1_manifest.json"
        ),
        "created_at": RELEASE_CREATED_AT,
    })


def build_goodreads() -> pd.DataFrame:
    require(GR_CROSSWALK)
    require(GR_SUMMARY)

    df = pd.read_csv(
        GR_CROSSWALK,
        sep="\t",
        dtype=str,
    ).fillna("")

    assert len(df) == 34789
    assert df["ol_work_id"].is_unique

    accepted = df.loc[
        df["goodreads_work_id"].ne(""),
        "goodreads_work_id",
    ]

    candidates = df.loc[
        df["candidate_goodreads_work_id"].ne(""),
        "candidate_goodreads_work_id",
    ]

    source_ids = pd.concat(
        [accepted, candidates],
        ignore_index=True,
    ).drop_duplicates()

    assert len(set(accepted)) == 6548
    assert len(set(candidates)) == 7011
    assert len(source_ids) == 7011
    assert source_ids.ne("").all()

    return pd.DataFrame({
        "source": "goodreads",
        "source_namespace": "work",
        "source_id": source_ids,
        "entity_type": "work",
        "source_snapshot": "2017",
        "source_artifact": (
            "derived/crosswalks/goodreads_work_crosswalk_v1.tsv"
        ),
        "provenance_ref": (
            "derived/crosswalks/"
            "goodreads_work_crosswalk_v1_summary.json"
        ),
        "created_at": RELEASE_CREATED_AT,
    })


def build_wikidata() -> pd.DataFrame:
    require(WD_CROSSWALK)
    require(WD_SUMMARY)

    df = pd.read_parquet(
        WD_CROSSWALK,
        columns=[
            "decision",
            "wikidata_qid",
        ],
    ).fillna("")

    accepted = df.loc[
        df["decision"].eq("MATCH")
        & df["wikidata_qid"].ne(""),
        "wikidata_qid",
    ].drop_duplicates()

    assert len(accepted) == 6852
    assert accepted.str.match(r"^Q[1-9][0-9]*$").all()

    return pd.DataFrame({
        "source": "wikidata",
        "source_namespace": "item",
        "source_id": accepted,
        "entity_type": "work",
        "source_snapshot": "2026-08-05",
        "source_artifact": (
            "derived/crosswalks/work_to_wikidata_v2.parquet"
        ),
        "provenance_ref": (
            "derived/crosswalks/work_to_wikidata_v2_summary.json"
        ),
        "created_at": RELEASE_CREATED_AT,
    })


def write_atomic_tsv(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )
    os.replace(tmp, path)


def write_atomic_parquet(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_parquet(
        tmp,
        index=False,
    )
    os.replace(tmp, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ol-population",
        type=Path,
        default=(
            ROOT
            / "derived/ol_dump_population_fiction_2026-02-28.tsv"
        ),
        help=(
            "Path to the frozen Open Library population TSV. "
            "The file must match the frozen SHA256."
        ),
    )
    args = parser.parse_args()

    ol_path = args.ol_population.expanduser().resolve()
    require(ol_path)

    ol = build_openlibrary(ol_path)
    gr = build_goodreads()
    wd = build_wikidata()

    assert len(ol) == 34789
    assert len(gr) == 7011
    assert len(wd) == 6852

    out = pd.concat(
        [ol, gr, wd],
        ignore_index=True,
    )

    natural_key_cols = [
        "source",
        "source_namespace",
        "source_id",
    ]

    assert len(out) == 48652
    assert not out[natural_key_cols].duplicated().any()
    assert out["source_id"].ne("").all()

    source_order = {
        "openlibrary": 0,
        "goodreads": 1,
        "wikidata": 2,
    }

    out["_source_order"] = out["source"].map(source_order)

    assert out["_source_order"].notna().all()

    out = (
        out.sort_values(
            [
                "_source_order",
                "source_namespace",
                "source_id",
            ],
            kind="mergesort",
        )
        .drop(columns="_source_order")
        .reset_index(drop=True)
    )

    out.insert(
        0,
        "entity_id",
        [
            f"E{i:09d}"
            for i in range(1, len(out) + 1)
        ],
    )

    assert out["entity_id"].is_unique
    assert out.iloc[0]["entity_id"] == "E000000001"
    assert out.iloc[-1]["entity_id"] == "E000048652"

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

    assert list(out.columns) == expected_columns

    counts = (
        out["source"]
        .value_counts()
        .sort_index()
        .to_dict()
    )

    assert counts == {
        "goodreads": 7011,
        "openlibrary": 34789,
        "wikidata": 6852,
    }

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_atomic_tsv(out, OUT_TSV)
    write_atomic_parquet(out, OUT_PARQUET)

    manifest = {
        "release_id": RELEASE_ID,
        "created_at": RELEASE_CREATED_AT,
        "row_count": len(out),
        "natural_key": [
            "source",
            "source_namespace",
            "source_id",
        ],
        "entity_id_policy": {
            "format": "E#########",
            "v1_assignment": (
                "deterministic ordering by explicit source order, "
                "then source_namespace, then source_id"
            ),
            "source_order": [
                "openlibrary",
                "goodreads",
                "wikidata",
            ],
            "future_policy": (
                "preserve all released E IDs; append new natural keys "
                "after the current maximum E ID"
            ),
        },
        "source_counts": counts,
        "sources": {
            "openlibrary": {
                "source_snapshot": "2026-02-28",
                "registry_input_logical_artifact": (
                    "derived/"
                    "ol_dump_population_fiction_2026-02-28.tsv"
                ),
                "registry_input_sha256": sha256_file(ol_path),
                "provenance_ref": (
                    "derived/population_dump_v1_manifest.json"
                ),
                "records": 34789,
            },
            "goodreads": {
                "source_snapshot": "2017",
                "snapshot_semantics": (
                    "UCSD Book Graph collection snapshot; "
                    "documented as collected in late 2017"
                ),
                "registry_input": str(
                    GR_CROSSWALK.relative_to(ROOT)
                ),
                "registry_input_sha256": sha256_file(GR_CROSSWALK),
                "provenance_ref": str(
                    GR_SUMMARY.relative_to(ROOT)
                ),
                "unique_entities": 7011,
                "accepted_unique_entities": 6548,
            },
            "wikidata": {
                "source_snapshot": "2026-08-05",
                "registry_input": str(
                    WD_CROSSWALK.relative_to(ROOT)
                ),
                "registry_input_sha256": sha256_file(WD_CROSSWALK),
                "provenance_ref": str(
                    WD_SUMMARY.relative_to(ROOT)
                ),
                "unique_accepted_entities": 6852,
            },
        },
        "outputs": {
            "tsv": str(OUT_TSV.relative_to(ROOT)),
            "parquet": str(OUT_PARQUET.relative_to(ROOT)),
        },
    }

    manifest["outputs"]["tsv_sha256"] = sha256_file(OUT_TSV)
    manifest["outputs"]["parquet_sha256"] = sha256_file(OUT_PARQUET)

    tmp_manifest = OUT_MANIFEST.with_suffix(".json.tmp")
    tmp_manifest.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(tmp_manifest, OUT_MANIFEST)

    print("=== SOURCE ENTITIES V1 ===")
    print("rows:", len(out))
    print("source counts:")
    print(out["source"].value_counts().to_string())
    print("duplicate natural keys:",
          out[natural_key_cols].duplicated().sum())
    print("first entity:", out.iloc[0]["entity_id"])
    print("last entity:", out.iloc[-1]["entity_id"])
    print()
    print("outputs:")
    print(" ", OUT_TSV)
    print(" ", OUT_PARQUET)
    print(" ", OUT_MANIFEST)


if __name__ == "__main__":
    main()
