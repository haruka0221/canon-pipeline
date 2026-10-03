#!/usr/bin/env python3
"""Create a new, immutable review-input release; never write judgments."""
import argparse
import csv
import hashlib
import json
import platform
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'derived/openalex_production/retrieval_precision_review_candidates_v3/full_profile_57959e90/openalex_retrieval_precision_review_candidates_v3.tsv'
SOURCE_SHA256 = '38dda4e170ff8f1f90101f0246edc627401666f24dac5d588336f429194483fa'
DEVELOPMENT_SHA256 = '0040da4263e8e5fcc26e44bab0471f0cf2575e34ded628d5ee2736fba2888b30'
DEFAULT_OUTPUT = ROOT / 'derived/openalex_production/precision_review_view_v1/full_profile_57959e90'
DEFAULT_DEVELOPMENT = ROOT / 'derived/openalex_production/precision_review_development_inputs_v1/openalex_precision_review_development_inputs_v1.tsv'
PROTOCOL = ROOT / 'docs/OPENALEX_PRECISION_REVIEW_PROTOCOL_V1.md'
SCHEMA = ROOT / 'derived/openalex_production/precision_review_protocol_v1/openalex_precision_review_judgment_schema_v1.json'
SEMANTIC_KEY = ['increment_type', 'project_work_id', 'title_match_norms', 'author_a1_norms', 'author_a2_reverse_norms']
RAW_KEY = ['increment_type', 'project_work_id', 'r3_query_titles', 'r3_query_authors']
SOURCE_COLUMNS = 'project_work_id openalex_work_id increment_type review_candidate_id r3_evidence_rows r3_query_ids r3_execution_ids r3_alias_ids r3_query_titles r3_query_authors title_match_norms author_a1_norms author_a2_reverse_norms any_title_match_in_title any_title_match_in_abstract any_author_a1_hit any_author_a2_reverse_hit r2_baseline_titles r2_baseline_authors openalex_id_url snapshot_source_file display_name abstract publication_year publication_date type language doi is_retracted is_paratext has_fulltext primary_topic_id primary_topic_name'.split()
AID_COLUMNS = 'review_semantic_group_id title_token_count title_token_bucket hit_location abstract_available provenance_multiplicity semantic_group_candidate_count semantic_group_volume_bucket'.split()
DEVELOPMENT_COLUMNS = 'review_candidate_id increment_type project_work_id openalex_work_id r2_baseline_titles r2_baseline_authors r3_query_titles r3_query_authors title_match_norms author_a1_norms author_a2_reverse_norms r3_evidence_rows r3_query_ids r3_execution_ids r3_alias_ids any_title_match_in_title any_title_match_in_abstract any_author_a1_hit any_author_a2_reverse_hit display_name abstract publication_year type language primary_topic_name title_token_count title_token_bucket hit_location abstract_available provenance_multiplicity semantic_group_candidate_count semantic_group_volume_bucket'.split()
EXPECTED_COUNTS = {'ALIAS_EXPANSION': 409, 'A2_AUTHOR_REVERSAL': 252}
EXPECTED_MISSING = dict.fromkeys(SOURCE_COLUMNS, 0)
EXPECTED_MISSING.update(author_a2_reverse_norms=408, display_name=3, abstract=73, publication_year=17, publication_date=17, language=8, doi=221, primary_topic_id=53, primary_topic_name=53)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_tsv(path):
    with Path(path).open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t', strict=True)
        rows = list(reader)
        require(reader.fieldnames is not None, 'Missing TSV header')
        require(len(reader.fieldnames) == len(set(reader.fieldnames)), 'Duplicate columns')
        require(all(None not in r and all(v is not None for v in r.values()) for r in rows), 'Malformed TSV width')
        return reader.fieldnames, rows


