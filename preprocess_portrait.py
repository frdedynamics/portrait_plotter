# preprocess_portrait.py
#
# Conservative portrait preprocessing for image-model based line-art generation.
#
# Goal:
#   Harmonize input photos before sending them to the image model:
#   - correct orientation
#   - detect face
#   - crop head + shoulders
#   - pad safely
#   - resize consistently
#   - mild exposure normalization
#
# Install:
#   pip install pillow numpy opencv-contrib-python
#
# Optional, better face detector:
#   pip install mediapipe
#
# Usage:
#   python preprocess_portrait.py input.jpg output.png --size 1024
#
# With debug image and metadata:
#   python preprocess_portrait.py input.jpg output.png --debug debug.png --meta meta.json

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps


@dataclass
class FaceBox:
    x: int
    y: int
    w: int
    h: int
    score: float
    detector: str


@dataclass
class PreprocessMeta:
    input_path: str
    output_path: str
    original_width: int
    original_height: int
    output_width: int
    output_height: int
    detector_used: str
    face_found: bool
    num_faces: int
    chosen_face: Optional[dict]
    crop_box_original_coords: Tuple[float, float, float, float]
    used_padding: bool
    warnings: List[str]


def load_image_rgb_fix_exif(path: str | Path) -> np.ndarray:
    """
    Load image as RGB and respect EXIF orientation.
    """
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    return np.array(img)


def detect_faces_mediapipe(rgb: np.ndarray) -> List[FaceBox]:
    """
    Optional MediaPipe face detection.
    Works better than Haar cascades for many real photos.
    """
    try:
        import mediapipe as mp
    except ImportError:
        return []

    if not hasattr(mp, "solutions") or not hasattr(mp.solutions, "face_detection"):
        return []

    h, w, _ = rgb.shape
    results: List[FaceBox] = []

    mp_face = mp.solutions.face_detection

    with mp_face.FaceDetection(
        model_selection=1,
        min_detection_confidence=0.45,
    ) as face_detection:
        detection_result = face_detection.process(rgb)

    if not detection_result.detections:
        return []

    for det in detection_result.detections:
        score = float(det.score[0]) if det.score else 0.0
        box = det.location_data.relative_bounding_box

        x = int(box.xmin * w)
        y = int(box.ymin * h)
        bw = int(box.width * w)
        bh = int(box.height * h)

        x = max(0, x)
        y = max(0, y)
        bw = min(w - x, bw)
        bh = min(h - y, bh)

        if bw > 10 and bh > 10:
            results.append(FaceBox(x, y, bw, bh, score, "mediapipe"))

    return results


def detect_faces_haar(rgb: np.ndarray) -> List[FaceBox]:
    """
    OpenCV Haar fallback.
    Less robust, but easy to install on Raspberry Pi.
    """
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.equalizeHist(gray)

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(cascade_path)

    faces = detector.detectMultiScale(
        gray,
        scaleFactor=1.08,
        minNeighbors=5,
        minSize=(40, 40),
    )

    results: List[FaceBox] = []

    for x, y, w, h in faces:
        results.append(FaceBox(int(x), int(y), int(w), int(h), 0.5, "haar"))

    return results


def detect_faces(rgb: np.ndarray, detector: str = "auto") -> List[FaceBox]:
    """
    detector:
      auto      -> try mediapipe, then haar
      mediapipe -> only mediapipe
      haar      -> only haar
    """
    if detector not in {"auto", "mediapipe", "haar"}:
        raise ValueError("detector must be 'auto', 'mediapipe', or 'haar'")

    if detector in {"auto", "mediapipe"}:
        faces = detect_faces_mediapipe(rgb)
        if faces or detector == "mediapipe":
            return faces

    return detect_faces_haar(rgb)


def choose_primary_face(faces: List[FaceBox]) -> Optional[FaceBox]:
    """
    Pick the largest/highest-confidence face.
    """
    if not faces:
        return None

    return max(faces, key=lambda f: f.w * f.h * max(f.score, 0.1))


def compute_portrait_crop(
    face: FaceBox,
    img_w: int,
    img_h: int,
    output_aspect: float = 1.0,
    face_height_factor: float = 3.4,
    min_width_factor: float = 2.7,
    center_y_shift: float = 0.45,
) -> Tuple[float, float, float, float]:
    """
    Compute a generous crop around face/head/shoulders.

    Coordinates returned as:
        left, top, right, bottom
    in original image coordinates.

    Important parameters:
      face_height_factor:
        Higher = wider/looser crop. 3.2–4.0 is useful for head + shoulders.

      min_width_factor:
        Ensures ears/headphones/hair/hat are not cut off.

      center_y_shift:
        Positive shifts crop downward to include neck/collar/shoulders.
    """
    fx, fy, fw, fh = face.x, face.y, face.w, face.h

    face_cx = fx + fw / 2.0
    face_cy = fy + fh / 2.0

    crop_h = fh * face_height_factor
    crop_w = crop_h * output_aspect

    min_crop_w = fw * min_width_factor
    if crop_w < min_crop_w:
        crop_w = min_crop_w
        crop_h = crop_w / output_aspect

    crop_cx = face_cx
    crop_cy = face_cy + center_y_shift * fh

    left = crop_cx - crop_w / 2.0
    right = crop_cx + crop_w / 2.0
    top = crop_cy - crop_h / 2.0
    bottom = crop_cy + crop_h / 2.0

    return left, top, right, bottom


