"""Lower-clock 720p line-blanking experiment; never changes saved profiles."""
from pathlib import Path
import json,time
from visual_aid.device import Device
from visual_aid.bus import GPIO,I2CBus
from visual_aid.camera import OV5640
from visual_aid.integrity import verify_payload
base=Path(__file__).resolve().parent
release=verify_payload(base);rows=[]
for hts in (1680,1577,1493,1419,1351,1290):
 dev=None;row={'hts':hts,'nominal_fps':21000000/hts/740,'release':release['built_at']}
 try:
  dev=Device(str(base/'board/visual_aid_v3.bit'))
  gpio=GPIO(dev.mmio);cam=OV5640(I2CBus(gpio),gpio);cam.initialize(fps=15)
  dev.mmio.write(4,0);time.sleep(.02)
  cam.write(0x380c,hts>>8);cam.write(0x380d,hts&255)
  row['timing']=cam.configure_timing(15)
  time.sleep(.4);dev.mmio.write(4,1);time.sleep(.4)
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
(base/'logs'/('performance_hts_'+time.strftime('%Y%m%d_%H%M%S')+'.json')).write_text(json.dumps(rows,indent=2))
