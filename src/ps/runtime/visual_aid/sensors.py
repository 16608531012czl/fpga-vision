"""Optional sensor worker; missing/failed readings are explicit, not zero lux/mm."""
import threading
import time
from .vl53l0x_vendor import VL53L0X


class BH1750:
    def __init__(self, bus, address=0x23):
        self.bus, self.address = bus, address
        bus.transfer(address, b'\x01')
        bus.transfer(address, b'\x10')  # continuous high resolution, wait >=180ms
        self.ready_at = time.monotonic()+0.18

    def read(self):
        if time.monotonic() < self.ready_at:
            return None
        b = self.bus.transfer(self.address, read=2)
        return ((b[0] << 8) | b[1])/1.2


class SensorWorker:
    def __init__(self, bus, enable_light=True, enable_distance=True):
        self.bus = bus
        self.enable_light, self.enable_distance = enable_light, enable_distance
        self.lock = threading.Lock()
        self.values = {'lux': None, 'distance_mm': None, 'errors': {}, 'sample_time': None}
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name='reading-sensors', daemon=True)

    def start(self):
        self.thread.start()
        return self

    def snapshot(self):
        with self.lock:
            result = dict(self.values)
            result['errors'] = dict(result['errors'])
            if result['sample_time'] is None or time.monotonic()-result['sample_time'] > 2:
                result['lux'] = result['distance_mm'] = None
            return result

    def run(self):
        drivers = {}
        factories = []
        if self.enable_light:
            factories.append(('lux', lambda: BH1750(self.bus)))
        if self.enable_distance:
            factories.append(('distance_mm', lambda: VL53L0X(self.bus, io_timeout_s=0.3)))
        for name, factory in factories:
            try:
                drivers[name] = factory()
            except Exception as exc:
                with self.lock:
                    self.values['errors'][name] = type(exc).__name__+': '+str(exc)
        while not self.stop_event.wait(0.25):
            for name, driver in drivers.items():
                try:
                    value = driver.read() if name == 'lux' else driver.range
                    # 8190/8191 are common out-of-range indications, never show
                    # these as useful distance measurements.
                    if name == 'distance_mm' and not 0 < value < 2000:
                        raise ValueError('out of usable ranging interval')
                    with self.lock:
                        self.values[name] = value
                        self.values['errors'].pop(name, None)
                        self.values['sample_time'] = time.monotonic()
                except Exception as exc:
                    with self.lock:
                        self.values[name] = None
                        self.values['errors'][name] = type(exc).__name__+': '+str(exc)

    def close(self):
        self.stop_event.set()
        self.thread.join(5)
        if self.thread.is_alive():
            raise RuntimeError('Sensor worker did not stop; do not reprogram overlay')
