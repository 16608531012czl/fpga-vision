"""Package a checked software-only update while proving the saved hardware is unchanged."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile

from package_board import check_software, hardware_sources, require

ROOT = Path(__file__).resolve().parents[1]
RELEASE = 'visual_aid_v3_lowlight_20261020'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-receipt', type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads(args.baseline_receipt.read_text(encoding='utf-8'))
    baseline = Path(receipt['backup'])
    require(digest(baseline) == receipt['sha256'], 'Baseline backup hash mismatch')
    require(hardware_sources() == receipt['hardware_sha256'], 'Hardware changed; use full build workflow')
    board = ROOT/'software/board'
    require({p.name:digest(p) for p in board.iterdir() if p.suffix in ('.bit','.hwh')}
            == receipt['board_artifact_sha256'], 'Bit/HWH changed since backup')
    with zipfile.ZipFile(baseline) as saved:
        baseline_bytes = saved.read('software/board/build_manifest.json')
        manifest = json.loads(baseline_bytes)
        # Verify the saved release itself, not merely the new software hashes.
        for name, expected in manifest['payload_sha256'].items():
            require(hashlib.sha256(saved.read('software/'+name)).hexdigest() == expected,
                    'Invalid saved baseline payload: '+name)
    require(manifest['hardware_source_sha256'] == hardware_sources(),
            'Hardware no longer matches the original implementation manifest')
    changed = {name for name, expected in manifest['payload_sha256'].items()
               if digest(ROOT/'software'/name) != expected}
    require(changed == {'run_board.py','visual_aid/image.py'}, 'Unexpected runtime changes: '+str(changed))
    software = check_software()
    # This software-only release inherits the original manifest's simulation
    # record. No RTL simulation is claimed as rerun; exact hardware hashes above
    # are the reuse gate. Some standalone historical XSim reports are absent.
    simulation = {'source':'saved_release_manifest', 'rerun_for_this_update':False,
                  'record':manifest['simulation']}
    evidence = json.loads((ROOT/'reports/lowlight_20261020/results.json').read_text(encoding='utf-8'))
    require(evidence['board_tested'] is False, 'Synthetic evidence incorrectly labelled')
    case = next(c for c in evidence['constant_gray_cases'] if c['source_gray'] == 40)
    require(case['lowlight_mean'] >= 110 and case['lowlight_mean']-case['legacy_mean'] >= 25,
            'Lowlight acceptance target failed')
    manifest.update(software_release_id=RELEASE, release_kind='software_only_existing_bitstream',
                    software_released_at=datetime.datetime.now().astimezone().isoformat(),
                    baseline_manifest_sha256=hashlib.sha256(baseline_bytes).hexdigest(),
                    baseline_backup=baseline.name, software_tests=software,
                    hardware_validation='lowlight_software_update_not_board_tested',
                    measured_board_camera_fps=None,
                    lowlight_validation={'host_reference':'passed', 'board_tested':False,
                                         'hardware_rebuilt':False, 'hardware_hashes_unchanged':True})
    manifest['payload_sha256'] = {name:digest(ROOT/'software'/name) for name in manifest['payload_sha256']}
    (board/'build_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    sys.path.insert(0,str(ROOT/'software'))
    from visual_aid.integrity import verify_payload
    verify_payload(ROOT/'software',board/'visual_aid_v3.bit')
    archive = ROOT/'delivery'/(RELEASE+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in list(manifest['payload_sha256'])+['board/build_manifest.json']:
            z.write(ROOT/'software'/name,RELEASE+'/'+name)
        for p in (ROOT/'docs').rglob('*'):
            if p.is_file(): z.write(p,RELEASE+'/docs/'+p.relative_to(ROOT/'docs').as_posix())
        z.write(ROOT/'docs/lowlight_20261020_zh.md',RELEASE+'/README_lowlight_zh.md')
        for name in ('LICENSE','THIRD_PARTY.md'):
            z.write(ROOT/name,RELEASE+'/'+name)
        for name in ('PYNQ_LICENSE','PYNQ_THIRD_PARTY_LIC','ADAFRUIT_VL53L0X_LICENSE',
                     'ESP32_CAMERA_LICENSE','af_firmware_source.txt'):
            p=ROOT/'vendor'/name
            if p.is_file(): z.write(p,RELEASE+'/licenses/'+name)
        for name in ('results.json','comparison.png'):
            z.write(ROOT/'reports/lowlight_20261020'/name,RELEASE+'/host_validation/lowlight/'+name)
        z.write(ROOT/'reports/software_tests.json',RELEASE+'/host_validation/software_tests.json')
    with zipfile.ZipFile(archive) as z:
        require(z.testzip() is None,'Corrupt archive')
        for name,expected in manifest['payload_sha256'].items():
            require(hashlib.sha256(z.read(RELEASE+'/'+name)).hexdigest()==expected,'Archive mismatch: '+name)
        with tempfile.TemporaryDirectory(prefix='lowlight_smoke_',dir=str(ROOT/'build')) as temp:
            z.extractall(temp)
            deployed=Path(temp)/RELEASE
            verify_payload(deployed,deployed/'board/visual_aid_v3.bit')
            smoke=subprocess.run([sys.executable,str(deployed/'preflight.py'),'--host'],
                                 capture_output=True,text=True,check=True)
            result=json.loads(smoke.stdout)
            require(result['outcome']=='passed','Extracted bundle preflight failed')
    result.update(archive=str(archive),archive_sha256=digest(archive),
                  hardware_rebuilt=False,hardware_hashes_unchanged=True,
                  host_software_tests=software,inherited_rtl_simulation=simulation,
                  baseline_backup=str(baseline),changed_runtime_files=sorted(changed))
    (ROOT/'reports/lowlight_20261020/package_smoke.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    archive.with_suffix('.zip.sha256').write_text(digest(archive)+'  '+archive.name+'\n',encoding='ascii')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
