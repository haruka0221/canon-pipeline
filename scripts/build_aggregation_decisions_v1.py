from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

UNITS = (
    ROOT / "derived/identity/aggregation_review_units_v1.parquet"
)

POLICY = (
    ROOT / "docs/AGGREGATION_POLICY.md"
)

OUT_DIR = ROOT / "derived/identity"

OUT_TSV = (
    OUT_DIR / "aggregation_decisions_v1.tsv"
)

OUT_PARQUET = (
    OUT_DIR / "aggregation_decisions_v1.parquet"
)

OUT_MANIFEST = (
    OUT_DIR / "aggregation_decisions_v1_manifest.json"
)

CREATED_AT = "2026-09-27"

EXPECTED_ROWS = 32847
EXPECTED_ONE_WORK = 31539
EXPECTED_REVIEW = 1308

SINGLE_TARGET_CLASSES = {
    "no_accepted_external_identity",
    "single_ol_single_external_source",
    "single_ol_cross_source_corroborated",
}

REVIEW_CLASSES = {
    "multi_ol_no_explicit_split",
    "cross_source_conflict",
}


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


def main() -> None:
    for p in [UNITS, POLICY]:
        require(p)

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    units = pd.read_parquet(
        UNITS
    ).fillna("")

    assert len(units) == EXPECTED_ROWS
    assert units["unit_anchor_entity_id"].is_unique

    rows = []

    for r in units.itertuples(index=False):
        cls = r.structural_class

        if cls in SINGLE_TARGET_CLASSES:
            assert r.current_target_count == 1

            decision = "ONE_WORK"
            method = "single_current_target_policy"
            review_status = "auto_accepted"

            notes = (
                "Current release treats this single-current-target "
                "unit as one project conceptual work; this is not "
                "a claim of global Open Library deduplication."
            )

        elif cls in REVIEW_CLASSES:
            assert r.current_target_count >= 2

            decision = "MANUAL_REVIEW_REQUIRED"
            method = "structural_review_gate"
            review_status = "pending"

            notes = (
                "Multiple current Open Library targets are present; "
                "project-work boundaries must be reviewed before "
                "W identifiers are assigned."
            )

        else:
            raise ValueError(
                f"Unexpected structural class: {cls}"
            )

        rows.append(
            {
                "unit_anchor_entity_id": (
                    r.unit_anchor_entity_id
                ),
                "structural_class": cls,
                "current_target_count": (
                    r.current_target_count
                ),
                "aggregation_decision": decision,
                "decision_method": method,
                "decision_version": "v1",
                "review_status": review_status,
                "source_artifact": (
                    "derived/identity/"
                    "aggregation_review_units_v1.parquet"
                ),
                "notes": notes,
                "created_at": CREATED_AT,
            }
        )

    out = pd.DataFrame(rows)

    out = out.sort_values(
        "unit_anchor_entity_id",
        kind="stable",
    ).reset_index(drop=True)

    assert len(out) == EXPECTED_ROWS
    assert out["unit_anchor_entity_id"].is_unique

    decision_counts = (
        out["aggregation_decision"]
        .value_counts()
        .to_dict()
    )

    assert decision_counts == {
        "ONE_WORK": EXPECTED_ONE_WORK,
        "MANUAL_REVIEW_REQUIRED": EXPECTED_REVIEW,
    }

    review_counts = (
        out["review_status"]
        .value_counts()
        .to_dict()
    )

    assert review_counts == {
        "auto_accepted": EXPECTED_ONE_WORK,
        "pending": EXPECTED_REVIEW,
    }

    assert set(
        out.loc[
            out["aggregation_decision"].eq(
                "ONE_WORK"
            ),
            "structural_class",
        ]
    ) == SINGLE_TARGET_CLASSES

    assert set(
        out.loc[
            out["aggregation_decision"].eq(
                "MANUAL_REVIEW_REQUIRED"
            ),
            "structural_class",
        ]
    ) == REVIEW_CLASSES

    assert (
        out.loc[
            out["aggregation_decision"].eq(
                "ONE_WORK"
            ),
            "current_target_count",
        ]
        .eq(1)
        .all()
    )

    write_atomic_tsv(
        out,
        OUT_TSV,
    )

    write_atomic_parquet(
        out,
        OUT_PARQUET,
    )

    structural_decisions = (
        out.groupby(
            [
                "structural_class",
                "aggregation_decision",
            ]
        )
        .size()
        .to_dict()
    )

    manifest = {
        "release": "aggregation-decisions-v1",
        "created_at": CREATED_AT,
        "row_count": len(out),
        "semantics": {
            "decision_scope": (
                "Project-level decisions about provisional "
                "aggregation units. These decisions do not "
                "modify source entities or source-level "
                "identity assertions."
            ),
            "one_work": (
                "The current project release may represent "
                "the provisional unit as one conceptual work. "
                "This is versioned and does not assert global "
                "source deduplication."
            ),
            "manual_review_required": (
                "Project-work boundaries must be reviewed "
                "before W identifiers are assigned."
            ),
            "important_note": (
                "This release assigns no W identifiers."
            ),
        },
        "inputs": {
            "aggregation_review_units": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_review_units_v1.parquet"
                ),
                "sha256": sha256_file(UNITS),
                "rows": EXPECTED_ROWS,
            },
            "aggregation_policy": {
                "artifact": (
                    "docs/AGGREGATION_POLICY.md"
                ),
                "sha256": sha256_file(POLICY),
                "version": "1",
            },
        },
        "policy": {
            "single_target_classes": sorted(
                SINGLE_TARGET_CLASSES
            ),
            "single_target_decision": "ONE_WORK",
            "single_target_method": (
                "single_current_target_policy"
            ),
            "review_classes": sorted(
                REVIEW_CLASSES
            ),
            "review_decision": (
                "MANUAL_REVIEW_REQUIRED"
            ),
            "review_method": (
                "structural_review_gate"
            ),
            "decision_version": "v1",
        },
        "counts": {
            "ONE_WORK": EXPECTED_ONE_WORK,
            "MANUAL_REVIEW_REQUIRED": (
                EXPECTED_REVIEW
            ),
            "structural_decisions": {
                "|".join(k): v
                for k, v in sorted(
                    structural_decisions.items()
                )
            },
        },
        "outputs": {
            "tsv": (
                "derived/identity/"
                "aggregation_decisions_v1.tsv"
            ),
            "parquet": (
                "derived/identity/"
                "aggregation_decisions_v1.parquet"
            ),
        },
    }

    manifest["outputs"]["tsv_sha256"] = (
        sha256_file(OUT_TSV)
    )

    manifest["outputs"]["parquet_sha256"] = (
        sha256_file(OUT_PARQUET)
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

    print("=== AGGREGATION DECISIONS V1 ===")
    print("rows:", len(out))

    print("\n=== DECISIONS ===")
    print(
        out["aggregation_decision"]
        .value_counts()
        .to_string()
    )

    print("\n=== BY STRUCTURAL CLASS ===")
    print(
        out.groupby(
            [
                "structural_class",
                "aggregation_decision",
            ]
        )
        .size()
        .to_string()
    )

    print("\n=== REVIEW STATUS ===")
    print(
        out["review_status"]
        .value_counts()
        .to_string()
    )

    print("\n=== OUTPUT SHA256 ===")
    print(
        "tsv:",
        sha256_file(OUT_TSV),
    )
    print(
        "parquet:",
        sha256_file(OUT_PARQUET),
    )
    print(
        "manifest:",
        sha256_file(OUT_MANIFEST),
    )


if __name__ == "__main__":
    main()
