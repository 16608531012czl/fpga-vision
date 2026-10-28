from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import os
import shlex
import socket
import warnings
import argparse

warnings.filterwarnings('ignore')
import paramiko

ROOT = Path(__file__).resolve().parents[1] / 'reports' / 'board_validation_20261028'
ROOT.mkdir(parents=True, exist_ok=True)
REMOTE = '/home/xilinx/jupyter_notebooks/visual_aid_v4_camera_detail_20261028'
parser = argparse.ArgumentParser()
parser.add_argument('--stage', choices=('sensors','live'), default='sensors')
parser.add_argument('--seconds', type=int, default=60)
options = parser.parse_args()
TAG = options.stage + '_light_' + datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')

SUPERVISOR = r'''
import json, os, signal, subprocess, sys, time
from pathlib import Path
root=Path(sys.argv[1]); tag=sys.argv[2]; stage=sys.argv[3]; seconds=int(sys.argv[4])
os.chdir(str(root)); (root/'logs').mkdir(exist_ok=True)
for process in Path('/proc').glob('[0-9]*/cmdline'):
    try: args=process.read_bytes().split(b'\0')
    except OSError: continue
    if any(a.rsplit(b'/',1)[-1]==b'run_board.py' for a in args):
        raise RuntimeError('An existing run_board.py process must finish before validation')
manifest=json.loads((root/'board/build_manifest.json').read_text())
assert manifest['sensor_wiring']['scl_package_pin']=='P15'
assert manifest['sensor_wiring']['sda_package_pin']=='P16'
log=root/'logs'/(tag+'.log'); report=root/'logs'/(tag+'.json')
guard_path=root/'logs'/(tag+'_guard.json')
temp_raw=next(Path('/sys/bus/iio/devices').glob('iio:device*/in_temp0_raw'))
temp_stem=str(temp_raw)[:-4]
def temperature():
    return (float(temp_raw.read_text())+float(Path(temp_stem+'_offset').read_text()))*float(Path(temp_stem+'_scale').read_text())/1000
guard={'temperature_limit_c':75.0,'wall_timeout_seconds':seconds+120,'samples':[],
       'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
       'project_report':str(report),'abort_reason':None}
initial=temperature()
if initial>=75:
    raise RuntimeError('Initial temperature exceeds validation limit: '+str(initial))
cmd=['/usr/bin/python3','-u','run_board.py','--stage',stage,'--pipeline','pl',
     '--camera-fps','20','--mode','color','--quality-preset','detail','--camera-isp','detail',
     '--no-distance','--af','continuous','--io-confirmed','--seconds',str(seconds),
     '--report',str(report)]
guard['command']=cmd
start=time.monotonic(); last_notice=-10; child=None; read_pos=0
def emit_progress():
    global read_pos
    with log.open() as f:
        f.seek(read_pos); lines=f.readlines();read_pos=f.tell()
    for line in lines:
        line=line.strip()
        if not line:continue
        if line.startswith('AF') or line.startswith('REPORT'):
            print(line,flush=True);continue
        try:
            item=json.loads(line)
            if 'rolling_unique_capture_fps' in item:
                print('FRAME '+json.dumps({k:item[k] for k in ('t','rolling_unique_capture_fps','counters','sensors','tone') if k in item}),flush=True)
            elif 'sensors' in item:
                print('SENSOR '+json.dumps(item),flush=True)
        except ValueError:
            print('APP '+line[:500],flush=True)
try:
    with log.open('w') as output:
        child=subprocess.Popen(cmd,stdout=output,stderr=subprocess.STDOUT)
        guard['pid']=child.pid
        print('START '+json.dumps({'pid':child.pid,'tag':tag,'temperature_c':initial}),flush=True)
        while child.poll() is None:
            elapsed=time.monotonic()-start
            try:temp=temperature()
            except Exception as exc:
                guard['abort_reason']='temperature_read_failed: '+str(exc);break
            guard['samples'].append({'elapsed_s':round(elapsed,2),'temperature_c':round(temp,2)})
            if temp>=75:guard['abort_reason']='temperature_limit';break
            if elapsed>seconds+120:guard['abort_reason']='wall_timeout';break
            if elapsed-last_notice>=10:
                print('HEALTH '+json.dumps(guard['samples'][-1]),flush=True)
                emit_progress();last_notice=elapsed
            time.sleep(2)
        if guard['abort_reason']:
            child.send_signal(signal.SIGINT)
            try:child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                child.terminate()
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
        guard['returncode']=child.wait()
finally:
    if child is not None and child.poll() is None:
        child.send_signal(signal.SIGINT)
        try:child.wait(timeout=8)
        except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
    guard['elapsed_s']=round(time.monotonic()-start,2)
    guard['boot_id_after']=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    try:guard['final_temperature_c']=round(temperature(),2)
    except Exception as exc:guard['final_temperature_error']=str(exc)
    guard_path.write_text(json.dumps(guard,indent=2))
    if log.exists():emit_progress()
    print('GUARD '+json.dumps(guard),flush=True)
    if report.exists():
        result=json.loads(report.read_text())
        keys=('outcome','error','camera','autofocus','autofocus_after','unique_camera_frames','measured_unique_capture_fps','counter_deltas','cleanup_errors','warnings','rendered_frames','measured_render_fps','display_observed')
        print('RESULT '+json.dumps({k:result[k] for k in keys if k in result}),flush=True)
sys.exit(0 if guard.get('returncode')==0 and not guard['abort_reason'] else 1)
'''


def main():
    password = os.environ.get('FPGA_BOARD_PASSWORD', 'xilinx')
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    connection = socket.socket()
    connection.settimeout(10)
    connection.bind(('192.168.2.1', 0))
    connection.connect(('192.168.2.99', 22))
    client.connect('192.168.2.99', username='xilinx', password=password,
                   sock=connection, look_for_keys=False, allow_agent=False,
                   timeout=10, banner_timeout=10, auth_timeout=10)
    client.get_transport().set_keepalive(10)
    try:
        command = 'sudo -S -p "" /usr/bin/python3 -u -c ' + shlex.quote(SUPERVISOR)
        command += ' ' + shlex.quote(REMOTE) + ' ' + shlex.quote(TAG) + ' ' + options.stage + ' ' + str(options.seconds)
        inp, out, err = client.exec_command(command, timeout=options.seconds+150)
        inp.write(password + '\n'); inp.flush(); inp.close()
        with (ROOT / (TAG + '_console.log')).open('w', encoding='utf-8') as log:
            for line in iter(out.readline, ''):
                print(line, end='', flush=True)
                log.write(line); log.flush()
        errors = err.read().decode('utf-8', errors='replace')
        code = out.channel.recv_exit_status()
        with client.open_sftp() as sftp:
            for suffix in ('.json', '.log', '_guard.json'):
                try: sftp.get(REMOTE+'/logs/'+TAG+suffix, str(ROOT/(TAG+suffix)))
                except FileNotFoundError: pass
        metadata={'tag':TAG,'exit_code':code,'stderr':errors,'output_dir':str(ROOT)}
        (ROOT/'latest_run.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
        print('LOCAL '+json.dumps(metadata),flush=True)
        return code
    finally:
        client.close()


if __name__ == '__main__':
    raise SystemExit(main())
