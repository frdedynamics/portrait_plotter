# CLI Reference

This file is generated from the current argparse help output.

Regenerate it with:

```powershell
python generate_cli_docs.py
```

## `plotter_pipeline.py`

Full photo/webcam to G-code pipeline

```text
usage: plotter_pipeline.py [-h] [--capture-webcam] [--capture-picamera]
                           [--captured-photo CAPTURED_PHOTO]
                           [--camera-index CAMERA_INDEX]
                           [--camera-backend {any,dshow,msmf,v4l2}]
                           [--camera-width CAMERA_WIDTH]
                           [--camera-height CAMERA_HEIGHT]
                           [--camera-warmup-frames CAMERA_WARMUP_FRAMES]
                           [--camera-delay CAMERA_DELAY]
                           [--picamera-width PICAMERA_WIDTH]
                           [--picamera-height PICAMERA_HEIGHT]
                           [--picamera-warmup-seconds PICAMERA_WARMUP_SECONDS]
                           [--picamera-num PICAMERA_NUM]
                           [--style-reference STYLE_REFERENCE]
                           [--preprocessed-photo PREPROCESSED_PHOTO]
                           [--skip-preprocess]
                           [--preprocess-mode {background,crop}]
                           [--preprocess-size PREPROCESS_SIZE]
                           [--detector {auto,mediapipe,haar}]
                           [--background-color BACKGROUND_COLOR]
                           [--face-height-factor FACE_HEIGHT_FACTOR]
                           [--min-width-factor MIN_WIDTH_FACTOR]
                           [--center-y-shift CENTER_Y_SHIFT]
                           [--autocontrast-clip AUTOCONTRAST_CLIP]
                           [--preprocess-debug PREPROCESS_DEBUG]
                           [--preprocess-meta PREPROCESS_META]
                           [--line-drawing LINE_DRAWING] [--skip-generation]
                           [--model MODEL] [--image-size IMAGE_SIZE]
                           [--quality {low,medium,high,auto}]
                           [--prompt PROMPT] [--prompt-file PROMPT_FILE]
                           --width-mm WIDTH_MM [--height-mm HEIGHT_MM]
                           [--lift-height LIFT_HEIGHT]
                           [--pen-down-height PEN_DOWN_HEIGHT] [--speed SPEED]
                           [--travel-speed TRAVEL_SPEED]
                           [--threshold THRESHOLD] [--invert]
                           [--min-size MIN_SIZE] [--simplify SIMPLIFY]
                           [--prune-spurs PRUNE_SPURS]
                           [--min-path-length MIN_PATH_LENGTH]
                           [--no-optimize-order] [--present-x PRESENT_X]
                           [--present-y PRESENT_Y] [--no-present]
                           [--send-to-printer] [--serial-port SERIAL_PORT]
                           [--serial-baud SERIAL_BAUD]
                           [--serial-connect-delay SERIAL_CONNECT_DELAY]
                           [--serial-response-timeout SERIAL_RESPONSE_TIMEOUT]
                           [--serial-dry-run]
                           [photo] [gcode]

Generate a plotter-ready line drawing from a photo and trace it to G-code.

positional arguments:
  photo                 Input photo to convert, or output G-code if using
                        --capture-webcam
  gcode                 Output G-code file

options:
  -h, --help            show this help message and exit
  --capture-webcam      Capture the input photo from a webcam
  --capture-picamera    Capture the input photo from a Raspberry Pi camera
  --captured-photo CAPTURED_PHOTO
                        Intermediate webcam capture path
  --camera-index CAMERA_INDEX
                        OpenCV webcam index
  --camera-backend {any,dshow,msmf,v4l2}
                        Optional OpenCV camera backend
  --camera-width CAMERA_WIDTH
                        Requested webcam frame width
  --camera-height CAMERA_HEIGHT
                        Requested webcam frame height
  --camera-warmup-frames CAMERA_WARMUP_FRAMES
                        Frames to discard before webcam capture
  --camera-delay CAMERA_DELAY
                        Seconds to wait before webcam capture
  --picamera-width PICAMERA_WIDTH
                        Requested Pi camera still width
  --picamera-height PICAMERA_HEIGHT
                        Requested Pi camera still height
  --picamera-warmup-seconds PICAMERA_WARMUP_SECONDS
                        Seconds to let Pi camera exposure settle
  --picamera-num PICAMERA_NUM
                        Picamera2 camera number
  --style-reference STYLE_REFERENCE
                        Optional style/context reference image
  --preprocessed-photo PREPROCESSED_PHOTO
                        Intermediate preprocessed portrait image
  --skip-preprocess     Send the original photo directly to the image model
  --preprocess-mode {background,crop}
                        background crops around all relevant faces and
                        suppresses background; crop skips background removal
  --preprocess-size PREPROCESS_SIZE
                        Preprocessed portrait size; defaults to --image-size
  --detector {auto,mediapipe,haar}
                        Face detector for preprocessing
  --background-color BACKGROUND_COLOR
                        RGB replacement color for background mode, e.g.
                        248,244,234
  --face-height-factor FACE_HEIGHT_FACTOR
                        Vertical context around detected face
  --min-width-factor MIN_WIDTH_FACTOR
                        Minimum crop width relative to face width
  --center-y-shift CENTER_Y_SHIFT
                        Shift crop downward relative to face height
  --autocontrast-clip AUTOCONTRAST_CLIP
                        Mild luminance autocontrast clipping percentage; use 0
                        to disable
  --preprocess-debug PREPROCESS_DEBUG
                        Optional debug image showing face/crop detection
  --preprocess-meta PREPROCESS_META
                        Optional JSON metadata path for preprocessing
  --line-drawing LINE_DRAWING
                        Intermediate line drawing PNG
  --skip-generation     Trace an existing --line-drawing without calling the
                        API
  --model MODEL         OpenAI image model
  --image-size IMAGE_SIZE
                        Generated image size, e.g. 1024x1536
  --quality {low,medium,high,auto}
  --prompt PROMPT       Override the default line drawing prompt
  --prompt-file PROMPT_FILE
                        Read the line drawing prompt from a text file
  --width-mm WIDTH_MM   Output drawing width in millimeters
  --height-mm HEIGHT_MM
                        Output drawing height in millimeters
  --lift-height LIFT_HEIGHT
                        Z height for travel moves
  --pen-down-height PEN_DOWN_HEIGHT
                        Z height while drawing
  --speed SPEED         Drawing feed rate in mm/min
  --travel-speed TRAVEL_SPEED
                        Travel feed rate in mm/min; defaults to --speed
  --threshold THRESHOLD
  --invert
  --min-size MIN_SIZE
  --simplify SIMPLIFY
  --prune-spurs PRUNE_SPURS
  --min-path-length MIN_PATH_LENGTH
  --no-optimize-order
  --present-x PRESENT_X
                        Final X position after lifting pen
  --present-y PRESENT_Y
                        Final Y position after lifting pen
  --no-present          Do not move XY after the final pen lift
  --send-to-printer     Stream generated G-code to a serial printer
  --serial-port SERIAL_PORT
                        Serial port, e.g. COM3 or /dev/ttyUSB0
  --serial-baud SERIAL_BAUD
                        Serial baud rate
  --serial-connect-delay SERIAL_CONNECT_DELAY
                        Seconds to wait after opening serial
  --serial-response-timeout SERIAL_RESPONSE_TIMEOUT
                        Seconds to wait for printer responses
  --serial-dry-run      Print serial commands without opening the port
```

