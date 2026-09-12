from pathlib import Path
import json
import pandas as pd

ROOT = Path("derived/benchmark/judgments")

inp = pd.read_csv(
    ROOT / "input" / "wikidata_judge_input_130.csv",
    dtype=str
).fillna("")

sample = pd.read_csv(
    ROOT / "adjudication" / "consensus_audit_sample_15.csv",
    dtype=str
).fillna("")

audit_ids = list(sample["claude_target_id"])

# Preserve sampled order
order = {tid: i for i, tid in enumerate(audit_ids)}

df = inp[inp["target_id"].isin(audit_ids)].copy()
df["audit_order"] = df["target_id"].map(order)
df = df.sort_values("audit_order")

out_md = ROOT / "adjudication" / "consensus_audit_blind_15.md"
out_csv = ROOT / "adjudication" / "consensus_audit_decisions_15.csv"

lines = [
    "# Wikidata Consensus Audit — Blind Human Review",
    "",
    "Purpose: audit cases where Claude and Gemini agreed.",
    "",
    "Target: abstract literary work.",
    "",
    "Allowed decisions: MATCH / NO_MATCH / AMBIGUOUS",
    "",
    "Do not consult the model judgments while making the human audit decision.",
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
        "### Human audit decision",
        "",
        "- decision:",
        "- selected_qid:",
        "- alternative_qids:",
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
pd.DataFrame(decision_rows).to_csv(out_csv, index=False)

print("Targets:", len(df))
print("Saved:", out_md)
print("Saved:", out_csv)
