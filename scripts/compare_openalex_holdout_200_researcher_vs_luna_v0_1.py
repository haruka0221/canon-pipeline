#!/usr/bin/env python3
"""Compare the independent, human-completed 200-pair OpenAlex holdout review with sealed Luna predictions.

Run from anywhere after placing this script in <repo>/scripts/:
    python -B scripts/compare_openalex_holdout_200_researcher_vs_luna_v0_1.py

NO API. Refuses to unblind until: 200 identifiable researcher labels are present,
judged sheet is an unmodified copy of the 200 blind input apart from review
fields, and the original blind-sheet hash agrees with its manifest.

Outputs only the selected 200-pair subset; remaining 400 predictions stay sealed.
Never modifies source judgments, saved model responses, prior releases or data.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from math import sqrt
from pathlib import Path
import json
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'derived' / 'openalex_production'
REVIEW_DIR = BASE / 'retrieval_r2a1_holdout_first_200_blind_review_v0_1'
ORIGINAL = REVIEW_DIR / 'holdout_first_200_blind_review_v0_1.tsv'
JUDGED = REVIEW_DIR / 'holdout_first_200_blind_review_v0_1_judged.tsv'
MANIFEST = REVIEW_DIR / 'blind_200_manifest_v0_1.json'
SEALED = BASE / 'retrieval_r2a1_holdout_600_identity_aware_v0_1' / 'HOLDOUT_MODEL_KEY_DO_NOT_OPEN_BEFORE_RESEARCHER_REVIEW.jsonl'
OUT = REVIEW_DIR / 'holdout_first_200_researcher_luna_comparison_v0_1'
LABELS = ('VALID_TARGET_REFERENCE', 'INVALID_TARGET_REFERENCE', 'UNCERTAIN')
NORMALIZE = {
    'VALID': LABELS[0], 'VALID_TARGET_REFERENCE': LABELS[0],
    'INVALID': LABELS[1], 'INVALID_TARGET_REFERENCE': LABELS[1],
    'UNCERTAIN': LABELS[2], 'UNSURE': LABELS[2], '不明': LABELS[2], '保留': LABELS[2],
}
KEYS = ('review_case_id', 'baseline_candidate_id', 'project_work_id', 'openalex_work_id')
JUDGMENT_COL = 'researcher_target_attribution_judgment'


def file_sha(path: Path) -> str:
    h = sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def tsv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f'Missing file: {path}')
    return pd.read_csv(path, sep='\t', dtype=str, keep_default_na=False, encoding='utf-8-sig')


def keyed(df: pd.DataFrame, name: str) -> None:
    absent = [c for c in KEYS if c not in df]
    if absent:
        raise ValueError(f'{name}: missing ID columns {absent}')
    if len(df) != 200 or df['baseline_candidate_id'].duplicated().any():
        raise ValueError(f'{name}: 200 distinct candidate IDs required, got rows={len(df)}')
    if df[list(KEYS)].eq('').any().any():
        raise ValueError(f'{name}: an ID column is blank')
    if df[list(KEYS)].duplicated().any():
        raise ValueError(f'{name}: repeated pair ID')


def wilson(k: int, n: int) -> dict | None:
    if n == 0:
        return None
    z = 1.959963984540054
    p = k / n
    den = 1 + z*z/n
    mid = (p + z*z/(2*n))/den
    err = z*sqrt(p*(1-p)/n + z*z/(4*n*n))/den
    return {'k': k, 'n': n, 'rate': p, 'wilson_95_low': max(0, mid-err), 'wilson_95_high': min(1, mid+err)}


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f'Refusing overwrite: {OUT}')

    original = tsv(ORIGINAL)
    judged = tsv(JUDGED)
    keyed(original, 'Frozen 200 blind sheet')
    keyed(judged, 'Researcher completed sheet')

    if not MANIFEST.is_file():
        raise FileNotFoundError(f'Missing blind selection manifest: {MANIFEST}')
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if manifest.get('n') != 200 or manifest.get('output_sha256') != file_sha(ORIGINAL):
        raise RuntimeError('Original blind-200 input fails original manifest verification')

    o = original.set_index('baseline_candidate_id', verify_integrity=True).sort_index()
    j = judged.set_index('baseline_candidate_id', verify_integrity=True).sort_index()
    if not o.index.equals(j.index):
        raise ValueError('Judged IDs differ from original independent 200; no model output opened')

    # Check all supplied original fields, including text and source-native context.
    # Additional, researcher-created columns are harmless; existing original
    # review fields may be filled, but ALL non-review content must be unchanged.
    for col in original.columns:
        if col == 'baseline_candidate_id' or col.startswith('researcher_'):
            continue
        if col not in j.columns:
            raise ValueError(f'Original column removed from judged file: {col}')
        differing = ~o[col].eq(j[col])
        if differing.any():
            sample_id = o.index[differing][0]
            raise ValueError(f'Original evidence or ID changed: column={col}; candidate={sample_id}. '
                             'Restore original evidence columns, preserving edited reviewer columns.')
    if JUDGMENT_COL not in j:
        raise ValueError(f'Missing researcher column: {JUDGMENT_COL}')
    labels = j[JUDGMENT_COL].astype(str).str.strip().str.upper().map(NORMALIZE)
    unjudged = labels.isna()
    if unjudged.any():
        print('STOP: human 200 judgments are not yet all valid. Model outputs have NOT been opened.')
        for cid in j.index[unjudged][:25]:
            print(' ', cid, repr(j.at[cid, JUDGMENT_COL]))
        print('Unfilled or unrecognized judgments:', int(unjudged.sum()))
        sys.exit(2)

    # 200 fully recorded labels are frozen by the SHA256 of the user-supplied TSV.
    # Only now may we access the 600 saved model judgments.
    if not SEALED.is_file():
        raise FileNotFoundError(f'Missing completed sealed Luna predictions: {SEALED}')
    prediction_by_id: dict[str, dict] = {}
    seen_n = 0
    with SEALED.open(encoding='utf-8') as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                raise ValueError(f'Empty model JSONL line at {lineno}')
            pred = json.loads(line)
            cid = pred.get('baseline_candidate_id')
            if not cid or cid in prediction_by_id:
                raise ValueError(f'Missing/duplicate model candidate_id: {cid}')
            if pred.get('model') != 'gpt-6-luna' or pred.get('judgment') not in LABELS:
                raise ValueError(f'Unexpected model or model judgment at line {lineno}')
            prediction_by_id[cid] = pred
            seen_n += 1
    if seen_n != 600:
        raise ValueError(f'Expected completed Luna holdout 600, found {seen_n}')
    if not set(j.index).issubset(prediction_by_id):
        raise ValueError('Some judged candidate IDs are absent from model holdout results')

    # Generate paired results ONLY for the 200 preselected review cases.
    kept_cols = [c for c in judged.columns if c == 'baseline_candidate_id' or
                 c in KEYS or c.startswith('researcher_') or
                 c in ('target_title', 'target_author', 'openalex_title')]
    paired = j.reset_index()[list(dict.fromkeys(kept_cols))].copy()
    paired['human_normalized'] = paired['baseline_candidate_id'].map(labels.to_dict())
    paired['luna_judgment'] = paired['baseline_candidate_id'].map(lambda cid: prediction_by_id[cid]['judgment'])
    for field in ('reason_code', 'confidence', 'identity_context_adequacy', 'note'):
        paired['luna_' + field] = paired['baseline_candidate_id'].map(lambda cid, fld=field: prediction_by_id[cid].get(fld, ''))
    paired['exact_agreement'] = paired['human_normalized'].eq(paired['luna_judgment'])
    human_valid = paired['human_normalized'].eq(LABELS[0])
    human_invalid = paired['human_normalized'].eq(LABELS[1])
    human_uncertain = paired['human_normalized'].eq(LABELS[2])
    luna_valid = paired['luna_judgment'].eq(LABELS[0])
    luna_invalid = paired['luna_judgment'].eq(LABELS[1])
    luna_uncertain = paired['luna_judgment'].eq(LABELS[2])
    paired['disagreement_type'] = 'AGREE'
    paired.loc[~paired.exact_agreement, 'disagreement_type'] = 'OTHER'
    paired.loc[human_valid & luna_invalid, 'disagreement_type'] = 'HUMAN_VALID__LUNA_INVALID'
    paired.loc[human_invalid & luna_valid, 'disagreement_type'] = 'HUMAN_INVALID__LUNA_VALID'
    paired.loc[human_valid & luna_uncertain, 'disagreement_type'] = 'HUMAN_VALID__LUNA_UNCERTAIN'
    paired.loc[human_invalid & luna_uncertain, 'disagreement_type'] = 'HUMAN_INVALID__LUNA_UNCERTAIN'
    paired.loc[human_uncertain & (luna_valid | luna_invalid), 'disagreement_type'] = 'HUMAN_UNCERTAIN__LUNA_DECISIVE'

    table = pd.crosstab(paired['human_normalized'], paired['luna_judgment']).reindex(
        index=LABELS, columns=LABELS, fill_value=0)
    tp = int((human_valid & luna_valid).sum())
    fp = int((human_invalid & luna_valid).sum())
    fn = int((human_valid & ~luna_valid).sum())
    # On gold-determinate model-valid predictions only. Ambiguous gold labels
    # are not silently treated as negative labels.
    known_model_valid = int((luna_valid & ~human_uncertain).sum())
    all_luna_valid = int(luna_valid.sum())
    vgold_unknown_on_model_valid = int((human_uncertain & luna_valid).sum())
    valid_gold_count = int(human_valid.sum())
    model_valid_ppv = wilson(tp, known_model_valid)
    candidate_pair_recall = wilson(tp, valid_gold_count)
    # Conditional probability across candidate pairs, not full corpus citation recall.
    agreement = wilson(int(paired.exact_agreement.sum()), 200)

    summary = {
        'release': 'openalex-r2a1-independent-holdout-200-researcher-vs-luna-v0_1',
        'status': 'INDEPENDENT_200_OF_FROZEN_600_PAIR_SAMPLE; 400_UNINSPECTED_IN_OUTPUT',
        'sampling_frame_n': 223875,
        'holdout_full_n': 600,
        'human_reviewed_n': 200,
        'selected_200_sampling': 'SRS 200 from the frozen 600 SRS; model-independent selection',
        'model': 'gpt-6-luna',
        'human_label_counts': dict(Counter(paired.human_normalized)),
        'model_label_counts': dict(Counter(paired.luna_judgment)),
        'exact_agreement_n': int(paired.exact_agreement.sum()),
        'exact_agreement': agreement,
        'confusion_human_rows_model_columns': table.to_dict(orient='index'),
        'disagreement_types': dict(Counter(paired.disagreement_type)),
        'human_valid_luna_invalid_n': int((human_valid & luna_invalid).sum()),
        'human_invalid_luna_valid_n': fp,
        'human_valid_luna_uncertain_n': int((human_valid & luna_uncertain).sum()),
        'human_invalid_luna_uncertain_n': int((human_invalid & luna_uncertain).sum()),
        'human_uncertain_luna_decisive_n': int((human_uncertain & ~luna_uncertain).sum()),
        'luna_valid_count': all_luna_valid,
        'luna_valid_human_gold_uncertain_n': vgold_unknown_on_model_valid,
        'model_valid_precision_given_determinate_human_gold': model_valid_ppv,
        'model_valid_precision_naive_identification_bounds': {
            'lower': (tp / all_luna_valid) if all_luna_valid else None,
            'upper': ((tp + vgold_unknown_on_model_valid) / all_luna_valid) if all_luna_valid else None,
            'note': 'Unknown human labels among Luna VALID could all be non-references or references; not a confidence interval.',
        },
        'model_valid_recall_within_candidate_sample_given_human_valid': candidate_pair_recall,
        'retrieval_recall_estimated': False,
        'population_precision_caveat': 'This sample estimates conditional attribution precision over the 223,875-pair NEW R2+A1 frame, not full OA coverage, 224,830 operational R2+A1, or all v2 routes. Human UNCERTAIN remains unadjudicated.',
        'ci_caveat': 'Wilson intervals are descriptive simple-binomial approximations; shared Project W clusters and adjudication uncertainty may require further analysis.',
        'human_gold_source': 'researcher-entered blind sheet; not independently checked by second researcher',
        'original_blind_200_sha256': file_sha(ORIGINAL),
        'researcher_judged_200_sha256': file_sha(JUDGED),
        'sealed_model_600_sha256': file_sha(SEALED),
        'remaining_400_predictions_in_outputs': False,
        'api_calls': 0,
    }

    # Refuse to overwrite and stage outputs only after every integrity check succeeds.
    OUT.mkdir(parents=False, exist_ok=False)
    paired.to_csv(OUT / 'holdout_first_200_human_luna_pairs_v0_1.tsv', sep='\t', index=False,
                  encoding='utf-8-sig', lineterminator='\n')
    (OUT / 'holdout_first_200_comparison_summary_v0_1.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    (OUT / 'README.md').write_text(
        '# OpenAlex R2+A1 independent 200-pair holdout comparison v0.1\n\n'
        'Sources: frozen 200-person blind packet, completed researcher-entered copy, '
        'and the 600 completed sealed Luna decisions.\n\n'
        'Human judgments and model outputs remain unchanged. Paired TSV contains ONLY 200 '
        'previously selected, human-reviewed pairs; never inspect the remaining 400 before '
        'their own independent review if expanding validation.\n\n'
        'Do not equate simple 3-class agreement with exact-work attribution precision. '
        'Human UNCERTAIN is not a negative reference. Model VALID precision is tabulated '
        'separately for determinate human gold and with uncertainty bounds.\n'
        'This is pair-level attribution in the 223,875 new R2+A1 frame, not total corpus recall.\n',
        encoding='utf-8')

    print('=== INDEPENDENT HOLDOUT 200: RESEARCHER x LUNA ===')
    print('200 researcher judgments and original blind evidence: verified')
    print('600 saved Luna results: verified; only matching 200 compared')
    print('Human labels:', summary['human_label_counts'])
    print('Luna labels (reviewed 200 only):', summary['model_label_counts'])
    print(f'Exact agreement: {summary["exact_agreement_n"]} / 200')
    print('Human VALID / Luna INVALID:', summary['human_valid_luna_invalid_n'])
    print('Human INVALID / Luna VALID:', summary['human_invalid_luna_valid_n'])
    print('Human VALID / Luna UNCERTAIN:', summary['human_valid_luna_uncertain_n'])
    print('Human INVALID / Luna UNCERTAIN:', summary['human_invalid_luna_uncertain_n'])
    print('Human UNCERTAIN / Luna decisive:', summary['human_uncertain_luna_decisive_n'])
    print('\nCONFUSION MATRIX (human rows / Luna columns)')
    print(table.to_string())
    print('\nMETRICS (human-UNCERTAIN excluded from binary gold evaluation)')
    print('Luna VALID precision (determinate gold):', model_valid_ppv)
    print('Luna VALID precision range incl. ambiguous gold:', summary['model_valid_precision_naive_identification_bounds'])
    print('Candidate-pair VALID recall (NOT retrieval recall):', candidate_pair_recall)
    print('\nDISAGREEMENTS (reviewed 200 only):')
    for r in paired.loc[~paired.exact_agreement].itertuples(index=False):
        print(f'{r.review_case_id} | {r.project_work_id} | '
              f'{str(r.target_title)[:50]} | HUMAN={r.human_normalized} | '
              f'LUNA={r.luna_judgment} | {r.disagreement_type}')
    print('\nSaved output:', OUT)
    print('No API; source evidence, frozen judgments, and remaining 400 human-blind rows unchanged.')


if __name__ == '__main__':
    main()
