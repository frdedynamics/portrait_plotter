import argparse
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

from status_led import StatusLed


EVENT_PREFIX = "PORTRAIT_PLOTTER_EVENT "


DEFAULT_CONFIG = {
    "button_pin": 17,
    "button_pull_up": True,
    "button_bounce_time": 0.2,
    "status_led_pin": None,
    "status_led_brightness": 0.35,
    "status_led_idle_mode": "heartbeat",
    "capture_countdown_seconds": 3,
    "pipeline_args": [
        "output.gcode",
        "--capture-picamera",
        "--captured-photo", "captured_photo.jpg",
        "--style-reference", "style_reference.png",
        "--width-mm", "100",
        "--height-mm", "125",
        "--speed", "1500",
        "--send-to-printer",
        "--serial-port", "/dev/serial/by-id/YOUR_PRINTER_SERIAL_ID",
    ],
}


def load_config(path):
    with Path(path).open("r", encoding="utf-8") as f:
        config = json.load(f)

    merged = DEFAULT_CONFIG.copy()
    merged.update(config)
    return merged


def validate_config(config):
    button_pin = config.get("button_pin")
    status_led_pin = config.get("status_led_pin")
    status_led_idle_mode = config.get("status_led_idle_mode", "heartbeat")
    try:
        status_led_brightness = float(config.get("status_led_brightness", 0.35))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("status_led_brightness must be a number between 0.0 and 1.0.") from exc

    if status_led_pin is not None and status_led_pin == button_pin:
        raise RuntimeError(
            f"button_pin and status_led_pin are both GPIO{button_pin}. "
            "Use different GPIO pins, or set status_led_pin to null."
        )
    if not 0.0 <= status_led_brightness <= 1.0:
        raise RuntimeError("status_led_brightness must be between 0.0 and 1.0.")
    if status_led_idle_mode not in {"heartbeat", "dim_wink"}:
        raise RuntimeError(
            "status_led_idle_mode must be either 'heartbeat' or 'dim_wink'."
        )


class ButtonPipelineRunner:
    def __init__(self, config):
        self.config = config
        self.lock = threading.Lock()
        self.busy = False
        self.status_led = StatusLed(
            config.get("status_led_pin"),
            brightness=config.get("status_led_brightness", 0.35),
            idle_mode=config.get("status_led_idle_mode", "heartbeat"),
        )
        self.status_led.ready()

    def run_pipeline(self):
        button_time = time.monotonic()
        if not self.lock.acquire(blocking=False):
            print("Pipeline is already running; ignoring button press.")
            self.status_led.busy_press()
            self.status_led.running()
            return

        self.busy = True
        try:
            countdown_seconds = float(self.config.get("capture_countdown_seconds", 0))
            self.status_led.running()

            command = [
                sys.executable,
                str(Path(__file__).with_name("plotter_pipeline.py")),
                *self.config["pipeline_args"],
                "--emit-events",
                "--capture-countdown-seconds",
                str(countdown_seconds),
            ]
            print("Running:")
            print(" ".join(command))
            process = subprocess.Popen(
                command,
                cwd=Path(__file__).parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in process.stdout:
                line = line.rstrip()
                if not self._handle_pipeline_event(line, button_time):
                    print(line)

            return_code = process.wait()
            if return_code:
                raise subprocess.CalledProcessError(return_code, command)

            print("Pipeline finished.")
            if "--capture-only" not in self.config["pipeline_args"]:
                self.status_led.success()
        except subprocess.CalledProcessError as exc:
            print(f"Pipeline failed with exit code {exc.returncode}.", file=sys.stderr)
            self.status_led.error()
        finally:
            self.status_led.ready()
            self.busy = False
            self.lock.release()

    def _handle_pipeline_event(self, line, button_time):
        if not line.startswith(EVENT_PREFIX):
            return False

        try:
            event_data = json.loads(line[len(EVENT_PREFIX):])
            event = event_data["event"]
            event_time = float(event_data["monotonic"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            print(f"Invalid pipeline event: {line}", file=sys.stderr)
            return True

        since_button = event_time - button_time
        if event == "capture_countdown":
            seconds = float(event_data.get("seconds", 0))
            print(f"Camera ready after {since_button:.3f}s; capture in {seconds:.1f}s.")
            self.status_led.start_countdown(seconds)
        elif event == "capture_start":
            led_time = self.status_led.capture_flash()
            message = f"Capture started {since_button:.3f}s after button press."
            if led_time is not None:
                indication_offset_ms = (led_time - event_time) * 1000.0
                message += f" LED indication offset {indication_offset_ms:+.1f}ms."
            print(message)
            self.status_led.running()
        elif event == "capture_complete":
            print(f"Capture completed {since_button:.3f}s after button press.")

        return True

    def run_pipeline_background(self):
        thread = threading.Thread(target=self.run_pipeline, daemon=True)
        thread.start()


def run_button_loop(config):
    try:
        from gpiozero import Button
        from signal import pause
    except ImportError as exc:
        raise RuntimeError("Missing gpiozero. Install with `python -m pip install gpiozero`.") from exc

    runner = ButtonPipelineRunner(config)
    button = Button(
        config["button_pin"],
        pull_up=config.get("button_pull_up", True),
        bounce_time=config.get("button_bounce_time", 0.2),
    )
    button.when_pressed = runner.run_pipeline_background

    print(f"Waiting for button on GPIO{config['button_pin']}...")
    pause()


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run the portrait plotter pipeline from a Raspberry Pi GPIO button.",
        allow_abbrev=False,
    )
    parser.add_argument("--config", default="embedded_config.json", help="JSON config path")
    parser.add_argument("--write-example-config", action="store_true", help="Write an example config and exit")
    parser.add_argument("--once", action="store_true", help="Run the configured pipeline once without GPIO")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    config_path = Path(args.config)
    if args.write_example_config:
        config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
        print(f"Wrote {config_path}")
        return

    try:
        config = load_config(config_path)
        validate_config(config)
        if args.once:
            runner = ButtonPipelineRunner(config)
            runner.run_pipeline()
        else:
            run_button_loop(config)
    except (RuntimeError, FileNotFoundError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
