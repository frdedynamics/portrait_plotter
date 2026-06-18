import cv2
import numpy as np


def render_hvlrobotics_signature_mask():
    text = "HVLRobotics"
    font = cv2.FONT_HERSHEY_SCRIPT_COMPLEX
    font_scale = 3.0
    thickness = 3
    padding = 24

    (text_width, text_height), baseline = cv2.getTextSize(
        text,
        font,
        font_scale,
        thickness,
    )
    mask = np.zeros(
        (text_height + baseline + (padding * 2), text_width + (padding * 2)),
        dtype=np.uint8,
    )
    origin = (padding, padding + text_height)
    cv2.putText(
        mask,
        text,
        origin,
        font,
        font_scale,
        255,
        thickness,
        lineType=cv2.LINE_AA,
    )
    flourish = np.array([
        [
            (padding + int(text_width * 0.18), origin[1] + baseline + 2),
            (padding + int(text_width * 0.48), origin[1] + baseline + 6),
            (padding + int(text_width * 0.78), origin[1] + baseline + 3),
            (padding + int(text_width * 0.98), origin[1] + baseline - 4),
        ]
    ], dtype=np.int32)
    cv2.polylines(mask, flourish, False, 255, thickness=2, lineType=cv2.LINE_AA)
    return mask > 64
