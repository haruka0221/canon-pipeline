# OpenAlex 取得・LLM作品帰属判定 — 2026-11-06引き継ぎ

状態：本番判定の保存と件数・ID・ラベル検査は完了。「全学術文献の人手確認」や「学術的可視性の確定」は未了。

## 1. 基盤と単位

- リポジトリ：`haruka0221/canon-pipeline`、作業ブランチ：`openalex-r2a1-production-20261021`、サーバー：`~/canon-pipeline-openalex-a2val`、仮想環境：`~/venvs/canon`。
- 文献メタデータは2026-09-23版OpenAlex Worksスナップショット。既存のR2/R3 scan・registry・hit evidenceからR2+A1候補を構築した。今回の本番LLM処理は、その既存候補の作品帰属を判定したもので、OpenAlex APIに対する新たな全件検索ではない。
- 母集団出発点：Open Library source Work 34,789レコード。現行active Project W 32,066（identity v7）。source entity E、Project W、OpenAlex Work ID、検索クエリは別。
- 作品帰属判定の単位：`(project_work_id, openalex_work_id)`。凍結モデル `gpt-6-luna`／identity-aware prompt／structured output schema／Open Library・Wikidata書誌証拠／OpenAlexタイトル・抄録・年・DOI等を使用。
- 出力ラベル：`VALID_TARGET_REFERENCE`、`INVALID_TARGET_REFERENCE`、`UNCERTAIN`。reason code・confidence・identity-context adequacyも保存。作品の原語・初刊年・ジャンル、OpenAlex文献の学術性、言及の質、retrieval recallを今回のラベルで判定してはいない。

## 2. 本番キューの定義

| 層 | ペア数 |
| --- | ---: |
| 統合v2のR2+A1 `INCLUDE_BASELINE_UNADJUDICATED` | 224,830 |
| 既往の評価済み候補を除外 | 855 |
| 既往パイロットを除外 | 100 |
| 独立サンプリングフレーム | 223,875 |
| developmentとして別に確保 | 160（無作為120＋題名リスク40） |
| blind holdoutとして別に確保 | 600 |
| 本番判定対象 | 223,115 |

根拠・抽出手続き：`docs/OPENALEX_R2A1_CHECKPOINT_2026-10-21.md`。この223,115ペアは統合OpenAlex全経路の総数ではなく、評価済み・holdoutを除いたR2+A1の本番部分。

## 3. 独立検証の記録

- Development 160モデル出力：VALID95／INVALID49／UNCERTAIN16。リスク富化のため母集団比率ではない。
- Developmentの人手40ケース：3クラス完全一致36/40。独立した母集団精度評価ではない。
- 独立holdout 600件：モデル推論保存済み。最初の200件は研究者が独立盲検で判定。残り400件のモデル予測は、人間が盲検レビューを終えるまで封印を維持し、表示・再利用・Git追加しない。
- 人手200件：VALID156／INVALID25／UNCERTAIN19。モデル：VALID156／INVALID32／UNCERTAIN12。3クラス一致181/200。
- モデルVALID156件中、人手VALID154件、INVALID2件：154/156＝98.72%。これはこの標本での対象作品帰属の確認結果であり、全研究文献の妥当性・学術性・検索網羅率を表さない。人手UNCERTAINやpost-unblinding診断も原goldに上書きしない。

## 4. 本番実行と完了確認（2026-11-05）

