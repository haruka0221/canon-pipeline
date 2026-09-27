from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

ENTITIES = (
    ROOT / "derived/identity/source_entities_v2.parquet"
)

GOODREADS = (
    ROOT
    / "derived/crosswalks/goodreads_work_crosswalk_v1.tsv"
)

WIKIDATA = (
    ROOT
    / "derived/crosswalks/work_to_wikidata_v2.parquet"
)

OUT_DIR = ROOT / "derived/identity"
OUT_TSV = OUT_DIR / "identity_assertions_v1.tsv"
OUT_PARQUET = OUT_DIR / "identity_assertions_v1.parquet"
OUT_MANIFEST = OUT_DIR / "identity_assertions_v1_manifest.json"

CREATED_AT = "2026-09-27"

EXPECTED_GR = 7624
EXPECTED_WD = 8441
EXPECTED_TOTAL = 16065

REVIEW_STATUS = "not_assessed_for_project_aggregation"


def require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_json(obj: dict) -> str:
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def boolish(v):
    if isinstance(v, bool):
        return v

    s = str(v).strip().lower()

    if s == "true":
        return True

    if s == "false":
        return False

    if s == "":
        return ""

    return str(v)


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
    for p in [
        ENTITIES,
        GOODREADS,
        WIKIDATA,
    ]:
        require(p)

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    ent = pd.read_parquet(
        ENTITIES
    ).fillna("")

    gr = pd.read_csv(
        GOODREADS,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    wd = pd.read_parquet(
        WIKIDATA
    ).fillna("")

    assert len(ent) == 48655
    assert ent["entity_id"].is_unique

    natural_key_to_entity = {}
    entity_snapshot = {}

    for r in ent.itertuples(index=False):
        key = (
            r.source,
            r.source_namespace,
            r.source_id,
        )

        assert key not in natural_key_to_entity

        natural_key_to_entity[key] = r.entity_id
        entity_snapshot[r.entity_id] = r.source_snapshot

    gm = gr[
        gr["crosswalk_decision"].eq("MATCH")
    ].copy()

    wm = wd[
        wd["decision"].eq("MATCH")
    ].copy()

    assert len(gm) == EXPECTED_GR
    assert len(wm) == EXPECTED_WD

    assert gm["ol_work_id"].is_unique
    assert wm["ol_work_id"].is_unique

    rows = []

    # ---------------------------------------------------------
    # Goodreads accepted source-specific work identity
    # ---------------------------------------------------------

    gm = gm.sort_values(
        [
            "ol_work_id",
            "goodreads_work_id",
        ],
        kind="stable",
    )

    for r in gm.itertuples(index=False):
        left = natural_key_to_entity[
            (
                "openlibrary",
                "work",
                r.ol_work_id,
            )
        ]

        right = natural_key_to_entity[
            (
                "goodreads",
                "work",
                r.goodreads_work_id,
            )
        ]

        snapshots = {}

        left_snapshot = entity_snapshot[left]
        right_snapshot = entity_snapshot[right]

        if left_snapshot:
            snapshots["openlibrary"] = left_snapshot

        if right_snapshot:
            snapshots["goodreads"] = right_snapshot

        evidence = {
            "source_snapshots": snapshots,
            "crosswalk_decision": r.crosswalk_decision,
            "processing_status": r.processing_status,
            "resolution_status_detail": (
                r.resolution_status_detail
            ),
            "title_match_type": r.title_match_type,
            "author_match_quality": (
                r.author_match_quality
            ),
            "review_needed": r.review_needed,
            "baseline_resolution_version": (
                r.baseline_resolution_version
            ),
            "baseline_source_file": (
                r.baseline_source_file
            ),
        }

        if str(
            r.resolution_status_detail
        ).startswith("AUTO_MATCH_WIKIDATA"):
            evidence[
                "wikidata_evidence_used"
            ] = True

        rows.append(
            {
                "_source_order": 0,
                "_left_source_id": r.ol_work_id,
                "_right_source_id": (
                    r.goodreads_work_id
                ),
                "left_entity_id": left,
                "right_entity_id": right,
                "identity_type": "work",
                "identity_decision": "SAME",
                "method": (
                    "goodreads_resolution_pipeline"
                ),
                "method_version": (
                    r.baseline_resolution_version
                ),
                "evidence": stable_json(evidence),
                "source_artifact": (
                    "derived/crosswalks/"
                    "goodreads_work_crosswalk_v1.tsv"
                ),
                "source_snapshot": right_snapshot,
                "confidence": "",
                "review_status": REVIEW_STATUS,
                "created_at": CREATED_AT,
            }
        )

    # ---------------------------------------------------------
    # Wikidata accepted source-specific work identity
    # ---------------------------------------------------------

    wm = wm.sort_values(
        [
            "ol_work_id",
            "wikidata_qid",
        ],
        kind="stable",
    )

    for r in wm.itertuples(index=False):
        left = natural_key_to_entity[
            (
                "openlibrary",
                "work",
                r.ol_work_id,
            )
        ]

        right = natural_key_to_entity[
            (
                "wikidata",
                "item",
                r.wikidata_qid,
            )
        ]

        snapshots = {}

        left_snapshot = entity_snapshot[left]
        right_snapshot = entity_snapshot[right]

        if left_snapshot:
            snapshots["openlibrary"] = left_snapshot

        if right_snapshot:
            snapshots["wikidata"] = right_snapshot

        evidence = {
            "source_snapshots": snapshots,
            "decision": r.decision,
            "confidence": r.confidence,
            "resolution_stage": r.resolution_stage,
            "decision_source": r.decision_source,
            "context_safe_fallback": boolish(
                r.context_safe_fallback
            ),
            "correction_applied": boolish(
                r.correction_applied
            ),
            "original_decision": (
                r.original_decision
            ),
            "original_wikidata_qid": (
                r.original_wikidata_qid
            ),
            "correction_type": r.correction_type,
            "correction_evidence_status": (
                r.correction_evidence_status
            ),
            "correction_reason": (
                r.correction_reason
            ),
        }

        rows.append(
            {
                "_source_order": 1,
                "_left_source_id": r.ol_work_id,
                "_right_source_id": r.wikidata_qid,
                "left_entity_id": left,
                "right_entity_id": right,
                "identity_type": "work",
                "identity_decision": "SAME",
                "method": "llm_judge",
                "method_version": r.decision_source,
                "evidence": stable_json(evidence),
                "source_artifact": (
                    "derived/crosswalks/"
                    "work_to_wikidata_v2.parquet"
                ),
                "source_snapshot": right_snapshot,
                "confidence": r.confidence,
                "review_status": REVIEW_STATUS,
                "created_at": CREATED_AT,
            }
        )

    out = pd.DataFrame(rows)

    assert len(out) == EXPECTED_TOTAL

    out = out.sort_values(
        [
            "_source_order",
            "_left_source_id",
            "_right_source_id",
        ],
        kind="stable",
    ).reset_index(drop=True)

    out.insert(
        0,
        "assertion_id",
        [
            f"A{i:09d}"
            for i in range(
                1,
                len(out) + 1,
            )
        ],
    )

    out = out.drop(
        columns=[
            "_source_order",
            "_left_source_id",
            "_right_source_id",
        ]
    )

    columns = [
        "assertion_id",
        "left_entity_id",
        "right_entity_id",
        "identity_type",
        "identity_decision",
        "method",
        "method_version",
        "evidence",
        "source_artifact",
        "source_snapshot",
        "confidence",
        "review_status",
        "created_at",
    ]

    out = out[columns]

    # ---------------------------------------------------------
    # Validation
    # ---------------------------------------------------------

    assert out["assertion_id"].is_unique
    assert out.iloc[0]["assertion_id"] == "A000000001"
    assert (
        out.iloc[-1]["assertion_id"]
        == "A000016065"
    )

    assert set(out["identity_type"]) == {"work"}
    assert set(out["identity_decision"]) == {"SAME"}

    assert set(out["review_status"]) == {
        REVIEW_STATUS
    }

    pair_cols = [
        "left_entity_id",
        "right_entity_id",
    ]

    assert not out.duplicated(
        subset=pair_cols
    ).any()

    entity_ids = set(ent["entity_id"])

    assert set(
        out["left_entity_id"]
    ).issubset(entity_ids)

    assert set(
        out["right_entity_id"]
    ).issubset(entity_ids)

    gr_out = out[
        out["source_artifact"].eq(
            "derived/crosswalks/"
            "goodreads_work_crosswalk_v1.tsv"
        )
    ]

    wd_out = out[
        out["source_artifact"].eq(
            "derived/crosswalks/"
            "work_to_wikidata_v2.parquet"
        )
    ]

    assert len(gr_out) == EXPECTED_GR
    assert len(wd_out) == EXPECTED_WD

    assert set(gr_out["confidence"]) == {""}

    assert (
        wd_out["confidence"]
        .value_counts()
        .to_dict()
        == {
            "high": 7985,
            "medium": 437,
            "low": 19,
        }
    )

    wikidata_supported_gr = sum(
        '"wikidata_evidence_used":true'
        in x
        for x in gr_out["evidence"]
    )

    assert wikidata_supported_gr == 16

    # Goodreads assertion source_snapshot must be the
    # right-hand Goodreads source snapshot.
    assert set(
        gr_out["source_snapshot"]
    ) == {"2017"}

    # Wikidata assertion source_snapshot must be the
    # right-hand Wikidata source snapshot.
    assert set(
        wd_out["source_snapshot"]
    ) == {"2026-08-05"}

    write_atomic_tsv(
        out,
        OUT_TSV,
    )

    write_atomic_parquet(
        out,
        OUT_PARQUET,
    )

    method_counts = (
        out.groupby(
            ["method", "method_version"],
            dropna=False,
        )
        .size()
        .to_dict()
    )

    manifest = {
        "release": "identity-assertions-v1",
        "created_at": CREATED_AT,
        "row_count": len(out),
        "semantics": {
            "identity_type": "work",
            "identity_decision": "SAME",
            "note": (
                "Each row records an accepted "
                "source-specific work-identity judgment. "
                "SAME does not by itself establish "
                "project-work membership and must not be "
                "transitively closed into project works "
                "without a separate aggregation policy."
            ),
        },
        "source_entities": {
            "release": "source-entities-v2",
            "artifact": (
                "derived/identity/"
                "source_entities_v2.parquet"
            ),
            "sha256": sha256_file(ENTITIES),
        },
        "inputs": {
            "goodreads": {
                "artifact": (
                    "derived/crosswalks/"
                    "goodreads_work_crosswalk_v1.tsv"
                ),
                "sha256": sha256_file(GOODREADS),
                "accepted_match_rows": EXPECTED_GR,
                "method": (
                    "goodreads_resolution_pipeline"
                ),
                "method_version": "v13",
                "right_source_snapshot": "2017",
                "wikidata_supported_match_rows": 16,
            },
            "wikidata": {
                "artifact": (
                    "derived/crosswalks/"
                    "work_to_wikidata_v2.parquet"
                ),
                "sha256": sha256_file(WIKIDATA),
                "accepted_match_rows": EXPECTED_WD,
                "method": "llm_judge",
                "method_version": (
                    "gpt-5.6-luna_v6"
                ),
                "right_source_snapshot": (
                    "2026-08-05"
                ),
                "confidence_counts": {
                    "high": 7985,
                    "medium": 437,
                    "low": 19,
                },
            },
        },
        "assertion_id_policy": {
            "initial_release": (
                "A000000001 through A000016065"
            ),
            "ordering": [
                "Goodreads assertions first",
                "Wikidata assertions second",
                (
                    "within each source: lexical "
                    "Open Library source_id, then "
                    "lexical external source_id"
                ),
            ],
            "future_policy": (
                "Released A IDs are never renumbered "
                "or reused. Future assertions append "
                "after the current maximum A ID."
            ),
        },
        "review_status": REVIEW_STATUS,
        "outputs": {
            "tsv": (
                "derived/identity/"
                "identity_assertions_v1.tsv"
            ),
            "parquet": (
                "derived/identity/"
                "identity_assertions_v1.parquet"
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

    print("rows:", len(out))
    print(
        "first assertion:",
        out.iloc[0]["assertion_id"],
    )
    print(
        "last assertion:",
        out.iloc[-1]["assertion_id"],
    )

    print("\n=== SOURCE ASSERTION COUNTS ===")
    print("Goodreads:", len(gr_out))
    print("Wikidata:", len(wd_out))

    print("\n=== DECISIONS ===")
    print(
        out["identity_decision"]
        .value_counts()
        .to_string()
    )

    print("\n=== METHODS ===")
    for k, v in sorted(method_counts.items()):
        print(k, v)

    print("\n=== WIKIDATA CONFIDENCE ===")
    print(
        wd_out["confidence"]
        .value_counts()
        .to_string()
    )

    print(
        "\nGoodreads assertions using "
        "Wikidata evidence:",
        wikidata_supported_gr,
    )

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
