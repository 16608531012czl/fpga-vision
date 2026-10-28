"""Bounded OV5640 documented clock/drive diagnostic; no changes to saved payload."""
from pathlib import Path
import time,json
from visual_aid.device import Device
from visual_aid.bus import GPIO,I2CBus
from visual_aid.camera import OV5640
from visual_aid.integrity import verify_payload
base=Path(__file__).resolve().parent
manifest=verify_payload(base)
assert manifest.get('capture_diagnostic_register')=='0x64'
dev=Device(str(base/'board/visual_aid_v3.bit'))
gpio=GPIO(dev.mmio);cam=OV5640(I2CBus(gpio),gpio)
rows=[]
try:
 cam.initialize(fps=15)
 for divider,multiplier in [(0x21,105),(0x21,84),(0x21,77),(0x31,105),(0x21,63),(0x41,105)]:
  polarity,drive=0x20,0xc3
  dev.mmio.write(4,0);time.sleep(.02);assert not(dev.mmio.read(0x18)&1);dev.armed=None
  cam.write(0x3035,divider);cam.write(0x3036,multiplier);cam.write(0x302c,drive);cam.write(0x4740,polarity);time.sleep(.25)
  dev.mmio.write(4,1);time.sleep(.25);before=dev.counters();t0=time.monotonic();time.sleep(1);after=dev.counters()
  row={'multiplier':multiplier,'polarity':polarity,'divider':hex(divider),'drive':hex(drive),'elapsed':time.monotonic()-t0,
       'deltas':{k:(after[k]-before[k])&0xffffffff for k in after}}
  word=dev.mmio.read(0x64)
  row['geometry']={'raw':hex(word),'good':bool(word&(1<<26)),'reason':(word>>23)&7,'line':(word>>12)&2047,'pixels':word&4095}
  if row['deltas']['malformed_frames']==0:
   try:
    dev.arm(0);ts=[]
    for i in range(10):
     dev.finish(rearm=i<9);ts.append(time.monotonic())
    row['capture_fps']=9/(ts[-1]-ts[0])
   except Exception as exc:row['error']=str(exc)
  rows.append(row);print(json.dumps(row),flush=True)
finally:
 dev.close()
 (base/'logs'/('performance_camera_sweep_'+time.strftime('%Y%m%d_%H%M%S')+'.json')).write_text(json.dumps(rows,indent=2))
