"""OV5640 register profile + supplied AF firmware, with explicit readback gates."""
from pathlib import Path
import hashlib
import json
import time

ASSETS = Path(__file__).resolve().parents[1]/'assets'


class OV5640:
    ADDRESS = 0x3c

    def __init__(self, bus, gpio):
        self.bus, self.gpio = bus, gpio

    def write(self, reg, value):
        self.bus.transfer(self.ADDRESS, bytes((reg >> 8, reg & 255, value)))

    def read(self, reg):
        return self.bus.transfer(self.ADDRESS, bytes((reg >> 8, reg & 255)), 1)[0]

    def wait(self, register, expected, timeout):
        end = time.monotonic()+timeout
        while time.monotonic() < end:
            value = self.read(register)
            if value == expected:
                return value
            time.sleep(0.01)
        raise TimeoutError('OV5640 reg 0x{:04x}: got 0x{:02x}, expected 0x{:02x}'.format(register, value, expected))

    def initialize(self, colorbars=False, fps=30):
        if fps not in (15, 30):
            raise ValueError('camera fps profile must be 15 or 30')
        self.gpio.set(5, 1); self.gpio.set(4, 0); time.sleep(0.01)
        self.gpio.set(5, 0); time.sleep(0.01); self.gpio.set(4, 1); time.sleep(0.02)
        chip = (self.read(0x300a) << 8) | self.read(0x300b)
        if chip != 0x5640:
            raise IOError('Expected OV5640 ID, got 0x{:04x}'.format(chip))
        profile = json.loads((ASSETS/'ov5640_720p.json').read_text())
        for reg, value in profile['default']+profile['profile']:
            if reg == 65535:
                time.sleep(value/1000.0)
            else:
                self.write(reg, value)
        # Supplied guide: 15fps uses 0x41/42MHz PCLK; 30fps 0x21/84MHz.
        # These are requested register profiles, not measured frame rates.
        self.write(0x3035, 0x41 if fps == 15 else 0x21)
        # Match this raw capture core's VSYNC/HREF interpretation while keeping
        # falling-edge data launch. On the supplied module, 0x21 drops every
        # frame; the board test accepted a full 1280x720 frame with 0x20.
        self.write(0x4740, 0x20)
        self.write(0x503d, 0x80 if colorbars else 0)
        size = ((self.read(0x3808) << 8) | self.read(0x3809), (self.read(0x380a) << 8) | self.read(0x380b))
        if size != (1280, 720) or self.read(0x501f) & 3 != 1:
            raise IOError('RGB565/720p register readback failed: {}'.format(size))
        return {'id': chip, 'size': size, 'profile': profile['name'], 'colorbars': colorbars,
                'requested_fps': fps, 'dvp_polarity': self.read(0x4740),
                'profile_hardware_validated': False}

    def image_quality(self, preset='detail'):
        if preset not in ('baseline', 'detail'):
            raise ValueError('quality preset must be baseline or detail')
        registers = (0x5000, 0x5308, 0x5302)
        before = {reg: self.read(reg) for reg in registers}
        expected = dict(before)
        if preset == 'detail':
            # A small ISP edge-strength increase, after optical focusing.
            # Preserve denoise, gamma, AWB, exposure and timing settings.
            expected[0x5000] |= 1
            expected[0x5308] |= 0x40
            expected[0x5302] = 0x20
            for reg in registers:
                if before[reg] != expected[reg]:
                    self.write(reg, expected[reg])
        actual = {reg: self.read(reg) for reg in registers}
        if actual != expected:
            raise IOError('OV5640 quality register readback mismatch')
        return {'preset': preset, 'registers_before': before,
                'registers_after': actual, 'resolution': [1280, 720]}

    def autofocus_status(self):
        status = self.read(0x3029)
        ack = self.read(0x3023)
        return {'status': status, 'command_ack': ack,
                'clock_3004': self.read(0x3004), 'clock_3005': self.read(0x3005),
                'firmware_focus_reported': status == 0x10,
                'optical_focus_observed': False}

    def _af_command(self, command, timeout=12):
        self.write(0x3004, self.read(0x3004) | 0x60)
        self.write(0x3005, self.read(0x3005) | 0x40)
        self.write(0x3023, 1)
        self.write(0x3022, command)
        self.wait(0x3023, 0, timeout)

    def autofocus(self, continuous=True, progress=None, block_size=32):
        if not isinstance(block_size, int) or not 1 <= block_size <= 128:
            raise ValueError('AF upload block_size must be 1..128')
        firmware = (ASSETS/'ov5640_af.bin').read_bytes()
        if not 0 < len(firmware) <= 0x1000:
            raise ValueError('AF firmware does not fit the 0x8000..0x8fff window')
        started = time.monotonic()
        self.write(0x3000, 0x20)
        # MCU/SCCB and AFC clocks must remain enabled for SRAM access.
        self.write(0x3004, self.read(0x3004) | 0x60)
        self.write(0x3005, self.read(0x3005) | 0x40)
        self.write(0x3001, self.read(0x3001) & ~0x40)
        if progress:
            progress(0, len(firmware))
        for i in range(0, len(firmware), block_size):
            address = 0x8000+i
            block = firmware[i:i+block_size]
            # The module guide recommends SCCB multi-byte firmware writes.
            self.bus.transfer(self.ADDRESS, bytes((address >> 8, address & 255))+block)
            if progress:
                progress(i+len(block), len(firmware))
        # Verify ALL code bytes before executing them, with MCU held in reset
        # and its SRAM clocks enabled; live-MCU reads are not this check.
        readback = bytearray()
        for i in range(0, len(firmware), block_size):
            address = 0x8000+i
            expected = firmware[i:i+block_size]
            actual = self.bus.transfer(self.ADDRESS, bytes((address >> 8, address & 255)), len(expected))
            if len(actual) != len(expected):
                raise IOError('AF SRAM short read at 0x{:04x}'.format(address))
            if actual != expected:
                mismatch = next(j for j, (a, b) in enumerate(zip(actual, expected)) if a != b)
                raise IOError('AF SRAM readback mismatch at 0x{:04x}: got 0x{:02x}, expected 0x{:02x}'.format(address+mismatch, actual[mismatch], expected[mismatch]))
            readback.extend(actual)
        for reg in range(0x3022, 0x3029):
            self.write(reg, 0)
        self.write(0x3029, 0x7f); self.write(0x3000, 0)
        self.wait(0x3029, 0x70, 5)
        # Supplied module driver releases the motor before continuous AF.
        self._af_command(8, 5)
        self._af_command(4 if continuous else 3)
        # ACK only confirms command handling, not optical focus success.
        if not continuous:
            self.wait(0x3029, 0x10, 12)
        result = self.autofocus_status()
        result.update(firmware_sha256=hashlib.sha256(firmware).hexdigest(),
                      firmware_bytes=len(firmware), verified_readback_bytes=len(readback),
                      full_readback_sha256=hashlib.sha256(readback).hexdigest(),
                      full_readback_verified=True,
                      upload_block_size=block_size, startup_seconds=time.monotonic()-started,
                      firmware_ready=True, command_acknowledged=True, continuous=continuous)
        return result
