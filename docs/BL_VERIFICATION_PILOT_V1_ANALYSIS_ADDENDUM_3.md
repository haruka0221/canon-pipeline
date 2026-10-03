# British Library SRU Verification Pilot v1 — Analysis Addendum 3 (Q3)

Status: written **before any Q3 candidate record was extracted or examined** (except as listed in §1).
Builds on: `docs/BL_VERIFICATION_PILOT_V1_ANALYSIS_ADDENDUM.md` (commit `5486bd0`) and `docs/BL_VERIFICATION_PILOT_V1_ANALYSIS_ADDENDUM_2.md` (commit `bde9d02`). Neither the frozen protocol (`b7ad972`) nor addenda 1–2 are changed.
Base commit when written: `125b351`.

The protocol (§8) says: "every random target with zero T1–T3 acceptances is reported with its A1/K1 outcome, classified as `absent_all_routes` or `title_route_miss`". It does not define "acceptance", the matching rule, or how incomplete routes are handled. This addendum fixes those definitions before extraction.

---

## 1. What had been seen when this addendum was written

- the Q3 targets and their logical queries (`logical_queries.tsv`): BLV017 *The Orange Fairy Book* (Andrew Lang), BLV018 *Four chapters* (Rabindranath Tagore), BLV019 *The shen's pigtail* (Julian Croskey), BLV020 *The Graysons* (Edward Eggleston), BLV021 *Baron Munchausen* (unresolved unit, three title aliases, Rudolf Erich Raspe);
- per-route status: T1, T2, T3 and K1 are `COMPLETE` for all five targets; A1 is `SKIPPED_POLICY_CAP` for BLV017 and BLV018 and `COMPLETE` for BLV019–BLV021;
- per-target link counts in `target_record_links.tsv`: BLV017 25, BLV018 127, BLV019 8, BLV020 93, BLV021 123 (376 in total);
- `q1_failure_examples.tsv` (commit `125b351`) contains no record linked to BLV017–BLV021 (checked by `marc_001`);
- `q1_record_structure.tsv` pools T1 links from all targets, including these five, into era-level rates only.

**BLV017 (Lang) is not blind.** Its first UK edition (Q2 row `Q2R12`) was examined in the Q2 review (`q2_candidates.tsv`, `q2_first_edition_review.tsv`, decision `found`, commit `82c92b7`), and that record's R1–R3 results appear in `q1_first_edition_matching.tsv` (commit `125b351`). BLV017 is kept in Q3, but its Q3 result is reported as not independent of earlier inspection.

**Not seen**: the content (245, dates, publishers, languages) of any record linked to BLV018–BLV021, or of any record linked to BLV017 outside the Q2 candidate window (1905–1907).

## 2. Mechanical extraction (no judgment)

Script: `scripts/bl/extract_q3_candidates_v1.py`, committed before its output.

Targets: the rows of `bl_verification_pilot_v1_sample.tsv` with `stratum` `random_w` or `random_unresolved` (BLV017–BLV021). They are selected by stratum, not by hard-coded IDs.

Inputs (read only): `bl_verification_pilot_v1_sample.tsv`, `logical_queries.tsv`, `physical_query_status.tsv`, `target_record_links.tsv`, `records_parsed.tsv`.

### 2.1 Matching rule

The normalization N1 and the rules R1/R2/R3 are those of `scripts/bl/analyze_q1_record_structure_v1.py` (commit `d323b4f`), copied without change:

- N1: Unicode NFKC → casefold → collapse whitespace → strip outer whitespace → strip trailing space / : ; . , =
- R1: N1(245$a) equals N1(title)
- R2: N1(245$a) starts with N1(title), followed by end of string or a non-alphanumeric character
- R3: as R2, after removing `[` and `]` from 245$a

Comparison is against **245$a only**, and against **every** T1–T3 `title_norm` of the target (BLV021 has three). A record passes if it passes for any title; the matched title is recorded.

Fields 240, 246, 505 and 700$t are output as raw values for the reviewers but are **not** used for matching. Whether the author's surname (taken as in Q1) occurs in 100 or in 700 is output for information only and is not used in any classification.

R2/R3 precision (how often they pass a different work) has not been measured. A record passing R3 is a candidate, not an acceptance.

### 2.2 Route groups

For each target × record link, from `routes`:

- `via_title_route`: `routes` contains T1, T2 or T3;
- `a1k1_only`: `routes` contains only A1 and/or K1.

### 2.3 Route completeness

