"""Save reproducible synthetic tone comparisons; this is not camera/HDMI evidence."""
from pathlib import Path
import json
import sys
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'software'))
from visual_aid.image import AdaptivePolicy, gray8, reference_enhance


def settled(image, profile):
    policy = AdaptivePolicy(profile)
    for i in range(17):
        policy.update(image, i*0.25, 0)
    return policy


def main():
    out = ROOT/'reports/lowlight_20261020'
    out.mkdir(exist_ok=True)
    cfg = 4 | 16 | 32 | (2 << 6)
    result = {'source': 'synthetic software reference', 'board_tested': False,
              'optical_detail_recovery_tested': False, 'settle_seconds': 4,
              'lux': 0, 'constant_gray_cases': []}
    for value in (20, 40, 80, 120, 180, 240):
        image = np.full((48, 64, 3), value, np.uint8)
        row = {'source_gray': value}
        for profile in ('legacy', 'lowlight'):
            policy = settled(image, profile)
            output = reference_enhance(image, cfg, policy.lut)
            row[profile+'_mean'] = float(gray8(output).mean())
        result['constant_gray_cases'].append(row)
    # Synthetic reading scene with dim page, dark text and one bright patch.
    h, w = 320, 480
    y, x = np.indices((h, w))
    page = (38+20*x/(w-1)+6*y/(h-1)).astype(np.uint8)
    image = np.repeat(page[:, :, None], 3, axis=2)
    for i, line in enumerate(('LOW LIGHT READING', 'Same scene, same pixels.',
                              'Shadow lift with highlight protection.',
                              'No extra light sensor required.', '0123456789 ABCDEFG')):
        cv2.putText(image, line, (15, 55+i*43), cv2.FONT_HERSHEY_SIMPLEX,
                    0.58 if i == 0 else 0.45, (10, 10, 10), 1, cv2.LINE_AA)
    image[275:303, 350:450] = 240
    panels = [image]
    for profile in ('legacy', 'lowlight'):
        policy = settled(image, profile)
        panels.append(reference_enhance(image, cfg, policy.lut))
    sheet = np.full((h+115, 3*w, 3), 245, np.uint8)
    for i, (label, panel) in enumerate(zip(('ORIGINAL', 'PREVIOUS POLICY', 'NEW LOWLIGHT'), panels)):
        sheet[75:75+h, i*w:(i+1)*w] = panel
        cv2.putText(sheet, label, (i*w+16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (30,30,30), 2)
        cv2.putText(sheet, 'Mean Y: {:.1f}'.format(gray8(panel).mean()), (i*w+16, 59),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40,40,40), 1)
    cv2.putText(sheet, 'SYNTHETIC SOFTWARE MODEL - NOT A BOARD CAPTURE', (16,h+102),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (30,30,30), 1)
    cv2.imwrite(str(out/'comparison.png'), sheet)
    result['reading_scene_mean'] = dict(zip(('source', 'legacy', 'lowlight'),
                                           [float(gray8(p).mean()) for p in panels]))
    (out/'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
