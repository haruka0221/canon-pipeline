from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

PREVIOUS = (
    ROOT / "derived/identity/aggregation_decisions_v3.parquet"
)

ADJUDICATION = (
    ROOT
    / "derived/identity/"
    "aggregation_llm_review_adjudication_v1.parquet"
)

POLICY = ROOT / "docs/AGGREGATION_POLICY.md"

LLM_REVIEW_DOC = (
    ROOT / "docs/AGGREGATION_LLM_REVIEW.md"
)

OUT_DIR = ROOT / "derived/identity"

OUT_TSV = OUT_DIR / "aggregation_decisions_v4.tsv"
OUT_PARQUET = OUT_DIR / "aggregation_decisions_v4.parquet"
OUT_MANIFEST = (
    OUT_DIR / "aggregation_decisions_v4_manifest.json"
)

CREATED_AT = "2026-09-27"

EXPECTED_ROWS = 32847

EXPECTED_PREVIOUS_ONE_WORK = 31653
EXPECTED_PREVIOUS_PENDING = 1194

EXPECTED_PROMOTED = 433
EXPECTED_PROMOTED_TARGETS = 923

EXPECTED_ONE_WORK = 32086
EXPECTED_PENDING = 761
EXPECTED_PENDING_TARGETS = 2083

DECISION_METHOD = (
    "llm_review_strict_external_support_rule"
)


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


