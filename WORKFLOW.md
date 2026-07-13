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

---

## 研究目的の明確化（2026-05-23 追記）

### 本研究が描くもの

本研究の目的は**複数の経路から見た作品評価の地形図（topography）を描くこと**である。学術的引用・文化的流通・読者受容という異なる回路がどのように交差し、あるいは独立しているかを実証的に示す。

**本研究は以下を主目的としない：**
- ジェンダー・人種・階級の格差や偏りの告発
- canonical vs non-canonicalの二項対立的な格差の批判
- 特定の属性グループへの不公正の証明

著者属性（ジェンダー・国籍・文学運動への帰属）はWikidata由来で取得予定だが、これは地形図の一要素として位置づけるものであり、「偏りの告発」のためではない。分析結果の解釈において、属性分布から規範的判断を導くことは本研究の射程外である。

この方針はWORKFLOW.md全体を通じて一貫して適用すること。特に§6aのShadow Canon分析・§6bの多指標分析における記述に注意。

---

## 各DBの現状と品質評価（2026-05-23 正直な評価）

WORKFLOW.md各所で「完了」と記録されているDBスキャンは、**第1次スキャンが完了した**という意味であり、**データ品質として十分である**という意味ではない。以下に各DBの正直な現状を記録する。

### multi_signal_merged.tsv について

`derived/multi_signal_merged.tsv`（34,789件）は現時点で信頼できない統合ファイルである。以下の理由から、分析に直接使用してはならない。

- JSTOR列：タイトル共起マッチング第1次スキャンの値。過小評価が確定している。
- OpenAlex列：title-only matchingの値。同様に過小評価。
- HathiTrust列：`htrc_ol_dump_match_summary_v2`（旧HTRC分類フィルタ版）を使用。最新の`ht_api_full.tsv`とは別物。

**このファイルを使った§6bのSpearman相関行列（ρ=0.293等）は参考値に過ぎない。** 全DBの再スキャン・照合完了後に`canon_integrated.tsv`として再構築する。

---

### DB別の正直な品質評価

#### JSTOR（`derived/jstor_mentions.tsv`）

| 項目 | 状態 |
|---|---|
| スキャン件数 | 30,973件（母集団の89%） |
| 照合方式 | タイトル共起マッチング（タイトルのみ） |
| 品質問題 | **著者名を照合条件に含めていない。同タイトル別著者の論文を誤カウントする可能性がある。** |
| 過小評価の確認 | C3グループ10件中2件（Moon and Sixpence・The Yearling）に実際はJSTOR論文が存在することを確認済み（`jstor_semantic_findings.md`参照） |
| hollow canon への影響 | 「24件がJSTOR=0」という数字は過大評価の可能性がある。Moon and SixpenceとThe Yearlingは少なくとも1件以上の論文が存在する。 |
| 必要な対応 | canonical 104件についてLLMセマンティック照合で再スキャン（未実施） |
| 費用見積もり | Claude Haiku で約200〜300円 |

⚠️ **論文でJSTOR値を使用する際は「第1次スキャン値・過小評価の可能性あり」と明記すること。**

#### OpenAlex（`derived/openalex_snapshot_mentions.tsv`）

| 項目 | 状態 |
|---|---|
| スキャン件数 | 33,978件（母集団の97%） |
| 照合方式 | title-only matching（abstractは無効化） |
| 品質問題 | **著者名・出版年を照合条件に含めていない。** The Yearlingで3,183件という明らかな誤カウントが確認済み（"yearling"が動物科学論文にヒット）。 |
| 必要な対応 | canonical 104件についてLLMによる意味的照合で再スキャン |
| 費用見積もり | Claude Haiku で約200〜300円 |

⚠️ **OpenAlex値も第1次スキャン値であり、非規範的タイトル（一般語と重複する単語を含む）は誤カウントが多い。**

#### HathiTrust

| ファイル | 内容 | 品質 |
|---|---|---|
| `derived/htrc_ol_dump_match_summary_v2.tsv` | 旧HTRC分類フィルタ版（6,286件） | **使用非推奨**。fiction分類フィルタで主要正典作品が除外されている。 |
| `derived/ht_api_full.tsv` | OCLC経由Bibliographic API（30,101件） | **現時点の最良値**だが、Ulysses・Great Gatsby等の主要作品が欠落。 |
| HathiFilesタイトル照合 | 未実施 | Phase 2・3完了後に補完予定 |

**multi_signal_merged.tsvのHT列はhtrc版であり、ht_api版ではない。**

#### Goodreads（未照合）

データは取得済み（UCSD・MajinBook）だが照合スクリプト未作成。読者受容軸の値は全件NaN。

#### Wikidata

canonical 82件のQIDは確定（F1=0.969）。non-canonical全件は未実施（研究費取得後）。著者属性（ジェンダー・国籍・文学運動）はcanonical 82件についてパイロット取得済みだが、全件適用は未実施。

#### Open Library（edition_count）

`derived/ol_edition_counts.tsv`（34,789件）はOLダンプから直接集計しており、**最も信頼性が高い指標**。ただしFORCE_MAPバグ3件（Dracula・Good Soldier・Prisoner of Zenda）のedition_countは別著者作品の値のため無効。

---

### 優先すべき照合作業（2026-05-23時点）

以下を優先度順に実施する。費用・難易度・研究への貢献度を考慮。

| 優先度 | タスク | 費用 | 状態 |
|---|---|---|---|
| 1 | Goodreads照合（UCSD→全34,789件） | 無料（LLM補完で~150円） | 未着手 |
| 2 | HathiTrust Phase 2（HathiFilesタイトル照合） | 無料 | 未着手 |
| 3 | JSTORセマンティック再スキャン（canonical 104件） | ~200円 | 未着手 |
| 4 | OpenAlexセマンティック再スキャン（canonical 104件） | ~200円 | 未着手 |
| 5 | canon_integrated.tsv 再構築（①〜④完了後） | 無料 | 未着手 |
| 6 | scope_flag実装（母集団ノイズ除去） | 無料 | 未着手 |
| 7 | Wikidata全件（non-canonical 34,685件） | 研究費取得後 | 未着手 |

---

### JSTORセマンティック検索の既知の修正事項（要反映）

`jstor_semantic_findings.md`（2026-05-03）に記録された知見：

**C3グループ（JSTOR=0・OpenAlex>0）10件中2件に実際はJSTOR論文が存在する：**

| 作品 | 確認された論文 | 現在の記録値 | 修正後 |
|---|---|---|---|
| The Moon and Sixpence / Maugham | "FANTASY AS NECESSITY: THE ROLE OF THE BIOGRAPHER IN 'THE MOON AND SIXPENCE'" 等2件 | jstor=0 | jstor≥2 |
| The Yearling / Rawlings | 関連論文あり（一般語"yearling"との混在に注意） | jstor=0 | 要個別確認 |

**hollow canonへの影響：**
現在「24件がJSTOR=0（hollow canon）」と記録されているが、Moon and Sixpenceは少なくとも2件の論文が確認されているため、正確なhollow canon件数は**最大22件**（Moon and Sixpenceを除外した場合）または23件（The Yearlingの確認次第）となる可能性がある。

**対応方針：**
JSTORセマンティック再スキャン（優先度3）でcanonical全104件を再確認し、hollow canon件数を確定させてから論文に使用すること。それまで「24件」という数字には⚠️注記を付すこと。

---

### The Four Vectors — 正直なStatus更新（2026-05-23）

| Vector | データ | 実際のStatus |
|---|---|---|
| 1. Attention economy | JSTOR + OpenAlex | 🔶 第1次スキャン完了・品質不十分。再スキャン必要 |
| 2. Conceptual terrain | CI PDFs（完了）+ HathiTrust（Phase 1完了） | 🔶 HT照合は部分的。Phase 2・3未実施 |
| 3. Pedagogical structures | phd_corpus (McGrath et al.) | ✅ canonical照合完了（104件確定） |
| 4. Evaluative practice | Goodreads（UCSD+MajinBook） | ❌ データ取得済み・照合未実施 |

**注：** WORKFLOW.md冒頭の四ベクター表の「✅ 完了」表記はVector 1・2について正確ではない。本セクションの評価を参照すること。

*最終更新: 2026-05-23*

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


## Stage 3d: Bibliographic Entity Resolution Benchmark Overview — 2026-04-21

### Purpose

本research pipelineが6つの異なるDBを横断的に照合する際に直面する失敗パターンを体系的に分析し、次のエンリッチメント段階（Stage 4-5）における課題を特定する。

### 確定した四類型

#### 類型I：識別子多義性
- **内容：** 1作品が複数のOCLCを持ち、どの版の識別子が正解かを自動判定できない
- **件数：** 13,862件（全体の39.8%）
- **深刻度：** 高
- **根本原因：** 初版・普及版・現代版・翻訳版でOCLCが別々に発行されるため、異なる世代のOCLCを参照することにより照合が失敗

**代表例：**
| 作品 | OCLC件数 |
|---|---|
| Treasure Island | 281 |
| Alice's Adventures in Wonderland | 214 |
| The Great Gatsby | 184 |
| The Wonderful Wizard of Oz | 161 |

#### 類型II：エンティティ混同
- **内容：** 同タイトル別著者、著者名表記ゆれによる誤照合
- **件数：** 著者名表記ゆれ（姓,名形式と名姓形式の混在）7,553件（21.7%）
- **深刻度：** 高
- **代表例：**
  - 「The Good Soldier」→ Ford Madox Ford（1915）とJaroslav Hašek作品が混在
  - 「Conrad, Joseph」と「Joseph Conrad」が別著者として扱われる
  - Wikidata検索で「Alas!」→ Alaska州（Q797）が最上位に返る

#### 類型III：収録構造限界
- **内容：** DBのフィルタ・著作権制約・スキャン方式によって照合自体が構造的に不可能
- **深刻度：** 中
- **重要発見：** UlyssesはOpen Library側に正常収録（/works/OL35695219W）されているが、htrc-fiction_metadata.csv内に「James Joyce」かつタイトル「Ulysses」の行がゼロ件。これはHTRCのfiction分類フィルタによる構造的除外。

**C3グループ（JSTOR=0かつOpenAlex>0）の10件：**

| 作品 | JSTOR | OpenAlex |
|---|---|---|
| White Fang | 0 | 29 |
| The Moon and Sixpence | 0 | 3 |
| The Yearling | 0 | 3 |
| Tarzan of the Apes | 0 | 2 |
| Senator North | 0 | 1 |

#### 類型IV：内部重複（新発見）
- **内容：** Open Library内で同一著作が複数のwork_keyに分裂して登録されている
- **件数：** 1,829件（全体の5.3%）
- **深刻度：** 高

**代表例：**
| タイトル | 著者 | 重複work_key数 |
|---|---|---|
| Ivanhoe | Scott, Walter | 15 |
| The Perfect Tribute | Mary Raymond Shipman Andrews | 14 |
| In the Boyhood of Lincoln | Hezekiah Butterworth | 9 |
| Heidi | Spyri | 8 |

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

### 4e-ext: Wikidata Entity Resolution Benchmark — Canonical 82件・F1=0.969

#### 背景

Wikidata照合は単なるメタデータマッチングではなく、著者名表記ゆれ・同タイトル別著作・Wikidata内部の複数エンティティ混在など複雑な失敗パターンに対処するため、LLM多段階推論エージェントの評価が必要だった。

#### 実装：5段階の多段階推論

| ステップ | 処理 | 解決する失敗パターン |
|---|---|---|
| 1 | 著者名正規化（姓,名 → 名姓） | Ethan Frome・Custom of the Country等の著者QID取得失敗 |
| 2 | 著者QID取得（3戦略：完全一致→姓+作家フィルタ→LLM別名生成） | Emma Orczy=Baroness Orczy等のペンネーム |
| 3 | SPARQL著作リスト照会（上限100件） | 多作著者の著作がリスト外に押し出される問題 |
| 4 | LLM照合（出版年を文脈情報として渡す） | Peter Pan戯曲vs文学エンティティの誤マッチ |
| 5 | タイトル短縮フォールバック | サブタイトル付きタイトルのSPARQL不一致 |

#### 結果（canonical 82件評価）

**混同行列（正例82件 + 負例48件・全130件）：**

| | 予測: QID | 予測: NO_MATCH |
|---|---|---|
| 正解: QID | TP=78 | FN=4 |
| 正解: NO_MATCH | FP=1 | TN=47 |

**指標：**

| 指標 | 値 |
|---|---|
| Precision | 0.987 |
| Recall | 0.951 |
| **F1** | **0.969** |
| ベースライン（fuzzy matching F1=0.516）比改善幅 | **+0.453** |

#### 難易度別性能

| 層 | sitelink数 | 正解率 |
|---|---|---|
| Easy | ≥50 | 11/11（100%） |
| Medium | 5-49 | 35/36（97.2%） |
| Hard | <5 | 32/35（91.4%） |

#### 残り失敗5件（Wikidata側のデータ品質問題）

全5件がエージェント改善では解決不可：

| 作品 | 原因 | 例 |
|---|---|---|
| Kim（Kipling） | 同著者・同タイトルの2エンティティ混在 | written work vs literary work |
| At Fault（Chopin） | Wikidataにラベルなし登録 | Q131573518（ラベル欠落） |
| The Octopus | タイトル長すぎ・著作リスト未収録 | "The octopus, a story of California" |
| Peter Pan | 戯曲・文学作品エンティティ混在 | Q19032697 vs Q3435337 |
| The Capsina | 別著者の同名作品を返却 | FP例 |

#### OL sitelink品質問題の発見

The House of MirthのOL sitelinkはQ131825212（1995年Project Gutenberg版・版レベルエンティティ）を指しており、正しい著作物レベル（FRBR Work）Q6474536とは異なっていた。エージェント予測が正解で、OL sitelink自体の品質問題が確認された。→ OL sitelinkを無条件にgold標準として使用できないことを示唆。

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
---

## Stage 4g: HathiTrust 所蔵数取得 — Phase 1・2完了 2026-05-25

### HathiTrustとは何か

2008年設立の北米大学図書館コンソーシアム（200機関以上参加）によるデジタルアーカイブ。コレクションの大部分はGoogleブックス大規模スキャンプロジェクト（2004年〜）でデジタル化されたもの。`htid_count`（所蔵ボリューム数）は「米国トップ大学図書館の蔵書のうちGoogleにスキャンされた分」を主に反映する。htid_countが低い・ゼロの作品は制度的不可視化の証拠として読め、文化的流通軸の指標となる。

