from pathlib import Path
from collections import defaultdict
import hashlib
import json
import os
import re
import unicodedata

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

REGISTRY_DIR = ROOT / "derived/openalex_production/registry_v4"
OUT_DIR = (
    ROOT
    / "derived/openalex_production/"
      "retrieval_calibration_sample_v2"
)

QUERIES = REGISTRY_DIR / "openalex_queries_v4.parquet"
QUERY_MANIFEST = (
    REGISTRY_DIR / "openalex_query_registry_v4_manifest.json"
)

EXEC_MAP = (
    REGISTRY_DIR / "openalex_query_execution_map_v4.parquet"
)
EXECUTIONS = (
    REGISTRY_DIR / "openalex_query_executions_v4.parquet"
)
EXEC_MANIFEST = (
    REGISTRY_DIR / "openalex_execution_registry_v4_manifest.json"
)

OUT_TARGETS_TSV = (
    OUT_DIR / "openalex_retrieval_calibration_targets_v2.tsv"
)
OUT_TARGETS_PARQUET = (
    OUT_DIR / "openalex_retrieval_calibration_targets_v2.parquet"
)

OUT_QUERIES_TSV = (
    OUT_DIR / "openalex_retrieval_calibration_queries_v2.tsv"
)
OUT_QUERIES_PARQUET = (
    OUT_DIR / "openalex_retrieval_calibration_queries_v2.parquet"
)

OUT_MANIFEST = (
    OUT_DIR / "openalex_retrieval_calibration_sample_v2_manifest.json"
)

RELEASE = "openalex-retrieval-calibration-sample-v2"
VERSION = "v2"
CREATED_AT = "2026-10-02"

SEED = 20260929

N_BASELINE = 300
N_A2 = 150
N_ONE_TOKEN = 100
N_TWO_TOKEN = 100

EXPECTED_RESOLVED_W = 32082
EXPECTED_UNRESOLVED_UNITS = 761

EXPECTED_MULTI_ALIAS_ALL = 550
EXPECTED_R2_MISSING_ALL = 352
EXPECTED_HIGH_R4_COLLISION_ALL = 329

EXPECTED_SELECTED_RESOLVED_W = 1846
EXPECTED_SELECTED_TARGET_UNITS = 2607
EXPECTED_SELECTED_LOGICAL_QUERIES = 10998
EXPECTED_SELECTED_EXECUTIONS = 5783

EXPECTED_QUERY_ROUTES = {
    "R2": 2253,
    "R3": 4192,
    "R4": 4553,
}


SUFFIXES = {
    "jr",
    "sr",
    "ii",
    "iii",
    "iv",
    "v",
    "2d",
    "2nd",
    "3d",
    "3rd",
}

COMPLEX_MARKERS = {
    "ca",
    "b",
    "d",
    "pseud",
    "pseudonym",
    "mrs",
    "mr",
    "miss",
    "lady",
    "lord",
    "sir",
    "baron",
    "viscount",
    "captain",
    "sister",
    "frère",
    "of",
    "and",
    "son",
}


def require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def write_atomic_tsv(
    df: pd.DataFrame,
    path: Path,
) -> None:
    tmp = path.with_name(path.name + ".tmp")

    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    os.replace(tmp, path)


def write_atomic_parquet(
    df: pd.DataFrame,
    path: Path,
) -> None:
    tmp = path.with_name(path.name + ".tmp")

    df.to_parquet(
        tmp,
        index=False,
        engine="pyarrow",
    )

    os.replace(tmp, path)


def write_atomic_json(
    value: dict,
    path: Path,
) -> None:
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


# ------------------------------------------------------------
# Matching-text normalization.
#
# This is for calibration diagnostics only.
# It is NOT openalex_execution_query_norm_v1.
# ------------------------------------------------------------

def match_tokens(value: str) -> str:
    s = unicodedata.normalize(
        "NFKC",
        str(value or ""),
    ).casefold()

    out = []

    for ch in s:
        cat = unicodedata.category(ch)

        if ch.isalnum() or cat.startswith("M"):
            out.append(ch)
        else:
            out.append(" ")

    return " ".join(
        "".join(out).split()
    )


