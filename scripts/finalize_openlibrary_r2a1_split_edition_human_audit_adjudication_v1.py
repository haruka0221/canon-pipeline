#!/usr/bin/env python3

from pathlib import Path
from collections import Counter
from zipfile import ZipFile
import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

PACKET_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_human_audit_v1"
)

CASES = (
    PACKET_DIR
    / "openlibrary_r2a1_split_edition_human_audit_cases_v1.tsv"
)

COMPONENTS = (
    PACKET_DIR
    / "openlibrary_r2a1_split_edition_human_audit_components_v1.tsv"
)

SOURCE_XLSX = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_human_audit_adjudication_v1"
    / "source"
    / "openlibrary_r2a1_split_edition_human_audit_review_completed_v1.xlsx"
)

OUT_DIR = (
    ROOT
    / "derived/identity"
    / "openlibrary_r2a1_split_edition_human_audit_adjudication_v1"
)

OUT_TSV = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_human_audit_adjudication_v1.tsv"
)

OUT_AUDIT = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_human_audit_adjudication_v1_audit.json"
)

OUT_MANIFEST = (
    OUT_DIR
    / "openlibrary_r2a1_split_edition_human_audit_adjudication_v1_manifest.json"
)


RELEASE = (
    "openlibrary-r2a1-split-edition-human-audit-adjudication-v1"
)

CREATED_AT = "2026-10-11"

REVIEW_SELECTION_FREEZE_COMMIT = (
    "32d95c3de27eabee635cb54e930f7c791a6822b3"
)

RAW_LLM_FREEZE_COMMIT = (
    "9d4a2d0ce50cc5335e06672732aa060d3a3be124"
)

EXPECTED_CASES = 118
EXPECTED_PROJECTS = 17
EXPECTED_COMPONENTS = 82

VALID_DECISIONS = {
    "ASSIGN_COMPONENT",
    "HOLD_UNRESOLVED",
    "REGISTRY_ISSUE",
}

VALID_CONFIDENCE = {
    "HIGH",
    "MEDIUM",
    "LOW",
}


