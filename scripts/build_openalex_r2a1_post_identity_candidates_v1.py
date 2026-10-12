from pathlib import Path
from collections import Counter
import hashlib
import json

import pandas as pd
import pyarrow.dataset as ds

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "derived/openalex_production"
IDENTITY = ROOT / "derived/identity"

SCAN = Path(
    "/media/hdd1/user/tsutsui/openalex/scans/"
    "full_r23_v1/full_2040files_4a275210"
)

EVIDENCE = (
    SCAN / "openalex_retrieval_full_r23_hit_evidence_v1.parquet"
)

SCAN_MANIFEST = SCAN / "openalex_retrieval_full_r23_scan_v1_manifest.json"

REGISTRY = (
    BASE / "retrieval_match_registry_full_v1"
    / "openalex_retrieval_match_registry_full_v1.parquet"
)

PRIMARY = (
    BASE / "retrieval_r2a1_baseline_validation_sample_v1"
    / "openalex_r2a1_baseline_primary_pair_sample_v1.tsv"
)

WORKS = IDENTITY / "project_works_v7.tsv"
SUSPENSIONS = IDENTITY / "project_work_identity_suspensions_v1.tsv"

OUT = BASE / "retrieval_r2a1_post_identity_candidates_v1"

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def read(path):
    return pd.read_csv(
        path, sep="\t", dtype=str, keep_default_na=False
    )

def candidate_id(wid, oid):
    value = f"R2_A1_BASELINE\t{wid}\t{oid}"
    return "OABASEV1_" + hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()[:16]

