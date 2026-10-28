"""Read the configured camera without reinitializing its exposure or AF."""
from pathlib import Path
import json,time
from pynq import PL,MMIO
from visual_aid.integrity import verify_payload
from visual_aid.bus import GPIO,I2CBus
from visual_aid.camera import OV5640

base=Path(__file__).resolve().parent
manifest=verify_payload(base)
assert Path(PL.bitfile_name).parent==base/'board'
m=MMIO(int(manifest['metadata']['control_base'],0),4096)
assert m.read(0)==0x56410400
camera=OV5640(I2CBus(GPIO(m),0,1),GPIO(m))
regs={a:camera.read(a) for a in tuple(range(0x5300,0x5310))+
      (0x5000,0x5001,0x3500,0x3501,0x3502,0x3503,0x350a,0x350b,
       0x380c,0x380d,0x380e,0x380f,0x3a18,0x3a19,0x3029)}
hts=(regs[0x380c]<<8)|regs[0x380d]
exposure=((regs[0x3500]&15)<<16)|(regs[0x3501]<<8)|regs[0x3502]
result={'release':manifest['built_at'],'registers':{hex(a):v for a,v in regs.items()},
        'exposure_lines':exposure/16.0,'nominal_exposure_ms':exposure/16.0*hts/21000000*1000,
        'gain_x':(((regs[0x350a]&3)<<8)|regs[0x350b])/16.0,
        'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
out=base/'logs'/('performance_quality_probe_'+time.strftime('%Y%m%d_%H%M%S')+'.json')
out.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
