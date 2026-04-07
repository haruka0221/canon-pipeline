# WORKFLOW.md — canon-pipeline
**DCC Digital Curation Workflow Narrative**
Last updated: 2026-04-06
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

本研究のDH的意義を文脈化するため、英文学の主要ジャーナルにおけるDigital Humanities関連論文の受容状況を定量的に調査する。序章および第4章冒頭の文脈化段落の根拠として使用する。

### 対象ジャーナルと収録件数（2016–2025）

OpenAlex APIによる確認値（2026-04-06）。

| ジャーナル | ISSN | 2016–2025総件数 | 備考 |
|---|---|---|---|
| PMLA | 0030-8129 | 1,203 | MLA刊行・英語文学フラッグシップ |
| ELH | 0013-8304 | 424 | 研究論文中心・書評比率低 |
| Novel | 0029-5132 | 397 | フィクション研究専門誌 |
| Modern Philology | 0026-8232 | 979 | 文学史・批評史中心（詳細スキャン未実施） |
| Critical Inquiry | 0093-1896 | 1,220 | 学際批評誌（§7でPDF直接分析済み） |
| Cultural Analytics | 2371-4549 | 212 | DH文学研究専門誌（比較基準） |
| DSH | 2055-7671 | 952 | DH専門誌（比較基準） |

⚠️ **ISSNミス記録（2026-04-06確認）:** ISSN 0026-7937はModern Philologyではなく**The Modern Language Review**（MLR）を指す。Modern PhilologyのISSNは0026-8232が正しい。OAスナップショット全件スキャン時にMLRを誤ってModern Philologyとして計上していた（12,749件）。この値は無効。

### 方法

**Step 1:** OpenAlex API `filter=primary_location.source.issn:{issn},publication_year:2016-2025` で各誌の総件数を取得。

**Step 2:** OpenAlex APIの`search`パラメータ（タイトル＋抄録全文検索）で下記キーワードを各誌に適用（上限値の算出）。
```
computational literary / distant reading / stylometry / topic modeling /
digital humanities / cultural analytics / text mining /
machine learning literature / corpus-based / digital archive /
network analysis literature
```

**Step 3:** APIヒット論文のタイトルを全件確認し、DH実践論文・メタ議論・言及のみの3種に分類。PMLAについては抄録も確認（20本）。

**Step 4:** §7で既処理の`ci_footnotes.tsv`（8,940行）に対してDHキーワードを単語境界マッチ（正規表現`\b`）で再スキャン。

**Step 5:** APIの`biblio`フィールドから巻号を取得し、DHヒット論文の号集中を確認（特集号効果の検証）。

⚠️ Step 2の値は上限値であり採用率ではない（#32参照）。

### 確定した数値

#### Critical Inquiry（PDF直接スキャン・最高精度）

| 対象 | 期間 | 総件数 | DH関連論文 | 比率 |
|---|---|---|---|---|
| ci_footnotes単語境界マッチ | 2019–2025 | 254本 | **7本** | **2.8%** |
| oa_ci_works タイトルスキャン | 1974–2025 | 1,220本 | 4本 | 0.3% |

DH関連語が確認されたファイル（7本）: Bode 2023、Franta & Silver 2024、Geoghegan 2025、Lee 2025、Liu 2025、Parisi 2022、Parker 2025。2022年以降に集中（5/7本が2022–2025）。

OAタイトルスキャンで確認されたDH関連論文（4本）:
- 2019: Computational Literary Studies: Participant Forum Responses, Day 2 → **批判的フォーラム**
- 2019: The Computational Case against Computational Literary Studies → **DHへの批判**
- 2021: Data as Symbolic Form: Datafication and the Imaginary Media of W. E. B. Du Bois
- 2021: Artificial Antisemitism: Critical Theory in the Age of Datafication

⚠️ 2019年の2本はDHを採用した論文ではなく批判的に検討したフォーラム論文。CIはDHの実践の場ではなく、DHという現象を批評言説の俎上に乗せた場所として機能している。

#### PMLA：特集号効果の確認（号数データで論証済み）

