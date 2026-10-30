"""Reusable JSON timing/DRC gate; accepts project-neutral metric keys."""
import argparse,json,math
from pathlib import Path
def check(d,min_setup=0.0,min_hold=0.0):
    errors=[]
    for key,minimum in [('setup_ns',min_setup),('hold_ns',min_hold)]:
        value=d.get(key)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<minimum:
            errors.append(key+' missing, non-finite or below threshold')
    if type(d.get('drc_errors')) is not int or d['drc_errors']!=0:errors.append('drc_errors must be integer zero')
    return {'passed':not errors,'errors':errors,'scope':'setup/hold/DRC metrics only; not CDC completeness or board acceptance'}
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('metrics',type=Path)
    ap.add_argument('--min-setup',type=float,default=0.0);ap.add_argument('--min-hold',type=float,default=0.0)
    a=ap.parse_args();r=check(json.loads(a.metrics.read_text()),a.min_setup,a.min_hold)
    print(json.dumps(r,indent=2));return 0 if r['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
