#!/usr/bin/env python3
"""
Analyze BL verification pilot v1 record structure for Q1 descriptive analysis.

Normalization N1 (used for title and author comparison):
- Unicode NFKC normalization
- casefold (lowercase + locale-independent case folding)
- collapse consecutive whitespace to single space
- strip leading/trailing whitespace
- strip trailing punctuation: space / : ; . , =

Input:
- records_parsed.tsv          parsed MARC records
- target_record_links.tsv     sample_id × marc_001 × routes
- logical_queries.tsv         logical query registry (title_norm, author_name)
- q2_first_edition_review.tsv Q2 human review results
- q2_candidates.tsv           Q2 candidate records

Output:
- q1_record_structure.tsv         aggregated T1 matching statistics
- q1_first_edition_matching.tsv   Q2 first-edition matching details
- q1_failure_examples.tsv         examples that fail all rules

Before running: source ~/canon-pipeline/.venv/bin/activate
"""

import csv
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple


def normalize_n1(text: str) -> str:
    """Apply N1 normalization for title/author comparison.

    N1 normalization:
    1. Unicode NFKC normalization
    2. casefold (lowercase + locale-independent case folding)
    3. collapse consecutive whitespace to single space
    4. strip leading/trailing whitespace
    5. strip trailing punctuation: space / : ; . , =
    """
    if not text:
        return ""

    # NFKC normalization
    text = unicodedata.normalize('NFKC', text)

    # casefold
    text = text.casefold()

    # collapse consecutive whitespace
    text = ' '.join(text.split())

    # strip leading/trailing whitespace
    text = text.strip()

    # strip trailing punctuation
    text = text.rstrip(' /:;.,=')

    return text


def check_matching_rules(field_245a: str, target_titles: List[str]) -> Tuple[bool, bool, bool]:
    """Check R1 (exact), R2 (prefix), R3 (bracket) matching rules.

    R2/R3 are rules measuring low false negatives; they may pass other works
    by the same author (e.g., She and Allan).

    Returns: (r1_match, r2_match, r3_match)
    True if ANY target title matches.
    """
    norm_245a = normalize_n1(field_245a)
    norm_245a_no_brackets = normalize_n1(field_245a.replace('[', '').replace(']', ''))

    r1_match = False
    r2_match = False
    r3_match = False

    for title in target_titles:
        norm_title = normalize_n1(title)

        # R1: exact match
        if norm_245a == norm_title:
            r1_match = True

        # R2: prefix match with word boundary
        # Either exact match, or starts with title and next char is not alphanumeric
        if norm_245a == norm_title:
            r2_match = True
        elif norm_245a.startswith(norm_title):
            # Check character immediately after title
            next_pos = len(norm_title)
            if next_pos < len(norm_245a):
                next_char = norm_245a[next_pos]
                if not next_char.isalnum():
                    r2_match = True
            else:
                # Title extends to end of 245a (shouldn't happen if not exact, but handle it)
                r2_match = True

        # R3: bracket-stripped prefix match with word boundary
        if norm_245a_no_brackets == norm_title:
            r3_match = True
        elif norm_245a_no_brackets.startswith(norm_title):
            # Check character immediately after title
            next_pos = len(norm_title)
            if next_pos < len(norm_245a_no_brackets):
                next_char = norm_245a_no_brackets[next_pos]
                if not next_char.isalnum():
                    r3_match = True
            else:
                r3_match = True

    return (r1_match, r2_match, r3_match)


def get_era(cf008_date1: str) -> str:
    """Classify record by 008 Date1 era (same as field_presence)."""
    if not cf008_date1 or not cf008_date1.strip():
        return 'unknown'

    try:
        year = int(cf008_date1.strip())
        if year < 1900:
            return 'pre-1900'
        elif year < 1950:
            return '1900-1949'
        elif year < 1975:
            return '1950-1974'
        elif year < 2000:
            return '1975-1999'
        else:
            return '2000+'
    except (ValueError, AttributeError):
        return 'unknown'


def get_260_264_status(f260_a: str, f260_b: str, f260_c: str,
                       f264_a: str, f264_b: str, f264_c: str) -> str:
    """Classify 260/264 usage."""
    has_260 = bool(f260_a or f260_b or f260_c)
    has_264 = bool(f264_a or f264_b or f264_c)

    if has_260 and has_264:
        return 'both'
    elif has_260:
        return '260_only'
    elif has_264:
        return '264_only'
    else:
        return 'neither'