| 年 | 集中号 | 特集テーマ | 件数 |
|---|---|---|---|
| 2016 | Vol.131 No.2 | Ecological Digital Humanities | 7/9件 |
| 2020 | Vol.135 No.1 | DHと多様性・人種 | 8/9件 |
| 2025 | — | Public Humanities（計算論的DHではない） | 9件 |
| 2021–2022 | — | 表紙・目次等のパレテキスト | 7件 |

**抄録確認（20本）に基づくPMLA DH論文の内部分類（2016–2022）:**

| 分類 | 件数 |
|---|---|
| DHを方法として使用（**実践**） | **3本** |
| DHを職能・制度として論じる（メタ議論） | 12本 |
| 言及・書評・返答 | 5本 |

**2016–2022のPMLA「digital humanities」ヒット20本のうち、DHを分析方法として使用した論文は3本（15%）。**

#### ELH・Novel

- **ELH 2016–2024:** DH実践論文1–2本（Extreme Reading: Josephine Miles [2019]; Data as Poetry in Cowper [2020]）。2025年の急増は特集号効果。
- **Novel 2016–2025:** DH方法採用論文はほぼ確認されず（≈0本）。distant reading等は議論の参照項として言及のみ。

#### DH専門誌との比較（比較基準）

| ジャーナル | 年平均 |
|---|---|
| DSH（DH専門誌） | 95本 |
| Cultural Analytics（DH文学研究専門誌） | 21本 |
| PMLA　DH実践論文 | 推定0.3–0.5本 |
| ELH　DH実践論文 | 推定0.1–0.2本 |
| Novel　DH実践論文 | ≈0本 |

### 確定した知見（論文に使用可）

英文学の主要ジャーナルにおけるDH関連論文の分析は、「浸透」ではなく「間欠的・制度的出現」という構造を示す。PMLAでは2016年（Vol.131 No.2、エコロジカルDH特集）・2020年（Vol.135 No.1、DHと多様性特集）にDH関連論文の集中が確認されるが、これらは特集号という編集的決定による出現であり、通常号でDHを方法として採用した論文は2016–2022年の検討範囲で3本程度にとどまる。Critical Inquiryにおいても同様の傾向が確認され、2019年の集中はComputational Literary Studiesへの批判的フォーラムという形式をとっており、方法の採用ではなく批評的検討の対象としてDHが登場している（2019–2025年のPDF直接スキャンでDH関連論文は254本中7本、2.8%）。Novelにおいてはdistant readingやcultural analyticsを議論の参照項として言及する論文は複数確認されるが、方法として採用した論文はほぼ確認されない。これに対しDH専門誌のCultural Analyticsは同期間に212本、DSHは952本を収録しており、主要文学誌との量的乖離は歴然としている。本研究は、DHが英文学研究において依然として周縁的な方法論にとどまる状況への介入として位置づけられる。

---

## Dissertation Progress（2026-04-06）

### 章構成と執筆状況

| 章 | タイトル | 状態 | ファイル |
|---|---|---|---|
| 序章 | 問いと方法 | 未着手（§8の知見を文脈化段落として使用予定） | — |
| 第1章 | 母集団と正典の構造的格差 | **草稿完成 v5** | `chapter1_v5.docx` |
| 第2章 | The Hollow Canon | **草稿完成 v4** | `chapter2_v4.docx` |
| 第3章 | Shadow Canonと排除の論理 | 未着手（属性分析が前提） | — |
| 第4章 | 批評言説と引用経済 | 未着手（HathiTrust待ち） | — |
| 結論 | — | 未着手 | — |

☑ 1・2章（§1–3）：方法論、34,789件の母集団構築・2軸構造の実証・hollow canon 24件の特定と制度論的解釈
☑ §8：英文学主要誌におけるDH受容状況の定量的文脈化（序章・第4章用）
☐ 3・4章：HathiTrust時系列分析待ち・shadow canon属性分析・CI言説分析本格化

### Student Survey Evidence（補完的定性証拠）

