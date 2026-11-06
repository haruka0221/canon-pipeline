# OpenAlex — 後回しにした検証と未決定事項（2026-11-06）

状態：OPEN ISSUE REGISTER。「LLM本番を終えた」ことと「学術的可視性を確定した」ことの間にある課題を保存する。解決時は根拠・担当・日時・新しい版とhashを記録。すでに凍結した結果を直接修正しない。

## 最重要の区別

`E`（source entity）／`W`（Project conceptual work）／Open Library Work／OpenAlex Work ID／検索クエリ／`(W, OA)`対象帰属／OpenAlex文献の学術的適格性／文学作品の主分析scope／一般読者・教育・出版等の可視性は、別の軸である。

- LLM VALID ≠ 全件人手検証済み、≠ 学術文献、≠ 文献での実質的な解釈、≠ 正典性。
- 同じ文献が真に別々の小説を論じているなら複数Wへの計上はありうる。一方、同じ文学作品を複数Wに分裂させて足し合わせると歪みうる。
- 「同じ題名＋著者の検索クエリ」≠「同一の文学作品」という人間確定。
- 未検索、未対応、曖昧、未評価とゼロ件を混ぜない。

## A. 高影響・方法上の未解決事項

| ID | 未解決事項 | 確認済みの事実 | あとで行うこと |
| --- | --- | --- | --- |
| OA-QC01 | W分裂・複数OL Work | 同一R2 query title+authorを共有する833グループ、1,799 Project W | 同じ作品・版／翻訳／収録物・別作品の関係を証拠つきでレビューし、元identityとは別のversioned分析関係に記録 |
| OA-QC02 | Ulysses | 3 W：W000030950→OL86318W、W000017666→OL38767940W、W000016985→OL35695219W。元v3計13,202ペア／OA union4,423／重複配置8,779 | 原典・Editionの書誌的対応確認。Edition由来最小年1914/1922/1934を別作品の証明に使わない |
| OA-QC03 | Heart of Darkness | 4 W：W000014272→OL29000391W、W000014830→OL31971259W、W000017583→OL38663W、W000030652→OL8137762W。重複配置5,851 | 単独作品と他作併録の刊行物を区別。無条件に4WをSAMEと判定しない |
| OA-QC04 | OpenAlex IDのWまたぎ共有 | v3採用173,897ペア、unique OA129,628 ID、うち24,001 IDが複数W、共有ID上に68,270ペア（39.3%） | 比較文学的な真の複数作品言及、検索クエリ共有、W分裂、誤帰属を区別。39.3%を誤一致率と呼ばない |
| OA-QC05 | 作品の主分析scope | 草案：1880〜1950年に初刊された英語原作の単独長編・中編小説。研究者による全Wの確定scopeなし | 原言語・原作年・最初の雑誌連載／単行本・作品形態・収録物を独立書誌で検証。AI候補を正式IN_SCOPEにしない |
| OA-QC06 | OpenAlex文献の適格性 | article、book-chapter、dissertation以外にbook、book-review、other、primary text等がありうる | 学術的言及、原典・版・研究書・書評・ガイド・資料等の採否規約と標本監査を別レイヤーで設計 |
| OA-QC07 | 新モデルを経由しなかったv3採用 | 3,106ペア | `route`・`disposition`・`judgment_provenance`・human evidence別に集計。人間検証済みとpolicy-acceptedを分ける |
| OA-QC08 | OpenAlex ID間の同一コンテンツ | 同じ研究内容が論文／章／preprintなど別OA IDになりうる（既存cross-route reviewでも疑い例あり） | DOI・著者・題名・版／掲載形態を照合。OA ID数と研究貢献件数を区別 |

## B. 実行は済んだが、後で監査・強化するもの

