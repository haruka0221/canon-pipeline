import json
import random
import re
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

import pandas as pd


SRC = Path("derived/literary_visibility_master_90works_v8.tsv")

OUT = Path("derived/internetarchive_candidates_90works_v2.tsv")
SUMMARY = Path("derived/internetarchive_retrieval_summary_90works_v2.tsv")
PROGRESS = Path("derived/internetarchive_retrieval_progress_90works_v2.json")

BASE_URL = "https://archive.org/advancedsearch.php"

ROWS = 50
MAX_PAGES_PRIMARY = 100
MAX_PAGES_BROAD = 200

# Broad title-only retrieval:
# retain all metadata-evidenced candidates + sample up to this many
# otherwise-unfiltered candidates for ambiguity/noise audit.
BROAD_OTHER_CAP = 100

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


def clean(x):
    if x is None:
        return ""

    # Internet Archive metadata can be list-valued
    if isinstance(x, list):
        return " ".join(
            str(v).strip()
            for v in x
            if v is not None and str(v).strip()
        )

    if isinstance(x, dict):
        return json.dumps(
            x,
            ensure_ascii=False
        )

    try:
        if pd.isna(x):
            return ""
    except (TypeError, ValueError):
        pass

    return str(x).strip()


def norm(s):
    s = clean(s).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def ia_escape(s):
    s = clean(s)
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    return s


def author_variants(author):
    """
    Generate conservative author strings for metadata evidence.
    """
    a = norm(author)

    variants = {a}

    parts = a.split()

    if parts:
        variants.add(parts[-1])

    # known Ford spelling issue
    if "ford maddox ford" in a:
        variants.add("ford madox ford")
        variants.add("ford madox hueffer")
        variants.add("madox ford")
        variants.add("hueffer")

    return {
        v for v in variants
        if len(v) >= 4
    }


def metadata_text(doc):
    vals = []

    for field in [
        "creator",
        "title",
        "subject",
        "description",
        "publisher",
    ]:
        v = doc.get(field)

        if isinstance(v, list):
            vals.extend(str(x) for x in v)
        elif v is not None:
            vals.append(str(v))

    return norm(" ".join(vals))


def author_evidence(doc, author):
    text = metadata_text(doc)

    variants = author_variants(author)

    return any(v in text for v in variants)


def creator_evidence(doc, author):
    creator = norm(doc.get("creator", ""))

    variants = author_variants(author)

    return any(v in creator for v in variants)


def build_primary_query(title, author):
    return (
        f'title:"{ia_escape(title)}" '
        f'AND creator:"{ia_escape(author)}" '
        f'AND mediatype:texts'
    )


def build_broad_query(title):
    return (
        f'title:"{ia_escape(title)}" '
        f'AND mediatype:texts'
    )


def fetch_json(params):

    url = BASE_URL + "?" + urllib.parse.urlencode(
        params,
        doseq=True
    )

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
                    2 ** (attempt - 1) + random.random()
                )

                print(
                    f"    HTTP {e.code}; retry "
                    f"{attempt}/{MAX_RETRIES} "
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
                2 ** (attempt - 1) + random.random()
            )

            print(
                f"    network error: {e}; "
                f"retry {attempt}/{MAX_RETRIES} "
                f"after {wait:.1f}s"
            )

            time.sleep(wait)

    raise RuntimeError(
        f"Failed after {MAX_RETRIES} retries"
    )


def search_all(query, max_pages):

    docs_by_id = {}
    reported_numfound = None

    for page in range(1, max_pages + 1):

        params = {
            "q": query,
            "fl[]": FIELDS,
            "rows": ROWS,
            "page": page,
            "output": "json",
        }

        data = fetch_json(params)

        response = data.get("response", {})
        docs = response.get("docs", [])
        numfound = response.get("numFound", 0)

        if reported_numfound is None:
            reported_numfound = numfound

        print(
            f"    page={page:3d} "
            f"returned={len(docs):3d} "
            f"numFound={numfound}"
        )

        if not docs:
            break

        before = len(docs_by_id)

        for d in docs:
            ident = clean(d.get("identifier"))

            if ident:
                docs_by_id[ident] = d

        added = len(docs_by_id) - before

        print(
            f"         unique={len(docs_by_id)} "
            f"(+{added})"
        )

        if len(docs) < ROWS:
            break

        time.sleep(
            BASE_SLEEP + random.random() * 0.5
        )

    return list(docs_by_id.values()), reported_numfound


def serialize(v):

    if v is None:
        return ""

    if isinstance(v, (list, dict)):
        return json.dumps(
            v,
            ensure_ascii=False
        )

    return str(v)


