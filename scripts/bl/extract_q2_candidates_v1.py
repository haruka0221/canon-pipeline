#!/usr/bin/env python3
"""
Extract Q2 first edition candidates from parsed BL verification pilot v1 records.

Year extraction rules:
- Extract all 4-digit sequences matching pattern \d{4} from 008 Date1 and 260/264 $c
- Accept years in brackets: [1891], parentheses: (1891), after "i.e.": "1890 [i.e. 1891]"
- Accept years with punctuation: "1891.", "1891,"
- For "i.e." constructions, extract both the stated and corrected year
- A record is a candidate if ANY extracted year falls within expected_year ± 1

Input:
- q2_ground_truth.tsv         ground truth first editions
- records_parsed.tsv          parsed MARC records
- target_record_links.tsv     sample_id × marc_001 × routes

Output:
- q2_candidates.tsv           q2_row_id × marc_001 with selected fields
- q2_candidates_diagnostics.tsv  undated record counts

No judgment or classification; outputs raw field values for human review.
"""

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Set, Tuple

def extract_years(text: str) -> List[int]:
    """Extract all 4-digit years from text.

    Handles: 1891, [1891], (1891), 1891., 1890 [i.e. 1891], etc.
    Returns list of integer years found.
    """
    if not text:
        return []

    # Find all 4-digit sequences
    matches = re.findall(r'\d{4}', text)
    years = []
    for match in matches:
        try:
            year = int(match)
            # Filter obviously invalid years (e.g. "1234" in ISBNs)
            # Keep only plausible publication years
            if 1400 <= year <= 2030:
                years.append(year)
        except ValueError:
            continue

    return years


def has_roman_numerals(text: str) -> bool:
    """Check if text contains Roman numeral-like tokens.

    Returns True if any whitespace-delimited token consists only of
    Roman numeral characters (M, D, C, L, X, V, I).
    """
    if not text:
        return False

    # Split on whitespace and punctuation, check each token
    tokens = re.findall(r'[MDCLXVI]+', text.upper())
    return len(tokens) > 0


def main():
    base_dir = Path(__file__).resolve().parents[2]
    derived = base_dir / 'derived' / 'bl_calibration' / 'verification_pilot_v1'

    # Load ground truth
    ground_truth = []
    with open(derived / 'q2_ground_truth.tsv') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            ground_truth.append(row)

    print(f"Loaded {len(ground_truth)} ground truth rows")

    # Load parsed records
    records = {}
    with open(derived / 'records_parsed.tsv') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            records[row['marc_001']] = row

    print(f"Loaded {len(records)} parsed records")

    # Load target record links
    # sample_id -> set of (marc_001, routes)
    sample_links = defaultdict(list)
    with open(derived / 'target_record_links.tsv') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            sample_links[row['sample_id']].append({
                'marc_001': row['marc_001'],
                'routes': row['routes']
            })

    print(f"Loaded links for {len(sample_links)} sample_ids")

    # Extract candidates and diagnostics
    candidates = []
    diagnostics = []

    for gt_row in ground_truth:
        q2_row_id = gt_row['q2_row_id']
        sample_ids = gt_row['sample_ids'].split(';')
        expected_year = int(gt_row['expected_year'])

        # Collect all records linked to these sample_ids
        linked_records = {}  # marc_001 -> routes (deduplicated)
        for sample_id in sample_ids:
            for link in sample_links.get(sample_id, []):
                marc_001 = link['marc_001']
                if marc_001 not in linked_records:
                    linked_records[marc_001] = set()
                linked_records[marc_001].update(link['routes'].split('|'))

        print(f"{q2_row_id}: {len(linked_records)} linked records, expected year {expected_year}")

        # Track undated records
        undated_count = 0
        undated_roman_count = 0

        # Filter to candidates within ±1 year
        for marc_001, routes_set in linked_records.items():
            rec = records[marc_001]

            # Extract years from 008 Date1
            years_008 = extract_years(rec['cf008_date1'])

            # Extract years from 260 $c and 264 $c
            years_260 = extract_years(rec['f260_c'])
            years_264 = extract_years(rec['f264_c'])

            all_years = years_008 + years_260 + years_264

            # Check if undated
            if not all_years:
                undated_count += 1
                # Check for Roman numerals in 260/264 $c
                if (has_roman_numerals(rec['f260_c']) or
                    has_roman_numerals(rec['f264_c'])):
                    undated_roman_count += 1

            # Check if any year falls within expected ± 1
            if any(abs(year - expected_year) <= 1 for year in all_years):
                candidates.append({
                    'q2_row_id': q2_row_id,
                    'marc_001': marc_001,
                    'routes': '|'.join(sorted(routes_set)),
                    'cf008_date1': rec['cf008_date1'],
                    'f260_a': rec['f260_a'],
                    'f260_b': rec['f260_b'],
                    'f260_c': rec['f260_c'],
                    'f264_a': rec['f264_a'],
                    'f264_b': rec['f264_b'],
                    'f264_c': rec['f264_c'],
                    'f245_a': rec['f245_a'],
                    'f245_b': rec['f245_b'],
                    'f245_c': rec['f245_c'],
                    'f250_a': rec['f250_a'],
                    'f100_entries': rec['f100_entries']
                })

        # Record diagnostics
        diagnostics.append({
            'q2_row_id': q2_row_id,
            'total_linked': len(linked_records),
            'undated': undated_count,
            'undated_with_roman': undated_roman_count
        })

    # Write candidates
    fieldnames = ['q2_row_id', 'marc_001', 'routes', 'cf008_date1',
                  'f260_a', 'f260_b', 'f260_c',
                  'f264_a', 'f264_b', 'f264_c',
                  'f245_a', 'f245_b', 'f245_c',
                  'f250_a', 'f100_entries']

    with open(derived / 'q2_candidates.tsv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(candidate)

    print(f"\nWrote {len(candidates)} candidates to q2_candidates.tsv")

    # Write diagnostics
    diag_fieldnames = ['q2_row_id', 'total_linked', 'undated', 'undated_with_roman']

    with open(derived / 'q2_candidates_diagnostics.tsv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=diag_fieldnames, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        for diag in diagnostics:
            writer.writerow(diag)

    print(f"Wrote {len(diagnostics)} diagnostic rows to q2_candidates_diagnostics.tsv")

    # Summary by q2_row_id
    by_row = defaultdict(int)
    for c in candidates:
        by_row[c['q2_row_id']] += 1

    print("\nCandidates per ground truth row:")
    for q2_row_id in sorted(by_row.keys()):
        print(f"  {q2_row_id}: {by_row[q2_row_id]}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
