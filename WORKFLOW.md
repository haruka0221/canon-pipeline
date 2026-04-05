# WORKFLOW.md — canon-pipeline
**DCC Digital Curation Workflow Narrative**
Last updated: 2026-04-05
Status: LIVING DOCUMENT — update on every major change

---

## Overview

This pipeline constructs and validates a population of English-language fiction works (1880–1950) for a doctoral dissertation on the formation and transformation of modernist literary studies as a scholarly field. The pipeline is structured in seven stages: Collection → Filtering → Validation → Enrichment → Citations → Analysis → Discourse Analysis.

**Core research question:** How was modernist literary studies made as a scholarly field? The pipeline provides empirical evidence for narratives that critics have previously constructed through impression and authority — mapping the formation of the modernist canon through multiple vectors of scholarly activity.

**Repository:** https://github.com/haruka0221/canon-pipeline
**Working environment:** WSL (Ubuntu 24) on Windows, ~/canon-pipeline
**Primary tools:** Python 3.12, pandas, rapidfuzz, pyahocorasick, pdfplumber
**External data (local only):** OpenAlex works snapshot (620GB, /mnt/d/openalex/works/), JSTOR metadata (6.5GB), Critical Inquiry PDFs (254 files)

---

## Stage 1: Population Collection (Dump-Based — Main Study)

### Purpose
Construct the definitive population from the Open Library Works dump,
replacing the Search API approach used in the pilot study.
Motivation: OL Search API returns results ranked by internal relevance score,
which correlates with prior attention — a circular method for studying
attention inequality. The dump provides a complete, unbiased snapshot.

### Inputs
- OL Works dump: `https://openlibrary.org/developers/dumps`
- File: `raw/ol_dump/ol_dump_works_2026-02-28.txt.gz` (.gitignore対象)
- File: `raw/ol_dump/ol_dump_editions_2026-02-28.txt.gz` (.gitignore対象)
- File: `raw/ol_dump/ol_dump_authors_2026-02-28.txt.gz` (.gitignore対象・2026-03-11追加)
- Snapshot date: 2026-02-28 (recorded in `derived/prov.json`)

### Filter Criteria
1. `first_publish_year`: 1880–1950
2. `language`: eng — determined from Edition-level `languages` field (Work-level language field is absent in dump; confirmed 2026-03-11)
3. `subject_keys`: fiction inclusion/exclusion rules (see Pilot Study Stage 2 below)

### Processing Method
3-pass stream processing (Works + Editions dumps combined):
- Pass 1: Extract work_key, title, author_keys, subjects from Works dump
- Pass 2: Extract first_publish_year, language from Editions dump
- Pass 3: Join and filter
Do NOT load entire dump into memory.

### Important OL Dump Structure Notes (confirmed 2026-03-11)
- `first_publish_year` does NOT exist in Work records — it is a Search API derived field only
- `subject_keys` does NOT exist in Work records — only raw `subjects` strings
- `language` is absent at Work level — must use Edition-level `languages`
- `author_keys` contains OL key format (`/authors/OL123A`), NOT author name strings
  → Author names require separate lookup against Authors dump (see Stage 4d)

### Outputs
| File | Description |
|------|-------------|
| `derived/ol_dump_population_fiction_2026-02-28.tsv` | Official main-study population (34,789 works) — local only |
| `derived/ol_dump_population_with_canonical.tsv` | + canonical flag from phd_corpus matching — local only |
| `derived/ol_dump_population_with_author.tsv` | + author_name column from Authors dump — local only |
| `derived/prov.json` | population-dump-v1 release record (frozen) |

### Commands
```bash
python3 scripts/build_population_from_dump.py
python3 scripts/build_author_lookup.py
# → output: derived/ol_author_lookup.tsv (607MB — local only, .gitignore対象)
# → output: derived/ol_dump_population_with_author.tsv (34,789 rows)
```

