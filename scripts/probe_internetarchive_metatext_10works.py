import time
from pathlib import Path

import pandas as pd
import requests

SRC = Path("derived/literary_visibility_master_90works_v8.tsv")
OUT = Path("derived/internetarchive_metatext_probe_10works.tsv")

TARGET_TITLES = [
    "The Great Gatsby",
    "Heart of Darkness",
    "Ulysses",
    "The Prisoner of Zenda",
    "Robert Elsmere",
    "Alas",
    "The Good Soldier",
    "Dracula",
    "The Jungle Book",
    "The Awakening",
]

URL = "https://archive.org/advancedsearch.php"
ROWS = 50
MAX_RESULTS = 100

df = pd.read_csv(SRC, sep="\t")

targets = df[df["selection_title"].isin(TARGET_TITLES)][
    [
        "openlibrary_work_key",
        "selection_title",
        "selection_author",
    ]
].copy()

all_rows = []

for _, r in targets.iterrows():

    wk = r["openlibrary_work_key"]
    title = str(r["selection_title"])
    author = str(r["selection_author"])

    # Deliberately omit creator.
    query = f'title:"{title}" AND mediatype:texts'

    print("\n" + "=" * 100)
    print(title, "/", author)
    print("QUERY:", query)

    collected = {}
    page = 1
    num_found = None

    while len(collected) < MAX_RESULTS:

        params = {
            "q": query,
            "fl[]": [
                "identifier",
                "title",
                "creator",
                "date",
                "year",
                "mediatype",
                "language",
                "publisher",
                "subject",
                "description",
                "collection",
            ],
            "rows": ROWS,
            "page": page,
            "output": "json",
        }

        try:
            resp = requests.get(
                URL,
                params=params,
                timeout=60,
                headers={
                    "User-Agent":
                        "canon-pipeline academic research"
                },
            )
            resp.raise_for_status()
            data = resp.json()

        except Exception as e:
            print("ERROR:", repr(e))
            break

        response = data.get("response", {})
        docs = response.get("docs", [])
        num_found = int(response.get("numFound", 0) or 0)

        print(
            f"  page={page:3d} "
            f"returned={len(docs):3d} "
            f"numFound={num_found}"
        )

        if not docs:
            break

        before = len(collected)

        for d in docs:

            identifier = d.get("identifier")

            if not identifier:
                continue

            if identifier in collected:
                continue

            collected[identifier] = {
                "openlibrary_work_key": wk,
                "selection_title": title,
                "selection_author": author,
                "retrieval_query": query,
                "ia_num_found": num_found,
                "ia_identifier": identifier,
                "ia_title": d.get("title"),
                "ia_creator": d.get("creator"),
                "ia_date": d.get("date"),
                "ia_year": d.get("year"),
                "ia_publisher": d.get("publisher"),
                "ia_subject": d.get("subject"),
                "ia_description": d.get("description"),
                "ia_collection": d.get("collection"),
            }

            if len(collected) >= MAX_RESULTS:
                break

        after = len(collected)

        print(
            f"       unique so far={after} "
            f"(+{after-before})"
        )

        if page * ROWS >= num_found:
            break

        if after == before:
            print("       STOP: no new identifiers")
            break

        page += 1
        time.sleep(0.7)

    print(
        "COLLECTED:",
        len(collected),
        "/ numFound:",
        num_found
    )

    all_rows.extend(collected.values())

    time.sleep(0.7)


out = pd.DataFrame(all_rows)

out.to_csv(OUT, sep="\t", index=False)

print("\nCreated:", OUT)
print("Rows:", len(out))

print("\nRESULTS PER WORK:")

summary = (
    out.groupby(
        ["selection_title", "selection_author"],
        dropna=False
    )
    .agg(
        candidates_collected=("ia_identifier", "nunique"),
        reported_numFound=("ia_num_found", "max"),
    )
    .sort_values(
        "reported_numFound",
        ascending=False
    )
)

print(summary.to_string())


print("\nSAMPLE TITLES:")

for title in TARGET_TITLES:

    z = out[out["selection_title"] == title]

    print("\n---", title, "---")

    print(
        z[
            [
                "ia_title",
                "ia_creator",
                "ia_date",
            ]
        ]
        .head(10)
        .to_string(index=False)
    )

print("\nIA METATEXT PROBE OK")