| 調査 | n | 主要発見 |
|---|---|---|
| Survey 1 | 79（人文社会系主体） | 美的評価と制度的配置の逆転：D(London/Call of Wild)が文学性最高(3.58)だがC(Ishiguro/Remains of Day)が最もアカデミックな配置（大学教材31+学術論文22=53名） |
| Survey 2 | 52（工学系主体） | 選択基準第1位「科学技術との関係」(32名)。hollow canon作品は一件も選ばれず |

Survey 1 サンプル詳細:
- Sample A: Tarzan of the Apes（hollow canon）
- Sample B: Heart of Darkness
- Sample C: The Remains of the Day（Ishiguro）→ 大学教材31・学術論文22・図書館15・空港書店11
- Sample D: The Call of the Wild（hollow canon）→ 文学性評価3.58（最高）

Survey 2 上位選択作品: Frankenstein(31)、The Time Machine(31)、Never Let Me Go(29)

---

## Scripts（全セッション）

| スクリプト | 場所 | 機能 |
|---|---|---|
| `build_population_from_dump.py` | scripts/ | OLダンプから母集団構築（3-pass） |
| `build_author_lookup.py` | scripts/ | OL Authorsダンプから著者名辞書構築 |
| `match_phd_corpus_v2.py` | scripts/ | phd_corpus v2マッチング |
| `fetch_oclc_from_dump.py` | scripts/ | OCLCダンプ抽出 |
| `build_edition_counts.py` | scripts/ | Editionsダンプからedition_count集計 |
| `ci_extract_citations.py` | scripts/ | CI PDF→テキスト・脚注・概念抽出 |
| `ci_discourse_analysis.py` | scripts/ | CI集計・著者頻度・概念頻度 |
| `temporal_citation_analysis.py` | scripts/ | OAスナップショットからcanonicalのcounts_by_year抽出 |
| `fix_titles.py` | scripts/ | title_normクリーニング + 6件JSTOR rescan（v3） |
| `jstor_rescan_extra29.py` | scripts/ | extra 30件のJSTORスキャン（v3） |
| `oa_rescan_extra30.py` | scripts/ | extra 30件のOpenAlexスキャン（v3） |

---

## Release History

| Release ID | Date | Key Artifact | Notes |
|---|---|---|---|
| population-v1 | 2026-02-22 | `ol_works_final_population.tsv` (4,833) | Initial filtered population (pilot) |
| population-dump-v1 | 2026-03-09 | `ol_dump_population_fiction_2026-02-28.tsv` (34,789) | **current baseline** |
| citations-v1 | 2026-03-27 | `jstor_mentions.tsv` + `openalex_snapshot_mentions.tsv` | Both citation indicators complete |
| enrichment-v2 | 2026-03-28 | `ol_edition_counts.tsv` + `htrc_ol_dump_match_summary_v2.tsv` | Edition count追加; HTRC v2（41→63件） |
| analysis-6b-v2 | 2026-03-28 | `multi_signal_merged.tsv` + `spearman_matrix.tsv` | §6b完了（4指標・2軸構造確定） |
| stage7-phase1-v1 | 2026-04-02 | `ci_articles.tsv` + `ci_footnotes.tsv` + `oa_ci_works_v2.tsv` + `temporal_citations_api.tsv` + `shadow_canon_final.tsv` | Stage 7 Phase 1完了 |
| canonical-v3 | 2026-04-05 | `jstor_mentions.tsv`（104件）+ `jstor_extra29.tsv` + `extra_canonical_editions.tsv` + `oa_extra30.tsv` | v3 matching完了・数値確定 |
| stage8-dh-reception-v1 | 2026-04-06 | （派生ファイルなし・API照会のみ） | §8 DH受容分析完了；CI脚注精度検証完了 |

---

## Known Limitations (Cumulative)