## `webcam_capture.py`

Capture one image from a webcam

```text
usage: webcam_capture.py [-h] [--list-cameras] [--max-index MAX_INDEX]
                         [--camera-index CAMERA_INDEX]
                         [--backend {any,dshow,msmf,v4l2}] [--width WIDTH]
                         [--height HEIGHT] [--warmup-frames WARMUP_FRAMES]
                         [--delay DELAY]
                         [output]

Capture one still image from a webcam.

positional arguments:
  output                Output image path

options:
  -h, --help            show this help message and exit
  --list-cameras        Probe camera indices and print which ones open
  --max-index MAX_INDEX
                        Highest camera index to probe with --list-cameras
  --camera-index CAMERA_INDEX
                        OpenCV camera index
  --backend {any,dshow,msmf,v4l2}
                        Optional OpenCV capture backend
  --width WIDTH         Requested camera frame width
  --height HEIGHT       Requested camera frame height
  --warmup-frames WARMUP_FRAMES
                        Frames to discard before capture
  --delay DELAY         Seconds to wait before capture
```

## `picamera_capture.py`

Capture one image from a Raspberry Pi camera

```text
usage: picamera_capture.py [-h] [--width WIDTH] [--height HEIGHT]
                           [--warmup-seconds WARMUP_SECONDS]
                           [--camera-num CAMERA_NUM]
                           output

Capture one still image from a Raspberry Pi camera.

positional arguments:
  output                Output image path

options:
  -h, --help            show this help message and exit
  --width WIDTH         Capture width
  --height HEIGHT       Capture height
  --warmup-seconds WARMUP_SECONDS
                        Seconds to let exposure settle
  --camera-num CAMERA_NUM
                        Picamera2 camera number
```

## `preprocess_portrait.py`

Preprocess a portrait photo

