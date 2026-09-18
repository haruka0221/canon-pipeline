# Wikidata Entity Resolution: Benchmark Design, Failure Modes, and Revised Workflow

## 1. Purpose

This note records the methodological lessons from rebuilding the Wikidata entity-resolution component of the literary-visibility pipeline. It is intended for future implementation, benchmark construction, and dissertation writing rather than as a chronological development log.

The task is to resolve an Open Library work record to the Wikidata entity that best represents the same **abstract literary work**. The target is therefore not merely a title match, and not any related Wikidata entity. Editions, translations, adaptations, performances, films, plays, and other derived or bibliographically related entities must be distinguished from the work-level entity.

A central lesson is that a high benchmark F1 score does not by itself guarantee that the benchmark is testing the correct bibliographic object. Wikidata may contain duplicate work-level items, edition-level items, incomplete metadata, misclassified entities, or newly created records that did not exist when an older gold set was annotated.

## 2. Development benchmark

The development benchmark contains 130 Open Library work records. Its original annotation consisted of:

- 82 positive cases with a Wikidata QID;
- 48 negative cases annotated as `NO_MATCH`.

Against that older benchmark, the earlier Claude-based resolver achieved approximately:

- Precision: 0.987
- Recall: 0.951
- F1: 0.969

Those figures are historically useful but should not be treated as the final benchmark result. Re-auditing showed that the old benchmark mixed several kinds of problems: edition-level gold QIDs, duplicate work-level items, time-sensitive `NO_MATCH` labels, and items that had changed or been added in Wikidata.

The final adjudicated benchmark created on 2026-09-11 contains:

```text
MATCH        83
NO_MATCH     42
AMBIGUOUS     5
TOTAL       130
```

Label provenance is retained explicitly:

```text
human_adjudication                 12
model_consensus_human_audited      15
model_consensus_unreviewed         103
```

The 12 directly adjudicated cases were reviewed without showing the human reviewer the model judgments. Live Wikidata could be consulted during verification, so this is best described as model-blind human adjudication rather than a metadata-only blind review.

The 15 consensus-audit cases were sampled from the 118 Claude/Gemini agreement cases using a fixed seed and stratified to include:

```text
Claude medium/low confidence    8
both models high confidence     7
```

All 15 human audit decisions agreed with the dual-model consensus. This should be reported as 15/15 agreement in the stratified audit sample, not as proof that model consensus is universally error-free.

The 130-item set should therefore be treated as a dated development and adjudication benchmark for the current Wikidata state, not as a timeless truth set.

## 3. What counts as the “same work”?

A single strict Wikidata QID is often too narrow as a gold representation. Several distinct situations occur:

1. **One clear work-level item** — straightforward case.
2. **One work plus many editions/translations** — e.g. *The Call of the Wild*. Thousands of author-linked items may be editions or translations and should collapse to the parent work when `P629` is available.
3. **Multiple work-level Wikidata items for the same conceptual work** — e.g. *Kim*. Q589868 and Q19086249 both appear to represent Kipling's 1901 novel, although Q589868 is much richer.
4. **A related edition exists but no usable work-level parent is represented** — e.g. *At Fault*. Q131573518 is typed as `version, edition or translation`, but has no usable `P629` parent.
5. **Adaptation or derived work instead of the target** — e.g. *Life with Father*, where the available candidate is the 1939 play rather than Clarence Day's source literary work.
6. **Compound or bundled bibliographic records** — e.g. *The Fortunes of Nigel ; Count Robert of Paris*, where one input record corresponds to two distinct works.

This requires separating **entity identity**, **bibliographic granularity**, and **canonical-QID selection**.

## 4. Why title-only search is insufficient

General Wikidata title search is useful as a fallback but unsuitable as the primary retrieval mechanism. Short, generic, reused, and non-literary titles make global title search noisy.

The production logic therefore remains **author-first**:

1. resolve the author entity;
2. retrieve all items linked by `P50`;
3. compare title fields within the author's linked works;
4. normalize edition/translation items to parent works where possible;
5. use global title search only as a fallback.

The `Kim` case demonstrates why this matters: author-first retrieval immediately surfaced the relevant work items, whereas global title search did not reliably rank them highly.

## 5. Failure in the earlier pipeline: `LIMIT 100`

The earlier author-first pipeline used:

```sparql
SELECT DISTINCT ?work WHERE {
  ?work wdt:P50 wd:AUTHOR_QID.
}
LIMIT 100
```

This is unsafe for two independent reasons.

First, prolific authors can have far more than 100 `P50`-linked items. Observed author-linked item counts included hundreds for Conrad and thousands for H. G. Wells and Jack London.

Second, the query had no `ORDER BY`. The returned 100 items were therefore not a reproducible sample of the author's work universe. Re-running the same query at a later date can yield a different 100-item set as Wikidata and the query service change.

A concrete failure appeared in the older Luna evaluation for Robert Louis Stevenson. Both *Treasure Island* and *Strange Case of Dr Jekyll and Mr Hyde* were resolved to Q108971503. The old run logged:

```text
author=Robert Louis Stevenson | author_qid=Q1512(API_exact) | works=100 | main=Q108971503
```

for both targets.

In the current Wikidata state, Q108971503 has no useful English label, description, alias, `P1476`, or `P577`; it is linked to Stevenson through `P50`. A current rerun of the same unordered `LIMIT 100` query did not even return Q108971503. Because the historical candidate set was not persisted, the exact old candidate configuration cannot be reconstructed.

This makes the failure methodological rather than merely anecdotal:

