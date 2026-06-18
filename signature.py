from pathlib import Path

import cv2
import numpy as np


SIGNATURE_SOURCE = Path(__file__).with_name("signature_source.png")


def render_hvlrobotics_signature_mask():
    image = cv2.imread(str(SIGNATURE_SOURCE), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError(f"Signature source image not found: {SIGNATURE_SOURCE}")

    if image.ndim == 3 and image.shape[2] == 4:
        color = image[:, :, :3].astype(np.float32)
        alpha = image[:, :, 3:4].astype(np.float32) / 255.0
        image = (color * alpha) + (255.0 * (1.0 - alpha))
        image = image.astype(np.uint8)

    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    mask = gray < 160
    rows, columns = np.where(mask)
    if not len(rows):
        raise RuntimeError(f"Signature source contains no dark strokes: {SIGNATURE_SOURCE}")

    padding = 4
    top = max(0, int(rows.min()) - padding)
    bottom = min(mask.shape[0], int(rows.max()) + padding + 1)
    left = max(0, int(columns.min()) - padding)
    right = min(mask.shape[1], int(columns.max()) + padding + 1)
    return mask[top:bottom, left:right]
