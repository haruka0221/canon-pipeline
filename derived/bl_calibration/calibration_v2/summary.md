# British Library SRU Calibration v2 — Summary

Status: final for v2. Nothing here is a BL visibility value. All counts are of BL SRU records returned by the frozen routes on 2026-10-25; they are not holdings totals and not counts of editions.

Protocol: `docs/BL_CALIBRATION_PROTOCOL_V2.md` (text finalised 2026-10-21 before retrieval; committed `9af2285` after retrieval, see `calibration_v2_protocol_freeze.json`). Addendum 1 (`8aa1e83`): LLM first pass + blind human audit.
Frozen inputs: target frame `63c3ef6`, sample `ecf1a4d`, first-edition table `628e6d4`, query plan `4e3fe24`.
Evidence commits: retrieval log `ba0e19a`; parsed manifest `0924cd4`; matching manifest `90c3cab`; LLM run `c9141b3`; analysis `198481f`.
Private files (BL record content) are outside the repository; their sha256 are in the manifests.

---

## 1. Retrieval

| item | value |
|---|---|
| targets | 270 (S1 random 150, S2 edition-count strata 100, S3 v1 re-test 20); 278 OL aliases |
| routes | T2 exact title, K1 title+surname keyword, A1 author (count-probe, paged only if ≤ 200) |
| logical / physical queries | 810 / 784 |
| HTTP requests | 1,384 (≈ 5.2 per target; estimate was ≈ 14), one night, run locally on WSL |
| stops | 3, all SRU diagnostic `Invalid query` on CQL containing a double quote; skipped as `SKIPPED_INVALID_QUERY` (3 physical queries), no retries |
| physical query status | `COMPLETE` / `CAPPED` / `SKIPPED_POLICY_CAP` / `SKIPPED_INVALID_QUERY`, see `retrieval/physical_query_status_*.tsv` |
| distinct records | 15,261; target × record links 16,681 |
| targets with ≥ 1 record | 260 of 270 (S1 143/150, S2 97/100, S3 20/20) |
| records returned for > 1 target | 686 |

## 2. Matching rules (frozen; v1 R1–R3 code imported unchanged)

| rule | links true | targets with ≥ 1 |
|---|---:|---:|
| exact (R1) | 2,010 | — |
| r3 (bracket-stripped prefix, word boundary) | 2,441 | 194 |
| r3_author (r3 and query-author surname in 100/700) | 1,667 | 157 |
| multi_w_candidate (r3 true for > 1 target) | 468 links / 117 records | — |

Publication dedup (245$a | publisher | year) over r3-true links: 2,205 publication keys, 206 with more than one record.

## 3. Judgment (addendum 1)

- Sample: 500 target × record rows, seed 20261021: J1 r3_author 300, J2 r3-only 100, J3 r3-false 100. Blind input (no rule flags).
- LLM first pass: `claude-opus-5-5` in Claude Code, prompt `docs/BL_CALIBRATION_V2_LLM_JUDGMENT_PROMPT_V1.md` (`8e1715f`), output unchanged (`judgment_llm_run_v2.json`). VALID 309 / INVALID 189 / UNCERTAIN 2.
- Blind human audit: 82 rows (LLM VALID 40, INVALID 40, UNCERTAIN 2), human did not see LLM labels.

| LLM | human VALID | human INVALID | human UNCERTAIN |
|---|---:|---:|---:|
| VALID (40) | 40 | 0 | 0 |
| INVALID (40) | 2 | 38 | 0 |
| UNCERTAIN (2) | 1 | 0 | 1 |

Work-relation agreement 96.3 %; publication-relation agreement 91.5 %. LLM VALID was never overturned; 5 % of LLM INVALID were VALID on audit.

## 4. Precision and recall of r3_author (S1+S2 only; S3 excluded as in-sample for R3)

Stratified estimate = Σ P(LLM label | stratum) × P(human VALID | LLM label); 95 % CI by parametric bootstrap, exact Clopper–Pearson lower bound where the audit was all-VALID.

| stratum | n judged | estimated VALID | 95 % CI |
|---|---:|---:|---|
| J1 r3_author true | 129 | 100 % | [91.2 %, 100 %] |
| J2 r3 true, author false | 74 | 22.3 % | [12.4 %, 32.5 %] |
| J3 r3 false | 89 | 8.2 % | [2.3 %, 16.4 %] |

