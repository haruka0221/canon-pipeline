from pathlib import Path
import re
import pandas as pd

BENCH = Path("derived/benchmark")
ADJ = BENCH / "judgments" / "adjudication"

gold = pd.read_csv(
    ADJ / "wikidata_benchmark_adjudicated_final_130.csv",
    dtype=str
).fillna("")

systems = [
    {
        "name": "old_pipeline",
        "path": BENCH / "full_eval_130items.tsv",
        "pred_col": "pred_qid",
    },
    {
        "name": "luna_enhanced_light",
        "path": BENCH / "wikidata_luna_enhanced_light_eval_130.tsv",
        "pred_col": "light_pred_qid",
    },
]

def qids(text):
    """Extract QIDs robustly from semicolon/comma/etc.-separated fields."""
    return set(re.findall(r"Q\d+", str(text)))

def safe_div(a, b):
    return a / b if b else 0.0

summary_rows = []
detail_frames = []

for sys in systems:
    pred = pd.read_csv(
        sys["path"],
        sep="\t",
        dtype=str
    ).fillna("")

    pred = pred[["wk", sys["pred_col"]]].rename(
        columns={
            "wk": "target_id",
            sys["pred_col"]: "pred_qid"
        }
    )

    df = gold.merge(
        pred,
        on="target_id",
        how="left",
        validate="one_to_one"
    )

    if len(df) != 130:
        raise ValueError(f"{sys['name']}: merged rows={len(df)}")

    if df["pred_qid"].isna().any() or (df["pred_qid"] == "").any():
        missing = df.loc[
            df["pred_qid"].isna() | (df["pred_qid"] == ""),
            "target_id"
        ].tolist()
        raise ValueError(f"{sys['name']}: missing predictions: {missing}")

    # Gold entity-existence status:
    # MATCH or AMBIGUOUS = positive
    # NO_MATCH = negative
    df["gold_positive"] = df["gold_decision"].isin(
        ["MATCH", "AMBIGUOUS"]
    )
    df["pred_positive"] = df["pred_qid"] != "NO_MATCH"

    tp = ((df["gold_positive"]) & (df["pred_positive"])).sum()
    fn = ((df["gold_positive"]) & (~df["pred_positive"])).sum()
    fp = ((~df["gold_positive"]) & (df["pred_positive"])).sum()
    tn = ((~df["gold_positive"]) & (~df["pred_positive"])).sum()

    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)

    # Primary-QID correctness:
    # positive -> must equal gold_selected_qid
    # NO_MATCH -> must predict NO_MATCH
    def primary_correct(row):
        if row["gold_decision"] == "NO_MATCH":
            return row["pred_qid"] == "NO_MATCH"
        return row["pred_qid"] == row["gold_selected_qid"]

    # Set-aware correctness:
    # AMBIGUOUS accepts selected QID + listed alternatives.
    def set_aware_correct(row):
        if row["gold_decision"] == "NO_MATCH":
            return row["pred_qid"] == "NO_MATCH"

        accepted = {row["gold_selected_qid"]}
        accepted |= qids(row["gold_alternative_qids"])
        accepted.discard("")

        return row["pred_qid"] in accepted

    df["primary_correct"] = df.apply(primary_correct, axis=1)
    df["set_aware_correct"] = df.apply(set_aware_correct, axis=1)

    positive = df[df["gold_positive"]]
    ambiguous = df[df["gold_decision"] == "AMBIGUOUS"]

    primary_all = df["primary_correct"].mean()
    set_all = df["set_aware_correct"].mean()

    primary_positive = positive["primary_correct"].mean()
    set_positive = positive["set_aware_correct"].mean()

    ambiguous_primary = (
        ambiguous["primary_correct"].mean()
        if len(ambiguous) else float("nan")
    )
    ambiguous_set = (
        ambiguous["set_aware_correct"].mean()
        if len(ambiguous) else float("nan")
    )

    summary_rows.append({
        "system": sys["name"],
        "n": len(df),
        "TP": tp,
        "FN": fn,
        "FP": fp,
        "TN": tn,
        "precision_match_detection": precision,
        "recall_match_detection": recall,
        "f1_match_detection": f1,
        "primary_accuracy_all": primary_all,
        "set_aware_accuracy_all": set_all,
        "primary_accuracy_positive": primary_positive,
        "set_aware_accuracy_positive": set_positive,
        "ambiguous_primary_accuracy": ambiguous_primary,
        "ambiguous_set_aware_accuracy": ambiguous_set,
        "predicted_match": int(df["pred_positive"].sum()),
        "predicted_no_match": int((~df["pred_positive"]).sum()),
    })

    df.insert(0, "system", sys["name"])
    detail_frames.append(df)

summary = pd.DataFrame(summary_rows)
details = pd.concat(detail_frames, ignore_index=True)

summary_path = ADJ / "wikidata_final_gold_evaluation_summary.csv"
detail_path = ADJ / "wikidata_final_gold_evaluation_details.csv"

summary.to_csv(summary_path, index=False)
details.to_csv(detail_path, index=False)

pd.set_option("display.max_columns", None)

print("\n=== FINAL GOLD ===")
print(gold["gold_decision"].value_counts().to_string())

print("\n=== SYSTEM COMPARISON ===")
for _, r in summary.iterrows():
    print(f"\n[{r['system']}]")
    print(
        f"TP={int(r['TP'])} FN={int(r['FN'])} "
        f"FP={int(r['FP'])} TN={int(r['TN'])}"
    )
    print(
        "Match detection: "
        f"P={r['precision_match_detection']:.3f} "
        f"R={r['recall_match_detection']:.3f} "
        f"F1={r['f1_match_detection']:.3f}"
    )
    print(
        "Primary QID accuracy (all): "
        f"{r['primary_accuracy_all']:.3f}"
    )
    print(
        "Set-aware accuracy (all): "
        f"{r['set_aware_accuracy_all']:.3f}"
    )
    print(
        "Primary QID accuracy (positive only): "
        f"{r['primary_accuracy_positive']:.3f}"
    )
    print(
        "Set-aware accuracy (positive only): "
        f"{r['set_aware_accuracy_positive']:.3f}"
    )
    print(
        "AMBIGUOUS primary/set-aware: "
        f"{r['ambiguous_primary_accuracy']:.3f} / "
        f"{r['ambiguous_set_aware_accuracy']:.3f}"
    )

print("\nSaved:", summary_path)
print("Saved:", detail_path)
