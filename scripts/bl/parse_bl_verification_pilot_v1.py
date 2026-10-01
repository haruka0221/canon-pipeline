#!/usr/bin/env python3
"""
Parse BL verification pilot v1 raw MARCXML responses.

Input:
- physical_requests.tsv (outcome=COMPLETE rows)
- raw XML files (from run_manifest raw_root)
- logical_queries.tsv

Output (derived/bl_calibration/verification_pilot_v1/):
- records_parsed.tsv     one row per distinct MARC 001
- target_record_links.tsv  sample_id × MARC 001 × routes
- field_presence.tsv     field presence rates by 008 Date1 era

No judgment or classification; values are preserved as-is with normalized
columns kept separate.
"""

import csv
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

# MARC21 slim namespace
NS = {'marc': 'http://www.loc.gov/MARC21/slim'}


def parse_controlfield(record, tag):
    """Extract controlfield value."""
    cf = record.find(f'marc:controlfield[@tag="{tag}"]', NS)
    return cf.text.strip() if cf is not None and cf.text else ''


def parse_leader(record):
    """Extract leader."""
    leader = record.find('marc:leader', NS)
    return leader.text if leader is not None and leader.text else ''


def parse_008_date1(cf008):
    """Extract Date1 from 008 (positions 7-10)."""
    if len(cf008) >= 11:
        return cf008[7:11]
    return ''


def parse_008_language(cf008):
    """Extract language from 008 (positions 35-37)."""
    if len(cf008) >= 38:
        return cf008[35:38]
    return ''


def parse_datafield_subfields(record, tag, subfields):
    """Extract datafield subfields as separate columns.

    Returns dict: {subfield_code: [values]}
    """
    result = {sf: [] for sf in subfields}
    for df in record.findall(f'marc:datafield[@tag="{tag}"]', NS):
        for sf_code in subfields:
            for sf in df.findall(f'marc:subfield[@code="{sf_code}"]', NS):
                if sf.text:
                    result[sf_code].append(sf.text.strip())
    return result


def has_subfield(record, tag, subfield):
    """Check if a datafield has a specific subfield."""
    for df in record.findall(f'marc:datafield[@tag="{tag}"]', NS):
        if df.find(f'marc:subfield[@code="{subfield}"]', NS) is not None:
            return True
    return False


def parse_name_fields(record, tag):
    """Parse 100/700 fields, tracking presence of $t."""
    entries = []
    for df in record.findall(f'marc:datafield[@tag="{tag}"]', NS):
        name_parts = []
        has_t = False
        for sf in df.findall('marc:subfield', NS):
            code = sf.get('code')
            if code and sf.text:
                if code == 't':
                    has_t = True
                name_parts.append(f'${code} {sf.text.strip()}')
        if name_parts:
            entry = ' '.join(name_parts)
            if has_t:
                entry += ' [has$t]'
            entries.append(entry)
    return entries


def field_exists(record, tag):
    """Check if field exists."""
    return record.find(f'marc:datafield[@tag="{tag}"]', NS) is not None or \
           record.find(f'marc:controlfield[@tag="{tag}"]', NS) is not None