**著作権構造：** Bibliographic API・HathiFilesともに著作権に関係なくメタデータを返す。フルテキスト分析はHTRC Data Capsule経由（申請者はアカウント・プロジェクト保有済み）。

---

### ローカルデータ

```
/mnt/d/hathitrust/hathi_full_20260501.txt.gz
  サイズ: 1.2GB（圧縮）
  総件数: 19,394,212件
  取得日: 2026-05-22
```

**HathiFiles列構造（0-indexed・確認済み）：**

| 列 | フィールド | 内容 |
|---|---|---|
| 0 | htid | HathiTrustボリュームID |
| 1 | access | allow/deny |
| 2 | rights | pd/ic/pdus等 |
| 7 | oclc_num | OCLC番号 |
| 11 | title | タイトル（著者・副題含む） |
| 16 | pub_date | 出版年 |
| 18 | language | 言語コード（eng等） |
| 23/24 | digitization_agent | google/ia/umich等 |
| -1（最終列） | author | 著者名 |

⚠️ タイトル列（col 11）は`Ulysses / James Joyce ; prefaced by...`のようにスラッシュ以降に著者・副編者情報が入ることがある。正規化時は`/`・`:`・`;`で分割して最初の部分のみ使用する。

---

### 照合パイプライン（2段階）

#### Phase 1: OCLC経由Bibliographic API照合（完了 2026-05-22）

**スクリプト：** `scripts/fetch_hathitrust_api.py`（チェックポイント再開対応）

```
API: https://catalog.hathitrust.org/api/volumes/brief/oclc/{oclc}.json
対象: OCLCあり30,101件
sleep: 0.5秒/件
実行時間: 約4時間
```

**結果：**

| 指標 | 値 |
|---|---|
| スキャン対象 | 30,101件 |
| htid_count > 0 | 18,923件（62.9%） |
| htid_count = 0 | 11,178件（37.1%） |

**出力：** `derived/ht_api_full.tsv`

⚠️ canonical中央値=1・最大=11は過小評価。Phase 2で大幅改善。
⚠️ htid_count最大値1,516はThe New Yorker（雑誌ノイズ）。

#### Phase 2: HathiFilesタイトル+著者照合（完了 2026-05-25）

**スクリプト：** `scripts/match_hathifiles_title.py`

**対象：**
- Phase 1でhtid=0だった11,178件
- OCLCなし（ht_api_full.tsv未収録）4,688件
- 合計15,866件→scope_flag除外後15,660件

**処理フロー：**

```
OL母集団インデックス構築（タイトル正規化）
  ↓
HathiFilesを1行ずつストリーム処理（19,394,212行・約15分）
  ↓
言語フィルタ（lang == 'eng'）
年フィルタ（pub_year >= first_publish_year - 5）
  ← 後刷り版が多いため「出版年以降」のみ許容
タイトル正規化照合
  ↓
著者姓フィルタ（どちらかが不明ならスキップしない）
  ↓
ヒット → htid_count累積カウント
```

**タイトル正規化：**
```python
t = t.split(':')[0].split(';')[0].split('/')[0]  # サブタイトル・著者除去
t = t.lower()
t = unicodedata.normalize('NFKD', t)             # アクセント正規化
t = re.sub(r'[^\w\s]', ' ', t)
t = re.sub(r'\b(the|a|an)\b', ' ', t)            # 冠詞除去
t = re.sub(r'\s+', ' ', t).strip()
```

**結果：**

| 指標 | 値 |
|---|---|
| 処理行数 | 19,394,212行 |
| ヒット作品数 | 4,173件 |
| canonical新規ヒット | 22件 |

**canonical新規ヒット主要作品：**
Tess（htid=39）・The Portrait of a Lady（21）・Robert Elsmere（20）・Jungle Book（21）・Portrait of the Artist（14）・Sister Carrie（13）・Ethan Frome（12）・Jude（17）・Heart of Darkness・Turn of the Screw・The Awakening・Ulysses 等

**出力：** `derived/ht_hathifiles_match.tsv`（4,173件）

---

### Phase 1+2 マージ（完了 2026-05-25）

**スクリプト：** インラインPython（再実行可能）

**優先順位：** OCLC照合（Phase 1）> タイトル照合（Phase 2）

**結果（ht_final.tsv・34,789件）：**

| 指標 | 件数 | 比率 |
|---|---|---|
| OCLC照合ヒット | 18,923 | 54.4% |
| タイトル照合ヒット | 4,173 | 12.0% |
| うち新規（OCLC外） | 1,697 | 4.9% |
| ゼロ（所蔵なし） | 11,693 | 33.6% |

**canonical最終結果（n=98）：**

| 指標 | 値 |
|---|---|
| htid > 0 | **91件（92.9%）** |
| htid = 0 | 7件 |

**依然ゼロの7件と理由：**

| 作品 | 理由 |
|---|---|
| The Good Soldier / Jaroslav Hašek | FORCE_MAPバグ（正しい著者はFord Madox Ford） |
| The Prisoner of Zenda / George F. Wear | FORCE_MAPバグ（正しい著者はAnthony Hope） |
| The Innocents / Alfred Machard | FORCE_MAPバグ |
| Looking Backward / Bellamy | HathiFilesに所蔵なし（確認済み） |
| The North Star / Henry-Ruffin | マイナー作品・所蔵なし |
| The Golden Cage / Bromige | マイナー作品・所蔵なし |
| The Damascus Road / Parini | 1999年出版・スコープ外 |

FORCE_MAPバグ3件を除くと**実質4件のみが構造的限界**。

**出力：** `derived/ht_final.tsv`（34,789件）

---

### 既知の問題・注意事項

| 問題 | 状態 |
|---|---|
| FORCE_MAPバグ3件 | 未修正。work_key修正後に当該3件のみ再実行で解決 |
| The New Yorker等の雑誌ノイズ | ht_api_full.tsvに混入。scope_flag実装後に除外 |
| タイトル照合の誤ヒット可能性 | 著者フィルタで軽減済みだが一部残存の可能性あり |
| Looking Backward | HathiFilesにBellamy版の所蔵が確認できない（構造的限界） |

---

### HTRC Data Capsuleとの関係

申請者はHTRC Data Capsuleのアカウント・プロジェクトを保有済み。フルテキスト分析が必要な場合はCapsule内で実施可能。ht_final.tsvのsample_htidsをWorkset構築に使用予定。

**Capsuleで実施予定のタスク（Stage 7 Phase 2・期限2026年9月）：**
- PMLA 1950–2025のdecade別概念語・理論家名頻度分析
- フルテキストはCapsule内でのみ処理・aggregate outputのみ外部持ち出し可

---

### Release記録

| Release ID | Date | Key Artifact |
|---|---|---|
| ht-hathifiles-v1 | 2026-05-22 | `hathi_full_20260501.txt.gz`（/mnt/d/hathitrust/） |
| ht-api-full-v1 | 2026-05-22 | `ht_api_full.tsv`（30,101件・OCLC経由） |
| ht-hathifiles-match-v1 | 2026-05-25 | `ht_hathifiles_match.tsv`（4,173件・タイトル照合） |
| ht-final-v1 | 2026-05-25 | `ht_final.tsv`（34,789件・Phase 1+2マージ） |

#### 4g-ext: HathiTrust Entity Resolution の構造的課題（ベンチマーク確認）

**目的：** OCLC照合で失敗した1923年以前のcanonical作品18件を対象に、タイトル検索+LLMで再挑戦し、OCLCに依存しない照合の限界を検証。

**重要な発見：** 照合失敗の主因はLLMの性能ではなくHTRCのfiction分類フィルタによる構造的除外であることが判明。

**具体例：**

```
=== exact-ish James Joyce + Ulysses ===
hit rows = 0  ← Ulysses はHTRC対象外

=== title contains Ulysses AND author contains Joyce ===
hit rows = 0  ← Heart of Darkness も同様
```

Ulysses・Heart of Darkness・Dubliners・As I Lay Dyingは`htrc-fiction_metadata.csv`（prob80precise≥0.5フィルタ適用済み）に存在しない。これはHTRCのfiction判定アルゴリズムが主要正典作品を構造的に除外しているという問題であり、LLMの再照合では解決できない。

**結果：** LLM照合成功 2/16件（New Grub Street、The North Star）、失敗 14/16件。失敗の大半はHTRC側の収録除外が原因。

**意義：** 「識別子照合の失敗」と「データ収録の構造的問題」を区別する本研究の診断枠組みの重要性を実証。

---

## Stage 4h: Goodreads 読者受容データ取得 — Phase 1完了 2026-05-24

### 研究上の位置づけ

Goodreadsの評価数・レビュー数・★別内訳は「読者受容軸」の指標として機能し、学術的注目軸（JSTOR・OpenAlex）・文化的流通軸（OL版数・HathiTrust）とは独立した第3の正典化ベクターを構成する。本研究の目的は複数の経路から見た作品評価の地形図を描くことであり、canonical・non-canonicalを含む34,789件全体の読者受容データが必要。

---

### ローカルデータ（取得済み）

#### UCSD Book Graph（主力）

**出典：** Wan & McAuley (2018, RecSys) / Wan et al. (2019, ACL)
**収集時期：** 2017年末
**ライセンス：** 学術利用専用・再配布禁止

```
/mnt/d/goodreads/
  goodreads_book_works.json.gz       72MB  1,521,962件（works単位・主力）
  goodreads_books.json.gz             2GB  2,360,655件（edition単位・ISBN照合用）
  goodreads_book_authors.json.gz     18MB    829,524件（著者ID→著者名）
  goodreads_book_genres_initial.json.gz 24MB 2,360,655件（ジャンル情報）
取得日: 2026-05-23
```

**goodreads_book_works の主要フィールド（確認済み）：**

| フィールド | 内容 |
|---|---|
| `work_id` | Goodreads works ID（照合・結合キー） |
| `original_title` | タイトル |
| `original_publication_year` | 初版年 |
| `ratings_count` | 評価した人の総数 |
| `text_reviews_count` | レビューを書いた人の数 |
| `rating_dist` | `5:N\|4:N\|3:N\|2:N\|1:N\|total:N`形式 |
| `best_book_id` | 代表edition ID（著者照合に使用） |

⚠️ 2017年収集のため評価数は2017年時点の値。絶対値ではなく相対順位・構造分析に使用すること。Great Gatsby: ratings=2,852,789（2017年）→ 現在5,683,258（2025年）。

#### MajinBook（ジャンル補完用・最終的に不使用）

UCSDに著者情報が揃っていることが判明したためMajinBookは照合に使用しなかった。work_idが共通なのでジャンル情報だけ後から結合できる。

---

### インデックス構築（完了）

**スクリプト：** `scripts/build_goodreads_index.py`

4段階でUCSDデータを統合インデックスに変換する：

```
Step 1: goodreads_book_authors.json.gz → author_id → 著者姓
Step 2: goodreads_books.json.gz → book_id → [著者姓リスト]（2GB・数分）
Step 3: goodreads_book_genres_initial.json.gz → book_id → ジャンル
Step 4: goodreads_book_works.json.gz → work_id単位に統合
```

**出力：** `derived/goodreads_works_index_v2.tsv`（1,521,962件）

| 列 | 内容 |
|---|---|
| `work_id` | Goodreads works ID |
| `title` | タイトル |
| `year` | 初版年 |
| `ratings_count` | 評価数 |
| `text_reviews_count` | レビュー数 |
| `rating_dist` | ★別内訳 |
| `ratings_5〜1` | ★別件数（パース済み） |
| `author_last_names` | 著者姓リスト（`\|`区切り、UCSDデータ由来） |
| `genres` | ジャンルリスト（`\|`区切り、最大5件） |

---

### 照合パイプライン（完了）

**スクリプト：** `scripts/match_goodreads_ucsd.py`

#### 照合ロジック

```
入力: ol_dump_population_with_scope.tsv（34,789件）
      goodreads_works_index_v2.tsv（1,521,962件）

scope_flag == 'out_lang' → SKIP_LANG（非英語除外）

タイトル正規化（サブタイトル除去・冠詞除去・記号除去）
  → 候補0件 → NO_MATCH
  → 候補1件 → 著者確認
      一致 → UNIQUE
      不一致 → NO_MATCH_AUTH
  → 候補複数 → 年±10フィルタ → 著者フィルタ（必須）
      著者0件 → NO_MATCH_AUTH（誤照合防止・RATINGS_MAX_NOAUTHは廃止）
      著者1件 → YEAR_AUTH
      著者複数 → ratings最大 → RATINGS_MAX
        ※ edition>=10かつratings差10%以内 → LLM_PENDING

LLM_PENDING → Claude Haiku-4-5で候補選択
  プロンプト: 英語・数字のみ返答指定
  結果: 240件中96件照合成功・144件NO_MATCH
```

**著者確認の実装：**
- OL側：`author_name`からカンマ有無でfirst/lastを判定し著者姓を抽出
- UCSD側：`goodreads_books` → `author_id` → `goodreads_book_authors` → 著者姓
- MajinBook不使用・UCSD完結

#### scope_flag（母集団ノイズ除去）

`derived/ol_dump_population_with_scope.tsv`に`scope_flag`列を追加：

| 値 | 判定基準 | 件数 |
|---|---|---|
| `in_scope` | 分析対象 | 33,942件 |
| `out_lang` | タイトル非ASCIIかつenglish_fiction等なし、またはフランス語・スペイン語等の冠詞で始まるタイトル | 847件 |

⚠️ canonical作品の誤除外ゼロを確認済み。
⚠️ `La femme et le pantin`等ASCIIタイトルの一部外国語作品は`in_scope`のまま残る可能性あり（限界として受け入れる）。

---

### 照合結果（最終・2026-05-24確定）

**全件（n=33,942・out_lang除く）**

| match_type | 件数 | 比率 | 説明 |
|---|---|---|---|
| UNIQUE | 5,688 | 16.8% | タイトル一意・著者確認済み |
| YEAR_AUTH | 3,733 | 11.0% | 年+著者フィルタで1件に絞込 |
| RATINGS_MAX | 1,782 | 5.3% | 著者確認済み・ratings最大選択 |
| LLM | 96 | 0.3% | LLM判定（推定精度93%） |
| **照合成功計** | **11,299** | **33.3%** | |
| LLM_PENDING | 0 | — | 処理済み |
| NO_MATCH | 13,241 | 39.0% | UCSDに存在しない |
| NO_MATCH_AUTH | 9,402 | 27.7% | 別著者の同名作品のみ |
| SKIP_LANG | 847 | — | scope_flag除外 |