### Decision Points
- **Why dump instead of API:** 72 canonical phd_corpus works were absent from the top-5,000 API results (e.g. Huckleberry Finn, Dracula, Tess of the D'Urbervilles). Direct evidence of search bias documented in pilot study.
- **No manual additions to dump population:** phd_corpus works not found in the dump are recorded as limitations; no supplementation of the dump-based population itself.
- **Authors dump required:** author_keys in population file are OL URIs, not names. Matching against JSTOR/OpenAlex requires last name strings → Authors dump lookup mandatory.

### Rights / Access
- OL dump data: CC0 (public domain dedication)
- No authentication required; direct download
- `ol_author_lookup.tsv` (607MB) excluded from GitHub due to size; local only

### Evidence / Logs
- `logs/build_population_from_dump_{date}.log`
- `derived/prov.json` (population-dump-v1 provenance record)

---

## Pilot Study: Population Collection (API-Based — Superseded)

### Purpose
Retrieve a large-scale list of fiction works from Open Library (OL) matching the study's temporal and linguistic scope.

### Inputs
- Open Library Search API (`https://openlibrary.org/search.json`)
- Query parameters: `subject=fiction`, `first_publish_year=[1880 TO 1950]`, `language=eng`

### Outputs
| File | Description |
|------|-------------|
| `derived/ol_works_population_unique_clean.tsv` | Initial retrieval: 5,000 works (deduplicated) |
| `derived/ol_works_expanded_raw.tsv` | Additional works from offset 5000–14999 |
| `derived/ol_works_expanded_population.tsv` | Merged expanded population (~15,000 works) |

### Decision Points
- **Initial limit=5,000:** Post-hoc analysis showed 72 phd_corpus canonical works were excluded → expanded to ~15,000.
- **"English" definition:** Works published in English are included regardless of original language.
- **OL search sort order:** Results biased toward frequently-edited/well-documented works — superseded by dump-based approach.

### Evidence / Logs
- `logs/expand_population.log`
- `raw/ol_expand/offset_*.json` (API response cache)

---

## Pilot Study: Population Filtering (API-Based — Superseded)

### Purpose
Remove non-fiction, poetry, drama, and picture books using subject_key-based rules.

### Outputs
| File | Description |
|------|-------------|
| `derived/ol_works_final_population.tsv` | Filtered population: 34,789 works |
| `derived/ol_works_filtered_removed.tsv` | Excluded 167 works |
| `derived/ol_works_augmented_population.tsv` | + 51 phd_corpus supplements = 4,884 works |

### Exclusion Rules (confirmed, do not change without new audit)
Works are excluded if their `subject_keys` contain **any** of:
```
plays, dramatic_works, scripts, poetry, poems, ballads, stories_in_rhyme,
nonsense_verses, verse, picture_books, literary_criticism, nonfiction,
biography__autobiography
```
AND do **not** contain **any** of:
```
novel, novels, short_stories, literary_fiction, fiction_general,
english_fiction, american_fiction
```

**Keywords explicitly NOT used for exclusion:**
- `drama` — appears on novels set in theatrical contexts (caused false exclusions of Jane Eyre, Martian Chronicles)
- `history_and_criticism` — appears on fiction works
- `fiction` — appears on virtually all works, not discriminative

### Decision Points
- Pre-filter audit (n=200, seed=20260222): 11% NG rate
- Post-filter audit (n=200): 3.5% NG rate; primary residual issue is `first_publish_year` mis-registration

### Evidence / Logs
- `derived/ol_works_audit200_seed20260222.tsv`
- `derived/ol_works_audit200_for_review.tsv`
- `derived/ol_works_postfilter_audit100.tsv`

---

## Stage 3: Validation

### 3a. Year Mismatch Audit

**Purpose:** Verify that `first_publish_year` (work-level) is consistent with edition-level `publish_date`.

**Result:** matched 98/100, near_match 2/100, mismatch 0/100. Apparent mismatches were caused by OL returning recent editions first (offset0 bias), not by data errors.

**Conclusion:** `first_publish_year` is reliable as population filter criterion.

---

### 3b. Identifier Coverage Audit

**Results (work-level, at least one identifier present):**

| Identifier | Coverage |
|---|---|
| ISBN (any) | 96.0% |
| OCLC (any) | 92.0% |
| LCCN | 82.0% |
| Internet Archive (ocaid) | 89.0% |

**Full population OCLC coverage (all 34,789 works):** 86.5% (30,101 works)

---

### 3c. phd_corpus Coverage Audit & Canonical Matching

#### Nature of the phd_corpus

`data/phd_corpus_1880_1950_cleaned.csv` is **not a self-curated list**.
Derived from McGrath et al. (2018), aggregating PhD reading lists at major US English departments.

- **Total works in phd_corpus:** 142件
- **Citation:** McGrath, L., Higgins, D., & Hintze, A. (2018). *Journal of Cultural Analytics*, 3(1). https://doi.org/10.22148/16.027

#### Matching history

**v2 (2026-03-11):** Fuzzy matching (token_sort_ratio ≥ 80) against OL dump population. Script: `scripts/match_phd_corpus_v2.py`

**v3 (2026-04-05):** Individual OL API verification of the 44 v2-unmatched works. Confirmed that most failures were caused by the fuzzy threshold being too strict, not by actual absence from OL. 6 works found in the dump population under different work_keys were added to canonical (main). 30 additional works exist in OL but not in the dump population; tracked separately as supplementary evidence.

#### Results summary (2026-04-05確定)

| Category | Count |
|---|---|
| canonical main (primary analysis) | **104件** |
| v3 extra (supplementary, not in dump) | 30件 |
| Permanently unresolved | 8件 |
| **phd_corpus total** | **142件** |

**Permanently unresolved 8件:**
- OLに存在しない（6件）: A Sylvan Queen, Romance of a Chalet, Cousin Simon, A Crown of Straw, The Hark Riders, Seven Keys to Bald Pate
- ノンフィクション（1件）: Rifle, rod, and gun in California
- phd_corpus誤記（1件）: "Confessions St Augustine / Howells"（Augustineの著作）

⚠️ **FORCE_MAP既知バグ（#21）:** 3件のwork_keyが別著者作品を誤って指している。JSTOR値は修正済み。

#### Scope of verification
**Covered:** All 104 canonical (main) works. JSTOR rescanned with correct author names.
**Not covered:** work_key correctness for 34,691 non-canonical works.

---

## Stage 4: Enrichment

### 4a. OCLC Bulk Fetch

**Outputs:** `derived/ol_dump_oclc_all.tsv` (91,449 rows; 30,101 works with OCLC)
**Command:** `python3 scripts/fetch_oclc_from_dump.py`

---

### 4b. HathiTrust Matching (htrc × OL) — v2

**Inputs:** `derived/ol_dump_oclc_all.tsv` + `data/htrc-fiction_metadata.csv`

| Metric | Value |
|---|---|
| v1 OCLC照合 | 41/79件（1923年以前canonical） |
| v2 タイトル補完追加 | +22件（スコア≥90） |
| **v2合計** | **63/79件（1923年以前canonical）** |
| 除外2件 | The North Star、The Innocents/Machard |
| 1924年以降出版 | 16件——著作権制約によりHTRC対象外 |

**Output:** `derived/htrc_ol_dump_match_summary_v2.tsv`

---

### 4d. Author Name Lookup (OL Authors Dump)

**Output:** `derived/ol_author_lookup.tsv` (607MB — local only)
**Output:** `derived/ol_dump_population_with_author.tsv` (34,789 rows)
**Results:** 付与率: 34,434/34,789 (99.0%)

---

### 4e. Wikidata Sitelink Fetch

**Final output:** `derived/wikidata_sitelinks_final.tsv`
**Coverage:** canonical 60/98件 sitelink > 0
**§6b多指標分析から除外:** coverage不十分のためedition_countを代替採用（#22参照）

---

### 4f. Edition Count (OL Editions Dump) — 完了 2026-03-28

**Input:** `raw/ol_dump/ol_dump_editions_2026-02-28.txt.gz` (12GB, 55,615,769行)
**Output:** `derived/ol_edition_counts.tsv` (34,789 rows)
**Script:** `scripts/build_edition_counts.py`

| Metric | Value |
|---|---|
| canonical中央値（main 104件） | 79.0 |
| non-canonical中央値 | 2.0 |

#### Hollow canon edition counts — 全件確定値（2026-04-02、The Uncalled追加2026-04-05）

全24件、missing: 0。`work_id` (jstor_mentions) と `work_key` (ol_edition_counts) は同形式で直接結合可能。

| Title | Author | edition_count |
|---|---|---|
| The Moon and Sixpence | W. Somerset Maugham | 397 |
| White Fang | Jack London | 387 |
| The Border Legion | Zane Grey | 302 |
| Tarzan of the Apes | Edgar Rice Burroughs | 226 |
| The Mystery of Cloomber | Arthur Conan Doyle | 215 |
| King Coal | Upton Sinclair | 86 |
| The Grand Babylon Hotel | Arnold Bennett | 75 |
| The Yearling | Marjorie Kinnan Rawlings | 65 |
| Senator North | Gertrude Franklin Atherton | 29 |
| The Red Axe | S. R. Crockett | 28 |
| The Frontiersmen | Charles Egbert Craddock | 9 |
| Megda | Emma Dunham Kelley | 6 |
| Stepsons of Light | Eugene Manlove Rhodes | 5 |
| Alas! | Rhoda Broughton | 3 |
| The Homeward Trail | Waldron Baily | 3 |
| The Golden Cage | Iris Bromige | 3 |
| The Sea Witch | Alexander Laing | 3 |
| Hearts Courageous | Hallie Erminie Rives | 2 |
| The Damascus Road | Jay Parini | 2 |
| The North Star | M. E. Henry-Ruffin | 1 |
| The Innocents | Alfred Machard | 1 |
| Princess Salome | Burris Jenkins | 1 |
| Trelawny | Holman Freeland | 1 |
| The Uncalled | Paul Laurence Dunbar | 1 |

---

## Stage 5: Academic Citations Enrichment

### 5a. JSTOR Full Scan — 完了

**Output:** `derived/jstor_mentions.tsv` (30,962 rows)

#### Confirmed canonical indicator values (main 104件・2026-04-05確定)

| Metric | Canonical (n=104) | Non-canonical (n=30,874) |
|---|---|---|
| Zero hits | 24 (23.1%) | 27,456 (88.9%) |
| 1 or more hits | 80 (76.9%) | 3,418 (11.1%) |
| Median | **6** | **0** |
| Mean | 18.3 | 2.2 |
| Maximum | 443 (Ulysses) | 10,559 |

⚠️ FORCE_MAP 3件の`author`列は誤著者名のまま。`jstor_mention_count`値は修正済み。

---

### 5b. OpenAlex Snapshot Scan — 完了 2026-03-26

**Output:** `derived/openalex_snapshot_mentions.tsv`

| Metric | Canonical (n=104) | Non-canonical |
|---|---|---|
| Median | **3.0** | **0** |
| ≥1 hit | 79.6% | — |

---

### 5c. OpenAlex CI論文抽出 — 完了 2026-04-02

**Output:** `derived/oa_ci_works_v2.tsv` (1,220件、1974–2025)
⚠️ 2023年=1件・2024年=0件は欠落。referenced_works充填率: 27%。

---

### 5d. Temporal Citation Analysis — 完了 2026-04-02

**Output:** `derived/temporal_citations_api.tsv` (104件)
⚠️ OA APIの`counts_by_year`は直近10年分のみ。歴史的時系列はHathiTrustカプセルに委ねる。

---

### 5e. v3 Extra Canonical — 補完的証拠（2026-04-05）

phd_corpusの142件のうちv2でunmatchedだった44件を個別OL APIで検索。30件がOLに存在するがダンプ母集団に不在。JSTOR・OA・edition_countの3指標を取得して補完的記録として保存。

**Outputs:**
| File | Description |
|---|---|
| `derived/jstor_extra29.tsv` | 30件のJSTOR値（28件=0、93.3%） |
| `derived/oa_extra30.tsv` | 28件のOA値（24件=0） |
| `derived/extra_canonical_editions.tsv` | 30件のedition_count（OL API経由、2026-04） |

**補完的発見:** v3 extra 30件の93.3%がJSTOR=0。OLダンプフィルタを通過しなかった作品は学術的引用においてもほぼ完全に不可視であることを確認。hollow canonの構造がデータ設計の偶然でなく実際の注目分布を反映していることの補強証拠。

**HathiTrust（extra 30件）:** HTRCメタデータにタイトル列なし、OCLC番号も不在のため照合不可（#31参照）。

---

## Stage 6: Analysis

### 6a. Hollow Canon / Shadow Canon Analysis — 完了

**Hollow canon（main）:** 24件（canonical=1 AND jstor=0）— 全件edition_count確定済み（§4f参照）
**Shadow canon（暫定）:** `derived/shadow_canon_final.tsv`

⚠️ 属性バイアス（ジェンダー・人種）分析は未実施。第3章執筆前に対処すること。

---

### 6b. Multi-Signal Agreement Analysis — 完了 2026-03-28

**4指標:** jstor / openalex / edition_count / htid_count

#### Spearman相関行列（n=34,789）

| ペア | ρ | 有意性 | 軸 |
|---|---|---|---|
| jstor ↔ openalex | 0.293 | *** | 学術的引用軸 |
| edition ↔ htid | 0.257 | *** | 文化的流通軸 |
| jstor ↔ edition | 0.197 | *** | 軸間（弱い正相関） |
| oa ↔ edition | 0.260 | *** | 軸間（弱い正相関） |
| jstor ↔ htid | -0.004 | n.s. | **軸間独立** |
| oa ↔ htid | 0.009 | n.s. | **軸間独立** |

---

### 6c. Temporal Analysis — 方針変更済み

HathiTrustカプセルに委ねる（期限: 2026年9月）。

---

## Stage 7: Preliminary Study — Critical Discourse Analysis

### Status: Phase 1完了（2026-04-02）→ Phase 2（HathiTrustカプセル）へ

#### Outputs（derived/）

| ファイル | 内容 |
|---|---|
| `ci_articles.tsv` (254件) | 記事メタデータ（⚠️ title_extractedは全件空） |
| `ci_footnotes.tsv` (8,941件) | 脚注テキスト（信頼できる） |
| `ci_concept_freq.tsv` | 概念グループ頻度 |
| `ci_intro_patterns.tsv` | レトリカルパターン |
| `oa_ci_works_v2.tsv` (1,220件) | CI論文OA収録版 |

#### 確定結果

Foucault: 42/15（首位）、Cavell: 21/7、Schmitt: 16/6、Latour: 11/6
**決定的不在:** Rainey・Moretti・Huyssen
**概念頻度:** form/formalism(83) > field_formation(36) > distant_reading(33)
**議論構造:** positive_alignment : position_to_overcome = 2.3 : 1

---

## Dissertation Progress（2026-04-05）

| 章 | 状態 | ファイル |
|---|---|---|
| 第1章 | 草稿完成 v4 | `chapter1_v4.docx` |
| 第2章 | 草稿完成 v3 | `chapter2_v3.docx` |
| 第3章 | 未着手 | — |
| 第4章 | 未着手（HathiTrust待ち） | — |

☑ 1・2章：34,789件の母集団構築・2軸構造の実証・hollow canon 24件の特定と制度論的解釈

☑ 3・4章：HathiTrust時系列分析待ち・shadow canon属性分析・CI言説分析本格化は今後

---

## Release History

| Release ID | Date | Key Artifact | Notes |
|---|---|---|---|
| population-dump-v1 | 2026-03-09 | `ol_dump_population_fiction_2026-02-28.tsv` (34,789) | **current baseline** |
| citations-v1 | 2026-03-27 | `jstor_mentions.tsv` + `openalex_snapshot_mentions.tsv` | |
| enrichment-v2 | 2026-03-28 | `ol_edition_counts.tsv` + `htrc_ol_dump_match_summary_v2.tsv` | |
| analysis-6b-v2 | 2026-03-28 | `multi_signal_merged.tsv` + `spearman_matrix.tsv` | §6b完了 |
| stage7-phase1-v1 | 2026-04-02 | `ci_articles.tsv` + `ci_footnotes.tsv` + `shadow_canon_final.tsv` | |
| canonical-v3 | 2026-04-05 | `jstor_mentions.tsv`（104件）+ `jstor_extra29.tsv`（30件）+ `extra_canonical_editions.tsv` | v3 matching完了・数値確定 |

---

## Known Limitations (Cumulative)

1. `first_publish_year` mis-registration ~2.5% (unfilterable)
2. Non-fiction residual contamination ~1% post-filter
3. OL search bias — pilot study only
4. OCLC identifier audit covers 100 works only
5. HathiTrust match covers 18.0% of population
6. WorldCat holdingsCount structurally unavailable
7. WorldCat Discovery API: institutional contract barrier
8. **phd_corpus 8件が永続的未解決**（旧44件のうち6件はv3 mainに、30件はv3 extraに回収）
9. htrc omnibus volumes inflate htid_count
10. FAST ID label resolution blocked by network policy
11. OL dump coverage: works not registered in OL treated as non-existent
12. OL dump language field absent at Work level
13. JSTOR abstract field is 0.0% populated → title-co-occurrence only
14. JSTOR title_norm deduplication reduced index to 30,962 works
15. Works with unknown author (355 works, 1.0%) receive title-only JSTOR matching
16. OpenAlex Concepts/Topics API cannot identify individual novels
17. work_key accuracy verified for canonical 104 works only
18. JSTOR mention counts for non-canonical works are unrevised
19. Shadow canon list contains works outside 1880–1950 scope
20. OpenAlex snapshot scan uses title-only matching
21. FORCE_MAP 3件のwork_keyが誤った作品を指している（jstor値は修正済み）
22. Wikidata sitelink coverage: canonical 60/98件のみ — §6b分析から除外
23. HTRCタイトル照合v2: OCLC世代不一致により初回41→v2補完後63件
24. Internet Archive download統計は公開APIから取得不可
25. edition_countはOLダンプ収録版のみカウント
26. htid ↔ edition相関の著作権切断バイアス: 全体ρ=0.257、1923年以前サブセットρ=0.374
27. OA APIのcounts_by_yearは直近10年分のみ
28. `ci_articles.tsv`のtitle_extractedは全254件空
29. oa_ci_works_v2.tsvの2023年=1件・2024年=0件は欠落
30. Shadow canon属性バイアス分析は未実施
31. **v3 extra 30件はHTRC照合不可**（HTRCメタデータにタイトル列なし、OCLC番号も不在）。JSTOR/OA/edition_countの3指標のみ取得済み。edition_countはOL API経由（2026-04）でダンプ由来値と出典が異なる。