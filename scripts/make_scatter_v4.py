"""
make_scatter_v6.py
v5 からの修正:
  - 同一作品が大文字小文字の表記ゆれで canonical/non-canonical に重複登録されている問題を修正
  - タイトルを小文字正規化してデdup → canonical=1 側を優先して残す
  - ラベルテキストは canonical 側のタイトル表記を使用

実行: cd ~/canon-pipeline && source .venv/bin/activate && python3 scripts/make_scatter_v6.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from adjustText import adjust_text
from pathlib import Path

BASE = Path("/home/haruka221/canon-pipeline")
OUT  = BASE / "derived/scatter_edition_sitelink_v6.png"

# ── パラメータ ────────────────────────────────────────────
NC_LABEL_MIN   = 40
TOP_N_MUST     = 60
CANON_LABEL_MIN = 0

# ── 1. データ読み込み ─────────────────────────────────────
pop = pd.read_csv(BASE / "derived/ol_dump_population_with_canonical_v2.tsv", sep="\t")
ec  = pd.read_csv(BASE / "derived/ol_edition_counts.tsv", sep="\t")
sl  = pd.read_csv(BASE / "derived/benchmark/work_sitelinks.tsv", sep="\t")

pop = pop.merge(ec[["work_key", "edition_count"]], on="work_key", how="left")
pop["edition_count"] = pop["edition_count"].fillna(0)

sl_map = dict(zip(sl["title"].str.strip().str.lower(), sl["sitelink_count"]))
pop["sitelink"] = pop["title"].str.strip().str.lower().map(sl_map).fillna(0)

# ── 2. 表記ゆれ重複の解消 ────────────────────────────────
# 正規化キーを追加し、同一キーに canonical と non-canonical が混在する場合は
# canonical=1 を優先して残す（sort して先頭を取る）
pop["title_key"] = pop["title"].str.strip().str.lower()
pop_dedup = (
    pop.sort_values("canonical", ascending=False)   # canonical=1 が先頭に来る
       .drop_duplicates(subset="title_key", keep="first")
       .reset_index(drop=True)
)

removed = len(pop) - len(pop_dedup)
print(f"表記ゆれ重複を {removed} 件除去 ({len(pop)} → {len(pop_dedup)} 件)")

canon    = pop_dedup[pop_dedup["canonical"] == 1].copy()
noncanon = pop_dedup[pop_dedup["canonical"] == 0].copy()
print(f"canonical: {len(canon)}件 / non-canonical: {len(noncanon)}件")

# ── 3. ラベル対象を決定 ──────────────────────────────────
top_n      = pop_dedup.nlargest(TOP_N_MUST, "sitelink")[
                 ["title", "edition_count", "sitelink", "canonical"]]
canon_label = canon[canon["sitelink"] >= CANON_LABEL_MIN][
                 ["title", "edition_count", "sitelink", "canonical"]]
nc_label    = noncanon[noncanon["sitelink"] >= NC_LABEL_MIN][
                 ["title", "edition_count", "sitelink", "canonical"]]

label_df = (
    pd.concat([top_n, canon_label, nc_label])
    .drop_duplicates(subset=["title"])   # dedup 済みなので title で十分
    .reset_index(drop=True)
)
print(f"ラベル対象: {len(label_df)}件")

# ── 4. 描画 ──────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(15, 9))
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

# non-canonical 背景点
bg = noncanon[~noncanon["title"].isin(label_df["title"])]
rng = np.random.default_rng(42)
jitter_y = rng.uniform(-0.4, 0.4, len(bg))
ax.scatter(bg["edition_count"], bg["sitelink"] + jitter_y,
           c="#A5A59C", s=16, alpha=0.38, linewidths=0,
           label=f"Non-canonical  (n={len(noncanon):,})")

# ラベル付き non-canonical 点
nc_labeled_pts = label_df[label_df["canonical"] == 0]
ax.scatter(nc_labeled_pts["edition_count"], nc_labeled_pts["sitelink"],
           c="#A5A59C", s=22, alpha=0.80, linewidths=0)

# canonical（濃い青）
ax.scatter(canon["edition_count"], canon["sitelink"],
           c="#1C5FA0", s=38, alpha=0.90, linewidths=0,
           label=f"PhD reading list (canonical)  (n={len(canon)})")

# ── 5. ラベル ────────────────────────────────────────────
label_df_sorted = label_df.sort_values("sitelink", ascending=False)

texts, px, py = [], [], []
for _, row in label_df_sorted.iterrows():
    x, y = float(row["edition_count"]), float(row["sitelink"])
    color = "#1C5FA0" if row["canonical"] == 1 else "#5A5A52"
    fontsize = 6.8 if row["sitelink"] >= 50 else 6.0
    t = ax.text(x, y, row["title"],
                fontsize=fontsize, color=color,
                ha="left", va="center", zorder=5)
    texts.append(t)
    px.append(x)
    py.append(y)

print(f"adjust_text 実行中 ({len(texts)} ラベル)...")
try:
    adjust_text(
        texts, x=px, y=py, ax=ax,
        arrowprops=dict(arrowstyle="-", color="#CCCCCC", lw=0.55),
        expand_text=(1.10, 1.25),
        expand_points=(1.15, 1.30),
        force_text=(0.5, 0.7),
        force_points=(0.3, 0.5),
        lim=1000,
        only_move={"points": "y", "text": "xy"},
    )
except Exception as e:
    print(f"adjust_text: {e}")

# ── 6. 軸・凡例 ──────────────────────────────────────────
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
    title=f"Labels: all canonical + nc sitelink≥{NC_LABEL_MIN} + top{TOP_N_MUST} overall",
    title_fontsize=6.5,
)

plt.tight_layout()
plt.savefig(OUT, dpi=200, bbox_inches="tight", facecolor="white")
print(f"Saved: {OUT}")