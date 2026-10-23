"""Optional validated ARM native resize; exact OpenCV fallback on other hosts."""
import ctypes
from pathlib import Path
import numpy as np

_lib = None
try:
    _lib = ctypes.CDLL(str(Path(__file__).resolve().parents[1]/'native/libcompose.so'))
    _lib.half_bgrx.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p,
                           ctypes.c_int,ctypes.c_int,ctypes.c_int]
    _lib.half_bgrx.restype=ctypes.c_int
    _lib.load_gamma.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
    _lib.load_gamma.restype=ctypes.c_int
    _lib.clean_chroma.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p,
                               ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int]
    _lib.clean_chroma.restype=ctypes.c_int
    _lib.temporal_chroma.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,
                                  ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int]
    _lib.temporal_chroma.restype=ctypes.c_int
    _lib.load_parameters.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int]
    _lib.load_parameters.restype=ctypes.c_int
except (OSError,AttributeError):
    _lib=None

def available():
    return _lib is not None


def load_parameters(registers,values,text=False):
    if _lib is None:return False
    if (not isinstance(registers,np.ndarray) or registers.dtype!=np.uint32 or
            not registers.flags.c_contiguous or not registers.flags.writeable or registers.size<44):
        raise ValueError('Parameters require the owned AXI-Lite register mapping')
    data=np.ascontiguousarray(values,dtype=np.uint16).ravel()
    if data.size!=(384 if text else 48) or np.any(data>(127 if text else 384)) or (not text and np.any(data<192)):
        raise ValueError('Invalid PL parameter table')
    if _lib.load_parameters(registers.ctypes.data,data.ctypes.data,int(text)):
        raise ValueError('Native parameter writer rejected data')
    return True


def clean_chroma(pane, scratch, history, strength, valid):
    if _lib is None:return False
    h,w,c=pane.shape
    if (c!=4 or pane.dtype!=np.uint8 or not pane.flags.writeable or pane.strides[1:]!=(4,1)
            or pane.strides[0]<w*4 or not 0<=strength<=10):
        raise ValueError('Chroma filter needs a writable BGRX pane and strength 0..10')
    for other in (scratch,history):
        if (other.shape!=pane.shape or other.dtype!=np.uint8 or not other.flags.c_contiguous
                or not other.flags.writeable or np.may_share_memory(pane,other)):
            raise ValueError('Chroma work buffers must be separate contiguous writable BGRX')
    if np.may_share_memory(scratch,history):raise ValueError('Chroma history aliases scratch')
    if _lib.temporal_chroma(pane.ctypes.data,pane.strides[0],history.ctypes.data,w,h,strength,int(valid)):
        raise ValueError('Native chroma filter rejected dimensions')
    return True


def load_gamma(registers, lut):
    if _lib is None:return False
    if (not isinstance(registers,np.ndarray) or registers.dtype!=np.uint32 or
            not registers.flags.c_contiguous or not registers.flags.writeable or registers.size<20):
        raise ValueError('Gamma requires the owned AXI-Lite register mapping')
    data=np.ascontiguousarray(lut,dtype=np.uint8)
    if data.shape!=(256,):raise ValueError('Gamma LUT must contain 256 bytes')
    if _lib.load_gamma(registers.ctypes.data,data.ctypes.data):
        raise ValueError('Native gamma writer rejected pointers')
    return True

def half_resize(source, output, second=None):
    if _lib is None:return False
    h,w,c=output.shape
    if c!=4 or source.shape!=(h*2,w*2,4):return False
    arrays=[source,output]+([] if second is None else [second])
    if any(a.dtype!=np.uint8 or a.strides[1:]!=(4,1) or a.strides[0]<a.shape[1]*4 for a in arrays):return False
    if not output.flags.writeable or np.may_share_memory(source,output):
        raise ValueError('Unsafe native output ownership')
    if second is not None and (second.shape!=output.shape or second.strides!=output.strides or
                              not second.flags.writeable or np.may_share_memory(source,second)):
        raise ValueError('Unsafe second native output')
    code=_lib.half_bgrx(source.ctypes.data,source.strides[0],output.ctypes.data,
                       None if second is None else second.ctypes.data,output.strides[0],w,h)
    if code:raise ValueError('Native composition dimensions rejected')
    return True