**canonical（n=98）**

| 指標 | 値 |
|---|---|
| 照合成功 | 79件（80.6%） |
| NO_MATCH（Goodreads未収録） | 7件 |
| NO_MATCH_AUTH（FORCE_MAPバグ等） | 9件 |

**canonical ratings上位（2017年値）：**

| 作品 | ratings | match_type |
|---|---|---|
| The Great Gatsby | 2,852,789 | UNIQUE |
| Nineteen Eighty-Four | 2,125,871 | RATINGS_MAX |
| Heart of Darkness | 315,808 | UNIQUE |
| The Sun Also Rises | 308,432 | UNIQUE |
| Mrs. Dalloway | 163,735 | UNIQUE |

---

### カバレッジ33.3%の解釈

33.3%は低く見えるが、以下の理由で研究目的には十分：

1. **OL母集団の大半はマイナー作品**（edition数1〜2件）→ Goodreadsに登録なし → NO_MATCHが正しい結果
2. **canonical 80.6%は照合済み** → 正典分析の核心はカバー
3. **NO_MATCHそのものが情報** → 「Goodreadsに評価がない」という読者受容の不在は文化的地形図の一部

---

### 精度検証

**LLM照合96件のサンプル確認（30件目視）：**

| 種別 | 件数 | 精度 |
|---|---|---|
| 正しい照合 | 28/30 | 93% |
| 誤照合 | 2/30 | 7% |

誤照合2件の特徴：ratings極小（6件・395件）→ 分析上の影響軽微。

**RATINGS_MAX 1,782件：** 著者姓フィルタ済み・ratings最大選択。RATINGS_MAX_NOAUTHは著者不一致のため廃止（誤照合防止）。

---

### 取得する指標

| 指標 | フィールド | 意味 |
|---|---|---|
| `n_ratings` | `ratings_count` | 評価した人の総数（読者受容の規模） |
| `n_reviews` | `text_reviews_count` | レビューを書いた人の数 |
| `ratings_5` | `rating_dist`からパース | ★5件数（熱狂的支持者の数） |
| `log_ratings` | `log10(n_ratings+1)` | 派生列・可視化用 |

⚠️ `average_rating`（平均評価）は使用しない。意味が薄くノイズが多い。

---

### 出力ファイル

| ファイル | 件数 | 内容 |
|---|---|---|
| `derived/goodreads_works_index_v2.tsv` | 1,521,962 | UCSDインデックス（著者・ジャンル付き） |
| `derived/goodreads_ucsd_match.tsv` | 34,789 | OL母集団×Goodreads照合結果 |
| `derived/ol_dump_population_with_scope.tsv` | 34,789 | scope_flag付き母集団 |
| `derived/goodreads_llm_pending_results.json` | 240 | LLM判定結果（96件成功・144件NO_MATCH） |

---

### 今後の課題

| タスク | 優先度 | 内容 |
|---|---|---|
| MajinBookジャンル結合 | 低 | work_idでgenresを追加 |
| ISBN照合補完 | 低 | goodreads_books.json.gzのISBNでNO_MATCHを追加照合 |
| scope_flag拡張 | 中 | Also sprach Zarathustra等の哲学書・非フィクションへの対応 |

---

### Release記録

| Release ID | Date | Key Artifact |
|---|---|---|
| goodreads-index-v1 | 2026-05-24 | `goodreads_works_index_v2.tsv`（1,521,962件・著者・ジャンル付き） |
| goodreads-match-v1 | 2026-05-24 | `goodreads_ucsd_match.tsv`（照合成功11,299件・精度検証済み） |
| scope-flag-v1 | 2026-05-24 | `ol_dump_population_with_scope.tsv`（out_lang 847件除外） |



## Stage 4i: canon_integrated.tsv 構築 — 完了 2026-05-28

### 概要

6DBのデータを1ファイルに統合した分析用マスターファイル。

**出力:** `derived/canon_integrated.tsv`（34,789件）

**列構成:**

| 列 | 内容 | 出典 |
|---|---|---|
| work_key / title / author_name / first_publish_year | 書誌情報 | OL |
| canonical / scope_flag | フラグ | OL + Stage 4h |
| jstor_count | JSTOR言及数 | Stage 5a |
| oa_count | OpenAlex言及数 | Stage 5b |
| edition_count | OL版数 | Stage 4f |
| htid_count / pd_count | HathiTrust所蔵数 | Stage 4g |
| gr_ratings / gr_reviews / ratings_5〜1 / gr_match | Goodreads評価 | Stage 4h |
| log_jstor / log_oa / log_edition / log_htid / log_gr | 対数変換値 | 派生列 |
| wikidata_qid / sitelink_count | Wikidata | Stage 4e |

---

### FORCE_MAPバグ修正 — 完了 2026-05-28

**修正した3件:**

| 旧work_key | 旧著者 | 新work_key | 正しい著者 | edition_count |
|---|---|---|---|---|
| OL9056552W | George F. Wear | OL245401W | Anthony Hope | 627 |
| OL15345521W | Jaroslav Hašek | OL509889W | Ford Madox Ford | 355 |
| OL15062619W | Martin Harry Greenberg | OL85892W | Bram Stoker | 736 |

修正はpopulationファイルおよびderived/以下の全ファイルに一括反映済み（2026-05-28）。

**修正後の3件の値（canon_integrated.tsv確定値）:**

| 作品 | JSTOR | OA | HT | GR | ED |
|---|---|---|---|---|---|
| The Prisoner of Zenda | 1 | 17 | 19 | 15,006 | 627 |
| The Good Soldier | 21 | 112 | 2 | 18,106 | 355 |
| Dracula | 63 | 200 | 1 | 711,064 | 736 |

⚠️ Good SoldierのOA=112は「The Good Soldier」という一般的語句のため過大評価の可能性あり。他の作品と同一の第1次スキャン方式なので一貫性は保たれているが、論文では注記すること。

---

### canonical 98件カバレッジ（2026-05-28時点確定値）

| DB | Coverage | 品質 | 備考 |
|---|---|---|---|
| OL版数 | 98/98 | ✅ 最良 | FORCE_MAPバグ修正済み |
| JSTOR | 75/98 | 🔶 第1次スキャン | セマンティック再スキャン未実施 |
| OpenAlex | 77/98 | 🔶 第1次スキャン | 誤カウントあり（The Yearling等） |
| HathiTrust | 93/98 | ✅ 最良値 | 残り5件は構造的限界 |
| Goodreads | 82/98 | ✅ 精度検証済み | 2017年データ・相対順位で使用 |
| Wikidata | 62/98 | 🔶 一部のみ | 残り36件は手動確認必要 |

**HathiTrustゼロの5件（構造的限界）:**
- Looking Backward / Bellamy：HathiFilesに所蔵なし
- The Golden Cage / Bromige：マイナー作品
- The Innocents / Machard：マイナー作品
- The North Star / Henry-Ruffin：マイナー作品
- The Damascus Road / Parini：1999年出版・スコープ外

**Goodreads手動補完3件（MANUAL_FIX）:**
- Dracula → work_id=3165724（ratings=711,064）
- The Good Soldier → work_id=1881188（ratings=18,106）
- The Prisoner of Zenda → work_id=2661176（ratings=15,006）
- Maggie, a girl of the streets → work_id=6712095（ratings=6,282）

---

### 次の優先作業

| 優先度 | タスク | 費用 | 状態 |
|---|---|---|---|
| 1 | JSTORセマンティック再スキャン（canonical 98件） | ~200円 | 未着手 |
| 2 | OpenAlexセマンティック再スキャン（canonical 98件） | ~200円 | 未着手 |
| 3 | Wikidata canonical残り36件の手動確認 | 無料 | 未着手 |
| 4 | Spearman相関行列の再計算（Goodreads軸追加） | 無料 | 未着手 |
| 5 | Wikidata全件（34,685件） | 研究費取得後 | 未着手 |

## Stage 4i-ext: Canon Integrated 品質評価 & カバレッジ検証 — 2026-06-13

### DH2026 Poster Evaluation Numbers

- Source: `derived/canon_integrated.tsv`
- Population: n=34,789件
- Canonical subset: n=98件

- Match definition: numeric DBs are treated as linked when the value is `>0`; Wikidata is linked when `wikidata_qid` is present; Goodreads uses `gr_match` to separate `value>0`, `matched but 0`, and `unmatched`.
- For JSTOR/OpenAlex/HathiTrust/Open Library, this file does not expose an explicit processing-status column, so `0` cannot be split further into `searched but zero` vs. `unprocessed`.

### 1. 全体カバレッジ

| DB | マッチあり | マッチ成功・値0 | 未マッチ |
|---|---:|---:|---:|
| Open Library | n=34,789件, 100.0% | 判別不可 | n=0件, 0.0% |
| JSTOR | n=3,498件, 10.1% | 判別不可 | n=31,291件, 89.9% |
| OpenAlex | n=8,363件, 24.0% | 判別不可 | n=26,426件, 76.0% |
| HathiTrust | n=23,098件, 66.4% | 判別不可 | n=11,691件, 33.6% |
| Goodreads | n=11,300件, 32.5% | n=2件, 0.0% | n=23,487件, 67.5% |
| Wikidata | n=1,367件, 3.9% | n=0件, 0.0% | n=33,422件, 96.1% |

### 2. 複数DBに繋がった作品の分布

| 接続DB数（6DB） | 件数 |
|---|---:|
| 6DB | n=284件, 0.8% |
| 5DB | n=1,289件, 3.7% |
| 4DB | n=3,764件, 10.8% |
| 3DB | n=7,935件, 22.8% |
| 2DB | n=13,890件, 39.9% |
| 1DB | n=7,627件, 21.9% |
| 0DB | n=0件, 0.0% |

注: Open Library は母集団そのものなので `0DB` は構造上 0件、`1DB` は実質的に「Open Library のみ」です。

### 3. 学術文献のリンク状況

| 指標 | 値 |
|---|---:|
| JSTORで引用1件以上 | n=3,498件, 10.1% |
| OpenAlexで引用1件以上 | n=8,363件, 24.0% |
| JSTORまたはOpenAlexで引用1件以上 | n=9,869件, 28.4% |
| 引用ゼロ（JSTOR=0かつOpenAlex=0） | n=24,920件, 71.6% |

### 4. Canonical作品での精度

| DB | canonical (n=98) | 全体 (n=34,789) | 差分 |
|---|---:|---:|---:|
| Open Library | n=98件, 100.0% | n=34,789件, 100.0% | +0.0 pt |
| JSTOR | n=75件, 76.5% | n=3,498件, 10.1% | +66.5 pt |
| OpenAlex | n=77件, 78.6% | n=8,363件, 24.0% | +54.5 pt |
| HathiTrust | n=93件, 94.9% | n=23,098件, 66.4% | +28.5 pt |
| Goodreads | n=82件, 83.7% | n=11,300件, 32.5% | +51.2 pt |
| Wikidata | n=62件, 63.3% | n=1,367件, 3.9% | +59.3 pt |

### 5. 代表作品プロファイル

| 作品 | 採用work_key | canonical | jstor_count | oa_count | edition_count | htid_count | gr_ratings | wikidata_qid | sitelink_count | 備考 |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| Heart of Darkness (Conrad) | /works/OL31971259W | 1 | 118 | 25 | 14 | 1 | 315808 | Q129778 | 57 | 候補4件; canonical=1を採用 |
| White Fang (London) | /works/OL74504W | 1 | 0 | 29 | 387 | 2 | 117038 | Q152267 | 45 | 候補2件; canonical=1を採用 |
| Ulysses (Joyce) | /works/OL35695219W | 1 | 443 | 54 | 71 | 3 | 88298 | Q6511 | 166 | 候補3件; canonical=1を採用 |

### 6. LLM判定の信頼度分布（Goodreads照合ログ由来）

| 指標 | 値 |
|---|---:|
| 高信頼度で自動確定（UNIQUE/YEAR_AUTH/RATINGS_MAX） | n=11,202件, 32.2% |
| 低信頼度で追加判定・人手補正（LLM/MANUAL_FIX） | n=100件, 0.3% |
| 一致なし判定（NO_MATCH/NO_MATCH_AUTH） | n=23,487件, 67.5% |
| 補足: LLM最終決定のみ | n=96件, 0.3% |
| 補足: 人手補正のみ | n=4件, 0.0% |

### 7. Wikidataベンチマーク（n=130）の誤り分析

| 指標 | 値 |
|---|---:|
| False Positive（negative=48件中の誤一致） | n=1件, 2.1% |
| False Negative（positive=82件中の見逃し/誤同定） | n=4件, 4.9% |

#### 誤りケースの要約
- Kim
- At Fault
- The octopus, a story of California
- Peter Pan
- The Capsina: An Historical Novel

#### 類型化（暫定）
| 類型 | 件数 | 代表ケース |
|---|---:|---|
| ① ID世代ずれ | 1件 | `Kim` |
| ② 同名異著者 | 1件 | `The Capsina: An Historical Novel` |
| ③ 収録制限 | 2件 | `At Fault`, `The octopus, a story of California` |
| ④ 重複登録 | 1件 | `Peter Pan` |

#### 誤り内容メモ
- Kim: 近接する別QIDへの取り違え。`OL19908W` 側に `Q589868` が付いており、同一題名の重複登録/IDずれが示唆される。
- At Fault: gold QIDはあるが `pred_qid=NO_MATCH`。sitelink 0 の疎な項目で、収録制限または探索漏れの可能性が高い。
- The octopus, a story of California: gold QIDはあるが `pred_qid=NO_MATCH`。著者作品一覧が 0件取得になっており、収録制限/取得失敗型。
- Peter Pan: `Q3435337` ではなく `Q19032697` を返しており、近接する別作品への重複登録・IDずれ型。
- The Capsina: An Historical Novel: gold は `NO_MATCH` だが `Q124087127` を返した。負例への過剰一致で、同名異著者または近接候補の誤採択とみられる。


### 4i-1: canon_integrated.tsv ファイル品質評価

**列構成（26列確定）**

