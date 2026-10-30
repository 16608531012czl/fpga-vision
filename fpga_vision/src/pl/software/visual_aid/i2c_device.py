"""Minimal local adapter for the MIT Adafruit VL53L0X driver."""
import time


class I2CDevice:
    def __init__(self, i2c, device_address):
        self.i2c, self.device_address = i2c, device_address

    def __enter__(self):
        while not self.i2c.try_lock():
            time.sleep(0.001)
        return self

    def __exit__(self, *args):
        self.i2c.unlock()

    def write(self, buf, *, start=0, end=None):
        self.i2c.writeto(self.device_address, buf, start=start, end=end)

    def readinto(self, buf, *, start=0, end=None):
        self.i2c.readfrom_into(self.device_address, buf, start=start, end=end)

    def write_then_readinto(self, out_buffer, in_buffer, *, out_start=0, out_end=None, in_start=0, in_end=None):
        self.i2c.writeto_then_readfrom(self.device_address, out_buffer, in_buffer,
                                     out_start=out_start, out_end=out_end, in_start=in_start, in_end=in_end)
