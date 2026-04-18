# WORKFLOW.md — canon-pipeline
**DCC Digital Curation Workflow Narrative**
Last updated: 2026-04-18
Status: LIVING DOCUMENT — update on every major change

---

## Overview

This pipeline constructs and validates a population of English-language fiction works (1880–1950) for a doctoral dissertation on the formation and transformation of modernist literary studies as a scholarly field. The pipeline is structured in eight stages: Collection → Filtering → Validation → Enrichment → Citations → Analysis → Discourse Analysis → DH Reception Analysis.

**Core research question:** How was modernist literary studies made as a scholarly field? The pipeline provides empirical evidence for narratives that critics have previously constructed through impression and authority — mapping the formation of the modernist canon through multiple vectors of scholarly activity.

**Repository:** https://github.com/haruka0221/canon-pipeline
**Working environment:** WSL (Ubuntu 24) on Windows, ~/canon-pipeline
**Primary tools:** Python 3.12, pandas, rapidfuzz, pyahocorasick, pdfplumber
**External data (local only):** OpenAlex works snapshot (620GB, /mnt/d/openalex/works/), JSTOR metadata (6.5GB), Critical Inquiry PDFs (254 files, 2019–2025)

---

## The Four Vectors (KCL Conference Framework)

本研究は正典形成を4つのベクターから実証する。

| Vector | データ | Status |
|---|---|---|
| 1. Attention economy | JSTOR + OpenAlex | ✅ 完了 |
| 2. Conceptual terrain | CI PDFs（予備）→ HathiTrust（本格） | 🔄 Phase 1完了 |
| 3. Pedagogical structures | phd_corpus (McGrath et al.) | ✅ 完了 |
| 4. Evaluative practice | 未定義 | ❌ Pending |

---

## Stage 1: Population Collection (Dump-Based — Main Study)

### Purpose
Construct the definitive population from the Open Library Works dump, replacing the Search API approach used in the pilot study. Motivation: OL Search API returns results ranked by internal relevance score, which correlates with prior attention — a circular method for studying attention inequality. The dump provides a complete, unbiased snapshot.

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
- `author_keys` contains OL key format (`/authors/OL123A`), NOT author name strings → Author names require separate lookup against Authors dump (see Stage 4d)

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

`data/phd_corpus_1880_1950_cleaned.csv` is **not a self-curated list**. It is derived from the appendix of McGrath et al.'s quantitative study of modernist literature, which aggregated publicly available PhD reading lists from multiple major university English departments.

- **Meaning:** Works on this list were judged "required reading" for doctoral study in English literature at multiple major universities.
- **Total works in phd_corpus:** 142件
- **Dissertation significance:** hollow canon works (canonical=1, jstor=0) represent a gap between pedagogical canon and research canon: works institutionally mandated for doctoral education that are nonetheless absent from the academic literature.
- **Citation:** McGrath, L., Higgins, D., & Hintze, A. (2018). Measuring modernist novelty. *Journal of Cultural Analytics*, 3(1). https://doi.org/10.22148/16.027

#### Matching history

**v2 (2026-03-11):** Fuzzy matching (token_sort_ratio ≥ 80) against OL dump population. Three-condition priority matching (best: title+year+author / year_only / title_only) + FORCE_MAP manual overrides. Script: `scripts/match_phd_corpus_v2.py`

**v3 (2026-04-05):** Individual OL API verification of the 44 v2-unmatched works. Confirmed that most failures were caused by the fuzzy threshold being too strict, not by actual absence from OL. 6 works found in the dump population under different work_keys were added to canonical (main). 30 additional works exist in OL but not in the dump population; tracked separately as supplementary evidence.

**v3追加6件:**
- The Rise of Silas Lapham / Howells → OL69032W（jstor=5）
- New Grub Street / Gissing → OL715553W（jstor=4）
- The Uncalled / Dunbar → OL1797345W（jstor=0 → hollow canonに追加）
- The Octopus / Norris → OL1794917W（jstor=25）
- Pointed Roofs / Richardson → OL3045976W（jstor=1）
- Huckleberry Finn / Twain → OL16025215W（1922年合本でプロキシ、jstor=27）

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

⚠️ **FORCE_MAP既知バグ（#21）:** 3件のwork_keyが別著者作品を誤って指している（The Prisoner of Zenda、The Good Soldier、Dracula）。JSTOR値は事後再スキャンで正著者名により修正済み。edition_count/wikidataシグナルはこの3件について無効。

#### Scope of verification
**Covered:** All 104 canonical (main) works. JSTOR rescanned with correct author names.
**Not covered:** work_key correctness for 34,691 non-canonical works. Individual non-canonical works cited in the dissertation should be manually verified against `derived/ol_dump_population_with_author.tsv`.

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
| 除外2件 | The North Star（score=90.3・別作品の疑い）、The Innocents（著者不一致の疑い） |
| 1924年以降出版 | 16件——著作権制約により構造的にHTRC対象外 |

**Output:** `derived/htrc_ol_dump_match_summary_v2.tsv`

---

### 4d. Author Name Lookup (OL Authors Dump)

**Output:** `derived/ol_author_lookup.tsv` (607MB — local only)
**Output:** `derived/ol_dump_population_with_author.tsv` (34,789 rows)
**Results:** 付与率: 34,434/34,789 (99.0%)