1. the candidate universe was truncated;
2. the truncation was unordered and therefore non-reproducible;
3. metadata-poor author-linked items remained eligible for LLM selection;
4. the raw candidate set was not saved.

Rule: never truncate the author-linked `P50` universe before candidate generation.

Rule: persist the exact candidate QIDs supplied to every judge or resolver run.

At production scale, repeated public WDQS requests should be replaced by a local Wikidata dump, cache, or index.

## 6. Candidate-generation experiments

Using the 82 positive benchmark items and known correct author QIDs to isolate the work-candidate-generation stage:

- all 82 gold items were linked from their author's `P50` set;
- no positive item was absent from the author-linked universe.

A simple title-similarity ranking gave high recall, but raw ranks were misleading because many editions share the same title. *The Call of the Wild* is the clearest example: thousands of exact-title author-linked records were editions/translations.

This showed that raw top-k ranking over author-linked items is not sufficient.

## 7. Exact-title buckets

An exact-title experiment over the 82 positive cases showed that most targets become easy once the author is correct:

- 46/82 had an exact-title bucket of size 1;
- 72/82 had bucket size ≤ 3;
- 76/82 had bucket size ≤ 5;
- 77/82 had the gold item in the exact-title bucket.

One extreme outlier was *The Call of the Wild*, with thousands of exact-title items before edition collapse.

The practical implication is:

> use exact-title matching first, but collapse bibliographic manifestations before invoking an LLM.

The difficult cases are often not fuzzy-title cases at all; they are **granularity**, **duplicate entity**, or **metadata quality** cases.

## 8. Using `P629` to collapse editions and translations

Wikidata property `P629` (“edition or translation of”) is structurally valuable:

```text
edition / translation item
    └── P629 → parent work
```

### New Grub Street

Old gold:

- Q7007870
- description: 1891 Smith, Elder & Co. edition
- `P629 → Q29053296`

Parent:

- Q29053296
- description: novel by George Gissing

The old gold therefore pointed to an edition, while the work-level gold should be Q29053296.

### The Call of the Wild

Thousands of edition/translation records collapse to a single parent work-level entity. This is exactly the type of case where structural normalization should occur before LLM judgment.

### Limitation

`P629` is incomplete and cannot be the only granularity signal. *At Fault* is typed as `version, edition or translation` but has no usable `P629` parent. The pipeline must therefore inspect `P31`, `P629`, title, author, date, and description jointly.

## 9. Gold-standard audit

The 82 previous positive gold items were first audited for `P629`:

- 81 unchanged;
- 1 collapsed through `P629`: *New Grub Street*, Q7007870 → Q29053296.

A subsequent `P31` audit found one additional granularity problem:

- *At Fault* Q131573518;
- `P31 = version, edition or translation`;
- no `P629` parent.

Thus the old positive gold contained at least two distinct granularity problems:

1. an edition with a recoverable parent work;
2. an edition with no usable parent work.

These should not be represented identically in the benchmark.

## 10. Author resolution is itself fallible

Candidate generation depends on author resolution, and a wrong author QID can remove the correct work from the author-first candidate universe.

### Robert Elsmere

Input author string:

```text
Humphry Ward
```

The initial resolver chose Q7790900, Thomas Humphry Ward. But *Robert Elsmere* was written by Mary Augusta Ward, Q952452, whose historical naming includes “Mrs. Humphry Ward”. Global title-search fallback recovered the correct work, Q7344052.

This shows that author strings can encode married names, pseudonyms, initials, catalog conventions, and historical naming practices. Author resolution must therefore be treated as a fallible upstream decision, not as ground truth.

## 11. Metadata incompleteness and search-index discrepancies

Wikidata search may know about an entity even when entity metadata expose little useful English information.

### At Fault

Q131573518 had:

- no useful English label in the retrieved entity metadata;
- no English description;
- no `P1476`;
- `P31 = version, edition or translation`.

Yet Wikidata's search index returned it for `At Fault`.

Candidate generation therefore cannot rely only on `rdfs:label`, `P1476`, or local title similarity. A global title-search fallback is necessary for metadata-poor records.

## 12. Revised candidate-generation workflow

```text
target title + author
        │
        ▼
resolve author QID
        │
        ▼
retrieve ALL P50-linked items
        │
        ▼
collect lightweight title evidence
(label + P1476 + P629)
        │
        ▼
normalize titles
        │
        ├── exact matches
        └── fuzzy-ranked author-linked candidates
        │
        ▼
collapse P629 edition/translation items to parent work
        │
        ▼
if exact author-title match is absent:
    run global Wikidata title-search fallback
        │
        ▼
deduplicate candidate QIDs
        │
        ▼
retrieve detailed metadata only for shortlisted candidates
```

### Stage 1: candidate generation

Use lightweight data to create candidate QID sets. Do not fetch full metadata for every item attached to prolific authors.

### Stage 2: candidate enrichment

After candidate QIDs are known:

1. deduplicate QIDs globally;
2. fetch entity metadata in batches;
3. cache results locally;
4. attach metadata to each target's candidate packet.

This substantially reduces API load and rate-limit failures.

## 13. Stage 1 benchmark result

The final Stage 1b candidate generator achieved:

```text
positive candidate recall = 82 / 82 = 1.000
```

Gold-rank distribution in the combined candidate lists:

- rank 1: 77/82 = 0.939
- rank ≤ 3: 80/82 = 0.976
- rank ≤ 5: 81/82 = 0.988
- rank ≤ 20: 81/82 = 0.988
- rank ≤ 25: 82/82 = 1.000

