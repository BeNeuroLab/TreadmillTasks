"""Host-side motion regressions; no board or additional packages required.

Run from the repository root: python3 tests/continuous_motion_test.py
Only hardware/framework boundaries are mocked; tests execute the real driver
and task code.
"""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
TASK_PATH = ROOT / 'tasks/5-run-to-center-stop-continuous-led-zone-gain.py'


def load_module(name, path, modules):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


class FakeDataChannel:
    def __init__(self, name, sampling_rate, **kwargs):
        self.sampling_rate = sampling_rate
        self.record = Mock()
        self.stop = Mock()
        self.put = Mock()


class FakeAnalogInput:
    def __init__(self, name, sampling_rate, **kwargs):
        self.data_channel = FakeDataChannel(name, sampling_rate)
        self.timer = Mock()
        self.rising_event_ID = 0


def load_driver():
    hardware = types.ModuleType('pyControl.hardware')
    hardware.Analog_input = FakeAnalogInput
    hardware.Data_channel = FakeDataChannel
    hardware.Digital_output = Mock
    hardware.fw = types.SimpleNamespace(current_time=0)
    hardware.interrupt_queue = Mock()
    pycontrol = types.ModuleType('pyControl')
    pycontrol.hardware = hardware
    devices = types.ModuleType('devices')
    devices.__path__ = []
    firmware = types.ModuleType('devices.PAA5100JE_firmware')
    devices.PAA5100JE_firmware = firmware
    irq = types.ModuleType('pyb')
    irq.disable_irq = Mock(return_value=123)
    irq.enable_irq = Mock()
    clock = types.ModuleType('time')
    clock.sleep_ms = Mock()
    clock.sleep_us = Mock()
    return load_module('motion_driver', ROOT / 'devices/PAA5100JE.py', {
        'pyControl': pycontrol,
        'pyControl.hardware': hardware,
        'devices': devices,
        'devices.PAA5100JE_firmware': firmware,
        'machine': types.ModuleType('machine'),
        'pyb': irq,
        'time': clock,
    })


class MotionTestCase(unittest.TestCase):
    def setUp(self):
        self.driver = load_driver()
        self.sensor = self.driver.MotionDetector(
            reset=None, cs1='Y', cs2='X', sampling_rate=100
        )
        self.sensor.configure_continuous_motion(50)

    def sample(self, dx, dy):
        self.sensor._delta_x = dx
        self.sensor._delta_y = dy
        self.sensor._update_continuous_motion()


class ContinuousMotionTests(MotionTestCase):
    def test_snapshots_require_configuration(self):
        self.sensor.continuous_motion_enabled = False
        with self.assertRaises(AssertionError):
            self.sensor.get_x_motion_snapshot()
        with self.assertRaises(AssertionError):
            self.sensor.get_xy_motion_snapshot()

    def test_reversals_and_rollover_preserve_absolute_motion(self):
        for dx, dy in [(2, 7), (-3, -8), (4, 9), (-5, -10), (6, 11)]:
            self.sample(dx, dy)
        self.assertEqual(self.sensor.get_xy_motion_snapshot(),
                         (12, 8, 20, 45, 5))
        self.assertEqual(self.sensor.get_x_motion_snapshot(), (12, 8, 20, 5))
        self.sample(1, -2)
        self.assertEqual(self.sensor.get_xy_motion_snapshot(),
                         (13, 8, 19, 40, 5))
        self.sensor.reset_delta()
        self.assertEqual(self.sensor.get_xy_motion_snapshot(),
                         (13, 8, 19, 40, 5))

    def test_xy_snapshot_captures_values_before_restoring_interrupts(self):
        self.sample(3, -7)
        self.driver.pyb.enable_irq.side_effect = lambda state: self.sample(9, 9)
        self.assertEqual(self.sensor.get_xy_motion_snapshot(), (3, 0, 3, 7, 1))
        self.driver.pyb.disable_irq.assert_called_once_with()
        self.driver.pyb.enable_irq.assert_called_once_with(123)
        self.assertEqual(self.sensor.y_window_abs_total, 16)

    def test_reconfiguration_clears_both_windows(self):
        self.sample(20, -30)
        self.sensor.configure_continuous_motion(30)
        self.assertEqual(self.sensor.get_xy_motion_snapshot(), (0, 0, 0, 0, 0))
        for _ in range(3):
            self.sample(1, -2)
        self.assertEqual(self.sensor.get_xy_motion_snapshot(), (3, 0, 3, 6, 3))

    def test_acquisition_restart_clears_both_windows(self):
        self.sensor._sensors_ready = True
        self.sensor._start_acquisition()
        self.sample(-20, 30)
        self.sensor.acquiring = False
        self.sensor._start_acquisition()
        self.assertEqual(self.sensor.get_xy_motion_snapshot(), (0, 0, 0, 0, 0))
        for _ in range(5):
            self.sample(0, 0)
        self.assertEqual(self.sensor.get_xy_motion_snapshot(), (0, 0, 0, 0, 5))


