from pathlib import Path
from collections import Counter
import hashlib
import json
import os
import re
import unicodedata

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

PROFILE = "full_profile_57959e90"
RELEASE = "openalex-retrieval-by-work-error-analysis-v1"
VERSION = "v1"
CREATED_AT = "2026-10-06"

CAND = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_precision_review_candidates_v3"
    / PROFILE
    / "openalex_retrieval_precision_review_candidates_v3.parquet"
)

ADJ = (
    ROOT
    / "derived/openalex_production"
    / "openalex_retrieval_precision_review_human_adjudication_complete_v1"
    / PROFILE
    / "openalex_retrieval_precision_review_human_adjudication_complete_v1.tsv"
)

ALIASES = (
    ROOT
    / "derived/openalex_production"
    / "registry_v4"
    / "openalex_aliases_v4.parquet"
)

FROZEN_PRECISION_SUMMARY = (
    ROOT
    / "derived/openalex_production"
    / "openalex_retrieval_precision_results_v1"
    / PROFILE
    / "openalex_retrieval_precision_results_v1_summary.tsv"
)

FROZEN_PRECISION_BY_WORK = (
    ROOT
    / "derived/openalex_production"
    / "openalex_retrieval_precision_results_v1"
    / PROFILE
    / "openalex_retrieval_precision_results_v1_by_work.tsv"
)

OUT_DIR = (
    ROOT
    / "derived/openalex_production"
    / "openalex_retrieval_by_work_error_analysis_v1"
    / PROFILE
)

OUT_CAND_TSV = (
    OUT_DIR
    / "openalex_retrieval_by_work_error_analysis_v1_candidate_diagnostics.tsv"
)

OUT_CAND_PARQUET = (
    OUT_DIR
    / "openalex_retrieval_by_work_error_analysis_v1_candidate_diagnostics.parquet"
)

OUT_WORK_TSV = (
    OUT_DIR
    / "openalex_retrieval_by_work_error_analysis_v1_by_work.tsv"
)

OUT_WORK_PARQUET = (
    OUT_DIR
    / "openalex_retrieval_by_work_error_analysis_v1_by_work.parquet"
)

OUT_AUDIT = (
    OUT_DIR
    / "openalex_retrieval_by_work_error_analysis_v1_audit_v1.json"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openalex_retrieval_by_work_error_analysis_v1_manifest.json"
)


EXPECTED_CANDIDATE_ROWS = 661
EXPECTED_WORK_ROWS = 65

EXPECTED_STRATUM_COUNTS = {
    "A2_AUTHOR_REVERSAL": {
        "candidate_count": 252,
        "valid_count": 241,
        "invalid_count": 10,
        "uncertain_count": 1,
    },
    "ALIAS_EXPANSION": {
        "candidate_count": 409,
        "valid_count": 364,
        "invalid_count": 24,
        "uncertain_count": 21,
    },
}

STRATUM_ORDER = {
    "A2_AUTHOR_REVERSAL": 0,
    "ALIAS_EXPANSION": 1,
}


def require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_atomic_tsv(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )
    os.replace(tmp, path)


