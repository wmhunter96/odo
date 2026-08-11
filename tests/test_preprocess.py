import math

import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.ocr.preprocess import crop_to_receipt


def _synthetic_receipt_photo(angle_deg: float = 12.0) -> tuple[Image.Image, int, int]:
    """A dark 'desk' background with a white rotated rectangle standing in
    for a photographed receipt. Returns (image, receipt_width, receipt_height)."""
    canvas = Image.new("RGB", (800, 800), (30, 30, 30))
    draw = ImageDraw.Draw(canvas)
    cx, cy, half_w, half_h = 400, 400, 150, 250
    angle = math.radians(angle_deg)
    corners = []
    for dx, dy in [(-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h)]:
        rx = dx * math.cos(angle) - dy * math.sin(angle)
        ry = dx * math.sin(angle) + dy * math.cos(angle)
        corners.append((cx + rx, cy + ry))
    draw.polygon(corners, fill=(255, 255, 255))
    return canvas, half_w * 2, half_h * 2


def test_crop_to_receipt_finds_and_flattens_a_rotated_receipt():
    photo, expected_w, expected_h = _synthetic_receipt_photo(angle_deg=12.0)
    cropped = crop_to_receipt(photo)

    # Perspective correction should recover roughly the original
    # (unrotated) receipt dimensions, not the photo's full 800x800 frame.
    assert cropped.size != photo.size
    assert cropped.size[0] == pytest.approx(expected_w, abs=3)
    assert cropped.size[1] == pytest.approx(expected_h, abs=3)

    # The crop should be (almost) entirely the white receipt, not the dark
    # background that surrounded it in the original photo.
    mean_brightness = np.array(cropped.convert("L")).mean()
    assert mean_brightness > 240


def test_crop_to_receipt_falls_back_to_original_when_no_outline_found():
    # A flat, featureless image has no quadrilateral to detect -- cropping
    # blind here would risk cutting into real content, so it must be a
    # no-op instead.
    blank = Image.new("RGB", (400, 300), (128, 128, 128))
    result = crop_to_receipt(blank)
    assert result.size == blank.size


def test_crop_to_receipt_ignores_small_contours():
    # A small white square that doesn't come close to filling the frame
    # shouldn't be mistaken for the receipt itself.
    photo = Image.new("RGB", (800, 800), (30, 30, 30))
    draw = ImageDraw.Draw(photo)
    draw.rectangle([380, 380, 420, 420], fill=(255, 255, 255))  # 40x40 -- well under 20% of the frame
    result = crop_to_receipt(photo)
    assert result.size == photo.size
