# Q3 LLM first-pass prompt — BL verification pilot v1

Prompt version: `q3_llm_prompt_v1`
Governing documents: protocol §7.1 (`b7ad972`), addendum 3 §3 (`0325107`).
This prompt is fixed before the model reads `q3_candidates.tsv`.

---

## Task

`q3_candidates.tsv` has one row per target × BL record (376 rows) for five targets. For **every row**, assign exactly one relation class (below) describing how the BL record relates to that row's target work, with a short reason and an uncertainty level.

Do not assign manifestation flags. Do not classify targets; target-level classes are computed later from the final record codes (addendum 3 §4). Do not edit any input file.

## The five target works

- **BLV017** *The Orange Fairy Book*, edited by Andrew Lang. Lang is the editor; he may appear in 100 or 700. Other books of Lang's coloured fairy-book series (Blue, Red, Green, …) are different works.
- **BLV018** *Four chapters*, by Rabindranath Tagore: the English translation of the Bengali novel *Char Adhyay*. An English-language edition of this novel is the target. The Bengali original, or a translation into any language other than English, is `other_language_version`.
- **BLV019** *The shen's pigtail*, by Julian Croskey. If the target book is itself a volume of stories under this title, a record of that volume is `target_alone`.
- **BLV020** *The Graysons*, by Edward Eggleston.
- **BLV021** Rudolf Erich Raspe's Baron Munchausen narratives (unresolved unit; title aliases: *The surprising adventures of Baron Munchausen*, *The singular adventures of Baron Munchausen*, *The adventures of Baron Munchausen*). An edition of the Munchausen narratives under any title is the target. Sequels or continuations by other writers are `related_derivative`.

## Relation classes (protocol §7.1; exactly one per row)

```
target_alone                  full text of the target, alone
target_with_other_works       target is the lead or co-title work (e.g. 245$a = target,
                              245$b names further works)
target_in_collection          target is one item in a volume titled otherwise
                              (collected works, omnibus, anthology)
target_excerpt                only part of the target
target_abridged_or_retold     abridged, simplified, graded reader, retold
                              (including children's retellings)
other_language_version        target in a language other than the target work's own
adaptation                    other medium or genre (play, film, opera, graphic novel, …)
related_study_guide           study guide, notes, teaching aid
related_criticism             criticism or scholarship about the target
related_derivative            sequel, prequel, parody, pastiche by others
unrelated                     not the target and not related to it, including
                              (a) title or name collisions and
                              (b) other works by the same author or editor
ambiguous                     cannot be decided from the record
other                         none of the above (reason required)
```

## Rules

1. Decide from the record's fields only: 245, 246, 240/130, 250, 260/264, 008 date and language, 041, 100, 700, the 505 and 600$t indicators. The R1–R3 columns and `routes` describe how the record was found; they are not evidence that it is the target.
2. General knowledge may be used **only** to recognise that a title, translation title or name form refers to the target work (e.g. that *Char Adhyay* is the same novel), or that a book is a different work by the same author. It must not be used to decide that a record exists or does not exist, or to supply facts absent from the record.
3. Facsimiles, reprints, microfilm or digitized reproductions of the target are coded by relation as usual (normally `target_alone`); being a reproduction does not change the class.
4. A collected or selected works volume whose record does not show that it contains the target (no title in 245/246, 505 indicator absent, no matching 700$t) is `ambiguous`, not `target_in_collection`.
5. When the record language (008/041) differs from the target's language, prefer `other_language_version` unless the record is clearly bilingual with the target text.
6. Use `ambiguous` rather than guessing. Use `other` only with a reason.

## Output

Write `q3_llm_output.tsv` (tab-separated, LF line endings, one row per input row, same order as `q3_candidates.tsv`), columns:

```
sample_id
marc_001
llm_relation
llm_reason              one sentence citing the fields used
llm_uncertainty         none | low | medium | high
```

Record in `q3_llm_run.json`: the model identifier actually running, the prompt version, the sha256 of this prompt file and of each input file, and the number of rows written.
