from pathlib import Path
import json
import pandas as pd

ROOT = Path("derived/benchmark/judgments")
src = ROOT / "adjudication" / "human_adjudication_packet_12.csv"

df = pd.read_csv(src, dtype=str).fillna("")

out_md = ROOT / "adjudication" / "human_adjudication_blind_12.md"
out_csv = ROOT / "adjudication" / "human_adjudication_decisions_12.csv"

lines = [
    "# Wikidata Human Adjudication — Blind Review",
    "",
    "Target: abstract literary work.",
    "",
    "Allowed decisions: MATCH / NO_MATCH / AMBIGUOUS",
    "",
    "Do not consult the model judgments while making the initial decision.",
    "",
]

decision_rows = []

for n, (_, row) in enumerate(df.iterrows(), start=1):
    candidates = json.loads(row["candidates_json"])

    lines += [
        f"## {n}. {row['title']}",
        "",
        f"- target_id: `{row['target_id']}`",
        f"- author: {row['author']}",
        f"- author_qid: `{row['author_qid']}`",
        f"- candidate_route: `{row['candidate_route']}`",
        "",
        "### Candidates",
        "",
    ]

    for c in candidates:
        p31 = "; ".join(
            f"{x.get('label','')} ({x.get('qid','')})"
            for x in c.get("instance_of", [])
        ) or "—"

        authors = "; ".join(
            f"{x.get('label','')} ({x.get('qid','')})"
            for x in c.get("authors", [])
        ) or "—"

        p629 = "; ".join(
            f"{x.get('label','')} ({x.get('qid','')})"
            for x in c.get("edition_or_translation_of", [])
        ) or "—"

        titles = "; ".join(
            x.get("text", "")
            for x in c.get("stated_titles", [])
            if x.get("text")
        ) or "—"

        aliases = "; ".join(c.get("aliases", [])) or "—"
        dates = "; ".join(c.get("publication_dates", [])) or "—"

        lines += [
            f"#### {c['qid']} — {c.get('label','') or '[no label]'}",
            "",
            f"- source: `{c.get('source','')}`",
            f"- description: {c.get('description','') or '—'}",
            f"- aliases: {aliases}",
            f"- stated_titles: {titles}",
            f"- publication_dates: {dates}",
            f"- instance_of: {p31}",
            f"- authors: {authors}",
            f"- P629 edition/translation of: {p629}",
            f"- enwiki: {c.get('has_enwiki', False)}",
            "",
        ]

    lines += [
        "### Human decision",
        "",
        "- decision:",
        "- selected_qid:",
        "- acceptable_alternative_qids:",
        "- issue_codes:",
        "- confidence:",
        "- notes:",
        "",
        "---",
        "",
    ]

    decision_rows.append({
        "target_id": row["target_id"],
        "title": row["title"],
        "author": row["author"],
        "human_decision": "",
        "human_selected_qid": "",
        "human_alternative_qids": "",
        "human_issue_codes": "",
        "human_confidence": "",
        "human_notes": "",
    })

out_md.write_text("\n".join(lines), encoding="utf-8")

pd.DataFrame(decision_rows).to_csv(
    out_csv,
    index=False,
    encoding="utf-8"
)

print("Targets:", len(df))
print("Saved:", out_md)
print("Saved:", out_csv)
