"""Read-only release/environment check; never loads an overlay."""
from pathlib import Path
import argparse
import json
import sys
from visual_aid.integrity import verify_payload


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--host', action='store_true', help='Check bundle on a PC without importing PYNQ')
    args = ap.parse_args()
    root = Path(__file__).resolve().parent
    result = {'overlay_loaded': False, 'board_tested': False, 'python': sys.version.split()[0]}
    try:
        manifest = verify_payload(root)
        import numpy
        import cv2
        result.update(payload_files=len(manifest['payload_sha256']), numpy=numpy.__version__, opencv=cv2.__version__)
        if not args.host:
            if sys.version_info < (3, 6):
                raise RuntimeError('Python 3.6 or later is required')
            import pynq
            from pynq import Overlay, Xlnk, DefaultIP
            from pynq.lib.video import VideoMode, PixelFormat
            result['pynq'] = getattr(pynq, '__version__', 'unknown')
            from visual_aid.fastcompose import available
            result['native_composition_available']=available()
            if manifest.get('native_composition') and not available():
                raise RuntimeError('Validated ARM composition library could not be loaded')
        result['outcome'] = 'passed'
    except Exception as exc:
        result.update(outcome='error', error=type(exc).__name__+': '+str(exc))
    print(json.dumps(result, indent=2))
    return 0 if result['outcome'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
