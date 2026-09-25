import csv
import re
import unicodedata
from collections import defaultdict, Counter
from pathlib import Path

POP = Path("derived/ol_dump_population_with_scope.tsv")
CAND = Path("derived/goodreads_candidates_v3.tsv")
EV = Path("derived/goodreads_contributor_evidence_v3.tsv")

AUTO = Path("derived/goodreads_auto_matches_v3.tsv")
BASE = Path("derived/goodreads_base_review_v3.tsv")
SUR = Path("derived/goodreads_surname_review_v3.tsv")

OUT = Path("derived/goodreads_resolution_status_v3.tsv")


def norm_text(s):
    s = unicodedata.normalize("NFKD", str(s or "").casefold())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s,]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def person_parts(name):
    s = norm_text(name)

    if not s:
        return "", []

    if "," in s:
        left, right = s.split(",", 1)
        surname = left.strip().split()[0] if left.strip() else ""
        given = right.strip().split()
    else:
        p = s.replace(",", " ").split()
        if not p:
            return "", []
        surname = p[-1]
        given = p[:-1]

    return surname, given


def canonical_person(name):
    surname, given = person_parts(name)
    return " ".join(given + ([surname] if surname else []))


def initial_compatible(a, b):
    if not a or not b:
        return False

    return (
        a == b
        or (len(a) == 1 and b.startswith(a))
        or (len(b) == 1 and a.startswith(b))
    )


def author_quality(ol_name, gr_name):
    os, og = person_parts(ol_name)
    gs, gg = person_parts(gr_name)

    if not os or not gs or os != gs:
        return None

    if canonical_person(ol_name) == canonical_person(gr_name):
        return "EXACT_NAME"

    if og and gg and initial_compatible(og[0], gg[0]):
        return "GIVEN_NAME_COMPATIBLE"

    return "SURNAME_ONLY"


# ------------------------------------------------------------
# 1. Parent population: full frozen source population
# ------------------------------------------------------------

population = {}
pop_fields = None

with POP.open(encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter="\t")
    pop_fields = reader.fieldnames

    for r in reader:
        # Goodreads matching population:
        # keep all frozen OL source records, including out_lang.
        # scope_flag remains available for downstream cohort decisions.
        # conceptual-work deduplication happens downstream.
        population[r["work_key"]] = r

print("source population:", len(population))


# ------------------------------------------------------------
# 2. Candidate rows
# ------------------------------------------------------------

by_ol = defaultdict(list)

with CAND.open(encoding="utf-8") as f:
    for r in csv.DictReader(f, delimiter="\t"):
        by_ol[r["ol_work_key"]].append(r)


title_strength = {
    "WORK_FULL": 4,
    "BOOK_FULL": 3,
    "WORK_BASE": 2,
    "BOOK_BASE": 1,
}


# ------------------------------------------------------------
# 3. Already-fixed layers
# ------------------------------------------------------------

def load_single_rows(path):
    out = {}

    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            out[r["ol_work_key"]] = r

    return out


auto = load_single_rows(AUTO)
base = load_single_rows(BASE)
surname_review = load_single_rows(SUR)


# ------------------------------------------------------------
# 4. Goodreads contributor evidence
# ------------------------------------------------------------

contributors = defaultdict(list)

with EV.open(encoding="utf-8") as f:
    for r in csv.DictReader(f, delimiter="\t"):

        role = (r.get("role_raw") or "").casefold().strip()

        if (
            role == ""
            or role == "author"
            or role.startswith("original author")
        ):
            role_class = "PRIMARY"

        elif "pseud" in role:
            role_class = "PSEUDONYM"

        elif "editor" in role:
            role_class = "EDITOR"

        elif "translat" in role:
            role_class = "TRANSLATOR"

        elif "adapt" in role:
            role_class = "ADAPTER"

        else:
            role_class = "OTHER"

        name = r.get("author_name", "")

        if name:
            contributors[
                r["goodreads_work_id"]
            ].append(
                (name, role_class)
            )


# ------------------------------------------------------------
# 5. Classify unresolved candidate-bearing OL works
# ------------------------------------------------------------