| グループ | 特徴 |
|---|---|
| 書誌情報 | work_key, title, author_name, first_publish_year |
| フラグ | canonical, scope_flag |
| DB値 | jstor_count, oa_count, edition_count, htid_count, pd_count |
| Goodreads | gr_ratings, gr_reviews, ratings_5-1, gr_match（唯一の方法列） |
| Wikidata | wikidata_qid, sitelink_count |

**重要な発見**

- edition_count のみ 100% 埋まり（OL Dump直接集計）
- gr_match のみが照合方式を記録（他DBは方法列なし）
- Wikidata QID 未解決 33,422件（96.1%）が構造的課題
- Canonical 行が優先的に再スキャンされた可能性


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


## Stage 5a-2: JSTOR L&L スキャン詳細記録 — 2026-05-31確定

### スキャン設計

**入力:** `derived/jstor_ll_articles.jsonl`（161万件）
**出力:** `derived/jstor_ll_scan.tsv`（33,888件）

#### 中間ファイル生成（jstor_ll_articles.jsonl）

JSTOR全件12,380,553件から以下の条件で抽出：

```
discipline_names に "Language & Literature" を含む
かつ content_type が article / book_part / book のいずれか
かつ title が存在する
```

抽出結果：1,612,019件（全体の13%）

#### 照合ロジック（確定版）

```python
# OL側タイトル正規化
def normalize(t):
    t = サブタイトル除去（:;/以降）
    t = 小文字化・NFKD正規化・記号→空白・連続空白圧縮
    return t

# JSTOR論文タイトルとのマッチング
条件1: OL正規化タイトルの全単語がJSTOR論文タイトルの単語セットに含まれる（AND）
条件2: OL正規化タイトルのフレーズがJSTOR論文タイトルに含まれる（順序保証）
条件3: 短いタイトル（1語 または 正規化後4文字以下）は著者姓必須
```

#### 短タイトル判定の例外処理

条件3（著者姓必須）は一般語の誤ヒットを防ぐためだが、固有名詞的な1語タイトルには過剰フィルタになる。そのため以下の作品は著者姓なしで個別再カウントした：

| 作品 | 理由 | 確定値 |
|---|---|---|
| Ulysses | 固有名詞的・著者フィルタで過小評価 | 582件 |
| Dubliners | 固有名詞的 | 76件 |
| Dracula | 固有名詞的 | 66件 |
| McTeague | 固有名詞的 | 20件 |
| Pembroke | 固有名詞的 | 19件 |
| Leonora | 固有名詞的 | 14件 |
| Trelawny | 固有名詞的 | 3件 |
| Megda | 固有名詞的・JSTOR不可視 | 0件 |

#### ノイズ判明作品の手動修正

照合後にサンプル確認で判明したノイズ混入作品を著者フィルタ版に修正：

| 作品 | 修正前 | 修正後 | 理由 |
|---|---|---|---|
| Alas! / Broughton | 319 | 0 | Leopoldo Alas（別著者）のノイズ |
| Kim / Kipling | 221 | 5 | 人名・地名としての混入 |
| Orlando / Woolf | 159 | 12 | イタリア叙事詩・地名の混入 |
| The Pit / Norris | 83 | 1 | 一般語ノイズ |
| The Job / Lewis | 48 | 0 | 一般語ノイズ |
| The Jungle / Sinclair | 48 | 2 | 一般語ノイズ |
| The "genius" / Dreiser | 61 | 3 | 一般語ノイズ |
| The Awakening / Chopin | 54 | 17 | 著者フィルタ後の保守値 |

#### duplicate_canonical 除外

OL母集団に同一作品が複数work_keyで登録されていた54件を `scope_flag=duplicate_canonical` として除外。Great Gatsby・Ulysses・Heart of Darkness等が対象。

---

### canonical 確定値（上位20件）

| 作品 | jstor_ll_count |
|---|---|
| Ulysses | 582 |
| Heart of Darkness | 157 |
| Dubliners | 76 |
| The Secret Agent | 71 |
| Dracula | 66 |
| The Great Gatsby | 64 |
| The Ambassadors | 55 |
| The Sound and the Fury | 54 |
| The Awakening | 54 |
| Turn of the Screw | 48 |
| Mrs. Dalloway | 47 |
| Tess of the D'Urbervilles | 43 |
| As I Lay Dying | 43 |
| Jude the Obscure | 42 |
| The Red Badge of Courage | 39 |
| The Good Soldier | 37 |
| Looking Backward | 31 |
| Sister Carrie | 31 |
| Sons and Lovers | 29 |
| A Portrait of the Artist as a Young Man | 29 |

---

### 方法論的注記（論文記述用）

**定義：**
「JSTOR Language & Literature論文（article/book_part/book）のタイトルに作品名フレーズが含まれる論文数（下限値）。本文・アブストラクト言及は不含。一般語タイトルの作品は著者姓一致件数に補正済み。固有名詞的1語タイトルは著者フィルタを適用しない。」

**既知の限界：**
1. タイトル言及のみ（本文言及は原理的に不可視）
2. L&L以外からの越境言及を含まない（例：Tarzan→African Studies）
3. Ulysses=582はJoyce作品・ホメロス神話・比較文学を含む広義の値
4. 2017年以降の論文は含まない（JSTORスナップショットの限界）
5. 短いタイトル・一般語タイトルはノイズ混入の可能性があり手動補正済み

---


### 5a-3: JSTOR スキャン照合確認（C3グループ検証）

**目的：** Hollow canonのうちOpenAlexに論文が存在するにもかかわらずJSTOR=0となっている10件について、JSTORメタデータ（13GB・jsonl形式）を直接検索し、照合失敗の実態を確認。

**結果（10件）：**

| 作品 | JSTORでの発見 |
|---|---|
| White Fang | 1件（タイトルのみ、詳細不明） |
| The Moon and Sixpence | **2件**（「FANTASY AS NECESSITY...」等） |
| The Yearling | 59件（生物学論文等が混在） |
| Tarzan | 66件（映画・文化研究等が混在） |
| Grand Babylon Hotel | 0件 |

**重要な発見：** The Moon and SixpenceについてはJSTORメタデータに明確に関連論文（「FANTASY AS NECESSITY: THE ROLE OF THE BIOGRAPHER IN 'THE MOON AND SIXPENCE'」等）が存在するにもかかわらず既存スキャンで取りこぼしていることが確認された。これは既存のタイトル照合スキャン方式の限界を直接示す証拠であり、LLMによる意味的照合の必要性を補強する。

**hollow canonの修正への示唆：** JSTOR=0の24件（hollow canon）は過小推定の可能性が高い。Moon and Sixpenceは少なくとも2件の論文が確認され、The Yearlingもノイズを除去すれば実質的にゼロではない可能性がある。

⚠️ **論文記述時の注記：** 「24件」という数字には「第1次スキャン値・過小評価の可能性あり」の注釈をつけること。

---

### 5a-2. JSTOR L&L Scan and Quality Audit — 2026-05-30 追記

#### 目的

JSTORは本研究における「学術的注目軸」の主要データ源である。ただし、初期の `jstor_mentions.tsv` はタイトル共起ベースの第1次スキャンであり、作品への批評的言及を十分に表しているとは限らない。そのため、2026年5月末の作業では、JSTOR値をそのまま分析に使うのではなく、より慎重に再点検し、後続のOpenAlex再設計のための方法論的基準を作ることを目的とした。

この段階の目的は、JSTOR値を完全に確定することではなく、以下の3点を明確にすることである。

1. どの作品がJSTOR上で実際に可視化されているか。
2. どの作品がタイトル照合の限界によって過大・過小評価されているか。
3. 乖離パターン分析に用いる前に、どのような品質監査が必要か。

---

#### 入力データ

| ファイル                                        | 内容                                   |
| ------------------------------------------- | ------------------------------------ |
| `derived/ol_dump_population_with_scope.tsv` | Open Libraryダンプ由来の母集団。`scope_flag`付き |
| `derived/jstor_mentions.tsv`                | 初期JSTORスキャン結果                        |
| `derived/jstor_ll_scan.tsv`                 | JSTOR L&L再スキャン結果                     |
| `derived/canon_integrated.tsv`              | 6DB統合ファイル                            |
| `derived/canon_analysis_base.tsv`           | JSTOR L&L値を反映した分析用ベース表               |

---

#### 出力データ

| ファイル                                         | 内容                                |
| -------------------------------------------- | --------------------------------- |
| `derived/jstor_ll_scan.tsv`                  | JSTOR L&L再スキャン値                   |
| `derived/canon_analysis_base.tsv`            | JSTOR L&L値・scope_flag更新後の分析用ベース表  |
| `derived/quality_review_queue.tsv`           | 一般語タイトル・著者欠落・異常値などの品質監査リスト        |
| `derived/divergence_patterns_v2.tsv`         | 品質フラグを考慮した乖離分類                    |
| `derived/divergence_patterns_v3.tsv`         | JSTORに加えOpenAlex由来ノイズも補正した乖離分類    |
| `derived/divergence_patterns_v3_deduped.tsv` | title + author 単位で代表行を残した重複抑制版    |
| `derived/analysis_scope_review.tsv`          | 作品ではないもの、ジャンル外、時代外、主題名的レコードの監査リスト |

---

#### JSTOR L&Lスキャンの結果

2026年5月末時点で、`jstor_ll_scan.tsv` は33,888件を含む。これは `scope_flag == in_scope` の母集団に対応する。canonical作品については、上位に以下のような作品が出た。

| 作品                     | JSTOR L&L count |
| ---------------------- | --------------: |
| Ulysses                |             582 |
| Heart of Darkness      |             157 |
| Dubliners              |              76 |
| The Secret Agent       |              71 |
| The Great Gatsby       |              64 |
| The Ambassadors        |              55 |
| The Sound and the Fury |              54 |
| The Awakening          |              54 |
| Turn of the Screw      |              48 |
| Mrs. Dalloway          |              47 |
| The Good Soldier       |              37 |

この結果により、FORCE_MAP修正後の `The Good Soldier` など、以前の誤ったwork_key・著者名に由来する不整合が一部改善された。

---

#### FORCE_MAP修正との関係

2026-05-28に、以下3件の誤ったwork_keyを修正した。

| 作品                    | 正しいwork_key        | 正しい著者           |
| --------------------- | ------------------ | --------------- |
| The Prisoner of Zenda | `/works/OL245401W` | Anthony Hope    |
| The Good Soldier      | `/works/OL509889W` | Ford Madox Ford |
| Dracula               | `/works/OL85892W`  | Bram Stoker     |

JSTOR値は、これらの修正後のwork_keyをもとに再統合した。したがって、`canon_integrated.tsv` 以前のJSTOR値と、`canon_analysis_base.tsv` 以後のJSTOR L&L値は区別する必要がある。

---

#### 品質監査で判明した問題

JSTOR L&L値を乖離パターン分類に入れると、以下のような問題が現れた。

1. 短いタイトル・一般語タイトルの過大評価
   例：`The Rescue`, `The Road`, `The river`, `The Children`, `The Source`

2. 著者名欠落レコードの混入
   例：`In the shadow`, `Farm animals`, `The raindrop`

3. 作品ではなく主題・人物名・批評書名に近いレコードの混入
   例：`Arnold`, `Edgar Allan Poe`, `Chaucer`, `Women writers`, `American literature`, `Short stories`

4. 同一 title + author の重複
   例：`Robinson Crusoe`, `Redgauntlet`, `The Rainbow`, `Under Western Eyes`

5. 研究対象のスコープ外レコードの残存
   例：詩、戯曲、宗教書、オペラ、中世文学、19世紀以前の古典作品など

このため、JSTOR値は単純な「論文数」としてではなく、「JSTOR上での可視性を示す候補値」として扱う。短いタイトルや一般語タイトルについては、品質監査フラグを付けたうえで、分析用分類から除外または手動確認に回す。

---

#### 品質監査フラグ

`quality_review_queue.tsv` では、以下のようなフラグを付与した。

| フラグ                                | 意味                      |
| ---------------------------------- | ----------------------- |
| `author_missing`                   | OL側に著者名がない              |
| `generic_or_ambiguous_title`       | 短い・一般語的・曖昧なタイトル         |
| `high_jstor_ll`                    | JSTOR L&L値が高い           |
| `extremely_high_jstor_ll`          | JSTOR L&L値が異常に高い        |
| `generic_title_high_jstor`         | 一般語タイトルでJSTOR値が高い       |
| `high_jstor_but_oa_zero`           | JSTOR値が高いがOpenAlex値がゼロ  |
| `duplicate_same_title_author`      | title + author が重複      |
| `subject_or_nonfiction_like_title` | 作品名ではなく主題名・批評書名に近い      |
| `form_or_genre_review`             | 詩・戯曲・オペラ・宗教書などジャンル確認が必要 |

---

#### 乖離パターン分類への影響

初期分類では、`academic_signal = jstor_ll_count + oa_count` として集計したため、以下のような不自然な例が上位に現れた。

| 例                           | 問題                             |
| --------------------------- | ------------------------------ |
| The Rescue                  | OpenAlex由来の巨大値とGoodreads誤照合が混在 |
| The aliens                  | author_missingかつOpenAlex巨大値    |
| In the shadow               | author_missingかつ一般語タイトル        |
| The American                | 一般語タイトルでJSTOR値が過大              |
| Henry James / D.H. Lawrence | 作品ではなく人物名・研究対象名に近い             |

このため、v2・v3の分類では、JSTOR由来のノイズだけでなく、OpenAlex由来のノイズも分類用シグナルから除外する処理を加えた。

---

#### v3分類の方針

v3では、以下の処理を行った。

1. `author_missing` の行は、JSTOR値・OpenAlex値を分類用シグナルから除外する。
2. 非canonicalで、一般語タイトルかつJSTORまたはOpenAlexが異常に高いものは分類用シグナルから除外する。
3. `Henry James`, `D.H. Lawrence`, `Ezra Pound`, `American literature`, `Short stories` など、主題名・人物名・批評書名に近いものは `subject_or_nonfiction_like_title` として監査対象にする。
4. canonical作品は自動除外せず、原則として保持する。
5. 同一 title + author の重複は `divergence_patterns_v3_deduped.tsv` で代表行のみ残す。

---

#### analysis_scope_review.tsv の意味

`analysis_scope_review.tsv` は、乖離分類そのものではなく、母集団のスコープ漏れを確認するための監査リストである。2026-05-30時点で、要確認件数は532件であった。

主な分布は以下の通り。