Decision-guide reading: **the precision criterion (CI lower bound ≥ 90 %) is met**, on an audit of 40 rows; the bound is close to the threshold and rests on that audit size.

Recall is low. Applied to the S1+S2 link population (r3_author 682; r3-only 596; r3-false 12,702), the expected VALID links are ≈ 682 / 133 / 1,042, giving an implied link-level recall for r3_author of **≈ 37 %**. The J3 figure depends heavily on the 5 % audit correction (2 of 40) and is imprecise; what is firm is that r3_author misses a substantial share of valid manifestations: combined volumes, early-edition titles, subtitle forms, and records where the OL author is wrong or absent.

S3 re-test (20 v1 targets): J1 92.2 % [88.0 %, 96.0 %]; the drop is driven by the famous-author targets (many editions, more title collisions among LLM INVALID rows).

## 5. Coverage against the first-edition table (G1 reading)

First-edition table: 30 S2 targets, drafted from general knowledge without the BL catalogue, all `verified=no`; 14 ESTABLISHED, 7 NO_UK_EDITION_KNOWN, 9 NO_EVIDENCE. Candidates = links whose record year is within ±1 of the UK first-edition year; 47 candidate rows, human-checked (yes 18, no 28, unsure 1).

| | targets |
|---|---:|
| ESTABLISHED | 14 |
| UK first edition found by any route | 11 (79 %) |
| … of which passes r3 | 10 |
| … of which passes r3_author | 8 (57 %) |
| unsure only | 1 (FE2_16) |
| not found | 2 (FE2_11 Farson: 4 candidates, none the first edition; FE2_24 Twain: no candidate, OL title is a volume title) |

Routes that returned the found first editions: K1 in 10 of 11, A1 in 7, T2 in 5. The three found-but-not-r3_author cases are: title match without author match (FE2_03, K1 only), r3 false (FE2_26 Zangwill, both records), and wrong OL author (FE2_28 Life with Father / O. Henry).

Retrieval coverage (79 %) meets the v1 G1 threshold (75 %); matching coverage by r3_author (57 %) does not. Because the first-edition table is an unverified draft, "not found" may also mean the table is wrong (Farson in particular).

## 6. Design cautions carried to production (v3)

1. **Quotes in CQL.** BL rejects `"` inside quoted CQL values. Pre-classify such queries as `SKIPPED_INVALID_QUERY` before sending (recorded before results were seen).
2. **r3_author is high-precision, low-recall.** Use it as the accepted core, and add a second lane for r3-only and author-only (A1/K1) links to be judged (LLM first pass + audit) rather than dropped. Do not widen r3 itself without a new calibration.
3. **OL author errors** (e.g. O. Henry for *Life with Father*) and missing authors (NO_OL_AUTHOR ≈ 1 %, absent from this sample) break the author rule; keep a per-target author-override table from identity review.
4. **Volume titles and non-English OL titles** (Twain 2/2; Zamyatin *Мы*) defeat T2/K1; alias expansion from Wikidata/Goodreads titles is the natural fix, to be calibrated separately.
5. **Duplicates and cross-target records**: 206 of 2,205 publications have > 1 record; 117 records are r3-true for several targets. Count publications, not records, and resolve multi-target records against identity (Heart of Darkness 4 W) before any W-level value.
6. **Prompt gap**: adaptations by other hands carrying none of the target's text had no class; the model used `INVALID / related_derivative`. Add the class to the v3 prompt.
7. **Audit size**: 40 LLM-VALID rows give a 91 % lower bound; v3 should audit ≥ 100 to make the bound informative.

## 7. Deviations from the protocol, recorded

- Run on WSL, not the server (server key access unavailable); raw at `~/bl_raw/calibration_v2/`, to be copied to `/media/hdd1/user/tsutsui/bl/calibration_v2_raw/`.
- Protocol markdown committed after retrieval (`9af2285`); text finalised before.
- Human judgment replaced by LLM first pass + blind audit (addendum 1, committed before matching results).
- First-edition table filled from general knowledge, unverified; coverage figures are conditional on it.
- Commit `628e6d4` message gives 15/7/8 for the first-edition table; actual 14/7/9.
- Two LLM rows changed by the model during its own run (BLJ2_0196, 0239); kept as left.

## 8. Decision

r3_author is adopted as the production acceptance rule for precision. On its own it is not sufficient for coverage; production must carry a judged second lane (§6 item 2) and the CQL pre-filter (§6 item 1). Full-scale retrieval size and dates are to be agreed with the BL after this summary.
