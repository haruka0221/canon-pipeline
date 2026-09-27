from pathlib import Path
import hashlib
import json
import os
import unicodedata

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

PREVIOUS = (
    ROOT / "derived/identity/aggregation_decisions_v2.parquet"
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

OUT_TSV = OUT_DIR / "aggregation_decisions_v3.tsv"
OUT_PARQUET = OUT_DIR / "aggregation_decisions_v3.parquet"
OUT_MANIFEST = OUT_DIR / "aggregation_decisions_v3_manifest.json"

CREATED_AT = "2026-09-27"

EXPECTED_ROWS = 32847
EXPECTED_PROMOTED = 2
EXPECTED_PROMOTED_ANCHORS = {
    "E000016422",
    "E000018958",
}
EXPECTED_PROMOTED_TARGETS = 5

EXPECTED_ONE_WORK = 31653
EXPECTED_PENDING = 1194


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
        MEMBERS,
        TARGETS,
        ASSERTIONS,
        POLICY,
    ]:
        require(p)

    previous = pd.read_parquet(
        PREVIOUS
    ).fillna("")

    members = pd.read_parquet(
        MEMBERS
    ).fillna("")

    targets = pd.read_parquet(
        TARGETS
    ).fillna("")

    assertions = pd.read_parquet(
        ASSERTIONS
    ).fillna("")

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
        )

        if not complete_metadata:
            continue

        titles = {
            norm_title(x)
            for x in ol["title"]
        }

        authors = {
            str(x).strip()
            for x in ol["author_keys"]
        }

        years = {
            str(x).strip()
            for x in ol["first_publish_year"]
        }

        if not (
            len(titles) == 1
            and len(authors) == 1
            and len(years) == 1
        ):
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

        if set(gr_rows["left_entity_id"]) != ol_ids:
            continue

        if set(wd_rows["left_entity_id"]) != ol_ids:
            continue

        if not wd_rows["confidence"].eq("high").all():
            continue

        gr_ok = True

        for r in gr_rows.itertuples(index=False):
            ev = json.loads(r.evidence)

            if (
                ev.get("resolution_status_detail")
                != "AUTO_MATCH_IDENTITY_EVIDENCE"
            ):
                gr_ok = False
                break

            if ev.get("author_match_quality") not in {
                "IDENTITY_OL_DIRECT",
                "IDENTITY_OL_REDIRECT_DIRECT",
            }:
                gr_ok = False
                break

            if str(ev.get("review_needed", "")) != "0":
                gr_ok = False
                break

            if ev.get("title_match_type") not in {
                "WORK_FULL",
                "BOOK_FULL",
            }:
                gr_ok = False
                break

            if ev.get("crosswalk_decision") != "MATCH":
                gr_ok = False
                break

            if ev.get("processing_status") != "processed_match":
                gr_ok = False
                break

        if not gr_ok:
            continue

        promoted.append(anchor)

    promoted = sorted(promoted)

    assert len(promoted) == EXPECTED_PROMOTED
    assert set(promoted) == EXPECTED_PROMOTED_ANCHORS

    out = previous.copy()

    mask = out[
        "unit_anchor_entity_id"
    ].isin(promoted)

    assert int(mask.sum()) == EXPECTED_PROMOTED

    out.loc[
        mask,
        "aggregation_decision",
    ] = "ONE_WORK"

    out.loc[
        mask,
        "decision_method",
    ] = "multi_ol_identity_evidence_cross_source_rule"

    out.loc[
        mask,
        "decision_version",
    ] = "v3"

    out.loc[
        mask,
        "review_status",
    ] = "auto_accepted"

    out.loc[
        mask,
        "notes",
    ] = (
        "Multiple current Open Library targets accepted as "
        "one project conceptual work by the strict v3 "
        "identity-evidence rule: same normalized title, "
        "same non-empty author_keys and first_publish_year, "
        "direct SAME edges from every OL target to one "
        "Goodreads and one Wikidata entity, Goodreads "
        "AUTO_MATCH_IDENTITY_EVIDENCE with direct/redirect "
        "Open Library identity evidence and review_needed=0, "
        "and Wikidata confidence=high."
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

    v3_rows = out[
        out["decision_version"].eq("v3")
    ]

    assert len(v3_rows) == EXPECTED_PROMOTED

    assert set(
        v3_rows["unit_anchor_entity_id"]
    ) == EXPECTED_PROMOTED_ANCHORS

    assert int(
        v3_rows["current_target_count"].sum()
    ) == EXPECTED_PROMOTED_TARGETS

    assert set(
        v3_rows["decision_method"]
    ) == {
        "multi_ol_identity_evidence_cross_source_rule"
    }

    assert set(
        v3_rows["aggregation_decision"]
    ) == {"ONE_WORK"}

    assert set(
        v3_rows["review_status"]
    ) == {"auto_accepted"}

    # Every row not promoted must preserve its previous
    # decision fields exactly.
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
        ~previous[
            "unit_anchor_entity_id"
        ].isin(promoted)
    ][compare_cols].reset_index(drop=True)

    new_unmodified = out[
        ~out[
            "unit_anchor_entity_id"
        ].isin(promoted)
    ][compare_cols].reset_index(drop=True)

    assert old_unmodified.equals(new_unmodified)

    # All cross-source conflicts remain pending.
    conflicts = out[
        out["structural_class"].eq(
            "cross_source_conflict"
        )
    ]

    assert len(conflicts) == 14

    assert set(
        conflicts["aggregation_decision"]
    ) == {"MANUAL_REVIEW_REQUIRED"}

    # Two Solitudes must remain pending because one direct
    # OL -> Wikidata assertion is absent.
    two_solitudes = out[
        out["unit_anchor_entity_id"].eq(
            "E000008831"
        )
    ]

    assert len(two_solitudes) == 1

    assert (
        two_solitudes.iloc[0][
            "aggregation_decision"
        ]
        == "MANUAL_REVIEW_REQUIRED"
    )

    write_atomic_tsv(
        out,
        OUT_TSV,
    )

    write_atomic_parquet(
        out,
        OUT_PARQUET,
    )

    manifest = {
        "release": "aggregation-decisions-v3",
        "created_at": CREATED_AT,
        "row_count": len(out),
        "semantics": {
            "previous_release": (
                "aggregation-decisions-v2"
            ),
            "update": (
                "Two additional multi-OL units are promoted "
                "from MANUAL_REVIEW_REQUIRED to ONE_WORK by "
                "the strict direct Open Library identity-"
                "evidence cross-source rule."
            ),
            "unchanged_rows": 32845,
            "important_note": (
                "Earlier aggregation-decision releases "
                "remain unchanged as historical releases."
            ),
        },
        "rule": {
            "name": (
                "multi_ol_identity_evidence_cross_source_rule"
            ),
            "decision_version": "v3",
            "criteria": [
                "multi_ol_no_explicit_split",
                "same normalized non-empty title",
                "same non-empty author_keys",
                "same non-empty first_publish_year",
                "exactly one Goodreads entity",
                "exactly one Wikidata entity",
                "every OL directly SAME to Goodreads",
                "every OL directly SAME to Wikidata",
                (
                    "all Goodreads "
                    "AUTO_MATCH_IDENTITY_EVIDENCE"
                ),
                (
                    "Goodreads author evidence is "
                    "IDENTITY_OL_DIRECT or "
                    "IDENTITY_OL_REDIRECT_DIRECT"
                ),
                "Goodreads review_needed=0",
                "Goodreads full title match",
                "all Wikidata confidence high",
            ],
        },
        "inputs": {
            "previous_decisions": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_decisions_v2.parquet"
                ),
                "sha256": sha256_file(PREVIOUS),
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
                "aggregation_decisions_v3.tsv"
            ),
            "parquet": (
                "derived/identity/"
                "aggregation_decisions_v3.parquet"
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

    print("=== AGGREGATION DECISIONS V3 ===")
    print("rows:", len(out))

    print("\n=== DECISIONS ===")
    print(
        out["aggregation_decision"]
        .value_counts()
        .to_string()
    )

    print("\n=== NEW V3 DECISIONS ===")
    print("promoted units:", len(v3_rows))
    print(
        "promoted current targets:",
        int(v3_rows["current_target_count"].sum()),
    )
    print(
        v3_rows[
            [
                "unit_anchor_entity_id",
                "current_target_count",
                "decision_method",
            ]
        ].to_string(index=False)
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

    print("\nPASS: Two Solitudes remains pending.")

    print("\n=== OUTPUT SHA256 ===")
    print("tsv:", sha256_file(OUT_TSV))
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
