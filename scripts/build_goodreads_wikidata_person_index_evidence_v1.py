from pathlib import Path
import re
import unicodedata

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

TRIAGE = (
    ROOT
    / "derived/goodreads_no_author_singleton_full_v10_temporal_triage.tsv"
)

GP = (
    ROOT
    / "derived/goodreads_wikidata_gr_person_evidence_v2.tsv"
)

CW = (
    ROOT
    / "derived/crosswalks/work_to_wikidata_v2.parquet"
)

IDX = (
    ROOT
    / "derived/goodreads_wikidata_person_name_index_v1.tsv"
)

OUT = (
    ROOT
    / "derived/goodreads_wikidata_person_index_evidence_v1.tsv"
)


TARGETS = [
    "/works/OL1002110W",   # The Besieged City
    "/works/OL1161367W",   # The throne of Saturn
    "/works/OL2343325W",   # The little shepherd of Kingdom Come
    "/works/OL5185419W",   # The flaming sword
]


def compact_norm(s):
    s = unicodedata.normalize(
        "NFKD",
        str(s or ""),
    )
    s = "".join(
        c for c in s
        if not unicodedata.combining(c)
    )
    s = s.casefold()
    return re.sub(
        r"[^a-z0-9]+",
        "",
        s,
    )


t = pd.read_csv(
    TRIAGE,
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

idx = pd.read_csv(
    IDX,
    sep="\t",
    dtype=str,
).fillna("")

idx["_compact"] = (
    idx["target_name"]
    .map(compact_norm)
)


# ------------------------------------------------------------
# 1. Current unresolved target cases
# ------------------------------------------------------------

x = t[
    t["work_key"].isin(TARGETS)
].merge(
    gp,
    left_on="work_key",
    right_on="ol_work_key",
    how="left",
    suffixes=("", "_gp"),
    validate="one_to_one",
)

assert len(x) == 4
assert x["work_key"].is_unique

assert (
    x["goodreads_resolution_status"]
    == "NO_AUTHOR_SUPPORT"
).all()

assert (
    x["goodreads_candidate_count"]
    == "1"
).all()


# ------------------------------------------------------------
# 2. Resolve Goodreads primary contributor names
#    against existing full-dump person-name index
# ------------------------------------------------------------

rows = []

for r in x.itertuples(index=False):

    gr_names = [
        z.strip()
        for z in r.gr_primary_contributors.split("|")
        if z.strip()
    ]

    gr_qids = set()
    matched_rows = []

    for name in gr_names:

        z = idx[
            idx["_compact"].eq(
                compact_norm(name)
            )
        ]

        for rr in z.itertuples(index=False):

            gr_qids.add(rr.qid)

            matched_rows.append(
                f"{name}->{rr.qid}:{rr.wikidata_label}"
            )

    p50_qids = {
        z.strip()
        for z in r.wikidata_p50_qids.split("|")
        if z.strip()
    }

    shared = gr_qids & p50_qids

    if shared:
        person_status = "SAME_P50"

    elif len(gr_qids) == 1:
        person_status = "UNIQUE_OTHER"

    elif len(gr_qids) > 1:
        person_status = "MULTIPLE_CANDIDATES"

    else:
        person_status = "NOT_INDEXED"

    ol_work_id = r.work_key.replace(
        "/works/",
        "",
    )

    c = cw[
        cw["ol_work_id"].eq(ol_work_id)
    ].copy()

    assert len(c) == 1

    c = c.iloc[0]

    assert c["decision"] == "MATCH"
    assert c["confidence"] == "high"
    assert (
        c["wikidata_qid"]
        == r.wikidata_work_qid
    )

    rows.append({
        "ol_work_key":
            r.work_key,

        "ol_title":
            r.ol_title,

        "ol_author_name":
            r.ol_author_name,

        "goodreads_work_id":
            r.goodreads_work_id,

        "title_match_type":
            r.title_match_type,

        "gr_primary_contributors":
            r.gr_primary_contributors,

        "wikidata_work_qid":
            r.wikidata_work_qid,

        "wikidata_p50_qids":
            r.wikidata_p50_qids,

        "wikidata_p50_people":
            r.wikidata_p50_people,

        "resolved_gr_person_qids":
            "|".join(sorted(gr_qids)),

        "shared_p50_qids":
            "|".join(sorted(shared)),

        "person_resolution_status":
            person_status,

        "person_index_evidence":
            " || ".join(matched_rows),

        "crosswalk_decision":
            c["decision"],

        "crosswalk_confidence":
            c["confidence"],
    })


out = pd.DataFrame(rows).sort_values(
    "ol_work_key"
)


# ------------------------------------------------------------
# 3. Expected evidence pattern
# ------------------------------------------------------------

status_by_work = dict(
    zip(
        out["ol_work_key"],
        out["person_resolution_status"],
    )
)

assert status_by_work == {
    "/works/OL1002110W":
        "UNIQUE_OTHER",

    "/works/OL1161367W":
        "UNIQUE_OTHER",

    "/works/OL2343325W":
        "SAME_P50",

    "/works/OL5185419W":
        "UNIQUE_OTHER",
}

assert (
    out["crosswalk_confidence"]
    == "high"
).all()

assert (
    out["resolved_gr_person_qids"]
    != ""
).all()


out.to_csv(
    OUT,
    sep="\t",
    index=False,
)


print("rows:", len(out))

print("\n=== PERSON INDEX EVIDENCE ===")
print(
    out[
        [
            "ol_work_key",
            "ol_title",
            "gr_primary_contributors",
            "wikidata_p50_people",
            "resolved_gr_person_qids",
            "shared_p50_qids",
            "person_resolution_status",
            "crosswalk_confidence",
        ]
    ].to_string(index=False)
)

print("\n=== STATUS ===")
print(
    out["person_resolution_status"]
    .value_counts()
    .to_string()
)

print("\noutput:", OUT)