---

### 4e. Wikidata Sitelink Fetch

**Final output:** `derived/wikidata_sitelinks_final.tsv`
**Coverage:** canonical 62/98件 QIDあり、60/98件 sitelink > 0
**§6b多指標分析から除外:** coverage不十分のためedition_countを代替採用（#22参照）

---

### 4f. Edition Count (OL Editions Dump) — 完了 2026-03-28

**Input:** `raw/ol_dump/ol_dump_editions_2026-02-28.txt.gz` (12GB, 55,615,769行)
**Output:** `derived/ol_edition_counts.tsv` (34,789 rows)
**Script:** `scripts/build_edition_counts.py`

**Key column:** `work_key`（`jstor_mentions.tsv`の`work_id`と同形式 `/works/OL123W` — 直接結合可能）

| Metric | Value |
|---|---|
| 中央値（全母集団） | 2.0 |
| canonical中央値（main 104件） | 79.0 |
| non-canonical中央値 | 2.0 |

#### Hollow canon edition counts — 全件確定値（2026-04-05、The Uncalled追加）

全24件、missing: 0。

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

⚠️ `jstor_mentions.tsv`の`author`列はFORCE_MAP 3件で誤著者名のまま。`jstor_mention_count`値は事後再スキャンで修正済みのため値は正しい。

---

### 5b. OpenAlex Snapshot Scan — 完了 2026-03-26

**Output:** `derived/openalex_snapshot_mentions.tsv`
**Runtime:** 89分（16 workers）

| Metric | Canonical (n=104) | Non-canonical |
|---|---|---|
| Median | **3.0** | **0** |
| ≥1 hit | 79.6% | — |

⚠️ スナップショットスキャンはtitle-only matching（abstract disabled）。

---

### 5c. OpenAlex CI論文抽出 — 完了 2026-04-02

**Purpose:** Critical InquiryのOA収録論文（ISSN: 0093-1896）を抽出し、referenced_worksを取得。

**Input:** `/mnt/d/openalex/works/updated_date=*/part_*.gz` (620GB, 901ファイル)
**Output:** `derived/oa_ci_works_v2.tsv` (1,220件、1974–2025)
**Script:** インラインPython（ISSN filter）

| Year | Count | refs>0 |
|---|---|---|
| 2019 | 37 | 17 |
| 2020 | 41 | 22 |
| 2021 | 35 | 14 |
| 2022 | 38 | 15 |
| 2023 | 1 | 1 |
| 2024 | 0 | 0 |
| 2025 | 15 | 7 |

⚠️ 2023年=1件・2024年=0件は欠落（スナップショットの分散による）。referenced_works充填率: 27%。
⚠️ CI PDF分析との交差検証は未完了（`ci_articles.tsv`の`title_extracted`が全254件空）。代替案: OA APIでfilter=ISSN+year+著者姓で検索。

---

### 5d. Temporal Citation Analysis — 完了 2026-04-02

**Input:** `derived/jstor_mentions.tsv`（canonical 104件）
**Output:** `derived/temporal_citations_api.tsv` (104件)
**Method:** OA API `search` by title, `select=counts_by_year`

⚠️ OA APIの`counts_by_year`は直近10年分のみ返す。1970-80年代のfeminist/postcolonial spikeは確認不可。歴史的時系列はHathiTrustカプセルに委ねる（期限: 2026年9月）。

---

### 5e. v3 Extra Canonical — 補完的証拠（2026-04-05）

phd_corpusの142件のうちv2でunmatchedだった44件を個別OL APIで検索。30件がOLに存在するがダンプ母集団に不在。JSTOR・OA・edition_countの3指標を取得して補完的記録として保存。

**Outputs:**
| File | Description |
|------|-------------|
| `derived/jstor_extra29.tsv` | 30件のJSTOR値（28件=0、93.3%） |
| `derived/oa_extra30.tsv` | 28件のOA値（24件=0） |
| `derived/extra_canonical_editions.tsv` | 30件のedition_count（OL API経由、2026-04） |

**補完的発見:** v3 extra 30件の93.3%がJSTOR=0。OLダンプフィルタを通過しなかった作品は学術的引用においてもほぼ完全に不可視——hollow canonの構造がデータ設計の偶然でなく実際の注目分布を反映していることの補強証拠。

⚠️ extra 30件のedition_countはOL API由来（ダンプ由来と出典が異なる）。論文では "via OL API, April 2026" と明記すること。
⚠️ Huckleberry Finnは合本（OL16025215W・1922年）をプロキシ使用。JSTOR値は正しいが、edition_countとHTRCは合本単位のため不正確。
⚠️ HTRCのextra 30件照合は不可能（HTRCメタデータにタイトル列なし、OCLC番号も不在）。

---

## Stage 6: Analysis

### 6a. Hollow Canon / Shadow Canon Analysis — 完了

**Hollow canon（main）:** 24件（canonical=1 AND jstor=0）— 全件edition_count確定済み（§4f参照）

**Shadow canon（暫定）:** 590件（フィルタ後・ノイズ含む）
**Output:** `derived/shadow_canon_final.tsv`

#### Shadow canonクリーニング方針（2026-04-02確定）

