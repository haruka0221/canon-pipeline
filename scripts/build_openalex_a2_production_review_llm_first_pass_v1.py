#!/usr/bin/env python3

from pathlib import Path
import hashlib
import json
import os
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

IN_DIR = (
    ROOT / "derived/openalex_production"
    / "retrieval_a2_production_review_input_v1"
)

IN_TSV = (
    IN_DIR / "openalex_a2_production_review_blind_v1.tsv"
)

OUT_DIR = (
    ROOT / "derived/openalex_production"
    / "retrieval_a2_production_review_llm_first_pass_v1"
)

OUT_TSV = (
    OUT_DIR / "openalex_a2_production_review_llm_first_pass_v1.tsv"
)

OUT_SUMMARY = (
    OUT_DIR / "openalex_a2_production_review_llm_first_pass_summary_v1.json"
)

OUT_MANIFEST = (
    OUT_DIR / "openalex_a2_production_review_llm_first_pass_v1_manifest.json"
)

RELEASE = "openalex-a2-production-review-llm-first-pass-v1"
CREATED_AT = "2026-10-10"


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
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


# Blind first pass based only on:
# target title / author + supplied OpenAlex title / abstract / metadata.
#
# No policy features were used.
#
# Values:
#   judgment, reason_code, note

J = {
"OA2PRODV1_92b891b5105a2f1d":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "Bojer is mentioned in discussion of Hamsun; 'life' is generic, with no reference to Bojer's target work."),

"OA2PRODV1_c08b6cf5ab152a74":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "Johan Bojer is mentioned generally; 'life' occurs lexically, not as the target work."),

"OA2PRODV1_d2ea447b11b70b1d":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "Article concerns Hamsun; Bojer is mentioned biographically and 'life' is generic."),

"OA2PRODV1_e4e88cb973d1c6de":
("INVALID_TARGET_REFERENCE","WRONG_WORK_SAME_AUTHOR",
 "Record is about Bojer's Our Kingdom; 'life' occurs only in descriptive prose."),

"OA2PRODV1_f8fad9c6e2e9ca99":
("INVALID_TARGET_REFERENCE","WRONG_WORK_SAME_AUTHOR",
 "Record is about Bojer's The Prisoner Who Sang; 'life' is generic."),

"OA2PRODV1_ab1569eed1c91e63":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "A Grain of Wheat by Toyohiko Kagawa is explicitly listed."),

"OA2PRODV1_08ff76ae11ac7e96":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "Jack Lindsay's 1649 is explicitly discussed."),

"OA2PRODV1_660ec5e64e4d9c2c":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "Jack Lindsay's 1649 is explicitly named."),

"OA2PRODV1_8deaad8224fcd9ec":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "1649 occurs as historical dating; Jack Lindsay is mentioned separately as a later transmitter of the song."),

"OA2PRODV1_737e0410ab38f4d5":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "John Brophy appears in a labor-news context; no evidence identifies the target work Sarah."),

"OA2PRODV1_97ca9a77c393deab":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "Tinbergen's Kleew is the explicit subject of the record."),

"OA2PRODV1_092b6ffce33bf3ad":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "Leonard Merrick's Cynthia is explicitly named."),

"OA2PRODV1_14cbcfe235f6db4b":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "Leonard Merrick is represented by other theatre works; no reference to his Cynthia is established."),

"OA2PRODV1_a8ab4e756caafa02":
("INVALID_TARGET_REFERENCE","TITLE_COLLISION_DIFFERENT_WORK",
 "Clement Wood is cited for The American Uplift in Haiti while the matching title token occurs in Nigger Heaven, a different work."),

"OA2PRODV1_94dbd42df2265494":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "The abstract explicitly identifies Eaton/Onoto Watanna's novel Marion."),

"OA2PRODV1_ad402f4c58c597a9":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "Marion is explicitly discussed as a work by Onoto Watanna."),

"OA2PRODV1_860f0338d7936b48":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "The Knife by Peadar O'Donnell is explicitly discussed."),

