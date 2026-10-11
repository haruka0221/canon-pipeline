#!/usr/bin/env python3

from pathlib import Path
import csv
import hashlib
import importlib.util
import json
import os


ROOT = Path(__file__).resolve().parents[1]

BASE_DIR = (
    ROOT
    / "derived/openalex_production"
    / "retrieval_r2a1_baseline_primary_human_adjudication_v1"
)

EXTRACTOR = (
    ROOT
    / "scripts"
    / "extract_openalex_r2a1_baseline_primary_human_adjudication_v1.py"
)

CORRECTION = (
    BASE_DIR
    / "corrections"
    / "openalex_r2a1_baseline_primary_human_correction_v1.tsv"
)

OUT_TSV = (
    BASE_DIR
    / "openalex_r2a1_baseline_primary_human_adjudication_v1.tsv"
)

SUMMARY = (
    BASE_DIR
    / "openalex_r2a1_baseline_primary_human_adjudication_summary_v1.json"
)

AUDIT = (
    BASE_DIR
    / "openalex_r2a1_baseline_primary_human_adjudication_v1_audit.json"
)

MANIFEST = (
    BASE_DIR
    / "openalex_r2a1_baseline_primary_human_adjudication_v1_manifest.json"
)

EXPECTED_CORRECTION_ID = (
    "OABASEV1_2c9d8b89650a9b04"
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


def write_json(obj, path):
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

    os.replace(tmp, path)


def load_extractor():
    spec = importlib.util.spec_from_file_location(
        "r2a1_extract_v1",
        EXTRACTOR,
    )

    module = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(
        module
    )

    return module


def main():

    m = load_extractor()

    review = m.load_completed_workbook()
    master = m.load_frozen_master()

    assert len(review) == 150
    assert len(master) == 150

    with CORRECTION.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as f:
        corrections = list(
            csv.DictReader(
                f,
                delimiter="\t",
            )
        )

    assert len(corrections) == 1

    c = corrections[0]

    assert (
        c["baseline_candidate_id"]
        == EXPECTED_CORRECTION_ID
    )

    correction_by_id = {
        c["baseline_candidate_id"]: c
    }

    master_by_id = {
        r["baseline_candidate_id"]: r
        for r in master
    }

    # --------------------------------------------------
    # Re-check context.
    # Representation-only differences are canonicalized.
    # Exactly one substantive XLSX/master mismatch is
    # permitted, and only because it has a frozen-source
    # blind correction record.
    # --------------------------------------------------

    substantive_mismatches = []

    for r in review:
        cid = r["baseline_candidate_id"]
        master_row = master_by_id[cid]

        for field in m.CONTEXT_FIELDS:

            left = m.canonicalize_context_text(
                r.get(field, "")
            )

            right = m.canonicalize_context_text(
                master_row.get(field, "")
            )

            if field == "publication_year":

                def norm_year(x):
                    x = x.strip()

                    if (
                        x.endswith(".0")
                        and x[:-2].isdigit()
                    ):
                        return x[:-2]

                    return x

                left = norm_year(left)
                right = norm_year(right)

            if left != right:
                substantive_mismatches.append(
                    {
                        "baseline_candidate_id":
                            cid,
                        "field":
                            field,
                    }
                )

    assert substantive_mismatches == [
        {
            "baseline_candidate_id":
                EXPECTED_CORRECTION_ID,

            "field":
                "openalex_abstract",
        }
    ], substantive_mismatches

    # --------------------------------------------------
    # Overlay the independently recorded correction.
    # --------------------------------------------------

    final_rows = []

    for r in review:
        r = dict(r)

        cid = r[
            "baseline_candidate_id"
        ]

        if cid in correction_by_id:
            c = correction_by_id[cid]

            r[
                "human_target_attribution_judgment"
            ] = c[
                "human_target_attribution_judgment"
            ]

            r[
                "human_adjudication_confidence"
            ] = c[
                "human_adjudication_confidence"
            ]

            r[
                "human_attribution_reason_code"
            ] = c[
                "human_attribution_reason_code"
            ]

            r[
                "human_reviewer_note"
            ] = c[
                "human_reviewer_note"
            ]

            r[
                "correction_basis"
            ] = c[
                "correction_basis"
            ]

            r[
                "human_adjudication_source"
            ] = (
                "FROZEN_MASTER_CORRECTION"
            )

        else:
            r[
                "correction_basis"
            ] = ""

            r[
                "human_adjudication_source"
            ] = (
                "COMPLETED_BLIND_XLSX"
            )

        final_rows.append(r)

    # --------------------------------------------------
    # Final semantic QC.
    # --------------------------------------------------

    valid_judgments = (
        m.VALID_JUDGMENTS
    )

    valid_confidences = (
        m.VALID_CONFIDENCES
    )

    reasons_by_judgment = (
        m.REASONS_BY_JUDGMENT
    )

    assert len(final_rows) == 150

    assert len({
        r["baseline_candidate_id"]
        for r in final_rows
    }) == 150

    for r in final_rows:

        judgment = r[
            "human_target_attribution_judgment"
        ].strip()

        confidence = r[
            "human_adjudication_confidence"
        ].strip()

        reason = r[
            "human_attribution_reason_code"
        ].strip()

        note = r[
            "human_reviewer_note"
        ].strip()

        assert judgment in valid_judgments
        assert confidence in valid_confidences

        assert (
            reason
            in reasons_by_judgment[
                judgment
            ]
        )

        if judgment in {
            "INVALID_TARGET_REFERENCE",
            "UNCERTAIN",
        }:
            assert note

    # --------------------------------------------------
    # Counts
    # --------------------------------------------------

    def counts(field):
        out = {}

        for r in final_rows:
            x = r[field].strip()

            out[x] = (
                out.get(x, 0) + 1
            )

        return dict(
            sorted(out.items())
        )

    judgment_counts = counts(
        "human_target_attribution_judgment"
    )

    confidence_counts = counts(
        "human_adjudication_confidence"
    )

    reason_counts = counts(
        "human_attribution_reason_code"
    )

    source_counts = counts(
        "human_adjudication_source"
    )

    # --------------------------------------------------
    # Write final human adjudication TSV.
    # No OpenAlex abstract is duplicated here.
    # --------------------------------------------------

    fields = [
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
        "human_adjudication_source",
        "correction_basis",
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
            fieldnames=fields,
            delimiter="\t",
            lineterminator="\n",
        )

        writer.writeheader()

        for r in final_rows:
            writer.writerow({
                field:
                    r.get(field, "")
                for field in fields
            })

    os.replace(
        tmp,
        OUT_TSV,
    )

    summary = {
        "release":
            "openalex-r2a1-baseline-primary-human-adjudication-v1",

        "candidate_pairs":
            150,

        "project_works":
            len({
                r["project_work_id"]
                for r in final_rows
            }),

        "judgment_counts":
            judgment_counts,

        "confidence_counts":
            confidence_counts,

        "reason_counts":
            reason_counts,

        "human_adjudication_source_counts":
            source_counts,

        "blind_review":
            True,

        "correction_count":
            1,

        "correction_candidate_id":
            EXPECTED_CORRECTION_ID,

        "correction_reason":
            (
                "Substantive OpenAlex abstract mismatch "
                "detected between completed XLSX and "
                "frozen blind packet; candidate was "
                "re-adjudicated from frozen source "
                "before LLM comparison."
            ),
    }

    write_json(
        summary,
        SUMMARY,
    )

    audit = {
        "status":
            "PASSED",

        "checks": {
            "candidate_rows_150":
                True,

            "candidate_ids_unique":
                True,

            "candidate_membership_matches_frozen_packet":
                True,

            "human_judgments_complete":
                True,

            "human_confidences_complete":
                True,

            "reason_codes_valid_for_judgment":
                True,

            "required_notes_complete":
                True,

            "representation_only_context_differences_normalized":
                True,

            "substantive_context_mismatch_count":
                1,

            "all_substantive_context_mismatches_resolved_by_blind_correction":
                True,
        },

        "substantive_context_mismatches": (
            substantive_mismatches
        ),

        "correction_file":
            str(
                CORRECTION.relative_to(
                    ROOT
                )
            ),
    }

    write_json(
        audit,
        AUDIT,
    )

    manifest = {
        "sources": {
            str(
                m.SOURCE_XLSX.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    m.SOURCE_XLSX
                ),

            str(
                m.FROZEN_MASTER.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    m.FROZEN_MASTER
                ),

            str(
                CORRECTION.relative_to(
                    ROOT
                )
            ):
                sha256_file(
                    CORRECTION
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

    write_json(
        manifest,
        MANIFEST,
    )

    print(
        "=== R2+A1 BASELINE FINAL "
        "HUMAN ADJUDICATION V1 ==="
    )

    print(
        "candidate pairs:",
        len(final_rows),
    )

    print(
        "project works:",
        summary[
            "project_works"
        ],
    )

    print(
        "judgments:",
        judgment_counts,
    )

    print(
        "confidence:",
        confidence_counts,
    )

    print(
        "adjudication sources:",
        source_counts,
    )

    print(
        "substantive XLSX context mismatches:",
        len(
            substantive_mismatches
        ),
    )

    print(
        "blind corrections:",
        1,
    )

    print()
    print(
        "QC STATUS: PASSED"
    )


if __name__ == "__main__":
    main()
