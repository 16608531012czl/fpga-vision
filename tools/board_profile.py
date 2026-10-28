"""Run on the board only: bounded capture and CPU profiling, no light sensor."""
from pathlib import Path
import time,json,cProfile,pstats,io
import numpy as np
import cv2
from visual_aid.device import Device
from visual_aid.bus import GPIO,I2CBus
from visual_aid.camera import OV5640
from visual_aid.image import compose,AdaptivePolicy
from visual_aid.integrity import verify_payload

base=Path(__file__).resolve().parent
result={'release':verify_payload(base)['built_at'],'runs':[]}
for fps in (30,15):
 dev=None
 item={'requested_fps':fps};result['runs'].append(item)
 try:
  dev=Device(str(base/'board/visual_aid_v3.bit'))
  gpio=GPIO(dev.mmio);camera=OV5640(I2CBus(gpio,0,1),gpio)
  item['camera']=camera.initialize(fps=fps)
  time.sleep(1)
  item['registers']={hex(a):camera.read(a) for a in (0x3034,0x3035,0x3036,0x3037,0x3108,0x3824,0x460b,0x460c,0x4713,0x380c,0x380d,0x380e,0x380f,0x4740)}
  before=dev.counters();time.sleep(2);after=dev.counters()
  item['idle_2s_deltas']={k:(after[k]-before[k])&0xffffffff for k in after}
  dev.arm(0);times=[]
  for n in range(30):
   _,fid,frame=dev.finish(rearm=n<29);times.append(time.monotonic())
  item['capture_only_fps']=(len(times)-1)/(times[-1]-times[0])
  policy=AdaptivePolicy();profile=cProfile.Profile();profile.enable()
  for n in range(20):
   canvas,roi,bounds=compose(frame)
   policy.update(roi,n*0.3)
   cv2.putText(canvas,'PROFILE',(12,30),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,255,0,0),1)
   dev.display(canvas)
  profile.disable();s=io.StringIO();pstats.Stats(profile,stream=s).sort_stats('cumtime').print_stats(30)
  item['cpu_profile']=s.getvalue();item['counters']=dev.counters()
 except Exception as exc:item['error']=type(exc).__name__+': '+str(exc)
 finally:
  if dev:dev.close()
 print(json.dumps(item,indent=2),flush=True)
out=base/'logs'/('performance_profile_'+time.strftime('%Y%m%d_%H%M%S')+'.json')
out.write_text(json.dumps(result,indent=2))
