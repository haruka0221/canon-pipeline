# British Library SRU Verification Pilot v1 — Summary

Status: interim summary. Q4 is answered descriptively and the §7 classification moves to v2 (addendum 4). Nothing here is a BL visibility value (protocol §1, §10).

Frozen protocol: `docs/BL_VERIFICATION_PILOT_V1_PROTOCOL.md` (commit `b7ad972`)
Addenda: 1 (`5486bd0`), 2 (`bde9d02`), 3 (`0325107`). None of them is changed by this summary.
Evidence commits: retrieval `dcfb93d`; parsing `a150921`, `e524326`; Q2 `82c92b7`; Q1 `125b351`; Q3 `2202bdb`, `225d099`.
Branch: `bl-pilot-v1` (from `0325107`). All outputs are in `derived/bl_calibration/verification_pilot_v1/`.

---

## 1. Retrieval

| item | value |
|---|---|
| sample | 21 targets (19 resolved W, 2 unresolved units), `bl_verification_pilot_v1_sample.tsv` |
| retrieval date | 2026-10-01 (UTC) |
| logical / physical queries | 113 / 96 |
| physical query status | `COMPLETE` 74, `CAPPED` 9, `SKIPPED_POLICY_CAP` 13 |
| HTTP requests | 296, all `COMPLETE`, no retries |
| distinct BL records parsed | 2,605 (`records_parsed.tsv`) |
| raw responses | 296 XML files, outside Git; archive `bl_verification_pilot_v1_raw_20261001.tar.gz`, 2.2 MB, sha256 `e613ae28bbaa9f5d5336bbb744cc2f6c552c1afbc4d075f764d08aab534739d3`; server copy made 2026-10-03 with matching sha256 |

A1 (author only) exceeded the 200-record cap for 13 of 16 authors. A1 is `COMPLETE` only for Raspe, Eggleston and Croskey.

Whether raw XML is committed to the repository is not yet decided.

## 2. Reading against the decision guide (protocol §8)

The decision guide is read on two separate points: coverage and old-record matching.

### 2.1 Coverage: G1

Q2 (addendum 1 §3.2, addendum 2 §3): 10 of 11 determinable ground-truth rows were `found` (91%; threshold 75%). One row (Heart of Darkness) is `undetermined_cap`, below the limit of three. G4 and G5 do not apply.

The coverage part of G1 is met.

The determinability criterion is weaker than addendum 1 §3.2 assumed. For Kim and She, T1 and T2 were `COMPLETE` with no cap (Kim 61 / 85 records, She 31 / 91), but neither returned the first-edition records. Those records were found only by K1. A complete T1 or T2 therefore does not guarantee that old-form records are retrieved. The `not_found_determinable` decision for Sister Carrie should be read with this caution. For Sister Carrie, K1 was also `COMPLETE` (47 records), so the keyword route did not find the Heinemann 1901 edition either. A1 was `SKIPPED_POLICY_CAP` (246 records). The G1 count (10 of 11) is unchanged.

### 2.2 Old-record matching: G3 under the protocol-time rule

At protocol time, local matching meant equality of `245$a` with the title (rule R1 in the Q1 analysis). On the 13 confirmed first-edition records (`q1_first_edition_matching.tsv`), R1 fails for 6:

| record | 245$a | R1 | R2 | R3 |
|---|---|---|---|---|
| Kim (1901) | `[Kim. [With plates.]]` | no | no | yes |
| She (1887) | `She: a history of adventure.` | no | yes | yes |
| She (1887) | `She: a History Of Adventure :` | no | yes | yes |
| Burmese Days (1935) | `Burmese Days. A novel.` | no | yes | yes |
| Four Just Men (1905) | `The Four Just Men. [A novel.]` | no | yes | yes |
| Orange Fairy Book (1906) | `The Orange Fairy Book. Edited by Andrew Lang ...` | no | yes | yes |

