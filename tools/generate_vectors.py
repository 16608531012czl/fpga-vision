from pathlib import Path
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'software'))
from visual_aid.image import reference_enhance


def generate(out, width, height, full=False):
    out.mkdir(parents=True, exist_ok=True)
    y, x = np.indices((height, width))
    bgr = np.stack(((x*17+y*9) % 256, (x*5+y*23) % 256, (x*31+y*3) % 256), axis=2).astype(np.uint8)
    lut = np.minimum(255, np.arange(256)*3//2).astype(np.uint8)
    configs = [1 | 16 | 32 | (2 << 6) | (8 << 8)] if full else [0, 1, 2, 3, 4, 0xf9, 0x08b3, 0xfff3, 0x08f4, 0x08f2]
    with (out/'input.mem').open('w') as inp, (out/'expected.mem').open('w') as exp:
        for cfg in configs:
            rgb = (bgr[:, :, 2].astype(np.uint32) << 16) | (bgr[:, :, 1].astype(np.uint32) << 8) | bgr[:, :, 0]
            expected = reference_enhance(bgr, cfg, lut)
            packed = (expected[:, :, 2].astype(np.uint32) << 16) | (expected[:, :, 1].astype(np.uint32) << 8) | expected[:, :, 0]
            inp.writelines('{:06x}\n'.format(int(p)) for p in rgb.ravel())
            exp.writelines('{:06x}\n'.format(int(p)) for p in packed.ravel())
    (out/'config.mem').write_text(''.join('{:08x}\n'.format(c) for c in configs))
    (out/'gamma.mem').write_text(''.join('{:02x}\n'.format(int(v)) for v in lut))
    return len(configs)


if __name__ == '__main__':
    p = Path(sys.argv[1]);full = '--full' in sys.argv
    print('Vector frames:', generate(p, 1280 if full else 32, 720 if full else 24, full))
