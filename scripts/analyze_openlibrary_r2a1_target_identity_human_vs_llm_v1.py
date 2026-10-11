#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

LLM = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_llm_v1"
    / "openlibrary_r2a1_target_identity_llm_v1.tsv"
)

HUMAN = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_human_adjudication_v1"
    / "openlibrary_r2a1_target_identity_human_adjudication_v1.tsv"
)

SELECTION = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_human_audit_sample_v1"
    / "openlibrary_r2a1_target_identity_human_audit_selection_v1.tsv"
)

OUT_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_human_vs_llm_v1"
)

JOINED = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_human_vs_llm_v1.tsv"
)

DISAGREE = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_human_vs_llm_disagreements_v1.tsv"
)

SUMMARY = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_human_vs_llm_v1_summary.json"
)

MANIFEST = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_human_vs_llm_v1_manifest.json"
)


RELEASE = (
    "openlibrary-r2a1-target-identity-human-vs-llm-v1"
)

EXPECTED_HUMAN_ROWS = 20
EXPECTED_LLM_ROWS = 48
EXPECTED_WEIGHT_SUM = 48.0


AXES = {
    "entity_status": (
        "llm_entity_status",
        "human_entity_status",
    ),
    "content_type": (
        "llm_content_type",
        "human_content_type",
    ),
    "date_window_assessment": (
        "llm_date_window_assessment",
        "human_date_window_assessment",
    ),
}


def sha256_file(path):
    h = hashlib.sha256()

    with Path(path).open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def atomic_tsv(df, path):
    tmp = path.with_name(
        path.name + ".tmp"
    )

    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    os.replace(
        tmp,
        path,
    )


