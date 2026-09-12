from pathlib import Path
import pandas as pd

ROOT = Path("derived/benchmark/judgments")
SEED = 20260911

cmp = pd.read_csv(
    ROOT / "adjudication" / "claude_gemini_comparison_130.csv",
    dtype=str
).fillna("")

human = pd.read_csv(
    ROOT / "adjudication" / "human_adjudication_decisions_12.csv",
    dtype=str
).fillna("")

human_ids = set(human["target_id"])

# Only cases not already human-adjudicated
pool = cmp[
    ~cmp["claude_target_id"].isin(human_ids)
].copy()

# All remaining cases should be core agreements
assert len(pool) == 118
assert (pool["core_agree"] == "True").all()

confidence_only = pool[
    pool["claude_confidence"].isin(["medium", "low"])
].copy()

clean_high = pool[
    (pool["claude_confidence"] == "high") &
    (pool["gemini_confidence"] == "high")
].copy()

audit_low = confidence_only.sample(
    n=min(8, len(confidence_only)),
    random_state=SEED
)

audit_high = clean_high.sample(
    n=min(7, len(clean_high)),
    random_state=SEED
)

audit = pd.concat([audit_low, audit_high], ignore_index=True)

audit["audit_stratum"] = (
    ["claude_medium_or_low"] * len(audit_low)
    + ["both_high"] * len(audit_high)
)

out = ROOT / "adjudication" / "consensus_audit_sample_15.csv"
audit.to_csv(out, index=False)

print("Consensus pool:", len(pool))
print("Claude medium/low pool:", len(confidence_only))
print("Both-high pool:", len(clean_high))
print("Audit sample:", len(audit))

print("\nSample:")
print(
    audit[
        [
            "claude_target_id",
            "claude_title",
            "claude_decision",
            "claude_selected_qid",
            "claude_confidence",
            "audit_stratum",
        ]
    ].to_string(index=False)
)

print("\nDecision counts:")
print(audit["claude_decision"].value_counts().to_string())

print("\nSaved:", out)