def compute_center_crop(
    img_w: int,
    img_h: int,
    output_aspect: float,
) -> Tuple[float, float, float, float]:
    """
    Fallback if no face is detected.
    """
    input_aspect = img_w / img_h

    if input_aspect > output_aspect:
        crop_h = img_h
        crop_w = crop_h * output_aspect
    else:
        crop_w = img_w
        crop_h = crop_w / output_aspect

    cx = img_w / 2.0
    cy = img_h / 2.0

    return (
        cx - crop_w / 2.0,
        cy - crop_h / 2.0,
        cx + crop_w / 2.0,
        cy + crop_h / 2.0,
    )


def estimate_border_color(rgb: np.ndarray) -> Tuple[int, int, int]:
    """
    Estimate a reasonable padding color from image borders.
    This avoids weird black/transparent padding if crop goes outside image.
    """
    top = rgb[0:5, :, :]
    bottom = rgb[-5:, :, :]
    left = rgb[:, 0:5, :]
    right = rgb[:, -5:, :]

    border_pixels = np.concatenate(
        [
            top.reshape(-1, 3),
            bottom.reshape(-1, 3),
            left.reshape(-1, 3),
            right.reshape(-1, 3),
        ],
        axis=0,
    )

    median = np.median(border_pixels, axis=0)
    return tuple(int(v) for v in median)


def crop_with_padding(
    rgb: np.ndarray,
    crop_box: Tuple[float, float, float, float],
    pad_color: Optional[Tuple[int, int, int]] = None,
) -> Tuple[np.ndarray, bool]:
    """
    Crop using original coordinates, padding where crop extends beyond image.
    """
    h, w, _ = rgb.shape
    left, top, right, bottom = crop_box

    left_i = int(np.floor(left))
    top_i = int(np.floor(top))
    right_i = int(np.ceil(right))
    bottom_i = int(np.ceil(bottom))

    pad_left = max(0, -left_i)
    pad_top = max(0, -top_i)
    pad_right = max(0, right_i - w)
    pad_bottom = max(0, bottom_i - h)

    used_padding = any(v > 0 for v in [pad_left, pad_top, pad_right, pad_bottom])

    if pad_color is None:
        pad_color = estimate_border_color(rgb)

    if used_padding:
        padded = cv2.copyMakeBorder(
            rgb,
            pad_top,
            pad_bottom,
            pad_left,
            pad_right,
            borderType=cv2.BORDER_CONSTANT,
            value=pad_color,
        )
    else:
        padded = rgb

    left_p = left_i + pad_left
    top_p = top_i + pad_top
    right_p = right_i + pad_left
    bottom_p = bottom_i + pad_top

    crop = padded[top_p:bottom_p, left_p:right_p]

    return crop, used_padding


def mild_luminance_autocontrast(
    rgb: np.ndarray,
    clip_percent: float = 0.5,
) -> np.ndarray:
    """
    Mild contrast normalization on luminance only.

    This is intentionally conservative.
    It should improve badly exposed webcam images without creating too many
    artificial details.
    """
    if clip_percent <= 0:
        return rgb

    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)

    low = np.percentile(l, clip_percent)
    high = np.percentile(l, 100.0 - clip_percent)

    if high <= low + 1:
        return rgb

    l_float = l.astype(np.float32)
    l_float = (l_float - low) * (255.0 / (high - low))
    l_float = np.clip(l_float, 0, 255).astype(np.uint8)

    lab_out = cv2.merge([l_float, a, b])
    return cv2.cvtColor(lab_out, cv2.COLOR_LAB2RGB)


def resize_image(
    rgb: np.ndarray,
    output_size: Tuple[int, int],
) -> np.ndarray:
    """
    Resize with high-quality interpolation.
    """
    out_w, out_h = output_size
    return cv2.resize(rgb, (out_w, out_h), interpolation=cv2.INTER_AREA)


