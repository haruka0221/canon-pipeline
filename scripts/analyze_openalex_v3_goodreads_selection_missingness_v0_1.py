#!/usr/bin/env python3
"""Goodreads crosswalk/metric-selection diagnostic for existing v0.2 all-W output.

Read-only source; no re-assignment of Goodreads IDs, no Project-W merging,
no literature-scope adjudication, no correlations. Supports --check-only.
"""
from __future__ import annotations
import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import tempfile

RELEASE = 'analysis_v3_goodreads_selection_missingness_v0_1'
INPUT_REL = Path('derived/openalex_production/analysis_v3_ol_goodreads_provisional_comparison_v0_2/all_project_w_provisional_visibility_ol_goodreads.tsv')
OUTPUT_REL = Path('derived/openalex_production') / RELEASE
REQUIRED = {
    'project_work_id', 'query_title_display', 'query_author_display',
    'v3_provisional_operational_pairs',
    'exploratory_article_chapter_dissertation_pairs',
    'goodreads_ratings_count', 'goodreads_text_reviews_count',
    'goodreads_identity_status', 'goodreads_metric_status',
    'accepted_goodreads_id_count', 'accepted_goodreads_work_id',
    'source_ol_work_count', 'any_shared_query_risk',
    'visibility_measurement_status', 'scope_researcher_status'
}
METRICS = {
    'OA_ALL_TYPES': 'v3_provisional_operational_pairs',
    'OA_CORE3': 'exploratory_article_chapter_dissertation_pairs'
}


def qc(condition: bool, detail: str) -> None:
    if not condition:
        raise ValueError('QC FAILED: ' + detail)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def integer(raw: str, col: str, w: str, nullable=True) -> int | None:
    s = str(raw).strip()
    if not s:
        qc(nullable, f'{w}: empty {col}')
        return None
    # Pandas nullable integer columns normally serialize as 1 or empty.
    try:
        value = int(s)
    except ValueError:
        try:
            f = float(s)
        except ValueError as exc:
            raise ValueError(f'QC FAILED: {w}: non-numeric {col}={s!r}') from exc
        qc(f.is_integer(), f'{w}: non-integer {col}={s!r}')
        value = int(f)
    qc(value >= 0, f'{w}: negative {col}={s!r}')
    return value


def flag(raw: str, w: str) -> bool:
    s = str(raw).strip().lower()
    qc(s in {'true', 'false', '0', '1'}, f'{w}: unexpected shared-query flag={raw!r}')
    return s in {'true', '1'}


def get_rows(path: Path) -> list[dict]:
    qc(path.is_file(), f'no v0.2 all-W input: {path}')
    seen: set[str] = set()
    rows = []
    with path.open('r', encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh, delimiter='\t')
        qc(reader.fieldnames is not None, 'no TSV header')
        qc(REQUIRED <= set(reader.fieldnames), f'missing columns: {sorted(REQUIRED - set(reader.fieldnames))}')
        for r in reader:
            w = r['project_work_id']
            qc(w.startswith('W') and w not in seen, f'empty/duplicate Project W {w!r}')
            seen.add(w)
            r['_all'] = integer(r['v3_provisional_operational_pairs'], 'OA_ALL_TYPES', w)
            r['_core3'] = integer(r['exploratory_article_chapter_dissertation_pairs'], 'OA_CORE3', w)
            r['_gr_ratings'] = integer(r['goodreads_ratings_count'], 'goodreads_ratings_count', w)
            r['_gr_reviews'] = integer(r['goodreads_text_reviews_count'], 'goodreads_text_reviews_count', w)
            r['_num_gr_ids'] = integer(r['accepted_goodreads_id_count'], 'accepted_goodreads_id_count', w, False)
            r['_source_ol_count'] = integer(r['source_ol_work_count'], 'source_ol_work_count', w, False)
            r['_shared_query'] = flag(r['any_shared_query_risk'], w)
            qc((r['_all'] is None) == (r['_core3'] is None), f'{w}: inconsistent OA NA between two indicators')
            if r['_core3'] is not None:
                qc(r['_core3'] <= r['_all'], f'{w}: OA core3 > all-types')
            if r['_num_gr_ids'] != 1:
                qc(r['_gr_ratings'] is None and r['_gr_reviews'] is None,
                   f'{w}: metric assigned to non-unique/absent GR work')
                qc(not r['accepted_goodreads_work_id'],
                   f'{w}: singular GR ID despite non-unique/absent accepted IDs')
            else:
                qc(bool(r['accepted_goodreads_work_id']), f'{w}: one accepted GR ID but no ID')
            if r['_gr_ratings'] is not None or r['_gr_reviews'] is not None:
                qc(r['_num_gr_ids'] == 1, f'{w}: GR metric without one accepted identity')
            if r['visibility_measurement_status'] in {
                    'NOT_QUERIED_R2_R3', 'HOLD_PRIMARY_SUCCESSOR_NOT_RERETRIEVED'}:
                qc(r['_all'] is None, f'{w}: nonmeasured OA marked as zero/nonmissing')
            rows.append(r)
    qc(len(rows) == 32066, f'expected frozen all-W frame 32066; found {len(rows)}')
    return rows