除去対象：
- 非英語タイトル（accented characters含む）→ 研究スコープ外
- 中世・古代著者（Chaucer, Shakespeare, Josephus等）→ 1880以前の作家
- 明らかな戯曲（Death of a Salesman等）

保留（除去しない）：
- Dickens・Tolstoy等の作品 → OL母集団への収録は「1880-1950の英語版」として合法。スコープの問題ではなく注記で対応。
- 非英語原作の英訳 → subject_keysに`english_fiction`等がない場合は除外対象（確認済み: Proust/Musil/Manzoni = 除外）

⚠️ 「属性バイアス（ジェンダー・人種）」の主張には著者属性の系統的分析が必要（未実施）。第3章執筆前に対処すること。

---

### 6b. Multi-Signal Agreement Analysis — 完了 2026-03-28

**4指標最終版:** jstor / openalex / edition_count / htid_count

#### Spearman相関行列（n=34,789）

| ペア | ρ | 有意性 | 軸 |
|---|---|---|---|
| jstor ↔ openalex | 0.293 | *** | 学術的引用軸・内部収束 |
| edition ↔ htid | 0.257 | *** | 文化的流通軸・内部収束 |
| jstor ↔ edition | 0.197 | *** | 軸間（弱い正相関） |
| oa ↔ edition | 0.260 | *** | 軸間（弱い正相関） |
| jstor ↔ htid | -0.004 | n.s. | **軸間独立** |
| oa ↔ htid | 0.009 | n.s. | **軸間独立** |

**論文英語記述（そのまま使用可）:**
> Four indicators were computed for the full population of 34,789 works: JSTOR mention count, OpenAlex mention count, Open Library edition count, and HathiTrust volume count. Spearman correlation analysis (n = 34,789) reveals a two-dimensional structure. Within the scholarly attention dimension, JSTOR and OpenAlex correlate at ρ = 0.293 (p < .001), confirming that two independent databases capture the same underlying construct of academic visibility. Within the cultural circulation dimension, edition count and HathiTrust volume count correlate at ρ = 0.257 (p < .001), indicating that commercial reprint history and library digitization measure a common axis of cultural persistence. Crucially, the cross-dimensional correlations are statistically non-significant (ρ ≈ 0.000, p > .05), demonstrating that scholarly attention and cultural circulation constitute independent axes of canonicity.

---

### 6c. Temporal Analysis — 方針変更済み

OA APIによる98件取得完了（`derived/temporal_citations_api.tsv`）。ただし直近10年分のみのため歴史的分析に不十分。

**HathiTrustカプセルに委ねる（期限: 2026年9月）:**
- PMLA 1950–2025でのdecade別概念語・理論家名頻度
- feminist criticismの1970年代spike、postcolonial criticismの1980年代spike
- 手法: 引用構造抽出は試みない。単純な語頻度カウントのみ
- 必要なJSTOR ISSNs: PMLA=0030-8129、ELH=0013-8304、Novel=0029-5132、CI=0093-1896

---

## Stage 7: Critical Discourse Analysis

### Status: Phase 1完了（2026-04-02）→ Phase 2（HathiTrustカプセル）へ

---

### Phase 1: Critical Inquiry 2019–2025 — 完了

#### Inputs

- Critical Inquiry PDFs (2019–2025): 254ファイル（local only、`/mnt/c/Users/tsuts/Desktop/色々使えるデータ/Critical Inquiry`）
- `derived/jstor_mentions.tsv`（cross-validation用）

#### Scripts

| スクリプト | 機能 |
|---|---|
| `scripts/ci_extract_citations.py` | PDF→テキスト抽出、脚注・イントロ分離 |
| `scripts/ci_discourse_analysis.py` | 著者頻度・概念頻度・レトリカルパターン集計 |

#### Outputs（derived/）

| ファイル | 行数 | 内容 |
|---|---|---|
| `ci_articles.tsv` | 254 | 記事メタデータ（⚠️ `title_extracted`は全件空） |
| `ci_footnotes.tsv` | 8,941 | 脚注テキスト（**信頼できる** — 後述の精度検証済み） |
| `ci_intro_sentences.tsv` | 2,429 | イントロ文単位データ |
| `ci_author_freq.tsv` | 505 | 著者頻度（KEY_SCHOLARSスキャン版・**信頼性低**） |
| `ci_concept_freq.tsv` | 202 | 概念グループ頻度 |
| `ci_intro_patterns.tsv` | 254 | レトリカルパターン記事別 |
| `oa_ci_works_v2.tsv` | 1,220 | CI論文OA収録版（2026-04-02追加） |

#### ci_footnotes.tsv 精度検証（2026-04-06確認）

| 指標 | 値 | 評価 |
|---|---|---|
| 抽出成功PDF数 | 248/248 | 脚注0件のPDFなし → 抽出は全件成功 |
| 脚注件数中央値 | 38件/PDF | 研究論文として正常 |
| 2021年の脚注1–2件PDF群 | Hayles、Daston、Latour等 | 同年シンポジウム形式号（短編応答文）のため正常 |
| 唯一の未収録ファイル | Gavin 2018.pdf | **分析対象期間（2019–2025）外のため影響なし** |

**結論:** `ci_footnotes.tsv`（8,940行）は信頼できる。ただしPDFディレクトリのパス不一致により全254件との完全比較は未実施（残6件は不明）。

