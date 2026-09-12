from pathlib import Path
import pandas as pd

ROOT = Path("derived/benchmark/judgments")

inp = pd.read_csv(
    ROOT / "input" / "wikidata_judge_input_130.csv",
    dtype=str
).fillna("")

cmp = pd.read_csv(
    ROOT / "adjudication" / "claude_gemini_comparison_130.csv",
    dtype=str
).fillna("")

challenge_ids = {
    "OL31971259W",  # Heart of Darkness
    "OL20172W",     # Kim
    "OL41540816W",  # Robert Elsmere
    "OL65437W",     # At Fault
    "OL715553W",    # New Grub Street
    "OL1794619W",   # With Roberts to Pretoria
    "OL1441628W",   # Life with father
}

mandatory = set(
    cmp.loc[
        cmp["review_reasons"].str.contains(
            "decision_disagreement|ambiguous|granularity_or_identity_issue",
            regex=True,
            na=False
        ),
        "claude_target_id"
    ]
)

review_ids = mandatory | challenge_ids

packet = inp[inp["target_id"].isin(review_ids)].copy()

keep_cmp = cmp[
    [
        "claude_target_id",
        "claude_decision",
        "claude_selected_qid",
        "claude_alternative_qids",
        "claude_confidence",
        "claude_issue_codes",
        "claude_reason",
        "gemini_decision",
        "gemini_selected_qid",
        "gemini_alternative_qids",
        "gemini_confidence",
        "gemini_issue_codes",
        "gemini_reason",
        "review_reasons",
    ]
].copy()

packet = packet.merge(
    keep_cmp,
    left_on="target_id",
    right_on="claude_target_id",
    how="left",
    validate="one_to_one"
)

packet["mandatory_reason"] = packet["target_id"].map(
    lambda x:
        "model_review" if x in mandatory else "challenge_regression"
)

out = ROOT / "adjudication" / "human_adjudication_packet_12.csv"
packet.to_csv(out, index=False)

print("Mandatory disagreement/granularity:", len(mandatory))
print("Challenge/regression set:", len(challenge_ids))
print("Unique adjudication targets:", len(packet))
print("\nTargets:")
print(packet[["target_id", "title", "mandatory_reason"]].to_string(index=False))
print("\nSaved:", out)