def main():
    for p in [
        PREVIOUS,
        ADJUDICATION,
        POLICY,
        LLM_REVIEW_DOC,
    ]:
        require(p)

    previous = pd.read_parquet(
        PREVIOUS
    ).fillna("")

    adjudication = pd.read_parquet(
        ADJUDICATION
    ).fillna("")

    assert len(previous) == EXPECTED_ROWS
    assert previous[
        "unit_anchor_entity_id"
    ].is_unique

    prev_counts = (
        previous["aggregation_decision"]
        .value_counts()
        .to_dict()
    )

    assert prev_counts == {
        "ONE_WORK": EXPECTED_PREVIOUS_ONE_WORK,
        "MANUAL_REVIEW_REQUIRED": (
            EXPECTED_PREVIOUS_PENDING
        ),
    }

    assert len(adjudication) == 1194
    assert adjudication[
        "unit_anchor_entity_id"
    ].is_unique

    # The LLM review covered exactly the v3 pending units.
    previous_pending = previous[
        previous["aggregation_decision"].eq(
            "MANUAL_REVIEW_REQUIRED"
        )
    ]

    assert set(
        adjudication["unit_anchor_entity_id"]
    ) == set(
        previous_pending[
            "unit_anchor_entity_id"
        ]
    )

    accepted = adjudication[
        adjudication[
            "final_auto_accept_eligible"
        ].astype(bool)
    ].copy()

    held = adjudication[
        ~adjudication[
            "final_auto_accept_eligible"
        ].astype(bool)
    ].copy()

    assert len(accepted) == EXPECTED_PROMOTED

    assert int(
        accepted[
            "current_target_count"
        ].sum()
    ) == EXPECTED_PROMOTED_TARGETS

    assert len(held) == EXPECTED_PENDING

    assert int(
        held[
            "current_target_count"
        ].sum()
    ) == EXPECTED_PENDING_TARGETS

    # Revalidate the key final-gate semantics before using
    # adjudication as a project aggregation decision.
    assert set(
        accepted["llm_decision"]
    ) == {"ONE_WORK"}

    assert set(
        accepted["llm_confidence"]
    ) == {"high"}

    assert not accepted[
        "llm_needs_human_review"
    ].astype(bool).any()

    assert accepted[
        "runner_auto_accept_eligible"
    ].astype(bool).all()

    assert set(
        accepted["structural_class"]
    ) == {
        "multi_ol_no_explicit_split"
    }

    assert (
        accepted[
            "strong_goodreads_support"
        ].astype(bool)
        |
        accepted[
            "strong_wikidata_support"
        ].astype(bool)
    ).all()

    promoted = sorted(
        accepted["unit_anchor_entity_id"]
        .tolist()
    )

    out = previous.copy()

    mask = out[
        "unit_anchor_entity_id"
    ].isin(promoted)

    assert int(mask.sum()) == EXPECTED_PROMOTED

    # All promoted rows must have been unresolved in v3.
    assert set(
        out.loc[
            mask,
            "aggregation_decision",
        ]
    ) == {"MANUAL_REVIEW_REQUIRED"}

    out.loc[
        mask,
        "aggregation_decision",
    ] = "ONE_WORK"

    out.loc[
        mask,
        "decision_method",
    ] = DECISION_METHOD

    out.loc[
        mask,
        "decision_version",
    ] = "v4"

    out.loc[
        mask,
        "review_status",
    ] = "auto_accepted"

    out.loc[
        mask,
        "notes",
    ] = (
        "Multiple current Open Library targets accepted as "
        "one project conceptual work after closed-book LLM "
        "review with prompt v2 and deterministic adjudication. "
        "The LLM returned ONE_WORK with high confidence and "
        "no human-review request; relation flags were limited "
        "to duplicate_record/title_variant/authorship_variant "
        "and included duplicate_record; the unit was "
        "multi_ol_no_explicit_split; and every current OL "
        "target converged directly on at least one qualifying "
        "common Goodreads or high-confidence Wikidata identity. "
        "See aggregation_llm_review_adjudication_v1 and "
        "docs/AGGREGATION_LLM_REVIEW.md."
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

    v4_rows = out[
        out["decision_version"].eq("v4")
    ]

    assert len(v4_rows) == EXPECTED_PROMOTED

    assert set(
        v4_rows["unit_anchor_entity_id"]
    ) == set(promoted)

    assert int(
        v4_rows[
            "current_target_count"
        ].sum()
    ) == EXPECTED_PROMOTED_TARGETS

    assert set(
        v4_rows["decision_method"]
    ) == {DECISION_METHOD}

    assert set(
        v4_rows["aggregation_decision"]
    ) == {"ONE_WORK"}

    assert set(
        v4_rows["review_status"]
    ) == {"auto_accepted"}

    # Every row outside the promoted set must preserve
    # all v3 fields exactly.
    unchanged_cols = list(previous.columns)

    old_unmodified = (
        previous[
            ~previous[
                "unit_anchor_entity_id"
            ].isin(promoted)
        ][unchanged_cols]
        .reset_index(drop=True)
    )

    new_unmodified = (
        out[
            ~out[
                "unit_anchor_entity_id"
            ].isin(promoted)
        ][unchanged_cols]
        .reset_index(drop=True)
    )

    assert old_unmodified.equals(
        new_unmodified
    )

    # All 14 structural cross-source conflicts remain held.
    conflicts = out[
        out["structural_class"].eq(
            "cross_source_conflict"
        )
    ]

    assert len(conflicts) == 14

    assert set(
        conflicts[
            "aggregation_decision"
        ]
    ) == {"MANUAL_REVIEW_REQUIRED"}

    pending = out[
        out["aggregation_decision"].eq(
            "MANUAL_REVIEW_REQUIRED"
        )
    ]

    assert len(pending) == EXPECTED_PENDING

    assert int(
        pending[
            "current_target_count"
        ].sum()
    ) == EXPECTED_PENDING_TARGETS

    write_atomic_tsv(
        out,
        OUT_TSV,
    )

    write_atomic_parquet(
        out,
        OUT_PARQUET,
    )

    manifest = {
        "release": "aggregation-decisions-v4",
        "created_at": CREATED_AT,
        "row_count": len(out),
        "semantics": {
            "previous_release": (
                "aggregation-decisions-v3"
            ),
            "update": (
                "Promote exactly the 433 units that passed "
                "LLM review v1 plus the deterministic strict "
                "external-support adjudication gate."
            ),
            "llm_is_review_evidence_not_project_decision": True,
            "held_units_are_intentionally_unresolved": True,
            "held_units": EXPECTED_PENDING,
            "held_current_targets": (
                EXPECTED_PENDING_TARGETS
            ),
            "important_note": (
                "No MULTIPLE_WORKS or UNRESOLVED LLM result "
                "is converted into a project split or merge. "
                "All non-accepted units remain unchanged from "
                "aggregation decisions v3."
            ),
        },
        "rule": {
            "name": DECISION_METHOD,
            "decision_version": "v4",
            "criteria": [
                (
                    "final_auto_accept_eligible=true in "
                    "aggregation_llm_review_adjudication_v1"
                ),
                "LLM decision ONE_WORK",
                "LLM confidence high",
                "LLM needs_human_review=false",
                "runner auto-accept gate passed",
                (
                    "relation flags limited to "
                    "duplicate_record, title_variant, "
                    "authorship_variant"
                ),
                "duplicate_record flag present",
                "multi_ol_no_explicit_split",
                (
                    "all current OL targets share at least "
                    "one qualifying strong common Goodreads "
                    "or Wikidata identity"
                ),
            ],
        },
        "inputs": {
            "previous_decisions": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_decisions_v3.parquet"
                ),
                "sha256": sha256_file(
                    PREVIOUS
                ),
            },
            "llm_adjudication": {
                "artifact": (
                    "derived/identity/"
                    "aggregation_llm_review_"
                    "adjudication_v1.parquet"
                ),
                "sha256": sha256_file(
                    ADJUDICATION
                ),
            },
            "aggregation_policy": {
                "artifact": (
                    "docs/AGGREGATION_POLICY.md"
                ),
                "sha256": sha256_file(
                    POLICY
                ),
                "version": "1",
            },
            "llm_review_methodology": {
                "artifact": (
                    "docs/AGGREGATION_LLM_REVIEW.md"
                ),
                "sha256": sha256_file(
                    LLM_REVIEW_DOC
                ),
            },
        },
        "counts": {
            "ONE_WORK": EXPECTED_ONE_WORK,
            "MANUAL_REVIEW_REQUIRED": (
                EXPECTED_PENDING
            ),
            "newly_promoted_units": (
                EXPECTED_PROMOTED
            ),
            "newly_promoted_current_targets": (
                EXPECTED_PROMOTED_TARGETS
            ),
            "remaining_pending_units": (
                EXPECTED_PENDING
            ),
            "remaining_pending_current_targets": (
                EXPECTED_PENDING_TARGETS
            ),
        },
        "promoted_unit_anchor_entity_ids": promoted,
        "outputs": {
            "tsv": (
                "derived/identity/"
                "aggregation_decisions_v4.tsv"
            ),
            "parquet": (
                "derived/identity/"
                "aggregation_decisions_v4.parquet"
            ),
        },
    }

    manifest["outputs"]["tsv_sha256"] = (
        sha256_file(OUT_TSV)
    )

    manifest[
        "outputs"
    ]["parquet_sha256"] = (
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

    print("=== AGGREGATION DECISIONS V4 ===")
    print("rows:", len(out))

    print("\n=== DECISIONS ===")
    print(
        out[
            "aggregation_decision"
        ]
        .value_counts()
        .to_string()
    )

    print("\n=== NEW V4 DECISIONS ===")
    print(
        "promoted units:",
        len(v4_rows),
    )
    print(
        "promoted current targets:",
        int(
            v4_rows[
                "current_target_count"
            ].sum()
        ),
    )

    print("\n=== REMAINING PENDING ===")
    print(
        "pending units:",
        len(pending),
    )
    print(
        "pending current targets:",
        int(
            pending[
                "current_target_count"
            ].sum()
        ),
    )

    print("\n=== PENDING BY STRUCTURAL CLASS ===")
    print(
        pending[
            "structural_class"
        ]
        .value_counts()
        .to_string()
    )

    print("\n=== DECISION VERSION ===")
    print(
        out[
            "decision_version"
        ]
        .value_counts()
        .to_string()
    )

    print(
        "\nPASS: all 14 cross-source conflicts "
        "remain pending."
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
