import argparse
import time
from pathlib import Path


def capture_picamera_image(
    output_path,
    width=2560,
    height=1440,
    warmup_seconds=2.0,
    camera_num=0,
):
    try:
        from picamera2 import Picamera2
    except ImportError as exc:
        raise RuntimeError(
            "Missing Pi camera dependency. On Raspberry Pi OS, install it with "
            "`sudo apt install python3-picamera2`."
        ) from exc

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    camera = Picamera2(camera_num=camera_num)
    try:
        config = camera.create_still_configuration(
            main={"size": (width, height)}
        )
        camera.configure(config)
        camera.start()
        time.sleep(warmup_seconds)
        camera.capture_file(str(output_path))
        return output_path
    finally:
        camera.stop()
        camera.close()


def build_parser():
    parser = argparse.ArgumentParser(
        description="Capture one still image from a Raspberry Pi camera.",
        allow_abbrev=False,
    )
    parser.add_argument("output", help="Output image path")
    parser.add_argument("--width", type=int, default=2560, help="Capture width")
    parser.add_argument("--height", type=int, default=1440, help="Capture height")
    parser.add_argument("--warmup-seconds", type=float, default=2.0, help="Seconds to let exposure settle")
    parser.add_argument("--camera-num", type=int, default=0, help="Picamera2 camera number")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        path = capture_picamera_image(
            output_path=args.output,
            width=args.width,
            height=args.height,
            warmup_seconds=args.warmup_seconds,
            camera_num=args.camera_num,
        )
    except RuntimeError as exc:
        parser.error(str(exc))

    print(f"Captured Pi camera image: {path}")


if __name__ == "__main__":
    main()