The sole apparent rank-24 case was *At Fault*. This was not genuinely the 24th-best search result: title-search candidates had simply been appended after 20 author-fuzzy candidates. In Wikidata title search, the relevant entity appeared much higher.

Therefore, candidate provenance should be preserved instead of collapsing all sources into one artificial rank.

Recommended provenance labels:

```text
author_exact
author_fuzzy
title_search
```

## 14. Candidate provenance is evidence, not truth

The source of a candidate is useful context, but not a correctness label:

- `author_exact` can still be an edition or wrong-granularity entity;
- `author_fuzzy` can contain the true work when title metadata are incomplete;
- `title_search` can recover a work after author resolution fails;
- title-search candidates can be correct even when API labels/descriptions are missing.

The judge should therefore receive provenance as context, not as a hard ranking rule.

## 15. Stage 2 metadata packet

The Stage 2 process collected metadata for all candidate QIDs in bulk.

Current development set:

- 130 targets;
- 1,407 unique candidate QIDs;
- 1,744 cached entities including related entities.

Candidate metadata includes:

- QID;
- candidate source;
- English label;
- description;
- aliases;
- `P1476` stated titles;
- `P577` publication dates;
- `P31` instance-of values;
- `P50` authors;
- `P629` parent-work links;
- English Wikipedia sitelink presence.

## 16. Work-level judgment policy

The benchmark target is explicitly the **abstract literary work**.

### MATCH

A supplied candidate represents the target at work level.

### NO_MATCH

Return `NO_MATCH` when:

- no supplied candidate represents the work;
- only an edition or translation is available without a usable work-level parent;
- only an adaptation, film, performance, or derived work is available;
- supplied candidates represent different works.

### AMBIGUOUS

Return `AMBIGUOUS` when multiple supplied work-level QIDs plausibly represent the same conceptual work and cannot be collapsed mechanically.

## 17. Representative ambiguity cases

### Kim

Two work-level items:

- Q589868
- Q19086249

Both correspond to Kipling's 1901 *Kim*. Q589868 is much richer and is the better canonical representative, while Q19086249 is sparse and contains questionable metadata.

Recommended benchmark representation:

```text
primary_qid = Q589868
acceptable_equivalent_qids = [Q589868, Q19086249]
```

### Heart of Darkness

Multiple work-level-looking items also appear to represent the same conceptual work, again motivating equivalence-aware evaluation rather than strict single-QID scoring.

## 18. Why strict single-QID accuracy is insufficient

At least three evaluation questions should be separated.

### 1. Match-decision accuracy

Did the system correctly decide whether a work-level Wikidata representation exists among the candidates?

### 2. Work-equivalence accuracy

Did the predicted QID belong to the acceptable set of QIDs representing the same conceptual work?

```text
prediction ∈ acceptable_equivalent_qids
```

### 3. Canonical-QID accuracy

Did the system select the preferred primary QID?

A model can be bibliographically correct but fail strict QID accuracy because Wikidata contains duplicate work records.

## 19. Benchmark schema

The adjudicated benchmark currently uses three top-level decisions:

```text
MATCH
NO_MATCH
AMBIGUOUS
```

Cases such as *At Fault*, where a related edition exists but no acceptable work-level item is available, remain `NO_MATCH` at the decision level and are distinguished through issue codes such as:

```text
edition_without_work_item
```

This avoids introducing a fourth decision class into the frozen judge schema while still preserving the bibliographic distinction.

The final benchmark file is:

```text
derived/benchmark/judgments/adjudication/
    wikidata_benchmark_adjudicated_final_130.csv
```

Core fields include:

```text
target_id
title
author
author_qid

gold_decision
gold_selected_qid
gold_alternative_qids
gold_issue_codes
gold_confidence
gold_notes

gold_source
label_source
human_audit_status
human_audit_stratum
```

For longer-term reuse, the benchmark should also preserve or add:

```text
edition_qids
adaptation_qids
other_related_qids

difficulty
annotation_date
wikidata_snapshot_or_revision_info
```

The key principle is that the benchmark must preserve both the identity judgment and the provenance of that judgment.

## 20. Recommended evaluation metrics

Report more than one score:

- match-decision precision / recall / F1;
- strict canonical-QID accuracy;
- equivalence-aware Top-1 accuracy;
- candidate recall@k;
- work-level candidate recall;
- granularity/type error rate;
- ambiguous-case accuracy;
- unambiguous-case accuracy;
- author-resolution failure rate;
- retrieval failure rate.

Technical failures must never be silently converted to `NO_MATCH`.

## 21. Dual-model consensus and human adjudication

The final benchmark does not define truth by simple model majority.

Two independent model judgments were used to triage review:

- Claude Sonnet 5, high effort;
- Gemini 3.1 Pro.

Both models received the same model-neutral candidate packet and the same work-level identity policy. Old gold labels were hidden. The task was to judge the supplied candidate set, not to browse for an answer.

The two judges agreed on the decision for 124/130 targets. Six decision disagreements occurred. Agreement alone was not considered sufficient for difficult cases: the mandatory review set was combined with the seven-case regression/challenge set, producing 12 unique human-adjudication targets.

The final 12 model-blind human decisions were:

```text
AMBIGUOUS    5
MATCH        3
NO_MATCH     4
```

These included all major duplicate-work cases and difficult granularity cases such as *At Fault*, *Peter Pan*, *With Roberts to Pretoria*, and *Life with Father*.

