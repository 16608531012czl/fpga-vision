"""Compare hexadecimal simulation words with first mismatch and length checks."""
import argparse,json
from pathlib import Path
def compare(expected,actual):
    a=[int(x,16) for x in expected.split()];b=[int(x,16) for x in actual.split()]
    mismatch=next((i for i,(x,y) in enumerate(zip(a,b)) if x!=y),None)
    return {'passed':bool(a) and len(a)==len(b) and mismatch is None,'expected_words':len(a),'actual_words':len(b),'first_mismatch':mismatch}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('expected',type=Path);ap.add_argument('actual',type=Path);a=ap.parse_args()
    r=compare(a.expected.read_text(),a.actual.read_text());print(json.dumps(r));raise SystemExit(not r['passed'])
