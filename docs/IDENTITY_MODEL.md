# Identity and Scope Model v0.2

**Status:** Draft for implementation<br>
**Date:** 2026-09-25
**Supersedes:** `Identity Model v0.1` (2026-09-21)

## 1. Purpose

本プロジェクトでは、Open Library、Wikidata、Goodreads、OpenAlex、JSTOR、HathiTrust 等の複数の情報源を用いて、文学作品・著者・版・関連レコード・受容／可視性の証拠を照合する。

各情報源は異なるidentifier、粒度、書誌モデルを持つ。Open Library Work、Wikidata item、Goodreads workは、いずれも文学作品そのものと同一ではない。また、一つの概念的作品が複数のsource recordに分裂していることも、逆に一つのsource recordが版・翻訳・作品の粒度を混在させていることもある。

したがって本プロジェクトでは、以下を基本方針とする。

* source identifier と source data を保存する。
* source entity と project-level conceptual entity を区別する。
* identity判断を元データから分離し、version付きのassertionとして保持する。
* 書誌的な年、言語、版、翻訳等の証拠を、その意味と粒度を保ったまま記録する。
* 「同じ作品か」というidentity判断と、「研究対象期間に入るか」というscope判断を分離する。
* 後から判断を修正しても、過去のsource recordや照合結果を失わない。

本モデルの目的は、完全なFRBR / IFLA LRM実装や汎用knowledge graphの構築ではない。文学研究におけるentity resolution、period/scope resolution、visibility analysisのために、**元データを失わず、判断を後から検証・修正できる最小限の共通基盤**を提供することを目的とする。

---

## 2. Core principles

### 2.1 Source identifiers are preserved

Open Library ID、Wikidata QID、Goodreads ID、VIAF ID等の外部identifierは、そのまま保持する。

特定の情報源のidentifierをプロジェクト全体のmaster IDとして使用しない。

### 2.2 Source entities and project entities are distinct

外部情報源に存在するentity / recordと、本プロジェクトが研究上同一実体として扱うproject-level entityを区別する。

複数のOpen Library Workと一つのWikidata itemが同じ作品を表すと判断された場合でも、元のsource entityは削除・上書きしない。

project-level entityは分析上の派生単位であり、source recordを置き換えるものではない。

### 2.3 Identity is an assertion, not a rewritten attribute

「二つのrecordが同一人物／同一作品である」という判断は、独立したidentity assertionとして記録する。

基本decisionは以下とする。

```text
SAME
DIFFERENT
AMBIGUOUS
UNRESOLVED
```

`AMBIGUOUS` / `UNRESOLVED` は、原則として自動的なproject-level統合の根拠としない。

identity assertionには少なくとも以下を保持する。

```text
assertion_id
left_entity
right_entity
identity_type
identity_decision
method
method_version
evidence
source_snapshot
created_at
```

### 2.4 Scope is separate from identity

同一作品であることと、その作品が研究対象期間・言語・ジャンルに入ることは別問題である。

例：

```text
The Prestige / Christopher Priest
identity_decision = SAME        # OL / WD等は同じ作品を指す
scope_decision    = OUT_POST1950
```

したがって、scope判断によってsource entityやproject workを削除しない。分析時にscope viewから除外する。

### 2.5 Uncertainty is preserved

不明な年、複数の候補、粒度不明なrecordを無理に確定しない。

`unknown`、`unresolved`、`ambiguous` は欠損ではなく、意味のある状態として保持する。

### 2.6 Granularity is recorded, not forced

作品、翻訳、版、volume、人物等の粒度を可能な範囲で記録する。

ただし、すべてのsource entityをFRBR / IFLA LRMの Work / Expression / Manifestation / Item に強制的に分類しない。

source-nativeな粒度を保持し、必要なproject-level relationを別途付与する。

### 2.7 Provenance is part of the data

source recordのprovenanceと、entity/scope resolutionのprovenanceを区別する。

少なくとも以下を保持する。

```text
source
dataset / API / dump
snapshot or retrieval date
source identifier
field / property (when applicable)
release / method version
SHA256 or equivalent fixed provenance when practical
```

### 2.8 Source-native evidence is not a project decision

names、aliases、P50、P577、Open Library alternate names、Goodreads contributor roles等はsource-native evidenceとして保存する。

それらはidentityやscope判断を支えることができるが、それ自体をproject-level decisionとみなさない。

---

## 3. Bibliographic reference model

### 3.1 FRBR / IFLA LRM is a reference model, not a mandatory ontology

本プロジェクトはFRBR / IFLA LRMの区別を概念整理に利用するが、完全準拠を目的としない。

おおまかな対応は以下の通りである。

```text
Project Work
    ≈ conceptual Work

translation / textual version
    ≈ Expression when distinction is analytically necessary

edition / publication
    ≈ Manifestation

individual library copy / digital object
    ≈ Item-like object when necessary
```

