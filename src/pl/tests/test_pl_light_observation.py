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


class PLLightObservation(unittest.TestCase):
    def test_zero_lux_is_observed_and_failed_distance_is_not(self):
        dev = Mock()
        view = (0x81, 0, (0, 0, 1280, 720), True)
        dev.views = {0: view}
        dev.view_request = view
        dev.finish.return_value = (0, 1, None)
        dev.tile_statistics.return_value = {'frame_id': 1, 'means': np.full((6, 8), 64.), 'mean': 64.}
        dev.render_count = dev.display_count = 1
        dev.render_first = dev.render_last = 0.
        state = State('detail')
        controls = Mock()
        controls.poll.return_value = []
        encoder = Mock()
        encoder.poll.return_value = ([], {})
        sensors = Mock()
        sensors.snapshot.return_value = {'lux': 0., 'distance_mm': None}
        observed = {'lux': False, 'distance_mm': False}
        report = {'unique_camera_frames': 0, 'events': [], 'samples': [],
                  'camera_capture_verified': False, 'sensor_readings_observed': observed}
        policy = AdaptivePolicy('stable')
        clock = [0.]

        def now():
            clock[0] += .01
            return clock[0]

        with patch('visual_aid.pl_runtime.time.monotonic', side_effect=now), patch('builtins.print'):
            run_pl(dev, state, controls, encoder, policy, sensors,
                   SimpleNamespace(seconds=.2), report, 0., 'OFF', lambda lut, b: lut)
        self.assertTrue(observed['lux'])
        self.assertFalse(observed['distance_mm'])
        self.assertEqual(policy.status()['lux'], 0.)
        self.assertGreater(report['unique_camera_frames'], 0)
