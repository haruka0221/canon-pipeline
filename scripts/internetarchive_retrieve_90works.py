import json
import random
import re
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

import pandas as pd


# ============================================================
# Configuration
# ============================================================

SRC = Path("derived/literary_visibility_master_90works_v8.tsv")

OUT = Path("derived/internetarchive_candidates_90works.tsv")
PROGRESS = Path("derived/internetarchive_candidates_90works_progress.json")

BASE_URL = "https://archive.org/advancedsearch.php"

ROWS = 50
MAX_PAGES = 200

MAX_RETRIES = 6
BASE_SLEEP = 1.0

FIELDS = [
    "identifier",
    "title",
    "creator",
    "date",
    "year",
    "publisher",
    "subject",
    "description",
    "collection",
    "language",
    "mediatype",
]


# ============================================================
# Helpers
# ============================================================

def clean(x):
    if pd.isna(x):
        return ""
    return str(x).strip()


def ia_escape(s):
    """
    Escape characters that can interfere with IA/Lucene phrase queries.
    """
    s = clean(s)
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    return s


def build_query(title):
    """
    Broad work-centered retrieval.

    Deliberately NO creator restriction:
    we want primary texts + metatexts + adaptations + noise,
    followed by semantic classification.
    """
    t = ia_escape(title)
    return f'title:"{t}" AND mediatype:texts'


def fetch_json(params):
    query_string = urllib.parse.urlencode(
        params,
        doseq=True
    )
    url = BASE_URL + "?" + query_string

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent":
                    "canon-pipeline/IA-literary-visibility-pilot "
                    "(research use)"
                }
            )

            with urllib.request.urlopen(
                req,
                timeout=60
            ) as r:
                return json.loads(
                    r.read().decode("utf-8")
                )

        except urllib.error.HTTPError as e:
            if e.code == 429 or 500 <= e.code < 600:
                wait = min(
                    60,
                    (2 ** (attempt - 1)) + random.random()
                )
                print(
                    f"  HTTP {e.code}; "
                    f"retry {attempt}/{MAX_RETRIES} "
                    f"after {wait:.1f}s"
                )
                time.sleep(wait)
                continue
            raise

        except (
            urllib.error.URLError,
            TimeoutError,
            ConnectionError,
        ) as e:
            wait = min(
                60,
                (2 ** (attempt - 1)) + random.random()
            )
            print(
                f"  network error: {e}; "
                f"retry {attempt}/{MAX_RETRIES} "
                f"after {wait:.1f}s"
            )
            time.sleep(wait)

    raise RuntimeError(
        f"Failed after {MAX_RETRIES} retries: {url}"
    )


def serialize(v):
    if v is None:
        return ""

    if isinstance(v, (list, dict)):
        return json.dumps(
            v,
            ensure_ascii=False
        )

    return str(v)


def save_output(rows):
    if not rows:
        return

    pd.DataFrame(rows).to_csv(
        OUT,
        sep="\t",
        index=False
    )


