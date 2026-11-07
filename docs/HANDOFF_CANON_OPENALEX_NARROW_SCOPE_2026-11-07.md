# 博論 Canon Pipeline / OpenAlex 可視性・scope作業 引継書

作成日：2026-11-07（JST）
状態：研究者レビューへの切替点。AIによる書誌点検80/80完了、研究者確定0/80。独立の狭義scopeデータセットは未発行。
Repo: https://github.com/haruka0221/canon-pipeline
作業ブランチ：`review/goodreads-shared-query-v0_1-20261107`
作成直前に確認したHEAD：`ffa852afb8c92ebe9b3eb07ac633f0fcad6315a7`（本引継書追加後はHEADが進む）。必ず最新状態を再取得すること。

## 1. このプロジェクトの核心

博士論文は文学的可視性・カノン形成・注意の経済を扱い、Open Library、OpenAlex、Goodreads等を同一文学作品の異なる可視性指標として比較する。これは単一の「正典性」指標ではない。

- 歴史的Open Library元データ：34,789 source records。統合後のOpenAlex分析用active Project W：32,066 W。
- 広義の歴史コーパス：1880–1950年に刊行された英語の版・出版物を収集したもので、原作がもっと古い作品の再版や英訳版を含みうる。広義母集団への掲載は、すべてのレコードが正しいことの保証でもなく、全作品が英語原著の小説という意味でもない。
- 狭義のOpenAlex主分析は、従来「英語原著・1880–1950年初刊の単独長編・中編小説」だった。2026-11-07に、著者によるオリジナルの単著短編集を加えるv0.2規約案をユーザーが「たぶんいいと思う」と暫定支持。現在は研究者レビューの作業規約であって、正式な判定規約として研究者サインオフしたわけではない。
- v0.2主分析候補：(A)英語原著の長編／中編小説（児童・YA・共著小説を理由に除外しない）、(B)1880–1950年に独立した作品集として初刊された英語原著の単著短編フィクション集。従来の(A)だけを比較対象 `NOVEL_NOVELLA_ONLY` として保持。
- 短編集の例：Joyceの1914年刊作品集は作品集レベルの対象内候補。ただし収録短編の初出年と作品集の初刊年は別。収録短編と作品集のOpenAlex学術言及を、重複排除なしに足し合わせない。
- 混合形式の単著作品集（小戯曲、風刺コラム、民話＋解説など）、死後編集・後年の選集、複数著者アンソロジー、単独の短編、映画ノヴェライズは一律自動包含しない。形式と書誌の同一性を分けてレビューする。

年代の暫定規約：
- 個別小説：原語で最初に公刊された年（連載なら開始年）を優先する作業案。完結公刊年・原語初単行本年を別列に保持。1880/1950境界をまたぐ場合は `PERIOD_BASIS_REVIEW_REQUIRED`、別年代規約の感度分析を検討する。連載日付の最終規則は未確定。
- 短編集：その特定の作品集・内容構成として初刊された年を用い、個別短編の初出年とは区別する。大幅に内容変更した版はversion関係を保持する。
- `OL linked Edition-derived min year` は原著初刊年ではない。Wikidata P577/P407も研究者確認なしに確定値としない。

## 2. このチャットで終わったこと

- 元の独立無作為80 Wを保全したまま、1–80番の全作品について既存AI書誌資料を再点検し、上記v0.2作業案に沿った非確定メモを7本作成した。書誌的な点検が80/80という意味であり、外部ソース・OL Edition→Work同一性の人間検証が80/80という意味ではない。
- 80 W正式研究者判定：0件。研究者欄はすべて空白、`NOT_REVIEWED`。AIのIN/OUT候補の割合を32,066 Wの対象内率に外挿しない。
- 実際の研究者レビューへ進むため、v0.2作業プロトコルを新規作成し、難しい15 Wの「確認用キュー」を新規TSVで作成、GitHubから読み戻してQCした。
- キューは15行・26列、Project W15件一意、全 `researcher_*` 欄空白、`review_status=NOT_REVIEWED`。元の80 W表とは別ファイル。
- 15 Wは無作為抽出ではなく、既存無作為80 Wのうち「難しさ」で目的選定した診断事例。これだけでは母集団の対象内率を推定できない。
- GitHubのレビュー用ブランチに書誌メモ・プロトコル・TSV・READMEを保存し、元の80 W表、32,066 Wの元データ、OpenAlex v3、Goodreads、凍結済みモデル評価、封印holdoutは変更していない。

## 3. 次のチャットが最初に読む必須資料

A. 今すぐ再開するための規約：
`docs/OPENALEX_NARROW_SCOPE_RESEARCHER_REVIEW_PROTOCOL_v0_2_WORKING_2026-11-07.md`

