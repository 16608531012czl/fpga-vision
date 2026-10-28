"""Package the accepted runtime plus the tested Jupyter panel, without board access."""
from pathlib import Path
import ast
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = 'visual_aid_v4_camera_detail_20261028'


def package():
    manifest = json.loads((ROOT/'software/board/build_manifest.json').read_text(encoding='utf-8'))
    notebook = ROOT/'delivery/FPGAvision_OneClick.ipynb'
    nb = json.loads(notebook.read_text(encoding='utf-8'))
    cells = [c for c in nb['cells'] if c['cell_type'] == 'code']
    assert len(cells) == 1
    assert ''.join(cells[0]['source']) == (ROOT/'tools/jupyter_panel_cell.py').read_text(encoding='utf-8')
    assert not cells[0].get('outputs')
    ast.parse(''.join(cells[0]['source']), feature_version=(3, 6))
    ast.parse((ROOT/'tools/jupyter_gui_guard.py').read_text(encoding='utf-8'), feature_version=(3, 6))
    entries = {}
    for name, expected in manifest['payload_sha256'].items():
        path = ROOT/'software'/name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
        entries[NAME+'/'+name] = path
    entries[NAME+'/board/build_manifest.json'] = ROOT/'software/board/build_manifest.json'
    entries[NAME+'/jupyter_gui_guard.py'] = ROOT/'tools/jupyter_gui_guard.py'
    entries['FPGAvision_OneClick.ipynb'] = notebook
    entries[NAME+'/README_board_zh.md'] = ROOT/'README_zh.md'
    for folder in ('docs',):
        for path in (ROOT/folder).rglob('*'):
            if path.is_file():
                entries[NAME+'/'+path.relative_to(ROOT).as_posix()] = path
    for name in ('LICENSE', 'THIRD_PARTY.md'):
        entries[NAME+'/'+name] = ROOT/name
    for name in ('PYNQ_LICENSE','PYNQ_THIRD_PARTY_LIC','ADAFRUIT_VL53L0X_LICENSE','ESP32_CAMERA_LICENSE','af_firmware_source.txt'):
        path = ROOT/'vendor'/name
        if path.is_file():
            entries[NAME+'/licenses/'+name] = path
    for name in ('system_timing_values.json','arduino_io.rpt','arduino_variant_lineage.json',
                 'software_tests.json','camera_validation_summary.json','CAMERA_VALIDATION_zh.md'):
        entries[NAME+'/host_validation/'+name] = ROOT/'reports'/name
    archive = ROOT/'delivery'/(NAME+'_board.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as out:
        for name, path in sorted(entries.items()):
            out.write(path, name)
    with zipfile.ZipFile(archive) as check:
        assert check.testzip() is None
        for name, path in entries.items():
            assert check.read(name) == path.read_bytes(), name
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n', encoding='ascii')
    receipt = {'archive':archive.name, 'sha256':digest, 'archive_entries':len(entries),
               'runtime_payload_files':len(manifest['payload_sha256']),
               'runtime_payload_unchanged':True, 'jupyter_guard_included':True,
               'notebook_included':True, 'hardware_loaded_by_packaging':False}
    (ROOT/'reports/current_package.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(receipt))


if __name__ == '__main__':
    package()
