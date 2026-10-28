"""Bounded, scene-controlled optical focus comparison using the UI release.

Actions: run (start); near/far (signal the prepared scene); collect (download
local evidence). The diagnostic shows an unenhanced camera preview temporarily.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse
import json
import os
import shlex
import socket
import warnings

warnings.filterwarnings('ignore')
import paramiko

ROOT = Path(__file__).resolve().parents[1]
REMOTE = '/home/xilinx/jupyter_notebooks/visual_aid_v4_camera_detail_20261028'
ACTIVE = ROOT/'reports/camera_focus_active.json'

BOARD_CODE = r'''
from pathlib import Path
import sys,os,time,json,signal,threading,traceback
import cv2,numpy as np
root=Path(sys.argv[1]);tag=sys.argv[2];sys.path.insert(0,str(root))
from visual_aid.device import Device
from visual_aid.bus import GPIO,I2CBus
from visual_aid.camera import OV5640
from visual_aid.integrity import verify_payload
for proc in Path('/proc').glob('[0-9]*/cmdline'):
 try:argv=proc.read_bytes().split(b'\0')
 except OSError:continue
 if any(a.rsplit(b'/',1)[-1]==b'run_board.py' for a in argv):raise RuntimeError('A live project is running')
manifest=verify_payload(root,root/'board/visual_aid_v3.bit')
assert manifest['sensor_wiring']['scl_package_pin']=='P15' and manifest['sensor_wiring']['sda_package_pin']=='P16'
out=root/'logs'/tag;out.mkdir(parents=True,exist_ok=False)
result={'tag':tag,'outcome':'running','boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'steps':[],'temperatures':[],'scene_confirmation':{},'abort_reason':None,'display':'raw diagnostic preview'}
stop=threading.Event();temp_raw=next(Path('/sys/bus/iio/devices').glob('iio:device*/in_temp0_raw'))
stem=str(temp_raw)[:-4]
def temperature():return (float(temp_raw.read_text())+float(Path(stem+'_offset').read_text()))*float(Path(stem+'_scale').read_text())/1000
initial_temp=temperature()
if initial_temp>=75:raise RuntimeError('Initial temperature exceeds test limit: '+str(initial_temp))
start=time.monotonic()
def guard():
 while not stop.wait(2):
  try:
   temp=temperature();result['temperatures'].append({'t':round(time.monotonic()-start,2),'c':round(temp,2)})
   if temp>=75:result['abort_reason']='temperature_limit';os.kill(os.getpid(),signal.SIGINT);return
   if time.monotonic()-start>450:result['abort_reason']='wall_timeout';os.kill(os.getpid(),signal.SIGINT);return
  except Exception as exc:
   result['abort_reason']='temperature_read_failed: '+str(exc);os.kill(os.getpid(),signal.SIGINT);return
threading.Thread(target=guard,daemon=True).start()
dev=None;cam=None;baseline=None
def progress(done,total):
 if done==0 or done==total or (done//32)%32==0:print('AF_UPLOAD '+str(done)+'/'+str(total),flush=True)
def stream_for(seconds):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  _,_,frame=dev.finish(rearm=True);dev.display(frame)
def wait_scene(scene):
 marker=Path('/tmp')/(tag+'_'+scene)
 print('WAIT_SCENE '+scene,flush=True);end=time.monotonic()+120
 while not marker.exists():
  if time.monotonic()>=end:raise TimeoutError('Scene not confirmed: '+scene)
  stream_for(.2)
 marker.unlink();result['scene_confirmation'][scene]=True
 print('SCENE_START '+scene,flush=True)
def capture(name):
 index,frame_id,frame=dev.finish(rearm=True)
 image=np.ascontiguousarray(frame[:,:,:3])
 dev.display(frame)
 path=out/(name+'.png')
 if not cv2.imwrite(str(path),image):raise IOError('Cannot save capture')
 gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
 # This proxy can rise with noise/sharpening and only compares the SAME scene.
 center=gray[144:576,256:1024]
 gx=cv2.Sobel(center,cv2.CV_32F,1,0,ksize=3);gy=cv2.Sobel(center,cv2.CV_32F,0,1,ksize=3)
 row={'capture':name,'frame_id':frame_id,'resolution':[1280,720],
      'center_laplacian_variance':float(cv2.Laplacian(center,cv2.CV_64F).var()),
      'center_gradient_energy':float(np.mean(gx*gx+gy*gy)),
      'mean_luma':float(np.mean(center)),'clip_black_fraction':float(np.mean(center<=3)),
      'clip_white_fraction':float(np.mean(center>=252)),
      'af':cam.autofocus_status(),
      'camera_registers':{hex(reg):cam.read(reg) for reg in (0x3500,0x3501,0x3502,0x350a,0x350b,0x5302,0x5308)}}
 result['steps'].append(row);print('CAPTURE '+json.dumps(row),flush=True)
def single_focus():
 cam._af_command(3,5);end=time.monotonic()+12;status=None
 while time.monotonic()<end:
  stream_for(.35);status=cam.autofocus_status()
  if status['firmware_focus_reported']:break
 result['steps'].append({'operation':'single_focus','status':status})
 print('FOCUS '+json.dumps(status),flush=True)
 if status and status['firmware_focus_reported']:
  cam._af_command(6,5);result['steps'].append({'operation':'focus_hold','acknowledged':True})
 stream_for(1)
def scene_run(scene,try_isp):
 stream_for(4);capture(scene+'_continuous')
 single_focus();capture(scene+'_single')
 if try_isp:
  quality=cam.image_quality('detail');result['steps'].append({'operation':'temporary_isp_detail','registers':quality})
  stream_for(2);capture(scene+'_isp_detail')
  for reg,value in baseline.items():cam.write(reg,value)
  assert all(cam.read(reg)==value for reg,value in baseline.items())
  stream_for(1);capture(scene+'_restored')
 cam._af_command(4,5);result['steps'].append({'operation':'resume_continuous','acknowledged':True})
 print('SCENE_DONE '+scene,flush=True)
try:
 print('INIT '+json.dumps({'temperature_c':initial_temp,'tag':tag}),flush=True)
 dev=Device(str(root/'board/visual_aid_v3.bit'),display=True,capture=True)
 dev.mmio.write(4,0);dev.mmio.write(0x78,0)
 gpio=GPIO(dev.mmio);cam=OV5640(I2CBus(gpio,0,1),gpio)
 result['camera']=cam.initialize(fps=20)
 result['image_quality']=cam.image_quality('baseline');result['exposure']=cam.stable_exposure()
 baseline={reg:cam.read(reg) for reg in (0x5000,0x5001,0x5308,0x5302,0x530b)}
 result['baseline_registers']={hex(k):v for k,v in baseline.items()}
 result['initial_af']=cam.autofocus(True,progress=progress)
 dev.mmio.write(4,1);time.sleep(.2);dev.arm(0)
 wait_scene('near');scene_run('near',True)
 wait_scene('far');scene_run('far',False)
 result['outcome']='completed'
except BaseException as exc:
 result['outcome']='interrupted' if isinstance(exc,KeyboardInterrupt) else 'error'
 result['error']=type(exc).__name__+': '+str(exc);traceback.print_exc()
finally:
 if cam is not None and baseline is not None:
  try:
   for reg,value in baseline.items():cam.write(reg,value)
   result['baseline_registers_restored']=all(cam.read(reg)==value for reg,value in baseline.items())
  except BaseException as exc:result['restore_error']=str(exc)
 if dev is not None:
  try:result['final_counters']=dev.counters();dev.close()
  except BaseException as exc:result['cleanup_error']=str(exc)
 stop.set();result['elapsed_seconds']=round(time.monotonic()-start,2)
 result['boot_id_after']=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 (out/'result.json').write_text(json.dumps(result,indent=2))
 print('RESULT '+json.dumps(result),flush=True)
sys.exit(0 if result['outcome']=='completed' and not result.get('cleanup_error') else 1)
'''


def connect():
    client = paramiko.SSHClient(); client.load_system_host_keys()
    sock = socket.socket(); sock.settimeout(8)
    sock.bind(('192.168.2.1', 0)); sock.connect(('192.168.2.99', 22))
    password = os.environ.get('FPGA_BOARD_PASSWORD', 'xilinx')
    client.connect('192.168.2.99', username='xilinx', password=password, sock=sock,
                   look_for_keys=False, allow_agent=False, timeout=8, banner_timeout=8, auth_timeout=8)
    client.get_transport().set_keepalive(10)
    return client, password


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('run', 'near', 'far', 'collect'))
    args = parser.parse_args()
    client, password = connect()
    try:
        if args.action == 'run':
            tag='focus_compare_'+datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
            ACTIVE.write_text(json.dumps({'tag':tag},indent=2),encoding='utf-8')
            path='/tmp/'+tag+'.py'
            with client.open_sftp() as sftp:
                with sftp.open(path, 'w') as remote: remote.write(BOARD_CODE)
            command='sudo -S -p "" /usr/bin/python3 -u '+shlex.quote(path)+' '+shlex.quote(REMOTE)+' '+shlex.quote(tag)
            inp,out,err=client.exec_command(command,timeout=480)
            inp.write(password+'\n');inp.flush();inp.close()
            for line in iter(out.readline,''):print(line,end='',flush=True)
            errors=err.read().decode('utf-8',errors='replace');code=out.channel.recv_exit_status()
            if code:print('REMOTE_ERROR '+errors,flush=True)
            return code
        tag=json.loads(ACTIVE.read_text())['tag']
        with client.open_sftp() as sftp:
            if args.action in ('near','far'):
                with sftp.open('/tmp/'+tag+'_'+args.action,'w') as marker:marker.write('scene confirmed\n')
                print('Signalled scene:',args.action)
            else:
                remote_dir=REMOTE+'/logs/'+tag;local=ROOT/'reports'/tag;local.mkdir(exist_ok=True)
                for name in sftp.listdir(remote_dir):
                    if name.endswith(('.png','.json')):sftp.get(remote_dir+'/'+name,str(local/name))
                print('Collected:',local)
        return 0
    finally:client.close()


if __name__ == '__main__':
    raise SystemExit(main())