- 初回1,000件はbatch0000に保存し凍結。後続batch0001〜0223は222,115件。batch0010の最初の100件はBatch API試験で正常に取り込み、残りは同期runnerで既存保存IDをスキップして処理した。Batch APIと同期runnerを同時に同一checkpointへ書き込まない。
- 依存スクリプト：`scripts/run_openalex_r2a1_production_first_1000_v0_1.py`（サーバーの `git status --short` で未追跡と表示されたため、Gitに保存済みだと決めつけない）、`scripts/run_openalex_r2a1_production_continue_v0_2.py`、`scripts/run_openalex_r2a1_production_batch_api_v0_1.py`。
- 本番保存先：`derived/openalex_production/retrieval_r2a1_production_identity_aware_v0_1/`。キュー／run config／prompt・schema hash／候補別入力／結果JSONL／Batch APIログ等の来歴を保持すること。
- ユーザー実行のstatus出力：`Continuation total: 222115 saved; with frozen first 1000: 223115`。最終batch0223は115/115。
- 別の読み取り専用QCで全224バッチの件数、候補ID一意性、ordinal一意性と0..223114の連続性、3ラベルの妥当性を検証：`QC: PASSED`。この検査は本文帰属の正確さを人間が全件認定した意味ではない。
- OpenAlex用tmux `openalex-all` は終了コマンド `tmux kill-session -t openalex-all` を実行済み。他のBritish Library取得ジョブは別物。

### 本番モデル判定（223,115ペア）

| LLMラベル | 件数 | 割合 |
| --- | ---: | ---: |
| VALID_TARGET_REFERENCE | 170,791 | 76.55% |
| INVALID_TARGET_REFERENCE | 42,351 | 18.98% |
| UNCERTAIN | 9,973 | 4.47% |

本番候補が存在するProject Wは6,793。主要reason：DIRECT_TARGET_REFERENCE 142,443；VALID_CONTEXTUAL_REFERENCE 23,233；WRONG_WORK_SAME_AUTHOR 16,321；TITLE_AUTHOR_UNLINKED_COOCCURRENCE 9,115；OTHER 7,466；GENERIC_OR_LEXICAL_TITLE_USE 6,237；INSUFFICIENT_CONTEXT 5,521；VALID_TITLE_VARIANT 5,115；AMBIGUOUS_TARGET_REFERENCE 4,452；TITLE_COLLISION_DIFFERENT_WORK 1,498；METADATA_TEXT_ARTIFACT 1,055；AUTHOR_COLLISION_DIFFERENT_PERSON 633；ALIAS_NOT_TARGET_EQUIVALENT 26。reasonは学術的適格性を表す分類ではない。

## 5. 統合v3との境界

- 凍結済み統合v2：291,859候補ペア、運用採用226,221。
- 本番223,115のcandidate ID・Project W・OpenAlex IDを一対一で照合してv2にモデル結果をoverlay。
- v3暫定採用＝173,897＝170,791モデルVALID＋3,106の既存v2運用採用（本番モデル以外のhuman/A2/alias/policy由来など）。3,106を一律「人手VALID」「未判定」とは言わない。
- モデルINVALID 42,351をv3採用から除外、UNCERTAIN 9,973を保留。元v2、原human、封印holdoutは保持。
- 実行済みbuilder：`scripts/build_openalex_r2a1_visibility_v3_provisional.py`。v3出力：`derived/openalex_production/integrated_work_visibility_v3_r2a1_model_provisional/`。ユーザーが `QC: PASSED; NO API CALLS; v2 and holdout unchanged` を確認。
- これは最終的な「173,897件の学術的引用」ではなく、帰属を暫定選別したWork×OpenAlex文献候補ペア。

## 6. 引き継ぐ際のコマンドと保全

~~~bash
cd ~/canon-pipeline-openalex-a2val
source ~/venvs/canon/bin/activate
git status --short --branch
git log -1 --oneline
python -B scripts/run_openalex_r2a1_production_continue_v0_2.py \
  --start-batch 1 --end-batch 223 | tail -n 5
~~~

statusに `--execute` は不要。全件の再推論を実行しない。サーバーの本番JSONL、未追跡runner、封印holdout等の安全なバックアップは別途点検が必要。`git add -A` で巨大／未公開生データ・credential等を一括コミットしない。

関連：`docs/OPENALEX_2026-11-06_DEFERRED_QC_AND_DECISIONS.md`、`docs/VISIBILITY_2026-11-06_ANALYSIS_LOG_AND_METHODS.md`。
