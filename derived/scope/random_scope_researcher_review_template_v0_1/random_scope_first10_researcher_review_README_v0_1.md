# First 10 independent-random Project W: researcher review sheet v0.1

Date: 2026-10-20
Status: **RESEARCHER_REVIEW_TEMPLATE / NO HUMAN DECISIONS RECORDED**

This file transcribes the ten fixed W from `derived/scope/random_scope_review_draft_v0_1/random_scope_first10_evidence_draft_v0_1.md`. Its `ai_draft_*` fields are exploratory hypotheses from that prior document, not newly verified source claims. URLs were copied from the prior draft; their validity and relation to a specific Open Library Work require researcher verification. Historical OL dates are **minimum years from linked Editions**, not original publication dates.

## Suggested review workflow

1. Work row by row, verifying the **specific bibliographic target**, ideally by stable catalog ID, Edition and/or digitized title page. Record whether the independently located book is truly the book described by the given OL Work.
2. Confirm original language, individual-work form (novel/novella vs. short story, anthology, criticism, etc.), and separately verify first public appearance, first complete publication, first book publication and first English manifestation where relevant. Leave unresolved dates empty.
3. Enter evidence identifiers/URLs and which claims each checked source actually supports in the `reviewer_*` columns. Reviewers may retain `UNRESOLVED` as a legitimate final decision, with a reason.
4. **Only after the human reviewer verifies the evidence**, set `reviewer_analysis_scope_status` to `IN_SCOPE`, `OUT_OF_SCOPE` or `UNRESOLVED`; record reviewer name/date/notes and set `review_status=RESEARCHER_CONFIRMED` (or leave `NOT_REVIEWED` for unreviewed cases). Do not infer researcher signoff from draft suggestions.
5. Do not modify the frozen 159-W pilot, OpenAlex integrated v2, Project W identities or the earlier 13-W evidence notes. Review this sheet as a **new versioned derivative**.

## Special cases

- `W000013966` *Surface and Depth*: the 2003 critical book and the OL Work must be positively linked before excluding the W on that basis. The contradictory Edition-derived year 1920 is not corrected here.
- `W000019449` *A Master Workman’s Oath*: single title alone does not settle the novel/short-story boundary.
- `W000026120` *The Angel* and `W000020394` *Carry Me Back*: insufficient independent evidence in the draft; `UNRESOLVED` is acceptable.
- `W000017199` *December the Fourteenth*: record English translation year separately from original publication and original language.

## Coverage and inference

The ten records are the **first review batch of the already frozen independent random 80-W sample**, not a replacement or a newly drawn random sample. The ten observations alone cannot provide a stable estimate of population scope prevalence. Do not pool these with purposive cases for prevalence estimates.

## Saved files on the server (recommended)

- `derived/scope/random_scope_researcher_review_template_v0_1/random_scope_first10_researcher_review_v0_1.tsv`
- `derived/scope/random_scope_researcher_review_template_v0_1/README.md`

Commit this template separately, keeping `review_status=NOT_REVIEWED` on all 10 rows until actual human review.