def atomic_json(obj, path):
    tmp = path.with_name(
        path.name + ".tmp"
    )

    tmp.write_text(
        json.dumps(
            obj,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    os.replace(
        tmp,
        path,
    )


def contingency(df, human_col, llm_col):
    tab = pd.crosstab(
        df[human_col],
        df[llm_col],
        dropna=False,
    )

    return {
        str(r): {
            str(c): int(
                tab.loc[r, c]
            )
            for c in tab.columns
        }
        for r in tab.index
    }


def weighted_contingency(
    df,
    human_col,
    llm_col,
):
    tab = pd.pivot_table(
        df,
        index=human_col,
        columns=llm_col,
        values="design_weight",
        aggfunc="sum",
        fill_value=0.0,
    )

    return {
        str(r): {
            str(c): float(
                tab.loc[r, c]
            )
            for c in tab.columns
        }
        for r in tab.index
    }


def main():

    for p in [
        LLM,
        HUMAN,
        SELECTION,
    ]:
        if not p.exists():
            raise FileNotFoundError(p)

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory already exists: {OUT_DIR}"
        )

    llm = pd.read_csv(
        LLM,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    human = pd.read_csv(
        HUMAN,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    selection = pd.read_csv(
        SELECTION,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    if len(llm) != EXPECTED_LLM_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_LLM_ROWS} LLM rows; "
            f"found {len(llm)}"
        )

    if len(human) != EXPECTED_HUMAN_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_HUMAN_ROWS} human rows; "
            f"found {len(human)}"
        )

    if len(selection) != EXPECTED_HUMAN_ROWS:
        raise RuntimeError(
            "Selection row count mismatch"
        )

    for df, name in [
        (llm, "LLM"),
        (human, "human"),
        (selection, "selection"),
    ]:
        if not df[
            "current_ol_work_id"
        ].is_unique:
            raise RuntimeError(
                f"{name}: current_ol_work_id not unique"
            )

    joined = (
        human.merge(
            selection[
                [
                    "current_ol_work_id",
                    "audit_sampling_stratum",
                    "audit_stratum_population_n",
                    "audit_stratum_sample_n",
                ]
            ],
            on="current_ol_work_id",
            how="left",
            validate="one_to_one",
        )
        .merge(
            llm[
                [
                    "current_ol_work_id",
                    "project_work_id",
                    "r2_target_title",
                    "r2_target_author",
                    "llm_entity_status",
                    "llm_content_type",
                    "llm_date_window_assessment",
                    "llm_confidence",
                    "llm_note",
                ]
            ],
            on="current_ol_work_id",
            how="left",
            validate="one_to_one",
            suffixes=("", "_llm"),
        )
    )

    if len(joined) != EXPECTED_HUMAN_ROWS:
        raise RuntimeError(
            "Joined row count mismatch"
        )

    for field in [
        "project_work_id",
        "r2_target_title",
        "r2_target_author",
    ]:
        other = field + "_llm"

        bad = joined[
            joined[field].ne(
                joined[other]
            )
        ]

        if len(bad):
            raise RuntimeError(
                f"Human/LLM identity mismatch in {field}"
            )

    joined[
        "audit_stratum_population_n"
    ] = pd.to_numeric(
        joined[
            "audit_stratum_population_n"
        ],
        errors="raise",
    )

    joined[
        "audit_stratum_sample_n"
    ] = pd.to_numeric(
        joined[
            "audit_stratum_sample_n"
        ],
        errors="raise",
    )

    joined[
        "design_weight"
    ] = (
        joined[
            "audit_stratum_population_n"
        ]
        /
        joined[
            "audit_stratum_sample_n"
        ]
    )

    weight_sum = float(
        joined[
            "design_weight"
        ].sum()
    )

    if abs(
        weight_sum
        - EXPECTED_WEIGHT_SUM
    ) > 1e-9:
        raise RuntimeError(
            f"Design weights sum to {weight_sum}, "
            f"expected {EXPECTED_WEIGHT_SUM}"
        )

    summary = {
        "release":
            RELEASE,

        "status":
            "human_llm_agreement_diagnostic",

        "sample_rows":
            len(joined),

        "risk_set_population_rows":
            EXPECTED_LLM_ROWS,

        "design_weight_sum":
            weight_sum,

        "interpretation": (
            "Agreement diagnostic between frozen LLM "
            "and frozen human judgments on the "
            "20-record stratified audit sample. "
            "The review workbook withheld LLM labels "
            "and retrieval-impact fields, but the human "
            "reviewer had previously been exposed to "
            "row-level LLM results. Therefore these "
            "statistics are not an independent blinded "
            "accuracy validation."
        ),

        "date_axis_caveat": (
            "Date-window agreement is diagnostic only. "
            "It must not be operationalized as a corpus "
            "inclusion/exclusion rule without separately "
            "establishing the intended corpus date "
            "semantics for collections and underlying "
            "intellectual works."
        ),

        "axes": {},
    }

    disagreement_parts = []

    for axis, (
        llm_col,
        human_col,
    ) in AXES.items():

        match_col = (
            axis + "_exact_match"
        )

        joined[
            match_col
        ] = joined[
            llm_col
        ].eq(
            joined[
                human_col
            ]
        )

        raw_matches = int(
            joined[
                match_col
            ].sum()
        )

        raw_rate = (
            raw_matches
            / len(joined)
        )

        weighted_rate = float(
            (
                joined[
                    "design_weight"
                ]
                * joined[
                    match_col
                ].astype(float)
            ).sum()
            / weight_sum
        )

        stratum_rows = {}

        for stratum, g in joined.groupby(
            "audit_sampling_stratum",
            sort=True,
        ):
            stratum_rows[
                stratum
            ] = {
                "population_n":
                    int(
                        g[
                            "audit_stratum_population_n"
                        ].iloc[0]
                    ),

                "sample_n":
                    int(len(g)),

                "exact_matches":
                    int(
                        g[
                            match_col
                        ].sum()
                    ),

                "sample_exact_agreement":
                    float(
                        g[
                            match_col
                        ].mean()
                    ),
            }

        summary[
            "axes"
        ][axis] = {
            "raw_exact_matches":
                raw_matches,

            "raw_sample_n":
                len(joined),

            "raw_exact_agreement":
                raw_rate,

            "design_weighted_exact_agreement":
                weighted_rate,

            "contingency_human_rows_llm_columns":
                contingency(
                    joined,
                    human_col,
                    llm_col,
                ),

            "weighted_contingency_human_rows_llm_columns":
                weighted_contingency(
                    joined,
                    human_col,
                    llm_col,
                ),

            "agreement_by_sampling_stratum":
                stratum_rows,
        }

        d = joined.loc[
            ~joined[
                match_col
            ],
            [
                "review_order",
                "project_work_id",
                "current_ol_work_id",
                "r2_target_title",
                "r2_target_author",
                "audit_sampling_stratum",
                "design_weight",
                llm_col,
                human_col,
                "llm_confidence",
                "human_confidence",
                "llm_note",
                "human_note",
            ],
        ].copy()

        d.insert(
            0,
            "axis",
            axis,
        )

        d = d.rename(
            columns={
                llm_col:
                    "llm_judgment",

                human_col:
                    "human_judgment",
            }
        )

        disagreement_parts.append(
            d
        )

    disagreements = pd.concat(
        disagreement_parts,
        ignore_index=True,
    )

    # Keep one analysis table with both sides visible.
    keep_cols = [
        "review_order",
        "project_work_id",
        "current_ol_work_id",
        "r2_target_title",
        "r2_target_author",
        "audit_sampling_stratum",
        "audit_stratum_population_n",
        "audit_stratum_sample_n",
        "design_weight",
        "llm_entity_status",
        "human_entity_status",
        "entity_status_exact_match",
        "llm_content_type",
        "human_content_type",
        "content_type_exact_match",
        "llm_date_window_assessment",
        "human_date_window_assessment",
        "date_window_assessment_exact_match",
        "llm_confidence",
        "human_confidence",
        "llm_note",
        "human_note",
    ]

    joined_out = (
        joined[
            keep_cols
        ]
        .sort_values(
            "review_order",
            key=lambda s:
                pd.to_numeric(
                    s,
                    errors="raise",
                ),
        )
        .reset_index(
            drop=True
        )
    )

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=False,
    )

    atomic_tsv(
        joined_out,
        JOINED,
    )

    atomic_tsv(
        disagreements,
        DISAGREE,
    )

    atomic_json(
        summary,
        SUMMARY,
    )

    manifest = {
        "release":
            RELEASE,

        "status":
            "frozen_analysis_candidate",

        "inputs": {
            str(
                LLM.relative_to(
                    ROOT
                )
            ):
                sha256_file(LLM),

            str(
                HUMAN.relative_to(
                    ROOT
                )
            ):
                sha256_file(HUMAN),

            str(
                SELECTION.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    SELECTION
                ),
        },

        "outputs": {
            str(
                JOINED.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    JOINED
                ),

            str(
                DISAGREE.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    DISAGREE
                ),

            str(
                SUMMARY.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    SUMMARY
                ),
        },

        "semantics": [
            (
                "No pair-count or retrieval-impact "
                "information is used in this agreement "
                "analysis."
            ),
            (
                "Raw agreement is the simple proportion "
                "within the 20-record audit sample."
            ),
            (
                "Design-weighted agreement uses "
                "N_h / n_h weights from the frozen "
                "LLM entity-status sampling strata to "
                "estimate agreement over the 48-record "
                "risk-set population."
            ),
            (
                "These agreement statistics are "
                "diagnostic and must not be described "
                "as independent blinded LLM accuracy."
            ),
        ],
    }

    atomic_json(
        manifest,
        MANIFEST,
    )

    print(
        "=== OL TARGET IDENTITY HUMAN VS LLM V1 ==="
    )

    print(
        "sample rows:",
        len(joined),
    )

    print(
        "weight sum:",
        f"{weight_sum:.6f}",
    )

    for axis in AXES:
        x = summary[
            "axes"
        ][axis]

        print(
            f"\n=== {axis} ==="
        )

        print(
            "raw exact:",
            f"{x['raw_exact_matches']}"
            f"/{x['raw_sample_n']}",
            f"= {x['raw_exact_agreement']:.6%}",
        )

        print(
            "design-weighted exact:",
            f"{x['design_weighted_exact_agreement']:.6%}",
        )

        print(
            "by sampling stratum:"
        )

        for k, v in (
            x[
                "agreement_by_sampling_stratum"
            ].items()
        ):
            print(
                " ",
                k,
                f"{v['exact_matches']}/{v['sample_n']}",
                f"= {v['sample_exact_agreement']:.6%}",
                f"(N={v['population_n']})",
            )

    print(
        "\ndisagreement rows:",
        len(disagreements),
    )

    print(
        "\n=== DISAGREEMENTS ==="
    )

    print(
        disagreements[
            [
                "axis",
                "review_order",
                "r2_target_title",
                "current_ol_work_id",
                "llm_judgment",
                "human_judgment",
            ]
        ].to_string(
            index=False
        )
    )

    print(
        "\nQC STATUS: PASSED"
    )


if __name__ == "__main__":
    main()
