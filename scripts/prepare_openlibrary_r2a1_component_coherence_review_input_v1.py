from pathlib import Path
import pandas as pd
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "derived/identity"

ROUTING = (
    BASE / "openlibrary_r2a1_split_edition_routing_final_v1"
    / "openlibrary_r2a1_split_edition_routing_final_v1.tsv"
)
REGISTRY = (
    BASE / "openlibrary_r2a1_split_component_registry_v2"
    / "openlibrary_r2a1_split_component_registry_v2.tsv"
)
UPSTREAM_MANIFEST = ROUTING.with_name(
    "openlibrary_r2a1_split_edition_routing_final_v1_manifest.json"
)

OUT = BASE / "openlibrary_r2a1_component_coherence_review_input_v1"

ROLES = {"SUCCESSOR", "PRIMARY_SUCCESSOR_HINT"}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(path):
    return pd.read_csv(
        path, sep="\t", dtype=str, keep_default_na=False
    )

def main():
    if OUT.exists():
        raise SystemExit(
            "STOP: output directory already exists; no overwrite"
        )

    manifest = json.loads(
        UPSTREAM_MANIFEST.read_text(encoding="utf-8")
    )

    assert sha(ROUTING) == manifest["outputs"][
        ROUTING.name
    ]
    assert sha(REGISTRY) == manifest["inputs"][
        "derived/identity/openlibrary_r2a1_split_component_registry_v2/"
        "openlibrary_r2a1_split_component_registry_v2.tsv"
    ]

    routing = load(ROUTING)
    registry = load(REGISTRY)

    assert len(routing) == 508
    assert len(registry) == 88
    assert routing["edition_key"].is_unique
    assert registry["component_id"].is_unique

    selected_registry = registry[
        registry["human_role_hint"].isin(ROLES)
    ].copy()

    assert len(selected_registry) == 72

    assigned = routing[
        routing["final_routing_decision"].eq("ASSIGN_COMPONENT")
        & routing["final_component_role_hint"].isin(ROLES)
    ].copy()

    assert len(assigned) == 371
    assert assigned["final_component_id"].nunique() == 71

    known = set(selected_registry["component_id"])
    assert set(assigned["final_component_id"]).issubset(known)

    # Earlier LLM notes, human decisions, confidence, review
    # hypotheses and registry definitions are NOT sent to the
    # independent assessment.
    fields = [
        "edition_key",
        "edition_title",
        "edition_subtitle",
        "publish_date",
        "publishers",
        "edition_author_keys",
        "number_of_pages",
    ]

    cases = []
    index = []

    reg_lookup = selected_registry.set_index("component_id")

    for i, (cid, g) in enumerate(
        assigned.groupby("final_component_id", sort=True),
        start=1,
    ):
        r = reg_lookup.loc[cid]
        g = g.sort_values("edition_key")

        assert g["project_work_id"].nunique() == 1
        assert g["current_ol_work_id"].nunique() == 1
        assert g["r2_target_author"].nunique() == 1
        assert g.iloc[0]["project_work_id"] == r["project_work_id"]

        case_id = f"CCV1_{i:04d}"

        editions = g[fields].to_dict("records")

        cases.append({
            "case_id": case_id,
            "task": "independent_publication_coherence_review",
            "predecessor_project_work_id": r["project_work_id"],
            "predecessor_ol_work_id": g.iloc[0]["current_ol_work_id"],
            "predecessor_author": g.iloc[0]["r2_target_author"],
            "component_id": cid,
            "editions": editions,
        })

        human = int(g["final_provenance"].isin({
            "human_direct_adjudication",
            "human_registry_remediation_v2",
        }).sum())

        index.append({
            "case_id": case_id,
            "project_work_id": r["project_work_id"],
            "component_id": cid,
            "role_hint": r["human_role_hint"],
            "component_label": r["component_label"],
            "edition_rows": len(g),
            "human_routed_rows": human,
            "llm_only_routed_rows": len(g) - human,
        })

    assert len(cases) == 71
    assert len(index) == 71
    assert sum(len(c["editions"]) for c in cases) == 371

    unused = (
        known - set(assigned["final_component_id"])
    )
    assert unused == {"W000004923_C02"}

    OUT.mkdir(parents=True)

    jsonl = OUT / "component_coherence_review_input_v1.jsonl"
    tsv = OUT / "component_coherence_review_index_v1.tsv"
    manifest_path = OUT / "component_coherence_review_manifest_v1.json"

    jsonl.write_text(
        "".join(
            json.dumps(
                c, ensure_ascii=False, sort_keys=True
            ) + "\n"
            for c in cases
        ),
        encoding="utf-8",
    )

    pd.DataFrame(index).to_csv(
        tsv, sep="\t", index=False, lineterminator="\n"
    )

    output_manifest = {
        "release": "openlibrary-r2a1-component-coherence-review-input-v1",
        "upstream_commit": (
            "c2a18cec290532ae529d87b2c3e28d0b4b61e201"
        ),
        "inputs": {
            str(ROUTING.relative_to(ROOT)): sha(ROUTING),
            str(REGISTRY.relative_to(ROOT)): sha(REGISTRY),
        },
        "outputs": {
            jsonl.name: sha(jsonl),
            tsv.name: sha(tsv),
        },
        "counts": {
            "component_cases": 71,
            "edition_rows": 371,
            "unused_successor_components": sorted(unused),
        },
        "semantics": {
            "status": "review_input_only",
            "scope": "SUCCESSOR_and_PRIMARY_SUCCESSOR_HINT",
            "independence": (
                "LLM/human routing notes, labels, prior review "
                "hypotheses and judgments withheld from model input"
            ),
            "limitation": (
                "The component grouping derives from operational "
                "routing; this is not independent sampling or "
                "proof of component correctness"
            ),
            "no_identity_decisions": True,
            "no_scope_decisions": True,
        },
    }

    manifest_path.write_text(
        json.dumps(
            output_manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    print("=== COMPONENT COHERENCE REVIEW INPUT V1 ===")
    print("cases:", len(cases))
    print("edition rows:", sum(len(c["editions"]) for c in cases))
    print("unused successor components:", sorted(unused))
    print("routing SHA256:", sha(ROUTING))
    print("output:", OUT)

    print("\n=== REVIEW INPUT COVERAGE ===")
    print(
        pd.DataFrame(index)
        .groupby("role_hint")
        .agg(
            components=("case_id", "size"),
            editions=("edition_rows", "sum"),
            human=("human_routed_rows", "sum"),
            llm_only=("llm_only_routed_rows", "sum"),
        )
        .to_string()
    )

    print("\nINPUT QC: PASSED")

if __name__ == "__main__":
    main()
