"""Owned DMA scanout slots: no CPU frame copy and no implicit buffer free."""
import time


class ParkedScanout:
    def __init__(self,mmio,buffers,width=1280,height=720,timeout=2):
        if len(buffers)!=4:raise ValueError('Exactly four owned scanout buffers required')
        if not mmio.read(4)&1:raise RuntimeError('Stop MM2S before replacing frame addresses')
        self.mmio,self.buffers,self.timeout=mmio,buffers,timeout
        self.pinned_raw=None
        for index,buffer in enumerate(buffers):
            address=int(buffer.physical_address)
            if address&63:raise ValueError('Canvas address must be cache-line aligned')
            mmio.write(0x5c+index*4,address)
        mmio.write(0x54,width*4);mmio.write(0x58,width*4)
        mmio.write(0x28,3)
        # Same internally synchronized parked mode as PYNQ 2.4, IRQ disabled.
        mmio.write(0,0x00010089);mmio.write(0x50,height)
        self.wait(3)

    def status(self):
        status=self.mmio.read(4)
        if status&0x70:raise IOError('Direct MM2S DMA error: 0x{:08x}'.format(status))
        word=self.mmio.read(0x28)
        return (word>>16)&31,word&31

    def wait(self,index):
        end=time.monotonic()+self.timeout
        while self.status()[0]!=index:
            if time.monotonic()>end:raise TimeoutError('MM2S did not park on requested canvas')
            time.sleep(.0002)

    def idle(self,index):
        current,desired=self.status()
        return index not in (current,desired)

    def free_capture_slot(self,exclude=()):
        blocked=set(exclude)
        if self.pinned_raw is not None:blocked.add(self.pinned_raw)
        current,desired=self.status();blocked.update((current,desired))
        for index in range(3):
            if index not in blocked:return index
        if current!=desired:
            self.wait(desired)
            return self.free_capture_slot(exclude)
        raise RuntimeError('No capture slot is free; retain DMA ownership')

    def present(self,index):
        if index not in range(4):raise ValueError('Invalid owned canvas slot')
        self.status()
        word=self.mmio.read(0x28)
        self.mmio.write(0x28,(word&~31)|index)

    def stop(self):
        self.mmio.write(0,0x00010088)
        end=time.monotonic()+self.timeout
        while not self.mmio.read(4)&1:
            if time.monotonic()>end:raise RuntimeError('MM2S did not halt; retain canvas buffers')
            time.sleep(.0002)
