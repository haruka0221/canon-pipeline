#!/usr/bin/env python3
"""Close an exploratory Conrad Edition audit without assigning researcher identity decisions.

Creates immutable-source evidence addendum, a closure note, a next-chat handoff,
and a SHA-256 manifest. Does NOT edit the frozen draft/Project W or use Git.
Run from ~/canon-pipeline-openalex-a2val.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

BASE_REL = Path("derived/identity")
DRAFT_REL = BASE_REL / "aggregation_held_narcissus_edition_scope_review_draft_v1"
OUT_REL = BASE_REL / "aggregation_held_narcissus_edition_evidence_closure_v1"
COMMIT_BASELINE = "b788763d"
HASHES = {
    "edition_scope_review_draft_v1.tsv": "b33b188fa32e7fee702b755076bd1b728914c29939e38bad1b7b6cb7ba7b6534",
    "work_identity_context_v1.tsv": "ca5096b19c3b99b4ffed4e9b3aebadf882b3534e2135284fdd1a42a6b424e5cd",
    "manifest_v1.json": "54db7aa050d4bddb4b03d668b051a189dc87b2db0c1ce3bb7415975feeedecae",
    "README_review_protocol_v1.md": "f62d5b996378731978b24d8762008a8a0391fcfc5a49348ad4c8bfef68072284",
}
EXTERNAL = "https://www.abebooks.com/9781850522041/Joseph-Conrad-Lord-Jim-Nigger-1850522049/plp"

# Interpretive prompts / observed evidence. NO human judgment or definitive non-inclusion.
EVIDENCE = {
    "/books/OL11558585M": ("NO_DETERMINATION", "Series title/subtitle identifies Complete Short Fiction / The Stories; no contents in frozen OL record.", "Locate volume-specific contents / ISBN bibliographic record.", ""),
    "/books/OL11952490M": ("NO_DETERMINATION", "Complete Short Fiction series title; no contents in frozen OL record.", "Identify precise volume and contents.", ""),
    "/books/OL15364763M": ("NO_DETERMINATION", "Complete Short Fiction catalogue entry; frozen table_of_contents has character-split item titles and cannot support constituent-work claims.", "Inspect original MARC or scanned multi-volume contents; do not interpret character-split ToC.", ""),
    "/books/OL20710563M": ("NO_DETERMINATION", "1988 title/subtitle says Joseph Conrad: author's notes; no constituent-work contents in frozen record.", "Check whether it reproduces the target novel, not merely author paratext.", ""),
    "/books/OL21568672M": ("FROZEN_CATALOG_TOC_SUPPORTS_PRESENCE", "Frozen OL contents explicitly lists Nigger of the Narcissus among selected novels and stories.", "Optional scan/original catalogue check before a formal reviewer judgment.", ""),
    "/books/OL8132525M": ("NO_DETERMINATION", "Complete Short Fiction / The Tales volume title; no contents in frozen OL record.", "Identify volume-specific contents from ISBN.", ""),
    "/books/OL8132526M": ("NO_DETERMINATION", "Complete Short Fiction / The Tales volume title; no contents in frozen OL record.", "Identify volume-specific contents from ISBN.", ""),
    "/books/OL8132533M": ("NO_DETERMINATION", "Complete Short Fiction / The Stories volume title; no contents in frozen OL record.", "Identify volume-specific contents from ISBN.", ""),
    "/books/OL8794202M": ("NO_DETERMINATION", "2004 subtitle identifies Heart of Darkness (Great Authors), not the target novel; absent contents evidence.", "Check full contents, ISBN 1584726539; do not infer target absence from subtitle.", ""),
    "/books/OL8968317M": ("EXTERNAL_BOOKSELLER_ISBN_SUPPORTS_PRESENCE", "Frozen OL source pointer contains ISBN 1850522049; an external bookseller's ISBN bibliographic listing explicitly names Lord Jim, The Nigger of the 'Narcissus', Typhoon, and Nostromo (Peerage Books, 1991).", "If upgrading to reviewer-confirmed, verify via catalogue/physical book; bookseller metadata is secondary.", EXTERNAL),
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict]):
    with path.open("x", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_rows(draft: list[dict]) -> list[dict]:
    assert len(draft) == 10
    assert {r["edition_key"] for r in draft} == set(EVIDENCE)
    rows = []
    for r in draft:
        key = r["edition_key"]
        category, statement, followup, url = EVIDENCE[key]
        assert r["researcher_review_status"] == "NOT_REVIEWED", key
        assert all(v == "" for k, v in r.items() if k.startswith("researcher_") and k != "researcher_review_status"), key
        assert r["reviewed_at"] == "", key
        assert r["unit_anchor_entity_id"] == "E000019634" and r["linked_current_ol_work_id"] == "OL38815W"
        sources = json.loads(r["source_records_json"])
        if key == "/books/OL8968317M":
            assert any("1850522049" in str(x) for x in sources), "External ISBN mismatch"
            assert r["publish_year"] == "1991"
        if key == "/books/OL21568672M":
            assert "Nigger of the Narcissus" in r["contents_preview"], "Expected frozen ToC evidence missing"
        if key == "/books/OL15364763M":
            assert "TOC_CHARACTER_SPLIT_SUSPECT" in json.loads(r["machine_observation_cues_json"])
        rows.append({
            "unit_anchor_entity_id": r["unit_anchor_entity_id"],
            "edition_key": key,
            "linked_current_ol_work_id": r["linked_current_ol_work_id"],
            "edition_title": r["edition_title"],
            "publish_year": r["publish_year"],
            "evidence_status_not_researcher_decision": category,
            "source_based_observation": statement,
            "evidence_provenance": "FROZEN_OL_2026_02_28_AND_EXTERNAL_ISBN" if url else "FROZEN_OL_2026_02_28",
            "external_bibliography_url": url,
            "remaining_verification": followup,
            "researcher_presence_decision": "",
            "researcher_work_identity_decision": "",
            "decision_status": "NOT_ADJUDICATED",
        })
    assert Counter(r["evidence_status_not_researcher_decision"] for r in rows) == {
        "NO_DETERMINATION": 8,
        "FROZEN_CATALOG_TOC_SUPPORTS_PRESENCE": 1,
        "EXTERNAL_BOOKSELLER_ISBN_SUPPORTS_PRESENCE": 1,
    }
    return rows


CLOSURE = """# Conrad Narcissus Edition audit: exploratory closure (2026-10-20)

