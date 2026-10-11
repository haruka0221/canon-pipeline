#!/usr/bin/env python3

from pathlib import Path
import csv
import hashlib
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]

OUT_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_r2a1_baseline_primary_human_adjudication_v1"
)

SOURCE_XLSX = (
    OUT_DIR
    / "source"
    / "openalex_r2a1_baseline_primary_human_audit_review_completed_v1.xlsx"
)

FROZEN_MASTER = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_r2a1_baseline_primary_human_audit_packet_v1"
    / "openalex_r2a1_baseline_primary_human_audit_master_v1.tsv"
)

OUT_TSV = (
    OUT_DIR
    / "openalex_r2a1_baseline_primary_human_adjudication_v1.tsv"
)

SUMMARY = (
    OUT_DIR
    / "openalex_r2a1_baseline_primary_human_adjudication_summary_v1.json"
)

AUDIT = (
    OUT_DIR
    / "openalex_r2a1_baseline_primary_human_adjudication_v1_audit.json"
)

MANIFEST = (
    OUT_DIR
    / "openalex_r2a1_baseline_primary_human_adjudication_v1_manifest.json"
)

EXPECTED_XLSX_SHA256 = (
    "17f9f57762457acec9464c9f8d907e1c"
    "120751929e730a3420e36c6407d7d684"
)

EXPECTED_ROWS = 150

VALID_JUDGMENTS = {
    "VALID_TARGET_REFERENCE",
    "INVALID_TARGET_REFERENCE",
    "UNCERTAIN",
}

VALID_CONFIDENCES = {
    "HIGH",
    "MEDIUM",
    "LOW",
}

REASONS_BY_JUDGMENT = {
    "VALID_TARGET_REFERENCE": {
        "DIRECT_TARGET_REFERENCE",
        "VALID_TITLE_VARIANT",
        "VALID_CONTEXTUAL_REFERENCE",
    },

    "INVALID_TARGET_REFERENCE": {
        "TITLE_COLLISION_DIFFERENT_WORK",
        "GENERIC_OR_LEXICAL_TITLE_USE",
        "AUTHOR_COLLISION_DIFFERENT_PERSON",
        "TITLE_AUTHOR_UNLINKED_COOCCURRENCE",
        "WRONG_WORK_SAME_AUTHOR",
        "ALIAS_NOT_TARGET_EQUIVALENT",
        "METADATA_TEXT_ARTIFACT",
        "OTHER",
    },

    "UNCERTAIN": {
        "INSUFFICIENT_CONTEXT",
        "AMBIGUOUS_TARGET_REFERENCE",
    },
}

SHEET_NAMES = [
    f"Audit {i:02d}"
    for i in range(1, 7)
]

# Columns in the completed review workbook.
COL = {
    "review_order": "A",
    "target_title": "B",
    "target_author": "C",
    "openalex_display_name": "D",
    "openalex_abstract": "E",
    "publication_year": "F",
    "publication_date": "G",
    "doi": "H",
    "human_target_attribution_judgment": "I",
    "human_adjudication_confidence": "J",
    "human_attribution_reason_code": "K",
    "human_reviewer_note": "L",
    "baseline_candidate_id": "M",
    "project_work_id": "N",
    "openalex_work_id": "O",
}

CONTEXT_FIELDS = [
    "project_work_id",
    "target_title",
    "target_author",
    "openalex_work_id",
    "openalex_display_name",
    "openalex_abstract",
    "publication_year",
    "publication_date",
    "doi",
]

