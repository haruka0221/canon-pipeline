from pathlib import Path
import csv
import hashlib
import json
import os


ROOT = Path(__file__).resolve().parents[1]

PROJECT_WORKS = (
    ROOT / "derived/identity/project_works_v4.tsv"
)

WORK_MAP = (
    ROOT / "derived/identity/work_identity_map_v4.tsv"
)

SOURCE_ENTITIES = (
    ROOT / "derived/identity/source_entities_v2.tsv"
)

OL_WORKS = (
    ROOT
    / "derived/openlibrary_author_source_v1/"
    "openlibrary_current_work_records_v1.tsv"
)

OL_WORK_AUTHORS = (
    ROOT
    / "derived/openlibrary_author_source_v1/"
    "openlibrary_current_work_authors_v1.tsv"
)

OL_AUTHORS = (
    ROOT
    / "derived/openlibrary_author_source_v1/"
    "openlibrary_author_records_v1.tsv"
)

OUT_DIR = ROOT / "derived/identity"

OUT_TSV = (
    OUT_DIR / "project_work_merge_review_v1.tsv"
)

OUT_MANIFEST = (
    OUT_DIR / "project_work_merge_review_v1_manifest.json"
)

CREATED_AT = "2026-10-01"

RELEASE = "project-work-merge-review-v1"


GROUPS = [
    {
        "review_group_id": "PWMR000001",
        "project_work_ids": [
            "W000000621",
            "W000008241",
            "W000019373",
        ],
        "expected_title": "The English novel",
        "decision": "MERGE",
        "confidence": "high",
        "rationale": (
            "Three v1 singleton project works derive from distinct "
            "Open Library Work records with the same title and the "
            "same Open Library Author ID OL113017A (George Saintsbury). "
            "No frozen Work metadata distinguishes separate conceptual "
            "works."
        ),
    },
    {
        "review_group_id": "PWMR000002",
        "project_work_ids": [
            "W000007035",
            "W000009181",
        ],
        "expected_title": "The golden horseshoe",
        "decision": "MERGE",
        "confidence": "high",
        "rationale": (
            "Two v1 singleton project works derive from distinct "
            "Open Library Work records with the same title and the "
            "same Open Library Author ID OL2123030A (Stephen Bonsal). "
            "No frozen Work metadata distinguishes separate conceptual "
            "works."
        ),
    },
    {
        "review_group_id": "PWMR000003",
        "project_work_ids": [
            "W000024476",
            "W000030357",
        ],
        "expected_title": "The short-story",
        "decision": "MERGE",
        "confidence": "high",
        "rationale": (
            "Two v1 singleton project works have the same title and "
            "author name Evelyn May Albright. Their Open Library Author "
            "records are split across OL1805052A and OL2566698A, but "
            "the names and personal_names are identical, no conflicting "
            "identity evidence is present, and only OL1805052A carries "
            "additional birth/death metadata."
        ),
    },
]


def read_tsv(path):
    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as f:
        return list(
            csv.DictReader(
                f,
                delimiter="\t",
            )
        )