B. 15作品の研究者レビュー用TSV：
`derived/scope/narrow_v02_researcher_pilot_2026_11_07/pilot15_reviewer_queue_v0_1.tsv`
同ディレクトリの `README.md` に内容、QC、レビュー手順あり。

C. 80 Wの暫定点検総括と重要事例：
`docs/OPENALEX_NARROW_SCOPE_RANDOM80_V0_2_REVIEW_GATE_2026-11-07.md`

D. 短編集を含める案の根拠と未決定事項：
`docs/OPENALEX_SHORT_FICTION_COLLECTION_SCOPE_POLICY_PROPOSAL_v0_2_2026-11-07.md`

E. 正式な研究者レビューがまだ入っていない元の80作品表：
`derived/scope/random_scope_80_researcher_evidence_sheet_v0_1/random_scope_80_researcher_evidence_sheet_v0_1.tsv`

F. 作業以前の規約（比較参照のみ）：
`docs/OPENALEX_ANALYSIS_SCOPE_DRAFT_v0_1.md`
`docs/OPENALEX_SCOPE_REVIEW_PROTOCOL_DRAFT_v0_1.md`

個別AI暫定点検：`docs/OPENALEX_NARROW_SCOPE_FIRST10_EVIDENCE_RECHECK_2026-11-07.md`、`docs/OPENALEX_NARROW_SCOPE_RANDOM11_20_EVIDENCE_RECHECK_2026-11-07.md`、`docs/OPENALEX_NARROW_SCOPE_RANDOM21_30_EVIDENCE_RECHECK_2026-11-07.md`、`docs/OPENALEX_NARROW_SCOPE_RANDOM31_40_AND_COLLECTION_RULE_RECHECK_2026-11-07.md`、`docs/OPENALEX_NARROW_SCOPE_RANDOM41_50_COLLECTION_POLICY_RECHECK_2026-11-07.md`、`docs/OPENALEX_NARROW_SCOPE_RANDOM51_60_COLLECTION_POLICY_RECHECK_2026-11-07.md`、`docs/OPENALEX_NARROW_SCOPE_RANDOM61_80_COLLECTION_POLICY_RECHECK_2026-11-07.md`。

## 4. 15作品パイロットの内訳とレビューの要点

元の80 W中のランク：`7,8,12,17,24,29,36,42,45,49,52,53,62,73,77`。
レビュー対象のW：
`W000013966, W000017199, W000013111, W000016912, W000006125, W000025937, W000009023, W000022733, W000029824, W000026024, W000002247, W000006556, W000025100, W000004535, W000012835`。

- #7 `W000013966`: 2003年刊批評書らしい外部レコードと、OL Edition-derived 1920年の不一致。別の作品を誤対応した可能性があるため、最初にtarget identityを検証。
- #8 `W000017199`: ロシア語原著の英訳。広義に残りうるが、狭義原語条件では対象外候補。確認必要。
- #12 `W000013111`: 単著の物語集であればv0.2対象内候補。内容・初刊年・OL対象の実物を確認。
- #17 `W000016912`: 単著作品集のなかにplayletがある。混合形式の扱い未決定。
- #24 `W000006125`: 1932年の物語集全体か、そのなかの短編の単独Workかを確認。
- #29 `W000025937`: 1926年の単著短編集なら、従来の長編のみscopeではOUT、v0.2ではIN候補に変わる。
- #36 `W000009023`: 1937年英国内原題と米国改題の同一性。OpenAlex検索のタイトル別網羅性にも関わる。
- #42 `W000022733`: 民話・フィクション・説明的文章が混在する可能性。著者/作品形式を決めつけない。
- #45 `W000029824`: 1933年原題 `Better Angel` と1951年改題 `Torment`。原著初刊年と検索対象タイトルを分ける。
- #49 `W000026024`: 1916年初刊の挿話群が、連続小説か短編集か混合スケッチか。
- #52 `W000002247`: 1991年刊と思われる作品にOLの1924年版表示あり。メタデータ原記録の由来要調査。
- #53 `W000006556`: Mr. Dooleyの風刺コラム集。創作短編集か文学的エッセイ／混合形式か未確定。
- #62 `W000025100`: 1947年映画と同名の書籍、映画ノヴェライズの独立性・内容・著者等が未確認。
- #73 `W000004535`: 外部照合の候補アンソロジーのOL Work IDが、標本のOL Work IDと異なる。自動同一視禁止。
- #77 `W000012835`: 個別短編と1887年の単著短編集について、OL Work IDが異なり、どちらが標本の概念的作品か未確定。作品集を自動採用しない。

元の80 W表のblob SHA（パイロット作成時）：
`d385cc1ca0ecca4aab10581bea74ceabc454bf49`
新パイロットTSVのblob SHA（read-back verified）：
`c118ba5232961e5377d57cca07caf39435657e34`