A particularly important result is *Life with Father*: both Claude and Gemini accepted Q14396011, but human adjudication rejected it because the candidate describes the 1939 play by Howard Lindsay and Russel Crouse rather than Clarence Day's source literary work. This demonstrates that correlated model agreement can still preserve a shared error.

After the 12 direct adjudications, 15 of the remaining 118 consensus cases were selected for a fixed-seed stratified audit:

- 8 from cases where Claude self-reported medium/low confidence;
- 7 from cases where both models reported high confidence.

The human reviewer agreed with the model consensus in all 15 cases.

The final label provenance is therefore:

```text
12  human_adjudication
15  model_consensus_human_audited
103 model_consensus_unreviewed
```

This resource should be described as dual-model consensus with targeted human adjudication and stratified human audit.

### Why Luna was not used as a third gold judge

Luna was used during prompt development and regression testing. Treating it as a fully independent third gold creator would therefore weaken the independence of the adjudication design. Luna is better reserved for sensitivity analysis, regression testing, and evaluation against the final benchmark.

### Bulk-judge failure mode: self-generated heuristic classifiers

An earlier Gemini bulk run responded to the task by constructing its own fixed rule-based classifier with title thresholds, author-overlap scores, and hard-coded entity-type rules. That run is not treated as an independent LLM judgment.

For bulk judging, the execution instruction should explicitly prohibit the model from replacing item-by-item judgment with a newly invented scoring classifier. Code may be used for CSV parsing, validation, progress tracking, and output writing, but not to define the identity decision rule.

If this execution constraint is incorporated into the stored prompt, it should be versioned rather than silently overwriting the frozen prompt used in earlier experiments.

## 22. Frozen judge prompt and decision schema

The work-level policy was frozen in:

```text
prompts/wikidata_judge_v1.txt
```

Output schema:

```json
{
  "decision": "MATCH | NO_MATCH | AMBIGUOUS",
  "selected_qid": "Q... | null",
  "alternative_qids": ["Q..."],
  "confidence": "high | medium | low",
  "issue_codes": [],
  "reason": "brief explanation"
}
```

Current issue codes:

```text
duplicate_work_items
edition_or_translation
edition_without_work_item
adaptation
author_ambiguity
missing_metadata
title_variant
wrong_work
```

The prompt explicitly states that the target is an abstract literary work and that edition-level or adaptation-level entities should not be accepted merely because no better candidate exists.

Candidate provenance is included as evidence, not as a correctness label.

For bulk chat-based judging, an additional execution constraint was required: the judge must inspect targets individually and must not construct a separate rule-based or heuristic scoring classifier to substitute for the requested semantic judgment. If retained for future runs, this wrapper instruction should be stored and versioned explicitly.

### Later versioned judge revisions

Subsequent production validation used versioned revisions rather than silently
overwriting the original development prompt:

- `prompts/wikidata_judge_v1.txt`: original frozen development judge;
- `prompts/wikidata_judge_v2.txt`: added explicit handling for sparse metadata
  and duplicate-work cases;
- `prompts/wikidata_judge_v3.txt`: added an explicit work-identity and
  bibliographic-granularity policy derived from error analysis on the first
  unseen diagnostic sample.

The v3 prompt was frozen before evaluation on the final untouched 50-record
holdout. Results from that holdout were not used to revise the reported v3
system.

## 23. Diagnostic seven-case regression test

Before scaling to all 130 records, seven deliberately difficult cases were used:

- *Heart of Darkness*
- *Kim*
- *Robert Elsmere*
- *At Fault*
- *New Grub Street*
- *With Roberts to Pretoria*
- *Life with Father*

The frozen work-level policy produced the expected distinctions:

- *Heart of Darkness* → duplicate work-level ambiguity;
- *Kim* → duplicate work-level ambiguity;
- *Robert Elsmere* → correct work recovered despite initial author-resolution error;
- *At Fault* → no acceptable work-level match;
- *New Grub Street* → edition normalized to parent work;
- *With Roberts to Pretoria* → supplied candidates are other works;
- *Life with Father* → available candidate is an adaptation/play, not the source literary work.

This set should be retained as a regression test for future changes.

## 24. Negative examples must be periodically re-audited

The previous 48 `NO_MATCH` items cannot be treated as permanent negatives. Several now have plausible current Wikidata work entities, including:

- *The Silk Stocking Murders*
- *Og, Son of Fire*
- *Consider Her Ways*
- *Briton or Boer?*
- *Ferdinand And Isabella*
- *A Sailor's Sweetheart*

Possible explanations include Wikidata changes, old candidate-generation failures, incomplete old gold, or newly added metadata/author links.

Therefore:

> Wikidata benchmark annotations should record an annotation date and ideally a Wikidata revision or snapshot reference.

A `NO_MATCH` label is a time-sensitive claim about a changing knowledge base.

## 25. Engineering lessons for production scale

### Do

- freeze the target population;
- cache author resolution;
- cache Wikidata entity metadata;
- retrieve all author-linked `P50` items before candidate reduction;
- separate candidate generation from candidate enrichment;
- batch API requests;
- checkpoint intermediate results;
- preserve candidate provenance;
- persist the exact candidate set used for each target and each run;
- distinguish retrieval errors from genuine `NO_MATCH`;
- save raw candidate sets and final judgments separately;
- record software, prompt, model, and annotation versions;
- retain old benchmark labels rather than overwriting them;
- use deterministic seeds for audit sampling;
- record whether human review was model-blind and whether live Wikidata was consulted.

### Do not

