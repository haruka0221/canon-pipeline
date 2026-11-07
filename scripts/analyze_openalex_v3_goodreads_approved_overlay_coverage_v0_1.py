#!/usr/bin/env python3
"""Read-only coverage sensitivity for approved Goodreads source-link overlay.

This script explicitly does NOT promote Goodreads Work IDs to independent Project W
visibility metrics, modify a crosswalk, merge conceptual works, or adjudicate scope.
It computes baseline source-link coverage among the frozen 1,797 shared-query W,
then counts seven approved OL->Goodreads links as a separate evidence overlay.
Goodreads ratings/reviews are inspected solely per distinct Goodreads Work ID.

No API calls. All existing inputs are read-only. New output directory is exclusive.
Python 3.9+ standard library only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT_RELEASE = 'analysis_v3_shared_query_goodreads_approved_overlay_coverage_v0_1'
EXPECTED_OVERLAY_SHA = 'a84da92f733f86d47451aeb77c3c4324dbb118481f50068c3e5e1ea22423e09d'
EXPECTED_GROUP = {'Rosalynde': ('1534534', 3), 'East Goes West': ('1035773', 2), 'Chita': ('1930317', 2)}
EXPECTED_REVIEW_SHA = 'a46762946c534c780b410abff9e4e334e119bc6314c0731fcbabdd367e2a0e31'


def check(test, reason):
    if not test:
        raise ValueError('QC FAILED: ' + reason)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_rows(path, needed=None):
    check(path.is_file(), f'missing input: {path}')
    with path.open(encoding='utf-8-sig', newline='') as fh:
        rows = csv.DictReader(fh, delimiter='\t')
        cols = rows.fieldnames
        check(cols is not None and len(cols) == len(set(cols)), f'invalid header: {path}')
        if needed:
            check(set(needed) <= set(cols), f'missing columns in {path.name}: {sorted(set(needed)-set(cols))}')
        data = list(rows)
    check(all(None not in x and all(v is not None for v in x.values()) for x in data),
          f'malformed TSV row in {path}')
    return data


def write_tsv(path, rows, fields):
    with path.open('x', encoding='utf-8', newline='') as out:
        w = csv.DictWriter(out, fieldnames=fields, delimiter='\t', lineterminator='\n',
                           extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def norm_ol(s):
    return s.removeprefix('/works/')


def parse_count(raw):
    """Return integer or None. Fail for invalid/negative/fractional observed counts."""
    s = raw.strip()
    if s.lower() in ('', 'na', 'nan', 'none', 'null'):
        return None
    try:
        n = Decimal(s)
    except InvalidOperation:
        raise ValueError(f'QC FAILED: malformed numeric Goodreads count: {s[:60]}')
    check(n.is_finite() and n >= 0 and n == n.to_integral_value(),
          f'invalid/noninteger/negative count: {s[:60]}')
    return int(n)


def uc_metric_evidence(path, ids):
    """Scan historical carrier for exactly three approved GR work IDs."""
    check(path.is_file(), f'missing UCSD metric carrier: {path}')
    found = defaultdict(list)
    with path.open(encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh, delimiter='\t')
        needed = {'work_id', 'ratings_count', 'text_reviews_count'}
        check(reader.fieldnames is not None and needed <= set(reader.fieldnames),
              'UCSD metric carrier columns changed')
        for row in reader:
            if row['work_id'].strip() not in ids:
                continue
            found[row['work_id'].strip()].append((
                parse_count(row['ratings_count']), parse_count(row['text_reviews_count'])))
    response = {}
    for gid in ids:
        pairs = found[gid]
        if not pairs:
            response[gid] = dict(status='NO_HISTORICAL_CARRIER_ROWS', source_rows=0,
                                 ratings=None, text_reviews=None)
            continue
        distinct = []
        for k in (0, 1):
            vals = {pair[k] for pair in pairs if pair[k] is not None}
            distinct.append(vals)
        if any(len(s) > 1 for s in distinct):
            response[gid] = dict(status='CONFLICTING_HISTORICAL_CARRIER_VALUES',
                                 source_rows=len(pairs), ratings=None, text_reviews=None)
        else:
            rx = next(iter(distinct[0])) if distinct[0] else None
            tx = next(iter(distinct[1])) if distinct[1] else None
            state = ('RATINGS_AND_REVIEWS_PRESENT' if rx is not None and tx is not None
                     else 'ONLY_ONE_COUNT_PRESENT' if rx is not None or tx is not None
                     else 'NO_NUMERIC_COUNTS')
            response[gid] = dict(status=state, source_rows=len(pairs),
                                 ratings=rx, text_reviews=tx)
    return response


def run(args):
    root = args.repo_root.resolve()
    overlay = root / 'derived/identity/goodreads_shared_query_3groups_match_review_evidence_v0_1/approved_ol_goodreads_source_identity_overlay_v0_1.tsv'
    overlay_manifest = overlay.parent / 'release_manifest_v0_1.json'
    original_review = overlay.parent / 'goodreads_shared_query_3groups_approved_match_review_v0_1_2026-11-06.tsv'
    risk = root / 'derived/openalex_production/analysis_v3_shared_query_goodreads_missingness_v0_1/risk_w_goodreads_resolution_audit.tsv'
    comparison = root / 'derived/openalex_production/analysis_v3_ol_goodreads_provisional_comparison_v0_2/all_project_w_provisional_visibility_ol_goodreads.tsv'
    crosswalk = root / 'derived/crosswalks/goodreads_work_crosswalk_v1.tsv'
    ucsd = root / 'derived/goodreads_ucsd_match.tsv'
    out = args.output_dir.resolve() if args.output_dir else (root / 'derived/openalex_production' / ROOT_RELEASE)
    inputs = [overlay, overlay_manifest, original_review, risk, comparison, crosswalk, ucsd]
    for p in inputs:
        check(p.is_file(), f'missing input: {p}')
    if not args.check_only:
        check(not out.exists(), f'output already exists (refusing overwrite): {out}')

    man = json.loads(overlay_manifest.read_text(encoding='utf-8'))
    check(man['release'] == 'goodreads_shared_query_3groups_match_review_evidence_v0_1',
          'unexpected approved release')
    check(digest(overlay) == EXPECTED_OVERLAY_SHA == man['files'][overlay.name]['sha256'],
          'approved overlay SHA mismatch')
    check(digest(original_review) == EXPECTED_REVIEW_SHA == man['source_review_sha256'],
          'approved review SHA mismatch')
    check(man['qc']['approved_source_links'] == 7 and man['qc']['identity_merges'] == 0,
          'approved review scope unexpectedly changed')
    check(man['qc']['scope_adjudications'] == 0 and man['qc']['goodreads_metrics_added_to_w_analyses'] == 0,
          'source review unexpectedly promoted to W-level result')
    check(man['independent_upstream_qc'].get('upstream_crosswalk_checked') is True,
          'missing independent crosswalk QC in release manifest')
    check(man['independent_upstream_qc'].get('project_w_membership_checked') is True,
          'missing independent Project W QC in release manifest')
    check(digest(crosswalk) == man['independent_upstream_qc']['upstream_crosswalk_sha256'],
          'crosswalk changed since source review')

    appr = read_rows(overlay, ['review_group_label', 'project_work_id', 'ol_work_id',
             'approved_goodreads_work_id', 'source_identity_decision',
             'upstream_crosswalk_v1_decision', 'project_w_identity_decision', 'scope_decision',
             'role_in_analysis', 'goodreads_counts_attached', 'review_approval_provenance'])
    check(len(appr) == 7, 'overlay must have seven approved links')
    check(len({r['project_work_id'] for r in appr}) == 7 and
          len({r['ol_work_id'] for r in appr}) == 7, 'duplicate approved W or OL source')
    assert_pairs = {}
    group_rows = defaultdict(list)
    for r in appr:
        g = r['review_group_label']
        check(g in EXPECTED_GROUP, 'unexpected approved group: ' + g)
        check(r['approved_goodreads_work_id'] == EXPECTED_GROUP[g][0], 'unexpected GR ID: ' + g)
        check(r['source_identity_decision'] == 'MATCH' and
              r['upstream_crosswalk_v1_decision'] == 'AMBIGUOUS' and
              r['project_w_identity_decision'] == 'NOT_ADJUDICATED' and
              r['scope_decision'] == 'NOT_ADJUDICATED' and
              r['goodreads_counts_attached'] == 'NO' and
              r['role_in_analysis'] == 'SOURCE_IDENTITY_EVIDENCE_ONLY_NOT_ADOPTED_IN_W_METRICS',
              'unapproved decision promotion in overlay')
        check(r['review_approval_provenance'] == 'USER_APPROVED_IN_CHAT_2026-11-06',
              'unexpected approval provenance')
        assert_pairs[r['project_work_id']] = r
        group_rows[g].append(r)
    check({g:len(rs) for g,rs in group_rows.items()} ==
          {g:v[1] for g,v in EXPECTED_GROUP.items()}, 'approved group sizes drifted')

    # The original source crosswalk remains frozen. Verify seven rows in its actual file.
    cross = read_rows(crosswalk, ['ol_work_id', 'crosswalk_decision', 'goodreads_work_id'])
    check(len(cross) == 34789, 'source crosswalk changed in row count')
    cross_by_id = {x['ol_work_id']:x for x in cross}
    check(len(cross_by_id) == len(cross), 'duplicate OL source ID in crosswalk')
    for r in appr:
        z = cross_by_id.get(r['ol_work_id'])
        check(z is not None and z['crosswalk_decision'] == 'AMBIGUOUS' and
              z['goodreads_work_id'] == '', 'approved OL not AMBIGUOUS in v1')

    rr = read_rows(risk, ['project_work_id', 'ol_work_id', 'crosswalk_decision',
                          'shared_query_cluster_id'])
    check(len(rr) == 1797, f'expected 1,797 risk W, got {len(rr)}')
    risk_by_w = {r['project_work_id']:r for r in rr}
    check(len(risk_by_w) == 1797, 'duplicate risk W in audit')
    status = Counter(x['crosswalk_decision'] for x in rr)
    check(status == {'AMBIGUOUS': 300, 'NO_CANDIDATE': 1497},
          f'baseline risk statuses drifted: {status}')
    for wid,r in assert_pairs.items():
        base = risk_by_w.get(wid)
        check(base is not None and norm_ol(base['ol_work_id']) == r['ol_work_id'],
              f'approved OL/W missing or different in risk audit: {wid}')
        check(base['crosswalk_decision'] == 'AMBIGUOUS',
              f'approved W not AMBIGUOUS in risk audit: {wid}')
    # The distinct-gr ID diagnostic is performed without projecting GR data to W.
    allw = read_rows(comparison, ['project_work_id', 'current_ol_work_ids_json',
        'source_ol_ids_semicolon', 'accepted_goodreads_work_id',
        'accepted_goodreads_id_count', 'any_shared_query_risk',
        'goodreads_ratings_count', 'goodreads_metric_status',
        'exploratory_article_chapter_dissertation_pairs', 'scope_researcher_status'])
    check(len(allw) == 32066, f'v0.2 expected 32,066 W, got {len(allw)}')
    by_w = {r['project_work_id']:r for r in allw}
    check(len(by_w) == 32066, 'duplicate W in v0.2 all-project table')
    check(set(risk_by_w) <= set(by_w), 'risk W absent from v0.2 all-project table')
    for wid, r in assert_pairs.items():
        base = by_w[wid]
        raw = json.loads(base['current_ol_work_ids_json'])
        check(isinstance(raw, list) and r['ol_work_id'] in {norm_ol(str(z)) for z in raw},
              'approved OL not found on W in v0.2 bridge: '+wid)
        check(base['accepted_goodreads_id_count'] in ('0', '0.0') and
              base['accepted_goodreads_work_id'] == '' and
              base['goodreads_ratings_count'].strip() == '',
              'existing v0.2 already has an accepted GR identity/count for overlay W: ' + wid)
        check(base['any_shared_query_risk'].lower() in ('true', '1'),
              'approved W is not marked shared-query risk in v0.2: ' + wid)

    gr_ids = {r['approved_goodreads_work_id'] for r in appr}
    prior = defaultdict(list)
    for w in allw:
        gid = w['accepted_goodreads_work_id'].strip()
        if gid in gr_ids:
            prior[gid].append(w['project_work_id'])
    metrics = uc_metric_evidence(ucsd, gr_ids)

    output_w = []
    for base in sorted(rr, key=lambda x:x['project_work_id']):
        wid = base['project_work_id']
        a = assert_pairs.get(wid)
        output_w.append(dict(
            project_work_id=wid,
            ol_work_id=norm_ol(base['ol_work_id']),
            shared_query_cluster_id=base['shared_query_cluster_id'],
            prior_crosswalk_v1_decision=base['crosswalk_decision'],
            source_link_after_approved_overlay=('USER_APPROVED_SOURCE_MATCH_OVERLAY' if a else
                                                'NO_APPROVED_OVERLAY_SOURCE_LINK'),
            approved_goodreads_work_id=(a['approved_goodreads_work_id'] if a else ''),
            approved_group=(a['review_group_label'] if a else ''),
            project_w_identity_after_overlay='NOT_ADJUDICATED' if a else 'UNCHANGED',
            scope_after_overlay='NOT_ADJUDICATED' if a else 'UNCHANGED',
            goodreads_count_eligible_for_w_metric='NO' if a else 'NO_CHANGE',
        ))
    fields_w = list(output_w[0])
    output_group = []
    for g,(gid,size) in EXPECTED_GROUP.items():
        group = group_rows[g]
        hist = metrics[gid]
        collisions = sorted(set(prior[gid]))
        cluster_ids = sorted({risk_by_w[r['project_work_id']]['shared_query_cluster_id'] for r in group})
        output_group.append(dict(
            approved_group=g,
            goodreads_work_id=gid,
            approved_ol_source_links=size,
            approved_project_w_memberships=size,
            distinct_gr_work_ids=1,
            member_project_w_ids=';'.join(sorted(r['project_work_id'] for r in group)),
            shared_query_cluster_ids=';'.join(cluster_ids),
            historical_metric_source='UCSD_GOODREADS_SNAPSHOT_2017',
            legacy_metric_carrier_rows=hist['source_rows'],
            legacy_metric_status=hist['status'],
            historical_ratings_count=(hist['ratings'] if hist['ratings'] is not None else ''),
            historical_text_reviews_count=(hist['text_reviews'] if hist['text_reviews'] is not None else ''),
            prior_v0_2_w_using_this_gr_id_count=len(collisions),
            prior_v0_2_w_using_this_gr_id_ids=';'.join(collisions),
            project_w_merge_decision='NOT_ADJUDICATED',
            scope_decision='NOT_ADJUDICATED',
            project_w_metric_promotion='NOT_AUTHORIZED',
        ))
    fields_group = list(output_group[0])
    amended = Counter(row['source_link_after_approved_overlay'] for row in output_w)
    check(amended['USER_APPROVED_SOURCE_MATCH_OVERLAY'] == 7, '7 overlay coverage rows required')
    check(amended['NO_APPROVED_OVERLAY_SOURCE_LINK'] == 1790, '1,790 remaining risk W required')
    summary = {
        'release': ROOT_RELEASE,
        'analysis_state': 'EXPLORATORY_SOURCE_COVERAGE_AND_GR_ID_METRIC_AVAILABILITY_ONLY',
        'coverage_unit': 'project_w_with_at_least_one_approved_OL_to_Goodreads_source_link',
        'denominator_shared_query_risk_project_w': 1797,
        'baseline_crosswalk_v1': {'match_w': 0, 'ambiguous_w': 300,
                                  'no_candidate_w':1497},
        'approved_overlay': {
            'source_ol_links':7, 'project_w_with_approved_link':7,
            'distinct_goodreads_work_ids':3,
            'fraction_of_1797_w_with_approved_source_link': round(7/1797, 8),
            'percent_of_1797_w_with_approved_source_link': round(100*7/1797, 5),
            'historical_ambiguous_w_not_in_approved_overlay':293,
            'historical_no_candidate_w_not_in_approved_overlay':1497,
            'upstream_v1_modified':False,
        },
        'distinct_gr_work_metric_observation': dict(Counter(x['status'] for x in metrics.values())),
        'historical_gr_work_ids_with_ratings_available': sum(v['ratings'] is not None for v in metrics.values()),
        'historical_gr_work_ids_with_reviews_available': sum(v['text_reviews'] is not None for v in metrics.values()),
        'project_w_metric_rows_newly_adopted':0,
        'project_w_identity_merges':0,
        'scope_adjudications':0,
        'openalex_correlation_recomputed':False,
        'comparison_population_selection_note':'Original crosswalk v1 has zero MATCH among 1,797 risk W. This is nonrandom missingness; overlay is purposefully reviewed and not representative.',
        'interpretation':'7 approved W-source memberships do NOT establish seven distinct conceptual works; the three GR IDs are also not adjudicated conceptual literary works.',
        'safeguards':[
            'No upstream data mutated', 'No Goodreads metric is copied to Project W rows',
            'No Project W merge or final scope assignment',
            'Goodreads numbers, if observed, derive from historical UCSD carrier, not current Goodreads',
            'Conflicting historical counts treated as missing and flagged',
            'Existing v0.2 correlations and OpenAlex v3 left unchanged',
        ]
    }
    # Inputs may live in separate worktree. Paths and content hashes allow independent QC.
    hashes = {str(p.relative_to(root)) if p.is_relative_to(root) else str(p):digest(p) for p in inputs}
    if args.check_only:
        print('QC PASSED (check-only, no files written)')
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    check(out.parent.is_dir(), f'output parent does not exist: {out.parent}')
    out.mkdir(exist_ok=False)
    wp = out / 'shared_query_risk_w_source_link_coverage_overlay_v0_1.tsv'
    gp = out / 'approved_goodreads_work_id_metric_availability_v0_1.tsv'
    sp = out / 'summary_v0_1.json'
    mp = out / 'manifest_v0_1.json'
    write_tsv(wp, output_w, fields_w)
    write_tsv(gp, output_group, fields_group)
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    outputs = {p.name:{'sha256':digest(p),'bytes':p.stat().st_size} for p in (wp,gp,sp)}
    manifest = {'release':ROOT_RELEASE, 'created_utc':datetime.now(timezone.utc).isoformat(),
                'status':'EXPLORATORY_NOT_SCOPE_OR_WORK_IDENTITY_ADJUDICATION',
                'input_sha256':hashes,'output_sha256':outputs,
                'output_row_counts':{wp.name:len(output_w),gp.name:len(output_group)},
                'method':'overlay on risk-W coverage; inspect historical ratings only by distinct GR Work ID; no per-W metrics projection',
                'upstream_unchanged':True}
    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
    print('QC PASSED; source coverage W 0 -> 7 / 1797; distinct approved GR Work IDs=3; W-metric promotions=0')
    print('Historical GR metric availability:', json.dumps({g:metrics[gid]['status'] for g,(gid,_) in EXPECTED_GROUP.items()}, ensure_ascii=False))
    print('OUTPUT:', out)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo-root', type=Path, default=Path.cwd(),
                   help='Existing server worktree with production analysis files')
    p.add_argument('--output-dir', type=Path, help='New, nonexistent output directory')
    p.add_argument('--check-only', action='store_true')
    args = p.parse_args()
    run(args)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
