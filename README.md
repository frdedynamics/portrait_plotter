# Portrait Plotter

Pipeline for turning a portrait photo into plotter-ready G-code:

1. take a photo,
2. preprocess it by cropping around all relevant faces and suppressing the photo background,
3. generate a black-line portrait drawing with the OpenAI API,
4. trace that bitmap line drawing with `bitmaptracer.py`,
5. write G-code to a file for the plotter controller.

Printer connection, Raspberry Pi UI, and job sending are intentionally outside this repository.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "sk-..."
```

On Linux/Raspberry Pi:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."
```

## Run The Full Pipeline

For the complete generated CLI parameter reference, see [CLI.md](CLI.md).

For Raspberry Pi camera, GPIO button, and Ender 3 embedded setup, see [EMBEDDED.md](EMBEDDED.md).

On Raspberry Pi, install with `requirements-rpi.txt` instead of only `requirements.txt` so GPIO button support is included.

```powershell
python plotter_pipeline.py photo.jpg output.gcode `
  --style-reference style_reference.png `
  --preprocessed-photo photo_preprocessed.png `
  --line-drawing output_line.png `
  --width-mm 100 `
  --height-mm 125 `
  --lift-height 5 `
  --speed 1500
```

The preprocessed photo and generated line drawing are saved separately so they can be inspected before plotting.

## Capture From Webcam

Capture a still image only:

```powershell
python webcam_capture.py captured_photo.jpg --camera-index 0
```

Request a specific capture resolution:

```powershell
python webcam_capture.py captured_photo.jpg `
  --camera-index 2 `
  --backend dshow `
  --width 2560 `
  --height 1440
```

If index `0` does not open, probe available indices:

```powershell
python webcam_capture.py --list-cameras --max-index 10
```

On Windows, trying a specific backend can help:

```powershell
python webcam_capture.py --list-cameras --backend dshow
python webcam_capture.py captured_photo.jpg --camera-index 0 --backend dshow
```

On Raspberry Pi/Linux, the backend is usually `v4l2`:

```bash
python webcam_capture.py --list-cameras --backend v4l2
python webcam_capture.py captured_photo.jpg --camera-index 0 --backend v4l2
```

Run the full pipeline using the webcam as input:

```powershell
python plotter_pipeline.py output.gcode `
  --capture-webcam `
  --captured-photo captured_photo.jpg `
  --camera-index 2 `
  --camera-width 2560 `
  --camera-height 1440 `
  --style-reference style_reference.png `
  --width-mm 100 `
  --height-mm 125
```

Preprocessing is enabled by default. It corrects image orientation, detects relevant faces, crops around the face group, replaces/suppresses the background with a light color, resizes to the model input size, and applies mild luminance normalization. This is the preferred mode when the input may contain multiple people.

To keep the group crop but skip background removal:

```powershell
python plotter_pipeline.py photo.jpg output.gcode `
  --preprocess-mode crop `
  --style-reference style_reference.png `
  --width-mm 100 `
  --height-mm 125
```

To send the original photo directly to the image model:

```powershell
python plotter_pipeline.py photo.jpg output.gcode `
  --skip-preprocess `
  --style-reference style_reference.png `
  --width-mm 100 `
  --height-mm 125
```

For debugging the portrait crop:

```powershell
python plotter_pipeline.py photo.jpg output.gcode `
  --style-reference style_reference.png `
  --preprocess-debug preprocess_debug.png `
  --preprocess-meta preprocess_meta.json `
  --width-mm 100 `
  --height-mm 125
```

## Preprocess Only

You can run preprocessing by itself:

```powershell
python preprocess_portrait.py photo.jpg preprocessed_photo.png `
  --size 1024x1536 `
  --debug preprocess_debug.png `
  --meta preprocess_meta.json
```

The default mode crops around all relevant faces and suppresses the background. The debug image shows detected face boxes and the selected group crop; the metadata JSON records which detector was used and any warnings.

To crop around the face group without background removal:

```powershell
python preprocess_portrait.py photo.jpg preprocessed_photo.png `
  --mode crop `
  --size 1024x1536 `
  --debug preprocess_debug.png `
  --meta preprocess_meta.json
