from pathlib import Path
import hashlib
import json

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OA = ROOT / "derived/openalex_production"
ID = ROOT / "derived/identity"

GATE = (
    OA / "retrieval_r2a1_post_identity_candidates_v1"
    / "openalex_r2a1_post_identity_candidates_v1.parquet"
)
GATE_MANIFEST = GATE.parent / "openalex_r2a1_post_identity_manifest_v1.json"

AUDIT = (
    OA / "retrieval_r2a1_baseline_primary_human_audit_analysis_v1"
    / "openalex_r2a1_baseline_primary_human_audit_join_v1.tsv"
)
A2 = (
    OA / "retrieval_a2_production_final_disposition_v1"
    / "openalex_a2_production_final_disposition_v1.tsv"
)
ALIAS = (
    OA / "retrieval_alias_production_final_disposition_v1"
    / "openalex_alias_production_final_disposition_v1.tsv"
)

WORKS = ID / "project_works_v7.tsv"
SUSPENSIONS = ID / "project_work_identity_suspensions_v1.tsv"

OUT = OA / "integrated_work_visibility_v1"

INCLUDE = {
    "INCLUDE_BASELINE_UNADJUDICATED",
    "INCLUDE_BASELINE_HUMAN_VALID",
    "INCLUDE_FINAL_VALID",
    "INCLUDE_POLICY_ACCEPT_UNADJUDICATED",
}

