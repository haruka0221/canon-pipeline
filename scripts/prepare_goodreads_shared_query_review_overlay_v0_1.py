#!/usr/bin/env python3
"""Make a frozen, non-destructive Goodreads match-review evidence release.

No network, no upstream edits, no Project W merges, no metrics projection.
Optionally perform read-only checks against the live crosswalk and W/scope bridge.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

EXPECTED_GROUP_SIZES = {'Rosalynde': 3, 'East Goes West': 2, 'Chita': 2}
EXPECTED_GR = {'Rosalynde': '1534534', 'East Goes West': '1035773', 'Chita': '1930317'}
EXPECTED_REVIEW_SHA = 'a46762946c534c780b410abff9e4e334e119bc6314c0731fcbabdd367e2a0e31'
EXPECTED_MANIFEST_RELEASE = 'goodreads_shared_query_3groups_approved_match_review_v0_1'
OUTPUT_RELEASE = 'goodreads_shared_query_3groups_match_review_evidence_v0_1'


def assert_valid(ok: bool, msg: str) -> None:
    if not ok:
        raise ValueError('QC FAILED: ' + msg)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, delimiter='\t')
        cols = reader.fieldnames
        assert_valid(cols is not None and len(cols) == len(set(cols)), 'Invalid TSV header: ' + str(path))
        rows = list(reader)
        assert_valid(all(None not in r for r in rows), 'Extra tab-delimited fields: ' + str(path))
        return cols, rows


def write_tsv(path: Path, cols: list[str], rows: list[dict[str, str]]) -> None:
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=cols, delimiter='\t', lineterminator='\n', extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def inspect_upstream(crosswalk: Path | None, bridge: Path | None, rows: list[dict[str, str]]) -> dict:
    result = {'upstream_crosswalk_checked': False, 'project_w_membership_checked': False}
    by_ol = {r['ol_work_id']: r for r in rows}
    if crosswalk is not None:
        assert_valid(crosswalk.is_file(), f'Crosswalk missing: {crosswalk}')
        cols, all_rows = read_tsv(crosswalk)
        assert_valid({'ol_work_id', 'crosswalk_decision', 'goodreads_work_id'} <= set(cols), 'Crosswalk schema mismatch')
        assert_valid(len(all_rows) == 34789, f'Crosswalk expected 34,789 rows, got {len(all_rows)}')
        assert_valid(len({r['ol_work_id'] for r in all_rows}) == 34789, 'Crosswalk OL ids not unique')
        found = {r['ol_work_id']: r for r in all_rows if r['ol_work_id'] in by_ol}
        assert_valid(len(found) == 7, 'Seven approved OL ids not all present in crosswalk')
        for oid, r in found.items():
            assert_valid(r['crosswalk_decision'] == 'AMBIGUOUS', f'Expected historical AMBIGUOUS: {oid}')
            assert_valid(not r['goodreads_work_id'], f'Old crosswalk already has a GR accepted ID: {oid}')
        result['upstream_crosswalk_checked'] = True
        result['upstream_crosswalk_sha256'] = sha(crosswalk)
        result['upstream_crosswalk_match_status_for_7'] = 'AMBIGUOUS_FOR_ALL_SEVEN'
    if bridge is not None:
        assert_valid(bridge.is_file(), f'W bridge missing: {bridge}')
        cols, all_rows = read_tsv(bridge)
        assert_valid({'project_work_id', 'current_ol_work_ids_json'} <= set(cols), 'W bridge schema mismatch')
        assert_valid(len(all_rows) == 32066, f'Bridge expected 32,066 W, got {len(all_rows)}')
        by_w = {r['project_work_id']: r for r in all_rows}
        assert_valid(len(by_w) == len(all_rows), 'Bridge Project W IDs not unique')
        for r in rows:
            w, ol = r['project_work_id'], r['ol_work_id']
            assert_valid(w in by_w, f'Approved Project W missing from bridge: {w}')
            lst = json.loads(by_w[w]['current_ol_work_ids_json'])
            assert_valid(isinstance(lst, list), 'Expected OL list for ' + w)
            ids = {str(t).removeprefix('/works/') for t in lst}
            assert_valid(ol in ids, f'Approved source OL {ol} not attached to {w} in bridge')
        result['project_w_membership_checked'] = True
        result['project_w_bridge_sha256'] = sha(bridge)
    return result


def prepare(review: Path, manifest: Path, crosswalk: Path | None, bridge: Path | None):
    assert_valid(review.is_file() and manifest.is_file(), 'Missing approved review or manifest')
    man = json.loads(manifest.read_text(encoding='utf-8'))
    assert_valid(man['release'] == EXPECTED_MANIFEST_RELEASE, 'Manifest release mismatch')
    assert_valid(man['output_review_file']['sha256'] == EXPECTED_REVIEW_SHA, 'Manifest approved SHA unexpected')
    assert_valid(sha(review) == EXPECTED_REVIEW_SHA, 'Review TSV SHA mismatch')
    assert_valid(man['approved_gr_work_ids'] == EXPECTED_GR, 'Manifest Goodreads group IDs mismatch')
    cols, rows = read_tsv(review)
    needed = {'review_group_label', 'project_work_id', 'ol_work_id', 'goodreads_work_id_candidate',
              'human_goodreads_identity_decision', 'human_project_w_identity_decision',
              'human_scope_decision', 'current_goodreads_crosswalk_decision',
              'review_approval_provenance', 'review_group_label',
              'independent_first_publication_year_evidence', 'date_evidence_note',
              'reference_url', 'matched_book_ids', 'matched_book_title',
              'candidate_goodreads_original_publication_year_unverified',
              'scope_review_suggestion_not_approved'}
    assert_valid(needed <= set(cols), f'Missing columns: {sorted(needed-set(cols))}')
    assert_valid(len(rows) == man['approved_project_w_rows'] == 7, 'Expected seven approved rows')
    assert_valid(len({r['project_work_id'] for r in rows}) == 7, 'Project W uniqueness failed')
    assert_valid(len({r['ol_work_id'] for r in rows}) == 7, 'OL source Work uniqueness failed')
    assert_valid(Counter(r['review_group_label'] for r in rows) == EXPECTED_GROUP_SIZES, 'Group sizes unexpected')
    assert_valid(all(re.fullmatch(r'W\d{9}', r['project_work_id']) for r in rows), 'Unexpected W ID')
    assert_valid(all(re.fullmatch(r'OL\d+W', r['ol_work_id']) for r in rows), 'Unexpected OL Work ID')
    for r in rows:
        g = r['review_group_label']
        assert_valid(r['goodreads_work_id_candidate'] == EXPECTED_GR[g], 'GR match not as approved for '+g)
        for k, val in [
            ('human_goodreads_identity_decision','MATCH'),
            ('human_project_w_identity_decision','NOT_ADJUDICATED'),
            ('human_scope_decision','NOT_ADJUDICATED'),
            ('current_goodreads_crosswalk_decision','AMBIGUOUS'),
            ('review_approval_provenance','USER_APPROVED_IN_CHAT_2026-11-06')]:
            assert_valid(r[k] == val, f'{k} unexpected for {r["project_work_id"]}')
    extra = inspect_upstream(crosswalk, bridge, rows)
    return man, rows, extra


def make_outputs(review: Path, manifest: Path, man: dict, rows: list[dict[str, str]], extra: dict, out: Path):
    assert_valid(not out.exists(), f'Refusing to overwrite: {out}')
    assert_valid(out.parent.exists(), f'Output parent directory must exist: {out.parent}')
    out.mkdir()
    src_review = out / man['output_review_file']['filename']
    src_manifest = out / 'goodreads_shared_query_3groups_approved_match_review_v0_1_2026-11-06_manifest.json'
    shutil.copyfile(review, src_review)
    shutil.copyfile(manifest, src_manifest)

    cols = ['review_event_id', 'review_group_label', 'project_work_id', 'ol_work_id',
            'approved_goodreads_work_id', 'source_identity_decision', 'review_approval_provenance',
            'upstream_crosswalk_v1_decision', 'project_w_identity_decision', 'scope_decision',
            'role_in_analysis', 'goodreads_counts_attached', 'human_review_reference_file']
    approved = []
    for i, r in enumerate(sorted(rows, key=lambda r: (r['review_group_label'],r['project_work_id'])),1):
        approved.append(dict(review_event_id=f'GRSQ20261106_{i:03d}', review_group_label=r['review_group_label'],
            project_work_id=r['project_work_id'], ol_work_id=r['ol_work_id'],
            approved_goodreads_work_id=r['goodreads_work_id_candidate'], source_identity_decision='MATCH',
            review_approval_provenance=r['review_approval_provenance'],
            upstream_crosswalk_v1_decision=r['current_goodreads_crosswalk_decision'],
            project_w_identity_decision='NOT_ADJUDICATED',scope_decision='NOT_ADJUDICATED',
            role_in_analysis='SOURCE_IDENTITY_EVIDENCE_ONLY_NOT_ADOPTED_IN_W_METRICS',
            goodreads_counts_attached='NO', human_review_reference_file=src_review.name))
    overlay = out/'approved_ol_goodreads_source_identity_overlay_v0_1.tsv'
    write_tsv(overlay, cols, approved)

    group_cols = ['review_group_label','approved_goodreads_work_id', 'project_w_count', 'ol_work_count',
                  'project_work_ids_semicolon','ol_work_ids_semicolon', 'project_w_merge_decision',
                  'conceptual_work_deduplication', 'status_for_w_level_visibility','group_notes']
    groups = []
    for g in EXPECTED_GROUP_SIZES:
        rs = [r for r in approved if r['review_group_label']==g]
        groups.append(dict(review_group_label=g, approved_goodreads_work_id=EXPECTED_GR[g],
            project_w_count=str(len(rs)), ol_work_count=str(len(rs)),
            project_work_ids_semicolon=';'.join(sorted(r['project_work_id'] for r in rs)),
            ol_work_ids_semicolon=';'.join(sorted(r['ol_work_id'] for r in rs)),
            project_w_merge_decision='NOT_ADJUDICATED',
            conceptual_work_deduplication='NOT_PERFORMED',
            status_for_w_level_visibility='BLOCKED_PENDING_IDENTITY_AND_SCOPE_ADJUDICATION',
            group_notes=('Book 1542316 (user page) vs matched base review Book 1542314; same GR Work not independently verified.'
                        if g=='Rosalynde' else 'GR Work convergence is not a Project W merge decision.')))
    groups_path=out/'goodreads_shared_work_group_diagnostic_v0_1.tsv'
    write_tsv(groups_path,group_cols,groups)

    scope_cols = ['review_group_label','project_work_id','ol_work_id','approved_goodreads_work_id',
        'bibliographic_year_signal_not_adjudicated','goodreads_reported_year_unverified',
        'year_evidence_note','bibliographic_reference_url_for_review','book_id_link_evidence',
        'scope_candidate_hint_not_approved','original_language_researcher_verified',
        'work_form_researcher_verified','first_public_appearance_year_researcher_verified',
        'first_complete_work_publication_year_researcher_verified',
        'first_book_publication_year_researcher_verified','period_basis',
        'bibliographic_target_link_status','period_status','language_status','form_status',
        'analysis_scope_status','reviewer','review_date','reviewer_verification_notes']
    scope_rows=[]
    for r in sorted(rows,key=lambda r:(r['review_group_label'],r['project_work_id'])):
        scope_rows.append(dict(review_group_label=r['review_group_label'],
            project_work_id=r['project_work_id'], ol_work_id=r['ol_work_id'],
            approved_goodreads_work_id=r['goodreads_work_id_candidate'],
            bibliographic_year_signal_not_adjudicated=r['independent_first_publication_year_evidence'],
            goodreads_reported_year_unverified=r['candidate_goodreads_original_publication_year_unverified'],
            year_evidence_note=r['date_evidence_note'],
            bibliographic_reference_url_for_review=r['reference_url'],
            book_id_link_evidence=r['matched_book_ids'],
            scope_candidate_hint_not_approved=r['scope_review_suggestion_not_approved'],
            original_language_researcher_verified='',work_form_researcher_verified='',
            first_public_appearance_year_researcher_verified='',
            first_complete_work_publication_year_researcher_verified='',
            first_book_publication_year_researcher_verified='',period_basis='',
            bibliographic_target_link_status='NOT_ADJUDICATED',period_status='NOT_ADJUDICATED',
            language_status='NOT_ADJUDICATED',form_status='NOT_ADJUDICATED',
            analysis_scope_status='NOT_ADJUDICATED',reviewer='',review_date='',
            reviewer_verification_notes=''))
    scope_path=out/'scope_review_seed_not_adjudicated_v0_1.tsv'
    write_tsv(scope_path,scope_cols,scope_rows)

    release_info={
        'release':OUTPUT_RELEASE,'released_review_date':'2026-11-06',
        'status':'VERSIONED_APPROVED_SOURCE_IDENTITY_REVIEW_ONLY',
        'source_manifest_sha256':sha(src_manifest),'source_review_sha256':sha(src_review),
        'source_review_proposal_sha256_not_reverified':man['input_review_proposal']['sha256'],
        'qc':{'approved_source_links':7,'project_work_ids':7,'ol_work_ids':7,
              'goodreads_work_ids':3,'identity_merges':0,'scope_adjudications':0,
              'goodreads_metrics_added_to_w_analyses':0,'upstream_crosswalk_v1_modified':False},
        'independent_upstream_qc':extra,
        'files':{x.name:{'sha256':sha(x),'bytes':x.stat().st_size} for x in
             (src_review,src_manifest,overlay,groups_path,scope_path)},
        'limitations':['NO Project W pairwise identity adjudication',
              'NO corpus-scope adjudication',
              'NO automatic GR Work metrics projection or W-unit correlation',
              'Original Goodreads crosswalk v1 remains unchanged',
              'Goodreads Book ID and Work ID distinct',
              'Original publication and language signals not research-verified',
              'Approval of GR ID does not prove all Project W are one conceptual work']}
    (out/'release_manifest_v0_1.json').write_text(json.dumps(release_info,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('QC PASSED; review_sha256=',sha(src_review),'rows=7, groups=3, no upstream mutation')
    print('OUTPUT:',out)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--review',type=Path,required=True)
    ap.add_argument('--manifest',type=Path,required=True)
    ap.add_argument('--crosswalk',type=Path,default=None,
        help='Optional read-only existing Goodreads crosswalk v1 TSV')
    ap.add_argument('--bridge',type=Path,default=None,
        help='Optional read-only all-W scope evidence bridge TSV')
    ap.add_argument('--check-only',action='store_true',
        help='Only verify original review + optional upstream datasets; write nothing')
    ap.add_argument('--output-dir',type=Path,default=None)
    args=ap.parse_args()
    man,rows,extra=prepare(args.review,args.manifest,args.crosswalk,args.bridge)
    if args.check_only:
        print('QC PASSED; approved 7 OL/W links -> 3 GR works; optional source checks:',extra)
        return
    assert_valid(args.output_dir is not None, '--output-dir required except in --check-only')
    make_outputs(args.review,args.manifest,man,rows,extra,args.output_dir)

if __name__=='__main__':
    main()
