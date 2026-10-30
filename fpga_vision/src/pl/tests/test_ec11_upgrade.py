from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'software'))
from visual_aid.controls import State
from visual_aid.encoder import Encoder, record_event
from visual_aid.image import reference_enhance


class Upgrade(unittest.TestCase):
    def test_physical_encoder_validation_requires_both_directions_and_keys(self):
        report={}
        record_event(report,'short',1);record_event(report,'long',1)
        self.assertFalse(report['encoder_connected_verified'])
        record_event(report,'rotate',2)
        self.assertFalse(report['encoder_connected_verified'])
        record_event(report,'rotate',-2)
        self.assertTrue(report['encoder_connected_verified'])

    def test_rotation_is_bounded_and_click_changes_selected_parameter(self):
        s=State();s.encoder('rotate',100)
        self.assertEqual(s.brightness,10)
        s.encoder('rotate',-100);self.assertEqual(s.brightness,-10)
        s.encoder('short');s.encoder('rotate',100)
        self.assertEqual(s.sharpness,10)
        s.encoder('long');self.assertEqual((s.brightness,s.sharpness),(0,4))
        self.assertTrue(s.automatic)

    def test_auto_toggle_preserves_user_settings(self):
        s=State();s.brightness=3;s.sharpness=7
        s.apply('auto');self.assertFalse(s.automatic)
        self.assertEqual((s.brightness,s.sharpness),(3,7))
        s.apply('auto');self.assertTrue(s.automatic)
        self.assertEqual((s.brightness,s.sharpness),(3,7))

    def test_encoder_counter_wrap_reverse_and_press_events(self):
        mmio=Mock();values={0x50:0xfffffffe,0x58:0xffffffff,0x5c:0,0x60:0,0x54:3}
        mmio.read.side_effect=lambda address:values[address]
        e=Encoder();self.assertEqual(e.poll(mmio)[0],[])
        values.update({0x50:1,0x58:0,0x5c:1})
        self.assertEqual(e.poll(mmio)[0],[('rotate',3),('short',1),('long',1)])
        reverse=Encoder(True);reverse.poll(mmio);values[0x50]=2
        self.assertEqual(reverse.poll(mmio)[0],[('rotate',-1)])

    def test_guided_filter_rejects_flat_background_noise(self):
        rng=np.random.RandomState(22)
        mono=(100+rng.randint(-3,4,(64,96))).astype(np.uint8)
        image=np.repeat(mono[:,:,None],3,axis=2)
        s=State();s.split=False;s.mode=1;s.denoise=0;s.contrast=0;s.sharpness=8
        s.algorithm=1;usm=reference_enhance(image,s.config())[4:,4:,0].astype(float)
        s.algorithm=3;guided=reference_enhance(image,s.config())[4:,4:,0].astype(float)
        np.testing.assert_array_equal(guided,mono[4:,4:])
        self.assertLess(guided.std(),usm.std())

    def test_advanced_algorithms_preserve_original_pane_and_bound_detail(self):
        image=np.full((48,96,3),160,np.uint8);image[:,20:22]=40;image[:,68:70]=40
        s=State();s.mode=4;s.denoise=0;s.contrast=0;s.sharpness=10
        for algorithm in (0,1,2,3):
            s.algorithm=algorithm
            result=reference_enhance(image,s.config())
            np.testing.assert_array_equal(result[:,:48],image[:,:48])
            delta=result[:,48:].astype(int)-image[:,48:].astype(int)
            self.assertLessEqual(np.abs(delta).max(),24)

    def test_sobel_diagnostic_and_raw_bypass(self):
        image=np.full((48,64,3),100,np.uint8);image[:,32:]=160
        s=State();s.split=False;s.edge_view=True;s.mode=1
        edges=reference_enhance(image,s.config())
        self.assertGreater(int(edges[:,32:35].max()),0)
        self.assertTrue(np.all(edges[4:,4:28]==0))
        s.mode=0;np.testing.assert_array_equal(reference_enhance(image,s.config()),image)


if __name__=='__main__':unittest.main()