def make_record(
    work,
    doc,
    retrieval_source,
    author_meta_evidence,
    author_creator_evidence,
    broad_sampling_status,
    primary_identifier_set,
):

    ident = clean(doc.get("identifier"))

    return {
        "openlibrary_work_key":
            clean(work["openlibrary_work_key"]),

        "selection_title":
            clean(work["selection_title"]),

        "selection_author":
            clean(work["selection_author"]),

        "selection_year":
            clean(work.get("selection_year", "")),

        "ia_identifier":
            ident,

        "retrieval_source":
            retrieval_source,

        "found_in_primary_query":
            ident in primary_identifier_set,

        "author_metadata_evidence":
            author_meta_evidence,

        "author_creator_evidence":
            author_creator_evidence,

        "broad_sampling_status":
            broad_sampling_status,

        "ia_title":
            serialize(doc.get("title")),

        "ia_creator":
            serialize(doc.get("creator")),

        "ia_date":
            serialize(doc.get("date")),

        "ia_year":
            serialize(doc.get("year")),

        "ia_publisher":
            serialize(doc.get("publisher")),

        "ia_subject":
            serialize(doc.get("subject")),

        "ia_description":
            serialize(doc.get("description")),

        "ia_collection":
            serialize(doc.get("collection")),

        "ia_language":
            serialize(doc.get("language")),

        "ia_mediatype":
            serialize(doc.get("mediatype")),
    }


# ------------------------------------------------------------
# Input
# ------------------------------------------------------------

works = pd.read_csv(SRC, sep="\t")

required = [
    "openlibrary_work_key",
    "selection_title",
    "selection_author",
]

for c in required:
    if c not in works.columns:
        raise KeyError(f"Missing required column: {c}")

keep = required.copy()

if "selection_year" in works.columns:
    keep.append("selection_year")

works = (
    works[keep]
    .drop_duplicates("openlibrary_work_key")
    .reset_index(drop=True)
)

print("Works:", len(works))


# ------------------------------------------------------------
# Resume
# ------------------------------------------------------------

completed = set()
all_rows = []
summary_rows = []

if OUT.exists():

    old = pd.read_csv(
        OUT,
        sep="\t",
        dtype=str
    )

    all_rows = old.to_dict("records")


if SUMMARY.exists():

    old_summary = pd.read_csv(
        SUMMARY,
        sep="\t",
        dtype=str
    )

    summary_rows = old_summary.to_dict("records")

    completed.update(
        old_summary[
            old_summary["retrieval_completed"]
            .astype(str)
            .str.lower()
            .eq("true")
        ]["openlibrary_work_key"]
        .astype(str)
    )


if PROGRESS.exists():

    try:
        p = json.loads(PROGRESS.read_text())

        completed.update(
            p.get("completed_work_keys", [])
        )

    except Exception:
        pass


print("Completed:", len(completed))
print("Remaining:", len(works) - len(completed))


# ------------------------------------------------------------
# Retrieval
# ------------------------------------------------------------

