# Goodreads共有クエリ3群：承認済み照合レビューの非破壊的保存

作成：2026-11-06（添付データに基づく）
対象：`haruka0221/canon-pipeline` / `openalex-r2a1-production-20261021`
状態：`VERSIONED_APPROVED_SOURCE_IDENTITY_REVIEW_ONLY`

## このパッケージで実施したこと

- 2026-11-06人間承認済みTSVのSHA-256を、添付の元manifestとバイト単位で照合した：`a46762946c534c780b410abff9e4e334e119bc6314c0731fcbabdd367e2a0e31`。
- 7 Project W / 7 OL Workのsource-level候補照合を、Rosalynde、East Goes West、Chitaの3 Goodreads Work IDに対応づけた。
- 元TSVと元manifestを**内容変更なし**で保存し、7行の証拠overlay、3行の重複リスク診断、7行のscope人間レビュー用シード表を生成した。
- 新規成果物のSHA-256と件数を`release_manifest_v0_1.json`に記録した。
- OpenAlex、Goodreads数値、Project W identity、scope、旧crosswalkは一切変更していない。

## 内容・意味

| ファイル | 行数 | 位置付け |
|---|---:|---|
| `derived/identity/goodreads_shared_query_3groups_match_review_evidence_v0_1/goodreads_shared_query_3groups_approved_match_review_v0_1_2026-11-06.tsv` | 7 | 元の研究者承認済み行をバイト保存 |
| `.../goodreads_shared_query_3groups_approved_match_review_v0_1_2026-11-06_manifest.json` | — | 元manifestをバイト保存 |
| `.../approved_ol_goodreads_source_identity_overlay_v0_1.tsv` | 7 | OL→GR候補の人間承認をread-only証拠として再利用するためのoverlay。`approved_goodreads_work_id`は旧crosswalkの`goodreads_work_id`列を置換しない |
| `.../goodreads_shared_work_group_diagnostic_v0_1.tsv` | 3 | 複数Wが同じGR IDに対応する状態を明示。作品統合ではない |
| `.../scope_review_seed_not_adjudicated_v0_1.tsv` | 7 | 書誌年・URL等の手掛かりと、人間による正式判定欄を分離。研究者による判定は未実施 |
| `.../release_manifest_v0_1.json` | — | 本リリースのQC・hash・明示的な未決定事項 |
| `scripts/prepare_goodreads_shared_query_review_overlay_v0_1.py` | — | 標準ライブラリのみで検証・再生成できるスクリプト。既存出力先がある場合は上書きを拒否 |

`goodreads_shared_work_group_diagnostic_v0_1.tsv`で同じGoodreads Work IDを共有することは、Project Wの`SAME`や自動mergeを承認するものではない。独立した概念作品の同一性やscopeが決まるまでは、7 WにGoodreads ratingsを転記してW単位の相関・順位分析に加えない。重複を避けるだけでなく、不適切なsource overaggregationの可能性も排除していない。

## 照合承認済みである範囲

- Rosalynde：`W000000884` / `W000005820` / `W000009109` → GR Work `1534534`。
- East Goes West：`W000010194` / `W000016944` → GR Work `1035773`。
- Chita：`W000006832` / `W000030926` → GR Work `1930317`。

Rosalyndeではユーザーが閲覧したGoodreads Book `1542316`と、内部base reviewの一致Book `1542314`が異なる。Book IDとWork IDは区別し、同じWorkに属するかをAPIレベルで確認済みとはしない。

## サーバーでの安全な追加確認（配置後のread-only操作）

GitHubとサーバーの状態がずれているため、まずサーバーで以下を確認する。次のコマンドはGit操作による更新をしない。

```bash
cd /home/tsutsui/canon-pipeline-openalex-a2val
git status --short --branch
git rev-parse HEAD
git rev-parse origin/openalex-r2a1-production-20261021
```

2026-11-06の引継ぎログではサーバーHEAD=`4e7932262346aa2405fc9da93654bed751af04a5`、リモート=`3971afe1273a57ead08588c9a0d5576c16257549`。GitHub側リモートが同値であることは、このパッケージ作成時にも読み取り確認したが、サーバー現況は未確認。`git pull`／`git add -A`をしない。

### 転送手順

このZIPをサーバーへ転送（方法・接続先は各自のSSH/SFTP設定に合わせる）。リポジトリの**外**で展開してから、成果物のフォルダー名が既存と衝突しないことを確認する。例：ZIPを`~/canon_gr_review_bundle_v0_1.zip`へ置いた場合。

```bash
cd /home/tsutsui
mkdir -p canon_gr_review_staging_v0_1
unzip -n ~/canon_gr_review_bundle_v0_1.zip -d canon_gr_review_staging_v0_1
ls -l canon_gr_review_staging_v0_1/derived/identity/
```

