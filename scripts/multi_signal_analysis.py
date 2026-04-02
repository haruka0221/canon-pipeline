"""
Stage 6b: Multi-Signal Agreement Analysis
==========================================
Inputs:
  derived/jstor_mentions.tsv
  derived/openalex_snapshot_mentions.tsv
  derived/wikidata_sitelinks.tsv
  derived/htrc_ol_dump_match_summary.tsv

Outputs:
  derived/multi_signal_merged.tsv       -- joined table (all 4 signals)
  derived/spearman_matrix.tsv           -- correlation matrix
  derived/multi_signal_clusters.tsv     -- work_key + type_threshold + type_kmeans
  derived/multi_signal_summary.txt      -- human-readable summary
  figures/spearman_heatmap.png          -- heatmap (if matplotlib available)

Usage:
  python3 scripts/multi_signal_analysis.py [--dry-run]

--dry-run: print column diagnostics only, exit before analysis.
"""

import argparse
import sys
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

# ── 0. Paths ──────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent   # ~/canon-pipeline
DERIVED = ROOT / "derived"
FIGURES = ROOT / "figures"
FIGURES.mkdir(exist_ok=True)

JSTOR_PATH   = DERIVED / "jstor_mentions.tsv"
OA_PATH      = DERIVED / "openalex_snapshot_mentions.tsv"
EC_PATH      = DERIVED / "ol_edition_counts.tsv"
HTRC_PATH    = DERIVED / "htrc_ol_dump_match_summary_v2.tsv"

# ── 1. Column name map (edit here if your files differ) ──────────────────────
#
# FORMAT: { "filename_stem": {"key": actual_col, "value": actual_col} }
#
# "key"   = the work identifier column (should resolve to /works/OLxxxW)
# "value" = the numeric indicator column

COL_MAP = {
    "jstor_mentions":                    {"key": "work_id",  "value": "jstor_mention_count"},
    "openalex_snapshot_mentions":        {"key": "work_key", "value": "oa_count"},
    "ol_edition_counts":                 {"key": "work_key", "value": "edition_count"},
    "htrc_ol_dump_match_summary_v2":     {"key": "work_id",  "value": "htid_count"},
}

# canonical flag source (jstor file is authoritative)
CANONICAL_SOURCE = "jstor_mentions"
CANONICAL_COL    = "canonical"

# ── 2. Helpers ────────────────────────────────────────────────────────────────

def load_tsv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t", low_memory=False)
    return df


def print_diagnostics(dfs: dict[str, pd.DataFrame]) -> None:
    print("\n=== COLUMN DIAGNOSTICS ===")
    for stem, df in dfs.items():
        cols = ", ".join(df.columns.tolist())
        print(f"\n[{stem}]")
        print(f"  rows : {len(df):,}")
        print(f"  cols : {cols}")
        cfg = COL_MAP.get(stem, {})
        key_col = cfg.get("key", "—")
        val_col = cfg.get("value", "—")
        key_ok = "✓" if key_col in df.columns else f"✗ NOT FOUND (expected: {key_col})"
        val_ok = "✓" if val_col in df.columns else f"✗ NOT FOUND (expected: {val_col})"
        print(f"  key  [{key_col}] {key_ok}")
        print(f"  value[{val_col}] {val_ok}")
    print()


def standardise_key(series: pd.Series) -> pd.Series:
    """Ensure all keys are /works/OLxxxW format (strip whitespace, add prefix if missing)."""
    s = series.astype(str).str.strip()
    # wikidata_sitelinks and htrc use bare OL123W format — normalise to /works/OL123W
    s = s.where(s.str.startswith("/works/"), "/works/" + s)
    return s


# ── 3. Build merged table ─────────────────────────────────────────────────────

