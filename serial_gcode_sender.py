import argparse
import re
import time
from pathlib import Path


OK_RE = re.compile(r"\bok\b", re.IGNORECASE)


def strip_gcode_line(line):
    line = line.strip()
    if not line:
        return ""

    if line.startswith(";"):
        return ""

    if ";" in line:
        line = line.split(";", 1)[0].strip()

    return line


def iter_gcode_commands(path):
    with Path(path).open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            command = strip_gcode_line(line)
            if command:
                yield command


def wait_for_ok(serial_port, timeout):
    deadline = time.monotonic() + timeout
    last_line = ""

    while time.monotonic() < deadline:
        raw = serial_port.readline()
        if not raw:
            continue

        line = raw.decode("utf-8", errors="replace").strip()
        if line:
            last_line = line
            print(f"< {line}")

        lower = line.lower()
        if OK_RE.search(line):
            return
        if lower.startswith("error") or "kill" in lower:
            raise RuntimeError(f"Printer reported an error: {line}")

    detail = f" Last response: {last_line}" if last_line else ""
    raise RuntimeError(f"Timed out waiting for printer ok.{detail}")


def stream_gcode(
    gcode_path,
    port,
    baud=115200,
    connect_delay=2.0,
    response_timeout=30.0,
    dry_run=False,
):
    commands = list(iter_gcode_commands(gcode_path))
    if not commands:
        raise RuntimeError(f"No G-code commands found in {gcode_path}.")

    if dry_run:
        print(f"Dry run: {len(commands)} commands would be sent to {port}.")
        for command in commands[:20]:
            print(f"> {command}")
        if len(commands) > 20:
            print(f"... {len(commands) - 20} more commands")
        return

    try:
        import serial
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: install pyserial with `python -m pip install pyserial`."
        ) from exc

    print(f"Opening serial port {port} at {baud} baud")
    with serial.Serial(port, baudrate=baud, timeout=1, write_timeout=10) as serial_port:
        time.sleep(connect_delay)
        serial_port.reset_input_buffer()
        serial_port.reset_output_buffer()

        # Marlin accepts a temperature query as a harmless readiness probe.
        serial_port.write(b"M105\n")
        serial_port.flush()
        wait_for_ok(serial_port, timeout=response_timeout)

        total = len(commands)
        for index, command in enumerate(commands, start=1):
            print(f"> {command}")
            serial_port.write((command + "\n").encode("ascii", errors="ignore"))
            serial_port.flush()
            wait_for_ok(serial_port, timeout=response_timeout)

            if index == 1 or index == total or index % 50 == 0:
                print(f"Progress: {index}/{total}")

    print("Finished streaming G-code.")


def build_parser():
    parser = argparse.ArgumentParser(description="Stream G-code to a Marlin-compatible printer over serial.")
    parser.add_argument("gcode", help="G-code file to stream")
    parser.add_argument("--port", required=True, help="Serial port, e.g. COM3 or /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--connect-delay", type=float, default=2.0, help="Seconds to wait after opening serial")
    parser.add_argument("--response-timeout", type=float, default=30.0, help="Seconds to wait for each printer response")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without opening the serial port")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        stream_gcode(
            gcode_path=args.gcode,
            port=args.port,
            baud=args.baud,
            connect_delay=args.connect_delay,
            response_timeout=args.response_timeout,
            dry_run=args.dry_run,
        )
    except RuntimeError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
