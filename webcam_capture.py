import argparse
import time
from pathlib import Path

import cv2


def probe_camera_indices(max_index=10, backend=None):
    results = []

    for index in range(max_index + 1):
        capture = open_capture(index, backend=backend)
        try:
            opened = capture.isOpened()
            width = None
            height = None

            if opened:
                ok, frame = capture.read()
                if ok and frame is not None:
                    height, width = frame.shape[:2]

            results.append(
                {
                    "index": index,
                    "opened": opened,
                    "width": width,
                    "height": height,
                }
            )
        finally:
            capture.release()

    return results


def open_capture(camera_index, backend=None):
    if backend is None:
        return cv2.VideoCapture(camera_index)

    backend_map = {
        "any": cv2.CAP_ANY,
        "dshow": cv2.CAP_DSHOW,
        "msmf": cv2.CAP_MSMF,
        "v4l2": cv2.CAP_V4L2,
    }
    if backend not in backend_map:
        raise RuntimeError(f"Unknown camera backend: {backend}")

    return cv2.VideoCapture(camera_index, backend_map[backend])


def capture_webcam_image(
    output_path,
    camera_index=0,
    width=None,
    height=None,
    warmup_frames=20,
    delay=0.0,
    backend=None,
):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    capture = open_capture(camera_index, backend=backend)
    if not capture.isOpened():
        raise RuntimeError(f"Could not open webcam index {camera_index}.")

    try:
        if width:
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height:
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        if delay > 0:
            time.sleep(delay)

        frame = None
        for _ in range(max(1, warmup_frames)):
            ok, frame = capture.read()
            if not ok:
                frame = None

        if frame is None:
            raise RuntimeError("Could not read a frame from the webcam.")

        if not cv2.imwrite(str(output_path), frame):
            raise RuntimeError(f"Could not write captured image: {output_path}")

        return output_path
    finally:
        capture.release()


def build_parser():
    parser = argparse.ArgumentParser(
        description="Capture one still image from a webcam.",
        allow_abbrev=False,
    )
    parser.add_argument("output", nargs="?", help="Output image path")
    parser.add_argument("--list-cameras", action="store_true", help="Probe camera indices and print which ones open")
    parser.add_argument("--max-index", type=int, default=10, help="Highest camera index to probe with --list-cameras")
    parser.add_argument("--camera-index", type=int, default=0, help="OpenCV camera index")
    parser.add_argument("--backend", choices=["any", "dshow", "msmf", "v4l2"], default=None, help="Optional OpenCV capture backend")
    parser.add_argument("--width", type=int, default=None, help="Requested camera frame width")
    parser.add_argument("--height", type=int, default=None, help="Requested camera frame height")
    parser.add_argument("--warmup-frames", type=int, default=20, help="Frames to discard before capture")
    parser.add_argument("--delay", type=float, default=0.0, help="Seconds to wait before capture")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.list_cameras:
            results = probe_camera_indices(max_index=args.max_index, backend=args.backend)
            for result in results:
                if result["opened"]:
                    size = ""
                    if result["width"] and result["height"]:
                        size = f" ({result['width']}x{result['height']})"
                    print(f"index {result['index']}: opened{size}")
                else:
                    print(f"index {result['index']}: not available")
            return

        if not args.output:
            parser.error("output is required unless --list-cameras is used.")

        path = capture_webcam_image(
            output_path=args.output,
            camera_index=args.camera_index,
            width=args.width,
            height=args.height,
            warmup_frames=args.warmup_frames,
            delay=args.delay,
            backend=args.backend,
        )
    except RuntimeError as exc:
        parser.error(str(exc))

    image = cv2.imread(str(path))
    if image is not None:
        height, width = image.shape[:2]
        print(f"Captured image: {path} ({width}x{height})")
    else:
        print(f"Captured image: {path}")


if __name__ == "__main__":
    main()
