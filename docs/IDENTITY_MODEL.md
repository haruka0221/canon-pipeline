# Identity Model v0.1

**Status:** Draft
**Date:** 2026-09-21

## 1. Purpose

本プロジェクトでは、Open Library、Wikidata、Goodreads、OpenAlex、HathiTrust 等の複数の情報源を用いて、文学作品・著者・版・その他の関連レコードを照合する。

各情報源は、それぞれ異なるデータモデルと粒度を持つ。たとえば、Open Library の複数の Work ID が一つの概念的作品に対応する場合や、作品・翻訳・版の区別が情報源によって異なる場合がある。また、著者名についても、筆名、異綴り、別名、同名異人などが存在する。

したがって、本プロジェクトでは、いずれか一つの外部IDを全体の基準IDとするのではなく、

* 各情報源のIDとデータを保持すること
* 情報源間の同一性判断を元データから分離すること
* 判断の根拠とprovenanceを追跡可能にすること
* 必要に応じて、複数のsource entityをproject-level entityとして統合できること

を基本方針とする。

本モデルの目的は、完全なFRBR実装や汎用知識グラフの構築ではなく、文学研究におけるentity resolutionと可視性分析のために、**元データを失わず、判断を後から検証・修正できる最小限の共通基盤**を提供することである。

## 2. Principles

### 2.1 Source identifiers are preserved

Open Library ID、Wikidata QID、Goodreads ID、VIAF ID等の外部identifierは、そのまま保持する。

Open Library Work IDやWikidata QIDなど、特定の情報源のidentifierをプロジェクト全体のmaster IDとして使用しない。

### 2.2 Source entities and project entities are distinct

外部情報源に存在するentityまたはrecordと、本プロジェクトが同一実体としてまとめたproject-level entityを区別する。

たとえば、複数のOpen Library Workと一つのWikidata itemが同じ作品を表すと判断された場合でも、元の各source entityは保持する。

project-level entityは、それらを研究上同一のconceptual entityとして扱うための派生的な単位であり、外部情報源のrecordを置き換えるものではない。

また、すべてのsource entityがproject-level entityに所属する必要はない。適用されるidentity policyによって十分な同一性根拠が得られた場合にのみ、project-level entityへの統合を行う。

### 2.3 Identity is represented as an assertion

「二つのrecordが同一人物である」「同一作品である」といった判断は、元データの属性として上書きせず、独立したidentity assertionとして記録する。

identity assertionでは、対象となるentityの種類と判断結果を分離する。

例：

```text
identity_type: person
decision: SAME
```

または、

```text
identity_type: work
decision: DIFFERENT
```

identity assertionには少なくとも、

* 対象となるsource entities
* identity type
* decision
* 使用した方法
* method version
* 根拠となった情報
* 使用したsource snapshot
* 作成日時

を記録する。

### 2.4 Uncertainty is preserved

解決できないentityや複数の候補が残るentityを、無理に統合しない。

`identity_type` は当面、少なくとも以下を想定する。

```text
person
work
```

`decision` は以下を基本とする。

```text
SAME
DIFFERENT
AMBIGUOUS
UNRESOLVED
```

`AMBIGUOUS` や `UNRESOLVED` は、原則としてproject-level entityへの自動統合の根拠としない。

### 2.5 Granularity is recorded, not forced

作品、翻訳、版、volume、人物等の粒度を可能な範囲で記録する。

ただし、すべてのsource entityをFRBRの Work / Expression / Manifestation / Item に強制的に分類しない。

情報源自体のデータモデルと粒度を保持し、その間の関係を別途記述することを優先する。

### 2.6 Provenance is part of the data

データ値だけでなく、その値がどこから得られたかを追跡可能にする。

少なくとも、

* source
* dataset / API / dump
* snapshot or retrieval date
* source identifier
* 必要に応じてfield / property
* SHA256等の固定情報

を保持する。

また、source recordそのもののprovenanceと、entity resolutionによる判断のprovenanceを区別する。

### 2.7 Source-native evidence is preserved separately from identity decisions

Names, aliases, pseudonym labels, contributor roles, external identifiers,
and other relationships supplied by an external source are preserved as
source-native evidence.

Such evidence does not by itself constitute a project-level identity
decision.

For example, a Goodreads contributor role such as `pseud.` or an Open
Library `alternate_names` entry may support a `SAME` person assertion,
but the original source value and the derived identity assertion are
stored separately.