def main():
    if OUT.exists():
        raise SystemExit("STOP: output directory exists")

    manifest = json.loads(SCAN_MANIFEST.read_text())
    expected_snapshot = (
        "57959e90573d6ef2adb953fd747ba718"
        "54819880f762077f680083476d490fc9"
    )

    assert manifest["snapshot"]["full_inventory_sha256"] == (
        expected_snapshot
    )
    assert manifest["snapshot"]["processed_inventory_sha256"] == (
        expected_snapshot
    )

    works = read(WORKS)
    suspended = read(SUSPENSIONS)
    primary = read(PRIMARY)

    assert len(works) == 32089
    assert len(suspended) == 17
    assert len(primary) == 800

    status_map = dict(zip(
        works["project_work_id"], works["status"]
    ))
    affected = set(suspended["project_work_id"])

    # Identical R2+A1 retrieval filter to the frozen
    # baseline sample-building script.
    dataset = ds.dataset(str(EVIDENCE), format="parquet")

    evidence = dataset.to_table(
        columns=[
            "query_id",
            "project_work_id",
            "openalex_work_id",
            "title_match_in_title",
            "title_match_in_abstract",
            "author_a1_hit",
        ],
        filter=(
            (ds.field("target_lane") == "resolved_w")
            & (ds.field("query_route") == "R2")
            & (ds.field("author_a1_hit") == True)
        ),
    ).to_pandas()

    registry = pd.read_parquet(
        REGISTRY,
        columns=["query_id", "title_match_token_count"]
    )

    assert registry["query_id"].is_unique

    evidence = evidence.merge(
        registry,
        on="query_id",
        validate="many_to_one",
    )

    evidence["title_match_token_count"] = pd.to_numeric(
        evidence["title_match_token_count"],
        errors="raise",
    ).astype(int)

    pairs = (
        evidence.groupby(
            ["project_work_id", "openalex_work_id"],
            sort=True
        )
        .agg(
            evidence_row_count=("query_id", "size"),
            query_count=("query_id", "nunique"),
            title_match_token_count_min=(
                "title_match_token_count", "min"
            ),
            title_match_token_count_max=(
                "title_match_token_count", "max"
            ),
            any_title_match_in_title=(
                "title_match_in_title", "any"
            ),
            any_title_match_in_abstract=(
                "title_match_in_abstract", "any"
            ),
        )
        .reset_index()
    )

    assert len(pairs) == 290480
    assert pairs["project_work_id"].nunique() == 6873

    pairs["baseline_candidate_id"] = [
        candidate_id(w, o)
        for w, o in zip(
            pairs["project_work_id"],
            pairs["openalex_work_id"],
        )
    ]

    assert pairs["baseline_candidate_id"].is_unique
    assert set(primary["baseline_candidate_id"]).issubset(
        set(pairs["baseline_candidate_id"])
    )

    title = pairs["any_title_match_in_title"]
    abstract = pairs["any_title_match_in_abstract"]

    pairs["hit_location"] = "ABSTRACT_ONLY"
    pairs.loc[title & ~abstract, "hit_location"] = "TITLE_ONLY"
    pairs.loc[title & abstract, "hit_location"] = (
        "TITLE_AND_ABSTRACT"
    )

    assert pairs["hit_location"].value_counts().to_dict() == {
        "ABSTRACT_ONLY": 171998,
        "TITLE_ONLY": 62345,
        "TITLE_AND_ABSTRACT": 56137,
    }

    def identity_state(wid):
        # Including restored Alcott: its old retrieval
        # target was still the overaggregated OL Work.
        if wid in affected:
            return "HOLD_LEGACY_OVERAGGREGATED_TARGET"

        status = status_map.get(wid, "UNKNOWN")

        if status == "active":
            return "ELIGIBLE_FOR_R2A1_ADJUDICATION"

        if status == "superseded":
            return "HOLD_SUPERSEDED_PROJECT_W"

        return "HOLD_OTHER_IDENTITY_STATUS"

    pairs["identity_gate"] = [
        identity_state(w)
        for w in pairs["project_work_id"]
    ]

    assert not pairs["identity_gate"].isna().any()

    counts = pairs["identity_gate"].value_counts().to_dict()

    # These are retrieval candidates, not accepted
    # target references or confirmed citation counts.
    OUT.mkdir(parents=True)

    output = OUT / "openalex_r2a1_post_identity_candidates_v1.parquet"
    summary = OUT / "openalex_r2a1_post_identity_summary_v1.json"
    release = OUT / "openalex_r2a1_post_identity_manifest_v1.json"

    pairs.to_parquet(output, index=False)

    result = {
        "release": "openalex-r2a1-post-identity-candidates-v1",
        "frozen_baseline_candidate_pairs": len(pairs),
        "identity_gate_counts": {
            k: int(v) for k, v in counts.items()
        },
        "affected_predecessor_w_count": len(affected),
        "primary_sample_membership_preserved": 800,
        "semantics": {
            "eligible": (
                "Identity eligibility only. "
                "Not an accepted target-reference judgment."
            ),
            "legacy_holds": (
                "Includes original Alcott target despite "
                "restoration of its conceptual W ID in v7."
            ),
            "frozen_primary_and_human_audit": "UNCHANGED",
            "new_identity_decisions": 0,
            "new_target_attribution_decisions": 0,
        },
    }

    summary.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n", encoding="utf-8"
    )

    release.write_text(
        json.dumps({
            "release": result["release"],
            "inputs": {
                str(WORKS.relative_to(ROOT)): sha(WORKS),
                str(SUSPENSIONS.relative_to(ROOT)): sha(SUSPENSIONS),
                str(PRIMARY.relative_to(ROOT)): sha(PRIMARY),
                "scan_manifest_sha256": sha(SCAN_MANIFEST),
            },
            "outputs": {
                output.name: sha(output),
                summary.name: sha(summary),
            },
            "snapshot_inventory_sha256": expected_snapshot,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8"
    )

    print("=== R2+A1 POST-IDENTITY CANDIDATES ===")
    print("original baseline pairs:", len(pairs))
    print("\n=== IDENTITY GATE ===")
    for k, v in sorted(counts.items()):
        print(f"{k}: {v:,}")

    print("\n=== LARGEST HELD LEGACY TARGETS ===")
    held = pairs[
        pairs["identity_gate"].eq(
            "HOLD_LEGACY_OVERAGGREGATED_TARGET"
        )
    ]
    print(
        held["project_work_id"].value_counts()
        .head(17).to_string()
    )

    print("\nNew attribution judgments: 0")
    print("Frozen sample preserved: 800")
    print("QC: PASSED")

if __name__ == "__main__":
    main()
