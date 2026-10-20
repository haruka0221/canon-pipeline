# Independent random 80 W: AI-assisted exploratory scope register v0.1

**Date:** 2026-10-20
**Status:** `EXPLORATORY_EVIDENCE_DRAFT / NOT_RESEARCHER_ADJUDICATED`
**Population context:** 80 independently sampled active Project W from the 32,066 active-W frame. This is not 80 sampled OpenAlex records or 80 random original Open Library Editions.

## Scope criterion under discussion

The proposed **primary OpenAlex scholarly-visibility analysis** covers individual novels and novellas **originally written in English** and **first published 1880–1950 inclusive**. Juvenile or children's novels are not excluded solely because of readership. Short stories, collections, critical/reference books, and translations from a non-English original are distinguished from in-scope novels/novellas. Unresolved border cases remain unresolved pending researcher decisions. The broader historical Open Library data and other visibility dimensions are retained; **nothing is deleted or reclassified in the underlying corpus**.

## What is in the TSV

`random_scope_80_ai_exploratory_register_v0_1.tsv` contains **80 unique Project W**, in the fixed review order, transcribed from the eight previously preserved exploratory evidence notes. Fields:

- `random_rank`, `project_work_id`: review order 1–80, unique Project W identity.
- `draft_title_or_title_author`: source-draft table label (not a normalized bibliographic title).
- `ai_proposed_class`: normalized *AI proposal* (`IN_SCOPE_CANDIDATE`, `OUT_OF_SCOPE_CANDIDATE`, or `UNRESOLVED`).
- `ai_proposal_verbatim`: source-draft wording, including important qualifications such as `UNRESOLVED_TARGET_LINK`.
- `ai_summary_basis_verbatim`: abbreviated evidence/uncertainty text as written in the source note; **not an independently re-verified fact**.
- `ai_outstanding_verification_first10`: extra open question appearing in the first 10-W evidence-update table, blank for later batches. The other batches' caveats are preserved within `ai_summary_basis_verbatim` and their source Markdown case notes.
- `evidence_url_count`, `evidence_urls_joined`: URLs *cited in the corresponding source notes*. These links have **not been re-opened or fact-checked** by this consolidation step; the presence of a URL does not prove direct linkage to the specified OL Work.
- `source_evidence_draft_repo_path`: exact existing Git-tracked evidence note location.
- `reviewer_scope_decision`, `reviewer_verification_notes`: intentionally **empty**; no researcher decision has been made or fabricated.

Note: this is a convenience evidence index and not a substitute for reading the full cases in the eight Markdown drafts. The metadata does **not** distinguish independently reverified claims from sources only cited in prior AI drafts.

## Mechanical consolidation results

| AI-proposed class | W count |
|---|---:|
| `IN_SCOPE_CANDIDATE` | 44 |
| `OUT_OF_SCOPE_CANDIDATE` | 26 |
| `UNRESOLVED` | 10 |
| **Total** | **80** |

Ten explicitly unresolved cases (rank, Project W):

- 5 `W000020394` — *Carry Me Back*: exact-book verification.
- 7 `W000013966` — *Surface and Depth*: source-target link not verified; **do not turn into OUT** simply because a same-author critical book was found.
- 12 `W000013111` — *Told at Tuxedo*: collection versus novel.
- 16 `W000015401` — *Alfred May*: literary form.
- 22 `W000026875` — *Armenian Romance*: fiction versus factual narrative.
- 24 `W000006125` — *Interference*: separate short story versus anthology / OL referent.
- 49 `W000026024` — *Ginger*: episodic novel versus sketches.
- 54 `W000028099` — *Flying Death*: fiction versus exploration-based narrative.
- 62 `W000025100` — *The Sin of Harold Diddlebock*: source edition and film-novelization form.
- 72 `W000011140` — *His Queen*: original English edition/language and attribution.

Two types of QC issue are separate from scope status: (1) **original-publication dates differ from edition-derived minimum dates**, sometimes dramatically, e.g. *Double Trouble Squared* and *Killer's Choice*; and (2) **records or titles may not identify exactly the externally found book**, e.g. *Surface and Depth*, *Humor*, or *Interference*. A provisional IN or OUT does not mean every bibliographic detail is settled.

## Verification completed, and what remains

During consolidation, checked:

1. Eight source drafts, each with 10 register rows, including the **updated first-10 v0.2** note (not the superseded v0.1 classifications).
2. Ranks 1–80 complete, no duplicate Project W ID.
3. Exactly 44/26/10 proposed class counts.
4. All 80 records have at least one URL transcribed from their case-specific evidence section: **176 URL entries**, with no assertion those sources were re-validated.

**Not yet verified in the consolidation environment:** exact membership/order against the original frozen random-80 TSV, because that TSV was not available here. The accompanying reproducible script performs this stronger assertion automatically **when run inside the server repository**, using `scope_evidence_review_template_v1.tsv` and fixed seed `scope-random80-first10-20261020`.

## Reproduction (read-only sources)

Place `build_random_scope_80_exploratory_register_v0_1.py` at e.g. `scripts/build_random_scope_80_exploratory_register_v0_1.py` in the worktree. It reads the eight **existing** Markdown drafts and the **existing** frozen sampling frame and writes only the output TSV to the specified destination. No network access needed.

```bash
cd ~/canon-pipeline-openalex-a2val || exit 1
python -B scripts/build_random_scope_80_exploratory_register_v0_1.py \
  --source-dir . \
  --output-dir derived/scope/random_scope_review_draft_v0_10
```

Expected summary: `Frozen 80-W sample membership/order: VERIFIED`, 44 IN, 26 OUT, 10 UNRESOLVED, 176 recorded URL entries. Re-running deterministically produces the same TSV from the same eight source notes.

Before any inferential use, researcher review should confirm the scope rule and each provisional classification or leave it unresolved; only **human-adjudicated cases** belong in a population-level estimator. That review should also consider evidence reliability/target linkage, not merely accept the AI candidate status as truth. Keep the pilot 159-W reviewer template, first-10 researcher-review TSV, historical OL population, Project W identity and frozen OpenAlex integrated v2 unchanged.
