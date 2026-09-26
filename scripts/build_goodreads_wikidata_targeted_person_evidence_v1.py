from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]

TRIAGE = ROOT / "derived/goodreads_no_author_singleton_full_v11_temporal_triage.tsv"
GP = ROOT / "derived/goodreads_wikidata_gr_person_evidence_v2.tsv"
CW = ROOT / "derived/crosswalks/work_to_wikidata_v2.parquet"

OUT = ROOT / "derived/goodreads_wikidata_targeted_person_evidence_v1.tsv"


# Manually reviewed after targeted Wikidata API search.
# Only cases with MATCH/high work crosswalk are included here.
CASES = {
    "/works/OL15866097W": {
        "gr_person_name": "Elinor Whitney",
        "gr_person_qid": "Q19879748",
        "relation_to_p50": "SAME_P50",
        "proposed_resolution_status":
            "AUTO_MATCH_WIKIDATA_P50_TARGETED_PERSON",
    },
    "/works/OL2571823W": {
        "gr_person_name": "Eilhart von Oberg",
        "gr_person_qid": "Q70774",
        "relation_to_p50": "SAME_P50",
        "proposed_resolution_status":
            "AUTO_MATCH_WIKIDATA_P50_TARGETED_PERSON",
    },
    "/works/OL19601011W": {
        "gr_person_name": "Jack London",
        "gr_person_qid": "Q45765",
        "relation_to_p50": "UNIQUE_OTHER",
        "proposed_resolution_status":
            "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT",
    },
    "/works/OL2939747W": {
        "gr_person_name": "Henry James",
        "gr_person_qid": "Q170509",
        "relation_to_p50": "UNIQUE_OTHER",
        "proposed_resolution_status":
            "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT",
    },
    "/works/OL7425541W": {
        "gr_person_name": "Henry James",
        "gr_person_qid": "Q170509",
        "relation_to_p50": "UNIQUE_OTHER",
        "proposed_resolution_status":
            "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT",
    },
}


triage = pd.read_csv(
    TRIAGE,
    sep="\t",
    dtype=str,
).fillna("")

gp = pd.read_csv(
    GP,
    sep="\t",
    dtype=str,
).fillna("")

cw = pd.read_parquet(CW).fillna("")


# ------------------------------------------------------------
# Fetch fixed Wikidata QIDs to preserve current source metadata.
# ------------------------------------------------------------

qids = sorted({
    v["gr_person_qid"]
    for v in CASES.values()
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

    t = triage[
        triage["work_key"].eq(wk)
    ]

    assert len(t) == 1
    t = t.iloc[0]

    assert (
        t["temporal_triage"]
        == "TEMPORALLY_PLAUSIBLE_UNRESOLVED"
    )

    g = gp[
        gp["ol_work_key"].eq(wk)
    ]

    assert len(g) == 1
    g = g.iloc[0]

    work_id = wk.replace("/works/", "")

    c = cw[
        cw["ol_work_id"].eq(work_id)
    ]

    assert len(c) == 1
    c = c.iloc[0]

    assert c["decision"] == "MATCH"
    assert c["confidence"] == "high"

    qid = spec["gr_person_qid"]

    e = entities[qid]

    label = (
        e.get("labels", {})
        .get("en", {})
        .get("value", "")
    )

    description = (
        e.get("descriptions", {})
        .get("en", {})
        .get("value", "")
    )

    aliases = [
        z["value"]
        for z in e.get("aliases", {}).get("en", [])
    ]

    p50_qids = {
        z.strip()
        for z in str(
            g["wikidata_p50_qids"]
        ).split("|")
        if z.strip()
    }

    if spec["relation_to_p50"] == "SAME_P50":
        assert qid in p50_qids
    else:
        assert p50_qids
        assert qid not in p50_qids

    assert spec["gr_person_name"] in g[
        "gr_primary_contributors"
    ]

    rows.append({
        "ol_work_key": wk,
        "ol_title": t["ol_title"],
        "ol_author_name": t["ol_author_name"],
        "goodreads_work_id":
            t["goodreads_work_id"],
        "title_match_type":
            t["title_match_type"],
        "gr_primary_contributors":
            g["gr_primary_contributors"],
        "wikidata_work_qid":
            c["wikidata_qid"],
        "wikidata_p50_people":
            g["wikidata_p50_people"],
        "gr_person_name":
            spec["gr_person_name"],
        "gr_person_qid": qid,
        "gr_person_label_en": label,
        "gr_person_description_en": description,
        "gr_person_aliases_en":
            " | ".join(aliases),
        "relation_to_p50":
            spec["relation_to_p50"],
        "crosswalk_decision":
            c["decision"],
        "crosswalk_confidence":
            c["confidence"],
        "evidence_source":
            "WIKIDATA_API_TARGETED_PERSON_LOOKUP",
        "proposed_resolution_status":
            spec["proposed_resolution_status"],
    })


out = pd.DataFrame(rows).sort_values(
    "ol_work_key"
)

assert len(out) == 5

assert (
    out["relation_to_p50"]
    == "SAME_P50"
).sum() == 2

assert (
    out["relation_to_p50"]
    == "UNIQUE_OTHER"
).sum() == 3


out.to_csv(
    OUT,
    sep="\t",
    index=False,
)


print("rows:", len(out))

print("\n=== TARGETED PERSON EVIDENCE ===")
print(
    out[
        [
            "ol_work_key",
            "ol_title",
            "gr_person_name",
            "gr_person_qid",
            "gr_person_label_en",
            "relation_to_p50",
            "wikidata_p50_people",
            "proposed_resolution_status",
        ]
    ].to_string(index=False)
)

print("\noutput:", OUT)
