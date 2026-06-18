import cv2
import numpy as np


def render_hvlrobotics_signature_mask():
    text = "HVLRobotics"
    font = cv2.FONT_HERSHEY_SCRIPT_SIMPLEX
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
    return mask > 64
