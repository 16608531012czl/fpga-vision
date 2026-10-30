"""Reproducible PC preview; images are software model output, not board evidence."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
from visual_aid.image import compose, reference_enhance, AdaptivePolicy


def page():
    h, w = 720, 1280
    y, x = np.indices((h, w))
    light = 0.40+0.58*x/w+0.08*np.sin(y/90)
    image = np.full((h, w, 3), 235, dtype=np.uint8)
    lines = ['ELECTRONIC READING ASSISTANT', 'Reading, magnification and adaptive contrast.',
             'The same frame and ROI are shown on both sides.', 'Move the 5D switch to inspect small text.',
             'Press the centre to cycle 1x / 2x / 4x.', 'Freeze the full frame, then pan and zoom.',
             'Lighting and distance are optional measured inputs.', 'Software preview: board performance is not measured.']
    for i, line in enumerate(lines):
        cv2.putText(image, line, (70, 110+i*66), cv2.FONT_HERSHEY_SIMPLEX, 0.72 if i else 1.0, (35, 35, 35), 2 if i == 0 else 1)
    rng = np.random.RandomState(2040)
    return np.clip(image.astype(float)*light[:, :, None]+rng.normal(0, 2.5, image.shape), 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser();ap.add_argument('--image');ap.add_argument('--out', default='reports/preview')
    args = ap.parse_args();out = Path(args.out);out.mkdir(parents=True, exist_ok=True)
    source = cv2.imread(args.image) if args.image else page()
    if source is None:
        raise ValueError('Cannot read input image')
    cv2.imwrite(str(out/'source.png'), source)
    policy = AdaptivePolicy()
    for i in range(12):
        policy.update(source, i*0.3, 30)
    cases = [('reading_split', 1, 1, (0.5, 0.5), True),
             ('color_split', 4, 1, (0.5, 0.5), True),
             ('inverse_2x', 2, 2, (0.5, 0.5), True),
             ('binary_4x', 3, 4, (0.65, 0.55), True),
             ('frozen_pan', 1, 4, (0.25, 0.4), False)]
    summary = {'source': 'software_reference', 'board_tested': False, 'examples': []}
    frozen = source.copy()
    for name, mode, zoom, center, split in cases:
        canvas, roi, bounds = compose(frozen, zoom, center, split)
        cfg = mode | (8 if split else 0) | 16 | 32 | (2 << 6) | (8 << 8)
        output = reference_enhance(canvas, cfg, policy.lut)
        cv2.imwrite(str(out/(name+'.png')), output)
        summary['examples'].append({'name': name, 'zoom': zoom, 'source_roi': bounds, 'split': split, 'cfg': cfg})
    (out/'preview.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print('PASS preview: {} examples; software model only'.format(len(cases)))


if __name__ == '__main__':
    main()
