"""Ownership and pixel-equivalence tests for direct HDMI composition."""
import unittest
from unittest.mock import Mock,patch
import numpy as np
import cv2
from visual_aid.image import compose,crop_roi
from visual_aid.device import Device
from visual_aid.camera import OV5640
from camera_model import SensorBus

class DirectComposition(unittest.TestCase):
    def test_gamma_pending_never_writes_or_commits(self):
        d=Device.__new__(Device);d.mmio=Mock();d.mmio.read.return_value=1
        with patch('visual_aid.device.load_gamma') as native:
            self.assertFalse(d.gamma(np.arange(256,dtype=np.uint8)))
            native.assert_not_called();d.mmio.write.assert_not_called()

    def test_gamma_ready_uses_owned_mapping_and_complete_lut(self):
        d=Device.__new__(Device);d.mmio=Mock();d.mmio.read.return_value=0
        d.mmio.array=np.zeros(1024,np.uint32);lut=np.arange(256,dtype=np.uint8)
        with patch('visual_aid.device.load_gamma',return_value=True) as native:
            self.assertTrue(d.gamma(lut))
            self.assertIs(native.call_args.args[0],d.mmio.array)
            self.assertIs(native.call_args.args[1],lut)
            d.mmio.write.assert_not_called()

    def test_camera_timing_readback_and_banding_follow_actual_clock(self):
        for fps in (15,18,20,21,22,24,30):
            bus=SensorBus()
            bus.registers.update({0x3034:0x1a,0x3037:0x13,0x3108:1,
                                  0x380c:7,0x380d:0x64,0x380e:2,0x380f:0xe4})
            result=OV5640(bus,Mock()).configure_timing(fps)
            self.assertAlmostEqual(result['nominal_fps'],fps,delta=.02)
            self.assertEqual((bus.registers[0x3a08]<<8)|bus.registers[0x3a09],
                             int(result['nominal_sysclk_hz']/result['hts']/100))
            self.assertTrue(result['readback_verified'])
            if fps<=21:self.assertEqual(bus.registers[0x3035],0x41)
    def test_reused_output_matches_original_resizing_and_clears_old_osd(self):
        frame=np.random.RandomState(6).randint(0,256,(80,128,4),dtype=np.uint8)
        output=np.full((80,128,4),255,np.uint8)
        for split in (True,False):
            for zoom in (1,2,4):
                roi,_=crop_roi(frame,zoom,(.7,.3))
                pw=64 if split else 128
                ratio=min(pw/roi.shape[1],80/roi.shape[0]);rw,rh=int(roi.shape[1]*ratio),int(roi.shape[0]*ratio)
                expected=np.zeros_like(output);ox,oy=(pw-rw)//2,(80-rh)//2
                resized=cv2.resize(roi,(rw,rh),interpolation=cv2.INTER_LINEAR)
                expected[oy:oy+rh,ox:ox+rw]=resized
                if split:expected[oy:oy+rh,pw+ox:pw+ox+rw]=resized
                actual,_,_=compose(frame,zoom,(.7,.3),split,(128,80),out=output)
                self.assertIs(actual,output)
                np.testing.assert_array_equal(actual,expected)

    def test_capture_output_alias_rejected(self):
        frame=np.zeros((80,128,4),np.uint8)
        with self.assertRaises(ValueError):compose(frame,size=(128,80),out=frame)

    def test_owned_output_submitted_once_without_allocating_or_copying(self):
        d=Device.__new__(Device);d.hout=Mock();d.pending_output=None
        out=np.zeros((2,2,4),np.uint8);d.hout.newframe.return_value=out
        self.assertIs(d.prepare_display(),out)
        with self.assertRaises(RuntimeError):d.prepare_display()
        d.display(out)
        d.hout.newframe.assert_called_once()
        self.assertIs(d.hout.writeframe.call_args.args[0],out)
        self.assertIsNone(d.pending_output)
