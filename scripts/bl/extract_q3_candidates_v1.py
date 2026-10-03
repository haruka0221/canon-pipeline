#!/usr/bin/env python3
"""
Extract Q3 candidates (random targets) from parsed BL verification pilot v1 records.

Implements docs/BL_VERIFICATION_PILOT_V1_ANALYSIS_ADDENDUM_3.md §2.
Mechanical extraction only: no relation class and no target class is assigned.

Targets: sample rows with stratum random_w or random_unresolved (selected by
stratum, not by hard-coded IDs).

Matching rule (addendum 3 §2.1): normalize_n1 and check_matching_rules are
copied without change from scripts/bl/analyze_q1_record_structure_v1.py
(commit d323b4f). Comparison is against 245$a only and against every T1-T3
title_norm of the target. 240, 246, 505 and 700$t are output as raw values and
are not used for matching. surname_in_100 / surname_in_700 use the Q1 surname
rule and are for information only.

R2/R3 precision has not been measured. A record passing R3 is a candidate,
not an acceptance.

Input (read only):
- bl_verification_pilot_v1_sample.tsv
- logical_queries.tsv
- physical_query_status.tsv
- target_record_links.tsv
- records_parsed.tsv

Output:
- q3_candidates.tsv           one row per target × linked record
- q3_target_summary.tsv       one row per target

Before running: source ~/canon-pipeline/.venv/bin/activate
"""

import csv
import hashlib
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

Q3_STRATA = ('random_w', 'random_unresolved')
TITLE_ROUTES = ('T1', 'T2', 'T3')


# --- copied without change from analyze_q1_record_structure_v1.py (d323b4f) ---

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

# --- end of copied functions ---


def surname_of(author_name: str) -> str:
    """Surname as in Q1: part before the first comma, else the last word."""
    if ',' in author_name:
        return author_name.split(',')[0].strip()
    return author_name.split()[-1] if author_name.split() else author_name


def tf(value: bool) -> str:
    return 'TRUE' if value else 'FALSE'


def surname_flag(entries: str, author_surnames: Set[str]) -> str:
    """As in Q1: empty when the field is absent, else TRUE/FALSE."""
    if not entries:
        return ''
    return tf(author_surname_in_100(entries, author_surnames))


