"""PaddleOCRProvider must correctly map the PaddleOCR pipeline's result
shape (rec_texts / rec_scores / rec_boxes) onto OCRResult/OCRWord, and must
configure the pipeline with document-orientation classification, document
unwarping, and text-line orientation all turned on.

Mocked so this runs without the actual `paddleocr` package (and its
`paddlepaddle` model-inference dependency, multi-hundred-MB model weights,
and CPU-only-but-still-slow first-load cost) installed -- this mirrors how
the old Tesseract provider's tests mocked pytesseract rather than
requiring a real Tesseract binary in every dev environment. The result
shape mocked here (a dict-like object indexable by "rec_texts"/
"rec_scores"/"rec_boxes") matches the actual `paddlex.inference.pipelines
.ocr.result.OCRResult` schema PaddleOCR 3.x's `.predict()` returns, not a
guess -- verified directly against the installed package source.
"""
import sys
import types
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from app.ocr.paddle_provider import PaddleOCRProvider
import app.ocr.paddle_provider as paddle_provider_module


@pytest.fixture(autouse=True)
def _reset_cached_engine():
    """The engine is memoized at module level (see _get_engine) so it's
    only ever built once per process -- reset that cache around each test
    so mocks in one test can't leak into another."""
    paddle_provider_module._engine = None
    yield
    paddle_provider_module._engine = None


def _blank_image() -> Image.Image:
    return Image.new("RGB", (10, 10), (255, 255, 255))


def _fake_page(rec_texts, rec_scores, rec_boxes):
    """A minimal stand-in for paddlex's dict-like OCRResult -- only the
    keys PaddleOCRProvider actually reads."""
    return {"rec_texts": rec_texts, "rec_scores": rec_scores, "rec_boxes": np.array(rec_boxes)}


def _install_fake_paddleocr(predict_return):
    """Installs a fake `paddleocr` module in sys.modules (PaddleOCRProvider
    does `from paddleocr import PaddleOCR` lazily, inside _get_engine) so
    the import succeeds without the real package, and returns the mock
    class so call args can be inspected."""
    fake_module = types.ModuleType("paddleocr")
    mock_cls = MagicMock(return_value=MagicMock(predict=MagicMock(return_value=predict_return)))
    fake_module.PaddleOCR = mock_cls
    return patch.dict(sys.modules, {"paddleocr": fake_module}), mock_cls


def test_pipeline_is_configured_with_all_three_preprocessing_flags():
    ctx, mock_cls = _install_fake_paddleocr([_fake_page([], [], [])])
    with ctx:
        PaddleOCRProvider().read(_blank_image())

    assert mock_cls.call_args.kwargs["use_doc_orientation_classify"] is True
    assert mock_cls.call_args.kwargs["use_doc_unwarping"] is True
    assert mock_cls.call_args.kwargs["use_textline_orientation"] is True
    assert mock_cls.call_args.kwargs["ocr_version"] == "PP-OCRv6"


def test_mkldnn_is_disabled():
    # Confirmed directly against a real install: PP-OCRv6's detection
    # model isn't yet on paddlex's oneDNN blocklist and throws a
    # NotImplementedError under it on real predictions (construction
    # alone succeeds, masking the bug until the first real photo).
    ctx, mock_cls = _install_fake_paddleocr([_fake_page([], [], [])])
    with ctx:
        PaddleOCRProvider().read(_blank_image())

    assert mock_cls.call_args.kwargs["enable_mkldnn"] is False


def test_engine_is_built_once_and_reused_across_calls():
    ctx, mock_cls = _install_fake_paddleocr([_fake_page([], [], [])])
    with ctx:
        provider = PaddleOCRProvider()
        provider.read(_blank_image())
        provider.read(_blank_image())

    assert mock_cls.call_count == 1


def test_lines_and_scores_and_boxes_map_onto_ocr_words():
    page = _fake_page(
        rec_texts=["REGULAR", "5.422"],
        rec_scores=[0.965, 0.932],
        rec_boxes=[[100, 50, 180, 70], [300, 50, 360, 70]],
    )
    ctx, _ = _install_fake_paddleocr([page])
    with ctx:
        result = PaddleOCRProvider().read(_blank_image())

    assert [w.text for w in result.words] == ["REGULAR", "5.422"]
    assert result.words[0].confidence == pytest.approx(96.5)
    assert result.words[1].confidence == pytest.approx(93.2)
    assert (result.words[0].left, result.words[0].top) == (100, 50)
    assert (result.words[0].width, result.words[0].height) == (80, 20)
    assert result.mean_confidence == pytest.approx((96.5 + 93.2) / 2)


def test_text_is_lines_joined_by_newline_in_detection_order():
    # receipt_parser.py's line-oriented patterns (splitlines(), adjacent-
    # line bridging) depend on this exact join -- and _line_confidence_at
    # depends on it lining up 1:1 with `words` to map a regex match back
    # to a confidence score.
    page = _fake_page(
        rec_texts=["PRICE/GAL", "$4.199"],
        rec_scores=[0.9, 0.9],
        rec_boxes=[[0, 0, 10, 10], [0, 20, 10, 30]],
    )
    ctx, _ = _install_fake_paddleocr([page])
    with ctx:
        result = PaddleOCRProvider().read(_blank_image())

    assert result.text == "PRICE/GAL\n$4.199"


def test_blank_lines_from_ocr_are_skipped():
    page = _fake_page(rec_texts=["REGULAR", "  ", "5.422"], rec_scores=[0.9, 0.9, 0.9], rec_boxes=[[0, 0, 1, 1]] * 3)
    ctx, _ = _install_fake_paddleocr([page])
    with ctx:
        result = PaddleOCRProvider().read(_blank_image())

    assert [w.text for w in result.words] == ["REGULAR", "5.422"]


def test_no_pages_returned_degrades_to_empty_result():
    ctx, _ = _install_fake_paddleocr([])
    with ctx:
        result = PaddleOCRProvider().read(_blank_image())

    assert result.text == ""
    assert result.words == []
    assert result.mean_confidence is None


def test_config_argument_is_accepted_but_ignored():
    # Unlike Tesseract's PSM flags, PaddleOCR's detector doesn't take a
    # page-layout hint -- `config` stays on the interface only so callers
    # don't need engine-specific branches (see provider.py).
    ctx, mock_cls = _install_fake_paddleocr([_fake_page([], [], [])])
    with ctx:
        PaddleOCRProvider().read(_blank_image(), config="--psm 4")

    assert mock_cls.call_count == 1