## 5. ここより前に完了したOpenAlex v3とGoodreads比較

これはscopeレビューとは別の研究進捗。文献適格性やscopeを確認していない探索的計測である。

- OpenAlex v3 provisional included W×OA pairs `173,897`。そのうちarticle+dissertation+book-chapterのCORE3候補 `146,724`。これは検証済み論文引用数ではない。
- LLM production queue `223,115` ペア終了。封印holdout600や凍結結果を再推論・閲覧・変更しない。
- 検索／計測未実施の352 Wと未再計測のAlcott 1 Wは0ではなくNA。Project Wの同一性問題や同じOpenAlex Work IDの複数Wへの帰属は別QC。
- 広義コーパスでのOA CORE3×Goodreads ratings Spearman探索相関：baseline `0.411970`（Goodreads観測4,642 W）、source-alert除外条件で `0.354431`（3,791 W）、追加のWikidata年代・言語条件で `0.349465`（1,348 W）。標本選択による変化があり、source-alert除外＝狭義scope確定ではない。Goodreads未照合は0にしない。
- 比較の入力と方法：`docs/README_SCOPE_SOURCE_ALERT_ROBUSTNESS_v0_1.md`、
`derived/openalex_production/analysis_v3_scope_source_alert_robustness_v0_1/` とその集計表。前の分析が完了しているため、直ちに再実行する必要はない。
- 古い2026-11-06 NEXT_STEPSなどには「相関分析未実行」と記載されるが、このチャット以前の2026-11-07実行で完了している。古いTODOをそのまま復活させない。

## 6. 次チャットで実際にやること（優先順）

1. GitHubブランチの最新HEADを確認し、本引継書・規約v0.2・15W TSV・READMEの4点を読む。過去の古いhand-offやNEXT_STEPSに引きずられず、実際の新しいcheckpointを優先する。
2. 15件のうちまず数件で、(i)対象OL Work/Editionと外部資料の対応、(ii)原語、(iii)原著／原集初刊年、(iv)形式と著者・翻訳者の役割、(v)根拠が不十分な点を、資料を直接確認しながらレビュー用の提案として提示する。
3. ユーザー本人が資料と判断を確認したケースだけ、`researcher_*` に新versionとして明示的に記入する。`review_status`をAIが勝手に`REVIEWED`へ進めない。未確定は`UNRESOLVED`のまま。
4. 混合形式の単著作品集や映画ノヴェライズ、serial開始年の規約を実例で検証してv0.2を固定する。重要変更があれば先に検証済みの事例も統一規則で再確認。
5. 15件の試行を踏まえ、凍結された同じ80 W全体を研究者が同一基準で確認して、根拠・保留・レビュー日を持つ独立した正式scope layerに進む。この時点で初めて抽出母集団に関する推定と不確実性を論じる。
6. scope layerの正式発行後にのみOA v3に後結合し、v0.2拡張主分析と小説・中編のみのネスト比較、異領域指標比較を実施する。

## 7. 保全・禁止事項

- `review/goodreads-shared-query_v0_1-20261107`ではなく正確に `review/goodreads-shared-query-v0_1-20261107`。
- 旧Project W identity、OL Edition、OA v2/v3、223,115 production decisions、600 holdout、Goodreads crosswalk、元80 W表を変更しない。
- 新しいレビュー承認とscope判定は別versionファイルに保存。AI証拠案やAI `IN_SCOPE_CANDIDATE` を人間の`IN_SCOPE`へ昇格させない。
- Original OL edition minimum != original first-publication year; original English publication != English translation publication; query title != canonical bibliographic identity; one Project W != necessarily one independently verified conceptual literary work.
- 複数OL Workを無条件に統合しない。Gitで`git add -A`しない。ローカル作業ツリーやサーバーの未追跡・封印ファイルを無断で公開しない。
- 原著以外の英訳・再版を広義コーパスから一括削除しない。引用数・OpenAlex検索候補・Goodreads未照合・0件・NAを混同しない。

## 8. 次のチャット開始文（そのまま利用可能）

「博士論文canon-pipelineのOpenAlex学術的可視性研究を続けます。GitHubブランチ `review/goodreads-shared-query-v0_1-20261107` の `docs/HANDOFF_CANON_OPENALEX_NARROW_SCOPE_2026-11-07.md` を最初に読んでください。広義コーパス32,066 Wを保持したまま、英語原著の長編・中編小説と単著短編集を含める暫定scope v0.2を検討中です。独立無作為80 WのAI書誌点検は終わったが、正式研究者判定は0件。既存の15 Wレビュー用TSVを使い、実際のOL Work/Edition・初出年・形式・原語の根拠を確認するところから始めてください。既存の凍結データ、研究者欄、OpenAlex v3は勝手に変更しないでください。」
