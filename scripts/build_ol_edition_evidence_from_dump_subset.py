#!/usr/bin/env python3

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import pandas as pd


def norm_title(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.casefold()
    s = s.replace("&", " and ")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def extract_year(s):
    m = re.search(
        r"\b(1[5-9]\d{2}|20\d{2})\b",
        str(s or "")
    )
    return m.group(1) if m else ""


def text_value(v):
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return str(v.get("value", ""))
    if isinstance(v, list):
        return " | ".join(map(str, v))
    return str(v)


def useful_edition(ed):
    fields = [
        "key",
        "title",
        "full_title",
        "subtitle",
        "publish_date",
        "publishers",
        "languages",
        "authors",
        "by_statement",
        "contributions",
        "edition_name",
        "work_titles",
        "other_titles",
        "notes",
        "series",
        "lccn",
        "oclc_numbers",
        "ocaid",
        "source_records",
        "lc_classifications",
    ]
    return {k: ed[k] for k in fields if k in ed}


def has_field(ed, field):
    v = ed.get(field)
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, dict)):
        return bool(v)
    return True


def relation_flags(ed):
    texts = []

    for field in [
        "title",
        "full_title",
        "subtitle",
        "by_statement",
        "notes",
    ]:
        txt = " ".join(text_value(ed.get(field)).split())
        if txt:
            texts.append(txt)

    blob = "\n".join(texts)

    return {
        "translation_of": bool(
            re.search(r"\btranslation\s+of\b", blob, re.I)
        ),
        "abridged_from": bool(
            re.search(r"\babridged\s+from\b", blob, re.I)
        ),
        "adapted_from": bool(
            re.search(r"\badapted\s+from\b", blob, re.I)
        ),
        "based_on": bool(
            re.search(r"\bbased\s+on\b", blob, re.I)
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", type=Path, required=True)
    ap.add_argument("--subset", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    args = ap.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    targets_df = pd.read_csv(
        args.targets,
        sep="\t",
        dtype=str,
    ).fillna("")

    targets = {
        r["target_id"]: {
            "target_id": r["target_id"],
            "title": r["title"],
            "author": r["author"],
            "year": r["year"],
        }
        for _, r in targets_df.iterrows()
    }

    linked_count = defaultdict(int)
    exact_title = defaultdict(list)
    exact_title_year = defaultdict(list)

    with args.subset.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            row = json.loads(line)
            ed = row["edition"]

            for tid in row["matched_target_ids"]:
                if tid not in targets:
                    continue

                linked_count[tid] += 1

                target = targets[tid]

                if (
                    norm_title(ed.get("title", ""))
                    != norm_title(target["title"])
                ):
                    continue

                cleaned = useful_edition(ed)
                exact_title[tid].append(cleaned)

                if (
                    target["year"]
                    and extract_year(ed.get("publish_date", ""))
                    == target["year"]
                ):
                    exact_title_year[tid].append(cleaned)

    selected_path = args.outdir / "selected_editions.jsonl"
    coverage_path = args.outdir / "target_coverage.tsv"

    coverage_rows = []
    selected_rows = []

    for tid, target in targets.items():
        ey = exact_title_year.get(tid, [])
        et = exact_title.get(tid, [])

        if ey:
            scope = "TITLE_YEAR_EXACT"
            selected = ey
        elif et:
            scope = "TITLE_EXACT"
            selected = et
        elif linked_count.get(tid, 0):
            scope = "NO_EXACT_TARGET_EDITION"
            selected = []
        else:
            scope = "NO_LINKED_EDITION_IN_SUBSET"
            selected = []

        flags = {
            "notes": False,
            "by_statement": False,
            "full_title": False,
            "subtitle": False,
            "work_titles": False,
            "other_titles": False,
            "contributions": False,
            "languages": False,
        }

        rel = {
            "translation_of": False,
            "abridged_from": False,
            "adapted_from": False,
            "based_on": False,
        }

        for ed in selected:
            selected_rows.append({
                "target_id": tid,
                "target_title": target["title"],
                "target_author": target["author"],
                "target_year": target["year"],
                "selection_scope": scope,
                "edition": ed,
            })

            for k in flags:
                flags[k] = flags[k] or has_field(ed, k)

            rf = relation_flags(ed)
            for k in rel:
                rel[k] = rel[k] or rf[k]

        coverage_rows.append({
            "target_id": tid,
            "title": target["title"],
            "author": target["author"],
            "year": target["year"],
            "dump_linked_editions": linked_count.get(tid, 0),
            "exact_title_editions": len(et),
            "exact_title_year_editions": len(ey),
            "selected_scope": scope,
            "selected_editions": len(selected),
            "has_notes": int(flags["notes"]),
            "has_by_statement": int(flags["by_statement"]),
            "has_full_title": int(flags["full_title"]),
            "has_subtitle": int(flags["subtitle"]),
            "has_work_titles": int(flags["work_titles"]),
            "has_other_titles": int(flags["other_titles"]),
            "has_contributions": int(flags["contributions"]),
            "has_languages": int(flags["languages"]),
            "has_translation_of": int(rel["translation_of"]),
            "has_abridged_from": int(rel["abridged_from"]),
            "has_adapted_from": int(rel["adapted_from"]),
            "has_based_on": int(rel["based_on"]),
            "has_any_source_relation": int(any(rel.values())),
        })

    with selected_path.open("w", encoding="utf-8") as f:
        for row in selected_rows:
            f.write(
                json.dumps(row, ensure_ascii=False) + "\n"
            )

    cov = pd.DataFrame(coverage_rows)
    cov.to_csv(
        coverage_path,
        sep="\t",
        index=False,
    )

    print("targets:", len(cov))
    print("\nselected_scope:")
    print(
        cov["selected_scope"]
        .value_counts(dropna=False)
        .to_string()
    )
    print(
        "\ntargets with selected editions:",
        int((cov["selected_editions"] > 0).sum())
    )
    print(
        "selected edition rows:",
        len(selected_rows)
    )
    print(
        "with source relation:",
        int(cov["has_any_source_relation"].sum())
    )
    print("selected:", selected_path)
    print("coverage:", coverage_path)


if __name__ == "__main__":
    main()
