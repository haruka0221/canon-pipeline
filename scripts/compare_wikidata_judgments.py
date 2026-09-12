from pathlib import Path
import pandas as pd

ROOT = Path("derived/benchmark/judgments")
NORM = ROOT / "normalized"
OUT = ROOT / "adjudication"
OUT.mkdir(parents=True, exist_ok=True)

claude = pd.read_csv(
    NORM / "claude_sonnet5_high_2026-09-11.csv",
    dtype=str
).fillna("")

gemini = pd.read_csv(
    NORM / "gemini_3.1_pro_2026-09-11.csv",
    dtype=str
).fillna("")

c = claude.add_prefix("claude_")
g = gemini.add_prefix("gemini_")

df = c.merge(
    g,
    left_on="claude_target_id",
    right_on="gemini_target_id",
    validate="one_to_one"
)

# Core agreement
df["decision_agree"] = (
    df["claude_decision"] == df["gemini_decision"]
)

df["selected_qid_agree"] = (
    df["claude_selected_qid"] == df["gemini_selected_qid"]
)

# For MATCH, QID must agree.
# For NO_MATCH, both selected_qid should be blank anyway.
df["core_agree"] = (
    df["decision_agree"] &
    (
        (df["claude_decision"] != "MATCH") |
        df["selected_qid_agree"]
    )
)

# Cases that should be human-reviewed even if decisions agree
GRANULARITY_ISSUES = {
    "duplicate_work_items",
    "edition_or_translation",
    "edition_without_work_item",
    "adaptation",
    "author_ambiguity",
}

def issue_set(x):
    return {
        s.strip()
        for s in str(x).split(";")
        if s.strip()
    }

def review_reasons(row):
    reasons = []

    if not row["decision_agree"]:
        reasons.append("decision_disagreement")

    if (
        row["claude_decision"] == "MATCH"
        and row["gemini_decision"] == "MATCH"
        and not row["selected_qid_agree"]
    ):
        reasons.append("selected_qid_disagreement")

    if (
        row["claude_decision"] == "AMBIGUOUS"
        or row["gemini_decision"] == "AMBIGUOUS"
    ):
        reasons.append("ambiguous")

    if row["claude_confidence"] != "high":
        reasons.append("claude_not_high_confidence")

    if row["gemini_confidence"] != "high":
        reasons.append("gemini_not_high_confidence")

    issues = (
        issue_set(row["claude_issue_codes"])
        | issue_set(row["gemini_issue_codes"])
    )

    if issues & GRANULARITY_ISSUES:
        reasons.append("granularity_or_identity_issue")

    return ";".join(reasons)

df["review_reasons"] = df.apply(review_reasons, axis=1)
df["needs_human_review"] = df["review_reasons"] != ""

# A provisional consensus is only a clean, high-confidence agreement
df["provisional_consensus"] = (
    df["core_agree"]
    & ~df["needs_human_review"]
)

# Convenient compact columns first
front = [
    "claude_target_id",
    "claude_title",
    "claude_decision",
    "claude_selected_qid",
    "claude_confidence",
    "claude_issue_codes",
    "gemini_decision",
    "gemini_selected_qid",
    "gemini_confidence",
    "gemini_issue_codes",
    "decision_agree",
    "selected_qid_agree",
    "core_agree",
    "needs_human_review",
    "review_reasons",
    "provisional_consensus",
]

rest = [x for x in df.columns if x not in front]
df = df[front + rest]

all_path = OUT / "claude_gemini_comparison_130.csv"
review_path = OUT / "human_review_queue.csv"
consensus_path = OUT / "provisional_consensus.csv"

df.to_csv(all_path, index=False)
df[df["needs_human_review"]].to_csv(review_path, index=False)
df[df["provisional_consensus"]].to_csv(consensus_path, index=False)

print("Total:", len(df))
print("Decision agreement:", int(df["decision_agree"].sum()))
print("Core agreement:", int(df["core_agree"].sum()))
print("Human review:", int(df["needs_human_review"].sum()))
print("Provisional consensus:", int(df["provisional_consensus"].sum()))

print("\nDecision cross-tab:")
print(pd.crosstab(
    df["claude_decision"],
    df["gemini_decision"],
    margins=True
).to_string())

print("\nReview reasons:")
reasons = (
    df.loc[df["needs_human_review"], "review_reasons"]
      .str.split(";")
      .explode()
      .value_counts()
)
print(reasons.to_string())

print("\nSaved:")
print(all_path)
print(review_path)
print(consensus_path)
