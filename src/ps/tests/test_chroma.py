"""Noise reduction must preserve luminance edges and original comparison pixels."""
from pathlib import Path
import sys,unittest
from unittest.mock import Mock,patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'runtime'))
from visual_aid.chroma import reference_chroma,reference_temporal,luma,ChromaDenoiser,enhanced_pane
from visual_aid.image import compose
from visual_aid.controls import State
from visual_aid.camera import OV5640
from camera_model import SensorBus


class ChromaTests(unittest.TestCase):
    def test_dark_color_noise_reduced_without_dimming_or_blurring_text(self):
        rng=np.random.RandomState(106)
        image=np.full((64,96,4),60,np.uint8)
        image[:,:,:3]=(60+rng.randint(-9,10,(64,96,3))).astype(np.uint8)
        image[:,46:49,:3]=10
        filtered=reference_chroma(image,6)
        before=(image[:,:,0].astype(float)-image[:,:,2]).std()
        after=(filtered[:,:,0].astype(float)-filtered[:,:,2]).std()
        self.assertLess(after,before*.8)
        self.assertLessEqual(np.abs(luma(image)-luma(filtered)).max(),1)
        np.testing.assert_array_equal(filtered[:,46:49],image[:,46:49])

    def test_temporal_filter_uses_current_luma_and_resets_on_large_motion(self):
        old=np.full((20,24,4),60,np.uint8);old[:,:,0]=68
        current=np.full_like(old,60);current[:,:,2]=68
        mixed=reference_temporal(current,6,old)
        self.assertLess((mixed[:,:,2].astype(float)-mixed[:,:,0]).mean(),8)
        moving=np.full_like(old,110)
        np.testing.assert_array_equal(reference_temporal(moving,6,old),moving)
        self.assertLessEqual(np.abs(luma(current)-luma(mixed)).max(),1)
        np.testing.assert_array_equal(reference_temporal(current,6),current)

    def test_highlights_strong_color_boundaries_and_bypass_survive(self):
        image=np.full((16,24,4),210,np.uint8)
        np.testing.assert_array_equal(reference_chroma(image,10),image)
        image[:,:12,:3]=(90,10,10);image[:,12:,:3]=(10,10,90)
        np.testing.assert_array_equal(reference_chroma(image,6),image)
        np.testing.assert_array_equal(reference_chroma(image,0),image)

    def test_original_pane_and_letterbox_never_filtered(self):
        image=np.random.RandomState(42).randint(20,90,(72,128,4),dtype=np.uint8)
        canvas,roi,bounds=compose(image,size=(128,72));before=canvas.copy()
        denoiser=ChromaDenoiser()
        with patch('visual_aid.chroma.clean_chroma',return_value=False):
            denoiser.apply(enhanced_pane(canvas,bounds,True),6,(bounds,True,6),1)
        np.testing.assert_array_equal(canvas[:,:64],before[:,:64])
        np.testing.assert_array_equal(canvas[:18],before[:18])
        np.testing.assert_array_equal(canvas[54:],before[54:])

    def test_history_invalidated_on_pan_strength_change_and_capture_gap(self):
        d=ChromaDenoiser();pane=np.full((8,10,4),60,np.uint8)
        with patch('visual_aid.chroma.clean_chroma',return_value=True) as native:
            for key,now,valid in (('a',1,False),('a',1.05,True),('b',1.10,False),('b',1.5,False)):
                d.apply(pane,6,key,now);self.assertEqual(native.call_args.args[-1],valid)
            d.apply(pane,0,'b',1.55);self.assertFalse(d.valid)

    def test_quality_knob_reset_uses_selected_profile_and_camera_preserves_exposure(self):
        s=State('balanced');s.sharpness=9;s.denoise=1;s.encoder('long')
        self.assertEqual((s.sharpness,s.denoise,s.noise,s.contrast),(2,6,6,0))
        bus=SensorBus();bus.registers={0x5000:0xa7,0x5001:0x83,0x5308:0x40,0x5302:24,0x530b:4,
                                      0x3503:0,0x3a19:248,0x3035:0x41,0x3022:4}
        before=bus.registers.copy();result=OV5640(bus,Mock()).image_quality('balanced')
        self.assertEqual(result['registers_after'][0x5001],0x87)
        for reg in (0x3503,0x3a19,0x3035,0x3022):self.assertEqual(bus.registers[reg],before[reg])
        self.assertFalse(bus.registers[0x5308]&16)


if __name__=='__main__':unittest.main()