for idx, work in works.iterrows():

    wk = clean(work["openlibrary_work_key"])
    title = clean(work["selection_title"])
    author = clean(work["selection_author"])

    if wk in completed:
        print(
            f"[{idx+1:02d}/{len(works)}] "
            f"SKIP {title}"
        )
        continue

    print("\n" + "=" * 100)
    print(
        f"[{idx+1:02d}/{len(works)}] "
        f"{title} / {author}"
    )

    # ========================================================
    # A. PRIMARY QUERY
    # ========================================================

    primary_query = build_primary_query(
        title,
        author
    )

    print("\n  PRIMARY")
    print("  QUERY:", primary_query)

    primary_docs, primary_numfound = search_all(
        primary_query,
        MAX_PAGES_PRIMARY
    )

    primary_ids = {
        clean(d.get("identifier"))
        for d in primary_docs
        if clean(d.get("identifier"))
    }

    print(
        "  PRIMARY UNIQUE:",
        len(primary_ids)
    )


    # ========================================================
    # B. BROAD QUERY
    # ========================================================

    broad_query = build_broad_query(title)

    print("\n  BROAD")
    print("  QUERY:", broad_query)

    broad_docs, broad_numfound = search_all(
        broad_query,
        MAX_PAGES_BROAD
    )

    print(
        "  BROAD UNIQUE RETRIEVED:",
        len(broad_docs)
    )


    # ========================================================
    # Partition broad candidates
    # ========================================================

    evidenced = []
    other = []

    for d in broad_docs:

        meta_ev = author_evidence(
            d,
            author
        )

        creator_ev = creator_evidence(
            d,
            author
        )

        if meta_ev or creator_ev:
            evidenced.append(
                (d, meta_ev, creator_ev)
            )
        else:
            other.append(
                (d, meta_ev, creator_ev)
            )


    # deterministic random sample
    rng = random.Random(
        f"IA-{wk}-20260821"
    )

    if len(other) > BROAD_OTHER_CAP:
        sampled_other = rng.sample(
            other,
            BROAD_OTHER_CAP
        )
    else:
        sampled_other = other


    print(
        "  BROAD AUTHOR-EVIDENCED:",
        len(evidenced)
    )

    print(
        "  BROAD OTHER:",
        len(other)
    )

    print(
        "  BROAD OTHER RETAINED:",
        len(sampled_other)
    )


    # ========================================================
    # Merge retained candidates
    # ========================================================

    retained = {}

    # Primary records always retained
    for d in primary_docs:

        ident = clean(d.get("identifier"))

        if not ident:
            continue

        retained[ident] = make_record(
            work=work,
            doc=d,
            retrieval_source="primary_query",
            author_meta_evidence=author_evidence(
                d, author
            ),
            author_creator_evidence=creator_evidence(
                d, author
            ),
            broad_sampling_status="not_applicable",
            primary_identifier_set=primary_ids,
        )


    # Broad author-evidenced always retained
    for d, meta_ev, creator_ev in evidenced:

        ident = clean(d.get("identifier"))

        if not ident:
            continue

        source = (
            "primary_and_broad"
            if ident in primary_ids
            else "broad_author_evidenced"
        )

        retained[ident] = make_record(
            work=work,
            doc=d,
            retrieval_source=source,
            author_meta_evidence=meta_ev,
            author_creator_evidence=creator_ev,
            broad_sampling_status="all_retained",
            primary_identifier_set=primary_ids,
        )


    # Broad residual sample
    for d, meta_ev, creator_ev in sampled_other:

        ident = clean(d.get("identifier"))

        if not ident:
            continue

        if ident in retained:
            continue

        retained[ident] = make_record(
            work=work,
            doc=d,
            retrieval_source="broad_other_sample",
            author_meta_evidence=meta_ev,
            author_creator_evidence=creator_ev,
            broad_sampling_status=(
                "sampled"
                if len(other) > BROAD_OTHER_CAP
                else "all_retained"
            ),
            primary_identifier_set=primary_ids,
        )


    work_rows = list(retained.values())

    print(
        "\n  FINAL CANDIDATES FOR LLM:",
        len(work_rows)
    )


    # ========================================================
    # Save
    # ========================================================

    all_rows.extend(work_rows)

    summary_rows.append({
        "openlibrary_work_key": wk,
        "selection_title": title,
        "selection_author": author,

        "primary_numfound_reported":
            primary_numfound,

        "primary_unique_retrieved":
            len(primary_ids),

        "broad_numfound_reported":
            broad_numfound,

        "broad_unique_retrieved":
            len(broad_docs),

        "broad_author_evidenced":
            len(evidenced),

        "broad_other_total":
            len(other),

        "broad_other_retained":
            len(sampled_other),

        "final_candidates_for_llm":
            len(work_rows),

        "retrieval_completed":
            True,
    })


    pd.DataFrame(all_rows).to_csv(
        OUT,
        sep="\t",
        index=False
    )

    pd.DataFrame(summary_rows).to_csv(
        SUMMARY,
        sep="\t",
        index=False
    )

    completed.add(wk)

    PROGRESS.write_text(
        json.dumps(
            {
                "completed_work_keys":
                    sorted(completed)
            },
            indent=2
        )
    )

    time.sleep(
        BASE_SLEEP + random.random()
    )


# ------------------------------------------------------------
# Final report
# ------------------------------------------------------------

print("\n" + "=" * 100)

summary = pd.read_csv(
    SUMMARY,
    sep="\t"
)

candidates = pd.read_csv(
    OUT,
    sep="\t"
)

print("Created:")
print(OUT)
print(SUMMARY)

print("\nCompleted works:", len(summary))

print(
    "Candidates for LLM:",
    len(candidates)
)

print(
    "\nTOTAL BROAD numFound:",
    summary["broad_numfound_reported"].sum()
)

print(
    "TOTAL broad unique actually retrieved:",
    summary["broad_unique_retrieved"].sum()
)

print(
    "TOTAL candidates retained for LLM:",
    summary["final_candidates_for_llm"].sum()
)

print("\nLARGEST BROAD RESULT SETS:")

print(
    summary[
        [
            "selection_title",
            "selection_author",
            "broad_numfound_reported",
            "broad_author_evidenced",
            "broad_other_total",
            "final_candidates_for_llm",
        ]
    ]
    .sort_values(
        "broad_numfound_reported",
        ascending=False
    )
    .head(20)
    .to_string(index=False)
)

print("\nIA 90-WORK RETRIEVAL V2 OK")
