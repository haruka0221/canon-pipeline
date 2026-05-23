"""
make_scatter_v3.py
実行: cd ~/canon-pipeline && source .venv/bin/activate && python3 scripts/make_scatter_v3.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from adjustText import adjust_text
from pathlib import Path

BASE = Path("/home/haruka221/canon-pipeline")
OUT  = BASE / "derived/scatter_edition_sitelink_v3.png"

# ── 1. データ読み込み ─────────────────────────────────────
pop = pd.read_csv(BASE / "derived/ol_dump_population_with_canonical.tsv", sep="\t")
ec  = pd.read_csv(BASE / "derived/ol_edition_counts.tsv", sep="\t")
sl  = pd.read_csv(BASE / "derived/benchmark/work_sitelinks.tsv", sep="\t")

pop = pop.merge(ec[["work_key", "edition_count"]], on="work_key", how="left")
pop["edition_count"] = pop["edition_count"].fillna(0)

sl_map = dict(zip(sl["title"].str.strip().str.lower(), sl["sitelink_count"]))
pop["sitelink"] = pop["title"].str.strip().str.lower().map(sl_map).fillna(0)

# ── 2. グループ分け ──────────────────────────────────────
canon    = pop[pop["canonical"] == 1].copy()
noncanon = pop[pop["canonical"] == 0].copy()

print(f"canonical: {len(canon)}件")
print(f"non-canonical: {len(noncanon)}件")

# ── 3. プロット ───────────────────────────────────────────
fig, ax = plt.subplots(figsize=(11, 7))
fig.patch.set_facecolor("white")
ax.set_facecolor("white")


# ── 4. ラベル付き作品 ────────────────────────────────────
label_titles = [
    "Ulysses", "Nineteen Eighty-Four", "The Great Gatsby",
    "Treasure Island", "The Picture of Dorian Gray",
    "Heart of Darkness", "The Time Machine",
    "Peter Pan", "The Jungle Book",
    "Strange case of Dr. Jekyll and Mr. Hyde",
    "White Fang", "Tarzan of the Apes", "The Yearling",
    "The Moon and Sixpence", "The Mystery of Cloomber",
    "The Grand Babylon Hotel", "King Coal",
    "Animal Farm", "Brave New World",
    "Alice's Adventures in Wonderland / Through the Looking Glass",
    "The Wonderful Wizard of Oz", "The Hound of the Baskervilles",
    "The Secret Garden", "The Hobbit",
    "The Wind in the Willows", "Anne of Green Gables",
    "Of Mice and Men", "The Grapes of Wrath",
    "The War of the Worlds", "Dubliners",
]

# non-canonical（グレー）
# 変更後（ラベル付き作品を除いた全件 + ラベル付き作品を別途描画）
label_set = set(t.lower() for t in label_titles)
bg = noncanon[~noncanon["title"].str.lower().isin(label_set)]
jitter_y = np.random.default_rng(42).uniform(-0.4, 0.4, len(bg))
ax.scatter(bg["edition_count"], bg["sitelink"] + jitter_y,
           c="#A5A59C", s=18, alpha=0.45, linewidths=0,
           label=f"Non-canonical  (n={len(noncanon):,})")

# ラベル付きnon-canonical作品も確実に描画
nc_labeled = noncanon[noncanon["title"].str.lower().isin(label_set)]
ax.scatter(nc_labeled["edition_count"], nc_labeled["sitelink"],
           c="#A5A59C", s=18, alpha=0.7, linewidths=0)

# canonical（濃い青）
ax.scatter(canon["edition_count"], canon["sitelink"],
           c="#1C5FA0", s=34, alpha=0.90, linewidths=0,
           label=f"PhD reading list (canonical)  (n={len(canon)})")


short_map = {
    "Alice's Adventures in Wonderland / Through the Looking Glass":
        "Alice's Adventures in Wonderland",
    "Strange case of Dr. Jekyll and Mr. Hyde": "Dr. Jekyll and Mr. Hyde",
}

all_pts = pd.concat([
    canon[["title", "edition_count", "sitelink"]],
    noncanon[noncanon["sitelink"] > 0][["title", "edition_count", "sitelink"]],
])

texts, px, py = [], [], []
for title in label_titles:
    row = all_pts[all_pts["title"] == title]
    if len(row) == 0:
        row = all_pts[all_pts["title"].str.contains(
            title.split()[0], case=False, na=False)]
    if len(row) == 0:
        continue
    row = row.iloc[0]
    x, y = float(row["edition_count"]), float(row["sitelink"])
    label = short_map.get(row["title"], row["title"])
    t = ax.text(x, y, label, fontsize=6.8, color="#1a1a1a",
                ha="left", va="center")
    texts.append(t)
    px.append(x)
    py.append(y)

try:
    adjust_text(
        texts, x=px, y=py, ax=ax,
        arrowprops=dict(arrowstyle="-", color="#BBBBBB", lw=0.65),
        expand_text=(1.2, 1.4),
        expand_points=(1.3, 1.5),
        force_text=(0.6, 0.9),
        force_points=(0.3, 0.5),
        lim=500,
    )
except Exception as e:
    print(f"adjust_text: {e}")

# ── 5. 軸・凡例 ──────────────────────────────────────────
ax.set_xlabel("Edition count (Open Library)", fontsize=10, color="#444", labelpad=7)
ax.set_ylabel("Wikidata sitelink count\n(international prominence)",
              fontsize=10, color="#444", labelpad=7)
ax.set_title(
    "Edition count and International prominence\n"
    "34,789 works, 1880–1950 English Fiction",
    fontsize=12, fontweight="medium", color="#1C1C1C", pad=12
)

ax.set_ylim(-6, 155)
ax.tick_params(labelsize=9, color="#CCC")
for spine in ax.spines.values():
    spine.set_color("#E4E4E4")
ax.grid(axis="y", color="#F2F2F2", lw=0.6, zorder=0)

ax.legend(
    fontsize=8.5, frameon=True, framealpha=0.97,
    edgecolor="#E2E2E2", loc="upper right",
    markerscale=1.3, handlelength=1.5, labelcolor="#333",
)

plt.tight_layout()
plt.savefig(OUT, dpi=200, bbox_inches="tight", facecolor="white")
print(f"Saved: {OUT}")