from pathlib import Path
import sqlite3

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

V9 = ROOT / "derived/goodreads_resolution_status_v9.tsv"

META = (
    ROOT
    / "derived/goodreads_no_author_singleton_full_v8.tsv"
)

GP = (
    ROOT
    / "derived/goodreads_wikidata_gr_person_evidence_v2.tsv"
)

CW = (
    ROOT
    / "derived/crosswalks/work_to_wikidata_v2.parquet"
)

DB = Path(
    "/media/hdd1/user/tsutsui/wikidata/"
    "wikidata_local_20260805.sqlite"
)

OUT = (
    ROOT
    / "derived/goodreads_identity_conflicts_wikidata_p50_v2.tsv"
)


# ------------------------------------------------------------
# 1. Load current evidence
# ------------------------------------------------------------

v9 = pd.read_csv(
    V9,
    sep="\t",
    dtype=str,
).fillna("")

meta = pd.read_csv(
    META,
    sep="\t",
    dtype=str,
).fillna("")

gp = pd.read_csv(
    GP,
    sep="\t",
    dtype=str,
).fillna("")

cw = pd.read_parquet(
    CW,
).fillna("")


# ------------------------------------------------------------
# 2. Strong negative identity pattern
#
# Identity evidence is evaluated independently of temporal
# triage:
#
# - Wikidata Work P50 supports OL author
# - Goodreads contributor does not match that P50 person
# - Goodreads contributor resolves uniquely to another person
# ------------------------------------------------------------

x = gp[
    gp["work_author_evidence_status"].eq(
        "P50_SUPPORTS_OL_ONLY"
    )
    & gp["gr_person_resolution_status"].eq(
        "GR_RESOLVES_UNIQUE_OTHER"
    )
].copy()

assert len(x) == 8
assert x["ol_work_key"].is_unique

x = x.rename(
    columns={
        "ol_work_key": "work_key",
    }
)


# ------------------------------------------------------------
# 3. Attach Goodreads singleton candidate metadata
# ------------------------------------------------------------

meta_cols = [
    "work_key",
    "goodreads_work_id",
    "title_match_type",
    "gr_original_title",
    "gr_original_publication_year",
    "goodreads_contributors",
    "source_batch",
]

x = x.merge(
    meta[meta_cols],
    on="work_key",
    how="left",
    validate="one_to_one",
    suffixes=("", "_meta"),
)

assert x["goodreads_work_id_meta"].ne("").all()

# GP and residual metadata must refer to same GR work.
assert (
    x["goodreads_work_id"]
    == x["goodreads_work_id_meta"]
).all()

x["goodreads_work_id"] = x["goodreads_work_id_meta"]
x = x.drop(columns=["goodreads_work_id_meta"])

assert x["title_match_type"].isin(
    ["WORK_FULL", "BOOK_FULL"]
).all()


# ------------------------------------------------------------
# 4. Verify current v9 state
# ------------------------------------------------------------

v9_check = v9[
    [
        "work_key",
        "goodreads_resolution_status",
        "goodreads_candidate_count",
    ]
].rename(
    columns={
        "goodreads_resolution_status":
            "v9_goodreads_resolution_status",
        "goodreads_candidate_count":
            "v9_goodreads_candidate_count",
    }
)

x = x.merge(
    v9_check,
    on="work_key",
    how="left",
    validate="one_to_one",
)

status_counts = (
    x["v9_goodreads_resolution_status"]
    .value_counts()
    .to_dict()
)

assert status_counts == {
    "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT": 7,
    "NO_AUTHOR_SUPPORT": 1,
}

assert (
    x["v9_goodreads_candidate_count"]
    == "1"
).all()


# ------------------------------------------------------------
# 5. Verify high-confidence OL -> Wikidata Work mapping
# ------------------------------------------------------------

crosswalk_rows = []

for r in x.itertuples(index=False):

    ol_work_id = r.work_key.replace(
        "/works/",
        "",
    )

    z = cw[
        cw["ol_work_id"].eq(ol_work_id)
        & cw["wikidata_qid"].eq(
            r.wikidata_work_qid
        )
        & cw["decision"].eq("MATCH")
        & cw["confidence"].eq("high")
    ].copy()

    assert len(z) == 1

    crosswalk_rows.append({
        "work_key":
            r.work_key,
        "crosswalk_decision":
            "MATCH",
        "crosswalk_confidence":
            "high",
    })