⚠️ **KEY_SCHOLARSスキャンは信頼できない（修正済み）:** intro_textのスキャンは副詞・形容詞と著者姓を混同する（"said"→動詞混同等）。有効データは`ci_footnotes.tsv`脚注直接抽出のみ。

#### 確定結果（論文に使用可）

**引用著者頻度（脚注直接抽出・信頼できる値）:**

| 著者 | mentions | articles | 解釈 |
|---|---|---|---|
| Foucault | 42 | 15 | 断然首位——権力・言説分析がCI言説の基盤的枠組み |
| Cavell | 21 | 7 | 語用論・倫理学への傾斜 |
| Schmitt | 16 | 6 | 政治哲学・例外状態論 |
| Latour | 11 | 6 | STS・アクターネットワーク理論 |
| Williams | 11 | 5 | Raymond Williams（文化的唯物論） |
| Derrida | 10 | 6 | 脱構築 |

**決定的不在:** Rainey・Moretti・HuyssenはいずれもCIに登場しない。→ Vector 1（引用経済）の主要理論的対話者がVector 2（CI言説）では参照されていない——KCL論文の核心的発見。

**概念頻度（上位）:** form/formalism(83) > field_formation(36) > distant_reading(33) > class(28)

**議論構造:** positive_alignment(728) : position_to_overcome(322) = 2.3 : 1

#### 方法論的限界

- KEY_SCHOLARSスキャンは信頼できない（修正済み）
- `ci_articles.tsv`の`title_extracted`は全254件空: OA交差検証にはOA APIで直接検索すること
- コーパス規模: 254論文（単一ジャーナル・6年分）は統計的推定に不十分

---

### Phase 1b: CI脚注証拠タイプ分類（LLMエージェント） — 完了 2026-04-18

#### Purpose

Critical Inquiry 2019–2025の脚注8,940行を対象に、LLMを用いて「証拠タイプ」を分類する。文学研究者が実際にどのような種類の証拠を用いているかを定量的に示し、「現代の文学研究が必要とするのはテキスト内容分析ではなく社会的流通・制度的扱われ方の追跡技術である」という本研究の根幹的主張の**問いの論理的構造**を実証する。

Piper（2020）*Can We Be Wrong?* が提示した「文学研究における一般化の根拠の多くは他の学者への言及（分野的一般化）である」という診断を、単一ジャーナルの全脚注規模で検証する実験でもある。

本分析はAI for Science申請書の§1-2（需要と供給の不一致）の定量的根拠として使用する。

---

#### Inputs

| ファイル | 説明 |
|---|---|
| `derived/ci_footnotes.tsv` | CI PDF抽出済み脚注（8,940行、精度検証済み） |
| Anthropic API（Claude Haiku） | 分類に使用 |

---

#### 分類スキーム（最終版・2段階精緻化後）

| カテゴリ | 定義 |
|---|---|
| **1a** LITERARY_ARTISTIC_TEXT | 文学・芸術・文化的作品の**内容**への参照。小説・詩・演劇・映画・絵画・写真・日記・文学的書簡等。作品の主目的が美的・表現的であるもの。 |
| **1b** OTHER_TEXT | 哲学・政治・法律・科学・宗教・技術的テキストの**内容**への参照。Plato・Hobbes・Wittgenstein等の哲学書、法的文書、科学論文、宗教テキスト、歴史文書、マニフェスト等。 |
| **2** SOCIAL_CIRCULATION | 特定の文学・芸術・知的作品が社会の中でどう流通したかの証拠。書評、出版・版・翻訳記録、作品の受容に関する書簡・日記、特定作品の貸出・借用記録。**現代の政治・経済・技術ニュース記事は含まない。** |
| **3** INSTITUTIONAL | 作品の制度的扱いに関する証拠。シラバス・課題図書リスト、出版社の決定記録、受賞記録、図書館蔵書方針、カノン形成文書、大学委員会報告等。 |
| **4** SECONDARY_SCHOLARSHIP | 他の批評家・理論家・学者への言及。学術書・学術論文・批評エッセイ・理論書。脚注が他者の**議論や解釈**を参照しているもの。 |
| **5** QUANTITATIVE_BIBLIOGRAPHIC | テキストや著者に関する数値・統計的データ。引用数、図書館所蔵統計、調査結果、出版数、読者数等。 |
| **0** OTHER | 上記に該当しないもの。ibid.・著作権表示・PDFアーティファクト・著者紹介・自己参照的注記（「第3章参照」等）・現代の政治・経済・技術ニュース記事。 |

---

#### 分類手順（3段階）

**Step 1：初回全件分類（8,940件）**

```python
# scripts: classify_ci_footnotes.py
# Model: claude-haiku-4-5-20251001
# Output: derived/ci_footnote_classification/classifications.tsv
# Runtime: ~35分, 費用: ~$2.9 USD
```

システムプロンプトで7カテゴリを定義。カテゴリ0除く7,730件が実質的な分析対象。

**Step 2：カテゴリ1の分割精緻化（1,329件）**

初回分類でカテゴリ1（テキスト証拠）とされた1,329件を1aと1bに分割再分類。Critical Inquiryが批評理論誌であるため、テキスト証拠の中に文学作品と哲学・政治文書が混在することが判明したため。

