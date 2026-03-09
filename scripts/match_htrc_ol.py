"""
OL全件OCLC × htrc突合スクリプト
入力:
  derived/ol_dump_oclc_all.tsv  (work_id, oclc)
  data/htrc-fiction_metadata.csv
出力:
  derived/htrc_ol_dump_match.tsv      (work_id + htrc メタデータ)
  derived/htrc_ol_dump_match_summary.tsv (work_id ごとの htid 数サマリー)
"""
import pandas as pd

# OL OCLC
ol = pd.read_csv('derived/ol_dump_oclc_all.tsv',
                 sep='\t', header=None,
                 names=['work_id','oclc'],
                 dtype={'oclc': str})
ol = ol[ol['oclc'].notna() & (ol['oclc'] != '')].copy()
ol['oclc'] = ol['oclc'].str.strip()

# htrc
htrc = pd.read_csv('data/htrc-fiction_metadata.csv',
                   dtype={'oclc': str}, low_memory=False)
htrc['startdate'] = pd.to_numeric(htrc['startdate'], errors='coerce')
htrc = htrc[htrc['oclc'].notna()].copy()
htrc['oclc'] = htrc['oclc'].str.strip()

print(f"OL works (OCLC あり): {ol['work_id'].nunique()}")
print(f"htrc 全件: {len(htrc)}")

# 突合
merged = ol.merge(htrc, on='oclc', how='inner')
print(f"\n突合ヒット（行数）: {len(merged)}")
print(f"突合ヒット（ユニーク work_id）: {merged['work_id'].nunique()}")

# work_id ごとのサマリー
summary = merged.groupby('work_id').agg(
    htid_count=('htid','count'),
    oclc_variants=('oclc','nunique'),
    title_htrc=('title','first'),
    date_htrc=('date','first'),
    prob80_max=('prob80precise','max'),
    englishpct_max=('englishpct','max'),
    htids=('htid', lambda x: '|'.join(x.tolist()))
).reset_index()

print(f"\nサマリー件数: {len(summary)}")
print(summary.head(10).to_string())

merged.to_csv('derived/htrc_ol_dump_match.tsv', sep='\t', index=False)
summary.to_csv('derived/htrc_ol_dump_match_summary.tsv', sep='\t', index=False)
print("\n→ derived/htrc_ol_dump_match.tsv に保存")
print("→ derived/htrc_ol_dump_match_summary.tsv に保存")