1. `first_publish_year` mis-registration ~2.5% (unfilterable)
2. Non-fiction residual contamination ~1% post-filter
3. OL search bias — pilot study only; dump-based main study is unbiased
4. OCLC identifier audit covers 100 works only
5. HathiTrust match covers 18.0% of population
6. WorldCat holdingsCount structurally unavailable
7. WorldCat Discovery API: institutional contract barrier
8. **phd_corpus 8件が永続的未解決**（旧44件のうち6件はv3 mainに、30件はv3 extraに回収）
9. htrc omnibus volumes inflate htid_count
10. FAST ID label resolution blocked by network policy
11. OL dump coverage: works not registered in OL treated as non-existent
12. OL dump language field absent at Work level
13. **JSTOR abstract field is 0.0% populated** → title-co-occurrence only
14. JSTOR title_norm deduplication reduced index to 30,962 works
15. Works with unknown author (355 works, 1.0%) receive title-only JSTOR matching
16. OpenAlex Concepts/Topics API cannot identify individual novels
17. **work_key accuracy verified for canonical 104 works only**
18. **JSTOR mention counts for non-canonical works are unrevised**
19. **Shadow canon list contains works outside 1880–1950 scope** — year filter not re-applied during extraction
20. **OpenAlex snapshot scan uses title-only matching** (abstract disabled)
21. **FORCE_MAP 3件のwork_keyが誤った作品を指している**（jstor値は修正済み、edition_count/wikidataシグナルは無効）
22. **Wikidata sitelink coverage: canonical 60/98件のみ** — §6b分析から除外
23. **HTRCタイトル照合v2:** OCLC世代不一致により初回41件→v2補完後63件。2件は手動除外
24. **Internet Archive download統計は公開APIから取得不可**
25. **edition_countはOLダンプ収録版のみカウント** — 過小推定の可能性あり
26. **htid ↔ edition相関の著作権切断バイアス:** 全体ρ=0.257、1923年以前サブセットρ=0.374（両値を論文で報告すること）
27. **OA APIのcounts_by_yearは直近10年分のみ** — 歴史的時系列はHathiTrustカプセルが必要（期限: 2026年9月）
28. **`ci_articles.tsv`の`title_extracted`フィールドは全254件空** — CI×OA交差検証にはOA API直接検索を使うこと
29. **oa_ci_works_v2.tsv の2023年=1件・2024年=0件は欠落** — スナップショットの分散によるもの
30. **Shadow canon属性バイアス分析は未実施** — 「ジェンダー・人種バイアス」の主張には著者属性の系統的分析が必要（第3章執筆前に対処すること）
31. **v3 extra 30件はHTRC照合不可**（HTRCメタデータにタイトル列なし、OCLC番号も不在）。edition_countはOL API経由（2026-04）でダンプ由来値と出典が異なる
32. **§8 DHキーワード検索はOA APIの全文検索に依存しており、実践論文と言及・批判論文を自動区別できない。** 報告値はすべて上限値として扱うこと。CIのみPDF直接スキャンにより精度が担保されている
33. **§8のELH・Novel・Modern Philologyの採用率はタイトル目視・定性的推定に基づく。** 抄録の体系的確認・分類器による判定は未実施
34. **§8でModern Philologyの詳細スキャンは未実施。** ISSN 0026-7937はThe Modern Language Review（別誌）であり無効。正しいISSNは0026-8232
35. **§8の「DH実践論文」判定はタイトル・抄録の目視分類に依存。** 操作的定義（方法として採用 vs 言及・批判）の境界は必ずしも明確でなく、主観的判断を含む。論文では判定根拠を明示すること
36. **ci_footnotes.tsv精度検証はPDFディレクトリのパス不一致により完全ではない。** 248/254件の一致を確認。Gavin 2018は対象期間外のため影響なし。残6件の所在は未確認

---

## References（第1・2章で使用確定）

- Bourdieu, P. (1993). *The field of cultural production* (R. Johnson, Ed.). Polity Press.
- Guillory, J. (1993). *Cultural capital*. University of Chicago Press.
- Huyssen, A. (1986). *After the great divide*. Indiana University Press.
- McGrath, L., Higgins, D., & Hintze, A. (2018). Measuring modernist novelty. *Journal of Cultural Analytics*, 3(1). https://doi.org/10.22148/16.027
- Moretti, F. (2013). *Distant reading*. Verso.
- Rainey, L. (1998). *Institutions of modernism*. Yale University Press.
- Rawlings, M. K. (1938). *The Yearling*. Charles Scribner's Sons.