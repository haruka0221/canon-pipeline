from pathlib import Path
from collections import Counter
import hashlib
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "derived/identity"

ROUTING_DIR = BASE / "openlibrary_r2a1_split_edition_routing_final_v1"
ROUTING = ROUTING_DIR / "openlibrary_r2a1_split_edition_routing_final_v1.tsv"

PLAN_DIR = BASE / "openlibrary_r2a1_identity_v6_planning_input_v1"
DISPOSITIONS = PLAN_DIR / "edition_dispositions_v1.tsv"
UNITS = PLAN_DIR / "publication_unit_candidates_v1.tsv"

OUT = BASE / "openlibrary_r2a1_identity_v6_migration_coverage_v1"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(path):
    return pd.read_csv(
        path, sep="\t", dtype=str, keep_default_na=False
    )

def main():
    if OUT.exists():
        raise SystemExit("STOP: output already exists")

    rm = json.loads(
        (ROUTING_DIR /
         "openlibrary_r2a1_split_edition_routing_final_v1_manifest.json"
        ).read_text()
    )

    pm = json.loads(
        (PLAN_DIR / "planning_input_manifest_v1.json").read_text()
    )

    assert sha(ROUTING) == rm["outputs"][ROUTING.name]
    assert sha(DISPOSITIONS) == pm["outputs"][DISPOSITIONS.name]
    assert sha(UNITS) == pm["outputs"][UNITS.name]

    routing = load(ROUTING)
    dispositions = load(DISPOSITIONS)
    units = load(UNITS)

    assert len(routing) == 508
    assert routing["edition_key"].is_unique

    assert len(dispositions) == 371
    assert dispositions["edition_key"].is_unique

    assert len(units) == 76
    assert units["candidate_unit_id"].is_unique

    assert units["edition_count"].astype(int).sum() == 280

    pcols = [
        "edition_key",
        "predecessor_project_work_id",
        "component_id",
        "case_id",
        "disposition",
        "candidate_unit_id",
    ]

    merged = routing.merge(
        dispositions[pcols],
        on="edition_key",
        how="left",
        validate="one_to_one",
        indicator=True,
    ).fillna("")

    assert len(merged) == 508
    assert merged["edition_key"].is_unique

    buckets = []

    for r in merged.to_dict("records"):
        matched = r["_merge"] == "both"

        if matched:
            assert r["project_work_id"] == (
                r["predecessor_project_work_id"]
            )
            assert r["final_component_id"] == r["component_id"]
            assert r["final_routing_decision"] == "ASSIGN_COMPONENT"
            assert r["final_component_role_hint"] in {
                "SUCCESSOR", "PRIMARY_SUCCESSOR_HINT"
            }

            if r["disposition"] == "PROVISIONAL_PUBLICATION_GROUP":
                assert r["candidate_unit_id"]
                bucket = "PROVISIONAL_PUBLICATION_GROUP"

            elif r["disposition"] == "COHERENCE_UNRESOLVED":
                assert not r["candidate_unit_id"]
                bucket = "COHERENCE_UNRESOLVED"

            else:
                raise AssertionError(
                    f"Unexpected disposition: {r['disposition']}"
                )

        elif r["final_routing_decision"] == "HOLD_UNRESOLVED":
            bucket = "ROUTING_UNRESOLVED"

        elif r["final_routing_decision"] == "ASSIGN_COMPONENT":
            role = r["final_component_role_hint"]

            if role == "DETACH":
                bucket = "DETACH_PENDING_IDENTITY"
            elif role == "EXCLUDE_APPARATUS":
                bucket = "APPARATUS_PENDING_SCOPE"
            else:
                raise AssertionError(
                    f"Unaccounted assigned Edition: {r['edition_key']}"
                )
        else:
            raise AssertionError(
                f"Unknown routing state: {r['edition_key']}"
            )

        buckets.append(bucket)

    merged["migration_bucket"] = buckets
    merged["identity_decision"] = "NOT_ADJUDICATED"

    counts = Counter(merged["migration_bucket"])

    expected = {
        "PROVISIONAL_PUBLICATION_GROUP": 280,
        "COHERENCE_UNRESOLVED": 91,
        "ROUTING_UNRESOLVED": 104,
        "DETACH_PENDING_IDENTITY": 28,
        "APPARATUS_PENDING_SCOPE": 5,
    }

    assert counts == expected, (counts, expected)

    grouped = merged[
        merged["migration_bucket"].eq(
            "PROVISIONAL_PUBLICATION_GROUP"
        )
    ]

    assert grouped["candidate_unit_id"].nunique() == 76
    assert set(grouped["candidate_unit_id"]) == set(
        units["candidate_unit_id"]
    )

    actual_group_sizes = grouped.groupby(
        "candidate_unit_id"
    ).size().to_dict()

    for u in units.to_dict("records"):
        assert actual_group_sizes[u["candidate_unit_id"]] == int(
            u["edition_count"]
        )

    columns = [
        "edition_key",
        "project_work_id",
        "current_ol_work_id",
        "edition_title",
        "edition_subtitle",
        "publish_date",
        "publishers",
        "final_routing_decision",
        "final_component_id",
        "final_component_role_hint",
        "final_provenance",
        "human_audit_case_id",
        "human_authority_effect",
        "case_id",
        "candidate_unit_id",
        "migration_bucket",
        "identity_decision",
    ]

    result = merged[columns].sort_values(
        ["project_work_id", "edition_key"]
    )

    OUT.mkdir(parents=True)

    output = OUT / "edition_migration_coverage_v1.tsv"
    result.to_csv(
        output, sep="\t", index=False, lineterminator="\n"
    )

    manifest = {
        "release": "openlibrary-r2a1-identity-v6-migration-coverage-v1",
        "status": "planning_only",
        "inputs": {
            str(ROUTING.relative_to(ROOT)): sha(ROUTING),
            str(DISPOSITIONS.relative_to(ROOT)): sha(DISPOSITIONS),
            str(UNITS.relative_to(ROOT)): sha(UNITS),
        },
        "outputs": {output.name: sha(output)},
        "counts": {
            "editions": len(result),
            "candidate_publication_units": len(units),
            "migration_buckets": dict(sorted(counts.items())),
        },
        "identity_decisions_created": 0,
        "project_works_created": 0,
        "scope_decisions_created": 0,
    }

    (OUT / "migration_coverage_manifest_v1.json").write_text(
        json.dumps(
            manifest, ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n",
        encoding="utf-8",
    )

    print("=== IDENTITY V6 MIGRATION COVERAGE ===")
    print("editions:", len(result))
    print("candidate publication units:", len(units))
    print("\n=== BUCKET COUNTS ===")

    for key, value in sorted(counts.items()):
        print(f"{key}: {value}")

    print("\nidentity decisions created: 0")
    print("project works created: 0")
    print("scope decisions created: 0")
    print("output:", OUT)
    print("QC: PASSED")

if __name__ == "__main__":
    main()
