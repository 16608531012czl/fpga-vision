"""Recheck the separate OV5640 V3 source against the upgrade's saved baseline."""
from pathlib import Path
import datetime
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
record=json.loads((ROOT/'reports/upgrade_baseline.json').read_text(encoding='utf-8'))
source=Path(record['source'])
changed=[name for name,expected in record['source_sha256'].items()
         if not (source/name).is_file() or hashlib.sha256((source/name).read_bytes()).hexdigest()!=expected]
result={'source':str(source),'checked_files':len(record['source_sha256']),
        'changed_files':changed,'unchanged':not changed,
        'checked_at':datetime.datetime.now().astimezone().isoformat()}
(ROOT/'reports/upgrade_original_unchanged.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
if changed:
    raise SystemExit('Original V3 changed: '+str(changed))
print('PASS original OV5640 V3: {} files unchanged'.format(result['checked_files']))
