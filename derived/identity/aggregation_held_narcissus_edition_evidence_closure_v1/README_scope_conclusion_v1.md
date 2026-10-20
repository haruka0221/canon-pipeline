# Conrad Narcissus Edition audit: exploratory closure (2026-10-20)

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
