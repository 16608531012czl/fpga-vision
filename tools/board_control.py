"""Local SSH deployment/validation helper; credentials stay in local environment/stdin."""
from pathlib import Path
import argparse
import datetime
import json
import os
import shlex
import socket
import sys
import warnings
warnings.filterwarnings('ignore')
import paramiko

ROOT=Path(__file__).resolve().parents[1]
REMOTE='/home/xilinx/jupyter_notebooks/visual_aid_v4_ec11'


def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=('inspect-video','demo-start','demo-stop','demo-status','demo-snapshot','diagnostic','inspect','health','status','pins','release-sensors','bus-recovery','base-pmod','pad-test','light-probe','deploy','encoder','sensors','static','colorbars','live'))
    p.add_argument('--script',type=Path)
    p.add_argument('--seconds',type=int,default=120)
    p.add_argument('--no-af',action='store_true')
    p.add_argument('--no-sensors',action='store_true')
    p.add_argument('--camera-fps',type=int,choices=(15,18,20,21,22,24,30),default=20)
    p.add_argument('--quality-preset',choices=('balanced','baseline','detail'),default='detail')
    p.add_argument('--pipeline',choices=('pl','cpu'),default='pl')
    p.add_argument('--archive',type=Path,help='Explicit validated board bundle for a diagnostic rollback')
    a=p.parse_args()
    password=os.environ.get('FPGA_BOARD_PASSWORD','xilinx')
    client=paramiko.SSHClient();client.load_system_host_keys()
    connection=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    connection.settimeout(30)
    if sys.platform=='win32':
        # Pin this task's board connection to the direct Ethernet interface;
        # an overlapping VPN route must not redirect it.
        connection.setsockopt(socket.IPPROTO_IP,31,socket.htonl(21))
    connection.bind(('192.168.2.1',0))
    connection.connect(('192.168.2.99',22))
    client.connect('192.168.2.99',username='xilinx',password=password,
                   look_for_keys=False,allow_agent=False,timeout=30,banner_timeout=30,auth_timeout=30,sock=connection)
    client.get_transport().set_keepalive(20)
    def run(command,sudo=False):
        stdin,stdout,stderr=client.exec_command(('sudo -S -p "" ' if sudo else '')+command)
        if sudo:stdin.write(password+'\n');stdin.flush()
        stdin.close()
        for line in iter(stdout.readline,''):
            print(line,end='',flush=True)
        errors=stderr.read().decode('utf-8',errors='replace')
        if errors:print(errors,file=sys.stderr,flush=True)
        code=stdout.channel.recv_exit_status()
        if code:raise RuntimeError('Remote command exited '+str(code))
    try:
        if a.action=='inspect-video':
            run('/usr/bin/python3 -c '+shlex.quote("import inspect;from pynq.lib.video.dma import AxiVDMA;print(inspect.getsource(AxiVDMA.MM2SChannel))"),True)
            return
        if a.action=='demo-snapshot':
            target=REMOTE+'/logs/active_demo_snapshot.json'
            script=("import sys,os,time,json,subprocess\nfrom pynq import PL,MMIO\n"
                "sys.path.insert(0,"+repr(REMOTE)+")\nfrom visual_aid.integrity import verify_payload\n"
                "manifest=verify_payload("+repr(REMOTE)+")\n"
                "assert os.path.dirname(PL.bitfile_name or '')=="+repr(REMOTE+'/board')+"\n"
                "m=MMIO(int(manifest['metadata']['control_base'],0),4096)\nassert m.read(0)==0x56410400\n"
                "service=subprocess.check_output(['systemctl','show','visual-aid-v4-demo.service','--property=ActiveState','--property=SubState','--property=MainPID','--property=ExecMainStatus']).decode()\n"
                "assert 'ActiveState=active' in service,service\n"
                "names={'capture_id':0x1c,'dma_errors':0x20,'camera_vsync':0x24,'overflow_frames':0x28,'malformed_frames':0x2c,'display_sof':0x34}\n"
                "before={k:m.read(v) for k,v in names.items()};t=time.monotonic();time.sleep(1);after={k:m.read(v) for k,v in names.items()}\n"
                "invocation=subprocess.check_output(['systemctl','show','visual-aid-v4-demo.service','--property=InvocationID','--value']).decode().strip()\n"
                "journal=subprocess.check_output(['journalctl','_SYSTEMD_INVOCATION_ID='+invocation,'--no-pager','-o','cat']).decode(errors='replace').splitlines()\n"
                "af=[v for v in journal if v.startswith('AF_READY ')]\n"
                "samples=[]\nfor v in journal:\n try:\n  j=json.loads(v)\n  if 'rolling_unique_capture_fps' in j:samples.append(j)\n except ValueError:pass\n"
                "result={'release':manifest['built_at'],'service':service,'boot_id':open('/proc/sys/kernel/random/boot_id').read().strip(),"
                "'uptime':open('/proc/uptime').read().strip(),'elapsed':time.monotonic()-t,'before':before,'after':after,"
                "'deltas':{k:(after[k]-before[k])&0xffffffff for k in names},'autofocus':json.loads(af[-1][9:]) if af else None,'latest_samples':samples[-3:], 'invocation_id':invocation,'active_config':hex(m.read(0x30))}\n"
                "assert result['deltas']['capture_id']>0 and result['autofocus'] and not any(result['deltas'][k] for k in ('dma_errors','overflow_frames','malformed_frames')),result\n"
                "open("+repr(target)+",'w').write(json.dumps(result,indent=2));print(json.dumps(result,indent=2))\n")
            run('/usr/bin/python3 -c '+shlex.quote(script),True)
            with client.open_sftp() as snapshot_sftp:
                snapshot_sftp.get(target,str(ROOT/'reports/active_demo_snapshot.json'))
            return
        if a.action in ('demo-stop','demo-status'):
            if a.action=='demo-stop':run('systemctl stop visual-aid-v4-demo.service',True)
            run('systemctl show visual-aid-v4-demo.service --property=ActiveState --property=SubState --property=MainPID --property=ExecMainStatus --no-pager')
            run('journalctl -u visual-aid-v4-demo.service -n 5 --no-pager -o cat',True)
            return
        if a.action=='health':
            remote_report=REMOTE+'/logs/health_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.json'
            script=("import json,subprocess,glob,os\nfrom pynq import PL\n"
                    "result={'uptime':open('/proc/uptime').read().strip(),'boot_id':open('/proc/sys/kernel/random/boot_id').read().strip(),'loaded_overlay':PL.bitfile_name}\n"
                    "for name,argv in [('boots',['journalctl','--list-boots','--no-pager']),('reboot_history',['last','-x','reboot','shutdown','-n','6']),('kernel_tail',['dmesg','-T'])]:\n"
                    " try: result[name]=subprocess.check_output(argv,stderr=subprocess.STDOUT).decode(errors='replace')[-12000:]\n"
                    " except Exception as exc: result[name]=str(exc)\n"
                    "result['pstore_files']=glob.glob('/sys/fs/pstore/*')\n"
                    "open("+repr(remote_report)+",'w').write(json.dumps(result,indent=2))\nprint(json.dumps(result,indent=2))")
            run('/usr/bin/python3 -c '+shlex.quote(script),True)
            with client.open_sftp() as health_sftp:
                health_sftp.get(remote_report,str(ROOT/'reports/board_validation_20261022'/Path(remote_report).name))
                for item in health_sftp.listdir(REMOTE+'/logs'):
                    if item.startswith('encoder_20261022_1651') and item.endswith('.json'):
                        health_sftp.get(REMOTE+'/logs/'+item,str(ROOT/'reports/board_validation_20261022'/item))
            return
        if a.action=='inspect':
            run("/usr/bin/python3 -c 'import pynq,sys,numpy,cv2; print(pynq.__version__,sys.version.split()[0],numpy.__version__,cv2.__version__)'",True)
            run("cat /proc/uptime")
            run("/usr/bin/python3 -c 'from pynq import PL; print(PL.bitfile_name)'",True)
            run("ps -eo pid,args | grep -E '[p]ython.*(run_board|static_test|live_demo)' || true")
            return
        if a.action in ('status','pins','release-sensors','bus-recovery'):
            # Read registers only; do not instantiate Overlay or reset a live app.
            manifest=json.loads((ROOT/'software/board/build_manifest.json').read_text())
            base=int(manifest['metadata']['control_base'],0)
            script=("from pynq import MMIO,PL; import json,os; "
                    "assert os.path.dirname(PL.bitfile_name or '')=="+repr(REMOTE+'/board')+", 'Expected overlay is not loaded; do not read inactive AXI'; "
                    "m=MMIO("+str(base)+",4096); "
                    "print(json.dumps({hex(a):m.read(a) for a in (0,4,0x1c,0x20,0x24,0x3c,0x40,0x50,0x54,0x58,0x5c,0x60)}))")
            if a.action in ('release-sensors','bus-recovery'):
                guard="import os\nfor pid in os.listdir('/proc'):\n if pid.isdigit():\n  try:\n   argv=open('/proc/'+pid+'/cmdline','rb').read().split(b'\\0')\n  except OSError: continue\n  if any(os.path.basename(v.decode(errors='replace'))=='run_board.py' for v in argv): raise RuntimeError('Stop run_board.py before releasing sensor GPIO')\n"
                script=guard+"from pynq import MMIO,PL\nimport time,json\nassert os.path.dirname(PL.bitfile_name or '')=="+repr(REMOTE+'/board')+"\nm=MMIO("+str(base)+",4096)\nassert m.read(0)==0x56410400\nbefore=m.read(0x3c)\nm.write(0x3c,before|12)\ntime.sleep(0.01)\nprint(json.dumps({'before_output':before,'released_output':m.read(0x3c),'input':m.read(0x40)}))"
                if a.action=='bus-recovery':
                    remote_report=REMOTE+'/logs/bus_recovery_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.json'
                    script=guard+(
                        "from pynq import MMIO,PL\nimport time,json,sys\n"
                        "sys.path.insert(0,"+repr(REMOTE)+")\n"
                        "from visual_aid.bus import GPIO,I2CBus\nfrom visual_aid.integrity import verify_payload\n"
                        "manifest=verify_payload("+repr(REMOTE)+")\n"
                        "assert os.path.dirname(PL.bitfile_name or '')=="+repr(REMOTE+'/board')+"\n"
                        "m=MMIO("+str(base)+",4096)\nassert m.read(0)==0x56410400\n"
                        "result={'stage':'bus-recovery','release':{'built_at':manifest['built_at'],'abi':hex(manifest['abi'])},"
                        "'before_output':m.read(0x3c),'before_input':m.read(0x40)}\n"
                        "try:\n I2CBus(GPIO(m),2,3).transfer(0x23,b'\\x01')\n result['transfer']='acknowledged'\n"
                        "except Exception as exc:\n result['transfer']='error';result['error']=type(exc).__name__+': '+str(exc)\n"
                        "time.sleep(0.01)\nresult.update(after_output=m.read(0x3c),after_input=m.read(0x40))\n"
                        "result['outcome']='passed' if result['after_output']&12==12 else 'error'\n"
                        "result['bus_released']=result['after_output']&12==12\n"
                        "result['sensor_communication_verified']=result['transfer']=='acknowledged'\n"
                        "open("+repr(remote_report)+",'w').write(json.dumps(result,indent=2))\nprint(json.dumps(result,indent=2))\n"
                        "raise SystemExit(0 if result['bus_released'] else 1)\n")
                run('/usr/bin/python3 -c '+shlex.quote(script),True)
                if a.action=='bus-recovery':
                    with client.open_sftp() as recovery_sftp:
                        recovery_sftp.get(remote_report,str(ROOT/'reports/board_validation_20261022'/Path(remote_report).name))
                return
            if a.action=='pins':
                remote_report=REMOTE+'/logs/pin_probe_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.json'
                script=("from pynq import MMIO,PL\nimport json,os,time\n"
                        "assert os.path.dirname(PL.bitfile_name or '')=="+repr(REMOTE+'/board')+"\n"
                        "m=MMIO("+str(base)+",4096)\nassert m.read(0)==0x56410400\n"
                        "samples=[]; start=time.monotonic(); previous=None\nprint('INPUT PROBE READY',flush=True)\n"
                        "while time.monotonic()-start<"+str(a.seconds)+":\n"
                        " current={'gpio_input':m.read(0x40),'gpio_output':m.read(0x3c),'encoder_status':m.read(0x54)}\n"
                        " if current!=previous:\n"
                        "  item=dict(current,t=time.monotonic()-start);samples.append(item);print(json.dumps(item),flush=True);previous=current\n"
                        " time.sleep(0.005)\n"
                        "open("+repr(remote_report)+",'w').write(json.dumps({'stage':'pins','outcome':'completed','samples':samples},indent=2))\n")
                run('/usr/bin/python3 -c '+shlex.quote(script),True)
                with client.open_sftp() as probe_sftp:
                    probe_sftp.get(remote_report,str(ROOT/'reports/board_validation_20261022'/Path(remote_report).name))
                return
            run('/usr/bin/python3 -c '+shlex.quote(script),True)
            return
        # Refuse to load any overlay while a separate camera/display app runs.
        script="import os; found=[]\nfor pid in os.listdir('/proc'):\n if pid.isdigit():\n  try:\n   argv=open('/proc/'+pid+'/cmdline','rb').read().split(b'\\0')\n   if any(os.path.basename(v.decode(errors='replace')) in ('run_board.py','static_test.py','live_demo.py','board_pl_exercise.py') for v in argv): found.append(pid)\n  except OSError: pass\nprint('Competing processes:',found); raise SystemExit(bool(found))"
        run('/usr/bin/python3 -c '+shlex.quote(script))
        sftp=client.open_sftp()
        try:
            if a.action=='demo-start':
                report=REMOTE+'/logs/live_active_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.json'
                args=['systemd-run','--unit=visual-aid-v4-demo','--property=KillSignal=SIGINT','--property=TimeoutStopSec=10',
                      '/usr/bin/python3','-u',REMOTE+'/run_board.py','--stage','live','--seconds','0',
                      '--camera-fps',str(a.camera_fps),'--mode','color','--sharp-mode','guided',
                      '--quality-preset',a.quality_preset,
                      '--no-sensors','--af','continuous','--io-confirmed','--report',report]
                with sftp.open(REMOTE+'/board/build_manifest.json') as manifest_file:
                    if json.load(manifest_file).get('pl_features'):args+=['--pipeline',a.pipeline]
                run(' '.join(shlex.quote(v) for v in args),True)
                print('Started continuous-AF demo; transient service stops on reboot. Report on exit:',report)
                return
            if a.action=='diagnostic':
                if not a.script or not a.script.is_file():raise ValueError('Diagnostic script required')
                if a.script.name=='board_native_build.py':
                    try:sftp.mkdir(REMOTE+'/native')
                    except IOError:pass
                    sftp.put(str(ROOT/'software/native/compose.c'),REMOTE+'/native/compose.c')
                    for name in ('chroma.py','fastcompose.py'):
                        sftp.put(str(ROOT/'software/visual_aid'/name),REMOTE+'/visual_aid/'+name)
                target=REMOTE+'/'+a.script.name
                sftp.put(str(a.script),target)
                try:
                    run('/usr/bin/python3 -u '+shlex.quote(target),True)
                    if a.script.name=='board_native_build.py':
                        sftp.get(REMOTE+'/native/libcompose.so',str(ROOT/'software/native/libcompose.so'))
                finally:
                    result=ROOT/'reports/performance';result.mkdir(exist_ok=True)
                    for name in sftp.listdir(REMOTE+'/logs'):
                        if name.startswith('performance_'):
                            sftp.get(REMOTE+'/logs/'+name,str(result/name))
                return
            if a.action=='light-probe':
                remote_report=REMOTE+'/logs/light_probe_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.json'
                script=("import sys,json,time,os\nfrom pynq import PL\n"
                        "sys.path.insert(0,"+repr(REMOTE)+")\nfrom visual_aid.integrity import verify_payload\n"
                        "from visual_aid.device import Device\nfrom visual_aid.bus import GPIO,I2CBus\nfrom visual_aid.sensors import BH1750\n"
                        "manifest=verify_payload("+repr(REMOTE)+")\ndev=Device("+repr(REMOTE+'/board/visual_aid_v3.bit')+",display=False,capture=False)\n"
                        "gpio=GPIO(dev.mmio);bus=I2CBus(gpio,2,3)\n"
                        "result={'stage':'light-probe','release':{'built_at':manifest['built_at'],'abi':hex(manifest['abi'])},"
                        "'boot_id':open('/proc/sys/kernel/random/boot_id').read().strip(),'uptime':open('/proc/uptime').read().strip(),"
                        "'before_input':dev.mmio.read(0x40),'addresses':{},'counters_before':dev.counters()}\n"
                        "for address in (0x23,0x5c):\n"
                        " try:\n"
                        "  assert PL.bitfile_name=="+repr(REMOTE+'/board/visual_aid_v3.bit')+"\n"
                        "  driver=BH1750(bus,address);time.sleep(0.2)\n"
                        "  values=[]\n  for i in range(3):\n   values.append(driver.read());time.sleep(0.2)\n"
                        "  result['addresses'][hex(address)]={'acknowledged':True,'lux':values}\n"
                        " except Exception as exc:\n  result['addresses'][hex(address)]={'acknowledged':False,'error':type(exc).__name__+': '+str(exc)}\n"
                        "result['loaded_overlay_after']=PL.bitfile_name\n"
                        "assert PL.bitfile_name=="+repr(REMOTE+'/board/visual_aid_v3.bit')+"\n"
                        "result.update(after_input=dev.mmio.read(0x40),after_output=dev.mmio.read(0x3c),counters_after=dev.counters())\n"
                        "dev.close()\nresult['outcome']='passed' if any(v['acknowledged'] for v in result['addresses'].values()) else 'no_sensor_ack'\n"
                        "with open("+repr(remote_report)+",'w') as report:\n report.write(json.dumps(result,indent=2));report.flush();os.fsync(report.fileno())\nprint(json.dumps(result,indent=2),flush=True)\n")
                run('/usr/bin/python3 -c '+shlex.quote(script),True)
                sftp.get(remote_report,str(ROOT/'reports/board_validation_20261022'/Path(remote_report).name))
                return
            if a.action=='base-pmod':
                remote_report=REMOTE+'/logs/base_pmod_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.json'
                script=("import json,os,time\nfrom pynq import PL\nfrom pynq.overlays.base import BaseOverlay\nfrom pynq.lib import Pmod_IO\n"
                        "assert PL.bitfile_name=="+repr('/usr/local/lib/python3.6/dist-packages/pynq/overlays/base/base.bit')+", 'Base overlay must already be loaded'\n"
                        "base=BaseOverlay('base.bit',download=False)\nscl=Pmod_IO(base.PMODB,2,'in');sda=Pmod_IO(base.PMODB,3,'in')\n"
                        "samples=[]\nfor i in range(10):\n samples.append({'scl':scl.read(),'sda':sda.read()});time.sleep(0.01)\n"
                        "result={'stage':'base-pmod','outcome':'passed' if all(v['scl']==1 and v['sda']==1 for v in samples) else 'error',"
                        "'scl_physical_pin':3,'sda_physical_pin':4,'samples':samples,'uptime':open('/proc/uptime').read().strip(),'boot_id':open('/proc/sys/kernel/random/boot_id').read().strip()}\n"
                        "with open("+repr(remote_report)+",'w') as report:\n report.write(json.dumps(result,indent=2));report.flush();os.fsync(report.fileno())\n"
                        "print(json.dumps(result,indent=2),flush=True)\n")
                run('/usr/bin/python3 -c '+shlex.quote(script),True)
                sftp.get(remote_report,str(ROOT/'reports/board_validation_20261022'/Path(remote_report).name))
                return
            if a.action=='pad-test':
                remote_report=REMOTE+'/logs/pad_test_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.json'
                script=("import sys,json,time,os\nfrom pynq import Overlay,MMIO\n"
                        "sys.path.insert(0,"+repr(REMOTE)+")\nfrom visual_aid.integrity import verify_payload\n"
                        "from visual_aid.startup import wait_for_boot_overlay\nwait_for_boot_overlay()\n"
                        "manifest=verify_payload("+repr(REMOTE)+")\n"
                        "assert manifest.get('sensor_wiring',{}).get('scl_package_pin')=='T11' and manifest.get('sensor_wiring',{}).get('sda_package_pin')=='T10', 'PMOD B bundle required for this empty-port test'\n"
                        "ol=Overlay("+repr(REMOTE+'/board/visual_aid_v3.bit')+")\n"
                        "m=MMIO(int(manifest['metadata']['control_base'],0),4096)\n"
                        "assert m.read(0)==0x56410400\noriginal=m.read(0x3c)\nbase=original|12\n"
                        "result={'stage':'pad-test','release':{'built_at':manifest['built_at'],'abi':hex(manifest['abi'])},"
                        "'wiring':manifest.get('sensor_wiring',{}),'samples':[],'boot_id':open('/proc/sys/kernel/random/boot_id').read().strip()}\n"
                        "try:\n"
                        " for name,output in [('released',base),('scl_low',base&~4),('sda_low',base&~8),('both_low',base&~12),('released_again',base)]:\n"
                        "  m.write(0x3c,output);time.sleep(0.02);value=m.read(0x40)\n"
                        "  item={'state':name,'output':m.read(0x3c),'input':value,'expected_sensor_inputs':output&12,'passed':value&12==output&12}\n"
                        "  result['samples'].append(item);print(json.dumps(item),flush=True)\n"
                        "finally:\n m.write(0x3c,base)\n"
                        "result['outcome']='passed' if all(v['passed'] for v in result['samples']) else 'error'\n"
                        "result['sensor_communication_verified']=False\n"
                        "with open("+repr(remote_report)+",'w') as report:\n report.write(json.dumps(result,indent=2));report.flush();os.fsync(report.fileno())\n"
                        "print('PAD_TEST '+result['outcome'],flush=True)\nraise SystemExit(0 if result['outcome']=='passed' else 1)\n")
                try:
                    run('/usr/bin/python3 -c '+shlex.quote(script),True)
                finally:
                    sftp.get(remote_report,str(ROOT/'reports/board_validation_20261022'/Path(remote_report).name))
                return
            if a.action=='deploy':
                archive=a.archive.resolve() if a.archive else ROOT/'delivery/visual_aid_v4_ec11_board.zip'
                target='/home/xilinx/jupyter_notebooks/'+archive.name
                sftp.put(str(archive),target)
                # Board-side native compilation can leave a root-owned library.
                # Extraction and ownership repair are limited to this app folder.
                run('/usr/bin/python3 -m zipfile -e '+shlex.quote(target)+' /home/xilinx/jupyter_notebooks',True)
                run('chown -R xilinx:xilinx '+shlex.quote(REMOTE),True)
                run('/usr/bin/python3 '+shlex.quote(REMOTE+'/preflight.py'),True)
                print('DEPLOYED',REMOTE)
                return
            stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            report='logs/'+a.action+'_'+stamp+'.json'
            args=['/usr/bin/python3',REMOTE+'/run_board.py','--stage',a.action,'--seconds',str(a.seconds),
                  '--no-distance','--io-confirmed','--report',REMOTE+'/'+report]
            args+=['--camera-fps',str(a.camera_fps)]
            args+=['--quality-preset',a.quality_preset]
            args+=['--pipeline',a.pipeline]
            if a.no_sensors:args+=['--no-sensors']
            if a.action=='live':
                args+=['--mode','color','--sharp-mode','guided']
                args+=['--no-af'] if a.no_af else ['--af','continuous']
            try:
                run(' '.join(shlex.quote(v) for v in args),True)
            finally:
                out=ROOT/'reports/board_validation_20261022';out.mkdir(exist_ok=True)
                try:
                    sftp.get(REMOTE+'/'+report,str(out/Path(report).name))
                    r=json.loads((out/Path(report).name).read_text())
                    print('BOARD_RESULT',json.dumps({k:r.get(k) for k in ('stage','outcome','unique_camera_frames',
                          'measured_unique_capture_fps','counter_deltas','cleanup_errors','encoder_connected_verified')},indent=2))
                except IOError as exc:print('Report download unavailable:',str(exc),file=sys.stderr)
        finally:sftp.close()
    finally:client.close()


if __name__=='__main__':main()
