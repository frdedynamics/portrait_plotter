# Raspberry Pi 5 Embedded Setup

This setup runs the same pipeline as the desktop CLI, but starts it from a physical GPIO button.

Target hardware:

- Raspberry Pi 5
- Raspberry Pi Camera Module 3
- Optional Raspberry Pi AI HAT+
- Ender 3 connected over USB serial
- Momentary push button on GPIO

The embedded flow is:

1. Button press
2. Capture photo with Raspberry Pi camera
3. Preprocess portrait
4. Generate line drawing with OpenAI API
5. Trace line drawing to G-code
6. Stream G-code to the Ender 3 over USB serial

## Hardware Wiring

Use BCM GPIO numbering.

### Button

Recommended:

- One button leg to `GPIO17` / physical pin `11`
- Other button leg to `GND` / physical pin `9`

The code uses the Raspberry Pi internal pull-up resistor:

```python
Button(17, pull_up=True)
```

So the button connects the GPIO pin to ground when pressed. Do not connect the button to 5V.

### Optional Status LED

Status LED:

- `GPIO27` / physical pin `13` -> resistor, for example 330 ohm -> LED anode
- LED cathode -> `GND`

The status LED is optional. Set `status_led_pin` to `null` if not used.

Current LED behaviors:

- ready: slow breathing
- capture countdown: blinks faster as capture approaches
- capture moment: one long pulse
- pipeline running: repeating pulse
- success: three slow blinks, then ready breathing
- error: fast blinking, then ready breathing
- button pressed while busy: two quick blinks

## Raspberry Pi Setup

Use a current Raspberry Pi OS release. Camera Module 3 uses the modern libcamera/Picamera2 stack, so this project uses `picamera2`, not the old legacy `picamera` package.

For Raspberry Pi 5, make sure you use the correct small 22-pin camera connector/cable for the Pi 5 camera port. Camera Module 3 kits are often supplied with the older 15-pin cable, so you may need the Pi 5 camera adapter cable.

Install OS packages:

```bash
sudo apt update
sudo apt install -y python3-picamera2 rpicam-apps
```

Check that the Pi sees the camera:

```bash
rpicam-hello --list-cameras
```

Test a still capture outside Python:

```bash
rpicam-still -o camera_test.jpg --width 2560 --height 1440
```

Create the project venv and install Python dependencies:

```bash
python -m venv .venv --system-site-packages
source .venv/bin/activate
python -m pip install -r requirements-rpi.txt
```

Use `requirements-rpi.txt` on the Raspberry Pi, not just `requirements.txt`.

`requirements-rpi.txt` includes the normal project dependencies from `requirements.txt` and adds Pi-specific GPIO support:

```text
-r requirements.txt
gpiozero
```

`--system-site-packages` is recommended because `python3-picamera2` is installed by apt into the system Python environment, not by pip.

Test the project PiCamera capture:

```bash
python picamera_capture.py captured_photo.jpg --width 2560 --height 1440
```

## Optional AI HAT+

The AI HAT+ is optional for this project.

It does not accelerate the OpenAI image-generation call. That part still runs through the OpenAI API.

Where it could help later:

- local person/foreground segmentation before sending the image to OpenAI
- more reliable multi-person background removal than OpenCV GrabCut
- local face/person detection at camera preview speed

Current recommendation:

- keep the first embedded version simple with Picamera2 + OpenCV preprocessing
- use the AI HAT+ only if background removal becomes unreliable or too slow
- treat HAT support as a separate enhancement, probably by adding a new preprocessing backend such as `--preprocess-backend hailo`

The current code does not require the AI HAT+.

Set the OpenAI API key locally on the Pi:

```bash
export OPENAI_API_KEY="sk-..."
```

For a service, put the key in a local environment file that is not committed.

## Printer Serial Port

Plug in the Ender 3 over USB and list stable serial device names:

```bash
ls -l /dev/serial/by-id/
```

Use the `/dev/serial/by-id/...` path in config instead of `/dev/ttyUSB0` when possible, because `ttyUSB0` can change after reboot.

If needed, give the Pi user serial access:

```bash
sudo usermod -aG dialout $USER
```

Log out and back in after changing groups.

## Configure Embedded Runner

Copy the example config:

```bash
cp embedded_config.example.json embedded_config.json
```

Edit:

- `style_reference.png`
- `width-mm` / `height-mm`
- `serial-port`
- optional `status_led_pin`
- `capture_countdown_seconds`

Example key part:

```json
{
  "button_pin": 17,
  "status_led_pin": 27,
  "capture_countdown_seconds": 3,
  "pipeline_args": [
    "output.gcode",
    "--capture-picamera",
    "--captured-photo", "captured_photo.jpg",
    "--picamera-width", "2560",
    "--picamera-height", "1440",
    "--style-reference", "style_reference.png",
    "--width-mm", "100",
    "--height-mm", "125",
    "--send-to-printer",
    "--serial-port", "/dev/serial/by-id/YOUR_PRINTER_SERIAL_ID"
  ]
}
```

## Test Without Button

Run the configured pipeline once:

```bash
source .venv/bin/activate
python embedded_button_runner.py --config embedded_config.json --once
```

For printer-safe testing, add `--serial-dry-run` inside `pipeline_args`.

## Run Button Listener

```bash
source .venv/bin/activate
python embedded_button_runner.py --config embedded_config.json
```

Press the button once. While a job is running, further button presses are ignored.

## systemd Service

Create a local environment file:

```bash
sudo mkdir -p /etc/portrait-plotter
sudo nano /etc/portrait-plotter/env
```

Contents:

```text
OPENAI_API_KEY=sk-...
```

Create service:

```bash
sudo nano /etc/systemd/system/portrait-plotter.service
```

Template:

```ini
[Unit]
Description=Portrait Plotter Button Runner
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/pi/portrait_plotter
EnvironmentFile=/etc/portrait-plotter/env
ExecStart=/home/pi/portrait_plotter/.venv/bin/python /home/pi/portrait_plotter/embedded_button_runner.py --config embedded_config.json
Restart=on-failure
User=pi

[Install]
WantedBy=multi-user.target
```

Enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable portrait-plotter.service
sudo systemctl start portrait-plotter.service
sudo systemctl status portrait-plotter.service
```

Logs:

```bash
journalctl -u portrait-plotter.service -f
```

## Disable Or Remove The Service

This is useful if the Raspberry Pi is also used for CODESYS or other software that may claim the same GPIO pins.

Stop the plotter listener temporarily:

```bash
sudo systemctl stop portrait-plotter.service
```

Disable automatic start at boot:

```bash
sudo systemctl disable portrait-plotter.service
```

For CODESYS work, usually do both:

```bash
sudo systemctl stop portrait-plotter.service
sudo systemctl disable portrait-plotter.service
```

Re-enable later:

```bash
sudo systemctl enable portrait-plotter.service
sudo systemctl start portrait-plotter.service
```

Check status:

```bash
sudo systemctl status portrait-plotter.service
```

Remove the service completely:

```bash
sudo systemctl stop portrait-plotter.service
sudo systemctl disable portrait-plotter.service
sudo rm /etc/systemd/system/portrait-plotter.service
sudo systemctl daemon-reload
```

If you also want to remove the local API key environment file:

```bash
sudo rm -r /etc/portrait-plotter
```

## Safety Checklist

- Test with `--serial-dry-run` first.
- Confirm the pen holder and Z lift height are safe.
- Confirm `G28` homing is safe for the current printer setup.
- Confirm the plot origin and paper position before enabling actual streaming.
- Keep hands clear when sending G-code.
