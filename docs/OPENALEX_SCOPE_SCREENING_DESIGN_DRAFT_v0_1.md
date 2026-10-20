# OpenAlex主分析用 scope スクリーニング設計草稿 v0.1

**作成日:** 2026-10-20
**状態:** `METHOD_DESIGN_DRAFT / NO_SCOPE_ADJUDICATION / NO_DATA_MUTATION`
**対象母集団:** OpenAlex統合v2で追跡するactive Project W 32,066件
**入力参照:** `derived/scope/scope_evidence_pilot_v1/`、`derived/scope/random_scope_review_draft_v0_10/`、既存のscope review protocol（いずれも凍結・既存入力として扱う）

## 1. 目的と適用範囲

OpenAlexによる**学術的注目の主分析**に用いる作品集合を、明示的な書誌証拠に基づいて限定する。暫定対象定義は「**1880–1950年（両端を含む）に初めて刊行された、英語で書かれた単独の長編・中編小説**」。児童・YA向けの長編・中編小説は、読者層だけを理由に除外しない。短編小説、短編集、アンソロジー、批評書、書誌、非英語原作からの翻訳は区別する。

これは**分析用の独立したscope layer**である。歴史的な34,789 OL source records、32,066 active Project W、OpenAlex v2の計測結果、identity対応、他の流通・読者受容・教育指標を消去・修正・再取得しない。

## 2. いま確定していること／していないこと

- 固定された独立無作為標本80 Wについて、8バッチのAI支援書誌証拠草稿がある。
- 統合表 `random_scope_80_ai_exploratory_register_v0_1.tsv` は、80件一意・固定標本との順序一致がサーバーで**VERIFIED**。AI提案の内訳はIN候補44、OUT候補26、UNRESOLVED10。出典URL記録176件。
- **研究者による正式なscope判定は0件**。URLの存在だけでは、そのURLが該当OL Workを直接支持することの検証にはならない。
- OLの `first_publish_year` に見える歴史的な年は**紐付くEditionの最小年**。概念的作品の原作初刊年ではない。OLの `fiction` 等subjectは探索信号であり、作品形態の確定的証拠ではない。
- 原作の雑誌連載初出・完結初出・単行本初版を区別し、境界事例で期間の判定が割れる場合は `PERIOD_BASIS_REVIEW_REQUIRED` とする。短編と中編の境界も規約を先に決める。

## 3. 三層の設計

### 層A：全Wに対する**書誌的証拠インベントリ**（まだscopeを判定しない）

`project_work_id` を唯一の行キーとし、各Wについて現行OL Work ID、著者・標題、Edition由来最小年、Subject signals、書誌ソース来歴、既知のtarget correction、identity曖昧性等を**出典ごと**に保存する。現段階のsource signalsは「診断手掛かり」として読み、真の原作年代や英語原作性とは区別する。

外部書誌が見つかる場合は、照合対象（OL Work／標題／著者／版）、ソース識別子・URL、原作言語、作品形態、原作初出年、完結版年、最初の単行本年、英訳年を別フィールドに残す。単なるtitle+author類似照合を確定リンクとみなさない。

### 層B：**規則に基づくレビュー優先度付け**（決定ではない）

次のフラグを付け、優先レビューを可能にする。

| 信号 | 意味 | 禁止する短絡 |
|---|---|---|
| `edition_year_conflict_flag` | OL Edition由来年と裏付けのある原作年が不一致 | OL年だけで対象内・外を決めない |
| `non_novel_form_signal` | bibliography、criticism、short stories、anthology等の手掛かり | Subject文字列だけでOUTを確定しない |
| `non_english_original_signal` | 翻訳者表記・原語版・原作言語の手掛かり | 英語版があることを英語原作と混同しない |
| `title_identity_risk` | 短い一般名詞題、改題、同名異作品、著者名題 | 誤リンク先の書誌を転用しない |
| `multi_ol_target_flag` | 1 Wに複数の現行OL Work | 重複と決めつけて勝手に統合しない |
| `evidence_gap_flag` | 原語・作品形態・初刊年等の確証不足 | 情報がないことをOUTとみなさない |

初期段階では `REVIEW_PRIORITY_HIGH / NORMAL / NEEDS_SOURCE` といった**作業キュー**を作る。高優先度も対象外という意味ではない。確定根拠がないWは `UNDETERMINED` を維持する。

### 層C：**研究者によるscope判定**（別ファイル・別権限）

`work_form`、`original_language`、`first_public_appearance_year`、`first_complete_work_publication_year`、`first_book_publication_year`、`period_basis`、`bibliographic_target_link_status`、`period_status`、`language_status`、`form_status`、`analysis_scope_status`、`evidence_ids`、`reviewer`、`review_date`、`review_status` を分けて保存する。

`IN_SCOPE`、`OUT_OF_SCOPE` は、独立資料と対象Workとの対応を研究者が確認した場合のみ。根拠不足は `UNRESOLVED`。**AIの `IN_SCOPE_CANDIDATE` を人間の `IN_SCOPE` に自動変換しない。** 80件の `reviewer_scope_decision` と `reviewer_verification_notes` は現時点で空欄のまま維持する。

## 4. 次の作業順序

1. **入力の列・欠損・結合可否を読み取り専用で診断**する。全32,066 Wのsampling frame、OpenAlex registry、OL enriched population、identity provenanceのどの列が実際に使えるかを確認する。ここでは一切の判定データを発行しない。
2. 診断結果に基づき、**全Wの証拠インベントリのスキーマ**を固定する。現行OL Workが複数の場合、複数の版由来年を保持し、どれか1件に勝手に縮約しない。
3. 既存の80 Wを研究者が独立して確認するための**レビュー用ワークシート**を作る。AI提案列と研究者の判断列を明確に分け、保留も許す。必要なら最初の10件で手順を試す。
4. 研究者判定が揃ってから、規則・ソース別の誤検出／取りこぼし／保留率を試験する。AI草稿44/26/10と機械スクリーニングの一致は、**正解率の検証ではない**。
5. その結果に基づき、全32,066 Wに対する**候補・レビュー待ち・研究者確定**のversioned scope layerを発行する。凍結済みのOpenAlex v2指標に後からjoinするだけで、原指標は再計算・上書きしない。

## 5. 推定・集計の禁止事項

- `44/80 = 55%` を、研究者未確認のまま「32,066 Wの対象内率」として報告しない。
- 独立無作為80 Wに、159 Wの残りの目的抽出例や上位OpenAlex count事例を混ぜて母集団比率を計算しない。
- **W単位のscope比率**を**OpenAlex候補ペアのprecision**と混同しない。OpenAlex operational candidate 226,221ペアは書誌scopeと別に帰属精度の問題がある。
- `NOT_QUERIED_R2_R3` の352 Wと、未再計測のAlcott 1 Wをゼロと解釈しない。
- 既存のフリーズ成果物、OL Edition監査、identity pilot未追跡ディレクトリに変更を加えない。

## 6. 次の到達点

**最初の具体的な成果物は全32,066 Wのscope確定表ではなく、入力信号のカバレッジ診断と、80 Wに適用可能なレビュー規約の確定版。** この順番で進めれば、作品集合の定義とOpenAlexの計測結果を混同せず、研究者が検証可能な主分析集合を構築できる。