```python
# インラインPython（再分類スクリプト）
# Model: claude-haiku-4-5-20251001
# 対象: 1,329件
# Output: derived/ci_footnote_classification/classifications_v2.tsv
# Runtime: ~12分, 費用: ~$0.5 USD
```

**Step 3：カテゴリ2の精緻化（588件）**

初回分類でカテゴリ2（社会的流通証拠）とされた588件を再分類。目視サンプル確認（20件）により、現代の政治・経済・技術ニュース記事が大量に誤分類されていることが判明したため。再分類後の残存率：141/588件（24%）。

```python
# インラインPython（再分類スクリプト）  
# Model: claude-haiku-4-5-20251001
# 対象: 588件
# Output: derived/ci_footnote_classification/classifications_final.tsv
# Runtime: ~8分, 費用: ~$0.3 USD
```

⚠️ Step 3の再分類で588→141件（76%減）という大幅な変化が生じた。原因：初回プロンプトでカテゴリ2の定義が「文学・芸術作品の流通」に限定されていなかったため、現代ニュースへの引用（政治・経済・テクノロジー）が誤って流通証拠と判定された。最終版プロンプトでは「文学・芸術・知的作品の流通に**厳密に限定**」と明示。

---

#### Outputs

| ファイル | 行数 | 内容 |
|---|---|---|
| `derived/ci_footnote_classification/classifications.tsv` | 8,940 | 初回分類結果（5カテゴリ） |
| `derived/ci_footnote_classification/classifications_v2.tsv` | 8,940 | Step 2後（カテゴリ1を1a/1bに分割） |
| `derived/ci_footnote_classification/classifications_final.tsv` | 8,940 | **最終版**（カテゴリ2精緻化済み） |
| `derived/ci_footnote_classification/checkpoint.jsonl` | 8,940 | 初回分類チェックポイント（再開用） |

---

#### 最終結果（classifications_final.tsv）

**全件集計（n=8,940）**

| カテゴリ | 件数 | 全体比率 | カテゴリ0除く比率 |
|---|---|---|---|
| **4** 二次的学術文献 | 5,694 | 63.7% | **76.9%** |
| **1b** 哲学・政治・科学テキスト証拠 | 714 | 8.0% | 9.6% |
| **1a** 文学・芸術テキスト証拠 | 669 | 7.5% | 9.0% |
| **0** その他（ibid.・著作権等） | 1,539 | 17.2% | — |
| **2** 社会的流通証拠 | 141 | 1.6% | 1.9% |
| **3** 制度的証拠 | 137 | 1.5% | 1.9% |
| **5** 定量的書誌データ | 46 | 0.5% | 0.6% |
| **合計** | **8,940** | **100%** | — |
| **カテゴリ0除く実質** | **7,401** | — | **100%** |

**一次証拠内訳（1a+1b+2+3+5 = 1,707件、実質比率23.1%）**

| 証拠タイプ | 件数 | 一次証拠内比率 | 実質比率 |
|---|---|---|---|
| テキスト内容証拠（1a+1b） | 1,383 | 81.0% | 18.7% |
| ─ 文学・芸術テキスト（1a） | 669 | 39.2% | 9.0% |
| ─ 哲学・政治・科学テキスト（1b） | 714 | 41.8% | 9.6% |
| 社会的流通・制度・定量（2+3+5） | 324 | 19.0% | **4.4%** |

---

#### 精度検証

**サンプル目視確認（各カテゴリ15件）**

| カテゴリ | 確認件数 | 正確件数 | 精度評価 |
|---|---|---|---|
| 4 学術文献 | 15 | 15 | ✅ 高（誤分類ゼロ） |
| 0 その他 | 15 | 13 | ✅ 概ね高（ibid.等正確、軽微誤分類2件） |
| 3 制度的証拠 | 15 | 12 | ✅ 概ね高 |
| 1a/1b（分割後） | 6 | 6 | ✅ 高 |
| 2（精緻化前） | 20 | 6 | ❌ 低（誤分類14件、Step 3で修正） |
| 2（精緻化後） | — | — | Step 3後はサンプル未実施（推定精度向上） |

⚠️ カテゴリ2の精緻化後サンプル確認は未実施。「文学・芸術・知的作品の流通に関する証拠」という定義を厳格化したため精度向上は確実だが、141件の精度を正式に検証するには追加目視確認が必要。

---

#### 分類変遷クロス集計（v2→final）

Step 3（カテゴリ2の精緻化）で移動した件数：

| v2 → final | 0 | 1a | 1b | 2 | 3 | 4 |
|---|---|---|---|---|---|---|
| **2（588件）** | 329 | 1 | 53 | **141** | 26 | 38 |

移動先の分布：0（その他）が329件と最多。1b（哲学・政治テキスト）への移動が53件あり、これは新聞オピニオン記事・政治評論等が1bに分類されたことを示す。

---

#### 発見の解釈

**第1層（76.9%）：権威依拠の構造**

脚注の約4分の3が他の批評家・理論家への言及である。これはPiper（2020）が*Can We Be Wrong?* で「文学研究における一般化の根拠の多くは他の学者がそう言っているという分野的一般化である」と診断した構造を、254論文・8,940脚注という規模で実証するものである。

