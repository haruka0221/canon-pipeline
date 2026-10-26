#!/usr/bin/env python3
"""BL calibration v2 analysis: agreement, precision, false negatives, coverage inputs.

Private inputs (~/bl_raw/calibration_v2_derived):
  judgment_sample_v2.tsv      500 rows with stratum (J1 r3_author / J2 r3 only / J3 r3 false) and rule flags
  judgment_llm_output_v2.tsv  LLM first pass (work_relation, publication_relation)
  human_audit_input_v2.tsv    82 blind human judgments (human_work_relation, ...)
  matching_results_v2.tsv     all 16,681 links with flags
  records_parsed_v2.tsv
Public inputs:
  sample_targets_v1.tsv (stratum S1/S2/S3), first_edition_targets_v1.tsv

Estimation (addendum 1 item 4): for a judgment stratum J,
  P(VALID | J) = sum_l P(LLM = l | J) * P(human VALID | LLM = l)
with P(human VALID | LLM = l) taken from the blind audit pooled over strata.
95% CI by parametric bootstrap (multinomial on the LLM labels within J,
binomial on the audit within each LLM label), 10,000 draws.
S3 (v1 re-test) rows are excluded from the estimates and reported separately.

Private outputs: agreement_v2.tsv, first_edition_candidates_v2.tsv
Public output:   derived/bl_calibration/calibration_v2/analysis_summary_v1.json
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CAL = ROOT / "derived" / "bl_calibration" / "calibration_v2"
D = Path.home() / "bl_raw" / "calibration_v2_derived"
OUT = CAL / "analysis_summary_v1.json"
LABELS = ["VALID", "INVALID", "UNCERTAIN"]
B = 10000
rng = np.random.default_rng(20261021)


def read(p):
    return pd.read_csv(p, sep="\t", dtype=str, keep_default_na=False)


def estimate(llm_labels: pd.Series, audit: pd.DataFrame):
    """Return point estimate and CI of P(human VALID) for rows with the given LLM labels."""
    n = len(llm_labels)
    if n == 0:
        return None
    counts = {l: int((llm_labels == l).sum()) for l in LABELS}
    aud = {l: audit[audit["llm"] == l] for l in LABELS}
    rate = {l: (float((aud[l]["human"] == "VALID").mean()) if len(aud[l]) else None) for l in LABELS}
    # labels with no audit rows contribute their own LLM label as the rate (VALID->1, else 0)
    eff = {l: (rate[l] if rate[l] is not None else (1.0 if l == "VALID" else 0.0)) for l in LABELS}
    point = sum(counts[l] / n * eff[l] for l in LABELS)
    draws = np.empty(B)
    p_lab = np.array([counts[l] / n for l in LABELS])
    for b in range(B):
        c = rng.multinomial(n, p_lab) / n
        r = []
        for l in LABELS:
            k = len(aud[l])
            r.append(rng.binomial(k, eff[l]) / k if k else eff[l])
        draws[b] = float(np.dot(c, r))
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return {"n": n, "llm_counts": counts, "audit_valid_rate_by_llm_label": rate,
            "estimate_human_valid": round(point, 4), "ci95": [round(lo, 4), round(hi, 4)]}


def main():
    J = read(D / "judgment_sample_v2.tsv")
    L = read(D / "judgment_llm_output_v2.tsv")
    H = read(D / "human_audit_input_v2.tsv")
    M = read(D / "matching_results_v2.tsv")
    R = read(D / "records_parsed_v2.tsv")
    S = read(CAL / "sample_targets_v1.tsv")
    FE = read(CAL / "first_edition_targets_v1.tsv")

    strat = dict(zip(S["sample_id"], S["stratum"]))
    J = J.merge(L[["judgment_id", "work_relation", "publication_relation", "confidence"]], on="judgment_id")
    J["s_stratum"] = J["sample_id"].map(strat)

    # ---- agreement
    A = H[["judgment_id", "human_work_relation", "human_publication_relation"]].merge(
        L[["judgment_id", "work_relation", "publication_relation"]], on="judgment_id")
    A = A.rename(columns={"work_relation": "llm", "human_work_relation": "human",
                          "publication_relation": "llm_pub", "human_publication_relation": "human_pub"})
    A = A.merge(J[["judgment_id", "stratum", "s_stratum", "r3_author", "r3"]], on="judgment_id")
    A.to_csv(D / "agreement_v2.tsv", sep="\t", index=False, lineterminator="\n")
    conf = pd.crosstab(A["llm"], A["human"]).reindex(index=LABELS, columns=LABELS, fill_value=0)
    pub_agree = float((A["llm_pub"] == A["human_pub"]).mean())

    # ---- precision / false-negative estimates (S1+S2 only)
    est_rows = J[J["s_stratum"] != "S3"]
    aud = A[["judgment_id", "llm", "human"]]
    est = {k: estimate(est_rows.loc[est_rows["stratum"] == k, "work_relation"], aud)
           for k in ["J1_r3_author", "J2_r3_only", "J3_r3_false"]}
    est_s3 = {k: estimate(J.loc[(J["s_stratum"] == "S3") & (J["stratum"] == k), "work_relation"], aud)
              for k in ["J1_r3_author", "J2_r3_only", "J3_r3_false"]}

    # population sizes of the strata among links (S1+S2 only), for the implied recall of r3_author
    Mns = M[M["sample_id"].map(strat) != "S3"]
    pop = {"J1_r3_author": int(Mns["r3_author"].eq("True").sum()),
           "J2_r3_only": int((Mns["r3"].eq("True") & Mns["r3_author"].eq("False")).sum()),
           "J3_r3_false": int(Mns["r3"].eq("False").sum())}
    exp_valid = {k: pop[k] * est[k]["estimate_human_valid"] for k in pop}
    recall_r3_author = exp_valid["J1_r3_author"] / sum(exp_valid.values()) if sum(exp_valid.values()) else None

    # ---- first-edition candidates (private list for human confirmation; public counts only)
    Rk = R.set_index("marc_001")
    rows = []
    for fe in FE[FE["status"] == "ESTABLISHED"].itertuples(index=False):
        yr = int(fe.uk_first_edition_year)
        links = M[(M["target_id"] == fe.project_work_id)]
        for lk in links.itertuples(index=False):
            y = lk.pub_year or lk.cf008_date1
            try:
                y = int(str(y).strip()[:4])
            except ValueError:
                continue
            if abs(y - yr) <= 1:
                r = Rk.loc[lk.marc_001]
                rows.append({"fe_id": fe.fe_id, "project_work_id": fe.project_work_id,
                             "uk_year": yr, "uk_publisher": fe.uk_first_edition_publisher,
                             "marc_001": lk.marc_001, "routes": lk.routes, "r3": lk.r3, "r3_author": lk.r3_author,
                             "year": y, "f245_a": r["f245_a"], "f260_b": r["f260_b"], "f264_b": r["f264_b"],
                             "f100_entries": r["f100_entries"], "human_is_uk_first_edition": "", "human": "PENDING"})
    C = pd.DataFrame(rows)
    C.to_csv(D / "first_edition_candidates_v2.tsv", sep="\t", index=False, lineterminator="\n")
    fe_counts = (C.groupby("fe_id").agg(candidates=("marc_001", "nunique"), r3=("r3", lambda s: int((s == "True").sum())),
                                       r3_author=("r3_author", lambda s: int((s == "True").sum())))
                 .reindex(FE.loc[FE["status"] == "ESTABLISHED", "fe_id"]).fillna(0).astype(int))

    # ---- per-target r3_author presence by S stratum
    per_t = M.groupby("sample_id").agg(n=("marc_001", "size"), r3=("r3", lambda s: int((s == "True").sum())),
                                       r3a=("r3_author", lambda s: int((s == "True").sum())))
    per_t["s"] = per_t.index.map(strat)
    tgt = per_t.groupby("s").agg(targets=("n", "size"), with_r3=("r3", lambda s: int((s > 0).sum())),
                                 with_r3_author=("r3a", lambda s: int((s > 0).sum())))
    all_t = S.groupby("stratum").size()
    tgt["targets_total"] = all_t
    tgt["targets_without_records"] = tgt["targets_total"] - tgt["targets"]

    summary = {
        "release": "bl_calibration_v2_analysis_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "audit": {"rows": int(len(A)), "confusion_llm_rows_human_cols": conf.astype(int).to_dict(),
                  "work_relation_agreement": round(float((A["llm"] == A["human"]).mean()), 4),
                  "publication_relation_agreement": round(pub_agree, 4)},
        "estimates_S1_S2": est, "estimates_S3_retest": est_s3,
        "link_population_S1_S2": pop, "expected_valid_links_S1_S2": {k: round(v, 1) for k, v in exp_valid.items()},
        "implied_recall_of_r3_author": round(recall_r3_author, 4) if recall_r3_author is not None else None,
        "targets_by_sample_stratum": tgt.astype(int).to_dict(orient="index"),
        "first_edition_candidate_counts": fe_counts.to_dict(orient="index"),
        "success_criterion_r3_author_ci_lower_ge_0.90": bool(est["J1_r3_author"]["ci95"][0] >= 0.90),
        "note": ("Estimates use S1+S2 only; S3 re-test shown separately. First-edition candidates are a private list "
                 "awaiting human confirmation; coverage (G1) is computed after that."),
    }
    OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
