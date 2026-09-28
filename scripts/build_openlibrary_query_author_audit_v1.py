#!/usr/bin/env python3

"""
Audit the frozen Open Library author source layer before selecting an
OpenAlex query-author rule.

This script does NOT choose the production query author.

It summarizes:
- no-author / single-author / multi-author source patterns;
- ordinal-0 evidence;
- missing Author records;
- normalized duplicate names across distinct Author IDs;
- heuristic organization-like names;
- metadata signals useful for manual review.

Heuristic flags are audit aids only and must not be treated as source truth.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import unicodedata

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

SOURCE_DIR = ROOT / "derived/openlibrary_author_source_v1"

WORK_RECORDS = (
    SOURCE_DIR / "openlibrary_current_work_records_v1.parquet"
)

WORK_AUTHORS = (
    SOURCE_DIR / "openlibrary_current_work_authors_v1.parquet"
)

AUTHOR_RECORDS = (
    SOURCE_DIR / "openlibrary_author_records_v1.parquet"
)

SOURCE_MANIFEST = (
    SOURCE_DIR / "openlibrary_author_source_v1_manifest.json"
)

OUT_DIR = ROOT / "derived/openlibrary_query_author_audit_v1"

RELEASE = "openlibrary-query-author-audit-v1"
CREATED_AT = "2026-09-28"
RANDOM_SEED = 20260928


ORG_PATTERN = re.compile(
    r"\b("
    r"press|publishing|publishers?|books?|library|libraries|"
    r"university|college|society|association|foundation|"
    r"company|corporation|corp|inc|ltd|limited|"
    r"project\s+gutenberg|studio|studios|media|productions?|"
    r"audio|edition|editions"
    r")\b",
    re.IGNORECASE,
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)

    return h.hexdigest()


def normalize_name(value: str) -> str:
    value = unicodedata.normalize(
        "NFKC",
        str(value or ""),
    ).casefold()

    chars = []

    for ch in value:
        category = unicodedata.category(ch)

        if category.startswith(("P", "S")):
            chars.append(" ")
        else:
            chars.append(ch)

    return " ".join(
        "".join(chars).split()
    )


def is_org_like_name(value: str) -> bool:
    value = str(value or "").strip()

    if not value:
        return False

    return bool(
        ORG_PATTERN.search(value)
    )


def json_object_size(value: str) -> int:
    try:
        obj = json.loads(value or "{}")
    except Exception:
        return 0

    if isinstance(obj, dict):
        return len(obj)

    return 0


def write_tsv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(
        path,
        sep="\t",
        index=False,
        lineterminator="\n",
    )


def main() -> None:
    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    source_manifest = json.loads(
        SOURCE_MANIFEST.read_text(
            encoding="utf-8"
        )
    )

    if (
        source_manifest.get("release")
        != "openlibrary-author-source-v1"
    ):
        raise RuntimeError(
            "Unexpected source release"
        )

    expected = {
        WORK_RECORDS:
            source_manifest["outputs"]
            ["work_records_parquet"]
            ["sha256"],
        WORK_AUTHORS:
            source_manifest["outputs"]
            ["work_authors_parquet"]
            ["sha256"],
        AUTHOR_RECORDS:
            source_manifest["outputs"]
            ["author_records_parquet"]
            ["sha256"],
    }

    print("=== VERIFYING FROZEN INPUTS ===")

    input_hashes = {}

    for path, expected_sha in expected.items():
        actual = sha256_file(path)

        print(path.name, actual)

        if actual != expected_sha:
            raise RuntimeError(
                f"SHA256 mismatch: {path}"
            )

        input_hashes[
            str(path.relative_to(ROOT))
        ] = actual

    works = pd.read_parquet(
        WORK_RECORDS
    )

    edges = pd.read_parquet(
        WORK_AUTHORS
    )

    authors = pd.read_parquet(
        AUTHOR_RECORDS
    )

    author_meta = authors[
        [
            "author_source_key",
            "name",
            "personal_name",
            "fuller_name",
            "birth_date",
            "death_date",
            "remote_ids_json",
        ]
    ].copy()

    author_meta = author_meta.rename(
        columns={
            "name": "author_name",
            "personal_name":
                "author_personal_name",
            "fuller_name":
                "author_fuller_name",
            "birth_date":
                "author_birth_date",
            "death_date":
                "author_death_date",
            "remote_ids_json":
                "author_remote_ids_json",
        }
    )

    edges = edges.merge(
        author_meta,
        on="author_source_key",
        how="left",
        validate="m:1",
    )

    edges["author_ordinal"] = (
        pd.to_numeric(
            edges["author_ordinal"],
            errors="coerce",
        )
        .astype("Int64")
    )

    for col in [
        "author_source_key",
        "author_source_id",
        "author_name",
        "author_personal_name",
        "author_fuller_name",
        "author_birth_date",
        "author_death_date",
        "author_remote_ids_json",
    ]:
        edges[col] = (
            edges[col]
            .fillna("")
            .astype(str)
        )

    edges["author_name_norm"] = (
        edges["author_name"]
        .map(normalize_name)
    )

    edges["heuristic_org_like_name"] = (
        edges["author_name"]
        .map(is_org_like_name)
    )

    edges["has_life_date"] = (
        edges["author_birth_date"].ne("")
        | edges["author_death_date"].ne("")
    )

    edges["remote_id_count"] = (
        edges["author_remote_ids_json"]
        .map(json_object_size)
    )

    edge_groups = {
        work_id: group.sort_values(
            "author_ordinal",
            kind="stable",
        )
        for work_id, group
        in edges.groupby(
            "current_ol_work_id",
            sort=False,
        )
    }

    audit_rows = []

    for work in works.to_dict("records"):
        work_id = str(
            work["current_ol_work_id"]
        )

        title = str(
            work.get("source_title", "")
            or ""
        )

        author_entry_count = int(
            work.get("author_entry_count", 0)
            or 0
        )

        group = edge_groups.get(work_id)

        if group is None:
            group = edges.iloc[0:0].copy()

        group = group.sort_values(
            "author_ordinal",
            kind="stable",
        )

        edge_count = len(group)

        keyed = group[
            group["author_source_key"].ne("")
        ]

        found = group[
            group[
                "author_record_found_in_snapshot"
            ].fillna(False)
        ]

        unresolved_record = group[
            group["author_source_key"].ne("")
            & ~group[
                "author_record_found_in_snapshot"
            ].fillna(False)
        ]

        missing_key_count = int(
            group["author_source_key"]
            .eq("")
            .sum()
        )

        ordinal0 = group[
            group["author_ordinal"].eq(0)
        ]

        first = (
            ordinal0.iloc[0]
            if len(ordinal0)
            else None
        )

        ordinal0_id = (
            str(first["author_source_id"])
            if first is not None
            else ""
        )

        ordinal0_name = (
            str(first["author_name"])
            if first is not None
            else ""
        )

        ordinal0_found = bool(
            first[
                "author_record_found_in_snapshot"
            ]
        ) if first is not None else False

        ordinal0_org_like = bool(
            first["heuristic_org_like_name"]
        ) if first is not None else False

        ordinal0_has_life_date = bool(
            first["has_life_date"]
        ) if first is not None else False

        ordinal0_remote_id_count = int(
            first["remote_id_count"]
        ) if first is not None else 0

        normalized_names = [
            x
            for x in group[
                "author_name_norm"
            ].tolist()
            if x
        ]

        norm_counts = Counter(
            normalized_names
        )

        duplicate_norms = sorted(
            name
            for name, count
            in norm_counts.items()
            if count > 1
        )

        author_ids = []

        author_names = []

        for row in group.to_dict("records"):
            aid = str(
                row.get(
                    "author_source_id",
                    "",
                )
                or ""
            )

            name = str(
                row.get(
                    "author_name",
                    "",
                )
                or ""
            )

            ordinal = row.get(
                "author_ordinal"
            )

            author_ids.append(
                f"{ordinal}:{aid or '<no-key>'}"
            )

            if name:
                label = name
            elif aid:
                label = f"<missing:{aid}>"
            else:
                label = "<no-author-key>"

            author_names.append(
                f"{ordinal}:{label}"
            )

        if author_entry_count == 0:
            complexity = "NO_AUTHOR_ENTRY"

        elif author_entry_count == 1:
            if (
                ordinal0_found
                and bool(ordinal0_name)
            ):
                complexity = (
                    "SINGLE_RESOLVED"
                )
            else:
                complexity = (
                    "SINGLE_UNRESOLVED"
                )

        else:
            complexity = "MULTI"

        reasons = []

        if complexity == "MULTI":
            if first is None:
                reasons.append(
                    "NO_ORDINAL_0_EDGE"
                )
            else:
                if not str(
                    first["author_source_key"]
                ):
                    reasons.append(
                        "ORDINAL_0_NO_AUTHOR_KEY"
                    )

                elif not ordinal0_found:
                    reasons.append(
                        "ORDINAL_0_RECORD_MISSING"
                    )

                if (
                    ordinal0_found
                    and not ordinal0_name
                ):
                    reasons.append(
                        "ORDINAL_0_NAME_MISSING"
                    )

                if ordinal0_org_like:
                    reasons.append(
                        "ORDINAL_0_ORG_LIKE"
                    )

            if len(unresolved_record):
                reasons.append(
                    "ANY_AUTHOR_RECORD_MISSING"
                )

            if missing_key_count:
                reasons.append(
                    "ANY_EDGE_WITHOUT_AUTHOR_KEY"
                )

            if duplicate_norms:
                reasons.append(
                    "DUPLICATE_NORMALIZED_NAME"
                )

            if author_entry_count >= 5:
                reasons.append(
                    "AUTHOR_COUNT_GE_5"
                )

            if (
                group[
                    "heuristic_org_like_name"
                ].sum()
                > int(ordinal0_org_like)
            ):
                reasons.append(
                    "LATER_ORG_LIKE_NAME"
                )

        if complexity != "MULTI":
            review_bucket = complexity

        elif any(
            reason in reasons
            for reason in [
                "NO_ORDINAL_0_EDGE",
                "ORDINAL_0_NO_AUTHOR_KEY",
                "ORDINAL_0_RECORD_MISSING",
                "ORDINAL_0_NAME_MISSING",
                "ORDINAL_0_ORG_LIKE",
            ]
        ):
            review_bucket = "MULTI_HIGH"

        elif any(
            reason in reasons
            for reason in [
                "ANY_AUTHOR_RECORD_MISSING",
                "ANY_EDGE_WITHOUT_AUTHOR_KEY",
                "DUPLICATE_NORMALIZED_NAME",
                "AUTHOR_COUNT_GE_5",
            ]
        ):
            review_bucket = "MULTI_MEDIUM"

        elif (
            author_entry_count >= 3
            or "LATER_ORG_LIKE_NAME"
            in reasons
        ):
            review_bucket = "MULTI_LOW"

        else:
            review_bucket = (
                "MULTI_BASELINE"
            )

        audit_rows.append({
            "current_entity_id":
                work["current_entity_id"],
            "current_ol_work_id":
                work_id,
            "source_title":
                title,
            "author_entry_count":
                author_entry_count,
            "edge_count":
                edge_count,
            "keyed_author_count":
                len(keyed),
            "resolved_author_count":
                len(found),
            "missing_author_record_count":
                len(unresolved_record),
            "edge_without_author_key_count":
                missing_key_count,
            "selection_complexity":
                complexity,
            "review_bucket":
                review_bucket,
            "review_reasons":
                ";".join(reasons),
            "ordinal0_author_id":
                ordinal0_id,
            "ordinal0_name":
                ordinal0_name,
            "ordinal0_record_found":
                ordinal0_found,
            "ordinal0_org_like_heuristic":
                ordinal0_org_like,
            "ordinal0_has_life_date":
                ordinal0_has_life_date,
            "ordinal0_remote_id_count":
                ordinal0_remote_id_count,
            "life_dated_author_count":
                int(
                    group[
                        "has_life_date"
                    ].sum()
                ),
            "org_like_author_count_heuristic":
                int(
                    group[
                        "heuristic_org_like_name"
                    ].sum()
                ),
            "duplicate_normalized_name":
                bool(duplicate_norms),
            "duplicate_normalized_names":
                " | ".join(
                    duplicate_norms
                ),
            "all_author_ids":
                " | ".join(author_ids),
            "all_author_names":
                " | ".join(author_names),
        })

    audit = pd.DataFrame(
        audit_rows
    )

    if len(audit) != 34789:
        raise RuntimeError(
            f"Expected 34789 audit rows; "
            f"found {len(audit)}"
        )

    multi = (
        audit[
            audit[
                "selection_complexity"
            ].eq("MULTI")
        ]
        .copy()
        .sort_values(
            [
                "review_bucket",
                "author_entry_count",
                "source_title",
                "current_ol_work_id",
            ],
            ascending=[
                True,
                False,
                True,
                True,
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    # -----------------------------------------------------
    # Summary tables
    # -----------------------------------------------------

    author_count_distribution = (
        audit.groupby(
            "author_entry_count",
            dropna=False,
        )
        .size()
        .rename("work_count")
        .reset_index()
        .sort_values(
            "author_entry_count"
        )
    )

    complexity_summary = (
        audit.groupby(
            "selection_complexity",
            dropna=False,
        )
        .size()
        .rename("work_count")
        .reset_index()
        .sort_values(
            "work_count",
            ascending=False,
        )
    )

    review_bucket_summary = (
        multi.groupby(
            "review_bucket",
            dropna=False,
        )
        .size()
        .rename("work_count")
        .reset_index()
        .sort_values(
            "work_count",
            ascending=False,
        )
    )

    # Deterministic manual-review sample:
    # up to 40 from each multi bucket.
    sample_parts = []

    for bucket in [
        "MULTI_HIGH",
        "MULTI_MEDIUM",
        "MULTI_LOW",
        "MULTI_BASELINE",
    ]:
        subset = multi[
            multi["review_bucket"].eq(
                bucket
            )
        ]

        if len(subset) == 0:
            continue

        sample_parts.append(
            subset.sample(
                n=min(40, len(subset)),
                random_state=RANDOM_SEED,
            )
        )

    review_sample = (
        pd.concat(
            sample_parts,
            ignore_index=True,
        )
        if sample_parts
        else multi.iloc[0:0].copy()
    )

    review_sample = (
        review_sample
        .sort_values(
            [
                "review_bucket",
                "author_entry_count",
                "source_title",
            ],
            ascending=[
                True,
                False,
                True,
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    outputs = {
        "all_work_status":
            OUT_DIR
            / "openlibrary_query_author_status_v1.tsv",
        "multi_author_audit":
            OUT_DIR
            / "openlibrary_multi_author_audit_v1.tsv",
        "author_count_distribution":
            OUT_DIR
            / "author_count_distribution_v1.tsv",
        "complexity_summary":
            OUT_DIR
            / "selection_complexity_summary_v1.tsv",
        "review_bucket_summary":
            OUT_DIR
            / "multi_review_bucket_summary_v1.tsv",
        "review_sample":
            OUT_DIR
            / "multi_author_manual_review_sample_v1.tsv",
    }

    write_tsv(
        audit,
        outputs["all_work_status"],
    )

    write_tsv(
        multi,
        outputs["multi_author_audit"],
    )

    write_tsv(
        author_count_distribution,
        outputs[
            "author_count_distribution"
        ],
    )

    write_tsv(
        complexity_summary,
        outputs["complexity_summary"],
    )

    write_tsv(
        review_bucket_summary,
        outputs[
            "review_bucket_summary"
        ],
    )

    write_tsv(
        review_sample,
        outputs["review_sample"],
    )

    counts = {
        "current_targets":
            len(audit),
        "no_author_entry":
            int(
                (
                    audit[
                        "selection_complexity"
                    ]
                    == "NO_AUTHOR_ENTRY"
                ).sum()
            ),
        "single_resolved":
            int(
                (
                    audit[
                        "selection_complexity"
                    ]
                    == "SINGLE_RESOLVED"
                ).sum()
            ),
        "single_unresolved":
            int(
                (
                    audit[
                        "selection_complexity"
                    ]
                    == "SINGLE_UNRESOLVED"
                ).sum()
            ),
        "multi":
            len(multi),
        "multi_ordinal0_record_missing":
            int(
                (
                    multi[
                        "review_reasons"
                    ]
                    .str.contains(
                        "ORDINAL_0_RECORD_MISSING",
                        regex=False,
                    )
                ).sum()
            ),
        "multi_ordinal0_org_like_heuristic":
            int(
                multi[
                    "ordinal0_org_like_heuristic"
                ].sum()
            ),
        "multi_duplicate_normalized_name":
            int(
                multi[
                    "duplicate_normalized_name"
                ].sum()
            ),
        "multi_with_any_missing_author_record":
            int(
                (
                    multi[
                        "missing_author_record_count"
                    ]
                    > 0
                ).sum()
            ),
        "multi_author_count_ge_5":
            int(
                (
                    multi[
                        "author_entry_count"
                    ]
                    >= 5
                ).sum()
            ),
        "maximum_author_entry_count":
            int(
                audit[
                    "author_entry_count"
                ].max()
            ),
        "manual_review_sample_rows":
            len(review_sample),
    }

    manifest = {
        "release": RELEASE,
        "created_at": CREATED_AT,
        "purpose": (
            "Audit the frozen Open Library "
            "author source layer before "
            "freezing query_author_selection_rule v1."
        ),
        "important_note": (
            "Organization-like and other risk "
            "flags are heuristic review aids "
            "only and are not source truth."
        ),
        "source_release":
            source_manifest["release"],
        "source_manifest":
            str(
                SOURCE_MANIFEST.relative_to(
                    ROOT
                )
            ),
        "input_sha256":
            input_hashes,
        "counts":
            counts,
        "outputs": {},
    }

    for key, path in outputs.items():
        manifest["outputs"][key] = {
            "artifact":
                str(path.relative_to(ROOT)),
            "sha256":
                sha256_file(path),
        }

    manifest_path = (
        OUT_DIR
        / "openlibrary_query_author_audit_v1_manifest.json"
    )

    manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print("\n=== SELECTION COMPLEXITY ===")
    print(
        complexity_summary.to_string(
            index=False
        )
    )

    print("\n=== MULTI REVIEW BUCKETS ===")
    print(
        review_bucket_summary.to_string(
            index=False
        )
    )

    print("\n=== KEY COUNTS ===")

    for key, value in counts.items():
        print(f"{key}: {value}")

    print("\n=== AUTHOR COUNT DISTRIBUTION ===")
    print(
        author_count_distribution
        .head(15)
        .to_string(index=False)
    )

    print("\noutputs:")
    for path in outputs.values():
        print(path.relative_to(ROOT))

    print(manifest_path.relative_to(ROOT))


if __name__ == "__main__":
    main()