def make_debug_image(
    rgb: np.ndarray,
    faces: List[FaceBox],
    chosen_face: Optional[FaceBox],
    crop_box: Tuple[float, float, float, float],
) -> np.ndarray:
    """
    Draw detected face boxes and selected crop on original image.
    """
    debug = rgb.copy()
    bgr = cv2.cvtColor(debug, cv2.COLOR_RGB2BGR)

    for face in faces:
        color = (180, 180, 180)
        if chosen_face and face == chosen_face:
            color = (0, 255, 0)

        cv2.rectangle(
            bgr,
            (face.x, face.y),
            (face.x + face.w, face.y + face.h),
            color,
            2,
        )

        cv2.putText(
            bgr,
            f"{face.detector} {face.score:.2f}",
            (face.x, max(0, face.y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1,
            cv2.LINE_AA,
        )

    left, top, right, bottom = crop_box
    cv2.rectangle(
        bgr,
        (int(left), int(top)),
        (int(right), int(bottom)),
        (0, 128, 255),
        2,
    )

    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def preprocess_portrait(
    input_path: str | Path,
    output_path: str | Path,
    output_size: Tuple[int, int] = (1024, 1024),
    detector: str = "auto",
    face_height_factor: float = 2.2,
    min_width_factor: float = 1.6,
    center_y_shift: float = 0.35,
    autocontrast_clip: float = 0.5,
    debug_path: Optional[str | Path] = None,
    meta_path: Optional[str | Path] = None,
) -> PreprocessMeta:
    input_path = str(input_path)
    output_path = str(output_path)

    rgb = load_image_rgb_fix_exif(input_path)
    img_h, img_w, _ = rgb.shape

    out_w, out_h = output_size
    output_aspect = out_w / out_h

    faces = detect_faces(rgb, detector=detector)
    chosen = choose_primary_face(faces)

    warnings: List[str] = []

    if chosen is not None:
        crop_box = compute_portrait_crop(
            chosen,
            img_w=img_w,
            img_h=img_h,
            output_aspect=output_aspect,
            face_height_factor=face_height_factor,
            min_width_factor=min_width_factor,
            center_y_shift=center_y_shift,
        )
    else:
        crop_box = compute_center_crop(img_w, img_h, output_aspect)
        warnings.append("No face detected. Used center crop fallback.")

    crop, used_padding = crop_with_padding(rgb, crop_box)
    crop = resize_image(crop, output_size)

    crop = mild_luminance_autocontrast(crop, clip_percent=autocontrast_clip)

    Image.fromarray(crop).save(output_path)

    if debug_path is not None:
        debug = make_debug_image(rgb, faces, chosen, crop_box)
        Image.fromarray(debug).save(debug_path)

    # Quality warnings
    if chosen is not None:
        face_fraction_original = chosen.h / img_h
        if face_fraction_original < 0.12:
            warnings.append("Detected face is small in the original image.")

        if len(faces) > 1:
            warnings.append(
                f"Multiple faces detected ({len(faces)}). Used the largest/highest-confidence face."
            )

        left, top, right, bottom = crop_box
        if left < 0 or top < 0 or right > img_w or bottom > img_h:
            warnings.append("Crop extended outside image. Padding was added.")

    meta = PreprocessMeta(
        input_path=input_path,
        output_path=output_path,
        original_width=img_w,
        original_height=img_h,
        output_width=out_w,
        output_height=out_h,
        detector_used=chosen.detector if chosen else detector,
        face_found=chosen is not None,
        num_faces=len(faces),
        chosen_face=asdict(chosen) if chosen else None,
        crop_box_original_coords=tuple(float(v) for v in crop_box),
        used_padding=used_padding,
        warnings=warnings,
    )

    if meta_path is not None:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(asdict(meta), f, indent=2)

    return meta


def parse_size(size_str: str) -> Tuple[int, int]:
    """
    Parse "1024" or "1024x1536".
    """
    if "x" in size_str.lower():
        w_str, h_str = size_str.lower().split("x")
        return int(w_str), int(h_str)

    size = int(size_str)
    return size, size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input portrait photo")
    parser.add_argument("output", help="Output preprocessed image")

    parser.add_argument(
        "--size",
        default="1024",
        help='Output size. Use "1024" for square or "1024x1536". Default: 1024',
    )

    parser.add_argument(
        "--detector",
        default="auto",
        choices=["auto", "mediapipe", "haar"],
        help="Face detector. Default: auto",
    )

    parser.add_argument(
        "--face-height-factor",
        type=float,
        default=2.2,
        help="How much vertical context to include around the face. Default: 2.2",
    )

    parser.add_argument(
        "--min-width-factor",
        type=float,
        default=1.6,
        help="Minimum crop width relative to face width. Default: 1.6",
    )

    parser.add_argument(
        "--center-y-shift",
        type=float,
        default=0.35,
        help="Shift crop center downward relative to face height. Default: 0.35",
    )

    parser.add_argument(
        "--autocontrast-clip",
        type=float,
        default=0.5,
        help="Mild luminance autocontrast clipping percentage. Use 0 to disable. Default: 0.5",
    )

    parser.add_argument("--debug", default=None, help="Optional debug image path")
    parser.add_argument("--meta", default=None, help="Optional JSON metadata path")

    args = parser.parse_args()

    output_size = parse_size(args.size)

    meta = preprocess_portrait(
        input_path=args.input,
        output_path=args.output,
        output_size=output_size,
        detector=args.detector,
        face_height_factor=args.face_height_factor,
        min_width_factor=args.min_width_factor,
        center_y_shift=args.center_y_shift,
        autocontrast_clip=args.autocontrast_clip,
        debug_path=args.debug,
        meta_path=args.meta,
    )

    print(json.dumps(asdict(meta), indent=2))


if __name__ == "__main__":
    main()
