#!/usr/bin/env python3
"""Read-only checks for the three open items of the v3 protocol (§10). Nothing is written.

1. Quote-bearing query strings in the full target frame (34,790 alias rows).
2. VALID rate of links returned by A1 only, from the v2 judgment sample.
3. Author-error notes in the v2 LLM output and human audit.

Decision rules are printed with each result.
"""
from pathlib import Path
import re
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CAL = ROOT / "derived" / "bl_calibration" / "calibration_v2"
D = Path.home() / "bl_raw" / "calibration_v2_derived"


def read(p):
    return pd.read_csv(p, sep="\t", dtype=str, keep_default_na=False)


print("=" * 70)
print("1. Quote-bearing queries in the full frame")
F = read(CAL / "target_frame_v1.tsv")
F = F[F["measurement_status"].isin(["TO_RETRIEVE", "TO_RETRIEVE_UNRESOLVED_LANE"])]
qt = F["source_title"].str.contains('"', regex=False)
qa = F["query_author_name"].str.contains('"', regex=False)
print(f"alias rows considered: {len(F)}")
print(f"titles with a double quote: {int(qt.sum())}  (T2 and K1 would be skipped)")
print(f"authors with a double quote: {int(qa.sum())}  (A1 and K1 would be skipped)")
print(f"targets affected (either): {F.loc[qt | qa, 'project_work_id'].replace('', pd.NA).dropna().nunique()} W, "
      f"{int((F.loc[qt | qa, 'target_lane'] == 'unresolved_source').sum())} unresolved aliases")
print("decision: <= 100 affected -> skip and record only; > 100 -> add an alternative query with quotes removed (as a separate route)")

print("=" * 70)
print("2. VALID rate of A1-only links (v2 judgment sample, LLM label; human audit where available)")
J = read(D / "judgment_sample_v2.tsv")
L = read(D / "judgment_llm_output_v2.tsv")
H = read(D / "human_audit_input_v2.tsv")
S = read(CAL / "sample_targets_v1.tsv")
J = J.merge(L[["judgment_id", "work_relation"]], on="judgment_id")
J["s"] = J["sample_id"].map(dict(zip(S["sample_id"], S["stratum"])))
J["a1_only"] = J["routes"] == "A1"
J["has_title_route"] = J["routes"].str.contains("T2|K1")
for name, sub in [("all", J), ("S1+S2", J[J["s"] != "S3"])]:
    print(f"-- {name}")
    t = (sub.groupby(["stratum", "a1_only"])["work_relation"]
         .agg(n="size", valid=lambda s: int((s == "VALID").sum())))
    t["valid_rate"] = (t["valid"] / t["n"]).round(3)
    print(t.to_string())
Hm = H[["judgment_id", "human_work_relation"]].merge(J[["judgment_id", "a1_only", "stratum"]], on="judgment_id")
print("-- human audit rows by a1_only")
print(Hm.groupby("a1_only")["human_work_relation"].value_counts().to_string())
print("decision: A1-only VALID rate in J3 <= 2% (and no human VALID) -> drop A1-only records from lane C, count them as 'author other works';")
print("          otherwise keep A1-only as its own stratum in lane C")

print("=" * 70)
print("3. Author-error notes (candidates for the override table)")
pat = re.compile(r"wrong author|misattribut|attributed to|author is|OL author|not by|pseudonym|actually by", re.I)
Lr = L[L["reason"].str.contains(pat)]
Lr = Lr.merge(J[["judgment_id", "sample_id", "target_id"]], on="judgment_id")
print(f"LLM reasons mentioning an author problem: {len(Lr)} rows, {Lr['target_id'].nunique()} targets")
print(Lr[["judgment_id", "target_id", "work_relation", "reason"]].to_string(index=False))
Hn = H[H["human_note"].str.strip() != ""][["judgment_id", "human_work_relation", "human_note"]]
Hn = Hn.merge(J[["judgment_id", "target_id"]], on="judgment_id")
print(f"human notes (all, {len(Hn)} rows) — read for author problems:")
print(Hn.to_string(index=False))
print("decision: the override table starts from the targets listed above; each entry needs the correct surname and a source. "
      "Expect ~1% of targets (NO_OL_AUTHOR 352 + wrong authors); the table need not be complete (lane B catches the rest).")
