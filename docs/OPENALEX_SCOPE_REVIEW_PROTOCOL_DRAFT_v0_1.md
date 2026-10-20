# OpenAlex Primary-Analysis Scope Review Protocol — Draft v0.1

Date: 2026-10-20

Status: **DRAFT / NOT AN ADJUDICATED SCOPE RELEASE**

Applies to: scope review for the primary OpenAlex scholarly-visibility analysis only.

## 1. Purpose and analytic unit

The primary analysis tentatively targets **individual novels and novellas originally written in English and first published in 1880–1950 (inclusive)**. This is an analytical restriction, **not** a revision of the historic 34,789 Open Library source records or existing Project W identities. Other publication, circulation, reception, and educational analyses may retain a broader population.

A Project W is the *unit to be reviewed*, not proof that its source records denote precisely one conceptual literary work. If its identity or granularity is ambiguous, record the ambiguity without merging, splitting, or otherwise changing it.

## 2. Separate evidence fields

Record each dimension independently:

| Field | Required observation |
| --- | --- |
| `bibliographic_target` | Which specific work or publication the OL source appears to denote, with its OL ID and independently checkable identifiers |
| `work_form` | Single novel, novella, individual short story, short-story collection, anthology/excerpts, poem, drama, criticism/nonfiction, other, or unresolved |
| `original_language` | Original composition/publication language, distinct from the language of an available edition |
| `first_public_appearance_year` | Earliest verified public appearance, including serial installments, if applicable |
| `first_complete_work_publication_year` | Earliest verified publication of the complete work, if different and ascertainable |
| `first_book_publication_year` | First book publication, when relevant; distinguish a standalone book from inclusion in a collection |
| `first_english_manifestation_year` | Earliest verified English publication or translation, separately from the original publication |
| `period_basis` | Which publication-year convention is being applied; record unresolved boundary cases |
| `period_status`, `language_status`, `genre_status`, `analysis_scope_status` | Independent assessments of the criteria and their combined outcome |
| `evidence_ids`, `independent_sources`, `reviewer`, `review_method`, `review_notes`, `review_status` | Review provenance and uncertainty |

**Never treat the historical OL edition-derived minimum year as an original-work first-publication year.** OL subjects such as `fiction` are discovery signals, not conclusive form evidence.

## 3. Publication-year convention (provisional)

For each work, preserve serial/periodical first appearance, first complete publication, and first book publication separately. The current working inclusion period is 1880–1950 inclusive. When these dates would lead to different eligibility decisions, mark `PERIOD_BASIS_REVIEW_REQUIRED`; do **not** silently use the edition minimum or the book year. The final treatment of serial publication and individual short stories remains open in the 2026-10-20 analysis-scope draft.

## 4. Provisional scope assessments

- `IN_SCOPE_CANDIDATE`: independently corroborated bibliographic target; English original; qualifying original-work publication in the period under the recorded period convention; and one individual novel or novella.
- `OUT_OF_SCOPE_CANDIDATE`: at least one exclusion condition is positively established by independent bibliographic evidence (e.g., original work pre-1880, non-English original, anthology or poem). Record the exclusion reason and retain any other unresolved fields.
- `UNRESOLVED`: target-work identity, date, original language, form, or evidence is insufficient or contradictory, and no exclusion condition is securely established. Do not force a binary decision.

`*_CANDIDATE` labels are **evidence-draft proposals**, not researcher-approved decisions. `review_status` remains `NOT_ADJUDICATED` until a researcher reviews the underlying evidence and explicitly confirms a status. Do not infer `IN_SCOPE` from OpenAlex candidate counts, visibility rankings, query results, or apparent fame.

## 5. Evidence and attribution standards

1. **Identify the object first.** Match the externally located item to the specific OL/Project W source before transferring its form or publication date. Title-and-author resemblance alone is insufficient, particularly for generic titles and apparent date conflicts.
2. Prefer first-edition evidence, contemporary catalogs, stable institutional catalog records, digitized title pages/contents, or specialist bibliographies. Later summaries can support orientation but should not silently displace primary bibliographic evidence.
3. Record a stable URL or identifier, the specific claim it supports, and the date consulted. Distinguish book-level evidence from conceptual-work evidence.
4. Record conflicting dates, languages, genre descriptions, pseudonyms, or editor/author attribution explicitly. Do not resolve a conflict simply by selecting the most plausible source.
5. AI assistance can propose findings and locate evidence. Researcher verification and judgment must be logged separately. Absence of an easily found record is not evidence of exclusion.

## 6. Pilot sequence and sampling design

- Historical frozen scope pilot: `derived/scope/scope_evidence_pilot_v1/` (159 distinct Project W, including an independently selected random sample of 80 W).
- Purposive 13-W evidence draft: `derived/scope/scope_evidence_review_draft_v0_2/`.
- First 10 random-W evidence draft: `derived/scope/random_scope_review_draft_v0_1/`.

**Keep the original 80-W random selection fixed.** First test the review procedure and source requirements on the already identified first 10 of those 80 W. After recording any protocol refinements, apply the stable procedure to the remaining 70, documenting unresolved records rather than substituting easier examples. If a procedure changes materially, note whether earlier cases require the same re-review.

When summarizing scope prevalence, use **the independent 80-W sample only**, with its unresolved share and substantial sampling uncertainty. Do not pool purposive cases into a population prevalence estimate. Work-level proportions do not estimate the precision of the 226,221 OpenAlex operational candidate pairs.

## 7. OpenAlex retrieval is separate from bibliographic scope

The existing integrated OpenAlex visibility v2 remains frozen. Its 226,221 operational pairs are candidates, not individually verified scholarly references. Retain distinctions between works with operational candidates, queried zeros, 352 W with no operational R2/R3 query (although R4 title-only queries exist), and the single unremeasured Alcott W (`NA`). Candidate attribution and cross-W overlap require separate evaluation from scope.

## 8. Outputs, review gate, and preservation

Keep the 159-W original `NOT_REVIEWED` template unmodified. Store new evidence drafts and eventual researcher-confirmed decisions in separate, versioned artifacts, with provenance and stable Project W IDs. Do not modify Project W identity, existing OpenAlex v2, frozen held-out evaluations, or completed Open Library Edition audits.

Before any all-W analytical-scope release, define the final rule for serialized works and short stories, review the random sample, document the error/uncertainty profile of automated screening, and record researcher sign-off. This draft alone authorizes **no bulk exclusions or recalculation**.
