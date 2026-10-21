# OpenAlex R2+A1 target-attribution checkpoint — 2026-10-21

Status: development and preliminary independent human evaluation complete; production first 1,000 **planned**, not yet reported as executed in this checkpoint.

## Research and data contract

- Population for this route: 224,830 operational `R2_A1_BASELINE / INCLUDE_BASELINE_UNADJUDICATED` Project W × OpenAlex Work pairs within frozen integration v2. These pairs are candidates, not adjudicated citations.
- Remove 855 previously evaluated candidate IDs and 100 earlier pilot IDs: 223,875 independent-sampling frame.
- Development: 160 pairs (120 random and 40 title-risk). Blind holdout: 600 sampled pairs, separate from development.
- New production queue: 223,875 - 160 - 600 = **223,115** pairs. This is NOT the full integrated-v2 route union and should not be labelled all OpenAlex mentions.
- Identity input: active Project Works v7 (32,066 W) and frozen source-native OL/Wikidata bibliographic evidence; scope (1880–1950 originally English novels/novellas), attribution, and scholarly/document visibility are distinct stages.
- Attribution policy: model `gpt-6-luna`, frozen identity-aware development prompt and structured output schema, bibliographic context, one candidate pair per request. `VALID_TARGET_REFERENCE`, `INVALID_TARGET_REFERENCE`, or `UNCERTAIN` are **provisional model judgments**, not human truth.

## Completed checks

1. Development 160 model assessments: VALID 95; INVALID 49; UNCERTAIN 16. Deliberately risk-enriched; these are model counts, not performance estimates.
2. Purposively selected development 40 human assessments: 36/40 exact agreement. Four differences concern UNCERTAIN; diagnostic only, no population accuracy inference.
3. Independently selected 600-pair holdout: all 600 Luna predictions completed and saved, with zero failed attempts. Model key for unreviewed cases remains **sealed**; do not print, inspect, Git-stage, or export remaining 400 labels during ongoing human review.
4. Random first 200 of holdout were independently reviewed by researcher. Human: VALID 156, INVALID 25, UNCERTAIN 19. Luna for these 200: VALID 156, INVALID 32, UNCERTAIN 12. Exact 3-class agreement 181/200. Human determinate-label confusion: true-valid predicted-valid 154; human-invalid predicted-valid 2; human-valid predicted-invalid 2; human-invalid predicted-invalid 19; human-invalid predicted-uncertain 4. Eleven human-UNCERTAIN predicted INVALID; eight human-UNCERTAIN predicted UNCERTAIN.
5. Among the 156 Luna-VALID results in this independently reviewed 200: 154 were researcher VALID and 2 researcher INVALID. Determinate-gold precision 154/156 = 98.72% (approximate Wilson 95% CI 95.45%–99.65%). Candidate-pair VALID recall among the 156 researcher-VALID cases is also 154/156. Neither quantity is corpus-wide **retrieval recall**. Human UNCERTAIN rows have no determinate binary gold.
6. Four decisive disagreements underwent a **post-unblinding diagnostic**; their notes are separate, not a retroactive rewrite of the frozen original 200 gold labels or primary statistics. They highlight adaptations, edition-versus-component identity, and document-quality distinctions.

## Scientific interpretation and remaining caveats

- The first 200 form a probability subsample of the frozen holdout; the 40 development cases do not.
- The 600 predictions are a sealed model output; the remaining 400 have not been researcher-adjudicated and can support further audit without altering the initial 200.
- The validation describes **target-work attribution conditional on R2+A1 retrieval**, not scientific relevance of the OpenAlex record, textual mention strength, completeness of initial retrieval, or representativeness of other routes (A2/R3/R4).
- Some works are ambiguous collections, author-name titles, or editions. A work-identity problem should not be silently converted to INVALID or folded into corpus scope.
- No modifications to the frozen source integration, Project Works v7, model prompt, historical human decisions, or independent sampling designs are authorized by this checkpoint.

## Production execution and traceability

Runner: `scripts/run_openalex_r2a1_production_first_1000_v0_1.py`.

1. Archive this note plus the reproducible scripts in version control **before** launching paid production. Use a deliberate branch/worktree, check `git status`, and stage named paths only. Do not stage `derived/openalex_production/` en masse, `token.sh`, API credentials, sealed prediction JSONL, or raw snapshot data.
2. In `tmux`, run `--prepare` first (no API); it constructs the deterministic new 223,115-pair queue and first 1,000 input rows, recording queue, input, source, prompt, and schema SHA-256 hashes in `run_config_v0_1.json`.
3. Verify the prepared batch before paid execution. Execute `--execute --max-new 1000` in the `tmux` session, with logging. The runner uses a lock and checkpoints each successful response, printing progress every 25 successes and stopping on the first error. Re-running the same command resumes; it never intentionally re-bills already saved IDs.
4. Keep large queues, raw model records, run logs, and sealed independent-holdout predictions on the server with backed-up storage; add small summaries, hashes, documentation, code, and release manifests to Git using an explicit allowlist. The checkpoint is not a final production release until run outputs and audit are generated and recorded.

## Relevant server directories

- `derived/openalex_production/retrieval_r2a1_independent_validation_v0_1/`
- `derived/openalex_production/retrieval_r2a1_development_160_review_v0_1/`
- `derived/openalex_production/retrieval_r2a1_holdout_600_identity_aware_v0_1/` (sealed predictions)
- `derived/openalex_production/retrieval_r2a1_holdout_first_200_blind_review_v0_1/`
- `derived/openalex_production/retrieval_r2a1_production_identity_aware_v0_1/` (planned production artifact directory)

This report contains no unrevealed holdout judgments and no API secrets.
