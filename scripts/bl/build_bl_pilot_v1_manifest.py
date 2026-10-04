#!/usr/bin/env python3
"""
Build manifest.json for the BL verification pilot v1 (protocol §9).

Records, for every file of the pilot:
    path, sha256, bytes, data rows (TSV only, header excluded),
    last commit that changed the file (git log -1 --format=%h -- <path>)

Files covered (tracked in Git only):
- docs/BRITISH_LIBRARY_SRU_RETRIEVAL_PLAN.md
- docs/BL_VERIFICATION_PILOT_V1_PROTOCOL.md
- docs/BL_VERIFICATION_PILOT_V1_ANALYSIS_ADDENDUM.md, _2, _3, _4
- every file under scripts/bl/
- every file under derived/bl_calibration/verification_pilot_v1/
  except manifest.json itself

Also records the raw archive (outside Git): file name, sha256, bytes,
number of XML members, server location, and notes.

Stops without writing if:
- any covered file has uncommitted changes, or an untracked file exists
  under the covered directories (the manifest must describe committed state);
- a listed document is not tracked;
- the raw archive's sha256 or XML count differs from the documented values
  (addendum 1 §2).

Deterministic: no timestamps; keys sorted; files sorted by path.
Output is written with LF line endings and a single trailing newline.

Output:
- derived/bl_calibration/verification_pilot_v1/manifest.json

Before running: source ~/canon-pipeline/.venv/bin/activate
"""

import csv
import hashlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path

MANIFEST_VERSION = 'bl_verification_pilot_v1_manifest_1'

DOCS = [
    'docs/BRITISH_LIBRARY_SRU_RETRIEVAL_PLAN.md',
    'docs/BL_VERIFICATION_PILOT_V1_PROTOCOL.md',
    'docs/BL_VERIFICATION_PILOT_V1_ANALYSIS_ADDENDUM.md',
    'docs/BL_VERIFICATION_PILOT_V1_ANALYSIS_ADDENDUM_2.md',
    'docs/BL_VERIFICATION_PILOT_V1_ANALYSIS_ADDENDUM_3.md',
    'docs/BL_VERIFICATION_PILOT_V1_ANALYSIS_ADDENDUM_4.md',
]
DIRS = [
    'scripts/bl',
    'derived/bl_calibration/verification_pilot_v1',
]
OUTPUT_REL = 'derived/bl_calibration/verification_pilot_v1/manifest.json'

RAW_ARCHIVE_NAME = 'bl_verification_pilot_v1_raw_20261001.tar.gz'
RAW_ARCHIVE_LOCAL = Path.home() / 'bl_raw' / RAW_ARCHIVE_NAME
RAW_EXPECTED_SHA256 = 'e613ae28bbaa9f5d5336bbb744cc2f6c552c1afbc4d075f764d08aab534739d3'
RAW_EXPECTED_XML = 296
RAW_SERVER_LOCATION = 'tsutsui@133.91.20.74:/media/hdd1/user/tsutsui/bl/'


def git(base_dir: Path, *args: str) -> str:
    return subprocess.run(['git', *args], cwd=base_dir, check=True,
                          capture_output=True, text=True).stdout


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def tsv_data_rows(path: Path) -> int:
    with open(path, newline='') as f:
        reader = csv.reader(f, delimiter='\t')
        next(reader, None)
        return sum(1 for _ in reader)


def collect_paths(base_dir: Path) -> list:
    """Tracked files for DOCS and DIRS, sorted, excluding the manifest itself."""
    covered = DOCS + DIRS

    dirty = git(base_dir, 'status', '--porcelain', '--', *covered).splitlines()
    dirty = [line for line in dirty if not line.endswith(OUTPUT_REL)]
    if dirty:
        sys.exit('Uncommitted or untracked files under covered paths:\n' + '\n'.join(dirty))

    tracked = git(base_dir, 'ls-files', '-z', '--', *covered).split('\0')
    tracked = sorted({p for p in tracked if p and p != OUTPUT_REL})

    missing_docs = [d for d in DOCS if d not in tracked]
    if missing_docs:
        sys.exit('Documents not tracked: ' + ', '.join(missing_docs))
    return tracked


def describe_file(base_dir: Path, rel: str) -> dict:
    path = base_dir / rel
    entry = {
        'path': rel,
        'sha256': sha256_file(path),
        'bytes': path.stat().st_size,
        'last_commit': git(base_dir, 'log', '-1', '--format=%h', '--', rel).strip(),
    }
    if rel.endswith('.tsv'):
        entry['tsv_data_rows'] = tsv_data_rows(path)
    return entry


def describe_raw() -> dict:
    if not RAW_ARCHIVE_LOCAL.is_file():
        sys.exit(f'Raw archive not found: {RAW_ARCHIVE_LOCAL}')
    digest = sha256_file(RAW_ARCHIVE_LOCAL)
    with tarfile.open(RAW_ARCHIVE_LOCAL, 'r:gz') as tar:
        n_xml = sum(1 for m in tar.getmembers() if m.isfile() and m.name.endswith('.xml'))
    if digest != RAW_EXPECTED_SHA256:
        sys.exit(f'Raw archive sha256 {digest} differs from documented {RAW_EXPECTED_SHA256}')
    if n_xml != RAW_EXPECTED_XML:
        sys.exit(f'Raw archive holds {n_xml} XML files, expected {RAW_EXPECTED_XML}')
    return {
        'archive_name': RAW_ARCHIVE_NAME,
        'archive_sha256': digest,
        'archive_bytes': RAW_ARCHIVE_LOCAL.stat().st_size,
        'xml_files': n_xml,
        'server_location': RAW_SERVER_LOCATION,
        'in_repository': False,
        'notes': [
            'Raw XML responses are kept outside Git; a local copy of the archive is kept outside the repository.',
            'Per-file sha256 of each XML response is recorded in physical_requests.tsv (column raw_sha256).',
            'Whether raw XML is committed to the repository is not yet decided.',
        ],
    }


def main():
    base_dir = Path(__file__).resolve().parents[2]

    paths = collect_paths(base_dir)
    files = [describe_file(base_dir, rel) for rel in paths]
    raw = describe_raw()
    head = git(base_dir, 'rev-parse', 'HEAD').strip()

    manifest = {
        'manifest_version': MANIFEST_VERSION,
        'protocol': 'docs/BL_VERIFICATION_PILOT_V1_PROTOCOL.md',
        'generated_at_head': head,
        'files': files,
        'raw': raw,
    }

    out_path = base_dir / OUTPUT_REL
    text = json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + '\n'
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)

    print(f'Wrote {OUTPUT_REL}: {len(files)} files, HEAD {head}')


if __name__ == '__main__':
    main()