| note                               |  件数 |
| ---------------------------------- | --: |
| `author_missing`                   | 328 |
| `form_or_genre_review`             | 104 |
| `review_before_use`                | 104 |
| `subject_or_nonfiction_like_title` |  61 |
| `exclude_candidate`                |  61 |
| `generic_short_title_review`       |  29 |
| `title_equals_author`              |  11 |

この結果は、母集団34,789件全体を維持しつつ、分析時には `core_analysis`, `manual_review`, `exclude_likely_leak` のような二次的スコープフラグを導入する必要があることを示している。

---

#### 方法論上の教訓

JSTOR作業から得られた重要な教訓は次の通りである。

1. 全件スキャンの完了と、分析可能な品質の確保は別である。
2. title-only matching は、短いタイトル・一般語タイトル・人物名的タイトルに弱い。
3. canonical作品では高いJSTOR値が妥当である場合が多いが、non-canonicalでは同じ値でもノイズの可能性が高い。
4. 著者名は、照合精度にとって不可欠である。
5. OpenAlexやGoodreadsなど他DBと照合することで、異常値を発見できる。
6. 自動分類は最終判断ではなく、手動確認すべき候補を抽出するための中間工程である。
7. 乖離パターン分析には、データ品質フラグと分析スコープフラグを併用する必要がある。

---

#### 現時点での使用方針

JSTOR L&L値は、以下のように使い分ける。

| 用途                     | 使用可否  | 備考                       |
| ---------------------- | ----- | ------------------------ |
| canonical作品の相対比較       | 使用可   | ただし短いタイトルは注記             |
| 全34,789件の粗い分布把握        | 使用可   | 品質フラグ併用                  |
| 個別non-canonical作品の強い主張 | 要手動確認 | title + author + 文脈確認が必要 |
| hollow canon件数の確定      | 要再確認  | JSTOR=0は過小評価の可能性あり       |
| OpenAlex再設計の基準         | 使用可   | JSTORで判明したノイズ類型を移植する     |

---

#### OpenAlex作業への接続

OpenAlexについては、すでにローカルダンプがあるため、APIで全件を取り直す前に、JSTOR作業で得た教訓をもとに再設計する。

OpenAlex再設計では、最低限以下を区別する。

| 列                       | 意味                       |
| ----------------------- | ------------------------ |
| `oa_count_old`          | 既存の第1次スキャン値              |
| `oa_title_only_count`   | タイトルのみの広い検索値             |
| `oa_title_author_count` | タイトル + 著者名で絞った値          |
| `oa_strict_count`       | 文学・人文学系文脈に限定した値          |
| `oa_quality_note`       | 一般語タイトル・著者欠落・異常値などの注意フラグ |

JSTORと同様に、OpenAlexも単一の `oa_count` ではなく、取得条件ごとに列を分ける。特に `The Rescue`, `The aliens`, `In the shadow` のように、OpenAlex側で巨大値が発生した例は、再設計時のテストケースとして保持する。

---

#### Release記録

| Release ID                  | Date       | Key Artifact                         |
| --------------------------- | ---------- | ------------------------------------ |
| jstor-firstscan-v1          | 2026-04-05 | `jstor_mentions.tsv`                 |
| jstor-ll-scan-v1            | 2026-05-30 | `jstor_ll_scan.tsv`                  |
| canon-analysis-base-v1      | 2026-05-30 | `canon_analysis_base.tsv`            |
| divergence-quality-audit-v1 | 2026-05-30 | `quality_review_queue.tsv`           |
| divergence-patterns-v3      | 2026-05-30 | `divergence_patterns_v3_deduped.tsv` |
| analysis-scope-review-v1    | 2026-05-30 | `analysis_scope_review.tsv`          |

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

### 5b-3: OpenAlex API vs ローカルスナップショット — String-Matching の限界

**タスク：** C3グループ（JSTOR=0かつOA>0の10件）についてOA APIでoa_countを再現できるか検証。

**結果：** 全件で大幅な乖離（再現不可）

| 作品 | gold_oa（ローカルスナップショット） | OA API取得数 | 乖離 |
|---|---|---|---|
| White Fang | 29 | 90 | +61 |
| The Yearling | **3** | **3,183** | **+3,180** |
| The Moon and Sixpence | 3 | 93 | +90 |
| Tarzan of the Apes | 2 | 48 | +46 |
| Senator North | 1 | 49 | +48 |

**原因分析：**

OA APIのtitle searchは意味的推論を持たない文字列マッチングであるため、以下の誤ヒットが発生：

- 「The Yearling」→ 動物科学の「yearling（離乳期）」論文3,183件にヒット
- 「Senator North」→ 政治学・議会関連論文49件にヒット
- 「White Fang」→ 合本・別著者作品が混入し90件

**gold_oa値（スナップショット由来）との関係：**

gold_oa=29（ローカルスナップショット・title-only matching）は、620GBのローカルデータに対して独自のマッチング処理を行った結果であり、OA APIとは異なる結果を返す。スナップショットとAPIは**同一のOpenAlexデータセットから異なる値を返す**ことが判明。

**意義：**

この発見はOpenAlexベンチマークの「失敗」ではなく、むしろ**LLMによる意味的エンティティ解決の必要性の直接的な実証**である。文字列マッチングでは「The Yearling（Rawlings, 1938）についての学術論文」と「yearling（離乳期の動物）に関する動物科学論文」を区別できない。著者・出版年・文学的文脈についての推論が不可欠であり、これがLLM多段階推論の存在意義を示す具体的な事例となる。

**今後への示唆：** OpenAlexの値を「第1次スキャン値」として扱い、個別の重要作品については著者名・出版年を含めた再確認が必要。

---

### 5b-2. OpenAlex Redesign and Full-Dump Test Scan — 2026-05-31 追記

#### 背景

OpenAlexは、本研究における「学術的注目軸」の補助的データ源である。既存の `derived/openalex_snapshot_mentions.tsv` は、ローカルOpenAlex Worksダンプを用いた第1次スキャン結果であり、主に title-only matching に基づいていた。

しかし、2026年5月末のJSTOR品質監査および乖離パターン分析の過程で、OpenAlexの旧 `oa_count` に大きなノイズが含まれることが確認された。特に、短いタイトル・一般語タイトル・人物名的タイトルでは、文学作品への学術的言及ではなく、一般語・主題語・生物名・地名・人名としての出現を拾ってしまう。

そのため、OpenAlex値は、JSTORと同じ「文学研究内部の批評的注目」ではなく、より広い学術圏における作品可視性として再定義する。また、単一の `oa_count` ではなく、複数の照合レベルを区別して保存する。

---

#### ローカルデータ

OpenAlex Worksダンプはローカルに保存済みである。

```text
/mnt/d/openalex/works/updated_date=*/part_*.gz
```

2026-05-31時点の確認結果：

| 項目                   |           値 |
| -------------------- | ----------: |
| ファイル数                |         901 |
| 全件テストスキャン対象レコード数     | 152,044,758 |
| JSON error           |           0 |
| 212件テスト対象の全ダンプスキャン時間 |      733.4分 |

---

#### OpenAlex Worksレコードの利用可能フィールド

スキーマ確認により、以下の主要フィールドが利用可能であることを確認した。

| フィールド                      | 用途                                   |
| -------------------------- | ------------------------------------ |
| `display_name` / `title`   | 論文・書籍等のタイトル                          |
| `abstract_inverted_index`  | abstract復元用                          |
| `publication_year`         | 出版年                                  |
| `language`                 | 言語                                   |
| `type`                     | article, book-chapter, dissertation等 |
| `authorships`              | OpenAlex work自体の著者                   |
| `primary_topic` / `topics` | OpenAlexのトピック分類                      |
| `concepts`                 | 概念分類                                 |
| `referenced_works`         | 参照文献情報                               |

ただし、`primary_topic`, `topics`, `concepts` は、今回の検証では文学文脈の判定にそのまま使うには不安定であった。無関係な医学・工学・生物系の論文でも、`Hermeneutics and Narrative Identity` などの人文学系topicが付与される例が見られたためである。したがって、OpenAlexのtopic情報は補助情報として保存するが、現時点では採用・除外の主条件にはしない。

---

#### 旧方式の問題

旧 `oa_count` は title-only matching に基づいていたため、以下のような問題が発生した。

| 作品・レコード       |        旧 `oa_count` | 新方式での問題確認                          |
| ------------- | ------------------: | ---------------------------------- |
| The Rescue    |              24,048 | title phraseは出るが、著者共起なし            |
| The aliens    |               8,400 | title phraseは出るが、著者共起なし            |
| In the shadow |               4,339 | title phraseは出るが、著者共起なし            |
| The American  |     旧値は小さいが、新方式でも危険 | `American` + `Fast` のような普通語共起が多い   |
| Dracula       |                 200 | `Desmodus draculae` など作品外ノイズを含む可能性 |
| The Yearling  | 旧スキャンで動物科学系ノイズを確認済み | title-onlyでは不適切                    |

このため、旧 `oa_count` は削除せず、今後は `oa_count_old` として保存し、ノイズ比較・方法論説明用の値として扱う。

---

#### 新しい照合レベル

OpenAlex再設計では、以下の複数列を作る。

| 列                                 | 意味                                       | 用途                            |
| --------------------------------- | ---------------------------------------- | ----------------------------- |
| `oa_count_old`                    | 旧title-only方式の値                          | 参考・比較・ノイズ説明用                  |
| `oa_title_phrase_count`           | 作品タイトル語句がtitle/abstractに出る件数             | ノイズ監査用                        |
| `oa_title_author_count`           | 作品タイトル語句と作品著者姓がtitle/abstract本文内に共起する件数  | 新しい主指標候補                      |
| `oa_title_author_english_count`   | title + author条件を満たし、languageがenまたは不明の件数 | 英語圏中心の補助値                     |
| `oa_title_author_lit_terms_count` | title + author条件に加え、本文中に文学語が出る件数         | 保守的補助指標                       |
| `oa_risk_flags`                   | 短題名・危険な著者姓・人物名タイトル等の注意フラグ                | 品質監査                          |
| `oa_recommendation_status`        | 自動採用・警告付き採用・手動確認等の区分                     | 分析時の制御                        |
| `oa_recommended_count`            | 現時点の推奨OpenAlex値                          | 原則として `oa_title_author_count` |

---

#### title matching の修正

旧方式では単純な substring matching を用いていたため、以下のような誤ヒットが発生した。

| 作品タイトル    | 誤ヒット例               |
| --------- | ------------------- |
| Alas!     | Alaska              |
| The trial | clinical trial      |
| The Pit   | 医学・看護系の文脈           |
| Dracula   | `Desmodus draculae` |
| Summer    | mid-summer          |
| Democracy | 政治学・教育学等の一般語        |

そのため、新方式では、単純な文字列包含ではなく、正規化後の token phrase matching を使用する。たとえば `The Great Gatsby` は `the great gatsby` または `great gatsby` を許可するが、`The Pit` のような短いタイトルでは冠詞除去後の短い語だけでは照合しない。

---

#### 著者姓判定の注意

OpenAlexレコードの `authorships` は、OpenAlex work自体の著者であり、文学作品の著者ではない。したがって、作品著者姓が `authorships` に出るだけでは作品言及とはみなさない。

採用条件は以下とする。

```text
作品タイトル語句が OpenAlex work の title/abstract に出る
かつ
作品著者姓が同じ title/abstract に出る
```

たとえば、`Heart of Darkness / Conrad` の場合、`Heart of Darkness` と `Conrad` がOpenAlex workのタイトルまたはabstract本文に共起する場合にカウントする。論文著者が Conrad であるだけの場合はカウントしない。

---

#### 文学語による保守指標

`oa_title_author_lit_terms_count` は、title + author 条件に加え、title/abstract本文内に以下のような文学・批評関連語が含まれる場合にカウントする。

```text
literature, literary, fiction, novel, novels,
narrative, modernism, modernist, realism, gothic,
criticism, critic, critics, reading, readings,
canon, canonical, postcolonial, colonial,
aesthetic, genre, character, narrator, poetics,
textual, story, stories, romance
```

ただし、この値は保守的すぎる可能性があるため、主指標ではなく補助指標として扱う。

---

#### 212件テスト対象

OpenAlex再設計のため、まず `derived/openalex_test_targets.tsv` を作成した。

対象は以下を含む212件である。

| 種類                        | 内容                                                                 |
| ------------------------- | ------------------------------------------------------------------ |
| canonical全件               | PhD reading list由来のcanonical作品                                     |
| A/B/C/F分類上位候補             | 乖離パターン分類の代表例                                                       |
| 既知ノイズ例                    | The Rescue, The aliens, In the shadow, The American, The Yearling等 |
| 人物名・主題名例                  | Arnold, Chaucer, Henry James, D.H. Lawrence, Edgar Allan Poe等      |
| hollow / public-visible候補 | White Fang, Tarzan of the Apes, Cannery Row等                       |

---

#### 212件の全OpenAlexダンプスキャン

`derived/openalex_test_targets.tsv` の212件について、全OpenAlex Worksダンプを走査した。

| 項目               |                                        値 |
| ---------------- | ---------------------------------------: |
| 対象作品数            |                                      212 |
| OpenAlexダンプファイル数 |                                      901 |
| 走査レコード数          |                              152,044,758 |
| JSON error       |                                        0 |
| 実行時間             |                                   733.4分 |
| 出力               | `derived/openalex_test_fullscan_212.tsv` |

---

#### 212件テスト結果の主要な発見

##### 1. 旧OpenAlex巨大ノイズは新方式で大幅に抑制された

| 作品            | 旧 `oa_count` | `oa_title_phrase_count` | `oa_title_author_count` | 判断               |
| ------------- | -----------: | ----------------------: | ----------------------: | ---------------- |
| The Rescue    |       24,048 |                   9,095 |                       0 | 旧値はtitle-onlyノイズ |
| The aliens    |        8,400 |                     437 |                       0 | 旧値はtitle-onlyノイズ |
| In the shadow |        4,339 |                   7,579 |                       0 | 旧値はtitle-onlyノイズ |

この結果により、旧 `oa_count` をそのまま学術的注目軸に使うべきでないことが確認された。

##### 2. canonical主要作品は title + author 条件でも大きく残る

