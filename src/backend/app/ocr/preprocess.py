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
# Tuned via a quantitative grid search against a real photographed
# receipt, scored against its known-correct manual transcription (through
# this exact function, not a reimplementation -- an earlier pass here
# tuned against a hand-rolled cv2 pipeline that resized before converting
# to grayscale, which turned out to behave differently enough from this
# actual PIL-then-grayscale order to invalidate its numbers). 900px wide +
# Otsu binarization + denoise strength 10 got gallons, price, total, AND
# date all correct simultaneously, and did so across multiple PSM modes
# (see routes/ocr.py) -- the more PSM-independent a width is, the more
# likely it generalizes to receipts other than the one it was tuned on.
# Used as an exact target (see resize_to_width), not just a floor.
#
# Re-tuned after switching to the "best" (not "fast") Tesseract English
# model -- see tesseract_provider.py -- which changes what each width
# gets right. 900 still wins for gallons/price/total/date with the new
# model too.
MIN_RECEIPT_WIDTH = 900
# Second pass, tried only when the primary pass doesn't find an address --
# a wider crop recovers small punctuation (a zip code's digits) better in
# practice, at the cost of it more often losing the exact time-of-day. See
# routes/ocr.py for how the two passes get merged. 1200 (not the "fast"-
# model-era 1800) is what actually recovers the address with the "best"
# model -- re-verified directly, not carried over by assumption.
WIDE_RECEIPT_WIDTH = 1200


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


def resize_to_width(img: Image.Image, width: int) -> Image.Image:
    """Scale a receipt crop to an exact target width (both up and down --
    the grid search behind MIN_RECEIPT_WIDTH found a specific sweet spot,
    not just a floor, so a crop that's naturally already wider than the
    target is deliberately brought back down to it too). Used to build a
    receipt variant at a given width from an already-cropped image,
    without repeating crop detection -- see prepare_receipt_variant()."""
    w, h = img.size
    if w == width:
        return img
    scale = width / w
    return img.resize((max(1, width), max(1, int(h * scale))), Image.LANCZOS)


def prepare_receipt_variant(cropped_receipt: Image.Image, width: int) -> Image.Image:
    """Build an OCR-ready receipt image at a specific target width from an
    already-cropped receipt (crop_to_receipt()'s output). Different widths
    genuinely favor different fields on the same receipt (finer print
    detail vs. more legible small punctuation like a zip code), so the
    caller may run OCR against more than one variant and merge whichever
    fields each finds -- see routes/ocr.py."""
    return binarize_for_receipt(resize_to_width(cropped_receipt, width))


