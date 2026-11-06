# 文学的可視性：探索的分析の実行記録・現在の方法（2026-11-06）

状態：WORK LOG / EXPLORATORY。これはOpenAlexの「取得・LLM帰属判定」文書とは別の分析記録。ここまでの数字はユーザーが2026-11-05〜06に提示したサーバーのQC出力で確認できる範囲に限る。主分析scopeと学術的適格性を人間が確定した最終版ではない。

## 1. 何を「可視性」と数えているか

現行のOpenAlex指標は、文学作品を表すProject Wに帰属できる可能性があるOpenAlex文献IDの件数。計数単位は一意の`(project_work_id, openalex_work_id)`ペア。「その作品への引用回数」「論文の中で論じられた強さ」「本文の言及箇所数」「真に学術的な文献数」「正典性」ではない。

OpenAlexの研究上の可視性、Goodreadsの読者からの注目、Open Libraryの版レコードによる出版流通、教育の収録、保存を分離したうえで比較する。外部source IDや元のOpen Library Workを自動的にconceptual Wと同一視しない。

## 2. 実行済みの分析と生成ディレクトリ

| 処理・コード | サーバーで確認した結果 | 生成先（すべて `derived/openalex_production/` 以下） |
| --- | --- | --- |
| `build_openalex_r2a1_visibility_v3_provisional.py` | v2 226,221→v3 173,897、QC PASS | `integrated_work_visibility_v3_r2a1_model_provisional/` |
| `analyze_openalex_visibility_v3_provisional_v0_1.py` | W数6,816、unique OA ID129,628、24,001 IDが複数Wと関連、QC PASS | `analysis_v3_provisional_diagnostics_v0_1/` |
| `audit_openalex_shared_r2_query_identity_risk_v0_1.py` | 同一R2 title+author群833、1,799W、QC PASS | `analysis_v3_shared_r2_query_identity_risk_v0_1/` |
| `analyze_openalex_v3_top2_identity_sensitivity_v0_1.py` | 3通りのW単位集計感度、QC PASS | `analysis_v3_top2_identity_sensitivity_v0_1/` |
| `analyze_openalex_v3_document_types_v0_1.py` | 全173,897ペアのOpenAlex type join成功、QC PASS | `analysis_v3_openalex_document_type_exploratory_v0_1/` |
| `analyze_openalex_v3_visibility_lenses_scope_bridge_v0_1.py` | 32,066Wのscope書誌証拠join、3 lenses×2 scenarios、QC PASS | `analysis_v3_visibility_lenses_scope_bridge_v0_1/` |

上記の分析は元v2/v3、human、holdout、identityを直接書き換えず、新たなディレクトリとSHA-256入力・出力manifestに記録。初回のR2クエリ診断は元OL populationの相対パス違いで停止したが、修正後の実行がPASSした。

## 3. v3の暫定作品別分布

- v2の運用採用226,221ペア。223,115本番LLMラベルをoverlayし、モデルINVALID42,351を除外、UNCERTAIN9,973を保留。
- v3運用上の暫定採用173,897＝モデルVALID170,791＋モデル本番以外の既存採用3,106。
- 32,066 active Wのうち6,816 Wにv3暫定採用候補が1件以上。
- v3採用173,897 W×OAペアに対しOA Work IDは129,628種類。24,001 IDは複数のWに結びつき、そのようなOA ID上の採用ペアは68,270（全体の39.3%）。
- これは同一の学術文献が複数作品を論じる場合も含むため、39.3%は誤一致率ではない。

### 同一クエリの重複と感度

- 同じ正規化R2タイトル＋著者クエリを複数のProject Wで使用：833グループ、1,799W。
- `Ulysses` / James Joyce：3 Wの暫定採用計13,202ペア、ユニークOA ID union4,423、重複配置8,779。
- `Heart of Darkness` / Joseph Conrad：4 Wの重複配置5,851。多作品収録物を示すOL Workもある可能性、identity同一の確定ではない。
- 上位2群のみ`SENS_`の仮説的作品単位に置き換える感度分析を実施。これは書誌的identity決定ではなく、元W集計と並記するシナリオ。

| 分析単位 | 全type候補ペア | top10集中度 | top100集中度 |
| --- | ---: | ---: | ---: |
| 現行v3 W | 173,897 | 16.1% | 48.9% |
| Ulysses 3Wのみ仮union | 165,118 | 13.9% | 46.5% |
| Ulysses・Heart of Darkness両群を仮union | 159,267 | 13.5% | 45.1% |

