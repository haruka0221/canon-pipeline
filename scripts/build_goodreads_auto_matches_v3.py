import csv
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

CAND = Path("derived/goodreads_candidates_v3.tsv")
EV = Path("derived/goodreads_contributor_evidence_v3.tsv")
OUT = Path("derived/goodreads_auto_matches_v3.tsv")


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


# Goodreads work -> PRIMARY contributor names
gr_primary = defaultdict(set)

with EV.open(encoding="utf-8") as f:
    for r in csv.DictReader(f, delimiter="\t"):
        role = (r.get("role_raw") or "").casefold().strip()

        if (
            role == ""
            or role == "author"
            or role.startswith("original author")
        ):
            name = r.get("author_name", "")
            if name:
                gr_primary[r["goodreads_work_id"]].add(name)


rank = {
    "EXACT_NAME": 3,
    "GIVEN_NAME_COMPATIBLE": 2,
    "SURNAME_ONLY": 1,
}


# OL work -> FULL-title candidates having PRIMARY surname support
supported = defaultdict(list)
candidate_fieldnames = None

with CAND.open(encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter="\t")
    candidate_fieldnames = reader.fieldnames

    for r in reader:
        if r["title_match_type"] not in {"WORK_FULL", "BOOK_FULL"}:
            continue

        matches = []

        for gr_name in gr_primary.get(
            r["goodreads_work_id"], set()
        ):
            q = author_quality(
                r.get("ol_author_name", ""),
                gr_name,
            )

            if q:
                # Normalize display whitespace, then choose a
                # deterministic representative among equal-quality names.
                display_name = " ".join(gr_name.split())
                matches.append((q, display_name))

        if not matches:
            continue

        q, gr_name = sorted(
            set(matches),
            key=lambda x: (
                -rank[x[0]],
                x[1].casefold(),
                x[1],
            ),
        )[0]

        r["author_match_quality"] = q
        r["matched_goodreads_author"] = gr_name

        supported[r["ol_work_key"]].append(r)


# Conservative auto-match:
# among FULL-title candidates, exactly one Goodreads work has
# strong PRIMARY-author support (EXACT or GIVEN-compatible).
# Other candidates with only surname support may coexist.
auto = []

for ol_key, rows in supported.items():

    strong_by_gr = {}

    for r in rows:
        if r["author_match_quality"] not in {
            "EXACT_NAME",
            "GIVEN_NAME_COMPATIBLE",
        }:
            continue

        strong_by_gr[r["goodreads_work_id"]] = r

    if len(strong_by_gr) != 1:
        continue

    r = next(iter(strong_by_gr.values()))
    auto.append(r)


# Preserve many-OL-to-one-GR structure.
by_gr = defaultdict(list)

for r in auto:
    by_gr[r["goodreads_work_id"]].append(r)


for r in auto:
    cluster_size = len(
        by_gr[r["goodreads_work_id"]]
    )

    r["match_status"] = "AUTO_MATCH_HIGH"
    r["goodreads_cluster_size"] = cluster_size
    r["conceptual_cluster_candidate"] = (
        1 if cluster_size > 1 else 0
    )


extra_fields = [
    "match_status",
    "author_match_quality",
    "matched_goodreads_author",
    "goodreads_cluster_size",
    "conceptual_cluster_candidate",
]

fieldnames = list(candidate_fieldnames)

for x in extra_fields:
    if x not in fieldnames:
        fieldnames.append(x)


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

    for r in sorted(
        auto,
        key=lambda x: x["ol_work_key"],
    ):
        writer.writerow(r)


print("AUTO_MATCH_HIGH rows:", len(auto))
print("distinct Goodreads works:", len(by_gr))
print(
    "OL rows in multi-OL conceptual cluster candidates:",
    sum(
        len(rs)
        for rs in by_gr.values()
        if len(rs) > 1
    ),
)
print(
    "multi-OL Goodreads clusters:",
    sum(
        1
        for rs in by_gr.values()
        if len(rs) > 1
    ),
)
print("output:", OUT)
