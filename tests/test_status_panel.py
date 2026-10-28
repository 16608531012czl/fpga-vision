from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'software'))
from visual_aid.controls import State
from visual_aid.image import AdaptivePolicy
from visual_aid.pl_runtime import run_pl
from visual_aid.status_panel import StatusPanel


class StatusPanelTests(unittest.TestCase):
    def test_all_parameters_show_value_with_supported_font_and_compact_rows(self):
        state = State('detail')
        panel = StatusPanel()
        panel.sample(0., 19.9, 98.)
        supported = set(' ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+-. :/>=?')
        for i, name in enumerate(state.parameters):
            state.selected = i
            lines = panel.lines(state, 'CONTINUOUS')
            self.assertEqual(len(lines), 6)
            self.assertTrue(all(len(line) <= 32 for line in lines), (name, lines))
            self.assertTrue(all(set(line) <= supported for line in lines), (name, lines))
            self.assertTrue(lines[4].startswith('EDIT '))
            self.assertNotIn('_', lines[4])
        state.selected = state.parameters.index('algorithm')
        self.assertIn('GUIDED', panel.lines(state, 'CONTINUOUS')[4])
        state.selected = state.parameters.index('local_tone')
        self.assertEqual(panel.lines(state, 'CONTINUOUS')[4], 'EDIT LOCAL TONE ON')

    def test_smoothing_is_display_only_and_missing_lux_is_not_shown_as_zero(self):
        panel = StatusPanel()
        panel.sample(0., 20., 100.)
        panel.sample(.1, 20., 0.)
        self.assertGreater(panel.lux, 0.)
        self.assertLess(panel.lux, 100.)
        panel.sample(.2, 20., None)
        self.assertIsNone(panel.lux)
        self.assertIn('LUX --', panel.lines(State(), 'OFF')[1])
        panel.sample(.3, 20., 0.)
        self.assertEqual(panel.lux, 0.)
        self.assertIn('LUX 0', panel.lines(State(), 'OFF')[1])

    def test_auto_key_updates_panel_promptly_without_changing_policy_input(self):
        dev = Mock()
        view = (0x81, 0, (0, 0, 1280, 720), True)
        dev.views = {0: view}
        dev.view_request = view
        dev.finish.return_value = (0, 1, None)
        dev.tile_statistics.return_value = {'frame_id': 1, 'means': np.full((6, 8), 64.), 'mean': 64.}
        dev.render_count = dev.display_count = 1
        dev.render_first = dev.render_last = 0.
        dev.status_text.return_value = True
        state = State('detail')
        controls = Mock()
        calls = [0]
        clock = [0.]
        event_time = []

        def control_poll(*args):
            calls[0] += 1
            if calls[0] == 2:
                event_time.append(clock[0])
                return ['auto']
            return []
        controls.poll.side_effect = control_poll
        encoder = Mock(); encoder.poll.return_value = ([], {})
        sensors = Mock(); sensors.snapshot.return_value = {'lux': 42., 'distance_mm': None}
        commits = []
        dev.status_text.side_effect = lambda lines: commits.append((clock[0], lines)) or True
        report = {'unique_camera_frames': 0, 'events': [], 'samples': [], 'camera_capture_verified': False}
        policy = AdaptivePolicy('stable')

        def now():
            clock[0] += .01
            return clock[0]
        with patch('visual_aid.pl_runtime.time.monotonic', side_effect=now), patch('builtins.print'):
            run_pl(dev, state, controls, encoder, policy, sensors,
                   SimpleNamespace(seconds=.22), report, 0., 'OFF', lambda lut, b: lut)
        manual = next(t for t, lines in commits if 'MANUAL' in lines[0])
        self.assertLessEqual(manual - event_time[0], .15)
        self.assertEqual(policy.status()['lux'], 42.)
        self.assertFalse(state.automatic)
