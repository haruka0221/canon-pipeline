#!/usr/bin/env python3
"""Build a NON-adjudicated 80-W researcher review sheet from frozen evidence.

No identity, OpenAlex, original evidence, or researcher decisions are modified.
Requires pandas. Read-only --dry-run; output refuses overwrite.
"""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd


SRC_REGISTER = Path('derived/scope/random_scope_review_draft_v0_10/random_scope_80_ai_exploratory_register_v0_1.tsv')
SRC_COMBINED = Path('derived/scope/scope_combined_bibliographic_evidence_v0_1/scope_combined_project_w_bibliographic_evidence_v0_1.tsv')
SRC_SAMPLE = Path('derived/scope/scope_evidence_pilot_v1/scope_evidence_review_template_v1.tsv')
DEFAULT_OUT = Path('derived/scope/random_scope_80_researcher_evidence_sheet_v0_1')
RANDOM_SEED = 'scope-random80-first10-20261020'

REVIEW_FIELDS = [
    'reviewer_bibliographic_target_confirmed',
    'reviewer_work_form',
    'reviewer_original_language',
    'reviewer_first_public_appearance_year',
    'reviewer_first_complete_publication_year',
    'reviewer_first_book_publication_year',
    'reviewer_first_english_manifestation_year',
    'reviewer_period_basis',
    'reviewer_period_status',
    'reviewer_language_status',
    'reviewer_form_status',
    'reviewer_analysis_scope_status',
    'reviewer_checked_evidence_ids_or_urls',
    'reviewer_source_claim_checks',
    'reviewer_name',
    'reviewer_date',
    'reviewer_notes',
]

CRITICISM_TERMS = (
    'history_and_criticism',
    'criticism_and_interpretation',
    'literary_criticism',
    'histoire_et_critique',
)
TITLE_PATTERN = re.compile(
    r'\b(and other stories|short stories|finding list|guide to the best fiction)\b', re.I
)


def read_tsv(path):
    return pd.read_csv(path, sep='\t', dtype=str, keep_default_na=False)


def array(cell):
    if not cell:
        return []
    result = json.loads(cell)
    if not isinstance(result, list):
        raise ValueError('Expected a JSON list, got ' + repr(cell)[:120])
    return result


def ids_years(cell):
    return [int(str(x)) for x in array(cell) if re.fullmatch(r'\d{4}', str(x))]


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def verify_frozen_sample(sample, register):
    flag = 'is_independent_random_active_sample'
    if flag not in sample.columns:
        raise ValueError(f'Missing sampling column {flag}')
    selected = sample.loc[sample[flag].str.lower().eq('true'), 'project_work_id']
    if len(selected) != 80 or not selected.is_unique:
        raise ValueError('The frozen 80-W sample must contain exactly 80 distinct W')
    ordered = sorted(
        selected.tolist(),
        key=lambda w: hashlib.sha256((RANDOM_SEED + '\x1f' + w).encode('utf-8')).hexdigest(),
    )
    ranks = register['random_rank'].astype(int).tolist()
    if ranks != list(range(1, 81)):
        raise ValueError('Register must be in fixed review-rank order 1..80')
    if register['project_work_id'].tolist() != ordered:
        raise ValueError('Register does not match frozen random sample membership/order')


def build(register, combined):
    if len(register) != 80 or not register.project_work_id.is_unique:
        raise ValueError('Exploratory register must contain exactly 80 distinct W')
    if len(combined) != 32066 or not combined.project_work_id.is_unique:
        raise ValueError('Combined bibliographic source must contain 32,066 distinct W')
    if any(register[f].str.strip().ne('').any() for f in ('reviewer_scope_decision', 'reviewer_verification_notes')):
        raise ValueError('Input AI register contains a reviewer decision/note; halt rather than override')
    result = register.merge(combined, on='project_work_id', validate='one_to_one', how='left', indicator=True)
    if not result['_merge'].eq('both').all():
        raise ValueError('Some review W missing from combined evidence')
    result = result.drop(columns=['_merge'])

    # These are only diagnostic prompts to a human reviewer, never scope decisions.
    flags = []
    for row in result.itertuples(index=False):
        subs = [str(v).lower() for v in array(row.historical_subject_keys_json)]
        titles = [str(v) for v in array(row.historical_titles_json)]
        ol_yrs = ids_years(row.historical_edition_derived_min_years_json)
        wd_yrs = [int(y) for y in array(row.wd_p577_parsed_positive_years_json)] if row.wd_p577_parsed_positive_years_json else []
        langs = [str(v) for v in array(row.wd_p407_values_json)] if row.wd_p407_values_json else []
        short = any('short_stor' in s or 'short_story' in s for s in subs)
        biblio = any('bibliograph' in s or 'catalog' in s for s in subs)
        critique = any(any(term in s for term in CRITICISM_TERMS) for s in subs)
        title = any(TITLE_PATTERN.search(s) for s in titles)
        wd_lang = bool(langs) and 'Q1860' not in langs
        wd_date = bool(wd_yrs) and all(y < 1880 or y > 1950 for y in wd_yrs)
        ol_flag = short or biblio or critique or title
        wd_flag = wd_lang or wd_date
        flags.append({
            'diagnostic_ol_short_story_subject': short,
            'diagnostic_ol_bibliography_subject': biblio,
            'diagnostic_ol_criticism_subject': critique,
            'diagnostic_ol_title_cue': title,
            'diagnostic_ol_any': ol_flag,
            'diagnostic_wd_p407_without_english': wd_lang,
            'diagnostic_wd_p577_all_years_outside_1880_1950': wd_date,
            'diagnostic_wd_any': wd_flag,
            'diagnostic_ol_or_wd_any': ol_flag or wd_flag,
            'diagnostic_wd_minus_ol_min_year': (
                wd_yrs[0] - min(ol_yrs) if len(wd_yrs) == 1 and ol_yrs else ''
            ),
        })
    flags_df = pd.DataFrame(flags, index=result.index)
    result = pd.concat([result, flags_df], axis=1)
    # Source and AI fields stay in their own names; reviewers have no default judgments.
    for column in REVIEW_FIELDS:
        result[column] = ''
    result['review_status'] = 'NOT_REVIEWED'
    return result


