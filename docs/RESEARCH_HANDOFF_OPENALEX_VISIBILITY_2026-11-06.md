# 引き継ぎ索引：OpenAlex取得・LLM判定と文学的可視性（2026-11-06）

対象リポジトリ：`haruka0221/canon-pipeline`  
現行作業ブランチ：`openalex-r2a1-production-20261021`  
サーバー作業先：`/home/tsutsui/canon-pipeline-openalex-a2val`  
性格：新しいチャット／担当者／作業環境への移行用。記録は完了事実と暫定結果と未実行計画を分けている。

## まず読む順序：4つの独立した記録

1. `OPENALEX_2026-11-06_RETRIEVAL_LLM_PRODUCTION_HANDOFF.md`  
   OpenAlex snapshotとR2+A1 retrievalの位置づけ、freeze済み本番キュー223,115件、モデル評価、推論・保存・検証の実績、v3への接続、サーバー成果物。
2. `OPENALEX_2026-11-06_DEFERRED_QC_AND_DECISIONS.md`  
   本番を先へ進めるために後回しにした検証・未決定事項17件、優先度、判断上の禁則、書誌的同一性・文献適格性・scopeの分離。
3. `VISIBILITY_2026-11-06_ANALYSIS_LOG_AND_METHODS.md`  
   別トラックの「学術的可視性」探索的分析。実行済みv3、文献type分布、shared query／multi-W重複、上位2作品群の感度分析、全W書誌証拠のjoin、6比較の実測値と手法。
4. `VISIBILITY_2026-11-06_NEXT_STEPS.md`  
   これからの実行順、OpenAlex×Open Library Edition×Goodreadsの未実行スクリプト、検証する観測数、異領域比較、scope審査、最終研究分析への移行。

## 現況（2026-11-06時点）

| フェーズ | 状態 | 結果／留意 |
| --- | --- | --- |
| OpenAlex 2026-09-23 snapshot・既存R2/R3 scan | 取得・走査済み | 既存snapshotと実データ・manifestを保持 |
| R2+A1 LLM本番 | 完了、全バッチの保存・ID/ordinal/QC確認 | 223,115件。モデルVALID170,791／INVALID42,351／UNCERTAIN9,973 |
| 600件独立holdout | モデル結果保存、人手先頭200件盲検済み | 残り400件の未開封モデル予測を研究者の今後の盲検評価から隔離 |
| 統合OpenAlex v3 | 実行・QC PASS | v2の226,221採用→v3暫定173,897のW×OA候補。研究文献性は未確定 |
| 文献type・共有文献・W分裂感度分析 | 実行・QC PASS | core3 146,724、query同一833群、6種類の比較集計 |
| 32,066Wのscope書誌証拠join | 実行・QC PASS | source-native OL/Wikidata証拠の結合。正式scope判断は未反映 |
| Goodreads・Open Library Editionとの相関 | 未実行 | スクリプトはGitにあるが、サーバーでの実行結果・実際の相関係数は未報告 |

### 「一つの数」として誤って扱わないこと

- 223,115はR2+A1 production判定対象ペア数、173,897は統合v3暫定採用ペア数、146,724はそのうち`article`＋`book-chapter`＋`dissertation`に分類されたペア数。
- これらは「学術研究での引用数」でも「全文献への実質的言及数」でもない。
- 6,816はv3暫定候補が1件以上あるW数。全active Project Wは32,066。
- 同一queryタイトル・著者833群をすべて同一作品と確定しない。`SENS_`を付けたunionは感度シナリオ。
- 歴史的OL年はEdition由来最小年であって原作初刊年ではない。
- 352のR2/R3未検索W、Alcottの未再計測Wと、調査して0件のWは別。
- Goodreadsで照合できないWは評価数0ではない。古いUCSD ratingsはリアルタイム値ではない。

## さらに古い文書との関係

次の先行文書は置き換えず履歴として保持する。

- `docs/OPENALEX_R2A1_CHECKPOINT_2026-10-21.md`：本番前の候補定義・独立評価・封印holdout・runner設計。
- `docs/OPENALEX_V3_PROVISIONAL_ANALYSIS_CHECKPOINT_2026-11-05.md`：初回のv3分析成果・問題点。
- `docs/OPENALEX_ANALYSIS_SCOPE_DRAFT_v0_1.md`：主分析scope案。
- `docs/OPENALEX_SCOPE_SCREENING_DESIGN_DRAFT_v0_1.md`：AI草稿と正式人手scope判断の分離。
- `WORKFLOW.md`：E/A/W identity、履歴、Git/provenanceの長期規約。

## 引き継ぎ時の作業ルール

1. GitHubに保存したこの文書群が、サーバーに残る未追跡production JSONL／first-1000 runner／封印holdoutをバックアップしたことにはならない。別途所在・hash・保管先を確認する。
2. `git status --short --branch` を先に確認する。巨大・機密ファイルを`git add -A`で取り込まない。
3. 現在のscript・manifest・結果の実物を確認してから新しいコマンドを案内する。過去の出力名を上書きしない。
4. 本番モデルはすでに完了。追加のOpenAI API実行は原則不要。
5. analysis、identity審査、文献type suitability、scope、読者受容・出版流通との比較を、それぞれ独立したversioned成果物で扱う。

## 新しいチャットでの開始例

> canon-pipelineの`docs/RESEARCH_HANDOFF_OPENALEX_VISIBILITY_2026-11-06.md`を入口に、4文書を読んで引き継いでください。OpenAlex R2+A1 LLM本番223,115件は完了、統合v3と可視性の探索的6比較も完了しています。最後に追加したOpenAlex×OL Editions×Goodreads比較スクリプトは実行結果未確認です。凍結結果と封印holdoutを変更せず、未完了事項と新たな分析を別々に進めたいです。

本引き継ぎの数値出典：ユーザー提供のサーバー実行出力、該当Gitコード、versioned集計／manifest。外部学術文献の新たな書誌的主張を追加したものではない。
