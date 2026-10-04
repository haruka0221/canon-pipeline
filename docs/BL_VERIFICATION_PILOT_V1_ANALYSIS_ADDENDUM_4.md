# British Library SRU Verification Pilot v1 — Analysis Addendum 4 (Scope of §7 classification and Q4)

Status: scope decision under addendum 1 §6.
Builds on: addenda 1 (`5486bd0`), 2 (`bde9d02`), 3 (`0325107`) and the interim summary `derived/bl_calibration/verification_pilot_v1/summary.md` (commit `9afd10f`). The frozen protocol (`b7ad972`) and addenda 1–3 are not changed.
Base commit when written: `9afd10f`.

---

## 1. What had been seen when this addendum was written

This addendum was written after the interim summary (`9afd10f`). No BL record was examined for it beyond those already examined for Q1–Q3 and reported in the summary. The record counts in §4 come from existing committed outputs.

## 2. Decision

- Pilot v1 does **not** carry out the protocol §7 two-axis classification. No `review.tsv` is produced in v1.
- Q4 is answered descriptively in v1, from existing outputs only (§4).
- The §7 classification and the open measurement questions move to the next stage: a calibration for full retrieval (v2), with a freshly drawn sample (protocol §10).

Addendum 1 §6 required the scope to be recorded before classification starts. This addendum records that scope as "none in v1".

## 3. Reasons

1. **The pilot's readings would not change.** The summary gives G1 for coverage and G3 for old-record matching (summary §2). Both rest on the Q2 ground-truth rows and the confirmed first-edition records. A full §7 classification of the retrieved records would not change either reading.
2. **v1 data cannot give out-of-sample estimates.** R2 and R3 were defined after the Q2 review had shown failure examples (summary §2.2). Their precision measured on v1 data would be an in-sample value only. If the full-retrieval design uses the rate of duplicate records or the rate of records found only by A1/K1, those rates should also be measured on a new sample.
3. **Effort is better spent on v2.** A full classification needs an AI first pass and a human audit of at least 100 pairs (addendum 1 §6). That effort is more useful on a fresh v2 sample, where the results can inform the design without in-sample bias.

## 4. Q4 in v1 (descriptive)

Each case is reported from existing outputs. No rate is inferred.

| case | observation | source |
|---|---|---|
| Short titles (Kim, She) | `alma.title = "She"` returned 18,143 records and `alma.title = "Kim"` 1,669, so T3 was capped for both. T1 and T2 were `COMPLETE` with no cap, but neither returned the first-edition records. Those records were found only by K1. | addendum 1 §2; summary §2.1, §2.3, §4 item 7; `target_record_links.tsv` |
| Pseudonym (Croskey) | The 1894 edition is catalogued as "by Mr. M- [i.e. Julian Croskey]". It was retrieved by A1, K1 and T3 (A1 `COMPLETE`). | summary §3.3; `q3_candidates.tsv`, `q3_review.tsv` |
| Pseudonym (Orwell) | The first edition of Burmese Days (Gollancz 1935) has 100 `Orwell, George` and was retrieved by K1 and T3. Its 245$a "Burmese Days. A novel." fails R1 and passes R2/R3. | summary §2.2, §3.2; `q1_first_edition_matching.tsv` |
| Editor as creator (Lang) | The first edition of The Orange Fairy Book (Longmans 1906) has 100 `Lang, Andrew`. Its 245$a includes "Edited by Andrew Lang ...", so it fails R1 and passes R2/R3. A1 for Lang was `SKIPPED_POLICY_CAP`. | summary §2.2, §3.2, §3.3; `q1_first_edition_matching.tsv` |
| Translation (Tagore) | The only standalone English translation found is the 2022 translation by Radha Chakraverty (Penguin Random House India). No record of the earlier English translation of c. 1950 was retrieved, and A1 was skipped at the cap. In the final Q3 codes for BLV018, no record is coded `other_language_version` (120 `unrelated`, 5 `ambiguous`, 1 `target_alone`, 1 `target_in_collection`). | summary §3.3; `q3_review.tsv` |
| Combined volumes (Heart of Darkness) | The first UK book edition is the 1902 volume *Youth*, which title routes cannot retrieve by construction. The Q2 row is `undetermined_cap`. | addendum 2 §3; summary §3.2 |
| Combined volumes (Tagore) | The 2011 Penguin omnibus *Classic Rabindranath Tagore* lists *Cāra adhyāya* in 700$t. It was retrieved by title routes but failed R3 (`title_route_r3_miss`, `target_in_collection`). | summary §3.3; `q3_target_classification.tsv` |
| Early-edition titles (Munchausen) | Records titled *Baron Munchausen's narrative ...* (1786) and *Gulliver revived* (1787–1799) were found only by A1/K1. In total, 39 of 53 present records were found only by A1/K1. | summary §3.3; `q3_target_classification.tsv` |

Not answered in v1: the protocol's concern that combined volumes with `245$a` = target and further works in `245$b` were undercounted in the earlier pilot. That would need the §7 relation axis (`target_with_other_works`), so it moves to v2.

## 5. Carried forward to v2

- validation of R3 on a new sample, with its precision measured;
- the rate of duplicate records (several records for one edition);
- the rate of present records found only by A1/K1;
- the frequency of `other` / `other_flag` and other exceptions in the §7 vocabulary, and the §7 classification itself;
- how to combine author-level retrieval with title routes;
- handling of BL's alphabetical truncation at the cap;
- titles of combined volumes and early editions;
- cross-W deduplication of BL records for fragmented W;
- the Q5 per-W OL edition check (standalone vs combined);
- confirmation with BL of request rate and access method before any large-scale retrieval.

## 6. Remaining steps to close v1

1. `manifest.json` (protocol §9): commit its generating script first, then the manifest.
2. Record the BL pilot in `WORKFLOW.md`.
3. Merge `bl-pilot-v1` into `kakenc-integration-20260927`.
