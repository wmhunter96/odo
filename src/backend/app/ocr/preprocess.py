"""Image preprocessing shared by both the odometer and receipt OCR paths.

Kept as small, composable, pure-image-in/image-out functions so individual
steps can be reordered, skipped, or tuned without touching the OCR engine or
parsers. Everything here runs on CPU with Pillow + OpenCV (headless), no
GPU and no network access required.
"""
from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image, ImageOps

MAX_DIMENSION = 2200


def load_image(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    # Respect EXIF orientation (phone cameras nearly always set this).
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")


def downscale(img: Image.Image, max_dimension: int = MAX_DIMENSION) -> Image.Image:
    w, h = img.size
    longest = max(w, h)
    if longest <= max_dimension:
        return img
    scale = max_dimension / longest
    return img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)


def _to_cv(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def _to_pil(mat: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(mat, cv2.COLOR_BGR2RGB))


def deskew(img: Image.Image) -> Image.Image:
    """Correct small rotation offsets (a few degrees) common in handheld
    photos, using the minimum-area bounding box of dark pixels."""
    mat = _to_cv(img)
    gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY)
    gray = cv2.bitwise_not(gray)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    coords = cv2.findNonZero(thresh)
    if coords is None or len(coords) < 20:
        return img
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    # Only correct small skew; large "angles" usually mean the heuristic
    # picked up noise rather than real rotation.
    if abs(angle) < 0.5 or abs(angle) > 15:
        return img
    (h, w) = mat.shape[:2]
    center = (w // 2, h // 2)
    m = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        mat, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    return _to_pil(rotated)


def grayscale_contrast(img: Image.Image) -> Image.Image:
    """Grayscale + adaptive contrast boost + light denoise. Suited to
    photos of illuminated dashboard displays: uneven lighting, glare, and
    a colored background behind the digits."""
    mat = _to_cv(img)
    gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, h=10)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    return Image.fromarray(gray)


def binarize_for_receipt(img: Image.Image) -> Image.Image:
    """Grayscale + adaptive threshold to pure black/white. Printed (often
    thermal) receipts are small, dense text on an already high-contrast
    background -- CLAHE tends to blotch that print into gray mush, while
    binarization is the standard, much more reliable preprocessing for
    Tesseract on document/receipt text."""
    mat = _to_cv(img)
    gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, h=7)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )
    return Image.fromarray(thresh)


def prepare_for_ocr(data: bytes, mode: str = "odometer") -> Image.Image:
    """Full pipeline: load -> orient -> downscale -> deskew -> mode-specific
    contrast handling. `mode` is "odometer" (dashboard display) or
    "receipt" (printed text)."""
    img = load_image(data)
    img = downscale(img)
    img = deskew(img)
    if mode == "receipt":
        return binarize_for_receipt(img)
    return grayscale_contrast(img)
