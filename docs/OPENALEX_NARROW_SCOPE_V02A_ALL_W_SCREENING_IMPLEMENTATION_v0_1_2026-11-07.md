# OpenAlex narrow scope v0.2a: source-evidence screening implementation v0.1

Date: 2026-11-07  
Status: `CODE_AND_TESTS_IMPLEMENTED / FULL_CORPUS_EXECUTION_PENDING / NO_SCOPE_MEMBERSHIP_RELEASE`  
Base rulebook: `docs/OPENALEX_NARROW_SCOPE_RESEARCHER_ACCEPTED_POLICY_v0_2a_2026-11-07.md`.  
Repository branch: `review/narrow-v02a-source-screening-20261107`.

## 1. Design: source signals are not original-work facts

The active frame is 32,066 Project W. The frozen broad Open Library historical sources and frozen OpenAlex v3 results are untouched. `ELIGIBLE_CANDIDATE` is not `IN_SCOPE`; `POSSIBLE_EXCLUSION_FOR_REVIEW` is not `OUT_OF_SCOPE`; and `FORM_OR_IDENTITY_UNRESOLVED` is not equivalent to a researched final `UNRESOLVED` decision.

Stage 1 of the implementation consumes an already frozen Project-W-level Open Library/Wikidata evidence join. It reads only the following source-native assertions:

- source-linked current OL Work IDs and historical title/author strings;
- historical OL *edition-derived minimum* years (not original first-publication years);
- Wikidata P577 years and P407 language statements (not original publication or original-language adjudications);
- historic OL subject strings and adopted Wikidata QID;
- existing 80-row researcher-accepted provisional ledger, retained as an **overlay**, not labels for training or generalization.

No external APIs are requested. No newly retrieved primary evidence, Edition-level identity links, first-appearance events or narrative-content reading is claimed in this stage. Those require the next evidence-enrichment and human verification step.

## 2. Routing and explicit invariants

The system creates exactly one non-adjudicative `triage_route_not_scope` per active Project W:

| Review route | Meaning, not a scope label |
|---|---|
| `FORM_OR_IDENTITY_UNRESOLVED` | Multiple/no OL Work IDs, mixed source dates, no dated source signal, or a WD language statement without an English value; require source-level inspection. |
| `POSSIBLE_EXCLUSION_FOR_REVIEW` | Nonfiction/reference subject cue or only out-of-period **source** dates; no automatic exclusions. |
| `ELIGIBLE_CANDIDATE` | OL fiction genre cue or collection-title cue without higher-priority ambiguity; original English, form, first year and target identity are **not** verified. |
| `INSUFFICIENT_EVIDENCE` | No decisive genre/form cue and no higher-priority exception. |

All routes may contain false positives and false negatives. If a source states `fiction`, it does not prove eligibility. The routing order is deterministic; its categories are a worklist, not a trained or validated model. Avoid using OpenAlex scholarly-reference counts, Goodreads observations or source presence as evidence for eligibility. The existing `scripts/build_openalex_all_w_scope_screening_signals_v0_1.py` is a separate prioritization diagnostic, not a final membership classifier.

Guaranteed invariants (programmatically checked):

1. The frozen combined evidence is checked against SHA256 `e6d01748327ef0eed243e0dc35f862cd9480714f10efaba7380ee3d5d38e523c`.
2. Exactly 32,066 unique Project W and 80 unique fixed sample W, ranks 1–80; the 80 are a subset of the 32,066, never extra observations.
3. The previously accepted provisional 80 distribution is exactly 41 `IN_SCOPE`, 19 `OUT_OF_SCOPE`, 20 `UNRESOLVED`—but these are historical review metadata in separate fields.
4. All output rows have `auto_analysis_scope_decision=NONE_NOT_ADJUDICATED` and `release_status=NOT_RELEASED`.
5. All W, including four source-light works, remain present; bad original-date metadata is not overwritten.
6. No existing output directory may be overwritten, and `--check-only` writes nothing.
7. A manifest records full input hashes, script hash and output hashes. No numbers from test fixtures are described as observed corpus results.

