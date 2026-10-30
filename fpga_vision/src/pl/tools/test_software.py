"""Run host checks and retain their counts and exact source hashes."""
from pathlib import Path
import hashlib
import json
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


def hashes():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('software', 'tests') for p in (ROOT/folder).rglob('*')
            if p.is_file() and '__pycache__' not in p.parts
            and not any(part in ('board','logs') for part in p.relative_to(ROOT/folder).parts)}


if __name__ == '__main__':
    before = hashes()
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    current = hashes()
    passed = result.wasSuccessful() and before == current and result.testsRun > 0
    record = {'passed': passed, 'tests_run': result.testsRun,
              'failures': len(result.failures), 'errors': len(result.errors),
              'skipped': len(result.skipped), 'sha256': before,
              'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
              'environment': 'Host Python; not a board execution'}
    (ROOT/'reports').mkdir(exist_ok=True)
    (ROOT/'reports/software_tests.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    if passed:
        print('PASS software tests={} failures=0 errors=0'.format(result.testsRun))
    else:
        print('FAIL software tests or source changed during execution', file=sys.stderr)
    raise SystemExit(0 if passed else 1)