def author_surname_in_100(f100_entries: str, author_surnames: Set[str]) -> bool:
    """Check if any author surname appears in 100$a.

    Normalization: casefold both sides for comparison.
    """
    if not f100_entries or not author_surnames:
        return False

    norm_100 = f100_entries.casefold()

    for surname in author_surnames:
        if normalize_n1(surname) in norm_100:
            return True

    return False


def main():
    base_dir = Path(__file__).resolve().parents[2]
    derived = base_dir / 'derived' / 'bl_calibration' / 'verification_pilot_v1'
    scripts = base_dir / 'scripts' / 'bl'

    # Load records
    records = {}
    with open(derived / 'records_parsed.tsv') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            records[row['marc_001']] = row

    print(f"Loaded {len(records)} parsed records")

    # Load target record links
    links = []
    with open(derived / 'target_record_links.tsv') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            links.append(row)

    print(f"Loaded {len(links)} target record links")

    # Load logical queries to get target titles and authors
    # sample_id -> list of (title_norm, author_name)
    sample_queries = defaultdict(list)
    with open(scripts / 'logical_queries.tsv') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            sample_queries[row['sample_id']].append({
                'title_norm': row['title_norm'],
                'author_name': row['author_name'],
                'route': row['route']
            })

    print(f"Loaded queries for {len(sample_queries)} sample_ids")

    # Load Q2 human review results
    q2_matched_records = []
    with open(derived / 'q2_first_edition_review.tsv') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            if row['human_decision'] == 'found' and row['matched_marc_001'].strip():
                marc_001_list = row['matched_marc_001'].split(';')
                for marc_001 in marc_001_list:
                    q2_matched_records.append({
                        'q2_row_id': row['q2_row_id'],
                        'work_label': row['work_label'],
                        'marc_001': marc_001.strip()
                    })

    print(f"Loaded {len(q2_matched_records)} Q2 matched records")

    # A. Analyze T1 links
    print("\n=== Part A: T1 link analysis ===")

    # Collect T1 links with their target titles
    t1_analysis = []

    for link in links:
        routes = link['routes'].split('|')
        if 'T1' not in routes:
            continue

        sample_id = link['sample_id']
        marc_001 = link['marc_001']

        # Get target titles for this sample
        queries = sample_queries.get(sample_id, [])
        target_titles = [q['title_norm'] for q in queries if q['route'] in ['T1', 'T2', 'T3']]

        # Get author surnames for 100 check
        author_surnames = set()
        for q in queries:
            if q['author_name']:
                # Extract surname (last word before comma if present)
                author_name = q['author_name']
                if ',' in author_name:
                    surname = author_name.split(',')[0].strip()
                else:
                    # Last word
                    surname = author_name.split()[-1] if author_name.split() else author_name
                author_surnames.add(surname)

        if not target_titles:
            continue

        rec = records.get(marc_001)
        if not rec:
            continue

        # Check matching rules
        r1, r2, r3 = check_matching_rules(rec['f245_a'], target_titles)

        # Get era and 260/264 status
        era = get_era(rec['cf008_date1'])
        status_260_264 = get_260_264_status(
            rec['f260_a'], rec['f260_b'], rec['f260_c'],
            rec['f264_a'], rec['f264_b'], rec['f264_c']
        )

        # Check 100
        has_100 = bool(rec['f100_entries'])
        surname_match = author_surname_in_100(rec['f100_entries'], author_surnames) if has_100 else False

        t1_analysis.append({
            'marc_001': marc_001,
            'sample_id': sample_id,
            'era': era,
            'status_260_264': status_260_264,
            'r1': r1,
            'r2': r2,
            'r3': r3,
            'has_100': has_100,
            'surname_match': surname_match,
            'f245_a': rec['f245_a'],
            'cf008_date1': rec['cf008_date1'],
            'f100_entries': rec['f100_entries']
        })

    print(f"Analyzed {len(t1_analysis)} T1 links")

    # Aggregate by era × 260/264 status
    aggregates = defaultdict(lambda: {
        'count': 0,
        'r1_pass': 0,
        'r2_pass': 0,
        'r3_pass': 0,
        'has_100': 0,
        'surname_match': 0
    })

    for item in t1_analysis:
        key = (item['era'], item['status_260_264'])
        agg = aggregates[key]
        agg['count'] += 1
        if item['r1']:
            agg['r1_pass'] += 1
        if item['r2']:
            agg['r2_pass'] += 1
        if item['r3']:
            agg['r3_pass'] += 1
        if item['has_100']:
            agg['has_100'] += 1
            if item['surname_match']:
                agg['surname_match'] += 1

    # Write q1_record_structure.tsv
    with open(derived / 'q1_record_structure.tsv', 'w', newline='') as f:
        fieldnames = ['era', 'status_260_264', 'count', 'r1_pass_rate', 'r2_pass_rate',
                      'r3_pass_rate', 'has_100_rate', 'surname_match_rate']
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t', lineterminator='\n')
        writer.writeheader()

        for (era, status_260_264), agg in sorted(aggregates.items()):
            count = agg['count']
            writer.writerow({
                'era': era,
                'status_260_264': status_260_264,
                'count': count,
                'r1_pass_rate': f"{agg['r1_pass'] / count:.4f}" if count > 0 else '0.0000',
                'r2_pass_rate': f"{agg['r2_pass'] / count:.4f}" if count > 0 else '0.0000',
                'r3_pass_rate': f"{agg['r3_pass'] / count:.4f}" if count > 0 else '0.0000',
                'has_100_rate': f"{agg['has_100'] / count:.4f}" if count > 0 else '0.0000',
                'surname_match_rate': f"{agg['surname_match'] / agg['has_100']:.4f}" if agg['has_100'] > 0 else ''
            })

    print(f"Wrote q1_record_structure.tsv")

    # B. Q2 first-edition matching
    print("\n=== Part B: Q2 first-edition matching ===")

    q2_matching = []

    for q2_rec in q2_matched_records:
        marc_001 = q2_rec['marc_001']
        rec = records.get(marc_001)
        if not rec:
            continue

        # Find the sample_id(s) for this Q2 row to get target titles
        # Load Q2 ground truth to get sample_ids
        with open(derived / 'q2_ground_truth.tsv') as f:
            for row in csv.DictReader(f, delimiter='\t'):
                if row['q2_row_id'] == q2_rec['q2_row_id']:
                    sample_ids = row['sample_ids'].split(';')

                    # Get target titles
                    target_titles = []
                    author_surnames = set()
                    for sample_id in sample_ids:
                        queries = sample_queries.get(sample_id, [])
                        target_titles.extend([q['title_norm'] for q in queries if q['route'] in ['T1', 'T2', 'T3']])
                        for q in queries:
                            if q['author_name']:
                                author_name = q['author_name']
                                if ',' in author_name:
                                    surname = author_name.split(',')[0].strip()
                                else:
                                    surname = author_name.split()[-1] if author_name.split() else author_name
                                author_surnames.add(surname)

                    if target_titles:
                        r1, r2, r3 = check_matching_rules(rec['f245_a'], target_titles)
                        has_100 = bool(rec['f100_entries'])
                        surname_match = author_surname_in_100(rec['f100_entries'], author_surnames) if has_100 else False

                        q2_matching.append({
                            'q2_row_id': q2_rec['q2_row_id'],
                            'work_label': q2_rec['work_label'],
                            'marc_001': marc_001,
                            'r1': 'TRUE' if r1 else 'FALSE',
                            'r2': 'TRUE' if r2 else 'FALSE',
                            'r3': 'TRUE' if r3 else 'FALSE',
                            'has_100': 'TRUE' if has_100 else 'FALSE',
                            'surname_match': 'TRUE' if surname_match else 'FALSE' if has_100 else '',
                            'f245_a': rec['f245_a'],
                            'cf008_date1': rec['cf008_date1'],
                            'f100_entries': rec['f100_entries']
                        })
                    break

    with open(derived / 'q1_first_edition_matching.tsv', 'w', newline='') as f:
        fieldnames = ['q2_row_id', 'work_label', 'marc_001', 'r1', 'r2', 'r3',
                      'has_100', 'surname_match', 'f245_a', 'cf008_date1', 'f100_entries']
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(q2_matching)

    print(f"Wrote q1_first_edition_matching.tsv ({len(q2_matching)} records)")

    # C. Failure examples (records that fail even R3)
    print("\n=== Part C: Failure examples ===")

    failures_by_era = defaultdict(list)

    for item in t1_analysis:
        if not item['r3']:  # Fails even R3
            failures_by_era[item['era']].append(item)

    failure_examples = []

    for era in sorted(failures_by_era.keys()):
        examples = failures_by_era[era][:5]  # Max 5 per era
        for ex in examples:
            failure_examples.append({
                'era': era,
                'marc_001': ex['marc_001'],
                'f245_a': ex['f245_a'],
                'cf008_date1': ex['cf008_date1'],
                'f100_entries': ex['f100_entries']
            })

    with open(derived / 'q1_failure_examples.tsv', 'w', newline='') as f:
        fieldnames = ['era', 'marc_001', 'f245_a', 'cf008_date1', 'f100_entries']
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(failure_examples)

    print(f"Wrote q1_failure_examples.tsv ({len(failure_examples)} examples)")

    return 0


if __name__ == '__main__':
    sys.exit(main())
