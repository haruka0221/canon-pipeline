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

QUEUE = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_remediation_queue_v1"
    / "openlibrary_r2a1_target_identity_remediation_queue_v1.tsv"
)

OUT_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_target_identity_remediation_adjudication_v1"
)

SOURCE_XLSX = (
    OUT_DIR
    / "source"
    / "openlibrary_r2a1_target_identity_remediation_review_completed_v1.xlsx"
)

OUT_TSV = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_remediation_adjudication_v1.tsv"
)

AUDIT_JSON = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_remediation_adjudication_v1_audit.json"
)

MANIFEST_JSON = (
    OUT_DIR
    / "openlibrary_r2a1_target_identity_remediation_adjudication_v1_manifest.json"
)


RELEASE = (
    "openlibrary-r2a1-target-identity-remediation-adjudication-v1"
)

EXPECTED_SOURCE_XLSX_SHA256 = (
    "ec242725f437d9d364b76b859121beeb"
    "894e6420e5b2b9fd57b278535049dc36"
)

EVIDENCE_FREEZE_COMMIT = (
    "62278b690b289f9f087c7b6fce2ac3a6ad3c2f96"
)

EXPECTED_ROWS = 24
EXPECTED_PAIR_MASS = 72_914

DECISIONS = {
    "RETAIN",
    "REMAP",
    "SPLIT",
    "HOLD",
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


def norm(value):
    if value is None:
        return ""

    return (
        str(value)
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )


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
                "Review worksheet relationship not found"
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

            cell_type = c.attrib.get("t")

            if cell_type == "inlineStr":
                node = c.find(
                    f"{{{NS_MAIN}}}is"
                )

                value = ""

                if node is not None:
                    value = "".join(
                        x.text or ""
                        for x
                        in node.iter(
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
                    cell_type == "s"
                    and value != ""
                ):
                    value = shared[
                        int(value)
                    ]

                elif cell_type == "b":
                    value = (
                        "TRUE"
                        if value == "1"
                        else "FALSE"
                    )

            cells[ref] = value

    def col_letters(n):
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

        return letters

    rows = []

    # Review data rows 5–28, columns A–R.
    for excel_row in range(
        5,
        29,
    ):
        row = []

        for col in range(
            1,
            19,
        ):
            ref = (
                f"{col_letters(col)}"
                f"{excel_row}"
            )

            row.append(
                cells.get(
                    ref,
                    "",
                )
            )

        rows.append(row)

    return rows


def main():

    for p in [
        QUEUE,
        SOURCE_XLSX,
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

    queue = read_tsv(
        QUEUE
    )

    if len(queue) != EXPECTED_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_ROWS} queue rows; "
            f"found {len(queue)}"
        )

    xlsx_rows = read_review_sheet_xlsx(
        SOURCE_XLSX
    )

    if len(xlsx_rows) != EXPECTED_ROWS:
        raise RuntimeError(
            "Completed workbook row count mismatch"
        )

    # Critical immutable workbook columns:
    # A rank
    # B project_work_id
    # C title
    # D author
    # E diagnostic_type
    # F LLM project status
    # G human review status
    # H OL Work(s)
    # L pair_count
    # M queue reason
    immutable_map = {
        0: (
            "remediation_priority_rank",
            "remediation_priority_rank",
        ),
        1: (
            "project_work_id",
            "project_work_id",
        ),
        2: (
            "r2_target_title",
            "r2_target_title",
        ),
        3: (
            "r2_target_author",
            "r2_target_author",
        ),
        4: (
            "diagnostic_type",
            "diagnostic_type",
        ),
        5: (
            "llm_project_entity_status",
            "llm_project_entity_status",
        ),
        6: (
            "human_entity_statuses_reviewed",
            "human_entity_statuses_reviewed",
        ),
        7: (
            "current_ol_work_ids",
            "current_ol_work_ids",
        ),
        11: (
            "pair_count",
            "pair_count",
        ),
        12: (
            "remediation_queue_reason",
            "remediation_queue_reason",
        ),
    }

    mismatches = []
    output = []

    for i, (
        q,
        xr,
    ) in enumerate(
        zip(
            queue,
            xlsx_rows,
        ),
        start=1,
    ):

        for col_idx, (
            label,
            queue_field,
        ) in immutable_map.items():

            expected = norm(
                q[
                    queue_field
                ]
            )

            observed = norm(
                xr[
                    col_idx
                ]
            )

            if expected != observed:
                mismatches.append(
                    {
                        "review_row": i,
                        "field": label,
                        "expected": expected,
                        "observed": observed,
                    }
                )

        decision = norm(
            xr[13]
        ).upper()

        confidence = norm(
            xr[14]
        ).upper()

        plan = norm(
            xr[15]
        )

        note = norm(
            xr[16]
        )

        if decision not in DECISIONS:
            raise RuntimeError(
                f"Row {i}: invalid or blank "
                f"resolution_decision: "
                f"{decision!r}"
            )

        if confidence not in CONFIDENCE:
            raise RuntimeError(
                f"Row {i}: invalid or blank "
                f"resolution_confidence: "
                f"{confidence!r}"
            )

        if (
            decision
            in {
                "REMAP",
                "SPLIT",
            }
            and not plan
        ):
            raise RuntimeError(
                f"Row {i}: {decision} requires "
                f"'Remap target / split plan'"
            )

        output.append(
            {
                "remediation_priority_rank":
                    q[
                        "remediation_priority_rank"
                    ],

                "project_work_id":
                    q[
                        "project_work_id"
                    ],

                "r2_target_title":
                    q[
                        "r2_target_title"
                    ],

                "r2_target_author":
                    q[
                        "r2_target_author"
                    ],

                "diagnostic_type":
                    q[
                        "diagnostic_type"
                    ],

                "pair_count":
                    q[
                        "pair_count"
                    ],

                "current_ol_work_ids":
                    q[
                        "current_ol_work_ids"
                    ],

                "llm_project_entity_status":
                    q[
                        "llm_project_entity_status"
                    ],

                "human_entity_statuses_reviewed":
                    q[
                        "human_entity_statuses_reviewed"
                    ],

                "remediation_queue_reason":
                    q[
                        "remediation_queue_reason"
                    ],

                "resolution_decision":
                    decision,

                "resolution_confidence":
                    confidence,

                "resolution_plan":
                    plan,

                "resolution_note":
                    note,
            }
        )

    if mismatches:
        raise RuntimeError(
            "Critical immutable workbook fields differ "
            "from frozen queue:\n"
            + json.dumps(
                mismatches[:20],
                ensure_ascii=False,
                indent=2,
            )
        )

    if len(
        {
            r[
                "project_work_id"
            ]
            for r in output
        }
    ) != EXPECTED_ROWS:
        raise RuntimeError(
            "Duplicate project_work_id in adjudication"
        )

    pair_mass = sum(
        int(
            r[
                "pair_count"
            ]
        )
        for r in output
    )

    if pair_mass != EXPECTED_PAIR_MASS:
        raise RuntimeError(
            f"Pair mass {pair_mass}; "
            f"expected {EXPECTED_PAIR_MASS}"
        )

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "remediation_priority_rank",
        "project_work_id",
        "r2_target_title",
        "r2_target_author",
        "diagnostic_type",
        "pair_count",
        "current_ol_work_ids",
        "llm_project_entity_status",
        "human_entity_statuses_reviewed",
        "remediation_queue_reason",
        "resolution_decision",
        "resolution_confidence",
        "resolution_plan",
        "resolution_note",
    ]

    atomic_tsv(
        output,
        fieldnames,
        OUT_TSV,
    )

    def counts(field):
        d = {}

        for r in output:
            value = r[field]

            d[value] = (
                d.get(
                    value,
                    0,
                )
                + 1
            )

        return dict(
            sorted(
                d.items()
            )
        )

    pair_mass_by_decision = {}

    for r in output:
        decision = r[
            "resolution_decision"
        ]

        pair_mass_by_decision[
            decision
        ] = (
            pair_mass_by_decision.get(
                decision,
                0,
            )
            + int(
                r[
                    "pair_count"
                ]
            )
        )

    audit = {
        "release":
            RELEASE,

        "audit_status":
            "PASSED",

        "source_xlsx_sha256":
            source_sha,

        "source_xlsx_sha256_matches_expected":
            True,

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

        "pair_mass":
            pair_mass,

        "critical_immutable_fields_match_frozen_queue":
            True,

        "resolution_decision_counts":
            counts(
                "resolution_decision"
            ),

        "resolution_confidence_counts":
            counts(
                "resolution_confidence"
            ),

        "pair_mass_by_resolution_decision":
            dict(
                sorted(
                    pair_mass_by_decision.items()
                )
            ),

        "blank_resolution_plans":
            sum(
                1
                for r in output
                if not r[
                    "resolution_plan"
                ]
            ),

        "blank_resolution_notes":
            sum(
                1
                for r in output
                if not r[
                    "resolution_note"
                ]
            ),

        "remap_or_split_without_plan":
            sum(
                1
                for r in output
                if (
                    r[
                        "resolution_decision"
                    ]
                    in {
                        "REMAP",
                        "SPLIT",
                    }
                    and not r[
                        "resolution_plan"
                    ]
                )
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
            "frozen_human_operational_adjudication_candidate",

        "evidence_freeze_commit":
            EVIDENCE_FREEZE_COMMIT,

        "purpose":
            (
                "Freeze human project-level remediation "
                "decisions for the 24-work Open Library "
                "R2+A1 target-identity queue before any "
                "identity-registry mutation."
            ),

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
                QUEUE.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    QUEUE
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

        "semantics": [
            (
                "These are operational human remediation "
                "decisions, not a blinded validation "
                "sample."
            ),
            (
                "RETAIN, REMAP, SPLIT, and HOLD apply to "
                "project/source identity handling only."
            ),
            (
                "The decisions do not encode temporal, "
                "language, or fiction-scope eligibility."
            ),
            (
                "Pair counts are preserved as impact "
                "metadata and were visible during review; "
                "they are not identity evidence."
            ),
            (
                "No identity registry is modified by this "
                "artifact."
            ),
            (
                "REMAP and SPLIT require an explicit "
                "resolution plan before this release can "
                "pass QC."
            ),
        ],
    }

    atomic_json(
        manifest,
        MANIFEST_JSON,
    )

    print(
        "=== OL TARGET IDENTITY REMEDIATION ADJUDICATION V1 ==="
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
                r[
                    "project_work_id"
                ]
                for r in output
            }
        ),
    )

    print(
        "pair mass:",
        pair_mass,
    )

    print(
        "\n=== RESOLUTION DECISIONS ==="
    )

    for k, v in counts(
        "resolution_decision"
    ).items():
        print(
            f"{k}\t{v}"
        )

    print(
        "\n=== CONFIDENCE ==="
    )

    for k, v in counts(
        "resolution_confidence"
    ).items():
        print(
            f"{k}\t{v}"
        )

    print(
        "\n=== PAIR MASS BY DECISION ==="
    )

    for k, v in sorted(
        pair_mass_by_decision.items()
    ):
        print(
            f"{k}\t{v}"
        )

    print(
        "\n=== NON-RETAIN DECISIONS ==="
    )

    for r in output:
        if (
            r[
                "resolution_decision"
            ]
            != "RETAIN"
        ):
            print(
                "\t".join(
                    [
                        r[
                            "remediation_priority_rank"
                        ],
                        r[
                            "project_work_id"
                        ],
                        r[
                            "r2_target_title"
                        ],
                        r[
                            "resolution_decision"
                        ],
                        r[
                            "resolution_confidence"
                        ],
                        r[
                            "resolution_plan"
                        ],
                        r[
                            "resolution_note"
                        ],
                    ]
                )
            )

    print(
        "\nblank resolution notes:",
        audit[
            "blank_resolution_notes"
        ],
    )

    print(
        "critical immutable field check: PASSED"
    )

    print(
        "QC STATUS: PASSED"
    )


if __name__ == "__main__":
    main()