def save_progress(completed):
    PROGRESS.write_text(
        json.dumps(
            {
                "completed_work_keys": sorted(completed),
                "updated": time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


# ============================================================
# Load 90-work universe
# ============================================================

works = pd.read_csv(SRC, sep="\t")

required = [
    "openlibrary_work_key",
    "selection_title",
    "selection_author",
]

for c in required:
    if c not in works.columns:
        raise KeyError(
            f"Required column missing from {SRC}: {c}"
        )

works = (
    works[required + (
        ["selection_year"]
        if "selection_year" in works.columns
        else []
    )]
    .drop_duplicates("openlibrary_work_key")
    .reset_index(drop=True)
)

print("Works:", len(works))

if len(works) != 90:
    print(
        f"WARNING: expected 90 works, found {len(works)}"
    )


# ============================================================
# Resume existing results
# ============================================================

all_rows = []
completed = set()

if OUT.exists():
    old = pd.read_csv(
        OUT,
        sep="\t",
        dtype=str
    )

    if len(old):
        all_rows = old.to_dict("records")

        if "openlibrary_work_key" in old.columns:
            completed.update(
                old["openlibrary_work_key"]
                .dropna()
                .astype(str)
                .unique()
            )

if PROGRESS.exists():
    try:
        p = json.loads(
            PROGRESS.read_text()
        )
        completed.update(
            p.get(
                "completed_work_keys",
                []
            )
        )
    except Exception as e:
        print(
            "WARNING: could not read progress:",
            e
        )

print("Already completed:", len(completed))
print("Remaining:", len(works) - len(completed))


# ============================================================
# Retrieval
# ============================================================

for i, row in works.iterrows():

    wk = clean(row["openlibrary_work_key"])
    title = clean(row["selection_title"])
    author = clean(row["selection_author"])
    year = clean(row.get("selection_year", ""))

    if wk in completed:
        print(
            f"[{i+1:02d}/{len(works)}] SKIP "
            f"{title} / {author}"
        )
        continue

    query = build_query(title)

    print("\n" + "=" * 100)
    print(
        f"[{i+1:02d}/{len(works)}] "
        f"{title} / {author}"
    )
    print("QUERY:", query)

    seen = set()
    work_rows = []

    page = 1
    num_found_first = None

    while page <= MAX_PAGES:

        params = {
            "q": query,
            "fl[]": FIELDS,
            "rows": ROWS,
            "page": page,
            "output": "json",
        }

        data = fetch_json(params)

        response = data.get(
            "response",
            {}
        )

        docs = response.get(
            "docs",
            []
        )

        num_found = response.get(
            "numFound",
            0
        )

        if num_found_first is None:
            num_found_first = num_found

        print(
            f"  page={page:3d} "
            f"returned={len(docs):3d} "
            f"numFound={num_found}"
        )

        if not docs:
            break

        added = 0

        for d in docs:

            ident = clean(
                d.get("identifier")
            )

            if not ident:
                continue

            if ident in seen:
                continue

            seen.add(ident)
            added += 1

            rec = {
                "openlibrary_work_key": wk,
                "selection_title": title,
                "selection_author": author,
                "selection_year": year,
                "ia_query": query,
                "ia_numfound_reported": num_found_first,
                "ia_identifier": ident,
                "ia_title": serialize(
                    d.get("title")
                ),
                "ia_creator": serialize(
                    d.get("creator")
                ),
                "ia_date": serialize(
                    d.get("date")
                ),
                "ia_year": serialize(
                    d.get("year")
                ),
                "ia_publisher": serialize(
                    d.get("publisher")
                ),
                "ia_subject": serialize(
                    d.get("subject")
                ),
                "ia_description": serialize(
                    d.get("description")
                ),
                "ia_collection": serialize(
                    d.get("collection")
                ),
                "ia_language": serialize(
                    d.get("language")
                ),
                "ia_mediatype": serialize(
                    d.get("mediatype")
                ),
            }

            work_rows.append(rec)

        print(
            f"       unique so far="
            f"{len(seen)} (+{added})"
        )

        # We have exhausted the result set.
        if len(docs) < ROWS:
            break

        page += 1

        # Be polite to IA.
        time.sleep(
            BASE_SLEEP + random.random() * 0.5
        )

    print(
        "UNIQUE IA TEXT OBJECTS:",
        len(work_rows)
    )

    # Important:
    # mark work completed even when retrieval returns zero.
    all_rows.extend(work_rows)
    completed.add(wk)

    save_output(all_rows)
    save_progress(completed)

    # pause between works
    time.sleep(
        BASE_SLEEP + random.random()
    )


# ============================================================
# Final checks
# ============================================================

save_output(all_rows)
save_progress(completed)

if OUT.exists():
    final = pd.read_csv(
        OUT,
        sep="\t"
    )

    print("\n" + "=" * 100)
    print("Created:", OUT)
    print("Rows:", len(final))

    if len(final):
        counts = (
            final.groupby(
                [
                    "selection_title",
                    "selection_author",
                ]
            )["ia_identifier"]
            .nunique()
            .sort_values(
                ascending=False
            )
        )

        print(
            "\nUNIQUE IA OBJECTS PER WORK:"
        )
        print(counts.to_string())

        dup = final.duplicated(
            [
                "openlibrary_work_key",
                "ia_identifier",
            ]
        ).sum()

        print(
            "\nDuplicate work+identifier pairs:",
            dup
        )

        print(
            "\nWorks with >=1 candidate:",
            final["openlibrary_work_key"]
            .nunique()
        )

print(
    "\nCompleted works:",
    len(completed)
)

print("\nIA 90-WORK RETRIEVAL OK")
