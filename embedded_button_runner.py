import argparse
import json
import subprocess
import sys
import threading
import time
from pathlib import Path


DEFAULT_CONFIG = {
    "button_pin": 17,
    "button_pull_up": True,
    "button_bounce_time": 0.2,
    "status_led_pin": None,
    "error_led_pin": None,
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


class OptionalLed:
    def __init__(self, pin):
        self.led = None
        if pin is None:
            return

        try:
            from gpiozero import LED
        except ImportError as exc:
            raise RuntimeError("Missing gpiozero. Install with `python -m pip install gpiozero`.") from exc

        self.led = LED(pin)

    def on(self):
        if self.led:
            self.led.on()

    def off(self):
        if self.led:
            self.led.off()

    def blink_error(self, count=3):
        if not self.led:
            return
        for _ in range(count):
            self.led.on()
            time.sleep(0.15)
            self.led.off()
            time.sleep(0.15)


class ButtonPipelineRunner:
    def __init__(self, config):
        self.config = config
        self.lock = threading.Lock()
        self.busy = False
        self.status_led = OptionalLed(config.get("status_led_pin"))
        self.error_led = OptionalLed(config.get("error_led_pin"))

    def run_pipeline(self):
        if not self.lock.acquire(blocking=False):
            print("Pipeline is already running; ignoring button press.")
            return

        self.busy = True
        self.status_led.on()
        try:
            command = [
                sys.executable,
                str(Path(__file__).with_name("plotter_pipeline.py")),
                *self.config["pipeline_args"],
            ]
            print("Running:")
            print(" ".join(command))
            subprocess.run(command, cwd=Path(__file__).parent, check=True)
            print("Pipeline finished.")
        except subprocess.CalledProcessError as exc:
            print(f"Pipeline failed with exit code {exc.returncode}.", file=sys.stderr)
            self.error_led.blink_error()
        finally:
            self.status_led.off()
            self.busy = False
            self.lock.release()

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
        runner = ButtonPipelineRunner(config)
        if args.once:
            runner.run_pipeline()
        else:
            run_button_loop(config)
    except (RuntimeError, FileNotFoundError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