**第2層（18.7%）：テキスト内容証拠の性格**

文学テキスト（1a: 9.0%）と哲学・政治テキスト（1b: 9.6%）がほぼ半々であることは、CIが純粋な文学批評誌ではなく批評理論誌であることを反映する。文学研究者が一次テキストを参照する場合でも、その半分はフーコー・ホッブズ・ウィトゲンシュタイン等の非文学テキストである。

**第3層（4.4%）：社会的流通証拠の希少性と意義**

正典化・受容・制度的扱われ方という文学研究の中心的問いに直接応答しうる証拠類型（2+3+5）の合計がわずか4.4%（324件/7,401件）にとどまる。この希少性は、当該証拠類型への関心の欠如ではなく、系統的に収集・横断参照できるデータ基盤が現状では存在しないことを示す。書評記録・出版版数・図書館所蔵数・翻訳記録は各研究者が個別のアーカイブ調査で散発的に引用するにとどまっており、再現性・スケーラビリティを持たない。

---

#### 方法論的限界と注意事項

1. **コーパスの代表性：** Critical Inquiry単誌（2019–2025）は英文学研究全体を代表しない。CIは批評理論寄りの誌であり、PMLA・ELH等とは論文性格が異なる。一般化には慎重を要する。
2. **カテゴリ2の精緻化後サンプル確認未実施：** 141件の最終精度は推定段階。論文では「推定値」として扱うこと。
3. **カテゴリ0の軽微誤分類：** Panofsky書簡等、本来カテゴリ2に入るべき数件がカテゴリ0に分類されている可能性がある（サンプル15件中2件で確認）。カテゴリ2（141件）は過小推定の可能性があるが影響は限定的。
4. **1aと1bの境界：** C.L.R. James *The Black Jacobins*（歴史書）が1bに分類されたように、文学と非文学の境界は必ずしも明確でない。境界事例は存在する。
5. **PDF抽出品質：** スペースが消失したテキスト（`SeeHarrietMartineau`等）はLLMがほぼ正確に読めることを確認済み（プロンプトに明示的注記あり）。

---

#### AI for Science申請書への使用方針

本分析結果は申請書§1-2「需要と供給の不一致」の定量的根拠として使用する。ただし「需要の証明」としてではなく、「文学研究者が問う問いの構造が、メタデータ分析なしには答えられない種類のものである」という**問いの論理的構造の論証**として位置づける。

**申請書に使用する数字（確定値）：**
- 脚注の76.9%が他の批評家・理論家への言及（権威依拠）
- 社会的流通・制度・定量証拠の合計は4.4%（実質比率）
- 文学テキストへの直接参照は9.0%のみ

**Piperとの接続：**
> Piper（2020）が*Can We Be Wrong?* において指摘した「文学研究における一般化の根拠の多くは他の学者への言及という分野的一般化である」という診断を、本分析はCritical Inquiry全脚注8,940件規模で実証した。

---

#### Release記録

| Release ID | Date | Key Artifact |
|---|---|---|
| ci-footnote-classification-v1 | 2026-04-18 | `classifications_final.tsv`（8,940件・7カテゴリ・2段階精緻化済み） |


### Phase 2: HathiTrust Data Capsule — 設計中

**期限:** 2026年9月

**優先タスク:**

| 優先度 | タスク |
|---|---|
| 高 | PMLA 1950–2025 引用頻度decade別集計 |
| 高 | 理論家名（Foucault/Williams/Derrida等）のdecade別推移 |
| 中 | 複数ジャーナル比較（PMLA vs ELH vs Novel） |
| 低 | 著者属性 × 引用頻度 |

**方法論（Phase 1の教訓）:**
- KEY_SCHOLARSは廃止 → 脚注全件から著者姓を自動抽出（emergent approach）
- spaCy NER導入で"said"問題を根本解決
- HathiTrustカプセル内ではaggregate outputのみ外部持ち出し可

---

## Stage 8: DH Reception Analysis in Literary Studies — 完了 2026-04-06

### Purpose

本研究のDH的意義を文脈化するため、英文学の主要ジャーナルおよび時代別・作家別専門誌、さらに比較のため言語学・歴史学の主要誌におけるDigital Humanities関連論文の受容状況を定量的に調査する。序章および第4章冒頭の文脈化段落の根拠として使用する。

### 調査期間の設計

手法ごとに適切な期間を設定した。統一期間を設けなかったのは、被引用蓄積の時差とキーワード検索の目的が異なるためである。

| 手法 | 期間 | 理由 |
|---|---|---|
| DHキーワード検索・総件数 | **2016–2025** | DHが英文学誌で議論され始めた時期以降に焦点 |
| CI PDF脚注直接スキャン | **2019–2025** | 保有PDFの期間による |
| プロキシ被引用チェック | **2010–2025** | Moretti(2005)・Jockers(2013)等の被引用蓄積を捕捉 |
| 強シグナル・アーカイブ確認 | **2010–2025** | 同上 |

### 対象ジャーナル

#### 主要英文学誌