NS = {
    "m":
        "http://schemas.openxmlformats.org/"
        "spreadsheetml/2006/main",

    "r":
        "http://schemas.openxmlformats.org/"
        "officeDocument/2006/relationships",

    "pr":
        "http://schemas.openxmlformats.org/"
        "package/2006/relationships",
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


def atomic_text(text, path):
    tmp = path.with_name(
        path.name + ".tmp"
    )

    tmp.write_text(
        text,
        encoding="utf-8",
    )

    os.replace(tmp, path)


def atomic_json(obj, path):
    atomic_text(
        json.dumps(
            obj,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        path,
    )


def normalize_text(x):
    if x is None:
        return ""

    x = (
        str(x)
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    return x


def canonicalize_context_text(x):
    """
    Normalize representation-only differences introduced by
    TSV -> XLSX serialization while preserving substantive text.
    """
    x = normalize_text(x)

    # Literal backslash-n in frozen TSV versus real newline in XLSX.
    x = x.replace("\\n", "\n")

    # Soft hyphen is a discretionary formatting character.
    x = x.replace("\u00ad ", "").replace("\u00ad", "")

    # Decorative long dash rules can vary in length through spreadsheet
    # serialization. Collapse runs of 3+ en/em dashes only.
    import re
    x = re.sub(r"[–—]{3,}", "<DASH_RULE>", x)

    return x


def load_shared_strings(z):
    name = "xl/sharedStrings.xml"

    if name not in z.namelist():
        return []

    root = ET.fromstring(
        z.read(name)
    )

    values = []

    for si in root.findall(
        "m:si",
        NS,
    ):
        text = "".join(
            t.text or ""
            for t in si.findall(
                ".//m:t",
                NS,
            )
        )

        values.append(text)

    return values


def workbook_sheet_targets(z):
    workbook = ET.fromstring(
        z.read(
            "xl/workbook.xml"
        )
    )

    rels = ET.fromstring(
        z.read(
            "xl/_rels/workbook.xml.rels"
        )
    )

    relmap = {}

    for rel in rels.findall(
        "pr:Relationship",
        NS,
    ):
        relmap[
            rel.attrib["Id"]
        ] = rel.attrib["Target"]

    out = {}

    for sheet in workbook.findall(
        "m:sheets/m:sheet",
        NS,
    ):
        name = sheet.attrib["name"]

        rid = sheet.attrib[
            "{"
            + NS["r"]
            + "}id"
        ]

        target = relmap[rid]

        if target.startswith("/"):
            path = target.lstrip("/")
        else:
            path = (
                Path("xl")
                / target
            ).as_posix()

        # Resolve any ../ components.
        parts = []

        for part in path.split("/"):
            if part == "..":
                parts.pop()
            elif (
                part
                and part != "."
            ):
                parts.append(part)

        out[name] = "/".join(
            parts
        )

    return out


def cell_col(ref):
    m = re.match(
        r"([A-Z]+)",
        ref,
    )

    if not m:
        raise ValueError(ref)

    return m.group(1)


def read_sheet_rows(
    z,
    sheet_path,
    shared_strings,
):
    root = ET.fromstring(
        z.read(sheet_path)
    )

    output = {}

    for row in root.findall(
        ".//m:sheetData/m:row",
        NS,
    ):
        row_num = int(
            row.attrib["r"]
        )

        values = {}

        for cell in row.findall(
            "m:c",
            NS,
        ):
            ref = cell.attrib["r"]
            col = cell_col(ref)
            ctype = cell.attrib.get(
                "t",
                "",
            )

            value = ""

            if ctype == "inlineStr":
                value = "".join(
                    t.text or ""
                    for t in cell.findall(
                        ".//m:is/m:t",
                        NS,
                    )
                )

            else:
                v = cell.find(
                    "m:v",
                    NS,
                )

                raw = (
                    ""
                    if v is None
                    else v.text or ""
                )

                if (
                    ctype == "s"
                    and raw != ""
                ):
                    value = (
                        shared_strings[
                            int(raw)
                        ]
                    )

                elif ctype == "b":
                    value = (
                        "TRUE"
                        if raw == "1"
                        else "FALSE"
                    )

                else:
                    value = raw

            values[col] = (
                normalize_text(value)
            )

        output[row_num] = values

    return output


def load_completed_workbook():
    with zipfile.ZipFile(
        SOURCE_XLSX
    ) as z:

        shared = (
            load_shared_strings(z)
        )

        targets = (
            workbook_sheet_targets(z)
        )

        missing_sheets = [
            s
            for s in SHEET_NAMES
            if s not in targets
        ]

        if missing_sheets:
            raise RuntimeError(
                "Missing sheets: "
                + repr(
                    missing_sheets
                )
            )

        records = []

        for batch_no, sheet_name in (
            enumerate(
                SHEET_NAMES,
                start=1,
            )
        ):
            rows = read_sheet_rows(
                z,
                targets[
                    sheet_name
                ],
                shared,
            )

            for excel_row in range(
                6,
                31,
            ):
                cells = rows.get(
                    excel_row,
                    {},
                )

                record = {
                    field:
                        normalize_text(
                            cells.get(
                                col,
                                "",
                            )
                        )
                    for field, col
                    in COL.items()
                }

                record[
                    "review_batch_id"
                ] = (
                    f"R2A1A"
                    f"{batch_no:02d}"
                )

                record[
                    "human_reviewer_id"
                ] = (
                    "haruka_tsutsui"
                )

                # The workbook did not record
                # candidate-level timestamps.
                record[
                    "human_adjudicated_at_utc"
                ] = ""

                records.append(
                    record
                )

    return records


def load_frozen_master():
    with FROZEN_MASTER.open(
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


def main():

    for path in [
        SOURCE_XLSX,
        FROZEN_MASTER,
    ]:
        if not path.exists():
            raise FileNotFoundError(
                path
            )

    source_sha = sha256_file(
        SOURCE_XLSX
    )

    if (
        source_sha
        != EXPECTED_XLSX_SHA256
    ):
        raise RuntimeError(
            "Completed XLSX SHA256 "
            "does not match transferred "
            "source.\n"
            f"expected: "
            f"{EXPECTED_XLSX_SHA256}\n"
            f"actual:   {source_sha}"
        )

    review = (
        load_completed_workbook()
    )

    master = load_frozen_master()

    issues = []

    if len(review) != EXPECTED_ROWS:
        issues.append(
            f"review rows="
            f"{len(review)}"
        )

    if len(master) != EXPECTED_ROWS:
        issues.append(
            f"master rows="
            f"{len(master)}"
        )

    review_ids = [
        r[
            "baseline_candidate_id"
        ]
        for r in review
    ]

    if (
        len(set(review_ids))
        != EXPECTED_ROWS
    ):
        issues.append(
            "candidate IDs are not "
            "150 unique values"
        )

    master_by_id = {
        r[
            "baseline_candidate_id"
        ]:
            r
        for r in master
    }

    if set(review_ids) != set(
        master_by_id
    ):
        issues.append(
            "candidate membership "
            "differs from frozen packet"
        )

    expected_orders = list(
        range(
            1,
            151,
        )
    )

    observed_orders = []

    for r in review:
        raw = (
            r["review_order"]
            .strip()
        )

        try:
            observed_orders.append(
                int(float(raw))
            )
        except Exception:
            issues.append(
                "bad review_order for "
                + r[
                    "baseline_candidate_id"
                ]
                + ": "
                + repr(raw)
            )

    if (
        len(observed_orders)
        == EXPECTED_ROWS
        and observed_orders
        != expected_orders
    ):
        issues.append(
            "review order is not "
            "exactly 1..150"
        )

    # Verify that the human saw the same
    # candidate/context as in the frozen
    # blank packet.
    context_mismatches = []

    for r in review:
        cid = r[
            "baseline_candidate_id"
        ]

        m = master_by_id.get(cid)

        if m is None:
            continue

        for field in CONTEXT_FIELDS:
            left = canonicalize_context_text(
                r.get(
                    field,
                    "",
                )
            )

            right = canonicalize_context_text(
                m.get(
                    field,
                    "",
                )
            )

            # Excel may serialize an
            # integer-looking year as 2001
            # while TSV has 2001.0.
            if field == "publication_year":
                def norm_year(x):
                    x = x.strip()

                    if re.fullmatch(
                        r"\d+\.0",
                        x,
                    ):
                        return x[:-2]

                    return x

                left = norm_year(left)
                right = norm_year(right)

            if left != right:
                context_mismatches.append(
                    {
                        "candidate_id":
                            cid,

                        "field":
                            field,

                        "workbook":
                            left[:200],

                        "frozen":
                            right[:200],
                    }
                )

    if context_mismatches:
        issues.append(
            "context differs from "
            "frozen packet for "
            f"{len(context_mismatches)} "
            "field comparisons"
        )

    missing_judgment = []
    missing_confidence = []
    bad_judgment = []
    bad_confidence = []
    bad_reason = []
    missing_note = []

    for r in review:
        cid = r[
            "baseline_candidate_id"
        ]

        judgment = (
            r[
                "human_target_attribution_judgment"
            ]
            .strip()
        )

        confidence = (
            r[
                "human_adjudication_confidence"
            ]
            .strip()
        )

        reason = (
            r[
                "human_attribution_reason_code"
            ]
            .strip()
        )

        note = (
            r[
                "human_reviewer_note"
            ]
            .strip()
        )

        if not judgment:
            missing_judgment.append(
                cid
            )

        elif (
            judgment
            not in VALID_JUDGMENTS
        ):
            bad_judgment.append(
                (cid, judgment)
            )

        if not confidence:
            missing_confidence.append(
                cid
            )

        elif (
            confidence
            not in VALID_CONFIDENCES
        ):
            bad_confidence.append(
                (cid, confidence)
            )

        if judgment in (
            REASONS_BY_JUDGMENT
        ):
            if (
                reason
                not in
                REASONS_BY_JUDGMENT[
                    judgment
                ]
            ):
                bad_reason.append(
                    (
                        cid,
                        judgment,
                        reason,
                    )
                )

        if (
            judgment
            in {
                "INVALID_TARGET_REFERENCE",
                "UNCERTAIN",
            }
            and not note
        ):
            missing_note.append(
                cid
            )

    if missing_judgment:
        issues.append(
            "missing judgment: "
            + str(
                len(
                    missing_judgment
                )
            )
        )

    if missing_confidence:
        issues.append(
            "missing confidence: "
            + str(
                len(
                    missing_confidence
                )
            )
        )

    if bad_judgment:
        issues.append(
            "invalid judgment values: "
            + str(
                len(
                    bad_judgment
                )
            )
        )

    if bad_confidence:
        issues.append(
            "invalid confidence values: "
            + str(
                len(
                    bad_confidence
                )
            )
        )

    if bad_reason:
        issues.append(
            "reason/judgment mismatch: "
            + str(
                len(
                    bad_reason
                )
            )
        )

    if missing_note:
        issues.append(
            "INVALID/UNCERTAIN rows "
            "without reviewer note: "
            + str(
                len(
                    missing_note
                )
            )
        )

    def count(field):
        out = {}

        for r in review:
            value = (
                r[field]
                .strip()
            )

            out[value] = (
                out.get(
                    value,
                    0,
                )
                + 1
            )

        return dict(
            sorted(
                out.items()
            )
        )

    print(
        "=== R2+A1 BASELINE HUMAN "
        "ADJUDICATION V1 QC ==="
    )

    print(
        "source SHA256:",
        source_sha,
    )

    print(
        "rows:",
        len(review),
    )

    print(
        "unique candidates:",
        len(
            set(
                review_ids
            )
        ),
    )

    print(
        "judgments:",
        count(
            "human_target_attribution_judgment"
        ),
    )

    print(
        "confidence:",
        count(
            "human_adjudication_confidence"
        ),
    )

    print(
        "missing judgments:",
        len(
            missing_judgment
        ),
    )

    print(
        "missing confidence:",
        len(
            missing_confidence
        ),
    )

    print(
        "bad reason mappings:",
        len(
            bad_reason
        ),
    )

    print(
        "missing notes "
        "(INVALID/UNCERTAIN):",
        len(
            missing_note
        ),
    )

    print(
        "context mismatches:",
        len(
            context_mismatches
        ),
    )

    if issues:
        print()
        print("QC STATUS: FAILED")

        for issue in issues:
            print(
                " -",
                issue,
            )

        if context_mismatches:
            print()
            print(
                "First context mismatches:"
            )

            for item in (
                context_mismatches[
                    :10
                ]
            ):
                print(
                    json.dumps(
                        item,
                        ensure_ascii=False,
                    )
                )

        if missing_judgment:
            print()
            print(
                "Missing judgment IDs:",
                missing_judgment[:20],
            )

        if missing_note:
            print()
            print(
                "Missing-note IDs:",
                missing_note[:20],
            )

        sys.exit(1)

    # ------------------------------------------------
    # Passed: write authoritative human-only artifact
    # ------------------------------------------------

    output_fields = [
        "review_batch_id",
        "review_order",
        "baseline_candidate_id",
        "project_work_id",
        "target_title",
        "target_author",
        "openalex_work_id",
        "openalex_display_name",
        "publication_year",
        "publication_date",
        "doi",
        "human_target_attribution_judgment",
        "human_adjudication_confidence",
        "human_attribution_reason_code",
        "human_reviewer_note",
        "human_reviewer_id",
        "human_adjudicated_at_utc",
    ]

    tmp = OUT_TSV.with_name(
        OUT_TSV.name + ".tmp"
    )

    with tmp.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=output_fields,
            delimiter="\t",
            lineterminator="\n",
        )

        writer.writeheader()

        for r in review:
            writer.writerow({
                field:
                    r.get(
                        field,
                        "",
                    )
                for field in output_fields
            })

    os.replace(
        tmp,
        OUT_TSV,
    )

    summary = {
        "release":
            (
                "openalex-r2a1-baseline-"
                "primary-human-"
                "adjudication-v1"
            ),

        "candidate_pairs":
            EXPECTED_ROWS,

        "project_works":
            len({
                r[
                    "project_work_id"
                ]
                for r in review
            }),

        "judgment_counts":
            count(
                "human_target_attribution_judgment"
            ),

        "confidence_counts":
            count(
                "human_adjudication_confidence"
            ),

        "reason_counts":
            count(
                "human_attribution_reason_code"
            ),

        "blind_review": True,

        "llm_candidate_outputs_visible":
            False,

        "candidate_level_timestamp_available":
            False,
    }

    atomic_json(
        summary,
        SUMMARY,
    )

    audit = {
        "status":
            "PASSED",

        "checks": {
            "source_sha256_matches":
                True,

            "exactly_150_rows":
                True,

            "candidate_membership_matches_frozen_packet":
                True,

            "review_order_1_to_150":
                True,

            "context_matches_frozen_packet":
                True,

            "all_judgments_complete":
                True,

            "all_confidences_complete":
                True,

            "all_reason_codes_valid_for_judgment":
                True,

            "negative_or_uncertain_notes_complete":
                True,
        },

        "context_mismatch_count":
            0,
    }

    atomic_json(
        audit,
        AUDIT,
    )

    manifest = {
        "sources": {
            str(
                SOURCE_XLSX.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    SOURCE_XLSX
                ),

            str(
                FROZEN_MASTER.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    FROZEN_MASTER
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
                SUMMARY.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    SUMMARY
                ),

            str(
                AUDIT.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    AUDIT
                ),
        },
    }

    atomic_json(
        manifest,
        MANIFEST,
    )

    print()
    print("QC STATUS: PASSED")

    print(
        "human adjudication TSV:",
        OUT_TSV,
    )

    print(
        "project works:",
        summary[
            "project_works"
        ],
    )


if __name__ == "__main__":
    main()