def _trim_margin(img: Image.Image, x_pct: float = 0.04, y_pct: float = 0.01) -> Image.Image:
    """Shave a small margin off each edge of a crop. Even a well-fit
    detected outline can carry a sliver of background right at the
    boundary (an imprecise contour edge, a bit of textured background
    bleeding in) that's enough to throw off OCR's line segmentation --
    trimming a few percent removes that without meaningfully cutting into
    the receipt itself, whose own margins are blank anyway."""
    w, h = img.size
    dx, dy = int(w * x_pct), int(h * y_pct)
    if w - 2 * dx < 20 or h - 2 * dy < 20:
        return img
    return img.crop((dx, dy, w - dx, h - dy))


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
    """Find the receipt against its background and crop tightly to it,
    straightening out any rotation, so OCR sees the receipt itself instead
    of it as a small part of a much larger, busier photo (a desk, a hand,
    a car seat/pants leg, ...).

    Deliberately brightness-based rather than edge-based: a receipt held
    or draped in a photo is rarely a flat, perfectly planar quadrilateral
    (thermal paper curls, gets bent/creased), and its own printed text
    creates a lot of internal edges. Edge detection + "find a clean
    4-sided contour" is fragile against that -- it tends to either latch
    onto a piece of the background or find nothing and silently give up.
    Segmenting by brightness (receipts are bright paper; most real
    backgrounds -- desks, hands, clothing -- are comparatively darker/more
    textured) is far more forgiving of a curled, non-planar receipt.

    The detected region is cropped with a plain rotation (via its rotated
    bounding box), not a full perspective warp: warping a curved surface
    flat would introduce its own distortion, which could easily make
    already-marginal OCR worse rather than better.

    Falls back to the original, uncropped image whenever no sufficiently
    large bright region is found, rather than risk cropping into content.
    """
    mat = _to_cv(img)
    h, w = mat.shape[:2]
    image_area = w * h

    gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    _, mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    # Order matters here. OPEN first strips thin bright structures --
    # crucially, things like a corduroy/textured background's raised
    # ridges catching light as thin streaks -- while they're still
    # separate blobs from the receipt. CLOSE second then fills in the
    # receipt's own internal gaps (text, creases) into one solid blob.
    # Doing this the other way around (close before open, as this used to)
    # lets those thin background streaks bridge straight into the receipt
    # before opening ever gets a chance to strip them, which was merging
    # in ~20%+ of extra background as if it were part of the receipt.
    open_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return img

    largest = max(contours, key=cv2.contourArea)
    # A handheld/draped receipt often occupies well under half the frame
    # once there's margin for safety -- 8% is a low enough bar to still
    # reject "the whole photo happened to threshold bright" false positives.
    if cv2.contourArea(largest) < image_area * 0.08:
        return img

    # Otsu always finds *some* split, even in a photo with no receipt at
    # all -- it'll happily call the relatively-brighter half of a
    # uniformly dim background "foreground". Requiring the detected region
    # to actually be bright in absolute terms (real paper, well-lit, reads
    # ~200+) guards against confidently cropping to the wrong thing.
    region_mask = np.zeros(gray.shape, dtype=np.uint8)
    cv2.drawContours(region_mask, [largest], -1, 255, thickness=cv2.FILLED)
    if cv2.mean(gray, mask=region_mask)[0] < 170:
        return img

    rect = cv2.minAreaRect(largest)
    (_, _), (rect_w, rect_h), _ = rect
    if min(rect_w, rect_h) < 20:
        return img

    box = cv2.boxPoints(rect).astype("float32")
    try:
        # boxPoints is always a true rectangle (just possibly rotated), so
        # warping its corners to an axis-aligned target is a pure rotation
        # + crop, not a distorting perspective transform.
        cropped = _four_point_transform(mat, box)
    except (ValueError, cv2.error):
        return img

    return _trim_margin(_to_pil(cropped))


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
    """Grayscale + denoise + threshold to pure black/white. Printed (often
    thermal) receipts are small, dense text on an already high-contrast
    background -- CLAHE tends to blotch that print into gray mush, while
    binarization is the standard, much more reliable preprocessing for
    Tesseract on document/receipt text.

    Global Otsu thresholding (not adaptive/local thresholding) and a
    stronger denoise pass (h=10, not 7) both came directly out of the grid
    search referenced on MIN_RECEIPT_WIDTH -- adaptive thresholding was
    actually *worse* here once the image is already tightly cropped to
    just the receipt, since there's no more lighting gradient across the
    frame for it to compensate for.

    A small white border is added at the end -- Tesseract's own
    documentation recommends a sensible border, since text running right up
    against the image edge can be misread. It made no measurable difference
    on the specific receipt this pipeline was tuned against (already had
    margin from _trim_margin), but it's effectively free and protects
    against tighter crops on other receipts, so it stays in regardless.
    """
    mat = _to_cv(img)
    gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, h=10)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    bordered = cv2.copyMakeBorder(thresh, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    return Image.fromarray(bordered)


def crop_receipt_from_bytes(data: bytes) -> Image.Image:
    """load -> orient -> downscale -> crop to the receipt's outline. The
    shared first half of the receipt pipeline, split out so a caller that
    wants more than one binarized variant (see prepare_receipt_variant())
    doesn't have to repeat crop detection for each one."""
    return crop_to_receipt(downscale(load_image(data)))


def prepare_for_ocr(data: bytes, mode: str = "odometer") -> Image.Image:
    """Full pipeline. `mode` is "odometer" (dashboard display) or "receipt"
    (printed text):

        odometer: load -> orient -> downscale -> rotation-only deskew ->
                  contrast boost
        receipt:  load -> orient -> downscale -> crop to the receipt's
                  outline (also corrects rotation as part of that) ->
                  upscale back up if the crop left the print small ->
                  binarize
    """
    if mode == "receipt":
        return prepare_receipt_variant(crop_receipt_from_bytes(data), MIN_RECEIPT_WIDTH)

    img = load_image(data)
    img = downscale(img)
    img = deskew(img)
    return grayscale_contrast(img)
