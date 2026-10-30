from pathlib import Path
import ast
import importlib
import json
import sys
import types
import unittest
from unittest.mock import Mock, patch
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'runtime'))
from visual_aid.image import compose, crop_roi, reference_enhance, trailing_mean, AdaptivePolicy
from visual_aid.controls import State, Controls
from visual_aid.camera import OV5640
from visual_aid.device import Device
from visual_aid.sensors import BH1750
from visual_aid.bus import I2CBus
from camera_model import SensorBus


class Images(unittest.TestCase):
    def setUp(self):
        self.image = np.random.RandomState(3).randint(0, 256, (80, 128, 3), dtype=np.uint8)

    def test_same_roi_in_both_panes_and_aspect(self):
        for zoom in (1, 2, 4):
            canvas, roi, rect = compose(self.image, zoom, (0.7, 0.2), True, (128, 80))
            np.testing.assert_array_equal(canvas[:, :64], canvas[:, 64:])
            self.assertEqual(roi.shape[:2], (80//zoom, 128//zoom))
            self.assertEqual(rect[2:], (128//zoom, 80//zoom))

    def test_frozen_full_source_can_pan(self):
        frozen = self.image.copy()
        left, _ = crop_roi(frozen, 4, (0.1, 0.5))
        right, _ = crop_roi(frozen, 4, (0.9, 0.5))
        self.assertFalse(np.array_equal(left, right))
        np.testing.assert_array_equal(frozen, self.image)

    def test_crop_clamps(self):
        roi, rect = crop_roi(self.image, 4, (-100, 100))
        self.assertEqual(rect, (0, 60, 32, 20))

    def test_invalid_zoom(self):
        with self.assertRaises(ValueError):
            crop_roi(self.image, 3)

    def test_raw_and_split_bypass(self):
        np.testing.assert_array_equal(reference_enhance(self.image, 0), self.image)
        np.testing.assert_array_equal(reference_enhance(self.image, 0xb9)[:, :64], self.image[:, :64])

    def test_constant_local_window(self):
        g = np.full((24, 32), 91, dtype=np.uint8)
        self.assertEqual(int(trailing_mean(g, 15)[14, 14]), 91)
        self.assertEqual(int(trailing_mean(g, 3)[2, 2]), 91)

    def test_negative_binary_threshold_never_wraps(self):
        g = np.full((24, 32, 3), 40, dtype=np.uint8)
        result = reference_enhance(g, 3 | (255 << 8))
        self.assertTrue(np.all(result[14:, 14:] == 255))

    def test_policy_throttle_and_missing_lux(self):
        p = AdaptivePolicy()
        self.assertIsNotNone(p.update(np.zeros((24, 32, 3), np.uint8), 0))
        self.assertIsNone(p.update(self.image, 0.1, None))
        self.assertTrue(np.all(np.diff(p.lut.astype(int)) >= 0))

    def test_denoise_preserves_high_contrast_thin_stroke(self):
        page = np.full((24, 64, 3), 240, dtype=np.uint8)
        page[:, 10] = 10
        np.testing.assert_array_equal(reference_enhance(page, 1 | 16), page)

    def test_split_seam_does_not_leak_other_pane_into_filter(self):
        page = np.full((24, 64, 3), 250, dtype=np.uint8)
        page[:, 32:] = 60
        result = reference_enhance(page, 1 | 8 | 16 | 32 | (3 << 6))
        np.testing.assert_array_equal(result, page)


class InputControls(unittest.TestCase):
    def test_button_bounce_and_no_hold_repeat(self):
        c = Controls()
        self.assertEqual(c.poll(1, 0.0), [])
        self.assertEqual(c.poll(0, 0.01), [])
        self.assertEqual(c.poll(1, 0.02), [])
        self.assertEqual(c.poll(1, 0.05), ['mode'])
        self.assertEqual(c.poll(1, 2.0), [])

    def test_pan_hold_repeats_but_center_does_not(self):
        c = Controls()
        c.poll(1 << 4, 0)
        self.assertEqual(c.poll(1 << 4, 0.03), ['up'])
        self.assertEqual(c.poll(1 << 4, 0.5), ['up'])
        z = Controls();z.poll(1 << 8, 0)
        self.assertEqual(z.poll(1 << 8, 0.03), ['zoom'])
        self.assertEqual(z.poll(1 << 8, 1), [])

    def test_zoom_and_roi_bounds(self):
        s = State();s.apply('zoom');s.apply('zoom')
        self.assertEqual(s.zoom, 4)
        for _ in range(100):
            s.apply('left');s.apply('down')
        self.assertEqual(s.center, [0.125, 0.875])
        s.apply('zoom');self.assertEqual(s.center, [0.5, 0.5])

    def test_board_buttons(self):
        s = State()
        for name, attr in [('freeze','frozen'),('split','split'),('auto','automatic')]:
            before = getattr(s, attr);s.apply(name);self.assertNotEqual(before, getattr(s, attr))


class CameraAndBus(unittest.TestCase):
    def test_sccb_register_addressing(self):
        b = Mock();b.transfer.return_value = b'\x56'
        c = OV5640(b, Mock());c.write(0x3008, 2)
        b.transfer.assert_called_with(0x3c, b'\x30\x08\x02')
        self.assertEqual(c.read(0x300a), 0x56)
        b.transfer.assert_called_with(0x3c, b'\x30\x0a', 1)

    def test_wrong_camera_id_stops_before_configuration(self):
        c = OV5640(Mock(), Mock());c.read = Mock(return_value=0);c.write = Mock()
        with patch('visual_aid.camera.time.sleep'), self.assertRaises(IOError):
            c.initialize()
        c.write.assert_not_called()

    def test_af_firmware_and_ack_vs_focus(self):
        bus = SensorBus();result = OV5640(bus, Mock()).autofocus(True)
        self.assertEqual(bus.commands, [8, 4])
        self.assertEqual(result['verified_readback_bytes'], 4077)
        self.assertTrue(result['full_readback_verified'])
        self.assertFalse(result['firmware_focus_reported'])
        self.assertFalse(result['optical_focus_observed'])

    def test_single_af_waits_for_focus(self):
        bus=SensorBus();result=OV5640(bus,Mock()).autofocus(False)
        self.assertEqual(bus.commands,[8,3])
        self.assertGreaterEqual(bus.focus_reads,2)
        self.assertTrue(result['firmware_focus_reported'])

    def test_i2c_nack_is_not_silently_ignored(self):
        b = I2CBus(Mock());b.bit=Mock(return_value=1)
        with self.assertRaises(IOError):b.write_byte(0x78)

    def test_bh1750_startup_delay_and_conversion(self):
        b=Mock();b.transfer.return_value=b'\x01\x20'
        with patch('visual_aid.sensors.time.monotonic',return_value=10):
            sensor=BH1750(b);self.assertIsNone(sensor.read())
        with patch('visual_aid.sensors.time.monotonic',return_value=11):self.assertEqual(sensor.read(),240)

    def test_ported_vl53l0x_imports_without_blinka(self):
        self.assertTrue(hasattr(importlib.import_module('visual_aid.vl53l0x_vendor'),'VL53L0X'))


class Ownership(unittest.TestCase):
    def test_output_only_vdma_never_instantiates_missing_s2mm(self):
        mmio=Mock();mmio.read.side_effect=lambda a:0x56410400 if a==0 else 0
        output=Mock()
        core_desc={'phys_addr':0x43c00000,'addr_range':65536}
        dma_desc={'interrupts':{'mm2s_introut':{'controller':'','index':0}}}
        overlay=types.SimpleNamespace(hdmi_out=output,ip_dict={'assist_core/s_axi':core_desc,'display_vdma':dma_desc})
        buffers=[Mock(),Mock()];xlnk=Mock();xlnk.cma_array.side_effect=buffers
        class OutputOnly:
            def __init__(self,*args):
                raise AssertionError('Full VDMA constructor requires missing S2MM')
            MM2SChannel=Mock(return_value=Mock())
        raw_dma=types.SimpleNamespace(mmio=Mock())
        raw_dma.mmio.read.return_value=0x11089
        pynq=types.ModuleType('pynq');pynq.Overlay=Mock(return_value=overlay)
        pynq.Xlnk=Mock(return_value=xlnk)
        pynq.DefaultIP=Mock(side_effect=[types.SimpleNamespace(mmio=mmio),raw_dma])
        video=types.ModuleType('pynq.lib.video');video.VideoMode=Mock();video.PixelFormat=Mock()
        video.PIXEL_BGR=types.SimpleNamespace(in_color=[1]*12,out_color=[1]*12)
        dma=types.ModuleType('pynq.lib.video.dma');dma.AxiVDMA=OutputOnly
        with patch('visual_aid.device.Path.is_file',return_value=True), \
             patch('visual_aid.device.wait_for_boot_overlay'), patch.dict(sys.modules,{
                'pynq':pynq,'pynq.lib':types.ModuleType('pynq.lib'),'pynq.lib.video':video,'pynq.lib.video.dma':dma}):
            device=Device(__file__)
            self.assertIs(output._vdma,raw_dma)
            self.assertEqual(pynq.DefaultIP.call_args_list[0].args,(core_desc,))
            self.assertEqual(pynq.DefaultIP.call_args_list[1].args[0]['interrupts'],{})
            self.assertIn('mm2s_introut',dma_desc['interrupts'])
            video.VideoMode.assert_called_once_with(1280,720,32,60)
            self.assertTrue(all(c.kwargs['cacheable']==1 for c in xlnk.cma_array.call_args_list))
            device.close()
        for buffer in buffers:
            buffer.flush.assert_called_once();buffer.freebuffer.assert_called_once()

    def test_rearm_busy_forbidden(self):
        d=Device.__new__(Device);d.armed=1;d.mmio=Mock()
        with self.assertRaises(RuntimeError):d.arm(0)

    def test_gamma_does_not_write_pending_bank(self):
        d=Device.__new__(Device);d.mmio=Mock();d.mmio.read.return_value=1
        self.assertFalse(d.gamma(np.arange(256)));d.mmio.write.assert_not_called()

    def test_stale_done_is_not_returned(self):
        d=Device.__new__(Device);d.armed=0;d.expected_id=8;d.mmio=Mock()
        d.mmio.read.side_effect=lambda a: 2 if a == 0x18 else 7
        with self.assertRaises(TimeoutError):d.finish(timeout=0.002)
        d.mmio.write.assert_called_with(4,0)

    def test_close_waits_for_outstanding_dma_before_free(self):
        d=Device.__new__(Device);d.closed=False;d.mmio=Mock();d.hout=Mock()
        buffers=[Mock(),Mock()];d.buffers=buffers
        statuses=iter([1,1,0])
        d.mmio.read.side_effect=lambda offset: next(statuses)
        for buffer in buffers:
            buffer.freebuffer.side_effect=lambda: self.assertEqual(d.mmio.read.call_count,3)
        with patch('visual_aid.device.time.sleep'):
            d.close()
        d.mmio.write.assert_called_once_with(4,0)
        for buffer in buffers:buffer.freebuffer.assert_called_once()
        self.assertTrue(d.closed)

    def test_close_timeout_retains_buffers(self):
        d=Device.__new__(Device);d.closed=False;d.mmio=Mock();d.mmio.read.return_value=1
        d.hout=Mock();buffers=[Mock(),Mock()];d.buffers=buffers
        with patch('visual_aid.device.time.monotonic',side_effect=[0,1]), self.assertRaises(RuntimeError):
            d.close()
        for buffer in buffers:buffer.freebuffer.assert_not_called()
        d.hout.close.assert_not_called()
        self.assertIs(d.buffers,buffers)
        self.assertFalse(d.closed)

    def test_gpio_constraints_no_pin_conflict(self):
        pins=json.loads((ROOT/'docs/pins.json').read_text())
        self.assertEqual(len(pins),len(set(pins.values())))
        self.assertEqual(pins['cam_pclk'],'U18')
        self.assertEqual(pins['joy_n[0]'],'V13')

    def test_board_python_36_syntax(self):
        for p in (ROOT/'runtime').rglob('*.py'):
            ast.parse(p.read_text(encoding='utf-8'),filename=str(p),feature_version=(3,6))


if __name__=='__main__':unittest.main(verbosity=2)
