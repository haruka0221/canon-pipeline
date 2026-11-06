# 文学的可視性：これからの分析・実行順と意思決定（2026-11-06）

状態：NEXT STEPS。OpenAlex本番LLMの追加実行を要請する文書ではない。いったん作業を停止しても、この地点から再開できるようにする。

## 0. いま停止している位置

- 完了：OpenAlex R2+A1本番LLM223,115／223,115件、v3暫定採用173,897件、全type/core3/expandedの6比較、同一クエリ833群、上位2群仮union、32,066WのOL/Wikidata書誌証拠の結合。
- 未完：OpenAlex×Open Library Edition数×Goodreads ratings/reviewsの実データ照合・相関分析。最後の比較スクリプトは2026-11-06にGitへ追加されたが、現時点でユーザーからサーバーの実行成功は報告されていない。結果を創作しない。
- ブランチ：`openalex-r2a1-production-20261021`。サーバー：`~/canon-pipeline-openalex-a2val`。本番データはサーバーの既存フォルダーにあり、Gitに全件含まれるとは限らない。

## 1. 次の最優先工程：残り831クエリ群の影響を先に計測（2026-11-06更新）

ユーザーとの最新合意：OpenAlex × Open Library × Goodreadsの比較を実行する前に、残り831の同一title+author R2検索クエリ群が、作品別可視性に与えうる影響を評価する。Ulysses/Heart of Darknessの上位2群は既に感度分析済みだが、残り831群の合計影響・順位への影響は未計算。既存の最後のOL×Goodreads比較スクリプトは未実行のまま保留する。

入力：`derived/openalex_production/analysis_v3_shared_r2_query_identity_risk_v0_1/shared_r2_title_author_clusters.tsv`、`shared_r2_query_cluster_members.tsv`、v3採用W×OpenAlex IDペア、文献type派生表、32,066W書誌証拠表。

この新しい分析コードはまだGitに存在しない。次のチャットで新規に作成し、既存結果を変更せず、別名`analysis_v3_all_shared_query_impact_v0_1`等に出力する。

分析内容：
1. 833全グループの個別影響（W数、元ペア数、OA IDのunion数、重複配置数、type別、上位Wの順位影響）を計算する。
2. 上位2群と残り831群を分けて、重複配置総量・集中度・ランキングの感度を調べる。`同一クエリ`を`同一作品`と断定しない。
3. 異なるグループに同一Project Wが属しうるので、グループ別重複を単純合算して全体の減少数としない。必要なら連結成分／条件付き仮集約を用い、全体の正確なunionと個別影響の両方を別々に提示する。
4. レビュー優先度は件数だけでなく、上位順位への影響・主分析scopeとの関連・OL source identityの矛盾・外部DBと結合する予定の作品を考慮する。
5. 書誌的同一性を研究者が確認できたものだけ別versionのidentity decisionに反映し、残りはUNREVIEWEDを保持する。223,115件のLLM推論を再実行せず、v3と封印holdoutを不変に保つ。

これが通ったら、重大なidentity問題を優先レビューし、その影響を注記した上で次の`2. OpenAlex×OL×Goodreads`へ進む。全833群の人手確認を必須の停止条件にしない。

## 2. その後の工程：OpenAlex×OL×Goodreads比較（現時点は未実行）

スクリプト：`scripts/analyze_openalex_v3_ol_goodreads_bridge_v0_1.py`。

~~~bash
cd ~/canon-pipeline-openalex-a2val
git status --short --branch
git pull --ff-only
source ~/venvs/canon/bin/activate
python -B scripts/analyze_openalex_v3_ol_goodreads_bridge_v0_1.py
~~~

これは外部API・LLM推論を呼ばず、上流データを変更しない想定。ただし実データでのQC未確認。未追跡のローカル変更を確認してから`git pull`。出力名がすでに存在するなら削除・上書きしない。QCに失敗した場合は原因と差分を記録し、新versionで修正。

予定出力先：`derived/openalex_production/analysis_v3_ol_goodreads_provisional_comparison_v0_1/`。予定ファイル：
- `all_project_w_provisional_visibility_ol_goodreads.tsv`（各Wの可視性、元OL ID、版、採用Goodreads ID、ratings/reviews、欠損理由）
- `complete_case_correlations.tsv`（相関係数と分析対象数）
- `academic_vs_goodreads_percentile_contrasts.tsv`（学術的／一般読者の百分位差）
- `summary.json`、`manifest.json`。

### 現行実装の結合方法

