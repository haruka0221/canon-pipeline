#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, os
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CAND_DIR = ROOT / 'derived/openalex_production/retrieval_a2_validation_candidates_v1'
LAB_DIR = ROOT / 'derived/openalex_production/retrieval_a2_validation_final_labels_v1'
OUT_DIR = ROOT / 'derived/openalex_production/retrieval_a2_validation_policy_overlay_v1'
CAND = CAND_DIR / 'openalex_a2_validation_candidates_v1.tsv'
LAB = LAB_DIR / 'openalex_a2_validation_final_labels_v1.tsv'
CAND_MAN = CAND_DIR / 'openalex_a2_validation_candidates_v1_manifest.json'
LAB_MAN = LAB_DIR / 'openalex_a2_validation_final_labels_v1_manifest.json'
EXPECTED_CAND_SHA = 'c18084914709a0306b348be970ab9e65a6d4a9804adc5121a4328e5085f03f0e'
EXPECTED_LAB_SHA = '8402fd5ffac8ac7355591294d137c61c58b0b0e593ae66b8158d6f8d5c8b9a42'


def sha256(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_tsv(df, p):
    tmp = p.with_name(p.name + '.tmp')
    df.to_csv(tmp, sep='\t', index=False, lineterminator='\n')
    os.replace(tmp, p)


def write_json(obj, p):
    tmp = p.with_name(p.name + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(tmp, p)


def summarize(df):
    n = len(df)
    v = int(df.final_judgment.eq('VALID_TARGET_REFERENCE').sum())
    i = int(df.final_judgment.eq('INVALID_TARGET_REFERENCE').sum())
    u = int(df.final_judgment.eq('UNCERTAIN').sum())
    bw = (df.assign(v=df.final_judgment.eq('VALID_TARGET_REFERENCE').astype(int))
            .groupby('project_work_id').agg(n=('validation_candidate_id','size'), v=('v','sum')))
    return {
        'candidate_pairs': n,
        'project_works': int(df.project_work_id.nunique()),
        'valid': v, 'invalid': i, 'uncertain': u,
        'micro_confirmed_valid': v / n,
        'micro_upper_bound': (v + u) / n,
        'micro_resolved_only': v / (v + i) if v + i else None,
        'macro_work_confirmed_valid': float((bw.v / bw.n).mean()),
    }


def main():
    for p in [CAND, LAB, CAND_MAN, LAB_MAN]:
        if not p.exists():
            raise FileNotFoundError(p)
    if OUT_DIR.exists():
        raise RuntimeError(f'Output directory exists: {OUT_DIR}')
    if sha256(CAND) != EXPECTED_CAND_SHA:
        raise RuntimeError('candidate TSV hash mismatch')
    if sha256(LAB) != EXPECTED_LAB_SHA:
        raise RuntimeError('final-label TSV hash mismatch')

    c = pd.read_csv(CAND, sep='\t', dtype=str, keep_default_na=False)
    l = pd.read_csv(LAB, sep='\t', dtype=str, keep_default_na=False)
    assert len(c) == 248 and len(l) == 248
    assert c.validation_candidate_id.is_unique and l.validation_candidate_id.is_unique
    assert set(c.validation_candidate_id) == set(l.validation_candidate_id)
    assert c.increment_type.eq('A2_AUTHOR_REVERSAL').all()

    c['title_match_token_count_min'] = pd.to_numeric(c.title_match_token_count, errors='raise').astype(int)
    collision = c.any_cross_w_title_collision.str.lower().map({'true': True, 'false': False})
    if collision.isna().any():
        raise RuntimeError('bad collision value')
    c['policy_condition_abstract_only'] = c.hit_location.eq('ABSTRACT_ONLY')
    c['policy_condition_one_token'] = c.title_match_token_count_min.eq(1)
    c['policy_condition_cross_w_collision'] = collision.astype(bool)
    c['policy_review_condition'] = c.policy_condition_abstract_only & (c.policy_condition_one_token | c.policy_condition_cross_w_collision)
    c['policy_action'] = c.policy_review_condition.map({True:'REVIEW', False:'ACCEPT'})

    keep = ['validation_candidate_id','final_judgment','final_reason_code','final_label_source','human_reviewed']
    x = c.merge(l[keep], on='validation_candidate_id', how='left', validate='one_to_one')
    a = x[x.policy_action.eq('ACCEPT')].copy()
    r = x[x.policy_action.eq('REVIEW')].copy()
    inv = x[x.final_judgment.eq('INVALID_TARGET_REFERENCE')].copy()
    inv_r = inv[inv.policy_action.eq('REVIEW')].copy()
    inv_a = inv[inv.policy_action.eq('ACCEPT')].copy()

    # Frozen held-out invariants.
    assert (len(x), x.project_work_id.nunique()) == (248, 64)
    assert tuple(x.final_judgment.value_counts().reindex(['VALID_TARGET_REFERENCE','INVALID_TARGET_REFERENCE','UNCERTAIN'], fill_value=0)) == (243,5,0)
    assert (len(a), int(a.final_judgment.eq('VALID_TARGET_REFERENCE').sum()), int(a.final_judgment.eq('INVALID_TARGET_REFERENCE').sum())) == (213,212,1)
    assert (len(r), int(r.final_judgment.eq('VALID_TARGET_REFERENCE').sum()), int(r.final_judgment.eq('INVALID_TARGET_REFERENCE').sum())) == (35,31,4)
    assert len(inv_a) == 1 and inv_a.validation_candidate_id.iloc[0] == 'A2V1_0081'

    overall, accept, review = summarize(x), summarize(a), summarize(r)
    summary = {
        'release':'openalex-a2-validation-policy-overlay-v1',
        'created_at':'2026-10-08',
        'status':'locked_policy_overlaid_on_frozen_heldout_labels',
        'scope':'A2_AUTHOR_REVERSAL held-out marginal candidates only',
        'policy':{
            'rule':'REVIEW iff hit_location == ABSTRACT_ONLY AND (title_match_token_count_min == 1 OR any_cross_w_title_collision == True); otherwise ACCEPT',
            'threshold_tuned_on_validation':False,
        },
        'metrics':{
            'overall':overall,
            'accept':accept,
            'review':review,
            'review_share_pairs':len(r)/len(x),
            'review_share_project_works':r.project_work_id.nunique()/x.project_work_id.nunique(),
            'invalid_capture_pairs':len(inv_r)/len(inv),
            'invalid_capture_project_works':inv_r.project_work_id.nunique()/inv.project_work_id.nunique(),
        },
        'accepted_invalid':{
            'validation_candidate_id':inv_a.validation_candidate_id.iloc[0],
            'project_work_id':inv_a.project_work_id.iloc[0],
            'target_title':inv_a.query_title.iloc[0],
            'target_author':inv_a.query_author.iloc[0],
            'openalex_work_id':inv_a.openalex_work_id.iloc[0],
            'hit_location':inv_a.hit_location.iloc[0],
            'title_match_token_count_min':int(inv_a.title_match_token_count_min.iloc[0]),
            'any_cross_w_title_collision':bool(inv_a.policy_condition_cross_w_collision.iloc[0]),
        },
        'constraints':[
            'Pair-level micro is primary; work-level macro is secondary.',
            'UNCERTAIN remains separate from INVALID.',
            'No ordinary confidence interval is attached.',
            'Review share is for held-out A2 marginal candidates, not whole production burden.',
            'The locked policy was not tuned after validation labels were seen.',
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=False)
    cols = ['validation_candidate_id','project_work_id','openalex_work_id','query_title','query_author','hit_location','title_match_token_count_min','any_cross_w_title_collision','policy_review_condition','policy_action','final_judgment','final_reason_code','final_label_source','human_reviewed']
    overlay = x[cols].sort_values(['project_work_id','openalex_work_id'], kind='stable')
    overlay_path = OUT_DIR / 'openalex_a2_validation_policy_overlay_v1.tsv'
    write_tsv(overlay, overlay_path)

    bw = (x.assign(valid=x.final_judgment.eq('VALID_TARGET_REFERENCE').astype(int), invalid=x.final_judgment.eq('INVALID_TARGET_REFERENCE').astype(int), uncertain=x.final_judgment.eq('UNCERTAIN').astype(int), accept=x.policy_action.eq('ACCEPT').astype(int), review=x.policy_action.eq('REVIEW').astype(int))
          .groupby('project_work_id', as_index=False)
          .agg(candidate_pairs=('validation_candidate_id','size'), valid=('valid','sum'), invalid=('invalid','sum'), uncertain=('uncertain','sum'), accept=('accept','sum'), review=('review','sum')))
    bw['confirmed_valid_precision'] = bw.valid / bw.candidate_pairs
    bywork_path = OUT_DIR / 'openalex_a2_validation_policy_overlay_by_work_v1.tsv'
    write_tsv(bw.sort_values('project_work_id', kind='stable'), bywork_path)

    summary_path = OUT_DIR / 'openalex_a2_validation_policy_overlay_summary_v1.json'
    write_json(summary, summary_path)
    manifest = {
        'release':'openalex-a2-validation-policy-overlay-v1',
        'inputs':{
            str(CAND.relative_to(ROOT)):sha256(CAND),
            str(LAB.relative_to(ROOT)):sha256(LAB),
            str(CAND_MAN.relative_to(ROOT)):sha256(CAND_MAN),
            str(LAB_MAN.relative_to(ROOT)):sha256(LAB_MAN),
        },
        'outputs':{
            overlay_path.name:sha256(overlay_path),
            bywork_path.name:sha256(bywork_path),
            summary_path.name:sha256(summary_path),
        },
    }
    write_json(manifest, OUT_DIR / 'openalex_a2_validation_policy_overlay_v1_manifest.json')

    print('A2 held-out policy overlay complete')
    print('OVERALL', overall)
    print('ACCEPT', accept)
    print('REVIEW', review)
    print(f'review_share_pairs={len(r)/len(x):.6f}')
    print(f'invalid_capture_pairs={len(inv_r)/len(inv):.6f}')
    print('accepted_invalid=A2V1_0081')
    print(f'output_dir={OUT_DIR}')


if __name__ == '__main__':
    main()
