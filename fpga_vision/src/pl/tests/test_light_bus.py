"""Fault recovery must release the bus even when an external clock stays low."""
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'software'))
from visual_aid.bus import I2CBus


class StuckClockGPIO:
    def __init__(self):
        self.shadow=0x17
        self.lock=threading.RLock()

    def set(self,bit,value):
        self.shadow=(self.shadow | (1<<bit)) if value else (self.shadow & ~(1<<bit))

    def get(self,bit):
        return 0 if bit==2 else (self.shadow>>bit)&1


class LightBusRecovery(unittest.TestCase):
    def test_stop_releases_sda_when_scl_stays_low(self):
        gpio=StuckClockGPIO()
        bus=I2CBus(gpio,2,3,half_period=0,timeout=0)
        with self.assertRaisesRegex(TimeoutError,'SCL held low'):
            bus.stop()
        self.assertEqual(gpio.shadow & 12,12)
        self.assertEqual(gpio.shadow & ~12,0x17 & ~12)

    def test_failed_transfer_does_not_hold_either_sensor_line_low(self):
        gpio=StuckClockGPIO()
        with self.assertRaisesRegex(TimeoutError,'SCL held low'):
            I2CBus(gpio,2,3,half_period=0,timeout=0).transfer(0x23,b'\x01')
        self.assertEqual(gpio.shadow,0x1f)