| 作品                                      | `oa_title_author_count` | `oa_title_author_lit_terms_count` |
| --------------------------------------- | ----------------------: | --------------------------------: |
| Ulysses                                 |                   2,194 |                             1,574 |
| Heart of Darkness                       |                   1,005 |                               774 |
| The Great Gatsby                        |                     858 |                               652 |
| Dracula                                 |                     774 |                               561 |
| Mrs. Dalloway                           |                     740 |                               576 |
| Dubliners                               |                     689 |                               544 |
| To the Lighthouse                       |                     634 |                               507 |
| A Portrait of the Artist as a Young Man |                     509 |                               384 |
| Tess of the D'Urbervilles               |                     504 |                               369 |
| The Picture of Dorian Gray              |                     504 |                               377 |
| The Sound and the Fury                  |                     492 |                               370 |
| Nineteen Eighty-Four                    |                     437 |                               302 |

この結果は、`oa_title_author_count` が旧 `oa_count` よりも文学作品への学術的可視性に近い指標として機能する可能性を示す。

##### 3. 人物名・主題名タイトルは title + author 条件でも大きく残る

| レコード                               | `oa_title_author_count` | 判断                 |
| ---------------------------------- | ----------------------: | ------------------ |
| Arnold / Matthew Arnold            |                  34,536 | 作品ではなく人物・主題としての可視性 |
| Chaucer / Geoffrey Chaucer         |                   7,818 | 作品ではなく人物・主題としての可視性 |
| Henry James / James, Henry         |                   5,613 | 作品ではなく人物・主題としての可視性 |
| D.H. Lawrence / Lawrence, D. H.    |                   3,458 | 作品ではなく人物・主題としての可視性 |
| Edgar Allan Poe / Poe, Edgar Allan |                   3,078 | 作品ではなく人物・主題としての可視性 |

これらはOpenAlex照合の失敗ではなく、母集団内に人物名・主題名的レコードが残っていることによる。したがって、OpenAlex側で除外するのではなく、`analysis_scope_flag` 側で `subject_or_person_title` として管理する。

##### 4. 著者姓が普通語の場合は注意が必要

例として、`The American / Howard Fast` は `oa_title_phrase_count=355,656`, `oa_title_author_count=2,809`, `oa_title_author_lit_terms_count=867` となった。これは、`American` と `fast` が普通語として共起している可能性がある。

このため、著者姓が一般語・形容詞・地名・普通名詞として現れやすい場合は、自動除外はしないが、`risky_author_last` フラグを付与する。

---

#### 品質監査結果

`derived/openalex_test_fullscan_212.tsv` に対して、`derived/openalex_test_fullscan_212_audit_v2.tsv` を作成した。

推薦ステータス分布は以下の通り。

| status                          | 件数 |
| ------------------------------- | -: |
| `use_with_warning_short_title`  | 95 |
| `use_title_author`              | 70 |
| `zero_title_author`             | 22 |
| `use_with_warning_risky_author` | 13 |
| `manual_scope_review`           |  9 |
| `exclude_author_missing`        |  3 |

リスクフラグ分布は以下の通り。

| flag                                     |  件数 |
| ---------------------------------------- | --: |
| `short_title_len_le_2`                   | 120 |
| `canonical_preserved`                    |  98 |
| `huge_phrase_with_author_check_needed`   |  27 |
| `observed_generic_short_title`           |  22 |
| `very_high_ta_noncanonical_check_needed` |  10 |
| `observed_subject_or_person_title`       |   9 |
| `huge_phrase_zero_author`                |   8 |
| `ta_without_lit_terms`                   |   5 |
| `author_missing`                         |   3 |
| `old_high_now_zero`                      |   3 |

---

#### short title flag の扱い

`short_title_len_le_2` は除外理由ではない。これは、title-only matching が危険であることを示す監査フラグである。

たとえば、以下のcanonical作品はいずれも短題名に分類されるが、title + author 条件では妥当な値を示している。

| 作品            | `oa_title_author_count` |
| ------------- | ----------------------: |
| Ulysses       |                   2,194 |
| Dracula       |                     774 |
| Mrs. Dalloway |                     740 |
| Dubliners     |                     689 |
| Orlando       |                     431 |
| The Awakening |                     411 |
| Sister Carrie |                     254 |
| Peter Pan     |                     241 |
| Kim           |                     218 |
| White Fang    |                      55 |

したがって、短題名は自動除外しない。`oa_title_phrase_count` のみを使わず、`oa_title_author_count` を主指標として採用する。

---

#### risky author surname の扱い

著者姓が普通語・形容詞・地名として出やすい場合、title + author 条件でも誤ヒットが残る可能性がある。

暫定的な注意対象例：

```text
fast, brown, green, white, black, king, young,
hardy, swift, hope, field, fields, stone,
wells, ward, west, north, ford
```

ただし、これらは除外リストではない。Ford Madox Ford, Thomas Hardy, H. G. Wells, Rebecca West, Anthony Hope など、重要な文学作品の著者姓でもあるため、自動除外すると正しいヒットを失う。

したがって、これらは `risky_author_last` としてフラグを付けるだけに留める。canonical作品は原則として保持する。

---

#### recommendation status の意味

| status                          | 意味                       | 分析での扱い                             |
| ------------------------------- | ------------------------ | ---------------------------------- |
| `use_title_author`              | title + author条件で採用可能    | 主分析に使用可                            |
| `use_with_warning_short_title`  | 短題名だがtitle + author条件は成立 | 主分析に使用可。ただし注記                      |
| `use_with_warning_risky_author` | 著者姓が普通語として出やすい           | canonicalは使用可。non-canonicalは個別確認推奨 |
| `manual_scope_review`           | 人物名・主題名・スコープ外の可能性        | 自動集計からは分ける                         |
| `zero_title_author`             | title phraseは出るが著者共起なし   | OpenAlex分析値は0                      |
| `exclude_author_missing`        | 著者名欠落                    | OpenAlex分析値は0                      |

---

#### 現時点の採用方針

OpenAlexの分析用値は、当面以下の方針で扱う。

```text
1. author_missing → 0
2. title_author_count = 0 → 0
3. subject_or_person_title → manual_scope_review
4. canonical → 原則保持
5. short title → warningを付けて保持
6. risky author surname → warningを付けて保持
7. その他 → title_author_count を採用
```

`oa_recommended_count` は、原則として `oa_title_author_count` とする。ただし、個別作品を論文で例示する場合は、`title_author_example_1` などの実例を確認する。

---

#### 今後の拡張方針

212件テストの結果、OpenAlexの主指標は旧 `oa_count` ではなく、新しい `oa_title_author_count` を用いる方針とする。

今後の実施段階は以下の通り。

| Phase | 内容                                | 対象      |
| ----- | --------------------------------- | ------- |
| OA-0  | 既存値と問題例の整理                        | 完了      |
| OA-1  | 212件テストセットの全ダンプスキャン               | 完了      |
| OA-2  | `openalex_rerun_targets.tsv` への拡張 | 4,914件  |
| OA-3  | 必要に応じてin_scope全件へ拡張               | 33,888件 |

OA-2では、212件テストで確定した照合ルールをそのまま適用する。ただし、除外ではなく、値を残したうえで `oa_risk_flags` と `oa_recommendation_status` を付与する。

---

#### 使用方針

OpenAlexは、JSTORと同じ意味の「文学研究内部の注目」ではない。OpenAlexは、より広い学術圏における可視性を示す補助指標である。

したがって、論文では以下のように使い分ける。

| 指標                                         | 解釈             |
| ------------------------------------------ | -------------- |
| JSTOR L&L                                  | 文学研究内部の注目      |
| OpenAlex `oa_title_author_count`           | 広義の学術圏での作品可視性  |
| OpenAlex `oa_title_author_lit_terms_count` | 文学語を含む保守的可視性   |
| OpenAlex `oa_count_old`                    | 旧方式の参考値・ノイズ比較用 |

単純な `jstor + oa_count_old` の合算値は使用しない。統合指標を作る場合は、必ず `oa_recommended_count` または `oa_title_author_count` を用い、JSTOR値とOpenAlex値を別々に確認したうえで合算する。

---

#### Release記録

| Release ID                    | Date       | Key Artifact                              |
| ----------------------------- | ---------- | ----------------------------------------- |
| openalex-firstscan-v1         | 2026-03-26 | `openalex_snapshot_mentions.tsv`          |
| openalex-rerun-targets-v1     | 2026-05-30 | `openalex_rerun_targets.tsv`              |
| openalex-test-targets-v1      | 2026-05-31 | `openalex_test_targets.tsv`               |
| openalex-test-fullscan-212-v1 | 2026-05-31 | `openalex_test_fullscan_212.tsv`          |
| openalex-test-audit-v2        | 2026-05-31 | `openalex_test_fullscan_212_audit_v2.tsv` |

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

---
---
## Stage 7 Phase 1c: CI本文直接引用分類 — 完了 2026-05-30

### 目的とPhase 1bとの関係

Phase 1b（脚注証拠タイプ分類）は脚注が参照している出典の種類を測定した。
Phase 1cは本文中のクォーテーションマーク付き直接引用（インライン）および一部のブロック引用の引用元を測定する。

| | Phase 1b | Phase 1c |
|---|---|---|
| 対象 | 脚注テキスト（8,940行） | 本文のクォート付き直接引用 |
| 測定 | この注は何を参照しているか | この引用はどこから来たか |
| 不可視 | 本文埋め込み引用（Ulysses p.19等） | 間接引用・要約・ブロック引用の一部 |

**Phase 1cを実施した理由:** 脚注分析だけでは本文中の一次テキスト直接引用が構造的に捕捉されない。特に文学テキストからの直接引用（"To be or not to be"等）は本文インライン引用として現れるが脚注に参照が出ないことが多い。

---

### 分類スキーム

| カテゴリ | 定義 | Phase 1b対応 |
|---|---|---|
| **A** | 批評家・理論家・学者の言葉（学術書・論文・批評エッセイ） | カテゴリ4 |
| **B** | 作家・芸術家の言葉（書簡・日記・エッセイ・序文、作品テキスト外） | カテゴリ1aの一部 |
| **C** | 文学・芸術作品テキストそのもの（小説・詩・戯曲の本文） | カテゴリ1a |
| **D** | その他一次資料（哲学・政治・法律・歴史テキスト等） | カテゴリ1b |
| **X** | 判定不能 | — |
| **0** | ノイズ除外（著者紹介・脚注テキスト・図版キャプション） | — |

---

### パイプライン

**抽出スクリプト:** `scripts/extract_body_quotations_v3.py`
**修正スクリプト:** `scripts/fix_greeson_classifications.py`

```bash
# 抽出（全248ファイル）
python3 scripts/extract_body_quotations_v3.py \
  --pdf-dir "/mnt/c/Users/tsuts/Desktop/色々使えるデータ/Critical Inquiry/2019-2025" \
  --step extract

# LLM分類（claude-haiku-4-5-20251001）
python3 scripts/extract_body_quotations_v3.py \
  --pdf-dir "/mnt/c/Users/tsuts/Desktop/色々使えるデータ/Critical Inquiry/2019-2025" \
  --step classify

# 手動修正（Greeson 2025 + 全論文ノイズ除外）
python3 scripts/fix_greeson_classifications.py
```

**設定:**
- inline引用: クォーテーションマーク付き・8語以上
- block引用: フォントサイズ差ベース・10–200語（CI PDFの多くはblock検出不可）
- 最小語数: 8語（3語は誤検出が多いため引き上げ）

---

### 確定結果（2026-05-30）

**総抽出件数:** 1,385件（raw）/ 1,209件（ノイズ・X除く）

| カテゴリ | 件数 | 件数% | 総語数 | 語数% |
|---|---|---|---|---|
| A 批評家・理論家 | 799 | 66.1% | 15,606 | 70.3% |
| B 作家語（作品外） | 34 | 2.8% | 623 | 2.8% |
| C 文学作品テキスト | 292 | 24.2% | 4,376 | 19.7% |
| D その他一次資料 | 84 | 6.9% | 1,595 | 7.2% |
| **計（A–D）** | **1,209** | **100%** | **22,200** | **100%** |
| X（判定不能） | 64 | — | — | — |
| 0（ノイズ除外） | 112 | — | — | — |

**block vs inline内訳:**
- A: block 188件 / inline 610件（blockの大半はノイズ除去後）
- C: block 3件 / inline 289件（文学テキストはほぼinline引用）
- D: block 11件 / inline 73件

---

### Phase 1b vs Phase 1c 確定対比表

| | 脚注（Phase 1b） | 本文件数（Phase 1c） | 本文語数（Phase 1c） |
|---|---|---|---|
| A 批評家・理論家 | 76.9% | **66.1%** | **70.3%** |
| B 作家語（作品外） | N/A | 2.8% | 2.8% |
| C 文学作品テキスト | 9.0% | **24.2%** | **19.7%** |
| D その他一次資料 | 9.6% | 6.9% | 7.2% |

**n:** 脚注=7,401件 / 本文=1,209件

---

### 主要な発見

**発見1: 文学テキスト（C）は脚注の2.7倍（件数比）**
脚注では9.0%だった文学テキストへの参照が、本文の直接引用では24.2%を占める。脚注分析のみでは文学テキストへの直接的な関与を大幅に過小評価する。

**発見2: 批評家の言葉（A）は本文でも支配的**
件数66.1%・語数70.3%。脚注76.9%より低いが依然として圧倒的多数。文学研究者が直接引用においても批評家の言葉を最も多く用いることが本文レベルで確認された。

**発見3: 件数と語数の乖離（C）**
C: 件数24.2% vs 語数19.7%。文学テキストは短く頻繁に引用され、批評家の言葉は長く引用される。1件あたりの平均語数: A=19.5語、C=15.0語。

**発見4: 作家語（B）の存在（2.8%）**
書簡・日記・インタビューへの直接引用はPhase 1bでは独立カテゴリがなかった新規指標。

---

### 精度検証

**サンプル確認（各カテゴリ20件・計100件）:**

| カテゴリ | 確認件数 | 正確件数 | 主な誤分類パターン |
|---|---|---|---|
| A 批評家 | 20 | 17 | 著者紹介・脚注のノイズ3件（修正済み） |
| B 作家語 | 20 | 18 | Hobbes等の哲学テキストがBに→D（修正） |
| C 文学テキスト | 20 | 13 | Greeson 2025のHobbes ELがCに→D（修正済み） |
| D その他一次 | 20 | 17 | 図版キャプション・研究者発言（修正済み） |
| X 判定不能 | 20 | — | 脚注・著者紹介ノイズが多数（修正済み） |