1. 全Wの`analysis_v3_visibility_lenses_scope_bridge_v0_1/work_visibility_with_scope_evidence.tsv`が基準。Wキーのユニーク性を確認。
2. 書誌証拠の`current_ol_work_ids_json`からOL Work IDを取得し、`derived/ol_edition_counts.tsv`に厳密なWork IDで結合する。OL Workが1つの場合のみ計量相関に利用。複数OL Workについては診断欄に留め、自動加算で「文学作品全体の版数」を作らない。
3. `derived/crosswalks/goodreads_work_crosswalk_v1.tsv`の`crosswalk_decision=MATCH`だけを採用。34,789 source OL records中、MATCH7,624、AMBIGUOUS4,685、NO_CANDIDATE22,465、NO_MATCH15（`goodreads_work_crosswalk_v1_summary.json`に記載）。このsource数を32,066 Project Wの照合数と呼ばない。
4. 歴史的`derived/goodreads_ucsd_match.tsv`の`work_id`は現在のcrosswalkの採否を上書きしない。現行MATCHで認定したGoodreads Work IDに対してだけ、旧データのratings_count・text_reviews_countを数値ソースとして照合。ID内で数値矛盾がある場合は保留。未照合と値欠損を0にしない。
5. academic指標：`v3_provisional_operational_pairs`と`exploratory_article_chapter_dissertation_pairs`（core3）。どちらも学術的な適格性は暫定。
6. complete-caseにおけるSpearman順位相関、`log1p` Pearson相関、matched sample内のpercentile差を計算する構想。上位2群の重複リスクWを除く感度比較も行う。分析母集団は非ランダムでselection biasを持ちうる。

### 最初に確認する数値

- OpenAlexの計測済みW数と「未検索352 W」「未再計測Alcott 1W」のNA条件。
- 受理されたGoodreads Work IDがProject Wにどれだけ一意に投影されるか（同一OL source上のIDとW対応の多対多を必ず確認）。
- Goodreads ratings/reviewsが実際に得られるW数、古いUCSDソースでのID別数値矛盾数。
- OL Edition登録数が結合できたW数、複数OL IDs／年不明／計測不能の扱い。
- 各相関が対象とする`complete_case_works`を明記。集計から消えたWの割合、欠損の偏りを報告。
- `Pride and Prejudice`、`The Waste Land`等のscope外の可能性がある作品を、最終の1880〜1950英語小説の結論へ流用しない。
- Goodreadsの評価数はUCSDの歴史的観測値であり、2026年リアルタイムの現在値と呼ばない。

## 3. その後の分析のロードマップ（並行して進めてよい）

### A. 記述統計：学術的可視性の分布

- all types、core3、expandedの各指標で、陽性W／計測済み0W／NAの区別、分位点、top1/10/100集中度、順位変化、外れ値を保存。
- 現行Project W集計と、上位2群だけを仮unionした感度の両方を表示。`SENS_`結果を正式identityに昇格させない。残り831の同一検索群は優先度でレビューする。
- `query_title_display`・`query_author_display`はR2クエリ由来の表示にすぎない。canonical書誌表示と混同しない。

### B. 文学的可視性の異領域比較

- OpenAlex学術言及の候補、Goodreads ratings/reviews、Open Library登録Edition、追加可能なJSTOR、HathiTrust、Open Syllabus等を、各source-native identityと単位を守って結合する。
- 複数のsource Work／edition／identifierを一文学作品へ結びつける場合、同一コンテンツの重複と分裂Work問題を先に診断する。
- 「学術高・読者低」／「読者高・学術低」の乖離は、同じ比較母集団・観測時点・標準化方法・欠損規則で定義。パーセンタイル差は仮説探索であって正典判定ではない。
- 過去の90作品パイロットのしきい値や対応結果を、全32,066 Wへ無検証で一般化しない。

### C. 主分析のscope確定と学術文献フィルタ

- 原作が英語、1880〜1950年初刊の単独長編・中編小説、という草案の確認。原語、作品の独立性、初出連載・初単行本年・完結年を別列で確認し、人間レビューを蓄積。
- 独立無作為80 Wについて過去のAI支援草稿はあるが、少なくとも2026-10-20時点では人手scope確定0。現時点で研究者による新規確認があった場合は新versionのソースで確認してから採用。
- OpenAlex側の文献typeと学術的利用目的を別規則として審査。articleやdissertationと表示されるだけで、対象文学作品への実質的学術研究と認めない。
- 作品identity確定・scope決定・文献適格性・可視性指標の採否を混ぜず、判断別にprovenance・version・未決定理由を残す。

### D. 論文の提示に適した検証

- 主分析と感度分析の図表・ランキングの基準日時、対象母集団、文献type、結合成功率、除外理由を明示。
- サンプル検証と推定精度を混同しない。1800 Wなどのquery重複を自動で同一作品とみなさない。
- 見つかった相関を正典形成の因果的メカニズムと呼ばず、補助的な文学史・受容・教育史の資料と照合して解釈する。

## 4. データの安全性と禁則

- 再実行するのは必要な分析だけ。本番223,115件のLLM推論を再実行しない。
- `git add -A`／丸ごと`derived`の公開は禁止。サーバー上の凍結JSONLや未開封holdout600の予測を無断Git公開しない。
- Open Library Edition数は登録レコード数。以前の`build_edition_counts.py`はEdition側`works[0]`を計数しており、講習会SQLiteが全Workリンクを数える定義と完全一致するとは限らない。
- `scope_combined_bibliographic_evidence`のEdition由来最小年は原作初刊年ではない。Wikidata P577/P407/P31も研究者確認なしに確定値へ変換しない。
- 再開する際はまず `docs/RESEARCH_HANDOFF_OPENALEX_VISIBILITY_2026-11-06.md` に戻り、最新の実行状況を確認する。
