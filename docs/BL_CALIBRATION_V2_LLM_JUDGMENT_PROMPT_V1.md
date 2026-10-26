# LLM first-pass judgment prompt — BL calibration v2

Prompt version: `bl_v2_llm_judgment_prompt_v1`
Governing documents: `docs/BL_CALIBRATION_PROTOCOL_V2.md` §5, `docs/BL_CALIBRATION_V2_ADDENDUM_1.md`, v1 protocol §7.1 (`b7ad972`) for the relation vocabulary.
This prompt is fixed and committed before the model reads `judgment_input_v2.tsv`.

---

## Task

`judgment_input_v2.tsv` (private, outside the repository) has one row per target × BL record: 500 rows, 270 possible targets. Rows are in a random order and carry no matching-rule result. For **every row**, judge two things and write them back in the output file:

1. `work_relation` — is this BL record a manifestation of the target work?
   - `VALID`: the record describes the target work (in any of the publication relations below that start with `target_`, or `other_language_version`, or `adaptation` only if the adaptation carries the target's text).
   - `INVALID`: the record is a different work (title or name collision, another work by the same author, a related but distinct work, criticism, study guide, sequel by others).
   - `UNCERTAIN`: the record cannot be placed with the fields given.
2. `publication_relation` — exactly one class from the v1 §7.1 vocabulary:

```
target_alone                  full text of the target, alone
target_with_other_works       target is the lead or co-title work (245$a = target, 245$b names further works)
target_in_collection          target is one item in a volume titled otherwise (collected works, omnibus, anthology)
target_excerpt                only part of the target
target_abridged_or_retold     abridged, simplified, graded reader, retold
other_language_version        target in a language other than the target work's own
adaptation                    other medium or genre (play, film, opera, graphic novel, …)
related_study_guide           study guide, notes, teaching aid
related_criticism             criticism or scholarship about the target
related_derivative            sequel, prequel, parody, pastiche by others
unrelated                     not the target and not related to it (title/name collisions, other works by the same author)
ambiguous                     fields insufficient to choose among the classes above
```

`work_relation` and `publication_relation` must be consistent: `target_*`, `other_language_version` and (text-carrying) `adaptation` go with `VALID`; `related_*` and `unrelated` go with `INVALID`; `ambiguous` goes with `UNCERTAIN`.

## What the target is

Each row gives `target_titles` (all Open Library titles of the target, separated by ` | `) and `target_authors` (the Open Library query author, which may be wrong or incomplete: it is evidence, not truth). The target is the literary work those titles name. Treat the author as a strong but not decisive signal: a record whose title matches and whose 100/700 name is a known variant, pseudonym, or transliteration of the author is still `VALID`; a record whose title matches but is clearly by a different person is `INVALID` (title collision).

Notes on particular cases:

- A target title in a language other than English (e.g. Cyrillic) means the target is that original work; its English translation is `other_language_version` and `VALID`.
- A target whose Open Library title is a volume title ("… in two volumes. 2/2") stands for the whole work.
- If `target_authors` is visibly wrong for the title (e.g. a well-known work attributed to the wrong author), judge by the work the title names and say so in `reason`.
- Records of other works by the same author are `INVALID` / `unrelated`, however similar the title.
- Old records (pre-1975 cataloguing) may carry the title in 245$a with bracketed notes, subtitles after a colon, or "A novel." appended: these are still the target if the title is the target's.

## Output

Write `judgment_llm_output_v2.tsv` in the same private directory, tab-separated, one row per input row, in input order, with exactly these columns:

```
judgment_id    work_relation    publication_relation    confidence    reason
```

- `confidence`: `high` / `medium` / `low`.
- `reason`: one short sentence (≤ 25 words) naming the field(s) that decided it.
- Do not edit `judgment_input_v2.tsv` or any other file. Do not look at `judgment_sample_v2.tsv` or `matching_results_v2.tsv` (they hold the rule flags).
- Process in batches of 50 rows; after each batch, append to the output file and state the running row count. Finish with the total.

When done, report: the model identifier as shown by `/status`, the number of rows written, and the counts of `work_relation` and `publication_relation` values.