Old records are found but fail the protocol-time `245$a` rule at a substantial rate. This is **G3** (structural problem in old records).

R3 (prefix match after removing `[` and `]`) passes all 13. R3 is a candidate remedy, not a validated rule:

- R2 and R3 were defined in the Q1 analyzer (`2f242fe`, `d323b4f`), written after the Q2 review had shown these failure examples. The 13/13 result is **in-sample**.
- R2/R3 precision (how often a different work passes) has not been measured.
- R3 needs to be checked on a separate sample, with precision measured, before it is used.

The overall reading is **G1 for coverage and G3 for old-record matching**. This summary does not combine them into a single conditional G1.

### 2.3 G2

Under addendum 1 §3.3, G2 is formally assessable only where A1 is `COMPLETE` (Raspe, Eggleston, Croskey). None of the three has a Q2 ground-truth row. G2 is therefore **not assessable** for Q2.

Descriptive only (from `target_record_links.tsv`): of the 10 found first editions, 8 were retrieved by at least one title route (T1–T3). Kim and She (both short titles; T3 `CAPPED`) were retrieved **only by K1**. For Q3, see §3.3.

## 3. Answers to Q1–Q6

### 3.1 Q1 Old records (descriptive)

- Pre-1975 manifestations are retrieved by title routes. For first editions, see §2.2.
- `q1_record_structure.tsv` gives pass rates by era and by 260/264, pooled over all T1 links. The links include records of other works with similar titles, so these rates describe the retrieved set, **not record structure as such**. They are not used as a structure indicator.
- R2/R3 precision has not been measured.

### 3.2 Q2 First-edition coverage

| row | work | decision |
|---|---|---|
| Q2R01 | Dorian Gray (Ward, Lock 1891) | found |
| Q2R02 | Tess (Osgood, McIlvaine 1891, 3 vols) | found (two records for one edition) |
| Q2R03 | Mrs Dalloway (Hogarth 1925; "L. & V. Woolf") | found |
| Q2R04 | Kim (Macmillan 1901) | found |
| Q2R05 | She (Longmans 1887) | found (three records for one edition) |
| Q2R06 | Burmese Days (Gollancz 1935) | found |
| Q2R07 | House of Mirth (Macmillan, London 1905) | found |
| Q2R08 | Sister Carrie (Heinemann 1901) | not_found_determinable |
| Q2R09 | Four Just Men (Tallis 1905) | found |
| Q2R10 | Heart of Darkness (*Youth*, Blackwood 1902) | undetermined_cap |
| Q2R11 | Howards End (Edward Arnold 1910) | found |
| Q2R12 | Orange Fairy Book (Longmans 1906) | found |

- Sister Carrie: only the 1900 Doubleday (US) edition and a Research Publications reproduction of it were linked. Why the Heinemann 1901 edition is absent is unknown.
- AI first pass (`claude-sonnet-4-5-20250929`): the decision agreed with the human decision on all 12 rows. Two AI reasons contained errors that did not affect the decision (Tess 008 date; Sister Carrie undated record omitted). See `q2_first_edition_review.tsv`.

### 3.3 Q3 Zero-result reliability (illustrative)

All five targets are `title_route_hit` (`q3_target_classification.tsv`). No target has zero title-route acceptances, so protocol §8's `absent_all_routes` / `title_route_miss` classification is not triggered. Per addendum 3 §6, these are illustrative examples, not population rates.

| target | class | present via title route + R3 | title_route_r3_miss | present via A1/K1 only | incomplete routes |
|---|---|---|---|---|---|
| BLV017 Orange Fairy Book (Lang) | title_route_hit | 5 | 0 | 1 | A1 skipped |
| BLV018 Four chapters (Tagore) | title_route_hit | 1 | 1 | 0 | A1 skipped |
| BLV019 The shen's pigtail (Croskey) | title_route_hit | 1 | 0 | 0 | — |
| BLV020 The Graysons (Eggleston) | title_route_hit | 4 | 0 | 0 | — |
| BLV021 Baron Munchausen (Raspe; unresolved unit) | title_route_hit | 13 | 1 | 39 | — |

