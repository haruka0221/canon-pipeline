from pathlib import Path
import pandas as pd

BASE = Path("/home/haruka221/canon-pipeline")
POP_PATH = BASE / "derived" / "ol_dump_population_with_author.tsv"
JSTOR_PATH = BASE / "derived" / "jstor_mentions.tsv"
OUT_DIR = BASE / "derived" / "benchmark"
OUT_PATH = OUT_DIR / "pilot_50_noncanonical.tsv"

OUT_DIR.mkdir(parents=True, exist_ok=True)


def sample_up_to(df, n, random_state):
    """件数がn未満でも落ちないようにサンプリングする"""
    if len(df) == 0:
        return df.copy()
    return df.sample(n=min(n, len(df)), random_state=random_state)


# 母集団読み込み
pop = pd.read_csv(POP_PATH, sep="\t")
jstor = pd.read_csv(JSTOR_PATH, sep="\t")

# work_keyの形式を合わせる（/works/OL123W → OL123W）
pop["work_key"] = pop["work_key"].astype("string")
pop["work_key_short"] = pop["work_key"].str.replace("/works/", "", regex=False)

# JSTOR側のキーを作る
# jstor_mentions.tsv に work_id がある想定だが、もし work_key しかない場合にも対応する
if "work_id" in jstor.columns:
    jstor["work_key_short"] = (
        jstor["work_id"]
        .astype("string")
        .str.replace("/works/", "", regex=False)
    )
elif "work_key" in jstor.columns:
    jstor["work_key_short"] = (
        jstor["work_key"]
        .astype("string")
        .str.replace("/works/", "", regex=False)
    )
else:
    raise KeyError("jstor_mentions.tsv に work_id または work_key 列がありません。")

if "jstor_mention_count" not in jstor.columns:
    raise KeyError("jstor_mentions.tsv に jstor_mention_count 列がありません。")

jstor["jstor_mention_count"] = pd.to_numeric(
    jstor["jstor_mention_count"],
    errors="coerce"
).fillna(0)

# JSTOR側に同じworkが複数行ある場合、最大値にまとめる
# これによりmerge後に母集団の行数が不必要に増えるのを防ぐ
jstor_small = (
    jstor[["work_key_short", "jstor_mention_count"]]
    .dropna(subset=["work_key_short"])
    .groupby("work_key_short", as_index=False)["jstor_mention_count"]
    .max()
)

# 結合
# on="work_key_short" に統一することで work_key_x / work_key_y の衝突を避ける
df = pop.merge(
    jstor_small,
    on="work_key_short",
    how="left"
)

df["jstor_mention_count"] = df["jstor_mention_count"].fillna(0)

# canonicalを数値として扱う
if "canonical" not in df.columns:
    raise KeyError("母集団ファイルに canonical 列がありません。")

df["canonical_num"] = pd.to_numeric(df["canonical"], errors="coerce").fillna(0).astype(int)

# non-canonicalのみ
nc = df[df["canonical_num"] == 0].copy()

# 著者名・タイトルがあるものに絞る
nc = nc[nc["author_name"].notna()]
nc = nc[nc["title"].notna()]
nc = nc[nc["author_name"].astype(str).str.strip() != ""]
nc = nc[nc["title"].astype(str).str.strip() != ""]

print(f"non-canonical総数: {len(nc)}件")

# グループA: JSTOR=0（shadow canon候補）
group_a_pool = nc[nc["jstor_mention_count"] == 0].sort_values("title").head(500)
group_a = sample_up_to(group_a_pool, 20, random_state=42)

# グループB: JSTOR>0（学術的に見えている非正典）
group_b_pool = nc[nc["jstor_mention_count"] > 0]
group_b = sample_up_to(group_b_pool, 20, random_state=42)

# グループC: JSTOR=0の残りから時代的カバレッジ用に追加
used_keys = set(pd.concat([group_a, group_b])["work_key"].dropna().astype(str))

group_c_pool = nc[
    (nc["jstor_mention_count"] == 0) &
    (~nc["work_key"].astype(str).isin(used_keys))
].copy()

# first_publish_yearがあるものを優先する
if "first_publish_year" in group_c_pool.columns:
    group_c_pool["first_publish_year_num"] = pd.to_numeric(
        group_c_pool["first_publish_year"],
        errors="coerce"
    )
    group_c_pool = group_c_pool.sort_values("first_publish_year_num")

group_c = sample_up_to(group_c_pool, 10, random_state=99)

# いったん結合
pilot = pd.concat([group_a, group_b, group_c], ignore_index=True)
pilot = pilot.drop_duplicates(subset="work_key")

# 重複削除後に50件未満なら、残りから補充する
if len(pilot) < 50:
    used_keys = set(pilot["work_key"].dropna().astype(str))
    filler_pool = nc[~nc["work_key"].astype(str).isin(used_keys)].copy()
    filler = sample_up_to(filler_pool, 50 - len(pilot), random_state=123)
    pilot = pd.concat([pilot, filler], ignore_index=True)
    pilot = pilot.drop_duplicates(subset="work_key")

# 出力列
cols = [
    "work_key",
    "title",
    "author_name",
    "first_publish_year",
    "jstor_mention_count",
    "canonical"
]

missing_cols = [c for c in cols if c not in pilot.columns]
if missing_cols:
    raise KeyError(f"出力に必要な列がありません: {missing_cols}")

pilot = pilot[cols].reset_index(drop=True)

pilot.to_csv(OUT_PATH, sep="\t", index=False)

print(f"\n選定件数: {len(pilot)}件")
print(f"グループA（JSTOR=0）: {len(group_a)}件")
print(f"グループB（JSTOR>0）: {len(group_b)}件")
print(f"グループC（時代分散）: {len(group_c)}件")
print(f"\nJSTOR中央値: {pilot['jstor_mention_count'].median()}")
print(f"first_publish_year範囲: {pilot['first_publish_year'].min()}〜{pilot['first_publish_year'].max()}")
print(f"\n出力先: {OUT_PATH}")

print("\n先頭10件:")
print(
    pilot[["title", "author_name", "first_publish_year", "jstor_mention_count"]]
    .head(10)
    .to_string(index=False)
)