def write_atomic_parquet(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(
        tmp,
        index=False,
        engine="pyarrow",
    )
    os.replace(tmp, path)


def write_atomic_json(value: dict, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def split_set(value):
    if pd.isna(value):
        return []

    return sorted(
        set(
            x.strip()
            for x in str(value).split(" || ")
            if x.strip()
        )
    )


def joined_set(value):
    return " || ".join(split_set(value))


def count_set(value):
    return len(split_set(value))


def compare_norm(value):
    x = unicodedata.normalize(
        "NFKC",
        str(value),
    )
    x = x.casefold()
    x = re.sub(r"\s+", " ", x).strip()
    return x


def norm_set(value):
    return {
        compare_norm(x)
        for x in split_set(value)
    }


def token_minmax(value):
    vals = split_set(value)

    if not vals:
        return pd.Series(
            [pd.NA, pd.NA],
            dtype="object",
        )

    counts = [
        len(x.split())
        for x in vals
    ]

    return pd.Series(
        [min(counts), max(counts)],
        dtype="object",
    )


def as_bool(value):
    if isinstance(value, bool):
        return value

    return (
        str(value)
        .strip()
        .lower()
        == "true"
    )


def reason_counts(series):
    values = [
        str(x)
        for x in series
        if pd.notna(x)
        and str(x).strip()
    ]

    if not values:
        return ""

    counts = Counter(values)

    return " || ".join(
        f"{key}:{counts[key]}"
        for key in sorted(counts)
    )


def safe_share(num, den):
    if den == 0:
        return pd.NA
    return num / den


def main():

    for path in [
        CAND,
        ADJ,
        ALIASES,
        FROZEN_PRECISION_SUMMARY,
        FROZEN_PRECISION_BY_WORK,
    ]:
        require(path)

    cand = pd.read_parquet(CAND)

    adj = pd.read_csv(
        ADJ,
        sep="\t",
        dtype=str,
    )

    aliases = pd.read_parquet(ALIASES)

    frozen_precision_summary = pd.read_csv(
        FROZEN_PRECISION_SUMMARY,
        sep="\t",
    )

    frozen_precision_by_work = pd.read_csv(
        FROZEN_PRECISION_BY_WORK,
        sep="\t",
    )

    # --------------------------------------------------------
    # Frozen input invariants
    # --------------------------------------------------------

    if len(cand) != 661:
        raise RuntimeError(
            f"candidate rows != 661: {len(cand)}"
        )

    if not cand["review_candidate_id"].is_unique:
        raise RuntimeError(
            "candidate review_candidate_id not unique"
        )

    if len(adj) != 661:
        raise RuntimeError(
            f"adjudication rows != 661: {len(adj)}"
        )

    if not adj["review_candidate_id"].is_unique:
        raise RuntimeError(
            "adjudication review_candidate_id not unique"
        )

    if not aliases["alias_id"].is_unique:
        raise RuntimeError(
            "alias_id not unique"
        )

    df = cand.merge(
        adj[
            [
                "review_candidate_id",
                "human_target_attribution_judgment",
                "human_attribution_reason_code",
            ]
        ],
        on="review_candidate_id",
        how="left",
        validate="one_to_one",
    )

    if len(df) != 661:
        raise RuntimeError(
            "candidate/adjudication join changed row count"
        )

    if df[
        "human_target_attribution_judgment"
    ].isna().any():
        raise RuntimeError(
            "missing human adjudication"
        )

    # --------------------------------------------------------
    # Candidate-level deterministic provenance aggregation
    #
    # query_id remains release-local provenance only.
    # IDs themselves are not emitted as persistent identity.
    # --------------------------------------------------------

    df[
        "provenance_evidence_row_count"
    ] = pd.to_numeric(
        df["r3_evidence_rows"],
        errors="raise",
    ).astype(int)

    df[
        "provenance_query_count_release_local"
    ] = df["r3_query_ids"].map(
        count_set
    )

    df[
        "provenance_execution_count_release_local"
    ] = df["r3_execution_ids"].map(
        count_set
    )

    df[
        "provenance_alias_count"
    ] = df["r3_alias_ids"].map(
        count_set
    )

    df[
        "query_title_set"
    ] = df["r3_query_titles"].map(
        joined_set
    )

    df[
        "query_author_set"
    ] = df["r3_query_authors"].map(
        joined_set
    )

    df[
        "alias_id_set"
    ] = df["r3_alias_ids"].map(
        joined_set
    )

    df[
        "title_match_norm_set"
    ] = df["title_match_norms"].map(
        joined_set
    )

    df[
        [
            "title_match_token_count_min",
            "title_match_token_count_max",
        ]
    ] = df[
        "title_match_norms"
    ].apply(
        token_minmax
    )

    # --------------------------------------------------------
    # Deployable feature: hit location
    # --------------------------------------------------------

    df["title_hit"] = (
        df[
            "any_title_match_in_title"
        ].map(as_bool)
    )

    df["abstract_hit"] = (
        df[
            "any_title_match_in_abstract"
        ].map(as_bool)
    )

    df["hit_location"] = "OTHER"

    df.loc[
        df["title_hit"]
        & ~df["abstract_hit"],
        "hit_location",
    ] = "TITLE_ONLY"

    df.loc[
        ~df["title_hit"]
        & df["abstract_hit"],
        "hit_location",
    ] = "ABSTRACT_ONLY"

    df.loc[
        df["title_hit"]
        & df["abstract_hit"],
        "hit_location",
    ] = "TITLE_AND_ABSTRACT"

    # --------------------------------------------------------
    # Deployable feature:
    # cross-project-work collision under frozen alias_value_norm
    # --------------------------------------------------------

    resolved = aliases[
        aliases["target_lane"].eq(
            "resolved_w"
        )
        & aliases[
            "project_work_id"
        ].notna()
        & aliases[
            "project_work_id"
        ].ne("")
    ].copy()

    collision = (
        resolved.groupby(
            "alias_value_norm"
        )
        .agg(
            distinct_project_work_count=(
                "project_work_id",
                "nunique",
            )
        )
        .reset_index()
    )

    lookup = (
        aliases[
            [
                "alias_id",
                "alias_value_norm",
            ]
        ]
        .merge(
            collision,
            on="alias_value_norm",
            how="left",
            validate="many_to_one",
        )
        .set_index("alias_id")
    )

    def collision_features(value):
        alias_ids = split_set(value)
        counts = []

        for aid in alias_ids:

            if aid not in lookup.index:
                raise RuntimeError(
                    "alias missing from registry: "
                    f"{aid}"
                )

            counts.append(
                int(
                    lookup.loc[
                        aid,
                        "distinct_project_work_count",
                    ]
                )
            )

        if not counts:
            return pd.Series(
                [
                    False,
                    0,
                    pd.NA,
                ],
                dtype="object",
            )

        return pd.Series(
            [
                any(x > 1 for x in counts),
                sum(x > 1 for x in counts),
                max(counts),
            ],
            dtype="object",
        )

    df[
        [
            "any_cross_w_title_collision",
            "cross_w_collision_alias_count",
            "max_distinct_project_work_count",
        ]
    ] = df[
        "r3_alias_ids"
    ].apply(
        collision_features
    )

    # --------------------------------------------------------
    # Deployable feature:
    # alias-expansion mechanism.
    #
    # This comparison normalization is diagnostic only:
    # NFKC + casefold + whitespace collapse.
    # It does NOT replace the frozen retrieval normalization.
    # --------------------------------------------------------

    def mechanism(row):

        if (
            row["increment_type"]
            != "ALIAS_EXPANSION"
        ):
            return "NOT_APPLICABLE_A2"

        r2_titles = norm_set(
            row["r2_baseline_titles"]
        )
        r3_titles = norm_set(
            row["r3_query_titles"]
        )

        r2_authors = norm_set(
            row["r2_baseline_authors"]
        )
        r3_authors = norm_set(
            row["r3_query_authors"]
        )

        title_variant = bool(
            r3_titles - r2_titles
        )

        author_variant = bool(
            r3_authors - r2_authors
        )

        if (
            title_variant
            and author_variant
        ):
            return (
                "TITLE_AND_AUTHOR_VARIANT"
            )

        if title_variant:
            return "TITLE_VARIANT_ONLY"

        if author_variant:
            return "AUTHOR_VARIANT_ONLY"

        return "SAME_NORMALIZED_PAIR"

    df[
        "alias_expansion_mechanism"
    ] = df.apply(
        mechanism,
        axis=1,
    )

    # --------------------------------------------------------
    # Explicit post-hoc outcomes
    # --------------------------------------------------------

    df = df.rename(
        columns={
            "human_target_attribution_judgment":
                "posthoc_human_target_attribution_judgment",

            "human_attribution_reason_code":
                "posthoc_human_attribution_reason_code",
        }
    )

    # --------------------------------------------------------
    # Candidate diagnostics
    # --------------------------------------------------------

    candidate_cols = [
        "review_candidate_id",
        "project_work_id",
        "openalex_work_id",
        "increment_type",

        "r2_baseline_titles",
        "r2_baseline_authors",

        "display_name",
        "publication_year",
        "type",

        "provenance_evidence_row_count",
        "provenance_query_count_release_local",
        "provenance_execution_count_release_local",
        "provenance_alias_count",

        "query_title_set",
        "query_author_set",
        "alias_id_set",

        "title_match_norm_set",
        "title_match_token_count_min",
        "title_match_token_count_max",

        "hit_location",
        "any_title_match_in_title",
        "any_title_match_in_abstract",
        "any_author_a1_hit",
        "any_author_a2_reverse_hit",

        "any_cross_w_title_collision",
        "cross_w_collision_alias_count",
        "max_distinct_project_work_count",

        "alias_expansion_mechanism",

        "posthoc_human_target_attribution_judgment",
        "posthoc_human_attribution_reason_code",
    ]

    diag = df[
        candidate_cols
    ].copy()

    diag["_stratum_order"] = (
        diag["increment_type"]
        .map(STRATUM_ORDER)
    )

    diag = (
        diag.sort_values(
            [
                "_stratum_order",
                "project_work_id",
                "review_candidate_id",
            ],
            kind="stable",
        )
        .drop(
            columns=[
                "_stratum_order"
            ]
        )
        .reset_index(drop=True)
    )

    if len(diag) != 661:
        raise RuntimeError(
            "candidate diagnostic rows != 661"
        )

    if not diag[
        "review_candidate_id"
    ].is_unique:
        raise RuntimeError(
            "candidate diagnostics not unique"
        )

    # --------------------------------------------------------
    # Work-level aggregation
    # --------------------------------------------------------

    groups = []

    group_keys = [
        "increment_type",
        "project_work_id",
        "r2_baseline_titles",
        "r2_baseline_authors",
    ]

    for keys, z in df.groupby(
        group_keys,
        dropna=False,
        sort=True,
    ):

        (
            increment_type,
            project_work_id,
            baseline_titles,
            baseline_authors,
        ) = keys

        judgment = z[
            "posthoc_human_target_attribution_judgment"
        ]

        valid = int(
            (
                judgment
                == "VALID_TARGET_REFERENCE"
            ).sum()
        )

        invalid = int(
            (
                judgment
                == "INVALID_TARGET_REFERENCE"
            ).sum()
        )

        uncertain = int(
            (
                judgment
                == "UNCERTAIN"
            ).sum()
        )

        candidate_count = len(z)

        invalid_reasons = z.loc[
            judgment
            == "INVALID_TARGET_REFERENCE",
            "posthoc_human_attribution_reason_code",
        ]

        uncertain_reasons = z.loc[
            judgment
            == "UNCERTAIN",
            "posthoc_human_attribution_reason_code",
        ]

        mechanisms = sorted(
            set(
                str(x)
                for x in z[
                    "alias_expansion_mechanism"
                ]
                if pd.notna(x)
            )
        )

        groups.append(
            {
                "increment_type":
                    increment_type,

                "project_work_id":
                    project_work_id,

                "r2_baseline_titles":
                    baseline_titles,

                "r2_baseline_authors":
                    baseline_authors,

                "candidate_count":
                    candidate_count,

                "valid_count":
                    valid,

                "invalid_count":
                    invalid,

                "uncertain_count":
                    uncertain,

                "not_confirmed_valid_count":
                    invalid + uncertain,

                "confirmed_valid_rate_within_work":
                    valid / candidate_count,

                "upper_valid_rate_within_work":
                    (
                        valid + uncertain
                    ) / candidate_count,

                "resolved_valid_rate_within_work":
                    (
                        valid
                        / (valid + invalid)
                        if (valid + invalid) > 0
                        else pd.NA
                    ),

                "abstract_only_candidate_count":
                    int(
                        (
                            z["hit_location"]
                            == "ABSTRACT_ONLY"
                        ).sum()
                    ),

                "title_only_candidate_count":
                    int(
                        (
                            z["hit_location"]
                            == "TITLE_ONLY"
                        ).sum()
                    ),

                "title_and_abstract_candidate_count":
                    int(
                        (
                            z["hit_location"]
                            == "TITLE_AND_ABSTRACT"
                        ).sum()
                    ),

                "cross_w_collision_candidate_count":
                    int(
                        z[
                            "any_cross_w_title_collision"
                        ]
                        .astype(bool)
                        .sum()
                    ),

                "any_cross_w_title_collision":
                    bool(
                        z[
                            "any_cross_w_title_collision"
                        ]
                        .astype(bool)
                        .any()
                    ),

                "max_distinct_project_work_count":
                    int(
                        pd.to_numeric(
                            z[
                                "max_distinct_project_work_count"
                            ],
                            errors="coerce",
                        )
                        .max()
                    ),

                "alias_expansion_mechanism_set":
                    " || ".join(
                        mechanisms
                    ),

                "title_variant_only_candidate_count":
                    int(
                        (
                            z[
                                "alias_expansion_mechanism"
                            ]
                            == "TITLE_VARIANT_ONLY"
                        ).sum()
                    ),

                "author_variant_only_candidate_count":
                    int(
                        (
                            z[
                                "alias_expansion_mechanism"
                            ]
                            == "AUTHOR_VARIANT_ONLY"
                        ).sum()
                    ),

                "title_and_author_variant_candidate_count":
                    int(
                        (
                            z[
                                "alias_expansion_mechanism"
                            ]
                            == "TITLE_AND_AUTHOR_VARIANT"
                        ).sum()
                    ),

                "posthoc_invalid_reason_code_counts":
                    reason_counts(
                        invalid_reasons
                    ),

                "posthoc_uncertain_reason_code_counts":
                    reason_counts(
                        uncertain_reasons
                    ),
            }
        )

    by_work = pd.DataFrame(groups)

    if len(by_work) != 65:
        raise RuntimeError(
            f"by-work rows != 65: {len(by_work)}"
        )

    # --------------------------------------------------------
    # Stratum metrics
    # --------------------------------------------------------

    work_parts = []

    for (
        stratum,
        x
    ) in by_work.groupby(
        "increment_type",
        sort=True,
    ):

        x = x.copy()

        N = int(
            x["candidate_count"].sum()
        )

        K = len(x)

        V = int(
            x["valid_count"].sum()
        )

        I = int(
            x["invalid_count"].sum()
        )

        U = int(
            x["uncertain_count"].sum()
        )

        NC = I + U

        full_micro = (
            V / N
        )

        full_macro = (
            x[
                "confirmed_valid_rate_within_work"
            ]
            .mean()
        )

        x[
            "candidate_share_within_stratum"
        ] = (
            x["candidate_count"]
            / N
        )

        x[
            "candidate_share_overall"
        ] = (
            x["candidate_count"]
            / 661
        )

        x[
            "equal_work_share_within_stratum"
        ] = (
            1 / K
        )

        x[
            "candidate_share_deviation_from_equal_work_within_stratum"
        ] = (
            x[
                "candidate_share_within_stratum"
            ]
            - 1 / K
        )

        x[
            "invalid_count_share_within_stratum"
        ] = [
            safe_share(v, I)
            for v in x[
                "invalid_count"
            ]
        ]

        x[
            "uncertain_count_share_within_stratum"
        ] = [
            safe_share(v, U)
            for v in x[
                "uncertain_count"
            ]
        ]

        x[
            "not_confirmed_valid_count_share_within_stratum"
        ] = [
            safe_share(v, NC)
            for v in x[
                "not_confirmed_valid_count"
            ]
        ]

        x[
            "full_micro_confirmed_valid_within_stratum"
        ] = full_micro

        x[
            "full_macro_w_confirmed_valid_within_stratum"
        ] = full_macro

        x[
            "leave_one_out_micro_confirmed_valid_within_stratum"
        ] = (
            (
                V
                - x["valid_count"]
            )
            /
            (
                N
                - x["candidate_count"]
            )
        )

        # Sign convention:
        #
        # full micro - leave-one-out micro
        #
        # positive => this work raises
        #             the full micro estimate
        x[
            "micro_change_if_work_removed_confirmed_valid"
        ] = (
            full_micro
            - x[
                "leave_one_out_micro_confirmed_valid_within_stratum"
            ]
        )

        # Primary confirmed-valid micro-macro
        # gap contribution only.
        x[
            "confirmed_valid_micro_macro_gap_contribution_within_stratum"
        ] = (
            x[
                "confirmed_valid_rate_within_work"
            ]
            * (
                x[
                    "candidate_share_within_stratum"
                ]
                - 1 / K
            )
        )

        # Competition ranking:
        # 10, 10, 8 -> 1, 1, 3
        for col in [
            "candidate_count",
            "invalid_count",
            "uncertain_count",
            "not_confirmed_valid_count",
        ]:

            x[
                f"{col}_rank_within_stratum"
            ] = (
                x[col]
                .rank(
                    method="min",
                    ascending=False,
                )
                .astype(int)
            )

        # Gap contribution identity.
        contribution_sum = x[
            "confirmed_valid_micro_macro_gap_contribution_within_stratum"
        ].sum()

        expected_gap = (
            full_micro
            - full_macro
        )

        if (
            abs(
                contribution_sum
                - expected_gap
            )
            > 1e-12
        ):
            raise RuntimeError(
                "micro-macro contribution "
                f"identity failed for {stratum}: "
                f"{contribution_sum} "
                f"vs {expected_gap}"
            )

        work_parts.append(x)

    by_work = pd.concat(
        work_parts,
        ignore_index=True,
    )

    by_work["_stratum_order"] = (
        by_work[
            "increment_type"
        ].map(
            STRATUM_ORDER
        )
    )

    by_work = (
        by_work.sort_values(
            [
                "_stratum_order",
                "project_work_id",
            ],
            kind="stable",
        )
        .drop(
            columns=[
                "_stratum_order"
            ]
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Frozen aggregate checks
    # --------------------------------------------------------

    aggregate_checks = {}

    for stratum in [
        "A2_AUTHOR_REVERSAL",
        "ALIAS_EXPANSION",
    ]:

        x = by_work[
            by_work[
                "increment_type"
            ].eq(stratum)
        ]

        n = int(
            x["candidate_count"].sum()
        )

        v = int(
            x["valid_count"].sum()
        )

        i = int(
            x["invalid_count"].sum()
        )

        u = int(
            x["uncertain_count"].sum()
        )

        micro = (
            v / n
        )

        macro = (
            x[
                "confirmed_valid_rate_within_work"
            ].mean()
        )

        exp = EXPECTED_STRATUM_COUNTS[stratum]

        if n != exp["candidate_count"]:
            raise RuntimeError(
                f"{stratum} N mismatch"
            )

        if v != exp["valid_count"]:
            raise RuntimeError(
                f"{stratum} VALID mismatch"
            )

        if i != exp["invalid_count"]:
            raise RuntimeError(
                f"{stratum} INVALID mismatch"
            )

        if u != exp["uncertain_count"]:
            raise RuntimeError(
                f"{stratum} UNCERTAIN mismatch"
            )

        frozen_rows = frozen_precision_summary[
            frozen_precision_summary[
                "stratum"
            ].eq(stratum)
        ]

        if len(frozen_rows) != 1:
            raise RuntimeError(
                f"{stratum} missing/duplicate in "
                "frozen precision summary"
            )

        frozen_row = frozen_rows.iloc[0]

        for col, actual in [
            ("candidate_count", n),
            ("valid_count", v),
            ("invalid_count", i),
            ("uncertain_count", u),
        ]:
            if int(frozen_row[col]) != actual:
                raise RuntimeError(
                    f"{stratum} frozen summary "
                    f"{col} mismatch"
                )

        if abs(
            micro
            - float(
                frozen_row[
                    "micro_confirmed_valid"
                ]
            )
        ) > 1e-12:
            raise RuntimeError(
                f"{stratum} frozen micro mismatch"
            )

        if abs(
            macro
            - float(
                frozen_row[
                    "macro_w_confirmed_valid"
                ]
            )
        ) > 1e-12:
            raise RuntimeError(
                f"{stratum} frozen macro mismatch"
            )

        contribution_sum = float(
            x[
                "confirmed_valid_micro_macro_gap_contribution_within_stratum"
            ].sum()
        )

        aggregate_checks[
            stratum
        ] = {
            "candidate_count": n,
            "valid_count": v,
            "invalid_count": i,
            "uncertain_count": u,
            "micro_confirmed_valid": micro,
            "macro_w_confirmed_valid": macro,
            "micro_minus_macro_confirmed_valid":
                micro - macro,
            "confirmed_valid_gap_contribution_sum":
                contribution_sum,
        }

    if len(by_work) != 65:
        raise RuntimeError(
            "final by-work rows != 65"
        )

    # --------------------------------------------------------
    # Direct comparison with frozen precision-results v1
    # by-work artifact.
    # --------------------------------------------------------

    frozen_bw = frozen_precision_by_work[
        frozen_precision_by_work[
            "stratum"
        ].isin(
            [
                "A2_AUTHOR_REVERSAL",
                "ALIAS_EXPANSION",
            ]
        )
    ][
        [
            "stratum",
            "project_work_id",
            "candidate_count",
            "valid_count",
            "invalid_count",
            "uncertain_count",
            "confirmed_valid",
        ]
    ].rename(
        columns={
            "stratum": "increment_type",
            "confirmed_valid":
                "frozen_confirmed_valid",
        }
    )

    compare_bw = frozen_bw.merge(
        by_work[
            [
                "increment_type",
                "project_work_id",
                "candidate_count",
                "valid_count",
                "invalid_count",
                "uncertain_count",
                "confirmed_valid_rate_within_work",
            ]
        ],
        on=[
            "increment_type",
            "project_work_id",
        ],
        how="outer",
        validate="one_to_one",
        indicator=True,
    )

    if len(compare_bw) != EXPECTED_WORK_ROWS:
        raise RuntimeError(
            "Frozen/new by-work row count mismatch"
        )

    if not (
        compare_bw["_merge"] == "both"
    ).all():
        raise RuntimeError(
            "Frozen/new by-work identity mismatch"
        )

    for col in [
        "candidate_count",
        "valid_count",
        "invalid_count",
        "uncertain_count",
    ]:
        if not (
            compare_bw[f"{col}_x"].to_numpy()
            == compare_bw[f"{col}_y"].to_numpy()
        ).all():
            raise RuntimeError(
                f"Frozen/new by-work {col} mismatch"
            )

    max_rate_diff = (
        compare_bw[
            "frozen_confirmed_valid"
        ]
        - compare_bw[
            "confirmed_valid_rate_within_work"
        ]
    ).abs().max()

    if max_rate_diff > 1e-12:
        raise RuntimeError(
            "Frozen/new by-work confirmed-valid "
            f"mismatch: {max_rate_diff}"
        )

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_atomic_tsv(
        diag,
        OUT_CAND_TSV,
    )

    write_atomic_parquet(
        diag,
        OUT_CAND_PARQUET,
    )

    write_atomic_tsv(
        by_work,
        OUT_WORK_TSV,
    )

    write_atomic_parquet(
        by_work,
        OUT_WORK_PARQUET,
    )

    audit = {
        "release": RELEASE,
        "version": VERSION,
        "profile": PROFILE,
        "created_at": CREATED_AT,

        "scope": (
            "Descriptive analysis of the frozen "
            "661-candidate audited marginal "
            "retrieval universe only."
        ),

        "candidate_rows": len(diag),
        "unique_review_candidate_ids":
            int(
                diag[
                    "review_candidate_id"
                ].nunique()
            ),

        "by_work_rows": len(by_work),

        "judgment_counts": (
            diag[
                "posthoc_human_target_attribution_judgment"
            ]
            .value_counts()
            .sort_index()
            .to_dict()
        ),

        "aggregate_checks":
            aggregate_checks,

        "invariants": {
            "uncertain_is_not_invalid":
                True,

            "not_confirmed_valid_definition":
                "INVALID + UNCERTAIN",

            "candidate_row_multiplication":
                False,

            "frozen_precision_results_v1_comparison":
                "PASSED",

            "query_id_semantics":
                (
                    "Release-local provenance only; "
                    "query IDs are not emitted as "
                    "persistent cross-release identity."
                ),

            "loo_sign":
                (
                    "full_micro_confirmed_valid - "
                    "leave_one_out_micro_confirmed_valid; "
                    "positive means the work raises "
                    "the full micro estimate."
                ),

            "rank_method":
                (
                    "competition ranking, pandas "
                    "method=min; ties share rank and "
                    "subsequent ranks are skipped."
                ),

            "gap_contribution_metric":
                (
                    "confirmed-valid metric only"
                ),

            "human_reason_codes":
                (
                    "post-hoc explanatory outcomes; "
                    "not production-policy inputs"
                ),
        },
    }

    write_atomic_json(
        audit,
        OUT_AUDIT,
    )

    output_hashes = {
        str(
            path.relative_to(ROOT)
        ): sha256_file(path)

        for path in [
            OUT_CAND_TSV,
            OUT_CAND_PARQUET,
            OUT_WORK_TSV,
            OUT_WORK_PARQUET,
            OUT_AUDIT,
        ]
    }

    manifest = {
        "release": RELEASE,
        "version": VERSION,
        "profile": PROFILE,
        "created_at": CREATED_AT,

        "purpose": (
            "Freeze reproducible candidate-level "
            "diagnostics and by-work descriptive "
            "error/ambiguity analysis for the "
            "audited OpenAlex marginal retrieval "
            "universe."
        ),

        "inputs": {
            str(
                CAND.relative_to(ROOT)
            ): sha256_file(CAND),

            str(
                ADJ.relative_to(ROOT)
            ): sha256_file(ADJ),

            str(
                ALIASES.relative_to(ROOT)
            ): sha256_file(ALIASES),

            str(
                FROZEN_PRECISION_SUMMARY.relative_to(ROOT)
            ): sha256_file(
                FROZEN_PRECISION_SUMMARY
            ),

            str(
                FROZEN_PRECISION_BY_WORK.relative_to(ROOT)
            ): sha256_file(
                FROZEN_PRECISION_BY_WORK
            ),
        },

        "outputs":
            output_hashes,

        "row_counts": {
            "candidate_diagnostics":
                len(diag),
            "by_work":
                len(by_work),
        },

        "semantics": {
            "candidate_primary_provenance":
                (
                    "Frozen "
                    "retrieval_precision_review_candidates_v3"
                ),

            "supplementary_registry_use":
                (
                    "Alias registry v4 is used only "
                    "for features absent from the "
                    "candidate artifact, principally "
                    "cross-project-work normalized "
                    "title collision."
                ),

            "multi_evidence_aggregation":
                (
                    "No arbitrary representative "
                    "query/alias/evidence row is "
                    "selected. Counts, sorted unique "
                    "sets, min/max and any-style "
                    "aggregations are deterministic."
                ),

            "alias_expansion_mechanism":
                (
                    "Exploratory/deployable comparison "
                    "feature derived with NFKC + "
                    "casefold + whitespace collapse. "
                    "This does not redefine frozen "
                    "retrieval normalization."
                ),

            "uncertain":
                (
                    "UNCERTAIN remains distinct from "
                    "INVALID throughout."
                ),

            "not_confirmed_valid":
                (
                    "Convenience aggregate equal to "
                    "INVALID + UNCERTAIN; not an error "
                    "or false-positive label."
                ),

            "scope":
                (
                    "Descriptive of the frozen audited "
                    "65-work / 661-candidate universe; "
                    "no inferential or significance "
                    "claim about the wider literary "
                    "work population."
                ),
        },

        "next_step":
            (
                "Use the frozen diagnostic release "
                "to formulate production retrieval "
                "policy without using post-hoc human "
                "reason codes as production inputs."
            ),
    }

    write_atomic_json(
        manifest,
        OUT_MANIFEST,
    )

    print("=== RELEASE BUILT ===")
    print("release:", RELEASE)
    print("profile:", PROFILE)
    print(
        "candidate rows:",
        len(diag),
    )
    print(
        "by-work rows:",
        len(by_work),
    )

    print("\n=== AGGREGATE CHECKS ===")

    for (
        stratum,
        values
    ) in aggregate_checks.items():
        print(
            stratum,
            values,
        )

    print("\n=== OUTPUTS ===")

    for path in [
        OUT_CAND_TSV,
        OUT_CAND_PARQUET,
        OUT_WORK_TSV,
        OUT_WORK_PARQUET,
        OUT_AUDIT,
        OUT_MANIFEST,
    ]:
        print(
            path.relative_to(ROOT)
        )


if __name__ == "__main__":
    main()