上記を確認したのち、`scripts/...`と`derived/identity/...`をリポジトリへ**ファイル単位で、上書きしない**方法で配置する。既存の同名ファイルがあれば停止する。サーバー側の実際の状態が確認できるまで、Gitコミットや別ブランチとの統合はしない。

read-onlyな追加QC（ディレクトリにファイルを配置済みの場合）：

```bash
cd /home/tsutsui/canon-pipeline-openalex-a2val
python -B scripts/prepare_goodreads_shared_query_review_overlay_v0_1.py \
  --review derived/identity/goodreads_shared_query_3groups_match_review_evidence_v0_1/goodreads_shared_query_3groups_approved_match_review_v0_1_2026-11-06.tsv \
  --manifest derived/identity/goodreads_shared_query_3groups_match_review_evidence_v0_1/goodreads_shared_query_3groups_approved_match_review_v0_1_2026-11-06_manifest.json \
  --crosswalk derived/crosswalks/goodreads_work_crosswalk_v1.tsv \
  --bridge derived/scope/scope_combined_bibliographic_evidence_v0_1/scope_combined_project_w_bibliographic_evidence_v0_1.tsv \
  --check-only
```

`--check-only`は新しいファイルを書かない。34,789件の旧crosswalkのスキーマ・件数・7行の`AMBIGUOUS`・Project WとOL Workの対応関係を追加検証する。server実ファイルでの合格は**まだ報告されていない**ので、QCの実行結果は保存してから判断する。

## その次の工程（今回自動実施していない）

1. `scope_review_seed_not_adjudicated_v0_1.tsv`の書誌年・URLを一次資料／出版社／信頼できる書誌で個別確認し、original language、novel/novella、連載初出／完結／単行本初刊、対象Workとのリンクを研究者が記入する。
2. 研究者のscope判断とProject W identity統合判断は別versionで確定する。現在、両方とも未実施。
3. GR Work ID単位の観測値（古いUCSDスナップショット）とProject W単位のOpenAlex値を、そのまま一対多にjoinしない。scopeが確定した作品集合と、共有クエリidentityリスク有無ごとにcoverage・感度を記述する。
4. 既存1,797共有クエリWでは旧crosswalk採用MATCHが0だったという構造を維持し、今回承認された7行だけの追加効果を別に報告。比較母集団の選択バイアスを隠さない。
5. 既存OpenAlex v2/v3、LLM本番223,115件、holdout600、Goodreads crosswalk v1は上書きしない。

### 方法資料

- `docs/OPENALEX_ANALYSIS_SCOPE_DRAFT_v0_1.md`
- `docs/OPENALEX_SCOPE_SCREENING_DESIGN_DRAFT_v0_1.md`
- 2026-11-06 `CANON_PIPELINE_HANDOFF_SHARED_QUERY_GOODREADS_2026-11-06.md`
- GitHub対象ブランチの`WORKFLOW.md`

## 2026-11-06追加：外部書誌の一次点検（正式scope判定ではない）

`derived/scope/goodreads_shared_query_3groups_bibliographic_evidence_v0_1/`を**承認済みGR照合とは独立した書誌証拠インベントリ**として追加。原作年代・英語原作性・作品形態について、公開されている書誌資料を照合した。3件ともProject Wのscope判定は`NOT_ADJUDICATED`であり、各OL Workのレコード同一性を外部書誌と1件ずつ独立確認していない。

- Rosalynde：1590年の版の表題紙をInternet Shakespeare Editionsで確認。1910年版の編集者序文は牧歌的ロマンスとして説明。1880年より前の刊行を強く示すが、人間の正式OUT判定ではない。
- East Goes West：LTI Koreaが1937年初刊、原語英語、小説と明記。1997年Kaya版は復刊であり、1937年の原作初刊に置換しない。IN候補だが正式判定ではない。
- Chita：Laura Stedmanの書誌に1888年4月『Harper's Monthly』掲載。CiNii所収書誌に1889年Harper & Brothers初版の注記。小説／中編／短編の境界は未審査。

閲覧した具体的書誌出典URLは外部書誌TSVに記録している。研究対象の書籍のMLA第9版形式での書誌表示（初刊の表題・出版者）：

- Hearn, Lafcadio. *Chita: A Memory of Last Island*. Harper & Brothers, 1889.
- Kang, Younghill. *East Goes West: The Making of an Oriental Yankee*. Charles Scribner's Sons, 1937.
- Lodge, Thomas. *Rosalynde: Euphues' Golden Legacy*. Thomas Orwin for T. G. and John Busbie, 1590.

これらは作品の書誌同一性の研究用表記であり、入力中のGoodreads Book ID・同一作品の集約・各OL source Workの版を独立に確定するものではない。