def portion(n: int, d: int) -> float | None:
    return round(n / d, 6) if d else None


def selection_record(name: str, label: str, group: list[dict]) -> dict:
    n = len(group)
    measured = [r for r in group if r['_core3'] is not None]
    nr = sum(r['_gr_ratings'] is not None for r in group)
    nrev = sum(r['_gr_reviews'] is not None for r in group)
    nr_meas = sum(r['_gr_ratings'] is not None for r in measured)
    return {
        'stratum': name, 'category': label,
        'project_w': n,
        'oa_measured_w': len(measured),
        'oa_unmeasured_w': n - len(measured),
        'oa_core3_positive_measured_w': sum(r['_core3'] > 0 for r in measured),
        'one_accepted_gr_id_w': sum(r['_num_gr_ids'] == 1 for r in group),
        'multiple_accepted_gr_ids_w': sum(r['_num_gr_ids'] > 1 for r in group),
        'gr_ratings_observed_w': nr,
        'gr_text_reviews_observed_w': nrev,
        'gr_ratings_available_among_oa_measured_w': nr_meas,
        'gr_ratings_observation_rate_all_w': portion(nr, n),
        'gr_ratings_observation_rate_oa_measured_w': portion(nr_meas, len(measured)),
    }


def count_bin(n: int | None) -> str:
    if n is None: return 'NA_NOT_MEASURED'
    if n == 0: return 'ZERO'
    if n == 1: return 'ONE'
    if n <= 4: return 'TWO_TO_FOUR'
    if n <= 9: return 'FIVE_TO_NINE'
    if n <= 24: return 'TEN_TO_24'
    if n <= 99: return '25_TO_99'
    return '100_PLUS'


def source_ol_bin(n: int) -> str:
    if n == 0: return 'ZERO_SOURCE_OL'
    if n == 1: return 'ONE_SOURCE_OL'
    return 'TWO_OR_MORE_SOURCE_OL'


def percentile(sorted_vals: list[int], fraction: float) -> float | None:
    if not sorted_vals: return None
    if len(sorted_vals) == 1: return float(sorted_vals[0])
    q = (len(sorted_vals) - 1) * fraction
    i = int(q)
    return sorted_vals[i] + (sorted_vals[min(i + 1, len(sorted_vals) - 1)] - sorted_vals[i]) * (q - i)


def dist_record(metric_name: str, category: str, group: list[dict], key: str) -> dict:
    data = sorted(r[key] for r in group if r[key] is not None)
    return {
        'academic_indicator': metric_name, 'gr_ratings_observed': category,
        'oa_measured_w': len(data),
        'oa_candidate_pair_sum': sum(data),
        'min': data[0] if data else None,
        'median': round(statistics.median(data), 4) if data else None,
        'mean': round(statistics.mean(data), 4) if data else None,
        'p90': round(percentile(data, .90), 4) if data else None,
        'p99': round(percentile(data, .99), 4) if data else None,
        'max': data[-1] if data else None,
    }


