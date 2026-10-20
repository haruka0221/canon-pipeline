#!/usr/bin/env python3
"""Exploratory OL Edition evidence-mechanism audit, v4 (non-adjudicative).

Run from the canon-pipeline repository root:
    python scripts/build_held_one_work_refined_evidence_v4.py --self-test
    python scripts/build_held_one_work_refined_evidence_v4.py

Uses immutable v1/v2/v3 artifacts. Does not access live APIs or the raw dump.
Creates a NEW output directory only. Does not change old tiers, evaluation,
researcher labels, Project W, git index, or any earlier input file.

Rules were developed AFTER prior held-out and exploratory examples were seen.
They are NOT validated predictions of conceptual work identity.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import tempfile
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path.cwd()
BASE = ROOT / 'derived/identity'
V1 = BASE / 'aggregation_held_one_work_bibliographic_screen_v1'
V2 = BASE / 'aggregation_held_one_work_raw_edition_enrichment_v2'
V3 = BASE / 'aggregation_held_one_work_research_triage_v3'
OUT = BASE / 'aggregation_held_one_work_refined_evidence_v4'
FROZEN = BASE / 'aggregation_held_heldout_human_review_draft_v1/heldout_researcher_review_frozen_v1.tsv'

EXPECTED_SHA = {
    V1 / 'unit_screen_v1.tsv': '560f50be62cddb3dbf7b8b5c76f6ee054d36d1df8a587c2fbb840c5645232cc5',
    V1 / 'work_screen_v1.tsv': '5b9591d1869aaa8fe01cbf380184ef5387792b331102132a63cfc0250de91f2a',
    V1 / 'edition_evidence_v1.tsv': '40ea3d224b7dc6195c65e9cafc0db372794b5619ef1f4b65ea0f0d55049e69d7',
    V1 / 'manifest_v1.json': '10505c674b2949515e54ac56d582bb0aa00ccfa4136b4ca3e1e6496ff655f174',
    V2 / 'unit_raw_metadata_screen_v2.tsv': 'd74089b713c59ea50db673c8f6c8b4929d86365a628a4a109301015ea89abc70',
    V2 / 'raw_edition_enrichment_v2.tsv': '3dcdea64a24b1dc7020bea64131be8a8bc810d2921246b4c0cdf8ce50ef862f4',
    V2 / 'manifest_v2.json': '6f25f6ea7a9219d3ca405e4fe772c8258373346b2d46b28ccb3b3fccd0a080ba',
    V3 / 'research_queue_v3.tsv': '091b69d464e63f64f6a5fa48df1ca92d9e80537d03b8654818cd9b3cf5fc2d6e',
    V3 / 'review_evidence_examples_v3.tsv': 'c502828fa094f61c73d19bc04a98dfef65ce9a9fc41bf5a9b887f9fb180f85ca',
    V3 / 'manifest_v3.json': '41e7b5730e7a8baba794863fa59aa08a4b7ea529d35f68f6cc69c23dd1760b7f',
    FROZEN: '9b9dea1b7ec54710affab9b739797de0dc5d01b7f8d9049d9e723a2962a91c8d',
}
SNAPSHOT = 'OL_EDITIONS_2026-02-28'
MULTI = re.compile(r'(?<!\d)(\d{1,5})\s*[,;]\s*(\d{1,5})(?!\d)')
ARABIC = re.compile(r'(?<![\w])\d{1,5}(?!\w)')
NUMERIC_RANGE = re.compile(r'\d\s*[-–]\s*\d')
ADVERTS = re.compile(r'\b(?:advertisements?|advertis(?:e|ing)|catalogue|catalog)\b', re.I)
SLIPCASE_WITH = re.compile(r'\bslip\s*case\s+with\s*:', re.I)
BOUND_WITH = re.compile(r'\bbound\s+with\b', re.I)
EXPLICIT_WITH = re.compile(r'\bwith\s*:', re.I)
TEXT_PLUS_CRIT = re.compile(r'\bcontains\s+the\s+text\b.{0,100}\bplus\b|\bnew\s+interpretations\b', re.I | re.S)
COLLECTION_NOTE = re.compile(r'\b(?:anthology|omnibus|collected\s+(?:stories|works)|other\s+(?:tales|stories)|dramati[sz]ation|adapted\s+for\s+the\s+stage)\b', re.I)
EDITORIAL_SUBTITLE = re.compile(r'\b(?:translated\s+by|translation\s+of|illustrated\s+by|edited\s+by|with\s+notes|intro(?:d\.|duction)|vocabulary|questionnaire|backgrounds\s+and\s+contexts|criticism)\b', re.I)
GENERIC_SUBTITLE = re.compile(r'^(?:a\s+)?(?:novel|story|romance|play|drama|tale|narrative)\.?$', re.I)
VOLUME_TITLE = re.compile(r'^\s*(?:v\.|vol\.?|volume)\s*(?:\d+|[ivxlcdm]+)\b', re.I)
ARCHIVAL_TITLE = re.compile(r'\b(?:holograph|typescript|manuscript|setting\s+copy|rejected\s+pages|publisher.s\s+front\s+matter)\b', re.I)
OTHER_STORIES_TITLE = re.compile(r'\b(?:other\s+(?:stories|tales|dogs|men)|collected\s+(?:stories|tales)|selected\s+(?:stories|tales)|anthology)\b', re.I)
TIER_ORDER = {'F1_CONTENT_BOUNDARY': 1, 'F2_PUBLICATION_CONTEXT': 2,
              'F3_AMBIGUOUS_METADATA': 3, 'F4_NO_DEFINED_PROMPT': 4}
MAX_EXAMPLES_PER_MECHANISM = 4


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f, delimiter='\t'))


def jd(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def decode(value: str):
    return json.loads(value)


def txt(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get('value'), str):
        return value['value']
    return ''


def compact(value, limit=370) -> str:
    if isinstance(value, list):
        value = ' | '.join(txt(x) if txt(x) else str(x.get('title', x) if isinstance(x, dict) else x)
                           for x in value[:8])
    value = re.sub(r'\s+', ' ', txt(value) if txt(value) else str(value or '')).strip()
    return value[:limit]


def norm_title(value: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())


def toc_titles(value):
    if not isinstance(value, list):
        return []
    titles = []
    for item in value:
        if isinstance(item, dict) and isinstance(item.get('title'), str):
            if item['title'].strip():
                titles.append(item['title'].strip())
        elif isinstance(item, str) and item.strip():
            titles.append(item.strip())
    return titles


def inspect_edition(raw: dict[str, str], v1: dict[str, str], unit_titles: list[str]) -> tuple[list[str], dict[str, str]]:
    """Detect descriptive mechanisms, never assign work identity."""
    flags: set[str] = set()
    excerpts: dict[str, str] = {}
    pagination = txt(decode(raw['pagination_json']))
    notes = txt(decode(raw['notes_json']))
    subtitle = txt(decode(raw['subtitle_json']))
    toc = toc_titles(decode(raw['table_of_contents_json']))
    edition_title = raw['raw_title'] or v1['edition_title']

    def flag(name: str, excerpt: str):
        flags.add(name)
        excerpts[name] = compact(excerpt)

    multi = list(MULTI.finditer(pagination))
    if multi:
        numbers = [int(x) for x in ARABIC.findall(pagination)]
        # Explicitly mentioned advertising outweighs ambiguous numeric segments.
        if ADVERTS.search(pagination) or ADVERTS.search(notes):
            flag('PAGINATION_ADVERTISING_MATERIAL_MENTIONED',
                 'pagination=' + pagination + '; notes=' + notes)
        elif len(numbers) == 2 and not NUMERIC_RANGE.search(pagination):
            x, y = int(multi[0].group(1)), int(multi[0].group(2))
            if x >= 50 and y >= 50:
                flag('PAGINATION_TWO_SUBSTANTIVE_SEGMENTS_POSSIBLE', pagination)
            elif x <= 20 and y >= 70:
                flag('PAGINATION_SHORT_LEAD_SEGMENT_UNSPECIFIED', pagination)
            else:
                flag('PAGINATION_OTHER_TWO_SEGMENTS_UNSPECIFIED', pagination)
        else:
            flag('PAGINATION_COMPLEX_NUMERIC_SEGMENTS_UNSPECIFIED', pagination)

    if SLIPCASE_WITH.search(notes):
        flag('NOTE_SLIPCASE_SEPARATELY_ISSUED_BOOK', notes)
    if BOUND_WITH.search(notes):
        flag('NOTE_BOUND_WITH_PUBLICATION_STATUS_UNKNOWN', notes)
    if EXPLICIT_WITH.search(notes) and not SLIPCASE_WITH.search(notes) and not BOUND_WITH.search(notes):
        flag('NOTE_WITH_REFERENCE_UNSPECIFIED', notes)
    if TEXT_PLUS_CRIT.search(notes):
        flag('NOTE_TEXT_PLUS_INTERPRETATION', notes)
    if COLLECTION_NOTE.search(notes):
        flag('NOTE_COLLECTION_OR_ADAPTATION_TERM', notes)

    if subtitle.strip():
        same_titles = {norm_title(t) for t in unit_titles + [edition_title] if t}
        if norm_title(subtitle) in same_titles:
            flag('SUBTITLE_REPEATS_KNOWN_TITLE', subtitle)
        elif GENERIC_SUBTITLE.fullmatch(subtitle.strip()):
            flag('SUBTITLE_GENERIC_FORM_WORDING', subtitle)
        elif EDITORIAL_SUBTITLE.search(subtitle):
            flag('SUBTITLE_EDITORIAL_OR_TRANSLATION_WORDING', subtitle)
        elif len([x for x in subtitle.split(':') if len(x.strip()) >= 6]) >= 3:
            flag('SUBTITLE_MULTIPLE_TITLED_SEGMENTS_CANDIDATE', subtitle)
        else:
            flag('SUBTITLE_UNRESOLVED_DISTINCT_TEXT', subtitle)

    if 'PAGINATION_TWO_SUBSTANTIVE_SEGMENTS_POSSIBLE' in flags and 'SUBTITLE_UNRESOLVED_DISTINCT_TEXT' in flags:
        flag('PAGINATION_AND_DISTINCT_SUBTITLE_CO_OCCUR',
             'pagination=' + pagination + '; subtitle=' + subtitle)

    if toc:
        if len(toc) >= 3:
            flag('CONTENTS_MULTIPLE_TITLED_ENTRIES', ' | '.join(toc[:8]))
        if any(VOLUME_TITLE.search(t) for t in toc):
            flag('CONTENTS_VOLUME_ENTRIES', ' | '.join(toc[:8]))
        if any(ARCHIVAL_TITLE.search(t) for t in toc):
            flag('CONTENTS_ARCHIVAL_MATERIAL', ' | '.join(toc[:8]))
        # Evidence of possible scope difference, not proof of distinct work IDs.
        if (len(toc) >= 3 and OTHER_STORIES_TITLE.search(edition_title)
                and not any(ARCHIVAL_TITLE.search(t) for t in toc)):
            flag('CONTENTS_AND_COLLECTION_TITLE_CO_OCCUR',
                 'edition_title=' + edition_title + '; contents=' + ' | '.join(toc[:7]))

    return sorted(flags), excerpts


def focus_tier(signals: set[str], v1: set[str], v2: set[str]) -> tuple[str, list[str]]:
    reasons = sorted(signals & {
        'SUBTITLE_MULTIPLE_TITLED_SEGMENTS_CANDIDATE',
        'PAGINATION_AND_DISTINCT_SUBTITLE_CO_OCCUR',
        'CONTENTS_AND_COLLECTION_TITLE_CO_OCCUR',
    })
    if reasons:
        return 'F1_CONTENT_BOUNDARY', reasons
    reasons = sorted(signals & {
        'NOTE_BOUND_WITH_PUBLICATION_STATUS_UNKNOWN',
        'NOTE_SLIPCASE_SEPARATELY_ISSUED_BOOK',
        'NOTE_TEXT_PLUS_INTERPRETATION',
        'NOTE_COLLECTION_OR_ADAPTATION_TERM',
        'CONTENTS_ARCHIVAL_MATERIAL',
        'CONTENTS_VOLUME_ENTRIES',
    })
    if reasons:
        return 'F2_PUBLICATION_CONTEXT', reasons
    if signals or v1 or v2:
        return 'F3_AMBIGUOUS_METADATA', ['GENERAL_OR_UNRESOLVED_METADATA_PROMPT']
    return 'F4_NO_DEFINED_PROMPT', ['NO_DEFINED_SIGNAL_NOT_A_SAFETY_FINDING']


def save_tsv(path, rows: list[dict[str, str]]) -> None:
    assert rows, f'No rows for {path}'
    with path.open('x', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def self_test() -> None:
    def specimen(title, subtitle='', pagination='', notes='', contents=None, work_titles=None):
        raw = {'raw_title': title, 'pagination_json': jd(pagination),
               'subtitle_json': jd(subtitle), 'notes_json': jd(notes),
               'table_of_contents_json': jd(contents)}
        v1 = {'edition_title': title}
        found, _ = inspect_edition(raw, v1, work_titles or [title])
        return set(found)

    case12 = specimen("The regent's daughter", 'The black tulip', '319, 253 pages')
    assert 'PAGINATION_AND_DISTINCT_SUBTITLE_CO_OCCUR' in case12
    assert focus_tier(case12, set(), set())[0] == 'F1_CONTENT_BOUNDARY'
    advertisements = specimen('"Ninety-three"', 'Quatrevingt-treize',
                              '187, 4 p. (4 p. at end advertisements)')
    assert 'PAGINATION_ADVERTISING_MATERIAL_MENTIONED' in advertisements
    assert 'PAGINATION_AND_DISTINCT_SUBTITLE_CO_OCCUR' not in advertisements
    cake = specimen('Xun huan zuo le', 'Cakes and ale', '8, 272 p. ;',
                    work_titles=['Cakes and ale', 'Cakes and ale, or, The skeleton in the cupboard'])
    assert 'SUBTITLE_REPEATS_KNOWN_TITLE' in cake
    assert 'PAGINATION_SHORT_LEAD_SEGMENT_UNSPECIFIED' in cake
    peg_advert = specimen('Peg Woffington', 'a novel', '255, 32 p.',
                          'Includes advertisements; those at end dated: March, 1884.')
    assert 'PAGINATION_ADVERTISING_MATERIAL_MENTIONED' in peg_advert
    peg_list = specimen('Peg Woffington',
        "The Knightsbridge mystery : The kindly jest : An old bachelor's adventure : A stroke of business : and What has become of Lord Camelford's body?")
    assert 'SUBTITLE_MULTIPLE_TITLED_SEGMENTS_CANDIDATE' in peg_list
    slipcase = specimen('The war of the worlds', notes='Issued in a slipcase with: The time machine / H.G. Wells.')
    assert focus_tier(slipcase, set(), set())[0] == 'F2_PUBLICATION_CONTEXT'
    bound = specimen('For my great folly', notes="Bound with the author's The moneyman, New York, 1947")
    assert focus_tier(bound, set(), set())[0] == 'F2_PUBLICATION_CONTEXT'
    rab = specimen('Rab and his friends and other dogs and men', contents=[
        {'title': 'Rab and his friends'}, {'title': 'Our dogs'}, {'title': 'More of our dogs'},
        {'title': 'Marjorie Fleming'},
    ])
    assert focus_tier(rab, {'COLLECTION_TITLE_WORDING'}, set())[0] == 'F1_CONTENT_BOUNDARY'
    wild = specimen('The wild palms', contents=[
        {'title': 'v. 1. Holograph manuscript and miscellaneous rejected holograph pages'},
        {'title': 'v. 2. Publisher front matter and typescript setting copy'},
    ])
    assert 'CONTENTS_ARCHIVAL_MATERIAL' in wild
    assert focus_tier(wild, {'COLLECTION_TITLE_WORDING'}, set())[0] == 'F2_PUBLICATION_CONTEXT'
    print('SELF-TEST PASSED: 8 synthetic bibliographic mechanisms, no files written')


def main() -> None:
    assert not OUT.exists(), f'STOP: refusing to overwrite existing release {OUT}'
    for path, digest in EXPECTED_SHA.items():
        assert path.is_file() and sha(path) == digest, f'STOP: missing/changed input {path}'

    u1 = load_tsv(V1 / 'unit_screen_v1.tsv')
    w1 = load_tsv(V1 / 'work_screen_v1.tsv')
    e1 = load_tsv(V1 / 'edition_evidence_v1.tsv')
    e2 = load_tsv(V2 / 'raw_edition_enrichment_v2.tsv')
    u3 = load_tsv(V3 / 'research_queue_v3.tsv')
    assert (len(u1), len(w1), len(e1), len(e2), len(u3)) == (438, 1249, 40305, 40305, 438)
    unit1 = {x['unit_anchor_entity_id']: x for x in u1}
    old3 = {x['unit_anchor_entity_id']: x for x in u3}
    work_titles = defaultdict(list)
    for w in w1:
        work_titles[w['unit_anchor_entity_id']].append(w['work_title'])
    assert len(unit1) == len(old3) == len(work_titles) == 438
    assert set(unit1) == set(old3) == set(work_titles)

    lookup1 = {x['edition_key']: x for x in e1}
    lookup2 = {x['edition_key']: x for x in e2}
    assert len(lookup1) == len(lookup2) == 40305 and set(lookup1) == set(lookup2)
    unit_signals = defaultdict(set)
    unit_edition_count = Counter()
    unit_mechanism_editions = defaultdict(lambda: defaultdict(list))
    edition_rows = []
    mechanisms_by_edition = Counter()

    for eid in sorted(lookup1):
        a, b = lookup1[eid], lookup2[eid]
        anchor = a['unit_anchor_entity_id']
        assert anchor in unit1 and anchor == b['unit_anchor_entity_id'], eid
        assert a['current_ol_work_id'] == b['current_ol_work_id'], eid
        assert a['source_snapshot'] == b['source_snapshot'] == SNAPSHOT, eid
        unit_edition_count[anchor] += 1
        old_signals = set(decode(unit1[anchor]['signals_json']))
        markers, excerpts = inspect_edition(b, a, work_titles[anchor])
        unit_signals[anchor].update(markers)
        mechanisms_by_edition.update(markers)
        for m in markers:
            unit_mechanism_editions[anchor][m].append((eid, a['current_ol_work_id'], excerpts[m]))
        edition_rows.append({
            'unit_anchor_entity_id': anchor,
            'current_ol_work_id': a['current_ol_work_id'],
            'edition_key': eid,
            'edition_title': compact(b['raw_title'] or a['edition_title'], 220),
            'mechanisms_json': jd(markers),
            'mechanism_evidence_excerpt_json': jd(excerpts),
            'v2_original_prompts_json': b['bibliographic_review_prompts_json'],
            'source_records_example_json': jd(decode(b['source_records_json'])[:4]
                     if isinstance(decode(b['source_records_json']), list) else []),
            'source_snapshot': SNAPSHOT,
            'interpretation': 'DESCRIPTIVE_ONLY_NOT_WORK_IDENTITY',
        })

    unit_rows = []
    evidence_rows = []
    tier_counts = Counter()
    transitions = Counter()
    unit_mechanism_counts = Counter()
    for anchor in sorted(unit1):
        original = unit1[anchor]
        prior = old3[anchor]
        assert unit_edition_count[anchor] == int(original['edition_link_count'])
        s = unit_signals[anchor]
        for mechanism in s:
            unit_mechanism_counts[mechanism] += 1
        old_s = set(decode(original['signals_json']))
        v2_s = set(decode(prior['v2_review_prompts_json']))
        focus, reasons = focus_tier(s, old_s, v2_s)
        tier_counts[focus] += 1
        transitions[(prior['triage_tier'], focus)] += 1
        examples = {}
        for mechanism in sorted(unit_mechanism_editions[anchor]):
            values = sorted(unit_mechanism_editions[anchor][mechanism])
            sample = values[:MAX_EXAMPLES_PER_MECHANISM]
            examples[mechanism] = [eid for eid, _, _ in sample]
            for eid, work, excerpt in sample:
                evidence_rows.append({
                    'unit_anchor_entity_id': anchor,
                    'v4_focus_group': focus,
                    'mechanism': mechanism,
                    'edition_key': eid,
                    'current_ol_work_id': work,
                    'evidence_excerpt_truncated': excerpt,
                    'interpretation': 'REVIEW_ORIGINAL_SOURCE_NO_IDENTITY_CLAIM',
                })
        unit_rows.append({
            'unit_anchor_entity_id': anchor,
            'v4_focus_group': focus,
            'v4_focus_reasons_json': jd(reasons),
            'v3_original_tier': prior['triage_tier'],
            'historical_sampling_stratum': original['historical_sampling_stratum'],
            'ol_work_count': original['ol_work_count'],
            'edition_link_count': str(unit_edition_count[anchor]),
            'v1_original_signals_json': original['signals_json'],
            'v2_original_prompts_json': prior['v2_review_prompts_json'],
            'v4_mechanisms_json': jd(sorted(s)),
            'v4_example_edition_ids_json': jd(examples),
            'interpretation': 'RESEARCH_QUEUE_ONLY_NO_AUTO_MERGE_OR_SPLIT',
        })

    assert sum(tier_counts.values()) == 438
    assert sum(transitions.values()) == 438
    assert len(edition_rows) == 40305
    assert len(evidence_rows) > 0
    # Diagnostic consistency of examples known before these rules were written;
    # these checks are NOT an independent holdout or precision evaluation.
    assert 'PAGINATION_AND_DISTINCT_SUBTITLE_CO_OCCUR' in unit_signals['E000019492']
    assert any(row['edition_key'] == '/books/OL52630896M' and
               'PAGINATION_AND_DISTINCT_SUBTITLE_CO_OCCUR' in decode(row['mechanisms_json'])
               for row in edition_rows if row['unit_anchor_entity_id'] == 'E000019492')
    assert old3['E000019492']['triage_tier'] == 'T1_CONTENT_CLUE'
    assert next(x for x in unit_rows if x['unit_anchor_entity_id'] == 'E000019492')['v4_focus_group'] == 'F1_CONTENT_BOUNDARY'

    unit_rows.sort(key=lambda r: (TIER_ORDER[r['v4_focus_group']], r['unit_anchor_entity_id']))
    edition_rows.sort(key=lambda r: (r['unit_anchor_entity_id'], r['edition_key']))
    evidence_rows.sort(key=lambda r: (TIER_ORDER[r['v4_focus_group']], r['unit_anchor_entity_id'], r['mechanism'], r['edition_key']))
    for i, r in enumerate(unit_rows, 1):
        r['queue_order'] = str(i)
    manifest = {
        'release': 'aggregation-held-one-work-refined-evidence-v4',
        'status': 'POST_HOC_EXPLORATORY_NOT_IDENTITY_ADJUDICATION',
        'source_snapshot': SNAPSHOT,
        'frame': '438 held old-LLM ONE_WORK units; 1249 OL Works; 40305 Editions',
        'inputs_sha256': {str(p.relative_to(ROOT)): digest for p, digest in EXPECTED_SHA.items()},
        'counts': {
            'units': len(unit_rows), 'ol_works': len(w1), 'editions': len(edition_rows),
            'evidence_examples': len(evidence_rows),
            'v4_focus_groups': dict(sorted(tier_counts.items())),
            'v4_mechanism_unit_counts': dict(sorted(unit_mechanism_counts.items())),
            'v4_mechanism_edition_counts': dict(sorted(mechanisms_by_edition.items())),
            'v3_to_v4_transition': {a + ' -> ' + b: n for (a, b), n in sorted(transitions.items())},
        },
        'rules': {
            'F1_CONTENT_BOUNDARY': 'Potential multi-item subtitles, distinct subtitle plus TWO substantial numeric page segments, or contents plus collection title (non-archival).',
            'F2_PUBLICATION_CONTEXT': 'Notes about binding/slipcases/interpretation/collection, archival contents or volume markers.',
            'F3_AMBIGUOUS_METADATA': 'Weak signals, advertisements, preliminary-page candidates, other or generic fields; retains earlier v1/v2 signals.',
            'F4_NO_DEFINED_PROMPT': 'No current prompt; NOT SAFE TO MERGE.',
            'max_edition_examples_per_mechanism_per_unit': MAX_EXAMPLES_PER_MECHANISM,
            'rules_are_explicitly_post_hoc': True,
            'old_v3_tier_preserved': True,
        },
        'limitations': [
            'No work identity changes or inferred constituent work IDs.',
            'A content-boundary prompt does not prove distinct conceptual works.',
            'Advertisements and multiple pagination sections are sometimes bibliographically ambiguous.',
            'A bound-with note may be copy-specific; slipcase is not a composite textual work.',
            'A contents list can contain chapters, criticism, or archival materials.',
            'A distinct subtitle may be translated title or descriptive information, not another work.',
            'All screening rules are exploratory and post-hoc to viewed held-out and development cases.',
            'The unselected 66 units are not certified as safe for merging.',
            'v1/v2 upstream Edition-derived tables retain their original local-validation status.',
            'No previously frozen human labels, adjudication, or Project W release was modified.',
        ],
        'output_sha256': {},
    }

    # Atomic publication: validate files in a temporary sibling directory,
    # rename only after all output files are complete and checks pass.
    with tempfile.TemporaryDirectory(prefix='.held_one_work_v4_build_', dir=BASE) as temp:
        staging = Path(temp)
        outputs = {
            'refined_unit_queue_v4.tsv': unit_rows,
            'refined_edition_mechanisms_v4.tsv': edition_rows,
            'refined_evidence_examples_v4.tsv': evidence_rows,
        }
        for name, rows in outputs.items():
            save_tsv(staging / name, rows)
            assert len(load_tsv(staging / name)) == len(rows)
        manifest['output_sha256'] = {name: sha(staging / name) for name in outputs}
        (staging / 'manifest_v4.json').write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
            encoding='utf-8')
        for name, digest in manifest['output_sha256'].items():
            assert sha(staging / name) == digest
        for path, digest in EXPECTED_SHA.items():
            assert sha(path) == digest
        assert not OUT.exists(), 'STOP: v4 output already exists'
        os.rename(staging, OUT)

    print('=== HELD ONE_WORK REFINED BIBLIOGRAPHIC EVIDENCE V4 CREATED ===')
    print('Units:', len(unit_rows), 'OL Works:', len(w1), 'Edition rows:', len(edition_rows))
    print('Evidence examples:', len(evidence_rows))
    print('Focus groups:', dict(sorted(tier_counts.items())))
    print('Selected case 12:', next(r['v4_focus_group'] for r in unit_rows if r['unit_anchor_entity_id']=='E000019492'))
    print('V3 to V4 transitions:', dict(sorted(transitions.items())))
    print('Mechanism unit counts:', dict(sorted(unit_mechanism_counts.items())))
    for p in sorted(OUT.iterdir()):
        print(p.name, sha(p))
    print('No git mutation, no identity adjudication, no Project W changes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true', help='synthetic examples; no repo files read or written')
    arguments = parser.parse_args()
    if arguments.self_test:
        self_test()
    else:
        main()
