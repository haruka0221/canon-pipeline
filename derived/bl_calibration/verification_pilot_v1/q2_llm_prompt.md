# Q2 LLM first-pass prompt — BL verification pilot v1

Prompt version: `q2_llm_prompt_v1`
Governing documents: protocol §5 (`b7ad972`), addendum 1 §3.2 and §5 (`5486bd0`), addendum 2 §3–§4 (`bde9d02`).
This prompt is fixed before the model reads `q2_candidates.tsv`.

---

## Task

You are given:

- `q2_ground_truth.tsv`: twelve rows, each an expected **first UK book edition** (year, publisher, place, note);
- `q2_candidates.tsv`: BL records linked to each row's sample(s) whose 008 Date 1 or 260/264 $c contains a year within the expected year ±1;
- `q2_candidates_diagnostics.tsv`: per row, the number of linked records with no extractable year.

For each ground-truth row, decide one of:

```
found                    a candidate is the expected first UK edition
not_found_determinable   no candidate is the expected edition
undetermined_cap         only for Q2R10 (Heart of Darkness), when no candidate
                         is the 1902 Youth volume (addendum 2 §3)
```

## Rules

1. A candidate matches when its **year** and **publisher** agree with the ground truth. Place may be absent or abbreviated. Publisher names may differ in form (e.g. "Ward, Lock", "Ward Lock & Co.", "Osgood, McIlvaine", "Longmans, Green"); treat these as the same publisher. A different publisher is not a match.
2. A US edition never matches a UK row, even if earlier (She, Kim, Burmese Days).
3. Sister Carrie (Q2R08): the expected edition is the abridged Heinemann 1901 edition. An abridged Heinemann 1901 record is a match.
4. Tess (Q2R02): the first edition is in three volumes. One record describing the set, or any record for one of its volumes, is a match. Note which.
5. Heart of Darkness (Q2R10): a match is only the 1902 Blackwood volume *Youth: A Narrative, and Two Other Stories*. If none, the decision is `undetermined_cap`, never `not_found_determinable`.
6. Later impressions, reissues, colonial or library editions dated within the window by the same publisher: if the record states it is not the first edition (e.g. "new edition", "second edition", a later impression in 250), it is not a match. If the record does not say, it is a match, and the uncertainty is stated in the reason.
7. Facsimiles, reprints by other publishers, and digitized reproductions are not matches even if they carry the original date.
8. Do not use knowledge beyond the records and the ground-truth table to decide that a record is or is not the first edition. You may use general knowledge only to recognise publisher name variants.
9. If several candidates match, give all their 001 values.
10. If the decision is `not_found_determinable` and the row has undated linked records (diagnostics), say so in the reason; do not inspect them.

## Output

Write `q2_llm_output.tsv` (tab-separated, LF line endings), one row per ground-truth row, columns:

```
q2_row_id
llm_decision
matched_marc_001        semicolon-separated, empty if none
llm_reason              one or two sentences citing the fields used
llm_uncertainty         none | low | medium | high
```

Do not edit any input file. Record the model identifier used in `q2_llm_run.json` together with the prompt version and the sha256 of this prompt file and of each input file.
