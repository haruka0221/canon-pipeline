from pathlib import Path
import hashlib
import json
import os
import re
import unicodedata

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

SAMPLE_DIR = (
    ROOT
    / "derived/openalex_production/"
      "retrieval_calibration_sample_v1"
)

REGISTRY_DIR = (
    ROOT
    / "derived/openalex_production/registry_v3"
)

OUT_DIR = (
    ROOT
    / "derived/openalex_production/"
      "retrieval_match_registry_v1"
)

QUERIES = (
    SAMPLE_DIR
    / "openalex_retrieval_calibration_queries_v1.parquet"
)

SAMPLE_MANIFEST = (
    SAMPLE_DIR
    / "openalex_retrieval_calibration_sample_v1_manifest.json"
)

EXEC_MAP = (
    REGISTRY_DIR
    / "openalex_query_execution_map_v3.parquet"
)

EXEC_MANIFEST = (
    REGISTRY_DIR
    / "openalex_execution_registry_v3_manifest.json"
)

OUT_TSV = (
    OUT_DIR
    / "openalex_retrieval_match_registry_v1.tsv"
)

OUT_PARQUET = (
    OUT_DIR
    / "openalex_retrieval_match_registry_v1.parquet"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openalex_retrieval_match_registry_v1_manifest.json"
)

RELEASE = "openalex-retrieval-match-registry-v1"
VERSION = "v1"
CREATED_AT = "2026-09-29"

EXPECTED_QUERIES = 11008
EXPECTED_TITLE_AUTHOR = 6453
EXPECTED_TITLE_ONLY = 4555


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
# Calibration textual matching normalization.
#
# This is deliberately separate from
# openalex_execution_query_norm_v1.
#
# NFKC + casefold, then punctuation/separators become token
# boundaries. Unicode letters, numbers and combining marks are
# retained.
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
    """
    Return only the incremental reversed variant.

    A2 as a retrieval condition is:
        A1 OR a2_reverse

    The reverse is generated only for conservative simple
    surname-first comma cases.
    """
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


