#!/usr/bin/env python3
"""Non-adjudicative bibliographic-alert robustness for OpenAlex/Goodreads v0.2.

Cohorts use source/identity alerts only: NEVER the prior review-priority score,
which itself uses OpenAlex counts (an endogenous selection variable).
This does not purport to identify in-scope literature. No frozen file mutation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

VERSION = 'analysis_v3_scope_source_alert_robustness_v0_1'
SIG_REL = 'derived/scope/scope_all_w_source_signal_priority_v0_1/all_project_w_bibliographic_source_signals_v0_1.tsv'
VIS_REL = 'derived/openalex_production/analysis_v3_ol_goodreads_provisional_comparison_v0_2/all_project_w_provisional_visibility_ol_goodreads.tsv'
OUT_REL = 'derived/openalex_production/analysis_v3_scope_source_alert_robustness_v0_1'
N_W, N_OA, N_GR = 32066, 31713, 4642
REQ_SIG = {'project_work_id','current_ol_count','combined_period_signal_not_original_year',
           'wd_p577_year_signal','wd_p407_values_json','wd_p407_includes_english_statement',
           'ol_subject_form_review_terms_json','shared_query_identity_risk','openalex_core3_candidate_pairs',
           'openalex_all_types_candidate_pairs','goodreads_historical_ratings_observed',
           'review_priority_score','wikidata_qid'}
REQ_VIS = {'project_work_id','exploratory_article_chapter_dissertation_pairs',
           'v3_provisional_operational_pairs','goodreads_ratings_count',
           'goodreads_text_reviews_count','ol_edition_count_for_correlation',
           'accepted_goodreads_work_id','scope_researcher_status'}


def check(condition, msg):
    if not bool(condition):
        raise ValueError('QC FAILED: '+msg)


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for b in iter(lambda:stream.read(1<<20),b''):
            h.update(b)
    return h.hexdigest()


def read(path, required, label):
    check(path.is_file(),f'{label} missing: {path}')
    frame=pd.read_csv(path,sep='\t',dtype=str,keep_default_na=False)
    check(required <= set(frame.columns),f'{label} missing columns: {required-set(frame.columns)}')
    check(len(frame)==N_W,f'{label} {len(frame)} != {N_W}')
    check(frame.project_work_id.is_unique and frame.project_work_id.ne('').all(),f'{label} duplicated/blank W')
    return frame


def numeric_column(frame, col):
    s=frame[col]
    values=pd.to_numeric(s.replace('',np.nan),errors='raise')
    check(values.dropna().ge(0).all(),f'{col} negative')
    return values.astype('float64')


def summary_stats(x):
    if not len(x):
        return None,None
    return float(x.median()),float(x.quantile(.9))


def corr(x,y):
    if len(x)<3 or x.nunique()<2 or y.nunique()<2:
        return None,None
    return round(float(x.rank(method='average').corr(y.rank(method='average'))), 6), round(float(np.log1p(x).corr(np.log1p(y))), 6)


def run(sig, vis):
    sig=sig.set_index('project_work_id').sort_index()
    vis=vis.set_index('project_work_id').sort_index()
    check(sig.index.equals(vis.index),'W identity sets differ')
    n_sig_core=numeric_column(sig,'openalex_core3_candidate_pairs')
    n_sig_all=numeric_column(sig,'openalex_all_types_candidate_pairs')
    measured=numeric_column(vis,'exploratory_article_chapter_dissertation_pairs')
    alltypes=numeric_column(vis,'v3_provisional_operational_pairs')
    goodreads=numeric_column(vis,'goodreads_ratings_count')
    reviews=numeric_column(vis,'goodreads_text_reviews_count')
    editions=numeric_column(vis,'ol_edition_count_for_correlation')
    check(n_sig_core.equals(measured),'CORE3 in scope signal table does not equal v0.2')
    check(n_sig_all.equals(alltypes),'All-types in scope signal table does not equal v0.2')
    check(measured.notna().sum()==N_OA,'measured W count')
    check(goodreads.notna().sum()==N_GR,'ratings W count')
    check(reviews.notna().sum()==N_GR,'reviews W count')
    check((measured[goodreads.notna()].notna()).all(),'GR matched W lacks OA')
    check(sig.goodreads_historical_ratings_observed.eq('True').equals(goodreads.notna()),'GR observed flags unequal')
    check(sig.shared_query_identity_risk.isin(['True','False']).all(),'invalid shared-query flag')
    check(int(sig.shared_query_identity_risk.eq('True').sum())==1797,'shared query-risk count')
    check((sig.review_priority_score!='').all(),'missing source priority scores')
    check(vis.scope_researcher_status.isin(['NOT_RESEARCHER_ADJUDICATED','NOT_ADJUDICATED','']).all(),
          'unexpected researcher-adjudicated scope label')

    # Source signals only; importantly NO review_priority_score and NO OA counts!
    count_ol=numeric_column(sig,'current_ol_count')
    year_ok=sig.combined_period_signal_not_original_year.eq('ONLY_1880_1950_YEAR_SIGNALS')
    language_absent=sig.wd_p407_values_json.eq('[]') | sig.wd_p407_values_json.eq('')
    english_signal=sig.wd_p407_includes_english_statement.eq('True')
    check(sig.wd_p407_includes_english_statement.isin(['True','False']).all(),'bad english statement flag')
    source_language_ok=language_absent | english_signal
    no_subject_alert=sig.ol_subject_form_review_terms_json.eq('[]')
    check(sig.ol_subject_form_review_terms_json.str.startswith('[').all(),'bad subject JSON')
    identity_no_alert=sig.shared_query_identity_risk.eq('False') & count_ol.eq(1)
    no_biblio_alert=identity_no_alert & year_ok & source_language_ok & no_subject_alert
    wd_window=sig.wd_p577_year_signal.eq('ONLY_1880_1950_YEAR_SIGNALS')
    independent_wd_evidence=wd_window & english_signal
    scenarios={
       'BASELINE_ALL_W': pd.Series(True,index=sig.index),
       'NO_SHARED_QUERY_AND_SINGLE_OL': identity_no_alert,
       'NO_SOURCE_ALERTS': no_biblio_alert,
       'NO_SOURCE_ALERTS_PLUS_WD_WINDOW_ENGLISH': no_biblio_alert & independent_wd_evidence,
    }
    check(len(scenarios)==4,'scenario keys')
    check(scenarios['NO_SOURCE_ALERTS_PLUS_WD_WINDOW_ENGLISH'].le(scenarios['NO_SOURCE_ALERTS']).all(),'nested cohort')
    check(scenarios['NO_SOURCE_ALERTS'].le(scenarios['NO_SHARED_QUERY_AND_SINGLE_OL']).all(),'nested cohort')
    check(scenarios['NO_SHARED_QUERY_AND_SINGLE_OL'].le(scenarios['BASELINE_ALL_W']).all(),'nested cohort')
    scenario_frames=[]
    correlations=[]
    ranks=[]
    for name,mask in scenarios.items():
        selected=sig.index[mask]
        measured_sel=selected[measured.loc[selected].notna()]
        matched_sel=selected[measured.loc[selected].notna() & goodreads.loc[selected].notna()]
        unique_ids=set(vis.loc[matched_sel,'accepted_goodreads_work_id'])
        check('' not in unique_ids,f'{name} matched with blank GR ID')
        check(len(unique_ids)==len(matched_sel),f'{name} reused Goodreads ID across W; cannot treat as independent')
        cov=float(len(matched_sel)/len(measured_sel)) if len(measured_sel) else None
        med,p90=summary_stats(measured.loc[measured_sel])
        scenario_frames.append({
          'scenario':name,'project_w':len(selected),'oa_measured_project_w':len(measured_sel),
          'matched_oa_and_gr_project_w':len(matched_sel),
          'goodreads_observation_fraction_of_oa_measured':cov,
          'oa_core3_median_measured':med,'oa_core3_p90_measured':p90,
          'oa_core3_candidate_pair_sum_measured':int(measured.loc[measured_sel].sum()),
          'unique_accepted_goodreads_work_ids':len(unique_ids),
          'selection_definition':'SOURCE_EVIDENCE_ONLY_NOT_SCOPE_ADJUDICATED'
        })
        for xx,xser in [('CORE3',measured),('ALL_TYPES',alltypes)]:
            for yy,yser in [('GOODREADS_RATINGS',goodreads),('GOODREADS_TEXT_REVIEWS',reviews),('OL_EDITION_COUNT',editions)]:
                pair_index=selected[xser.loc[selected].notna() & yser.loc[selected].notna()]
                x=xser.loc[pair_index]; y=yser.loc[pair_index]
                rho,pearson=corr(x,y)
                correlations.append({'scenario':name,'academic_indicator':xx,'comparison_indicator':yy,
                                     'complete_case_project_w':len(pair_index),
                                     'spearman_rank_corr':rho,'pearson_corr_log1p':pearson,
                                     'source_scope_status':'NOT_RESEARCHER_ADJUDICATED'})
        if len(matched_sel)>=3:
            # Re-rank from scratch within each specific matched population.
            x=measured.loc[matched_sel]
            y=goodreads.loc[matched_sel]
            ac=x.rank(pct=True,method='average')
            public=y.rank(pct=True,method='average')
            differences=ac-public
            for direction,ordered in [('ACADEMIC_OVER_PUBLIC',differences.sort_values(ascending=False,kind='stable')),
                                      ('PUBLIC_OVER_ACADEMIC',differences.sort_values(ascending=True,kind='stable'))]:
                for rank,(w,d) in enumerate(ordered.iloc[:10].items(),start=1):
                    rr=vis.loc[w]
                    ranks.append({'scenario':name,'direction':direction,'rank_within_direction':rank,
                                  'project_work_id':w,
                                  'query_title_display':rr['query_title_display'],
                                  'query_author_display':rr['query_author_display'],
                                  'oa_core3_candidate_pairs':int(x.loc[w]),
                                  'historical_goodreads_ratings_count':int(y.loc[w]),
                                  'oa_core3_percentile_recomputed_within_scenario':float(ac.loc[w]),
                                  'goodreads_percentile_recomputed_within_scenario':float(public.loc[w]),
                                  'academic_minus_public_percentile_recomputed':float(d),
                                  'source_scope_status':'NOT_RESEARCHER_ADJUDICATED'})
    bas=scenario_frames[0]
    check(bas['project_w']==N_W and bas['oa_measured_project_w']==N_OA and bas['matched_oa_and_gr_project_w']==N_GR,'baseline counts')
    check(bas['oa_core3_candidate_pair_sum_measured']==146724,'core3 total')
    # An alert prevalence vs observed association table over a fixed OA-measured denominator.
    alert_defs={
       'SHARED_QUERY_RISK':sig.shared_query_identity_risk.eq('True'),
       'ZERO_OR_MULTIPLE_CURRENT_OL':~count_ol.eq(1),
       'MIXED_OR_NO_DATE_SIGNALS':~year_ok,
       'WD_NON_ENGLISH_OR_NO_ENGLISH_STATEMENT':~source_language_ok,
       'OL_NON_NOVEL_SUBJECT_SIGNAL':~no_subject_alert,
       'ANY_SOURCE_ALERT':~no_biblio_alert,
       'ADOPTED_WIKIDATA_QID':sig.wikidata_qid.ne(''),
    }
    strat=[]
    for label,flag in alert_defs.items():
        for status,value in [('SIGNAL_PRESENT',True),('SIGNAL_ABSENT',False)]:
            mask=flag.eq(value) & measured.notna()
            n=int(mask.sum()); obs=int((mask & goodreads.notna()).sum())
            strat.append({'signal':label,'stratum':status,'oa_measured_project_w':n,
                          'gr_ratings_observed_w':obs,
                          'gr_observation_fraction':obs/n if n else None})
    summary={
      'release':VERSION,'status':'EXPLORATORY_SOURCE_ALERT_SENSITIVITY_NOT_SCOPE_ADJUDICATED',
      'all_project_w':N_W,'oa_measured_w':N_OA,'gr_metrics_observed_w':N_GR,
      'scenarios':scenario_frames,
      'methodological_warning':'Do not select on review_priority_score: score includes OpenAlex CORE3 and would cause outcome-dependent filtering.',
      'scope_status':'NO_RESEARCHER_SCOPE_ADJUDICATION',
      'notes':[
        'Only bibliographic/identity SOURCE SIGNALS define scenarios; no source-signal absence establishes original scope.',
        'Wikidata P577/P407 are not independently verified first publication year/original language.',
        'OL subjects may reflect attached collections or editions and are not definitive genre labels.',
        'Scenario percentiles are recomputed from the paired subset separately for each cohort.',
        'Differences between correlations are descriptive; case selection is strongly nonrandom.',
        'OpenAlex values are provisional candidate W x OA pairs, not validated citation counts.',
        'Zero is distinct from unmeasured NA. Missing Goodreads is not zero readership.',
        'All Project W units retain frozen identities; no merges, scope status updates, ratings allocations, or original analysis mutation.'
      ],
    }
    return {
      'cohort_comparison_v0_1.tsv':pd.DataFrame(scenario_frames),
      'correlations_by_source_alert_cohort_v0_1.tsv':pd.DataFrame(correlations),
      'percentile_extremes_recomputed_by_cohort_v0_1.tsv':pd.DataFrame(ranks),
      'goodreads_observation_by_bibliographic_source_alert_v0_1.tsv':pd.DataFrame(strat),
    },summary


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo-root',type=Path,default=Path.cwd())
    ap.add_argument('--source-signals',type=Path,default=Path(SIG_REL))
    ap.add_argument('--comparison',type=Path,default=Path(VIS_REL))
    ap.add_argument('--output-dir',type=Path,default=Path(OUT_REL))
    ap.add_argument('--check-only',action='store_true')
    args=ap.parse_args()
    root=args.repo_root.resolve()
    resolve=lambda p: p if p.is_absolute() else root/p
    sp,vp,dest=map(resolve,(args.source_signals,args.comparison,args.output_dir))
    if not args.check_only:
        check(not dest.exists(),f'refusing overwrite existing output directory: {dest}')
    sig=read(sp,REQ_SIG,'scope signal')
    vis=read(vp,REQ_VIS | {'query_title_display','query_author_display'},'frozen comparison')
    tables, summary=run(sig,vis)
    # Independent QC against published frozen v0.2 complete-case correlations,
    # enabled only when BOTH source files match the exact released SHA-256s.
    expected_sig_sha='85373189f4d77cdd4d9fb8313afca0e7e4590379a092c6e879bfe205150ff49a'
    expected_vis_sha='504223c45b017891d9cb5a6ee04cb84cadd9438ba08d44eef096942f3208efdc'
    source_sha=sha(sp); vis_sha=sha(vp)
    if source_sha==expected_sig_sha and vis_sha==expected_vis_sha:
        corr_table=tables['correlations_by_source_alert_cohort_v0_1.tsv']
        def baseline_coefficient(y):
            z=corr_table.loc[
                corr_table.scenario.eq('BASELINE_ALL_W') &
                corr_table.academic_indicator.eq('CORE3') &
                corr_table.comparison_indicator.eq(y)
            ]
            check(len(z)==1,f'baseline correlation missing for {y}')
            return float(z.iloc[0].spearman_rank_corr),int(z.iloc[0].complete_case_project_w)
        check(baseline_coefficient('GOODREADS_RATINGS')==(0.411970,4642),
              'baseline CORE3-GR correlation differs from v0.2 release')
        check(baseline_coefficient('OL_EDITION_COUNT')==(0.405520,31160),
              'baseline CORE3-OL edition correlation differs from v0.2 release')
        print('FROZEN V0.2 CORRELATION REGRESSION CHECK: PASSED')
    print('QC PASSED (scope source-alert sensitivity, inputs unchanged)')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print('CORE3 x historical Goodreads ratings:')
    for d in tables['correlations_by_source_alert_cohort_v0_1.tsv'].to_dict('records'):
        if d['academic_indicator']=='CORE3' and d['comparison_indicator']=='GOODREADS_RATINGS':
            print(d['scenario'], 'n=',d['complete_case_project_w'],'Spearman=',d['spearman_rank_corr'])
    if args.check_only:
        print('CHECK ONLY: NO FILES WRITTEN')
        return
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.scope_alert_robustness_',dir=dest.parent) as staging:
        temp=Path(staging)
        outputs={}
        for filename,table in tables.items():
            p=temp/filename
            table.to_csv(p,sep='\t',index=False,lineterminator='\n',na_rep='')
            outputs[filename]={'rows':len(table),'sha256':sha(p)}
        p=temp/'summary_v0_1.json'
        p.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        outputs[p.name]={'sha256':sha(p)}
        manifest={
          'release':VERSION,'created_utc':datetime.now(timezone.utc).isoformat(),
          'inputs':{
             'scope_signals':{'path':str(sp),'sha256':sha(sp)},
             'frozen_comparison':{'path':str(vp),'sha256':sha(vp)}
          },
          'builder_sha256':sha(Path(__file__)),
          'outputs':outputs,'no_upstream_modified':True
        }
        (temp/'manifest_v0_1.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        check(not dest.exists(),f'output appeared during build: {dest}')
        temp.rename(dest)
    print('OUTPUT:',dest)

if __name__=='__main__':
    main()
