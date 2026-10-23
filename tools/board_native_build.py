"""Board-only build and pixel/stride/guard-region verification of NEON kernel."""
from pathlib import Path
import ctypes,json,hashlib,time,subprocess
import cv2,numpy as np
base=Path(__file__).resolve().parent
native=base/'native';native.mkdir(exist_ok=True)
source=native/'compose.c';output=native/'libcompose.so'
subprocess.check_call(['gcc','-std=c99','-O3','-fPIC','-shared','-mcpu=cortex-a9','-mfpu=neon','-mfloat-abi=hard','-fno-strict-aliasing',str(source),'-o',str(output)])
lib=ctypes.CDLL(str(output));lib.half_bgrx.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int]
lib.half_bgrx.restype=ctypes.c_int
lib.load_gamma.argtypes=[ctypes.c_void_p,ctypes.c_void_p];lib.load_gamma.restype=ctypes.c_int
lib.load_parameters.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int]
lib.load_parameters.restype=ctypes.c_int
for text in (False,True):
 registers=np.full(1024,0xdeadbeef,np.uint32);expected=registers.copy()
 values=np.full(384 if text else 48,65 if text else 256,np.uint16)
 assert lib.load_parameters(registers.ctypes.data,values.ctypes.data,int(text))==0
 expected[(0xa0 if text else 0x90)//4]=(len(values)-1)|(int(values[-1])<<(16 if text else 8))
 expected[(0xa4 if text else 0x94)//4]=1
 np.testing.assert_array_equal(registers,expected)
 values[0]=999;before=registers.copy()
 assert lib.load_parameters(registers.ctypes.data,values.ctypes.data,int(text))==-1
 np.testing.assert_array_equal(registers,before)
assert lib.load_parameters(None,None,0)==-1
lib.clean_chroma.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p,
                          ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int]
lib.clean_chroma.restype=ctypes.c_int
lib.temporal_chroma.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,
                             ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int]
lib.temporal_chroma.restype=ctypes.c_int
for final in (0,127,255):
 registers=np.full(1024,0xdeadbeef,np.uint32);expected=registers.copy()
 table=np.arange(256,dtype=np.uint8);table[-1]=final
 assert lib.load_gamma(registers.ctypes.data,table.ctypes.data)==0
 expected[0x44//4]=255|(final<<8);expected[0x48//4]=1
 np.testing.assert_array_equal(registers,expected)
assert lib.load_gamma(None,None)==-1
rng=np.random.RandomState(47);cases=[]
for w,h in ((1,1),(3,7),(4,3),(17,9),(640,360)):
 src=rng.randint(0,256,(h*2,w*2+6,4),dtype=np.uint8)[:,3:3+w*2]
 dst=np.full((h+4,w*2+16,4),199,np.uint8);before=dst.copy()
 left=dst[2:2+h,4:4+w];right=dst[2:2+h,8+w:8+w*2]
 expected=cv2.resize(src,(w,h),interpolation=cv2.INTER_LINEAR)
 assert lib.half_bgrx(src.ctypes.data,src.strides[0],left.ctypes.data,right.ctypes.data,dst.strides[0],w,h)==0
 np.testing.assert_array_equal(left,expected);np.testing.assert_array_equal(right,expected)
 before[2:2+h,4:4+w]=expected;before[2:2+h,8+w:8+w*2]=expected
 np.testing.assert_array_equal(dst,before)
 cases.append([w,h])
from visual_aid.chroma import reference_chroma,reference_temporal,luma
quality=[]
for w,h in ((1,1),(3,7),(17,9),(640,360)):
 storage=rng.randint(0,256,(h+4,w+12,4),dtype=np.uint8)
 pane=storage[2:2+h,4:4+w];scratch=np.empty(pane.shape,np.uint8);history=np.empty_like(scratch)
 for strength in (0,1,6,10):
  for valid in (False,True):
   history[:]=rng.randint(0,256,history.shape,dtype=np.uint8)
   expected=reference_chroma(pane,strength,history if valid else None)
   before=storage.copy();before[2:2+h,4:4+w]=expected
   assert lib.clean_chroma(pane.ctypes.data,pane.strides[0],scratch.ctypes.data,history.ctypes.data,w,h,strength,int(valid))==0
   np.testing.assert_array_equal(storage,before)
   if strength:np.testing.assert_array_equal(history,expected)
   history[:]=rng.randint(0,256,history.shape,dtype=np.uint8)
   expected=reference_temporal(pane,strength,history if valid else None)
   before=storage.copy();before[2:2+h,4:4+w]=expected
   assert lib.temporal_chroma(pane.ctypes.data,pane.strides[0],history.ctypes.data,w,h,strength,int(valid))==0
   np.testing.assert_array_equal(storage,before)
   if strength:np.testing.assert_array_equal(history,expected)
 quality.append([w,h])
# Independent quality gates at the same current luma, without a darker tone LUT.
history=np.empty((64,96,4),np.uint8);scratch=np.empty_like(history)
raws=[];filtered=[]
for n in range(24):
 image=np.full_like(history,60);image[:,:,:3]=(60+rng.randint(-9,10,(64,96,3))).astype(np.uint8)
 image[:,46:49,:3]=10;original=image.copy()
 assert lib.temporal_chroma(image.ctypes.data,image.strides[0],history.ctypes.data,96,64,6,int(n>0))==0
 assert np.abs(luma(original)-luma(image)).max()<=1
 np.testing.assert_array_equal(image[:,46:49],original[:,46:49])
 raws.append(original);filtered.append(image)
raw=np.stack(raws).astype(float);clean=np.stack(filtered).astype(float)
before=(raw[:,:,:,0]-raw[:,:,:,2])[:,4:-4,4:40]
after=(clean[:,:,:,0]-clean[:,:,:,2])[:,4:-4,4:40]
metrics={'chroma_std_before':float(before.std()),'chroma_std_after':float(after.std()),
         'temporal_std_before':float(before.std(axis=0).mean()),'temporal_std_after':float(after.std(axis=0).mean()),
         'luma_max_error':int(np.abs(luma(raw[0])-luma(clean[0])).max()),'text_stroke_unchanged':True,
         'scope':'seeded synthetic dark patch, not a physical camera noise measurement'}
assert metrics['chroma_std_after']<metrics['chroma_std_before']*.8
assert metrics['temporal_std_after']<metrics['temporal_std_before']*.8
bench=np.full((360,640,4),60,np.uint8);scratch=np.empty_like(bench);history=np.empty_like(bench)
times=[]
for n in range(12):
 started=time.monotonic()
 assert lib.temporal_chroma(bench.ctypes.data,bench.strides[0],history.ctypes.data,640,360,6,int(n>0))==0
 times.append((time.monotonic()-started)*1000)
metrics['native_640x360_median_ms']=float(np.median(times[2:]))
report={'passed':True,'cases':cases,'gamma_guard_checks':True,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'binary_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'compiler':subprocess.check_output(['gcc','--version']).decode().splitlines()[0],
        'chroma_guard_cases':quality,'chroma_quality':metrics}
(base/'logs'/('performance_neon_'+time.strftime('%Y%m%d_%H%M%S')+'.json')).write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)
