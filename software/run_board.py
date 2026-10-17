"""Staged PYNQ 2.4 application: static, keys, sensors, colorbars and live."""
import argparse
import json
import math
from pathlib import Path
import time
import traceback
import cv2
import numpy as np
from visual_aid.device import Device
from visual_aid.bus import GPIO, I2CBus
from visual_aid.camera import OV5640
from visual_aid.sensors import SensorWorker
from visual_aid.controls import State, Controls
from visual_aid.image import compose, AdaptivePolicy
from visual_aid.integrity import verify_payload

BASE = Path(__file__).resolve().parent
MODE_NAMES = ('RAW', 'GRAY', 'INVERSE', 'BINARY', 'COLOR')


def static_pattern():
    image = np.zeros((720, 1280, 4), dtype=np.uint8)
    for i, color in enumerate(((255, 0, 0, 0), (0, 255, 0, 0), (0, 0, 255, 0))):
        image[:, i*1280//3:(i+1)*1280//3] = color
    cv2.putText(image, 'B / G / R - STATIC HDMI TEST', (50, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255, 0), 2)
    return image


def active(start, seconds):
    return seconds == 0 or time.monotonic()-start < seconds


def run(args):
    dev = sensors = None
    state, controls, policy = State(), Controls(), AdaptivePolicy()
    report = {'outcome': 'running', 'stage': args.stage, 'display_observed': None,
              'camera_capture_verified': False, 'unique_camera_frames': 0,
              'hdmi_refresh_is_not_camera_fps': True, 'samples': [], 'events': [], 'warnings': []}
    first = last = None
    frozen = frozen_id = None
    seen_sensors = {'lux': False, 'distance_mm': False}
    try:
        manifest = verify_payload(BASE, args.bit)
        report['release'] = {'built_at': manifest.get('built_at'), 'abi': hex(manifest['abi'])}
        capture = args.stage in ('colorbars', 'live')
        display = args.stage in ('static', 'colorbars', 'live')
        dev = Device(args.bit, display=display, capture=capture)
        gpio = GPIO(dev.mmio)
        if capture:
            camera = OV5640(I2CBus(gpio, 0, 1), gpio)
            report['camera'] = camera.initialize(args.stage == 'colorbars', args.camera_fps)
            if args.af != 'off':
                last_progress = [-1]
                def progress(done, total):
                    pct = 100*done//total
                    if pct//10 != last_progress[0]//10 or done == total:
                        print('AF firmware {}% ({}/{})'.format(pct, done, total), flush=True)
                        last_progress[0] = pct
                try:
                    report['autofocus'] = camera.autofocus(args.af == 'continuous', progress=progress)
                except Exception as exc:
                    report['autofocus'] = {'outcome': 'error', 'error': str(exc), 'optical_focus_observed': False}
                    report['warnings'].append('Autofocus failed; live display continues: '+str(exc))
                    print(report['warnings'][-1], flush=True)
        if args.stage in ('sensors', 'live') and not args.no_sensors:
            sensors = SensorWorker(I2CBus(gpio, 2, 3), not args.no_light, not args.no_distance).start()
        report['counters_before'] = dev.counters()
        start = time.monotonic()
        if args.stage == 'static':
            dev.mmio.write(0x30, 0)
            dev.display(static_pattern())
            print('Static B/G/R pattern running; verify the physical monitor.', flush=True)
            while active(start, args.seconds):
                time.sleep(0.1)
        elif args.stage == 'keys':
            print('Press board BTN0..3 and 5D UP/DWN/LFT/RHT/MID; Ctrl+C ends.', flush=True)
            while active(start, args.seconds):
                now = time.monotonic()
                bits = dev.mmio.read(0x38)
                for key in controls.poll(bits, now):
                    event = {'t': now-start, 'key': key, 'bits': hex(bits)}
                    report['events'].append(event);print(json.dumps(event), flush=True)
                time.sleep(0.005)
        elif args.stage == 'sensors':
            if sensors is None:
                raise ValueError('No sensors enabled')
            while active(start, args.seconds):
                readings = sensors.snapshot()
                for name in seen_sensors:
                    seen_sensors[name] |= readings[name] is not None
                sample = {'t': time.monotonic()-start, 'sensors': readings}
                report['samples'].append(sample);print(json.dumps(sample), flush=True)
                time.sleep(0.5)
            requested = [name for name, enabled in [('lux', not args.no_light), ('distance_mm', not args.no_distance)] if enabled]
            report['sensor_readings_observed'] = seen_sensors
            if not all(seen_sensors[name] for name in requested):
                report['warnings'].append('Some enabled sensors produced no valid measurements')
        else:
            dev.arm(0)
            pending_lut = None
            while active(start, args.seconds):
                begin = time.monotonic()
                index, frame_id, frame = dev.finish(rearm=True)
                now = time.monotonic()
                first = now if first is None else first;last = now
                report['unique_camera_frames'] += 1
                report['camera_capture_verified'] = True
                if args.stage == 'colorbars':
                    dev.mmio.write(0x30, 0)
                    dev.display(frame)
                    bounds = (0, 0, 1280, 720)
                    readings = {'lux': None, 'distance_mm': None}
                    composed = adapted = now
                else:
                    was_frozen, was_automatic = state.frozen, state.automatic
                    for key in controls.poll(dev.mmio.read(0x38), now):
                        state.apply(key);report['events'].append({'t': now-start, 'key': key})
                    if state.frozen and not was_frozen:
                        frozen, frozen_id = frame.copy(), frame_id
                    if not state.frozen:
                        frozen = frozen_id = None
                    source = frozen if state.frozen else frame
                    canvas, roi, bounds = compose(source, state.zoom, state.center, state.split)
                    composed = time.monotonic()
                    readings = sensors.snapshot() if sensors is not None else {'lux': None, 'distance_mm': None}
                    if state.automatic != was_automatic:
                        pending_lut = policy.lut.copy() if state.automatic else np.arange(256, dtype=np.uint8)
                    if state.automatic:
                        candidate = policy.update(roi, now, readings['lux'])
                        if candidate is not None:
                            pending_lut = candidate
                    if pending_lut is not None and dev.gamma(pending_lut):
                        pending_lut = None
                    adapted = time.monotonic()
                    label = '{} {}x {} {} LUX {} DIST {}mm'.format(MODE_NAMES[state.mode], state.zoom,
                            'FREEZE' if state.frozen else 'LIVE', 'AUTO' if state.automatic else 'MANUAL',
                            '-' if readings['lux'] is None else round(readings['lux']),
                            '-' if readings['distance_mm'] is None else readings['distance_mm'])
                    cv2.putText(canvas, label, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0, 0), 1)
                    dev.mmio.write(0x30, state.config())
                    dev.display(canvas)
                ended = time.monotonic()
                if report['unique_camera_frames'] % 15 == 0:
                    sample = {'t': now-start, 'capture_id': frame_id,
                              'render_source_id': frozen_id if state.frozen else frame_id,
                              'roi': bounds, 'zoom': state.zoom, 'config': 0 if args.stage == 'colorbars' else state.config(),
                              'frozen': state.frozen, 'automatic': state.automatic,
                              'sensors': readings, 'counters': dev.counters(),
                              'timing_ms': {'capture_wait': (now-begin)*1000, 'compose': (composed-now)*1000,
                                            'policy': (adapted-composed)*1000, 'display': (ended-adapted)*1000}}
                    report['samples'].append(sample);print(json.dumps(sample), flush=True)
        report['outcome'] = 'completed'
    except KeyboardInterrupt:
        report['outcome'] = 'interrupted'
    except BaseException as exc:
        report['outcome'] = 'error';report['error'] = type(exc).__name__+': '+str(exc)
        traceback.print_exc()
    finally:
        n = report['unique_camera_frames']
        report['measured_unique_capture_fps'] = (n-1)/(last-first) if n > 1 and last > first else None
        cleanup_errors = []
        if dev is not None:
            try:
                report['counters_after'] = dev.counters()
                if 'counters_before' in report:
                    report['counter_deltas'] = {k: (v-report['counters_before'][k]) & 0xffffffff
                                                for k, v in report['counters_after'].items()}
            except Exception as exc:
                cleanup_errors.append('counter read: '+str(exc))
        for object_ in (sensors, dev):
            if object_ is not None:
                try:
                    object_.close()
                except BaseException as exc:
                    cleanup_errors.append(str(exc));break
        report['cleanup_errors'] = cleanup_errors
        if cleanup_errors:
            report['outcome'] = 'cleanup_error'
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print('REPORT '+str(path.resolve()), flush=True)
    return 0 if report['outcome'] in ('completed', 'interrupted') else 1


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stage', choices=('static', 'keys', 'sensors', 'colorbars', 'live'), default='live')
    ap.add_argument('--bit', default=str(BASE/'board/visual_aid_v3.bit'))
    ap.add_argument('--seconds', type=float, default=0, help='0 runs until Ctrl+C')
    ap.add_argument('--camera-fps', type=int, choices=(15, 30), default=15)
    ap.add_argument('--report')
    ap.add_argument('--af', choices=('off', 'single', 'continuous'), default=None)
    ap.add_argument('--no-af', action='store_true')
    ap.add_argument('--colorbars', action='store_true', help='Compatibility alias for --stage colorbars')
    ap.add_argument('--no-sensors', action='store_true')
    ap.add_argument('--no-light', action='store_true')
    ap.add_argument('--no-distance', action='store_true')
    ap.add_argument('--io-confirmed', action='store_true', help='Confirm IO compatibility and wiring before loading hardware')
    args = ap.parse_args(argv)
    if not args.io_confirmed:
        ap.error('Verify physical module IO compatibility and wiring, then pass --io-confirmed')
    if not math.isfinite(args.seconds) or args.seconds < 0:
        ap.error('--seconds must be a finite value >= 0')
    if args.colorbars:
        args.stage = 'colorbars'
    args.af = 'off' if args.no_af or args.stage != 'live' else (args.af or 'continuous')
    if args.no_light and args.no_distance:
        args.no_sensors = True
    if args.report is None:
        args.report = str(BASE/'logs'/('{}_{}.json'.format(args.stage, time.strftime('%Y%m%d_%H%M%S'))))
    return args


if __name__ == '__main__':
    raise SystemExit(run(parse_args()))
