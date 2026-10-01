# British Library SRU Verification Pilot v1 — Analysis Addendum 2

Status: written **before any Q2 candidate record was examined**.
Builds on: `docs/BL_VERIFICATION_PILOT_V1_ANALYSIS_ADDENDUM.md` (commit `5486bd0`). Neither the frozen protocol (`b7ad972`) nor addendum 1 is changed.
Parsed data: commits `a150921`, `e524326` (LF line endings; content unchanged).

---

## 1. What had been seen when this addendum was written

- per-query `numberOfRecords` and status; T1/T2 status for all twelve ground-truth works (all `COMPLETE`);
- per-sample link counts in `target_record_links.tsv`;
- `field_presence.tsv`;
- the first and last ten records (001, 245$a, 008 Date 1) of `BLP0023` (`alma.title = "She"`), used only to determine BL's result order.

**Not seen**: any record linked to a ground-truth work, in or near its first-edition year.

## 2. Observed result order

BL returned `BLP0023` in alphabetical order of title (digits first, then A…), not by 001 and not by relevance. A capped query therefore holds the alphabetically earliest 200 matching records. This is recorded for the summary and for any later retrieval design. It does not change any rule.

## 3. Clarification of addendum 1 §3.2 for Heart of Darkness

Addendum 1 §3.2 treats a ground-truth row as determinable when T1 or T2 completed without cap. The intent is that a complete route **that could have contained the expected edition** exists.

Heart of Darkness's expected first UK book edition is *Youth: A Narrative, and Two Other Stories* (Blackwood, 1902). T1 and T2 search for the title "Heart of Darkness" and cannot retrieve a volume titled *Youth* by construction. Only K1 (keyword; `CAPPED`, alphabetical order) and A1 (`SKIPPED_POLICY_CAP`) could have.

Therefore, for the Heart of Darkness row only:

- `found` if a linked record is the 1902 *Youth* volume;
- otherwise `undetermined_cap` (not `not_found_determinable`).

The other eleven rows are unaffected: in each, the expected edition carries the target title and T1/T2 could retrieve it. With one undetermined row, addendum 1 §3.2 applies to the remaining determinable rows (threshold proportions 75% / 50%).

## 4. Q2 procedure

1. **Deterministic candidate extraction.** For each ground-truth row, list every record linked to that target whose 008 Date 1, or any 260/264 $c year, lies within the expected year ±1. For multi-volume first editions (Tess), all volumes' records are kept. Output: `q2_candidates.tsv`.
2. **LLM first pass.** The model reads `q2_candidates.tsv` and the ground-truth table (protocol §5) and proposes, per row: `found` (with the matching 001), `not_found_determinable`, or `undetermined_cap`, plus a short reason. The exact prompt is saved as `q2_llm_prompt.md`; the model name and the raw output are saved as `q2_llm_output.tsv`. The model does not edit `q2_candidates.tsv`.
3. **Human confirmation of every row.** The human reviewer records `human_decision` and `human_note` for all twelve rows in `q2_first_edition_review.tsv`. The final decision is the human decision.
4. The G1–G5 reading is written into the summary only after step 3.

A record is accepted as the expected edition when its year and publisher match the ground-truth table; place may be absent. Issue points, binding states and later impressions dated within the window are noted but not resolved.
