# British Library SRU Verification Pilot v1 — Protocol

Status: **DRAFT** — becomes frozen only when committed. No BL request may be sent under this protocol before the freeze commit exists on `origin/kakenc-integration-20260927`.

Project: `canon-pipeline`
Related planning note: `BRITISH_LIBRARY_SRU_RETRIEVAL_PLAN.md` (2026-09-30)
Input identity release: `project_works_v4` / `work_identity_map_v4`
Alias source used for target lookup: `derived/openalex_production/registry_v3/openalex_aliases_v3.tsv`
Author source used for queries: `derived/openlibrary_query_author_selection_v1/openlibrary_query_author_selection_v1.tsv`

The OpenAlex alias registry and query-author selection are used here **only as lookups** (which titles and names belong to which target). This pilot does not adopt any OpenAlex retrieval policy for BL.

---

## 1. Purpose

The Heart of Darkness pilot showed that BL SRU can support descriptive reconstruction of a famous work's later manifestations. It did not show whether BL evidence is interpretable across the population. This pilot tests that, at small scale, before any decision about large-scale retrieval.

This is a verification pilot, not a calibration release and not production. Its outputs must not be used as BL visibility values.

## 2. Questions (fixed before any request)

- **Q1 Old records.** When BL holds manifestations published before c. 1975, are they retrieved by the title routes, and are their 245/100 structures usable for local matching in the same way as modern records?
- **Q2 First-edition coverage.** For works whose first UK edition is independently documented (§5), is a BL record for that edition found by any route?
- **Q3 Zero-result reliability.** When title routes return zero accepted records, do author-only or keyword routes reveal records that the title routes missed?
- **Q4 Hard cases.** How do short titles (Kim, She), pseudonyms (Orwell, Croskey), editor-as-creator (Lang), translation (Tagore), multi-alias title variation (Munchausen), and novella combined volumes behave? Heart of Darkness is frequently published together with other works (e.g. with *The Secret Sharer*, or within *Youth*). The earlier pilot's `245$a` equality rule would accept a record whose `245$a` is the target title and whose `245$b` names further works, so combined volumes may have been undercounted there.
- **Q5 Cross-W duplication.** Do the four Heart of Darkness W receive identical or overlapping BL candidate sets? (Strong fragmentation candidate: same title, same OL author `OL19441A`.) Because an OL Work titled "Heart of Darkness" may in practice represent a combined volume, overlapping BL candidates alone do not establish that the four W are one work; the review records, for each W, whether its OL editions look standalone or combined.
- **Q6 Field presence.** How often do 015, 240, 246, 260 vs 264, 600$t, 700$t, 041 and 776 occur, stratified by 008 date?

## 3. Sample

Frozen in `bl_verification_pilot_v1_sample.tsv` (21 targets: 19 resolved W, 2 unresolved units).

Selection:

- 16 purposive targets chosen for the strata below (15 W + 1 unresolved unit);
- 4 W drawn uniformly at random from `project_works_v4` excluding the purposive W, sorted by `project_work_id`, `pandas.DataFrame.sample(n=4, random_state=20260930)`, pandas 3.0.3; pool size 32,071;
- 1 unresolved unit drawn uniformly at random from unresolved anchors excluding `E000016319`, sorted, `pandas.Series.sample(n=1, random_state=20260930)`; pool size 760.

The random draw is used as drawn. It is not redrawn because of scope, translation, or editor status; those properties are part of what is being tested.

Strata:

| stratum | targets |
|---|---|
| uk_first_edition | W000030670, W000032021, W000018010 |
| short_title | W000031897, W000007201 |
| pseudonym_us_first | W000001624 |
| us_author | W000031971, W000000003 |
| prolific_popular | W000004670 |
| fragmentation_candidate | W000014272, W000014830, W000017583, W000030652 |
| collection_as_w | W000014701, W000031089 |
| unresolved_purposive | E000016319 |
| random_w | W000000582, W000006387, W000030186, W000001300 |
| random_unresolved | E000000192 |

Alias expansion is derived at run time from `openalex_aliases_v3.tsv` by `project_work_id` (resolved) or `unresolved_unit_anchor_entity_id` (unresolved), and the expanded alias list is written to the run output. Hand transcriptions of OL IDs in conversation notes are not authoritative.

## 4. Query routes (fixed)

For each target, take the distinct normalized alias titles (`alias_value_norm`, deduplicated) and the selected query author (`query_author_name`). Queries use the raw title form of the first alias carrying each normalized value.

| route | CQL | unit |
|---|---|---|
| T1 title_exact_author | `alma.title == "<title>" and alma.creator all "<author>"` | per title |
| T2 title_exact | `alma.title == "<title>"` | per title |
| T3 title_phrase | `alma.title = "<title>"` | per title |
| A1 author_only | `alma.creator all "<author>"` | per distinct author |
| K1 keyword | `alma.all_for_ui all "<title> <author surname>"` | per title |

