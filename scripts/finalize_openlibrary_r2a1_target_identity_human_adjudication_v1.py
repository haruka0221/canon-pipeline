#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import csv
import hashlib
import json
import os
import re
import zipfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]

SAMPLE_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_human_audit_sample_v1"
)

FROZEN_REVIEW = (
    SAMPLE_DIR
    / "openlibrary_r2a1_target_identity_human_audit_review_input_v1.tsv"
)

SAMPLE_MANIFEST = (
    SAMPLE_DIR
    / "openlibrary_r2a1_target_identity_human_audit_sample_v1_manifest.json"
)

OUT_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_human_adjudication_v1"
)

SOURCE_XLSX = (
    OUT_DIR
    / "source"
    / "openlibrary_r2a1_target_identity_human_audit_review_completed_v1.xlsx"
)

OUT_TSV = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_human_adjudication_v1.tsv"
)

AUDIT_JSON = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_human_adjudication_v1_audit.json"
)

MANIFEST_JSON = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_human_adjudication_v1_manifest.json"
)


RELEASE = (
    "openlibrary-r2a1-target-identity-human-adjudication-v1"
)

EXPECTED_SOURCE_XLSX_SHA256 = (
    "7a6cf2db46b925cbec014402f8551dbd1"
    "db659d75827d292c724faf7fb4a44a1"
)

EXPECTED_ROWS = 20


ENTITY_STATUS = {
    "COHERENT_SINGLE_WORK",
    "COHERENT_COLLECTION",
    "HETEROGENEOUS_CLUSTER",
    "NONWORK_OR_HEADING_ARTIFACT",
    "UNCERTAIN",
}

CONTENT_TYPE = {
    "SPECIFIC_FICTION_WORK",
    "FICTION_COLLECTION_OR_ANTHOLOGY",
    "BROAD_AUTHOR_OEUVRE_OR_MIXED_COLLECTION",
    "NONFICTION_OR_OTHER_LITERARY_FORM",
    "MIXED_OR_UNCLEAR",
}

DATE_STATUS = {
    "LIKELY_ORIGINAL_1880_1950",
    "LIKELY_ORIGINAL_OUTSIDE_1880_1950",
    "INSUFFICIENT_DATE_EVIDENCE",
}

