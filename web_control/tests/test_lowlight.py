"""Acceptance checks for visible shadow lift and existing PL/bypass contracts."""
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'runtime'))
from visual_aid.image import AdaptivePolicy, compose, reference_enhance


def settle(image, profile='lowlight', lux=0):
    policy = AdaptivePolicy(profile)
    for i in range(17):
        policy.update(image, i*0.25, lux)
    return policy


class Lowlight(unittest.TestCase):
    def test_stable_curve_rejects_small_brightness_variation_and_bounds_changes(self):
        policy=AdaptivePolicy('stable')
        image=lambda level:np.full((48,64,3),level,np.uint8)
        policy.update(image(40),0,None);initial=policy.lut.copy()
        self.assertGreater(int(initial[40]),80)
        self.assertTrue(np.all(initial.astype(int)<=3*np.arange(256)))
        for i in range(1,21):
            policy.update(image(40+(1 if i%2 else -1)),i*.25,None)
            np.testing.assert_array_equal(policy.lut,initial)
        previous=policy.lut.copy()
        for i in range(21,61):
            policy.update(image(160),i*.25,None)
            self.assertLessEqual(np.max(np.abs(policy.lut.astype(int)-previous.astype(int))),1)
            self.assertTrue(np.all(np.diff(policy.lut.astype(int))>=0))
            previous=policy.lut.copy()
        self.assertLess(int(policy.lut[40]),int(initial[40]))

    def test_dark_scene_is_visibly_brighter_than_previous_policy(self):
        image = np.full((48, 64, 3), 40, np.uint8)
        old, new = settle(image, 'legacy'), settle(image)
        # Independent acceptance targets: >2.5x source and >25 levels above old.
        self.assertGreaterEqual(int(new.lut[40]), 110)
        self.assertGreaterEqual(int(new.lut[40])-int(old.lut[40]), 25)
        actual = reference_enhance(image, 4 | 16 | 32 | (2 << 6), new.lut)
        self.assertGreaterEqual(float(actual.mean()), 110)

    def test_lux_strengthens_dark_scene_but_bright_page_stays_identity(self):
        dark = np.full((48, 64, 3), 60, np.uint8)
        self.assertGreater(int(settle(dark, lux=0).lut[60]),
                           int(settle(dark, lux=200).lut[60]))
        bright = np.full((48, 64, 3), 180, np.uint8)
        np.testing.assert_array_equal(settle(bright, lux=0).lut, np.arange(256))

    def test_highlights_black_and_near_black_gain_are_bounded(self):
        image = np.full((48, 64, 3), 40, np.uint8)
        image[:, -4:] = 240
        lut = settle(image).lut
        self.assertEqual(int(lut[0]), 0)
        np.testing.assert_array_equal(lut[224:], np.arange(224, 256))
        self.assertTrue(np.all(np.diff(lut.astype(int)) >= 0))
        self.assertTrue(np.all(lut.astype(int) <= 5*np.arange(256)))
        actual = reference_enhance(image, 4, lut)
        np.testing.assert_array_equal(actual[:, -4:], image[:, -4:])

    def test_invalid_lux_falls_back_to_image_statistics(self):
        dark = np.full((24, 32, 3), 50, np.uint8)
        expected = settle(dark, lux=None).lut
        for lux in (float('nan'), float('inf'), -1):
            policy = settle(dark, lux=lux)
            np.testing.assert_array_equal(policy.lut, expected)
            self.assertIsNone(policy.status()['lux'])

    def test_split_and_raw_keep_original_pixels(self):
        dark = np.full((48, 64, 3), 40, np.uint8)
        policy = settle(dark)
        canvas, _, _ = compose(dark, split=True, size=(128, 48))
        out = reference_enhance(canvas, 4 | 8, policy.lut)
        np.testing.assert_array_equal(out[:, :64], canvas[:, :64])
        self.assertGreater(out[:, 64:].mean(), canvas[:, 64:].mean()+50)
        np.testing.assert_array_equal(reference_enhance(canvas, 0, policy.lut), canvas)

    def test_light_transition_settles_without_single_frame_jump(self):
        bright = np.full((48, 64, 3), 180, np.uint8)
        dark = np.full_like(bright, 40)
        policy = settle(bright)
        policy.update(dark, 4.25, 0)
        self.assertLess(int(policy.lut[40]), 70)
        for i in range(18, 33):
            policy.update(dark, i*0.25, 0)
        self.assertGreaterEqual(int(policy.lut[40]), 110)
        for i in range(33, 53):
            policy.update(bright, i*0.25, 0)
        self.assertLessEqual(int(policy.lut[40]), 42)

    def test_legacy_reproduces_previous_updates_exactly(self):
        policy = AdaptivePolicy('legacy')
        expected = np.arange(256, dtype=np.uint8)
        smoothed = None
        for i, value in enumerate((40, 80, 180, 60)):
            image = np.full((24, 32, 3), value, np.uint8)
            smoothed = value if smoothed is None else 0.8*smoothed+0.2*value
            exponent = np.clip(1+(smoothed-120)/250-0.08, 0.55, 1.3)
            target = np.rint(255*(np.arange(256)/255.0)**exponent)
            expected = np.rint(0.75*expected+0.25*target).astype(np.uint8)
            policy.update(image, i*0.25, 0)
            np.testing.assert_array_equal(policy.lut, expected)


if __name__ == '__main__':
    unittest.main()