Notes:

- **BLV017 is not blind.** Its first edition was examined in Q2 (Q2R12).
- **BLV018:** the only standalone English translation found is a 2022 translation by Radha Chakraverty (Penguin Random House India, Gurgaon; 250 "New edition"). No record of the earlier English translation of c. 1950 was retrieved. The title-route R3 miss is the 2011 Penguin omnibus *Classic Rabindranath Tagore*, which lists *Cāra adhyāya* in 700$t (`target_in_collection`). Because A1 was skipped at the cap, this is not evidence that BL lacks the earlier translation.
- **BLV019:** an 1894 edition exists, catalogued as "by Mr. M- [i.e. Julian Croskey]". The work is pseudonymous and obscure.
- **BLV020:** besides the New York Century Co. 1888 edition, an Edinburgh David Douglas 1888 edition exists.
- **BLV021:** of 53 present records, 39 were found only by A1/K1. These include the records titled *Baron Munchausen's narrative of his marvellous travels and campaigns in Russia* (1786) and *Gulliver revived* (1787–1799). The earlier the edition, the more its title differs from the alias titles. BLV021 is an unresolved unit, so this is retrieval evidence only, with no W-level value (addendum 3 §3.2).
- AI first pass (`claude-opus-5-5`, Claude Opus 5.5 in Claude Code, confirmed with `/status`) coded all 376 rows. The 78 rows in human-review scope (addendum 3 §3.3) were all confirmed as coded. Six rows carry notes: five chapbooks kept as `target_alone` although they may be abridged, and one translation from German (041 $h ger) kept as `target_with_other_works`. All six are BLV021 records and count among its 53 present records.

### 3.4 Q4 Hard cases

Answered descriptively in v1 under addendum 4 (`docs/BL_VERIFICATION_PILOT_V1_ANALYSIS_ADDENDUM_4.md`, §4). The answer lists the hard cases already reported in this summary, each with its source: short titles, pseudonyms, editor as creator, translation, combined volumes and early-edition titles. The protocol §7 classification is not carried out in v1 and moves to v2 (addendum 4 §2).

### 3.5 Q5 Cross-W duplication

Determined by construction (addendum 1 §3.1). The four Heart of Darkness W (W000014272, W000014830, W000017583, W000030652) share their physical queries, and each receives the same 276 linked records. Title+author retrieval cannot separate fragmented W. Without cross-W deduplication or prior identity resolution, per-W BL evidence would be counted four times. Whether the four W are one work is left to identity review. The per-W check of OL editions (standalone vs combined) named in protocol Q5 has not been done. `project_works_v4` is not modified.

### 3.6 Q6 Field presence

From `field_presence.tsv` (2,605 distinct records, by 008 Date 1 era):

| era | records | 015 | 240/130 | 260 | 264 | 700$t | 776 |
|---|---|---|---|---|---|---|---|
| pre-1900 | 306 | 0.0% | 16.3% | 29.4% | 68.6% | 5.9% | 15.7% |
| 1900–1949 | 270 | 0.0% | 36.7% | 43.3% | 56.3% | 5.9% | 0.4% |
| 1950–1974 | 256 | 29.7% | 21.1% | 61.7% | 37.5% | 5.9% | 0.8% |
| 1975–1999 | 432 | 64.8% | 14.4% | 96.5% | 3.0% | 14.4% | 1.4% |
| 2000+ | 1,265 | 70.9% | 5.9% | 39.4% | 61.1% | 9.6% | 16.3% |
| unknown | 76 | 0.0% | 7.9% | 67.1% | 7.9% | 1.3% | 0.0% |