def author_a3_anchor(raw: str) -> tuple[str, str]:
    """
    Experimental surname-like anchor.

    Returns:
        (anchor, derivation_rule)

    Complex comma forms are intentionally unavailable rather
    than guessed.
    """
    raw = str(raw or "").strip()

    if not raw:
        return "", "EMPTY"

    structure = comma_structure(raw)

    if structure == "SIMPLE_SURNAME_FIRST_CANDIDATE":
        left = raw.split(",", 1)[0]

        anchor = match_tokens(left)

        return (
            anchor,
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


def main() -> None:
    for path in [
        QUERIES,
        SAMPLE_MANIFEST,
        EXEC_MAP,
        EXEC_MANIFEST,
    ]:
        require(path)

    q = pd.read_parquet(
        QUERIES
    ).fillna("")

    emap = pd.read_parquet(
        EXEC_MAP
    ).fillna("")

    sample_manifest = json.loads(
        SAMPLE_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    execution_manifest = json.loads(
        EXEC_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    if (
        sample_manifest.get("release")
        != "openalex-retrieval-calibration-sample-v1"
    ):
        raise RuntimeError(
            "Unexpected calibration sample release"
        )

    if (
        execution_manifest.get("release")
        != "openalex-execution-registry-v3"
    ):
        raise RuntimeError(
            "Unexpected execution registry release"
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

    expected_form_counts = {
        "title_author": EXPECTED_TITLE_AUTHOR,
        "title_only": EXPECTED_TITLE_ONLY,
    }

    if form_counts != expected_form_counts:
        raise RuntimeError(
            f"Unexpected query-form counts: "
            f"{form_counts}"
        )

    # --------------------------------------------------------
    # Attach frozen execution ID.
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

    # --------------------------------------------------------
    # Title matching representation.
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
    )

    out["title_match_char_count"] = (
        out["title_match_norm"]
        .str.replace(
            " ",
            "",
            regex=False,
        )
        .str.len()
    )

    if out["title_match_norm"].eq("").any():
        raise RuntimeError(
            "Empty normalized query title"
        )

    # --------------------------------------------------------
    # Author conditions.
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
        out[
            "author_a3_anchor"
        ]
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
        out[
            "author_a3_anchor"
        ]
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
    # Calibration-condition semantics.
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

    # Deterministic output ordering.
    out = (
        out.sort_values(
            "query_id",
            kind="stable",
        )
        .reset_index(drop=True)
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
        "logical_queries": int(
            len(out)
        ),
        "query_forms": {
            str(k): int(v)
            for k, v
            in out[
                "query_form"
            ].value_counts().items()
        },
        "unique_execution_ids": int(
            out["execution_id"].nunique()
        ),
        "unique_title_match_patterns": int(
            out["title_match_norm"].nunique()
        ),
        "title_token_count": {
            "one": int(
                out[
                    "title_match_token_count"
                ].eq(1).sum()
            ),
            "two": int(
                out[
                    "title_match_token_count"
                ].eq(2).sum()
            ),
            "three_plus": int(
                out[
                    "title_match_token_count"
                ].ge(3).sum()
            ),
        },
        "title_author_queries": int(
            len(ta_out)
        ),
        "author_comma_structure": {
            str(k): int(v)
            for k, v
            in ta_out[
                "author_comma_structure"
            ].value_counts().items()
        },
        "a1_unique_patterns": int(
            ta_out[
                "author_a1_norm"
            ].nunique()
        ),
        "a2_reverse_available_queries": int(
            ta_out[
                "author_a2_reverse_available"
            ].sum()
        ),
        "a2_reverse_unique_patterns": int(
            ta_out.loc[
                ta_out[
                    "author_a2_reverse_available"
                ],
                "author_a2_reverse_norm",
            ].nunique()
        ),
        "a3_available_queries": int(
            ta_out[
                "author_a3_available"
            ].sum()
        ),
        "a3_unavailable_queries": int(
            (~ta_out[
                "author_a3_available"
            ]).sum()
        ),
        "a3_unique_anchors": int(
            ta_out.loc[
                ta_out[
                    "author_a3_available"
                ],
                "author_a3_anchor",
            ].nunique()
        ),
        "a3_short_le3_queries": int(
            ta_out[
                "author_a3_short_le3"
            ].sum()
        ),
    }

    # --------------------------------------------------------
    # Write
    # --------------------------------------------------------

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_atomic_tsv(
        out,
        OUT_TSV,
    )

    write_atomic_parquet(
        out,
        OUT_PARQUET,
    )

    manifest = {
        "release": RELEASE,
        "version": VERSION,
        "created_at": CREATED_AT,
        "status": "calibration_match_registry_built",
        "purpose": (
            "Freeze deterministic textual matching "
            "representations for the fixed OpenAlex "
            "retrieval calibration sample. These are "
            "calibration conditions and do not by "
            "themselves enable a production route."
        ),
        "source_releases": {
            "calibration_sample": (
                sample_manifest["release"]
            ),
            "execution_registry": (
                execution_manifest["release"]
            ),
        },
        "matching_contract": {
            "searchable_snapshot_fields": [
                "OpenAlex Work.display_name",
                "OpenAlex Work.abstract_inverted_index "
                "reconstructed to token order",
            ],
            "field_policy": (
                "Title and abstract matches will be "
                "recorded separately. A query may match "
                "either field."
            ),
            "title_condition": {
                "id": "T1_TOKEN_PHRASE",
                "normalization": [
                    "Unicode NFKC",
                    "Unicode casefold",
                    (
                        "retain Unicode letters, numbers, "
                        "and combining marks"
                    ),
                    (
                        "convert other characters to "
                        "token boundaries"
                    ),
                    "collapse whitespace",
                ],
                "matching": (
                    "contiguous whole-token phrase"
                ),
            },
            "author_A1": (
                "Source-order full query-author name "
                "under the same token normalization."
            ),
            "author_A2": (
                "A1 OR one conservative reversed form "
                "for SIMPLE_SURNAME_FIRST_CANDIDATE "
                "comma names."
            ),
            "author_A3": (
                "Experimental surname-like anchor. "
                "Complex comma structures remain "
                "unavailable rather than guessed. "
                "No A3 anchor is automatically accepted "
                "for production."
            ),
            "important_separation": (
                "This textual matching normalization is "
                "not openalex_execution_query_norm_v1 "
                "and does not alter query_id, execution_id, "
                "or literary-work identity."
            ),
        },
        "diagnostics": diagnostics,
        "inputs": {
            str(
                QUERIES.relative_to(ROOT)
            ): sha256_file(QUERIES),
            str(
                SAMPLE_MANIFEST.relative_to(ROOT)
            ): sha256_file(SAMPLE_MANIFEST),
            str(
                EXEC_MAP.relative_to(ROOT)
            ): sha256_file(EXEC_MAP),
            str(
                EXEC_MANIFEST.relative_to(ROOT)
            ): sha256_file(EXEC_MANIFEST),
        },
        "outputs": {},
        "next_step": (
            "smoke_test_snapshot_calibration_scanner_v1"
        ),
    }

    manifest["outputs"] = {
        "tsv": {
            "artifact": str(
                OUT_TSV.relative_to(ROOT)
            ),
            "sha256": sha256_file(
                OUT_TSV
            ),
        },
        "parquet": {
            "artifact": str(
                OUT_PARQUET.relative_to(ROOT)
            ),
            "sha256": sha256_file(
                OUT_PARQUET
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
        "MATCH REGISTRY V1 ==="
    )

    print(
        "logical queries:",
        len(out),
    )

    print(
        "unique execution IDs:",
        out["execution_id"].nunique(),
    )

    print(
        "unique title match patterns:",
        out["title_match_norm"].nunique(),
    )

    print("\nQuery forms:")
    print(
        out["query_form"]
        .value_counts()
        .to_string()
    )

    print("\nTitle token counts:")
    print(
        out[
            "title_match_token_count"
        ]
        .value_counts()
        .sort_index()
        .head(20)
        .to_string()
    )

    print("\nAuthor comma structure:")
    print(
        ta_out[
            "author_comma_structure"
        ]
        .value_counts()
        .to_string()
    )

    print(
        "\nA2 reverse available queries:",
        int(
            ta_out[
                "author_a2_reverse_available"
            ].sum()
        ),
    )

    print(
        "A2 reverse unique patterns:",
        ta_out.loc[
            ta_out[
                "author_a2_reverse_available"
            ],
            "author_a2_reverse_norm",
        ].nunique(),
    )

    print(
        "\nA3 available queries:",
        int(
            ta_out[
                "author_a3_available"
            ].sum()
        ),
    )

    print(
        "A3 unavailable queries:",
        int(
            (~ta_out[
                "author_a3_available"
            ]).sum()
        ),
    )

    print(
        "A3 unique anchors:",
        ta_out.loc[
            ta_out[
                "author_a3_available"
            ],
            "author_a3_anchor",
        ].nunique(),
    )

    print(
        "A3 short <=3 queries:",
        int(
            ta_out[
                "author_a3_short_le3"
            ].sum()
        ),
    )

    print("\nOutputs:")
    for path in [
        OUT_TSV,
        OUT_PARQUET,
        OUT_MANIFEST,
    ]:
        print(path.relative_to(ROOT))

    print(
        "\nOpenAlex retrieval match registry "
        "v1 checks passed."
    )


if __name__ == "__main__":
    main()
