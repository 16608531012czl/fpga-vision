"""PYNQ 2.4 backend with cached, read-only BGRX capture buffers."""
from pathlib import Path
import asyncio
import time
import numpy as np


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
    def __init__(self, bitfile, display=True, capture=True):
        from pynq import Overlay, Xlnk, DefaultIP
        from pynq.lib.video import VideoMode, PixelFormat, PIXEL_BGR
        from pynq.lib.video.dma import AxiVDMA
        p = Path(bitfile).resolve()
        if not p.is_file() or not p.with_suffix('.hwh').is_file():
            raise FileNotFoundError('Matching new-project .bit/.hwh are required: '+str(p))
        self.ol = Overlay(str(p))
        # PYNQ 2.4 exposes a module-reference slave under its bus name;
        # assist_core itself is a hierarchy because it also has master ports.
        self.mmio = DefaultIP(self.ol.ip_dict['assist_core/s_axi']).mmio
        if self.mmio.read(0) != 0x56410300:
            raise RuntimeError('Wrong overlay ABI; do not use the old project bitstream')
        self.buffers = []
        self.hout = None
        self.armed = None
        self.closed = False
        try:
            self.mmio.write(4, 0)
            self.mmio.write(0x30, 0)
            self.xlnk = Xlnk()
            for _ in range(2 if capture else 0):
                buffer = self.xlnk.cma_array(shape=(720, 1280), dtype=np.uint32, cacheable=1)
                self.buffers.append(buffer)
                # Clean allocation-time CPU writes once, before PL ownership.
                # CPU views stay read-only, so no dirty lines need flushing
                # on every rearm. Invalidate after each completed PL write.
                buffer.flush()
                buffer.flags.writeable = False
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
            self.mmio.write(4, int(capture))
        except BaseException:
            self.close()
            raise

    def arm(self, index):
        if self.armed is not None or self.mmio.read(0x18) & 1:
            raise RuntimeError('Capture buffer is still owned by DMA')
        self.expected_id = (self.mmio.read(0x1c)+1) & 0xffffffff
        self.mmio.write(0x10, int(self.buffers[index].physical_address))
        self.mmio.write(0x14, 1)
        self.armed = index

    def finish(self, timeout=2, rearm=False):
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
                    self.arm(1-index)
                # The PL has completed the final AXI B response. Discard stale
                # CPU cache lines before reading the newly captured frame.
                self.buffers[index].invalidate()
                bgrx = np.asarray(self.buffers[index]).view(np.uint8).reshape(720, 1280, 4)
                bgrx.flags.writeable = False
                return index, frame_id, bgrx
            time.sleep(0.0002)
        self.mmio.write(4, 0)  # stop input; writer drains its outstanding AXI burst
        raise TimeoutError('No valid full DVP frame; check PCLK, sync polarity, byte order and counters')

    def gamma(self, lut):
        if self.mmio.read(0x4c) & 1:
            return False
        if len(lut) != 256:
            raise ValueError('Gamma LUT must contain 256 bytes')
        for i, value in enumerate(lut):
            self.mmio.write(0x44, i | (int(value) << 8))
        self.mmio.write(0x48, 1)
        return True

    def display(self, image):
        output = self.hout.newframe()
        try:
            if image.shape[-1] == 3:
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

    def counters(self):
        return {name: self.mmio.read(offset) for name, offset in
                [('capture_id', 0x1c), ('dma_errors', 0x20), ('camera_vsync', 0x24),
                 ('overflow_frames', 0x28), ('malformed_frames', 0x2c), ('display_sof', 0x34)]}

    def close(self):
        if self.closed:
            return
        self.mmio.write(4, 0)
        end = time.monotonic()+0.2
        while self.mmio.read(0x18) & 1:
            if time.monotonic() >= end:
                raise RuntimeError('DMA did not quiesce; capture buffers intentionally retained')
            time.sleep(0.001)
        if self.hout is not None:
            self.hout.close()
        for buffer in self.buffers:
            buffer.freebuffer()
        self.buffers = []
        self.closed = True