- 015 (national bibliography number) never occurs before 1950, which is consistent with the start of the BNB.
- 264 is more frequent than 260 in pre-1949 records. Publication era and the way a record was made are separate: many old books have recently re-made records.
- 246, 600$t and 041 are in the source file and are not repeated here.

## 4. Design cautions for any full retrieval

1. **Alphabetical truncation.** BL returns results in alphabetical order of title (addendum 2 §2). A capped query holds only the alphabetically earliest 200 records, which is a non-random subset.
2. **Duplicate records.** One edition can have several records (Tess 2, She 3). Records need deduplication at the edition level before counting.
3. **Fragmented W.** Identical queries give identical candidate sets (Q5). This needs cross-W deduplication of BL records or prior identity resolution.
4. **Matching rule.** The protocol-time `245$a` equality rule fails on old records (§2.2). R3 is a candidate, but it was built in-sample and its precision is unmeasured. It must be validated on a separate sample.
5. **Titles of combined volumes and early editions.** Combined volumes (*Youth* for Heart of Darkness) and early editions (*Gulliver revived* for Munchausen) carry titles that title routes cannot retrieve.
6. **Author-level retrieval alongside title routes.** For authors under the cap, A1 retrieves the full author set. In BLV021 it found 39 of 53 present records that title routes missed.
7. **Old-form records and BL's own title index.** The first editions of Kim and She were not returned by T1/T2 (index title match), although both queries completed with no cap. They were found only by K1. Old-form records cannot always be retrieved by title even through BL's own title index. (T3 was also capped for both short titles.)
8. **Precision unmeasured.** R2/R3 precision, and how often A1/K1-only records are present, have not been measured at population level.

## 5. Procedural record

- **AI models.** Q2 first pass: `claude-sonnet-4-5-20250929` (`q2_llm_run.json`). Q3 first pass: `claude-opus-5-5` (Claude Opus 5.5 in Claude Code, confirmed with `/status`; `q3_llm_run.json`). Whether the Q2 model name matched `/status` at the time was not checked.
- **Deviation from the protocol:** an LLM first pass with human confirmation or audit (addendum 1 §5, §6) replaces fully manual classification. Prompts were committed before the runs (`67c2005`, `e89ef40`). AI outputs are kept unedited and separate from final codes.
- **`125b351` committed before the `--check` warning was examined.** The working rule was to stop and report the cause with `cat -A` when `--check` warned. In that session (context usage about 88%), the cause was examined only after commit and push. The cause is a trailing tab on lines 4 and 18 of `q1_failure_examples.tsv`, where the last column `f100_entries` is empty. Data is not affected. The commit message does not record the reason.
- **`not_classified`.** Addendum 3 §4 says that a target whose only present records are `title_route_r3_miss` "is not forced into either class" but gives no label. The classifier (`951a763`) writes `q3_class = not_classified` for that case. No target received it.
- **File naming.** Addendum 1 §7 listed `q1_q3_review.tsv`. Q1 and Q3 use separate `q1_*` and `q3_*` files (addendum 3 §2.4).
- **Q3 extractor.** `extract_q3_candidates_v1.py` (`69305f6`) copies N1/R1–R3 from the Q1 analyzer unchanged; this was checked by comparison.
- **Minor known issues (no effect on results).** A `SyntaxWarning` from `\d` in the docstring of `extract_q2_candidates_v1.py`. The diagnostic Roman-numeral flag fires on one-letter words (e.g. "I" in "Inc.").

## 6. Not yet done

- The §7 two-axis classification (`review.tsv`) and the Q4 questions that need it: carried forward to v2 (addendum 4).
- `manifest.json` (protocol §9). It will be produced in a separate commit, with its generating script committed first.
- The decision on committing raw XML.
- The Q5 per-W OL edition check (standalone vs combined) (v2, addendum 4).
- Validation of R3 and measurement of its precision on a separate sample (v2, addendum 4).
- `WORKFLOW.md` entry, and the merge of `bl-pilot-v1` into `kakenc-integration-20260927`.
