#!/usr/bin/env python3

import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / "scripts"))
from wikidata_resolver_production import (
    normalize_author,
    normalize_title,
)

DB = Path(
    "/media/hdd1/user/tsutsui/wikidata/"
    "wikidata_local_20260805.sqlite"
)

INFILE = (
    ROOT
    / "derived/goodreads_wikidata_work_author_evidence_v2.tsv"
)

OUTFILE = (
    ROOT
    / "derived/goodreads_wikidata_gr_person_evidence_v2.tsv"
)


def keys_for_name(name):
    return {
        normalize_title(name),
        normalize_title(normalize_author(name)),
    } - {""}


df = pd.read_csv(
    INFILE,
    sep="\t",
    dtype=str,
).fillna("")

con = sqlite3.connect(
    f"file:{DB}?mode=ro",
    uri=True,
)

out = []

for _, r in df.iterrows():

    p50 = {
        x
        for x in r["wikidata_p50_qids"].split("|")
        if x
    }

    gr_names = [
        x.strip()
        for x in r["gr_primary_contributors"].split("|")
        if x.strip()
    ]

    gr_qids = set()

    for name in gr_names:
        for key in keys_for_name(name):

            rows = con.execute(
                """
                SELECT DISTINCT qid
                FROM target_author_matches
                WHERE author_key = ?
                """,
                (key,),
            ).fetchall()

            gr_qids.update(
                qid for (qid,) in rows
            )

    shared = p50 & gr_qids

    if shared:
        status = "GR_RESOLVES_TO_P50"

    elif len(gr_qids) == 1:
        status = "GR_RESOLVES_UNIQUE_OTHER"

    elif len(gr_qids) > 1:
        status = "GR_RESOLVES_MULTIPLE_OTHER"

    else:
        # Important:
        # this existing index was built only for the original
        # target-author key set, so zero does NOT mean
        # Wikidata has no such person.
        status = "GR_NOT_IN_EXISTING_TARGET_INDEX"

    out.append({
        **r.to_dict(),

        "gr_person_candidate_count":
            len(gr_qids),

        "gr_person_candidate_qids":
            "|".join(sorted(gr_qids)),

        "gr_p50_shared_qids":
            "|".join(sorted(shared)),

        "gr_person_resolution_status":
            status,
    })


con.close()

result = pd.DataFrame(out)

result.to_csv(
    OUTFILE,
    sep="\t",
    index=False,
)


print("=== GR PERSON RESOLUTION ===")
print(
    result["gr_person_resolution_status"]
    .value_counts()
    .to_string()
)


print("\n=== UNIQUE OTHER, where P50 supports OL ===")

cols = [
    "ol_title",
    "ol_author_name",
    "gr_primary_contributors",
    "wikidata_p50_people",
    "gr_person_candidate_qids",
]

sample = result[
    (
        result["work_author_evidence_status"]
        == "P50_SUPPORTS_OL_ONLY"
    )
    &
    (
        result["gr_person_resolution_status"]
        == "GR_RESOLVES_UNIQUE_OTHER"
    )
]

print("rows:", len(sample))
print(
    sample[cols]
    .head(30)
    .to_string(index=False)
)

print("\noutput:", OUTFILE)
