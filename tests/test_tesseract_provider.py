"""TesseractProvider must always run with --oem 1 (LSTM engine only),
regardless of what config a caller passes -- the Docker image installs
LSTM-only "best" tessdata (see Dockerfile), which the default --oem 3
("legacy + LSTM combined") isn't built for. Mocked so this runs without an
actual Tesseract binary/tessdata installed (this dev environment's local
Tesseract may not even be the same version as the container's).
"""
from unittest.mock import MagicMock, patch

from PIL import Image

from app.ocr.tesseract_provider import TesseractProvider


def _blank_image() -> Image.Image:
    return Image.new("L", (10, 10), 255)


def test_oem_1_is_always_included_with_no_caller_config():
    with patch("pytesseract.image_to_string", return_value="") as mock_string, patch(
        "pytesseract.image_to_data", return_value={"text": [], "conf": [], "left": [], "top": [], "width": [], "height": []}
    ):
        TesseractProvider().read(_blank_image())
    assert mock_string.call_args.kwargs["config"] == "--oem 1"


def test_oem_1_is_prepended_to_caller_supplied_config():
    with patch("pytesseract.image_to_string", return_value="") as mock_string, patch(
        "pytesseract.image_to_data", return_value={"text": [], "conf": [], "left": [], "top": [], "width": [], "height": []}
    ):
        TesseractProvider().read(_blank_image(), config="--psm 4")
    assert mock_string.call_args.kwargs["config"] == "--oem 1 --psm 4"


def test_word_confidence_and_bbox_are_extracted():
    fake_data = {
        "text": ["", "REGULAR", "5.422"],
        "conf": ["-1", "96.5", "93.2"],
        "left": [0, 100, 300],
        "top": [0, 50, 50],
        "width": [0, 80, 60],
        "height": [0, 20, 20],
    }
    with patch("pytesseract.image_to_string", return_value="REGULAR 5.422"), patch(
        "pytesseract.image_to_data", return_value=fake_data
    ):
        result = TesseractProvider().read(_blank_image(), config="--psm 4")
    assert [w.text for w in result.words] == ["REGULAR", "5.422"]
    assert result.words[0].confidence == 96.5
    assert result.mean_confidence == (96.5 + 93.2) / 2
