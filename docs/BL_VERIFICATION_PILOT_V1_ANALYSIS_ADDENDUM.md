# British Library SRU Verification Pilot v1 — Analysis Addendum

Status: written after retrieval, **before any record-level review**.
Frozen protocol: `docs/BL_VERIFICATION_PILOT_V1_PROTOCOL.md` (commit `b7ad972`) — unchanged by this addendum.
Runner: `scripts/bl/run_bl_verification_pilot_v1.py` (commit `efc79e1`, sha256 `960da345412b1805d7971edf0aa185e245c2aa15f03ed5f7c5fa7f68b6e6c34b`)
Retrieval record: commit `dcfb93d`

This addendum does not change the protocol's questions, sample, routes, caps, ground truth or decision guide. It records (a) consequences of the protocol design that became visible only after retrieval, and (b) how the analysis will be carried out. Where it adds a procedure the protocol did not specify, that is stated explicitly as a deviation.

---

## 1. What had been seen when this addendum was written

To make the addendum's independence from the results auditable:

- seen: per-query `numberOfRecords`, per-query status (`COMPLETE` 74, `CAPPED` 9, `SKIPPED_POLICY_CAP` 13), per-request outcomes (296 `COMPLETE`, no retries), raw file hashes;
- seen for format checking only: the first raw page of `BLP0001` (leader and element structure of the first record);
- **not seen**: any record-level content relevant to Q1–Q6 (dates, publishers, titles of retrieved records, first-edition presence).

## 2. Retrieval summary

| item | value |
|---|---|
| retrieval date | 2026-10-01 (UTC 07:36–11:47) |
| logical / physical queries | 113 / 96 |
| HTTP requests | 296 (3 smoke test + 293 full run), all `COMPLETE`, no retries |
| raw responses | 296 XML files, outside Git, all `raw_sha256` verified |
| raw archive | `bl_verification_pilot_v1_raw_20261001.tar.gz`, 2.2 MB, sha256 `e613ae28bbaa9f5d5336bbb744cc2f6c552c1afbc4d075f764d08aab534739d3` |
| response format | SRU 1.2, `recordData` contains MARCXML elements (MARC21 slim namespace), not escaped strings |
| environment | Python virtualenv `~/canon-pipeline/.venv`, pandas 3.0.3 |

Observations from counts alone (no record content needed):

- short titles: `alma.title = "She"` 18,143 records; `alma.title = "Kim"` 1,669;
- `alma.title = "Heart of Darkness"` 283 records — the same count as the earlier Heart of Darkness pilot (live catalogue, so consistent but not a strict reproduction);
- A1 author-only queries exceeded the cap for 13 of 16 authors (246 to 2,905 records).

## 3. Consequences of the design, recorded before review

### 3.1 Q5 is determined by construction

The four Heart of Darkness W (W000014272, W000014830, W000017583, W000030652) have the same normalized title and the same query author. Their logical queries therefore map to identical physical queries, and their BL candidate sets are identical by construction. Overlap cannot discriminate between fragmentation and genuinely distinct works.

Q5 is reported as follows: **title+author retrieval cannot separate fragmented W; per-W BL evidence for such W would be counted once per W (here four times).** Any large-scale BL retrieval therefore requires either cross-W deduplication of BL records or prior identity resolution. Whether the four W are one work is left to identity review (OL edition evidence), not to BL. `project_works_v4` is not modified.

### 3.2 Caps limit negative conclusions

A `CAPPED` query holds only the first 200 records in BL's result order; a `SKIPPED_POLICY_CAP` query holds only its first page. A record absent from such a query may exist beyond the cap.

For Q2, each ground-truth edition is assigned one of:

```
found                   retrieved by any route
not_found_determinable  not retrieved, and at least one of T1 or T2 for that
                        work completed without cap (status COMPLETE)
undetermined_cap        not retrieved, and every T1/T2 for that work was
                        capped or skipped
```

The decision guide is applied to the determinable rows, with the protocol's thresholds kept as the same proportions (9/12 = 75%, 6/12 = 50%):

- G1 if `found` ≥ 75% of determinable rows;
- G4 if `found` ≤ 50%;
- G5 otherwise.

`undetermined_cap` rows are reported separately with the routes involved. If more than three rows are undetermined, no G1/G4 conclusion is drawn and the result is G5.

### 3.3 G2 cannot be assessed for most authors

G2 ("found mainly by A1/K1, not T1–T3") depends on A1, but A1 holds only one page for 13 of 16 authors. G2 is assessed only where A1 is `COMPLETE` (Raspe, Eggleston, Croskey); elsewhere it is reported as not assessable.

## 4. Analysis order

1. **Deterministic parsing (no judgment).** From the raw files: one row per distinct BL record (keyed by MARC 001), and a link table target × record × routes. Q6 field presence is computed here, stratified by 008 date.
2. **Q2 first-edition check.** For each ground-truth row, list linked records whose 008 Date 1 or 260/264 date falls within ±1 year of the expected first UK edition year.
3. **Q1 old-record structure and Q3 random targets.**
4. **§7 two-axis classification**, with scope decided after steps 1–3 (§6).

## 5. Q2 review method (deviation: LLM first pass)

The protocol says records are "manually classified". For Q2 the candidate set is small, so:

- an LLM proposes, for each ground-truth row, which candidate record (if any) is the expected first UK edition, with reasons;
- **a human confirms or corrects every Q2 outcome** (all rows, not a sample);
- model name, prompt text and raw model output are saved with the result.

## 6. §7 classification method (deviation: LLM first pass + human audit)

Full manual classification is not feasible at the observed volume (up to ~5,900 record instances before deduplication). Therefore:

- scope (all target × record pairs, or a stratified subset) is decided after steps 1–3 and recorded in a short note **before** classification starts;
- an LLM produces first-pass codes on both §7 axes, using a versioned prompt; model name, prompt version and raw outputs are preserved; the model's codes are kept separate from final accepted codes;
- a human audits a stratified sample of at least 100 pairs (covering every relation class the model used and every stratum), records agreement, and corrects; disagreement rates are reported;
- `other` and `other_flag` cases are all human-reviewed.

## 7. Outputs added by the analysis

```
derived/bl_calibration/verification_pilot_v1/
    records_parsed.tsv
    target_record_links.tsv
    field_presence.tsv
    q2_first_edition_review.tsv     (+ LLM prompt / raw output)
    q1_q3_review.tsv
    review.tsv                      (§7, LLM first pass + audited final codes)
    summary.md
```

Parsing and review scripts are committed before their outputs.
