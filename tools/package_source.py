"""Export reviewed source and validation evidence beside the board archive."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DEST=Path('C:/Users/CHENZHELONG/Desktop/FPGAvision/releases/visual_aid_v4_pl_upgrade_20261023')


def main():
    status=json.loads((ROOT/'reports/delivery_manifest.json').read_text(encoding='utf-8'))
    board=ROOT/status['board_archive']
    if hashlib.sha256(board.read_bytes()).hexdigest()!=status['board_archive_sha256']:
        raise RuntimeError('Status refers to a different board archive')
    DEST.mkdir(parents=True,exist_ok=True)
    for p in (board,board.with_suffix('.zip.sha256')):
        shutil.copy2(p,DEST/p.name)
    shutil.copy2(ROOT/'docs/pl_upgrade_zh.md',DEST/'README_zh.md')
    shutil.copy2(ROOT/'reports/PL_UPGRADE_zh.md',DEST/'STATUS_zh.md')
    for name in ('pl_upgrade_summary.json','active_demo_snapshot.json'):
        shutil.copy2(ROOT/'reports'/name,DEST/name)
    for name in ('quality_zh.md','pl_roadmap_zh.md','pl_upgrade_zh.md'):
        shutil.copy2(ROOT/'docs'/name,DEST/name)
    target=DEST/'visual_aid_v4_ec11_source.zip'
    files=[]
    for name in ('rtl','sim','software','tests','tools','vivado','vendor','docs'):
        files.extend(p for p in (ROOT/name).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and 'logs' not in p.relative_to(ROOT).parts
                     and not (p.parent==ROOT/'tools' and p.name.startswith('board_')
                              and p.name not in ('board_native_build.py','board_pl_exercise.py')))
    files.extend(ROOT/name for name in ('build.ps1','README.md','README_zh.md','LICENSE','THIRD_PARTY.md'))
    files.extend(p for p in (ROOT/'reports').glob('*') if p.is_file() and p.suffix in ('.json','.md','.rpt','.txt'))
    files.extend(p for p in (ROOT/'reports/board_validation_20261022').glob('*') if p.is_file())
    files.extend(p for p in (ROOT/'reports/ec11_preview').glob('*') if p.is_file())
    files.extend(p for p in (ROOT/'reports/performance').glob('*.json') if p.is_file())
    files.extend(p for p in (ROOT/'reports/attempts').rglob('*') if p.is_file() and p.suffix in ('.xdc','.json','.txt','.rpt'))
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in sorted(set(files)):
            archive.write(p,'visual_aid_v4_ec11/'+p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:raise RuntimeError('Corrupt source archive')
    target.with_suffix('.zip.sha256').write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name+'\n',encoding='ascii')
    print('PACKAGED',DEST)
    print('SOURCE_FILES',len(set(files)))


if __name__=='__main__':main()
