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


def test_crop_to_receipt_falls_back_when_nothing_is_actually_bright():
    # Otsu always finds *some* split, even here -- roughly half of this
    # uniformly dim, textured scene will threshold as the "bright" side.
    # Without an absolute-brightness floor, that relatively-brighter half
    # would get confidently (and wrongly) cropped as if it were a receipt.
    rng = np.random.default_rng(0)
    dim_textured = rng.integers(90, 140, size=(300, 400), dtype=np.uint8)
    photo = Image.fromarray(dim_textured).convert("RGB")
    result = crop_to_receipt(photo)
    assert result.size == photo.size


def test_crop_to_receipt_handles_a_textured_background():
    # Mirrors a receipt draped over patterned fabric rather than laid on a
    # plain desk: a bright rectangle over a noisy, moderately-lit backdrop
    # (not dark enough to trip the earlier "nothing found" tests) should
    # still be detected as the dominant bright region.
    rng = np.random.default_rng(1)
    noise = rng.integers(60, 150, size=(800, 800), dtype=np.uint8)
    canvas = Image.fromarray(noise).convert("RGB")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([250, 150, 550, 650], fill=(255, 255, 255))  # 300x500, axis-aligned

    cropped = crop_to_receipt(canvas)
    assert cropped.size != canvas.size
    assert cropped.size[0] == pytest.approx(300, abs=5)
    assert cropped.size[1] == pytest.approx(500, abs=5)


def test_crop_to_receipt_ignores_small_contours():
    # A small white square that doesn't come close to filling the frame
    # shouldn't be mistaken for the receipt itself.
    photo = Image.new("RGB", (800, 800), (30, 30, 30))
    draw = ImageDraw.Draw(photo)
    draw.rectangle([380, 380, 420, 420], fill=(255, 255, 255))  # 40x40 -- well under 20% of the frame
    result = crop_to_receipt(photo)
    assert result.size == photo.size