## 3. Running on the actual repository checkout

From the server checkout containing the committed source evidence:

```bash
cd /home/tsutsui/canon-pipeline-openalex-a2val

git fetch origin review/narrow-v02a-source-screening-20261107
# Use a separate worktree if current checkout has uncommitted work.
git worktree add /tmp/canon-scope-v02a review/narrow-v02a-source-screening-20261107
cd /tmp/canon-scope-v02a

python -B -m unittest discover -s tests -p 'test_openalex_narrow_scope_v02a_screening_v0_1.py' -v
python -B scripts/build_openalex_narrow_scope_v02a_screening_v0_1.py --check-only
python -B scripts/build_openalex_narrow_scope_v02a_screening_v0_1.py
```

`git worktree add` may require the local branch ref to be created; if absent, use `git worktree add -b review/narrow-v02a-source-screening-20261107 /tmp/canon-scope-v02a origin/review/narrow-v02a-source-screening-20261107`. A fixed path under `/tmp` is only an example: choose an unused path and do not overwrite existing directories. After execution, preserve the console QC output and manifest.

Output directory (created only if it does not already exist):

`derived/scope/narrow_v02a_all_w_source_screening_v0_1/`

- `all_project_w_scope_source_screening_v0_1.tsv`: 32,066 source-evidence rows and their non-adjudicative routing labels, with provisional 80 overlay fields.
- `bibliographic_exception_queue_v0_1.tsv`: all works in high-priority ambiguity/possible-exclusion strata, ordered for follow-up; not a random sample.
- `fixed_random80_provisional_overlay_v0_1.tsv`: exactly the fixed 80, in original sampling order, with provisional researcher assessment separated from routing signal.
- `separate_stratified_diagnostic_review_v0_1.tsv`: up to 50 deterministic, nonrandom diagnostic cases from each review route, **excluding the original 80**; never pool these with random80 for prevalence inference.
- `summary_v0_1.json`: descriptive counts and non-release warnings.
- `manifest_v0_1.json`: input/script/output hashes and provenance.

Before executing, ensure the source checkout contains the actual frozen TSVs. The first command runs structural validation; a successful test on synthetic 32,066 rows is **not** proof of successful execution on the actual corpus.

## 4. Stage 2 — what has NOT been implemented or released

A source-claim registry is still required before any main-analysis membership release. For every IN/OUT case, capture:

- Project W → exact OL Work → relevant original Edition/manifestation, with cited source record and evaluated author/editor/translator roles;
- confirmed prose-fiction form and unit of analysis (`INDIVIDUAL_NOVEL`, `INDIVIDUAL_NOVELLA`, `ORIGINAL_SINGLE_AUTHOR_SHORT_FICTION_COLLECTION`, mixed or other);
- first original-language public appearance, first complete publication, first book edition and original collection issue as applicable, with dates supported by source URLs and source claims;
- original language (not only language of English manifestation) and variants/retitlings;
- individually checked, reviewer-confirmed verdict; separately signed novel/novella-only comparator verdict and explicit unresolved reasons;
- versioned evidence sources, revision history and release validation.

The random80 **requires independent claim-by-claim verification** before any eligibility proportion/confidence interval or per-stratum error-rate is reported. The 15-case pilot is not independent of that random80. Any diagnostic stratum review is intentionally separate and must not be added to the random80 denominator. A full validated member list, release gate, OpenAlex/Goodreads join, manuscript-level scholarly-reference attribution, and source-level new acquisition are outside the implementation delivered here.

## 5. Verification done in the assistant execution environment

- All 11 source-routing and safety unit tests passed.
- A separate **synthetic** 32,066-row fixture and a **synthetic** 80-row 41/19/20 ledger completed check-only and a complete file-output run without dropping works. It is **not** actual corpus evidence.
- The repository's actual 12.9 MB combined source TSV was not available in this execution container; a real-corpus run on the user's clone/server and inspection of the resulting manifest are still required.