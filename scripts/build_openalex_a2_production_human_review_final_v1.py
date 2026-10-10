#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

IN_DIR = (
    ROOT / "derived/openalex_production"
    / "retrieval_a2_production_human_review_queue_v1"
)

IN_TSV = (
    IN_DIR / "openalex_a2_production_human_review_queue_v1.tsv"
)

OUT_DIR = (
    ROOT / "derived/openalex_production"
    / "retrieval_a2_production_human_review_final_v1"
)

OUT_TSV = (
    OUT_DIR / "openalex_a2_production_human_review_final_v1.tsv"
)

OUT_SUMMARY = (
    OUT_DIR / "openalex_a2_production_human_review_final_summary_v1.json"
)

OUT_MANIFEST = (
    OUT_DIR / "openalex_a2_production_human_review_final_v1_manifest.json"
)

CREATED_AT = "2026-10-10"
RELEASE = "openalex-a2-production-human-review-final-v1"


J = {
"OA2PRODV1_92b891b5105a2f1d":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),
"OA2PRODV1_c08b6cf5ab152a74":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),
"OA2PRODV1_d2ea447b11b70b1d":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),
"OA2PRODV1_e4e88cb973d1c6de":
("INVALID_TARGET_REFERENCE","WRONG_WORK_SAME_AUTHOR"),
"OA2PRODV1_f8fad9c6e2e9ca99":
("INVALID_TARGET_REFERENCE","WRONG_WORK_SAME_AUTHOR"),

"OA2PRODV1_8deaad8224fcd9ec":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),
"OA2PRODV1_737e0410ab38f4d5":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),
"OA2PRODV1_14cbcfe235f6db4b":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),
"OA2PRODV1_a8ab4e756caafa02":
("INVALID_TARGET_REFERENCE","TITLE_COLLISION_DIFFERENT_WORK"),
"OA2PRODV1_2b6e1b28e21bd002":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),

"OA2PRODV1_088030ef2011afb4":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),
"OA2PRODV1_aaaed94c3c9d0158":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),
"OA2PRODV1_bb34eadf3c1d1d9a":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),
"OA2PRODV1_de5bd85d614e97b2":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),
"OA2PRODV1_ed445eb7c33db3c3":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),

"OA2PRODV1_62efc10d5412172d":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),
"OA2PRODV1_776768f75cc86a8a":
("UNCERTAIN","INSUFFICIENT_CONTEXT"),
"OA2PRODV1_8941a3712d3d205c":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),
"OA2PRODV1_925e62e292f4f9fe":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),
"OA2PRODV1_da952ecee1befe27":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),

"OA2PRODV1_e3b2987ed67899a6":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),
"OA2PRODV1_46afb568a6887f3c":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),
"OA2PRODV1_eea5bff0f1a2345b":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),
"OA2PRODV1_f7c09f6e466fdde0":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),
"OA2PRODV1_bf7a19fccf5a5e0d":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH"),
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_tsv(df, path):
    tmp = path.with_name(path.name + ".tmp")
    df.to_csv(
        tmp,
        sep="\t",
        index=False,
        lineterminator="\n",
    )
    os.replace(tmp, path)


def write_json(obj, path):
    tmp = path.with_name(path.name + ".tmp")
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


def main():
    if not IN_TSV.exists():
        raise FileNotFoundError(IN_TSV)

    if OUT_DIR.exists():
        raise RuntimeError(f"Output directory exists: {OUT_DIR}")

    df = pd.read_csv(
        IN_TSV,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    assert len(df) == 25
    assert df["production_candidate_id"].is_unique
    assert set(df["production_candidate_id"]) == set(J)

    assert df["human_judgment"].eq("").all()
    assert df["human_reason_code"].eq("").all()
    assert df["human_notes"].eq("").all()

    df["human_judgment"] = [
        J[x][0] for x in df["production_candidate_id"]
    ]

    df["human_reason_code"] = [
        J[x][1] for x in df["production_candidate_id"]
    ]

    df["human_notes"] = (
        "Direct review of frozen blind target/OpenAlex evidence."
    )

    counts = df["human_judgment"].value_counts().to_dict()

    expected = {
        "INVALID_TARGET_REFERENCE": 24,
        "UNCERTAIN": 1,
    }

    assert counts == expected, counts

    OUT_DIR.mkdir(parents=True, exist_ok=False)

    write_tsv(df, OUT_TSV)

    summary = {
        "release": RELEASE,
        "created_at": CREATED_AT,
        "status": "final_direct_review",
        "candidate_rows": 25,
        "project_works": int(df["project_work_id"].nunique()),
        "judgment_counts": expected,
        "valid_count": 0,
        "invalid_count": 24,
        "uncertain_count": 1,
        "uncertain_is_not_invalid": True,
        "note": (
            "Targeted direct review of candidates selected after "
            "a blind LLM first pass; not an independent random "
            "human validation sample."
        ),
    }

    write_json(summary, OUT_SUMMARY)

    manifest = {
        "release": RELEASE,
        "created_at": CREATED_AT,
        "source": {
            str(IN_TSV.relative_to(ROOT)):
                sha256_file(IN_TSV),
        },
        "outputs": {
            str(OUT_TSV.relative_to(ROOT)):
                sha256_file(OUT_TSV),
            str(OUT_SUMMARY.relative_to(ROOT)):
                sha256_file(OUT_SUMMARY),
        },
    }

    write_json(manifest, OUT_MANIFEST)

    print("=== A2 PRODUCTION HUMAN REVIEW FINAL V1 ===")
    print("rows:", len(df))
    print("project works:", df["project_work_id"].nunique())
    print("VALID:", 0)
    print("INVALID:", 24)
    print("UNCERTAIN:", 1)
    print("output:", OUT_DIR)


if __name__ == "__main__":
    main()