Escaping: double quotes and backslashes inside values are backslash-escaped; no other alteration. Author strings are used as given in `query_author_name` (including initials such as `H. Rider Haggard`, `E. M. Forster`); failures caused by this are findings, not bugs to fix mid-run.

Pagination and caps (fixed before the run):

- `maximumRecords=20`, `startRecord` advanced until all reported records are retrieved;
- cap: 200 records (10 pages) per query; beyond the cap, record `numberOfRecords` and mark `SKIPPED_POLICY_CAP`;
- A1 is always probed first for its count; full retrieval only if count ≤ 200.

No route is added, removed, or modified after the first request. If a route turns out to be broken, the run is completed as specified and the problem is reported.

## 5. Independent ground truth (Q2)

Recorded **before** the run. Every row needs a cited source before the freeze commit; rows without a source are dropped from Q2 rather than kept on memory.

| target | expected first UK book edition | source (as cited) | conf. |
|---|---|---|---|
| W000030670 Dorian Gray | 1891, Ward, Lock & Co., London (book form; serial in *Lippincott's*, July 1890) | Mason 328, cited by Bauman Rare Books and Sotheby's lot descriptions | high |
| W000032021 Tess | 1891, James R. Osgood, McIlvaine & Co., London, 3 vols | Purdy pp. 67–68, cited by several dealers; Eton College Library catalogue (1st ed., 3 v.) | high |
| W000018010 Mrs Dalloway | 1925, Hogarth Press, London (published 14 May 1925) | Kirkpatrick A9a, cited by Heritage Auctions, Jonkers, Christie's | high |
| W000031897 Kim | 1901, Macmillan & Co., London (17 Oct 1901; US Doubleday 1 Oct 1901 earlier) | Livingston 250 / Richards A174, cited by dealers; Morgan Library catalogue ("First English published ed."); Kipling Society readers' guide | high |
| W000007201 She | 1887, Longmans, Green & Co., London (1 Jan 1887; US Harper 24 Dec 1886 earlier) | Whatmore F4, cited by Sotheby's; Victorian Web | high |
| W000001624 Burmese Days | 1935, Victor Gollancz, London (24 Jun 1935; US Harper 25 Oct 1934 earlier) | Fenwick A.2c, cited by Lucius Books; Penguin/Complete Works blurb (Davison) | high |
| W000031971 House of Mirth | 1905, Macmillan & Co., London | Morgan Library catalogue, PML 176919 (London: Macmillan, 1905); Garrison A12 for US issue | medium-high |
| W000000003 Sister Carrie | 1901, William Heinemann, London, *Dollar Library of American Fiction* (abridged by Arthur Henry) | University of Pennsylvania Libraries, Dreiser exhibition text | high |
| W000004670 Four Just Men | 1905, Tallis Press, London (revised ed. Tallis 1906) | SF Encyclopedia (Wallace entry); ABAA dealer listing | high |
| E000016319 Howards End | 1910, Edward Arnold, London | Kirkpatrick A4, cited by Jonkers | high |
| Heart of Darkness (4 W) | 1902, William Blackwood & Sons, Edinburgh and London, in *Youth: A Narrative, and Two Other Stories* (13 Nov 1902; serial in *Blackwood's Magazine* 1899) | Cagle A7a.1 / Wise 10, cited by Bauman; Heritage Auctions (quoting Smith) | high |
| W000000582 Orange Fairy Book | 1906, Longmans, Green & Co., London (Aug 1906) | Printed edition statement "First Edition August 1906" (Project Gutenberg transcription); Jonkers | medium-high |

**Provenance of this table.** Compiled by LLM-assisted web lookup (Claude, 2026-09-30). Bibliography numbers are recorded *as cited* in dealer, auction and library descriptions; the bibliographies themselves were not consulted. No source is the BL catalogue, Open Library, Goodreads or Wikidata. Before the freeze commit, a human spot-checks at least three rows; any row found wrong is corrected or dropped, and the check is noted here.

Spot-checked by Haruka TSUTSUI, 2026-09-30: House of Mirth, Sister Carrie, Orange Fairy Book — consistent.

Notes relevant to review: Sister Carrie's first UK edition is itself abridged (expected class `target_abridged_or_retold`); Tess's first edition is `multi_volume`; for She, Kim and Burmese Days the US edition preceded the UK edition, so a US record in BL is not the Q2 target.

Random targets other than Lang have no ground truth; they serve Q3 only.

## 6. Execution rules

- concurrency 1; ≥ 3 s between request starts (more conservative than the 2 s proposed for production);
- transient HTTP/network errors: wait 30 s, at most 3 retries, then `FAILED_FINAL`; parse errors are never retried;
- explicit User-Agent identifying the project and a contact address;
- every response saved as raw XML, one file per physical request, with SHA256, request URL, timestamp (UTC), HTTP status, `numberOfRecords`, elapsed ms;
- physically identical requests (same normalized CQL, same `startRecord`) are executed once and referenced by all logical queries that need them;
- resumable: completed physical requests are never re-sent.

Estimated volume: ≤ 400 requests (≈ 20–30 min). This is comparable to the earlier Heart of Darkness pilot and within the searching use BL described. It does not substitute for BL confirmation of a production access pattern.

## 7. Review vocabulary

Each distinct BL record retrieved for a target is coded on two independent axes. The vocabulary is fixed before the run; anything that does not fit is coded `other` with a free-text note rather than forced into a near class. The frequency of `other` cases and flags is itself a pilot finding and feeds the vocabulary of any later calibration release.

### 7.1 Relation to the target work (exactly one)

```
target_alone                  full text of the target, alone
target_with_other_works       target is the lead / co-title work
                              (e.g. 245$a = target, 245$b = further works)
target_in_collection          target is one item in a volume titled otherwise
                              (collected works, omnibus, anthology; via 505 / 700$t)
target_excerpt                only part of the target (selection, extract)
target_abridged_or_retold     abridged, simplified, graded reader, retold
other_language_version        target in a language other than the target
                              work's own language (for an English-language
                              target: a translation from English; for an
                              English translation target such as Tagore:
                              the original or another-language version)
adaptation                    other medium or genre (play, film script, opera,
                              graphic novel, etc.)
related_study_guide           study guide / notes / teaching aid
related_criticism             criticism or scholarship about the target
related_derivative            sequel, prequel, parody, pastiche by others
unrelated                     title or name collision
ambiguous                     cannot be decided from the record
other                         none of the above (note required)
```

### 7.2 Manifestation flags (zero or more)

```
annotated_or_critical_edition   notes / critical apparatus / criticism bound in
illustrated
childrens_edition
large_print
braille
audio                           336/337/338 spoken word / audio carrier
facsimile_reprint               facsimile of an earlier edition
digitized_reproduction          online resource reproducing an older edition
electronic_original             born-digital / ebook edition
multi_volume                    record covers, or is part of, a multi-volume set
non_uk_place                    place of publication outside UK/Ireland
                                (e.g. Tauchnitz, US editions)
bilingual
possible_duplicate_record       appears to describe the same edition as
                                another retrieved record
other_flag                      note required
```

### 7.3 Also recorded per record

Full 245 ($a, $b, $c); whether 505 or 700$t lists other works; 008 date and language; 041; 260/264 place, publisher and date as separate subfields; 250; 015 if present; whether it is the §5 first edition; which routes retrieved it; reviewer note.

Ground-truth "first edition" in §5 means **first UK book edition**. Serial first publication (e.g. Heart of Darkness in *Blackwood's Magazine*, 1899; Dorian Gray in *Lippincott's*, 1890) is noted but not expected in BL book records.

## 8. Decision guide (fixed before the run)

These are the interpretations the results will be read against. They guide the next design decision; they are not a release gate.

- **G1 (Q1/Q2) coverage supports interpretation**: ≥ 9 of the ≤ 12 ground-truth first editions found by some route, and pre-1975 records usable with 245/100 matching → proceed to design a calibration sample for large-scale retrieval.
- **G2 routing problem**: first editions exist in BL but are found mainly by A1/K1 and not T1–T3 → redesign candidate routes (e.g., author sweep) before any calibration release.
- **G3 structural problem in old records**: old records found but fail 245/100 matching → design era-specific matching; add record era as a calibration stratum.
- **G4 coverage too weak**: ≤ 6 found → BL absence is not treated as interpretable; BL restricted to descriptive or sampled use in the dissertation.
- **G5 inconclusive**: 7–8 found → no coverage conclusion is drawn from the count alone; each miss is examined and the result is read through G2/G3 (routing vs. old-record structure). If misses have no common cause, extend the check with a fresh, independently drawn set of ground-truth works before any calibration release.
- **Q5**: if the four HoD W receive overlapping accepted records, record the four W as an identity-review item for a future forward-versioned identity release. Do not modify `project_works_v4`.
- **Q3**: every random target with zero T1–T3 acceptances is reported with its A1/K1 outcome, classified as `absent_all_routes` or `title_route_miss`.

## 9. Outputs

```
derived/bl_calibration/verification_pilot_v1/
    bl_verification_pilot_v1_sample.tsv        (frozen input, committed)
    expanded_aliases.tsv
    logical_queries.tsv
    physical_requests.tsv
    records_parsed.tsv
    review.tsv
    field_presence.tsv
    summary.md
    manifest.json                               (hashes of all above + raw files)
```

Raw XML is kept outside Git at first, at a path recorded in the manifest with per-file SHA256. Whether raw is committed is decided after the size is known.

## 10. Non-goals

- No BL visibility metric is produced.
- No change to `project_works_v4`, identity maps, or any frozen release.
- No tuning of routes, normalization, or thresholds on this sample for later reuse as if it were held out: if a calibration release follows, its sample is drawn fresh.