def describe_input(path: Path) -> None:
    """Print sha256 and number of data rows (excluding header) of an input TSV."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with open(path) as f:
        n_rows = sum(1 for _ in csv.DictReader(f, delimiter='\t'))
    print(f"  {path.name}\tsha256={digest}\trows={n_rows}")


def unique_in_order(values: List[str]) -> List[str]:
    seen = set()
    out = []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def main():
    base_dir = Path(__file__).resolve().parents[2]
    derived = base_dir / 'derived' / 'bl_calibration' / 'verification_pilot_v1'

    print("Inputs:")
    for name in ('bl_verification_pilot_v1_sample.tsv', 'logical_queries.tsv',
                 'physical_query_status.tsv', 'target_record_links.tsv', 'records_parsed.tsv'):
        describe_input(derived / name)

    # Q3 targets, selected by stratum
    targets = []
    with open(derived / 'bl_verification_pilot_v1_sample.tsv') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            if row['stratum'] in Q3_STRATA:
                targets.append(row)
    target_ids = [t['sample_id'] for t in targets]
    print(f"Q3 targets ({len(targets)}): {', '.join(target_ids)}")

    # Logical queries per target, in file order
    queries: Dict[str, List[dict]] = defaultdict(list)
    with open(derived / 'logical_queries.tsv') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            if row['sample_id'] in target_ids:
                queries[row['sample_id']].append(row)

    # Physical query status
    phys_status = {}
    with open(derived / 'physical_query_status.tsv') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            phys_status[row['phys_id']] = row['status']

    # Links
    links: Dict[str, List[dict]] = defaultdict(list)
    seen_links: Set[Tuple[str, str]] = set()
    with open(derived / 'target_record_links.tsv') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            if row['sample_id'] not in target_ids:
                continue
            key = (row['sample_id'], row['marc_001'])
            if key in seen_links:
                sys.exit(f"ERROR: duplicate link {key}")
            seen_links.add(key)
            links[row['sample_id']].append(row)

    # Records (only those linked to Q3 targets)
    needed = {m for (_, m) in seen_links}
    records = {}
    with open(derived / 'records_parsed.tsv') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            if row['marc_001'] in needed:
                records[row['marc_001']] = row
    missing = needed - set(records)
    if missing:
        sys.exit(f"ERROR: {len(missing)} linked records missing from records_parsed.tsv")

    candidate_rows = []
    summary_rows = []

    for target in targets:
        sid = target['sample_id']
        tq = queries[sid]
        if not tq:
            sys.exit(f"ERROR: no logical queries for {sid}")

        title_norms = unique_in_order([q['title_norm'] for q in tq if q['route'] in TITLE_ROUTES])
        author_names = unique_in_order([q['author_name'] for q in tq])
        author_surnames = {surname_of(a) for a in author_names}
        multi_title = len(title_norms) > 1

        # Route completeness (addendum 3 §2.3)
        route_statuses = []
        incomplete = []
        for q in tq:
            if q['phys_id'] not in phys_status:
                sys.exit(f"ERROR: no status for {q['phys_id']} ({q['bl_query_id']})")
            status = phys_status[q['phys_id']]
            label = q['route']
            if multi_title and q['title_norm']:
                label = f"{label}[{q['title_norm']}]"
            route_statuses.append(f"{label}:{status}")
            if status != 'COMPLETE':
                incomplete.append(f"{label}:{status}")

        counts = {'n_links': 0, 'n_title_route': 0, 'n_title_route_r3': 0,
                  'n_a1k1_only': 0, 'n_a1k1_only_r3': 0}

        for link in sorted(links[sid], key=lambda r: r['marc_001']):
            rec = records[link['marc_001']]
            routes = set(link['routes'].split('|'))
            via_title = bool(routes & set(TITLE_ROUTES))
            via_a1 = 'A1' in routes
            via_k1 = 'K1' in routes
            a1k1_only = bool(routes) and routes <= {'A1', 'K1'}
            if not via_title and not a1k1_only:
                sys.exit(f"ERROR: unexpected routes {link['routes']} for {sid} {link['marc_001']}")

            r1, r2, r3 = check_matching_rules(rec['f245_a'], title_norms)
            r3_titles = [t for t in title_norms if check_matching_rules(rec['f245_a'], [t])[2]]

            candidate_rows.append({
                'sample_id': sid,
                'marc_001': link['marc_001'],
                'routes': link['routes'],
                'via_title_route': tf(via_title),
                'via_a1': tf(via_a1),
                'via_k1': tf(via_k1),
                'a1k1_only': tf(a1k1_only),
                'r1': tf(r1),
                'r2': tf(r2),
                'r3': tf(r3),
                'r3_matched_title_norm': ';'.join(r3_titles),
                'surname_in_100': surname_flag(rec['f100_entries'], author_surnames),
                # same check as for 100, applied to the 700 entries
                'surname_in_700': surname_flag(rec['f700_entries'], author_surnames),
                'f245_a': rec['f245_a'],
                'f245_b': rec['f245_b'],
                'f245_c': rec['f245_c'],
                'f246_a': rec['f246_a'],
                'f240_a': rec['f240_a'],
                'f130_a': rec['f130_a'],
                'has_f505': rec['has_f505'],
                'has_f600_t': rec['has_f600_t'],
                'cf008_date1': rec['cf008_date1'],
                'cf008_language': rec['cf008_language'],
                'f041_a': rec['f041_a'],
                'f041_h': rec['f041_h'],
                'f250_a': rec['f250_a'],
                'f260_a': rec['f260_a'],
                'f260_b': rec['f260_b'],
                'f260_c': rec['f260_c'],
                'f264_a': rec['f264_a'],
                'f264_b': rec['f264_b'],
                'f264_c': rec['f264_c'],
                'f100_entries': rec['f100_entries'],
                'f700_entries': rec['f700_entries'],
            })

            counts['n_links'] += 1
            if via_title:
                counts['n_title_route'] += 1
                if r3:
                    counts['n_title_route_r3'] += 1
            if a1k1_only:
                counts['n_a1k1_only'] += 1
                if r3:
                    counts['n_a1k1_only_r3'] += 1

        summary_rows.append({
            'sample_id': sid,
            'target_lane': target['target_lane'],
            'project_work_id': target['project_work_id'],
            'unresolved_unit_anchor_entity_id': target['unresolved_unit_anchor_entity_id'],
            'title_norms': ';'.join(title_norms),
            'author_name': ';'.join(author_names),
            'route_statuses': '|'.join(route_statuses),
            'any_route_incomplete': tf(bool(incomplete)),
            'incomplete_routes': '|'.join(incomplete),
            **counts,
        })
        print(f"  {sid}: {counts['n_links']} links, "
              f"{counts['n_title_route']} via title route ({counts['n_title_route_r3']} R3), "
              f"{counts['n_a1k1_only']} A1/K1 only ({counts['n_a1k1_only_r3']} R3), "
              f"incomplete: {'|'.join(incomplete) or '-'}")

    cand_fields = ['sample_id', 'marc_001', 'routes', 'via_title_route', 'via_a1', 'via_k1', 'a1k1_only',
                   'r1', 'r2', 'r3', 'r3_matched_title_norm', 'surname_in_100', 'surname_in_700',
                   'f245_a', 'f245_b', 'f245_c', 'f246_a', 'f240_a', 'f130_a', 'has_f505', 'has_f600_t',
                   'cf008_date1', 'cf008_language', 'f041_a', 'f041_h', 'f250_a',
                   'f260_a', 'f260_b', 'f260_c', 'f264_a', 'f264_b', 'f264_c', 'f100_entries', 'f700_entries']
    with open(derived / 'q3_candidates.tsv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=cand_fields, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(candidate_rows)
    print(f"Wrote q3_candidates.tsv ({len(candidate_rows)} rows)")

    summary_fields = ['sample_id', 'target_lane', 'project_work_id', 'unresolved_unit_anchor_entity_id',
                      'title_norms', 'author_name', 'route_statuses',
                      'any_route_incomplete', 'incomplete_routes',
                      'n_links', 'n_title_route', 'n_title_route_r3', 'n_a1k1_only', 'n_a1k1_only_r3']
    with open(derived / 'q3_target_summary.tsv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"Wrote q3_target_summary.tsv ({len(summary_rows)} rows)")

    return 0


if __name__ == '__main__':
    sys.exit(main())