def parse_record(record_elem) -> Dict:
    """Parse one MARC record element."""
    rec = {}

    # Control fields
    rec['marc_001'] = parse_controlfield(record_elem, '001')
    rec['leader'] = parse_leader(record_elem)
    cf008 = parse_controlfield(record_elem, '008')
    rec['cf008'] = cf008
    rec['cf008_date1'] = parse_008_date1(cf008)
    rec['cf008_language'] = parse_008_language(cf008)

    # 041 language codes
    lang041 = parse_datafield_subfields(record_elem, '041', ['a', 'b', 'h'])
    rec['f041_a'] = '|'.join(lang041['a']) if lang041['a'] else ''
    rec['f041_b'] = '|'.join(lang041['b']) if lang041['b'] else ''
    rec['f041_h'] = '|'.join(lang041['h']) if lang041['h'] else ''

    # 245 title
    f245 = parse_datafield_subfields(record_elem, '245', ['a', 'b', 'c'])
    rec['f245_a'] = '|'.join(f245['a']) if f245['a'] else ''
    rec['f245_b'] = '|'.join(f245['b']) if f245['b'] else ''
    rec['f245_c'] = '|'.join(f245['c']) if f245['c'] else ''

    # 246 variant title
    f246 = parse_datafield_subfields(record_elem, '246', ['a'])
    rec['f246_a'] = '|'.join(f246['a']) if f246['a'] else ''

    # 250 edition
    f250 = parse_datafield_subfields(record_elem, '250', ['a'])
    rec['f250_a'] = '|'.join(f250['a']) if f250['a'] else ''

    # 260/264 publication
    f260 = parse_datafield_subfields(record_elem, '260', ['a', 'b', 'c'])
    rec['f260_a'] = '|'.join(f260['a']) if f260['a'] else ''
    rec['f260_b'] = '|'.join(f260['b']) if f260['b'] else ''
    rec['f260_c'] = '|'.join(f260['c']) if f260['c'] else ''

    f264 = parse_datafield_subfields(record_elem, '264', ['a', 'b', 'c'])
    rec['f264_a'] = '|'.join(f264['a']) if f264['a'] else ''
    rec['f264_b'] = '|'.join(f264['b']) if f264['b'] else ''
    rec['f264_c'] = '|'.join(f264['c']) if f264['c'] else ''

    # 100/700 names with $t tracking
    rec['f100_entries'] = '||'.join(parse_name_fields(record_elem, '100'))
    rec['f700_entries'] = '||'.join(parse_name_fields(record_elem, '700'))

    # 240/130 uniform title
    f240 = parse_datafield_subfields(record_elem, '240', ['a'])
    rec['f240_a'] = '|'.join(f240['a']) if f240['a'] else ''
    f130 = parse_datafield_subfields(record_elem, '130', ['a'])
    rec['f130_a'] = '|'.join(f130['a']) if f130['a'] else ''

    # 505 contents note presence
    rec['has_f505'] = 'yes' if field_exists(record_elem, '505') else 'no'

    # 600$t subject with title
    rec['has_f600_t'] = 'yes' if has_subfield(record_elem, '600', 't') else 'no'

    # 015 national bibliography number
    f015 = parse_datafield_subfields(record_elem, '015', ['a'])
    rec['f015_a'] = '|'.join(f015['a']) if f015['a'] else ''

    # 020 ISBN
    f020 = parse_datafield_subfields(record_elem, '020', ['a'])
    rec['f020_a'] = '|'.join(f020['a']) if f020['a'] else ''

    # 336/337/338 RDA content/media/carrier
    f336 = parse_datafield_subfields(record_elem, '336', ['a', 'b'])
    rec['f336_a'] = '|'.join(f336['a']) if f336['a'] else ''
    rec['f336_b'] = '|'.join(f336['b']) if f336['b'] else ''

    f337 = parse_datafield_subfields(record_elem, '337', ['a', 'b'])
    rec['f337_a'] = '|'.join(f337['a']) if f337['a'] else ''
    rec['f337_b'] = '|'.join(f337['b']) if f337['b'] else ''

    f338 = parse_datafield_subfields(record_elem, '338', ['a', 'b'])
    rec['f338_a'] = '|'.join(f338['a']) if f338['a'] else ''
    rec['f338_b'] = '|'.join(f338['b']) if f338['b'] else ''

    # 776 additional physical form
    rec['has_f776'] = 'yes' if field_exists(record_elem, '776') else 'no'

    return rec