- issue one detailed API request per candidate;
- truncate prolific authors arbitrarily;
- use unordered `LIMIT` as a hidden sampling mechanism;
- rely only on title search;
- rely only on English labels;
- accept an author-linked item with no title evidence merely because metadata may be incomplete;
- treat `P31` as perfectly reliable;
- treat `P629` as complete;
- assume one conceptual work always has one Wikidata QID;
- treat model agreement as automatically correct;
- allow a bulk LLM judge to replace semantic review with a self-generated heuristic classifier;
- overwrite old gold without preserving the original annotation.

At full scale, use a local Wikidata dump/index or another locally cached representation instead of repeatedly querying public WDQS.

## 26. Reproducibility artifacts

Important current files include:

```text
derived/benchmark/full_eval_130items.tsv
derived/benchmark/full_eval_130items_worklevel_v2.tsv

derived/benchmark/wikidata_candidate_generator_v2.tsv
derived/benchmark/wikidata_candidates_stage1_130.jsonl
derived/benchmark/wikidata_candidates_stage1b_130.jsonl

derived/benchmark/wikidata_candidate_metadata_cache.json
derived/benchmark/wikidata_annotation_packets_stage2_130.jsonl

prompts/wikidata_judge_v1.txt
derived/benchmark/wikidata_judge_luna_test.jsonl
```

Judge inputs and raw/normalized judgments:

```text
derived/benchmark/judgments/input/
    wikidata_judge_input_130.csv

derived/benchmark/judgments/raw/
    claude_sonnet5_high_2026-09-11.csv
    gemini_3.1_pro_2026-09-11.csv

derived/benchmark/judgments/normalized/
    claude_sonnet5_high_2026-09-11.csv
    gemini_3.1_pro_2026-09-11.csv
```

Human adjudication and audit:

```text
derived/benchmark/judgments/adjudication/
    human_adjudication_packet_12.csv
    human_adjudication_blind_12.md
    human_adjudication_decisions_12.csv

    consensus_audit_sample_15.csv
    consensus_audit_blind_15.md
    consensus_audit_decisions_15.csv

    wikidata_benchmark_adjudicated_draft_130.csv
    wikidata_benchmark_adjudicated_final_130.csv
```

Final evaluation:

```text
derived/benchmark/judgments/adjudication/
    wikidata_final_gold_evaluation_summary.csv
    wikidata_final_gold_evaluation_details.csv
```

Supporting scripts include:

```text
scripts/validate_wikidata_judgments.py
scripts/normalize_wikidata_judgments.py
scripts/compare_wikidata_judgments.py
scripts/build_wikidata_adjudication_packet.py
scripts/build_wikidata_blind_adjudication.py
scripts/sample_wikidata_consensus_audit.py
scripts/build_wikidata_consensus_audit_packet.py
scripts/finalize_wikidata_benchmark.py
scripts/evaluate_wikidata_against_final_gold.py
```

### Unseen-holdout artifacts

```text
derived/benchmark/holdout/
    unseen_random100_seed20260912.tsv
    unseen_random50_review51_100_seed20260912.tsv

derived/benchmark/holdout/random50_v3_final/
    stage2_packets.jsonl
    judgments.jsonl
    results.tsv
    FINAL_HOLDOUT_SHA256.txt

derived/benchmark/holdout/random50_v3_final/human_gold/
    random50_human_blind_51_100.tsv
    random50_candidate_packet_blind_51_100.md

prompts/
    wikidata_judge_v2.txt
    wikidata_judge_v3.txt

scripts/
    wikidata_resolver_production.py
```

Key frozen SHA-256 values for the final v3 holdout include:

```text
target input
1380a1f369ae92818f0762cf7e03e6470e851a9e3b3092ca458970f77d2859dc

v3 prompt
e72640f4af84d86cf3f71efbdba06e5972b6882ab2d53ee7c1a33b1a551ab2ca

resolver script
a57041f928e5f72fb8fc23603b9b1c7cbb0032bd554c5aa7f5e4501c6a662993

Stage 2 packet
5dd4a0c10107a418acaf332cb4405dca2c6df024e72380555f8aeaf28d2643e1

frozen judgments
0a2b6a4d58e7439fa656502cb2ae97c3191ccfed160d8b8af29fbd4693b1ac03

frozen results
83baca18a761ddcb44852b1d4f0eb80c540d63ccf38a4d97db4828b0df6c75e5

completed manual gold
c4aa43c60f5840d69adb28338474f7e5ae6de4a235d1981b6b92496dc5a84470
```

These artifacts represent different methodological stages and should not be conflated:

```text
old benchmark
→ work-level gold audit
→ candidate generation
→ title-search fallback enhancement
→ metadata enrichment
→ frozen model judgments
→ model-blind human adjudication
→ stratified consensus audit
→ final adjudicated benchmark
→ final system evaluation
```

## 27. Final benchmark and system evaluation

The final adjudicated benchmark contains:

```text
MATCH        83
NO_MATCH     42
AMBIGUOUS     5
```

For match-detection evaluation, `MATCH` and `AMBIGUOUS` are treated as positive cases because both indicate that at least one acceptable work-level Wikidata representation is available among the candidates. `NO_MATCH` is negative.

Three distinct evaluation questions are reported:

1. match detection: does an acceptable work-level representation exist?
2. primary-QID accuracy: did the system choose the preferred canonical QID?
3. set-aware accuracy: did the system choose either the preferred QID or an accepted equivalent work-level QID?

### Earlier pipeline

