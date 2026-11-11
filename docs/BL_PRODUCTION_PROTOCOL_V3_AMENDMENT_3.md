# BL 本番 v3 プロトコル 改訂 3：メンテナンス画面の扱いと再開枠の拡大

日付：2026-11-11
対象：`docs/BL_PRODUCTION_PROTOCOL_V3.md` §7（安全装置）、改訂 1。凍結文書と `protocol_freeze_v1.json` は変更しない。

## 理由

1. 2026-11-07 23:17 GMT（バッチ 12）：BL の SRU が HTTP 200 で HTML のメンテナンス画面（Ex Libris の `maintenance.jpg` ページ）を返し、XML として読めず `STOP_PARSE` で夜が終了した。直前 23:07 GMT に `RemoteDisconnected` があり、改訂 1 の自動再開の直後に起きている。これは XML の破損ではなく、BL が応答できない状態の表れで、network 停止と同種である。
2. 2026-11-11（バッチ 17）：1 晩に network 停止が 3 回起き、改訂 1 の再開枠（2 回）を超えて夜が終了した。再開は完了済みクエリを再送しないため、枠を増やしても BL への送信量は変わらない。

network 停止の記録（GMT）：10/30 01:02、11/1 23:06、11/2 00:35・00:45、11/3 23:05、11/7 23:07、11/11 03:59・04:48 ほか。いずれも一過性で、再開後は正常に続いている。

## 変更

1. runner：HTTP 200 で本文が XML として読めず、かつ本文が HTML（`<!DOCTYPE html` または `<html` で始まる）の場合、`STOP_MAINTENANCE` として記録して停止する（raw は保存）。本文が HTML でない場合は従来どおり `STOP_PARSE`。
2. driver：`STOP_MAINTENANCE` は `STOP_NETWORK` と同じく待って同一バッチを再開する。待ち時間は network 10 分、maintenance 30 分。
3. driver：1 晩の再開枠を network と maintenance の合計で 6 回に（改訂 1 では 2 回）。7 回目は従来どおり夜を終了し、翌日も自動では動かない。

## 変わらないこと

- `retries=0`、夜間窓、1 晩 7,000、累計 200,000。
- `STOP_HTTP`、`STOP_DIAGNOSTIC`（改訂 2 の 200812 を除く）、HTML でない `STOP_PARSE` の即終了。
- BL への通知内容（送信量・時間帯は変わらない）。

## 適用

2026-11-12 の夜から。実装 commit は本文書の次の commit。