def analyze(rows: list[dict]) -> tuple[dict, dict[str, list[dict]]]:
    out = []
    out.append(selection_record('ALL_ACTIVE_W', 'ALL', rows))
    out.append(selection_record('OA_MEASUREMENT', 'MEASURED', [r for r in rows if r['_core3'] is not None]))
    out.append(selection_record('OA_MEASUREMENT', 'UNMEASURED', [r for r in rows if r['_core3'] is None]))
    for key, label in [('SHARED_R2_QUERY_RISK', True), ('SHARED_R2_QUERY_RISK', False)]:
        out.append(selection_record(key, str(label).upper(), [r for r in rows if r['_shared_query'] == label]))
    for title, fn in [
        ('OL_SOURCE_WORK_MULTIPLICITY', lambda r: source_ol_bin(r['_source_ol_count'])),
        ('GOODREADS_IDENTITY_STATUS', lambda r: r['goodreads_identity_status'] or 'BLANK'),
        ('GOODREADS_METRIC_STATUS', lambda r: r['goodreads_metric_status'] or 'BLANK'),
        ('OA_VISIBILITY_MEASUREMENT_STATUS', lambda r: r['visibility_measurement_status'] or 'BLANK'),
        ('SCOPE_RESEARCHER_STATUS', lambda r: r['scope_researcher_status'] or 'BLANK'),
        ('OA_ALL_TYPES_BIN', lambda r: count_bin(r['_all'])),
        ('OA_CORE3_BIN', lambda r: count_bin(r['_core3'])),
    ]:
        buckets: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            buckets[fn(r)].append(r)
        for label in sorted(buckets):
            out.append(selection_record(title, label, buckets[label]))

    distrib = []
    measured = [r for r in rows if r['_core3'] is not None]
    for label, key in [('OA_ALL_TYPES', '_all'), ('OA_CORE3', '_core3')]:
        for avail in [True, False]:
            group = [r for r in measured if (r['_gr_ratings'] is not None) == avail]
            distrib.append(dist_record(label, 'YES' if avail else 'NO', group, key))
        distrib.append(dist_record(label, 'ALL', measured, key))

    observed = [r for r in rows if r['_gr_ratings'] is not None]
    by_gr: dict[str, list[dict]] = defaultdict(list)
    for r in observed:
        by_gr[r['accepted_goodreads_work_id']].append(r)
    duplicate = [
        {
            'goodreads_work_id': gr,
            'project_w_count': len(items),
            'project_work_ids_semicolon': ';'.join(sorted(r['project_work_id'] for r in items)),
            'distinct_historical_ratings_counts': ';'.join(map(str, sorted(set(r['_gr_ratings'] for r in items)))),
            'distinct_historical_reviews_counts': ';'.join(map(str, sorted(set(r['_gr_reviews'] for r in items if r['_gr_reviews'] is not None)))),
        }
        for gr, items in by_gr.items() if len(items) > 1
    ]
    duplicate.sort(key=lambda d: (-d['project_w_count'], d['goodreads_work_id']))
    # Matched sample can contain distinct W IDs sharing one Goodreads Work ID.
    # Never sum their ratings as independent work-level observations.
    examples = sorted(
        (r for r in measured if r['_gr_ratings'] is None),
        key=lambda r: (-r['_core3'], -r['_all'], r['project_work_id'])
    )[:40]
    review_queue = [
        {
            'project_work_id': r['project_work_id'],
            'query_title_display_unverified': r['query_title_display'],
            'query_author_display_unverified': r['query_author_display'],
            'oa_core3_candidate_pairs': r['_core3'],
            'oa_all_type_candidate_pairs': r['_all'],
            'goodreads_identity_status': r['goodreads_identity_status'],
            'goodreads_metric_status': r['goodreads_metric_status'],
            'source_ol_work_count': r['_source_ol_count'],
            'shared_query_risk': r['_shared_query'],
            'scope_researcher_status': r['scope_researcher_status'],
        }
        for r in examples
    ]
    n_measured = len(measured)
    n_present = sum(r['_gr_ratings'] is not None for r in measured)
    n_all_present = sum(r['_gr_ratings'] is not None for r in rows)
    n_id = sum(r['_num_gr_ids'] == 1 for r in rows)
    risk = sum(r['_shared_query'] for r in rows)
    summary = {
        'release': RELEASE,
        'status': 'EXPLORATORY_SELECTION_DIAGNOSTIC_NOT_CAUSAL_NOT_SCOPE_ADJUDICATED',
        'input_population': 'frozen v0.2 32066 Project W frame',
        'all_project_w': len(rows),
        'openalex_measured_w': n_measured,
        'openalex_unmeasured_w': len(rows) - n_measured,
        'shared_query_risk_project_w': risk,
        'w_with_exactly_one_accepted_goodreads_id': n_id,
        'w_with_observed_historical_goodreads_ratings': n_all_present,
        'oa_measured_w_with_observed_historical_goodreads_ratings': n_present,
        'share_of_oa_measured_w_with_goodreads_ratings': portion(n_present, n_measured),
        'unique_observed_historical_goodreads_work_ids': len(by_gr),
        'shared_observed_goodreads_ids_across_project_w': len(duplicate),
        'project_w_in_shared_observed_goodreads_ids': sum(d['project_w_count'] for d in duplicate),
        'distribution_observed_oa_vs_goodreads_missing': distrib,
        'risk_sample_goodreads_ratings_observed': sum(r['_gr_ratings'] is not None for r in rows if r['_shared_query']),
        'nonrisk_sample_goodreads_ratings_observed': sum(r['_gr_ratings'] is not None for r in rows if not r['_shared_query']),
        'interpretation_notes': [
            'Counts are Project W units and may overcount conceptual literary works through identity splits.',
            'Goodreads observed means an accepted v0.2 ID and historical UCSD metric value; missing means identity, carrier, or ambiguity and does not imply zero readership.',
            'Academic counts represent candidate (W, OpenAlex Work ID) pairs, not verified scholarly engagements.',
            'The matched population is nonrandom: this is a descriptive selection check, not a correction for missing not at random.',
            'OA measurable-zero is not the same as OA unqueried or held/unmeasured.',
            'No scope adjudication, identity merging, Goodreads v0.1 overlay adoption, or re-estimated correlation.',
            'Existing frozen v0.2 table is the ONLY analytical frame; approved 7-source-link overlay is kept separately.'
        ]
    }
    qc(n_measured > 0 and n_present <= n_measured, 'invalid OA matched denominators')
    qc(sum(1 for r in rows if r['_all'] is None) == len(rows) - n_measured, 'OA availability mismatch')
    qc(risk == 1797, f'expected shared-query-risk frame 1797, got {risk}')
    qc(sum(r['_num_gr_ids'] > 0 for r in rows) >= n_all_present, 'accepted ID count mismatch')
    tables = {
        'goodreads_selection_by_stratum_v0_1.tsv': out,
        'oa_candidate_counts_by_goodreads_availability_v0_1.tsv': distrib,
        'shared_goodreads_metric_id_multiplicity_v0_1.tsv': duplicate,
        'high_core3_missing_goodreads_review_examples_v0_1.tsv': review_queue,
    }
    return summary, tables