def main():
    base_dir = Path(__file__).resolve().parents[2]
    derived = base_dir / 'derived' / 'bl_calibration' / 'verification_pilot_v1'

    # Load manifest for raw_root
    manifests = sorted(derived.glob('run_manifest_*.json'))
    if not manifests:
        print("ERROR: no run_manifest found", file=sys.stderr)
        return 1

    with open(manifests[-1]) as f:
        manifest = json.load(f)
    raw_root = Path(manifest['raw_root'])

    # Load physical requests (COMPLETE only)
    requests = []
    with open(derived / 'physical_requests.tsv') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            if row['outcome'] == 'COMPLETE':
                requests.append(row)

    print(f"Processing {len(requests)} COMPLETE requests from {len(set(r['phys_id'] for r in requests))} physical queries")

    # Load logical queries for sample_id lookup
    phys_to_samples = defaultdict(set)
    phys_to_routes = {}
    with open(derived / 'logical_queries.tsv') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            phys_id = row['phys_id']
            sample_id = row['sample_id']
            route = row['route']
            phys_to_samples[phys_id].add(sample_id)
            phys_to_routes[phys_id] = route

    # Parse all records
    records = {}  # marc_001 -> record dict
    record_sources = defaultdict(list)  # marc_001 -> list of raw files
    record_conflicts = []  # list of (marc_001, field, values)
    target_record_routes = defaultdict(lambda: defaultdict(set))  # sample_id -> marc_001 -> set of routes

    no_001_count = 0
    parse_error_count = 0

    for req in requests:
        raw_file = raw_root / req['raw_relpath']
        if not raw_file.exists():
            print(f"WARNING: raw file not found: {raw_file}", file=sys.stderr)
            continue

        try:
            tree = ET.parse(raw_file)
            root = tree.getroot()

            # Find all record elements
            for record_elem in root.findall('.//marc:record', NS):
                rec = parse_record(record_elem)
                marc_001 = rec['marc_001']

                if not marc_001:
                    no_001_count += 1
                    continue

                # Track source
                record_sources[marc_001].append(req['raw_relpath'])

                # Check for conflicts
                if marc_001 in records:
                    existing = records[marc_001]
                    for key, val in rec.items():
                        if key != 'marc_001' and existing[key] != val:
                            record_conflicts.append((marc_001, key, existing[key], val))
                else:
                    records[marc_001] = rec

                # Link to targets
                phys_id = req['phys_id']
                route = phys_to_routes.get(phys_id, 'UNKNOWN')
                for sample_id in phys_to_samples[phys_id]:
                    target_record_routes[sample_id][marc_001].add(route)

        except ET.ParseError as e:
            print(f"WARNING: XML parse error in {raw_file}: {e}", file=sys.stderr)
            parse_error_count += 1
            continue

    print(f"Parsed {len(records)} distinct MARC records")
    print(f"  Records without 001: {no_001_count}")
    print(f"  Files with parse errors: {parse_error_count}")
    if record_conflicts:
        print(f"  Content conflicts detected: {len(record_conflicts)} field mismatches across {len(set(c[0] for c in record_conflicts))} records")

    # Write records_parsed.tsv
    fieldnames = ['marc_001', 'leader', 'cf008', 'cf008_date1', 'cf008_language',
                  'f041_a', 'f041_b', 'f041_h',
                  'f245_a', 'f245_b', 'f245_c', 'f246_a', 'f250_a',
                  'f260_a', 'f260_b', 'f260_c', 'f264_a', 'f264_b', 'f264_c',
                  'f100_entries', 'f700_entries', 'f240_a', 'f130_a',
                  'has_f505', 'has_f600_t', 'f015_a', 'f020_a',
                  'f336_a', 'f336_b', 'f337_a', 'f337_b', 'f338_a', 'f338_b',
                  'has_f776', 'source_files']

    with open(derived / 'records_parsed.tsv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t', extrasaction='ignore')
        writer.writeheader()
        for marc_001 in sorted(records.keys()):
            rec = records[marc_001].copy()
            rec['source_files'] = '|'.join(record_sources[marc_001])
            writer.writerow(rec)

    # Write target_record_links.tsv
    with open(derived / 'target_record_links.tsv', 'w', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['sample_id', 'marc_001', 'routes'])
        for sample_id in sorted(target_record_routes.keys()):
            for marc_001 in sorted(target_record_routes[sample_id].keys()):
                routes = '|'.join(sorted(target_record_routes[sample_id][marc_001]))
                writer.writerow([sample_id, marc_001, routes])

    # Compute field_presence.tsv stratified by 008 Date1
    def year_to_era(year_str):
        """Categorize year into era."""
        if not year_str or len(year_str) != 4:
            return 'unknown'
        try:
            year = int(year_str)
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
        except ValueError:
            return 'unknown'

    era_counts = defaultdict(int)
    era_field_presence = defaultdict(lambda: defaultdict(int))

    for rec in records.values():
        era = year_to_era(rec['cf008_date1'])
        era_counts[era] += 1

        # Track field presence
        if rec['f015_a']:
            era_field_presence[era]['f015'] += 1
        if rec['f240_a'] or rec['f130_a']:
            era_field_presence[era]['f240_or_f130'] += 1
        if rec['f246_a']:
            era_field_presence[era]['f246'] += 1
        if rec['f260_a'] or rec['f260_b'] or rec['f260_c']:
            era_field_presence[era]['f260'] += 1
        if rec['f264_a'] or rec['f264_b'] or rec['f264_c']:
            era_field_presence[era]['f264'] += 1
        if rec['has_f600_t'] == 'yes':
            era_field_presence[era]['f600_t'] += 1
        if rec['f700_entries'] and '[has$t]' in rec['f700_entries']:
            era_field_presence[era]['f700_t'] += 1
        if rec['f041_a'] or rec['f041_b'] or rec['f041_h']:
            era_field_presence[era]['f041'] += 1
        if rec['has_f776'] == 'yes':
            era_field_presence[era]['f776'] += 1

    with open(derived / 'field_presence.tsv', 'w', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['era', 'total_records', 'field', 'present_count', 'present_pct'])

        for era in sorted(era_counts.keys()):
            total = era_counts[era]
            for field in ['f015', 'f240_or_f130', 'f246', 'f260', 'f264',
                         'f600_t', 'f700_t', 'f041', 'f776']:
                count = era_field_presence[era][field]
                pct = 100.0 * count / total if total > 0 else 0.0
                writer.writerow([era, total, field, count, f'{pct:.1f}'])

    print(f"\nWrote:")
    print(f"  records_parsed.tsv: {len(records)} rows")
    print(f"  target_record_links.tsv: {sum(len(v) for v in target_record_routes.values())} rows")
    print(f"  field_presence.tsv: {sum(len(era_field_presence[e]) for e in era_counts)} rows")

    return 0


if __name__ == '__main__':
    sys.exit(main())
