"""Publish only a current, simulated, timed and internally consistent board bundle."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SUITE = ['reading','capture','registers','gamma','fifo','abort']


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hardware_sources():
    return {p.relative_to(ROOT).as_posix(): digest(p)
            for folder in ('rtl','sim','vivado','vendor')
            for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}


def read_json(name):
    return json.loads((ROOT/name).read_text(encoding='utf-8'))


def snapshot():
    record={'timestamp':datetime.datetime.now().astimezone().isoformat(),
            'started_at_epoch':time.time(),'sha256':hardware_sources()}
    (ROOT/'reports/implementation_inputs.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print('PASS hardware build inputs captured')


def check_simulation():
    results={}
    for scope in ('quick','full'):
        result=read_json('reports/xsim_'+scope+'.json')
        require(result['passed_tests']==SUITE,'Incomplete XSim '+scope)
        require(result['full_resolution']==(scope=='full'),'Wrong XSim resolution flag')
        for folder in ('rtl','sim'):
            for p in (ROOT/folder).glob('*.sv'):
                key=p.relative_to(ROOT).as_posix()
                require(result['sha256'].get(key)==digest(p),'RTL/testbench changed after simulation: '+key)
        results[scope]={'timestamp':result['timestamp'],'tests':result['passed_tests']}
    return results


def check_software():
    report=read_json('reports/software_tests.json')
    require(report['passed'] and report['tests_run']>0 and report['skipped']==0,'Software suite incomplete')
    for name,expected in report['sha256'].items():
        require((ROOT/name).is_file() and digest(ROOT/name)==expected,'Software changed after testing: '+name)
    return {'tests':report['tests_run'],'timestamp':report['timestamp']}


def check_hwh(path):
    root=ET.parse(path).getroot()
    modules={m.get('FULLNAME','').strip('/'):m for m in root.iter('MODULE')}
    require('assist_core' in modules,'Missing enhanced core in HWH')
    require(modules['assist_core'].get('MODTYPE')=='visual_aid_core','Wrong core type')
    ranges={m.get('INSTANCE'):m for m in root.iter('MEMRANGE') if m.get('MASTERBUSINTERFACE')=='M_AXI_GP0'}
    require('assist_core' in ranges and ranges['assist_core'].get('SLAVEBUSINTERFACE')=='s_axi','PYNQ slave metadata mismatch')
    require('display_vdma' in ranges,'Missing output VDMA')
    return {'control_ip':'assist_core/s_axi','control_base':ranges['assist_core'].get('BASEVALUE'),
            'vdma_ip':'display_vdma','vdma_base':ranges['display_vdma'].get('BASEVALUE')}


def check_protected():
    original=read_json('reports/original_project_check.json')
    require(original['unchanged'],'Original project changed')
    record=read_json('reports/raw_baseline_before.json')
    raw=Path(record['root'])
    bad=[name for name,h in record['sha256'].items() if not (raw/name).is_file() or digest(raw/name)!=h]
    require(not bad,'Raw baseline changed: '+str(bad[:5]))
    result={'original_files':original['original_files'],'original_unchanged':True,
            'raw_protected_files':len(record['sha256']),'raw_baseline_unchanged':True}
    (ROOT/'reports/protected_projects_check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


def publish():
    inputs=read_json('reports/implementation_inputs.json')
    require(inputs['sha256']==hardware_sources(),'Hardware sources/constraints changed during build; rerun implementation')
    simulation=check_simulation();software=check_software();protected=check_protected()
    timing=read_json('reports/system_timing_values.json')
    require(timing['setup_ns']>=0 and timing['hold_ns']>=0 and timing['drc_errors']==0,'Timing/DRC failed')
    require(timing['bidirectional_pads']==4 and timing['enhancement_present'],'Missing enhanced logic or bidirectional pads')
    log=(ROOT/'reports/implement_system.log').read_text(errors='replace')
    require('PASS: enhanced overlay timing, DRC and staged bit/HWH' in log,'No final implementation acceptance marker')
    skew=(ROOT/'reports/system_bus_skew.rpt').read_text(errors='replace')
    # Summary entries have corner / requirement / actual / slack columns.
    skew_rows=re.findall(r'^\s*(?:Slow|Fast)\s+([-+\d.]+)\s+([-+\d.]+)\s+([-+\d.]+)\s*$',skew,re.M)
    require(bool(skew_rows),'Bus-skew summary missing')
    require(all(float(row[-1])>=0 for row in skew_rows),'Bus-skew violation')
    route=(ROOT/'reports/system_route_status.rpt').read_text(errors='replace')
    routable=re.search(r'# of routable nets\.*\s*:\s*(\d+)',route,re.I)
    routed=re.search(r'# of fully routed nets\.*\s*:\s*(\d+)',route,re.I)
    errors=re.search(r'# of nets with routing errors\.*\s*:\s*(\d+)',route,re.I)
    require(routable and routed and errors and routable[1]==routed[1] and int(errors[1])==0,
            'Route report does not confirm complete error-free routing')
    require(timing.get('gray_groups')==5,'Custom Gray crossing verification missing')
    require(len(skew_rows)>=8,'Missing custom or official bus-skew constraints')
    timing_text=(ROOT/'reports/system_timing.rpt').read_text(errors='replace')
    require('All user specified timing constraints are met.' in timing_text,
            'Overall timing report has unmet constraints')
    timing_check=(ROOT/'reports/check_timing.rpt').read_text(errors='replace')
    require('There are 0 register/latch pins with no clock.' in timing_check,'Registers without clocks')
    require('There are 0 pins that are not constrained for maximum delay.' in timing_check,'Unconstrained internal timing')
    metadata=check_hwh(ROOT/'build/visual_aid_v3.hwh')
    for name in ('visual_aid_v3','visual_aid_v3_external_pullup'):
        require((ROOT/'build'/(name+'.bit')).stat().st_size>1000000,'Incomplete bitstream: '+name)
        require(digest(ROOT/'build'/(name+'.hwh'))==digest(ROOT/'build/visual_aid_v3.hwh'),'Variant HWH mismatch')
    board=ROOT/'software/board';board.mkdir(exist_ok=True)
    for name in ('visual_aid_v3','visual_aid_v3_external_pullup'):
        for suffix in ('.bit','.hwh'):
            shutil.copy2(ROOT/'build'/(name+suffix),board/(name+suffix))
    files=[p for p in (ROOT/'software').rglob('*') if p.is_file()
           and '__pycache__' not in p.parts and 'logs' not in p.relative_to(ROOT/'software').parts
           and p.suffix in ('.py','.bin','.json','.bit','.hwh') and p!=board/'build_manifest.json']
    manifest={'project':'visual_aid_v3','abi':0x56410300,'built_at':datetime.datetime.now().astimezone().isoformat(),
              'vivado':'2018.3','pynq_target':'2.4','resolution':[1280,720],'timing':timing,
              'full_system_implementation':'passed','hardware_validation':'not_run_user_requested_host_only',
              'measured_board_camera_fps':None,'metadata':metadata,'simulation':simulation,'software_tests':software,
              'protected_projects':protected,'hardware_source_sha256':inputs['sha256'],
              'variants':{'default':{'bit':'board/visual_aid_v3.bit','hwh':'board/visual_aid_v3.hwh','camera_weak_pullups':True},
                          'external_pullup':{'bit':'board/visual_aid_v3_external_pullup.bit',
                                             'hwh':'board/visual_aid_v3_external_pullup.hwh','camera_weak_pullups':False}},
              'payload_sha256':{p.relative_to(ROOT/'software').as_posix():digest(p) for p in files}}
    (board/'build_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    sys.path.insert(0,str(ROOT/'software'))
    from visual_aid.integrity import verify_payload
    verify_payload(ROOT/'software',board/'visual_aid_v3.bit')
    delivery=ROOT/'delivery';delivery.mkdir(exist_ok=True)
    archive=delivery/'visual_aid_v3_board.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files+[board/'build_manifest.json']:
            z.write(p,'visual_aid_v3_enhanced/'+p.relative_to(ROOT/'software').as_posix())
        for p in (ROOT/'docs').rglob('*'):
            if p.is_file():z.write(p,'visual_aid_v3_enhanced/docs/'+p.relative_to(ROOT/'docs').as_posix())
        for license_name in ('PYNQ_LICENSE','PYNQ_THIRD_PARTY_LIC','ADAFRUIT_VL53L0X_LICENSE','ESP32_CAMERA_LICENSE','af_firmware_source.txt'):
            source=ROOT/'vendor'/license_name
            if source.is_file():z.write(source,'visual_aid_v3_enhanced/licenses/'+license_name)
        for name in ('LICENSE','THIRD_PARTY.md'):
            z.write(ROOT/name,'visual_aid_v3_enhanced/'+name)
        z.write(ROOT/'docs/board_bringup_zh.md','visual_aid_v3_enhanced/README_board_zh.md')
        for name in ('system_timing.rpt','system_drc.rpt','system_utilization.rpt','system_clocks.rpt',
                     'system_cdc.rpt','system_cdc_details.rpt','check_timing.rpt','system_bus_skew.rpt',
                     'system_timing_values.json','protected_projects_check.json'):
            z.write(ROOT/'reports'/name,'visual_aid_v3_enhanced/host_validation/'+name)
    with zipfile.ZipFile(archive) as z:
        require(z.testzip() is None,'Corrupt board archive')
        for name,expected in manifest['payload_sha256'].items():
            require(hashlib.sha256(z.read('visual_aid_v3_enhanced/'+name)).hexdigest()==expected,'Archive hash mismatch: '+name)
    (delivery/'visual_aid_v3_board.zip.sha256').write_text(digest(archive)+'  '+archive.name+'\n',encoding='ascii')
    print('PASS board package:',archive)
    print('PASS setup={}ns hold={}ns software_tests={} payload_files={}; BOARD NOT TESTED'.format(
        timing['setup_ns'],timing['hold_ns'],software['tests'],len(files)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--snapshot',action='store_true')
    args=parser.parse_args()
    if args.snapshot:snapshot()
    else:publish()
