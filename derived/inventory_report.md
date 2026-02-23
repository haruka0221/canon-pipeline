# canon-pipeline inventory report

## Required artifacts
- OK derived/ol_works_final_population.tsv (1516057 bytes, mtime=2026-02-22 22:37:57.316237)
- OK derived/README_population.txt (1325 bytes, mtime=2026-02-22 22:51:13.945870)
- OK derived/editions_min_year_limit50.tsv (3050 bytes, mtime=2026-02-23 16:07:42.900848)
- OK derived/year_audit_first_publish_year.tsv (3427 bytes, mtime=2026-02-23 16:10:16.796376)
- OK derived/year_audit_joined_limit50.tsv (5562 bytes, mtime=2026-02-23 16:11:44.374724)

## TSV quick stats

### derived/editions_min_year_limit50.tsv
- lines: 101
```tsv
work_id	min_year_from_editions	n_entries_in_file	n_years_found	missing_publish_date	nonmatch_publish_date	size_top
OL100237W	1912	50	50	0	0	352
OL100278W	1944	50	47	3	0	72
OL101949W	1950	24	23	1	0	24
OL10340782W	1900	20	19	1	0	20
OL10416779W	1933	16	14	2	0	16
```

### derived/year_audit_first_publish_year.tsv
- lines: 101
```tsv
work_id	work_key	first_publish_year
OL100237W	/works/OL100237W	1912
OL100278W	/works/OL100278W	1944
OL101949W	/works/OL101949W	1950
OL10340782W	/works/OL10340782W	1900
OL10416779W	/works/OL10416779W	1933
```

### derived/year_audit_joined_limit50.tsv
- lines: 101
```tsv
work_id	work_key	first_publish_year	min_year_from_editions_limit50	delta_min_minus_first	size_top	n_entries_in_file	n_years_found	missing_publish_date	nonmatch_publish_date
OL100237W	/works/OL100237W	1912	1912	0	352	50	50	0	0
OL100278W	/works/OL100278W	1944	1944	0	72	50	47	3	0
OL101949W	/works/OL101949W	1950	1950	0	24	24	23	1	0
OL10340782W	/works/OL10340782W	1900	1900	0	20	20	19	1	0
OL10416779W	/works/OL10416779W	1933	1933	0	16	16	14	2	0
```

## raw/editions_year_audit
- total json: 110
- offset json: 10

### work_ids with offsets
- OL1064284W: OL1064284W_offset50.json
- OL108735W: OL108735W_offset50.json
- OL118407W: OL118407W_offset50.json
- OL1937789W: OL1937789W_offset50.json
- OL267110W: OL267110W_offset100.json, OL267110W_offset50.json
- OL468564W: OL468564W_offset50.json
- OL472073W: OL472073W_offset100.json, OL472073W_offset50.json
- OL631009W: OL631009W_offset50.json
