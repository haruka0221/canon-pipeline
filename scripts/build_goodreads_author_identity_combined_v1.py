from pathlib import Path
import pandas as pd

OL = Path("derived/goodreads_ol_author_identity_evidence_v1.tsv")
WD = Path("derived/goodreads_wikidata_author_identity_evidence_v1.tsv")
OUT = Path("derived/goodreads_author_identity_combined_v1.tsv")

ol = pd.read_csv(OL, sep="\t", dtype=str).fillna("")
wd = pd.read_csv(WD, sep="\t", dtype=str).fillna("")

assert len(ol) == 1122
assert len(wd) == 1122
assert ol["ol_work_key"].is_unique
assert wd["ol_work_key"].is_unique
assert set(ol["ol_work_key"]) == set(wd["ol_work_key"])

wd_keep = [
    "ol_work_key",
    "wikidata_identity_status",
    "gr_wikidata_candidate_qid_count",
    "corroborated_qid_count",
    "corroborated_qids",
    "matched_qid",
    "matched_gr_target_names",
    "matched_ol_name",
    "matched_ol_name_source",
    "matched_wikidata_name",
    "matched_wikidata_name_source",
    "wikidata_label",
    "wikidata_description",
    "wikidata_occupation_qids",
    "wikidata_birth",
    "wikidata_death",
    "enwiki_title",
]

x = ol.merge(
    wd[wd_keep],
    on="ol_work_key",
    how="left",
    validate="one_to_one",
).fillna("")

def combined_status(r):
    prior = r["identity_status"]
    wd_status = r["wikidata_identity_status"]

    if prior == "DIRECT_NAME_MATCH":
        return "SAME_PERSON_OL_DIRECT"

    if prior == "OL_ALIAS_MATCH":
        return "SAME_PERSON_OL_ALIAS"

    if (
        prior == "UNRESOLVED"
        and wd_status == "SAME_PERSON_WIKIDATA"
    ):
        return "SAME_PERSON_WIKIDATA"

    if prior == "OL_AUTHOR_KEY_AMBIGUOUS":
        return "AMBIGUOUS_OL_AUTHOR_KEY"

    return "UNRESOLVED"

x["combined_identity_status"] = x.apply(combined_status, axis=1)

x["cross_source_corroborated"] = (
    x["identity_status"].isin(
        ["DIRECT_NAME_MATCH", "OL_ALIAS_MATCH"]
    )
    & x["wikidata_identity_status"].eq("SAME_PERSON_WIKIDATA")
)

x["newly_resolved_by_wikidata"] = (
    x["identity_status"].eq("UNRESOLVED")
    & x["wikidata_identity_status"].eq("SAME_PERSON_WIKIDATA")
)

x["resolved_person_qid"] = x["matched_qid"].where(
    x["wikidata_identity_status"].eq("SAME_PERSON_WIKIDATA"),
    "",
)

def resolved_gr_name(r):
    if r["identity_status"] in {
        "DIRECT_NAME_MATCH",
        "OL_ALIAS_MATCH",
    }:
        return r["matched_gr_name"]

    if r["combined_identity_status"] == "SAME_PERSON_WIKIDATA":
        return r["matched_gr_target_names"]

    return ""

def resolved_ol_name(r):
    if r["identity_status"] in {
        "DIRECT_NAME_MATCH",
        "OL_ALIAS_MATCH",
    }:
        return r["matched_ol_name_raw"]

    if r["combined_identity_status"] == "SAME_PERSON_WIKIDATA":
        return r["matched_ol_name"]

    return ""

x["resolved_gr_name"] = x.apply(resolved_gr_name, axis=1)
x["resolved_ol_name"] = x.apply(resolved_ol_name, axis=1)

front = [
    "ol_work_key",
    "ol_title",
    "ol_author_name",
    "goodreads_work_id",
    "gr_primary_contributors",
    "ol_author_key",
    "combined_identity_status",
    "cross_source_corroborated",
    "newly_resolved_by_wikidata",
    "resolved_person_qid",
    "resolved_gr_name",
    "resolved_ol_name",
]

rest = [c for c in x.columns if c not in front]
x = x[front + rest]

x.to_csv(OUT, sep="\t", index=False)

print("=== COMBINED AUTHOR IDENTITY ===")
print(x["combined_identity_status"].value_counts().to_string())

print("\npositive:", int(
    x["combined_identity_status"].str.startswith("SAME_PERSON_").sum()
))
print(
    "cross-source corroborated:",
    int(x["cross_source_corroborated"].sum()),
)
print(
    "newly resolved by Wikidata:",
    int(x["newly_resolved_by_wikidata"].sum()),
)
print(
    "resolved person QIDs:",
    x.loc[
        x["resolved_person_qid"].ne(""),
        "resolved_person_qid",
    ].nunique(),
)

print("\n=== NEW WIKIDATA RESOLUTIONS ===")
print(
    x[x["newly_resolved_by_wikidata"]][
        [
            "ol_title",
            "ol_author_name",
            "gr_primary_contributors",
            "resolved_person_qid",
            "resolved_gr_name",
            "resolved_ol_name",
        ]
    ].to_string(index=False)
)

assert len(x) == 1122
assert (x["combined_identity_status"] == "SAME_PERSON_OL_DIRECT").sum() == 80
assert (x["combined_identity_status"] == "SAME_PERSON_OL_ALIAS").sum() == 103
assert (x["combined_identity_status"] == "SAME_PERSON_WIKIDATA").sum() == 5
assert (x["combined_identity_status"] == "AMBIGUOUS_OL_AUTHOR_KEY").sum() == 22
assert (x["combined_identity_status"] == "UNRESOLVED").sum() == 912
assert x["cross_source_corroborated"].sum() == 38
assert x["newly_resolved_by_wikidata"].sum() == 5

print("\noutput:", OUT)