**修正後推定精度:** 88–92%（修正済み1,209件中）

**主要な残存限界:**
- ブロック引用の大部分が未検出（CI PDFのフォント・レイアウト構造による）。ただし文学テキスト（C）のブロック引用はクォート付きinlineでほぼ捕捉済み。
- X 64件（5.0%）は分類不能として除外。
- 本分析はインライン直接引用に限定。間接引用（要約・言い換え）は対象外（Arnold et al. 2025参照）。

---

### 出力ファイル

| ファイル | 件数 | 内容 |
|---|---|---|
| `derived/ci_body_quotations/quotations_raw_v3.tsv` | 1,385 | 抽出済み全引用スパン |
| `derived/ci_body_quotations/classifications_v3.tsv` | 1,385 | LLM分類結果（修正前） |
| `derived/ci_body_quotations/classifications_v3_fixed.tsv` | 1,385 | **確定版**（手動修正・ノイズ除外済み） |
| `derived/ci_body_quotations/checkpoint_v3.jsonl` | 1,343 | チェックポイント |
| `derived/ci_body_quotations/validation_sample.tsv` | 100 | 精度検証サンプル |

---

### 費用記録

| 処理 | モデル | 件数 | 費用（推定） |
|---|---|---|---|
| LLM分類 | claude-haiku-4-5-20251001 | 1,343件 | ~$0.5 USD |

---

### Phase 1b との統合解釈（論文用）

脚注（Phase 1b）と本文引用（Phase 1c）を合算すると、Critical Inquiry 2019–2025における引用実践の全体像が以下のように描かれる:

**批評家・理論家への依存（A）:** 脚注・本文ともに最大カテゴリ（脚注76.9%・本文66%）。Piper（2020）が診断した「分野的一般化」構造は脚注だけでなく本文の直接引用にも貫徹している。

**文学テキストとの関与（C）:** 脚注9%・本文24%。批評家は文学テキストを脚注では参照せず本文で直接引用する。この構造は「文学テキストが議論の根拠としてではなく、議論の例示として機能している」可能性を示す。

**社会的流通・制度・定量証拠（Phase 1b: カテゴリ2+3+5 = 4.4%）:** 本文引用でも同様に少数（B: 2.8%）。文学研究者が正典化・受容・制度的扱われ方を問う際に、それを実証するデータ基盤が乏しいという構造的問題は本文レベルでも確認される。

---

### Release記録

| Release ID | Date | Key Artifact |
|---|---|---|
| ci-body-quot-v1 | 2026-05-30 | `classifications_v3.tsv`（LLM分類・1,385件） |
| ci-body-quot-fixed-v1 | 2026-05-30 | `classifications_v3_fixed.tsv`（確定版・手動修正済み） |

*本セクション作成: 2026-05-30*


## Stage 7a: DH Reception Analysis — OpenAlex Journal Metadata Scan 2000–2025

### Purpose

This stage examines how visibly DH-related vocabulary appears in selected English literary studies, critical theory, digital humanities, and comparison journals. The aim is not to count actual DH practice articles directly, but to create a metadata-level screening measure of DH visibility across journals.

### Data source

OpenAlex Works API was used to retrieve article metadata for selected journals from 2000 to 2025. Journal retrieval was based on ISSN / OpenAlex source matching. For each retrieved work, the title and reconstructed abstract were searched locally.

### Search design

The search did not rely on OpenAlex’s general search function. Instead, metadata was retrieved first, and then title and abstract fields were searched locally using exact phrase and word-boundary matching.

Two types of counts were separated:

| Measure                   | Meaning                                                                                                          |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `dh_articles`             | Number of deduplicated article records containing at least one strong DH-related term                            |
| `dh_term_occurrences`     | Total occurrences of strong DH-related terms, including multiple terms or repeated terms within the same article |
| `review_only_articles`    | Records containing broader digitization/archive/database terms, excluded from the main DH count                  |
| `review_only_occurrences` | Total occurrences of those review-only terms                                                                     |

Strong DH-related terms included:

* digital humanities
* distant reading
* computational literary studies
* computational literary criticism
* cultural analytics
* macroanalysis
* stylometry
* topic modeling
* text mining
* word embedding

Broader digitization- or archive-related terms, such as “digitization,” “digital archive,” “digitized books,” “database,” and “electronic text,” were not included in the main count. They were recorded separately as review-only signals, because they may refer to digital resources or book digitization rather than computational literary analysis.

### Output files

| File                                                                      | Content                                  |
| ------------------------------------------------------------------------- | ---------------------------------------- |
| `derived/dh_reception/openalex_dh_article_hits_2000_2025.tsv`             | Article-level DH and review-only signals |
| `derived/dh_reception/openalex_dh_term_hits_2000_2025.tsv`                | Term-level hit records                   |
| `derived/dh_reception/openalex_dh_journal_summary_2000_2025.tsv`          | Journal-level summary                    |
| `derived/dh_reception/openalex_dh_term_summary_2000_2025.tsv`             | Strong DH term summary by journal        |
| `derived/dh_reception/openalex_dh_review_only_term_summary_2000_2025.tsv` | Review-only term summary by journal      |
| `derived/dh_reception/openalex_dh_year_summary_2000_2025.tsv`             | Year-level summary by journal            |

### Journal-level results

| Group               |                                    Journal | Total records | DH articles | DH article rate | DH term occurrences | Review-only articles |
| ------------------- | -----------------------------------------: | ------------: | ----------: | --------------: | ------------------: | -------------------: |
| Comparanda          |                 American Historical Review |        31,031 |          19 |           0.06% |                  24 |                   56 |
| Comparanda          |                         Cultural Analytics |           211 |          57 |          27.01% |                  98 |                   13 |
| Comparanda          |      Digital Scholarship in the Humanities |         1,134 |         329 |          29.01% |                 685 |                  121 |
| Comparanda          |                         History and Theory |         1,266 |           0 |           0.00% |                   0 |                    3 |
| Literary / critical |                           Critical Inquiry |         2,151 |           7 |           0.33% |                  10 |                    5 |
| Literary / critical |                                        ELH |         1,092 |           6 |           0.55% |                  15 |                    2 |
| Literary / critical |               Journal of Modern Literature |         1,668 |           2 |           0.12% |                   4 |                    2 |
| Literary / critical |                           Modern Philology |         2,646 |          12 |           0.45% |                  14 |                   18 |
| Literary / critical |                        Modernism/modernity |         2,300 |           2 |           0.09% |                   2 |                    7 |
| Literary / critical |                       New Literary History |         1,264 |          18 |           1.42% |                  28 |                    3 |
| Literary / critical |                                      Novel |         1,092 |          11 |           1.01% |                  31 |                    6 |
| Literary / critical |                                       PMLA |         4,964 |          39 |           0.79% |                  86 |                   20 |
| Specialist          | English Literature in Transition 1880–1920 |           445 |           0 |           0.00% |                   0 |                    0 |
| Specialist          |                      James Joyce Quarterly |         1,467 |          11 |           0.75% |                  15 |                   11 |
| Specialist          |                      Shakespeare Quarterly |         1,530 |           2 |           0.13% |                   3 |                    3 |
| Specialist          |                          Victorian Studies |         5,174 |          29 |           0.56% |                  55 |                   34 |

### Interpretation

The results show a clear contrast between DH-specialist journals and mainstream literary-critical journals. Cultural Analytics and Digital Scholarship in the Humanities show high DH signal rates, as expected. In contrast, major English literary and critical journals show much lower rates: PMLA has 39 DH-signal records out of 4,964 total records; Critical Inquiry has 7 out of 2,151; ELH has 6 out of 1,092; and Modernism/modernity has only 2 out of 2,300.

This supports the working hypothesis that DH is institutionally visible as a field, but its explicit uptake in mainstream English literary criticism remains limited and uneven. However, these figures should not be read as direct counts of DH practice articles. They are metadata-level signals based on title and abstract vocabulary.

### Term-level observations

In mainstream literary-critical journals, the most common signals are “digital humanities” and “distant reading,” rather than more technical method terms. PMLA shows 39 DH-signal records, with notable concentration around “digital humanities” and “distant reading.” New Literary History and Novel also show signals around distant reading, computational literary studies, and related debates. Critical Inquiry contains only a small number of DH-related signals, including “computational literary studies,” “digital humanities,” and “distant reading.”

In the comparison journals, Digital Scholarship in the Humanities and Cultural Analytics show much higher term frequency and broader method vocabulary, including “topic modeling,” “stylometry,” “text mining,” “word embedding,” and “cultural analytics.”

### Known limitations

1. The scan is based on OpenAlex metadata, not full-text journal content.
2. Abstract availability is uneven across journals and years.
3. OpenAlex record types include articles, book reviews, editorial material, and other records unless filtered further.
4. Some DH-signal records are book reviews or forum pieces rather than research articles.
5. Some records appear duplicated or near-duplicated in the hit list and require further deduplication by title, year, DOI, and OpenAlex work ID.
6. “Digital humanities” can appear as a field label or review topic without indicating actual computational method use.
7. The figures should therefore be treated as upper-bound metadata signals, not as direct counts of DH practice.

### Next steps

* Deduplicate records by journal, year, normalized title, and DOI.
* Separate research articles from book reviews, introductions, responses, and forum pieces where possible.
* Manually classify a sample of hits in PMLA, Critical Inquiry, New Literary History, Novel, and Victorian Studies into:

  * actual computational/DH method use
  * meta-discussion of DH
  * review or mention only
* Compare 2000–2025 overall with a recent-window subset, especially 2016–2025.
* Use this screening as the basis for revising the KCL presentation slides on DH visibility in English literary studies.

### Status

Status: completed as first-pass OpenAlex metadata screening.
Use in presentation: yes, with explicit qualification as metadata-level signal counts rather than direct counts of DH practice articles.

### Review queue and LLM-assisted classification

Because the first-pass OpenAlex scan retrieves metadata records rather than a clean set of research articles, a review queue was created to identify records that required further classification.

The review queue flags three issues:

1. possible book reviews or review essays;
2. duplicated or near-duplicated records;
3. DH-signal records whose meaning cannot be determined from keyword presence alone.

This step is necessary because the first-pass DH signal count is intentionally an upper-bound metadata measure. It identifies where DH/CLS-related vocabulary appears, but it does not directly count actual DH practice articles.

#### Review queue outputs

| File                                                                            | Content                                                                         |
| ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `derived/dh_reception/openalex_dh_manual_review_queue_2000_2025.tsv`            | Review queue for all DH-signal records                                          |
| `derived/dh_reception/openalex_dh_article_hits_provisional_clean_2000_2025.tsv` | Provisional file excluding obvious review and duplicate candidates              |
| `derived/dh_reception/openalex_dh_review_queue_summary_2000_2025.tsv`           | Journal-level summary of review and duplicate candidates                        |
| `derived/dh_reception/openalex_dh_manual_review_core_litcrit_2000_2025.tsv`     | Follow-up set of 77 DH-signal records from five core literary-critical journals |

The core follow-up set consists of records from five literary-critical journals:

* `PMLA`
* `New Literary History`
* `Novel`
* `Critical Inquiry`
* `Modernism/modernity`

The initial core set contained 77 DH-signal records:

| Journal              | Records |
| -------------------- | ------: |
| PMLA                 |      39 |
| New Literary History |      18 |
| Novel                |      11 |
| Critical Inquiry     |       7 |
| Modernism/modernity  |       2 |
| Total                |      77 |


### Review queue

Because the first-pass OpenAlex scan retrieves metadata records rather than a clean set of research articles, a review queue was created to flag possible book reviews, duplicated records, and ambiguous DH-signal records.

This confirmed that the first-pass DH signal count should be treated as an upper-bound metadata measure. Several journals contain book reviews, review essays, duplicated records, or records with missing titles. The queue was therefore used to construct a core follow-up set for LLM-assisted classification.

Output files:

| File | Content |
|---|---|
| `derived/dh_reception/openalex_dh_manual_review_queue_2000_2025.tsv` | Review queue for all DH-signal records |
| `derived/dh_reception/openalex_dh_article_hits_provisional_clean_2000_2025.tsv` | Provisional file excluding obvious review and duplicate candidates |
| `derived/dh_reception/openalex_dh_review_queue_summary_2000_2025.tsv` | Journal-level summary of review and duplicate candidates |
| `derived/dh_reception/openalex_dh_manual_review_core_litcrit_2000_2025.tsv` | Core follow-up set of 77 DH-signal records from five literary-critical journals |



#### LLM-assisted classification design

The 77 core records were classified using the OpenAI API. The script used was:

| Script                                       | Purpose                                                                |
| -------------------------------------------- | ---------------------------------------------------------------------- |
| `scripts/classify_dh_core_litcrit_openai.py` | Classify core literary-critical DH-signal records using the OpenAI API |

The script reported the model as:

| Model     | Use                                              |
| --------- | ------------------------------------------------ |
| `gpt-5.5` | LLM-assisted classification of DH-signal records |

For each record, the classifier received the following information:

* journal;
* year;
* title;
* matched DH/CLS terms;
* DH term occurrences;
* review priority;
* review candidate reason;
* duplicate count;
* DOI;
* OpenAlex work ID;
* reconstructed abstract, when available.

The classifier assigned one of the following labels:

| Label               | Meaning                                                                                                                                                                             |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `method_use`        | The article appears to use computational, quantitative, digital, or DH/CLS methods as part of its own scholarly argument                                                            |
| `meta_discussion`   | The article primarily discusses DH, CLS, scale, method debates, disciplinary debates, or the limits of computational approaches, without clearly being a computational study itself |
| `review_or_mention` | The record is likely a book review, review essay, introduction, response, forum item, editorial, or passing mention                                                                 |
| `false_positive`    | The keyword match does not actually indicate DH/CLS relevance                                                                                                                       |
| `uncertain`         | There is not enough information in the metadata to classify confidently                                                                                                             |

The output was constrained to a fixed JSON structure including:

* classification label;
* confidence score;
* short reason;
* evidence phrase;
* human-check flag.

#### LLM classification outputs

