"""Compact, readable status text for the existing six-row PL overlay.

Display smoothing is deliberately separate from sensor values and image control.
Only characters present in the hardware 5x7 font are used.
"""
import math

MODES = ('RAW', 'GRAY', 'INVERSE', 'BINARY', 'COLOR')
ALGORITHMS = ('OFF', 'USM', 'LAPLACIAN', 'GUIDED')
LABELS = {
    'brightness': 'BRIGHTNESS', 'sharpness': 'SHARPNESS',
    'denoise': 'DENOISE', 'contrast': 'CONTRAST',
    'algorithm': 'ALGORITHM', 'noise': 'NOISE',
    'edge_view': 'EDGE VIEW', 'color': 'COLOR',
    'local_tone': 'LOCAL TONE', 'window31': 'WINDOW',
    'binary_c': 'BINARY C',
}


class StatusPanel:
    def __init__(self):
        self.fps = None
        self.lux = None
        self.last_time = None

    @staticmethod
    def _smooth(previous, value, dt, tau):
        if value is None:
            return None
        value = float(value)
        if not math.isfinite(value) or value < 0:
            return None
        if previous is None:
            return value
        alpha = 1.0 - math.exp(-max(0.0, dt) / tau)
        return previous + alpha * (value - previous)

    def sample(self, now, fps, lux):
        dt = 0.0 if self.last_time is None else min(2.0, max(0.0, now - self.last_time))
        self.last_time = now
        self.fps = self._smooth(self.fps, fps, dt, 0.8)
        self.lux = self._smooth(self.lux, lux, dt, 0.45)

    @staticmethod
    def signature(state):
        return (state.mode, state.zoom, state.frozen, state.automatic, state.selected) + tuple(
            getattr(state, name) for name in state.parameters)

    def lines(self, state, af_label):
        selected = state.parameters[state.selected]
        value = getattr(state, selected)
        if selected == 'algorithm':
            shown = ALGORITHMS[value]
        elif selected in ('edge_view', 'local_tone'):
            shown = 'ON' if value else 'OFF'
        elif selected == 'window31':
            shown = '31' if value else '15'
        elif selected == 'brightness':
            shown = '{:+d}'.format(value)
        else:
            shown = str(value)
        fps = '--.-' if self.fps is None else '{:4.1f}'.format(min(self.fps, 999.9))
        lux = '--' if self.lux is None else str(min(99999, int(round(self.lux))))
        af = {'CONTINUOUS': 'ON', 'SINGLE': 'ONE', 'OFF': 'OFF', 'ERROR': 'ERR'}.get(af_label, '--')
        return [
            '{}  {}X  {}  {}'.format(MODES[state.mode], state.zoom,
                                      'FREEZE' if state.frozen else 'LIVE',
                                      'AUTO' if state.automatic else 'MANUAL'),
            'FPS {}  LUX {}  AF {}'.format(fps, lux, af),
            'B {:+d}  SH {}  DN {}  CT {}'.format(
                state.brightness, state.sharpness, state.denoise, state.contrast),
            'NR {}  ALG {}  EDGE {}'.format(state.noise, ALGORITHMS[state.algorithm],
                                             'ON' if state.edge_view else 'OFF'),
            'EDIT {} {}'.format(LABELS[selected], shown),
            'COLOR {}  LOCAL {}  WIN {}  C {}'.format(
                state.color, 'ON' if state.local_tone else 'OFF',
                31 if state.window31 else 15, state.binary_c),
        ]