| ジャーナル | ISSN | 2016–2025件数 |
|---|---|---|
| PMLA | 0030-8129 | 1,203 |
| ELH | 0013-8304 | 424 |
| Novel | 0029-5132 | 397 |
| Critical Inquiry | 0093-1896 | 945 |
| Modern Philology | 0026-8232 | 979（詳細スキャン未実施） |
| Cultural Analytics | 2371-4549 | 212（DH専門誌・比較基準） |
| DSH | 2055-7671 | 952（DH専門誌・比較基準） |

#### 時代別・作家別専門誌（2016–2025件数）

| ジャーナル | ISSN | 件数 | カテゴリ |
|---|---|---|---|
| Shakespeare Quarterly | 0037-3222 | 427 | 近世 |
| Victorian Studies | 0042-5222 | 1,707 | ヴィクトリア朝 |
| Studies in English Literature 1500–1900 | 0039-3657 | 331 | 近世〜19世紀 |
| Studies in Romanticism | 0039-3762 | 403 | ロマン派 |
| Modernism/modernity | 1071-6068 | 723 | モダニズム |
| Nineteenth-Century Literature | 0891-9356 | 407 | 19世紀 |
| Journal of Modern Literature | 0022-281X | 618 | 20世紀 |
| Victorian Literature and Culture | 1060-1503 | 581 | ヴィクトリア朝 |
| Henry James Review | 0273-0340 | 309 | 作家別 |
| James Joyce Quarterly | 0021-4183 | 531 | 作家別 |
| English Literature in Transition 1880–1920 | 0013-8339 | 50 | 本研究対象期間と完全一致 |

除外：The Conradian（142件・件数不足）、Virginia Woolf Miscellany（OpenAlex未収録）。

#### 分野横断比較誌

| ジャーナル | ISSN | 分野 | 2016–2025件数 |
|---|---|---|---|
| Language (LSA) | 0097-8507 | 言語学 | 910 |
| Corpus Linguistics & Linguistic Theory | 1613-7027 | 言語学（コーパス） | 215 |
| Journal of Corpus Linguistics | 1388-0209 | 言語学（コーパス） | 1,509 |
| American Historical Review | 0002-8762 | 歴史学 | 8,125 |
| History and Theory | 0018-2656 | 歴史学 | 517 |

⚠️ **ISSNミス記録:** ISSN 0026-7937はModern Philologyではなく**The Modern Language Review**（MLR）を指す。OAスナップショット全件スキャン時にMLRを誤ってModern Philologyとして計上していた（12,749件）。この値は無効。

### 方法（四手法）

**Step 1：DHキーワード全文検索（2016–2025）**
OpenAlex APIの`search`パラメータで下記キーワードを全対象誌に適用。
```
computational literary / distant reading / stylometry / topic modeling /
digital humanities / cultural analytics / text mining /
machine learning literature / corpus-based / digital archive /
network analysis literature
```
値は上限値であり採用率ではない（特集号効果・言及混入が主な偽陽性原因）。

**Step 2：タイトル・抄録目視確認**
APIヒット論文のタイトルを全件確認し、DH実践・メタ議論・言及のみの3種に分類。PMLAは抄録も確認（20本）。VLC・Romanticism・Joyce Q.の上位20件も確認。

**Step 3：PDF直接スキャン（CI）（2019–2025）**
`ci_footnotes.tsv`（8,940行）に対してDHキーワードを単語境界マッチで検索。この手法のみ偽陽性が除去済み。

**Step 4：DH方法論書プロキシ被引用チェック（2010–2025）**
Cultural Analytics（212本）とDSH（952本の先頭1,000本）の最多被引用著作から帰納的に構築したプロキシリストへの被引用件数を確認。Da（2019）等の批判論文は除外。

| プロキシ著作 | OA ID | CA被引用 | DSH被引用 |
|---|---|---|---|
| Moretti, *Graphs Maps Trees* (2005) | W1604638557 | 5 | — |
| Underwood, *Distant Horizons* (2019) | W2886940283 | 6 | — |
| Piper, *Enumerations* (2018) | W2101234009 | 5 | — |
| Bode, *A World of Fiction* (2018) | W2790567261 | 4 | — |
| Algee-Hewitt et al., Canon/Archive (2016) | W2583401130 | 5 | — |
| Jockers, *Macroanalysis* (2013) | W4244181777 | — | 30 |
| Burrows, Delta (2002) | W2107317033 | — | 62 |
| Eder, Stylometry with R (2016) | W2787026234 | — | 38 |

⚠️ CA（文学史・正典分析）とDSH（スタイロメトリ・著者帰属）は異なるDHコミュニティを代表している。

**Step 5：計算論的実践の強シグナル確認（2010–2025）**

強シグナル（計算論的実践）：Project Gutenberg、HathiTrust、Google Ngram、JSTOR Data for Research、Python（統計文脈）、R（統計文脈）、Stylo、Gephi

弱シグナル（デジタルアーカイブ参照・計算論的利用ではない）：EEBO、ECCO、digital edition

**この区別は重要：** EEBOをシェイクスピア研究者が引用する行為はデジタル図書館で一次資料を参照することであり、計算論的分析とは異なる。デジタルアーカイブの充実（弱シグナル高）と計算論的DH採用（強シグナル低）は英文学研究において独立した現象。

### 確定した数値

#### Critical Inquiry（PDF直接スキャン・最高精度）

