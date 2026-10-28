"""Board-side supervisor for the Jupyter button panel, Python 3.6 compatible."""
from pathlib import Path
import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time

ROOT = Path('/home/xilinx/jupyter_notebooks/visual_aid_v4_camera_detail_20261028')
LOGS = ROOT/'logs'
STATE = LOGS/'jupyter_control_state.json'
LOCK = Path('/tmp/pynq_visual_aid_jupyter_control.lock')
LIMIT_C = 75.0


def run_seconds(value):
    try: seconds = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError('seconds must be a non-negative integer')
    if seconds < 0:
        raise argparse.ArgumentTypeError('seconds must be a non-negative integer')
    return seconds


def temperature():
    raw = next(Path('/sys/bus/iio/devices').glob('iio:device*/in_temp0_raw'))
    stem = str(raw)[:-4]
    return (float(raw.read_text()) + float(Path(stem+'_offset').read_text())) * float(Path(stem+'_scale').read_text()) / 1000


def start_ticks(pid):
    text = Path('/proc/{}/stat'.format(pid)).read_text()
    return int(text[text.rfind(')')+2:].split()[19])


def other_project_pids():
    found = []
    for proc in Path('/proc').glob('[0-9]*/cmdline'):
        try: args = proc.read_bytes().split(b'\0')
        except OSError: continue
        if any(a.rsplit(b'/', 1)[-1] == b'run_board.py' for a in args):
            found.append(int(proc.parent.name))
    return found


def save(state):
    tmp = STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, indent=2), encoding='utf-8')
    os.replace(str(tmp), str(STATE))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--isp', choices=('detail', 'baseline'), default='detail')
    parser.add_argument('--seconds', type=run_seconds, default=0,
                        help='Live duration in seconds after camera initialization; 0 runs until stopped')
    args = parser.parse_args()
    LOGS.mkdir(parents=True, exist_ok=True)
    lock = LOCK.open('w')
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError: return 2
    tag = time.strftime('jupyter_%Y%m%d_%H%M%S')
    state = {'phase':'starting', 'guard_pid':os.getpid(), 'guard_start_ticks':start_ticks(os.getpid()),
             'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
             'isp':args.isp, 'seconds':args.seconds, 'temperature_limit_c':LIMIT_C,
             'log':str(LOGS/(tag+'.log')), 'report':str(LOGS/(tag+'.json')),
             'reason':None, 'temperature_c':None}
    save(state)
    stop = [False]
    def on_stop(signum, frame): stop[0] = True
    signal.signal(signal.SIGINT, on_stop);signal.signal(signal.SIGTERM, on_stop)
    child = None
    try:
        if os.geteuid() != 0: raise RuntimeError('Jupyter kernel must run as root')
        os.chdir(str(ROOT));sys.path.insert(0,str(ROOT))
        from visual_aid.integrity import verify_payload
        manifest=verify_payload(ROOT, ROOT/'board/visual_aid_v3.bit')
        wiring=manifest['sensor_wiring']
        if (wiring['scl_package_pin'],wiring['sda_package_pin']) != ('P15','P16'):
            raise RuntimeError('Camera release wiring does not match Arduino sensor pins')
        existing=other_project_pids()
        if existing: raise RuntimeError('Another project is already running: '+str(existing))
        initial=temperature();state['temperature_c']=round(initial,2)
        if initial>=LIMIT_C:raise RuntimeError('Board temperature exceeds 75 C')
        cmd=['/usr/bin/python3','-u',str(ROOT/'run_board.py'), '--stage','live', '--pipeline','pl',
             '--camera-fps','20','--mode','color','--quality-preset','detail',
             '--camera-isp',args.isp,'--tone-profile','stable','--no-distance',
             '--af','continuous','--io-confirmed','--seconds',str(args.seconds), '--report',state['report']]
        with open(state['log'],'w',encoding='utf-8') as output:
            child=subprocess.Popen(cmd,cwd=str(ROOT),stdout=output,stderr=subprocess.STDOUT)
            state.update(phase='running',child_pid=child.pid);save(state)
            while child.poll() is None:
                if stop[0]:state['reason']='user_stop';break
                try:state['temperature_c']=round(temperature(),2)
                except Exception as exc:
                    state['reason']='temperature_read_failed: '+str(exc);break
                if state['temperature_c']>=LIMIT_C:state['reason']='temperature_limit';break
                save(state);time.sleep(2)
            if state['reason']:
                state['phase']='stopping';save(state)
                child.send_signal(signal.SIGINT)
                try:child.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    child.terminate()
                    try:child.wait(timeout=5)
                    except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
            state['exit_code']=child.wait()
        if state['reason']=='user_stop':state['phase']='stopped'
        elif state['reason']:state['phase']='error'
        elif state['exit_code']==0:state['phase']='completed'
        else:state['phase']='error';state['reason']='project_exit_{}'.format(state['exit_code'])
        report=Path(state['report'])
        if report.is_file():
            data=json.loads(report.read_text())
            state['report_outcome']=data.get('outcome')
            state['cleanup_errors']=data.get('cleanup_errors',[])
            if state['cleanup_errors']:state['phase']='error';state['reason']='cleanup_error'
            if data.get('outcome') not in ('completed','interrupted'):
                state['phase']='error';state['reason']=data.get('error','project_report_error')
    except BaseException as exc:
        state['phase']='error';state['reason']=type(exc).__name__+': '+str(exc)
        if child is not None and child.poll() is None:
            child.send_signal(signal.SIGINT)
            try:child.wait(timeout=12)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
    finally:
        try:state['temperature_c']=round(temperature(),2)
        except Exception:pass
        state['finished_at']=time.strftime('%Y-%m-%d %H:%M:%S')
        save(state);fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
    return 0 if state['phase'] in ('completed','stopped') else 1


if __name__ == '__main__':
    raise SystemExit(main())
