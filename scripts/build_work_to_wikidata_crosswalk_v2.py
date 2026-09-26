import json
from pathlib import Path

import pandas as pd


ROOT = Path("derived/crosswalks")

V1 = ROOT / "work_to_wikidata.parquet"
CORR = ROOT / "work_to_wikidata_corrections_v1.tsv"

OUT = ROOT / "work_to_wikidata_v2.parquet"
SUMMARY = ROOT / "work_to_wikidata_v2_summary.json"


v1 = pd.read_parquet(V1).copy()

corr = pd.read_csv(
    CORR,
    sep="\t",
    dtype=str,
    keep_default_na=False,
)


# ------------------------------------------------------------
# 1. Validate base crosswalk and correction layer
# ------------------------------------------------------------

assert len(v1) == 34789
assert v1["ol_work_id"].is_unique

assert len(corr) == 1
assert corr["ol_work_id"].is_unique

assert set(corr["ol_work_id"]).issubset(
    set(v1["ol_work_id"])
)

base_check = v1[
    v1["ol_work_id"].isin(corr["ol_work_id"])
][
    [
        "ol_work_id",
        "decision",
        "wikidata_qid",
    ]
].merge(
    corr[
        [
            "ol_work_id",
            "original_decision",
            "original_wikidata_qid",
        ]
    ],
    on="ol_work_id",
    how="inner",
    validate="one_to_one",
)

assert (
    base_check["decision"]
    == base_check["original_decision"]
).all()

assert (
    base_check["wikidata_qid"].fillna("")
    == base_check["original_wikidata_qid"]
).all()


# ------------------------------------------------------------
# 2. Add provenance columns
# ------------------------------------------------------------

out = v1.copy()

out["correction_applied"] = False
out["original_decision"] = ""
out["original_wikidata_qid"] = ""
out["correction_type"] = ""
out["correction_evidence_status"] = ""
out["correction_reason"] = ""


# ------------------------------------------------------------
# 3. Apply source-supported corrections
# ------------------------------------------------------------

out = out.set_index("ol_work_id")

for r in corr.itertuples(index=False):

    oid = r.ol_work_id

    out.at[oid, "correction_applied"] = True

    out.at[
        oid,
        "original_decision",
    ] = r.original_decision

    out.at[
        oid,
        "original_wikidata_qid",
    ] = r.original_wikidata_qid

    out.at[
        oid,
        "decision",
    ] = r.corrected_decision

    out.at[
        oid,
        "wikidata_qid",
    ] = (
        r.corrected_wikidata_qid
        if r.corrected_wikidata_qid
        else None
    )

    out.at[
        oid,
        "confidence",
    ] = ""

    out.at[
        oid,
        "resolution_stage",
    ] = "source_correction"

    out.at[
        oid,
        "decision_source",
    ] = "work_to_wikidata_corrections_v1"

    out.at[
        oid,
        "context_safe_fallback",
    ] = False

    out.at[
        oid,
        "correction_type",
    ] = r.correction_type

    out.at[
        oid,
        "correction_evidence_status",
    ] = r.evidence_status

    out.at[
        oid,
        "correction_reason",
    ] = r.reason


out = out.reset_index()


# ------------------------------------------------------------
# 4. Integrity checks
# ------------------------------------------------------------

assert len(out) == 34789
assert out["ol_work_id"].is_unique

assert out["correction_applied"].sum() == 1

assert (
    out.loc[
        out["ol_work_id"].eq("OL69043W"),
        "decision",
    ].iloc[0]
    == "NO_MATCH"
)

assert pd.isna(
    out.loc[
        out["ol_work_id"].eq("OL69043W"),
        "wikidata_qid",
    ].iloc[0]
)

assert (
    out.loc[
        out["ol_work_id"].eq("OL69043W"),
        "original_wikidata_qid",
    ].iloc[0]
    == "Q301517"
)

assert (
    out.loc[
        out["ol_work_id"].eq("OL85885W"),
        "wikidata_qid",
    ].iloc[0]
    == "Q301517"
)

assert (
    out.loc[
        out["decision"].ne("MATCH"),
        "wikidata_qid",
    ].notna().sum()
    == 0
)


# ------------------------------------------------------------
# 5. Write
# ------------------------------------------------------------

out.to_parquet(
    OUT,
    index=False,
)

summary = {
    "source_crosswalk": str(V1),
    "correction_layer": str(CORR),
    "output": str(OUT),
    "rows": len(out),
    "corrections_applied": int(
        out["correction_applied"].sum()
    ),
    "decision_counts": (
        out["decision"]
        .value_counts()
        .to_dict()
    ),
    "policy": (
        "Original v1 crosswalk remains unchanged. "
        "Source-supported corrections are overlaid "
        "with explicit provenance."
    ),
}

SUMMARY.write_text(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2,
    ) + "\n",
    encoding="utf-8",
)


print("=== V2 CROSSWALK ===")
print(out["decision"].value_counts().to_string())

print("\n=== CORRECTIONS ===")
print(
    out[
        out["correction_applied"]
    ][
        [
            "ol_work_id",
            "original_decision",
            "original_wikidata_qid",
            "decision",
            "wikidata_qid",
            "resolution_stage",
            "decision_source",
            "correction_type",
        ]
    ].to_string(index=False)
)

print("\n=== DISTINCT SAME-TITLE WORK CHECK ===")
print(
    out[
        out["ol_work_id"].isin(
            ["OL69043W", "OL85885W"]
        )
    ][
        [
            "ol_work_id",
            "decision",
            "wikidata_qid",
            "correction_applied",
        ]
    ].to_string(index=False)
)

print("\noutput:", OUT)
print("summary:", SUMMARY)