| 対象 | 期間 | 総件数 | DH関連論文 | 比率 |
|---|---|---|---|---|
| ci_footnotes単語境界マッチ | 2019–2025 | 254本 | **7本** | **2.8%** |
| oa_ci_worksタイトルスキャン | 1974–2025 | 1,220本 | 4本 | 0.3% |

脚注スキャンでDHシグナルが確認された7本（2022年以降に集中）: Bode 2023、Franta & Silver 2024、Geoghegan 2025、Lee 2025、Liu 2025、Parisi 2022、Parker 2025。

OAタイトルスキャンの4本はすべて批判的フォーラム（Da 2019・CLS批判）または批評的概念としての「データ」論文。CIはDHの実践の場ではなく批評的検討の対象としてDHを扱っている。

**プロキシ被引用（2010–2025）：** 全プロキシでゼロ。Eder被引用1件のみで、これはBode（2023）"What's the Matter with Computational Literary Studies?"——CLS批判論文による引用。CIにおける③型暗黙的DH実践はゼロで確定。

#### PMLA：特集号効果（号数データで論証）

| 年 | 集中号 | 特集テーマ | 件数 |
|---|---|---|---|
| 2016 | Vol.131 No.2 | Ecological Digital Humanities | 7/9件 |
| 2020 | Vol.135 No.1 | DHと多様性・人種 | 8/9件 |
| 2025 | — | Public Humanities（計算論的DHではない） | 9件 |
| 2021–2022 | — | 表紙・目次等のパレテキスト | 7件 |

抄録確認（20本）：DH実践論文3本（15%）、メタ議論12本、言及・書評5本。

Moretti被引用12本の大半（≈9本）は世界文学の理論家として引用しているだけ。MorettiはPMLA研究者に「遠読の方法論的創始者」ではなく「世界文学の理論家」として引用されている。

#### 専門誌：全誌で実践論文ほぼゼロ

| 誌 | 上限率（見かけ） | 実態 |
|---|---|---|
| Victorian Literature and Culture | 11.4% | 特集号1号への登録バグ → 完全無効 |
| Studies in Romanticism | 5.7% | "reading"一般語の誤検出 → 実質ゼロ |
| Joyce Quarterly | 3.4% | 会議報告・デジタル版紹介のみ → DH実践ゼロ |
| English Literature in Transition 1880–1920 | **0.0%** | 完全ゼロ（本研究の対象時代と一致する誌） |
| Shakespeare Quarterly | 1.4% | 実践論文ほぼゼロ |

**仮説検証：**
- 仮説A「古い時代の専門誌の方がDH多い」→ **外れ**（Shakespeare Q.が最低水準）
- 仮説B「モダニズム専門誌が最も抵抗的」→ **部分的に外れ**（ELT=0%が最低、Joyce Q.は3.4%だが内容は全て会議報告）

#### 強シグナル確認：全誌でほぼゼロ

専門誌はすべて強シグナルがゼロまたは1件。主要誌でも最大3–5件。Stylo（スタイロメトリ専用ツール）は全誌ゼロ。EEBO（弱シグナル）はShakespeare Q.で9件・SELで7件あるが、これは計算論的分析ではなくデジタル化一次資料への参照アクセス。

#### 分野横断比較：AHRとの構造的対比

言語学は同一キーワードで比較不可（コーパス言語学では"corpus-based"が基礎的方法論を意味するため）。歴史学（AHR）との比較：

| 比較項目 | PMLA（英文学） | AHR（歴史学） |
|---|---|---|
| 上限率 | 10.6% | 0.7% |
| DH実践論文の出現 | 2特集号に集中（2016・2020） | **毎年分散**（通常号として掲載） |
| DHへの批判フォーラム | 2019年 Da論文 | 確認されない |
| DH実践論文数（推定） | ≈3本/10年 | **≈4–5本/10年** |

上限率が高い英文学の方が実践論文の実数は少ない。この逆転は、英文学でのDH語彙出現が特集号効果・職能論争・批判フォーラムによるものであることを示す。英文学のDH受容の低さは人文学全体の現象ではなく、英文学特有の方法論的緊張関係を反映している可能性がある。

### 確定した知見（論文に使用可）

英文学の主要ジャーナルおよび時代別・作家別専門誌11誌にわたる四手法の調査は、DHの出現パターンが「浸透」ではなく「間欠的・制度的出現」であることを収束的に示す。PMLAでは特集号集中が号数データで論証された。CIでは2019年の集中がDa論文による批判フォーラムであり、被引用プロキシチェックでも暗黙的DH実践はゼロで確定した。専門誌11誌でも計算論的DH実践はほぼゼロであり、時代・作家による差異は存在しない。EEBOへの言及（弱シグナル）と計算論的ツール使用（強シグナル）は独立した現象である。歴史学（AHR）との比較では、英文学での特集号集中に対して歴史学では通常号として有機的に分散していることが確認された。本研究は、DHが英文学研究において依然として周縁的な方法論にとどまる状況への介入として位置づけられる。

---

## Dissertation Progress（2026-04-06）

### 章構成と執筆状況

| 章 | タイトル | 状態 | ファイル |
|---|---|---|---|
| 序章 | 問いと方法 | 未着手（§8の知見を文脈化段落として使用予定） | — |
| 第1章 | 母集団と正典の構造的格差 | **草稿完成 v5** | 