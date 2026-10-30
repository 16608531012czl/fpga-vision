from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'runtime'))
from visual_aid.auto_quality import AutoQuality, scene_metrics
from visual_aid.controls import State, AUTO_PARAMETERS
from visual_aid.remote_control import apply_command, snapshot
from visual_aid.image import AdaptivePolicy


def scene(mean=60, noise=0, uneven=False):
    rng = np.random.RandomState(42)
    a = np.full((180, 320), float(mean))
    if uneven: a += np.linspace(-40, 100, 320)[None, :]
    if noise: a += rng.normal(0, noise, a.shape)
    a = np.clip(a, 0, 255).astype(np.uint8)
    return np.repeat(a[:, :, None], 3, axis=2)


def settle(frame, lux=10):
    state, policy = State('detail'), AutoQuality()
    for i in range(50): policy.update(state, frame, (0, 0, 320, 180), i*.5, lux)
    return state


class AutoQualityTests(unittest.TestCase):
    def test_noise_estimate_increases_and_bounds_sampling_cost(self):
        clean = scene_metrics(scene(), (0,0,320,180))
        noisy = scene_metrics(scene(noise=12), (0,0,320,180))
        self.assertLess(clean['noise_sigma'], .01)
        self.assertGreater(noisy['noise_sigma'], 8)
        self.assertEqual(noisy['sample_pixels'], 9*24*24)

    def test_text_edges_are_not_treated_as_uniform_noise(self):
        frame = scene(180)
        frame[:, ::8] = 20
        metrics = scene_metrics(frame, (0,0,320,180))
        self.assertGreater(metrics['edge_fraction'], .1)
        self.assertLess(metrics['noise_sigma'], 2)

    def test_noisy_scene_reduces_sharpening_and_increases_denoising(self):
        clean, noisy = settle(scene()), settle(scene(noise=12))
        self.assertGreater(noisy.denoise, clean.denoise)
        self.assertLess(noisy.sharpness, clean.sharpness)
        self.assertGreater(noisy.noise, clean.noise)
        self.assertEqual(noisy.brightness, 0)  # one adaptive tone curve, no double lift

    def test_noisy_scene_limits_lift_with_monotonic_highlight_safe_curve(self):
        clean,noisy=settle(scene()),settle(scene(noise=12))
        tone=AdaptivePolicy('stable');tone.update(scene(),0,0)
        a=AutoQuality.tone_lut(clean,tone.lut)
        b=AutoQuality.tone_lut(noisy,tone.lut)
        self.assertGreater(int(a[60]),int(b[60]))
        self.assertGreater(int(b[60]),60)
        self.assertTrue(np.all(np.diff(b.astype(int))>=0))
        np.testing.assert_array_equal(b[224:],np.arange(224,256))

    def test_uneven_clean_scene_enables_local_compensation(self):
        self.assertTrue(settle(scene(70, uneven=True)).local_tone)
        self.assertFalse(settle(scene(120)).local_tone)
        self.assertFalse(settle(scene(70, noise=16, uneven=True)).local_tone)

    def test_clipped_highlights_do_not_trigger_aggressive_enhancement(self):
        s = settle(scene(255))
        self.assertFalse(s.local_tone)
        self.assertEqual(s.denoise, 0)
        self.assertLessEqual(s.sharpness, 1)

    def test_lux_failure_falls_back_but_zero_lux_is_valid(self):
        for lux in (None, -1, float('nan'), float('inf')):
            s = settle(scene(), lux)
            self.assertIsNone(s.auto_status['metrics']['lux'])
            self.assertIn('照度缺失', s.auto_status['reason'])
        self.assertEqual(settle(scene(), 0).auto_status['metrics']['lux'], 0)

    def test_existing_tone_policy_combines_lux_and_image_without_lifting_highlights(self):
        curves=[]
        for lux in (0,1000):
            p=AdaptivePolicy('stable')
            for i in range(20): p.update(scene(60),i*.5,lux)
            curves.append(p.lut.copy())
            np.testing.assert_array_equal(p.lut[224:], np.arange(224,256))
        self.assertGreater(int(curves[0][60]), int(curves[1][60]))
        p=AdaptivePolicy('stable');p.update(scene(240),0,0)
        np.testing.assert_array_equal(p.lut,np.arange(256))

    def test_slow_bounded_steps_under_abrupt_scene_change(self):
        s, p = State('detail'), AutoQuality()
        before = {k:getattr(s,k) for k in ('denoise','sharpness','noise','brightness','contrast')}
        for i in range(60):
            now=i*.1
            p.update(s,scene(50,noise=18), (0,0,320,180),now,0)
            after={k:getattr(s,k) for k in before}
            for k in before:self.assertLessEqual(abs(after[k]-before[k]),1)
            if i%5 not in (0,): self.assertEqual(after,before)
            before=after
        self.assertLessEqual(s.denoise,7)

    def test_manual_freezes_values_and_auto_resumes(self):
        s,p=State('detail'),AutoQuality()
        p.update(s,scene(noise=12),(0,0,320,180),0,10)
        apply_command(s,{'op':'set','values':{'automatic':False,'sharpness':7,'denoise':2}})
        before={k:getattr(s,k) for k in s.parameters}
        for i in range(1,20):p.update(s,scene(noise=18),(0,0,320,180),i,0)
        self.assertEqual(before,{k:getattr(s,k) for k in s.parameters})
        apply_command(s,{'op':'set','values':{'automatic':True}})
        p.update(s,scene(noise=18),(0,0,320,180),21,0)
        self.assertLess(s.sharpness,7)

    def test_manual_edit_and_encoder_take_control(self):
        for name in AUTO_PARAMETERS:
            s=State('detail')
            apply_command(s,{'op':'set','values':{name:False if name in ('local_tone','window31') else 0}})
            self.assertFalse(s.automatic)
            s=State('detail');s.selected=s.parameters.index(name);s.encoder('rotate',1)
            self.assertFalse(s.automatic)
        s=State('detail');s.encoder('short')
        self.assertTrue(s.automatic)
        apply_command(s,{'op':'set','values':{'zoom':2,'mode':4,'frozen':True}})
        self.assertTrue(s.automatic)

    def test_conflicting_request_is_atomic(self):
        s=State('detail');before=snapshot(s)
        with self.assertRaises(ValueError):
            apply_command(s,{'op':'set','values':{'automatic':True,'denoise':4}})
        self.assertEqual(before,snapshot(s))

    def test_freeze_pauses_auto_and_unfreeze_resumes(self):
        s,p=State('detail'),AutoQuality()
        p.update(s,scene(),(0,0,320,180),0,10)
        s.frozen=True;before=s.snapshot()
        p.update(s,scene(noise=20),(0,0,320,180),10,0)
        self.assertEqual(before,s.snapshot())
        self.assertEqual(s.auto_status['status'],'paused')
        s.frozen=False;p.update(s,scene(noise=20),(0,0,320,180),11,0)
        self.assertEqual(s.auto_status['status'],'active')

    def test_invalid_frame_preserves_parameters_and_reports_waiting(self):
        s,p=State('detail'),AutoQuality();before=s.snapshot()
        p.update(s,None,(0,0,320,180),0,0)
        self.assertEqual(s.snapshot(),before)
        self.assertEqual(s.auto_status['status'],'waiting')

    def test_roi_only_and_no_input_writes(self):
        a=np.concatenate((scene(30),scene(200)),axis=1);before=a.copy();a.flags.writeable=False
        self.assertAlmostEqual(scene_metrics(a,(320,0,320,180))['mean'],200)
        np.testing.assert_array_equal(a,before)

    def test_contrast_and_advanced_targets_follow_different_scenes(self):
        low=settle(scene(70))
        high=settle(scene(90,uneven=True))
        noisy=settle(scene(70,noise=16))
        self.assertGreater(low.contrast,high.contrast)
        self.assertNotEqual(low.window31,high.window31)
        self.assertGreater(noisy.binary_c,low.binary_c)
        self.assertLess(noisy.color,low.color)
        self.assertEqual(noisy.contrast,0)

    def test_advanced_values_are_bounded_and_diagnostic_is_untouched(self):
        s,p=State('detail'),AutoQuality();s.edge_view=True
        for i in range(40):p.update(s,scene(65,noise=12,uneven=True),(0,0,320,180),i*.5,10)
        self.assertTrue(s.edge_view)
        self.assertTrue(0<=s.color<=16 and 0<=s.binary_c<=32 and 0<=s.contrast<=3)


if __name__=='__main__': unittest.main()