CONFIDENCE = {
    "HIGH",
    "MEDIUM",
    "LOW",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def atomic_tsv(rows, fieldnames, path):
    tmp = path.with_name(
        path.name + ".tmp"
    )

    with tmp.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:
        w = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        w.writeheader()
        w.writerows(rows)

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


def display_bullets(value):
    value = (value or "").strip()

    if not value:
        return ""

    parts = [
        x.strip()
        for x in value.split("||")
        if x.strip()
    ]

    if len(parts) <= 1:
        return (
            parts[0]
            if parts
            else ""
        )

    return "• " + "\n• ".join(parts)


def col_number(cell_ref):
    m = re.match(
        r"([A-Z]+)",
        cell_ref,
    )

    if not m:
        raise ValueError(
            f"Bad cell reference: {cell_ref}"
        )

    n = 0

    for ch in m.group(1):
        n = (
            n * 26
            + ord(ch)
            - ord("A")
            + 1
        )

    return n


def read_review_sheet_xlsx(path):
    NS_MAIN = (
        "http://schemas.openxmlformats.org/"
        "spreadsheetml/2006/main"
    )

    NS_REL = (
        "http://schemas.openxmlformats.org/"
        "officeDocument/2006/relationships"
    )

    NS_PKG_REL = (
        "http://schemas.openxmlformats.org/"
        "package/2006/relationships"
    )

    with zipfile.ZipFile(
        path,
        "r",
    ) as z:

        shared = []

        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(
                z.read(
                    "xl/sharedStrings.xml"
                )
            )

            for si in root.findall(
                f"{{{NS_MAIN}}}si"
            ):
                shared.append(
                    "".join(
                        t.text or ""
                        for t
                        in si.iter(
                            f"{{{NS_MAIN}}}t"
                        )
                    )
                )

        wb_root = ET.fromstring(
            z.read(
                "xl/workbook.xml"
            )
        )

        review_rid = None

        sheets = wb_root.find(
            f"{{{NS_MAIN}}}sheets"
        )

        for sheet in sheets:
            if sheet.attrib.get(
                "name"
            ) == "Review":
                review_rid = sheet.attrib.get(
                    f"{{{NS_REL}}}id"
                )
                break

        if not review_rid:
            raise RuntimeError(
                "Review sheet not found"
            )

        rel_root = ET.fromstring(
            z.read(
                "xl/_rels/workbook.xml.rels"
            )
        )

        target = None

        for rel in rel_root.findall(
            f"{{{NS_PKG_REL}}}Relationship"
        ):
            if rel.attrib.get(
                "Id"
            ) == review_rid:
                target = rel.attrib.get(
                    "Target"
                )
                break

        if not target:
            raise RuntimeError(
                "Review sheet relationship not found"
            )

        target = target.lstrip("/")

        if not target.startswith(
            "xl/"
        ):
            target = "xl/" + target

        sheet_root = ET.fromstring(
            z.read(target)
        )

        cells = {}

        for c in sheet_root.iter(
            f"{{{NS_MAIN}}}c"
        ):
            ref = c.attrib.get("r")

            if not ref:
                continue

            t = c.attrib.get("t")

            if t == "inlineStr":
                is_node = c.find(
                    f"{{{NS_MAIN}}}is"
                )

                value = ""

                if is_node is not None:
                    value = "".join(
                        x.text or ""
                        for x
                        in is_node.iter(
                            f"{{{NS_MAIN}}}t"
                        )
                    )

            else:
                v = c.find(
                    f"{{{NS_MAIN}}}v"
                )

                value = (
                    ""
                    if v is None
                    else (v.text or "")
                )

                if (
                    t == "s"
                    and value != ""
                ):
                    value = shared[
                        int(value)
                    ]

                elif t == "b":
                    value = (
                        "TRUE"
                        if value == "1"
                        else "FALSE"
                    )

            cells[ref] = value

    rows = []

    # Data are rows 3–22, columns A–V.
    for excel_row in range(
        3,
        23,
    ):
        row = []

        for col in range(
            1,
            23,
        ):
            # Convert 1-based column number to letters.
            n = col
            letters = ""

            while n:
                n, rem = divmod(
                    n - 1,
                    26,
                )
                letters = (
                    chr(
                        ord("A")
                        + rem
                    )
                    + letters
                )

            row.append(
                cells.get(
                    f"{letters}{excel_row}",
                    "",
                )
            )

        rows.append(row)

    return rows


def norm(value):
    if value is None:
        return ""

    value = str(value)

    # Normalize workbook line endings only.
    return value.replace(
        "\r\n",
        "\n",
    ).replace(
        "\r",
        "\n",
    ).strip()


def main():

    for p in [
        SOURCE_XLSX,
        FROZEN_REVIEW,
        SAMPLE_MANIFEST,
    ]:
        if not p.exists():
            raise FileNotFoundError(p)

    source_sha = sha256_file(
        SOURCE_XLSX
    )

    if (
        source_sha
        != EXPECTED_SOURCE_XLSX_SHA256
    ):
        raise RuntimeError(
            "Completed XLSX SHA256 mismatch:\n"
            f"expected {EXPECTED_SOURCE_XLSX_SHA256}\n"
            f"actual   {source_sha}"
        )

    frozen = read_tsv(
        FROZEN_REVIEW
    )

    if len(frozen) != EXPECTED_ROWS:
        raise RuntimeError(
            "Frozen review row count mismatch"
        )

    xlsx_rows = read_review_sheet_xlsx(
        SOURCE_XLSX
    )

    if len(xlsx_rows) != EXPECTED_ROWS:
        raise RuntimeError(
            "Completed workbook row count mismatch"
        )

    # Column positions in the human workbook.
    # A–V => indexes 0–21.
    #
    # F–J are the human-editable fields.
    immutable_map = {
        0: (
            "review_order",
            lambda r: r["review_order"],
        ),
        1: (
            "project_work_id",
            lambda r: r["project_work_id"],
        ),
        2: (
            "current_ol_work_id",
            lambda r: r["current_ol_work_id"],
        ),
        3: (
            "r2_target_title",
            lambda r: r["r2_target_title"],
        ),
        4: (
            "r2_target_author",
            lambda r: r["r2_target_author"],
        ),

        10: (
            "title",
            lambda r: r["title"],
        ),
        11: (
            "first_publish_year",
            lambda r: r["first_publish_year"],
        ),
        12: (
            "current_work_title",
            lambda r: r["current_work_title"],
        ),
        13: (
            "current_work_first_publish_date",
            lambda r: r[
                "current_work_first_publish_date"
            ],
        ),
        14: (
            "current_work_description",
            lambda r: r[
                "current_work_description"
            ],
        ),
        15: (
            "current_work_subjects",
            lambda r:
                display_bullets(
                    r[
                        "current_work_subjects"
                    ]
                ),
        ),
        16: (
            "edition_total_reported",
            lambda r:
                r[
                    "edition_total_reported"
                ],
        ),
        17: (
            "distinct_edition_titles",
            lambda r:
                r[
                    "distinct_edition_titles"
                ],
        ),
        18: (
            "edition_titles",
            lambda r:
                display_bullets(
                    r[
                        "edition_titles"
                    ]
                ),
        ),
        19: (
            "edition_subtitles",
            lambda r:
                display_bullets(
                    r[
                        "edition_subtitles"
                    ]
                ),
        ),
        20: (
            "edition_publish_dates",
            lambda r:
                display_bullets(
                    r[
                        "edition_publish_dates"
                    ]
                ),
        ),
        21: (
            "edition_publishers",
            lambda r:
                display_bullets(
                    r[
                        "edition_publishers"
                    ]
                ),
        ),
    }

    mismatches = []

    output = []

    for i, (
        fr,
        xr,
    ) in enumerate(
        zip(
            frozen,
            xlsx_rows,
        ),
        start=1,
    ):

        for col_idx, (
            field,
            expected_fn,
        ) in immutable_map.items():

            expected = norm(
                expected_fn(fr)
            )

            observed = norm(
                xr[col_idx]
            )

            if expected != observed:
                mismatches.append(
                    {
                        "review_row": i,
                        "field": field,
                        "expected": expected,
                        "observed": observed,
                    }
                )

        entity = norm(xr[5])
        content = norm(xr[6])
        date_status = norm(xr[7])
        confidence = norm(xr[8])
        note = norm(xr[9])

        if entity not in ENTITY_STATUS:
            raise RuntimeError(
                f"Row {i}: invalid/blank "
                f"human_entity_status: "
                f"{entity!r}"
            )

        if content not in CONTENT_TYPE:
            raise RuntimeError(
                f"Row {i}: invalid/blank "
                f"human_content_type: "
                f"{content!r}"
            )

        if date_status not in DATE_STATUS:
            raise RuntimeError(
                f"Row {i}: invalid/blank "
                f"human_date_window_assessment: "
                f"{date_status!r}"
            )

        if confidence not in CONFIDENCE:
            raise RuntimeError(
                f"Row {i}: invalid/blank "
                f"human_confidence: "
                f"{confidence!r}"
            )

        output.append(
            {
                "review_order":
                    fr["review_order"],

                "project_work_id":
                    fr["project_work_id"],

                "current_ol_work_id":
                    fr["current_ol_work_id"],

                "r2_target_title":
                    fr["r2_target_title"],

                "r2_target_author":
                    fr["r2_target_author"],

                "human_entity_status":
                    entity,

                "human_content_type":
                    content,

                "human_date_window_assessment":
                    date_status,

                "human_confidence":
                    confidence,

                "human_note":
                    note,
            }
        )

    if mismatches:
        preview = json.dumps(
            mismatches[:10],
            ensure_ascii=False,
            indent=2,
        )

        raise RuntimeError(
            "Immutable workbook evidence differs "
            "from frozen review input.\n"
            + preview
        )

    if len(
        {
            r["current_ol_work_id"]
            for r in output
        }
    ) != EXPECTED_ROWS:
        raise RuntimeError(
            "Duplicate OL Work ID in adjudication"
        )

    if [
        int(r["review_order"])
        for r in output
    ] != list(
        range(
            1,
            EXPECTED_ROWS + 1,
        )
    ):
        raise RuntimeError(
            "Review order is not exactly 1..20"
        )

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    fields = [
        "review_order",
        "project_work_id",
        "current_ol_work_id",
        "r2_target_title",
        "r2_target_author",
        "human_entity_status",
        "human_content_type",
        "human_date_window_assessment",
        "human_confidence",
        "human_note",
    ]

    atomic_tsv(
        output,
        fields,
        OUT_TSV,
    )

    def counts(field):
        d = {}

        for r in output:
            value = r[field]
            d[value] = (
                d.get(value, 0)
                + 1
            )

        return dict(
            sorted(
                d.items()
            )
        )

    audit = {
        "release":
            RELEASE,

        "audit_status":
            "PASSED",

        "rows":
            len(output),

        "unique_project_works":
            len(
                {
                    r[
                        "project_work_id"
                    ]
                    for r in output
                }
            ),

        "unique_openlibrary_works":
            len(
                {
                    r[
                        "current_ol_work_id"
                    ]
                    for r in output
                }
            ),

        "source_xlsx_sha256":
            source_sha,

        "source_xlsx_sha256_matches_expected":
            True,

        "immutable_review_fields_match_frozen_input":
            True,

        "all_required_categorical_judgments_present":
            True,

        "blank_human_notes":
            sum(
                1
                for r in output
                if not r[
                    "human_note"
                ]
            ),

        "human_entity_status_counts":
            counts(
                "human_entity_status"
            ),

        "human_content_type_counts":
            counts(
                "human_content_type"
            ),

        "human_date_window_assessment_counts":
            counts(
                "human_date_window_assessment"
            ),

        "human_confidence_counts":
            counts(
                "human_confidence"
            ),
    }

    atomic_json(
        audit,
        AUDIT_JSON,
    )

    manifest = {
        "release":
            RELEASE,

        "status":
            "frozen_human_only_adjudication",

        "purpose":
            (
                "Freeze the completed human judgments "
                "for the 20-record Open Library target-"
                "identity audit before joining them to "
                "the frozen LLM judgments."
            ),

        "review_blinding_note":
            (
                "The review workbook itself withheld "
                "LLM labels, LLM confidence, pair counts, "
                "retrieval-risk classes, and retrieval "
                "impact fields. However, the reviewer had "
                "previously been exposed to row-level LLM "
                "results during the analysis discussion. "
                "Therefore this adjudication must not be "
                "described as a fully independent blinded "
                "human audit."
            ),

        "important_semantics": [
            (
                "This artifact contains human judgments "
                "only; it does not load or join the LLM "
                "adjudication."
            ),
            (
                "The completed XLSX SHA256 is fixed and "
                "verified against the local pre-transfer "
                "hash."
            ),
            (
                "All immutable evidence fields visible in "
                "the review workbook were checked against "
                "the frozen review-input TSV."
            ),
            (
                "Human-versus-LLM comparison must occur "
                "only after this human-only release has "
                "been committed."
            ),
        ],

        "inputs": {
            str(
                SOURCE_XLSX.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    SOURCE_XLSX
                ),

            str(
                FROZEN_REVIEW.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    FROZEN_REVIEW
                ),

            str(
                SAMPLE_MANIFEST.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    SAMPLE_MANIFEST
                ),
        },

        "outputs": {
            str(
                OUT_TSV.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    OUT_TSV
                ),

            str(
                AUDIT_JSON.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    AUDIT_JSON
                ),
        },
    }

    atomic_json(
        manifest,
        MANIFEST_JSON,
    )

    print(
        "=== OL TARGET IDENTITY HUMAN ADJUDICATION V1 ==="
    )
    print(
        "source XLSX SHA256:",
        source_sha,
    )
    print(
        "rows:",
        len(output),
    )
    print(
        "project works:",
        len(
            {
                r["project_work_id"]
                for r in output
            }
        ),
    )
    print()

    for field in [
        "human_entity_status",
        "human_content_type",
        "human_date_window_assessment",
        "human_confidence",
    ]:
        print(
            f"=== {field} ==="
        )

        for k, v in counts(
            field
        ).items():
            print(
                f"{k}\t{v}"
            )

        print()

    print(
        "blank human notes:",
        audit[
            "blank_human_notes"
        ],
    )

    print(
        "immutable evidence check: PASSED"
    )

    print(
        "QC STATUS: PASSED"
    )


if __name__ == "__main__":
    main()
