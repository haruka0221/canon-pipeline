# OpenAlex R2+A1：Batch APIへの移行（v0.1）

2026-10-24。対象は、凍結済みのProject W × OpenAlex R2+A1本番候補223,115件。同期Responses APIで完了したバッチ0000〜0009の10,000件は再送しない。開発160件・独立holdout600件は本番キューから除外済みで、既存の人間判定や統合v2を変更しない。

## 何が変わるか

- **変更するもの**：Responses APIの呼出方法のみ（同期 → OpenAI Batch API、24h完了枠）。GPT-6 LunaのBatch料金は標準料金の50%。
- **変更しないもの**：`gpt-6-luna`、`run_openalex_r2a1_development_20_v0_1.py`の`PROMPT`、`SCHEMA`、`case_payload`、Project W、R2+A1候補の順序とID、VALID/INVALID/UNCERTAINと理由コード。
- **結果保存**：成功した判定は従来の`derived/openalex_production/retrieval_r2a1_production_identity_aware_v0_1/batch_XXXX_continuation_v0_1/model_results.jsonl`へ追記。APIの生の出力、ジョブID、エラー、入力SHA-256は`batch_api_v0_1/jobs/`内に別保存。重複IDは再追記しない。
- **非同期**：投入後はtmux/SSH接続を切ってよい。完了後に明示的な`--collect`が必要。応答の順序に頼らず`custom_id`を照合する。

## 0. 前提

`run_openalex_r2a1_production_first_1000_v0_1.py`と`run_openalex_r2a1_production_continue_v0_2.py`が`./scripts/`にあり、元の本番10,000件が検証済みであること。同期ランナーと同じ対象を同時に動かさないこと。

```bash
cd ~/canon-pipeline-openalex-a2val
source ~/venvs/canon/bin/activate
# OPENAI_API_KEY の有無だけ確認する（キー本体は表示しない）
[ -n "${OPENAI_API_KEY:-}" ] && echo 'API KEY: SET' || echo 'API KEY: MISSING'
```

## 1. まず100件だけ切替テスト

```bash
python -B scripts/run_openalex_r2a1_production_batch_api_v0_1.py \
  --stage --start-batch 10 --end-batch 10 --max-requests 100
```

この`--stage`は**API呼出しゼロ**。新規候補の入力JSONLとマニフェストを作り、既存の判定済みIDを除外する。まずコマンドの出力を確認する。

```bash
python -B scripts/run_openalex_r2a1_production_batch_api_v0_1.py --submit
```

`--submit`は**有料**。Batch APIへ100リクエストの入力をアップロードして非同期ジョブを作成する。remote `batch_id`と`input_file_id`はサーバー内に記録される。ジョブ作成時のAPI通信が不明確に中断したら**同じ投入を盲目的に繰り返さず**、保存された状態に従って`--reconcile`で照会する。

```bash
python -B scripts/run_openalex_r2a1_production_batch_api_v0_1.py --check
```

`--check`で `completed` が出たら、以下を実行する。

```bash
python -B scripts/run_openalex_r2a1_production_batch_api_v0_1.py --collect
```

`--collect`は出力・エラーファイルをローカル保存し、応答IDと候補IDの整合性・JSONスキーマ・判定と理由コードの対応を確認する。適合する結果だけを従来の1,000件ファイルへ追記し、その他は`unaccepted_audit.json`に残す。中断した場合は同じ`--collect`で再開できる。

## 2. 問題なければ10,000件規模に拡大

上記の100件が`--collect`で完了した後：

```bash
python -B scripts/run_openalex_r2a1_production_batch_api_v0_1.py \
  --stage --start-batch 10 --end-batch 19 --max-requests 10000
python -B scripts/run_openalex_r2a1_production_batch_api_v0_1.py --submit
```

Batch APIの処理が完了してから `--check` と `--collect`を実行する。10,000件の中では、最初の100件で既に保存されたものは除外するため再課金しない。以後、範囲を20〜29、30〜39というように変えて同じ手順で進められる。各ジョブが完了・回収されるまでは次のジョブをステージしない安全設計。

`--max-requests=10000`はこのプロジェクトの保守的な区切り。OpenAIの一般的な上限は1ファイル50,000リクエスト・200MBだが、別途モデルのBatchキュートークン上限が適用されるため、最初の大規模ジョブでは10,000件程度を推奨する。投入前にファイル実サイズを検査する。

## 3. 状態確認

```bash
python -B scripts/run_openalex_r2a1_production_batch_api_v0_1.py --status  # ローカルのみ
python -B scripts/run_openalex_r2a1_production_batch_api_v0_1.py --check   # リモート参照
```

ジョブが`failed`/`expired`/`cancelled`となった場合も`--collect`で取得可能な成功結果と失敗理由を保存。失敗分だけを次回ステージに回す。Batch結果ファイルの保持期間には限りがあるため、完了したら速やかに収集する。

## 4. Git・運用上の注意

`git add`するのは **スクリプトとこの説明文書だけ**。`batch_api_v0_1/jobs/`にはプロンプトを含むリクエストや生のモデル応答があるため、通常はGitへ追加せずサーバーのバックアップ対象にする。ログとハッシュで再現性を管理する。APIキーをGit、README、ログ、チャットに貼らない。

Batch APIは50%割引だが、入力・出力のトークン量やクレジット／利用枠によって実請求額は変わる。モデル価格は公式の[GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)、手順・制限は[Batch API](https://developers.openai.com/api/docs/guides/batch)を参照。
