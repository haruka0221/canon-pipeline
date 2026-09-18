#!/usr/bin/env python3

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd


ROOT = Path(
    "derived/benchmark/holdout/"
    "fresh_random100_v6_20260918"
)

TARGETS = ROOT / "targets.tsv"
PACKETS = ROOT / "stage2_packets.jsonl"
EDITIONS = ROOT / "openlibrary_editions/selected_editions.jsonl"
COVERAGE = ROOT / "openlibrary_editions/target_coverage.tsv"

OUTDIR = ROOT / "human_gold"
OUT_MD = OUTDIR / "blind_review_packet.md"
OUT_TSV = OUTDIR / "human_gold.tsv"

OUTDIR.mkdir(parents=True, exist_ok=True)


def read_jsonl(path):
    with path.open(encoding="utf-8") as f:
        return [
            json.loads(line)
            for line in f
            if line.strip()
        ]


def fmt_list(xs):
    if not xs:
        return "—"

    out = []
    for x in xs:
        if isinstance(x, dict):
            if "qid" in x:
                label = x.get("label", "")
                desc = x.get("description", "")
                s = x["qid"]

                if label:
                    s += f" — {label}"
                if desc:
                    s += f" [{desc}]"

                out.append(s)

            elif "key" in x:
                out.append(str(x["key"]))

            elif "text" in x:
                text = str(x.get("text", ""))
                lang = str(x.get("language", ""))

                out.append(
                    f"{text} [{lang}]"
                    if lang else text
                )

            else:
                out.append(
                    json.dumps(
                        x,
                        ensure_ascii=False,
                    )
                )
        else:
            out.append(str(x))

    return "; ".join(out) if out else "—"


def text_value(v):
    if v is None:
        return "—"

    if isinstance(v, dict):
        if "value" in v:
            return str(v["value"])
        return json.dumps(v, ensure_ascii=False)

    if isinstance(v, list):
        return fmt_list(v)

    s = str(v).strip()
    return s or "—"


targets = pd.read_csv(
    TARGETS,
    sep="\t",
    dtype=str,
).fillna("")

coverage = pd.read_csv(
    COVERAGE,
    sep="\t",
    dtype=str,
).fillna("")

coverage_by_id = {
    r["target_id"]: r
    for _, r in coverage.iterrows()
}

packets = {
    x["target_id"]: x
    for x in read_jsonl(PACKETS)
}

editions_by_id = defaultdict(list)

for x in read_jsonl(EDITIONS):
    editions_by_id[x["target_id"]].append(
        x["edition"]
    )


lines = [
    "# Wikidata v6 Fresh Holdout — Prediction-Blind Human Review",
    "",
    "This packet contains no v6 model judgments.",
    "",
    "## Task definition",
    "",
    "For each Open Library target, determine whether a Wikidata item "
    "represents the same underlying conceptual literary work.",
    "",
    "- MATCH: an identifiable Wikidata item represents the same conceptual work.",
    "- NO_MATCH: no appropriate Wikidata work item can be verified.",
    "- AMBIGUOUS: available evidence does not support a unique work-level choice.",
    "",
    "The gold QID may be outside the supplied candidate set. "
    "If external verification finds the correct Wikidata item, record it; "
    "candidate recall will be evaluated separately.",
    "",
    "Identity policy:",
    "",
    "- ordinary translations normally count as the same underlying conceptual work;",
    "- explicit abridgements, adaptations, or works based on another work "
    "are derivative works and should not automatically be identified with the source;",
    "- wording such as edited by, translated by, revised by, or adapted and edited by "
    "does not by itself establish a separate conceptual work;",
    "- edition/recording/publication manifestations should not be preferred over "
    "an identifiable abstract work-level item.",
    "",
    "External Wikidata and bibliographic sources may be consulted. "
    "Do not inspect any v6 prediction while completing the initial review.",
    "",
    "---",
    "",
]


decision_rows = []


for _, target in targets.iterrows():
    tid = target["target_id"]
    packet = packets[tid]
    cov = coverage_by_id[tid]

    order = int(target["review_order"])

    lines += [
        f"## {order}. {target['title']}",
        "",
        f"- target_id: `{tid}`",
        f"- author: {target['author'] or '—'}",
        f"- year: {target['year'] or '—'}",
        f"- supplied candidate count: {packet.get('candidate_count', 0)}",
        f"- Open Library edition status: `{cov['selected_scope']}`",
        "",
    ]

    raw_editions = editions_by_id.get(tid, [])

    lines += [
        "### Open Library edition evidence",
        "",
    ]

    if not raw_editions:
        lines += [
            "No target-matching edition was selected for this target.",
            "",
        ]

    for j, ed in enumerate(raw_editions, 1):
        lines += [
            f"#### Edition {j}: {ed.get('key', '—')}",
            "",
        ]

        edition_fields = [
            ("title", "title"),
            ("full_title", "full title"),
            ("subtitle", "subtitle"),
            ("publish_date", "publication date"),
            ("publishers", "publishers"),
            ("languages", "languages"),
            ("authors", "Open Library authors"),
            ("by_statement", "by statement"),
            ("contributions", "contributions"),
            ("edition_name", "edition name"),
            ("work_titles", "work titles"),
            ("other_titles", "other titles"),
            ("notes", "notes"),
            ("series", "series"),
            ("lccn", "LCCN"),
            ("oclc_numbers", "OCLC"),
            ("ocaid", "Internet Archive ID"),
            ("lc_classifications", "LC classifications"),
        ]

        for key, label in edition_fields:
            if key in ed:
                lines.append(
                    f"- {label}: {text_value(ed[key])}"
                )

        lines.append("")

    lines += [
        "### Supplied Wikidata candidates",
        "",
    ]

    candidates = packet.get("candidates", [])

    if not candidates:
        lines += [
            "No candidates were supplied by the frozen candidate generator.",
            "",
        ]

    for c in candidates:
        lines += [
            f"#### {c['qid']} — {c.get('label', '') or '[no English label]'}",
            "",
            f"- description: {c.get('description', '') or '—'}",
            f"- aliases: {fmt_list(c.get('aliases', []))}",
            f"- stated titles: {fmt_list(c.get('stated_titles', []))}",
            f"- publication dates: {fmt_list(c.get('publication_dates', []))}",
            f"- instance of: {fmt_list(c.get('instance_of', []))}",
            f"- authors: {fmt_list(c.get('authors', []))}",
            "- edition/version/translation of: "
            f"{fmt_list(c.get('edition_or_translation_of', []))}",
            f"- English Wikipedia sitelink: {bool(c.get('has_enwiki', False))}",
            "",
        ]

    lines += [
        "### Human decision",
        "",
        "- decision: ",
        "- selected_qid: ",
        "- acceptable_alternative_qids: ",
        "- issue_codes: ",
        "- confidence: ",
        "- notes/evidence: ",
        "",
        "---",
        "",
    ]

    decision_rows.append({
        "review_order": order,
        "target_id": tid,
        "title": target["title"],
        "author": target["author"],
        "year": target["year"],
        "candidate_count": packet.get(
            "candidate_count", 0
        ),
        "human_decision": "",
        "human_selected_qid": "",
        "human_alternative_qids": "",
        "human_issue_codes": "",
        "human_confidence": "",
        "human_notes": "",
    })


OUT_MD.write_text(
    "\n".join(lines),
    encoding="utf-8",
)

pd.DataFrame(decision_rows).to_csv(
    OUT_TSV,
    sep="\t",
    index=False,
)

print("targets:", len(decision_rows))
print("review packet:", OUT_MD)
print("blank gold:", OUT_TSV)
