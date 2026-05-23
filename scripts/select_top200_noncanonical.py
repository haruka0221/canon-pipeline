import pandas as pd
from pathlib import Path

BASE = Path("/home/haruka221/canon-pipeline")

pop = pd.read_csv(BASE / "derived/ol_dump_population_with_author.tsv", sep="\t")
ec  = pd.read_csv(BASE / "derived/ol_edition_counts.tsv", sep="\t")

# 結合
df = pop.merge(ec[["work_key","edition_count"]], on="work_key", how="left")
df["edition_count"] = df["edition_count"].fillna(0)

# non-canonicalのみ・著者名あり
nc = df[
    (df["canonical"] == 0) &
    (df["author_name"].notna()) &
    (df["title"].notna())
].copy()

# 版数上位200件
top200 = nc.sort_values("edition_count", ascending=False).head(200)

top200 = top200[["work_key","title","author_name",
                  "first_publish_year","edition_count"]].reset_index(drop=True)

top200.to_csv(
    BASE / "derived/benchmark/top200_noncanonical.tsv",
    sep="\t", index=False
)

print(f"選定件数: {len(top200)}件")
print(f"edition_count範囲: {top200['edition_count'].min():.0f}〜{top200['edition_count'].max():.0f}")
print(f"\n上位20件:")
print(top200[["title","author_name","edition_count"]].head(20).to_string(index=False))
