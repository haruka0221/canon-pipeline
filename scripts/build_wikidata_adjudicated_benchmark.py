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

human = pd.read_csv(
    ROOT / "adjudication" / "human_adjudication_decisions_12.csv",
    dtype=str
).fillna("")

human = human.set_index("target_id")

rows = []

for _, row in inp.iterrows():
    tid = row["target_id"]

    comp = cmp.loc[cmp["claude_target_id"] == tid]
    if len(comp) != 1:
        raise ValueError(f"{tid}: comparison row count={len(comp)}")
    comp = comp.iloc[0]

    out = {
        "target_id": tid,
        "title": row["title"],
        "author": row["author"],
        "author_qid": row["author_qid"],
    }

    if tid in human.index:
        h = human.loc[tid]

        out.update({
            "gold_decision": h["human_decision"],
            "gold_selected_qid": h["human_selected_qid"],
            "gold_alternative_qids": h["human_alternative_qids"],
            "gold_issue_codes": h["human_issue_codes"],
            "gold_confidence": h["human_confidence"],
            "gold_notes": h["human_notes"],
            "gold_source": "human_adjudication",
        })

    else:
        if comp["claude_decision"] != comp["gemini_decision"]:
            raise ValueError(f"{tid}: unadjudicated decision disagreement")

        if (
            comp["claude_decision"] == "MATCH"
            and comp["claude_selected_qid"] != comp["gemini_selected_qid"]
        ):
            raise ValueError(f"{tid}: unadjudicated QID disagreement")

        out.update({
            "gold_decision": comp["claude_decision"],
            "gold_selected_qid": comp["claude_selected_qid"],
            "gold_alternative_qids": "",
            "gold_issue_codes": "",
            "gold_confidence": "provisional",
            "gold_notes": "",
            "gold_source": "model_consensus",
        })

    rows.append(out)

out = pd.DataFrame(rows)

path = ROOT / "adjudication" / "wikidata_benchmark_adjudicated_draft_130.csv"
out.to_csv(path, index=False)

print("rows:", len(out))
print("unique target_ids:", out["target_id"].nunique())

print("\ngold_source:")
print(out["gold_source"].value_counts().to_string())

print("\ngold_decision:")
print(out["gold_decision"].value_counts().to_string())

print("\nHuman-adjudicated decisions:")
print(
    out[out["gold_source"] == "human_adjudication"]
    [["title", "gold_decision", "gold_selected_qid"]]
    .to_string(index=False)
)

print("\nSaved:", path)