## 4. OpenAlex文献typeの全件結合

OpenAlexの既存スナップショットmetadataへのjoin：129,628/129,628 distinct OA ID、173,897/173,897 candidate pairs、欠損なし。

| OA type | W×OAペア |
| --- | ---: |
| article | 103,547 |
| dissertation | 22,315 |
| book-chapter | 20,862 |
| book | 9,617 |
| other | 6,737 |
| book-review | 3,377 |
| 上記以外の全type | 7,442 |

`CORE3`＝article＋book-chapter＋dissertation＝146,724（84.4%）。学術文献の暫定proxyであって、研究書等の`book`や書評を自動的に無価値とする判断ではない。拡張レンズ`EXPANDED_DOCUMENT_TYPES`は article／book-chapter／dissertation／book／conference-paper／preprint／book-review／report。

### 実行済みの6比較（2026-11-05のQC出力）

| 文献レンズ | 集計単位 | 候補ペア | 1件以上のanalysis units | top10 | top100 | 陽性unitの中央値 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| ALL_TYPES | 現行W | 173,897 | 6,816 | 16.098% | 48.875% | 3 |
| ALL_TYPES | 仮union上位2群 | 159,267 | 6,811 | 13.515% | 45.060% | 3 |
| CORE3 | 現行W | 146,724 | 6,252 | 16.432% | 49.777% | 2 |
| CORE3 | 仮union上位2群 | 134,100 | 6,247 | 13.888% | 45.885% | 2 |
| EXPANDED | 現行W | 162,403 | 6,673 | 16.382% | 49.378% | 2 |
| EXPANDED | 仮union上位2群 | 148,447 | 6,668 | 13.789% | 45.477% | 2 |

集中度はscope未限定、候補レベル、かつW分裂に影響される。core3の1件以上あるW数6,252、中央値2件はこの測定単位についての結果。

## 5. 作品名とscope書誌証拠の扱い

- `project_works_v7.tsv` は作品ID・origin entity・status中心のidentity管理表で、題名・著者の列は持たない。表示にはR2 query registryの`query_title`、`query_author`を使用した。これは書誌的に確定した正規表示とは限らない。
- 現在の上位には、主分析scope案（1880–1950年初刊の英語原作の単独長編・中編小説）と関係しない作品、例：`Pride and Prejudice`、`The Waste Land`、`Jane Eyre`、`Death of a Salesman`もある。現行の全Wランキングは主分析母集団の正式なランキングではない。
- `derived/scope/scope_combined_bibliographic_evidence_v0_1/scope_combined_project_w_bibliographic_evidence_v0_1.tsv` を全32,066Wのv3/type表とjoinし、原Open Library Work・歴史的書誌証拠とWikidataのsource-native属性を保った。
- Open Libraryの`first_publish_year`に見える歴史的数値は、関連Editionの最小観測年であり原作初刊年とは限らない。Wikidata P577/P407/P31も人間による原語・年代・形態の確定値へ自動変換しない。
- R2/R3未検索352WとAlcott未再計測1Wは、文献ゼロと区別してNAを保持。厳密なscopeについては2026-11-06時点で研究者の正式全W判定がまだない。

## 6. 現在の「どこまで進んだか」

学術的可視性の候補集計・OpenAlex document typeの分析・上位重複の感度分析・全Wのscope書誌証拠との結合は実行済み。ここまでの6比較が現時点で再現すべき探索的成果。

2026-11-06にGitへ追加した`scripts/analyze_openalex_v3_ol_goodreads_bridge_v0_1.py`は、現行Goodreads crosswalk（MATCH限定）と以前のUCSD数値、Open Library Edition登録数をW単位にjoinし、相関とパーセンタイル乖離を探索するための次工程。ただしこの記録の作成時点で、サーバー実行結果・QC PASS・実際の相関数値はまだ報告されていない。実行前の設計を「完成した研究結果」として書かない。

関連：`docs/VISIBILITY_2026-11-06_NEXT_STEPS.md`、`docs/OPENALEX_2026-11-06_RETRIEVAL_LLM_PRODUCTION_HANDOFF.md`、`docs/OPENALEX_ANALYSIS_SCOPE_DRAFT_v0_1.md`、`docs/OPENALEX_SCOPE_SCREENING_DESIGN_DRAFT_v0_1.md`。