"OA2PRODV1_068bee773f96abac":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "The text explicitly identifies Islanders by Peadar O'Donnell."),

"OA2PRODV1_c73fe1e6a11a7c6c":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "O'Donnell's Islanders is explicitly named and discussed."),

"OA2PRODV1_2a56afd21a9a9577":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "Ehrenstein's Tubutsch is explicitly identified and analyzed."),

"OA2PRODV1_aae9a060c25d4f53":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "The record directly analyzes Ehrenstein's Tubutsch."),

"OA2PRODV1_2b6e1b28e21bd002":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "'sometime' is a temporal adverb; the record concerns Herrick's Hock-cart poem, not the target work."),

"OA2PRODV1_088030ef2011afb4":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "'waste' occurs lexically in an article on Taylor/Jonson/Herrick attribution; the target work is not referenced."),

"OA2PRODV1_543c544cf263613b":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "Front matter explicitly lists 'Robert Herrick's Waste: Summary of a Career and an Age'."),

"OA2PRODV1_aaaed94c3c9d0158":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "'waste' is used lexically and Herrick is cited for another poem; no target-work reference."),

"OA2PRODV1_bb34eadf3c1d1d9a":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "Robert Herrick is mentioned in biographical context and 'waste' occurs as an ordinary verb."),

"OA2PRODV1_de5bd85d614e97b2":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "The anthology contains other Herrick material and a separate title containing Waste; no target-work reference."),

"OA2PRODV1_ed445eb7c33db3c3":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "The article discusses other Herrick poems and uses 'waste' lexically; it does not establish the target work."),

"OA2PRODV1_19f34f26f136981b":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "Merlin by Herry Lovelich is explicitly the reviewed work."),

"OA2PRODV1_8b5ff2f730be2be6":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "Henry Watterson's Oddities in Southern Life and Character is explicitly cited."),

"OA2PRODV1_62efc10d5412172d":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "The record is a biography of Vorse and discusses historical strikes; the novel Strike! is not identified."),

"OA2PRODV1_66c7bf26d80ab00b":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "Mary Heaton Vorse's Strike! is explicitly named."),

"OA2PRODV1_776768f75cc86a8a":
("UNCERTAIN","INSUFFICIENT_CONTEXT",
 "The abstract says Vorse transformed Ella May Wiggins into a heroic figure but does not identify the work as Strike!."),

"OA2PRODV1_8941a3712d3d205c":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "Labor bibliography contains strike-related titles and another Vorse work, but not Vorse's Strike!."),

"OA2PRODV1_925e62e292f4f9fe":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "Vorse is mentioned as a journalist in discussion of a historical strike; no target-work reference."),

"OA2PRODV1_da952ecee1befe27":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "Reminiscence metadata names several historical strikes but does not identify the novel Strike!."),

"OA2PRODV1_dd08ba3ab3ac3a84":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "Mary Heaton Vorse's Strike! is explicitly included among the radical novels discussed."),

"OA2PRODV1_e3b2987ed67899a6":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "Vorse appears as a historical figure and strike occurs as a historical event; no reference to her novel Strike!."),

"OA2PRODV1_46afb568a6887f3c":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "Konrad Bercovici and a separate person named Charles Alexander Eastman occur in the same abstract; no target-work reference."),

"OA2PRODV1_eea5bff0f1a2345b":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "Konrad Bercovici and Alexander Goldenweiser are separate referents; no evidence for Bercovici's target work Alexander."),

"OA2PRODV1_f7c09f6e466fdde0":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "The record concerns Bercovici and separately mentions Alexander Woollcott; no target-work reference."),

"OA2PRODV1_bf7a19fccf5a5e0d":
("INVALID_TARGET_REFERENCE","GENERIC_OR_LEXICAL_MATCH",
 "George Morgan is cited in urban-theory context and 'issue' is generic; the target work is not established."),

"OA2PRODV1_750609903fd1cc3a":
("VALID_TARGET_REFERENCE","AUTHOR_AND_WORK_CONTEXT",
 "The abstract explicitly identifies Manfred Schneider's Don Francisco de Goya, providing direct author-and-work context for the target."),

