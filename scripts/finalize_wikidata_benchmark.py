from pathlib import Path
import pandas as pd

ROOT = Path("derived/benchmark/judgments")
ADJ = ROOT / "adjudication"

draft = pd.read_csv(
    ADJ / "wikidata_benchmark_adjudicated_draft_130.csv",
    dtype=str
).fillna("")

audit = pd.read_csv(
    ADJ / "consensus_audit_decisions_15.csv",
    dtype=str
).fillna("")

sample = pd.read_csv(
    ADJ / "consensus_audit_sample_15.csv",
    dtype=str
).fillna("")

audit = audit.merge(
    sample[["claude_target_id", "audit_stratum"]],
    left_on="target_id",
    right_on="claude_target_id",
    validate="one_to_one"
)

audit = audit.set_index("target_id")

rows = []

for _, row in draft.iterrows():
    tid = row["target_id"]
    out = row.to_dict()

    out["human_audit_status"] = ""
    out["human_audit_stratum"] = ""

    if out["gold_source"] == "human_adjudication":
        out["label_source"] = "human_adjudication"
        out["human_audit_status"] = "adjudicated"

    elif tid in audit.index:
        h = audit.loc[tid]

        # Audit must agree with existing consensus
        if h["human_decision"] != out["gold_decision"]:
            raise ValueError(f"{tid}: audit decision disagrees with draft")

        if (
            h["human_decision"] == "MATCH"
            and h["human_selected_qid"] != out["gold_selected_qid"]
        ):
            raise ValueError(f"{tid}: audit QID disagrees with draft")

        out["label_source"] = "model_consensus_human_audited"
        out["human_audit_status"] = "confirmed"
        out["human_audit_stratum"] = h["audit_stratum"]

        # Preserve human audit notes as evidence of confirmation
        out["gold_confidence"] = h["human_confidence"]
        out["gold_notes"] = h["human_notes"]

    else:
        out["label_source"] = "model_consensus_unreviewed"

    rows.append(out)

final = pd.DataFrame(rows)

out_path = ADJ / "wikidata_benchmark_adjudicated_final_130.csv"
final.to_csv(out_path, index=False)

print("rows:", len(final))
print("unique target_ids:", final["target_id"].nunique())

print("\nlabel_source:")
print(final["label_source"].value_counts().to_string())

print("\ngold_decision:")
print(final["gold_decision"].value_counts().to_string())

print("\nhuman audit strata:")
print(
    final.loc[
        final["label_source"] == "model_consensus_human_audited",
        "human_audit_stratum"
    ].value_counts().to_string()
)

print("\nSaved:", out_path)
