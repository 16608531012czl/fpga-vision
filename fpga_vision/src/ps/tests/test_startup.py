"""Prevent boot-time overlay replacement, including jobs queued before activation."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'runtime'))
from visual_aid.startup import wait_for_boot_overlay


class BootOverlayWait(unittest.TestCase):
    def test_finished_service_does_not_delay_project(self):
        with patch('visual_aid.startup._boot_overlay_state',return_value={
                'LoadState':'loaded','ActiveState':'inactive','Job':''}), \
             patch('visual_aid.startup.time.sleep') as sleep:
            wait_for_boot_overlay()
            sleep.assert_not_called()

    def test_queued_job_and_running_job_both_finish_before_return(self):
        states=[{'LoadState':'loaded','ActiveState':'inactive','Job':'31'},
                {'LoadState':'loaded','ActiveState':'activating','Job':'31'},
                {'LoadState':'loaded','ActiveState':'inactive','Job':''}]
        with patch('visual_aid.startup._boot_overlay_state',side_effect=states) as query, \
             patch('visual_aid.startup.time.sleep') as sleep:
            wait_for_boot_overlay()
            self.assertEqual(query.call_count,3)
            self.assertEqual(sleep.call_count,2)

    def test_timeout_refuses_to_load_over_running_boot_program(self):
        with patch('visual_aid.startup._boot_overlay_state',return_value={
                'LoadState':'loaded','ActiveState':'activating','Job':'31'}):
            with self.assertRaisesRegex(TimeoutError,'boot overlay'):
                wait_for_boot_overlay(timeout=0)

    def test_image_without_boot_led_service_remains_supported(self):
        with patch('visual_aid.startup._boot_overlay_state',return_value={
                'LoadState':'not-found','ActiveState':'inactive','Job':''}):
            wait_for_boot_overlay()