```

## Trace An Existing Line Drawing

Use this when you already have a generated bitmap line drawing and only want G-code:

```powershell
python plotter_pipeline.py output.gcode `
  --skip-generation `
  --line-drawing output_line.png `
  --width-mm 100 `
  --height-mm 125
```

## Useful Tracing Knobs

- `--simplify`: higher values make fewer, straighter G-code moves.
- `--min-size`: removes small bitmap components before skeleton tracing.
- `--prune-spurs`: removes short dangling skeleton branches.
- `--min-path-length`: omits dot-like traced paths.
- `--threshold`: manually controls black/white thresholding; by default Otsu thresholding is used.

The defaults in `plotter_pipeline.py` are more aggressive than raw `bitmaptracer.py` because GPT-generated line drawings often contain small texture marks that become tiny plotter moves.

Generated G-code homes with `G28` at the start. At the end it lifts the pen and presents the work at `X0 Y220` by default. Adjust with `--present-x` / `--present-y`, or disable the final XY move with `--no-present`.

## Optional HVLRobotics Signature

Add a single-line `HVLRobotics` signature in the bottom-left corner:

```powershell
python plotter_pipeline.py photo.jpg output.gcode `
  --style-reference style_reference.png `
  --width-mm 100 `
  --signature
```

The default signature is 28 mm wide with a 4 mm left and bottom margin. Adjust it with:

```text
--signature-width 24
--signature-margin 5
--signature-gap 2
```

The signature is appended after the portrait paths and before the final presentation move. When enabled, the portrait is uniformly scaled and shifted upward to reserve a bottom band for the signature, including the configured gap. This preserves the portrait aspect ratio and guarantees that portrait lines cannot overlap the signature.

The signature is generated as plotter-ready vector strokes and does not require an additional font dependency.

## Send G-code To Ender 3

First do a dry run. This reads the G-code and prints the commands that would be sent, without opening the serial port:

```powershell
python serial_gcode_sender.py output.gcode --port COM3 --dry-run
```

Stream to the printer:

```powershell
python serial_gcode_sender.py output.gcode --port COM3 --baud 115200
```

On Raspberry Pi the port is often `/dev/ttyUSB0` or `/dev/ttyACM0`:

```bash
python serial_gcode_sender.py output.gcode --port /dev/ttyUSB0 --baud 115200
```

You can also send directly after generating:

```powershell
python plotter_pipeline.py photo.jpg output.gcode `
  --style-reference style_reference.png `
  --width-mm 100 `
  --height-mm 125 `
  --send-to-printer `
  --serial-port COM3
```

For a full webcam-to-printer run:

```powershell
python plotter_pipeline.py output.gcode `
  --capture-webcam `
  --captured-photo captured_photo.jpg `
  --style-reference style_reference.png `
  --width-mm 100 `
  --height-mm 125 `
  --send-to-printer `
  --serial-port COM3
```

Serial streaming is intentionally opt-in because it can move the printer. Confirm the pen is mounted, the bed is clear, the drawing origin and Z heights are safe, and the correct serial port is selected before using `--send-to-printer`.

## API Key Safety

For local development, keep your OpenAI API key out of the repository.

Recommended local setup:

1. Copy `.env.example` to `.env`.
2. Put your real key in `.env`.
3. Load it into your shell before running the pipeline.

PowerShell:

```powershell
$env:OPENAI_API_KEY = "sk-..."
```

Linux/Raspberry Pi:

```bash
export OPENAI_API_KEY="sk-..."
```

`.env` and `.venv` are ignored by git in this repo. `.env.example` is safe to commit because it contains only a placeholder.

Use GitHub Secrets only for GitHub Actions or other GitHub-hosted automation. A GitHub Secret does not automatically help your Raspberry Pi or your local shell; for the Pi, store the key as an environment variable, a local `.env` file, or a systemd environment file that is not committed.

Before pushing, run:

```powershell
git status
git diff -- .gitignore README.md requirements.txt .env.example
```

Do not commit screenshots, logs, shell history, config files, or test scripts that contain a real `OPENAI_API_KEY`. If a key is ever committed, revoke it in the OpenAI dashboard and create a new one; deleting it from git later is not enough because it remains in history.
