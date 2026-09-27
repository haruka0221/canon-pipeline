from pathlib import Path
import hashlib
import json
import os
import unicodedata

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

PREVIOUS = (
    ROOT / "derived/identity/aggregation_decisions_v1.parquet"
)

UNITS = (
    ROOT / "derived/identity/aggregation_review_units_v1.parquet"
)

MEMBERS = (
    ROOT / "derived/identity/aggregation_review_members_v1.parquet"
)

TARGETS = (
    ROOT / "derived/identity/openlibrary_analysis_targets_v1.parquet"
)

ASSERTIONS = (
    ROOT / "derived/identity/identity_assertions_v1.parquet"
)

POLICY = ROOT / "docs/AGGREGATION_POLICY.md"

OUT_DIR = ROOT / "derived/identity"

OUT_TSV = OUT_DIR / "aggregation_decisions_v2.tsv"
OUT_PARQUET = OUT_DIR / "aggregation_decisions_v2.parquet"
OUT_MANIFEST = OUT_DIR / "aggregation_decisions_v2_manifest.json"

CREATED_AT = "2026-09-27"

EXPECTED_ROWS = 32847
EXPECTED_PROMOTED = 112
EXPECTED_ONE_WORK = 31651
EXPECTED_PENDING = 1196
EXPECTED_PROMOTED_TARGETS = 239


def require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


def write_atomic_tsv(df, path):
    tmp = path.with_name(path.name + ".tmp")
    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )
    os.replace(tmp, path)


def write_atomic_parquet(df, path):
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(
        tmp,
        index=False,
        engine="pyarrow",
    )
    os.replace(tmp, path)


def norm_title(value):
    value = unicodedata.normalize(
        "NFKC",
        str(value),
    ).casefold()

    return "".join(
        ch
        for ch in value
        if ch.isalnum()
    )