def canonical_key(row):
    # JSON object, exact strings, no Unicode normalization, no delimiter splitting.
    return json.dumps({c: row[c] for c in SEMANTIC_KEY}, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def semantic_group_id(row):
    return 'OAPRSG1_' + hashlib.sha256(canonical_key(row).encode('utf-8')).hexdigest()[:16]


def partition(rows, columns):
    groups = defaultdict(set)
    for row in rows:
        groups[tuple(row[c] for c in columns)].add(row['review_candidate_id'])
    return {frozenset(ids) for ids in groups.values()}


def missingness(rows, columns):
    return {c: sum(not r[c].strip() for r in rows) for c in columns}


def derive(rows):
    sizes = Counter(semantic_group_id(r) for r in rows)
    id_keys = defaultdict(set)
    out = []
    for row in rows:
        group = semantic_group_id(row)
        id_keys[group].add(canonical_key(row))
        require(' || ' not in row['title_match_norms'], 'Multiple normalized title predicates need a new token-count policy')
        tokens = len(row['title_match_norms'].split())
        require(tokens > 0, 'Empty normalized title')
        flags = [row[c] for c in ['any_title_match_in_title', 'any_title_match_in_abstract']]
        require(all(v in {'True', 'False'} for v in flags), 'Unexpected source match boolean')
        title, abstract = (v == 'True' for v in flags)
        evidence = int(row['r3_evidence_rows'])
        require(evidence >= 1, 'Nonpositive provenance count')
        size = sizes[group]
        out.append({**row, 'review_semantic_group_id': group,
                    'title_token_count': str(tokens),
                    'title_token_bucket': str(tokens) if tokens < 3 else '3+',
                    'hit_location': 'TITLE_AND_ABSTRACT' if title and abstract else 'TITLE_ONLY' if title else 'ABSTRACT_ONLY' if abstract else 'NEITHER',
                    'abstract_available': str(bool(row['abstract'].strip())),
                    'provenance_multiplicity': 'SINGLE' if evidence == 1 else 'MULTIPLE',
                    'semantic_group_candidate_count': str(size),
                    'semantic_group_volume_bucket': 'SMALL' if size <= 2 else 'MEDIUM' if size <= 20 else 'LARGE'})
    require(all(len(keys) == 1 for keys in id_keys.values()), 'Truncated digest collision')
    return out, sizes


def check_source(path=SOURCE):
    require(sha256(path) == SOURCE_SHA256, 'Frozen source SHA256 mismatch')
    columns, rows = read_tsv(path)
    require(columns == SOURCE_COLUMNS, 'Source columns/order differ')
    require(len(rows) == 661, 'Expected 661 parsed candidate records')
    require(len({r['review_candidate_id'] for r in rows}) == 661, 'Duplicate candidate IDs')
    require(len({(r['project_work_id'], r['openalex_work_id']) for r in rows}) == 661, 'Duplicate W x OA pair')
    require(Counter(r['increment_type'] for r in rows) == EXPECTED_COUNTS, 'Increment counts differ')
    require(len({r['project_work_id'] for r in rows}) == 65, 'Release W count differs')
    require(missingness(rows, columns) == EXPECTED_MISSING, 'Expected missingness differs')
    require(partition(rows, RAW_KEY) == partition(rows, SEMANTIC_KEY), 'Raw and normalized partitions differ')
    return columns, rows


def check_development(path, view):
    require(sha256(path) == DEVELOPMENT_SHA256, 'Development input SHA256 mismatch')
    columns, rows = read_tsv(path)
    require(columns == DEVELOPMENT_COLUMNS, 'Development input columns differ')
    require(len(rows) == 24 and len({r['review_candidate_id'] for r in rows}) == 24, 'Expected 24 unique development candidates')
    require(Counter(r['increment_type'] for r in rows) == {'ALIAS_EXPANSION': 12, 'A2_AUTHOR_REVERSAL': 12}, 'Development mechanism counts differ')
    lookup = {r['review_candidate_id']: r for r in view}
    for row in rows:
        require(row['review_candidate_id'] in lookup, 'Development ID outside frozen universe')
        require(all(row[c] == lookup[row['review_candidate_id']][c] for c in columns), 'Development inputs/aids differ from source derivation')
    for mechanism in EXPECTED_COUNTS:
        counts = Counter(r['project_work_id'] for r in rows if r['increment_type'] == mechanism)
        require(len(counts) >= 8 and max(counts.values()) <= 2, 'Development W diversity/cap differs')
    require(sum(r['project_work_id'] == 'W000012843' and r['increment_type'] == 'A2_AUTHOR_REVERSAL' for r in rows) <= 2, 'In Parenthesis development cap exceeded')
    return rows


def write_tsv(path, columns, rows):
    with path.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, data):
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--development-input', type=Path, default=DEFAULT_DEVELOPMENT)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    require(not output.exists(), 'Output directory already exists; use a new release path')
    # Finish input validation before creating any output.
    columns, source = check_source()
    view, sizes = derive(source)
    require(len(sizes) == 65, 'Expected 65 release-specific semantic groups')
    require(all(r['hit_location'] != 'NEITHER' for r in view), 'Unexpected NEITHER hit')
    development = check_development(args.development_input, view)
    require(PROTOCOL.is_file() and SCHEMA.is_file(), 'Protocol/schema missing')
    import pyarrow as pa
    import pyarrow.parquet as pq
    builder_hash = sha256(Path(__file__))
    dependencies = {str(p.relative_to(ROOT)): sha256(p) for p in [SOURCE, PROTOCOL, SCHEMA]}
    # Path-independent manifest input name; hash binds exact development bytes.
    dependencies['openalex_precision_review_development_inputs_v1.tsv'] = DEVELOPMENT_SHA256
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    git_state = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).splitlines()
    output.mkdir(parents=True, exist_ok=False)
    stem = 'openalex_precision_review_view_v1'
    tsv = output / (stem + '.tsv')
    parquet = output / (stem + '.parquet')
    manifest_path = output / (stem + '_manifest.json')
    audit_path = output / (stem + '_audit_v1.json')
    all_columns = columns + AID_COLUMNS
    write_tsv(tsv, all_columns, view)
    # All source values remain strings, including blank cells and year lexemes.
    # Aids also remain strings to give exact cell-level TSV/Parquet parity.
    table = pa.Table.from_pylist(view, schema=pa.schema([(c, pa.string()) for c in all_columns]))
    pq.write_table(table, parquet, compression='zstd', version='2.6')
    tcols, trows = read_tsv(tsv)
    prows = pq.read_table(parquet).to_pylist()
    require(tcols == all_columns and trows == view == prows, 'TSV/Parquet parity failed')
    require([{c: r[c] for c in columns} for r in trows] == source, 'Source values/order changed')
    require(missingness(trows, columns) == EXPECTED_MISSING, 'Missingness changed')
    require(sha256(SOURCE) == SOURCE_SHA256, 'Frozen source changed during build')
    group_distribution = dict(sorted(Counter(sizes.values()).items()))
    development_counts = {'rows': len(development), 'by_increment_type': dict(Counter(r['increment_type'] for r in development)), 'distinct_W_by_increment_type': {m: len({r['project_work_id'] for r in development if r['increment_type'] == m}) for m in EXPECTED_COUNTS}}
    manifest = {'release': 'openalex-precision-review-view-v1', 'review_protocol_version': 'v1',
                'status': 'implemented_uncommitted_not_adjudicated', 'inputs': dependencies,
                'builder': {'path': str(Path(__file__).relative_to(ROOT)), 'sha256': builder_hash, 'git_head': head, 'git_status_porcelain': git_state, 'python_version': platform.python_version(), 'pyarrow_version': pa.__version__},
                'counts': {'rows': len(view), 'columns': len(all_columns), 'original_columns': len(columns), 'increment_type': EXPECTED_COUNTS, 'semantic_groups': len(sizes), 'semantic_group_size_distribution': group_distribution},
                'development_input_counts': development_counts,
                'semantic_group': {'key_fields': SEMANTIC_KEY, 'serialization': 'UTF-8 JSON object; exact source strings; ensure_ascii=False, sort_keys=True, separators=(comma,colon), allow_nan=False', 'id': 'OAPRSG1_ + first 16 lowercase hex characters of SHA256(serialized key)', 'group_is_not_W': True},
                'columns': all_columns, 'parquet_cell_types': 'all UTF-8 strings; no null coercion',
                'outputs': {p.name: sha256(p) for p in [tsv, parquet]},
                'interpretation': 'Review inputs only; no judgments. Evaluates R3 alias and A2 reversal marginal target-attribution precision only. No R2 absolute precision or R4 precision inference.'}
    write_json(manifest_path, manifest)
    audit = {'audit_release': 'openalex-precision-review-view-v1-audit-v1', 'audit_status': 'PASSED',
             'checks': dict.fromkeys(['source_tsv_sha256', '661_parsed_records', '33_original_columns_exact_order', 'source_values_unchanged', 'unique_candidate_ids', 'unique_W_OA_pairs', 'candidate_id_set_exact', 'W_OA_pair_set_exact', '409_alias_expansion', '252_a2_reversal', '65_release_specific_semantic_groups', 'semantic_id_digest_collision_free', 'raw_normalized_partition_equivalent', 'zero_NEITHER', 'expected_missingness_preserved', 'tsv_parquet_cell_parity', 'output_hashes_match_manifest', 'development_input_hash_exact', 'development_inputs_match_frozen_candidates_and_aids', 'frozen_source_unchanged'], True),
             'source_columns': columns, 'source_missingness': EXPECTED_MISSING,
             'counts': manifest['counts'], 'development_input_counts': development_counts,
             'hit_location_counts': dict(Counter(r['hit_location'] for r in view)),
             'artifacts': {p.name: {'sha256': sha256(p), 'bytes': p.stat().st_size} for p in [tsv, parquet, manifest_path]},
             'builder_sha256': builder_hash,
             'interpretation': 'Build-integrated artifact audit; not an independent human audit or relevance adjudication.'}
    require(all(sha256(output / name) == digest for name, digest in manifest['outputs'].items()), 'Output hash mismatch')
    require(sha256(SOURCE) == SOURCE_SHA256, 'Frozen source changed before audit')
    write_json(audit_path, audit)
    print(json.dumps({'audit_status': 'PASSED', 'counts': manifest['counts'], 'development_input_counts': development_counts, 'hashes': {p.name: sha256(p) for p in [tsv, parquet, manifest_path, audit_path]}}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