crosswalk = pd.DataFrame(
    crosswalk_rows
)

x = x.merge(
    crosswalk,
    on="work_key",
    how="left",
    validate="one_to_one",
)


# ------------------------------------------------------------
# 6. Goodreads person metadata
# ------------------------------------------------------------

con = sqlite3.connect(
    f"file:{DB}?mode=ro",
    uri=True,
)

person_rows = []

for r in x.itertuples(index=False):

    qids = [
        z.strip()
        for z in
        r.gr_person_candidate_qids.split("|")
        if z.strip()
    ]

    assert len(qids) == 1

    gr_qid = qids[0]

    person = con.execute(
        """
        SELECT
            qid,
            label_en,
            description_en,
            aliases_en
        FROM people
        WHERE qid = ?
        """,
        (gr_qid,),
    ).fetchone()

    assert person is not None

    p50_qids = {
        z.strip()
        for z in
        r.wikidata_p50_qids.split("|")
        if z.strip()
    }

    ol_p50_qids = {
        z.strip()
        for z in
        r.ol_matching_p50_qids.split("|")
        if z.strip()
    }

    gr_p50_qids = {
        z.strip()
        for z in
        r.gr_matching_p50_qids.split("|")
        if z.strip()
    }

    assert p50_qids
    assert ol_p50_qids
    assert not gr_p50_qids
    assert gr_qid not in p50_qids

    person_rows.append({
        "work_key":
            r.work_key,
        "gr_person_qid":
            gr_qid,
        "gr_person_label":
            person[1] or "",
        "gr_person_description":
            person[2] or "",
        "gr_person_aliases":
            person[3] or "",
    })

con.close()

persons = pd.DataFrame(
    person_rows
)

x = x.merge(
    persons,
    on="work_key",
    how="left",
    validate="one_to_one",
)


# ------------------------------------------------------------
# 7. Negative identity evidence layer
# ------------------------------------------------------------

out = pd.DataFrame({
    "ol_work_key":
        x["work_key"],

    "ol_title":
        x["ol_title"],

    "ol_author_name":
        x["ol_author_name"],

    "goodreads_work_id":
        x["goodreads_work_id"],

    "title_match_type":
        x["title_match_type"],

    "gr_original_title":
        x["gr_original_title"],

    "gr_original_publication_year":
        x["gr_original_publication_year"],

    "goodreads_contributors":
        x["goodreads_contributors"],

    "source_batch":
        x["source_batch"],

    "wikidata_work_qid":
        x["wikidata_work_qid"],

    "wikidata_p50_people":
        x["wikidata_p50_people"],

    "ol_matching_p50_qids":
        x["ol_matching_p50_qids"],

    "gr_person_qid":
        x["gr_person_qid"],

    "gr_person_label":
        x["gr_person_label"],

    "gr_person_description":
        x["gr_person_description"],

    "crosswalk_decision":
        x["crosswalk_decision"],

    "crosswalk_confidence":
        x["crosswalk_confidence"],

    "v9_resolution_status":
        x["v9_goodreads_resolution_status"],

    "conflict_type":
        "OL_P50_VS_GR_UNIQUE_OTHER_PERSON",

    "proposed_resolution_status":
        "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT",
})

out = out.sort_values(
    "ol_work_key"
)

out.to_csv(
    OUT,
    sep="\t",
    index=False,
)


print("rows:", len(out))

print("\n=== CURRENT V9 STATUS ===")
print(
    out["v9_resolution_status"]
    .value_counts()
    .to_string()
)

print("\n=== 8 IDENTITY CONFLICTS ===")
print(
    out[
        [
            "ol_work_key",
            "ol_title",
            "ol_author_name",
            "wikidata_p50_people",
            "goodreads_contributors",
            "gr_person_qid",
            "gr_person_label",
            "v9_resolution_status",
        ]
    ].to_string(index=False)
)

assert len(out) == 8

assert (
    out["proposed_resolution_status"]
    == "NO_MATCH_WIKIDATA_P50_IDENTITY_CONFLICT"
).all()

assert (
    out["crosswalk_confidence"]
    == "high"
).all()

print("\noutput:", OUT)
