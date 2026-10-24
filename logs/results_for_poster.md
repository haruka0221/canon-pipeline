# DH2026 Poster Evaluation Numbers

- Source: `derived/canon_integrated.tsv`
- Population: n=34,789件
- Canonical subset: n=98件

- Match definition: numeric DBs are treated as linked when the value is `>0`; Wikidata is linked when `wikidata_qid` is present; Goodreads uses `gr_match` to separate `value>0`, `matched but 0`, and `unmatched`.
- For JSTOR/OpenAlex/HathiTrust/Open Library, this file does not expose an explicit processing-status column, so `0` cannot be split further into `searched but zero` vs. `unprocessed`.

## 1. 全体カバレッジ

| DB | マッチあり | マッチ成功・値0 | 未マッチ |
|---|---:|---:|---:|
| Open Library | n=34,789件, 100.0% | 判別不可 | n=0件, 0.0% |
| JSTOR | n=3,498件, 10.1% | 判別不可 | n=31,291件, 89.9% |
| OpenAlex | n=8,363件, 24.0% | 判別不可 | n=26,426件, 76.0% |
| HathiTrust | n=23,098件, 66.4% | 判別不可 | n=11,691件, 33.6% |
| Goodreads | n=11,300件, 32.5% | n=2件, 0.0% | n=23,487件, 67.5% |
| Wikidata | n=1,367件, 3.9% | n=0件, 0.0% | n=33,422件, 96.1% |

## 2. 複数DBに繋がった作品の分布

| 接続DB数（6DB） | 件数 |
|---|---:|
| 6DB | n=284件, 0.8% |
| 5DB | n=1,289件, 3.7% |
| 4DB | n=3,764件, 10.8% |
| 3DB | n=7,935件, 22.8% |
| 2DB | n=13,890件, 39.9% |
| 1DB | n=7,627件, 21.9% |
| 0DB | n=0件, 0.0% |

注: Open Library は母集団そのものなので `0DB` は構造上 0件、`1DB` は実質的に「Open Library のみ」です。

## 3. 学術文献のリンク状況

| 指標 | 値 |
|---|---:|
| JSTORで引用1件以上 | n=3,498件, 10.1% |
| OpenAlexで引用1件以上 | n=8,363件, 24.0% |
| JSTORまたはOpenAlexで引用1件以上 | n=9,869件, 28.4% |
| 引用ゼロ（JSTOR=0かつOpenAlex=0） | n=24,920件, 71.6% |

## 4. Canonical作品での精度

| DB | canonical (n=98) | 全体 (n=34,789) | 差分 |
|---|---:|---:|---:|
| Open Library | n=98件, 100.0% | n=34,789件, 100.0% | +0.0 pt |
| JSTOR | n=75件, 76.5% | n=3,498件, 10.1% | +66.5 pt |
| OpenAlex | n=77件, 78.6% | n=8,363件, 24.0% | +54.5 pt |
| HathiTrust | n=93件, 94.9% | n=23,098件, 66.4% | +28.5 pt |
| Goodreads | n=82件, 83.7% | n=11,300件, 32.5% | +51.2 pt |
| Wikidata | n=62件, 63.3% | n=1,367件, 3.9% | +59.3 pt |

## 5. 代表作品プロファイル

| 作品 | 採用work_key | canonical | jstor_count | oa_count | edition_count | htid_count | gr_ratings | wikidata_qid | sitelink_count | 備考 |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| Heart of Darkness (Conrad) | /works/OL31971259W | 1 | 118 | 25 | 14 | 1 | 315808 | Q129778 | 57 | 候補4件; canonical=1を採用 |
| White Fang (London) | /works/OL74504W | 1 | 0 | 29 | 387 | 2 | 117038 | Q152267 | 45 | 候補2件; canonical=1を採用 |
| Ulysses (Joyce) | /works/OL35695219W | 1 | 443 | 54 | 71 | 3 | 88298 | Q6511 | 166 | 候補3件; canonical=1を採用 |

## 6. LLM判定の信頼度分布（Goodreads照合ログ由来）

| 指標 | 値 |
|---|---:|
| 高信頼度で自動確定（UNIQUE/YEAR_AUTH/RATINGS_MAX） | n=11,202件, 32.2% |
| 低信頼度で追加判定・人手補正（LLM/MANUAL_FIX） | n=100件, 0.3% |
| 一致なし判定（NO_MATCH/NO_MATCH_AUTH） | n=23,487件, 67.5% |
| 補足: LLM最終決定のみ | n=96件, 0.3% |
| 補足: 人手補正のみ | n=4件, 0.0% |

## 7. Wikidataベンチマーク（n=130）の誤り分析

| 指標 | 値 |
|---|---:|
| False Positive（negative=48件中の誤一致） | n=1件, 2.1% |
| False Negative（positive=82件中の見逃し/誤同定） | n=4件, 4.9% |

### 誤りケースの要約
- Kim
- At Fault
- The octopus, a story of California
- Peter Pan
- The Capsina: An Historical Novel

### 類型化（暫定）
| 類型 | 件数 | 代表ケース |
|---|---:|---|
| ① ID世代ずれ | 1件 | `Kim` |
| ② 同名異著者 | 1件 | `The Capsina: An Historical Novel` |
| ③ 収録制限 | 2件 | `At Fault`, `The octopus, a story of California` |
| ④ 重複登録 | 1件 | `Peter Pan` |

### 誤り内容メモ
- Kim: 近接する別QIDへの取り違え。`OL19908W` 側に `Q589868` が付いており、同一題名の重複登録/IDずれが示唆される。
- At Fault: gold QIDはあるが `pred_qid=NO_MATCH`。sitelink 0 の疎な項目で、収録制限または探索漏れの可能性が高い。
- The octopus, a story of California: gold QIDはあるが `pred_qid=NO_MATCH`。著者作品一覧が 0件取得になっており、収録制限/取得失敗型。
- Peter Pan: `Q3435337` ではなく `Q19032697` を返しており、近接する別作品への重複登録・IDずれ型。
- The Capsina: An Historical Novel: gold は `NO_MATCH` だが `Q124087127` を返した。負例への過剰一致で、同名異著者または近接候補の誤採択とみられる。
