"""Open-drain SCCB/I2C over assist_regs; explicit ACK/stretch/timeout errors."""
import threading
import time


class GPIO:
    def __init__(self, mmio):
        self.mmio = mmio
        self.shadow = mmio.read(0x3c) & 63
        self.lock = threading.RLock()

    def set(self, bit, value):
        with self.lock:
            self.shadow = (self.shadow | (1 << bit)) if value else (self.shadow & ~(1 << bit))
            self.mmio.write(0x3c, self.shadow)

    def get(self, bit):
        return (self.mmio.read(0x40) >> bit) & 1


class I2CBus:
    def __init__(self, gpio, scl=0, sda=1, half_period=0.000005, timeout=0.05):
        self.gpio, self.scl, self.sda = gpio, scl, sda
        self.period, self.timeout = half_period, timeout

    def delay(self):
        time.sleep(self.period)

    def clock_high(self):
        self.gpio.set(self.scl, 1)
        end = time.monotonic()+self.timeout
        while not self.gpio.get(self.scl):
            if time.monotonic() >= end:
                raise TimeoutError('SCL held low: check wiring/pullups/power')
        self.delay()

    def start(self):
        self.gpio.set(self.sda, 1); self.clock_high()
        if not self.gpio.get(self.sda):
            raise IOError('SDA stuck low')
        self.gpio.set(self.sda, 0); self.delay(); self.gpio.set(self.scl, 0)

    def stop(self):
        self.gpio.set(self.scl, 0); self.gpio.set(self.sda, 0); self.delay()
        self.clock_high(); self.gpio.set(self.sda, 1); self.delay()

    def bit(self, value):
        self.gpio.set(self.sda, value); self.delay(); self.clock_high()
        sampled = self.gpio.get(self.sda)
        self.gpio.set(self.scl, 0); self.delay()
        return sampled

    def write_byte(self, value):
        for i in range(7, -1, -1):
            self.bit((value >> i) & 1)
        if self.bit(1):
            raise IOError('I2C NACK writing 0x{:02x}'.format(value))

    def read_byte(self, last=False):
        value = 0
        for _ in range(8):
            value = (value << 1) | self.bit(1)
        self.bit(1 if last else 0)
        self.gpio.set(self.sda, 1)
        return value

    def transfer(self, address, write=b'', read=0):
        with self.gpio.lock:
            try:
                self.start()
                if write or not read:
                    self.write_byte(address << 1)
                    for value in write:
                        self.write_byte(value)
                    if read:
                        self.start()
                if read:
                    self.write_byte((address << 1) | 1)
                return bytes(self.read_byte(i == read-1) for i in range(read))
            finally:
                self.stop()

    # CircuitPython-compatible surface for the vendored VL53L0X driver.
    def try_lock(self):
        return self.gpio.lock.acquire(False)

    def unlock(self):
        self.gpio.lock.release()

    def writeto(self, address, buffer, *, start=0, end=None, stop=True):
        if not stop:
            raise ValueError('Use writeto_then_readfrom for repeated START')
        self.transfer(address, bytes(buffer[start:end]))

    def readfrom_into(self, address, buffer, *, start=0, end=None):
        if end is None:
            end = len(buffer)
        buffer[start:end] = self.transfer(address, read=end-start)

    def writeto_then_readfrom(self, address, out_buffer, in_buffer, *, out_start=0, out_end=None, in_start=0, in_end=None):
        if in_end is None:
            in_end = len(in_buffer)
        in_buffer[in_start:in_end] = self.transfer(address, bytes(out_buffer[out_start:out_end]), in_end-in_start)
