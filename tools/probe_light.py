"""Bounded open-drain pad and BH1750 address check on the loaded Arduino variant."""
from pathlib import Path
import os
import shlex
import socket
import warnings

warnings.filterwarnings('ignore')
import paramiko

REMOTE_CODE = r'''
import json,sys,time
from pathlib import Path
from pynq import MMIO,PL
root=Path('/home/xilinx/jupyter_notebooks/visual_aid_v4_camera_detail_20261028')
for p in Path('/proc').glob('[0-9]*/cmdline'):
 try:argv=p.read_bytes().split(b'\0')
 except OSError:continue
 if any(a.rsplit(b'/',1)[-1]==b'run_board.py' for a in argv):raise RuntimeError('Stop the project before probing')
sys.path.insert(0,str(root))
from visual_aid.bus import GPIO,I2CBus
from visual_aid.sensors import BH1750
from visual_aid.integrity import verify_payload
manifest=verify_payload(root)
assert str(Path(PL.bitfile_name).parent)==str(root/'board'),PL.bitfile_name
assert manifest['sensor_wiring']['scl_package_pin']=='P15'
assert manifest['sensor_wiring']['sda_package_pin']=='P16'
mm=MMIO(int(manifest['metadata']['control_base'],0),4096)
assert mm.read(0)==0x56410400
gpio=GPIO(mm)
result={'loaded_overlay':PL.bitfile_name,'wiring':manifest['sensor_wiring'],'pad_samples':[],'addresses':[]}
try:
 # Values of 1 release open-drain lines; no high level is actively driven.
 # Lower SCL before changing SDA, then finish with a STOP condition.
 for scl,sda in ((0,1),(0,0),(1,0),(1,1)):
  gpio.set(2,scl);gpio.set(3,sda);time.sleep(.02)
  result['pad_samples'].append({'requested_release':[scl,sda],'observed':[gpio.get(2),gpio.get(3)]})
 bus=I2CBus(gpio,2,3)
 for address in (0x23,0x5c):
  item={'address':hex(address)}
  try:
   sensor=BH1750(bus,address);time.sleep(.2)
   item.update(acknowledged=True,lux=sensor.read())
  except Exception as exc:item.update(acknowledged=False,error=type(exc).__name__+': '+str(exc))
  result['addresses'].append(item)
 if not any(item['acknowledged'] for item in result['addresses']):
  result['address_only_scan']={'acknowledged':[],'range':'0x08..0x77; address byte only, no command/data bytes'}
  for address in range(0x08,0x78):
   try:bus.transfer(address)
   except OSError:continue
   result['address_only_scan']['acknowledged'].append(hex(address))
finally:
 gpio.set(2,1);gpio.set(3,1)
result['final_released']=[gpio.get(2),gpio.get(3)]
print(json.dumps(result,indent=2))
'''


def main():
    client = paramiko.SSHClient(); client.load_system_host_keys()
    sock = socket.socket(); sock.settimeout(8)
    sock.bind(('192.168.2.1', 0)); sock.connect(('192.168.2.99', 22))
    password = os.environ.get('FPGA_BOARD_PASSWORD', 'xilinx')
    client.connect('192.168.2.99', username='xilinx', password=password, sock=sock,
                   look_for_keys=False, allow_agent=False, timeout=8, banner_timeout=8, auth_timeout=8)
    try:
        inp, out, err = client.exec_command('sudo -S -p "" /usr/bin/python3 -c '+shlex.quote(REMOTE_CODE), timeout=30)
        inp.write(password+'\n'); inp.flush(); inp.close()
        output = out.read().decode(); errors = err.read().decode()
        code = out.channel.recv_exit_status()
        print(output)
        if code: raise RuntimeError(errors)
        path = Path(__file__).resolve().parents[1]/'reports/light_pad_address_probe.json'
        path.write_text(output, encoding='utf-8')
    finally:
        client.close()


if __name__ == '__main__':
    main()
