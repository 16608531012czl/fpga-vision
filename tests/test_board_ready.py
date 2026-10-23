"""Regression tests for board integration without a connected FPGA board."""
from pathlib import Path
import asyncio
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'software'))
from camera_model import SensorBus
from visual_aid.camera import OV5640, ASSETS
from visual_aid.device import Device, _PollingFrameReady
from visual_aid.image import compose
from visual_aid.integrity import verify_payload

spec = importlib.util.spec_from_file_location('enhanced_app', ROOT/'software/run_board.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class BoardReady(unittest.TestCase):
    def test_af_verifies_all_sram_and_never_executes_corrupt_code(self):
        firmware = (ASSETS/'ov5640_af.bin').read_bytes()
        bus = SensorBus(corrupt=0x81ff)
        with self.assertRaisesRegex(IOError, 'SRAM readback mismatch'):
            OV5640(bus, Mock()).autofocus()
        self.assertEqual(bus.commands, [])
        self.assertEqual(bus.registers[0x3000], 0x20)
        bus = SensorBus(); progress = []
        result = OV5640(bus, Mock()).autofocus(progress=lambda a,b: progress.append((a,b)))
        self.assertEqual(result['full_readback_sha256'], hashlib.sha256(firmware).hexdigest())
        self.assertEqual(progress[-1], (len(firmware), len(firmware)))
        self.assertFalse(result['optical_focus_observed'])

    def test_polling_mm2s_times_out_and_reports_dma_faults(self):
        mmio = Mock(); loop = asyncio.new_event_loop()
        try:
            mmio.read.side_effect = [0, 0x1000]
            loop.run_until_complete(_PollingFrameReady(mmio).wait())
            mmio.read.side_effect = None; mmio.read.return_value = 0x20
            with self.assertRaisesRegex(IOError, 'DMA error'):
                loop.run_until_complete(_PollingFrameReady(mmio).wait())
            mmio.read.return_value = 0
            with self.assertRaisesRegex(TimeoutError, 'frame timeout'):
                loop.run_until_complete(_PollingFrameReady(mmio, timeout=0).wait())
        finally:
            loop.close()

    def test_cached_capture_rearms_before_invalidate_and_is_read_only(self):
        events = []
        class Frame(np.ndarray):
            def invalidate(self):
                events.append('invalidate'); self[:] = np.uint32(0x00332211)
        first = np.zeros((720,1280), np.uint32).view(Frame)
        second = np.zeros_like(first)
        first.physical_address=0x10000000;second.physical_address=0x10400000
        dev=Device.__new__(Device);dev.buffers=[first,second];dev.armed=0;dev.expected_id=7;dev.mmio=Mock()
        reads={0x18:iter([0,2,2]),0x1c:iter([7,7])}
        dev.mmio.read.side_effect=lambda a:next(reads[a])
        dev.mmio.write.side_effect=lambda a,v:events.append((a,v))
        index,frame_id,image=dev.finish(rearm=True)
        self.assertEqual((index,frame_id,dev.armed,dev.expected_id),(0,7,1,8))
        self.assertLess(events.index((0x10,0x10400000)),events.index('invalidate'))
        np.testing.assert_array_equal(image[0,0],[0x11,0x22,0x33,0])
        self.assertFalse(image.flags.writeable)
        dev.hout=Mock();output=np.empty((720,1280,4),np.uint8)
        dev.hout.newframe.return_value=output;dev.display(image)
        np.testing.assert_array_equal(output,image)
        dev.hout.writeframe.assert_called_once_with(output)

    def test_compose_preserves_bgrx_layout_and_duplicates_same_roi(self):
        image=np.zeros((72,128,4),np.uint8);image[:,:,:3]=[10,20,30]
        image.flags.writeable=False
        canvas,roi,bounds=compose(image,2,(0.4,0.7),True,(128,72))
        self.assertEqual(canvas.shape,(72,128,4));self.assertTrue(canvas.flags.c_contiguous)
        self.assertFalse(roi.flags.writeable)
        np.testing.assert_array_equal(canvas[:,:64],canvas[:,64:])
        self.assertTrue(np.all(canvas[:,:,3]==0))

    def test_pipeline_reciprocals_are_exact_over_entire_input_domains(self):
        for width, multiplier, shift, divisor in ((13,7282,16,9),(17,149131,25,225)):
            n=np.arange(1<<width,dtype=np.int64)
            np.testing.assert_array_equal((n*multiplier)>>shift,n//divisor)

    def test_cli_stages_and_explicit_diagnostic_fallback(self):
        live=app.parse_args(['--io-confirmed'])
        self.assertEqual((live.stage,live.af,live.camera_fps,live.seconds),('live','continuous',20,0))
        self.assertEqual((live.mode,live.tone_profile),('gray','stable'))
        compare=app.parse_args(['--io-confirmed','--mode','color','--tone-profile','legacy'])
        self.assertEqual((compare.mode,compare.tone_profile),('color','legacy'))
        bars=app.parse_args(['--colorbars','--io-confirmed'])
        self.assertEqual((bars.stage,bars.af),('colorbars','off'))
        live=app.parse_args(['--io-confirmed','--no-af','--no-light','--no-distance'])
        self.assertEqual(live.af,'off');self.assertTrue(live.no_sensors)
        for seconds in ('-1','nan','inf'):
            with patch('sys.stderr'),self.assertRaises(SystemExit):
                app.parse_args(['--io-confirmed','--seconds',seconds])

    def run_stage(self,stage,**kwargs):
        with tempfile.TemporaryDirectory() as directory:
            args=app.parse_args(['--pipeline','cpu','--stage',stage,'--io-confirmed','--seconds','1','--report',str(Path(directory)/'report.json')])
            for k,v in kwargs.items():setattr(args,k,v)
            dev=Mock();dev.counters.return_value={'capture_id':0,'dma_errors':0}
            dev.prepare_display.side_effect=lambda:np.empty((720,1280,4),np.uint8)
            dev.mmio.read.return_value=0x1f
            dev.finish.return_value=(0,1,np.zeros((720,1280,4),np.uint8))
            camera=Mock();camera.initialize.return_value={};camera.image_quality.return_value={};camera.stable_exposure.return_value={}
            if kwargs.get('af_error'):
                camera.autofocus.side_effect=IOError('AF unavailable')
            with patch.object(app,'verify_payload',return_value={'abi':0x56410400}),patch.object(app,'Device',return_value=dev) as ctor, \
                 patch.object(app,'OV5640',return_value=camera) as camera_ctor,patch.object(app,'active',side_effect=[True,False]), \
                 patch.object(app.time,'sleep'),patch('builtins.print'):
                outcome=app.run(args)
            return outcome,json.loads(Path(args.report).read_text()),dev,ctor,camera_ctor

    def test_static_is_independent_of_camera_and_preserves_color_order(self):
        code,report,dev,ctor,camera=self.run_stage('static')
        self.assertEqual(code,0);self.assertFalse(report['camera_capture_verified'])
        self.assertIsNone(report['display_observed']);camera.assert_not_called()
        self.assertFalse(ctor.call_args.kwargs['capture'])
        np.testing.assert_array_equal(dev.display.call_args.args[0][300,[0,600,1279]],
                                      [[255,0,0,0],[0,255,0,0],[0,0,255,0]])
        dev.close.assert_called_once()

    def test_keys_do_not_start_hdmi_or_camera(self):
        with patch.object(app,'Controls') as controls:
            controls.return_value.poll.return_value=['up']
            code,report,dev,ctor,camera=self.run_stage('keys')
        self.assertEqual(code,0);self.assertFalse(ctor.call_args.kwargs['display'])
        self.assertEqual(report['events'][0]['key'],'up');camera.assert_not_called()
        dev.display.assert_not_called();dev.arm.assert_not_called()

    def test_colorbars_bypasses_enhancement_and_af(self):
        code,report,dev,ctor,camera=self.run_stage('colorbars')
        self.assertEqual(code,0);self.assertTrue(report['camera_capture_verified'])
        camera.return_value.autofocus.assert_not_called()
        dev.mmio.write.assert_called_with(0x30,0)
        dev.finish.assert_called_once_with(rearm=True)

    def test_af_failure_keeps_live_display_and_records_warning(self):
        code,report,dev,ctor,camera=self.run_stage('live',no_sensors=True,af_error=True)
        self.assertEqual(code,0);self.assertTrue(report['camera_capture_verified'])
        self.assertEqual(report['autofocus']['outcome'],'error')
        self.assertTrue(report['warnings']);dev.display.assert_called_once()

    def test_color_lowlight_run_records_estimates_and_selected_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            args=app.parse_args(['--pipeline','cpu','--io-confirmed','--no-af','--no-sensors','--mode','color',
                                 '--seconds','1','--report',str(Path(directory)/'report.json')])
            dev=Mock();dev.mmio.read.return_value=0
            dev.prepare_display.side_effect=lambda:np.empty((720,1280,4),np.uint8)
            dev.counters.return_value={'capture_id':0}
            dev.finish.return_value=(0,1,np.full((48,64,4),40,np.uint8))
            camera=Mock();camera.initialize.return_value={};camera.image_quality.return_value={};camera.stable_exposure.return_value={}
            with patch.object(app,'verify_payload',return_value={'abi':0x56410400}), \
                 patch.object(app,'Device',return_value=dev),patch.object(app,'OV5640',return_value=camera), \
                 patch.object(app,'active',side_effect=[True]*15+[False]),patch('builtins.print'):
                self.assertEqual(app.run(args),0)
            report=json.loads(Path(args.report).read_text())
            sample=report['samples'][0]
            self.assertEqual(sample['config'] & 7,4)
            self.assertEqual(sample['tone']['profile'],'stable')
            self.assertEqual(sample['tone']['mean'],40)
            self.assertGreater(sample['tone']['lut_mean_estimate'],40)
            self.assertIn('not HDMI',sample['tone']['estimate_scope'])

    def test_manual_to_auto_restores_gamma_even_when_scene_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            args=app.parse_args(['--pipeline','cpu','--io-confirmed','--no-af','--no-sensors','--seconds','1',
                                 '--report',str(Path(directory)/'report.json')])
            dev=Mock();dev.mmio.read.return_value=0;dev.counters.return_value={'capture_id':0}
            dev.prepare_display.side_effect=lambda:np.empty((720,1280,4),np.uint8)
            frame=np.zeros((720,1280,4),np.uint8)
            dev.finish.side_effect=[(0,1,frame),(1,2,frame),(0,3,frame)]
            dev.gamma.side_effect=[False,True,True]
            policy=Mock();policy.lut=(np.arange(256)//2).astype(np.uint8);policy.update.return_value=None
            policy.status.return_value={'mean':None}
            controls=Mock();controls.poll.side_effect=[['auto'],[],['auto']]
            camera=Mock();camera.initialize.return_value={};camera.image_quality.return_value={};camera.stable_exposure.return_value={}
            with patch.object(app,'verify_payload',return_value={'abi':0x56410400}), \
                 patch.object(app,'Device',return_value=dev),patch.object(app,'OV5640',return_value=camera), \
                 patch.object(app,'AdaptivePolicy',return_value=policy),patch.object(app,'Controls',return_value=controls), \
                 patch.object(app,'active',side_effect=[True,True,True,False]),patch('builtins.print'):
                self.assertEqual(app.run(args),0)
            self.assertEqual(dev.gamma.call_count,3)
            np.testing.assert_array_equal(dev.gamma.call_args_list[0].args[0],np.arange(256,dtype=np.uint8))
            np.testing.assert_array_equal(dev.gamma.call_args_list[1].args[0],np.arange(256,dtype=np.uint8))
            np.testing.assert_array_equal(dev.gamma.call_args_list[2].args[0],policy.lut)

    def test_sensor_stage_reports_missing_readings_without_fabrication(self):
        sensor=Mock();sensor.snapshot.return_value={'lux':50,'distance_mm':None,'errors':{'distance_mm':'missing'}}
        with patch.object(app,'SensorWorker',return_value=sensor):
            sensor.start.return_value=sensor
            code,report,dev,ctor,camera=self.run_stage('sensors')
        self.assertEqual(code,0);self.assertTrue(report['sensor_readings_observed']['lux'])
        self.assertFalse(report['sensor_readings_observed']['distance_mm']);self.assertTrue(report['warnings'])
        self.assertFalse(ctor.call_args.kwargs['display']);sensor.close.assert_called_once()

    def test_live_sensor_failure_keeps_image_policy_and_marks_lux_error(self):
        sensor=Mock();sensor.snapshot.return_value={'lux':None,'distance_mm':None,
                                                   'errors':{'lux':'SCL held low'}}
        with patch.object(app,'SensorWorker',return_value=sensor),patch.object(app.cv2,'putText') as text:
            sensor.start.return_value=sensor
            code,report,dev,ctor,camera=self.run_stage('live',no_distance=True,af='off')
        self.assertEqual(code,0);dev.display.assert_called_once()
        self.assertFalse(report['sensor_readings_observed']['lux'])
        self.assertIn('image statistics',report['warnings'][0])
        self.assertTrue(any('LUX ERR' in call.args[1] for call in text.call_args_list))

    def test_release_integrity_detects_modified_script_and_wrong_bit_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'board').mkdir()
            for name,data in [('run_board.py',b'print(1)'),('board/v.bit',b'bit'),('board/v.hwh',b'hwh')]:
                (root/name).write_bytes(data)
            hashes={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ('run_board.py','board/v.bit','board/v.hwh')}
            (root/'board/build_manifest.json').write_text(json.dumps({'project':'visual_aid_v3','abi':0x56410400,'payload_sha256':hashes}))
            verify_payload(root,root/'board/v.bit')
            with self.assertRaisesRegex(ValueError,'pair'):
                verify_payload(root,root/'board/other.bit')
            (root/'run_board.py').write_text('changed')
            with self.assertRaisesRegex(IOError,'hash mismatch'):
                verify_payload(root)


if __name__=='__main__':
    unittest.main(verbosity=2)
