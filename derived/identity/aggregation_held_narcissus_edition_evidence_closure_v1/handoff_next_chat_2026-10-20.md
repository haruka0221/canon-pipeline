# 博論 `canon-pipeline` 引継ぎ — OL Edition監査を一区切り（2026-10-20）

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
