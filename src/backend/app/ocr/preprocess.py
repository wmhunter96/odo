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


def _order_corners(pts: np.ndarray) -> np.ndarray:
    """Order 4 arbitrary points as top-left, top-right, bottom-right,
    bottom-left, however they came out of contour detection."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _four_point_transform(mat: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Warp the quadrilateral `pts` in `mat` to a flat, top-down rectangle
    (the classic "document scanner" perspective correction)."""
    tl, tr, br, bl = _order_corners(pts)
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if width < 20 or height < 20:
        raise ValueError("degenerate receipt outline")
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32")
    src = np.array([tl, tr, br, bl], dtype="float32")
    matrix = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(mat, matrix, (width, height))


def crop_to_receipt(img: Image.Image) -> Image.Image:
    """Find the receipt's outline against its background and
    perspective-correct/crop to just that region, so OCR sees the receipt
    instead of the desk/hand/background around it. This also makes a
    separate rotation-only deskew pass unnecessary for receipts -- the
    perspective warp corrects orientation as part of flattening it.

    Falls back to the original, uncropped image whenever detection isn't
    confident (no clear 4-sided contour large enough to plausibly be the
    receipt) rather than risk cropping into the receipt itself.
    """
    mat = _to_cv(img)
    h, w = mat.shape[:2]

    gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)
    edged = cv2.dilate(edged, None, iterations=2)
    edged = cv2.erode(edged, None, iterations=1)

    contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return img

    image_area = w * h
    candidates = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    best_quad = None
    for c in candidates:
        # A receipt should dominate a reasonably tightly-framed photo of
        # it; smaller contours are more likely noise/background clutter.
        if cv2.contourArea(c) < image_area * 0.2:
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            best_quad = approx.reshape(4, 2).astype("float32")
            break

    if best_quad is None:
        return img

    try:
        warped = _four_point_transform(mat, best_quad)
    except (ValueError, cv2.error):
        return img

    return _to_pil(warped)


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
    """Full pipeline. `mode` is "odometer" (dashboard display) or "receipt"
    (printed text):

        odometer: load -> orient -> downscale -> rotation-only deskew ->
                  contrast boost
        receipt:  load -> orient -> downscale -> find & crop to the
                  receipt's outline (also corrects perspective/rotation
                  as part of flattening it) -> binarize
    """
    img = load_image(data)
    img = downscale(img)
    if mode == "receipt":
        img = crop_to_receipt(img)
        return binarize_for_receipt(img)
    img = deskew(img)
    return grayscale_contrast(img)