```text
TP = 81
FN = 7
FP = 0
TN = 42

Precision = 1.000
Recall    = 0.920
F1        = 0.959

Primary QID accuracy, all targets       = 0.931
Set-aware accuracy, all targets         = 0.931
Primary QID accuracy, positive targets  = 0.898
Set-aware accuracy, positive targets    = 0.898
AMBIGUOUS primary/set-aware             = 1.000 / 1.000
```

The earlier system was conservative: it produced no false positives but missed seven now-valid positive works.

### Luna enhanced-light resolver

```text
TP = 88
FN = 0
FP = 4
TN = 38

Precision = 0.957
Recall    = 1.000
F1        = 0.978

Primary QID accuracy, all targets       = 0.954
Set-aware accuracy, all targets         = 0.954
Primary QID accuracy, positive targets  = 0.977
Set-aware accuracy, positive targets    = 0.977
AMBIGUOUS primary/set-aware             = 1.000 / 1.000
```

The Luna resolver recovered all positive cases but over-matched four negative cases and selected the wrong QID for two positive cases.

The older F1=0.969 figure should not be directly compared as if it measured the same target. The final evaluation uses a substantially revised work-level benchmark with human adjudication, explicit ambiguity, and updated Wikidata state.

## 28. Error analysis against the final benchmark

The final benchmark makes the qualitative trade-off between the two earlier systems visible.

### Earlier pipeline: false negatives

Seven current work-level matches were missed:

```text
The Octopus, a Story of California
The Silk Stocking Murders
Og, Son of Fire
Consider Her Ways
Briton or Boer?
Ferdinand And Isabella
A Sailor's Sweetheart
```

Several of these have high Q-number identifiers and may reflect Wikidata growth or changed metadata since the older benchmark run. Their histories should be checked before attributing every miss to the old resolver itself.

### Earlier pipeline: wrong granularity

Two positive cases were detected but mapped to the wrong entity:

```text
New Grub Street
    predicted Q7007870
    final work-level Q29053296
    reason: edition rather than parent work

Peter Pan
    predicted Q19032697
    final work-level Q3435337
    reason: dramatic-work/play representation rather than the target literary work
```

These cases directly motivate work-level normalization and explicit adaptation/granularity rules.

### Luna enhanced-light: false positives

Four negative cases were over-matched.

#### The Fortunes of Nigel ; Count Robert of Paris

The input record is compound: it contains two distinct Walter Scott works. Luna selected Q3230799 for *The Fortunes of Nigel*, matching only the first half of the bibliographic record. A single-work resolver should not silently collapse a compound record to one component.

#### With Roberts to Pretoria

Luna selected Q124091395, *With Buller in Natal*, another G. A. Henty novel. This is a wrong-work error caused by overvaluing author identity and partial title similarity.

#### Life with Father

Luna selected Q14396011. The candidate is described as the 1939 play by Howard Lindsay and Russel Crouse, although its author metadata also include Clarence Day. This is an adaptation/conflation error. It is especially important because Claude and Gemini also agreed on the same incorrect match before human adjudication.

#### Poor Fool

Luna selected Q5724950, an Erskine Caldwell-linked item with no useful English label, description, stated title, or date in the retrieved metadata. This shows that author linkage alone must not rescue a metadata-poor item when there is no positive title evidence.

### Luna enhanced-light: wrong QIDs for Stevenson

For both *Treasure Island* and *Strange Case of Dr Jekyll and Mr Hyde*, the older Luna resolver returned Q108971503 even though the final work-level QIDs are Q185118 and Q217352 respectively.

The old logs show:

```text
author=Robert Louis Stevenson
author_qid=Q1512(API_exact)
works=100
main=Q108971503
```

for both targets.

The historical pipeline retrieved an unordered `LIMIT 100` subset of Stevenson-linked items and cached that subset for the author. Current Wikidata metadata for Q108971503 provide almost no title-level evidence, and a current rerun of the same unordered query does not return Q108971503 in the first 100 items.

Because the historical candidate set was not persisted, the exact old selection cannot be reconstructed. The safest diagnosis is therefore:

```text
non-reproducible truncated candidate retrieval
+ permissive treatment of metadata-poor author-linked candidates
+ LLM candidate selection
```

rather than a simple hallucination claim.

### Production implications

The production resolver should therefore:

1. retrieve all author-linked items;
2. preserve exact candidate sets;
3. prioritize exact normalized title evidence before fuzzy comparison;
4. include `P1476`, aliases, `P31`, `P50`, `P577`, and `P629`;
5. collapse edition/translation items through `P629` where possible;
6. reject metadata-poor author-linked candidates without affirmative title evidence;
7. distinguish source works from adaptations and dramatic derivatives;
8. flag compound bibliographic records rather than forcing one component as the answer;
9. use title search only as a fallback;
10. run the frozen semantic judge only after candidate generation and structural normalization.

## 29. Recommended production workflow

The older `enhanced_light` resolver should not be incrementally patched into the production system. The more reproducible design is the Stage 1 → Stage 2 → judge architecture already validated on the benchmark.

```text
Open Library target
    │
    ├── normalize title / author
    │
    ▼
resolve author QID
    │
    ▼
retrieve ALL P50-linked items
    │
    ▼
collect lightweight evidence
(label + P1476 + P629 + provenance)
    │
    ├── exact normalized title candidates
    │
    └── fuzzy author-linked candidates
    │
    ▼
collapse P629 editions/translations
    │
    ▼
if needed: global title-search fallback
    │
    ▼
deduplicate candidate QIDs
    │
    ▼
Stage 2 batched metadata enrichment
    │
    ▼
frozen semantic work-level judge
    │
    ▼
MATCH / NO_MATCH / AMBIGUOUS
```

