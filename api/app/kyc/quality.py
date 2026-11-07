"""Image quality gate. BLUR_THRESHOLD calibrated on the 47 specimens: sharp images have Laplacian variance >= 930, the blurred one 1.0."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

BLUR_THRESHOLD = 100.0
MIN_SIDE_PX = 600
MAX_BYTES = 5 * 1024 * 1024


@dataclass
class Quality:
    ok: bool
    reason: str | None  # blurry | small | undecodable | None
    sharpness: float = 0.0
    width: int = 0
    height: int = 0


def sniff_mime(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def assess(data: bytes, mime: str) -> Quality:
    if mime == "application/pdf":  # cannot measure blur without rendering; the extraction confidence gate still applies
        return Quality(True, None)
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return Quality(False, "undecodable")
    h, w = img.shape
    sharp = float(cv2.Laplacian(img, cv2.CV_64F).var())
    if min(h, w) < MIN_SIDE_PX:
        return Quality(False, "small", sharp, w, h)
    if sharp < BLUR_THRESHOLD:
        return Quality(False, "blurry", sharp, w, h)
    return Quality(True, None, sharp, w, h)
