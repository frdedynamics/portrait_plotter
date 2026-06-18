import math
import threading
import time


class StatusLed:
    def __init__(self, pin=None, brightness=0.35):
        self.pin = pin
        self.brightness = max(0.0, min(1.0, float(brightness)))
        self.led = None
        self._stop_event = threading.Event()
        self._thread = None
        self._lock = threading.Lock()

        if pin is None:
            return

        try:
            from gpiozero import PWMLED
        except ImportError as exc:
            raise RuntimeError("Missing gpiozero. Install with `python -m pip install gpiozero`.") from exc

        self.led = PWMLED(pin, frequency=1000)

    def available(self):
        return self.led is not None

    def close(self):
        self.off()
        if self.led:
            self.led.close()

    def _stop_pattern(self):
        with self._lock:
            self._stop_event.set()
            thread = self._thread

        if thread and thread.is_alive():
            thread.join(timeout=1.0)

        with self._lock:
            self._stop_event = threading.Event()
            self._thread = None

    def _start_pattern(self, target):
        if not self.led:
            return

        self._stop_pattern()
        with self._lock:
            self._thread = threading.Thread(target=target, args=(self._stop_event,), daemon=True)
            self._thread.start()

    def off(self):
        self._stop_pattern()
        if self.led:
            self.led.off()

    def on(self, value=1.0):
        self._stop_pattern()
        if self.led:
            self._set(value)

    def ready(self):
        self._start_pattern(self._ready_beacon)

    def running(self):
        self._start_pattern(
            lambda stop_event: self._breathe(
                stop_event,
                period=1.8,
                minimum=0.08,
                maximum=1.0,
            )
        )

    def success(self):
        self._run_blocking_pattern(self._blink_count, count=3, on_time=0.35, off_time=0.25)

    def error(self):
        self._run_blocking_pattern(self._blink_for_duration, duration=10.0, on_time=0.08, off_time=0.08)

    def busy_press(self):
        self._run_blocking_pattern(self._blink_count, count=2, on_time=0.08, off_time=0.08)

    def capture_flash(self):
        if not self.led:
            return None

        self._stop_pattern()
        started = time.monotonic()
        self._set(1.0)
        time.sleep(1.0)
        self._set(0.0)
        time.sleep(0.75)
        return started

    def start_countdown(self, seconds):
        if not self.led or seconds <= 0:
            return

        self._start_pattern(
            lambda stop_event: self._countdown_pattern(stop_event, seconds)
        )

    def _run_blocking_pattern(self, func, **kwargs):
        if not self.led:
            return
        self._stop_pattern()
        func(self._stop_event, **kwargs)

    def _breathe(self, stop_event, period, minimum, maximum):
        started = time.monotonic()
        while not stop_event.is_set():
            phase = ((time.monotonic() - started) % period) / period
            wave = (1.0 - math.cos(phase * 2.0 * math.pi)) / 2.0
            self._set(minimum + ((maximum - minimum) * wave))
            if stop_event.wait(0.01):
                break

    def _ready_beacon(self, stop_event):
        while not stop_event.is_set():
            for _ in range(2):
                self._set(0.35)
                if stop_event.wait(0.12):
                    return
                self._set(0.0)
                if stop_event.wait(0.14):
                    return
            if stop_event.wait(4.0):
                break

    def _countdown_pattern(self, stop_event, seconds):
        started = time.monotonic()
        next_beat = started
        deadline = started + seconds
        while next_beat < deadline and not stop_event.is_set():
            wait_time = next_beat - time.monotonic()
            if wait_time > 0 and stop_event.wait(wait_time):
                break

            self._set(1.0)
            if stop_event.wait(0.12):
                break
            self._set(0.0)

            progress = min(1.0, (time.monotonic() - started) / seconds)
            interval = 0.9 - (0.72 * (progress ** 1.5))
            next_beat += max(0.18, interval)

    def _blink_count(self, stop_event, count, on_time, off_time):
        for _ in range(count):
            if stop_event.is_set():
                break
            self._set(1.0)
            if stop_event.wait(on_time):
                break
            self._set(0.0)
            if stop_event.wait(off_time):
                break

    def _blink_for_duration(self, stop_event, duration, on_time, off_time):
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline and not stop_event.is_set():
            self._set(1.0)
            if stop_event.wait(on_time):
                break
            self._set(0.0)
            if stop_event.wait(off_time):
                break

    def _set(self, value):
        self.led.value = max(0.0, min(1.0, value)) * self.brightness