Deterministic structure should do as much work as possible before an LLM is invoked. The LLM should resolve bibliographic identity among a compact, persisted candidate set rather than compensate for incomplete or unstable retrieval.

## 30. Unseen holdout validation of the production resolver

After the development benchmark and production workflow had been established,
the resolver was evaluated on records sampled from the Open Library population
that had not been used in the 130-item development benchmark.

The unseen sample was drawn from the remaining Open Library population using
the fixed seed `20260912`. Model predictions were hidden during manual review.
The review could consult live Wikidata and external bibliographic evidence.
Because LLM assistance was used during manual verification, this evaluation is
best described as **prediction-blind manual verification with LLM-assisted
review**, rather than as a purely human-only gold standard.

### Initial unseen diagnostic sample

The first 50 reviewed records were evaluated using the v2 work-level judge.

```text
records reviewed              50
exact decision agreement      47 / 50 = 0.940

gold positive cases           15
gold negative cases           35

TP = 14
FN = 1
FP = 2
TN = 33

Precision = 0.875
Recall    = 0.933
F1        = 0.903
Specificity = 0.943

Primary-QID accuracy,
gold-positive cases           14 / 15 = 0.933

Set-aware Top-1 accuracy,
gold-positive cases           14 / 15 = 0.933
```

The three disagreements all exposed bibliographic-granularity boundaries:

- *Henri Quatre, king of France*: the target represented only one component of
  a larger combined work selected by the resolver;
- *King Arthur*: an abridged or retold derivative was incorrectly normalized
  to the underlying source work;
- *Cinq-Mars, Adapted and edited by G. G. Loane*: the resolver was too strict
  and failed to normalize the record to the underlying work.

These errors motivated an explicit work-identity and granularity policy
covering:

1. ordinary editions and translations;
2. compound or collected volumes;
3. abridgments, retellings, and adaptations;
4. edited or adapted editions;
5. part-versus-whole relations;
6. duplicate work-level items;
7. publication year as supporting rather than decisive evidence.

Because these 50 records were used to formulate the revised policy, they became
a diagnostic/development sample and were not reused as the final untouched
evaluation set.

### Frozen v3 final holdout

The revised judge prompt (`prompts/wikidata_judge_v3.txt`) was frozen before
evaluation on a separate untouched set of 50 records corresponding to review
orders 51–100 of the original random sample.

The target input, Stage 2 candidate packets, judge prompt, resolver script,
model judgments, and manual-review sheet were preserved with SHA-256 hashes
before comparison.

Final results:

```text
records reviewed              50

gold decisions:
MATCH                         12
NO_MATCH                      38
AMBIGUOUS                      0

exact three-way agreement     48 / 50 = 0.960

TP = 11
FN = 1
FP = 0
TN = 38

Precision   = 1.000
Recall      = 0.917
F1          = 0.957
Specificity = 1.000

Primary-QID accuracy,
gold-positive cases           11 / 12 = 0.917

Set-aware Top-1 accuracy,
gold-positive cases           11 / 12 = 0.917
```

### Final holdout disagreements

#### Under Milk Wood

Gold:

```text
MATCH Q2497140
```

Prediction:

```text
AMBIGUOUS Q2497140
alternatives: Q20601952, Q20601957
```

The resolver selected the preferred QID correctly but treated two additional
same-title, same-author items as plausible duplicate work-level entities.
Manual inspection showed that those sparse items were associated with specific
BBC/CD manifestations despite their broad `literary work` typing.

This is primarily an **ambiguity-calibration / manifestation-granularity**
error rather than a candidate-retrieval failure.

#### The Flower and Market Girls of Paris

Gold:

```text
MATCH Q338034
```

Prediction:

```text
NO_MATCH
```

The correct underlying work, Émile Zola's *Le Ventre de Paris* (Q338034), was
present in the candidate set. The target title is an English translation title,
but the candidate packet did not contain affirmative metadata explicitly
linking that English title to the French work. The v3 judge therefore rejected
the candidate rather than relying on thematic similarity.

This is an **evidence-enrichment / translated-title normalization** error rather
than a candidate-retrieval failure.

### Interpretation

The final unseen holdout indicates a conservative resolver: no false-positive
matches occurred in the 50-record final holdout, while one valid match was
missed.

The preferred work-level QID was present in the candidate set for all 12
gold-positive cases:

```text
positive candidate recall = 12 / 12 = 1.000
```

The remaining errors therefore occurred after candidate retrieval, at the
level of bibliographic interpretation and evidence enrichment.

The 48/50 result should be reported as a count as well as a percentage. With
only 50 observations, uncertainty around the point estimate remains
substantial. The final holdout also contained no gold `AMBIGUOUS` cases, so it
does not independently estimate ambiguity-detection performance.

The v3 prompt should remain frozen after this evaluation. The two final holdout
errors should be retained as genuine evaluation errors rather than used to
retroactively modify the reported v3 result.

## 31. Dissertation-ready methodological formulation

> Wikidata entity resolution was treated as a bibliographic representation problem rather than a string-matching problem. Candidate entities were generated primarily through author–work relations (`P50`), with title normalization and global title search used as secondary evidence. Edition and translation records were normalized to parent works where `P629` permitted this, while `P31`, publication date, author metadata, descriptions, aliases, and sitelinks were retained for adjudication. Evaluation revealed that errors could arise not only from failed matching but also from ambiguous or inconsistent knowledge-base modeling: a conceptual work may be represented by multiple work-level QIDs, by thousands of edition-level records, or only by a bibliographically related entity. Consequently, the benchmark distinguishes work-level identity from canonical-QID selection and treats duplicate work entities and granularity mismatches as explicit annotation categories.

