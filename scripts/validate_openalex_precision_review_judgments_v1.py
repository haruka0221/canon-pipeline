#!/usr/bin/env python3
"""Read-only validator for a future final judgment release; creates no data."""
import argparse
import datetime
import json
import re
from pathlib import Path

from build_openalex_precision_review_view_v1 import (
    SCHEMA, check_source, read_tsv, require, semantic_group_id,
)


def validate_rows(columns, rows, source):
    schema = json.loads(SCHEMA.read_text(encoding='utf-8'))
    require(columns == schema['x-table-column-order'], 'Judgment columns/order differ')
    require(len(rows) == 661, 'Final release must contain exactly 661 rows')
    ids = [r['review_candidate_id'] for r in rows]
    require(len(set(ids)) == 661, 'Duplicate judgment candidate IDs')
    expected = {r['review_candidate_id']: r for r in source}
    require(set(ids) == set(expected), 'Candidate ID set differs from source')
    require({(r['project_work_id'], r['openalex_work_id']) for r in rows} ==
            {(r['project_work_id'], r['openalex_work_id']) for r in source},
            'W x OA pair set differs from source')
    props = schema['items']['properties']
    boolean_fields = [c for c, p in props.items() if p.get('type') == 'boolean']
    reason_map = {rule['if']['properties']['target_attribution_judgment']['const']:
                  rule['then']['properties']['attribution_reason_code']['enum']
                  for rule in schema['items']['allOf']
                  if 'target_attribution_judgment' in rule['if']['properties']}
    for row in rows:
        require(set(row) == set(columns), 'Malformed judgment row fields')
        candidate = expected[row['review_candidate_id']]
        for c in ['project_work_id', 'openalex_work_id', 'increment_type']:
            require(row[c] == candidate[c], 'Per-candidate identity/mechanism mapping differs')
        require(row['review_semantic_group_id'] == semantic_group_id(candidate), 'Semantic group ID differs')
        for c in columns:
            value = row[c]
            p = props[c]
            require(isinstance(value, str), 'TSV cells must be strings')
            if c in boolean_fields:
                require(value in {'True', 'False'}, 'Boolean must be True or False')
            if 'enum' in p:
                require(value in p['enum'], 'Unknown controlled vocabulary: ' + c)
            if 'const' in p:
                require(value == p['const'], 'Unexpected fixed version: ' + c)
            if 'pattern' in p:
                require(re.search(p['pattern'], value) is not None, 'Pattern/nonblank constraint: ' + c)
        require(row['attribution_reason_code'] in reason_map[row['target_attribution_judgment']], 'Incompatible judgment/reason')
        external = row['evidence_used_external_check'] == 'True'
        for c in ['external_check_reference', 'external_check_note']:
            require(bool(row[c].strip()) if external else row[c] == '', 'External-check reference/note constraint')
        require(row['attribution_reason_code'] != 'OTHER' or bool(row['reviewer_note'].strip()), 'OTHER requires reviewer_note')
        stamp = datetime.datetime.fromisoformat(row['adjudicated_at_utc'].replace('Z', '+00:00'))
        require(stamp.utcoffset() == datetime.timedelta(0), 'Adjudication timestamp must be UTC')
    return {'audit_status': 'PASSED', 'rows': len(rows), 'unique_candidate_ids': len(set(ids)),
            'exact_candidate_id_and_pair_sets': True, 'per_candidate_mapping_and_semantic_groups': True,
            'controlled_vocabularies_and_reason_compatibility': True,
            'protocol_version_v1': True, 'external_evidence_requirements': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('judgment_tsv', type=Path)
    args = parser.parse_args()
    _, source = check_source()
    columns, rows = read_tsv(args.judgment_tsv)
    print(json.dumps(validate_rows(columns, rows, source), sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
