from pathlib import Path
import pandas as pd

V5 = Path("derived/goodreads_resolution_status_v5.tsv")
PROMO = Path("derived/goodreads_identity_promotions_redirect_v1.tsv")
OUT = Path("derived/goodreads_resolution_status_v6.tsv")

v5 = pd.read_csv(V5, sep="\t", dtype=str).fillna("")
p = pd.read_csv(PROMO, sep="\t", dtype=str).fillna("")

assert len(v5) == 34789
assert v5["work_key"].is_unique
assert len(p) == 9
assert p["ol_work_key"].is_unique
assert (
    p["proposed_resolution_status"]
    == "AUTO_MATCH_IDENTITY_EVIDENCE"
).all()

out = v5.copy()
out_i = out.set_index("work_key")

assert set(p["ol_work_key"]).issubset(set(out_i.index))

# All 9 redirect-supported cases must still be unresolved in v5.
assert (
    out_i.loc[
        p["ol_work_key"],
        "goodreads_resolution_status",
    ]
    == "NO_AUTHOR_SUPPORT"
).all()


def quality(status):
    return {
        "SAME_PERSON_OL_REDIRECT_DIRECT":
            "IDENTITY_OL_REDIRECT_DIRECT",
        "SAME_PERSON_OL_REDIRECT_ALIAS":
            "IDENTITY_OL_REDIRECT_ALIAS",
    }[status]


for r in p.itertuples(index=False):
    wk = r.ol_work_key

    out_i.at[wk, "goodreads_resolution_status"] = (
        "AUTO_MATCH_IDENTITY_EVIDENCE"
    )
    out_i.at[wk, "selected_goodreads_work_id"] = (
        r.goodreads_work_id
    )
    out_i.at[wk, "selected_title_match_type"] = (
        r.title_match_type
    )
    out_i.at[wk, "selected_author_match_quality"] = (
        quality(r.combined_identity_status)
    )
    out_i.at[wk, "selected_goodreads_author"] = (
        r.resolved_gr_name
    )
    out_i.at[wk, "selected_gr_original_title"] = (
        r.gr_original_title
    )
    out_i.at[wk, "selected_gr_original_publication_year"] = (
        r.gr_original_publication_year
    )
    out_i.at[wk, "review_needed"] = "0"

out = out_i.reset_index()
out.to_csv(OUT, sep="\t", index=False)

print("=== V6 RESOLUTION STATUS ===")
print(
    out["goodreads_resolution_status"]
    .value_counts()
    .to_string()
)

print("\ntotal:", len(out))

print("\n=== IDENTITY AUTO MATCHES BY QUALITY ===")
x = out[
    out["goodreads_resolution_status"]
    == "AUTO_MATCH_IDENTITY_EVIDENCE"
]

print(
    x["selected_author_match_quality"]
    .value_counts()
    .to_string()
)

print("\n=== V5 -> V6 CHANGES ===")
cmp = v5.merge(
    out,
    on="work_key",
    suffixes=("_v5", "_v6"),
    validate="one_to_one",
)

changed = cmp[
    cmp["goodreads_resolution_status_v5"]
    != cmp["goodreads_resolution_status_v6"]
]

print("changed rows:", len(changed))

print(
    changed[
        [
            "work_key",
            "title_v6",
            "author_name_v6",
            "goodreads_resolution_status_v5",
            "goodreads_resolution_status_v6",
            "selected_author_match_quality_v6",
        ]
    ].to_string(index=False)
)

# Integrity checks.
assert len(out) == 34789
assert out["work_key"].is_unique

assert (
    out["goodreads_resolution_status"]
    == "AUTO_MATCH_IDENTITY_EVIDENCE"
).sum() == 208

assert (
    out["goodreads_resolution_status"]
    == "NO_AUTHOR_SUPPORT"
).sum() == 3538

assert (
    out["goodreads_resolution_status"]
    == "REVIEW_GENERIC_AUTHOR_IDENTITY"
).sum() == 1

assert len(changed) == 9

assert (
    changed["selected_author_match_quality_v6"]
    == "IDENTITY_OL_REDIRECT_DIRECT"
).all()

print("\noutput:", OUT)