class ZoneGainStoppingTests(MotionTestCase):
    def setUp(self):
        super().setUp()
        self.now = 0
        utility = types.ModuleType('pyControl.utility')
        utility.v = types.SimpleNamespace()
        utility.ms = 1
        utility.second = 1000
        utility.minute = 60000
        utility.get_current_time = lambda: self.now
        for name in ('goto_state', 'set_timer', 'disarm_timer', 'reset_timer',
                     'stop_framework', 'print'):
            setattr(utility, name, Mock())
        pycontrol = types.ModuleType('pyControl')
        pycontrol.utility = utility
        self.hw = types.ModuleType('hardware_definition')
        self.hw.motionSensor = self.sensor
        for name in ('speaker', 'light', 'reward', 'cameraTrigger', 'off'):
            setattr(self.hw, name, Mock())
        self.task = load_module('zone_gain_task', TASK_PATH, {
            'pyControl': pycontrol,
            'pyControl.utility': utility,
            'hardware_definition': self.hw,
            'devices': types.ModuleType('devices'),
        })
        self.v = self.task.v
        self.v.cpi = 254
        self.v.cpi_y = 508

    def set_speed(self, now, x_counts, y_counts, samples=5):
        self.now = now
        self.task.update_stop_speed(now, x_counts, y_counts, samples)

    def test_defaults_remain_unchanged(self):
        self.assertEqual(self.v.stop_speed_threshold_cm_s, 5)
        self.assertEqual(self.v.speed_window_ms, 50)
        self.assertEqual(self.v.reward_wait_time, 250)
        self.assertEqual(self.v.performance_timeout, 15000)

    def test_axis_limits_block_at_equality_and_above(self):
        for x_counts, y_counts in [(25, 0), (30, 0), (0, 50), (0, 60)]:
            with self.subTest(x_counts=x_counts, y_counts=y_counts):
                self.set_speed(0, 0, 0)
                self.set_speed(300, x_counts, y_counts)
                self.assertIsNone(self.v.below_speed_start_time)
                self.assertFalse(self.task.stop_detected())

    def test_individual_sensor_cpi_and_separate_axis_limits(self):
        self.set_speed(0, 20, 40)
        self.assertAlmostEqual(self.v.rolling_speed_x_cm_s, 4)
        self.assertAlmostEqual(self.v.rolling_speed_y_cm_s, 4)
        self.assertAlmostEqual(self.v.rolling_speed_cm_s, 4)
        self.now = 250
        self.assertTrue(self.task.stop_detected())
        self.set_speed(300, 20, 20)
        self.assertAlmostEqual(self.v.rolling_speed_y_cm_s, 2)

    def test_stop_dwell_requires_full_duration_and_restarts_for_y_motion(self):
        self.set_speed(0, 0, 0)
        self.now = 249
        self.assertFalse(self.task.stop_detected())
        self.now = 250
        self.assertTrue(self.task.stop_detected())
        self.set_speed(260, 0, 50)
        self.assertFalse(self.task.stop_detected())
        self.set_speed(300, 0, 0)
        self.now = 549
        self.assertFalse(self.task.stop_detected())
        self.now = 550
        self.assertTrue(self.task.stop_detected())

    def test_incomplete_window_clears_stop_dwell(self):
        self.set_speed(0, 0, 0)
        self.set_speed(300, 0, 0, samples=4)
        self.assertFalse(self.v.rolling_speed_valid)
        self.assertIsNone(self.v.below_speed_start_time)
        self.assertEqual(self.v.rolling_speed_x_cm_s, 0)
        self.assertEqual(self.v.rolling_speed_y_cm_s, 0)
        self.assertFalse(self.task.stop_detected())
        self.set_speed(310, 0, 0)
        self.assertFalse(self.task.stop_detected())
        self.now = 560
        self.assertTrue(self.task.stop_detected())

    def test_cue_motion_tracking_remains_x_only(self):
        self.set_speed(0, 0, 60)
        self.assertFalse(self.task.moving_at_cue_on())
        self.set_speed(10, 25, 0)
        self.assertTrue(self.task.moving_at_cue_on())
        self.set_speed(300, 0, 60)
        self.assertEqual(self.v.last_above_speed_time, 10)
        self.assertFalse(self.task.moving_at_cue_on())

    def test_forward_progress_uses_x_and_selected_sign(self):
        self.sample(3, 100)
        self.assertAlmostEqual(self.task.poll_motion_sensor(), 0.03)
        self.sample(-2, -100)
        self.assertEqual(self.task.poll_motion_sensor(), 0)
        self.v.forward_sign = -1
        self.task.sync_motion_snapshot()
        self.sample(-4, 100)
        self.assertAlmostEqual(self.task.poll_motion_sensor(), 0.04)
        self.sample(4, -100)
        self.assertEqual(self.task.poll_motion_sensor(), 0)

    def test_running_and_reversals_on_either_axis_prevent_stopping(self):
        for dx, dy in [(5, 0), (0, 10)]:
            with self.subTest(dx=dx, dy=dy):
                self.sensor.configure_continuous_motion(50)
                self.v.below_speed_start_time = None
                for i in range(35):
                    sign = 1 if i % 2 else -1
                    self.sample(sign * dx, sign * dy)
                    self.now = 10 * (i + 1)
                    self.task.poll_motion_sensor()
                self.assertFalse(self.task.stop_detected())
                self.assertIsNone(self.v.below_speed_start_time)

    def test_target_wait_rewards_only_after_y_motion_stops(self):
        self.v.current_distance = 50
        self.task.target_wait('entry')
        for i in range(35):
            self.sample(0, 12 if i % 2 else -12)
            self.now += 10
            self.task.target_wait('sensor_update')
        self.task.goto_state.assert_not_called()
        self.assertEqual(self.v.current_distance, 50)
        self.assertEqual(self.v.current_led_percent, 76)
        for _ in range(25):
            self.sample(0, 0)
            self.now += 10
            self.task.target_wait('sensor_update')
        self.task.goto_state.assert_not_called()
        self.sample(0, 0)
        self.now += 10
        self.task.target_wait('sensor_update')
        self.task.goto_state.assert_called_once_with('reward')
        output = [call.args[0] for call in self.task.print.call_args_list]
        self.assertTrue(any('stop_detected_speed_x_cm_s' in line
                            for line in output))
        self.assertTrue(any('stop_detected_speed_y_cm_s' in line
                            for line in output))

    def test_startup_reads_each_cpi_after_sensor_initialization(self):
        self.sensor._sensors_ready = False
        self.sensor.sensor_x = None
        self.sensor.sensor_y = None

        def initialise():
            self.sensor.sensor_x = types.SimpleNamespace(CPI=254)
            self.sensor.sensor_y = types.SimpleNamespace(CPI=508)
            self.sensor._sensors_ready = True

        self.sensor._initialise_sensors = initialise
        self.task.run_start()
        self.assertEqual(self.v.cpi, 254)
        self.assertEqual(self.v.cpi_y, 508)
        self.hw.cameraTrigger.start.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
