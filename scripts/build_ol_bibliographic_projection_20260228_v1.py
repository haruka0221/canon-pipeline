#!/usr/bin/env python3
"""Build a separate, provenance-preserving OL Edition -> Project W v7 preview.
Never overwrite an existing destination; leave all upstream releases untouched.
"""
import csv
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / 'canon-pipeline-openalex-a2val'
BASE = Path.home() / 'workshop-20261016/data_sources'
IDENTITY = REPO / 'derived/identity'
DETAILS = BASE / 'ol_editions_34792targets_tables_20260228_v1'
SLICES = BASE / 'ol_editions_34792targets_slices_20260228_v1'
DEST = REPO / 'derived/ol_bibliographic_projection_20260228_v1'
TEMP = DEST.with_name('.' + DEST.name + '.incomplete')
PINNED_COMMIT = 'dd8ee20393297edfd786fdb3566291fceccb475c'


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as fh:
        yield from csv.DictReader(fh, delimiter='\t')


def indexed(path, field):
    data = list(rows(path))
    out = {r[field]: r for r in data}
    if len(data) != len(out):
        raise ValueError(f'Duplicate keys in {path}')
    return out


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write(path, fields, iterable):
    with path.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        for row in iterable:
            writer.writerow(row)


def main():
    if DEST.exists() or TEMP.exists():
        raise FileExistsError(f'Refusing overwrite: {DEST} or {TEMP}')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    if head != PINNED_COMMIT:
        raise RuntimeError(f'Unexpected research commit: {head}')

    paths = {
        'targets': IDENTITY / 'openlibrary_analysis_targets_v1.tsv',
        'memberships': IDENTITY / 'work_identity_map_v7.tsv',
        'works': IDENTITY / 'project_works_v7.tsv',
        'summary': DETAILS / 'work_edition_summary_v1.tsv',
        'quality': SLICES / 'work_edition_quality_v1.tsv',
        'decades': SLICES / 'work_edition_by_decade_v1.tsv',
        'languages': SLICES / 'work_edition_by_language_v1.tsv',
        'details_manifest': DETAILS / 'manifest_v1.json',
        'slices_manifest': SLICES / 'manifest_v1.json',
        'target_manifest': BASE / 'ol_edition_target_set_v1/manifest_v1.json',
        'projection_manifest': BASE / 'ol_historical_edition_projection_20260228_v1/manifest_v1.json',
    }
    for p in paths.values():
        if not p.is_file():
            raise FileNotFoundError(p)

    targets = list(rows(paths['targets']))
    works = indexed(paths['works'], 'project_work_id')
    summary = indexed(paths['summary'], 'source_ol_work_id')
    quality = indexed(paths['quality'], 'source_ol_work_id')
    assert len(targets) == 34789 and len(summary) == len(quality) == 34792
    assert len(works) == 32089

    e_to_w = {}
    for row in rows(paths['memberships']):
        if row['membership_role'] != 'current_analysis_target':
            continue
        eid, wid = row['source_entity_id'], row['project_work_id']
        if eid in e_to_w:
            raise ValueError(f'Duplicate membership: {eid}')
        if works[wid]['status'] != 'active':
            raise ValueError(f'Inactive W mapped: {wid}')
        e_to_w[eid] = wid

    current = {}
    historical = set()
    mapped_count = Counter()
    w_n_sources = Counter()
    w_editions = Counter()
    w_year_unknown = Counter()
    w_language_missing = Counter()
    w_publisher_missing = Counter()
    w_multi_lang = Counter()
    w_incomplete = Counter()
    w_before_review = Counter()
    w_after_review = Counter()
    w_earliest = {}
    w_latest = {}
    source_out = []

    for row in targets:
        old = row['historical_ol_work_id']
        new = row['current_ol_work_id']
        eid = row['current_entity_id']
        if new in current or old in historical:
            raise ValueError(f'Duplicate target: {old} / {new}')
        historical.add(old)
        wid = e_to_w.get(eid, '')
        current[new] = wid
        s = summary[new]
        q = quality[new]
        n = int(s['edition_count'])
        if n != int(q['edition_count']):
            raise AssertionError(f'Quality summary mismatch: {new}')
        if int(s['editions_without_publish_year']) != int(q['year_unknown']):
            raise AssertionError(f'Year missing mismatch: {new}')
        if int(s['editions_without_language_metadata']) != int(q['language_missing']):
            raise AssertionError(f'Language missing mismatch: {new}')
        if int(s['editions_with_publish_year']) + int(q['year_unknown']) != n:
            raise AssertionError(f'Year sum mismatch: {new}')
        if int(s['editions_with_language_metadata']) + int(q['language_missing']) != n:
            raise AssertionError(f'Language sum mismatch: {new}')
        if int(s['editions_with_publisher_metadata']) + int(s['editions_without_publisher_metadata']) != n:
            raise AssertionError(f'Publisher sum mismatch: {new}')
        source_out.append(dict(
            historical_entity_id=row['historical_entity_id'],
            historical_ol_work_id=old,
            historical_ol_edition_count=summary[old]['edition_count'],
            current_entity_id=eid,
            current_ol_work_id=new,
            target_resolution=row['target_resolution'],
            project_work_id=wid,
            identity_state='ACTIVE_W' if wid else 'NO_CURRENT_W_MEMBERSHIP',
            ol_edition_record_count=n,
            year_unknown=int(q['year_unknown']),
            year_before_review_min=int(q['year_before_review_min']),
            year_after_review_max=int(q['year_after_review_max']),
            language_missing=int(q['language_missing']),
            multiple_distinct_languages=int(q['multiple_distinct_languages']),
            duplicate_language_tags=int(q['duplicate_language_tags']),
            incomplete_date=int(q['incomplete_date']),
            explicit_und_language=int(q['explicit_und_language']),
            publisher_missing=int(s['editions_without_publisher_metadata']),
            earliest_observed_edition_year=s['earliest_observed_edition_year'],
            latest_observed_edition_year=s['latest_observed_edition_year'],
        ))
        if not wid:
            continue
        mapped_count['targets'] += 1
        w_n_sources[wid] += 1
        w_editions[wid] += n
        w_year_unknown[wid] += int(q['year_unknown'])
        w_language_missing[wid] += int(q['language_missing'])
        w_publisher_missing[wid] += int(s['editions_without_publisher_metadata'])
        w_multi_lang[wid] += int(q['multiple_distinct_languages'])
        w_incomplete[wid] += int(q['incomplete_date'])
        w_before_review[wid] += int(q['year_before_review_min'])
        w_after_review[wid] += int(q['year_after_review_max'])
        if s['earliest_observed_edition_year']:
            y = int(s['earliest_observed_edition_year'])
            w_earliest[wid] = min(y, w_earliest.get(wid, y))
        if s['latest_observed_edition_year']:
            y = int(s['latest_observed_edition_year'])
            w_latest[wid] = max(y, w_latest.get(wid, y))

    if len(current) != 34789 or len(historical | set(current)) != 34792:
        raise AssertionError('Incorrect historical / current target union')
    if mapped_count['targets'] != 32689 or len(w_editions) != 32065:
        raise AssertionError('Unexpected active W coverage')
    active = {wid for wid, r in works.items() if r['status'] == 'active'}
    if active - set(w_editions) != {'W000014515'}:
        raise AssertionError('Unexpected source-light active W set')
    current_sum = sum(int(summary[ol]['edition_count']) for ol in current)
    unmapped_sum = sum(int(summary[ol]['edition_count']) for ol, w in current.items() if not w)
    if (current_sum, sum(w_editions.values()), unmapped_sum) != (421749, 367622, 54127):
        raise AssertionError('Edition coverage changed')

    source_decades = []
    source_languages = []
    w_decades = Counter()
    w_languages = Counter()
    source_decade_sum = Counter()
    source_lang_missing = Counter()
    source_lang_totals = Counter()
    for r in rows(paths['decades']):
        ol = r['source_ol_work_id']
        if ol not in current:
            continue
        n = int(r['edition_count'])
        source_decades.append(dict(current_ol_work_id=ol, decade_start_year=r['decade_start_year'],
                                   year_review_category=r['year_review_category'], edition_count=n))
        source_decade_sum[ol] += n
        if current[ol]:
            w_decades[(current[ol], r['decade_start_year'], r['year_review_category'])] += n
    for r in rows(paths['languages']):
        ol = r['source_ol_work_id']
        if ol not in current:
            continue
        n = int(r['edition_count'])
        source_languages.append(dict(current_ol_work_id=ol, language_code=r['language_code'],
                                     edition_count=n))
        source_lang_totals[ol] += n
        if r['language_code'] == '__MISSING__':
            source_lang_missing[ol] += n
        if current[ol]:
            w_languages[(current[ol], r['language_code'])] += n
    for ol in current:
        n = int(summary[ol]['edition_count'])
        if source_decade_sum[ol] != n:
            raise AssertionError(f'Decade counts mismatch: {ol}')
        if source_lang_totals[ol] < n or source_lang_missing[ol] != int(quality[ol]['language_missing']):
            raise AssertionError(f'Language counts mismatch: {ol}')

    w_out = []
    for wid in sorted(active):
        observed = wid in w_editions
        w_out.append(dict(
            project_work_id=wid,
            status=works[wid]['status'],
            edition_observation_status='CURRENT_OL_MEMBERSHIP' if observed else 'SOURCE_LIGHT_NOT_OBSERVED',
            current_ol_work_count=w_n_sources[wid] if observed else '',
            ol_edition_record_count=w_editions[wid] if observed else '',
            year_unknown=w_year_unknown[wid] if observed else '',
            year_before_review_min=w_before_review[wid] if observed else '',
            year_after_review_max=w_after_review[wid] if observed else '',
            language_missing=w_language_missing[wid] if observed else '',
            publisher_missing=w_publisher_missing[wid] if observed else '',
            multiple_distinct_languages=w_multi_lang[wid] if observed else '',
            incomplete_date=w_incomplete[wid] if observed else '',
            earliest_observed_edition_year=w_earliest.get(wid, ''),
            latest_observed_edition_year=w_latest.get(wid, ''),
        ))

    TEMP.mkdir(parents=True)
    try:
        source_cols = list(source_out[0])
        w_cols = list(w_out[0])
        files = {
            'source_ol_work_v1.tsv': (source_cols, source_out),
            'project_w_v1.tsv': (w_cols, w_out),
            'source_ol_work_by_decade_v1.tsv':
                (['current_ol_work_id','decade_start_year','year_review_category','edition_count'],
                 sorted(source_decades, key=lambda r:(r['current_ol_work_id'],r['decade_start_year'],r['year_review_category']))),
            'source_ol_work_by_language_v1.tsv':
                (['current_ol_work_id','language_code','edition_count'],
                 sorted(source_languages, key=lambda r:(r['current_ol_work_id'],r['language_code']))),
            'project_w_by_decade_v1.tsv':
                (['project_work_id','decade_start_year','year_review_category','edition_count'],
                 (dict(zip(['project_work_id','decade_start_year','year_review_category','edition_count'], (*key, n)))
                  for key, n in sorted(w_decades.items()))),
            'project_w_by_language_v1.tsv':
                (['project_work_id','language_code','edition_count'],
                 (dict(zip(['project_work_id','language_code','edition_count'], (*key, n)))
                  for key, n in sorted(w_languages.items()))),
        }
        for name, (fields, data) in files.items():
            write(TEMP / name, fields, data)
        manifest = dict(
            status='LOCAL_QC_NOT_PUBLISHED',
            created_utc=datetime.now(timezone.utc).isoformat(),
            research_commit=head,
            edition_snapshot='2026-02-28',
            dates_source='strict_parse_publish_date_v1',
            source_work_target='current_ol_work_id; historical IDs retained separately',
            edition_count_semantics='Open Library registered Edition records; not publication events',
            language_count_semantics='Edition counted once for each distinct tagged language; sum may exceed total',
            edition_link_semantics='Target extraction manifest reports zero Editions with multiple source Work links',
            identity_semantics='Project W v7 current_analysis_target only; no implicit merges; unresolved targets omitted from W totals',
            scope_semantics='No final genre, language, period or literary work scope determination',
            raw_editions_dump_sha256='NOT_CALCULATED_IN_UPSTREAM_MANIFEST',
            counts=dict(historical_target_rows=34789, current_target_rows=len(current),
                        all_extracted_target_ids=len(summary), active_works=len(active),
                        active_works_with_ol_source=len(w_editions), source_light_works=1,
                        mapped_source_works=mapped_count['targets'], unmapped_source_works=len(current)-mapped_count['targets'],
                        current_target_edition_sum=current_sum, mapped_w_edition_sum=sum(w_editions.values()),
                        unmapped_edition_sum=unmapped_sum),
            input_sha256={str(p): digest(p) for p in paths.values()},
            outputs={name:dict(bytes=(TEMP/name).stat().st_size,sha256=digest(TEMP/name)) for name in files},
        )
        (TEMP / 'manifest_v1.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        TEMP.rename(DEST)
    except Exception:
        # Preserve partial output for inspection; never delete blindly.
        raise
    print('=== OL BIBLIOGRAPHIC PROJECTION V1 ===')
    print('Output:', DEST)
    print('Status:', manifest['status'])
    print(json.dumps(manifest['counts'], indent=2))
    print('Output files:', ', '.join(manifest['outputs']))
    print('All upstream files and frozen releases unchanged.')

if __name__ == '__main__':
    main()