def build_merged(dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    for stem, df in dfs.items():
        cfg = COL_MAP[stem]
        key_col = cfg["key"]
        val_col = cfg["value"]

        sub = df[[key_col, val_col]].copy()
        sub.rename(columns={key_col: "work_key", val_col: stem}, inplace=True)
        sub["work_key"] = standardise_key(sub["work_key"])

        # keep max per work_key (de-dup; some htrc files have multiple rows)
        sub = sub.groupby("work_key")[stem].max().reset_index()
        frames.append(sub)

    # outer join — works absent from a source get NaN (→ filled with 0 below)
    merged = frames[0]
    for f in frames[1:]:
        merged = merged.merge(f, on="work_key", how="outer")

    # attach canonical flag from jstor
    jstor_df = dfs["jstor_mentions"]
    canon_lookup = (
        jstor_df[["work_id", CANONICAL_COL]]
        .rename(columns={"work_id": "work_key"})
        .copy()
    )
    canon_lookup["work_key"] = standardise_key(canon_lookup["work_key"])
    merged = merged.merge(canon_lookup, on="work_key", how="left")

    # also attach title + author for readability
    title_lookup = (
        jstor_df[["work_id", "title", "author"]]
        .rename(columns={"work_id": "work_key"})
        .copy()
    )
    title_lookup["work_key"] = standardise_key(title_lookup["work_key"])
    merged = merged.merge(title_lookup, on="work_key", how="left")

    # fill NaN indicators with 0
    indicator_cols = list(COL_MAP.keys())
    merged[indicator_cols] = merged[indicator_cols].fillna(0)

    return merged


# ── 4. Spearman correlation matrix ────────────────────────────────────────────

def spearman_matrix(merged: pd.DataFrame, indicator_cols: list[str]) -> pd.DataFrame:
    data = merged[indicator_cols].values.astype(float)
    n = len(indicator_cols)
    rho_mat  = np.zeros((n, n))
    pval_mat = np.zeros((n, n))

    for i in range(n):
        for j in range(n):
            rho, pval = spearmanr(data[:, i], data[:, j])
            rho_mat[i, j]  = round(rho, 4)
            pval_mat[i, j] = round(pval, 4)

    rho_df  = pd.DataFrame(rho_mat,  index=indicator_cols, columns=indicator_cols)
    pval_df = pd.DataFrame(pval_mat, index=indicator_cols, columns=indicator_cols)
    return rho_df, pval_df


def plot_heatmap(rho_df: pd.DataFrame, out_path: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns

        fig, ax = plt.subplots(figsize=(6, 5))
        sns.heatmap(
            rho_df,
            annot=True, fmt=".2f",
            cmap="RdYlGn", vmin=-1, vmax=1,
            linewidths=0.5, ax=ax
        )
        ax.set_title("Spearman ρ — multi-signal indicators\n(n = all works)", fontsize=11)
        plt.tight_layout()
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"  Heatmap saved → {out_path}")
    except ImportError:
        print("  [skip] matplotlib/seaborn not installed — heatmap skipped")


# ── 5. Clustering: threshold-based (quartile) ─────────────────────────────────

def classify_threshold(row: pd.Series, thresholds: dict[str, float]) -> str:
    """
    4指標版分類:
      軸1（学術的引用）: jstor, openalex
      軸2（文化的流通）: edition_count, htid_count

      Type A: 軸1高 AND 軸2高  → 研究正典 + 文化的正典（真の正典）
      Type B: 軸2高 AND 軸1低  → 文化的に持続するが学術的に無視（hollow canon型）
      Type C: 軸1高 AND 軸2低  → 学術的に重要だが文化的持続力低（shadow canon型）
      Type D: 全低             → 忘却された作品
      Type X: 混合
    """
    cols = list(thresholds.keys())
    high = {col: (row[col] >= thresholds[col]) for col in cols}

    jstor_col   = next((c for c in cols if "jstor" in c), None)
    oa_col      = next((c for c in cols if "openalex" in c), None)
    ec_col      = next((c for c in cols if "edition" in c), None)
    htid_col    = next((c for c in cols if "htrc" in c or "htid" in c), None)

    jstor_h = high.get(jstor_col, False)
    oa_h    = high.get(oa_col, False)
    ec_h    = high.get(ec_col, False)
    htid_h  = high.get(htid_col, False) if htid_col else False

    scholarly   = jstor_h or oa_h
    cultural    = ec_h or htid_h

    if scholarly and cultural:
        return "A_true_canon"
    if cultural and not scholarly:
        return "B_popular_unscholarly"
    if scholarly and not cultural:
        return "C_scholarly_obscure"
    if not scholarly and not cultural:
        return "D_forgotten"
    return "X_mixed"


def add_threshold_clusters(merged: pd.DataFrame, indicator_cols: list[str]) -> pd.DataFrame:
    # These distributions are extremely zero-inflated (75%+ = 0 on every indicator).
    # Q3 collapses to 0 → threshold = median of NON-ZERO values per indicator.
    # Works with value=0 are always "low". Works >= non-zero median are "high".
    thresholds = {}
    print("\n  Thresholds (median of non-zero values):")
    for col in indicator_cols:
        nonzero = merged[col][merged[col] > 0]
        thr = float(nonzero.median()) if len(nonzero) > 0 else 1.0
        thresholds[col] = thr
        print(f"    {col}: {thr:.1f}  (non-zero n={len(nonzero):,} / {len(merged):,})")

    merged["type_threshold"] = merged.apply(
        lambda row: classify_threshold(row, thresholds), axis=1
    )
    return merged


# ── 6. Clustering: k-means ────────────────────────────────────────────────────

def add_kmeans_clusters(merged: pd.DataFrame, indicator_cols: list[str],
                        k: int = 4) -> pd.DataFrame:
    try:
        from sklearn.preprocessing import RobustScaler
        from sklearn.cluster import KMeans
    except ImportError:
        print("  [skip] scikit-learn not installed — k-means skipped")
        merged["type_kmeans"] = np.nan
        return merged

    X = merged[indicator_cols].values.astype(float)
    # RobustScaler handles the heavy right-skew in citation counts
    X_scaled = RobustScaler().fit_transform(X)

    km = KMeans(n_clusters=k, random_state=42, n_init=20)
    merged["type_kmeans_raw"] = km.fit_predict(X_scaled)

    # label clusters by mean jstor value (highest = cluster A etc.)
    label_map = (
        merged.groupby("type_kmeans_raw")["jstor_mentions"].mean()
        .sort_values(ascending=False)
        .reset_index()
        .reset_index()  # gives rank column
        .rename(columns={"index": "rank", "type_kmeans_raw": "cluster"})
    )
    labels = ["KM_A_high", "KM_B", "KM_C", "KM_D_low"]
    rank_to_label = dict(zip(label_map["cluster"], [labels[r] for r in label_map["rank"]]))
    merged["type_kmeans"] = merged["type_kmeans_raw"].map(rank_to_label)
    merged.drop(columns=["type_kmeans_raw"], inplace=True)

    return merged


# ── 7. Summary report ─────────────────────────────────────────────────────────

def write_summary(merged: pd.DataFrame, rho_df: pd.DataFrame,
                  pval_df: pd.DataFrame, indicator_cols: list[str],
                  out_path: Path) -> None:
    lines = []

    lines.append("=" * 60)
    lines.append("Stage 6b: Multi-Signal Agreement Analysis — Summary")
    lines.append("=" * 60)
    lines.append(f"Total works in merged table: {len(merged):,}")
    n_can = int(merged[CANONICAL_COL].sum()) if CANONICAL_COL in merged.columns else "N/A"
    lines.append(f"Canonical works (canonical=1): {n_can}")
    lines.append("")

    lines.append("── Spearman ρ matrix ──────────────────────────────────")
    lines.append(rho_df.to_string())
    lines.append("")
    lines.append("── p-values ───────────────────────────────────────────")
    lines.append(pval_df.to_string())
    lines.append("")

    # per-indicator stats split by canonical
    lines.append("── Indicator stats by canonical status ────────────────")
    for col in indicator_cols:
        can = merged[merged[CANONICAL_COL] == 1][col]
        non = merged[merged[CANONICAL_COL] == 0][col]
        lines.append(f"  {col}")
        lines.append(f"    canonical   median={can.median():.1f}  mean={can.mean():.1f}  ≥1: {(can>0).mean()*100:.1f}%")
        lines.append(f"    non-canon   median={non.median():.1f}  mean={non.mean():.1f}  ≥1: {(non>0).mean()*100:.1f}%")
    lines.append("")

    # threshold cluster distribution
    if "type_threshold" in merged.columns:
        lines.append("── Threshold cluster distribution ─────────────────────")
        ct = merged["type_threshold"].value_counts()
        lines.append(ct.to_string())
        lines.append("")
        lines.append("  [canonical breakdown per cluster]")
        ct2 = merged.groupby("type_threshold")[CANONICAL_COL].agg(["sum", "count"])
        ct2.columns = ["n_canonical", "n_total"]
        ct2["pct_canonical"] = (ct2["n_canonical"] / ct2["n_total"] * 100).round(1)
        lines.append(ct2.to_string())
        lines.append("")

    # k-means cluster distribution
    if "type_kmeans" in merged.columns and merged["type_kmeans"].notna().any():
        lines.append("── k-means cluster distribution ───────────────────────")
        ct3 = merged["type_kmeans"].value_counts()
        lines.append(ct3.to_string())
        lines.append("")
        lines.append("  [canonical breakdown per cluster]")
        ct4 = merged.groupby("type_kmeans")[CANONICAL_COL].agg(["sum", "count"])
        ct4.columns = ["n_canonical", "n_total"]
        ct4["pct_canonical"] = (ct4["n_canonical"] / ct4["n_total"] * 100).round(1)
        lines.append(ct4.to_string())
        lines.append("")

    # representative works per cluster (type_threshold)
    if "type_threshold" in merged.columns and "title" in merged.columns:
        lines.append("── Top works per threshold cluster (jstor desc) ───────")
        for cluster in merged["type_threshold"].unique():
            sub = (merged[merged["type_threshold"] == cluster]
                   .sort_values("jstor_mentions", ascending=False)
                   .head(5))
            lines.append(f"\n  [{cluster}]")
            for _, row in sub.iterrows():
                vals = "  ".join(
                    f"{col.split('_')[0]}={int(row.get(col, 0)):4d}"
                    for col in indicator_cols
                )
                lines.append(
                    f"    {row.get('title','?')[:50]:50s}  "
                    f"{vals}  "
                    f"canonical={int(row.get(CANONICAL_COL, 0))}"
                )

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Summary saved → {out_path}")


# ── 8. Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print column diagnostics only, do not run analysis.")
    args = parser.parse_args()

    print("Loading files...")
    paths = {
        "jstor_mentions":                JSTOR_PATH,
        "openalex_snapshot_mentions":    OA_PATH,
        "ol_edition_counts":             EC_PATH,
        "htrc_ol_dump_match_summary_v2": HTRC_PATH,
    }

    dfs = {}
    for stem, path in paths.items():
        if not path.exists():
            print(f"  [ERROR] Not found: {path}")
            sys.exit(1)
        dfs[stem] = load_tsv(path)
        print(f"  Loaded {stem}: {len(dfs[stem]):,} rows")

    print_diagnostics(dfs)

    if args.dry_run:
        print("--dry-run: exiting before analysis.")
        sys.exit(0)

    # Check that all expected columns exist before proceeding
    errors = []
    for stem, cfg in COL_MAP.items():
        df = dfs[stem]
        for role, col in cfg.items():
            if col not in df.columns:
                errors.append(f"  [{stem}] missing column '{col}' (role: {role})")
    if errors:
        print("\n[ABORT] Column mismatches detected. Fix COL_MAP in the script:")
        for e in errors:
            print(e)
        sys.exit(1)

    print("\nBuilding merged table...")
    merged = build_merged(dfs)
    print(f"  Merged: {len(merged):,} works")

    indicator_cols = list(COL_MAP.keys())

    print("\nComputing Spearman correlation matrix...")
    rho_df, pval_df = spearman_matrix(merged, indicator_cols)
    print(rho_df.to_string())

    print("\nThreshold-based clustering...")
    merged = add_threshold_clusters(merged, indicator_cols)

    print("\nk-means clustering (k=4)...")
    merged = add_kmeans_clusters(merged, indicator_cols, k=4)

    # Save outputs
    merged_out  = DERIVED / "multi_signal_merged.tsv"
    rho_out     = DERIVED / "spearman_matrix.tsv"
    cluster_out = DERIVED / "multi_signal_clusters.tsv"
    summary_out = DERIVED / "multi_signal_summary.txt"
    heatmap_out = FIGURES  / "spearman_heatmap.png"

    merged.to_csv(merged_out, sep="\t", index=False)
    print(f"  Merged table → {merged_out}")

    rho_df.to_csv(rho_out, sep="\t")
    print(f"  Spearman matrix → {rho_out}")

    cluster_cols = ["work_key", "title", "author", CANONICAL_COL] + indicator_cols + \
                   ["type_threshold", "type_kmeans"]
    cluster_cols = [c for c in cluster_cols if c in merged.columns]
    merged[cluster_cols].to_csv(cluster_out, sep="\t", index=False)
    print(f"  Cluster table → {cluster_out}")

    print("\nPlotting heatmap...")
    plot_heatmap(rho_df, heatmap_out)

    print("\nWriting summary...")
    write_summary(merged, rho_df, pval_df, indicator_cols, summary_out)

    print("\nDone.")


if __name__ == "__main__":
    main()