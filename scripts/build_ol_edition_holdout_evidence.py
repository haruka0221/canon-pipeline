#!/usr/bin/env python3

import argparse
import json
import re
import time
import unicodedata
from pathlib import Path

import pandas as pd
import requests


USER_AGENT = (
    "canon-pipeline-openlibrary-edition-evidence/1.0 "
    "(research use)"
)


def norm_title(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(
        c for c in s
        if not unicodedata.combining(c)
    )
    s = s.casefold()
    s = s.replace("&", " and ")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def extract_year(s):
    m = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", str(s or ""))
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


def fetch_editions(session, work_id, cache_path):
    if cache_path.exists():
        return json.loads(
            cache_path.read_text(encoding="utf-8")
        )

    entries = []
    offset = 0
    limit = 1000
    reported_size = None

    while True:
        url = (
            f"https://openlibrary.org/works/"
            f"{work_id}/editions.json"
        )

        last = None
        for attempt in range(6):
            try:
                r = session.get(
                    url,
                    params={
                        "limit": limit,
                        "offset": offset,
                    },
                    timeout=60,
                )
                r.raise_for_status()
                data = r.json()
                break
            except Exception as e:
                last = e
                if attempt == 5:
                    raise
                time.sleep(min(30, 2 ** attempt))
        else:
            raise last

        if reported_size is None:
            reported_size = int(data.get("size", 0))

        batch = data.get("entries", []) or []
        entries.extend(batch)

        if not batch:
            break

        offset += len(batch)

        if offset >= reported_size:
            break

        time.sleep(0.2)

    result = {
        "reported_size": reported_size or 0,
        "entries": entries,
    }

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(result, ensure_ascii=False),
        encoding="utf-8",
    )

    return result


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

    return {
        k: ed[k]
        for k in fields
        if k in ed
    }


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
        txt = " ".join(
            text_value(ed.get(field)).split()
        )
        if txt:
            texts.append(txt)

    blob = "\n".join(texts)

    return {
        "translation_of": bool(
            re.search(
                r"\btranslation\s+of\b",
                blob,
                re.I,
            )
        ),
        "abridged_from": bool(
            re.search(
                r"\babridged\s+from\b",
                blob,
                re.I,
            )
        ),
        "adapted_from": bool(
            re.search(
                r"\badapted\s+from\b",
                blob,
                re.I,
            )
        ),
        "based_on": bool(
            re.search(
                r"\bbased\s+on\b",
                blob,
                re.I,
            )
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    args = ap.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    cache_dir = args.outdir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    selected_path = args.outdir / "selected_editions.jsonl"
    coverage_path = args.outdir / "target_coverage.tsv"

    targets = pd.read_csv(
        args.input,
        sep="\t",
        dtype=str,
    ).fillna("")

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
    })

    selected_rows = []
    coverage_rows = []

    for i, r in targets.iterrows():
        tid = str(r["target_id"]).strip()
        title = str(r["title"]).strip()
        author = str(r["author"]).strip()
        year = str(r["year"]).strip()

        print(
            f"[{i+1}/{len(targets)}] "
            f"{tid} | {title}"
        )

        cache_path = cache_dir / f"{tid}.json"

        try:
            data = fetch_editions(
                session,
                tid,
                cache_path,
            )

            editions = data["entries"]
            reported = data["reported_size"]

            exact_title = [
                ed for ed in editions
                if norm_title(ed.get("title", ""))
                == norm_title(title)
            ]

            exact_title_year = [
                ed for ed in exact_title
                if year
                and extract_year(
                    ed.get("publish_date", "")
                ) == year
            ]

            if exact_title_year:
                scope = "TITLE_YEAR_EXACT"
                selected = exact_title_year
            elif exact_title:
                scope = "TITLE_EXACT"
                selected = exact_title
            else:
                scope = "NO_EXACT_TARGET_EDITION"
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
                cleaned = useful_edition(ed)

                selected_rows.append({
                    "target_id": tid,
                    "target_title": title,
                    "target_author": author,
                    "target_year": year,
                    "selection_scope": scope,
                    "edition": cleaned,
                })

                for k in flags:
                    flags[k] = (
                        flags[k]
                        or has_field(ed, k)
                    )

                rf = relation_flags(ed)
                for k in rel:
                    rel[k] = rel[k] or rf[k]

            coverage_rows.append({
                "target_id": tid,
                "title": title,
                "author": author,
                "year": year,
                "reported_editions": reported,
                "fetched_editions": len(editions),
                "truncated": int(
                    len(editions) < reported
                ),
                "exact_title_editions":
                    len(exact_title),
                "exact_title_year_editions":
                    len(exact_title_year),
                "selected_scope": scope,
                "selected_editions": len(selected),
                "has_notes": int(flags["notes"]),
                "has_by_statement":
                    int(flags["by_statement"]),
                "has_full_title":
                    int(flags["full_title"]),
                "has_subtitle":
                    int(flags["subtitle"]),
                "has_work_titles":
                    int(flags["work_titles"]),
                "has_other_titles":
                    int(flags["other_titles"]),
                "has_contributions":
                    int(flags["contributions"]),
                "has_languages":
                    int(flags["languages"]),
                "has_translation_of":
                    int(rel["translation_of"]),
                "has_abridged_from":
                    int(rel["abridged_from"]),
                "has_adapted_from":
                    int(rel["adapted_from"]),
                "has_based_on":
                    int(rel["based_on"]),
                "has_any_source_relation":
                    int(any(rel.values())),
                "error": "",
            })

        except Exception as e:
            is_404 = (
                isinstance(e, requests.HTTPError)
                and e.response is not None
                and e.response.status_code == 404
            )

            failure_scope = (
                "WORK_NOT_FOUND"
                if is_404
                else "FETCH_ERROR"
            )

            coverage_rows.append({
                "target_id": tid,
                "title": title,
                "author": author,
                "year": year,
                "reported_editions": 0,
                "fetched_editions": 0,
                "truncated": 0,
                "exact_title_editions": 0,
                "exact_title_year_editions": 0,
                "selected_scope": failure_scope,
                "selected_editions": 0,
                "has_notes": 0,
                "has_by_statement": 0,
                "has_full_title": 0,
                "has_subtitle": 0,
                "has_work_titles": 0,
                "has_other_titles": 0,
                "has_contributions": 0,
                "has_languages": 0,
                "has_translation_of": 0,
                "has_abridged_from": 0,
                "has_adapted_from": 0,
                "has_based_on": 0,
                "has_any_source_relation": 0,
                "error": f"{type(e).__name__}: {e}",
            })

        time.sleep(0.2)

    with selected_path.open(
        "w",
        encoding="utf-8",
    ) as f:
        for x in selected_rows:
            f.write(
                json.dumps(
                    x,
                    ensure_ascii=False,
                )
                + "\n"
            )

    cov = pd.DataFrame(coverage_rows)
    cov.to_csv(
        coverage_path,
        sep="\t",
        index=False,
    )

    print("\nDONE")
    print("targets:", len(cov))
    print(
        cov["selected_scope"]
        .value_counts(dropna=False)
        .to_string()
    )
    print(
        "with source relation:",
        int(cov["has_any_source_relation"].sum()),
    )
    print(
        "fetch errors:",
        int((cov["selected_scope"] == "FETCH_ERROR").sum()),
    )
    print("selected:", selected_path)
    print("coverage:", coverage_path)


if __name__ == "__main__":
    main()