**Status: CLOSED AS EVIDENCE-GATHERING ONLY / NOT ADJUDICATED.**

The ten deliberately chosen Editions linked to `OL38815W` have a frozen
non-adjudicative worksheet in `aggregation_held_narcissus_edition_scope_review_draft_v1`
(commit `b788763d`). This addendum *does not edit that worksheet* and adds
no human-accepted identity/Edition decisions.

## Evidence summary

- **1 frozen-catalogue ToC supporting inclusion:** `/books/OL21568672M`
  explicitly lists the target novel in its contents. This is a catalogue
  assertion, not direct examination of all leaves of the book.
- **1 ISBN-linked external bibliographic listing supporting inclusion:**
  `/books/OL8968317M`, source ISBN `1850522049`, matches a secondary bookseller
  listing of the Peerage Books 1991 joint volume naming the target novel.
  Bookseller information is supporting evidence, not an independently
  examined physical item.
- **8 entries remain indeterminate as to inclusion.** They must NOT be
  counted as confirmed absent. Six are Complete Short Fiction records;
  another refers to Author's Notes and another to Heart of Darkness.
- `/books/OL15364763M` has an unusable character-by-character ToC anomaly.
- The separate OL Works `OL38815W` and `OL44245458W` have **no new
  researcher-confirmed identity decision**. The old LLM ONE_WORK frame
  and Project W are unchanged.

## Methodological boundary

`linked Edition` != `Edition containing the conceptual target text`.
A title lacking the word Narcissus is not proof of non-inclusion; conversely,
source-linked publication volumes and copy-specific bound-with notes do not
necessarily indicate mistaken Work identity. Scope of publication, physical
binding, bibliographic metadata quality, and conceptual Work identity are
separate axes.

The selected ten Editions are an exploratory, post-heldout convenience set.
Neither an error rate nor a generalization to 93/94 or 40,305 Editions can be
estimated from them. For this phase, **do not expand the review to all
93 linked Editions** or continue optimizing v4 on examined cases.

## Closeout criteria

- Frozen draft and v1-v4 screens retained verbatim.
- Each of the 10 Editions has evidence status, source provenance, and a
  remaining question, with all researcher decision columns blank.
- Acknowledged unresolved items stay explicitly unresolved.
- No source metadata, Project W, heldout labels, or historical LLM outcomes
  are rewritten.
- Next priority after checking/committing this file: resume OpenAlex QC,
  specifically the known 7-pair R3+A2 vs integrated-v1 discrepancy.
"""

HANDOFF = """# 博論 `canon-pipeline` 引継ぎ — OL Edition監査を一区切り（2026-10-20）

## 作業位置と安全原則

