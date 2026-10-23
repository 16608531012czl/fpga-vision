"""Staged PYNQ 2.4 application: static, keys, sensors, colorbars and live."""
import argparse
import json
import math
from pathlib import Path
import time
import traceback
from collections import deque
import cv2
import numpy as np
from visual_aid.device import Device
from visual_aid.bus import GPIO, I2CBus
from visual_aid.camera import OV5640
from visual_aid.sensors import SensorWorker
from visual_aid.controls import State, Controls
from visual_aid.encoder import Encoder, record_event
from visual_aid.image import compose, AdaptivePolicy
from visual_aid.integrity import verify_payload
from visual_aid.fastcompose import available as native_compose_available
from visual_aid.chroma import ChromaDenoiser,enhanced_pane
from visual_aid.pl_runtime import run_pl

BASE = Path(__file__).resolve().parent
MODE_NAMES = ('RAW', 'GRAY', 'INVERSE', 'BINARY', 'COLOR')
SHARP_NAMES = ('OFF', 'USM', 'LAPLACIAN', 'GUIDED')


def brightness_lut(base, brightness):
    if brightness == 0:
        return np.asarray(base, dtype=np.uint8).copy()
    exponent = 2.0**(-brightness/12.0)
    return np.rint(255*(np.asarray(base,dtype=float)/255.0)**exponent).astype(np.uint8)


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
    state, controls, policy = State(args.quality_preset), Controls(), AdaptivePolicy(args.tone_profile)
    chroma=ChromaDenoiser()
    state.mode = MODE_NAMES.index(args.mode.upper())
    state.algorithm = SHARP_NAMES.index(args.sharp_mode.upper())
    state.edge_view = args.edge_view
    encoder = Encoder(args.encoder_reverse)
    report = {'outcome': 'running', 'stage': args.stage, 'display_observed': None,
              'camera_capture_verified': False, 'unique_camera_frames': 0,
              'hdmi_refresh_is_not_camera_fps': True, 'tone_profile': args.tone_profile,
              'samples': [], 'events': [], 'warnings': [], 'encoder_connected_verified': False}
    report['quality_preset']=args.quality_preset
    report['chroma_denoise']={'enabled':args.quality_preset=='balanced','scope':'enhanced COLOR pane before PL; original pane bypassed',
                            'native':native_compose_available(),'motion_gated':True}
    report['native_neon_composition_available']=native_compose_available()
    if Path('/proc/sys/kernel/random/boot_id').is_file():
        report['boot_id']=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        report['uptime_start']=Path('/proc/uptime').read_text().strip()
    first = last = None
    frozen = frozen_id = None
    seen_sensors = {'lux': False, 'distance_mm': False}
    try:
        manifest = verify_payload(BASE, args.bit)
        report['release'] = {'built_at': manifest.get('built_at'), 'abi': hex(manifest['abi'])}
        capture = args.stage in ('colorbars', 'live')
        display = args.stage in ('static', 'colorbars', 'live')
        pl_live=args.pipeline=='pl' and args.stage=='live'
        dev = Device(args.bit, display=display, capture=capture,pl_canvas=pl_live)
        report['pipeline']=args.pipeline if args.stage=='live' else 'cpu'
        if pl_live:report['chroma_denoise']={'enabled':bool(state.quality_config()&256),'scope':'PL gated spatial 3x3 on enhanced COLOR pane; DN=0 bypasses','motion_gated':False}
        else:dev.mmio.write(0x78,0)
        gpio = GPIO(dev.mmio)
        if capture:
            # Hold capture in reset throughout PLL/timing changes and AF upload.
            dev.mmio.write(4,0)
            camera = OV5640(I2CBus(gpio, 0, 1), gpio)
            report['camera'] = camera.initialize(args.stage == 'colorbars', args.camera_fps)
            if args.stage=='live':
                report['camera_quality']=camera.image_quality('baseline' if args.quality_preset=='detail' else args.quality_preset)
                if args.tone_profile=='stable':report['exposure_stability']=camera.stable_exposure()
            if args.af != 'off':
                last_progress = [-1]
                def progress(done, total):
                    pct = 100*done//total
                    if pct//10 != last_progress[0]//10 or done == total:
                        print('AF firmware {}% ({}/{})'.format(pct, done, total), flush=True)
                        last_progress[0] = pct
                try:
                    report['autofocus'] = camera.autofocus(args.af == 'continuous', progress=progress)
                    print('AF_READY '+json.dumps(report['autofocus']),flush=True)
                except Exception as exc:
                    report['autofocus'] = {'outcome': 'error', 'error': str(exc), 'optical_focus_observed': False}
                    report['warnings'].append('Autofocus failed; live display continues: '+str(exc))
                    print(report['warnings'][-1], flush=True)
            dev.mmio.write(4,1)
            time.sleep(0.2)
        if args.stage in ('sensors', 'live') and not args.no_sensors:
            sensors = SensorWorker(I2CBus(gpio, 2, 3), not args.no_light, not args.no_distance).start()
        report['counters_before'] = dev.counters()
        af_label=('OFF' if args.af=='off' else args.af.upper()
                  if report.get('autofocus',{}).get('command_acknowledged') else 'ERROR')
        start = time.monotonic()
        encoder.poll(dev.mmio)
        if args.stage == 'static':
            dev.mmio.write(0x30, 0)
            dev.display(static_pattern())
            print('Static B/G/R pattern running; verify the physical monitor.', flush=True)
            while active(start, args.seconds):
                time.sleep(0.1)
        elif args.stage == 'encoder':
            print('Rotate EC11 both ways; short press selects, hold 1s resets. No camera/HDMI.',flush=True)
            previous = None
            while active(start,args.seconds):
                now = time.monotonic()
                events, raw = encoder.poll(dev.mmio)
                for event,value in events:
                    state.encoder(event,value)
                    record_event(report, event, value)
                    item={'t':now-start,'encoder_event':event,'value':value,'parameters':state.snapshot()}
                    report['events'].append(item);print(json.dumps(item),flush=True)
                if raw != previous:
                    report['samples'].append({'t':now-start,'encoder':raw})
                    previous=raw.copy()
                time.sleep(0.005)
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
        elif pl_live:
            first,last=run_pl(dev,state,controls,encoder,policy,sensors,args,report,start,af_label,brightness_lut)
        else:
            dev.arm(0)
            pending_lut = None
            tone_key = None
            frame_times = deque()
            rolling_fps = 0.0
            encoder_raw = None
            while active(start, args.seconds):
                begin = time.monotonic()
                index, frame_id, frame = dev.finish(rearm=True)
                now = time.monotonic()
                first = now if first is None else first;last = now
                report['unique_camera_frames'] += 1
                report['camera_capture_verified'] = True
                frame_times.append(now)
                while len(frame_times)>2 and now-frame_times[0]>1.0:
                    frame_times.popleft()
                rolling_fps=(len(frame_times)-1)/(now-frame_times[0]) if len(frame_times)>1 and now>frame_times[0] else 0.0
                chroma_ms=0.0
                if args.stage == 'colorbars':
                    dev.mmio.write(0x30, 0)
                    dev.display(frame)
                    bounds = (0, 0, 1280, 720)
                    readings = {'lux': None, 'distance_mm': None}
                    composed = adapted = now
                else:
                    was_frozen, was_automatic = state.frozen, state.automatic
                    events, encoder_raw = encoder.poll(dev.mmio)
                    for event,value in events:
                        state.encoder(event,value)
                        record_event(report, event, value)
                        report['events'].append({'t':now-start,'encoder_event':event,'value':value,
                                                 'parameters':state.snapshot()})
                    for key in controls.poll(dev.mmio.read(0x38), now):
                        state.apply(key);report['events'].append({'t': now-start, 'key': key})
                    if state.frozen and not was_frozen:
                        frozen, frozen_id = frame.copy(), frame_id
                    if not state.frozen:
                        frozen = frozen_id = None
                    source = frozen if state.frozen else frame
                    canvas, roi, bounds = compose(source, state.zoom, state.center, state.split,
                                                 out=dev.prepare_display())
                    before_chroma=time.monotonic()
                    if args.quality_preset=='balanced' and state.mode==4 and not state.edge_view:
                        chroma.apply(enhanced_pane(canvas,bounds,state.split),state.denoise,
                                     (bounds,state.split,state.denoise,state.frozen,frozen_id),now)
                    else:
                        chroma.reset()
                    chroma_ms=(time.monotonic()-before_chroma)*1000
                    composed = time.monotonic()
                    readings = sensors.snapshot() if sensors is not None else {'lux': None, 'distance_mm': None}
                    for name in seen_sensors:
                        seen_sensors[name] |= readings[name] is not None
                    policy.update(roi, now, readings['lux'])
                    base_lut=policy.lut if state.automatic else np.arange(256,dtype=np.uint8)
                    next_tone_key=(state.automatic,state.brightness,base_lut.tobytes())
                    if tone_key!=next_tone_key:
                        pending_lut=brightness_lut(base_lut,state.brightness)
                        tone_key=next_tone_key
                    if pending_lut is not None and dev.gamma(pending_lut):
                        pending_lut = None
                    adapted = time.monotonic()
                    label = '{} {}x {} {} LUX {} DIST {}mm'.format(MODE_NAMES[state.mode], state.zoom,
                            'FREEZE' if state.frozen else 'LIVE', 'AUTO' if state.automatic else 'MANUAL',
                            ('ERR' if 'lux' in readings.get('errors', {}) else '-') if readings['lux'] is None else round(readings['lux']),
                            '-' if readings['distance_mm'] is None else readings['distance_mm'])
                    cv2.putText(canvas, label, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0, 0), 1)
                    tone = policy.status()
                    if not state.automatic:
                        tone_label = 'MANUAL B {:+d} | SOURCE Y {}'.format(state.brightness,
                                      '-' if tone['mean'] is None else round(tone['mean']))
                    elif state.mode in (0, 3):
                        tone_label = 'TONE BYPASS - SELECT COLOR OR GRAY'
                    elif tone['mean'] is None:
                        tone_label = 'TONE WAIT'
                    else:
                        tone_label = '{} G {:.2f} BASE LUT Y {:.0f}>{:.0f} (EST)'.format(
                            args.tone_profile.upper(), tone['target_gamma'],
                            tone['mean'], tone['lut_mean_estimate'])
                    cv2.putText(canvas, tone_label, (12, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0, 0), 1)
                    settings='{} SH {} DN {} CT {} NR {} B {:+d}  EDIT {}'.format(
                        'SOBEL' if state.edge_view else SHARP_NAMES[state.algorithm],state.sharpness,
                        state.denoise,state.contrast,state.noise,state.brightness,state.parameters[state.selected].upper())
                    cv2.putText(canvas,settings,(12,78),cv2.FONT_HERSHEY_SIMPLEX,0.55,(0,255,255,0),1)
                    cv2.putText(canvas,'CAM {:.1f} FPS | AF {} | {} | EC11 TURN / CLICK / HOLD'.format(rolling_fps,af_label,args.quality_preset.upper()),
                                (12,102),cv2.FONT_HERSHEY_SIMPLEX,0.55,(0,255,255,0),1)
                    dev.mmio.write(0x30, state.config())
                    dev.display(canvas)
                ended = time.monotonic()
                if report['unique_camera_frames'] % 15 == 0:
                    sample = {'t': now-start, 'capture_id': frame_id,
                              'render_source_id': frozen_id if state.frozen else frame_id,
                              'roi': bounds, 'zoom': state.zoom, 'config': 0 if args.stage == 'colorbars' else state.config(),
                              'frozen': state.frozen, 'automatic': state.automatic,
                              'sensors': readings, 'counters': dev.counters(),
                              'tone': policy.status() if args.stage == 'live' else None,
                              'tone_lut_pending': pending_lut is not None,
                              'parameters':state.snapshot(), 'encoder':encoder_raw,
                              'chroma_denoise_ms':chroma_ms,
                              'rolling_unique_capture_fps':rolling_fps,
                              'timing_ms': {'capture_wait': (now-begin)*1000, 'compose': (composed-now)*1000,
                                            'policy': (adapted-composed)*1000, 'display': (ended-adapted)*1000}}
                    report['samples'].append(sample);print(json.dumps(sample), flush=True)
                    if args.seconds == 0 and len(report['samples']) > 600:
                        del report['samples'][:300]
                        report['samples_discarded']=report.get('samples_discarded',0)+300
        if args.stage == 'live' and sensors is not None:
            report['sensor_readings_observed'] = seen_sensors
            if not args.no_light and not seen_sensors['lux']:
                report['warnings'].append('No valid light-sensor reading; tone policy used image statistics only')
        report['outcome'] = 'completed'
        if args.stage=='live' and args.af!='off' and report.get('autofocus',{}).get('firmware_ready'):
            report['autofocus_after']=camera.autofocus_status()
    except KeyboardInterrupt:
        report['outcome'] = 'interrupted'
    except BaseException as exc:
        report['outcome'] = 'error';report['error'] = type(exc).__name__+': '+str(exc)
        traceback.print_exc()
    finally:
        first=report.pop('_capture_first',first);last=report.pop('_capture_last',last)
        n = report['unique_camera_frames']
        report['measured_unique_capture_fps'] = (n-1)/(last-first) if n > 1 and last > first else None
        cleanup_errors = []
        if dev is not None:
            try:
                report['counters_after'] = dev.counters()
                if manifest.get('capture_diagnostic_register'):
                    word=dev.mmio.read(int(manifest['capture_diagnostic_register'],0))
                    report['capture_geometry']={'raw':hex(word),'valid':bool(word&(1<<26)),
                         'reason':(word>>23)&7,'line':(word>>12)&2047,'pixels':word&4095}
                if 'counters_before' in report:
                    report['counter_deltas'] = {k: (v-report['counters_before'][k]) & 0xffffffff
                                                for k, v in report['counters_after'].items()}
            except Exception as exc:
                cleanup_errors.append('counter read: '+str(exc))
        if Path('/proc/sys/kernel/random/boot_id').is_file():
            report['boot_id_after']=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
            report['uptime_end']=Path('/proc/uptime').read_text().strip()
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
    ap.add_argument('--stage', choices=('static', 'keys', 'encoder', 'sensors', 'colorbars', 'live'), default='live')
    ap.add_argument('--bit', default=str(BASE/'board/visual_aid_v3.bit'))
    ap.add_argument('--seconds', type=float, default=0, help='0 runs until Ctrl+C')
    ap.add_argument('--camera-fps', type=int, choices=tuple(sorted(OV5640.FPS_PROFILES)), default=20)
    ap.add_argument('--mode', choices=('raw', 'gray', 'inverse', 'binary', 'color'), default='gray')
    ap.add_argument('--sharp-mode',choices=('off','usm','laplacian','guided'),default='guided')
    ap.add_argument('--quality-preset',choices=('baseline','balanced','detail'),default='detail',
                    help='balanced reduces color noise and repeated sharpening; baseline restores previous processing')
    ap.add_argument('--pipeline',choices=('pl','cpu'),default='pl',help='PL scales/composes live frames; CPU retains the previous pipeline')
    ap.add_argument('--edge-view',action='store_true',help='Diagnostic Sobel view')
    ap.add_argument('--encoder-reverse',action='store_true',help='Reverse software interpretation of rotation')
    ap.add_argument('--tone-profile', choices=('lowlight', 'legacy','stable'), default='stable',
                    help='lowlight lifts shadows; legacy reproduces the previous adaptive policy')
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
