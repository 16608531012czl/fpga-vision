"""Portable standard-library SHA-256 verifier. Manifest paths are root-relative."""
import argparse,hashlib,json,re
from pathlib import Path,PurePosixPath
def verify(root,hashes):
    root=Path(root).resolve();errors=[]
    if not isinstance(hashes,dict) or not hashes:return ['empty or invalid manifest']
    for name,expected in hashes.items():
        rel=PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or '\\' in name or ':' in name:
            errors.append('unsafe path: '+name);continue
        p=(root/str(rel)).resolve()
        if root not in p.parents:errors.append('path escapes root: '+name);continue
        if not re.fullmatch('[0-9a-f]{64}',str(expected)):errors.append('invalid digest: '+name);continue
        if not p.is_file():errors.append('missing: '+name)
        elif hashlib.sha256(p.read_bytes()).hexdigest()!=expected:errors.append('hash mismatch: '+name)
    return errors
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('root',type=Path);ap.add_argument('manifest',type=Path)
    a=ap.parse_args();d=json.loads(a.manifest.read_text(encoding='utf-8'));e=verify(a.root,d.get('sha256',d))
    print(json.dumps({'passed':not e,'errors':e},indent=2));return bool(e)
if __name__=='__main__':raise SystemExit(main())
