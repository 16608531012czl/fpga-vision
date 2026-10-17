from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[1]
record=json.loads((ROOT/'reports/original_project_before.json').read_text(encoding='utf-8'))
old=Path(record['root'])
current={p.relative_to(old).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in old.rglob('*') if p.is_file()}
changed=[p for p,h in record['sha256'].items() if current.get(p)!=h]
added=sorted(set(current)-set(record['sha256']))
result={'original_files':len(record['sha256']),'changed_or_deleted':changed,'added':added,'unchanged':not changed and not added}
(ROOT/'reports/original_project_check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
if not result['unchanged']:raise SystemExit('Original project changed: '+str(result))
print('PASS original project: {} files unchanged'.format(len(current)))