| ID | 項目 | 済んだこと／未了のこと |
| --- | --- | --- |
| OA-QC09 | 本番の完全性・manifest | 224バッチ・223,115件のID/ordinal/ラベル/件数QCはPASS。今後はsource・queue・prompt・schema・出力JSONLのhash、保存場所・バックアップ・データ権限、理由・confidence分布、費用と実行来歴を独立監査 |
| OA-QC10 | Git未追跡の成果物 | 2026-11-05 `git status --short` に本番 `derived`、LLM first-1000 runner、holdoutなどが未追跡。巨大結果や封印predictions、API秘密を無差別 `git add -A` しない。最小のコード・doc・manifestと安全なバックアップ計画を別扱い |
| OA-QC11 | 600件holdout | 全600モデル出力保存、先頭200人手盲検済み。残400人手未判定、モデル結果を封印したまま後で独立評価。未開封予測を分析・コード・プロンプトへ混入させない |
| OA-QC12 | モデルの外的妥当性 | 200人手評価の181/200一致、モデルVALIDの人手VALID率154/156。retrieval recall、ほかroute、学術文献性、作品scopeには一般化できない |
| OA-QC13 | 検索未計測 | R2/R3未検索active W352。source-light Alcott successor W000014515は未再計測。両者をゼロとしない。再取得・新経路R4等は新設計・別release |
| OA-QC14 | W分裂に対する結果の頑健性 | 2つの高影響群だけ仮union：全type 173,897→159,267、core3 146,724→134,100。正式なidentity修復ではない。上位影響から順に調べ、残り831群を研究の停止条件にしない |
| OA-QC15 | 時系列・出版年 | 2026-09-23 OpenAlex snapshotのpublication_yearと文学作品の原作初刊年は別。OL Edition最小年も原作初刊年ではない |
| OA-QC16 | 外部DBとの結合 | 現行GR crosswalkのMATCHを優先。旧UCSDデータは件数ソースとしてのみ。OL Edition登録件数は販売・増刷・ユニーク出版出来事ではない。多対多joinや欠損ゼロ化を抑止 |
| OA-QC17 | 本研究の解釈 | 学術的注目、出版上の可視性、読者からの注目、教育、デジタル保存を単一尺度にしない。記述的相関から正典形成の因果関係は言えない |

## C. 現時点の判断と禁止事項

1. 元の`project_works_v7`、OpenAlex統合v2、LLM本番results、独立human audit、holdout600を不変の根拠として保持。変更は新しいversion付き出力に限定。
2. OpenAlexの当該LLM結果に対して全件再推論は不要。追加課金・同一出力への上書きをしない。
3. 仮にUlysses 3 W、Heart of Darkness 4 Wを1作品とした感度分析を行ったが、これらは`SENS_`分析用の仮説的グループであり、正式Wの統合を許可するものではない。
4. 一次資料、書評、book、articleをtypeだけで包含／除外せず、文献適格性の採否を研究上の判断として別途固定する。
5. 未検索W、Goodreads未照合・曖昧、版数未計測、研究者scope未確定を一律ゼロやOUTに変換しない。
6. 未開封holdoutのpredictionsをGitに公開・無断参照しない。サーバーから削除もしない。

## D. 優先して閉じる順番

- P0（保全）：本番JSONL・queue・未追跡runner・manifestの所在、hash、バックアップとアクセス権、封印holdoutを確認。
- P1（分析直近）：OL×Goodreads比較でcomplete case・identityマッピング・版数の意味を監査。scope未確定の探索的結果として扱う。
- P2（本分析前）：Ulysses/Heart of Darknessのidentity、主分析scopeの根拠、OpenAlex文献適格性の規約、3,106件のプロヴェナンスをレビュー。
- P3（継続的）：ほか831の同一検索群、OA別IDの同内容重複、retrieval網羅性／時系列分析を版管理して検証。

参照：`docs/OPENALEX_2026-11-06_RETRIEVAL_LLM_PRODUCTION_HANDOFF.md`／`docs/VISIBILITY_2026-11-06_NEXT_STEPS.md`。課題解決ログは別コミットで追加し、本台帳の未解決項目がいつどう閉じられたかを追跡可能にする。