For each target, every route used (T1, T2, T3, K1, A1; for BLV021 every title's T1–T3 and K1) is checked in `physical_query_status.tsv`.

- `any_route_incomplete` = true if at least one of these routes has a status other than `COMPLETE`;
- `incomplete_routes` lists each such route with its status (e.g. `A1:SKIPPED_POLICY_CAP`).

A capped query holds only the alphabetically earliest records by title (addendum 2 §2); a skipped query holds only its first page.

### 2.4 Outputs

`q3_candidates.tsv` — one row per target × linked record (all links, including records failing R3):

```
sample_id, marc_001, routes, via_title_route, via_a1, via_k1, a1k1_only,
r1, r2, r3, r3_matched_title_norm, surname_in_100, surname_in_700,
f245_a, f245_b, f245_c, f246_a, f240_a, f130_a, has_f505, has_f600_t,
cf008_date1, cf008_language, f041_a, f041_h, f250_a,
f260_a, f260_b, f260_c, f264_a, f264_b, f264_c, f100_entries, f700_entries
```

`q3_target_summary.tsv` — one row per target:

```
sample_id, target_lane, project_work_id, unresolved_unit_anchor_entity_id,
title_norms, author_name, route_statuses,
any_route_incomplete, incomplete_routes,
n_links, n_title_route, n_title_route_r3, n_a1k1_only, n_a1k1_only_r3
```

Neither file contains a class. Files are written with `lineterminator="\n"`.

Naming deviation: addendum 1 §7 listed `q1_q3_review.tsv`. Q1 was recorded separately (`125b351`); Q3 uses the `q3_` files listed here and in §5.

## 3. Record-level judgment

### 3.1 AI first pass

The prompt is committed as `q3_llm_prompt.md` before the run. The model reads `q3_candidates.tsv` and assigns each target × record row exactly one relation class from protocol §7.1, with a short reason. §7.2 manifestation flags are not coded in Q3. The model does not edit `q3_candidates.tsv`.

The model name actually running at the time of the run is recorded in `q3_llm_run.json`, together with the prompt's sha256 and the input file hashes. The raw output is saved unedited as `q3_llm_output.tsv`.

### 3.2 "Present"

A record is **present** (a manifestation of the target work itself) if its relation class is one of:

```
target_alone
target_with_other_works
target_in_collection
```

All other classes (`target_excerpt`, `target_abridged_or_retold`, `other_language_version`, `adaptation`, `related_study_guide`, `related_criticism`, `related_derivative`, `unrelated`, `ambiguous`, `other`) are **not present**.

Manifestation properties (facsimile, digitized reproduction, illustrated, etc.) do not affect the relation class. A facsimile or a digitized reproduction of the target counts as present if its relation is one of the three classes above.

There is no restriction on publication year in Q3.

BLV018 (Tagore): the target work is the English translation *Four chapters*. The Bengali original (*Char Adhyay*) and translations into other languages are `other_language_version`.

BLV021 is an unresolved unit. Its Q3 result is retrieval evidence only and does not contribute to any W-level value.

### 3.3 Human review scope

The human reviewer confirms or corrects:

- every row the AI coded as present; and
- every row with `via_title_route` = true and `r3` = true that the AI coded as not present.

Other rows are not reviewed by a human; their AI code stands. `q3_review.tsv` keeps `ai_relation`, `human_relation`, `human_note`, `final_relation` and `final_source` (`human` or `ai`) as separate columns.

## 4. Target-level classification

Applied deterministically to the final record codes (§3.3), after the human review:

- **`title_route_hit`** — at least one record with `via_title_route` = true, `r3` = true and final relation present. This target is not classified further under Q3 (protocol §8 applies only to zero T1–T3 acceptances).
- **`title_route_miss`** — not `title_route_hit`, and at least one record with `a1k1_only` = true and final relation present.
- **`absent_all_routes`** — no record from any route has final relation present.

Records with `via_title_route` = true, `r3` = false and final relation present are reported separately as `title_route_r3_miss` (retrieved by a title route but not matched by R3). They are not counted as `title_route_hit` or as `title_route_miss`, because they are a matching failure, not a retrieval failure. A target whose only present records are of this kind is reported with that note and is not forced into either class.

When `any_route_incomplete` is true, the class is kept and the incomplete routes are reported alongside it. In particular, `absent_all_routes` for such a target does not rule out a present record beyond the cap. No third class is added.

Output: `q3_target_classification.tsv`, one row per target, with the class, the counts behind it, `any_route_incomplete`, `incomplete_routes`, and for BLV017 a note that it is not blind.

## 5. Outputs added

```
derived/bl_calibration/verification_pilot_v1/
    q3_candidates.tsv
    q3_target_summary.tsv
    q3_llm_prompt.md
    q3_llm_run.json
    q3_llm_output.tsv
    q3_review.tsv
    q3_target_classification.tsv
```

Commit order: this addendum → extraction script → extraction output → prompt → AI output (unedited) → human review and target classification.

## 6. Scope of the conclusion

Q3 covers five targets, one of which (BLV017) is not blind. Its results are **illustrative examples** of how title routes and A1/K1 routes behave. They are not a statistical estimate for the population, and no rate of title-route misses or of absence is inferred from them.
