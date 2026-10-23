"""PYNQ 2.4 backend with cached, read-only BGRX capture buffers."""
from pathlib import Path
import asyncio
import time
import numpy as np
from .startup import wait_for_boot_overlay
from .fastcompose import load_gamma,load_parameters
from .scanout import ParkedScanout


class _PollingFrameReady:
    """Wait for MM2S frame status without a PYNQ AXI interrupt controller."""

    def __init__(self, mmio, timeout=2):
        self.mmio = mmio
        self.timeout = timeout

    async def wait(self):
        deadline = time.monotonic()+self.timeout
        while True:
            status = self.mmio.read(0x04)
            if status & 0x70:
                raise IOError('HDMI MM2S DMA error: 0x{:08x}'.format(status))
            if status & 0x1000:
                return
            if time.monotonic() >= deadline:
                raise TimeoutError('HDMI frame timeout: MM2S status 0x{:08x}'.format(status))
            await asyncio.sleep(0.001)


class Device:
    def __init__(self, bitfile, display=True, capture=True,pl_canvas=False):
        from pynq import Overlay, Xlnk, DefaultIP
        from pynq.lib.video import VideoMode, PixelFormat, PIXEL_BGR
        from pynq.lib.video.dma import AxiVDMA
        p = Path(bitfile).resolve()
        if not p.is_file() or not p.with_suffix('.hwh').is_file():
            raise FileNotFoundError('Matching new-project .bit/.hwh are required: '+str(p))
        wait_for_boot_overlay()
        self.ol = Overlay(str(p))
        # PYNQ 2.4 exposes a module-reference slave under its bus name;
        # assist_core itself is a hierarchy because it also has master ports.
        self.mmio = DefaultIP(self.ol.ip_dict['assist_core/s_axi']).mmio
        if self.mmio.read(0) != 0x56410400:
            raise RuntimeError('Wrong overlay ABI; do not use the old project bitstream')
        self.buffers = []
        self.canvases=[]
        self.pl_canvas=pl_canvas
        self.scanout=None
        self.rendering=None
        self.render_live=True
        self.render_count=0
        self.display_count=0
        self.pending_present=None
        self.render_first=self.render_last=None
        self.view_request=(0x81,0,(0,0,1280,720),True)
        self.views={};self.canvas_layout={}
        self.hout = None
        self.pending_output = None
        self.armed = None
        self.closed = False
        try:
            self.mmio.write(4, 0)
            self.mmio.write(0x30, 0)
            self.xlnk = Xlnk()
            if pl_canvas and self.mmio.read(0x7c)!=0x504c0002:
                raise RuntimeError('PL canvas hardware feature signature missing')
            for _ in range((3 if pl_canvas else 2) if capture else 0):
                buffer = self.xlnk.cma_array(shape=(720, 1280), dtype=np.uint32, cacheable=1)
                self.buffers.append(buffer)
                # Clean allocation-time CPU writes once, before PL ownership.
                # CPU views stay read-only, so no dirty lines need flushing
                # on every rearm. Invalidate after each completed PL write.
                buffer.flush()
                buffer.flags.writeable = False
            if pl_canvas:
                for index in range(4):
                    canvas=self.xlnk.cma_array(shape=(720,1280),dtype=np.uint32,cacheable=1)
                    canvas.fill(0);canvas.flush();canvas.flags.writeable=False
                    self.canvases.append(canvas);self.canvas_layout[index]=True
            if not display:
                self.mmio.write(4, int(capture))
                return
            # PYNQ 2.4 AxiVDMA.__init__ unconditionally instantiates BOTH
            # directions. This overlay deliberately has only MM2S, so bind the
            # real output channel explicitly, without touching missing S2MM IRQ.
            # This design routes IRQ directly to the PS. PYNQ 2.4 requires
            # an AXI INTC for Interrupt(), so keep the metadata intact and use
            # a local description with cooperative MM2S status polling.
            dma_description = dict(self.ol.ip_dict['display_vdma'])
            dma_description['interrupts'] = {}
            self.display_dma = DefaultIP(dma_description)
            self.display_dma.framecount = 4
            self.display_dma.writechannel = AxiVDMA.MM2SChannel(
                self.display_dma, _PollingFrameReady(self.display_dma.mmio))
            self.hout = self.ol.hdmi_out
            self.hout._vdma = self.display_dma
            # Keep the writer's B,G,R,0 layout for one contiguous CPU copy.
            # The existing pixel_unpack IP discards byte 4 in 32-bpp mode.
            # Use BGR coefficients explicitly; default RGBA swaps red/blue.
            bgrx = PixelFormat(32, PIXEL_BGR.in_color, PIXEL_BGR.out_color)
            self.hout.configure(VideoMode(1280, 720, 32, 60), bgrx)
            self.hout.start()
            control = self.display_dma.mmio.read(0)
            self.display_dma.mmio.write(0, control & ~0x7000)
            if pl_canvas:
                self.display_dma.writechannel.stop()
                self.scanout=ParkedScanout(self.display_dma.mmio,self.canvases)
                for index in range(4):self.slot_config(index,0)
            self.mmio.write(4, int(capture))
        except BaseException:
            self.close()
            raise

    def arm(self, index):
        if self.armed is not None or self.mmio.read(0x18) & 1:
            raise RuntimeError('Capture buffer is still owned by DMA')
        self.expected_id = (self.mmio.read(0x1c)+1) & 0xffffffff
        if getattr(self,'pl_canvas',False):
            if index==self.scanout.pinned_raw or (self.rendering is not None and index==self.rendering['raw']):
                raise RuntimeError('Raw buffer is owned by renderer or frozen source')
            view,roi,bounds,split=self.view_request
            self.views[index]=self.view_request
            self.mmio.write(0x6c,roi);self.mmio.write(0x70,view)
        self.mmio.write(0x10, int(self.buffers[index].physical_address))
        self.mmio.write(0x14, 1)
        self.armed = index

    def finish(self, timeout=2, rearm=False,invalidate=True):
        if self.armed is None:
            raise RuntimeError('No armed frame')
        end = time.monotonic()+timeout
        while time.monotonic() < end:
            status = self.mmio.read(0x18)
            if status & 4:
                raise IOError('Capture rejected frame / AXI response; inspect counters')
            if status & 2 and self.mmio.read(0x1c) == self.expected_id:
                index = self.armed; frame_id = self.expected_id
                self.armed = None
                # Rearm within vertical blanking before slow CPU cache work.
                # The other capture buffer is separate from the HDMI buffers.
                if rearm:
                    if getattr(self,'pl_canvas',False):
                        self.arm(self.free_raw_slot(exclude=(index,)))
                    else:self.arm(1-index)
                # The PL has completed the final AXI B response. Discard stale
                # CPU cache lines before reading the newly captured frame.
                if invalidate:self.buffers[index].invalidate()
                bgrx = np.asarray(self.buffers[index]).view(np.uint8).reshape(720, 1280, 4)
                bgrx.flags.writeable = False
                return index, frame_id, bgrx
            if getattr(self,'pl_canvas',False):self.service_render()
            time.sleep(0.0002)
        self.mmio.write(4, 0)  # stop input; writer drains its outstanding AXI burst
        raise TimeoutError('No valid full DVP frame; check PCLK, sync polarity, byte order and counters')

    def set_view(self,state):
        zoom={1:0,2:1,4:2}[state.zoom]
        w,h=1280>>zoom,720>>zoom
        x=int(max(0,min(1280-w,round(state.center[0]*1280-w/2))))&~1
        y=int(max(0,min(720-h,round(state.center[1]*720-h/2))))&~1
        self.view_request=(128|int(state.split)|(zoom<<1),x|(y<<16),(x,y,w,h),bool(state.split))

    def slot_config(self,index,cfg):
        self.mmio.write(0xb0,index);self.mmio.write(0xb4,cfg)

    def present_canvas(self,index,cfg):
        if not self.pl_canvas:raise RuntimeError('PL canvas scanout not enabled')
        if self.rendering is not None and self.rendering['canvas']==index:
            raise RuntimeError('Renderer still owns requested canvas')
        self.slot_config(index,cfg)
        self.scanout.present(index)

    def free_raw_slot(self,exclude=()):
        # Raw DDR and HDMI canvases have independent ownership and indices.
        self.service_render()
        blocked=set(exclude)
        blocked.add(self.scanout.pinned_raw)
        if self.rendering is not None:blocked.add(self.rendering['raw'])
        for index in range(len(self.buffers)):
            if index not in blocked:return index
        raise RuntimeError('No free raw buffer; retain renderer and frozen ownership')

    def free_canvas_slot(self):
        self.service_render()
        for index in range(len(self.canvases)):
            if self.scanout.idle(index) and (self.rendering is None or self.rendering['canvas']!=index):
                return index
        raise RuntimeError('No idle HDMI canvas')

    def service_render(self):
        if self.pending_present is not None and self.scanout.status()[0]==self.pending_present:
            self.display_count+=1;self.pending_present=None
        if self.rendering is None:return
        status=self.mmio.read(0x74)
        if status&4:raise IOError('Canvas AXI renderer error: 0x{:08x}'.format(status))
        if status&2 and not status&1:
            job=self.rendering;self.rendering=None
            now=time.monotonic();self.render_count+=1
            if self.render_first is None:self.render_first=now
            self.render_last=now
            if self.render_live:
                self.present_canvas(job['canvas'],job['config'])
                self.pending_present=job['canvas']

    def queue_render(self,index,frame_id,cfg,view):
        self.service_render()
        end=time.monotonic()+2
        while self.rendering is not None:
            if time.monotonic()>end:raise TimeoutError('Canvas renderer did not complete')
            self.service_render();time.sleep(.0002)
        if index==self.armed:raise RuntimeError('Cannot render an active raw capture')
        slot=self.free_canvas_slot();word,roi,bounds,split=view
        if split and not self.canvas_layout[slot]:
            canvas=self.canvases[slot];canvas.flags.writeable=True
            try:
                canvas[:180].fill(0);canvas[540:].fill(0);canvas.flush()
            finally:canvas.flags.writeable=False
        self.canvas_layout[slot]=split
        self.mmio.write(0x68,int(self.canvases[slot].physical_address))
        self.mmio.write(0xc0,int(self.buffers[index].physical_address))
        self.mmio.write(0x6c,roi);self.mmio.write(0x70,word)
        self.rendering={'raw':index,'canvas':slot,'frame_id':frame_id,'config':cfg,'view':view}
        self.mmio.write(0xc4,1)
        return slot

    def tile_statistics(self):
        first=self.mmio.read(0x8c)
        if not first:return None
        count=self.mmio.read(0x88)
        sums=[]
        for index in range(48):
            self.mmio.write(0x80,index);sums.append(self.mmio.read(0x84))
        if self.mmio.read(0x8c)!=first or not count:return None
        means=np.asarray(sums,dtype=float).reshape(6,8)/count
        return {'frame_id':first,'count_per_tile':count,'means':means,'mean':float(means.mean())}

    def gamma(self, lut):
        if self.mmio.read(0x4c) & 1:
            return False
        if len(lut) != 256:
            raise ValueError('Gamma LUT must contain 256 bytes')
        if load_gamma(self.mmio.array,lut):
            return True
        for i, value in enumerate(lut):
            self.mmio.write(0x44, i | (int(value) << 8))
        self.mmio.write(0x48, 1)
        return True

    def local_gains(self,gains):
        if self.mmio.read(0x9c)&1:return False
        values=np.asarray(gains,dtype=np.uint16).ravel()
        if values.size!=48 or np.any(values<192) or np.any(values>384):raise ValueError('Invalid local gains')
        if not load_parameters(self.mmio.array,values):
            for i,value in enumerate(values):self.mmio.write(0x90,i|(int(value)<<8))
            self.mmio.write(0x94,1)
        return True

    def status_text(self,lines):
        if self.mmio.read(0xac)&1:return False
        text=''.join(str(line).upper()[:64].ljust(64) for line in list(lines)[:6]).ljust(384)
        values=np.array([ord(c) if 32<=ord(c)<128 else 63 for c in text],dtype=np.uint16)
        if not load_parameters(self.mmio.array,values,True):
            for i,value in enumerate(values):self.mmio.write(0xa0,i|(int(value)<<16))
            self.mmio.write(0xa4,1)
        self.mmio.write(0xa8,1)
        return True

    def prepare_display(self):
        if self.pending_output is not None:
            raise RuntimeError('Previous HDMI buffer has not been submitted')
        self.pending_output = self.hout.newframe()
        return self.pending_output

    def display(self, image):
        direct = image is getattr(self,'pending_output',None)
        output = image if direct else self.hout.newframe()
        try:
            if direct:
                pass
            elif image.shape[-1] == 3:
                # Static BGR test images are padded once; live BGRX frames
                # take the contiguous four-byte path below.
                output[:, :, :3] = image
                output[:, :, 3] = 0
            else:
                output[:] = image
            self.hout.writeframe(output)
        except BaseException:
            output.freebuffer()
            raise
        finally:
            if direct:
                self.pending_output = None

    def counters(self):
        return {name: self.mmio.read(offset) for name, offset in
                [('capture_id', 0x1c), ('dma_errors', 0x20), ('camera_vsync', 0x24),
                 ('overflow_frames', 0x28), ('malformed_frames', 0x2c), ('display_sof', 0x34)]}

    def close(self):
        if self.closed:
            return
        self.mmio.write(4, 0)
        end = time.monotonic()+0.2
        while self.mmio.read(0x18) & 1 or (getattr(self,'pl_canvas',False) and self.mmio.read(0x74)&1):
            if time.monotonic() >= end:
                raise RuntimeError('DMA did not quiesce; capture buffers intentionally retained')
            time.sleep(0.001)
        if self.hout is not None:
            if getattr(self,'scanout',None) is not None:self.scanout.stop()
            self.hout.close()
        if getattr(self,'pending_output',None) is not None:
            self.pending_output.freebuffer()
            self.pending_output = None
        for buffer in self.buffers:
            buffer.freebuffer()
        self.buffers = []
        for canvas in getattr(self,'canvases',[]):canvas.freebuffer()
        self.canvases=[]
        self.closed = True