def classify_remaining(rows):

    ol_author = rows[0].get("ol_author_name", "")

    if not norm_text(ol_author):
        return "OL_AUTHOR_MISSING"

    strong_primary = set()
    surname_primary = set()
    nonprimary = set()

    for r in rows:

        gid = r["goodreads_work_id"]

        for gr_name, role_class in contributors.get(gid, []):

            q = author_quality(
                ol_author,
                gr_name,
            )

            if not q:
                continue

            if role_class == "PRIMARY":

                if q in {
                    "EXACT_NAME",
                    "GIVEN_NAME_COMPATIBLE",
                }:
                    strong_primary.add(gid)

                elif q == "SURNAME_ONLY":
                    surname_primary.add(gid)

            else:
                nonprimary.add(
                    (gid, role_class)
                )

    if len(strong_primary) >= 2:
        return "STRONG_PRIMARY_MULTIPLE"

    if len(strong_primary) == 1:
        return "UNIQUE_STRONG_PRIMARY_REMAINDER"

    if surname_primary:
        return "SURNAME_ONLY_REMAINDER"

    if nonprimary:
        return "NONPRIMARY_ROLE_SUPPORT"

    return "NO_AUTHOR_SUPPORT"


# ------------------------------------------------------------
# 6. Build one-row-per-OL-work summary
# ------------------------------------------------------------

summary_fields = [
    "goodreads_resolution_status",
    "goodreads_candidate_count",
    "goodreads_strongest_title_evidence",

    "selected_goodreads_work_id",
    "selected_title_match_type",
    "selected_author_match_quality",
    "selected_goodreads_author",
    "selected_gr_original_title",
    "selected_gr_original_publication_year",

    "review_needed",
]

rows_out = []
counts = Counter()

for work_key, poprow in population.items():

    cand_rows = by_ol.get(work_key, [])

    candidate_count = len(cand_rows)

    if cand_rows:
        strongest = max(
            cand_rows,
            key=lambda r: title_strength.get(
                r.get("title_match_type", ""),
                0,
            ),
        ).get("title_match_type", "")
    else:
        strongest = ""

    selected = None

    if work_key in auto:
        status = "AUTO_MATCH_HIGH"
        selected = auto[work_key]
        review_needed = "0"

    elif work_key in base:
        status = "REVIEW_BASE"
        selected = base[work_key]
        review_needed = "1"

    elif work_key in surname_review:
        status = "REVIEW_SURNAME_ONLY"
        selected = surname_review[work_key]
        review_needed = "1"

    elif not cand_rows:
        status = "NO_TITLE_CANDIDATE"
        review_needed = "0"

    else:
        status = classify_remaining(
            cand_rows
        )
        review_needed = "1"

    counts[status] += 1

    out = dict(poprow)

    out.update({
        "goodreads_resolution_status":
            status,

        "goodreads_candidate_count":
            candidate_count,

        "goodreads_strongest_title_evidence":
            strongest,

        "selected_goodreads_work_id":
            selected.get(
                "goodreads_work_id", ""
            ) if selected else "",

        "selected_title_match_type":
            selected.get(
                "title_match_type", ""
            ) if selected else "",

        "selected_author_match_quality":
            selected.get(
                "author_match_quality", ""
            ) if selected else "",

        "selected_goodreads_author":
            selected.get(
                "matched_goodreads_author", ""
            ) if selected else "",

        "selected_gr_original_title":
            selected.get(
                "gr_original_title", ""
            ) if selected else "",

        "selected_gr_original_publication_year":
            selected.get(
                "gr_original_publication_year", ""
            ) if selected else "",

        "review_needed":
            review_needed,
    })

    rows_out.append(out)


# ------------------------------------------------------------
# 7. Integrity checks
# ------------------------------------------------------------

assert len(population) == 34789, (
    f"Expected frozen source population of 34,789, "
    f"got {len(population)}"
)

assert len(rows_out) == len(population), (
    f"Expected {len(population):,} output rows, "
    f"got {len(rows_out):,}"
)

assert sum(counts.values()) == len(population)

assert counts[
    "UNIQUE_STRONG_PRIMARY_REMAINDER"
] == 0, (
    "Unexpected unique strong-primary "
    "remainders remain."
)

expected_no_title = len(population) - len(by_ol)

assert counts["NO_TITLE_CANDIDATE"] == expected_no_title, (
    f"Expected {expected_no_title:,} NO_TITLE_CANDIDATE rows, "
    f"got {counts['NO_TITLE_CANDIDATE']:,}"
)


# ------------------------------------------------------------
# 8. Write
# ------------------------------------------------------------

fieldnames = list(pop_fields) + summary_fields

with OUT.open(
    "w",
    newline="",
    encoding="utf-8",
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames,
        delimiter="\t",
        extrasaction="ignore",
    )

    writer.writeheader()
    writer.writerows(rows_out)


print("\n=== RESOLUTION STATUS ===")

for status, n in counts.most_common():
    print(f"{status}: {n:,}")

print("\ntotal:", len(rows_out))
print("output:", OUT)