def sha256_file(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
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


# ------------------------------------------------------------
# Minimal XLSX reader using only Python stdlib.
# No spreadsheet recalculation and no LLM artifact access.
# ------------------------------------------------------------

NS_MAIN = (
    "http://schemas.openxmlformats.org/"
    "spreadsheetml/2006/main"
)

NS_REL = (
    "http://schemas.openxmlformats.org/"
    "officeDocument/2006/relationships"
)


def column_number(ref):
    letters = re.match(
        r"[A-Z]+",
        ref,
    ).group(0)

    n = 0

    for ch in letters:
        n = (
            n * 26
            + ord(ch)
            - 64
        )

    return n


def read_review_sheet(path):

    with ZipFile(path) as z:

        shared = []

        if (
            "xl/sharedStrings.xml"
            in z.namelist()
        ):
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

        workbook = ET.fromstring(
            z.read(
                "xl/workbook.xml"
            )
        )

        review_rid = None

        sheets = workbook.find(
            f"{{{NS_MAIN}}}sheets"
        )

        for sheet in sheets:
            if (
                sheet.attrib.get(
                    "name"
                )
                == "Review"
            ):
                review_rid = (
                    sheet.attrib[
                        f"{{{NS_REL}}}id"
                    ]
                )
                break

        if not review_rid:
            raise RuntimeError(
                "Review sheet not found"
            )

        rels = ET.fromstring(
            z.read(
                "xl/_rels/workbook.xml.rels"
            )
        )

        target = None

        for rel in rels:
            if (
                rel.attrib.get("Id")
                == review_rid
            ):
                target = (
                    rel.attrib[
                        "Target"
                    ]
                )
                break

        if not target:
            raise RuntimeError(
                "Review sheet relationship not found"
            )

        if target.startswith("/"):
            sheet_path = (
                target.lstrip("/")
            )

        elif target.startswith("xl/"):
            sheet_path = target

        else:
            sheet_path = (
                "xl/" + target
            )

        root = ET.fromstring(
            z.read(
                sheet_path
            )
        )

        rows = []

        for row in root.iter(
            f"{{{NS_MAIN}}}row"
        ):

            values = {}

            for cell in row.findall(
                f"{{{NS_MAIN}}}c"
            ):

                ref = cell.attrib["r"]

                col = column_number(
                    ref
                )

                typ = cell.attrib.get(
                    "t",
                    "",
                )

                value = ""

                if typ == "inlineStr":

                    node = cell.find(
                        f"{{{NS_MAIN}}}is"
                    )

                    if node is not None:
                        value = "".join(
                            t.text or ""
                            for t
                            in node.iter(
                                f"{{{NS_MAIN}}}t"
                            )
                        )

                else:

                    node = cell.find(
                        f"{{{NS_MAIN}}}v"
                    )

                    if (
                        node is not None
                        and node.text
                        is not None
                    ):

                        if typ == "s":
                            value = (
                                shared[
                                    int(
                                        node.text
                                    )
                                ]
                            )
                        else:
                            value = (
                                node.text
                            )

                values[col] = value

            rows.append(
                values
            )

    if not rows:
        raise RuntimeError(
            "Review sheet is empty"
        )

    header = rows[0]

    name_to_col = {
        str(value).strip():
            col
        for col, value
        in header.items()
    }

    def get(row, name):
        return str(
            row.get(
                name_to_col[name],
                "",
            )
        ).strip()

    required = [
        "audit_case_id",
        "priority_rank",
        "project_work_id",
        "target_title",
        "target_author",
        "current_ol_work_id",
        "edition_key",
        "edition_title",
        "edition_subtitle",
        "publish_date",
        "publishers",
        "edition_author_keys",
        "pages",
        "human_resolution_confidence",
        "human_routing_decision",
        "human_component_id",
        "human_confidence",
        "human_note",
    ]

    for name in required:
        if name not in name_to_col:
            raise RuntimeError(
                f"Missing Review column: {name}"
            )

    parsed = []

    for row in rows[1:]:

        case_id = get(
            row,
            "audit_case_id",
        )

        if not case_id:
            continue

        parsed.append({
            name:
                get(
                    row,
                    name,
                )
            for name
            in required
        })

    return parsed


def main():

    for p in [
        CASES,
        COMPONENTS,
        SOURCE_XLSX,
    ]:
        if not p.exists():
            raise FileNotFoundError(p)

    if (
        OUT_TSV.exists()
        or OUT_AUDIT.exists()
        or OUT_MANIFEST.exists()
    ):
        raise RuntimeError(
            "Final adjudication output already exists"
        )

    cases = pd.read_csv(
        CASES,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    components = pd.read_csv(
        COMPONENTS,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    assert len(cases) == EXPECTED_CASES
    assert cases["audit_case_id"].is_unique

    assert (
        cases[
            "project_work_id"
        ].nunique()
        == EXPECTED_PROJECTS
    )

    assert len(
        components
    ) == EXPECTED_COMPONENTS

    assert components[
        "component_id"
    ].is_unique

    review_rows = (
        read_review_sheet(
            SOURCE_XLSX
        )
    )

    assert len(
        review_rows
    ) == EXPECTED_CASES

    review = pd.DataFrame(
        review_rows
    )

    assert review[
        "audit_case_id"
    ].is_unique

    assert set(
        review[
            "audit_case_id"
        ]
    ) == set(
        cases[
            "audit_case_id"
        ]
    )

    # --------------------------------------------------------
    # Verify that bibliographic/evidence fields in the
    # completed workbook were not modified relative to the
    # frozen review packet.
    # --------------------------------------------------------

    field_map = {
        "priority_rank":
            "remediation_priority_rank",

        "project_work_id":
            "project_work_id",

        "target_title":
            "r2_target_title",

        "target_author":
            "r2_target_author",

        "current_ol_work_id":
            "current_ol_work_id",

        "edition_key":
            "edition_key",

        "edition_title":
            "edition_title",

        "edition_subtitle":
            "edition_subtitle",

        "publish_date":
            "publish_date",

        "publishers":
            "publishers",

        "edition_author_keys":
            "edition_author_keys",

        "pages":
            "number_of_pages",

        "human_resolution_confidence":
            "resolution_confidence",
    }

    frozen = (
        cases
        .set_index(
            "audit_case_id"
        )
    )

    review_indexed = (
        review
        .set_index(
            "audit_case_id"
        )
    )

    evidence_mismatches = []

    for case_id in frozen.index:

        for xlsx_col, tsv_col in (
            field_map.items()
        ):

            a = str(
                frozen.loc[
                    case_id,
                    tsv_col,
                ]
            ).strip()

            b = str(
                review_indexed.loc[
                    case_id,
                    xlsx_col,
                ]
            ).strip()

            if a != b:
                evidence_mismatches.append({
                    "audit_case_id":
                        case_id,

                    "field":
                        xlsx_col,

                    "frozen_value":
                        a,

                    "workbook_value":
                        b,
                })

    if evidence_mismatches:
        print(
            "EVIDENCE MISMATCHES:"
        )

        for x in (
            evidence_mismatches[:30]
        ):
            print(x)

        raise RuntimeError(
            "Completed workbook changed "
            "frozen evidence fields"
        )

    # --------------------------------------------------------
    # Validate human decisions.
    # --------------------------------------------------------

    component_meta = (
        components
        .set_index(
            "component_id"
        )
        .to_dict(
            orient="index"
        )
    )

    problems = []

    normalized = {}

    for r in review.to_dict(
        orient="records"
    ):

        case = r[
            "audit_case_id"
        ]

        pid = r[
            "project_work_id"
        ]

        decision = r[
            "human_routing_decision"
        ].strip()

        component_id = r[
            "human_component_id"
        ].strip()

        confidence = r[
            "human_confidence"
        ].strip()

        note = r[
            "human_note"
        ].strip()

        if (
            decision
            not in VALID_DECISIONS
        ):
            problems.append(
                (
                    case,
                    "invalid_decision",
                    decision,
                )
            )

        if (
            confidence
            not in VALID_CONFIDENCE
        ):
            problems.append(
                (
                    case,
                    "invalid_confidence",
                    confidence,
                )
            )

        component_label = ""
        component_role_hint = ""

        if (
            decision
            == "ASSIGN_COMPONENT"
        ):

            if not component_id:
                problems.append(
                    (
                        case,
                        "missing_component",
                        "",
                    )
                )

            elif (
                component_id
                not in component_meta
            ):
                problems.append(
                    (
                        case,
                        "unknown_component",
                        component_id,
                    )
                )

            else:

                meta = (
                    component_meta[
                        component_id
                    ]
                )

                if (
                    meta[
                        "project_work_id"
                    ]
                    != pid
                ):
                    problems.append(
                        (
                            case,
                            "component_wrong_project",
                            component_id,
                        )
                    )

                component_label = (
                    meta[
                        "component_label"
                    ]
                )

                component_role_hint = (
                    meta[
                        "human_role_hint"
                    ]
                )

        else:

            if component_id:
                problems.append(
                    (
                        case,
                        "nonassign_has_component",
                        component_id,
                    )
                )

        if (
            decision
            == "REGISTRY_ISSUE"
            and not note
        ):
            problems.append(
                (
                    case,
                    "registry_issue_missing_note",
                    "",
                )
            )

        normalized[
            case
        ] = {
            "human_routing_decision":
                decision,

            "human_component_id":
                component_id,

            "human_component_label":
                component_label,

            "human_component_role_hint":
                component_role_hint,

            "human_confidence":
                confidence,

            "human_note":
                note,
        }

    if problems:
        print("PROBLEMS:")

        for x in problems[:50]:
            print(x)

        raise RuntimeError(
            "Human adjudication validation failed"
        )

    # --------------------------------------------------------
    # Produce human-only normalized adjudication.
    # --------------------------------------------------------

    out = cases.copy()

    # Remove blank review-entry columns from the frozen packet
    # and replace them with completed normalized values.
    for col in [
        "human_routing_decision",
        "human_component_id",
        "human_confidence",
        "human_note",
    ]:
        if col in out.columns:
            out = out.drop(
                columns=col
            )

    human_rows = pd.DataFrame(
        [
            {
                "audit_case_id":
                    case_id,

                **normalized[
                    case_id
                ],
            }
            for case_id
            in out[
                "audit_case_id"
            ]
        ]
    )

    out = out.merge(
        human_rows,
        on="audit_case_id",
        how="left",
        validate="one_to_one",
    )

    assert len(out) == EXPECTED_CASES

    assert out[
        "human_routing_decision"
    ].isin(
        VALID_DECISIONS
    ).all()

    assert out[
        "human_confidence"
    ].isin(
        VALID_CONFIDENCE
    ).all()

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    atomic_tsv(
        out,
        OUT_TSV,
    )

    decision_counts = {
        str(k): int(v)
        for k, v
        in out[
            "human_routing_decision"
        ]
        .value_counts()
        .sort_index()
        .items()
    }

    confidence_counts = {
        str(k): int(v)
        for k, v
        in out[
            "human_confidence"
        ]
        .value_counts()
        .sort_index()
        .items()
    }

    assigned = out.loc[
        out[
            "human_routing_decision"
        ].eq(
            "ASSIGN_COMPONENT"
        )
    ].copy()

    assigned_role_counts = {
        str(k): int(v)
        for k, v
        in assigned[
            "human_component_role_hint"
        ]
        .value_counts()
        .sort_index()
        .items()
    }

    registry_issue_counts = {
        str(k): int(v)
        for k, v
        in out.loc[
            out[
                "human_routing_decision"
            ].eq(
                "REGISTRY_ISSUE"
            ),
            "project_work_id",
        ]
        .value_counts()
        .sort_index()
        .items()
    }

    audit = {
        "release":
            RELEASE,

        "audit_status":
            "PASSED",

        "rows":
            len(out),

        "unique_case_ids":
            out[
                "audit_case_id"
            ].nunique(),

        "project_works":
            out[
                "project_work_id"
            ].nunique(),

        "frozen_evidence_fields_unchanged":
            True,

        "all_decisions_valid":
            True,

        "all_confidences_valid":
            True,

        "all_assigned_components_valid_for_project":
            True,

        "all_nonassign_components_blank":
            True,

        "all_registry_issues_have_notes":
            True,

        "decision_counts":
            decision_counts,

        "confidence_counts":
            confidence_counts,

        "assigned_component_role_hint_counts":
            assigned_role_counts,

        "registry_issue_counts_by_project":
            registry_issue_counts,
    }

    atomic_json(
        audit,
        OUT_AUDIT,
    )

    manifest = {
        "release":
            RELEASE,

        "status":
            "frozen_human_only_adjudication",

        "created_at":
            CREATED_AT,

        "review_selection_freeze_commit":
            REVIEW_SELECTION_FREEZE_COMMIT,

        "raw_llm_freeze_commit":
            RAW_LLM_FREEZE_COMMIT,

        "semantics": [
            (
                "This release freezes human review "
                "before row-level unblinding against "
                "the frozen LLM routing output."
            ),
            (
                "The finalizer does not read the "
                "LLM routing artifact."
            ),
            (
                "ASSIGN_COMPONENT selects one fixed "
                "human-defined routing component."
            ),
            (
                "HOLD_UNRESOLVED preserves insufficient "
                "evidence without forcing an assignment."
            ),
            (
                "REGISTRY_ISSUE flags cases where the "
                "fixed component registry is inadequate "
                "for the observed Edition."
            ),
            (
                "This review is not a fully independent "
                "blinded validation because the reviewer "
                "had prior project knowledge and had seen "
                "aggregate LLM results, but row-level LLM "
                "answers were withheld during review."
            ),
        ],

        "inputs": {
            str(
                CASES.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    CASES
                ),

            str(
                COMPONENTS.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    COMPONENTS
                ),

            str(
                SOURCE_XLSX.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    SOURCE_XLSX
                ),

            str(
                Path(__file__).relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    Path(__file__)
                ),
        },

        "outputs": {
            OUT_TSV.name:
                sha256_file(
                    OUT_TSV
                ),

            OUT_AUDIT.name:
                sha256_file(
                    OUT_AUDIT
                ),
        },
    }

    atomic_json(
        manifest,
        OUT_MANIFEST,
    )

    print(
        "=== HUMAN-ONLY ADJUDICATION V1 ==="
    )

    print(
        "rows:",
        len(out),
    )

    print(
        "project works:",
        out[
            "project_work_id"
        ].nunique(),
    )

    print()
    print(
        "=== DECISIONS ==="
    )

    print(
        out[
            "human_routing_decision"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print()
    print(
        "=== CONFIDENCE ==="
    )

    print(
        out[
            "human_confidence"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print()
    print(
        "=== ASSIGNED COMPONENT ROLE HINTS ==="
    )

    print(
        assigned[
            "human_component_role_hint"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print()
    print(
        "=== REGISTRY ISSUES BY PROJECT ==="
    )

    if registry_issue_counts:
        for k, v in (
            registry_issue_counts.items()
        ):
            print(
                f"{k}: {v}"
            )
    else:
        print("[none]")

    print()
    print(
        "completed workbook sha256:",
        sha256_file(
            SOURCE_XLSX
        ),
    )

    print()
    print(
        "QC STATUS: PASSED"
    )


if __name__ == "__main__":
    main()