def count_report(df):
    counts = Counter(df['ai_proposed_class'])
    if counts != {'IN_SCOPE_CANDIDATE': 44, 'OUT_OF_SCOPE_CANDIDATE': 26, 'UNRESOLVED': 10}:
        raise ValueError('AI exploratory labels diverged from frozen 44/26/10')
    out = df[df.ai_proposed_class.eq('OUT_OF_SCOPE_CANDIDATE')]
    ins = df[df.ai_proposed_class.eq('IN_SCOPE_CANDIDATE')]
    unresolved = df[df.ai_proposed_class.eq('UNRESOLVED')]
    return {
        'sample_rows': len(df),
        'ai_provisional_in': int(counts['IN_SCOPE_CANDIDATE']),
        'ai_provisional_out': int(counts['OUT_OF_SCOPE_CANDIDATE']),
        'ai_provisional_unresolved': int(counts['UNRESOLVED']),
        'ol_diagnostic_any_w': int(df.diagnostic_ol_any.sum()),
        'wikidata_diagnostic_any_w': int(df.diagnostic_wd_any.sum()),
        'combined_diagnostic_any_w': int(df.diagnostic_ol_or_wd_any.sum()),
        'ai_out_with_ol_signal': int(out.diagnostic_ol_any.sum()),
        'ai_out_with_wikidata_signal': int(out.diagnostic_wd_any.sum()),
        'ai_out_with_either_signal': int(out.diagnostic_ol_or_wd_any.sum()),
        'ai_out_without_either_signal': int((~out.diagnostic_ol_or_wd_any).sum()),
        'ai_in_with_either_signal': int(ins.diagnostic_ol_or_wd_any.sum()),
        'ai_unresolved_with_either_signal': int(unresolved.diagnostic_ol_or_wd_any.sum()),
        'reviewer_decisions_recorded': int(sum(df[c].ne('').sum() for c in REVIEW_FIELDS)),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo', type=Path, default=Path('.'))
    ap.add_argument('--output-dir', type=Path, default=DEFAULT_OUT)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    repo = args.repo.resolve()
    paths = {'ai_exploratory_register': repo / SRC_REGISTER,
             'combined_bibliographic_evidence': repo / SRC_COMBINED,
             'frozen_random80_sample': repo / SRC_SAMPLE}
    outdir = args.output_dir if args.output_dir.is_absolute() else repo / args.output_dir
    if not args.dry_run and outdir.exists():
        raise FileExistsError('Refusing to overwrite existing directory: ' + str(outdir))
    register, combined, sample = (read_tsv(paths[p]) for p in paths)
    verify_frozen_sample(sample, register)
    sheet = build(register, combined)
    report = count_report(sheet)
    print('=== RANDOM 80 RESEARCHER EVIDENCE SHEET QC ===')
    print('Frozen random sample: VERIFIED')
    for name, n in report.items():
        print(f'{name}: {n}')
    print('Reviewer decision fields: EMPTY; review_status=NOT_REVIEWED on every row.')
    print('OL/Wikidata signals are diagnostic, not research scope decisions.')
    if args.dry_run:
        print('DRY-RUN VERIFIED — no files written.')
        return
    outdir.mkdir(parents=True, exist_ok=False)
    output = outdir / 'random_scope_80_researcher_evidence_sheet_v0_1.tsv'
    sheet.to_csv(output, sep='\t', index=False, lineterminator='\n')
    manifest = {
        'name': 'random_scope_80_researcher_evidence_sheet_v0_1',
        'status': 'NOT_REVIEWED / NOT_ADJUDICATED',
        'random_seed': RANDOM_SEED,
        'counts': report,
        'input_sha256': {key: {'path': str(path.relative_to(repo)), 'sha256': sha256(path)}
                         for key, path in paths.items()},
        'output_sha256': {output.name: sha256(output)},
        'limitations': [
            'All AI proposal classifications remain exploratory, not human-verified.',
            'All diagnostic flags are metadata signals, never grounds for automatic exclusions.',
            'Wikidata P577 dates and P407 languages are snapshot statements, not validated original date/language.',
            'Historical Open Library years are minimum linked-edition years, not verified original-work publication years.',
            'URLs cited in exploratory notes have not been revalidated by this generator.',
            'All researcher decision fields are blank; all review statuses NOT_REVIEWED.',
            'The 80-W sample is fixed; frozen upstream identity, source snapshots, OpenAlex data and existing review sheets are untouched.',
        ],
    }
    (outdir / 'random_scope_80_researcher_evidence_sheet_manifest_v0_1.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )
    print('WROTE:', outdir)
    print('Rows:', len(sheet))


if __name__ == '__main__':
    main()