def write_tsv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo-root', type=Path, required=True)
    ap.add_argument('--check-only', action='store_true')
    ap.add_argument('--output-dir', type=Path, default=None)
    args = ap.parse_args()
    root = args.repo_root.expanduser().resolve()
    source = root / INPUT_REL
    rows = get_rows(source)
    summary, tables = analyze(rows)
    print('QC PASSED', '(check-only; no files written)' if args.check_only else '(input validated)')
    print(json.dumps({k: v for k, v in summary.items() if k != 'distribution_observed_oa_vs_goodreads_missing'}, ensure_ascii=False, indent=2))
    print('OA candidate-count comparison:')
    for r in summary['distribution_observed_oa_vs_goodreads_missing']:
        print(f"  {r['academic_indicator']:12s} GR={r['gr_ratings_observed']:3s} "
              f"n={r['oa_measured_w']:6d} median={r['median']} p90={r['p90']} "
              f"sum_pairs={r['oa_candidate_pair_sum']}")
    if args.check_only: return
    out = args.output_dir or (root / OUTPUT_REL)
    out = out.expanduser().resolve()
    qc(not out.exists(), f'output directory already exists: {out}')
    qc(out.parent.is_dir(), f'output parent not found: {out.parent}')
    with tempfile.TemporaryDirectory(prefix=f'.{RELEASE}_', dir=out.parent) as t:
        stage = Path(t)
        outputs = {}
        for fn, table in tables.items():
            # Duplicate table may be empty; retain explicit header schema.
            fields = list(table[0]) if table else (
                ['goodreads_work_id', 'project_w_count', 'project_work_ids_semicolon',
                 'distinct_historical_ratings_counts', 'distinct_historical_reviews_counts']
                if fn.startswith('shared_goodreads_metric') else [])
            qc(bool(fields), f'could not derive header for {fn}')
            write_tsv(stage / fn, table, fields)
            outputs[fn] = {'rows': len(table), 'sha256': sha256(stage / fn)}
        summary_path = stage / 'summary_v0_1.json'
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        outputs[summary_path.name] = {'sha256': sha256(summary_path)}
        manifest = {
            'release': RELEASE, 'created_utc': datetime.now(timezone.utc).isoformat(),
            'input_source': str(INPUT_REL), 'input_sha256': sha256(source),
            'builder_sha256': sha256(Path(__file__)),
            'outputs': outputs,
            'no_upstream_modified': True,
            'check_only_supported': True,
        }
        (stage / 'manifest_v0_1.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        qc(not out.exists(), f'output appeared while staging: {out}')
        stage.rename(out)
    print('OUTPUT:', out)

if __name__ == '__main__':
    main()