```text
usage: preprocess_portrait.py [-h] [--size SIZE]
                              [--detector {auto,mediapipe,haar}]
                              [--mode {background,crop}]
                              [--background-color BACKGROUND_COLOR]
                              [--face-height-factor FACE_HEIGHT_FACTOR]
                              [--min-width-factor MIN_WIDTH_FACTOR]
                              [--center-y-shift CENTER_Y_SHIFT]
                              [--autocontrast-clip AUTOCONTRAST_CLIP]
                              [--debug DEBUG] [--meta META]
                              input output

positional arguments:
  input                 Input portrait photo
  output                Output preprocessed image

options:
  -h, --help            show this help message and exit
  --size SIZE           Output size. Use "1024" for square or "1024x1536".
                        Default: 1024
  --detector {auto,mediapipe,haar}
                        Face detector. Default: auto
  --mode {background,crop}
                        Preprocessing mode. background crops around all
                        relevant faces and suppresses background; crop crops
                        around all relevant faces without background removal.
                        Default: background
  --background-color BACKGROUND_COLOR
                        RGB background replacement color for background mode.
                        Default: 248,244,234
  --face-height-factor FACE_HEIGHT_FACTOR
                        How much vertical context to include around the face.
                        Default: 2.2
  --min-width-factor MIN_WIDTH_FACTOR
                        Minimum crop width relative to face width. Default:
                        1.6
  --center-y-shift CENTER_Y_SHIFT
                        Shift crop center downward relative to face height.
                        Default: 0.35
  --autocontrast-clip AUTOCONTRAST_CLIP
                        Mild luminance autocontrast clipping percentage. Use 0
                        to disable. Default: 0.5
  --debug DEBUG         Optional debug image path
  --meta META           Optional JSON metadata path
```

## `bitmaptracer.py`

Trace a bitmap line drawing to SVG or G-code

```text
usage: bitmaptracer.py [-h] [--threshold THRESHOLD] [--invert]
                       [--min-size MIN_SIZE] [--simplify SIMPLIFY]
                       [--prune-spurs PRUNE_SPURS]
                       [--min-path-length MIN_PATH_LENGTH]
                       [--stroke-width STROKE_WIDTH] [--gcode]
                       [--width-mm WIDTH_MM] [--height-mm HEIGHT_MM]
                       [--lift-height LIFT_HEIGHT]
                       [--pen-down-height PEN_DOWN_HEIGHT] [--speed SPEED]
                       [--travel-speed TRAVEL_SPEED] [--no-optimize-order]
                       [--present-x PRESENT_X] [--present-y PRESENT_Y]
                       [--no-present]
                       input output

positional arguments:
  input                 Input bitmap image, e.g. PNG/JPG
  output                Output SVG or G-code file

options:
  -h, --help            show this help message and exit
  --threshold THRESHOLD
  --invert
  --min-size MIN_SIZE
  --simplify SIMPLIFY
  --prune-spurs PRUNE_SPURS
                        Remove dangling skeleton branches up to this many
                        pixels
  --min-path-length MIN_PATH_LENGTH
                        Omit traced paths shorter than this many pixels
  --stroke-width STROKE_WIDTH
  --gcode               Export G-code even if output extension is not .gcode
  --width-mm WIDTH_MM   Output drawing width in millimeters
  --height-mm HEIGHT_MM
                        Output drawing height in millimeters
  --lift-height LIFT_HEIGHT
                        Z height for travel moves
  --pen-down-height PEN_DOWN_HEIGHT
                        Z height while drawing
  --speed SPEED         Drawing feed rate in mm/min
  --travel-speed TRAVEL_SPEED
                        Travel feed rate in mm/min; defaults to --speed
  --no-optimize-order   Keep traced path order instead of nearest-neighbor
                        ordering
  --present-x PRESENT_X
                        Final X position after lifting pen
  --present-y PRESENT_Y
                        Final Y position after lifting pen
  --no-present          Do not move XY after the final pen lift
```

## `serial_gcode_sender.py`

Stream G-code to a serial printer

```text
usage: serial_gcode_sender.py [-h] --port PORT [--baud BAUD]
                              [--connect-delay CONNECT_DELAY]
                              [--response-timeout RESPONSE_TIMEOUT]
                              [--dry-run]
                              gcode

Stream G-code to a Marlin-compatible printer over serial.

positional arguments:
  gcode                 G-code file to stream

options:
  -h, --help            show this help message and exit
  --port PORT           Serial port, e.g. COM3 or /dev/ttyUSB0
  --baud BAUD           Serial baud rate
  --connect-delay CONNECT_DELAY
                        Seconds to wait after opening serial
  --response-timeout RESPONSE_TIMEOUT
                        Seconds to wait for each printer response
  --dry-run             Print commands without opening the serial port
```

## `embedded_button_runner.py`

Run the pipeline from a Raspberry Pi GPIO button

```text
usage: embedded_button_runner.py [-h] [--config CONFIG]
                                 [--write-example-config] [--once]

Run the portrait plotter pipeline from a Raspberry Pi GPIO button.

options:
  -h, --help            show this help message and exit
  --config CONFIG       JSON config path
  --write-example-config
                        Write an example config and exit
  --once                Run the configured pipeline once without GPIO
```
