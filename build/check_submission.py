"""Read-only release checks; no Vivado invocation or board access."""
from pathlib import Path
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    files = [p for p in ROOT.rglob('*')
             if p.is_file() and '.git' not in p.relative_to(ROOT).parts
             and '__pycache__' not in p.relative_to(ROOT).parts]
    for p in files:
        rel = p.relative_to(ROOT)
        assert all(re.fullmatch('[a-z0-9_-]+', x) for x in rel.parts[:-1]), str(rel)
        assert p.name == 'README.md' or re.fullmatch('[a-z0-9_.-]+', p.name), str(rel)
    manifest = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
    actual = {p.relative_to(ROOT).as_posix() for p in files if p != ROOT / 'manifest.json'}
    assert actual == set(manifest['sha256']), 'release file set differs from manifest'
    for rel, expected in manifest['sha256'].items():
        assert digest((ROOT / rel).read_bytes()) == expected, rel
    sim = json.loads((ROOT / 'sim/results/xsim_full.json').read_text())
    assert len(sim['passed_tests']) == 9
    for rel, expected in sim['sha256'].items():
        if rel.startswith(('rtl/', 'sim/')):
            assert digest((ROOT / 'src/pl' / rel).read_bytes()) == expected, rel
    fingerprints = json.loads((ROOT / 'build/rebuilt/source_fingerprints.json').read_text())
    for rel, expected in fingerprints.items():
        assert digest((ROOT / 'src/pl' / rel).read_bytes()) == expected, rel
    for name in ['runtime_bundle.zip', 'rebuilt_runtime.zip']:
        with zipfile.ZipFile(ROOT / 'board' / name) as z:
            assert z.testzip() is None, name
            key = next(n for n in z.namelist() if n.endswith('/board/build_manifest.json'))
            prefix = key[:-len('board/build_manifest.json')]
            payload = json.loads(z.read(key))
            for rel, expected in payload['payload_sha256'].items():
                assert digest(z.read(prefix + rel)) == expected, (name, rel)
            if name == 'runtime_bundle.zip':
                for n in z.namelist():
                    if not n.endswith('/'):
                        assert z.read(n) == (ROOT / 'src/ps/runtime' / n[len(prefix):]).read_bytes(), n
    print(json.dumps({'passed': True, 'files': len(files), 'historical_xsim_fingerprints': True,
                      'historical_rebuild_fingerprints': True, 'runtime_archives': True,
                      'new_vivado_run': False, 'new_board_run': False}, indent=2))


if __name__ == '__main__':
    main()