A formulation emphasizing benchmark construction:

> The benchmark was rebuilt through two independent model judgments followed by targeted, model-blind human adjudication and a stratified audit of consensus cases. This procedure was designed not to define correctness by model majority, but to use model agreement as a triage mechanism for human review. The final benchmark preserves whether each label came from direct human adjudication, human-audited model consensus, or unaudited dual-model consensus, making the provenance of the evaluation target explicit.

A formulation emphasizing reproducibility:

> Candidate generation was treated as part of the evidential record rather than as an invisible preprocessing step. Earlier experiments showed that an unordered `LIMIT 100` over author-linked Wikidata items could make the candidate universe itself non-reproducible. The revised workflow therefore retrieves the full author-linked universe, preserves candidate provenance and exact candidate sets, and separates deterministic structural normalization from semantic judgment.

A formulation emphasizing the epistemological implication:

> The resolution task therefore does not simply ask whether a title can be found in Wikidata. It asks which level of bibliographic abstraction a Wikidata entity represents, whether multiple entities should be regarded as equivalent representations of the same work, and when the absence of a work-level entity should be distinguished from the presence of editions or adaptations. These cases show that knowledge-base linkage is itself an interpretive modeling decision rather than a neutral lookup operation.

## 32. Recommended repository documentation structure

Keep `WORKFLOW.md` relatively short and link to this dedicated methodological note:

```text
WORKFLOW.md
docs/
    WIKIDATA_ENTITY_RESOLUTION.md
prompts/
    wikidata_judge_v1.txt
derived/
    benchmark/
```

Suggested short entry for `WORKFLOW.md`:

```markdown
### Wikidata entity resolution

Wikidata resolution is author-first and work-level. The pipeline retrieves all
`P50`-linked items for a resolved author, compares normalized title evidence,
collapses editions/translations through `P629` where possible, and uses global
title search only as a fallback. Candidate generation and metadata enrichment
are separate stages, and technical retrieval failures are never treated as
`NO_MATCH`.

The benchmark distinguishes abstract works from editions, translations,
adaptations, compound records, and duplicate work-level entities. Benchmark
labels retain their adjudication provenance, including direct human review,
human-audited dual-model consensus, and unaudited dual-model consensus.

See `docs/WIKIDATA_ENTITY_RESOLUTION.md` for benchmark design, failure modes,
evaluation policy, adjudication procedure, and production-scale workflow.
```

## 33. v6 fresh prediction-blind holdout — 2026-09-18

A new 100-record holdout was sampled from the 34,789-work Open Library
population after excluding records used in earlier Wikidata benchmarks.
Human gold was completed and frozen before any v6 predictions were generated.

### Frozen provenance

- human-gold freeze: `5c6316e`
- v6 prediction freeze: `c0fdc47`
- final evaluation freeze: `4a6b1ca`

Authoritative run-specific files are under:

`derived/benchmark/holdout/fresh_random100_v6_20260918/`

The human annotation protocol separates entity identity from population
eligibility. Ordinary translations are treated as the same conceptual work,
whereas explicit adaptations, abridgements, and retellings are not
automatically collapsed to their sources. Eligibility is determined at the
conceptual-work level rather than from the date of a later edition or
translation.

### Gold composition

Of the 100 frozen records:

- 26 were gold MATCH
- 74 were gold NO_MATCH
- 68 were INCLUDE
- 32 were EXCLUDE_OUT_OF_SCOPE

Excluded records were retained in the frozen sample and were not replaced.

### Primary evaluation

On the 68 records independently judged to belong to the intended population:

- strict accuracy: **67/68 = 0.9853**
- TP = 14
- FP = 0
- FN = 1
- TN = 53
- precision = **1.0000**
- recall = **0.9333**
- F1 = **0.9655**
- candidate recall among gold MATCH cases = **14/15 = 0.9333**

The sole primary error was *Prince Schamyl's Wooing*
(OL1492280W; gold Q124092201). The correct QID was absent from the frozen
candidate set.

### Sensitivity analysis on all 100 records

- strict accuracy: **98/100 = 0.9800**
- TP = 24
- FP = 0
- FN = 2
- TN = 74
- precision = **1.0000**
- recall = **0.9231**
- F1 = **0.9600**
- candidate recall among gold MATCH cases = **24/26 = 0.9231**

The two errors were:

1. *Rossingon FR Nightingale* — gold Q1200454
2. *Prince Schamyl's Wooing* — gold Q124092201

Both gold QIDs were absent from the frozen candidate sets. Revision-history
checks confirmed that Q1200454 (created 2012-12-19) and Q124092201
(created 2024-01-02) both predated the frozen 2026-08-05 Wikidata snapshot.
They are therefore genuine candidate-retrieval misses rather than
post-snapshot additions.

### Interpretation

No false-positive MATCH predictions occurred.

Conditional on the correct gold QID being present in the frozen candidate set,
v6 selected the correct QID in every observed gold-positive case:

- primary population: **14/14**
- all 100 records: **24/24**

This conditional result is diagnostic rather than the main reported metric.
The end-to-end evaluation remains 67/68 on the primary population.

The fresh holdout is now frozen and must not be used for further v6 prompt or
resolver tuning. The observed remaining error source is candidate retrieval,
not semantic selection among supplied candidates.
