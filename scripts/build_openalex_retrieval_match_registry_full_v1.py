from pathlib import Path
import hashlib
import json
import os
import re
import unicodedata

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

REGISTRY_DIR = (
    ROOT
    / "derived/openalex_production"
    / "registry_v4"
)

CALIBRATION_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_match_registry_v2"
)

OUT_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_match_registry_full_v1"
)

QUERIES = (
    REGISTRY_DIR
    / "openalex_queries_v4.parquet"
)

QUERY_MANIFEST = (
    REGISTRY_DIR
    / "openalex_query_registry_v4_manifest.json"
)

EXEC_MAP = (
    REGISTRY_DIR
    / "openalex_query_execution_map_v4.parquet"
)

EXEC_MANIFEST = (
    REGISTRY_DIR
    / "openalex_execution_registry_v4_manifest.json"
)

CALIBRATION_MATCH = (
    CALIBRATION_DIR
    / "openalex_retrieval_match_registry_v2.parquet"
)

CALIBRATION_MANIFEST = (
    CALIBRATION_DIR
    / "openalex_retrieval_match_registry_v2_manifest.json"
)

OUT_TSV = (
    OUT_DIR
    / "openalex_retrieval_match_registry_full_v1.tsv"
)

OUT_PARQUET = (
    OUT_DIR
    / "openalex_retrieval_match_registry_full_v1.parquet"
)

OUT_AUDIT = (
    OUT_DIR
    / "openalex_retrieval_match_registry_full_v1_audit_v1.json"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openalex_retrieval_match_registry_full_v1_manifest.json"
)

RELEASE = "openalex-retrieval-match-registry-full-v1"
VERSION = "v1"
CREATED_AT = "2026-10-06"

EXPECTED_QUERIES = 101706
EXPECTED_TITLE_AUTHOR = 66917
EXPECTED_TITLE_ONLY = 34789
EXPECTED_R2 = 32489
EXPECTED_R3 = 34428
EXPECTED_R4 = 34789
EXPECTED_EXECUTIONS = 63624
EXPECTED_CALIBRATION_ROWS = 10998


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


def write_atomic_tsv(df, path):
    tmp = path.with_name(path.name + ".tmp")

    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )

    os.replace(tmp, path)


def write_atomic_parquet(df, path):
    tmp = path.with_name(path.name + ".tmp")

    df.to_parquet(
        tmp,
        index=False,
        engine="pyarrow",
    )

    os.replace(tmp, path)


def write_atomic_json(value, path):
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
# Matching normalization.
#
# This MUST remain semantically identical to
# retrieval_match_registry_v2.
#
# It is deliberately distinct from
# openalex_execution_query_norm_v1.
# ------------------------------------------------------------