Server worktree: `~/canon-pipeline-openalex-a2val`, branch
`ol-bibliographic-projection-review-20261018`. Last confirmed committed
HEAD **before this closure artifact**: `b788763d` (unadjudicated Narcissus
Edition review draft). If this closure is committed, use `git log -2 --oneline`
to get its actual new commit ID; do not assume an unpublished hash.

Separate untracked path `derived/identity/openlibrary_r2a1_split_identity_review_pilot_v1/`
is unrelated and must not be staged/deleted/overwritten. Project W v7,
frozen historical LLM adjudications, human-assisted heldout decisions,
old snapshots and v1-v4 evidence are immutable. Git push has not been
established by this closure script.

## Frozen OL Work / Edition screening completed in this chat

- Historical old LLM review rows: 1,194; `HOLD_FOR_LATER_REVIEW` 761:
  `ONE_WORK` 438, `MULTIPLE_WORKS` 19, `UNRESOLVED` 304. The 438 were
  **held, not automatically merged**.
- 20-case human-assisted heldout reference: 13 ONE / 7 MULTIPLE;
  old LLM problematic ONE_WORK cases #11, #12, #13. Not unaided gold.
- v1 screening: 438 units, 1,249 OL Works, 40,305 Edition links,
  345 units with defined hints / 93 without.
- v2 enriches all 40,305 distinct Editions from **frozen OL Editions dump
  dated 2026-02-28** (55,615,769 dump rows), including subtitle, pagination,
  notes, ToC and source-record pointers. v1+v2: 372/438 any hint, 66 none.
  Case #12 Regent's Daughter 1894 Edition `/books/OL52630896M` shows
  subtitle `The black tulip` and pagination `319, 253 pages`, with a
  separate record noting a bound item. Screening not identity proof.
- v3 exploratory review queue: T1 75 / T2 61 / T3 236 / T4 66.
- v4 refined cues: F1 27 / F2 20 / F3 367 / F4 24, 40,305 Edition rows.
  Trained/adapted after heldout examples; not an independent accuracy test.
- Commits: v1-v3 `194b5ea0`; v4 `a854107f`; unadjudicated Conrad
  review draft `b788763d`.

## Work identity and Edition scope are different

- `E000019621` Conrad *Youth*: two OL Works have edition-level contents
  listing the same three stories (*Youth*, *Heart of Darkness*, *The End of
  the Tether*). Possible duplicate **collection** identities; no formal
  new adjudication.
- `E000019634` Conrad *The Nigger of the “Narcissus”*: OL38815W has 93
  linked Editions, OL44245458W has 1. The former includes editions described
  as joint volumes, Complete Short Fiction, notes, etc. This does not by
  itself establish a mistake in Work-to-Work identity.
- `E000006651` *Rab and His Friends*: 1901 D. C. Heath 58-page and
  1900 Houghton Mifflin 299-page publications have different scope; both
  contain overlapping component literary works. Publication scope difference
  is not automatically MULTIPLE_WORKS for the project unit.
- Other useful scope distinctions: *Peg Woffington*, *The Postman Always
  Rings Twice*, *The War of the Worlds*; advertising pagination and
  copy-specific binding are not evidence of independent conceptual works.

## Conrad 10 Edition evidence-closeout

Frozen worksheet: `derived/identity/aggregation_held_narcissus_edition_scope_review_draft_v1/`
(commit `b788763d`, 10 Editions / 2 OL Works / zero reviewer decisions).
This new `aggregation_held_narcissus_edition_evidence_closure_v1` is only an
addendum: 1 frozen ToC supports inclusion, 1 bookseller ISBN-linked
bibliography supports inclusion, 8 **UNDETERMINED**. The 1 catalogue ToC
Edition is `/books/OL21568672M`. The 1 secondary ISBN-linked entry is
`/books/OL8968317M`, ISBN 1850522049 (Peerage Books, 1991). **No
ABSENT_CONFIRMED, no formal researcher decisions, no Work changes.**
The other 8 should not be revisited immediately; missing contents are not
negative evidence. An anomalous per-character ToC is flagged for future
metadata quality work, not interpreted as literal story entries.

## Next chat: resume core dissertation OpenAlex work, not Edition audits

Reference project handoff `canon_pipeline_handoff_2026-10-12.md` and this
new handoff. Inspect current repo Git status and manifests first. The
2026-10-12 *historical* OpenAlex integrated v1 was **226,214 operational
candidate W×OA pairs across 7,077 W**; not human-verified citations.
Frozen R3+A2 contains 291,859 unique pairs versus 291,852 integrated raw;
read-only QC must identify the **7 actual missing pairs**, determine identity
gates/provenance, and only if necessary make an integrated **v2** without
changing v1. Then review top 50–100 work rankings, generic-title false
positives and projection onto the historical 34,789 OL source target frame.
Do not assume the 7-pair discrepancy is still open before checking current
repo state, and do not resume the 17 legacy Work repair/re-run broad LLM.

