from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]

V12 = ROOT / "derived/goodreads_resolution_status_v12.tsv"
TRIAGE = ROOT / "derived/goodreads_no_author_singleton_full_v12_temporal_triage.tsv"

OUT = ROOT / "derived/goodreads_wikidata_dual_name_identity_evidence_v1.tsv"


CASES = {
    "/works/OL11888695W": {
        "ol_name": "Dorothy Canfield",
        "gr_name": "Dorothy Canfield Fisher",
        "person_qid": "Q5298346",
    },
    "/works/OL12107549W": {
        "ol_name": "Polly Anne Colver Graff",
        "gr_name": "Anne Colver",
        "person_qid": "Q114233463",
    },
    "/works/OL5408075W": {
        "ol_name": "Gaylord Du Bois",
        "gr_name": "Gaylord DuBois",
        "person_qid": "Q5528851",
    },
    "/works/OL6327626W": {
        "ol_name": "Beirne Lay",
        "gr_name": "Beirne Lay Jr.",
        "person_qid": "Q4881371",
    },
}


v12 = pd.read_csv(
    V12,
    sep="\t",
    dtype=str,
).fillna("")

triage = pd.read_csv(
    TRIAGE,
    sep="\t",
    dtype=str,
).fillna("")


qids = sorted({
    x["person_qid"]
    for x in CASES.values()
})

r = requests.get(
    "https://www.wikidata.org/w/api.php",
    params={
        "action": "wbgetentities",
        "ids": "|".join(qids),
        "props": "labels|descriptions|aliases",
        "languages": "en",
        "format": "json",
    },
    headers={
        "User-Agent":
            "canon-pipeline/1.0 research identity audit"
    },
    timeout=30,
)

r.raise_for_status()
entities = r.json()["entities"]


rows = []

for wk, spec in CASES.items():

    vr = v12[
        v12["work_key"].eq(wk)
    ]

    assert len(vr) == 1
    vr = vr.iloc[0]

    assert (
        vr["goodreads_resolution_status"]
        == "NO_AUTHOR_SUPPORT"
    )

    assert (
        vr["goodreads_candidate_count"]
        == "1"
    )

    tr = triage[
        triage["work_key"].eq(wk)
    ]

    assert len(tr) == 1
    tr = tr.iloc[0]

    assert (
        tr["temporal_triage"]
        == "TEMPORALLY_PLAUSIBLE_UNRESOLVED"
    )

    assert tr["ol_author_name"] == spec["ol_name"]

    assert (
        spec["gr_name"]
        in tr["goodreads_contributors"]
    )

    qid = spec["person_qid"]
    entity = entities[qid]

    label = (
        entity.get("labels", {})
        .get("en", {})
        .get("value", "")
    )

    description = (
        entity.get("descriptions", {})
        .get("en", {})
        .get("value", "")
    )

    aliases = [
        z["value"]
        for z in entity
        .get("aliases", {})
        .get("en", [])
    ]

    rows.append({
        "ol_work_key":
            wk,

        "ol_title":
            tr["ol_title"],

        "ol_author_name":
            spec["ol_name"],

        "goodreads_work_id":
            tr["goodreads_work_id"],

        "title_match_type":
            tr["title_match_type"],

        "gr_original_title":
            tr["gr_original_title"],

        "gr_original_publication_year":
            tr["gr_original_publication_year"],

        "goodreads_contributors":
            tr["goodreads_contributors"],

        "gr_person_name":
            spec["gr_name"],

        "matched_person_qid":
            qid,

        "wikidata_label_en":
            label,

        "wikidata_description_en":
            description,

        "wikidata_aliases_en":
            " | ".join(aliases),

        "identity_relation":
            "SAME_PERSON_QID_DUAL_NAME_SEARCH",

        "evidence_source":
            "WIKIDATA_API_DUAL_NAME_SEARCH_MANUAL_REVIEW",

        "promotion_eligible":
            "1",

        "proposed_resolution_status":
            "AUTO_MATCH_WIKIDATA_DUAL_NAME_IDENTITY",
    })


out = pd.DataFrame(rows).sort_values(
    "ol_work_key"
)

assert len(out) == 4
assert out["ol_work_key"].is_unique

assert (
    out["promotion_eligible"]
    == "1"
).all()

out.to_csv(
    OUT,
    sep="\t",
    index=False,
)


print("rows:", len(out))

print("\n=== DUAL-NAME IDENTITY EVIDENCE ===")
print(
    out[
        [
            "ol_work_key",
            "ol_title",
            "ol_author_name",
            "gr_person_name",
            "matched_person_qid",
            "wikidata_label_en",
            "proposed_resolution_status",
        ]
    ].to_string(index=False)
)

print("\noutput:", OUT)
