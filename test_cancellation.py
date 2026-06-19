import unittest
from unittest.mock import Mock, patch

from embedded_button_runner import ButtonPipelineRunner
from serial_gcode_sender import EMERGENCY_COMMANDS, emergency_stop_and_lift
from status_led import StatusLed


def runner_config():
    return {
        "button_pin": 17,
        "status_led_pin": None,
        "status_led_brightness": 0.35,
        "status_led_idle_mode": "heartbeat",
        "cancel_hold_seconds": 2.0,
        "cancel_timeout_seconds": 0.1,
        "capture_countdown_seconds": 0,
        "pipeline_args": ["output.gcode"],
    }


class ButtonGestureTests(unittest.TestCase):
    def setUp(self):
        self.runner = ButtonPipelineRunner(runner_config())
        self.runner.run_pipeline_background = Mock()

    def tearDown(self):
        if self.runner.hold_timer:
            self.runner.hold_timer.cancel()

    def test_short_idle_press_starts_pipeline_on_release(self):
        self.runner.button_pressed()
        self.runner.press_started -= 0.1
        self.runner.button_released()
        self.runner.run_pipeline_background.assert_called_once_with()

    def test_long_idle_press_does_not_start_pipeline(self):
        self.runner.button_pressed()
        self.runner.press_started -= 2.1
        self.runner.button_released()
        self.runner.run_pipeline_background.assert_not_called()

    def test_short_busy_press_does_not_start_or_cancel(self):
        self.runner.busy = True
        self.runner.cancel_pipeline = Mock()
        self.runner.button_pressed()
        self.runner.press_started -= 0.1
        self.runner.button_released()
        self.runner.run_pipeline_background.assert_not_called()
        self.runner.cancel_pipeline.assert_not_called()

    def test_long_busy_press_cancels_once(self):
        self.runner.busy = True
        self.runner.cancel_pipeline = Mock()
        self.runner.button_pressed()
        self.runner.hold_timer.cancel()
        self.runner._handle_busy_long_press()
        self.runner.button_released()
        self.runner.cancel_pipeline.assert_called_once_with()
        self.runner.run_pipeline_background.assert_not_called()


class FakeSerial:
    def __init__(self):
        self.writes = []
        self.output_reset = False
        self.flushed = False

    def reset_output_buffer(self):
        self.output_reset = True

    def write(self, value):
        self.writes.append(value)

    def flush(self):
        self.flushed = True


class FakeLed:
    def __init__(self):
        self.value = 1.0

    def off(self):
        self.value = 0.0


class LedStateTests(unittest.TestCase):
    def test_preparing_capture_turns_led_off(self):
        status_led = StatusLed()
        status_led.led = FakeLed()

        status_led.preparing_capture()

        self.assertEqual(status_led.led.value, 0.0)


class PrinterCancellationTests(unittest.TestCase):
    def test_emergency_stop_sends_quickstop_and_relative_lift(self):
        serial_port = FakeSerial()
        emergency_stop_and_lift(serial_port)

        self.assertTrue(serial_port.output_reset)
        self.assertTrue(serial_port.flushed)
        self.assertEqual(
            serial_port.writes,
            [(command + "\n").encode("ascii") for command in EMERGENCY_COMMANDS],
        )


class ProcessCancellationTests(unittest.TestCase):
    def test_cancel_interrupts_active_process(self):
        runner = ButtonPipelineRunner(runner_config())
        process = Mock()
        process.poll.return_value = None
        process.wait.return_value = 0
        runner.active_process = process

        with patch.object(runner, "_interrupt_process") as interrupt:
            runner.cancel_pipeline()

        interrupt.assert_called_once_with(process)
        self.assertTrue(runner.cancel_requested.is_set())


if __name__ == "__main__":
    unittest.main()