重要なのは、**Workの属性とManifestationの属性を混同しないこと**である。

たとえば特定editionの`publish_date`は、そのままconceptual workのoriginal publication yearを意味しない。

### 3.2 Expression is optional in the current implementation

翻訳・改稿・言語版を区別する必要がある場合はExpression相当の層を導入できるようにする。

ただしv0.2では、すべての翻訳にproject expression IDを作ることを要求しない。

まずrelationとして保存し、必要になった時点でproject expression entityを導入する。

### 3.3 LOD-friendly, but RDF is not required

project IDとsource IDを明示し、relationとprovenanceを保持することで、将来RDF / Linked Dataへ変換可能な構造を保つ。

現時点ではTSV / Parquet / DuckDBを主たる実装とし、RDF化そのものを要件としない。

---

## 4. Identifier scheme

### 4.1 Source entity

```text
E000000001
```

外部情報源に存在する個々のentity / recordを表す。

例：

```text
entity_id: E000000001
source: openlibrary
source_namespace: work
source_id: OL16583974W
entity_type: work
```

```text
entity_id: E000000002
source: wikidata
source_namespace: item
source_id: Q840974
entity_type: work
```

`E` ID自体は、異なるsource records間の同一性を意味しない。

### 4.2 Project work

```text
W000000001
```

acceptedなidentity evidenceに基づき、本プロジェクトが同一conceptual workとして扱うsource entitiesの集合を表す。

```text
W000000001
 ├── E000000001  Open Library Work
 ├── E000000002  Open Library Work
 └── E000000003  Wikidata item
```

`W` IDは外部identifierではなく、本プロジェクトの分析単位である。

### 4.3 Project person

```text
P000000001
```

同一人物と判断された複数source entitiesをまとめるproject-level identifier。

### 4.4 Identity assertion

```text
A000000001
```

source entities間のidentity判断を識別する。

### 4.5 Source snapshot

```text
S000000001
```

使用したdump / API / datasetの時点を識別する。

---

## 5. Population model

### 5.1 The frozen 34,789 rows are a source population, not the final conceptual-work population

2026-02-28 Open Library dumpから構築した34,789行は、今後も削除・上書きしない。

ただし、これを「34,789の確定した1880–1950 conceptual works」とは表現しない。

正式には以下のように位置づける。

```text
frozen source population v1
= 34,789 Open Library Work records selected by the historical dump rule
```

このreleaseは、既存のGoodreads、JSTOR、OpenAlex、Wikidata、HathiTrust等の照合結果を再現するためのanchorとして保持する。

### 5.2 Candidate population and analysis population are separate

今後は次の層を区別する。

```text
frozen source population v1
        ↓
expanded candidate population
        ↓
identity resolution
        ↓
period / language / genre scope resolution
        ↓
analysis population release
```

`expanded candidate population` は漏れを避けるための候補集合であり、それ自体を最終分析母集団とはみなさない。

`analysis population release` は、明示したscope policyとversionに基づいて作る派生releaseである。

### 5.3 Existing source matches are not discarded when scope changes

後に`OUT_PRE1880`や`OUT_POST1950`と判断された作品でも、既に取得したGoodreads / JSTOR / OpenAlex等のsource matchは削除しない。

source evidenceは保持し、最終分析viewでscope filterを適用する。

---

## 6. Temporal evidence and year semantics

### 6.1 Do not use one generic `year` field

異なる意味の年を同一列に潰さない。

最低限、以下を区別する。

```text
original_work_year
first_english_manifestation_year
manifestation_publish_year
source_reported_year
observation_year
```

すべての作品で全項目が得られる必要はない。

### 6.2 Historical Open Library `first_publish_year` semantics

現在のdump-based population builderは、Open Library Editionsの`publish_date`から各Workに対する最小観測年を取っている。

したがって既存列`first_publish_year`は、conceptual workのoriginal publication yearとして扱わない。

v0.2以降の文書・新規派生データでは、意味上以下として扱う。

```text
ol_min_observed_edition_year
```

歴史的fileの列名自体は再現性のため変更しないが、semantic aliasをdocumentationに明記する。

### 6.3 Year evidence is stored before resolution

年はsourceごとのevidenceとして保持し、直ちに一つの正解値へ上書きしない。

推奨evidence schema：

```text
year_evidence_id
project_work_id / source_entity_id
source
source_id
property_or_field
year_value
year_role
entity_granularity
snapshot_id
method
notes
```

`year_role` の例：

```text
original_publication
first_english_publication
edition_publication
source_claimed_work_year
unknown
```

### 6.4 Wikidata / Goodreads / OL years are evidence, not absolute truth

Wikidata P577やGoodreads `original_publication_year`は、conceptual work yearの有力なevidenceになり得る。

ただし、source間の矛盾や同名異作品、edition-level item、誤入力があるため、単独sourceを無条件にgoldとしない。

