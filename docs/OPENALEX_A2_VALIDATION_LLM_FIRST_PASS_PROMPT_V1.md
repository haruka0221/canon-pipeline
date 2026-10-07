# OpenAlex A2 Validation LLM First-Pass Prompt v1

You are performing a provisional blind adjudication of OpenAlex retrieval
candidates for literary works.

Use only the information supplied in each row, especially:

- `target_title`
- `target_author`
- `openalex_display_name`
- `openalex_abstract`

Do not browse the web.
Do not use outside knowledge to fill gaps.
Do not infer validity merely because the record concerns the same author,
period, national literature, or topic.

For each candidate, decide whether the OpenAlex record substantively refers
to the specific target literary work.

Allowed provisional judgments:

- `VALID_TARGET_REFERENCE`
- `INVALID_TARGET_REFERENCE`
- `UNCERTAIN`

Use `UNCERTAIN` whenever the supplied title and abstract do not provide enough
evidence for a reliable decision. Do not treat uncertainty as invalidity.

Allowed reason codes for VALID:

- `DIRECT_WORK_REFERENCE`
- `AUTHOR_AND_WORK_CONTEXT`
- `OTHER_VALID`

Allowed reason codes for INVALID:

- `TITLE_COLLISION_DIFFERENT_WORK`
- `GENERIC_OR_LEXICAL_MATCH`
- `WRONG_WORK_SAME_AUTHOR`
- `AUTHOR_COLLISION`
- `OTHER_INVALID`

Allowed reason codes for UNCERTAIN:

- `INSUFFICIENT_CONTEXT`
- `OTHER_UNCERTAIN`

Return exactly one output row for every input candidate.

Output columns:

1. `validation_candidate_id`
2. `llm_first_pass_judgment`
3. `llm_first_pass_reason_code`
4. `llm_first_pass_note`

Notes should be concise and state the textual evidence supporting the
decision.

This is a provisional first pass only. Do not write or infer final human
judgments.