def sha256_file(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def write_atomic_text(path, text):
    tmp = path.with_name(
        path.name + ".tmp"
    )

    tmp.write_text(
        text,
        encoding="utf-8",
    )

    os.replace(tmp, path)


for path in [
    PROJECT_WORKS,
    WORK_MAP,
    SOURCE_ENTITIES,
    OL_WORKS,
    OL_WORK_AUTHORS,
    OL_AUTHORS,
]:
    if not path.exists():
        raise FileNotFoundError(path)


works = read_tsv(PROJECT_WORKS)
work_map = read_tsv(WORK_MAP)
entities = read_tsv(SOURCE_ENTITIES)
ol_works = read_tsv(OL_WORKS)
ol_work_authors = read_tsv(OL_WORK_AUTHORS)
ol_authors = read_tsv(OL_AUTHORS)


works_by_id = {
    r["project_work_id"]: r
    for r in works
}

entities_by_id = {
    r["entity_id"]: r
    for r in entities
}

ol_works_by_id = {
    r["current_ol_work_id"]: r
    for r in ol_works
}

ol_authors_by_id = {
    r["author_source_id"]: r
    for r in ol_authors
}


current_members = {}

for row in work_map:
    if (
        row["membership_role"]
        == "current_analysis_target"
    ):
        current_members.setdefault(
            row["project_work_id"],
            [],
        ).append(row)


author_edges = {}

for row in ol_work_authors:
    author_edges.setdefault(
        row["current_ol_work_id"],
        [],
    ).append(row)


output_rows = []


for group in GROUPS:
    wids = group["project_work_ids"]

    ol_ids = []
    entity_ids = []
    titles = []
    author_ids = []
    author_names = []

    for wid in wids:
        if wid not in works_by_id:
            raise RuntimeError(
                f"Missing project W: {wid}"
            )

        work = works_by_id[wid]

        if work["aggregation_decision_version"] != "v1":
            raise RuntimeError(
                f"{wid}: expected v1 project work"
            )

        if work["status"] != "active":
            raise RuntimeError(
                f"{wid}: expected active status"
            )

        members = current_members.get(
            wid,
            [],
        )

        if len(members) != 1:
            raise RuntimeError(
                f"{wid}: expected exactly one "
                f"current analysis target; "
                f"found {len(members)}"
            )

        entity_id = members[0][
            "source_entity_id"
        ]

        source = entities_by_id.get(
            entity_id
        )

        if source is None:
            raise RuntimeError(
                f"{wid}: missing source entity "
                f"{entity_id}"
            )

        if (
            source["source"] != "openlibrary"
            or source["source_namespace"]
            != "work"
        ):
            raise RuntimeError(
                f"{wid}: unexpected source identity"
            )

        ol_id = source["source_id"]

        ol_work = ol_works_by_id.get(
            ol_id
        )

        if ol_work is None:
            raise RuntimeError(
                f"{wid}: missing frozen OL Work "
                f"{ol_id}"
            )

        title = ol_work[
            "source_title"
        ]

        if title != group[
            "expected_title"
        ]:
            raise RuntimeError(
                f"{wid}: unexpected title "
                f"{title!r}"
            )

        edges = author_edges.get(
            ol_id,
            [],
        )

        if len(edges) != 1:
            raise RuntimeError(
                f"{wid}: expected one author edge; "
                f"found {len(edges)}"
            )

        aid = edges[0][
            "author_source_id"
        ]

        author = ol_authors_by_id.get(
            aid
        )

        if author is None:
            raise RuntimeError(
                f"{wid}: missing OL author {aid}"
            )

        entity_ids.append(
            entity_id
        )

        ol_ids.append(
            ol_id
        )

        titles.append(
            title
        )

        author_ids.append(
            aid
        )

        author_names.append(
            author["name"]
        )

    if len(set(titles)) != 1:
        raise RuntimeError(
            f"{group['review_group_id']}: "
            "titles differ"
        )

    if len(set(author_names)) != 1:
        raise RuntimeError(
            f"{group['review_group_id']}: "
            "author names differ"
        )

    # Strong exact-author-ID evidence for
    # Saintsbury and Bonsal.
    if group["review_group_id"] in {
        "PWMR000001",
        "PWMR000002",
    }:
        if len(set(author_ids)) != 1:
            raise RuntimeError(
                f"{group['review_group_id']}: "
                "expected identical author IDs"
            )

    # Albright author-record split must be exactly
    # the already reviewed pair.
    if group["review_group_id"] == "PWMR000003":
        if set(author_ids) != {
            "OL1805052A",
            "OL2566698A",
        }:
            raise RuntimeError(
                "Unexpected Albright author IDs"
            )

        a = ol_authors_by_id[
            "OL1805052A"
        ]
        b = ol_authors_by_id[
            "OL2566698A"
        ]

        if (
            a["name"] != b["name"]
            or a["personal_name"]
            != b["personal_name"]
        ):
            raise RuntimeError(
                "Albright author names conflict"
            )

        for field in [
            "remote_ids_json",
            "source_records_json",
        ]:
            if (
                a[field] not in {"{}", "[]"}
                or b[field] not in {"{}", "[]"}
            ):
                raise RuntimeError(
                    f"Unexpected Albright "
                    f"{field} evidence"
                )

    output_rows.append(
        {
            "review_group_id":
                group["review_group_id"],
            "decision":
                group["decision"],
            "confidence":
                group["confidence"],
            "predecessor_project_work_ids":
                "|".join(wids),
            "current_source_entity_ids":
                "|".join(entity_ids),
            "current_ol_work_ids":
                "|".join(ol_ids),
            "source_title":
                titles[0],
            "author_source_ids":
                "|".join(author_ids),
            "author_name":
                author_names[0],
            "decision_method":
                (
                    "manual_duplicate_review_"
                    "after_openalex_precision_diagnostic"
                ),
            "decision_version":
                "merge_review_v1",
            "scope_decision":
                "NOT_EVALUATED",
            "rationale":
                group["rationale"],
            "created_at":
                CREATED_AT,
        }
    )


fieldnames = [
    "review_group_id",
    "decision",
    "confidence",
    "predecessor_project_work_ids",
    "current_source_entity_ids",
    "current_ol_work_ids",
    "source_title",
    "author_source_ids",
    "author_name",
    "decision_method",
    "decision_version",
    "scope_decision",
    "rationale",
    "created_at",
]


lines = []

import io

buf = io.StringIO(
    newline=""
)

writer = csv.DictWriter(
    buf,
    fieldnames=fieldnames,
    delimiter="\t",
    lineterminator="\n",
)

writer.writeheader()
writer.writerows(output_rows)

write_atomic_text(
    OUT_TSV,
    buf.getvalue(),
)


manifest = {
    "release": RELEASE,
    "created_at": CREATED_AT,

    "semantics": {
        "unit_of_review":
            "project-work merge group",

        "decision_scope":
            (
                "Conceptual-work identity only. "
                "Corpus scope is not evaluated."
            ),

        "historical_release_policy":
            (
                "This artifact records merge "
                "judgments only. It does not "
                "rewrite project_works_v4 or "
                "work_identity_map_v4."
            ),

        "next_step":
            (
                "Represent accepted merges in "
                "a versioned project-work "
                "lineage/current-identity release."
            ),
    },

    "counts": {
        "review_groups":
            len(output_rows),

        "predecessor_project_works":
            sum(
                len(
                    r[
                        "predecessor_project_work_ids"
                    ].split("|")
                )
                for r in output_rows
            ),

        "merge_decisions":
            sum(
                r["decision"] == "MERGE"
                for r in output_rows
            ),

        "high_confidence":
            sum(
                r["confidence"] == "high"
                for r in output_rows
            ),
    },

    "inputs": {},

    "output": {
        "artifact":
            str(
                OUT_TSV.relative_to(ROOT)
            ),

        "sha256":
            sha256_file(OUT_TSV),
    },
}


for path in [
    PROJECT_WORKS,
    WORK_MAP,
    SOURCE_ENTITIES,
    OL_WORKS,
    OL_WORK_AUTHORS,
    OL_AUTHORS,
]:
    manifest["inputs"][
        str(path.relative_to(ROOT))
    ] = sha256_file(path)


write_atomic_text(
    OUT_MANIFEST,
    json.dumps(
        manifest,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n",
)


print(
    "=== PROJECT WORK MERGE REVIEW V1 ==="
)

for row in output_rows:
    print(
        row["review_group_id"],
        row["decision"],
        row["confidence"],
        row[
            "predecessor_project_work_ids"
        ],
        row["source_title"],
    )

print()
print(
    "review groups:",
    len(output_rows),
)

print(
    "predecessor W:",
    sum(
        len(
            r[
                "predecessor_project_work_ids"
            ].split("|")
        )
        for r in output_rows
    ),
)

print(
    "TSV:",
    OUT_TSV,
)

print(
    "Manifest:",
    OUT_MANIFEST,
)

print(
    "TSV SHA256:",
    sha256_file(OUT_TSV),
)

print(
    "Manifest SHA256:",
    sha256_file(OUT_MANIFEST),
)
