#!/usr/bin/env python3
"""Build a NON-ADJUDICATED 80-W exploratory register from eight frozen Markdown notes.

Reads only input evidence notes; writes one TSV in --output-dir.
Uses exact documented AI proposals, not independent bibliographic judgments.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import re
from collections import Counter
from pathlib import Path

FILES = [
    (1, 10, 'random_scope_first10_evidence_update_v0_2.md', 'derived/scope/random_scope_review_draft_v0_2/random_scope_first10_evidence_update_v0_2.md'),
    (11, 20, 'random_scope_11_20_evidence_draft_v0_1.md', 'derived/scope/random_scope_review_draft_v0_3/random_scope_11_20_evidence_draft_v0_1.md'),
    (21, 30, 'random_scope_21_30_evidence_draft_v0_1.md', 'derived/scope/random_scope_review_draft_v0_4/random_scope_21_30_evidence_draft_v0_1.md'),
    (31, 40, 'random_scope_31_40_evidence_draft_v0_1.md', 'derived/scope/random_scope_review_draft_v0_5/random_scope_31_40_evidence_draft_v0_1.md'),
    (41, 50, 'random_scope_41_50_evidence_draft_v0_1.md', 'derived/scope/random_scope_review_draft_v0_6/random_scope_41_50_evidence_draft_v0_1.md'),
    (51, 60, 'random_scope_51_60_evidence_draft_v0_1.md', 'derived/scope/random_scope_review_draft_v0_7/random_scope_51_60_evidence_draft_v0_1.md'),
    (61, 70, 'random_scope_61_70_evidence_draft_v0_1.md', 'derived/scope/random_scope_review_draft_v0_8/random_scope_61_70_evidence_draft_v0_1.md'),
    (71, 80, 'random_scope_71_80_evidence_draft_v0_1.md', 'derived/scope/random_scope_review_draft_v0_9/random_scope_71_80_evidence_draft_v0_1.md'),
]
W_ID = re.compile(r'W\d{9}\b')
URL = re.compile(r'https?://[^\s<>"`]+')
CASE_HEADING = re.compile(r'^#{2,3}\s*(\d{1,2})(?:\.|\s*[—–-])\s*(W\d{9})\b')
CLASSES = ('IN_SCOPE_CANDIDATE', 'OUT_OF_SCOPE_CANDIDATE', 'UNRESOLVED')


def clean_cell(s: str) -> str:
    return s.strip().replace('`', '').replace('**', '').strip()


def proposal(raw: str) -> str:
    if raw.startswith('UNRESOLVED'):
        return 'UNRESOLVED'
    if raw.startswith('IN_SCOPE_CANDIDATE'):
        return 'IN_SCOPE_CANDIDATE'
    if raw.startswith('OUT_OF_SCOPE_CANDIDATE'):
        return 'OUT_OF_SCOPE_CANDIDATE'
    raise ValueError(f'Unknown proposal: {raw!r}')


def urls_from(text: str) -> list[str]:
    out = []
    for m in URL.findall(text):
        url = m.rstrip('.,;)]}')
        if url not in out:
            out.append(url)
    return out


def case_sources(text: str, start: int, end: int) -> dict[str, list[str]]:
    if start == 1:
        s = text.split('## Source URLs for later independent verification',1)
        if len(s) != 2:
            raise ValueError('Missing first-10 source URL section')
        section = s[1].split('\n## ',1)[0]
        blocks = re.split(r'(?m)^- (W\d{9}):\s*$', section)
        return {w: urls_from(blocks[2*i+2]) for i,w in enumerate(blocks[1::2])}
    found: dict[str, list[str]] = {}
    lines = text.splitlines()
    positions = []
    for ix, line in enumerate(lines):
        m = CASE_HEADING.match(line)
        if m and start <= int(m.group(1)) <= end:
            positions.append((ix, m.group(2)))
    assert len(positions) == 10, (start, end, positions)
    for ix, (line_num, w) in enumerate(positions):
        next_case_line = positions[ix+1][0] if ix+1 < len(positions) else len(lines)
        # Last item must end when a new methodological section starts.
        next_heading = next((j for j in range(line_num+1, next_case_line)
                             if lines[j].startswith('## ')), next_case_line)
        found[w] = urls_from('\n'.join(lines[line_num+1:next_heading]))
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--source-dir', type=Path, default=Path('.'), help='directory containing the eight Markdown source drafts, or project repository root')
    ap.add_argument('--output-dir', type=Path, required=True)
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for start,end,filename,repo_path in FILES:
        local = args.source_dir / filename
        if not local.exists():
            local = args.source_dir / repo_path
        assert local.is_file(), f'Missing source {filename}'
        txt = local.read_text(encoding='utf-8')
        source_by_w = case_sources(txt, start, end)
        selected=[]
        for line in txt.splitlines():
            if not line.startswith('|') or line.startswith('|---') or line.startswith('|:'):
                continue
            cells = [clean_cell(x) for x in line.strip().strip('|').split('|')]
            matches = [W_ID.fullmatch(c) for c in cells]
            if not any(matches):
                continue
            wi = next(i for i,v in enumerate(matches) if v)
            w=cells[wi]
            if start==1:
                # first ten updated model proposals: W | title/author | proposal | evidence | outstanding
                assert wi==0 and len(cells)==5, (filename,cells)
                idx = len(selected)+1
                title = cells[1]
                raw = cells[2]
                basis = cells[3]
                caveat = cells[4]
            else:
                assert wi==1 and len(cells)>=5, (filename,cells)
                idx = int(cells[0])
                possible = [i for i,c in enumerate(cells) if any(c.startswith(cls) for cls in CLASSES)]
                assert len(possible)==1, (filename, idx, cells, possible)
                pi = possible[0]
                raw = cells[pi]
                # the title is the field immediately before proposal unless year field intervenes
                title = cells[2] if len(cells)==5 else (cells[3] if pi==5 else cells[pi-1])
                basis = cells[pi+1] if pi+1<len(cells) else ''
                caveat = ''
            assert start <= idx <= end, (filename, idx)
            selected.append((idx, w))
            links=source_by_w.get(w,[])
            rows.append({
                'random_rank':idx, 'project_work_id':w,
                'draft_title_or_title_author':title,
                'ai_proposed_class':proposal(raw), 'ai_proposal_verbatim':raw,
                'ai_summary_basis_verbatim':basis,
                'ai_outstanding_verification_first10':caveat,
                'evidence_url_count':len(links),
                'evidence_urls_joined':' ; '.join(links),
                'reviewer_scope_decision':'',
                'reviewer_verification_notes':'',
                'source_evidence_draft_repo_path':repo_path,
            })
        assert len(selected)==10 and len(set(selected))==10, (filename,selected)
        assert set(source_by_w)==set(w for _,w in selected), (filename, set(source_by_w)^set(w for _,w in selected))
    rows.sort(key=lambda r:r['random_rank'])
    assert [r['random_rank'] for r in rows]==list(range(1,81))
    assert len({r['project_work_id'] for r in rows})==80
    frame = args.source_dir / 'derived/scope/scope_evidence_pilot_v1/scope_evidence_review_template_v1.tsv'
    if frame.exists():
        with frame.open(encoding='utf-8', newline='') as f:
            frame_rows = list(csv.DictReader(f, delimiter='\t'))
        cohort = [r['project_work_id'] for r in frame_rows
                  if r['is_independent_random_active_sample'].strip().lower()=='true']
        assert len(cohort)==80 and len(set(cohort))==80, 'Frozen random sample must have 80 unique W'
        seed='scope-random80-first10-20261020'
        cohort.sort(key=lambda w:hashlib.sha256((seed+'\x1f'+w).encode('utf-8')).hexdigest())
        assert [r['project_work_id'] for r in rows]==cohort, 'Mismatch with frozen random-80 sampling frame/order'
        print('Frozen 80-W sample membership/order: VERIFIED')
    else:
        print('Frozen sample membership/order: NOT VERIFIED (no sampling frame at source-dir)')
    count=Counter(r['ai_proposed_class'] for r in rows)
    assert count == {'IN_SCOPE_CANDIDATE':44,'OUT_OF_SCOPE_CANDIDATE':26,'UNRESOLVED':10}, count
    assert all(r['evidence_url_count'] > 0 for r in rows), [(r['random_rank'],r['project_work_id']) for r in rows if r['evidence_url_count']==0]
    out=args.output_dir/'random_scope_80_ai_exploratory_register_v0_1.tsv'
    with out.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    print('Wrote:',out)
    print('Counts:',dict(count))
    print('URLs:',sum(r['evidence_url_count'] for r in rows),'across',len(rows),'works')
    print('Each of 80 unique IDs with >= 1 URL; all source sections matched.')

if __name__=='__main__':
    main()
