"""Bounded manual DVP-clock divider diagnostic; reset/verify each candidate."""
from pathlib import Path
import json,time
from visual_aid.device import Device
from visual_aid.bus import GPIO,I2CBus
from visual_aid.camera import OV5640
from visual_aid.integrity import verify_payload
base=Path(__file__).resolve().parent
release=verify_payload(base)
rows=[]
for fps,divider in ((30,4),(30,5),(30,6),(24,5),(20,5),(20,6),(18,0)):
 dev=None
 row={'requested_fps':fps,'dvp_manual_divider':divider,'release':release['built_at']}
 try:
  dev=Device(str(base/'board/visual_aid_v3.bit'))
  gpio=GPIO(dev.mmio);cam=OV5640(I2CBus(gpio),gpio)
  cam.initialize(fps=15)
  dev.mmio.write(4,0);time.sleep(.02)
  if fps==18:
   cam.write(0x3035,0x21);cam.write(0x3036,63)
  else:cam.configure_timing(fps)
  if divider:
   cam.write(0x3824,divider);cam.write(0x460c,cam.read(0x460c)|2)
  row['registers']={hex(a):cam.read(a) for a in (0x3035,0x3036,0x460c,0x3824,0x4740)}
  time.sleep(.4);dev.mmio.write(4,1);time.sleep(.3)
  before=dev.counters();started=time.monotonic();time.sleep(2);after=dev.counters()
  row['deltas']={k:(after[k]-before[k])&0xffffffff for k in after}
  row['elapsed']=time.monotonic()-started
  word=dev.mmio.read(0x64)
  row['geometry']={'raw':hex(word),'good':bool(word&(1<<26)),
                   'reason':(word>>23)&7,'line':(word>>12)&2047,'pixels':word&4095}
  if row['deltas']['camera_vsync'] and not row['deltas']['malformed_frames']:
   dev.arm(0);times=[]
   for n in range(30):
    dev.finish(rearm=n<29);times.append(time.monotonic())
   row['capture_fps']=29/(times[-1]-times[0])
 except Exception as exc:row['error']=type(exc).__name__+': '+str(exc)
 finally:
  if dev:dev.close()
 rows.append(row);print(json.dumps(row),flush=True)
(base/'logs'/('performance_divider_'+time.strftime('%Y%m%d_%H%M%S')+'.json')).write_text(json.dumps(rows,indent=2))
