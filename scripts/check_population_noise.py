import pandas as pd
from pathlib import Path

BASE = Path("/home/haruka221/canon-pipeline")
pop = pd.read_csv(BASE / "derived/ol_dump_population_with_author.tsv", sep="\t")

print(f"母集団総数: {len(pop)}件\n")

# 1. 年代チェック（1880未満・1950超）
year_out = pop[
    (pop["first_publish_year"] < 1880) | (pop["first_publish_year"] > 1950)
]
print(f"=== 年代スコープ外 ===")
print(f"件数: {len(year_out)} ({len(year_out)/len(pop)*100:.1f}%)")
print(pop[pop["first_publish_year"] < 1880][["title","author_name","first_publish_year"]].head(10).to_string(index=False))

# 2. 非英語原作の疑いがあるタイトル（アクセント文字・非ASCII）
import unicodedata
def has_nonascii(s):
    if pd.isna(s): return False
    return any(ord(c) > 127 for c in str(s))

nonascii = pop[pop["title"].apply(has_nonascii)]
print(f"\n=== 非ASCII文字を含むタイトル ===")
print(f"件数: {len(nonascii)} ({len(nonascii)/len(pop)*100:.1f}%)")
print(nonascii[["title","author_name","first_publish_year"]].head(10).to_string(index=False))

# 3. ノンフィクション疑い（subject_keysに明示的なキーワード）
nonfic_keywords = ["nonfiction", "biography", "history", "handbook", 
                   "philosophy", "essays", "criticism", "autobiography"]
def has_nonfic(s):
    if pd.isna(s): return False
    s = str(s).lower()
    return any(kw in s for kw in nonfic_keywords)

nonfic = pop[pop["subject_keys_str"].apply(has_nonfic)]
print(f"\n=== ノンフィクション疑い ===")
print(f"件数: {len(nonfic)} ({len(nonfic)/len(pop)*100:.1f}%)")
print(nonfic[["title","author_name","subject_keys_str"]].head(10).to_string(index=False))

# 4. 重複チェック（同タイトル・同著者）
dupes = pop[pop.duplicated(subset=["title","author_name"], keep=False)]
print(f"\n=== 同タイトル・同著者の重複 ===")
print(f"件数: {len(dupes)} ({len(dupes)/len(pop)*100:.1f}%)")
print(dupes[["title","author_name","first_publish_year"]].head(10).to_string(index=False))

# 5. 著者名なし
no_author = pop[pop["author_name"].isna()]
print(f"\n=== 著者名なし ===")
print(f"件数: {len(no_author)} ({len(no_author)/len(pop)*100:.1f}%)")

# サマリ
print(f"\n=== ノイズ推定サマリ ===")
print(f"母集団総数:           {len(pop):>6}件")
print(f"年代スコープ外:       {len(year_out):>6}件 ({len(year_out)/len(pop)*100:.1f}%)")
print(f"非ASCII（非英語疑い）: {len(nonascii):>6}件 ({len(nonascii)/len(pop)*100:.1f}%)")
print(f"ノンフィクション疑い: {len(nonfic):>6}件 ({len(nonfic)/len(pop)*100:.1f}%)")
print(f"重複:                 {len(dupes):>6}件 ({len(dupes)/len(pop)*100:.1f}%)")
print(f"著者名なし:           {len(no_author):>6}件 ({len(no_author)/len(pop)*100:.1f}%)")