特に外部DBに存在しないことを、scope外の根拠としない。外部DB coverageは作品のvisibilityと相関し得るためである。

---

## 7. Period / scope resolution

### 7.1 Scope resolution is a versioned assertion

各project workについて、identityとは別にscope resolutionを保存する。

最低限のstatus：

```text
IN_SCOPE
OUT_PRE1880
OUT_POST1950
CONFLICT
UNRESOLVED
```

必要に応じて、言語・ジャンルは別軸で保持する。

例：

```text
period_status
language_status
genre_status
analysis_scope_status
```

### 7.2 Scope decision fields

推奨schema：

```text
project_work_id
scope_policy_version
period_basis
resolved_original_year
resolved_first_english_year
period_status
language_status
genre_status
analysis_scope_status
decision_method
evidence_ids
confidence_or_review_status
created_at
```

### 7.3 `period_basis` must be explicit

1880–1950という境界を何の年に適用したかを必ず明記する。

候補となるbasis：

```text
original_work_year
first_english_manifestation_year
```

この二つを混同しない。

最終analysis releaseをfreezeする前に、primary analysisがどちらを採用するかを明示的に決定する。

他方の年も可能な限り保持し、必要であればsensitivity analysisに利用できるようにする。

### 7.4 Conservative resolution rule

scopeの自動判定は、source coverageの高低を作品価値・visibilityと混同しないよう保守的に行う。

原則：

* 強い矛盾のない複数証拠が同じ年域を示す場合は自動確定可能。
* 高品質な一つのconceptual-work-level evidenceしかない場合は、method/versionを明記した上で暫定確定可能。
* Work-level yearとedition-level yearが衝突する場合は、edition yearでWork yearを上書きしない。
* source間で大きく矛盾する場合は`CONFLICT`とする。
* 外部sourceに存在しない場合は`UNRESOLVED`であり、`OUT_*`ではない。
* `UNRESOLVED`を一律に分析から除外するかどうかは、最終scope policyで別途決定する。

---

## 8. Identity and non-identity relations

identityと、entity間のその他の関係を区別する。

relationの初期候補：

```text
EDITION_OF
TRANSLATION_OF
ADAPTATION_OF
EXPRESSION_OF
DESCRIBES
CREATED_BY
```

これらを自動的に`SAME` identityとして扱わない。

特にtranslation/adaptationを同一project workに含めるかは、project-level aggregation policyとしてversion管理する。

---

## 9. Minimal implementation artifacts

v0.2の実装で最初から巨大なknowledge graphを作る必要はない。

当面の最低限のmachine-readable artifactは以下とする。

```text
source_entities.*
identity_assertions.*
project_works.*
work_identity_map.*
work_year_evidence.*
work_scope_resolution.*
```

`*` は安定releaseではTSV + Parquetを基本とする。

Source-specific visibility tables（Goodreads / OpenAlex / JSTOR等）はこれらを置き換えず、`project_work_id`またはbridgeを通じて接続する。

### 9.1 No destructive rewrite

既存の34,789-row outputsやsource-specific match filesはhistorical artifactsとして保存する。

修正は新releaseまたはderived layerとして行い、過去の結果をsilent overwriteしない。

### 9.2 Status semantics remain explicit

少なくとも以下を区別する。

```text
processed_match
processed_no_match
ambiguous
not_processed
excluded
error
```

numeric `0`、missing、unprocessedを同一視しない。

---

## 10. Current decisions and open questions

### 10.1 Decisions adopted in v0.2

* 34,789行はfrozen source populationとして保存する。
* Open Library Work IDを最終conceptual identityとみなさない。
* existing `first_publish_year`をconceptual original yearとみなさない。
* identity resolutionとscope resolutionを分離する。
* source evidenceを上書きせず、resolutionを派生層として作る。
* FRBR / IFLA LRMは概念整理に用いるが、完全実装を要求しない。
* Expression層は必要になった場合に導入可能とし、現時点で全件実装しない。
* LOD-friendlyなID/relation/provenanceを保持するが、RDF化は現時点の要件としない。
* 外部DBに存在しない作品を、それだけを理由にscope外としない。

### 10.2 Open questions before the final analysis population is frozen

* Primary period basisを`original_work_year`とするか、`first_english_manifestation_year`とするか。
* 翻訳を原作品と同一project workに集約する分析と、Expression相当として分ける分析の境界。
* adaptationのrelationと集計方針。
* project work clusterの最終確定rule。
* `UNRESOLVED` period casesをprimary analysisに含めるか、sensitivity analysisに回すか。
* confidence / manual review tierをどの粒度で持つか。
* candidate population v2をどこまで拡張してfalse negativeを回収するか。

これらは実データを確認しながらversion付きで決定する。決定後も、元のsource dataおよび過去releaseは保持する。