| File                                                                                    | Content                                              |
| --------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `derived/dh_reception/openalex_abstract_cache_core_litcrit_2000_2025.jsonl`             | Cached OpenAlex metadata and reconstructed abstracts |
| `derived/dh_reception/openalex_dh_llm_classified_core_litcrit_2000_2025.tsv`            | Raw LLM-classified output for 77 core records        |
| `derived/dh_reception/openalex_dh_llm_class_summary_core_litcrit_2000_2025.tsv`         | Raw journal-level classification summary             |
| `derived/dh_reception/openalex_dh_llm_classified_core_litcrit_deduped_2000_2025.tsv`    | Deduplicated LLM-classified output                   |
| `derived/dh_reception/openalex_dh_llm_class_summary_core_litcrit_deduped_2000_2025.tsv` | Deduplicated journal-level classification summary    |

#### Raw classification result

Before deduplication, the 77 records were classified as follows:

| Classification      | Records |  Share |
| ------------------- | ------: | -----: |
| `method_use`        |       9 |  11.7% |
| `meta_discussion`   |      46 |  59.7% |
| `review_or_mention` |      22 |  28.6% |
| Total               |      77 | 100.0% |

Journal-level raw result:

| Journal              | Method use | Meta-discussion | Review / mention |
| -------------------- | ---------: | --------------: | ---------------: |
| Critical Inquiry     |          1 |               5 |                1 |
| Modernism/modernity  |          0 |               1 |                1 |
| New Literary History |          4 |              10 |                4 |
| Novel                |          0 |               0 |               11 |
| PMLA                 |          4 |              30 |                5 |

The classifier marked 75 records as not requiring human check and 2 records as requiring human check. However, low-confidence cases were also inspected separately.

#### Low-confidence / check cases

The following five records had either `llm_needs_human_check = True` or confidence below 0.75:

| Journal              | Year | Title                                                                | LLM class           | Confidence |
| -------------------- | ---: | -------------------------------------------------------------------- | ------------------- | ---------: |
| New Literary History | 2015 | The Bechdel Test and the Social Form of Character Networks           | `meta_discussion`   |       0.72 |
| Novel                | 2021 | Keywords, Structures of Feeling, and the Novel                       | `review_or_mention` |       0.68 |
| PMLA                 | 2016 | Talking French                                                       | `meta_discussion`   |       0.72 |
| PMLA                 | 2017 | On Disciplinary Finitude                                             | `review_or_mention` |       0.62 |
| PMLA                 | 2020 | Picture This: The Screenshot's Use in Digital Humanities Scholarship | `meta_discussion`   |       0.72 |

These records should be treated as borderline cases if the classification is used for publication. For the KCL presentation, they are acceptable as part of an explicitly LLM-assisted exploratory classification.

#### Deduplicated classification result

A further deduplication step was applied using journal, year, and normalized title. This removed two duplicated records, reducing the core set from 77 to 75 records.

After deduplication, the classification result was:

| Classification      | Records |  Share |
| ------------------- | ------: | -----: |
| `method_use`        |       9 |  12.0% |
| `meta_discussion`   |      45 |  60.0% |
| `review_or_mention` |      21 |  28.0% |
| Total               |      75 | 100.0% |

Deduplicated journal-level result:

| Journal              | Method use | Meta-discussion | Review / mention | Total |
| -------------------- | ---------: | --------------: | ---------------: | ----: |
| Critical Inquiry     |          1 |               4 |                1 |     6 |
| Modernism/modernity  |          0 |               1 |                1 |     2 |
| New Literary History |          4 |              10 |                4 |    18 |
| Novel                |          0 |               0 |               11 |    11 |
| PMLA                 |          4 |              30 |                4 |    38 |
| Total                |          9 |              45 |               21 |    75 |

#### Method-use cases

The nine deduplicated `method_use` cases were:

| Journal              | Year | Title                                                                                                 | Matched term(s)                  |
| -------------------- | ---: | ----------------------------------------------------------------------------------------------------- | -------------------------------- |
| Critical Inquiry     | 2023 | #COVID, Crisis, and the Search for Story in the Platform Age                                          | distant reading                  |
| New Literary History | 2017 | Distributed Character: Quantitative Models of the English Stage, 1550–1900                            | digital humanities               |
| New Literary History | 2021 | The Scale of Genre                                                                                    | digital humanities               |
| New Literary History | 2022 | A Queer Way of Counting: Bibliography and Computational Approaches to the Queer Novel                 | text mining                      |
| New Literary History | 2022 | Content's Forms                                                                                       | computational literary criticism |
| PMLA                 | 2020 | Anthropocene and Empire: Discourse Networks of the Human Record                                       | digital humanities               |
| PMLA                 | 2020 | Dimensions of Scale: Invisible Labor, Editorial Work, and the Future of Quantitative Literary Studies | topic modeling                   |
| PMLA                 | 2020 | Race and Distant Reading                                                                              | distant reading                  |
| PMLA                 | 2020 | The Experimental Turn                                                                                 | digital humanities               |

These cases include distant reading, quantitative character-network analysis, computational bibliography, text mining, topic modeling, large-scale database analysis, and visualization-based analysis.

#### Interpretation

The LLM-assisted classification confirms that explicit DH/CLS vocabulary in core literary-critical journals does not usually indicate actual DH method use.

Among the 75 deduplicated DH-signal records from five core literary-critical journals, only 9 were classified as `method_use`. Most were classified as `meta_discussion`, and a substantial number were classified as `review_or_mention`.

This suggests that, in mainstream literary-critical venues, DH often becomes visible as a topic of methodological debate, disciplinary reflection, or review discourse rather than as routine computational practice.

The result is especially clear in Critical Inquiry and Novel:

* Critical Inquiry contains a small number of DH-signal records, most of which are meta-discussions rather than method-use articles.
* Novel contains 11 DH-signal records, all classified as review or mention, indicating that DH-related vocabulary often appears there through reviews of DH-adjacent books rather than through DH method articles.

For the KCL presentation, this classification supports the following claim:

> Explicit DH/CLS vocabulary remains rare in mainstream literary-critical journals. Even when it appears, it is more often part of methodological debate, disciplinary reflection, or review discourse than evidence of routine DH method use.

#### Presentation use

Use the deduplicated classification result for slides:

| Category         | Records | Share |
| ---------------- | ------: | ----: |
| Method use       |       9 | 12.0% |
| Meta-discussion  |      45 | 60.0% |
| Review / mention |      21 | 28.0% |

Recommended slide wording:

> The map of DH visibility changes once the DH-signal records are classified. In five core literary-critical journals, only 9 of 75 records were classified as actual method use. Most were meta-discussion or review/mention. This suggests that DH is visible in these venues less as ordinary research practice than as a topic of methodological debate, disciplinary reflection, or review discourse.

#### Status

Status: completed as LLM-assisted exploratory classification.

Use in presentation: yes, with clear qualification.

Important qualification: these are LLM-assisted interpretive labels based on OpenAlex metadata and reconstructed abstracts. They are not final human-coded classifications.

作成日：2026-06-13

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
---

## Stage 8a: OpenAlex DH Keyword Search 再取得 — 2026-05-31

### 目的

英文学・批評系ジャーナル、時代別専門誌、DH系比較対象誌、歴史学系比較対象誌において、DH関連語が2016–2025年のOpenAlex収録論文にどの程度出現するかを、同一条件で再取得した。

この調査は、DH実践論文数を直接数えるものではない。OpenAlex検索におけるDH関連語の上限ヒット数を確認するための補助的調査である。

### 位置づけ

本節の数値は、Stage 8の旧「DHキーワード検索・総件数」表の再取得版である。

旧Stage 8では、複数キーワードをまとめて検索した結果や、個別確認に基づく暫定的評価が混在していた。今回の再取得では、以下の点を統一した。

* 期間を2016–2025に固定
* 各誌ごとに総件数を再取得
* キーワードごとにOpenAlex APIで検索
* 各誌内でOpenAlex work idにより重複除去
* summary、detail、HTML貼り付け用行、metadataを保存

### 実行スクリプト

```bash
scripts/save_openalex_dh_keyword_search.py
```

### 出力ファイル

| ファイル                                                             | 内容                                                                      |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `derived/dh_reception/openalex_dh_keyword_summary_2016_2025.tsv` | 雑誌別の総件数、重複除去後ヒット数、割合、キーワード別raw count                                    |
| `derived/dh_reception/openalex_dh_keyword_hits_2016_2025.tsv`    | ヒットした個別work一覧。journal, year, type, title, doi, keywords, openalex_idを含む |
| `derived/dh_reception/openalex_dh_keyword_summary_rows.html`     | スライドHTMLに貼るための`<tr>`行                                                   |
| `derived/dh_reception/openalex_dh_keyword_search_metadata.json`  | 実行条件、検索語、対象誌、出力先を記録したmetadata                                           |

### 検索条件

| 項目         | 内容                                                               |
| ---------- | ---------------------------------------------------------------- |
| API        | OpenAlex Works API                                               |
| 期間         | 2016–2025                                                        |
| フィルタ       | `primary_location.source.issn:{issn},publication_year:2016-2025` |
| 検索方法       | 各キーワードを`search=`で個別検索                                            |
| 取得項目       | `id,title,publication_year,type,doi`                             |
| ページング      | cursor paging, `per-page=200`                                    |
| 重複除去       | 各誌内でOpenAlex work idにより重複除去                                      |
| User-Agent | `haruka0221@canon-pipeline`                                      |

### 検索語

```text
digital humanities
distant reading
computational literary
text mining
stylometry
topic model
```

注：この検索語セットは、DH/CLS実践の直接検出ではなく、DH関連語の出現を拾うための上限検索である。書評、特集号、広義の理論的言及、一般語的用法を含む可能性がある。

### 対象誌と再取得結果

| ジャーナル                                      | ISSN      | 位置づけ             |   総件数 | 重複除去後ヒット | 表示用             |
| ------------------------------------------ | --------- | ---------------- | ----: | -------: | --------------- |
| PMLA                                       | 0030-8129 | 英文学・MLA          | 1,203 |      100 | 100/1203 = 8.3% |
| ELH                                        | 0013-8304 | 英文学              |   424 |       42 | 42/424 = 9.9%   |
| Novel                                      | 0029-5132 | 小説研究             |   413 |       47 | 47/413 = 11.4%  |
| Critical Inquiry                           | 0093-1896 | 批評理論             |   945 |       27 | 27/945 = 2.9%   |
| Modernism/modernity                        | 1071-6068 | モダニズム            |   723 |       36 | 36/723 = 5.0%   |
| Journal of Modern Literature               | 0022-281X | 20世紀文学           |   618 |        9 | 9/618 = 1.5%    |
| Shakespeare Quarterly                      | 0037-3222 | 近世               |   427 |        5 | 5/427 = 1.2%    |
| Victorian Studies                          | 0042-5222 | ヴィクトリア朝          | 1,707 |       62 | 62/1707 = 3.6%  |
| James Joyce Quarterly | 0021-4183 | 作家別：Joyce | 531 | 19 | 19/531 = 3.6% |
| English Literature in Transition 1880–1920 | 0013-8339 | 後期ヴィクトリア朝〜20世紀初頭 |    50 |        0 | 0/50 = 0.0%     |
| Cultural Analytics                         | 2371-4549 | 比較：計量・DH系        |   211 |      143 | 143/211 = 67.8% |
| Digital Scholarship in the Humanities      | 2055-7671 | 比較：DH専門誌         |   954 |      430 | 430/954 = 45.1% |
| American Historical Review                 | 0002-8762 | 比較：歴史学           | 8,125 |       56 | 56/8125 = 0.7%  |

### キーワード別raw count

| ジャーナル                                      | digital humanities | distant reading | computational literary | text mining | stylometry | topic model |
| ------------------------------------------ | -----------------: | --------------: | ---------------------: | ----------: | ---------: | ----------: |
| PMLA                                       |                 58 |              39 |                     12 |          10 |          0 |          27 |
| ELH                                        |                  4 |              18 |                      4 |           4 |          0 |          23 |
| Novel                                      |                  7 |              23 |                      9 |           2 |          1 |          18 |
| Critical Inquiry                           |                  9 |              11 |                      6 |           1 |          1 |           9 |
| Modernism/modernity                        |                  6 |              15 |                      3 |           5 |          0 |          15 |
| Journal of Modern Literature               |                  2 |               1 |                      1 |           0 |          0 |           5 |
| Shakespeare Quarterly                      |                  1 |               4 |                      1 |           2 |          0 |           2 |
| Victorian Studies                          |                 13 |              28 |                      2 |           6 |          0 |          24 |
| James Joyce Quarterly | 8 | 8 | 2 | 1 | 0 | 5 |
| English Literature in Transition 1880–1920 |                  0 |               0 |                      0 |           0 |          0 |           0 |
| Cultural Analytics                         |                108 |              65 |                    100 |          43 |          9 |          82 |
| Digital Scholarship in the Humanities      |                339 |              61 |                    118 |          79 |         53 |         127 |
| American Historical Review                 |                 21 |               9 |                      3 |           6 |          0 |          25 |

注：raw countはキーワード別の件数であり、同一論文が複数キーワードにヒットするため、単純合計は重複除去後ヒット数と一致しない。

### 解釈上の注意

この表は、DH関連語のOpenAlex検索上限値を示すものであり、DH実践論文数ではない。

とくに以下の混入を含みうる。

* 書評
* 特集号の導入・周辺記事
* DHやCLSを批判的に論じる論文
* “distant reading” や “topic model” の広義・一般語的用法
* 計算論的実践ではない理論的言及
* OpenAlex側のmetadataや検索仕様に由来するノイズ

したがって、論文本文では、この値を「DH実践率」として使ってはならない。「OpenAlex検索上のDH関連語上限ヒット率」または「DH関連語の可視性」として扱うこと。

### スライド用の短い注記

```text
OpenAlex APIで2016–2025年の各誌を検索。検索語は digital humanities / distant reading / computational literary / text mining / stylometry / topic model。各キーワードの検索結果をOpenAlex work idで重複除去した上限値であり、DH実践論文数ではない。
```

### 旧Stage 8との関係

* 旧Stage 8の「専門誌：全誌で実践論文ほぼゼロ」表は、目視確認や旧キーワード条件に基づく暫定評価を含む。
* 本節の表は、OpenAlex APIによる再取得値であり、対象12誌の検索条件を揃えた最新版である。
* Critical InquiryのPDF直接スキャン結果、PMLAの特集号効果、プロキシ被引用チェック、強シグナル確認は別手法として引き続き保持する。
* 今後、各誌のヒット一覧を目視分類する場合は、`openalex_dh_keyword_hits_2016_2025.tsv`を使用する。
