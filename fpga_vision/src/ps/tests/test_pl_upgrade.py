from pathlib import Path
import sys,unittest
from unittest.mock import Mock,patch
from types import SimpleNamespace
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'runtime'))
from visual_aid.image import reconstruct_color,gray8,reference_enhance
from visual_aid.scanout import ParkedScanout
from visual_aid.controls import State
from visual_aid.local import TilePolicy,spatial_chroma,mapped_luma
from visual_aid.device import Device
from visual_aid.pl_runtime import run_pl
from visual_aid.image import AdaptivePolicy
from visual_aid.camera import OV5640
from camera_model import SensorBus


class PLUpgrade(unittest.TestCase):
    def test_camera_stability_retains_focus_timing_and_automatic_exposure(self):
        bus=SensorBus();bus.registers.update({0x3a00:0x58,0x3c01:0x24,0x3c00:0,
            0x3503:0,0x380c:5,0x380d:139,0x3022:4,0x350b:32})
        protected={k:bus.registers[k] for k in (0x3503,0x380c,0x380d,0x3022,0x350b)}
        r=OV5640(bus,Mock()).stable_exposure()
        self.assertTrue(r['readback_verified']);self.assertEqual(bus.registers[0x3a1b],56)
        self.assertEqual(bus.registers[0x3a1e],32)
        self.assertEqual({k:bus.registers[k] for k in protected},protected)

    def test_detail_preset_preserves_weak_text_and_resets_without_extra_smoothing(self):
        image=np.full((48,96,3),80,np.uint8);image[12:38,55:57]=70
        detail=State('detail');detail.mode=4;detail.sharpness=0
        balanced=State('balanced');balanced.mode=4;balanced.sharpness=0
        sharp=reference_enhance(image,detail.config(),quality=detail.quality_config())
        smooth=reference_enhance(image,balanced.config(),quality=balanced.quality_config())
        # Detail bypasses the mean replacement that erases weak print strokes.
        self.assertLess(float(sharp[15:35,55,0].mean()),float(smooth[15:35,55,0].mean()))
        detail.denoise=9;detail.noise=10;detail.encoder('long')
        self.assertEqual((detail.denoise,detail.sharpness,detail.noise),(0,4,1))
        self.assertFalse(detail.quality_config()&256)

    def test_independent_renderer_protects_raw_and_canvas_owners(self):
        dev=Device.__new__(Device);dev.mmio=Mock();dev.pl_canvas=True
        dev.buffers=[SimpleNamespace(physical_address=0x100000+i*0x400000) for i in range(3)]
        dev.canvases=[SimpleNamespace(physical_address=0x2000000+i*0x400000) for i in range(4)]
        dev.canvas_layout={i:True for i in range(4)}
        dev.scanout=Mock();dev.scanout.pinned_raw=None;dev.scanout.status.return_value=(3,3)
        dev.scanout.idle.side_effect=lambda i:i!=3
        dev.rendering=None;dev.pending_present=None;dev.render_live=True
        dev.render_count=dev.display_count=0;dev.render_first=dev.render_last=None
        dev.armed=1;dev.mmio.read.return_value=0
        view=(0x81,0,(0,0,1280,720),True)
        slot=dev.queue_render(0,123,12,view)
        self.assertEqual(slot,0) # Raw slot 1 is capturing independently.
        self.assertEqual(dev.free_raw_slot(exclude=(1,)),2)
        dev.scanout.pinned_raw=2
        with self.assertRaises(RuntimeError):dev.free_raw_slot(exclude=(1,))
        with self.assertRaises(RuntimeError):dev.present_canvas(slot,12)
        dev.mmio.write.assert_any_call(0xc0,0x100000)
        dev.mmio.write.assert_any_call(0xc4,1)
        dev.mmio.read.return_value=2;dev.service_render()
        self.assertIsNone(dev.rendering);self.assertEqual(dev.render_count,1)
        dev.scanout.present.assert_called_once_with(slot)
        dev.scanout.status.return_value=(slot,slot);dev.service_render()
        self.assertEqual(dev.display_count,1)

    def test_shutdown_retains_memory_until_independent_canvas_stops(self):
        dev=Device.__new__(Device);dev.closed=False;dev.pl_canvas=True;dev.mmio=Mock()
        dev.mmio.read.side_effect=lambda offset:1 if offset==0x74 else 0
        dev.buffers=[Mock()];dev.canvases=[Mock()];dev.hout=None
        with patch('visual_aid.device.time.monotonic',side_effect=[0.,1.]):
            with self.assertRaises(RuntimeError):dev.close()
        dev.buffers[0].freebuffer.assert_not_called();dev.canvases[0].freebuffer.assert_not_called()

    def test_spatial_chroma_reduces_flat_patch_noise_and_preserves_edges_and_raw_pane(self):
        rng=np.random.RandomState(14)
        rgb=(60+rng.randint(-9,10,(40,96,3))).astype(np.uint8);rgb[:,70:73]=[5,5,5]
        cfg=4|8|16|(6<<17);out=spatial_chroma(rgb,cfg,256)
        np.testing.assert_array_equal(out[:,:50],rgb[:,:50])
        self.assertLessEqual(np.abs(out[:,70:73].astype(int)-rgb[:,70:73]).max(),1)
        delta=lambda p:p[3:-3,52:67,0].astype(float)-p[3:-3,52:67,2]
        self.assertLess(delta(out).std(),delta(rgb).std()*.8)
        np.testing.assert_array_equal(spatial_chroma(rgb,cfg,0),rgb)

    def test_local_map_bounds_shadows_highlights_and_tile_boundaries(self):
        policy=TilePolicy();means=np.tile(np.linspace(20,180,8),(6,1))
        gains=policy.update(means,(0,0));self.assertTrue(np.all((gains>=192)&(gains<=384)))
        values=[mapped_luma(80,120,x,360,4,128,gains) for x in range(1280)]
        self.assertLessEqual(np.abs(np.diff(values)).max(),1)
        self.assertLessEqual(np.max(np.abs(np.asarray(values)-120)),24)
        for source,target in ((0,100),(23,100),(80,224),(80,255)):
            self.assertEqual(mapped_luma(source,target,300,360,4,128,gains),target)
        for _ in range(12):
            updated=policy.update(np.flip(means,axis=1),(0,0))
            self.assertLessEqual(np.abs(updated.astype(int)-gains.astype(int)).max(),2)
            gains=updated

    def test_pl_loop_freeze_pan_split_and_resume_preserve_owned_buffers(self):
        class Buffer(np.ndarray):
            def flush(self):pass
            def invalidate(self):
                if dev.armed is not None:
                    assert not np.shares_memory(self,dev.buffers[dev.armed])
                dev.cache_invalidations += 1
        class Backend:
            set_view=Device.set_view
            free_raw_slot=Device.free_raw_slot
            free_canvas_slot=Device.free_canvas_slot
            slot_config=lambda self,*args:None
            def __init__(self):
                self.buffers=[np.full((720,1280),0x00404040,np.uint32).view(Buffer) for _ in range(3)]
                self.cache_invalidations=0
                for buffer in self.buffers:buffer.flags.writeable=False
                self.canvases=[np.zeros((720,1280),np.uint32).view(Buffer) for _ in range(4)]
                self.mmio=Mock();self.mmio.read.return_value=0
                self.scanout=ParkedScanout.__new__(ParkedScanout);self.scanout.pinned_raw=None
                self.scanout.status=lambda:(self.active,self.active)
                self.active=3;self.scanout.present=lambda slot:setattr(self,'active',slot)
                self.views={};self.armed=None;self.n=0;self.frozen_ids=[]
                self.rendering=None;self.render_live=True;self.canvas_layout={}
                self.render_count=0;self.display_count=0;self.render_first=self.render_last=None
            def service_render(self):
                if self.rendering is not None:
                    assert self.rendering['raw']!=self.armed
                    if self.render_live:self.active=self.rendering['canvas']
                    self.render_count+=1;self.display_count+=int(self.render_live)
                    self.render_first=0.;self.render_last=float(self.render_count)
                    self.rendering=None
            def arm(self,index):
                assert index!=self.scanout.pinned_raw
                assert self.rendering is None or index!=self.rendering['raw']
                self.armed=index;self.views[index]=self.view_request
            def finish(self,rearm,invalidate):
                assert rearm and not invalidate
                self.n+=1;index=self.armed;self.armed=None
                self.arm(self.free_raw_slot(exclude=(index,)))
                return index,self.n,self.buffers[index].view(np.uint8).reshape(720,1280,4)
            def queue_render(self,index,frame_id,cfg,view):
                self.service_render()
                assert index!=self.armed
                slot=self.free_canvas_slot()
                self.rendering={'raw':index,'canvas':slot}
            def tile_statistics(self):return {'frame_id':self.n,'means':np.full((6,8),64.),'mean':64.}
            def gamma(self,lut):return True
            def local_gains(self,gains):return True
            def status_text(self,lines):return True
            def counters(self):return {}
        dev=Backend();state=State('balanced');state.mode=4
        controls=Mock();controls.poll.side_effect=[[],['freeze'],['zoom'],['right'],['split'],['freeze']]+[[]]*20
        encoder=Mock();encoder.poll.return_value=([],{})
        report={'unique_camera_frames':0,'events':[],'samples':[],'camera_capture_verified':False}
        clock=[0.]
        def now():clock[0]+=.01;return clock[0]
        args=SimpleNamespace(seconds=1.)
        with patch('visual_aid.pl_runtime.time.monotonic',side_effect=now),patch('builtins.print'):
            run_pl(dev,state,controls,encoder,AdaptivePolicy(),None,args,report,0,'OFF',lambda lut,b:lut)
        self.assertGreater(dev.n,6);self.assertIsNone(dev.scanout.pinned_raw)
        self.assertGreater(dev.cache_invalidations,0)
        self.assertEqual(state.auto_status['status'],'active')
        self.assertTrue(report['camera_capture_verified']);self.assertFalse(state.frozen)
        dev.mmio.write.assert_any_call(0x78,state.quality_config())

    def test_color_compensation_increases_dark_object_saturation_preserving_hue(self):
        image=np.tile(np.array([20,40,80],np.uint8),(20,32,1));y=gray8(image).astype(int)
        target=np.full(y.shape,110)
        old=reconstruct_color(image,y,target,0);new=reconstruct_color(image,y,target,0x11)
        saturation=lambda p:(p.max(axis=2).astype(float)-p.min(axis=2))/np.maximum(1,p.max(axis=2))
        self.assertGreater(float(saturation(new).mean()),float(saturation(old).mean())+.03)
        self.assertLessEqual(np.abs(gray8(new).astype(int)-target).max(),1)
        self.assertTrue(np.all(new[:,:,2]>new[:,:,1]));self.assertTrue(np.all(new[:,:,1]>new[:,:,0]))
        neutral=np.full_like(image,40)
        np.testing.assert_array_equal(reconstruct_color(neutral,gray8(neutral).astype(int),target,0x11),np.full_like(image,110))

    def test_gamut_compression_bounds_channels_without_independent_hue_clipping(self):
        image=np.tile(np.array([10,50,200],np.uint8),(2,2,1));y=gray8(image).astype(int)
        for level in (0,10,220,250,255):
            out=reconstruct_color(image,y,np.full(y.shape,level),0x21)
            self.assertLessEqual(np.abs(gray8(out).astype(int)-level).max(),1)
            self.assertTrue(np.all(out[:,:,2]>=out[:,:,1]));self.assertTrue(np.all(out[:,:,1]>=out[:,:,0]))

    def test_large_binary_window_and_threshold_are_real_user_controls(self):
        state=State('balanced');state.mode=3;state.split=False
        self.assertTrue(state.quality_config()&64)
        shade=np.tile(np.rint(210-.75*np.arange(96)).astype(np.uint8),(80,1))
        image=np.repeat(shade[:,:,None],3,axis=2);image[:,45:50]-=5
        large=reference_enhance(image,state.config(),quality=state.quality_config())
        state.window31=0
        small=reference_enhance(image,state.config(),quality=state.quality_config())
        self.assertFalse(np.array_equal(large,small))
        state.selected=state.parameters.index('binary_c');state.encoder('rotate',100)
        self.assertEqual((state.config()>>8)&255,32)

    def test_division_961_is_exact_for_all_valid_31x31_sums(self):
        n=np.arange(31*31*255+1,dtype=np.int64)
        np.testing.assert_array_equal((n*139665)>>27,n//961)

    def test_capture_never_reuses_active_pending_or_pinned_scanout_slots(self):
        display=ParkedScanout.__new__(ParkedScanout);display.mmio=Mock();display.pinned_raw=None
        word=[0|(1<<16)]
        display.mmio.read.side_effect=lambda address:word[0] if address==0x28 else 0
        self.assertEqual(display.free_capture_slot(),2)
        display.pinned_raw=2
        display.wait=Mock(side_effect=lambda target:word.__setitem__(0,target|(target<<16)))
        self.assertEqual(display.free_capture_slot(),1)
        self.assertTrue(display.idle(1));self.assertFalse(display.idle(0))
        display.present(2)
        display.mmio.write.assert_called_with(0x28,2)

    def test_no_free_slot_and_dma_error_fail_without_overwriting_a_buffer(self):
        display=ParkedScanout.__new__(ParkedScanout);display.mmio=Mock();display.pinned_raw=2
        display.mmio.read.side_effect=lambda address:0 if address==0x28 else 0
        with self.assertRaises(RuntimeError):display.free_capture_slot(exclude=(1,))
        display.mmio.write.assert_not_called()
        display.mmio.read.side_effect=lambda address:0x20 if address==4 else 0
        with self.assertRaises(IOError):display.present(1)
        display.mmio.write.assert_not_called()


if __name__=='__main__':unittest.main()