def main():
    for p in [
        PREVIOUS,
        UNITS,
        MEMBERS,
        TARGETS,
        ASSERTIONS,
        POLICY,
    ]:
        require(p)

    previous = pd.read_parquet(PREVIOUS).fillna("")
    units = pd.read_parquet(UNITS).fillna("")
    members = pd.read_parquet(MEMBERS).fillna("")
    targets = pd.read_parquet(TARGETS).fillna("")
    assertions = pd.read_parquet(ASSERTIONS).fillna("")

    assert len(previous) == EXPECTED_ROWS
    assert previous["unit_anchor_entity_id"].is_unique

    candidates = previous[
        previous["structural_class"].eq(
            "multi_ol_no_explicit_split"
        )
        & previous["aggregation_decision"].eq(
            "MANUAL_REVIEW_REQUIRED"
        )
    ]

    promoted = []

    for drow in candidates.itertuples(index=False):
        anchor = drow.unit_anchor_entity_id

        z = members[
            members["unit_anchor_entity_id"].eq(anchor)
        ]

        ol = z[
            z["is_current_target"]
        ].merge(
            targets[
                [
                    "current_entity_id",
                    "title",
                    "author_keys",
                    "first_publish_year",
                ]
            ],
            left_on="entity_id",
            right_on="current_entity_id",
            how="left",
            validate="one_to_one",
        )

        gr = z[z["source"].eq("goodreads")]
        wd = z[z["source"].eq("wikidata")]

        titles = {
            norm_title(x)
            for x in ol["title"]
            if str(x).strip()
        }

        authors = {
            str(x).strip()
            for x in ol["author_keys"]
            if str(x).strip()
        }

        years = {
            str(x).strip()
            for x in ol["first_publish_year"]
            if str(x).strip()
        }

        # Require every OL row to contribute a non-empty
        # title, author_keys value, and year.
        complete_metadata = (
            len(ol) > 1
            and ol["title"].map(
                lambda x: bool(str(x).strip())
            ).all()
            and ol["author_keys"].map(
                lambda x: bool(str(x).strip())
            ).all()
            and ol["first_publish_year"].map(
                lambda x: bool(str(x).strip())
            ).all()
            and len(titles) == 1
            and len(authors) == 1
            and len(years) == 1
        )

        if not complete_metadata:
            continue

        if len(gr) != 1 or len(wd) != 1:
            continue

        ol_ids = set(ol["entity_id"])
        gr_id = gr.iloc[0]["entity_id"]
        wd_id = wd.iloc[0]["entity_id"]

        az = assertions[
            assertions["left_entity_id"].isin(ol_ids)
            & assertions["right_entity_id"].isin(
                {gr_id, wd_id}
            )
        ]

        gr_rows = az[
            az["right_entity_id"].eq(gr_id)
        ]

        wd_rows = az[
            az["right_entity_id"].eq(wd_id)
        ]

        direct_gr = set(gr_rows["left_entity_id"])
        direct_wd = set(wd_rows["left_entity_id"])

        if direct_gr != ol_ids:
            continue

        if direct_wd != ol_ids:
            continue

        gr_auto_high = True

        for r in gr_rows.itertuples(index=False):
            ev = json.loads(r.evidence)

            if (
                ev.get("resolution_status_detail")
                != "AUTO_MATCH_HIGH"
            ):
                gr_auto_high = False
                break

        if not gr_auto_high:
            continue

        if not wd_rows["confidence"].eq("high").all():
            continue

        promoted.append(anchor)

    promoted = sorted(promoted)

    assert len(promoted) == EXPECTED_PROMOTED

    out = previous.copy()

    mask = out["unit_anchor_entity_id"].isin(promoted)

    assert mask.sum() == EXPECTED_PROMOTED

    out.loc[
        mask,
        "aggregation_decision",
    ] = "ONE_WORK"

    out.loc[
        mask,
        "decision_method",
    ] = "multi_ol_exact_metadata_cross_source_rule"

    out.loc[
        mask,
        "decision_version",
    ] = "v2"

    out.loc[
        mask,
        "review_status",
    ] = "auto_accepted"

    out.loc[
        mask,
        "notes",
    ] = (
        "Multiple current Open Library targets accepted as "
        "one project conceptual work by the strict v2 rule: "
        "same normalized title, same non-empty author_keys, "
        "same non-empty first_publish_year, exactly one "
        "Goodreads and one Wikidata entity, direct SAME "
        "edges from every OL target to both, all Goodreads "
        "AUTO_MATCH_HIGH, and all Wikidata confidence=high."
    )

    out["source_artifact"] = (
        "derived/identity/"
        "aggregation_review_units_v1.parquet"
    )

    out = out.sort_values(
        "unit_anchor_entity_id",
        kind="stable",
    ).reset_index(drop=True)

    assert len(out) == EXPECTED_ROWS

    counts = (
        out["aggregation_decision"]
        .value_counts()
        .to_dict()
    )

    assert counts == {
        "ONE_WORK": EXPECTED_ONE_WORK,
        "MANUAL_REVIEW_REQUIRED": EXPECTED_PENDING,
    }

    v2_rows = out[
        out["decision_version"].eq("v2")
    ]

    assert len(v2_rows) == EXPECTED_PROMOTED

    assert set(v2_rows["decision_method"]) == {
        "multi_ol_exact_metadata_cross_source_rule"
    }

    assert set(v2_rows["aggregation_decision"]) == {
        "ONE_WORK"
    }

    assert set(v2_rows["review_status"]) == {
        "auto_accepted"
    }

    assert (
        v2_rows["current_target_count"].sum()
        == EXPECTED_PROMOTED_TARGETS
    )

    # Every row not promoted must be byte-logically
    # unchanged in the decision fields inherited from v1.
    compare_cols = [
        "unit_anchor_entity_id",
        "structural_class",
        "current_target_count",
        "aggregation_decision",
        "decision_method",
        "decision_version",
        "review_status",
    ]

    old_unmodified = previous[
        ~previous["unit_anchor_entity_id"].isin(promoted)
    ][compare_cols].reset_index(drop=True)

    new_unmodified = out[
        ~out["unit_anchor_entity_id"].isin(promoted)
    ][compare_cols].reset_index(drop=True)

    assert old_unmodified.equals(new_unmodified)

    write_atomic_tsv(out, OUT_TSV)
    write_atomic_parquet(out, OUT_PARQUET)

    manifest = {
        "release": "aggregation-decisions-v2",
        "created_at": CREATED_AT,
        "row_count": len(out),
        "semantics": {
            "previous_release": "aggregation-decisions-v1",
            "update": (
                "112 multi-OL units are promoted from "
                "MANUAL_REVIEW_REQUIRED to ONE_WORK by the "
                "strict multi-OL exact-metadata cross-source rule."
            ),
            "unchanged_rows": 32735,
            "important_note": (
                "aggregation_decisions_v1 remains unchanged "
                "as a historical release."
            ),
        },
        "rule": {
            "name": (
                "multi_ol_exact_metadata_cross_source_rule"
            ),
            "decision_version": "v2",
            "criteria": [
                "multi_ol_no_explicit_split",
                "same normalized non-empty title",
                "same non-empty author_keys",
                "same non-empty first_publish_year",
                "exactly one Goodreads entity",
                "exactly one Wikidata entity",
                "every OL directly SAME to Goodreads",
                "every OL directly SAME to Wikidata",
                "all Goodreads AUTO_MATCH_HIGH",
                "all Wikidata confidence high",
            ],
        },
        "inputs": {
            "previous_decisions": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_decisions_v1.parquet"
                ),
                "sha256": sha256_file(PREVIOUS),
            },
            "review_units": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_review_units_v1.parquet"
                ),
                "sha256": sha256_file(UNITS),
            },
            "review_members": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_review_members_v1.parquet"
                ),
                "sha256": sha256_file(MEMBERS),
            },
            "analysis_targets": {
                "artifact": (
                    "derived/identity/"
                    "openlibrary_analysis_targets_v1.parquet"
                ),
                "sha256": sha256_file(TARGETS),
            },
            "identity_assertions": {
                "artifact": (
                    "derived/identity/"
                    "identity_assertions_v1.parquet"
                ),
                "sha256": sha256_file(ASSERTIONS),
            },
            "aggregation_policy": {
                "artifact": "docs/AGGREGATION_POLICY.md",
                "sha256": sha256_file(POLICY),
                "version": "1",
            },
        },
        "counts": {
            "ONE_WORK": EXPECTED_ONE_WORK,
            "MANUAL_REVIEW_REQUIRED": EXPECTED_PENDING,
            "newly_promoted_units": EXPECTED_PROMOTED,
            "newly_promoted_current_targets": (
                EXPECTED_PROMOTED_TARGETS
            ),
        },
        "promoted_unit_anchor_entity_ids": promoted,
        "outputs": {
            "tsv": (
                "derived/identity/"
                "aggregation_decisions_v2.tsv"
            ),
            "parquet": (
                "derived/identity/"
                "aggregation_decisions_v2.parquet"
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

    os.replace(tmp, OUT_MANIFEST)

    print("=== AGGREGATION DECISIONS V2 ===")
    print("rows:", len(out))

    print("\n=== DECISIONS ===")
    print(
        out["aggregation_decision"]
        .value_counts()
        .to_string()
    )

    print("\n=== NEW V2 DECISIONS ===")
    print("promoted units:", len(v2_rows))
    print(
        "promoted current targets:",
        int(v2_rows["current_target_count"].sum()),
    )

    print("\n=== PENDING BY STRUCTURAL CLASS ===")
    print(
        out[
            out["aggregation_decision"].eq(
                "MANUAL_REVIEW_REQUIRED"
            )
        ]["structural_class"]
        .value_counts()
        .to_string()
    )

    print("\n=== DECISION VERSION ===")
    print(
        out["decision_version"]
        .value_counts()
        .to_string()
    )

    print("\n=== OUTPUT SHA256 ===")
    print("tsv:", sha256_file(OUT_TSV))
    print("parquet:", sha256_file(OUT_PARQUET))
    print("manifest:", sha256_file(OUT_MANIFEST))


if __name__ == "__main__":
    main()