def match_tokens(value: str) -> str:
    s = unicodedata.normalize(
        "NFKC",
        str(value or ""),
    ).casefold()

    chars = []

    for ch in s:
        cat = unicodedata.category(ch)

        if ch.isalnum() or cat.startswith("M"):
            chars.append(ch)
        else:
            chars.append(" ")

    return " ".join(
        "".join(chars).split()
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

    left_tokens = match_tokens(left).split()
    right_tokens = match_tokens(right).split()

    if not left_tokens or not right_tokens:
        return "EMPTY_SIDE"

    if (
        len(right_tokens) <= 2
        and all(
            token in SUFFIXES
            for token in right_tokens
        )
    ):
        return "SUFFIX_COMMA"

    if (
        any(
            token in COMPLEX_MARKERS
            for token in right_tokens
        )
        or re.search(r"\d", right)
        or "&" in right
    ):
        return "COMPLEX_COMMA"

    return "SIMPLE_SURNAME_FIRST_CANDIDATE"


def author_a1(raw: str) -> str:
    return match_tokens(raw)


def author_a2_reverse(raw: str) -> str:
    raw = str(raw or "").strip()

    if (
        comma_structure(raw)
        != "SIMPLE_SURNAME_FIRST_CANDIDATE"
    ):
        return ""

    left, right = [
        x.strip()
        for x in raw.split(",", 1)
    ]

    a1 = author_a1(raw)

    reverse = match_tokens(
        f"{right} {left}"
    )

    if not reverse or reverse == a1:
        return ""

    return reverse


def author_a3_anchor(raw: str):
    raw = str(raw or "").strip()

    if not raw:
        return "", "EMPTY"

    structure = comma_structure(raw)

    if structure == "SIMPLE_SURNAME_FIRST_CANDIDATE":
        left = raw.split(",", 1)[0]

        return (
            match_tokens(left),
            "SIMPLE_COMMA_LEFT",
        )

    if structure == "SUFFIX_COMMA":
        left = raw.split(",", 1)[0]

        tokens = match_tokens(left).split()

        if not tokens:
            return "", "UNAVAILABLE"

        return (
            tokens[-1],
            "SUFFIX_COMMA_LAST_TOKEN_BEFORE_SUFFIX",
        )

    if structure in {
        "MULTI_COMMA",
        "COMPLEX_COMMA",
        "EMPTY_SIDE",
    }:
        return (
            "",
            "COMPLEX_COMMA_UNAVAILABLE",
        )

    tokens = match_tokens(raw).split()

    while (
        tokens
        and tokens[-1] in SUFFIXES
    ):
        tokens.pop()

    if not tokens:
        return "", "UNAVAILABLE"

    return (
        tokens[-1],
        "NO_COMMA_LAST_TOKEN",
    )


def main():

    for path in [
        QUERIES,
        QUERY_MANIFEST,
        EXEC_MAP,
        EXEC_MANIFEST,
        CALIBRATION_MATCH,
        CALIBRATION_MANIFEST,
    ]:
        require(path)

    q = pd.read_parquet(
        QUERIES
    ).fillna("")

    emap = pd.read_parquet(
        EXEC_MAP
    ).fillna("")

    calibration = pd.read_parquet(
        CALIBRATION_MATCH
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

    calibration_manifest = json.loads(
        CALIBRATION_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    # --------------------------------------------------------
    # Frozen registry invariants
    # --------------------------------------------------------

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

    if (
        calibration_manifest.get("release")
        != "openalex-retrieval-match-registry-v2"
    ):
        raise RuntimeError(
            "Unexpected calibration match release"
        )

    if len(q) != EXPECTED_QUERIES:
        raise RuntimeError(
            f"Expected {EXPECTED_QUERIES} queries; "
            f"found {len(q)}"
        )

    if not q["query_id"].is_unique:
        raise RuntimeError(
            "query_id is not unique"
        )

    form_counts = (
        q["query_form"]
        .value_counts()
        .to_dict()
    )

    if form_counts != {
        "title_author": EXPECTED_TITLE_AUTHOR,
        "title_only": EXPECTED_TITLE_ONLY,
    }:
        raise RuntimeError(
            f"Unexpected query-form counts: "
            f"{form_counts}"
        )

    route_counts = (
        q["query_route"]
        .value_counts()
        .to_dict()
    )

    if route_counts != {
        "R4": EXPECTED_R4,
        "R3": EXPECTED_R3,
        "R2": EXPECTED_R2,
    }:
        raise RuntimeError(
            f"Unexpected route counts: "
            f"{route_counts}"
        )

    # --------------------------------------------------------
    # Attach frozen execution identity.
    #
    # query_id is used only inside this frozen registry release.
    # --------------------------------------------------------

    em = emap[
        [
            "query_id",
            "execution_id",
            "normalized_query_signature",
        ]
    ].copy()

    if not em["query_id"].is_unique:
        raise RuntimeError(
            "execution map query_id is not unique"
        )

    out = q.merge(
        em,
        on="query_id",
        how="left",
        validate="one_to_one",
    )

    if out["execution_id"].eq("").any():
        raise RuntimeError(
            "Missing execution_id"
        )

    if (
        out["execution_id"].nunique()
        != EXPECTED_EXECUTIONS
    ):
        raise RuntimeError(
            "Unexpected physical execution count"
        )

    # --------------------------------------------------------
    # Title matching representation
    # --------------------------------------------------------

    out["title_match_norm"] = (
        out["query_title"]
        .map(match_tokens)
    )

    out["title_match_token_count"] = (
        out["title_match_norm"]
        .map(
            lambda x: len(x.split())
        )
        .astype(int)
    )

    out["title_match_char_count"] = (
        out["title_match_norm"]
        .str.replace(
            " ",
            "",
            regex=False,
        )
        .str.len()
        .astype(int)
    )

    if out["title_match_norm"].eq("").any():
        raise RuntimeError(
            "Empty normalized query title"
        )

    # --------------------------------------------------------
    # Author matching representations
    # --------------------------------------------------------

    out["author_comma_structure"] = ""

    out["author_a1_norm"] = ""
    out["author_a2_reverse_norm"] = ""

    out["author_a2_reverse_available"] = False

    out["author_a3_anchor"] = ""
    out["author_a3_derivation_rule"] = ""
    out["author_a3_available"] = False
    out["author_a3_token_count"] = 0
    out["author_a3_char_count"] = 0
    out["author_a3_short_le3"] = False

    mask = out["query_form"].eq(
        "title_author"
    )

    ta = out.loc[mask].copy()

    out.loc[
        mask,
        "author_comma_structure",
    ] = (
        ta["query_author"]
        .map(comma_structure)
        .values
    )

    out.loc[
        mask,
        "author_a1_norm",
    ] = (
        ta["query_author"]
        .map(author_a1)
        .values
    )

    out.loc[
        mask,
        "author_a2_reverse_norm",
    ] = (
        ta["query_author"]
        .map(author_a2_reverse)
        .values
    )

    a3_values = (
        ta["query_author"]
        .map(author_a3_anchor)
    )

    out.loc[
        mask,
        "author_a3_anchor",
    ] = [
        x[0]
        for x in a3_values
    ]

    out.loc[
        mask,
        "author_a3_derivation_rule",
    ] = [
        x[1]
        for x in a3_values
    ]

    out[
        "author_a2_reverse_available"
    ] = (
        out[
            "author_a2_reverse_norm"
        ].ne("")
    )

    out[
        "author_a3_available"
    ] = (
        out[
            "author_a3_anchor"
        ].ne("")
    )

    out[
        "author_a3_token_count"
    ] = (
        out["author_a3_anchor"]
        .map(
            lambda x:
            len(str(x).split())
            if x else 0
        )
        .astype(int)
    )

    out[
        "author_a3_char_count"
    ] = (
        out["author_a3_anchor"]
        .str.replace(
            " ",
            "",
            regex=False,
        )
        .str.len()
        .astype(int)
    )

    out[
        "author_a3_short_le3"
    ] = (
        out["author_a3_available"]
        & out["author_a3_char_count"].le(3)
    )

    if (
        out.loc[
            mask,
            "author_a1_norm",
        ]
        .eq("")
        .any()
    ):
        raise RuntimeError(
            "title_author query has empty A1"
        )

    if (
        out.loc[
            ~mask,
            [
                "author_a1_norm",
                "author_a2_reverse_norm",
                "author_a3_anchor",
            ],
        ]
        .ne("")
        .any()
        .any()
    ):
        raise RuntimeError(
            "title_only query received author evidence"
        )

    # --------------------------------------------------------
    # Matching contract metadata
    # --------------------------------------------------------

    out["matching_registry_version"] = VERSION

    out["title_matching_condition"] = (
        "T1_TOKEN_PHRASE"
    )

    out["author_a1_condition"] = (
        "SOURCE_ORDER_FULL_NAME_TOKEN_PHRASE"
    )

    out["author_a2_condition"] = (
        "A1_OR_CONSERVATIVE_SIMPLE_COMMA_REVERSAL"
    )

    out["author_a3_condition"] = (
        "EXPERIMENTAL_SURNAME_LIKE_ANCHOR"
    )

    out = (
        out.sort_values(
            "query_id",
            kind="stable",
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Calibration parity audit.
    #
    # Calibration match-registry v2 is drawn from this same
    # frozen registry-v4 release. Within-release query_id use
    # is therefore allowed here.
    # --------------------------------------------------------

    if len(calibration) != EXPECTED_CALIBRATION_ROWS:
        raise RuntimeError(
            "Unexpected calibration match row count"
        )

    if not calibration["query_id"].is_unique:
        raise RuntimeError(
            "Calibration query_id not unique"
        )

    full_index = out.set_index(
        "query_id",
        drop=False,
    )

    missing_calibration_qids = (
        set(calibration["query_id"])
        - set(full_index.index)
    )

    if missing_calibration_qids:
        raise RuntimeError(
            "Calibration query IDs missing from full registry"
        )

    parity_columns = [
        "execution_id",
        "normalized_query_signature",
        "title_match_norm",
        "title_match_token_count",
        "title_match_char_count",
        "author_comma_structure",
        "author_a1_norm",
        "author_a2_reverse_norm",
        "author_a2_reverse_available",
        "author_a3_anchor",
        "author_a3_derivation_rule",
        "author_a3_available",
        "author_a3_token_count",
        "author_a3_char_count",
        "author_a3_short_le3",
        "title_matching_condition",
        "author_a1_condition",
        "author_a2_condition",
        "author_a3_condition",
    ]

    parity_mismatches = {}

    for col in parity_columns:

        expected = (
            calibration[
                [
                    "query_id",
                    col,
                ]
            ]
            .set_index("query_id")[col]
            .sort_index()
        )

        actual = (
            full_index.loc[
                expected.index,
                col,
            ]
            .sort_index()
        )

        expected_s = expected.astype(str)
        actual_s = actual.astype(str)

        bad = (
            expected_s
            != actual_s
        )

        n_bad = int(bad.sum())

        if n_bad:
            parity_mismatches[col] = n_bad

    if parity_mismatches:
        raise RuntimeError(
            "Calibration parity mismatch: "
            f"{parity_mismatches}"
        )

    # --------------------------------------------------------
    # Diagnostics
    # --------------------------------------------------------

    ta_out = out[
        out["query_form"].eq(
            "title_author"
        )
    ]

    diagnostics = {
        "logical_queries":
            int(len(out)),

        "route_counts": {
            str(k): int(v)
            for k, v
            in out[
                "query_route"
            ].value_counts().items()
        },

        "query_forms": {
            str(k): int(v)
            for k, v
            in out[
                "query_form"
            ].value_counts().items()
        },

        "unique_execution_ids":
            int(
                out["execution_id"].nunique()
            ),

        "unique_title_match_patterns":
            int(
                out[
                    "title_match_norm"
                ].nunique()
            ),

        "title_token_count": {
            str(k): int(v)
            for k, v
            in out[
                "title_match_token_count"
            ].value_counts()
            .sort_index()
            .items()
        },

        "title_author_queries":
            int(len(ta_out)),

        "author_comma_structure": {
            str(k): int(v)
            for k, v
            in ta_out[
                "author_comma_structure"
            ].value_counts().items()
        },

        "a2_reverse_available_queries":
            int(
                ta_out[
                    "author_a2_reverse_available"
                ].sum()
            ),

        "a2_reverse_unique_patterns":
            int(
                ta_out.loc[
                    ta_out[
                        "author_a2_reverse_available"
                    ],
                    "author_a2_reverse_norm",
                ].nunique()
            ),

        "calibration_parity_rows":
            int(len(calibration)),

        "calibration_parity_status":
            "PASSED",
    }

    # --------------------------------------------------------
    # Write release
    # --------------------------------------------------------

    if OUT_DIR.exists():
        raise RuntimeError(
            f"Output directory exists: {OUT_DIR}"
        )

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=False,
    )

    write_atomic_tsv(
        out,
        OUT_TSV,
    )

    write_atomic_parquet(
        out,
        OUT_PARQUET,
    )

    audit = {
        "release": RELEASE,
        "version": VERSION,
        "created_at": CREATED_AT,

        "audit_status": "PASSED",

        "counts": diagnostics,

        "calibration_parity": {
            "source_release":
                "openalex-retrieval-match-registry-v2",

            "rows_checked":
                EXPECTED_CALIBRATION_ROWS,

            "columns_checked":
                parity_columns,

            "mismatches": {},
        },

        "invariants": {
            "query_id_scope":
                (
                    "query_id is release-local and used "
                    "only for joins within frozen "
                    "registry-v4 semantics."
                ),

            "matching_normalization":
                (
                    "NFKC + Unicode casefold; Unicode "
                    "letters/numbers/combining marks "
                    "retained; other characters become "
                    "token boundaries; whitespace "
                    "collapsed."
                ),

            "execution_normalization_separate":
                True,

            "r4_policy_status":
                (
                    "R4 is represented in this registry "
                    "but is not enabled by marginal "
                    "retrieval policy v1."
                ),
        },
    }

    write_atomic_json(
        audit,
        OUT_AUDIT,
    )

    manifest = {
        "release": RELEASE,
        "version": VERSION,
        "created_at": CREATED_AT,
        "status":
            "full_matching_registry_built",

        "purpose":
            (
                "Freeze deterministic textual matching "
                "representations for the complete "
                "OpenAlex registry-v4 logical-query "
                "universe. This release does not itself "
                "enable R4 or establish full-production "
                "precision."
            ),

        "source_releases": {
            "query_registry":
                query_manifest["release"],

            "execution_registry":
                execution_manifest["release"],

            "calibration_match_registry":
                calibration_manifest["release"],
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
                EXEC_MANIFEST.relative_to(ROOT)
            ): sha256_file(EXEC_MANIFEST),

            str(
                CALIBRATION_MATCH.relative_to(ROOT)
            ): sha256_file(CALIBRATION_MATCH),

            str(
                CALIBRATION_MANIFEST.relative_to(ROOT)
            ): sha256_file(CALIBRATION_MANIFEST),
        },

        "outputs": {
            str(
                OUT_TSV.relative_to(ROOT)
            ): sha256_file(OUT_TSV),

            str(
                OUT_PARQUET.relative_to(ROOT)
            ): sha256_file(OUT_PARQUET),

            str(
                OUT_AUDIT.relative_to(ROOT)
            ): sha256_file(OUT_AUDIT),
        },

        "counts": diagnostics,

        "matching_contract": {
            "title":
                "T1_TOKEN_PHRASE",

            "author_A1":
                "SOURCE_ORDER_FULL_NAME_TOKEN_PHRASE",

            "author_A2":
                "A1_OR_CONSERVATIVE_SIMPLE_COMMA_REVERSAL",

            "author_A3":
                "EXPERIMENTAL_SURNAME_LIKE_ANCHOR",

            "production_policy_scope":
                (
                    "Marginal retrieval policy v1 "
                    "applies only to audited R2/R3-derived "
                    "marginal routes. R4 remains disabled."
                ),
        },

        "next_step":
            (
                "Build an R2/R3-only full snapshot scanner "
                "using this matching registry, preserving "
                "the frozen calibration matching contract."
            ),
    }

    write_atomic_json(
        manifest,
        OUT_MANIFEST,
    )

    print("=== FULL MATCH REGISTRY V1 ===")
    print("rows:", len(out))
    print(
        "unique query_id:",
        out["query_id"].nunique(),
    )
    print(
        "unique execution_id:",
        out["execution_id"].nunique(),
    )

    print("\nroute counts:")
    print(
        out["query_route"]
        .value_counts()
        .to_string()
    )

    print("\nquery forms:")
    print(
        out["query_form"]
        .value_counts()
        .to_string()
    )

    print("\nA2 reverse available:")
    print(
        int(
            out[
                "author_a2_reverse_available"
            ].sum()
        )
    )

    print("\ncalibration parity: PASSED")

    print("\noutputs:")
    for p in [
        OUT_TSV,
        OUT_PARQUET,
        OUT_AUDIT,
        OUT_MANIFEST,
    ]:
        print(p.relative_to(ROOT))


if __name__ == "__main__":
    main()
