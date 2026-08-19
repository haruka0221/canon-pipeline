import pandas as pd
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

MASTER = Path("derived/literary_visibility_master_90works_v5.tsv")
POP = Path("derived/ol_dump_population_with_scope.tsv")
ED = Path("derived/ol_edition_counts.tsv")

OUT = Path("derived/ol_edition_counts_90works_merged.tsv")
REVIEW = Path("audit/ol_edition_merge_review_90works.tsv")


def norm(s):
    if pd.isna(s) or not str(s).strip():
        return ""

    s = unicodedata.normalize("NFKD", str(s)).lower()

    # possessive apostropheを統一
    s = re.sub(r"[’']s\b", "s", s)

    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\b(the|a|an)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    return s


def author_last(author):
    if pd.isna(author) or not str(author).strip():
        return ""

    author = str(author)

    if "," in author:
        return norm(author.split(",")[0])

    parts = norm(author).split()
    return parts[-1] if parts else ""


master = pd.read_csv(MASTER, sep="\t")
pop = pd.read_csv(POP, sep="\t")
ed = pd.read_csv(ED, sep="\t")

pop = pop.merge(
    ed[["work_key", "edition_count"]],
    on="work_key",
    how="left",
    validate="one_to_one",
)

pop["edition_count"] = (
    pop["edition_count"].fillna(0).astype(int)
)

pop["title_norm"] = pop["title"].map(norm)
pop["author_last_norm"] = pop["author_name"].map(author_last)

summary_rows = []
review_rows = []

for _, t in master.iterrows():

    target_key = t["openlibrary_work_key"]

    # --------------------------------------------------
    # selected Open Library Work を基準にする
    # --------------------------------------------------

    selected = pop[pop["work_key"] == target_key]

    if len(selected) != 1:
        raise RuntimeError(
            f"Selected OL work not uniquely found: {target_key}"
        )

    selected = selected.iloc[0]

    selected_count = int(selected["edition_count"])

    target_title_norm = selected["title_norm"]
    target_author_last = selected["author_last_norm"]

    # selection metadataとの相違は記録する
    selection_title_norm = norm(t["selection_title"])
    selection_author_last = author_last(t["selection_author"])

    metadata_title_mismatch = int(
        selection_title_norm != target_title_norm
    )

    metadata_author_mismatch = int(
        selection_author_last != target_author_last
    )

    # --------------------------------------------------
    # STRICT:
    # selected OL record と
    # normalized title + OL author surname が完全一致
    # --------------------------------------------------

    strict = pop[
        (pop["title_norm"] == target_title_norm)
        & (pop["author_last_norm"] == target_author_last)
    ].copy()

    strict_count = len(strict)

    # 理論上 selected work 自身が必ずここに入る
    if strict_count == 0:
        strict_sum = selected_count
        strict_keys = target_key
        fallback_used = 1
    else:
        strict_sum = int(strict["edition_count"].sum())
        strict_keys = "|".join(strict["work_key"].astype(str))
        fallback_used = 0

    summary_rows.append({
        "openlibrary_work_key": target_key,

        "selection_title": t["selection_title"],
        "selection_author": t["selection_author"],

        "selected_ol_title": selected["title"],
        "selected_ol_author": selected["author_name"],

        "selection_title_mismatch": metadata_title_mismatch,
        "selection_author_mismatch": metadata_author_mismatch,

        "selected_work_edition_count": selected_count,
        "strict_matching_work_count": strict_count,
        "strict_merged_edition_count": strict_sum,

        "additional_editions_from_split_works":
            strict_sum - selected_count,

        "edition_inflation_ratio":
            strict_sum / selected_count
            if selected_count > 0 else None,

        "strict_matching_work_keys": strict_keys,
        "fallback_used": fallback_used,
    })

    # --------------------------------------------------
    # REVIEW ONLY
    # 同著者で似ているが完全一致しないtitle
    # --------------------------------------------------

    same_author = pop[
        pop["author_last_norm"] == target_author_last
    ].copy()

    for _, r in same_author.iterrows():

        if r["title_norm"] == target_title_norm:
            continue

        score = SequenceMatcher(
            None,
            target_title_norm,
            r["title_norm"]
        ).ratio()

        contains = (
            target_title_norm in r["title_norm"]
            or r["title_norm"] in target_title_norm
        )

        if contains or score >= 0.86:
            review_rows.append({
                "openlibrary_work_key": target_key,
                "selection_title": t["selection_title"],
                "selection_author": t["selection_author"],
                "selected_ol_title": selected["title"],
                "selected_ol_author": selected["author_name"],
                "candidate_work_key": r["work_key"],
                "candidate_title": r["title"],
                "candidate_author_name": r["author_name"],
                "candidate_first_publish_year":
                    r.get("first_publish_year", ""),
                "candidate_scope_flag":
                    r.get("scope_flag", ""),
                "candidate_edition_count":
                    r["edition_count"],
                "title_similarity": score,
                "contains_title_norm": int(contains),
                "manual_include": "",
                "manual_note": "",
            })


summary = pd.DataFrame(summary_rows)

summary = summary.sort_values(
    [
        "additional_editions_from_split_works",
        "strict_merged_edition_count",
    ],
    ascending=False,
)

review = pd.DataFrame(review_rows)

summary.to_csv(
    OUT,
    sep="\t",
    index=False,
)

review.to_csv(
    REVIEW,
    sep="\t",
    index=False,
)

print("Created:", OUT)
print("Created:", REVIEW)
print()

print("90 works:", len(summary))
print(
    "Works with >1 strict matching OL Work:",
    int((summary["strict_matching_work_count"] > 1).sum())
)
print(
    "Fallback used:",
    int(summary["fallback_used"].sum())
)
print(
    "Selection title mismatches:",
    int(summary["selection_title_mismatch"].sum())
)
print(
    "Selection author mismatches:",
    int(summary["selection_author_mismatch"].sum())
)
print(
    "Additional editions recovered:",
    int(summary["additional_editions_from_split_works"].sum())
)

print("\nLargest changes:")
print(
    summary[
        [
            "selection_title",
            "selection_author",
            "selected_ol_title",
            "selected_ol_author",
            "selected_work_edition_count",
            "strict_matching_work_count",
            "strict_merged_edition_count",
            "additional_editions_from_split_works",
        ]
    ]
    .head(30)
    .to_string(index=False)
)

print("\nSelection metadata mismatches:")
print(
    summary[
        (summary["selection_title_mismatch"] == 1)
        | (summary["selection_author_mismatch"] == 1)
    ][
        [
            "openlibrary_work_key",
            "selection_title",
            "selection_author",
            "selected_ol_title",
            "selected_ol_author",
            "selection_title_mismatch",
            "selection_author_mismatch",
        ]
    ].to_string(index=False)
)

print("\nReview-only non-exact candidates:", len(review))
