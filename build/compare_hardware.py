"""Compare Xilinx configuration payloads and PYNQ 2.4 HWH runtime dictionaries."""
from pathlib import Path
import argparse,json,hashlib,struct
from pynq_hwh_parser_24 import _HWHZynq
def sha(b):return hashlib.sha256(b).hexdigest()
def payload(path):
    b=path.read_bytes();i=2+int.from_bytes(b[:2],'big')
    if b[i:i+2]!=b'\x00\x01':raise ValueError('Not a supported Xilinx bit container')
    i+=2
    while i<len(b):
        tag=chr(b[i]);i+=1;width=4 if tag=='e' else 2
        n=int.from_bytes(b[i:i+width],'big');i+=width
        if i+n>len(b):raise ValueError('Truncated bit container')
        if tag=='e':
            if i+n!=len(b):raise ValueError('Unexpected trailing data')
            return b[i:i+n]
        if tag not in 'abcd':raise ValueError('Unknown bit header field')
        i+=n
    raise ValueError('Missing configuration payload')
def compare(old,new):
    a=payload(old);b=payload(new)
    pa=_HWHZynq(str(old.with_suffix('.hwh')));pb=_HWHZynq(str(new.with_suffix('.hwh')))
    fields=['ip_dict','clock_dict','gpio_dict','interrupt_controllers','interrupt_pins','hierarchy_dict']
    equal={k:getattr(pa,k)==getattr(pb,k) for k in fields}
    return {'passed':a==b and all(equal.values()),'configuration_data_identical':a==b,'configuration_bytes':len(b),'original_configuration_sha256':sha(a),'rebuilt_configuration_sha256':sha(b),'pynq_24_parser_outputs_equal':equal,'scope':'Header-independent configuration and runtime metadata comparison; not a new board run'}
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('original_bit',type=Path);ap.add_argument('rebuilt_bit',type=Path)
    args=ap.parse_args();result=compare(args.original_bit,args.rebuilt_bit)
    print(json.dumps(result,indent=2));raise SystemExit(not result['passed'])