This distinction allows the project to retain what each source actually
states while keeping entity-resolution decisions independently
versioned and revisable.


## 3. Identifier Scheme

プロジェクト内部では、外部identifierとは独立した内部IDを使用する。

### 3.1 Source entity

```text
E000000001
```

外部情報源に存在する個々のentityまたはrecordを表す。

source entityでは、情報源そのものと、その情報源内でのidentifier namespaceを区別する。

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

たとえばGoodreadsにworkとcontributorの異なるidentifier体系がある場合も、

```text
source: goodreads
source_namespace: work
```

と

```text
source: goodreads
source_namespace: contributor
```

を区別できる。

`source_namespace + source_id` は外部情報源内のidentifierの意味を保持するために用い、`entity_type` は本プロジェクトで扱う際の粗いentity分類を表す。

`E` ID自体は、異なるsource records間の同一性を意味しない。

### 3.2 Project work

```text
W000000001
```

acceptedなidentity evidenceに基づいて、本プロジェクトが同一のconceptual workとして扱うsource entitiesの集合を表す。

例：

```text
W000000001
 ├── E000000001  Open Library Work
 ├── E000000002  Open Library Work
 └── E000000003  Wikidata item
```

`W` IDは外部情報源に存在するidentifierではなく、本プロジェクトの分析上の単位である。

source entityが必ずいずれかの`W` IDに所属するとは限らない。

### 3.3 Project person

```text
P000000001
```

同一人物と判断された複数のsource entitiesをまとめるためのproject-level identifier。

筆名・別名・異なる情報源のauthor recordを統合する場合などに使用する。

source entityが必ずいずれかの`P` IDに所属するとは限らない。

### 3.4 Identity assertion

```text
A000000001
```

source entities間のidentityについて行った個々の判断を識別する。

例：

```text
assertion_id: A000000001
left_entity: E000001
right_entity: E000002
identity_type: person
decision: SAME
method: same_wikidata_qid
method_version: person_identity_v0.1
```

identity assertionはproject entityそのものとは区別され、後から判断方法や根拠を検証・変更できるように保持する。

### 3.5 Source snapshot

```text
S000000001
```

使用したデータセット、dump、API取得時点等を識別する。

例：

```text
snapshot_id: S000000001
source: wikidata
dataset: full dump
snapshot_date: 2026-08-05
```

## 4. Important Distinctions

以下の三つは同一ではない。

```text
source identifier
    ↓
source entity
    ↓
project entity
```

たとえば、

```text
OL16583974W
```

はOpen Libraryにおけるidentifierであり、

```text
E000000001
```

はそのsource recordを本プロジェクト内部で参照するためのidentifierである。

さらに、

```text
W000000001
```

は、identity resolutionの結果として複数のsource entitiesを同一作品として扱うことが妥当と判断された場合にのみ作られるproject-level entityである。

したがって、Open Libraryを34,789作品の母集団として使用することと、Open Library Work IDをconceptual workの最終的なidentityとして使用することは区別する。

同様に、Wikidata QIDやGoodreads IDもproject-level identityそのものとはみなさない。

## 5. Initial Entity Types

v0.1では、必要以上に細かく分類せず、以下を基本とする。

```text
work
edition
person
volume
record
unknown
```

必要になった場合に追加する。

ここでの`entity_type`はFRBRクラスへの厳密な割当てを意味しない。

翻訳、adaptation、expression等の扱いは、この段階では固定しない。

## 6. Identity and Other Relations

identityと、entity間のその他の関係は区別する。

たとえば将来的に、

```text
TRANSLATION_OF
ADAPTATION_OF
EDITION_OF
```

等のrelationを導入する可能性があるが、これらを自動的に`SAME` identityとして扱うことはしない。

特に翻訳やadaptationを同一project workに含めるかどうかは、研究目的と実データを確認した上で別途決定する。

## 7. Current Open Questions

以下はv0.1では未確定とする。

* 翻訳を原作品と同一project workに含めるか
* adaptationをどのrelationで表現するか
* project entityを生成する具体的なcluster rule
* identity assertionのconfidence体系
* 時点の異なる同一source entityをどの粒度でversion管理するか
* external identifier（VIAF、ISNI等）をsource entityとして扱うか、identifier属性として扱うか
* sourceのentity typeとproject側のconceptual typeが異なる場合の表現方法
* source-nativeなrelationとproject-level relationをどのように区別するか

これらは実データを確認しながら決定し、決定理由とversionを記録する。