"OA2PRODV1_a3511495b5a30a2c":
("VALID_TARGET_REFERENCE","AUTHOR_AND_WORK_CONTEXT",
 "The abstract explicitly analyzes a novel about Goya by Manfred Schneider."),

"OA2PRODV1_f0dcf56bec7084ae":
("VALID_TARGET_REFERENCE","AUTHOR_AND_WORK_CONTEXT",
 "The abstract explicitly identifies Manfred Schneider's Don Francisco de Goya."),

"OA2PRODV1_016d38410cc75dec":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "Josephina Niggli's Mexican Village is explicitly identified."),

"OA2PRODV1_60dc53dcc28ef8aa":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "The article explicitly discusses Niggli's 1945 novel Mexican Village."),

"OA2PRODV1_78fa6faea85e6354":
("VALID_TARGET_REFERENCE","DIRECT_WORK_REFERENCE",
 "The abstract explicitly contrasts Step Down, Elder Brother with Niggli's Mexican Village."),
}


def main():
    if not IN_TSV.exists():
        raise FileNotFoundError(IN_TSV)

    if OUT_DIR.exists():
        raise RuntimeError(f"Output directory exists: {OUT_DIR}")

    src = pd.read_csv(
        IN_TSV,
        sep="\t",
        dtype=str,
        keep_default_na=False,
    )

    assert len(src) == 48
    assert src["production_candidate_id"].is_unique

    ids = set(src["production_candidate_id"])
    assert ids == set(J), (
        f"ID mismatch: missing={set(J)-ids}, extra={ids-set(J)}"
    )

    # Preserve blind source unchanged.
    assert src["human_judgment"].eq("").all()
    assert src["human_reason_code"].eq("").all()
    assert src["human_notes"].eq("").all()

    out = src.copy()

    out["llm_first_pass_judgment"] = [
        J[x][0]
        for x in out["production_candidate_id"]
    ]

    out["llm_first_pass_reason_code"] = [
        J[x][1]
        for x in out["production_candidate_id"]
    ]

    out["llm_first_pass_note"] = [
        J[x][2]
        for x in out["production_candidate_id"]
    ]

    counts = (
        out["llm_first_pass_judgment"]
        .value_counts()
        .to_dict()
    )

    expected = {
        "INVALID_TARGET_REFERENCE": 24,
        "VALID_TARGET_REFERENCE": 23,
        "UNCERTAIN": 1,
    }

    assert counts == expected, counts

    nonvalid = out.loc[
        ~out["llm_first_pass_judgment"]
        .eq("VALID_TARGET_REFERENCE")
    ].copy()

    assert len(nonvalid) == 25

    OUT_DIR.mkdir(parents=True, exist_ok=False)

    write_tsv(out, OUT_TSV)

    summary = {
        "release": RELEASE,
        "created_at": CREATED_AT,
        "status": "provisional_blind_llm_first_pass",
        "candidate_rows": 48,
        "judgment_counts": expected,
        "nonvalid_rows_requiring_direct_human_review": 25,
        "interpretation": [
            "These are provisional LLM first-pass labels, not human gold-standard judgments.",
            "The frozen production routing policy was not used as adjudication evidence.",
            "All first-pass INVALID and UNCERTAIN cases should receive direct human review.",
            "Production routing policy must not be retuned from these outcomes.",
        ],
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
        "counts": expected,
        "blinding": {
            "policy_features_used": False,
            "candidate_frequency_used": False,
            "external_web_used": False,
        },
    }

    write_json(manifest, OUT_MANIFEST)

    print("=== A2 PRODUCTION REVIEW LLM FIRST PASS V1 ===")
    print("rows:", len(out))
    print("VALID:", expected["VALID_TARGET_REFERENCE"])
    print("INVALID:", expected["INVALID_TARGET_REFERENCE"])
    print("UNCERTAIN:", expected["UNCERTAIN"])
    print("direct human review queue:", len(nonvalid))
    print("output:", OUT_DIR)


if __name__ == "__main__":
    main()
