#!/usr/bin/env python3
"""
Classify Q3 targets from the final record codes (BL verification pilot v1).

Implements docs/BL_VERIFICATION_PILOT_V1_ANALYSIS_ADDENDUM_3.md §4 mechanically.
No record is re-judged; final_relation from q3_review.tsv is used as is.

Present (addendum 3 §3.2): final_relation in
    target_alone, target_with_other_works, target_in_collection

Per target:
- title_route_hit:   >= 1 record with via_title_route=TRUE, r3=TRUE and present
- title_route_miss:  not title_route_hit, and >= 1 record with a1k1_only=TRUE and present
- absent_all_routes: no record from any route is present
Records with via_title_route=TRUE, r3=FALSE and present are counted as
title_route_r3_miss and reported in the note; they do not make a target
title_route_hit or title_route_miss. A target whose only present records are
of this kind is not forced into either class (q3_class = not_classified,
with a note). Incomplete routes are reported alongside the class.

Input (read only):
- q3_candidates.tsv
- q3_review.tsv
- q3_target_summary.tsv

Output:
- q3_target_classification.tsv   one row per target

Before running: source ~/canon-pipeline/.venv/bin/activate
"""

import csv
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

PRESENT = {'target_alone', 'target_with_other_works', 'target_in_collection'}
RELATIONS = PRESENT | {'target_excerpt', 'target_abridged_or_retold', 'other_language_version',
                       'adaptation', 'related_study_guide', 'related_criticism', 'related_derivative',
                       'unrelated', 'ambiguous', 'other'}
TARGET_NOTES = {'BLV017': 'Not blind: first edition examined in Q2 (Q2R12).'}


def describe_input(path: Path) -> None:
    """Print sha256 and number of data rows (excluding header) of an input TSV."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with open(path) as f:
        n_rows = sum(1 for _ in csv.DictReader(f, delimiter='\t'))
    print(f"  {path.name}\tsha256={digest}\trows={n_rows}")


def read_tsv(path: Path):
    with open(path) as f:
        return list(csv.DictReader(f, delimiter='\t'))


def main():
    base_dir = Path(__file__).resolve().parents[2]
    derived = base_dir / 'derived' / 'bl_calibration' / 'verification_pilot_v1'

    print("Inputs:")
    for name in ('q3_candidates.tsv', 'q3_review.tsv', 'q3_target_summary.tsv'):
        describe_input(derived / name)

    candidates = read_tsv(derived / 'q3_candidates.tsv')
    review = read_tsv(derived / 'q3_review.tsv')
    summary = read_tsv(derived / 'q3_target_summary.tsv')

    if [(c['sample_id'], c['marc_001']) for c in candidates] != \
       [(r['sample_id'], r['marc_001']) for r in review]:
        sys.exit("ERROR: q3_review.tsv rows do not match q3_candidates.tsv rows")
    bad = {r['final_relation'] for r in review} - RELATIONS
    if bad:
        sys.exit(f"ERROR: unknown final_relation values: {sorted(bad)}")
    if {c['sample_id'] for c in candidates} - {s['sample_id'] for s in summary}:
        sys.exit("ERROR: candidates contain targets missing from q3_target_summary.tsv")

    present_title_r3 = defaultdict(list)
    present_title_r3_miss = defaultdict(list)
    present_a1k1_only = defaultdict(list)
    for c, r in zip(candidates, review):
        if r['final_relation'] not in PRESENT:
            continue
        sid = c['sample_id']
        if c['via_title_route'] == 'TRUE' and c['r3'] == 'TRUE':
            present_title_r3[sid].append(c['marc_001'])
        elif c['via_title_route'] == 'TRUE':
            present_title_r3_miss[sid].append(c['marc_001'])
        elif c['a1k1_only'] == 'TRUE':
            present_a1k1_only[sid].append(c['marc_001'])
        else:
            sys.exit(f"ERROR: present record with no route group: {sid} {c['marc_001']}")

    out_rows = []
    for s in summary:
        sid = s['sample_id']
        n_hit = len(present_title_r3[sid])
        n_r3_miss = len(present_title_r3_miss[sid])
        n_a1k1 = len(present_a1k1_only[sid])

        notes = []
        if n_hit > 0:
            q3_class = 'title_route_hit'
        elif n_a1k1 > 0:
            q3_class = 'title_route_miss'
        elif n_r3_miss > 0:
            q3_class = 'not_classified'
            notes.append('Only present records are title_route_r3_miss; not forced into a class.')
        else:
            q3_class = 'absent_all_routes'
        if n_r3_miss > 0:
            notes.append(f"title_route_r3_miss: {n_r3_miss} ({';'.join(present_title_r3_miss[sid])}).")
        if sid in TARGET_NOTES:
            notes.append(TARGET_NOTES[sid])

        out_rows.append({
            'sample_id': sid,
            'q3_class': q3_class,
            'n_present_title_r3': n_hit,
            'n_present_title_r3_miss': n_r3_miss,
            'n_present_a1k1_only': n_a1k1,
            'any_route_incomplete': s['any_route_incomplete'],
            'incomplete_routes': s['incomplete_routes'],
            'note': ' '.join(notes),
        })

    fields = ['sample_id', 'q3_class', 'n_present_title_r3', 'n_present_title_r3_miss',
              'n_present_a1k1_only', 'any_route_incomplete', 'incomplete_routes', 'note']
    with open(derived / 'q3_target_classification.tsv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"Wrote q3_target_classification.tsv ({len(out_rows)} rows)")

    return 0


if __name__ == '__main__':
    sys.exit(main())
