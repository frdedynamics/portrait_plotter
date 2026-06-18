import threading
import time


class StatusLed:
    def __init__(self, pin=None):
        self.pin = pin
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

        self.led = PWMLED(pin)

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
            self.led.value = value

    def ready(self):
        self._start_pattern(self._breathe_slow)

    def running(self):
        self._start_pattern(self._pulse_running)

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
        self.led.on()
        time.sleep(0.75)
        self.led.off()
        time.sleep(0.1)
        return started

    def start_countdown(self, seconds):
        if not self.led or seconds <= 0:
            return

        self._start_pattern(
            lambda stop_event: self._countdown_pattern(stop_event, seconds)
        )

    def countdown(self, seconds):
        if not self.led or seconds <= 0:
            if seconds > 0:
                time.sleep(seconds)
            return

        self._stop_pattern()
        steps = max(1, int(seconds))
        for index in range(steps):
            remaining = steps - index
            period = max(0.18, 0.55 - (index * 0.10))
            print(f"Capture in {remaining}...")
            end_time = time.monotonic() + 1.0
            while time.monotonic() < end_time:
                self.led.on()
                time.sleep(period / 2.0)
                self.led.off()
                time.sleep(period / 2.0)

    def _run_blocking_pattern(self, func, **kwargs):
        if not self.led:
            return
        self._stop_pattern()
        func(self._stop_event, **kwargs)

    def _breathe_slow(self, stop_event):
        while not stop_event.is_set():
            for value in list(range(0, 101, 4)) + list(range(100, -1, -4)):
                if stop_event.is_set():
                    break
                self.led.value = value / 100.0
                time.sleep(0.04)

    def _pulse_running(self, stop_event):
        while not stop_event.is_set():
            self.led.value = 1.0
            time.sleep(0.7)
            if stop_event.is_set():
                break
            self.led.value = 0.25
            time.sleep(0.7)

    def _countdown_pattern(self, stop_event, seconds):
        started = time.monotonic()
        while not stop_event.is_set():
            elapsed = time.monotonic() - started
            if elapsed >= seconds:
                break

            progress = min(1.0, elapsed / seconds)
            period = max(0.18, 0.55 - (progress * 0.37))
            self.led.on()
            if stop_event.wait(period / 2.0):
                break
            self.led.off()
            if stop_event.wait(period / 2.0):
                break

    def _blink_count(self, stop_event, count, on_time, off_time):
        for _ in range(count):
            if stop_event.is_set():
                break
            self.led.on()
            time.sleep(on_time)
            self.led.off()
            time.sleep(off_time)

    def _blink_for_duration(self, stop_event, duration, on_time, off_time):
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline and not stop_event.is_set():
            self.led.on()
            time.sleep(on_time)
            self.led.off()
            time.sleep(off_time)