Recommended next-chat opening:
"博論のOpenAlex分析に戻ります。2026-10-20にOpen Libraryの438件Edition書誌監査v1-v4とConrad 10 Editionの非判定的証拠整理を一区切りにしました。Project W・凍結済み評価は不変です。まずリポジトリ現状と2026-10-12ハンドオフを読み、R3+A2と統合v1の7ペア差分が解消済みか、読み取り専用で検証してください。Edition監査は再開しません。"
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--self-test", action="store_true")
    a = parser.parse_args()
    if a.self_test:
        assert len(EVIDENCE) == 10
        assert Counter(v[0] for v in EVIDENCE.values()) == {
            "NO_DETERMINATION": 8,
            "FROZEN_CATALOG_TOC_SUPPORTS_PRESENCE": 1,
            "EXTERNAL_BOOKSELLER_ISBN_SUPPORTS_PRESENCE": 1,
        }
        print("SELF-TEST PASSED: exact Edition IDs, 1 frozen-ToC cue, 1 secondary ISBN cue, 8 undetermined")
        return
    repo = a.repo.resolve()
    draft = repo / DRAFT_REL
    out = repo / OUT_REL
    if out.exists():
        raise SystemExit(f"STOP refusing to overwrite existing path: {out}")
    for name, digest in HASHES.items():
        f = draft / name
        if not f.is_file() or sha(f) != digest:
            raise SystemExit(f"STOP frozen input missing/changed: {f}")
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=repo, text=True).strip()
    if branch != "ol-bibliographic-projection-review-20261018":
        raise SystemExit(f"STOP unexpected branch: {branch}")
    if subprocess.run(["git", "merge-base", "--is-ancestor", COMMIT_BASELINE, "HEAD"], cwd=repo).returncode:
        raise SystemExit("STOP expected b788763d is not an ancestor of HEAD")
    if subprocess.run(["git", "diff", "--quiet"], cwd=repo).returncode or subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo).returncode:
        raise SystemExit("STOP tracked worktree/stage not clean; untracked other work is allowed")
    rows = build_rows(read(draft / "edition_scope_review_draft_v1.tsv"))
    work_context = read(draft / "work_identity_context_v1.tsv")
    assert len(work_context) == 2 and all(r["researcher_identity_review_status"] == "NOT_REVIEWED" for r in work_context)
    with tempfile.TemporaryDirectory(prefix=".narcissus_scope_close_stage_", dir=out.parent) as tmp:
        stage = Path(tmp)
        write_tsv(stage / "edition_evidence_closure_v1.tsv", rows)
        (stage / "README_scope_conclusion_v1.md").write_text(CLOSURE, encoding="utf-8")
        (stage / "handoff_next_chat_2026-10-20.md").write_text(HANDOFF, encoding="utf-8")
        outputs = {p.name: sha(p) for p in sorted(stage.iterdir())}
        manifest = {
            "release": "narcissus_edition_scope_evidence_closure_v1",
            "status": "EVIDENCE_CLOSED_NO_RESEARCHER_ADJUDICATION",
            "source_snapshot": "OL_EDITIONS_2026-02-28",
            "source_commit_minimum": COMMIT_BASELINE,
            "source_draft_sha256": HASHES,
            "counts": {"editions": len(rows), "work_context": len(work_context), "researcher_decisions": 0, "evidence_status": dict(Counter(r["evidence_status_not_researcher_decision"] for r in rows))},
            "external_sources": [EXTERNAL],
            "outputs_sha256": outputs,
            "restrictions": ["No identity adjudications", "Missing contents is not evidence of absence", "No Project W or frozen revisions", "External ISBN source is a secondary bookseller listing, not a physical-copy inspection", "v4 is exploratory and post-hoc"],
        }
        (stage / "manifest_v1.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        assert len(read(stage / "edition_evidence_closure_v1.tsv")) == 10
        for name, digest in outputs.items():
            assert sha(stage / name) == digest
        if out.exists():
            raise SystemExit("STOP output appeared during staging")
        stage.rename(out)
    print("=== CONRAD EDITION EVIDENCE CLOSURE V1 CREATED ===")
    print("10 Edition rows; 1 frozen-catalogue inclusion cue; 1 external bibliographic inclusion cue; 8 undetermined")
    print("0 new human decisions, Work identity changes, or Project W changes")
    for p in sorted(out.iterdir()):
        print(p.name, sha(p))
    print("No Git staging, commit, or push")


if __name__ == "__main__":
    main()