def comma_structure(raw: str) -> str:
    raw = str(raw or "").strip()

    parts = [
        p.strip()
        for p in raw.split(",")
    ]

    if len(parts) == 1:
        return "NO_COMMA"

    if len(parts) > 2:
        return "MULTI_COMMA"

    left, right = parts

    lt = match_tokens(left).split()
    rt = match_tokens(right).split()

    if not lt or not rt:
        return "EMPTY_SIDE"

    if (
        len(rt) <= 2
        and all(x in SUFFIXES for x in rt)
    ):
        return "SUFFIX_COMMA"

    if (
        any(x in COMPLEX_MARKERS for x in rt)
        or re.search(r"\d", right)
        or "&" in right
    ):
        return "COMPLEX_COMMA"

    return "SIMPLE_SURNAME_FIRST_CANDIDATE"


# ------------------------------------------------------------
# Stable sampling.
#
# Do not depend on pandas/numpy RNG implementation.
# ------------------------------------------------------------

def stable_score(
    item_id: str,
    cohort_name: str,
) -> str:
    payload = (
        f"{SEED}\x1f"
        f"{cohort_name}\x1f"
        f"{item_id}"
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def stable_pick(
    ids,
    n: int,
    cohort_name: str,
) -> set[str]:
    ids = sorted(
        set(str(x) for x in ids)
    )

    ranked = sorted(
        ids,
        key=lambda x: (
            stable_score(x, cohort_name),
            x,
        ),
    )

    return set(ranked[:min(n, len(ranked))])


def main() -> None:
    for path in [
        QUERIES,
        QUERY_MANIFEST,
        EXEC_MAP,
        EXECUTIONS,
        EXEC_MANIFEST,
    ]:
        require(path)

    q = pd.read_parquet(
        QUERIES
    ).fillna("")

    emap = pd.read_parquet(
        EXEC_MAP
    ).fillna("")

    exe = pd.read_parquet(
        EXECUTIONS
    ).fillna("")

    query_manifest = json.loads(
        QUERY_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    execution_manifest = json.loads(
        EXEC_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    if (
        query_manifest.get("release")
        != "openalex-query-registry-v4"
    ):
        raise RuntimeError(
            "Unexpected query registry release"
        )

    if (
        execution_manifest.get("release")
        != "openalex-execution-registry-v4"
    ):
        raise RuntimeError(
            "Unexpected execution registry release"
        )

    # --------------------------------------------------------
    # Resolved W feature table
    # --------------------------------------------------------

    resolved = q[
        q["target_lane"].eq("resolved_w")
    ].copy()

    all_w = sorted(
        resolved.loc[
            resolved["project_work_id"].ne(""),
            "project_work_id",
        ].unique()
    )

    if len(all_w) != EXPECTED_RESOLVED_W:
        raise RuntimeError(
            f"Expected {EXPECTED_RESOLVED_W} resolved W; "
            f"found {len(all_w)}"
        )

    w = pd.DataFrame({
        "project_work_id": all_w
    })

    # One R4 logical query per OL title alias.
    alias_count = (
        resolved.loc[
            resolved["query_route"].eq("R4")
        ]
        .groupby("project_work_id")["alias_id"]
        .nunique()
        .rename("ol_alias_count")
    )

    w = w.merge(
        alias_count,
        on="project_work_id",
        how="left",
    )

    w["ol_alias_count"] = (
        w["ol_alias_count"]
        .fillna(0)
        .astype(int)
    )

    r2_w = set(
        resolved.loc[
            resolved["query_route"].eq("R2"),
            "project_work_id",
        ]
    )

    w["has_r2"] = (
        w["project_work_id"].isin(r2_w)
    )

    # --------------------------------------------------------
    # R4 cross-W execution collision
    # --------------------------------------------------------

    r4_map = emap[
        emap["target_lane"].eq("resolved_w")
        & emap["query_route"].eq("R4")
    ][
        [
            "project_work_id",
            "execution_id",
        ]
    ].copy()

    exe_cross = (
        exe.set_index("execution_id")[
            "distinct_resolved_w_count"
        ]
        .astype(int)
    )

    r4_map["r4_cross_w_count"] = (
        r4_map["execution_id"]
        .map(exe_cross)
        .fillna(0)
        .astype(int)
    )

    max_collision = (
        r4_map
        .groupby("project_work_id")[
            "r4_cross_w_count"
        ]
        .max()
        .rename("max_r4_cross_w_count")
    )

    w = w.merge(
        max_collision,
        on="project_work_id",
        how="left",
    )

    w["max_r4_cross_w_count"] = (
        w["max_r4_cross_w_count"]
        .fillna(0)
        .astype(int)
    )

    # --------------------------------------------------------
    # R4 title token count
    # --------------------------------------------------------

    r4q = resolved[
        resolved["query_route"].eq("R4")
    ][
        [
            "project_work_id",
            "query_title",
        ]
    ].copy()

    r4q["title_token_count"] = (
        r4q["query_title"]
        .map(
            lambda x:
            len(match_tokens(x).split())
        )
    )

    min_tokens = (
        r4q
        .groupby("project_work_id")[
            "title_token_count"
        ]
        .min()
        .rename("min_r4_title_tokens")
    )

    w = w.merge(
        min_tokens,
        on="project_work_id",
        how="left",
    )

    w["min_r4_title_tokens"] = (
        w["min_r4_title_tokens"]
        .fillna(0)
        .astype(int)
    )

    # --------------------------------------------------------
    # A2-sensitive
    # --------------------------------------------------------

    ta = (
        resolved.loc[
            resolved["query_form"].eq(
                "title_author"
            ),
            [
                "project_work_id",
                "query_author",
            ],
        ]
        .drop_duplicates()
        .copy()
    )

    ta["comma_structure"] = (
        ta["query_author"]
        .map(comma_structure)
    )

    a2_w = set(
        ta.loc[
            ta["comma_structure"].eq(
                "SIMPLE_SURNAME_FIRST_CANDIDATE"
            ),
            "project_work_id",
        ]
    )

    w["a2_sensitive"] = (
        w["project_work_id"].isin(a2_w)
    )

    # --------------------------------------------------------
    # Cohorts
    # --------------------------------------------------------

    cohorts = {}

    cohorts["baseline_random"] = stable_pick(
        w["project_work_id"],
        N_BASELINE,
        "baseline_random",
    )

    cohorts["multi_alias_all"] = set(
        w.loc[
            w["ol_alias_count"].gt(1),
            "project_work_id",
        ]
    )

    cohorts["r2_missing_all"] = set(
        w.loc[
            ~w["has_r2"],
            "project_work_id",
        ]
    )

    cohorts["high_r4_collision_all"] = set(
        w.loc[
            w["max_r4_cross_w_count"].ge(4),
            "project_work_id",
        ]
    )

    cohorts["a2_sensitive_random"] = stable_pick(
        w.loc[
            w["a2_sensitive"],
            "project_work_id",
        ],
        N_A2,
        "a2_sensitive_random",
    )

    cohorts["one_token_title_random"] = stable_pick(
        w.loc[
            w["min_r4_title_tokens"].eq(1),
            "project_work_id",
        ],
        N_ONE_TOKEN,
        "one_token_title_random",
    )

    cohorts["two_token_title_random"] = stable_pick(
        w.loc[
            w["min_r4_title_tokens"].eq(2),
            "project_work_id",
        ],
        N_TWO_TOKEN,
        "two_token_title_random",
    )

    if (
        len(cohorts["multi_alias_all"])
        != EXPECTED_MULTI_ALIAS_ALL
    ):
        raise RuntimeError(
            "Unexpected multi-alias population: "
            f"{len(cohorts['multi_alias_all'])}"
        )

    if (
        len(cohorts["r2_missing_all"])
        != EXPECTED_R2_MISSING_ALL
    ):
        raise RuntimeError(
            "Unexpected R2-missing population: "
            f"{len(cohorts['r2_missing_all'])}"
        )

    if (
        len(cohorts["high_r4_collision_all"])
        != EXPECTED_HIGH_R4_COLLISION_ALL
    ):
        raise RuntimeError(
            "Unexpected high-R4-collision population: "
            f"{len(cohorts['high_r4_collision_all'])}"
        )

    # --------------------------------------------------------
    # Selection reasons
    # --------------------------------------------------------

    reasons = defaultdict(list)

    for cohort_name, ids in cohorts.items():
        for wid in ids:
            reasons[wid].append(cohort_name)

    selected_w = set(reasons)

    for cohort_name in cohorts:
        w[f"cohort_{cohort_name}"] = (
            w["project_work_id"]
            .isin(cohorts[cohort_name])
        )

    w["selected"] = (
        w["project_work_id"]
        .isin(selected_w)
    )

    w["selection_reasons"] = (
        w["project_work_id"]
        .map(
            lambda wid:
            "|".join(
                sorted(reasons.get(wid, []))
            )
        )
    )

    # --------------------------------------------------------
    # Resolved target output
    # --------------------------------------------------------

    resolved_targets = (
        w.loc[w["selected"]]
        .copy()
    )

    resolved_targets.insert(
        0,
        "calibration_target_id",
        [
            f"W:{wid}"
            for wid in resolved_targets[
                "project_work_id"
            ]
        ],
    )

    resolved_targets.insert(
        1,
        "target_lane",
        "resolved_w",
    )

    resolved_targets.insert(
        3,
        "unresolved_unit_anchor_entity_id",
        "",
    )

    # --------------------------------------------------------
    # Unresolved lane: all units
    # --------------------------------------------------------

    unresolved_q = q[
        q["target_lane"].eq(
            "unresolved_source"
        )
    ].copy()

    unresolved_units = sorted(
        unresolved_q.loc[
            unresolved_q[
                "unresolved_unit_anchor_entity_id"
            ].ne(""),
            "unresolved_unit_anchor_entity_id",
        ].unique()
    )

    if (
        len(unresolved_units)
        != EXPECTED_UNRESOLVED_UNITS
    ):
        raise RuntimeError(
            f"Expected {EXPECTED_UNRESOLVED_UNITS} "
            f"unresolved units; "
            f"found {len(unresolved_units)}"
        )

    unresolved_targets = pd.DataFrame({
        "calibration_target_id": [
            f"U:{uid}"
            for uid in unresolved_units
        ],
        "target_lane": "unresolved_source",
        "project_work_id": "",
        "unresolved_unit_anchor_entity_id": (
            unresolved_units
        ),
        "ol_alias_count": 0,
        "has_r2": False,
        "max_r4_cross_w_count": 0,
        "min_r4_title_tokens": 0,
        "a2_sensitive": False,
    })

    for cohort_name in cohorts:
        unresolved_targets[
            f"cohort_{cohort_name}"
        ] = False

    unresolved_targets[
        "cohort_unresolved_all"
    ] = True

    resolved_targets[
        "cohort_unresolved_all"
    ] = False

    unresolved_targets[
        "selected"
    ] = True

    unresolved_targets[
        "selection_reasons"
    ] = "unresolved_all"

    # Keep same columns and deterministic order.
    target_columns = [
        "calibration_target_id",
        "target_lane",
        "project_work_id",
        "unresolved_unit_anchor_entity_id",
        "ol_alias_count",
        "has_r2",
        "max_r4_cross_w_count",
        "min_r4_title_tokens",
        "a2_sensitive",
    ] + [
        f"cohort_{name}"
        for name in cohorts
    ] + [
        "cohort_unresolved_all",
        "selected",
        "selection_reasons",
    ]

    targets = pd.concat(
        [
            resolved_targets[target_columns],
            unresolved_targets[target_columns],
        ],
        ignore_index=True,
    )

    targets = targets.sort_values(
        [
            "target_lane",
            "project_work_id",
            "unresolved_unit_anchor_entity_id",
        ],
        kind="stable",
    ).reset_index(drop=True)

    if not targets[
        "calibration_target_id"
    ].is_unique:
        raise RuntimeError(
            "calibration_target_id is not unique"
        )

    # --------------------------------------------------------
    # Freeze logical-query subset
    # --------------------------------------------------------

    selected_queries = q[
        (
            q["target_lane"].eq("resolved_w")
            & q["project_work_id"].isin(
                selected_w
            )
        )
        |
        q["target_lane"].eq(
            "unresolved_source"
        )
    ].copy()

    selected_queries = (
        selected_queries
        .sort_values(
            "query_id",
            kind="stable",
        )
        .reset_index(drop=True)
    )

    if not selected_queries[
        "query_id"
    ].is_unique:
        raise RuntimeError(
            "Selected query_id is not unique"
        )

    selected_query_ids = set(
        selected_queries["query_id"]
    )

    selected_map = emap[
        emap["query_id"].isin(
            selected_query_ids
        )
    ].copy()

    if len(selected_map) != len(selected_queries):
        raise RuntimeError(
            "Query-to-execution map coverage mismatch"
        )

    unique_executions = (
        selected_map["execution_id"]
        .nunique()
    )

    # Frozen sample-v2 preflight expectations.
    if len(resolved_targets) != EXPECTED_SELECTED_RESOLVED_W:
        raise RuntimeError(
            "Unexpected selected resolved-W count: "
            f"{len(resolved_targets)}"
        )

    if len(targets) != EXPECTED_SELECTED_TARGET_UNITS:
        raise RuntimeError(
            "Unexpected selected target-unit count: "
            f"{len(targets)}"
        )

    if len(selected_queries) != EXPECTED_SELECTED_LOGICAL_QUERIES:
        raise RuntimeError(
            "Unexpected selected logical-query count: "
            f"{len(selected_queries)}"
        )

    if unique_executions != EXPECTED_SELECTED_EXECUTIONS:
        raise RuntimeError(
            "Unexpected selected execution count: "
            f"{unique_executions}"
        )

    observed_routes = (
        selected_queries["query_route"]
        .value_counts()
        .to_dict()
    )

    if observed_routes != EXPECTED_QUERY_ROUTES:
        raise RuntimeError(
            "Unexpected selected query-route counts: "
            f"{observed_routes}"
        )

    # --------------------------------------------------------
    # Diagnostics
    # --------------------------------------------------------

    resolved_selected = targets[
        targets["target_lane"].eq(
            "resolved_w"
        )
    ]

    lane_route = pd.crosstab(
        selected_queries["target_lane"],
        selected_queries["query_route"],
    )

    route_counts = (
        selected_queries["query_route"]
        .value_counts()
        .sort_index()
        .to_dict()
    )

    cohort_counts = {
        name: len(ids)
        for name, ids in cohorts.items()
    }

    # --------------------------------------------------------
    # Write
    # --------------------------------------------------------

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_atomic_tsv(
        targets,
        OUT_TARGETS_TSV,
    )

    write_atomic_parquet(
        targets,
        OUT_TARGETS_PARQUET,
    )

    write_atomic_tsv(
        selected_queries,
        OUT_QUERIES_TSV,
    )

    write_atomic_parquet(
        selected_queries,
        OUT_QUERIES_PARQUET,
    )

    manifest = {
        "release": RELEASE,
        "version": VERSION,
        "created_at": CREATED_AT,
        "status": "calibration_sample_built",
        "purpose": (
            "Freeze a reproducible target and logical-query "
            "sample for comparing OpenAlex R2/R3/R4 retrieval "
            "and author-text matching strategies."
        ),
        "sampling": {
            "seed": SEED,
            "method": (
                "stable_sha256_rank"
            ),
            "score_payload": (
                "seed + ASCII Unit Separator + "
                "cohort_name + ASCII Unit Separator + "
                "project_work_id"
            ),
            "random_cohort_sizes": {
                "baseline_random": N_BASELINE,
                "a2_sensitive_random": N_A2,
                "one_token_title_random": (
                    N_ONE_TOKEN
                ),
                "two_token_title_random": (
                    N_TWO_TOKEN
                ),
            },
            "exhaustive_cohorts": [
                "multi_alias_all",
                "r2_missing_all",
                "high_r4_collision_all",
                "unresolved_all",
            ],
        },
        "cohort_definitions": {
            "baseline_random": (
                "Stable random baseline from all "
                "32,082 resolved project W."
            ),
            "multi_alias_all": (
                "All resolved W with more than one "
                "current Open Library title alias."
            ),
            "r2_missing_all": (
                "All resolved W without an R2 "
                "title-author logical query."
            ),
            "high_r4_collision_all": (
                "All resolved W for which at least one "
                "R4 execution signature is shared by "
                "four or more resolved W."
            ),
            "a2_sensitive_random": (
                "Stable sample of resolved W having at "
                "least one title-author query whose raw "
                "Open Library query-author string is a "
                "simple surname-first comma candidate."
            ),
            "one_token_title_random": (
                "Stable sample of resolved W having at "
                "least one one-token R4 title under the "
                "calibration matching tokenizer."
            ),
            "two_token_title_random": (
                "Stable sample of resolved W having at "
                "least one two-token R4 title under the "
                "calibration matching tokenizer."
            ),
            "unresolved_all": (
                "All 761 unresolved aggregation units; "
                "kept in a separate unresolved lane and "
                "excluded from W-level visibility."
            ),
        },
        "matching_diagnostic_semantics": {
            "match_tokens": (
                "Unicode NFKC + casefold; Unicode "
                "letters/numbers/combining marks are "
                "retained and other characters become "
                "token boundaries. This is a calibration "
                "matching representation, not execution "
                "normalization."
            ),
            "a2_sensitive": (
                "Indicates availability of a conservative "
                "surname-first comma reversal candidate. "
                "It does not enable an author-matching "
                "production rule."
            ),
        },
        "counts": {
            "resolved_population_w": (
                EXPECTED_RESOLVED_W
            ),
            "unresolved_population_units": (
                EXPECTED_UNRESOLVED_UNITS
            ),
            "cohorts_before_union": (
                cohort_counts
            ),
            "selected_resolved_w": (
                len(resolved_selected)
            ),
            "selected_unresolved_units": (
                len(unresolved_targets)
            ),
            "selected_target_units_total": (
                len(targets)
            ),
            "selected_logical_queries": (
                len(selected_queries)
            ),
            "selected_query_routes": (
                route_counts
            ),
            "selected_unique_execution_ids": (
                int(unique_executions)
            ),
            "selected_lane_by_route": {
                str(lane): {
                    str(route): int(
                        lane_route.loc[
                            lane,
                            route,
                        ]
                    )
                    for route
                    in lane_route.columns
                }
                for lane in lane_route.index
            },
            "selected_resolved_feature_counts": {
                "multi_alias": int(
                    resolved_selected[
                        "ol_alias_count"
                    ].gt(1).sum()
                ),
                "r2_missing": int(
                    (~resolved_selected[
                        "has_r2"
                    ]).sum()
                ),
                "r4_collision_ge4": int(
                    resolved_selected[
                        "max_r4_cross_w_count"
                    ].ge(4).sum()
                ),
                "a2_sensitive": int(
                    resolved_selected[
                        "a2_sensitive"
                    ].sum()
                ),
                "one_token_title": int(
                    resolved_selected[
                        "min_r4_title_tokens"
                    ].eq(1).sum()
                ),
                "two_token_title": int(
                    resolved_selected[
                        "min_r4_title_tokens"
                    ].eq(2).sum()
                ),
            },
        },
        "source_releases": {
            "query_registry": (
                query_manifest["release"]
            ),
            "execution_registry": (
                execution_manifest["release"]
            ),
        },
        "inputs": {
            str(
                QUERIES.relative_to(ROOT)
            ): sha256_file(QUERIES),
            str(
                QUERY_MANIFEST.relative_to(ROOT)
            ): sha256_file(QUERY_MANIFEST),
            str(
                EXEC_MAP.relative_to(ROOT)
            ): sha256_file(EXEC_MAP),
            str(
                EXECUTIONS.relative_to(ROOT)
            ): sha256_file(EXECUTIONS),
            str(
                EXEC_MANIFEST.relative_to(ROOT)
            ): sha256_file(EXEC_MANIFEST),
        },
        "outputs": {},
        "semantics": {
            "resolved_sampling_unit": (
                "project_work_id"
            ),
            "unresolved_sampling_unit": (
                "unresolved_unit_anchor_entity_id"
            ),
            "unresolved_policy": (
                "Unresolved units are included for "
                "retrieval diagnostics but must not "
                "contribute to W-level visibility."
            ),
            "query_policy": (
                "All R2/R3/R4 logical queries belonging "
                "to selected resolved W and all unresolved "
                "units are retained. R4 remains a "
                "calibration candidate route, not a "
                "production-enabled route."
            ),
        },
        "next_step": (
            "build_openalex_retrieval_match_registry_v2"
        ),
    }

    # Output hashes require files to exist first.
    manifest["outputs"] = {
        "targets_tsv": {
            "artifact": str(
                OUT_TARGETS_TSV.relative_to(ROOT)
            ),
            "sha256": sha256_file(
                OUT_TARGETS_TSV
            ),
        },
        "targets_parquet": {
            "artifact": str(
                OUT_TARGETS_PARQUET.relative_to(ROOT)
            ),
            "sha256": sha256_file(
                OUT_TARGETS_PARQUET
            ),
        },
        "queries_tsv": {
            "artifact": str(
                OUT_QUERIES_TSV.relative_to(ROOT)
            ),
            "sha256": sha256_file(
                OUT_QUERIES_TSV
            ),
        },
        "queries_parquet": {
            "artifact": str(
                OUT_QUERIES_PARQUET.relative_to(ROOT)
            ),
            "sha256": sha256_file(
                OUT_QUERIES_PARQUET
            ),
        },
    }

    write_atomic_json(
        manifest,
        OUT_MANIFEST,
    )

    # --------------------------------------------------------
    # Report
    # --------------------------------------------------------

    print(
        "=== OPENALEX RETRIEVAL "
        "CALIBRATION SAMPLE V2 ==="
    )

    print(
        "resolved population:",
        EXPECTED_RESOLVED_W,
    )

    print(
        "unresolved units:",
        EXPECTED_UNRESOLVED_UNITS,
    )

    print("\nCohorts before union:")
    for name, ids in cohorts.items():
        print(
            f"{name:28s}",
            len(ids),
        )

    print(
        "\nselected resolved W:",
        len(resolved_selected),
    )

    print(
        "selected unresolved units:",
        len(unresolved_targets),
    )

    print(
        "selected target units total:",
        len(targets),
    )

    print(
        "selected logical queries:",
        len(selected_queries),
    )

    print(
        "selected unique execution IDs:",
        unique_executions,
    )

    print("\nLane × route:")
    print(
        lane_route.to_string()
    )

    print("\nResolved feature coverage:")
    print(
        "multi alias:",
        int(
            resolved_selected[
                "ol_alias_count"
            ].gt(1).sum()
        ),
    )
    print(
        "R2 missing:",
        int(
            (~resolved_selected[
                "has_r2"
            ]).sum()
        ),
    )
    print(
        "R4 collision >=4:",
        int(
            resolved_selected[
                "max_r4_cross_w_count"
            ].ge(4).sum()
        ),
    )
    print(
        "A2 sensitive:",
        int(
            resolved_selected[
                "a2_sensitive"
            ].sum()
        ),
    )
    print(
        "one-token title:",
        int(
            resolved_selected[
                "min_r4_title_tokens"
            ].eq(1).sum()
        ),
    )
    print(
        "two-token title:",
        int(
            resolved_selected[
                "min_r4_title_tokens"
            ].eq(2).sum()
        ),
    )

    print("\nOutputs:")
    for path in [
        OUT_TARGETS_TSV,
        OUT_TARGETS_PARQUET,
        OUT_QUERIES_TSV,
        OUT_QUERIES_PARQUET,
        OUT_MANIFEST,
    ]:
        print(path.relative_to(ROOT))

    print(
        "\nOpenAlex retrieval calibration "
        "sample v2 checks passed."
    )


if __name__ == "__main__":
    main()
