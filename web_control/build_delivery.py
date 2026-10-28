"""Create a traceable local-only bundle. Never connects to hardware."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parent
RUNTIME=ROOT/'runtime'
BASE=ROOT.parent


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path=RUNTIME/'board/build_manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    baseline=json.loads((BASE/'software/board/build_manifest.json').read_text(encoding='utf-8'))
    files={p.relative_to(RUNTIME).as_posix():p for p in RUNTIME.rglob('*')
           if p.is_file() and '__pycache__' not in p.parts and 'logs' not in p.relative_to(RUNTIME).parts
           and p!=manifest_path and p.suffix not in ('.pyc','.log')}
    for name in baseline['payload_sha256']:
        if name.startswith('board/'):
            assert digest(RUNTIME/name)==baseline['payload_sha256'][name],name
    manifest['payload_sha256']={name:digest(path) for name,path in sorted(files.items())}
    manifest['web_control_revision']='2026-10-28-local-v1'
    manifest['web_control_validation']='host tested; hardware integration pending'
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    files['board/build_manifest.json']=manifest_path
    import sys
    sys.path.insert(0,str(RUNTIME))
    from visual_aid.integrity import verify_payload
    verify_payload(RUNTIME,RUNTIME/'board/visual_aid_v3.bit')
    archive=ROOT/'delivery/FPGAvision_Control_board.zip'
    entries={'FPGAvision_Control/'+name:path for name,path in files.items()}
    entries['FPGAvision_Control/README_zh.md']=ROOT/'README_zh.md'
    for name in ('LICENSE','THIRD_PARTY.md'):
        entries['FPGAvision_Control/'+name]=BASE/name
    for p in (BASE/'vendor').glob('*'):
        if p.is_file() and ('LICENSE' in p.name or p.name in ('PYNQ_THIRD_PARTY_LIC','af_firmware_source.txt')):
            entries['FPGAvision_Control/licenses/'+p.name]=p
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for name,path in sorted(entries.items()):z.write(path,name)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,path in entries.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest(path)
    archive.with_suffix('.zip.sha256').write_text(digest(archive)+'  '+archive.name+'\n',encoding='ascii')
    receipt={'base_project':str(BASE),'runtime_payload_count':len(files),
             'bit_hwh_unchanged':True,'board_connected':False,
             'archive_sha256':digest(archive),'archive':str(archive)}
    (ROOT/'delivery/package_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
