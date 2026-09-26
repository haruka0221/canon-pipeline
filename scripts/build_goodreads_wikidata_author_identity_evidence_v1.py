#!/usr/bin/env python3

import json
import re
import sqlite3
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

DB = Path(
    "/media/hdd1/user/tsutsui/wikidata/"
    "wikidata_local_20260805.sqlite"
)

INFILE = (
    ROOT
    / "derived/goodreads_ol_author_identity_evidence_v1.tsv"
)

OUTFILE = (
    ROOT
    / "derived/goodreads_wikidata_author_identity_evidence_v1.tsv"
)


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(
        c for c in s
        if not unicodedata.combining(c)
    )
    s = s.casefold()
    s = re.sub(r"\([^)]*\)", " ", s)

    # "Surname, Given" → "Given Surname"
    if "," in s:
        left, right = s.split(",", 1)
        s = f"{right.strip()} {left.strip()}"

    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def lookup_keys(name):
    raw = str(name or "").strip()

    out = {norm(raw)}

    if "," in raw:
        last, first = raw.split(",", 1)
        out.add(norm(f"{first.strip()} {last.strip()}"))

    return {x for x in out if x}


df = pd.read_csv(
    INFILE,
    sep="\t",
    dtype=str,
).fillna("")

# 今回調べるのはOL evidenceでまだ解決していないものだけ
targets = df[
    df["identity_status"].isin(
        ["UNRESOLVED", "OL_AUTHOR_KEY_AMBIGUOUS"]
    )
].copy()

print("target rows:", len(targets))

con = sqlite3.connect(
    f"file:{DB}?mode=ro",
    uri=True,
)

out = []

for _, r in targets.iterrows():

    ol_name = r["ol_author_name"]

    gr_names = [
        x.strip()
        for x in r["gr_primary_contributors"].split("|")
        if x.strip()
    ]

    # ---------------------------------------------
    # OL author name → candidate Wikidata people
    # ---------------------------------------------
    qids = {}

    for key in lookup_keys(ol_name):

        rows = con.execute(
            """
            SELECT
                m.qid,
                m.matched_text,
                m.source,
                p.label_en,
                p.aliases_en
            FROM target_author_matches m
            JOIN people p
              ON p.qid = m.qid
            WHERE m.author_key = ?
            """,
            (key,),
        ).fetchall()

        for (
            qid,
            matched_text,
            source,
            label,
            aliases_json,
        ) in rows:

            try:
                aliases = json.loads(
                    aliases_json or "[]"
                )
            except Exception:
                aliases = []

            names = [
                x
                for x in [label, *aliases]
                if x
            ]

            qids[qid] = {
                "qid": qid,
                "label": label or "",
                "names": names,
                "matched_text": matched_text or "",
                "source": source or "",
            }

    # ---------------------------------------------
    # Does a candidate person also contain
    # a Goodreads primary contributor name?
    # ---------------------------------------------
    shared = []

    for qid, person in qids.items():

        wikidata_names = {
            norm(x): x
            for x in person["names"]
            if norm(x)
        }

        for gr_name in gr_names:
            ngr = norm(gr_name)

            if ngr and ngr in wikidata_names:
                shared.append({
                    "qid": qid,
                    "gr_name": gr_name,
                    "wikidata_name":
                        wikidata_names[ngr],
                    "label":
                        person["label"],
                })

    shared_qids = sorted({
        x["qid"]
        for x in shared
    })

    if len(shared_qids) == 1:
        status = "SAME_PERSON_WIKIDATA"

        hit = next(
            x for x in shared
            if x["qid"] == shared_qids[0]
        )

        selected_qid = shared_qids[0]
        matched_gr_name = hit["gr_name"]
        matched_wikidata_name = (
            hit["wikidata_name"]
        )
        wikidata_label = hit["label"]

    elif len(shared_qids) > 1:
        status = "AMBIGUOUS_WIKIDATA"
        selected_qid = ""
        matched_gr_name = ""
        matched_wikidata_name = ""
        wikidata_label = ""

    else:
        status = "UNRESOLVED"
        selected_qid = ""
        matched_gr_name = ""
        matched_wikidata_name = ""
        wikidata_label = ""

    out.append({
        "ol_work_key":
            r["ol_work_key"],

        "ol_title":
            r["ol_title"],

        "ol_author_name":
            ol_name,

        "goodreads_work_id":
            r["goodreads_work_id"],

        "gr_primary_contributors":
            r["gr_primary_contributors"],

        "ol_identity_status":
            r["identity_status"],

        "wikidata_identity_status":
            status,

        "wikidata_candidate_count":
            len(qids),

        "wikidata_candidate_qids":
            "|".join(sorted(qids)),

        "selected_person_qid":
            selected_qid,

        "wikidata_label":
            wikidata_label,

        "matched_gr_name":
            matched_gr_name,

        "matched_wikidata_name":
            matched_wikidata_name,
    })


con.close()

result = pd.DataFrame(out)

result.to_csv(
    OUTFILE,
    sep="\t",
    index=False,
)

print("\n=== WIKIDATA IDENTITY STATUS ===")
print(
    result[
        "wikidata_identity_status"
    ].value_counts().to_string()
)

print("\n=== QID CANDIDATE COUNT ===")
print(
    result[
        "wikidata_candidate_count"
    ].value_counts().sort_index().to_string()
)

print("\n=== SAMPLE SAME_PERSON ===")
cols = [
    "ol_author_name",
    "gr_primary_contributors",
    "selected_person_qid",
    "wikidata_label",
]

print(
    result[
        result["wikidata_identity_status"]
        == "SAME_PERSON_WIKIDATA"
    ][cols]
    .head(20)
    .to_string(index=False)
)

print("\noutput:", OUTFILE)