def read(path):
    return pd.read_csv(
        path, sep="\t", dtype=str, keep_default_na=False
    )

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    if OUT.exists():
        raise SystemExit("STOP: output directory exists")

    gm = json.loads(GATE_MANIFEST.read_text())
    assert sha(GATE) == gm["outputs"][GATE.name]

    gate = pd.read_parquet(GATE)
    audit = read(AUDIT)
    a2 = read(A2)
    alias = read(ALIAS)
    works = read(WORKS)
    suspensions = read(SUSPENSIONS)

    assert len(gate) == 290480
    assert len(audit) == 150
    assert len(a2) == 963
    assert len(alias) == 409
    assert len(works) == 32089
    assert len(suspensions) == 17

    affected = set(suspensions["project_work_id"])
    statuses = dict(zip(
        works["project_work_id"], works["status"]
    ))

    assert len(affected) == 17
    assert len(statuses) == len(works)

    assert gate["identity_gate"].value_counts().to_dict() == {
        "ELIGIBLE_FOR_R2A1_ADJUDICATION": 224934,
        "HOLD_LEGACY_OVERAGGREGATED_TARGET": 65546,
    }

    assert audit["baseline_candidate_id"].is_unique
    assert gate["baseline_candidate_id"].is_unique

    # 1. Overlay existing human decisions onto R2+A1.
    b = gate.merge(
        audit[[
            "baseline_candidate_id",
            "human_target_attribution_judgment",
        ]],
        on="baseline_candidate_id",
        how="left",
        validate="one_to_one",
    )

    b["human_target_attribution_judgment"] = (
        b["human_target_attribution_judgment"].fillna("")
    )

    assert b[
        "human_target_attribution_judgment"
    ].ne("").sum() == 150

    eligible = b["identity_gate"].eq(
        "ELIGIBLE_FOR_R2A1_ADJUDICATION"
    )
    labels = b["human_target_attribution_judgment"]

    b["disposition"] = "HOLD_LEGACY_OVERAGGREGATED_TARGET"

    b.loc[eligible, "disposition"] = (
        "INCLUDE_BASELINE_UNADJUDICATED"
    )

    b.loc[
        eligible & labels.eq("VALID_TARGET_REFERENCE"),
        "disposition"
    ] = "INCLUDE_BASELINE_HUMAN_VALID"

    b.loc[
        eligible & labels.eq("INVALID_TARGET_REFERENCE"),
        "disposition"
    ] = "EXCLUDE_BASELINE_HUMAN_INVALID"

    b.loc[
        eligible & labels.eq("UNCERTAIN"),
        "disposition"
    ] = "HOLD_BASELINE_HUMAN_UNCERTAIN"

    expected_baseline = {
        "INCLUDE_BASELINE_UNADJUDICATED": 224830,
        "INCLUDE_BASELINE_HUMAN_VALID": 98,
        "EXCLUDE_BASELINE_HUMAN_INVALID": 5,
        "HOLD_BASELINE_HUMAN_UNCERTAIN": 1,
        "HOLD_LEGACY_OVERAGGREGATED_TARGET": 65546,
    }

    assert b["disposition"].value_counts().to_dict() == (
        expected_baseline
    )

    baseline_pairs = pd.DataFrame({
        "project_work_id": b["project_work_id"],
        "openalex_work_id": b["openalex_work_id"],
        "route": "R2_A1_BASELINE",
        "source_candidate_id": b["baseline_candidate_id"],
        "disposition": b["disposition"],
        "judgment": labels,
        "judgment_provenance": [
            "FROZEN_DIRECT_HUMAN_AUDIT" if v else
            "NO_INDIVIDUAL_ADJUDICATION"
            for v in labels
        ],
        "identity_gate": b["identity_gate"],
    })

    # 2. Reuse frozen A2 and Alias dispositions.
    def marginal(df, route, id_col):
        assert df[id_col].is_unique

        z = pd.DataFrame({
            "project_work_id": df["project_work_id"],
            "openalex_work_id": df["openalex_work_id"],
            "route": route,
            "source_candidate_id": df[id_col],
            "disposition": df["final_operational_disposition"],
            "judgment": df["final_judgment"],
            "judgment_provenance": df["source_final_label_source"],
        })

        z["identity_gate"] = [
            (
                "HOLD_LEGACY_OVERAGGREGATED_TARGET"
                if w in affected else
                "ELIGIBLE_FOR_R2A1_ADJUDICATION"
                if statuses.get(w) == "active" else
                "HOLD_NONACTIVE_PROJECT_W"
            )
            for w in z["project_work_id"]
        ]

        # No formerly overaggregated predecessor may
        # become valid again through a marginal route.
        if not z["identity_gate"].eq(
            "ELIGIBLE_FOR_R2A1_ADJUDICATION"
        ).all():
            raise AssertionError(
                f"{route}: noneligible identity present"
            )

        return z

    a2_pairs = marginal(
        a2, "A2_AUTHOR_REVERSAL", "production_candidate_id"
    )
    alias_pairs = marginal(
        alias, "ALIAS_EXPANSION", "review_candidate_id"
    )

    assert a2_pairs["disposition"].value_counts().to_dict() == {
        "INCLUDE_FINAL_VALID": 507,
        "INCLUDE_POLICY_ACCEPT_UNADJUDICATED": 415,
        "EXCLUDE_FINAL_INVALID": 39,
        "HOLD_UNCERTAIN": 2,
    }

    assert alias_pairs["disposition"].value_counts().to_dict() == {
        "INCLUDE_FINAL_VALID": 364,
        "EXCLUDE_FINAL_INVALID": 24,
        "HOLD_UNCERTAIN": 21,
    }

    # 3. Pair-level union. Never double-count the same
    # Project Work x OpenAlex Work combination.
    combined = pd.concat(
        [baseline_pairs, a2_pairs, alias_pairs],
        ignore_index=True,
    )

    pair_cols = ["project_work_id", "openalex_work_id"]

    duplicate = combined.duplicated(pair_cols, keep=False)

    if duplicate.any():
        print(
            combined.loc[
                duplicate, pair_cols + ["route", "disposition"]
            ].head(20).to_string(index=False)
        )
        raise AssertionError(
            "Cross-route overlap detected; explicit "
            "deduplication policy required"
        )

    assert len(combined) == 291852

    combined["operational_include"] = (
        combined["disposition"].isin(INCLUDE)
    )

    included = combined[
        combined["operational_include"]
    ].copy()

    # 224,928 baseline + 922 A2 + 364 Alias.
    assert len(included) == 226214

    assert not set(included["project_work_id"]) & affected

    # 4. Aggregate by Project W, including zero-hit
    # active works. Zero refers only to this retrieval
    # protocol, not to absence of scholarly discussion.
    active = works.loc[
        works["status"].eq("active"),
        ["project_work_id"]
    ].copy()

    assert len(active) == 32066

    counts = (
        included.groupby(["project_work_id", "route"])
        .size()
        .unstack(fill_value=0)
        .reindex(
            columns=[
                "R2_A1_BASELINE",
                "A2_AUTHOR_REVERSAL",
                "ALIAS_EXPANSION",
            ],
            fill_value=0,
        )
        .reset_index()
    )

    counts = counts.rename(columns={
        "R2_A1_BASELINE": "r2a1_operational_pairs",
        "A2_AUTHOR_REVERSAL": "a2_operational_pairs",
        "ALIAS_EXPANSION": "alias_operational_pairs",
    })

    result = active.merge(
        counts, on="project_work_id",
        how="left", validate="one_to_one"
    )

    metric_cols = [
        "r2a1_operational_pairs",
        "a2_operational_pairs",
        "alias_operational_pairs",
    ]

    result[metric_cols] = (
        result[metric_cols].fillna(0).astype("Int64")
    )

    result["total_operational_pairs"] = (
        result[metric_cols].sum(axis=1).astype("Int64")
    )

    result["measurement_status"] = (
        "OPERATIONAL_CANDIDATE_COUNT"
    )

    # Alcott's W ID was restored, but the old query
    # targeted an overaggregated source Work.
    # It MUST NOT be reported as zero citations.
    alcott = result["project_work_id"].eq("W000014515")

    assert alcott.sum() == 1

    result.loc[alcott, "measurement_status"] = (
        "HOLD_PRIMARY_SUCCESSOR_NOT_RERETRIEVED"
    )
    result.loc[alcott, metric_cols + [
        "total_operational_pairs"
    ]] = pd.NA

    assert (
        result["total_operational_pairs"].dropna().sum()
        == 226214
    )

    # 5. Reproducible outputs.
    OUT.mkdir(parents=True)

    pair_path = OUT / "integrated_candidate_dispositions_v1.parquet"
    work_path = OUT / "openalex_visibility_by_project_work_v1.tsv"
    work_pq = OUT / "openalex_visibility_by_project_work_v1.parquet"
    summary_path = OUT / "integrated_visibility_summary_v1.json"
    manifest_path = OUT / "integrated_visibility_manifest_v1.json"

    combined.to_parquet(pair_path, index=False)

    result.to_csv(
        work_path, sep="\t", index=False,
        lineterminator="\n"
    )
    result.to_parquet(work_pq, index=False)

    route_counts = {
        k: int(v)
        for k, v in included["route"].value_counts().items()
    }

    summary = {
        "release": "openalex-integrated-work-visibility-v1",
        "status": "PROVISIONAL_OPERATIONAL",
        "total_candidate_pairs": len(combined),
        "operationally_included_pairs": len(included),
        "included_by_route": route_counts,
        "identity_held_legacy_pairs": 65546,
        "active_project_works": len(active),
        "source_light_unremeasured_works": 1,
        "project_works_with_operational_candidates": int(
            result["total_operational_pairs"].fillna(0).gt(0).sum()
        ),
        "semantics": {
            "baseline":
                "Identity-eligible R2+A1 candidates "
                "operationally included unless a frozen "
                "human judgment is INVALID or UNCERTAIN.",
            "baseline_unadjudicated":
                "Not individual VALID adjudications.",
            "marginal_routes":
                "Reuse frozen A2 and Alias final dispositions.",
            "unit":
                "Unique Project W x OpenAlex Work pair.",
            "identity":
                "All 17 original overaggregated "
                "retrieval targets are held.",
            "scope":
                "No corpus-scope adjudication.",
            "limits":
                "R2+A1 and marginal operational inclusion "
                "are not complete human verification. "
                "R4 title-only retrieval is not included. "
                "Counts are not corrected for estimated "
                "false-positive rates.",
        },
    }

    summary_path.write_text(
        json.dumps(
            summary, ensure_ascii=False,
            indent=2, sort_keys=True
        ) + "\n", encoding="utf-8"
    )

    manifest = {
        "release": summary["release"],
        "inputs": {
            str(p.relative_to(ROOT)): sha(p)
            for p in [
                GATE, GATE_MANIFEST, AUDIT, A2, ALIAS,
                WORKS, SUSPENSIONS,
            ]
        },
        "outputs": {
            p.name: sha(p)
            for p in [
                pair_path, work_path,
                work_pq, summary_path,
            ]
        },
    }

    manifest_path.write_text(
        json.dumps(
            manifest, ensure_ascii=False,
            indent=2, sort_keys=True
        ) + "\n", encoding="utf-8"
    )

    print("=== OPENALEX INTEGRATED VISIBILITY V1 ===")
    print("Candidate pairs:", len(combined))
    print("Operationally included:", len(included))
    print("\nIncluded by route:")
    for k, v in sorted(route_counts.items()):
        print(f"  {k}: {v:,}")

    print("\nHeld legacy pairs:", 65546)
    print("Active Project Ws:", len(active))
    print(
        "Ws with operational candidates:",
        summary["project_works_with_operational_candidates"]
    )
    print("Unremeasured restored W: W000014515")
    print("Output:", OUT)
    print("QC: PASSED")


if __name__ == "__main__":
    main()
